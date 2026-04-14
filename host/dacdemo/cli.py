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
    cfg = _cfg()
    ct = cfg["coherent_tone"]
    fs_app = args.fs_app or ct["fs_app"]
    multiplier = args.multiplier or ct["multiplier"]
    n = args.n or ct["n"]
    x_seed = args.x_seed or ct["x_seed"]
    plan = build_plan(fs_app=fs_app, multiplier=multiplier, n=n, x_seed=x_seed)
    print(json.dumps(plan.__dict__, indent=2))
    output_path = Path(cfg["paths"]["coherent_tone_plan"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan.__dict__, indent=2))
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


def build_parser():
    parser = argparse.ArgumentParser(prog="dacdemo")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list-ports")
    p.set_defaults(func=cmd_list_ports)

    p = sub.add_parser("detect-port")
    p.set_defaults(func=cmd_detect_port)

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

    p = sub.add_parser("calc")
    p.add_argument("--fs-app", type=float)
    p.add_argument("--multiplier", type=float)
    p.add_argument("--n", type=int)
    p.add_argument("--x-seed", type=int)
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

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
