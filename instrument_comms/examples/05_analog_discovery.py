"""
Example 05 — Digilent Analog Discovery 2: load DWF library, open device, generate signals.

The AD2 does NOT use VISA. It communicates through Digilent's native DWF shared library
loaded via Python's ctypes module. The DWF library must be installed separately
(part of the Digilent Waveforms desktop application).

Demonstrates:
  - Loading the DWF library on Windows/macOS/Linux
  - Opening the first available AD2 device
  - Outputting a DC voltage on analog out (W1)
  - Generating a single pulse on analog out (W2) — used as a reset signal
  - Controlling the AD2's onboard V+ power supply
  - Driving a digital IO pin constantly high
  - Proper device close

Requirements:
  - Digilent Waveforms application installed (provides dwf.dll / libdwf.so / dwf.framework)
  - No pip install needed — ctypes is part of the Python standard library
"""

import sys
from ctypes import cdll, c_int
from time import sleep

# Add parent directory so we can import from instruments/
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from instruments.analog_discovery import AnalogDiscovery

# ── Load DWF shared library ───────────────────────────────────────────────────
# The library name differs per platform. It must be installed via Digilent Waveforms.
if sys.platform.startswith("win"):
    dwf = cdll.dwf                                              # Windows: dwf.dll in system32
elif sys.platform.startswith("darwin"):
    dwf = cdll.LoadLibrary("/Library/Frameworks/dwf.framework/dwf")  # macOS
else:
    dwf = cdll.LoadLibrary("libdwf.so")                        # Linux

# ── Open device ───────────────────────────────────────────────────────────────
# c_int(-1) means "open the first available device"
ad = AnalogDiscovery(dwf)
if not ad.open_and_init_device():
    print("ERROR: Could not open Analog Discovery device.")
    sys.exit(1)

ad.print_version()

# ── Set onboard V+ power supply to 3.3 V ─────────────────────────────────────
# The AD2 has a built-in adjustable positive supply (0–5 V, up to ~700 mA).
ad.set_positive_power_supply(3.3)
print("V+ supply set to 3.3 V")
sleep(0.1)

# ── Output DC voltage on W1 (analog out channel 0) ───────────────────────────
# Useful for bias voltage generation. Range: ±5 V on AD2.
ad.analog_out_dc(c_int(0), offset=1.8)   # W1 = 1.8 V DC
print("W1 set to 1.8 V DC")
sleep(0.5)

# ── Generate a single reset pulse on W2 (analog out channel 1) ───────────────
# This generates one square pulse: 5 V amplitude, 10 ms duration, 0° phase.
# Phase 0° means the pulse starts HIGH (rising edge first).
ad.analog_out_single_pulse(
    channel=c_int(1),          # W2
    pulse_length=0.010,        # 10 ms
    amplitude_in_volts=1.65,   # ±1.65 V around 0 V offset → 0 to 3.3 V swing
    phase_in_degrees=0,        # start high
)
print("Reset pulse sent on W2")
sleep(0.1)  # wait for pulse to complete before doing anything else

# ── Drive digital IO pin 0 constantly high ───────────────────────────────────
# Useful for holding a chip reset line de-asserted (active-low reset).
# DIO channel 0 = first digital IO pin on the AD2 connector.
ad.set_digital_io_constant_high(channel=0)
print("DIO 0 driven high")
sleep(0.5)

# ── Close device ─────────────────────────────────────────────────────────────
# Always call close — omitting this can leave the device in an active state
# and prevent other programs (including Waveforms GUI) from opening it.
ad.close_device()
print("Device closed.")
