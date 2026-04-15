# host/dacdemo/ad3_capture.py
#
# Core AD3 digital capture logic for ItsyBitsy SPI signals.
# Used by:
#   tools/capture_validate.py  — standalone runner
#   dacdemo capture            — CLI subcommand
#
# AD3 connections (as wired):
#   DIO 0 <- ItsyBitsy pin  1  (SPI_SCK_PAT — bit clock)
#   DIO 1 <- ItsyBitsy pin 12  (SPI_SCAN    — HIGH during 20-bit control word)
#   DIO 4 <- ItsyBitsy pin  9  (DIN_PAT     — serial data)
#   DIO 5 <- ItsyBitsy pin 13  (WR_PAT      — HIGH during 256-sample data burst)
#   DIO 6 <- ItsyBitsy pin  7  (EN_PAT      — pattern enable)
#   DIO 7 <- ItsyBitsy SDA     (I2C SDA     — INA219 monitoring)
#
# Protocol (from firmware):
#   Phase 1 — control word (SPI_SCAN=HIGH):
#     20 bits, MSB first, data valid on CLK rising edge
#   Phase 2 — sine data (WR_PAT=HIGH, SPI_SCAN=LOW):
#     256 x 12 bits, LSB first, data valid on CLK rising edge

import ctypes
import csv
import math
import sys
import time
from ctypes import byref, c_int
from pathlib import Path

# ---------------------------------------------------------------------------
# DWF library
# ---------------------------------------------------------------------------
DWF_DLL = r"C:\Program Files (x86)\Digilent\WaveForms3\dwf.dll"

# ---------------------------------------------------------------------------
# DIO channel assignments (must match wiring above)
# ---------------------------------------------------------------------------
DIO_CLK     = 0   # SPI_SCK_PAT — bit clock
DIO_SCAN    = 1   # SPI_SCAN    — HIGH during 20-bit control word
DIO_DIN_PAT = 4   # DIN_PAT     — serial data
DIO_WR_PAT  = 5   # WR_PAT      — HIGH during 256-sample data burst
DIO_EN_PAT  = 6   # EN_PAT      — pattern enable
DIO_SDA     = 7   # I2C SDA     — INA219

# ---------------------------------------------------------------------------
# Protocol constants (must match firmware)
# ---------------------------------------------------------------------------
BITS_PER_WORD        = 12
DAC_NUM_SAMPLES      = 256
DAC_CONTROL_BITS     = 20
DAC_CONTROL_WORD_EXP = 0x01586

# ---------------------------------------------------------------------------
# Capture settings
# ---------------------------------------------------------------------------
SYSTEM_FREQ_HZ = 100_000_000
SAMPLE_RATE_HZ = 10_000_000   # 10 MHz — 10x the ~500 kHz bit clock
CAPTURE_MS     = 20           # 20 ms window — covers the full 256 x 12-bit burst

# DWF constants
_ACQMODE_SINGLE          = c_int(1)
_DWF_STATE_DONE          = 2
_TRIGSRC_DETECTOR_DIGIN  = ctypes.c_ubyte(3)  # hardware trigger from digital input detector


# ---------------------------------------------------------------------------
# Device management
# ---------------------------------------------------------------------------

def _load_dwf() -> ctypes.CDLL:
    try:
        return ctypes.cdll.LoadLibrary(DWF_DLL)
    except OSError:
        sys.exit(f"Cannot load DWF library at {DWF_DLL}\nIs WaveForms installed?")


def _open_device(dwf) -> c_int:
    hdwf = c_int()
    dwf.FDwfDeviceOpen(c_int(-1), byref(hdwf))
    if hdwf.value == 0:
        sys.exit("No AD3 found — is it plugged in and not open in WaveForms?")
    print("AD3 opened.")
    return hdwf


def _arm_capture(dwf, hdwf: c_int) -> int:
    """
    Configure and arm the AD3 digital logic analyzer.

    Trigger: rising edge of SPI_SCAN (DIO 1) — fires the moment the firmware
    begins clocking out the 20-bit control word, so the entire transaction
    lands in the capture window.
    """
    max_buf = c_int()
    dwf.FDwfDigitalInBufferSizeInfo(hdwf, byref(max_buf))
    n = min(int(SAMPLE_RATE_HZ * CAPTURE_MS / 1000), max_buf.value)
    print(f"AD3 max buffer: {max_buf.value} samples  |  using: {n} samples ({n / SAMPLE_RATE_HZ * 1000:.1f} ms)")
    divider = SYSTEM_FREQ_HZ // SAMPLE_RATE_HZ

    dwf.FDwfDigitalInReset(hdwf)
    dwf.FDwfDigitalInAcquisitionModeSet(hdwf, _ACQMODE_SINGLE)
    dwf.FDwfDigitalInDividerSet(hdwf, c_int(divider))
    dwf.FDwfDigitalInSampleFormatSet(hdwf, c_int(16))  # 16-bit samples, one per DIO channel
    dwf.FDwfDigitalInBufferSizeSet(hdwf, c_int(n))

    # Hardware trigger on DIO_SCAN rising edge — no timing dependency on host-side delays
    dwf.FDwfDigitalInTriggerSourceSet(hdwf, _TRIGSRC_DETECTOR_DIGIN)
    dwf.FDwfDigitalInTriggerSet(
        hdwf,
        c_int(0),              # levelLow  mask — none
        c_int(0),              # levelHigh mask — none
        c_int(1 << DIO_SCAN),  # edgeRise  mask — trigger on SPI_SCAN rising edge
        c_int(0),              # edgeFall  mask — none
    )
    dwf.FDwfDigitalInConfigure(hdwf, c_int(False), c_int(True))
    print(f"Armed: {n} samples @ {SAMPLE_RATE_HZ / 1e6:.0f} MHz  |  trigger: DIO_SCAN rising edge")
    return n


def _wait_for_capture(dwf, hdwf: c_int, timeout_s: float = 15.0) -> None:
    sts = ctypes.c_byte()
    t0 = time.time()
    last_sts = None
    while True:
        dwf.FDwfDigitalInStatus(hdwf, c_int(1), byref(sts))
        if sts.value != last_sts:
            print(f"  AD3 status: {sts.value}")
            last_sts = sts.value
        if sts.value == _DWF_STATE_DONE:
            print("Capture complete.")
            return
        if time.time() - t0 > timeout_s:
            szerr = ctypes.create_string_buffer(512)
            dwf.FDwfGetLastErrorMsg(szerr)
            sys.exit(f"Capture timed out (status={sts.value}). Last error: {szerr.value}")
        time.sleep(0.05)


def _read_samples(dwf, hdwf: c_int, n: int) -> list:
    buf = (ctypes.c_uint16 * n)()
    dwf.FDwfDigitalInStatusData(hdwf, buf, c_int(n * 2))
    return list(buf)


# ---------------------------------------------------------------------------
# CSV output
# ---------------------------------------------------------------------------

def save_raw_csv(samples: list, path: Path) -> None:
    """Write raw 16-bit DIO samples with per-channel bit columns."""
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


def save_decoded_csv(decoded: list, expected: list, path: Path) -> None:
    """Write decoded vs expected word comparison CSV."""
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["word_idx", "decoded", "expected", "match"])
        for i in range(min(len(decoded), len(expected))):
            w.writerow([i, decoded[i], expected[i], decoded[i] == expected[i]])
    print(f"Decoded words -> {path}")


# ---------------------------------------------------------------------------
# Decode
# ---------------------------------------------------------------------------

def _rising_edges(signal: list, start: int, end: int) -> list:
    return [
        i for i in range(max(1, start), min(end, len(signal)))
        if signal[i - 1] == 0 and signal[i] == 1
    ]


def decode_control_word(samples: list) -> int | None:
    """
    Decode the 20-bit control word sent MSB-first during SPI_SCAN=HIGH.
    Samples DIN_PAT on each CLK rising edge.
    """
    clk  = [(s >> DIO_CLK)     & 1 for s in samples]
    scan = [(s >> DIO_SCAN)    & 1 for s in samples]
    din  = [(s >> DIO_DIN_PAT) & 1 for s in samples]

    scan_start = next((i for i in range(1, len(scan)) if scan[i - 1] == 0 and scan[i] == 1), None)
    if scan_start is None:
        print("Warning: SPI_SCAN never went HIGH — control word not captured.")
        return None
    scan_end = next((i for i in range(scan_start + 1, len(scan)) if scan[i] == 0), len(scan))

    edges = _rising_edges(clk, scan_start, scan_end)
    if len(edges) < DAC_CONTROL_BITS:
        print(f"Warning: only {len(edges)} clock edges in SCAN window, expected {DAC_CONTROL_BITS}.")

    bits = [din[e] for e in edges[:DAC_CONTROL_BITS]]
    word = 0
    for b in bits:
        word = (word << 1) | b

    match = "OK" if word == DAC_CONTROL_WORD_EXP else f"MISMATCH (expected 0x{DAC_CONTROL_WORD_EXP:05X})"
    print(f"Control word: 0x{word:05X}  ({DAC_CONTROL_BITS} bits, MSB first)  [{match}]")
    return word


def decode_sine_words(samples: list) -> list:
    """
    Decode 256 x 12-bit words from DIN_PAT during WR_PAT=HIGH.
    Data is LSB first, clocked on CLK rising edge.
    """
    clk = [(s >> DIO_CLK)    & 1 for s in samples]
    wr  = [(s >> DIO_WR_PAT) & 1 for s in samples]
    din = [(s >> DIO_DIN_PAT) & 1 for s in samples]

    wr_start = next((i for i in range(1, len(wr)) if wr[i - 1] == 0 and wr[i] == 1), None)
    if wr_start is None:
        sys.exit("WR_PAT never went HIGH — no data burst captured.")
    wr_end = next((i for i in range(wr_start + 1, len(wr)) if wr[i] == 0), len(wr))

    burst_ms = (wr_end - wr_start) / SAMPLE_RATE_HZ * 1000
    edges = _rising_edges(clk, wr_start, wr_end)
    print(f"WR_PAT HIGH: samples {wr_start}–{wr_end}  ({burst_ms:.2f} ms)")
    print(f"Clock edges in burst: {len(edges)}  (expected {DAC_NUM_SAMPLES * BITS_PER_WORD})")

    words: list = []
    for bit_idx, edge in enumerate(edges[:DAC_NUM_SAMPLES * BITS_PER_WORD]):
        bit = din[edge]
        if bit_idx % BITS_PER_WORD == 0:
            words.append(0)
        words[-1] |= (bit << (bit_idx % BITS_PER_WORD))

    return words


def expected_sine(f_out: float, f_sample: float) -> list:
    """Compute the expected 256-sample 12-bit sine pattern for given frequencies."""
    M = (f_out * DAC_NUM_SAMPLES) / f_sample
    return [
        int(round(2047.5 * math.sin(2.0 * math.pi * M * k / DAC_NUM_SAMPLES) + 2047.5))
        for k in range(DAC_NUM_SAMPLES)
    ]


def compare(decoded: list, expected: list) -> list:
    """Compare decoded words against expected. Returns list of (index, got, expected) mismatches."""
    n = min(len(decoded), len(expected))
    mismatches = [(i, decoded[i], expected[i]) for i in range(n) if decoded[i] != expected[i]]
    if not mismatches:
        print(f"OK — all {n} words match expected sine pattern.")
    else:
        print(f"{len(mismatches)}/{n} words mismatched (first 10):")
        for i, got, exp in mismatches[:10]:
            print(f"  word[{i:3d}]  got=0x{got:03X} ({got:4d})  expected=0x{exp:03X} ({exp:4d})")
    return mismatches


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run(port: str, baudrate: int, f_out: float, f_sample: float,
        output_dir: Path, validate: bool = True) -> dict:
    """
    Full capture → decode → (validate) sequence.

    1. Arms the AD3 logic analyzer with a hardware trigger on SPI_SCAN rising edge.
    2. Triggers the DAC demo over serial (load sine + enable pattern).
    3. Waits for the SPI transaction to complete and the capture to finish.
    4. Saves capture_raw.csv with all DIO channels.
    5. Decodes the control word and 256 sine words.
    6. If validate=True, compares against the expected pattern and saves decoded_words.csv.

    Returns a dict: {raw_csv, decoded_csv, control_word, mismatches}.
    """
    from dacdemo.board_control import BoardSession

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    dwf = _load_dwf()
    hdwf = _open_device(dwf)
    try:
        n_samples = _arm_capture(dwf, hdwf)
        print(f"\nConnecting to board on {port}...")
        sess = BoardSession.open(port=port, baudrate=baudrate)
        try:
            print(f"  dac_load_sine      -> {sess.dac_load_sine(f_out, f_sample)}")
            print(f"  dac_enable_pattern -> {sess.dac_enable_pattern()}")
        finally:
            sess.close()
        print("Waiting for SPI_SCAN trigger...")
        _wait_for_capture(dwf, hdwf, timeout_s=15.0)
        samples = _read_samples(dwf, hdwf, n_samples)
    finally:
        dwf.FDwfDeviceClose(hdwf)

    raw_path = output_dir / "capture_raw.csv"
    save_raw_csv(samples, raw_path)

    print("\n--- Control word ---")
    cw = decode_control_word(samples)

    print("\n--- Sine data ---")
    decoded = decode_sine_words(samples)
    print(f"Decoded {len(decoded)} words.  First 8: {decoded[:8]}")

    result: dict = {"raw_csv": raw_path, "control_word": cw, "decoded_csv": None, "mismatches": []}

    if validate:
        exp = expected_sine(f_out, f_sample)
        print(f"Expected first 8:       {exp[:8]}")
        print("\n--- Comparison ---")
        mismatches = compare(decoded, exp)
        decoded_path = output_dir / "decoded_words.csv"
        save_decoded_csv(decoded, exp, decoded_path)
        result["decoded_csv"] = decoded_path
        result["mismatches"] = mismatches

    return result
