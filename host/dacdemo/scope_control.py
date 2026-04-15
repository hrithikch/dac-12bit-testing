# host/dacdemo/scope_control.py
#
# Keysight oscilloscope wrapper adapted for the MSOS054A (InfiniiVision X-Series).
#
# Based on instrument_comms/instruments/keysight_scope.py but uses only the SCPI
# commands that are common across Keysight scopes. MXR404A-specific features
# (CGRade eye diagrams, RJDJ jitter) are intentionally omitted.
#
# Connection string examples:
#   HiSLIP (preferred): "TCPIP0::<ip>::hislip0::INSTR"
#   VXI-11:             "TCPIP0::<ip>::inst0::INSTR"

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "instrument_comms"))

import pyvisa


class ScopeSession:
    """
    Open session to a Keysight oscilloscope (MSOS054A or compatible).

    Usage:
        with ScopeSession(addr) as scope:
            measurements = scope.measure(channel=1)
            scope.screenshot(Path("scope.png"))
    """

    def __init__(self, addr: str, timeout_ms: int = 60_000) -> None:
        self._rm = pyvisa.ResourceManager()
        self._res = self._rm.open_resource(addr)
        self._res.timeout = timeout_ms
        self._init()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _init(self) -> None:
        self._res.clear()
        self._write("*CLS")
        self._write(":SYSTem:HEADer 0")   # suppress response headers — bare values only

    def _write(self, cmd: str) -> None:
        self._res.write(cmd)
        self._check_errors(cmd)

    def _query(self, cmd: str) -> str:
        result = self._res.query(cmd)
        self._check_errors(cmd)
        return result.strip()

    def _query_float(self, cmd: str) -> float | None:
        raw = self._query(cmd)
        try:
            v = float(raw)
            return None if v > 9e36 else v   # 9.9E+37 sentinel = measurement unavailable
        except ValueError:
            return None

    def _query_block(self, cmd: str) -> bytes:
        return self._res.query_binary_values(cmd, datatype="s", container=bytes)

    def _check_errors(self, cmd: str) -> None:
        while True:
            err = self._res.query(":SYSTem:ERRor? STRing")
            if not err:
                break
            if not err.startswith("0,"):
                print(f"Scope error after '{cmd}': {err.strip()}")
                break
            else:
                break

    # ------------------------------------------------------------------
    # Measurement
    # ------------------------------------------------------------------

    def measure(self, channel: int = 1) -> dict:
        """
        Run a standard set of measurements on the specified channel.

        Returns a dict with keys:
            channel, frequency_hz, vpp_v, rise_time_s, fall_time_s, duty_cycle_pct
        All values are float or None if the scope could not compute the measurement.
        """
        ch = f"CHANnel{channel}"
        self._write(f":MEASure:SOURce {ch}")
        self._write(":RUN")
        _ = self._query("*OPC?")

        return {
            "channel":       channel,
            "frequency_hz":  self._query_float(":MEASure:FREQuency?"),
            "vpp_v":         self._query_float(":MEASure:VPP?"),
            "rise_time_s":   self._query_float(":MEASure:RISetime?"),
            "fall_time_s":   self._query_float(":MEASure:FALLtime?"),
            "duty_cycle_pct": self._query_float(":MEASure:DUTYcycle?"),
        }

    def screenshot(self, path: Path) -> None:
        """Capture a PNG screenshot from the scope display and write it to disk."""
        self._res.timeout = 90_000   # screenshots can be slow
        data = self._query_block(":DISPlay:DATA? PNG")
        self._res.timeout = 60_000
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        print(f"Screenshot -> {path}")

    def idn(self) -> str:
        return self._query("*IDN?")

    def close(self) -> None:
        self._rm.close()


def save_measurements_csv(row: dict, path: Path) -> None:
    """Append a measurement row to a CSV file (creates with header if new)."""
    import datetime
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["timestamp"] + list(row.keys())
    write_header = not path.exists()
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            w.writeheader()
        w.writerow({"timestamp": datetime.datetime.now().isoformat(), **row})
    print(f"Measurements -> {path}")
