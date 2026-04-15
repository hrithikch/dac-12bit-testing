"""
Example 02 — Keysight MXR404A oscilloscope: setup, measurements, screenshot.

Demonstrates:
  - Opening a LAN connection
  - Oscilloscope initialization (clear, header off, acquire config)
  - Taking eye diagram measurements (CGRade)
  - Taking jitter measurements (RJDJ)
  - Taking time/voltage measurements (rise, fall, duty, VPP, frequency)
  - Reading phase noise markers
  - Capturing a PNG screenshot

Requirements: pyvisa, Keysight IO Libraries Suite (or NI-VISA with HiSLIP support).
"""

import pathlib
import pyvisa
import sys

# Add parent directory so we can import from instruments/
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from instruments.keysight_scope import KeysightOscilloscope

SCOPE_ADDRESS = "TCPIP0::192.168.1.100::hislip0::INSTR"  # update IP

rm = pyvisa.ResourceManager()
scope_resource = rm.open_resource(SCOPE_ADDRESS)

scope = KeysightOscilloscope(scope_resource, debug=False)
scope.set_timeout(60000)

# ── Initialize ────────────────────────────────────────────────────────────────
scope_resource.clear()
scope.clear_status()                          # *CLS
scope.turn_off_system_header()                # :SYSTem:HEADer 0
scope.do_command(":MEASure:SOURce CHANnel1")  # set measurement source
scope.do_command(":ACQuire:AVERage 0")        # no averaging
scope.do_command(":ACQuire:POINts 10000")     # acquisition depth
scope.do_command(":MEASure:SENDvalid ON")     # include status with each result
_ = scope.do_query_number("*OPC?")           # wait for operation complete

# ── Start acquisition ─────────────────────────────────────────────────────────
scope.do_command(":RUN")

# ── Autoscale then wait ───────────────────────────────────────────────────────
scope.do_command(":AUToscale:VERTical CHANnel1")
_ = scope.do_query_number("*OPC?")

# ── Individual measurements ───────────────────────────────────────────────────
freq = scope.do_query_number(":MEASure:FREQuency?")
print(f"Frequency:    {freq} Hz")

eye_h = scope.get_eye_height()
print(f"Eye Height:   {eye_h} V")

eye_w = scope.get_eye_width()
print(f"Eye Width:    {eye_w} s")

rise = scope.get_rise_time()
print(f"Rise Time:    {rise} s")

fall = scope.get_fall_time()
print(f"Fall Time:    {fall} s")

duty = scope.do_query_number(":MEASure:DUTYcycle?")
print(f"Duty Cycle:   {duty} %")

vpp = scope.do_query_number(":MEASure:VPP?")
print(f"Vpp:          {vpp} V")

# ── Batch query — send multiple SCPI queries in one round trip ────────────────
# Results are returned as a semicolon-separated string in the same order.
query_list = [
    ":MEASure:FREQuency?",
    ":MEASure:CGRade:EHEight?",
    ":MEASure:CGRade:EWIDth?",
    ":MEASure:RJDJ:ALL?",
    ":MEASure:RISetime?",
    ":MEASure:FALLtime?",
    ":MEASure:DUTYcycle?",
    ":MEASure:VPP?",
]
batch_result = scope.do_query_string(";".join(query_list) + ";")
values = batch_result.split(";")
labels = ["Freq", "Eye H", "Eye W", "RJDJ:ALL", "Rise", "Fall", "Duty", "Vpp"]
for label, val in zip(labels, values):
    print(f"  {label:10s}: {val.strip()}")

# ── Phase noise markers ───────────────────────────────────────────────────────
# Markers return 9.9E+37 when not active — stop on first inactive marker.
print("\nPhase noise markers:")
for marker_num in range(1, 11):
    x = scope.do_query_string(f":MARKer{marker_num}:X:POSition?").strip()
    y = scope.do_query_string(f":MARKer{marker_num}:Y:POSition?").strip()
    if "E+37" in x or "E+37" in y:
        break
    print(f"  Marker {marker_num}: X={x}  Y={y}")

# ── Screenshot ────────────────────────────────────────────────────────────────
screenshot_path = pathlib.Path("scope_screenshot.png")
scope.set_timeout(90000)  # screenshots can take a while
screen_bytes = scope.do_query_ieee_block(":DISPlay:DATA? PNG")
screenshot_path.write_bytes(screen_bytes)
print(f"\nScreenshot saved to {screenshot_path}")

# ── Cleanup ───────────────────────────────────────────────────────────────────
scope.do_command(":STOP")
scope_resource.close()
rm.close()
