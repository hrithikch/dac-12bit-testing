# tools/capture_validate.py
#
# Arms the AD3 logic analyzer, runs the DAC demo, then decodes and validates
# the captured signal against the expected sine pattern.
#
# AD3 connections (as wired):
#   DIO 0 <- ItsyBitsy pin  1  (SPI_SCK_PAT — bit clock)
#   DIO 1 <- ItsyBitsy pin 12  (SPI_SCAN    — HIGH during 20-bit control word)
#   DIO 4 <- ItsyBitsy pin  9  (DIN_PAT     — serial data)
#   DIO 5 <- ItsyBitsy pin 13  (WR_PAT      — HIGH during 256-sample data burst)
#   DIO 6 <- ItsyBitsy pin  7  (EN_PAT      — pattern enable)
#   DIO 7 <- ItsyBitsy SDA     (I2C SDA     — INA219)
#
# Protocol (from firmware):
#   Phase 1 — control word (SPI_SCAN=HIGH):
#     20 bits, MSB first, data valid on CLK rising edge
#   Phase 2 — sine data (WR_PAT=HIGH, SPI_SCAN=LOW):
#     256 x 12 bits, LSB first, data valid on CLK rising edge
#
# Run from repo root with venv active:
#   python tools/capture_validate.py

import ctypes
import csv
import math
import sys
import time
from ctypes import byref, c_int
from pathlib import Path

# ---------------------------------------------------------------------------
# DWF SDK
# ---------------------------------------------------------------------------
DWF_DLL = r"C:\Program Files (x86)\Digilent\WaveForms3\dwf.dll"

try:
    dwf = ctypes.cdll.LoadLibrary(DWF_DLL)
except OSError:
    sys.exit(f"Cannot load DWF library at {DWF_DLL}\nIs WaveForms installed?")

_acqmodeSingle        = c_int(1)
_trigsrcDetectorDigIn = ctypes.c_ubyte(3)
_DwfStateDone         = 2

# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------
DIO_CLK     = 0   # ItsyBitsy pin 1  — SPI_SCK_PAT (bit clock)
DIO_SCAN    = 1   # ItsyBitsy pin 12 — SPI_SCAN (HIGH during control word)
DIO_DIN_PAT = 4   # ItsyBitsy pin 9  — serial data
DIO_WR_PAT  = 5   # ItsyBitsy pin 13 — HIGH during data burst
DIO_EN_PAT  = 6   # ItsyBitsy pin 7  — pattern enable
DIO_SDA     = 7   # ItsyBitsy SDA    — I2C

# ---------------------------------------------------------------------------
# Protocol constants (must match firmware)
# ---------------------------------------------------------------------------
BITS_PER_WORD        = 12
DAC_NUM_SAMPLES      = 256
DAC_CONTROL_BITS     = 20
DAC_CONTROL_WORD_EXP = 0x01586   # expected value to verify control word

# ---------------------------------------------------------------------------
# Capture settings
# ---------------------------------------------------------------------------
SYSTEM_FREQ_HZ  = 100_000_000
SAMPLE_RATE_HZ  = 10_000_000    # 10 MHz — 10x the ~500 kHz bit clock
# Burst duration: 256 words x 12 bits x 2us/bit = ~6ms
# Buffer: 20ms gives comfortable margin; AD3 logic analyzer buffer is limited (~16k-1M samples)
CAPTURE_MS      = 20


def open_device() -> c_int:
    hdwf = c_int()
    dwf.FDwfDeviceOpen(c_int(-1), byref(hdwf))
    if hdwf.value == 0:
        sys.exit("No AD3 found — is it plugged in and not open in WaveForms?")
    print("AD3 opened.")
    return hdwf


def arm_capture(hdwf: c_int) -> int:
    # Query actual device buffer limit
    max_buf = c_int()
    dwf.FDwfDigitalInBufferSizeInfo(hdwf, byref(max_buf))
    n = min(int(SAMPLE_RATE_HZ * CAPTURE_MS / 1000), max_buf.value)
    print(f"AD3 max buffer: {max_buf.value} samples  |  using: {n} samples ({n/SAMPLE_RATE_HZ*1000:.1f} ms)")
    divider = SYSTEM_FREQ_HZ // SAMPLE_RATE_HZ

    dwf.FDwfDigitalInReset(hdwf)
    dwf.FDwfDigitalInAcquisitionModeSet(hdwf, _acqmodeSingle)
    dwf.FDwfDigitalInDividerSet(hdwf, c_int(divider))
    dwf.FDwfDigitalInSampleFormatSet(hdwf, c_int(16))   # 16-bit samples for 16 DIO channels
    dwf.FDwfDigitalInBufferSizeSet(hdwf, c_int(n))

    # Trigger immediately via PC (software trigger) to verify capture pipeline,
    # then switch to hardware trigger once pipeline is confirmed.
    dwf.FDwfDigitalInTriggerSourceSet(hdwf, ctypes.c_ubyte(1))  # trigsrcPC
    dwf.FDwfDigitalInConfigure(hdwf, c_int(False), c_int(True))
    dwf.FDwfDigitalInConfigure(hdwf, c_int(False), c_int(False))  # force PC trigger
    print(f"Armed: {n} samples @ {SAMPLE_RATE_HZ/1e6:.0f} MHz  |  PC (immediate) trigger")
    return n


def wait_for_capture(hdwf: c_int, timeout_s: float = 15.0) -> None:
    sts = ctypes.c_byte()
    t0 = time.time()
    last_sts = None
    while True:
        dwf.FDwfDigitalInStatus(hdwf, c_int(1), byref(sts))
        if sts.value != last_sts:
            print(f"  AD3 status: {sts.value}")
            last_sts = sts.value
        if sts.value == _DwfStateDone:
            print("Capture complete.")
            return
        if time.time() - t0 > timeout_s:
            szerr = ctypes.create_string_buffer(512)
            dwf.FDwfGetLastErrorMsg(szerr)
            sys.exit(f"Capture timed out (status={sts.value}). Last error: {szerr.value}")
        time.sleep(0.05)


def read_samples(hdwf: c_int, n: int) -> list[int]:
    buf = (ctypes.c_uint16 * n)()
    dwf.FDwfDigitalInStatusData(hdwf, buf, c_int(n * 2))
    return list(buf)


def save_raw_csv(samples: list[int], path: Path) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sample_idx", "raw_hex", "CLK", "SCAN", "DIN_PAT", "WR_PAT", "EN_PAT", "SDA"])
        for i, s in enumerate(samples):
            w.writerow([
                i, hex(s),
                (s >> DIO_CLK)     & 1,
                (s >> DIO_SCAN)    & 1,
                (s >> DIO_DIN_PAT) & 1,
                (s >> DIO_WR_PAT)  & 1,
                (s >> DIO_EN_PAT)  & 1,
                (s >> DIO_SDA)     & 1,
            ])
    print(f"Raw CSV -> {path}")


def _rising_edges(signal: list[int], start: int, end: int) -> list[int]:
    """Return sample indices of rising edges of signal within [start, end)."""
    return [
        i for i in range(max(1, start), min(end, len(signal)))
        if signal[i-1] == 0 and signal[i] == 1
    ]


def decode_control_word(samples: list[int]) -> int | None:
    """
    Decode the 20-bit control word sent MSB-first during SPI_SCAN=HIGH.
    Samples DIN_PAT on each CLK rising edge.
    """
    clk  = [(s >> DIO_CLK)     & 1 for s in samples]
    scan = [(s >> DIO_SCAN)    & 1 for s in samples]
    din  = [(s >> DIO_DIN_PAT) & 1 for s in samples]

    scan_start = next((i for i in range(1, len(scan)) if scan[i-1] == 0 and scan[i] == 1), None)
    scan_end   = next((i for i in range(scan_start + 1, len(scan)) if scan[i] == 0), len(scan)) if scan_start else None

    if scan_start is None:
        print("Warning: SPI_SCAN never went HIGH — control word not captured.")
        return None

    edges = _rising_edges(clk, scan_start, scan_end)
    if len(edges) < DAC_CONTROL_BITS:
        print(f"Warning: only {len(edges)} clock edges in SCAN window, expected {DAC_CONTROL_BITS}.")

    bits = [din[e] for e in edges[:DAC_CONTROL_BITS]]
    word = 0
    for b in bits:            # MSB first
        word = (word << 1) | b

    match = "OK" if word == DAC_CONTROL_WORD_EXP else f"MISMATCH (expected 0x{DAC_CONTROL_WORD_EXP:05X})"
    print(f"Control word: 0x{word:05X}  ({DAC_CONTROL_BITS} bits, MSB first)  [{match}]")
    return word


def decode_sine_words(samples: list[int]) -> list[int]:
    """
    Decode 256 x 12-bit words from DIN_PAT during WR_PAT=HIGH window.
    Samples DIN_PAT on each CLK rising edge. Data is LSB first.
    """
    clk = [(s >> DIO_CLK)     & 1 for s in samples]
    wr  = [(s >> DIO_WR_PAT)  & 1 for s in samples]
    din = [(s >> DIO_DIN_PAT) & 1 for s in samples]

    wr_start = next((i for i in range(1, len(wr)) if wr[i-1] == 0 and wr[i] == 1), None)
    if wr_start is None:
        sys.exit("WR_PAT never went HIGH — no data burst captured.")

    wr_end = next((i for i in range(wr_start + 1, len(wr)) if wr[i] == 0), len(wr))

    burst_ms = (wr_end - wr_start) / SAMPLE_RATE_HZ * 1000
    edges = _rising_edges(clk, wr_start, wr_end)
    print(f"WR_PAT HIGH: samples {wr_start}–{wr_end}  ({burst_ms:.2f} ms)")
    print(f"Clock edges in burst: {len(edges)}  (expected {DAC_NUM_SAMPLES * BITS_PER_WORD})")

    words: list[int] = []
    for bit_idx, edge in enumerate(edges[:DAC_NUM_SAMPLES * BITS_PER_WORD]):
        bit = din[edge]
        if bit_idx % BITS_PER_WORD == 0:
            words.append(0)
        words[-1] |= (bit << (bit_idx % BITS_PER_WORD))  # LSB first

    return words


def expected_sine(f_out: float, f_sample: float) -> list[int]:
    M = (f_out * DAC_NUM_SAMPLES) / f_sample
    return [
        int(round(2047.5 * math.sin(2.0 * math.pi * M * k / DAC_NUM_SAMPLES) + 2047.5))
        for k in range(DAC_NUM_SAMPLES)
    ]


def compare(decoded: list[int], expected: list[int]) -> list[tuple]:
    n = min(len(decoded), len(expected))
    mismatches = [(i, decoded[i], expected[i]) for i in range(n) if decoded[i] != expected[i]]
    if not mismatches:
        print(f"OK — all {n} words match expected sine pattern.")
    else:
        print(f"{len(mismatches)}/{n} words mismatched (first 10):")
        for i, got, exp in mismatches[:10]:
            print(f"  word[{i:3d}]  got=0x{got:03X} ({got:4d})  expected=0x{exp:03X} ({exp:4d})")
    return mismatches


def save_decoded_csv(decoded: list[int], expected: list[int], path: Path) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["word_idx", "decoded", "expected", "match"])
        for i in range(min(len(decoded), len(expected))):
            w.writerow([i, decoded[i], expected[i], decoded[i] == expected[i]])
    print(f"Decoded words -> {path}")


def run_demo() -> tuple[float, float]:
    from dacdemo import config as cfg_mod
    from dacdemo.board_control import BoardSession

    cfg      = cfg_mod.load()
    port     = cfg["hardware"]["port"]
    baudrate = cfg["hardware"]["baudrate"]
    f_out    = cfg["dac"]["f_out"]
    f_sample = cfg["dac"]["f_sample"]

    print(f"Connecting to board on {port}...")
    sess = BoardSession.open(port=port, baudrate=baudrate)
    try:
        print(f"Sending DAC_LOAD_SINE: f_out={f_out/1e6:.3f} MHz  f_sample={f_sample/1e9:.5f} GHz")
        print(f"  dac_load_sine      -> {sess.dac_load_sine(f_out, f_sample)}")
        print(f"  dac_enable_pattern -> {sess.dac_enable_pattern()}")
    finally:
        sess.close()
    return f_out, f_sample


if __name__ == "__main__":
    out_dir = Path("data/captures")
    out_dir.mkdir(parents=True, exist_ok=True)

    hdwf = open_device()
    try:
        n_samples = arm_capture(hdwf)
        print("\nRunning demo — waiting for SPI_SCAN trigger...")
        f_out, f_sample = run_demo()
        wait_for_capture(hdwf, timeout_s=15.0)
        samples = read_samples(hdwf, n_samples)
    finally:
        dwf.FDwfDeviceClose(hdwf)

    save_raw_csv(samples, out_dir / "capture_raw.csv")

    print("\n--- Control word ---")
    decode_control_word(samples)

    print("\n--- Sine data ---")
    decoded = decode_sine_words(samples)
    print(f"Decoded {len(decoded)} words. First 8: {decoded[:8]}")

    exp = expected_sine(f_out, f_sample)
    print(f"Expected first 8:      {exp[:8]}")

    print("\n--- Comparison ---")
    mismatches = compare(decoded, exp)
    save_decoded_csv(decoded, exp, out_dir / "decoded_words.csv")
