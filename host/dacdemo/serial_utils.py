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


def read_exact(ser, n: int) -> bytes:
    data = ser.read(n)
    if len(data) != n:
        raise RuntimeError(f"Incomplete read: wanted {n}, got {len(data)}")
    return data


def read_status_frame(ser):
    while True:
        if read_exact(ser, 1) == b"\xAA" and read_exact(ser, 1) == b"\x55":
            break
    n = struct.unpack("<B", read_exact(ser, 1))[0]
    payload = read_exact(ser, n)
    chk = struct.unpack("<B", read_exact(ser, 1))[0]
    x = 0
    for b in payload:
        x ^= b
    if x != chk:
        raise RuntimeError("Bad checksum (frame corrupted or misaligned)")
    return list(payload)
