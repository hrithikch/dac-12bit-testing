# Setup and testing — from scratch

Complete bring-up guide for a fresh machine. Follow sections in order on first install; revisit individual sections as needed.

---

## 1. Install system prerequisites

### Python 3.9+

Download the latest Python 3.x installer from [python.org](https://www.python.org/downloads/) and run it.
Check "Add Python to PATH" during install. Verify:

```bash
python --version
```

### Git

Download from [git-scm.com](https://git-scm.com/download/win) and install with defaults. Verify:

```bash
git --version
```

### Arduino CLI

Install via winget (Windows 11):

```bash
winget install ArduinoSA.Arduino.CLI
```

Or download the Windows ZIP from the [Arduino CLI releases page](https://github.com/arduino/arduino-cli/releases), extract it, and add the folder to your PATH. Verify:

```bash
arduino-cli version
```

### NI-VISA (required for LAN instruments)

Download and install **NI-VISA** from [ni.com/visa](https://www.ni.com/en/support/downloads/drivers/download.ni-visa.html). This is the backend `pyvisa` uses to talk to the signal generator, oscilloscope, and signal analyzer over LAN. Without it, all `detect-instruments`, `set-siggen`, `sa-*`, and `scope-*` commands will fail.

After install, reboot if prompted.

### Digilent WaveForms (required for AD3 capture)

Download and install **WaveForms** from [digilent.com/waveforms](https://digilent.com/shop/software/digilent-waveforms/). This installs `dwf.dll`, which the `capture` command loads automatically. Close the WaveForms GUI before running `dacdemo capture` — the AD3 requires exclusive access.

---

## 2. Clone the repository

```bash
git clone https://github.com/hrithikch/dac-12bit-testing.git
cd dac-12bit-testing
```

---

## 3. Set up the Python environment

Create and activate a virtual environment from the repo root:

```bash
python -m venv .venv
.venv\Scripts\activate
```

Your prompt should now show `(.venv)`. Install the `dacdemo` package and its dependencies:

```bash
pip install -e host/
pip install pyvisa
```

`pip install -e host/` installs the package in editable mode — edits to source files take effect immediately without reinstalling. `pyvisa` is installed separately since it is only needed for instrument commands.

Verify the CLI is available:

```bash
dacdemo --help
```

> **Every session:** activate the venv before using `dacdemo`. The remaining steps assume it is active.

---

## 4. Set up Arduino CLI

### Add the Adafruit board manager URL

```bash
arduino-cli config init
arduino-cli config add board_manager.additional_urls https://adafruit.github.io/arduino-board-index/package_adafruit_index.json
```

### Install the Adafruit SAMD core and required library

```bash
arduino-cli core update-index
arduino-cli core install adafruit:samd
arduino-cli lib install "Adafruit DotStar"
```

These only need to be run once. `adafruit:samd` is the core for the ItsyBitsy M0; `Adafruit DotStar` drives the board's RGB LED.

### Install the INA219 rail monitor library

The `Ina219Rails` library is included in the repo. Copy it to your Arduino libraries folder:

**Windows:**
```
Documents\Arduino\libraries\Ina219Rails\
```

You can do this from the repo root:

```bash
cp -r lib/Ina219Rails "%USERPROFILE%\Documents\Arduino\libraries\Ina219Rails"
```

Or copy the folder manually in Explorer.

---

## 5. Detect the board USB port

Plug in the Adafruit ItsyBitsy M0 via USB, then run:

```bash
dacdemo detect-port
```

This scans USB devices, finds the ItsyBitsy by its VID (`0x239A`), and writes the COM port to `config/dacdemo.toml` under `[hardware] port`. Re-run any time you change USB ports or the board is re-enumerated.

To confirm the port is visible to the OS independently:

```bash
dacdemo list-ports
```

---

## 6. Flash the firmware

```bash
dacdemo flash
```

Compiles `firmware/Arduino_DAC_framework` and uploads it using the port and FQBN from config. This is only needed on first setup or after firmware changes.

To flash manually with arduino-cli:

```bash
arduino-cli compile --fqbn adafruit:samd:adafruit_itsybitsy_m0 firmware/Arduino_DAC_framework
arduino-cli upload  --fqbn adafruit:samd:adafruit_itsybitsy_m0 --port COM6 firmware/Arduino_DAC_framework
```

---

## 7. Configure instrument addresses

Connect your bench instruments to the LAN, then run:

```bash
dacdemo detect-instruments
```

This queries every VISA resource for `*IDN?`, identifies the R&S SMA100B, Keysight N9010B EXA, Keysight oscilloscope (MSO / MXR / UXR), and Keysight PSU, and writes their VISA addresses to `config/dacdemo.toml` automatically.

If instruments are on a separate LAN subnet, include `--subnet`:

```bash
dacdemo detect-instruments --subnet 192.168.10
```

If a recognized model is not found for a given role, you will be prompted to pick from all other discovered instruments or skip. This lets you assign a scope or analyzer that is not in the known-model list.

To set an address manually, edit `config/dacdemo.toml` directly:

```toml
[instruments]
siggen_addr = "TCPIP0::192.168.10.159::hislip0::INSTR"
scope_addr  = "TCPIP0::192.168.10.20::hislip0::INSTR"
sa_addr     = "TCPIP0::K-N9010B-00524::hislip0::INSTR"
psu_addr    = "TCPIP0::192.168.10.213::inst0::INSTR"
```

Use HiSLIP (`hislip0::INSTR`) for Keysight instruments where available — it is faster and more reliable than VXI-11.

---

## 8. Verify — no hardware required

These commands only need the config file and can be run before connecting any hardware:

```bash
dacdemo list-ports          # confirm the board COM port is visible to the OS
dacdemo calc                # derive f_sample and f_out from [coherent_tone]; writes back to [dac]
dacdemo gen-sine            # generate 256-sample sine table from f_out and f_sample
```

With default config (`fs_app=5000`, `x_seed=23`, `fin="low"`) you should see:

```
f_sample = 5242880000.0 Hz  (≈ 5.24 GHz)
f_out    = 471040000.0 Hz   (≈ 471 MHz)
```

---

## 9. Verify — board connected

Test in this order. Each step validates one more layer:

**Serial link** — simplest round-trip, no chip in socket required:

```bash
python -c "from dacdemo.board_control import BoardSession; s=BoardSession.open('COM6'); print(s.led_on()); print(s.led_off()); s.close()"
```

**Rail monitor read-back** — safe without a chip in the socket:

```bash
dacdemo health
```

**Set rail voltages** — requires chip in socket:

```bash
dacdemo bias --initialize-compliance
```

**Load and enable sine pattern:**

```bash
dacdemo play-sine
```

**Full sequence in one command:**

```bash
dacdemo run-demo --initialize-compliance
```

---

## 10. End-to-end measurement sequence

Once board and instruments are all confirmed working:

```bash
dacdemo calc                              # derive f_sample and f_out
dacdemo set-siggen                        # push f_sample to R&S clock source
dacdemo run-demo --initialize-compliance  # bias rails + load + enable DAC pattern
dacdemo capture                           # capture + decode + validate SPI via AD3
dacdemo scope-measure                     # measure analog output on scope
dacdemo sa-measure                        # single-frequency SA measurement
dacdemo sa-comprehensive-sweep --freqs 100e6 500e6 1e9 2e9 3e9 4e9   # SFDR/SNR/THD sweep
```

See `docs/command_reference.md` for full flag listings and `docs/quickstart.md` for coherent tone setup and sweep configuration.

---

## Troubleshooting

**`dacdemo` not found after install**
Make sure the venv is activated (`.venv\Scripts\activate`) and that `pip install -e host/` completed without errors.

**`detect-port` finds nothing**
The board may not have enumerated yet — wait a few seconds and retry. If it still fails, check Device Manager for a COM port appearing under "Ports (COM & LPT)" when the board is plugged in.

**`flash` fails with a port error**
Close any serial monitors (Arduino IDE, PuTTY, etc.) that have the COM port open. Only one process can hold the port at a time.

**`detect-instruments` finds nothing**
Confirm NI-VISA is installed and that `python -c "import pyvisa; print(pyvisa.ResourceManager().list_resources())"` returns instrument addresses. If the instruments are on a different subnet, use `--subnet A.B.C`.

**`capture` fails immediately**
Close the Digilent WaveForms GUI — the AD3 requires exclusive access and will reject connections while WaveForms is open.

**`pyvisa.errors.VisaIOError` on instrument commands**
The instrument address in `config/dacdemo.toml` is stale. Run `dacdemo detect-instruments` to refresh it, or update `[instruments]` manually.
