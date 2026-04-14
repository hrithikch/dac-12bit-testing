import serial
import serial.tools.list_ports
import time
import struct

NAMES = {
    0: "OK",
    1: "WARN",
    2: "OUT_OF_RANGE",
    3: "STUCK",
    4: "TIMEOUT",
    5: "DEVICE_FAIL",
    6: "UNSTABLE",
    7: "OVERCURRENT",
}

# -----------------------------------------------------------------------------
# Utility: read exactly N bytes from the serial port
# Raises an error if fewer bytes are received (prevents silent framing bugs)
# -----------------------------------------------------------------------------
def read_exact(ser, n: int) -> bytes:
    b = ser.read(n)
    if len(b) != n:
        raise RuntimeError(f"Incomplete read: wanted {n}, got {len(b)}")
    return b

# -----------------------------------------------------------------------------
# Read a framed status response from the device
#
# Frame format:
#   SOF      : 0xAA 0x55
#   LEN      : 1 byte (payload length)
#   PAYLOAD  : LEN bytes (status codes)
#   CHECKSUM : 1 byte XOR of payload bytes
# -----------------------------------------------------------------------------
def read_status_frame(ser):
    # Search for Start Of Frame (SOF = 0xAA 0x55)
    while True:
        if read_exact(ser, 1) == b"\xAA" and read_exact(ser, 1) == b"\x55":
            break

    # Read payload length (0–255 bytes)
    n = struct.unpack("<B", read_exact(ser, 1))[0]

    # Read payload
    payload = read_exact(ser, n)

    # Read checksum byte
    chk = struct.unpack("<B", read_exact(ser, 1))[0]

    # Verify XOR checksum
    x = 0
    for b in payload:
        x ^= b
    if x != chk:
        raise RuntimeError("Bad checksum (frame corrupted or misaligned)")

    # Return payload as list of integers
    return list(payload)

# -----------------------------------------------------------------------------
# Enumerate available serial ports (useful for debugging COM port issues)
# -----------------------------------------------------------------------------
ports = serial.tools.list_ports.comports()
print(ports)

# -----------------------------------------------------------------------------
# Configure and open serial port
# -----------------------------------------------------------------------------
serialInst = serial.Serial()
serialInst.baudrate = 115200
serialInst.port = "COM4"
serialInst.open()
time.sleep(2)

# -----------------------------------------------------------------------------
# Initialize current compliance to default values in rail table
# -----------------------------------------------------------------------------
print("Initializing current compliance")

#serialInst.write("INITIALIZE_COMPLIANCE".encode('utf-8'))
#value = serialInst.read(1)
#print(value[0])

print("Finished initializing current compliance\n")

# -----------------------------------------------------------------------------
# Basic LED test: toggle ON/OFF several times
# -----------------------------------------------------------------------------
print("Flashing LED")

serialInst.write("ON".encode('utf-8'))
value = serialInst.read(1)
print(value[0])
time.sleep(1)

serialInst.write("OFF".encode('utf-8'))
value = serialInst.read(1)
print(value[0])
time.sleep(1)

serialInst.write("ON".encode('utf-8'))
value = serialInst.read(1)
print(value[0])
time.sleep(1)

serialInst.write("OFF".encode('utf-8'))
value = serialInst.read(1)
print(value[0])
time.sleep(1)

print("Finished flashing LED\n")

# -----------------------------------------------------------------------------
# Pulse digital I/O pin 13 (toggles green LED on hardware)
# -----------------------------------------------------------------------------
print("Pulse DIO 13 high, low, high, low, high. Flashes green LED")

serialInst.write("DIO_ON,13".encode('utf-8'))
print(serialInst.read(1)[0])
time.sleep(1)

serialInst.write("DIO_OFF,13".encode('utf-8'))
print(serialInst.read(1)[0])
time.sleep(1)

serialInst.write("DIO_ON,13".encode('utf-8'))
print(serialInst.read(1)[0])
time.sleep(1)

serialInst.write("DIO_OFF,13".encode('utf-8'))
print(serialInst.read(1)[0])
time.sleep(1)

serialInst.write("DIO_ON,13".encode('utf-8'))
print(serialInst.read(1)[0])
time.sleep(1)

print("Finished pulsing DIO 13\n")

# -----------------------------------------------------------------------------
# Read Arduino internal ADC pin A0
# -----------------------------------------------------------------------------
print("Reading Arduino ADC value")
serialInst.write("READ_ADC,A0".encode('utf-8'))
value = serialInst.read(2)
print(struct.unpack('<H', value)[0])
print("Finished reading Arduino ADC value\n")

time.sleep(3)

# -----------------------------------------------------------------------------
# Read AVDD rail measurements via INA219
# -----------------------------------------------------------------------------
print("Reading AVDD voltage")
serialInst.write("READ_VOLTAGE,AVDD".encode('utf-8'))
print(f"{struct.unpack('<f', serialInst.read(4))[0]:.3f}")
print("Finished reading AVDD voltage\n")

print("Reading AVDD shunt voltage")
serialInst.write("READ_SHUNTV,AVDD".encode('utf-8'))
print(f"{struct.unpack('<f', serialInst.read(4))[0]:.3f}")
print("Finished reading AVDD shunt voltage\n")

print("Reading AVDD current")
serialInst.write("READ_CURRENT,AVDD".encode('utf-8'))
print(f"{struct.unpack('<f', serialInst.read(4))[0]:.3f}")
print("Finished reading AVDD current\n")

print("Reading AVDD power")
serialInst.write("READ_POWER,AVDD".encode('utf-8'))
print(f"{struct.unpack('<f', serialInst.read(4))[0]:.3f}")
print("Finished reading AVDD power\n")

time.sleep(3)

# -----------------------------------------------------------------------------
# Set multiple rail voltages (returns framed status response)
# -----------------------------------------------------------------------------
print("Setting AVDD=0.85V, AVDD0P85=0.85V and AVDD18 = 1.8V")
serialInst.write(
    "SET_VOLTAGE,AVDD,0.85,AVDD0P85,0.85,AVDD18,1.8".encode('utf-8')
)

statuses = read_status_frame(serialInst)

print([NAMES.get(s, f"UNKNOWN({s})") for s in statuses])
print("Finished setting voltages\n")

# -----------------------------------------------------------------------------
# Read back rail voltages and power metrics
# -----------------------------------------------------------------------------
print("Reading AVDD voltage")
serialInst.write("READ_VOLTAGE,AVDD".encode('utf-8'))
print(f"{struct.unpack('<f', serialInst.read(4))[0]:.3f}")
print("Finished reading AVDD voltage\n")

print("Reading AVDD0P85 voltage")
serialInst.write("READ_VOLTAGE,AVDD0P85".encode('utf-8'))
print(f"{struct.unpack('<f', serialInst.read(4))[0]:.3f}")
print("Finished reading AVDD0P85 voltage\n")

print("Reading AVDD18 voltage")
serialInst.write("READ_VOLTAGE,AVDD18".encode('utf-8'))
print(f"{struct.unpack('<f', serialInst.read(4))[0]:.3f}")
print("Finished reading AVDD18 voltage\n")

print("Reading AVDD18 shunt voltage")
serialInst.write("READ_SHUNTV,AVDD18".encode('utf-8'))
value = serialInst.read(4)
unpacked_value = round(struct.unpack('<f', value)[0],3)
print(f"{unpacked_value:.3f}");
print("Finished reading AVDD18 shunt voltage\n")

print("Reading AVDD18 current in mA")
serialInst.write("READ_CURRENT,AVDD18".encode('utf-8'))
value = serialInst.read(4)
unpacked_value = round(struct.unpack('<f', value)[0],3)
print(f"{unpacked_value:.3f}");
print("Finished reading AVDD18 current\n")

print("Reading AVDD18 power")
serialInst.write("READ_POWER,AVDD18".encode('utf-8'))
value = serialInst.read(4)
unpacked_value = round(struct.unpack('<f', value)[0],3)
print(f"{unpacked_value:.3f}");
print("Finished reading AVDD18 power\n")

# -----------------------------------------------------------------------------
# Set LDO digital potentiometer
# -----------------------------------------------------------------------------
print("Setting LDO pot for AVDD18")
serialInst.write("LDO_WRITE,AVDD18,255".encode('utf-8'))
print(serialInst.read(1)[0])
print("Done setting LDO pot for AVDD18")

# -----------------------------------------------------------------------------
# Read AVDD18 voltage to see that it changed after setting the LDO pot
# -----------------------------------------------------------------------------
print("Reading AVDD18 voltage")
serialInst.write("READ_VOLTAGE,AVDD18".encode('utf-8'))
value = serialInst.read(4)
unpacked_value = round(struct.unpack('<f', value)[0],3)
print(f"{unpacked_value:.3f}");
print("Finished reading AVDD18 voltage\n")

# -----------------------------------------------------------------------------
# Set compliance current on VREFC_GATE rail
# -----------------------------------------------------------------------------
print("Setting VDD18 compliance to 0.04 mA")
serialInst.write("SET_COMPLIANCE,VREFC_GATE,0.04".encode('utf-8'))
print(serialInst.read(1)[0])
print("Finished setting AVDD compliance\n")

# -----------------------------------------------------------------------------
# Set multiple rail voltages (blocking version)
# This command will:
#   1) Adjust AVDD to 0.8V
#   2) Adjust AVDD0P85 to 0.6V
#   3) Adjust AVDD18 to 1.2V
# The Arduino responds with a framed status packet (SOF + LEN + payload + XOR)
# -----------------------------------------------------------------------------
print("Setting AVDD=0.85, AVDD0P85=0.85 and AVDD18=1.8, and DVDD=0.8, and VCM = 0.6")

serialInst.write(
    "SET_VOLTAGE,AVDD,0.85,AVDD0P85,0.85,AVDD18,1.8,DVDD,0.8,VCM,0.6".encode('utf-8')
)

# Read framed status response from device
statuses = read_status_frame(serialInst)

# Convert numeric RailStatus codes into human-readable strings
print([NAMES.get(s, f"UNKNOWN({s})") for s in statuses])

print("Finished reading Error value\n")
print("Finished setting voltages")


# -----------------------------------------------------------------------------
# Read back AVDD voltage to verify convergence
# Device returns float32 (4 bytes, little-endian IEEE-754)
# -----------------------------------------------------------------------------
print("Reading AVDD voltage")

serialInst.write("READ_VOLTAGE,AVDD".encode('utf-8'))

value = serialInst.read(4)
unpacked_value = round(struct.unpack('<f', value)[0], 3)

print(f"{unpacked_value:.3f}")
print("Finished reading AVDD voltage\n")


# -----------------------------------------------------------------------------
# Read back AVDD0P85 voltage
# -----------------------------------------------------------------------------
print("Reading AVDD0P85 voltage")

serialInst.write("READ_VOLTAGE,AVDD0P85".encode('utf-8'))

value = serialInst.read(4)
unpacked_value = round(struct.unpack('<f', value)[0], 3)

print(f"{unpacked_value:.3f}")
print("Finished reading AVDD0P85 voltage\n")


# -----------------------------------------------------------------------------
# Read back AVDD18 voltage
# -----------------------------------------------------------------------------
print("Reading AVDD18 voltage")

serialInst.write("READ_VOLTAGE,AVDD18".encode('utf-8'))

value = serialInst.read(4)
unpacked_value = round(struct.unpack('<f', value)[0], 3)

print(f"{unpacked_value:.3f}")
print("Finished reading AVDD18 voltage\n")


# -----------------------------------------------------------------------------
# Read back DVDD voltage
# -----------------------------------------------------------------------------
print("Reading DVDD voltage")

serialInst.write("READ_VOLTAGE,DVDD".encode('utf-8'))

value = serialInst.read(4)
unpacked_value = round(struct.unpack('<f', value)[0], 3)

print(f"{unpacked_value:.3f}")
print("Finished reading DVDD voltage\n")


# -----------------------------------------------------------------------------
# Read back VCM voltage
# -----------------------------------------------------------------------------
print("Reading VCM voltage")

serialInst.write("READ_VOLTAGE,VCM".encode('utf-8'))

value = serialInst.read(4)
unpacked_value = round(struct.unpack('<f', value)[0], 3)

print(f"{unpacked_value:.3f}")
print("Finished reading VCM voltage\n")


# -----------------------------------------------------------------------------
# Close serial connection cleanly
# -----------------------------------------------------------------------------
serialInst.close()
