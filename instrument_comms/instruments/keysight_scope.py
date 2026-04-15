import pyvisa
import sys
import pathlib


class KeysightOscilloscope:
    """
    Driver for Keysight MXR404A oscilloscope (and compatible Keysight scopes).

    Wraps a pyvisa Resource opened via TCPIP (LAN).
    Pass the resource object from pyvisa.ResourceManager().open_resource(...).

    Connection string format:
        "TCPIP0::<ip_address>::hislip0::INSTR"   (HiSLIP, preferred for MXR)
        "TCPIP0::<ip_address>::inst0::INSTR"      (VXI-11)

    All instrument errors are checked after every command via :SYSTem:ERRor? STRing.
    """

    def __init__(self, keysight_scope_resource: pyvisa.resources.Resource, debug=False) -> None:
        self.keysight_scope = keysight_scope_resource
        self.debug = debug

    def check_instrument_name(self):
        return self.do_query_string("*IDN?").startswith("KEYSIGHT TECHNOLOGIES,MXR404A")

    def set_timeout(self, timeout_val: int):
        """Set VISA timeout in milliseconds."""
        self.keysight_scope.timeout = timeout_val

    def clear_status(self):
        self.do_command("*CLS")

    def load_default_setup(self):
        self.do_command("*RST")

    def turn_off_system_header(self):
        """Suppress response headers so query results are bare values."""
        self.do_command(":SYSTem:HEADer 0")

    def load_setup_from_file(self, setup_file_path: pathlib.Path):
        """Restore a previously saved scope setup from a binary .scp file."""
        setup_bytes = ""
        file = open(setup_file_path, "rb")
        setup_bytes = file.read()
        file.close()
        self.do_command_ieee_block(":SYSTem:SETup", setup_bytes)
        print(f"Loaded {str(setup_file_path)}")

    def set_measurement_source(self, source_string):
        """Set the primary measurement source channel (e.g. 'CHANnel1')."""
        self.do_command(f":MEASure:SOURce {source_string}")

    def get_eye_height(self):
        """Return smallest eye height (V) from color-grade eye diagram."""
        return self.do_query_number(":MEASure:CGRade:EHEight?")

    def get_eye_width(self):
        """Return smallest eye width (s) from color-grade eye diagram."""
        return self.do_query_number(":MEASure:CGRade:EWIDth?")

    def get_dj_rj_tj(self):
        """Return TJ/RJ/DJ jitter summary string."""
        return self.do_query_string("MEASure:RJDJ:TJRJDJ?")

    def get_rise_time(self):
        return self.do_query_number(":MEASure:RISetime?")

    def get_fall_time(self):
        return self.do_query_number(":MEASure:FALLtime?")

    def save_screen_image_to_file(self, path_to_save_to: pathlib.Path):
        """Capture a PNG screenshot from the scope display and write it to disk."""
        screen_bytes = self.do_query_ieee_block(":DISPlay:DATA? PNG")
        f = open(path_to_save_to, "wb")
        f.write(screen_bytes)
        f.close()
        print(f"Screen image saved to {str(path_to_save_to)}")

    # ------------------------------------------------------------------
    # Low-level VISA helpers (adapted from Keysight programming guide)
    # ------------------------------------------------------------------

    def do_command(self, command, hide_params=False):
        """Send a SCPI write command and check for errors."""
        if hide_params:
            (header, data) = command.split(" ", 1)
            if self.debug:
                print("\nCmd = '%s'" % header)
        else:
            if self.debug:
                print("\nCmd = '%s'" % command)
        self.keysight_scope.write("%s" % command)
        if hide_params:
            self.check_instrument_errors(header, exit_on_error=False)
        else:
            self.check_instrument_errors(command, exit_on_error=False)

    def do_command_ieee_block(self, command, values):
        """Send a SCPI command with an IEEE 488.2 binary block payload."""
        if self.debug:
            print("Cmb = '%s'" % command)
        self.keysight_scope.write_binary_values("%s " % command, values, datatype='B')
        self.check_instrument_errors(command, exit_on_error=False)

    def do_query_string(self, query):
        """Send a SCPI query and return the response as a string."""
        if self.debug:
            print("Qys = '%s'" % query)
        result = self.keysight_scope.query("%s" % query)
        self.check_instrument_errors(query, exit_on_error=False)
        return result

    def do_query_number(self, query):
        """Send a SCPI query and return the response as a float."""
        if self.debug:
            print("Qyn = '%s'" % query)
        results = self.keysight_scope.query("%s" % query)
        self.check_instrument_errors(query, exit_on_error=False)
        if not results:
            return None
        return float(results)

    def do_query_ieee_block(self, query):
        """Send a SCPI query and return an IEEE 488.2 binary block as bytes."""
        if self.debug:
            print("Qyb = '%s'" % query)
        result = self.keysight_scope.query_binary_values("%s" % query, datatype='s', container=bytes)
        self.check_instrument_errors(query, exit_on_error=False)
        return result

    def check_instrument_errors(self, command, exit_on_error=True):
        """Poll :SYSTem:ERRor? STRing until the error queue is empty."""
        while True:
            error_string: str = self.keysight_scope.query(":SYSTem:ERRor? STRing")
            if error_string:
                if error_string.find("0,", 0, 2) == -1:  # not "No error"
                    print("ERROR: %s, command: '%s'" % (error_string, command))
                    if exit_on_error:
                        print("Exited because of error.")
                        sys.exit(1)
                else:
                    break
            else:
                print("ERROR: :SYSTem:ERRor? STRing returned nothing, command: '%s'" % command)
                print("Exited because of error.")
                sys.exit(1)
