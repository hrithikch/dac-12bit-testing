import pyvisa


class KeithleyPowerSupply:
    """
    Driver for Keithley 2230-30-1 triple-output DC power supply.

    Communicates over USB (USBTMC) via pyvisa.
    Pass the resource object from pyvisa.ResourceManager().open_resource(...).

    Connection string format:
        "USB0::0x05E6::0x2230::<serial>::INSTR"

    The 2230-30-1 has three independent output channels selected with
    INSTrument:NSELect {1|2|3}. Channels 1 and 2 can be tracked (mirrored);
    disable tracking before setting voltages independently.
    """

    def __init__(self, keithley_power_supply_resource: pyvisa.resources.Resource) -> None:
        self.power_supply = keithley_power_supply_resource

    def check_instr_name(self):
        """Return 0 if IDN matches expected instrument, -1 otherwise."""
        if not self.power_supply.query("*IDN?").startswith("Keithley instruments, 2230-30-1"):
            return -1
        return 0

    def reset_supply(self):
        self.power_supply.write("*RST")

    def turn_output_on(self):
        self.power_supply.write("OUTPut 1")

    def turn_output_off(self):
        self.power_supply.write("OUTPut 0")

    def turn_track_mode_off(self):
        """Disable channel tracking so CH1 and CH2 can be set independently."""
        self.power_supply.write("OUTPut:TRACK 0")

    def select_channel(self, channel_num: int):
        """
        Select active channel for subsequent voltage/current commands.

        channel_num: 1, 2, or 3 (1-based)
        """
        self.power_supply.write(f"INSTrument:NSELect {channel_num}")

    def set_channel_voltage(self, channel_num: int, voltage: float):
        """
        Set voltage on the specified channel.

        channel_num: 1, 2, or 3 (1-based)
        voltage    : target voltage in volts
        """
        self.power_supply.write(f"INSTrument:NSELect {channel_num}")
        self.power_supply.write(f"VOLTage {voltage}")

    def measure_power(self, channel_num: int) -> str:
        """Return measured power (W) on the specified channel as a string."""
        self.power_supply.write(f"INSTrument:NSELect {channel_num}")
        return self.power_supply.query("MEASure:POWer?").strip()

    def measure_voltage(self, channel_num: int) -> str:
        """Return measured output voltage (V) on the specified channel."""
        self.power_supply.write(f"INSTrument:NSELect {channel_num}")
        return self.power_supply.query("MEASure:VOLTage?").strip()

    def measure_current(self, channel_num: int) -> str:
        """Return measured output current (A) on the specified channel."""
        self.power_supply.write(f"INSTrument:NSELect {channel_num}")
        return self.power_supply.query("MEASure:CURRent?").strip()
