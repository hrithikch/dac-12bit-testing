import serial
import serial.tools.list_ports
import time
import struct

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
serialInst.port = "COM6"
serialInst.open()

# -----------------------------------------------------------------------------
# Initialize current compliance to default values in rail table
# -----------------------------------------------------------------------------
print("Initializing current compliance")

serialInst.write("INITIALIZE_COMPLIANCE".encode('utf-8'))
value = serialInst.read(1)
print(value[0])

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
# Pulse digital I/O pin 87 (toggles green LED on hardware)
# -----------------------------------------------------------------------------
print("Pulse DIO 87 high, low, high, low, high. Flashes green LED")

serialInst.write("DIO_ON,87".encode('utf-8'))
print(serialInst.read(1)[0])
time.sleep(1)

serialInst.write("DIO_OFF,87".encode('utf-8'))
print(serialInst.read(1)[0])
time.sleep(1)

serialInst.write("DIO_ON,87".encode('utf-8'))
print(serialInst.read(1)[0])
time.sleep(1)

serialInst.write("DIO_OFF,87".encode('utf-8'))
print(serialInst.read(1)[0])
time.sleep(1)

serialInst.write("DIO_ON,87".encode('utf-8'))
print(serialInst.read(1)[0])
time.sleep(1)

print("Finished pulsing DIO 87\n")

# -----------------------------------------------------------------------------
# Read FIFO data stream until sentinel value 0xFFFF is received
# -----------------------------------------------------------------------------
print("Downloading FIFO Data")
serialInst.write("READ_FIFO".encode('utf-8'))

count = 0
while True:
    value = serialInst.read(2)                       # 16-bit samples
    unpacked_value = struct.unpack('<H', value)[0]
    if unpacked_value == 65535:                      # End-of-stream marker
        print("Exiting\n")
        break
    count += 1

print(f"Received {count} samples")
print("Finished downloading FIFO data\n")

# -----------------------------------------------------------------------------
# SPI write to ADC (chip select 23, 4 bytes, hex payload)
# -----------------------------------------------------------------------------
print("Writing to ADC SPI port")
serialInst.write("SPI_WRITE,23,4,32A67CF5".encode('utf-8'))
print(serialInst.read(1)[0])
print("Finished write to ADC SPI port\n")

time.sleep(3)

# -----------------------------------------------------------------------------
# SPI read from ADC (chip select 23, 4 bytes)
# -----------------------------------------------------------------------------
print("Reading from ADC SPI port")
serialInst.write("SPI_READ,23,4".encode('utf-8'))
value = serialInst.read(4)
print(struct.unpack('<I', value)[0])
print("Finished read ADC SPI port\n")

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
print("Setting voltages")
serialInst.write(
    "SET_VOLTAGE,AVDD,0.7,VREFC_GATE,1.2,VREF,0.6".encode('utf-8')
)

statuses = read_status_frame(serialInst)

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

print([NAMES.get(s, f"UNKNOWN({s})") for s in statuses])
print("Finished setting voltages\n")

# -----------------------------------------------------------------------------
# Read back rail voltages and power metrics
# -----------------------------------------------------------------------------
print("Reading AVDD voltage")
serialInst.write("READ_VOLTAGE,AVDD".encode('utf-8'))
print(f"{struct.unpack('<f', serialInst.read(4))[0]:.3f}")
print("Finished reading AVDD voltage\n")

print("Reading VREFC_GATE voltage")
serialInst.write("READ_VOLTAGE,VREFC_GATE".encode('utf-8'))
print(f"{struct.unpack('<f', serialInst.read(4))[0]:.3f}")
print("Finished reading VREFC_GATE voltage\n")

print("Reading VREF voltage")
serialInst.write("READ_VOLTAGE,VREF".encode('utf-8'))
print(f"{struct.unpack('<f', serialInst.read(4))[0]:.3f}")
print("Finished reading VREF voltage\n")

print("Reading VREFC_GATE shunt voltage")
serialInst.write("READ_SHUNTV,VREFC_GATE".encode('utf-8'))
value = serialInst.read(4)
unpacked_value = round(struct.unpack('<f', value)[0],3)
print(f"{unpacked_value:.3f}");
print("Finished reading VREFC_GATE shunt voltage\n")

print("Reading VREFC_GATE current in mA")
serialInst.write("READ_CURRENT,VREFC_GATE".encode('utf-8'))
value = serialInst.read(4)
unpacked_value = round(struct.unpack('<f', value)[0],3)
print(f"{unpacked_value:.3f}");
print("Finished reading VREFC_GATE current\n")

print("Reading VREFC_GATE power")
serialInst.write("READ_POWER,VREFC_GATE".encode('utf-8'))
value = serialInst.read(4)
unpacked_value = round(struct.unpack('<f', value)[0],3)
print(f"{unpacked_value:.3f}");
print("Finished reading VREFC_GATE power\n")

# -----------------------------------------------------------------------------
# Set LDO digital potentiometer
# -----------------------------------------------------------------------------
print("Setting LDO pot")
serialInst.write("LDO_WRITE,AVDD,128".encode('utf-8'))
print(serialInst.read(1)[0])
print("Done setting LDO pot")

# -----------------------------------------------------------------------------
# Read AVDD voltage to see that it changed after setting the LDO pot
# -----------------------------------------------------------------------------
print("Reading AVDD voltage")
serialInst.write("READ_VOLTAGE,AVDD".encode('utf-8'))
value = serialInst.read(4)
unpacked_value = round(struct.unpack('<f', value)[0],3)
print(f"{unpacked_value:.3f}");
print("Finished reading AVDD voltage\n")

# -----------------------------------------------------------------------------
# Set compliance current on VREFC_GATE rail
# -----------------------------------------------------------------------------
print("Setting VREFC_GATE compliance to 0.04 mA")
serialInst.write("SET_COMPLIANCE,VREFC_GATE,0.04".encode('utf-8'))
print(serialInst.read(1)[0])
print("Finished setting VREFC_GATE compliance\n")

# -----------------------------------------------------------------------------
# Set multiple rail voltages (blocking version)
# This command will:
#   1) Adjust AVDD to 0.8V
#   2) Adjust VREFC_GATE to 1.3V
#   3) Adjust VREF to 0.5V
# The Arduino responds with a framed status packet (SOF + LEN + payload + XOR)
# -----------------------------------------------------------------------------
print("Setting voltages")

serialInst.write(
    "SET_VOLTAGE,AVDD,0.8,VREFC_GATE,1.3,VREF,0.5".encode('utf-8')
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
# Read back VREFC_GATE voltage
# -----------------------------------------------------------------------------
print("Reading VREFC_GATE voltage")

serialInst.write("READ_VOLTAGE,VREFC_GATE".encode('utf-8'))

value = serialInst.read(4)
unpacked_value = round(struct.unpack('<f', value)[0], 3)

print(f"{unpacked_value:.3f}")
print("Finished reading VREFC_GATE voltage\n")


# -----------------------------------------------------------------------------
# Read back VREF voltage
# -----------------------------------------------------------------------------
print("Reading VREF voltage")

serialInst.write("READ_VOLTAGE,VREF".encode('utf-8'))

value = serialInst.read(4)
unpacked_value = round(struct.unpack('<f', value)[0], 3)

print(f"{unpacked_value:.3f}")
print("Finished reading VREF voltage\n")
# -----------------------------------------------------------------------------
# Close serial connection cleanly
# -----------------------------------------------------------------------------
serialInst.close()
