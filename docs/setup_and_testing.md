# Setup and testing

## 1. Install the Python package

```bash
pip install -e host/
```

For LAN instruments (signal generator, oscilloscope, signal analyzer), a native VISA backend is required. NI-VISA is recommended on Windows — download from ni.com/visa and install before using any instrument commands.

For AD3 logic analyzer capture, install Digilent WaveForms from digilent.com — this installs `dwf.dll`, which the capture tool loads automatically.

---

## 2. Arduino prerequisites

**Copy the INA219 library** from `lib/Ina219Rails/` into your Arduino libraries directory:

| Platform | Path |
|---|---|
| Windows | `Documents\Arduino\libraries\Ina219Rails\` |
| Mac/Linux | `~/Arduino/libraries/Ina219Rails/` |

**Install Adafruit DotStar and the SAMD core** (one time):

```bash
arduino-cli lib install "Adafruit DotStar"
arduino-cli config add board_manager.additional_urls https://adafruit.github.io/arduino-board-index/package_adafruit_index.json
arduino-cli core update-index
arduino-cli core install adafruit:samd
```

---

## 3. Detect board port

```bash
dacdemo detect-port
```

Finds the Adafruit ItsyBitsy by USB VID and writes the COM port to `config/dacdemo.toml`. Re-run any time you change USB ports.

---

## 4. Flash firmware

```bash
dacdemo flash
```

Compiles and uploads `firmware/Arduino_DAC_framework` using the port and board from config.

To flash manually with arduino-cli:

```bash
arduino-cli compile --fqbn adafruit:samd:adafruit_itsybitsy_m0 firmware/Arduino_DAC_framework
arduino-cli upload  --fqbn adafruit:samd:adafruit_itsybitsy_m0 --port COM3 firmware/Arduino_DAC_framework
```

---

## 5. Configure instrument addresses

```bash
dacdemo detect-instruments
```

Queries VISA for the R&S SMA100B, Keysight N9010B EXA, and Keysight oscilloscope. Writes `siggen_addr`, `sa_addr`, and `scope_addr` directly into `config/dacdemo.toml` — no manual copy-paste needed.

If an instrument isn't found, check its network settings and re-run with `--subnet`:

```bash
dacdemo detect-instruments --subnet 192.168.10
```

---

## 6. Verify — no hardware needed

```bash
dacdemo list-ports    # confirm board port is visible to the OS
dacdemo calc          # derive f_sample + f_out from [coherent_tone]; writes back into [dac]
dacdemo gen-sine      # generate the 256-sample sine table
```

Default config (`fs_app=5000`, `x_seed=4`, `fin="low"`) should produce:
- `f_sample = 5.24288 GHz`
- `f_out ≈ 61.44 MHz`

---

## 7. Verify — board connected

Test in this order — each step validates one more layer:

**Confirm serial link** (simplest round-trip, no chip required):
```python
python -c "from dacdemo.board_control import BoardSession; s=BoardSession.open('COM5'); print(s.led_on()); print(s.led_off()); s.close()"
```

**Read-only rail check** (no chip in socket required):
```bash
dacdemo health
```

**Set rail voltages:**
```bash
dacdemo bias --initialize-compliance
```

**Load and enable sine pattern:**
```bash
dacdemo play-sine
```

**Full board sequence in one command:**
```bash
dacdemo run-demo --initialize-compliance
```

---

## 8. End-to-end sequence

See `docs/command_reference.md` for details on each instrument command.

```bash
dacdemo calc                              # derive f_sample + f_out
dacdemo set-siggen                        # push f_sample to R&S clock generator
dacdemo run-demo --initialize-compliance  # bias rails + load + enable DAC
dacdemo capture                           # capture + decode + validate SPI
dacdemo scope-measure                     # measure analog output on scope
dacdemo sa-measure                        # measure RF spectrum on signal analyzer
```
