Yes — you can use essentially the **same PyVISA + SCPI pattern** as your scope code, but swap the oscilloscope-specific commands for **X-Series signal analyzer** commands.

Your scope example already gives you the right architecture:

* a thin Python driver class around a VISA resource,
* helpers for `write`, `query`, binary transfers, and error polling,
* then a short script that opens the instrument, configures it, takes measurements, and saves data/images.  

For the N9010B specifically, Keysight documents that X-Series analyzers are remotely programmable over VISA/SCPI, support LAN/HiSLIP and USB connections, and use mode-specific programmer references for the detailed SCPI command set. The general programmer’s guide also points to built-in SCPI help such as `:SYST:HELP:HEAD?`. ([Keysight United States][1])

Here’s the practical translation.

## What stays the same

From your scope files, these ideas carry over directly:

* `pyvisa.ResourceManager()`
* `open_resource(...)`
* wrapper methods like `do_command`, `do_query_string`, `do_query_number`
* checking `:SYSTem:ERRor?`
* using `*CLS`, `*RST`, `*OPC?`, and timeouts
* optionally retrieving binary data or a screen capture.  

## What changes

Instead of scope commands like:

* `:MEASure:FREQuency?`
* `:MEASure:VPP?`
* `:DISPlay:DATA? PNG`

you’ll usually work with analyzer concepts like:

* center frequency
* span
* RBW / VBW
* reference level
* sweep mode
* markers
* trace data

Keysight’s X-Series docs make an important distinction here: the **general programmer’s guide** covers SCPI/VISA fundamentals, while the **Spectrum Analyzer Mode User’s and Programmer’s Reference** is where the spectrum-analyzer-mode command details live. ([Keysight United States][1])

## A clean driver skeleton for the N9010B

This is the closest equivalent to your `KeysightOscilloscope` class, but shaped for the EXA.

```python
import pathlib
import pyvisa
import sys


class KeysightEXA:
    """
    Minimal PyVISA driver for a Keysight N9010B EXA Signal Analyzer.

    Pattern adapted from the uploaded scope driver:
      - SCPI write/query helpers
      - instrument error polling
      - simple measurement workflow
    """

    def __init__(self, resource: pyvisa.resources.Resource, debug: bool = False) -> None:
        self.inst = resource
        self.debug = debug

    def set_timeout(self, timeout_ms: int) -> None:
        self.inst.timeout = timeout_ms

    def check_instrument_name(self) -> bool:
        idn = self.query_string("*IDN?").strip()
        return "N9010B" in idn and "KEYSIGHT" in idn.upper()

    def clear_status(self) -> None:
        self.write("*CLS")

    def preset(self) -> None:
        self.write("*RST")

    def turn_off_system_header(self) -> None:
        self.write(":SYSTem:HEADer 0")

    # ---------------------------
    # Low-level helpers
    # ---------------------------
    def write(self, command: str) -> None:
        if self.debug:
            print(f"WRITE: {command}")
        self.inst.write(command)
        self.check_instrument_errors(command)

    def query_string(self, query: str) -> str:
        if self.debug:
            print(f"QUERY: {query}")
        result = self.inst.query(query)
        self.check_instrument_errors(query)
        return result

    def query_number(self, query: str) -> float:
        result = self.query_string(query).strip()
        return float(result)

    def query_ascii_values(self, query: str):
        if self.debug:
            print(f"QUERY ASCII: {query}")
        result = self.inst.query_ascii_values(query)
        self.check_instrument_errors(query)
        return result

    def query_binary_block(self, query: str, datatype="B"):
        if self.debug:
            print(f"QUERY BIN: {query}")
        result = self.inst.query_binary_values(query, datatype=datatype)
        self.check_instrument_errors(query)
        return result

    def check_instrument_errors(self, command: str) -> None:
        while True:
            err = self.inst.query(":SYSTem:ERRor?").strip()
            if err.startswith("+0") or err.startswith("0,"):
                break
            raise RuntimeError(f"Instrument error after '{command}': {err}")

    # ---------------------------
    # Analyzer setup helpers
    # ---------------------------
    def configure_spectrum_view(
        self,
        center_hz: float,
        span_hz: float,
        rbw_hz: float,
        vbw_hz: float,
        ref_level_dbm: float,
    ) -> None:
        # Common X-Series SA-style setup
        self.write(f":FREQuency:CENTer {center_hz}")
        self.write(f":FREQuency:SPAN {span_hz}")
        self.write(f":BANDwidth {rbw_hz}")
        self.write(f":BANDwidth:VIDeo {vbw_hz}")
        self.write(f":DISPlay:WINDow:TRACe:Y:RLEVel {ref_level_dbm}")

    def single_sweep(self) -> None:
        self.write(":INITiate:CONTinuous OFF")
        self.query_number(":INITiate:IMMediate;*OPC?")

    def continuous_sweep_on(self) -> None:
        self.write(":INITiate:CONTinuous ON")

    def move_marker_to_peak(self) -> None:
        self.write(":CALCulate:MARKer1:MAXimum")

    def get_marker_frequency_hz(self) -> float:
        return self.query_number(":CALCulate:MARKer1:X?")

    def get_marker_amplitude_dbm(self) -> float:
        return self.query_number(":CALCulate:MARKer1:Y?")

    def get_trace_ascii(self):
        # Often used to fetch trace points; verify exact form on your unit/mode.
        return self.query_ascii_values(":TRACe:DATA? TRACe1")

    def close(self) -> None:
        self.inst.close()
```

## Example script: peak search on a known tone

```python
import pyvisa
from keysight_exa import KeysightEXA

EXA_ADDRESS = "TCPIP0::192.168.1.50::inst0::INSTR"   # or hislip0 if available

rm = pyvisa.ResourceManager()
inst = rm.open_resource(EXA_ADDRESS)

exa = KeysightEXA(inst, debug=False)
exa.set_timeout(30000)

# Init
inst.clear()
exa.clear_status()
exa.turn_off_system_header()

# Optional sanity check
print(exa.query_string("*IDN?").strip())

# Configure analyzer
exa.configure_spectrum_view(
    center_hz=12.288e6,
    span_hz=2e6,
    rbw_hz=10e3,
    vbw_hz=10e3,
    ref_level_dbm=0.0,
)

# Acquire one sweep
exa.single_sweep()

# Marker to max
exa.move_marker_to_peak()
peak_freq = exa.get_marker_frequency_hz()
peak_amp = exa.get_marker_amplitude_dbm()

print(f"Peak frequency: {peak_freq} Hz")
print(f"Peak amplitude: {peak_amp} dBm")

exa.close()
rm.close()
```

## How this maps to your scope example

Your scope script does:

1. connect
2. clear/setup
3. configure acquisition
4. wait for completion
5. query measurements
6. save screenshot
7. close. 

For the EXA, that becomes:

1. connect
2. clear/setup
3. set center/span/RBW/VBW/reference level
4. run single sweep and wait with `*OPC?`
5. place marker on peak
6. read marker frequency/amplitude
7. optionally fetch trace or screen image
8. close

So conceptually it is almost a one-for-one replacement.

## The main thing to be careful about

The N9010B is an **X-Series platform**, and the exact SCPI tree can depend on:

* firmware generation,
* whether you are in **Spectrum Analyzer mode** versus another measurement app,
* and which feature/application is active. Keysight explicitly separates the generic programmer’s guide from the per-mode programmer references for that reason. ([Keysight United States][1])

So the safest workflow is:

* start with the class above,
* verify each SCPI command against your EXA’s Spectrum Analyzer mode reference,
* or query the instrument’s SCPI help as documented by Keysight. ([Keysight United States][1])

## About screenshots

Your scope example uses `:DISPlay:DATA? PNG` to pull a PNG directly. 
For analyzers, Keysight notes that screen capture support exists but the exact mechanism can vary by instrument family and supported print/image formats, so this is one area I would not assume is identical to the scope command without checking the EXA’s specific programming reference. ([Keysight United States][2])

## Bottom line

Yes — you should build this **the same way** as the scope code:

* keep the PyVISA wrapper pattern from your uploaded files,
* rename the driver for the analyzer,
* replace oscilloscope measurements with SA setup + marker/trace queries,
* use `*OPC?` and `:SYST:ERR?` the same way.   ([Keysight United States][1])


[1]: https://www.keysight.com/us/en/assets/9018-02192/programming-guides/9018-02192.pdf "X-Series Signal Analyzer Programmer's Guide"
[2]: https://www.keysight.com/us/en/lib/resources/technical-specifications/capture-an-image-from-an-instruments-screen-and-transfer-it-to-a-pc.html "Capture an image from an instrument's screen and transfer it to a PC | Keysight"
