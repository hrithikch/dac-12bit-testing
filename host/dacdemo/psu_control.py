import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "instrument_comms"))

import pyvisa
from instruments.keysight_supply import KeysightPowerSupply


class PsuSession:
    """Thin wrapper around the Keysight E363xx PSU for pre-bias bench setup."""

    def __init__(self, addr: str, timeout_ms: int = 30_000) -> None:
        self._rm = pyvisa.ResourceManager()
        resource = self._rm.open_resource(addr)
        resource.timeout = timeout_ms
        self._resource = resource
        self._psu = KeysightPowerSupply(resource)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def idn(self) -> str:
        return self._resource.query("*IDN?").strip()

    def _query_float(self, command: str) -> float | None:
        try:
            return float(self._resource.query(command).strip())
        except Exception:
            return None

    def configured_voltage(self, channel: int) -> float | None:
        return self._query_float(f"VOLTage? (@{channel})")

    def configured_current_limit(self, channel: int) -> float | None:
        return self._query_float(f"CURRent? (@{channel})")

    def output_enabled(self, channel: int) -> bool | None:
        try:
            value = self._resource.query(f"OUTPut? (@{channel})").strip()
            return value in {"1", "ON", "on"}
        except Exception:
            return None

    def ensure_channel(
        self,
        channel: int,
        voltage: float,
        current_limit: float,
        tolerance: float = 1e-6,
    ) -> dict:
        prev_voltage = self.configured_voltage(channel)
        prev_current = self.configured_current_limit(channel)
        prev_output = self.output_enabled(channel)

        voltage_ok = prev_voltage is not None and abs(prev_voltage - voltage) <= tolerance
        current_ok = prev_current is not None and abs(prev_current - current_limit) <= tolerance
        output_ok = prev_output is True

        changed = not (voltage_ok and current_ok and output_ok)
        if changed:
            self._psu.set_voltage(channel, voltage)
            self._resource.write(f"CURRent {current_limit}, (@{channel})")
            self._psu.enable_output(channel)

        return {
            "channel": channel,
            "voltage_target_V": voltage,
            "current_limit_A": current_limit,
            "voltage_prev_V": prev_voltage,
            "current_limit_prev_A": prev_current,
            "output_prev_on": prev_output,
            "changed": changed,
        }

    def close(self) -> None:
        self._resource.close()
        self._rm.close()
