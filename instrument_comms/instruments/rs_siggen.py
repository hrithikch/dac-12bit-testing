import pyvisa


class RohdeAndSchwarzSignalGenerator:
    """
    Driver for Rohde & Schwarz SMA100B signal generator.

    Communicates via VISA over LAN (TCPIP/VXI-11 or HiSLIP) or USB.
    Pass the resource object from pyvisa.ResourceManager().open_resource(...).

    Connection string formats:
        LAN:  "TCPIP0::<ip_address>::inst0::INSTR"      (VXI-11)
              "TCPIP0::<ip_address>::hislip0::INSTR"     (HiSLIP)
        USB:  "USB0::0x0AAD::0x0088::<serial>::INSTR"

    All frequency commands use Hz as units.
    Level commands require the unit suffix in the string (e.g. "0 dBm", "-10 dBm").
    """

    def __init__(self, signal_generator_resource: pyvisa.resources.Resource) -> None:
        self.signal_gen = signal_generator_resource

    def check_instr_name(self):
        """Return 0 if IDN matches expected instrument, -1 otherwise."""
        if not self.signal_gen.query("*IDN?").startswith("Rohde&Schwarz,SMA100B"):
            return -1
        return 0

    def reset_sig_gen(self):
        self.signal_gen.write("*RST")

    def turn_rf_on(self):
        self.signal_gen.write("OUTPut ON")

    def turn_rf_off(self):
        self.signal_gen.write("OUTPut OFF")

    def set_continuous_wave_mode(self):
        """Set frequency mode to CW (single fixed frequency, no sweep)."""
        self.signal_gen.write("SOURce1:FREQ:MODE CW")

    def set_frequency(self, frequency_in_hertz: float):
        """Set CW output frequency in Hz."""
        self.signal_gen.write(f"SOURce1:FREQuency:CW {frequency_in_hertz}")

    def set_level(self, level_string_with_units: str):
        """
        Set output power level.

        level_string_with_units: e.g. "0 dBm", "-10 dBm", "100 mV"
        """
        self.signal_gen.write(f"SOURce1:POWer {level_string_with_units}")
