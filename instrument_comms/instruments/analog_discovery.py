from ctypes import *
from .dwfconstants import *


class AnalogDiscovery:
    """
    Driver for Digilent Analog Discovery 2 (and compatible devices).

    Communicates via the DWF (Digilent Waveforms) shared library loaded through ctypes.
    The dwf library is NOT a VISA resource — it is a native C library provided by Digilent.

    Instantiate by passing the loaded dwf cdll object (see examples/05_analog_discovery.py).
    """

    def __init__(self, dwf_handler_object) -> None:
        self.dwf = dwf_handler_object
        self.hdwf = c_int()

    def __set_on_close_to_run(self):
        self.dwf.FDwfParamSet(DwfParamOnClose, c_int(0))

    def __open_device(self):
        self.dwf.FDwfDeviceOpen(c_int(-1), byref(self.hdwf))
        return self.hdwf.value != hdwfNone.value

    def __turn_off_auto_config(self):
        # Disabling auto-configure means settings are applied only when
        # FDwfAnalogOutConfigure / FDwfDigitalOutConfigure etc. are explicitly called.
        self.dwf.FDwfDeviceAutoConfigureSet(self.hdwf, c_int(0))

    def open_and_init_device(self):
        """Open the first available AD device and initialize it. Returns True on success."""
        self.__set_on_close_to_run()
        if not self.__open_device():
            print("Unable to open AD device")
            return False
        self.__turn_off_auto_config()
        return True

    def print_version(self):
        version = create_string_buffer(16)
        self.dwf.FDwfGetVersion(version)
        print("DWF Version: " + str(version.value))

    def analog_out_single_pulse(self, channel: c_int, pulse_length: float, amplitude_in_volts: float, phase_in_degrees: float):
        """
        Generate a single square pulse on the specified analog output channel.

        channel          : c_int(0) for W1, c_int(1) for W2
        pulse_length     : duration of the pulse in seconds
        amplitude_in_volts: half the peak-to-peak swing (e.g. 1.65 for 0–3.3 V with offset=0)
        phase_in_degrees : phase offset of the square wave (0 = starts high)
        """
        self.dwf.FDwfAnalogOutNodeEnableSet(self.hdwf, channel, AnalogOutNodeCarrier, c_int(1))
        self.dwf.FDwfAnalogOutIdleSet(self.hdwf, channel, DwfAnalogOutIdleOffset)
        self.dwf.FDwfAnalogOutNodeFunctionSet(self.hdwf, channel, AnalogOutNodeCarrier, funcSquare)
        self.dwf.FDwfAnalogOutNodeFrequencySet(self.hdwf, channel, AnalogOutNodeCarrier, c_double(0))  # low frequency = single cycle
        self.dwf.FDwfAnalogOutNodeAmplitudeSet(self.hdwf, channel, AnalogOutNodeCarrier, c_double(amplitude_in_volts))
        self.dwf.FDwfAnalogOutNodeOffsetSet(self.hdwf, channel, AnalogOutNodeCarrier, c_double(0))
        self.dwf.FDwfAnalogOutNodePhaseSet(self.hdwf, channel, AnalogOutNodeCarrier, c_double(phase_in_degrees))
        self.dwf.FDwfAnalogOutRunSet(self.hdwf, channel, c_double(pulse_length))   # pulse duration
        self.dwf.FDwfAnalogOutWaitSet(self.hdwf, channel, c_double(0))             # no pre-run wait
        self.dwf.FDwfAnalogOutRepeatSet(self.hdwf, channel, c_int(1))              # fire once

        print("Generating pulse")
        self.dwf.FDwfAnalogOutConfigure(self.hdwf, channel, c_int(1))

    def analog_out_dc(self, channel: c_int, offset: float):
        """
        Output a constant DC voltage on an analog output channel.

        channel : c_int(0) for W1, c_int(1) for W2
        offset  : voltage level in volts
        """
        self.dwf.FDwfAnalogOutNodeEnableSet(self.hdwf, channel, AnalogOutNodeCarrier, c_int(1))
        self.dwf.FDwfAnalogOutIdleSet(self.hdwf, channel, DwfAnalogOutIdleOffset)
        self.dwf.FDwfAnalogOutNodeFunctionSet(self.hdwf, channel, AnalogOutNodeCarrier, funcDC)
        self.dwf.FDwfAnalogOutNodeOffsetSet(self.hdwf, channel, AnalogOutNodeCarrier, c_double(offset))
        print("Generating DC output...")
        self.dwf.FDwfAnalogOutConfigure(self.hdwf, channel, c_int(1))

    def close_device(self):
        """Close the device handle. Call before program exit."""
        self.dwf.FDwfDeviceClose(self.hdwf)

    def set_positive_power_supply(self, voltage):
        """
        Enable the AD2's onboard V+ power supply rail and set its voltage.

        voltage: target voltage in volts (AD2 range: 0–5 V)
        """
        self.dwf.FDwfAnalogIOChannelNodeSet(self.hdwf, c_int(0), c_int(0), c_double(1))       # enable
        self.dwf.FDwfAnalogIOChannelNodeSet(self.hdwf, c_int(0), c_int(1), c_double(voltage))  # set voltage
        self.dwf.FDwfAnalogIOEnableSet(self.hdwf, c_int(1))
        self.dwf.FDwfAnalogIOConfigure(self.hdwf)

    def set_digital_io_constant_high(self, channel):
        """
        Drive a digital output pin constantly high (useful as a logic-level reset wire).

        channel: zero-based DIO channel index (e.g. 0 for DIO 0)
        """
        self.dwf.FDwfDigitalOutEnableSet(self.hdwf, channel, 1)
        self.dwf.FDwfDigitalOutCounterInitSet(self.hdwf, channel, 1, 0)  # init high
        self.dwf.FDwfDigitalOutCounterSet(self.hdwf, channel, 0, 0)      # no toggle — stays constant
        self.dwf.FDwfDigitalOutConfigure(self.hdwf, c_int(1))
