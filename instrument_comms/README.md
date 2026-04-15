# Instrument Communications Reference

Extracted from the PLL sweep automation project. Self-contained — no dependency on
the rest of the PLL codebase.

## Contents

```
instrument_comms/
├── instruments/                 # Instrument drivers (copy these into any new project)
│   ├── analog_discovery.py      — Digilent AD2 via DWF ctypes library
│   ├── dwfconstants.py          — Digilent DWF constant definitions (Digilent, 2024-07-24)
│   ├── keysight_scope.py        — Keysight MXR404A oscilloscope via VISA/TCPIP
│   ├── keithley_supply.py       — Keithley 2230-30-1 power supply via VISA/USB
│   ├── keysight_supply.py       — Keysight E36300 power supply via VISA/LAN or USB
│   ├── rs_siggen.py             — R&S SMA100B signal generator via VISA/LAN or USB
│   └── __init__.py
└── examples/
    ├── 01_visa_connection.py    — Discover and connect to all instruments
    ├── 02_keysight_scope.py     — Scope setup, measurements, screenshot
    ├── 03_keithley_supply.py    — USB supply: set voltage, measure power
    ├── 04_rs_siggen.py          — Signal gen: CW mode, frequency sweep
    ├── 05_analog_discovery.py   — AD2: DC out, pulse, digital IO, V+ supply
    ├── 06_keysight_supply.py    — LAN supply: multi-channel voltage and measurement
    └── 07_full_measurement_session.py  — All instruments together, saves CSV
```

---

## Environment & Dependencies

### Python

Python 3.8 or later. Developed and tested on Python 3.11.

### pip packages

```
pyvisa>=1.13
```

Optional (only needed for `07_full_measurement_session.py` CSV output):
```
pandas
```

Install:
```bash
pip install pyvisa
# or, if using this project's venv:
.venv/Scripts/pip install pyvisa
```

### VISA backend

pyvisa is a pure-Python wrapper; it requires a native VISA backend to talk to instruments.
Install one of:

| Backend | Source | Notes |
|---|---|---|
| **NI-VISA** | ni.com/visa | Most compatible. Required for USBTMC on Windows. |
| **Keysight IO Libraries Suite** | keysight.com/find/iosuite | Alternative to NI-VISA. Includes Connection Expert GUI. |
| **pyvisa-py** | `pip install pyvisa-py` | Pure-Python fallback. No extra install, but limited USBTMC support on Windows. |

For USB instruments (Keithley) on Windows, NI-VISA or the Keithley driver is required.

### Analog Discovery 2 (DWF library)

The AD2 does **not** use VISA. It uses Digilent's native DWF shared library:

- **Windows**: Install [Digilent Waveforms](https://digilent.com/shop/software/digilent-waveforms/)
  — installs `dwf.dll` into `C:\Windows\System32\`
- **macOS**: Waveforms installs `dwf.framework` into `/Library/Frameworks/`
- **Linux**: Install `digilent.waveforms` package — provides `libdwf.so`

No pip install needed — `ctypes` is part of the Python standard library.

---

## Instrument Communication Protocols

| Instrument | Protocol | Typical VISA String |
|---|---|---|
| Keysight MXR404A scope | TCPIP / HiSLIP | `TCPIP0::<ip>::hislip0::INSTR` |
| R&S SMA100B signal gen | TCPIP / VXI-11 | `TCPIP0::<ip>::inst0::INSTR` |
| Keysight E36300 supply | TCPIP / VXI-11 | `TCPIP0::<ip>::inst0::INSTR` |
| Keithley 2230-30-1 | USB / USBTMC | `USB0::0x05E6::0x2230::<serial>::INSTR` |
| Analog Discovery 2 | USB / DWF library | *(not VISA — see above)* |

### Finding your USB resource string

```python
import pyvisa
rm = pyvisa.ResourceManager()
print(rm.list_resources())
```

---

## SCPI Command Reference

### Keysight MXR404A Oscilloscope

| Operation | Command |
|---|---|
| Reset | `*RST` |
| Clear status | `*CLS` |
| Wait for complete | `*OPC?` |
| Suppress headers | `:SYSTem:HEADer 0` |
| Check error queue | `:SYSTem:ERRor? STRing` |
| Set source channel | `:MEASure:SOURce CHANnel1` |
| Acquire points | `:ACQuire:POINts <N>` |
| Enable status in results | `:MEASure:SENDvalid ON` |
| Start / stop acquisition | `:RUN` / `:STOP` |
| Autoscale vertical | `:AUToscale:VERTical CHANnel1` |
| Output frequency | `:MEASure:FREQuency?` |
| Eye height | `:MEASure:CGRade:EHEight?` |
| Eye width | `:MEASure:CGRade:EWIDth?` |
| Jitter (all) | `:MEASure:RJDJ:ALL?` |
| TJ/RJ/DJ summary | `MEASure:RJDJ:TJRJDJ?` |
| Rise time | `:MEASure:RISetime?` |
| Fall time | `:MEASure:FALLtime?` |
| Duty cycle | `:MEASure:DUTYcycle?` |
| Peak-to-peak voltage | `:MEASure:VPP?` |
| Phase noise marker X | `:MARKer<N>:X:POSition?` |
| Phase noise marker Y | `:MARKer<N>:Y:POSition?` |
| Screenshot (PNG) | `:DISPlay:DATA? PNG` (IEEE block) |
| Load setup from file | `:SYSTem:SETup` (IEEE block write) |

**Batch queries**: Multiple SCPI queries can be sent in a single round trip separated by
semicolons. Results are returned as a semicolon-separated string in the same order:
```python
result = scope.do_query_string(":MEASure:FREQuency?;:MEASure:VPP?;")
freq, vpp = result.split(";")
```

**Inactive marker sentinel**: A measurement value of `9.9E+37` means the instrument
could not complete the measurement (out of range, no signal, marker inactive, etc.).
Always check for this before using a value numerically.

### Keithley 2230-30-1 Power Supply

| Operation | Command |
|---|---|
| Reset | `*RST` |
| Identity | `*IDN?` |
| Enable all outputs | `OUTPut 1` |
| Disable all outputs | `OUTPut 0` |
| Disable channel tracking | `OUTPut:TRACK 0` |
| Select channel | `INSTrument:NSELect <1\|2\|3>` |
| Set voltage (active channel) | `VOLTage <value>` |
| Measure power (active channel) | `MEASure:POWer?` |
| Measure voltage (active channel) | `MEASure:VOLTage?` |
| Measure current (active channel) | `MEASure:CURRent?` |

Channel selection (NSELect) persists until changed — always select before measuring.

### Keysight E36300 Power Supply

| Operation | Command |
|---|---|
| Set voltage on channel | `VOLTage <value>, (@<N>)` |
| Enable outputs (multi-channel) | `OUTPut 1, (@1:3)` |
| Disable outputs (multi-channel) | `OUTPut 0, (@1:3)` |
| Measure current | `MEASure:CURRent? CH<N>` |
| Measure voltage | `MEASure:VOLTage? CH<N>` |

### R&S SMA100B Signal Generator

| Operation | Command |
|---|---|
| Reset | `*RST` |
| RF on / off | `OUTPut ON` / `OUTPut OFF` |
| Set CW mode | `SOURce1:FREQ:MODE CW` |
| Set frequency | `SOURce1:FREQuency:CW <Hz>` |
| Set power level | `SOURce1:POWer <value> <unit>` |

### Analog Discovery 2 (DWF API)

The AD2 uses function calls into the DWF shared library, not SCPI text commands.
Key functions used:

| Purpose | DWF Function |
|---|---|
| Set on-close behavior | `FDwfParamSet(DwfParamOnClose, c_int(0))` |
| Open first device | `FDwfDeviceOpen(c_int(-1), byref(hdwf))` |
| Disable auto-configure | `FDwfDeviceAutoConfigureSet(hdwf, c_int(0))` |
| Close device | `FDwfDeviceClose(hdwf)` |
| Analog out: enable node | `FDwfAnalogOutNodeEnableSet(hdwf, ch, node, c_int(1))` |
| Analog out: set function | `FDwfAnalogOutNodeFunctionSet(hdwf, ch, node, func)` |
| Analog out: set frequency | `FDwfAnalogOutNodeFrequencySet(hdwf, ch, node, c_double(hz))` |
| Analog out: set amplitude | `FDwfAnalogOutNodeAmplitudeSet(hdwf, ch, node, c_double(v))` |
| Analog out: set offset | `FDwfAnalogOutNodeOffsetSet(hdwf, ch, node, c_double(v))` |
| Analog out: set run time | `FDwfAnalogOutRunSet(hdwf, ch, c_double(s))` |
| Analog out: set repeats | `FDwfAnalogOutRepeatSet(hdwf, ch, c_int(n))` |
| Analog out: apply config | `FDwfAnalogOutConfigure(hdwf, ch, c_int(1))` |
| V+ supply enable+set | `FDwfAnalogIOChannelNodeSet(hdwf, c_int(0), c_int(0), c_double(1))` then `c_int(1)` for voltage node |
| V+ supply apply | `FDwfAnalogIOConfigure(hdwf)` |
| Digital out: enable pin | `FDwfDigitalOutEnableSet(hdwf, ch, 1)` |
| Digital out: set constant | `FDwfDigitalOutCounterSet(hdwf, ch, 0, 0)` |
| Digital out: apply config | `FDwfDigitalOutConfigure(hdwf, c_int(1))` |

---

## Timeouts

| Instrument | Recommended timeout | Notes |
|---|---|---|
| Keysight scope (normal) | 60 000 ms | Extend to 90 000 ms for screenshots or long acquisitions |
| Keysight scope (batch measurement) | 90 000 ms | Eye/jitter on slow signals can be slow |
| R&S signal gen | 50 000 ms | |
| Keysight supply | 30 000 ms | |
| Keithley supply | 30 000 ms | |

Set timeout with `resource.timeout = <ms>` before opening the driver wrapper.

---

## Common Issues

### "9.9E+37" in measurement results
The instrument could not complete the measurement: no signal, out of range, or
the feature is not active (e.g. phase noise marker not placed). Treat as `NaN`.

### VISA resource not found
- Confirm the instrument is powered on and connected to the network/USB.
- Run `pyvisa.ResourceManager().list_resources()` and check the string matches.
- For USB instruments on Windows, ensure NI-VISA or the vendor driver is installed.
- For LAN instruments, check firewall rules — VISA uses port 111 (VXI-11) or 4880 (HiSLIP).

### AD2 "Unable to open device"
- Digilent Waveforms GUI must be closed — it holds exclusive access to the device.
- Only one process can hold the AD2 handle at a time.

### Keithley channels not independent
Call `OUTPut:TRACK 0` after reset. Track mode is re-enabled by `*RST` on some firmware
versions, so always disable it before setting voltages independently.
