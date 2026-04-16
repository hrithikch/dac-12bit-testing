import pyvisa
import sys


class KeysightEXA:
    """
    Driver for Keysight N9010B EXA Signal Analyzer (X-Series).

    Wraps a pyvisa Resource opened via TCPIP (LAN).
    Pass the resource object from pyvisa.ResourceManager().open_resource(...).

    Connection string format:
        "TCPIP0::<ip_address>::hislip0::INSTR"   (HiSLIP, preferred)
        "TCPIP0::<ip_address>::inst0::INSTR"      (VXI-11)

    Instrument errors are polled after every command via :SYSTem:ERRor?.
    Commands follow Spectrum Analyzer mode SCPI (X-Series programmer's guide).
    """

    def __init__(self, exa_resource: pyvisa.resources.Resource, debug: bool = False) -> None:
        self.exa = exa_resource
        self.debug = debug

    def check_instrument_name(self) -> bool:
        idn = self.do_query_string("*IDN?").upper()
        return "N9010B" in idn and "KEYSIGHT" in idn

    def set_timeout(self, timeout_ms: int) -> None:
        self.exa.timeout = timeout_ms

    def clear_status(self) -> None:
        self.do_command("*CLS")

    def preset(self) -> None:
        self.do_command("*RST")

    # ------------------------------------------------------------------
    # Spectrum Analyzer setup
    # ------------------------------------------------------------------

    def configure_spectrum_view(
        self,
        center_hz: float,
        span_hz: float,
        rbw_hz: float,
        vbw_hz: float,
        ref_level_dbm: float,
    ) -> None:
        """Set center frequency, span, RBW, VBW, and reference level."""
        self.do_command(f":FREQuency:CENTer {center_hz}")
        self.do_command(f":FREQuency:SPAN {span_hz}")
        self.do_command(f":BANDwidth {rbw_hz}")
        self.do_command(f":BANDwidth:VIDeo {vbw_hz}")
        self.do_command(f":DISPlay:WINDow:TRACe:Y:RLEVel {ref_level_dbm}")

    def single_sweep(self) -> None:
        """Trigger one complete sweep and block until it finishes."""
        self.do_command(":INITiate:CONTinuous OFF")
        self.do_query_number(":INITiate:IMMediate;*OPC?")

    def continuous_sweep_on(self) -> None:
        self.do_command(":INITiate:CONTinuous ON")

    # ------------------------------------------------------------------
    # Marker
    # ------------------------------------------------------------------

    def move_marker_to_peak(self) -> None:
        """Place marker 1 on the highest amplitude point in the trace."""
        self.do_command(":CALCulate:MARKer1:MAXimum")

    def get_marker_frequency_hz(self) -> float:
        return self.do_query_number(":CALCulate:MARKer1:X?")

    def get_marker_amplitude_dbm(self) -> float:
        return self.do_query_number(":CALCulate:MARKer1:Y?")

    # ------------------------------------------------------------------
    # Trace data
    # ------------------------------------------------------------------

    def get_trace_ascii(self) -> list:
        """Fetch trace 1 amplitude values as a list of floats (dBm)."""
        if self.debug:
            print("QyA: :TRACe:DATA? TRACe1")
        result = self.exa.query_ascii_values(":TRACe:DATA? TRACe1")
        self.check_instrument_errors(":TRACe:DATA? TRACe1", exit_on_error=False)
        return result

    # ------------------------------------------------------------------
    # Screen capture
    # ------------------------------------------------------------------

    def save_screen_image_to_file(self, path) -> None:
        """Capture a PNG screenshot from the analyzer display and write to disk."""
        import pathlib
        data = self.do_query_ieee_block(":MMEMory:STORe:SCReen \"SA_screen.png\";:MMEMory:DATA? \"SA_screen.png\"")
        p = pathlib.Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        print(f"Screen image saved to {p}")

    # ------------------------------------------------------------------
    # Low-level VISA helpers (same pattern as KeysightOscilloscope)
    # ------------------------------------------------------------------

    def do_command(self, command: str) -> None:
        if self.debug:
            print(f"Cmd = '{command}'")
        self.exa.write(command)
        self.check_instrument_errors(command, exit_on_error=False)

    def do_query_string(self, query: str) -> str:
        if self.debug:
            print(f"Qys = '{query}'")
        result = self.exa.query(query)
        self.check_instrument_errors(query, exit_on_error=False)
        return result

    def do_query_number(self, query: str) -> float:
        if self.debug:
            print(f"Qyn = '{query}'")
        result = self.exa.query(query)
        self.check_instrument_errors(query, exit_on_error=False)
        if not result:
            return None
        return float(result)

    def do_query_ieee_block(self, query: str) -> bytes:
        if self.debug:
            print(f"Qyb = '{query}'")
        result = self.exa.query_binary_values(query, datatype="s", container=bytes)
        self.check_instrument_errors(query, exit_on_error=False)
        return result

    def check_instrument_errors(self, command: str, exit_on_error: bool = True) -> None:
        """Poll :SYSTem:ERRor? until the error queue is empty."""
        while True:
            error_string: str = self.exa.query(":SYSTem:ERRor?")
            if error_string:
                if not (error_string.startswith("+0") or error_string.startswith("0,")):
                    print(f"ERROR: {error_string.strip()}, command: '{command}'")
                    if exit_on_error:
                        print("Exited because of error.")
                        sys.exit(1)
                else:
                    break
            else:
                print(f"ERROR: :SYSTem:ERRor? returned nothing, command: '{command}'")
                print("Exited because of error.")
                sys.exit(1)
