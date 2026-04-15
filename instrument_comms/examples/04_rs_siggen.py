"""
Example 04 — Rohde & Schwarz SMA100B signal generator: connect, configure, sweep.

Demonstrates:
  - LAN connection via pyvisa
  - CW mode setup
  - Setting frequency and power level
  - Sweeping frequency across a list of values

Requirements: pyvisa, NI-VISA or Keysight IO Libraries Suite.
"""

import pathlib
import pyvisa
import sys
from time import sleep

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from instruments.rs_siggen import RohdeAndSchwarzSignalGenerator

SIGGEN_ADDRESS = "TCPIP0::192.168.1.101::inst0::INSTR"  # update IP

rm = pyvisa.ResourceManager()
resource = rm.open_resource(SIGGEN_ADDRESS)
resource.timeout = 50000  # ms

siggen = RohdeAndSchwarzSignalGenerator(resource)

# ── Verify identity ───────────────────────────────────────────────────────────
if siggen.check_instr_name() != 0:
    print("WARNING: IDN does not match expected R&S SMA100B")

# ── Reset and configure CW mode ───────────────────────────────────────────────
siggen.reset_sig_gen()             # *RST
siggen.set_continuous_wave_mode()  # SOURce1:FREQ:MODE CW

# ── Set output level ──────────────────────────────────────────────────────────
siggen.set_level("0 dBm")          # SOURce1:POWer 0 dBm

# ── Enable RF output ──────────────────────────────────────────────────────────
siggen.turn_rf_on()

# ── Set a single frequency ────────────────────────────────────────────────────
target_freq_hz = 68_825_000   # 68.825 MHz
siggen.set_frequency(target_freq_hz)
print(f"Frequency set to {target_freq_hz} Hz")
sleep(0.5)

# ── Step through a list of frequencies ───────────────────────────────────────
frequencies_hz = [60_000_000, 65_000_000, 68_825_000, 72_000_000, 75_000_000]

for freq in frequencies_hz:
    siggen.set_frequency(freq)
    print(f"  Frequency: {freq / 1e6:.3f} MHz")
    sleep(0.2)   # settle time — adjust to your DUT's requirements

# ── Turn off and close ────────────────────────────────────────────────────────
siggen.turn_rf_off()
resource.close()
rm.close()
