"""
Example 06 — Keysight E36300-series power supply: connect over LAN, set voltages, measure.

Demonstrates:
  - LAN connection via pyvisa
  - Setting per-channel voltages with the (@N) channel list syntax
  - Enabling/disabling all outputs simultaneously
  - Measuring voltage, current, and calculating power per channel

Requirements: pyvisa, NI-VISA or Keysight IO Libraries Suite.
"""

import pathlib
import pyvisa
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from instruments.keysight_supply import KeysightPowerSupply

SUPPLY_ADDRESS = "TCPIP0::192.168.1.102::inst0::INSTR"  # update IP

rm = pyvisa.ResourceManager()
resource = rm.open_resource(SUPPLY_ADDRESS)
resource.timeout = 30000  # ms

supply = KeysightPowerSupply(resource)
print("IDN:", resource.query("*IDN?").strip())

# ── Set all three channel voltages ────────────────────────────────────────────
supply.set_all_voltages(v1=1.8, v2=0.8, v3=0.45)

# ── Enable all outputs at once ────────────────────────────────────────────────
supply.enable_all_outputs()   # OUTPut 1, (@1:3)

# ── Measure all channels ──────────────────────────────────────────────────────
data = supply.measure_all()
for ch in (1, 2, 3):
    print(f"CH{ch}: {data[f'ch{ch}_voltage']:.4f} V  "
          f"{data[f'ch{ch}_current']:.6f} A  "
          f"{data[f'ch{ch}_power']:.6f} W")

# ── Disable outputs and close ─────────────────────────────────────────────────
supply.disable_all_outputs()
resource.close()
rm.close()
