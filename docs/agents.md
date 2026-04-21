# Agent Context

Extra context for agents working in this repo. Everything user-facing lives in the other docs (`quickstart.md`, `command_reference.md`, `setup_and_testing.md`, `workflow.md`, `pin_map_analysis.md`, `sa_scpi_validated.md`) — this file captures the operational knowledge that isn't covered there.

## Repo layout at a glance

```
firmware/Arduino_DAC_framework/     # unified Arduino sketch (rails + DAC)
legacy/sketch/Arduino_DAC_control_sketch/  # legacy Phase 1 sketch (rails only)
legacy/sketch/sine_din_h/           # legacy Phase 2 sketch (sine playback)
legacy/legacy_8027_DAC_Arduino_test.py     # legacy standalone test script
host/dacdemo/                       # the Python CLI package
host/scripts/dacdemo.py             # console entry-point (registered via pyproject)
instrument_comms/instruments/       # VISA drivers (KeysightEXA, etc.)
config/dacdemo.toml                 # single source of truth for user-editable fields
config/sweeps/<name>.toml           # named sweep-frequency lists
data/captures/                      # CSV / PNG outputs of measurement commands
docs/                               # user-facing docs (agents.md is this file)
```

## Imports and entry point

The project installs a `dacdemo` console script; users invoke `dacdemo <subcommand>`. If you ever need to run the CLI directly from a checkout:

```bash
PYTHONPATH=host python host/scripts/dacdemo.py <subcommand>
```

`host/` is the package root on `sys.path`, so all internal imports are `from dacdemo.X import Y` — **never** `from host.dacdemo.X import Y`. The smoke-test trick for pure helpers:

```bash
PYTHONPATH=host python -c "from dacdemo.sfdr_analysis import classify_spur; ..."
```

## Serial protocol (firmware <-> host)

Both the unified firmware and the legacy `Arduino_DAC_control_sketch` speak the same text-based command protocol:

- Commands are ASCII strings like `SET_VOLTAGE,AVDD,0.85,AVDD18,1.8` or `READ_VOLTAGE,AVDD`.
- Single-byte boolean or 2/4-byte little-endian numeric responses for most commands.
- Multi-rail status responses use a framed format: `0xAA 0x55 <len> <payload> <xor>`, decoded by `dacdemo.serial_utils.read_status_frame`.

Consequence: `dacdemo bias` works against either firmware. The legacy test script is a fixed demo (hardcoded COM port, 3 rails, LED/DIO/ADC/LDO checks); `cmd_bias` is the generalized config-driven version.

**Gotcha:** the unified firmware resets rails on each serial open (because Adafruit SAMD boards reboot when the CDC port is opened). Prefer `dacdemo run-demo` over calling `bias` and `play-sine` as separate commands — `run-demo` uses a single serial session. This is captured in `MEMORY.md`.

## arduino-cli expectations

`cmd_flash` shells out to `arduino-cli compile` + `arduino-cli upload`. arduino-cli requires the **sketch folder name to match the .ino file's basename**. The legacy control sketch originally lived as a loose `legacy/sketch/Arduino_DAC_control_sketch.ino` — it has since been moved into `legacy/sketch/Arduino_DAC_control_sketch/` to satisfy this rule. If you add another sketch, keep the `foo/foo.ino` layout.

## CSV writer — schema pinning and auto-archive

`dacdemo.siganalyzer_control.save_measurements_csv` accepts an optional `fieldnames=` argument that pins column order. When writing:

- If no file exists: header is written from `fieldnames`.
- If the file exists and its header does **not** match `fieldnames`: the old file is renamed to `<stem>.legacy-<YYYYMMDDTHHMMSS><ext>` (with a `-N` collision suffix if the same second already has an archive) and a fresh file is started.
- If `fieldnames=None`: falls back to the legacy "infer from row keys" behavior. Used by `sa-measure` and `sa-sfdr`.

When adding columns to `sa-sfdr-sweep`:
1. Extend `SFDR_SWEEP_FIELDNAMES` at the top of `host/dacdemo/siganalyzer_control.py`.
2. Ensure `measure_sfdr` and `measure_sfdr_windowed` both return dicts containing the new keys (use `NaN` when a field doesn't apply to a given mode).
3. Populate the new keys in `cmd_sa_sfdr_sweep` before the `save_measurements_csv` call.
4. Users' existing CSVs will be auto-archived on the next run — no manual migration needed.

## SFDR analysis helpers

`host/dacdemo/sfdr_analysis.py` holds pure functions for Nyquist-aliasing math and spur classification:

- `alias_to_nyquist(f, fs)` — fold a frequency into `[0, fs/2]`.
- `expected_harmonics(fund, fs, orders=(2,3,4,5))` — predicted aliased harmonic locations.
- `classify_spur(spur, fund, fs, tol_hz, orders=(2,3,4,5))` — returns `'harmonic_N'`, `'bin_split'`, `'other'`, or `'unknown'`. Bin-split is checked **first** because the user explicitly wants it flagged even if an unusual config made H2 land near the fundamental.

Tolerance at the call site in `cmd_sa_sfdr_sweep` is `max(3 * sweep_span / 1001, 2 * rbw_hz, dac_clock_hz / num_samples)`. `sweep_span` is the actual span being swept per acquisition: the full Nyquist span in single mode, one sub-window's span in windowed mode. 1001 is the default trace-point count on the Keysight N9010B EXA — the `3×` factor covers leakage into a few adjacent display bins.

## Instrument discovery and addresses

`dacdemo detect-instruments` uses both VISA RM enumeration and an optional LAN subnet scan (`--subnet 192.168.10`). Matched instruments are written back to `[instruments]` in `config/dacdemo.toml` (`siggen_addr`, `sa_addr`, `scope_addr`). When instruments aren't on the list, verify with `visa-shell` / `pyvisa.ResourceManager().list_resources()` before blaming the code.

## Coherent-tone math

Frequencies are quantized to "prime bins": the DAC plays only at `k * f_sample / N` for prime `k`, so the tone lands cleanly in one FFT bin and stays coherent across `N` samples. `dacdemo calc` derives `f_sample` and `f_out`; `find_coherent_bin` snaps an arbitrary requested frequency to the nearest prime bin. Never hand-edit `[dac] f_sample` or `f_out` — they are derived fields.

## Windows / shell gotchas

- Default shell in this repo's harness is `bash` on Windows (use Unix syntax; forward slashes work for most paths). PowerShell examples in docs assume the user's own shell, not the agent's.
- Python console codepage is cp1252 by default — **em-dashes (`—`) render as `?`** when printed from subprocess or CLI flows captured by the harness. Use ASCII (`-`) in `print()` strings to avoid confusion. Markdown docs are fine; runtime messages are not.
- The repo lives under a OneDrive path with spaces in it. Always quote paths; always use absolute paths when invoking Python scripts.

## Testing without hardware

- Pure helpers: import under `PYTHONPATH=host` and exercise directly. See the smoke test pattern at the end of the plan file `C:\Users\nuc-user\.claude\plans\dacdemo-sa-sfdr-sweep-windowed-humble-stallman.md`.
- CSV writer: pass a temp path (`tempfile.TemporaryDirectory()`) and a canned row dict; you can validate the auto-archive behavior end-to-end without any instruments.
- Measurement commands (`sa-*`, `scope-*`, `capture`, any `bias`/`play-sine` variant): **require hardware**. Don't fabricate tool results or add mock branches — when you can't run them, say so and let the user verify.

## Memory: stable notes across conversations

`MEMORY.md` (in `~/.claude/projects/<this-project>/memory/`) persists across sessions. Current notable entries:

- **Legacy DAC workflow** — legacy uses two sketches; unified firmware resets rails on each serial open; prefer `run-demo` over `bias + play-sine`.

If you learn something durable about the user or this repo (a preference, a non-obvious constraint, a frequently-referenced external resource), save it to memory so the next session has it.
