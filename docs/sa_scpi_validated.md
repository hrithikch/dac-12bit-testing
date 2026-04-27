# Signal Analyzer SCPI — Validated Commands

Commands used in `keysight_exa.py` / `siganalyzer_control.py`, cross-referenced against
`instrument_comms/signal_analyzer/SCPI_commands.md` (X-Series Programmer's Reference).

---

## Frequency / span

| Command sent | Full form in reference | Notes |
|---|---|---|
| `:FREQuency:CENTer <hz>` | `[:SENSe]:FREQuency:CENTer` | `[:SENSe]` prefix optional |
| `:FREQuency:SPAN <hz>` | `[:SENSe]:FREQuency:SPAN` | `[:SENSe]` prefix optional |

Extra options available:
- `[:SENSe]:FREQuency:SPAN:FULL` — set span to full range
- `[:SENSe]:FREQuency:SPAN:PREVious` — restore previous span
- `[:SENSe]:FREQuency:CENTer:STEP[:INCRement] <hz>` — set center frequency step size
- `[:SENSe]:FREQuency:CENTer:STEP:AUTO ON|OFF`

---

## Bandwidth (RBW / VBW)

| Command sent | Full form in reference | Notes |
|---|---|---|
| `:BANDwidth <hz>` | `[:SENSe]:BANDwidth\|BWIDth[:RESolution]` | `[:SENSe]` optional; `BWIDth` is valid short form; `[:RESolution]` optional |
| `:BANDwidth:VIDeo <hz>` | `[:SENSe]:BANDwidth\|BWIDth:VIDeo` | same short-form rules |

Extra options available:
- `[:SENSe]:BANDwidth[:RESolution]:AUTO ON|OFF`
- `[:SENSe]:BANDwidth[:RESolution]:WIDE` — wide (FFT) RBW mode
- `[:SENSe]:BANDwidth:SHAPe` — filter shape
- `[:SENSe]:BANDwidth:TYPE` — filter type
- `[:SENSe]:BANDwidth:VIDeo:AUTO ON|OFF`
- `[:SENSe]:BANDwidth:VIDeo:RATio <ratio>` — set VBW as ratio of RBW
- `[:SENSe]:BANDwidth:VIDeo:RATio:AUTO ON|OFF`

---

## Reference level

| Command sent | Full form in reference | Notes |
|---|---|---|
| `:DISPlay:WINDow:TRACe:Y:RLEVel <dbm>` | `DISPlay:WINDow[1]:TRACe:Y[:SCALe]:RLEVel` | `[1]` defaults to window 1; `[:SCALe]` optional node |

Extra options available:
- `DISPlay:WINDow[1]:TRACe:Y[:SCALe]:RLEVel:OFFSet <db>` — add offset to reference level

---

## Sweep control

| Command sent | Full form in reference | Notes |
|---|---|---|
| `:INITiate:CONTinuous ON\|OFF` | `INITiate:CONTinuous` | |
| `:INITiate:IMMediate` | `INITiate[:IMMediate]` | `[:IMMediate]` optional — bare `:INITiate` also valid |

---

## Markers

| Command sent | Full form in reference | Notes |
|---|---|---|
| `:CALCulate:MARKer1:MAXimum` | `CALCulate:MARKer[1]\|2\|…\|24:MAXimum` | marker number 1–24 |
| `:CALCulate:MARKer1:X?` | `CALCulate:MARKer[1]\|…:X` | returns marker frequency (Hz) |
| `:CALCulate:MARKer1:Y?` | `CALCulate:MARKer[1]\|…:Y` | returns marker amplitude (dBm) |

Extra options available:
- `CALCulate:MARKer[1]|…:MAXimum:NEXT` — move to next lower peak
- `CALCulate:MARKer[1]|…:MAXimum:LEFT` — next peak to the left
- `CALCulate:MARKer[1]|…:MAXimum:RIGHt` — next peak to the right
- `CALCulate:MARKer[1]|…:MAXimum:ALL` — place markers on all peaks
- `CALCulate:MARKer[1]|…:X:POSition` — set marker by trace point index instead of frequency
- `CALCulate:MARKer[1]|…:X:READout` — change readout type (frequency, time, etc.)
- `CALCulate:MARKer[1]|…:X:READout:AUTO ON|OFF`
- `CALCulate:MARKer[1]|…:FCOunt[:STATe] ON|OFF` — enable frequency counter on marker
- `CALCulate:MARKer[1]|…:FCOunt:X?` — read frequency counter result
- `CALCulate:MARKer[1]|…:FCOunt:GATetime <s>` — set counter gate time
- `CALCulate:MARKer[1]|…[:SET]:RLEVel` — set reference level to marker amplitude

---

## Trace data

| Command sent | Full form in reference | Notes |
|---|---|---|
| `:TRACe:DATA? TRACe1` | `TRACe[:DATA]` | `[:DATA]` optional |

The project's SNR flow is not backed by a native EXA `:MEASure:SNR?` command.
It derives SNR in software from marker peak reads plus trace data:
- `:CALCulate:MARKer1:MAXimum`
- `:CALCulate:MARKer1:X?`
- `:CALCulate:MARKer1:Y?`
- `:TRACe:DATA? TRACe1`

Extra options available:
- `MMEMory:STORe:TRACe:DATA` — save trace data directly to a file on the instrument
- `MMEMory:LOAD:TRACe:DATA` — load trace data from a file on the instrument

---

## Screen capture

| Command sent | Full form in reference | Notes |
|---|---|---|
| `MMEMory:STORe:SCReen "<filename>"` | `MMEMory:STORe:SCReen` | saves PNG to instrument internal storage |
| `MMEMory:DATA? "<filename>"` | `MMEMory:DATA` | transfers file bytes back over VISA |

Extra options available:
- `MMEMory:STORe:SCReen:BLOCked` — save screenshot without blocking sweep
- `MMEMory:STORe:SCReen:THEMe` — set color theme for saved screenshot

---

## Error / status

| Command sent | Full form in reference | Notes |
|---|---|---|
| `:SYSTem:ERRor?` | `SYSTem:ERRor[:NEXT]?` | `[:NEXT]` optional; returns one error and removes it from queue |

Extra options available:
- `SYSTem:ERRor:VERBose` — return verbose error descriptions
- `SYSTem:ERRor:OVERload[:STATe]` — overload error reporting state
- `SYSTem:ERRor:PUP?` — power-up error query

---

## Not supported on EXA

| Command | Reason |
|---|---|
| `:SYSTem:HEADer 0` | Not in X-Series SA reference — removed from driver. Response headers are not an issue for the EXA in normal use. |
