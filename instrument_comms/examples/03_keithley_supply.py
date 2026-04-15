"""
Example 03 — Keithley 2230-30-1 power supply: connect over USB, set voltages, measure.

Demonstrates:
  - USB (USBTMC) connection via pyvisa
  - Disabling channel tracking for independent control
  - Setting per-channel voltages
  - Measuring power on each channel

Requirements: pyvisa, NI-VISA or Keysight IO Libraries (for USBTMC support).
On Windows the Keithley driver or NI-VISA must be installed to enumerate USB instruments.
"""

import pathlib
import pyvisa
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from instruments.keithley_supply import KeithleyPowerSupply

# USB resource string — find yours with pyvisa.ResourceManager().list_resources()
# Format: "USB0::<VID>::<PID>::<SerialNumber>::INSTR"
KEITHLEY_ADDRESS = "USB0::0x05E6::0x2230::1234567::INSTR"  # replace serial

rm = pyvisa.ResourceManager()
resource = rm.open_resource(KEITHLEY_ADDRESS)
resource.timeout = 30000  # ms

supply = KeithleyPowerSupply(resource)

# ── Verify instrument identity ────────────────────────────────────────────────
if supply.check_instr_name() != 0:
    print("WARNING: IDN response does not match expected Keithley 2230-30-1")

# ── Reset and configure ───────────────────────────────────────────────────────
supply.reset_supply()          # *RST — returns to factory defaults
supply.turn_track_mode_off()   # OUTPut:TRACK 0 — independent channel control

# ── Set voltages (channels are 1-indexed) ────────────────────────────────────
# CH1 = VPW (positive well bias), CH2 = VNW (negative well bias)
supply.set_channel_voltage(1, 1.2)    # VPW = 1.2 V
supply.set_channel_voltage(2, 0.8)    # VNW = 0.8 V (supply will output abs value)

# ── Enable output ─────────────────────────────────────────────────────────────
supply.turn_output_on()   # OUTPut 1

# ── Measure power on both channels ───────────────────────────────────────────
ch1_power = supply.measure_power(1)
ch2_power = supply.measure_power(2)
print(f"CH1 power: {ch1_power} W")
print(f"CH2 power: {ch2_power} W")

ch1_v = supply.measure_voltage(1)
ch1_i = supply.measure_current(1)
print(f"CH1 measured: {ch1_v} V  {ch1_i} A")

# ── Turn off and close ────────────────────────────────────────────────────────
supply.turn_output_off()
resource.close()
rm.close()
