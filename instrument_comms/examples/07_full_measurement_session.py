"""
Example 07 — Full measurement session: all instruments together.

Shows the complete sequence used in PLL sweep testing:
  1. Load all instruments (VISA + AD2)
  2. Configure power supplies and signal generator
  3. Send AD2 reset pulse to DUT
  4. Collect scope measurements (frequency, eye, jitter, phase noise, power)
  5. Iterate over a voltage/frequency grid
  6. Save results to CSV
  7. Tear down cleanly

Adapt the ADDRESSES and sweep parameters to your setup.

Requirements: pyvisa, pandas (for CSV writing)
"""

import csv
import pathlib
import sys
from ctypes import cdll, c_int
from time import sleep

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from instruments.analog_discovery import AnalogDiscovery
from instruments.keysight_scope import KeysightOscilloscope
from instruments.keithley_supply import KeithleyPowerSupply
from instruments.keysight_supply import KeysightPowerSupply
from instruments.rs_siggen import RohdeAndSchwarzSignalGenerator
import pyvisa

# ── Instrument addresses — update these ──────────────────────────────────────
SCOPE_ADDR    = "TCPIP0::192.168.1.100::hislip0::INSTR"
SIGGEN_ADDR   = "TCPIP0::192.168.1.101::inst0::INSTR"
KS_SUPPLY_ADDR = "TCPIP0::192.168.1.102::inst0::INSTR"
KEITH_ADDR    = "USB0::0x05E6::0x2230::1234567::INSTR"

OUTPUT_CSV = pathlib.Path("results.csv")

# ── Sweep parameters ──────────────────────────────────────────────────────────
VPW_VALUES   = [1.0, 1.1, 1.2]      # V
VNW_VALUES   = [-0.8, -0.9, -1.0]   # V  (sign handled by supply driver)
FREQ_VALUES  = [65_000_000, 68_825_000, 72_000_000]  # Hz

# ── Fixed configuration ───────────────────────────────────────────────────────
SIG_GEN_LEVEL    = "0 dBm"
KS_V1, KS_V2, KS_V3 = 1.8, 0.8, 0.45   # Keysight supply channel voltages
AD_DC_VOLTAGE    = 1.8     # DC bias on AD2 W1
AD_V_PLUS        = 3.3     # AD2 onboard V+ supply
RESET_CHANNEL    = c_int(1)  # AD2 W2 used for reset pulse
RESET_PULSE_LEN  = 0.010     # 10 ms
RESET_AMPLITUDE  = 1.65      # ±1.65 V → 0–3.3 V swing
POST_RESET_SLEEP = 2.0       # seconds to wait after reset before measuring


def open_instruments(rm):
    """Open all VISA resources and return a dict of raw resources."""
    print("Opening instruments...")
    resources = {}

    resources["scope_raw"]     = rm.open_resource(SCOPE_ADDR);     resources["scope_raw"].timeout     = 90000
    resources["siggen"]        = rm.open_resource(SIGGEN_ADDR);    resources["siggen"].timeout        = 50000
    resources["ks_supply"]     = rm.open_resource(KS_SUPPLY_ADDR); resources["ks_supply"].timeout     = 30000
    resources["keithley"]      = rm.open_resource(KEITH_ADDR);     resources["keithley"].timeout      = 30000

    # Load DWF library (Analog Discovery 2)
    if sys.platform.startswith("win"):
        dwf = cdll.dwf
    elif sys.platform.startswith("darwin"):
        dwf = cdll.LoadLibrary("/Library/Frameworks/dwf.framework/dwf")
    else:
        dwf = cdll.LoadLibrary("libdwf.so")

    ad = AnalogDiscovery(dwf)
    if not ad.open_and_init_device():
        raise RuntimeError("Could not open Analog Discovery device")
    resources["ad"] = ad

    print("All instruments opened.")
    return resources


def setup_instruments(res):
    """Configure all instruments to initial test conditions."""
    scope_raw  = res["scope_raw"]
    siggen     = res["siggen"]
    ks_supply  = res["ks_supply"]
    keithley   = res["keithley"]
    ad         = res["ad"]

    # Signal generator: CW mode, set level, RF on
    siggen.write("OUTPut OFF")
    siggen.write("*RST")
    siggen.write("SOURce1:FREQ:MODE CW")
    siggen.write(f"SOURce1:POWer {SIG_GEN_LEVEL}")
    siggen.write("OUTPut ON")

    # AD2: DC bias on W1, V+ rail
    ad.analog_out_dc(c_int(0), AD_DC_VOLTAGE)
    ad.set_positive_power_supply(AD_V_PLUS)

    # Keysight supply: set voltages, enable
    ks_supply.write(f"VOLTage {KS_V1}, (@1)")
    ks_supply.write(f"VOLTage {KS_V2}, (@2)")
    ks_supply.write(f"VOLTage {KS_V3}, (@3)")
    ks_supply.write("OUTPut 1, (@1:3)")

    # Keithley: enable output (voltages set per step)
    keithley.write("OUTPut:TRACK 0")   # independent channels
    keithley.write("OUTPut 1")

    # Oscilloscope: initialize
    scope = KeysightOscilloscope(scope_raw)
    scope_raw.clear()
    scope.clear_status()
    scope.turn_off_system_header()
    scope.do_command(":MEASure:SOURce CHANnel1")
    scope.do_command(":ACQuire:AVERage 0")
    scope.do_command(":ACQuire:POINts 10000")
    scope.do_command(":MEASure:SENDvalid ON")
    _ = scope.do_query_number("*OPC?")

    print("Instruments configured.")
    return scope


def send_reset(ad):
    """Send a reset pulse via AD2 W2 and wait for DUT to settle."""
    ad.analog_out_single_pulse(RESET_CHANNEL, RESET_PULSE_LEN, RESET_AMPLITUDE, 0)
    sleep(POST_RESET_SLEEP)


def set_voltages(keithley, vpw, vnw):
    """Set Keithley VPW (CH1) and VNW (CH2) bias voltages."""
    keithley.write("INSTrument:NSELect 2")
    keithley.write(f"VOLTage {abs(vnw)}")
    keithley.write("INSTrument:NSELect 1")
    keithley.write(f"VOLTage {abs(vpw)}")


def collect_measurements(scope, ks_supply, keithley, vpw, vnw, freq):
    """
    Collect a full set of measurements from scope and power supplies.

    Returns a flat dict suitable for writing to a CSV row.
    """
    # Ensure scope is running
    scope.do_command(":RUN")
    scope.set_timeout(90000)

    # Batch scope query
    queries = [
        ":MEASure:FREQuency?",
        ":MEASure:CGRade:EHEight?",
        ":MEASure:CGRade:EWIDth?",
        ":MEASure:RJDJ:ALL?",
        ":MEASure:RISetime?",
        ":MEASure:FALLtime?",
        ":MEASure:DUTYcycle?",
        ":MEASure:VPP?",
    ]
    raw = scope.do_query_string(";".join(queries) + ";")
    parts = raw.split(";")

    def safe_get(lst, i):
        return lst[i].strip() if i < len(lst) else "ERROR"

    row = {
        "vpw":                  vpw,
        "vnw":                  vnw,
        "input_freq_hz":        freq,
        "output_freq_hz":       safe_get(parts, 0),
        "eye_height_v":         safe_get(parts, 1),
        "eye_width_s":          safe_get(parts, 2),
        "rjdj_all":             safe_get(parts, 3),
        "rise_time_s":          safe_get(parts, 4),
        "fall_time_s":          safe_get(parts, 5),
        "duty_cycle_pct":       safe_get(parts, 6),
        "vpp_v":                safe_get(parts, 7),
    }

    # Phase noise markers
    scope.set_timeout(30000)
    for marker_num in range(1, 11):
        x = scope.do_query_string(f":MARKer{marker_num}:X:POSition?").strip()
        y = scope.do_query_string(f":MARKer{marker_num}:Y:POSition?").strip()
        if "E+37" in x or "E+37" in y:
            break
        row[f"pn_marker_{marker_num}_x"] = x
        row[f"pn_marker_{marker_num}_y"] = y

    # Power supply measurements
    keithley.write("INSTrument:NSELect 1")
    row["keith_ch1_power_w"] = keithley.query("MEASure:POWer?").strip()
    keithley.write("INSTrument:NSELect 2")
    row["keith_ch2_power_w"] = keithley.query("MEASure:POWer?").strip()

    for ch in (1, 2, 3):
        v = ks_supply.query(f"MEASure:VOLTage? CH{ch}").strip()
        i = ks_supply.query(f"MEASure:CURRent? CH{ch}").strip()
        row[f"ks_ch{ch}_voltage_v"] = v
        row[f"ks_ch{ch}_current_a"] = i
        try:
            row[f"ks_ch{ch}_power_w"] = f"{float(v) * float(i):.6e}"
        except ValueError:
            row[f"ks_ch{ch}_power_w"] = "CALC_ERROR"

    return row


def close_instruments(res):
    """Turn off outputs and close all connections."""
    try:
        res["ks_supply"].write("OUTPut 0, (@1:3)")
        res["ks_supply"].close()
    except Exception as e:
        print(f"Warning closing Keysight supply: {e}")
    try:
        res["keithley"].write("OUTPut 0")
        res["keithley"].close()
    except Exception as e:
        print(f"Warning closing Keithley: {e}")
    try:
        res["siggen"].write("OUTPut OFF")
        res["siggen"].close()
    except Exception as e:
        print(f"Warning closing signal gen: {e}")
    try:
        res["scope_raw"].close()
    except Exception as e:
        print(f"Warning closing scope: {e}")
    try:
        res["ad"].close_device()
    except Exception as e:
        print(f"Warning closing AD2: {e}")
    print("All instruments closed.")


# ── Main sweep ────────────────────────────────────────────────────────────────
def main():
    rm = pyvisa.ResourceManager()
    res = open_instruments(rm)
    scope = setup_instruments(res)

    all_rows = []
    total = len(VPW_VALUES) * len(VNW_VALUES) * len(FREQ_VALUES)
    step = 0

    try:
        for vpw in VPW_VALUES:
            for vnw in VNW_VALUES:
                # Apply bias voltages
                set_voltages(res["keithley"], vpw, vnw)

                # Send reset pulse to DUT and wait for lock
                send_reset(res["ad"])

                for freq in FREQ_VALUES:
                    step += 1
                    print(f"\n[{step}/{total}] VPW={vpw}V  VNW={vnw}V  Freq={freq/1e6:.3f}MHz")

                    # Set signal generator frequency
                    res["siggen"].write(f"SOURce1:FREQuency:CW {int(freq)}")

                    # Autoscale scope
                    scope.do_command(":AUToscale:VERTical CHANnel1")
                    _ = scope.do_query_number("*OPC?")
                    sleep(1)  # let waveform stabilize

                    # Collect measurements
                    row = collect_measurements(
                        scope, res["ks_supply"], res["keithley"], vpw, vnw, freq
                    )
                    all_rows.append(row)
                    print(f"  Output freq: {row['output_freq_hz']}  Eye H: {row['eye_height_v']}")

    finally:
        close_instruments(res)
        rm.close()

    # ── Write CSV ─────────────────────────────────────────────────────────────
    if all_rows:
        fieldnames = list(all_rows[0].keys())
        with open(OUTPUT_CSV, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_rows)
        print(f"\nResults written to {OUTPUT_CSV}  ({len(all_rows)} rows)")


if __name__ == "__main__":
    main()
