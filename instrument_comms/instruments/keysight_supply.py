import pyvisa


class KeysightPowerSupply:
    """
    Driver for Keysight E36300-series triple-output DC power supply.

    Communicates via VISA over LAN or USB.
    Pass the resource object from pyvisa.ResourceManager().open_resource(...).

    Connection string formats:
        LAN: "TCPIP0::<ip_address>::inst0::INSTR"
        USB: "USB0::0x2A8D::0x1102::<serial>::INSTR"

    Channel addressing uses the SCPI channel list syntax (@1), (@2), (@3),
    or ranges like (@1:3) for all three channels simultaneously.

    All voltage/current values are in SI units (V, A).
    """

    def __init__(self, keysight_supply_resource: pyvisa.resources.Resource) -> None:
        self.supply = keysight_supply_resource

    def set_voltage(self, channel: int, voltage: float):
        """Set output voltage on the specified channel (1, 2, or 3)."""
        self.supply.write(f"VOLTage {voltage}, (@{channel})")

    def set_all_voltages(self, v1: float, v2: float, v3: float):
        """Set voltages on channels 1, 2, and 3 individually."""
        self.supply.write(f"VOLTage {v1}, (@1)")
        self.supply.write(f"VOLTage {v2}, (@2)")
        self.supply.write(f"VOLTage {v3}, (@3)")

    def enable_all_outputs(self):
        """Enable outputs on all three channels simultaneously."""
        self.supply.write("OUTPut 1, (@1:3)")

    def disable_all_outputs(self):
        """Disable outputs on all three channels simultaneously."""
        self.supply.write("OUTPut 0, (@1:3)")

    def enable_output(self, channel: int):
        self.supply.write(f"OUTPut 1, (@{channel})")

    def disable_output(self, channel: int):
        self.supply.write(f"OUTPut 0, (@{channel})")

    def measure_current(self, channel: int) -> str:
        """Return measured output current (A) as a string."""
        return self.supply.query(f"MEASure:CURRent? CH{channel}").strip()

    def measure_voltage(self, channel: int) -> str:
        """Return measured output voltage (V) as a string."""
        return self.supply.query(f"MEASure:VOLTage? CH{channel}").strip()

    def measure_all(self) -> dict:
        """
        Return voltage, current, and calculated power for all three channels.

        Returns dict with keys: ch{N}_voltage, ch{N}_current, ch{N}_power (N=1,2,3)
        """
        results = {}
        for ch in (1, 2, 3):
            v = float(self.measure_voltage(ch))
            i = float(self.measure_current(ch))
            results[f"ch{ch}_voltage"] = v
            results[f"ch{ch}_current"] = i
            results[f"ch{ch}_power"] = v * i
        return results
