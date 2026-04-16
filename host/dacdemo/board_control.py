import struct
import time
from dataclasses import dataclass

import serial
import serial.tools.list_ports

from dacdemo.serial_utils import NAMES, read_exact, read_status_frame


@dataclass
class BoardSession:
    ser: serial.Serial

    @classmethod
    def open(cls, port: str, baudrate: int = 115200, startup_delay_s: float = 2.0, read_timeout_s: float = 5.0):
        ser = serial.Serial()
        ser.baudrate = baudrate
        ser.port = port
        ser.timeout = read_timeout_s
        ser.open()
        time.sleep(startup_delay_s)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        return cls(ser=ser)

    def close(self):
        self.ser.close()

    def write_text(self, command: str):
        # Drop any stale bytes from an earlier timed-out transaction before issuing a new command.
        self.ser.reset_input_buffer()
        self.ser.write(command.encode("utf-8"))
        self.ser.flush()

    def read_bool(self) -> bool:
        data = self.ser.read(1)
        if not data:
            raise TimeoutError("No response from board — is the firmware flashed and running?")
        return bool(data[0])

    def read_u16(self) -> int:
        return struct.unpack("<H", read_exact(self.ser, 2))[0]

    def read_f32(self) -> float:
        return struct.unpack("<f", read_exact(self.ser, 4))[0]

    def led_on(self) -> bool:
        self.write_text("ON")
        return self.read_bool()

    def led_off(self) -> bool:
        self.write_text("OFF")
        return self.read_bool()

    def dio_on(self, pin: int) -> bool:
        self.write_text(f"DIO_ON,{pin}")
        return self.read_bool()

    def dio_off(self, pin: int) -> bool:
        self.write_text(f"DIO_OFF,{pin}")
        return self.read_bool()

    def read_adc(self, channel: str) -> int:
        self.write_text(f"READ_ADC,{channel}")
        return self.read_u16()

    def read_voltage(self, rail: str) -> float:
        self.write_text(f"READ_VOLTAGE,{rail}")
        return self.read_f32()

    def read_shuntv(self, rail: str) -> float:
        self.write_text(f"READ_SHUNTV,{rail}")
        return self.read_f32()

    def read_current(self, rail: str) -> float:
        self.write_text(f"READ_CURRENT,{rail}")
        return self.read_f32()

    def read_power(self, rail: str) -> float:
        self.write_text(f"READ_POWER,{rail}")
        return self.read_f32()

    def set_compliance(self, rail: str, value_mA: float) -> bool:
        self.write_text(f"SET_COMPLIANCE,{rail},{value_mA}")
        return self.read_bool()

    def ldo_write(self, rail: str, raw_value: int) -> bool:
        self.write_text(f"LDO_WRITE,{rail},{raw_value}")
        return self.read_bool()

    def initialize_compliance(self) -> bool:
        self.write_text("INITIALIZE_COMPLIANCE")
        return self.read_bool()

    def set_voltages(self, rail_to_value: dict[str, float]) -> list[str]:
        parts = ["SET_VOLTAGE"]
        for rail, value in rail_to_value.items():
            parts.extend([rail, str(value)])
        previous_timeout = self.ser.timeout
        # Rail convergence can legitimately take well over the default read timeout.
        self.ser.timeout = max(previous_timeout or 0, 20.0)
        try:
            self.write_text(",".join(parts))
            statuses = read_status_frame(self.ser)
        finally:
            self.ser.timeout = previous_timeout
        return [NAMES.get(s, f"UNKNOWN({s})") for s in statuses]

    def dac_disable_pattern(self) -> bool:
        self.write_text("DAC_DISABLE_PATTERN")
        return self.read_bool()

    def dac_enable_pattern(self) -> bool:
        self.write_text("DAC_ENABLE_PATTERN")
        return self.read_bool()

    def dac_load_sine(self, f_out: float, f_sample: float) -> bool:
        self.write_text(f"DAC_LOAD_SINE,{f_out},{f_sample}")
        return self.read_bool()

    def dac_play_sine(self, f_out: float, f_sample: float) -> bool:
        self.write_text(f"DAC_PLAY_SINE,{f_out},{f_sample}")
        return self.read_bool()


def list_ports() -> list[str]:
    return [p.device for p in serial.tools.list_ports.comports()]
