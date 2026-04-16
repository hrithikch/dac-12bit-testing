import argparse
import json
import subprocess
import sys
from pathlib import Path

import serial.tools.list_ports

from dacdemo.board_control import BoardSession, list_ports
from dacdemo.coherent_tone import build_plan
from dacdemo.sine_gen import generate_sine_codes
from dacdemo import config as _config
from dacdemo.config import set_dac_freq, set_f_sample, set_coherent_params, set_siggen_addr, set_sa_addr, set_scope_addr

ADAFRUIT_VID = 0x239A


def _cfg():
    return _config.load()


def cmd_list_ports(_args):
    for port in list_ports():
        print(port)


def cmd_flash(args):
    cfg = _cfg()
    fqbn   = args.fqbn   or cfg["firmware"]["fqbn"]
    sketch = args.sketch or cfg["firmware"]["sketch"]
    port   = args.port   or cfg["hardware"]["port"]

    compile_cmd = ["arduino-cli", "compile", "--fqbn", fqbn, sketch]
    upload_cmd  = ["arduino-cli", "upload",  "--fqbn", fqbn, "--port", port, sketch]

    print(f"Compiling {sketch}...")
    result = subprocess.run(compile_cmd)
    if result.returncode != 0:
        sys.exit("Compile failed.")

    print(f"Uploading to {port}...")
    result = subprocess.run(upload_cmd)
    if result.returncode != 0:
        sys.exit("Upload failed.")

    print("Done.")


def cmd_detect_port(_args):
    matches = [
        p for p in serial.tools.list_ports.comports()
        if p.vid == ADAFRUIT_VID
    ]
    if not matches:
        print("No Adafruit board found. Is it plugged in?")
        return
    if len(matches) > 1:
        print("Multiple Adafruit boards found — specify one with --port:")
        for p in matches:
            print(f"  {p.device}  ({p.description})")
        return
    port = matches[0].device
    _config.set_port(port)
    print(f"Detected {matches[0].description} on {port} — config updated.")


def cmd_detect_instruments(args):
    """
    Discover the signal generator, signal analyzer, and oscilloscope and
    update their addresses in config.
    """
    import time
    from dacdemo.discover import discover_via_visa, scan_subnet, visa_string_hint

    all_results = []
    t0 = time.time()

    print("\n--- VISA Resource Manager ---")
    all_results += discover_via_visa(timeout_ms=args.visa_timeout)

    if args.subnet:
        parts = args.subnet.split(".")
        if len(parts) != 3 or not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
            sys.exit(f"ERROR: --subnet must be three octets, e.g. 192.168.10  (got '{args.subnet}')")
        print("\n--- LAN Subnet Scan ---")
        all_results += scan_subnet(
            subnet=args.subnet,
            connect_timeout=args.timeout,
            max_workers=args.threads,
            visa_timeout_ms=args.visa_timeout,
        )

    def _visa_addr(inst):
        return inst.address if inst.source == "VISA" else (visa_string_hint(inst) or inst.address)

    def _dedup(matches):
        """Drop duplicates where two entries report the same IDN (same physical instrument)."""
        seen, result = set(), []
        for inst in matches:
            key = inst.idn if inst.idn else id(inst)
            if key not in seen:
                seen.add(key)
                result.append(inst)
        return result

    def _pick(matches, display_name):
        """Return chosen DiscoveredInstrument or None."""
        matches = _dedup(matches)
        if not matches:
            print(f"  WARNING: no {display_name} found — skipping.")
            return None
        if len(matches) == 1:
            return matches[0]
        print(f"\n  Multiple {display_name}s found:")
        for i, inst in enumerate(matches):
            print(f"    [{i + 1}] {_visa_addr(inst)}  —  {inst.idn}")
        while True:
            try:
                idx = int(input(f"  Select {display_name} number: ")) - 1
                if 0 <= idx < len(matches):
                    return matches[idx]
            except (ValueError, KeyboardInterrupt):
                pass
            print(f"  Please enter a number between 1 and {len(matches)}.")

    targets = [
        (
            lambda inst: inst.label and "SMA100" in inst.label.upper(),
            "R&S SMA100B signal generator",
            set_siggen_addr,
        ),
        (
            lambda inst: inst.label and "N9010B" in inst.label.upper(),
            "Keysight N9010B signal analyzer",
            set_sa_addr,
        ),
        (
            lambda inst: inst.label and ("MSO" in inst.label.upper() or "MXR" in inst.label.upper()),
            "Keysight oscilloscope",
            set_scope_addr,
        ),
    ]

    print()
    any_updated = False
    for match_fn, display_name, setter in targets:
        matches = [inst for inst in all_results if match_fn(inst)]
        chosen = _pick(matches, display_name)
        if chosen is not None:
            addr = _visa_addr(chosen)
            setter(addr)
            print(f"  {display_name}: {addr} — config updated.")
            any_updated = True

    if not any_updated:
        print("No recognized instruments found. Is the network/VISA connection up?")

    print(f"\nDiscovery completed in {time.time() - t0:.1f} s")


def cmd_bias(args):
    cfg = _cfg()
    port = args.port or cfg["hardware"]["port"]
    baudrate = args.baudrate or cfg["hardware"]["baudrate"]
    rails = cfg["rails"]
    sess = BoardSession.open(port=port, baudrate=baudrate)
    try:
        if args.initialize_compliance:
            print({"initialize_compliance": sess.initialize_compliance()})
        result = sess.set_voltages(rails)
        print({"set_voltages": result})
        for rail in rails:
            print({"rail": rail, "voltage_V": round(sess.read_voltage(rail), 6)})
    finally:
        sess.close()


def cmd_health(args):
    cfg = _cfg()
    port = args.port or cfg["hardware"]["port"]
    baudrate = args.baudrate or cfg["hardware"]["baudrate"]
    rails = args.rails or list(cfg["rails"].keys())
    sess = BoardSession.open(port=port, baudrate=baudrate)
    try:
        for rail in rails:
            print({
                "rail": rail,
                "voltage_V": round(sess.read_voltage(rail), 6),
                "shunt_mV": round(sess.read_shuntv(rail), 6),
                "current_mA": round(sess.read_current(rail), 6),
                "power_mW": round(sess.read_power(rail), 6),
            })
    finally:
        sess.close()


def cmd_calc(args):
    from dacdemo.coherent_tone import find_coherent_bin

    cfg = _cfg()
    ct  = cfg["coherent_tone"]
    dac = cfg["dac"]

    fs_app = args.fs_app or ct["fs_app"]
    n      = dac["num_samples"]          # single source of truth — not duplicated in [coherent_tone]
    x_seed = args.x_seed or ct["x_seed"]
    fin    = ct["fin"]

    if args.from_fout is not None:
        # Back-calculation: find the prime bin closest to the desired f_out,
        # then update [coherent_tone] so the forward calc produces consistent state.
        fs_actual_current = build_plan(fs_app=fs_app, n=n, x_seed=x_seed, fin=fin).fs_actual
        x_seed, fin = find_coherent_bin(args.from_fout, fs_actual_current, n)
        set_coherent_params(x_seed, fin)
        print(f"Back-calc: x_seed={x_seed}, fin={fin!r}  (target {args.from_fout/1e6:.4f} MHz)")

    plan = build_plan(fs_app=fs_app, n=n, x_seed=x_seed, fin=fin)
    print(json.dumps(plan.__dict__, indent=2))

    output_path = Path(cfg["paths"]["coherent_tone_plan"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan.__dict__, indent=2))

    set_dac_freq(f_out=plan.f_out, f_sample=plan.fs_actual)
    print(f"config updated: f_out={plan.f_out/1e6:.4f} MHz, f_sample={plan.fs_actual/1e9:.6f} GHz")
    print(output_path)


def cmd_gen_sine(args):
    cfg = _cfg()
    f_out = args.f_out or cfg["dac"]["f_out"]
    f_sample = args.f_sample or cfg["dac"]["f_sample"]
    num_samples = args.num_samples or cfg["dac"]["num_samples"]
    output = args.output or cfg["paths"]["sine_output"]
    codes = generate_sine_codes(f_out=f_out, f_sample=f_sample, num_samples=num_samples)
    out = {
        "f_out": f_out,
        "f_sample": f_sample,
        "num_samples": num_samples,
        "codes": codes,
    }
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(out, indent=2))
    print(output_path)


def cmd_play_sine(args):
    cfg = _cfg()
    port = args.port or cfg["hardware"]["port"]
    baudrate = args.baudrate or cfg["hardware"]["baudrate"]
    f_out = args.f_out or cfg["dac"]["f_out"]
    f_sample = args.f_sample or cfg["dac"]["f_sample"]
    sess = BoardSession.open(port=port, baudrate=baudrate)
    try:
        print({"dac_play_sine": sess.dac_play_sine(f_out=f_out, f_sample=f_sample)})
    finally:
        sess.close()


def cmd_run_demo(args):
    cfg = _cfg()
    port = args.port or cfg["hardware"]["port"]
    baudrate = args.baudrate or cfg["hardware"]["baudrate"]
    f_out = args.f_out or cfg["dac"]["f_out"]
    f_sample = args.f_sample or cfg["dac"]["f_sample"]
    rails = cfg["rails"]
    sess = BoardSession.open(port=port, baudrate=baudrate)
    try:
        if args.initialize_compliance:
            print({"initialize_compliance": sess.initialize_compliance()})
        print({"set_voltages": sess.set_voltages(rails)})
        for rail in rails:
            print({"rail": rail, "voltage_V": round(sess.read_voltage(rail), 6)})
        print({"dac_play_sine": sess.dac_play_sine(f_out=f_out, f_sample=f_sample)})
    finally:
        sess.close()


# ---------------------------------------------------------------------------
# Instrument commands
# ---------------------------------------------------------------------------

def _coherent_tone_summary(f_sample: float, num_samples: int, ct_cfg: dict) -> None:
    """Print coherent f_out options for the given f_sample, marking the active bin."""
    from dacdemo.coherent_tone import nearest_prime_bins
    bins = nearest_prime_bins(ct_cfg["x_seed"])
    active_fin = ct_cfg["fin"]
    active_bin = bins[0] if active_fin == "low" else bins[-1]
    for b in bins:
        f = b * f_sample / num_samples
        marker = "  <-- active (fin=" + active_fin + ")" if b == active_bin else ""
        print(f"    bin {b:3d}  ->  f_out = {f / 1e6:.4f} MHz{marker}")


def cmd_set_siggen(args):
    """
    Set the R&S SMA100B to the DAC sample clock frequency.

    If --freq is supplied, f_sample is updated in config and the coherent
    tone frequencies for the new f_sample are printed so the user knows
    which f_out values remain valid. Run 'dacdemo calc' afterwards if you
    need to regenerate the full coherent tone plan.
    """
    from dacdemo.siggen_control import SiggenSession

    cfg = _cfg()
    addr = cfg["instruments"]["siggen_addr"]
    instruments_cfg = cfg["instruments"]
    if args.level is not None:
        level = args.level
    elif "siggen_level" in instruments_cfg:
        level = instruments_cfg["siggen_level"]
    else:
        level = f'{instruments_cfg["siggen_level_dbm"]} dBm'

    if args.freq is not None:
        set_f_sample(args.freq)
        print(f"Config updated: f_sample = {args.freq / 1e9:.6f} GHz")
        print("Valid coherent f_out values for new f_sample:")
        _coherent_tone_summary(args.freq, cfg["dac"]["num_samples"], cfg["coherent_tone"])
        print("  (Run 'dacdemo calc' to regenerate the full coherent tone plan.)\n")

    f_sample = args.freq or cfg["dac"]["f_sample"]

    with SiggenSession(addr) as sg:
        if args.off:
            sg.rf_off()
        else:
            sg.set_clock(f_sample, level)


def cmd_capture(args):
    """Capture ItsyBitsy SPI signals via AD3, decode, and optionally validate."""
    from dacdemo.ad3_capture import run as ad3_run

    cfg = _cfg()
    output_dir = Path(args.output_dir) if args.output_dir else Path("data/captures")

    result = ad3_run(
        port=cfg["hardware"]["port"],
        baudrate=cfg["hardware"]["baudrate"],
        f_out=cfg["dac"]["f_out"],
        f_sample=cfg["dac"]["f_sample"],
        output_dir=output_dir,
        validate=not args.no_validate,
    )
    if result["mismatches"]:
        print(f"\n{len(result['mismatches'])} mismatch(es) detected.")
    else:
        print("\nCapture complete.")


def cmd_scope_measure(args):
    """Take measurements from the Keysight MSOS054A oscilloscope."""
    from dacdemo.scope_control import ScopeSession, save_measurements_csv

    cfg = _cfg()
    addr = cfg["instruments"]["scope_addr"]
    channel = args.channel or 1
    output = Path(args.output) if args.output else Path("data/captures/scope_measurements.csv")

    with ScopeSession(addr) as scope:
        print(f"Connected: {scope.idn()}")
        measurements = scope.measure(channel=channel)
        for k, v in measurements.items():
            print(f"  {k}: {v}")
        save_measurements_csv(measurements, output)
        if args.screenshot:
            scope.screenshot(output.parent / "scope_screenshot.png")


def cmd_discover(args):
    """Scan for VISA instruments and (optionally) a LAN subnet."""
    import time
    from dacdemo.discover import (
        discover_via_visa, scan_subnet, discover_analog_discovery, print_results,
    )

    all_results = []
    t0 = time.time()

    if not args.skip_visa:
        print("\n--- VISA Resource Manager ---")
        all_results += discover_via_visa(timeout_ms=args.visa_timeout)

    if args.subnet:
        parts = args.subnet.split(".")
        if len(parts) != 3 or not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
            sys.exit(f"ERROR: --subnet must be three octets, e.g. 192.168.1  (got '{args.subnet}')")
        print("\n--- LAN Subnet Scan ---")
        all_results += scan_subnet(
            subnet=args.subnet,
            connect_timeout=args.timeout,
            max_workers=args.threads,
            visa_timeout_ms=args.visa_timeout,
        )

    if not args.skip_ad2:
        print("\n--- Analog Discovery ---")
        all_results += discover_analog_discovery()

    print_results(all_results)
    print(f"Discovery completed in {time.time() - t0:.1f} s")


def cmd_sa_measure(args):
    """Peak-power measurement on the Keysight N9010B EXA Signal Analyzer."""
    from dacdemo.siganalyzer_control import SASession, save_measurements_csv

    cfg = _cfg()
    addr = cfg["instruments"]["sa_addr"]
    center_hz = args.center or cfg["dac"]["f_out"]
    span_hz   = args.span   or 2e6
    rbw_hz    = args.rbw    or 10e3
    vbw_hz    = args.vbw    or 10e3
    ref_dbm   = args.ref    if args.ref is not None else 0.0
    output    = Path(args.output) if args.output else Path("data/captures/sa_measurements.csv")

    with SASession(addr) as sa:
        print(f"Connected: {sa.idn()}")
        measurements = sa.measure(
            center_hz=center_hz,
            span_hz=span_hz,
            rbw_hz=rbw_hz,
            vbw_hz=vbw_hz,
            ref_level_dbm=ref_dbm,
        )
        for k, v in measurements.items():
            print(f"  {k}: {v}")
        save_measurements_csv(measurements, output)
        if args.screenshot:
            sa.screenshot(output.parent / "sa_screenshot.png")


def build_parser():
    parser = argparse.ArgumentParser(prog="dacdemo")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list-ports")
    p.set_defaults(func=cmd_list_ports)

    p = sub.add_parser("detect-port")
    p.set_defaults(func=cmd_detect_port)

    p = sub.add_parser("detect-instruments",
        help="Discover signal generator, signal analyzer, and oscilloscope; update config addresses")
    p.add_argument("--subnet", metavar="A.B.C",
        help="Also scan this subnet for LAN instruments (e.g. 192.168.10)")
    p.add_argument("--timeout", type=float, default=0.5, metavar="SEC",
        help="TCP connect timeout per host during LAN scan (default: 0.5 s)")
    p.add_argument("--visa-timeout", type=int, default=5000, metavar="MS",
        help="VISA IDN query timeout in milliseconds (default: 5000)")
    p.add_argument("--threads", type=int, default=64,
        help="Thread pool size for LAN scan (default: 64)")
    p.set_defaults(func=cmd_detect_instruments)

    p = sub.add_parser("flash")
    p.add_argument("--fqbn")
    p.add_argument("--sketch")
    p.add_argument("--port")
    p.set_defaults(func=cmd_flash)

    p = sub.add_parser("bias")
    p.add_argument("--port")
    p.add_argument("--baudrate", type=int)
    p.add_argument("--initialize-compliance", action="store_true")
    p.set_defaults(func=cmd_bias)

    p = sub.add_parser("health")
    p.add_argument("--port")
    p.add_argument("--baudrate", type=int)
    p.add_argument("--rails", nargs="+")
    p.set_defaults(func=cmd_health)

    p = sub.add_parser("calc",
        help="Compute coherent tone plan and update [dac] f_sample + f_out in config")
    p.add_argument("--fs-app", type=float,
        metavar="HZ_APP",
        help="Override fs_app (maps to f_sample via fixed 2^20 scale)")
    p.add_argument("--x-seed", type=int,
        metavar="N",
        help="Override x_seed (prime bin search seed)")
    p.add_argument("--from-fout", type=float,
        metavar="HZ",
        help="Back-calculate x_seed/fin from a desired f_out, then run forward calc")
    p.set_defaults(func=cmd_calc)

    p = sub.add_parser("gen-sine")
    p.add_argument("--f-out", type=float)
    p.add_argument("--f-sample", type=float)
    p.add_argument("--num-samples", type=int)
    p.add_argument("--output")
    p.set_defaults(func=cmd_gen_sine)

    p = sub.add_parser("play-sine")
    p.add_argument("--port")
    p.add_argument("--baudrate", type=int)
    p.add_argument("--f-out", type=float)
    p.add_argument("--f-sample", type=float)
    p.set_defaults(func=cmd_play_sine)

    p = sub.add_parser("run-demo")
    p.add_argument("--port")
    p.add_argument("--baudrate", type=int)
    p.add_argument("--initialize-compliance", action="store_true")
    p.add_argument("--f-out", type=float)
    p.add_argument("--f-sample", type=float)
    p.set_defaults(func=cmd_run_demo)

    p = sub.add_parser("set-siggen",
        help="Set the R&S SMA100B to the DAC sample clock frequency")
    p.add_argument("--freq", type=float,
        metavar="HZ",
        help="Override f_sample (Hz). Updates config and shows valid coherent f_out values.")
    p.add_argument("--level",
        metavar="LEVEL",
        help='Output level with units, e.g. "700 mV" or "0 dBm" (default: siggen_level from config)')
    p.add_argument("--off", action="store_true",
        help="Turn RF output off")
    p.set_defaults(func=cmd_set_siggen)

    p = sub.add_parser("capture",
        help="Capture ItsyBitsy SPI signals via AD3 and decode to CSV")
    p.add_argument("--no-validate", action="store_true",
        help="Skip comparison against expected sine pattern")
    p.add_argument("--output-dir",
        metavar="PATH",
        help="Output directory for CSV files (default: data/captures/)")
    p.set_defaults(func=cmd_capture)

    p = sub.add_parser("scope-measure",
        help="Measure DAC analog output via Keysight MSOS054A")
    p.add_argument("--channel", type=int, metavar="N",
        help="Scope channel to measure (default: 1)")
    p.add_argument("--screenshot", action="store_true",
        help="Also save a PNG screenshot")
    p.add_argument("--output", metavar="PATH",
        help="Output CSV path (default: data/captures/scope_measurements.csv)")
    p.set_defaults(func=cmd_scope_measure)

    p = sub.add_parser("sa-measure",
        help="Peak-power measurement via Keysight N9010B EXA Signal Analyzer")
    p.add_argument("--center", type=float, metavar="HZ",
        help="Center frequency in Hz (default: dac.f_out from config)")
    p.add_argument("--span", type=float, metavar="HZ",
        help="Frequency span in Hz (default: 2e6)")
    p.add_argument("--rbw", type=float, metavar="HZ",
        help="Resolution bandwidth in Hz (default: 10e3)")
    p.add_argument("--vbw", type=float, metavar="HZ",
        help="Video bandwidth in Hz (default: 10e3)")
    p.add_argument("--ref", type=float, metavar="DBM",
        help="Reference level in dBm (default: 0.0)")
    p.add_argument("--screenshot", action="store_true",
        help="Also save a PNG screenshot")
    p.add_argument("--output", metavar="PATH",
        help="Output CSV path (default: data/captures/sa_measurements.csv)")
    p.set_defaults(func=cmd_sa_measure)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
