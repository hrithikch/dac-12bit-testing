# Setup and testing

## 1. Arduino library dependency

The firmware depends on `Ina219Rails`. The library source is included in this repo at `lib/Ina219Rails/`.
Copy that folder into your Arduino libraries directory before compiling:

- Windows: `Documents\Arduino\libraries\Ina219Rails\`
- Mac/Linux: `~/Arduino/libraries/Ina219Rails/`

You also need `Adafruit_DotStar`, available through the Arduino IDE library manager or arduino-cli:

```
arduino-cli lib install "Adafruit DotStar"
```

## 2. Flash the firmware

```bash
# Install Adafruit SAMD core (one time)
arduino-cli config add board_manager.additional_urls https://adafruit.github.io/arduino-board-index/package_adafruit_index.json
arduino-cli core update-index
arduino-cli core install adafruit:samd

# Confirm your board and port
arduino-cli board list

# Compile and upload
arduino-cli compile --fqbn adafruit:samd:adafruit_itsybitsy_m0 firmware/Arduino_DAC_framework
arduino-cli upload  --fqbn adafruit:samd:adafruit_itsybitsy_m0 --port COM3 firmware/Arduino_DAC_framework
```

Replace `COM3` with the port shown by `arduino-cli board list`.
Or use `dacdemo flash` after configuring `config/dacdemo.toml`.

## 3. Install the Python package

```bash
# From repo root
pip install -e host/
```

This installs `pyserial` and `pyvisa`. For LAN instruments (signal generator, scope), pyvisa also requires a native VISA backend — NI-VISA is recommended on Windows:
- Download from ni.com/visa and install before using `set-siggen` or `scope-measure`.
- The AD3 capture commands use the Digilent WaveForms DWF library instead (not VISA). Install WaveForms from digilent.com — this installs `dwf.dll` which the capture tool loads automatically.

## 4. Configure instrument addresses

Edit `config/dacdemo.toml` `[instruments]` with the actual IP addresses of your instruments:

```toml
[instruments]
siggen_addr      = "TCPIP0::<siggen_ip>::inst0::INSTR"    # R&S SMA100B (VXI-11)
scope_addr       = "TCPIP0::<scope_ip>::hislip0::INSTR"   # Keysight MSOS054A (HiSLIP)
sa_addr          = "TCPIP0::<sa_ip>::hislip0::INSTR"      # Keysight N9010B EXA (HiSLIP)
siggen_level_dbm = 0.0
```

To find the IP of each instrument, check its front panel network settings or use the VISA resource discovery tool in NI MAX (NI Measurement & Automation Explorer).

## 5. Detect and save the board port

```bash
dacdemo detect-port
```

Finds the Adafruit board by USB VID and writes the port to `config/dacdemo.toml`. Re-run any time you change USB ports.

## 6. Test incrementally (safest order)

**No hardware — verify Python install and coherent tone math:**
```bash
dacdemo list-ports
dacdemo calc
dacdemo gen-sine
```

`calc` reads `[coherent_tone]` from the TOML and writes derived `f_sample` and `f_out` back into `[dac]`. See the config ownership table in `docs/command_reference.md` for which fields are inputs vs derived. The current defaults (`fs_app=5000`, `x_seed=4`, `fin="low"`) should produce:
- `f_sample = 5.24288 GHz`
- `f_out ≈ 61.44 MHz`

**Board connected — simplest round-trip (confirms serial link and firmware):**
```python
python -c "from dacdemo.board_control import BoardSession; s=BoardSession.open('COM5'); print(s.led_on()); print(s.led_off()); s.close()"
```

**Read-only rail check (no chip in socket required):**
```bash
dacdemo health
```

**Set rail voltages:**
```bash
dacdemo bias --initialize-compliance
```

**Load sine pattern without enabling output:**
```python
python -c "from dacdemo.board_control import BoardSession; s=BoardSession.open('COM5'); print(s.dac_load_sine(266.24e6, 5.24288e9)); s.close()"
```

**Enable pattern output:**
```python
python -c "from dacdemo.board_control import BoardSession; s=BoardSession.open('COM5'); print(s.dac_enable_pattern()); s.close()"
```

**Or load and enable in one command:**
```bash
dacdemo play-sine
```

**Full demo sequence:**
```bash
dacdemo run-demo --initialize-compliance
```

The ordering matters: LED first (simplest), then rail reads (read-only), then bias (writes voltages), then DAC load, then enable. Each step validates one more layer.

---

## 7. Instrument testing (requires LAN and instruments connected)

**Signal generator — set DAC sample clock:**
```bash
dacdemo set-siggen
```
Sends `f_sample` from `[dac]` to the R&S SMA100B. Run `dacdemo calc` first to ensure `f_sample` is up to date.

**Digital capture — capture and decode SPI signals from ItsyBitsy:**

Wire the AD3 to the ItsyBitsy per the table in `docs/command_reference.md` (section 9). Close the WaveForms GUI first.

```bash
dacdemo capture
```
Arms the AD3, triggers the DAC demo over serial, decodes the SPI transaction, and validates the 256-word sine pattern. Saves CSVs to `data/captures/`. A passing run prints `OK — all 256 words match expected sine pattern.`

**Oscilloscope measurements:**
```bash
dacdemo scope-measure
```
Connects to the MSOS054A, measures CH1, and saves a timestamped row to `data/captures/scope_measurements.csv`.

**Signal analyzer measurements:**
```bash
dacdemo sa-measure
```
Connects to the N9010B EXA, configures a spectrum view centered on `dac.f_out`, runs one sweep, places a peak marker, and saves a timestamped row to `data/captures/sa_measurements.csv`. Pass `--center` and `--span` to override the frequency range.

**End-to-end sequence:**
```bash
dacdemo calc                     # derive f_sample + f_out from [coherent_tone]
dacdemo set-siggen               # push f_sample to R&S
dacdemo run-demo --initialize-compliance   # bias rails + load + enable DAC
dacdemo capture                  # capture + decode + validate SPI signals
dacdemo scope-measure            # measure analog output on scope
dacdemo sa-measure               # measure RF spectrum on signal analyzer
```
