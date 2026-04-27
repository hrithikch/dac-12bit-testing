"""
Instrument discovery — VISA, LAN subnet, and Analog Discovery.

Three discovery modes run in sequence:
  1. VISA layer   — queries pyvisa.ResourceManager().list_resources() and IDN-identifies each
  2. LAN scan     — probes a subnet for hosts listening on VXI-11 (port 111) or HiSLIP (port 4880),
                    then attempts *IDN? on anything that responds
  3. Analog Discovery — checks for Digilent AD2/AD3 devices via the DWF ctypes library
"""

import socket
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from typing import Optional

# ── Known instrument fingerprints ────────────────────────────────────────────
# Maps a substring found in *IDN? response to a human-readable label.
# Primary entries match instruments used in this project; extras kept for lab context.
IDN_FINGERPRINTS = {
    # ── Project instruments ────────────────────────────────────────────────────
    # Keysight N9010B EXA signal analyzer  →  KeysightEXA driver
    "KEYSIGHT TECHNOLOGIES,N9010B":  "Keysight N9010B EXA signal analyzer",
    # Keysight MSOS054A oscilloscope  →  KeysightOscilloscope driver
    "KEYSIGHT TECHNOLOGIES,MSOS":    "Keysight MSO oscilloscope",
    "KEYSIGHT TECHNOLOGIES,MXR":     "Keysight MXR oscilloscope",
    "KEYSIGHT TECHNOLOGIES,UXR":     "Keysight UXR oscilloscope",
    # Keysight E36300-series power supply  →  KeysightPowerSupply driver
    "KEYSIGHT TECHNOLOGIES,E363":    "Keysight E363xx power supply",
    "KEYSIGHT TECHNOLOGIES,E364":    "Keysight E364xx power supply",
    # Keithley 2230-30-1 power supply  →  KeithleyPowerSupply driver
    "KEITHLEY INSTRUMENTS,MODEL 2230": "Keithley 2230 power supply",
    # R&S SMA100B signal generator  →  RohdeAndSchwarzSignalGenerator driver
    "ROHDE&SCHWARZ,SMA100":          "R&S SMA100B signal generator",

    # ── Other common lab instruments ───────────────────────────────────────────
    "KEYSIGHT TECHNOLOGIES,DSO":     "Keysight DSO oscilloscope",
    "KEYSIGHT TECHNOLOGIES,33":      "Keysight 33xxx function/arb generator",
    "KEYSIGHT TECHNOLOGIES,N57":     "Keysight N57xx signal generator",
    "ROHDE&SCHWARZ,SMB100":          "R&S SMB100 signal generator",
    "ROHDE&SCHWARZ,SMW200":          "R&S SMW200A vector signal generator",
    "ROHDE&SCHWARZ,RTO":             "R&S RTO oscilloscope",
    "ROHDE&SCHWARZ,RTM":             "R&S RTM oscilloscope",
    "ROHDE&SCHWARZ,FSW":             "R&S FSW signal/spectrum analyzer",
    "TEKTRONIX,MSO":                 "Tektronix MSO oscilloscope",
    "TEKTRONIX,DPO":                 "Tektronix DPO oscilloscope",
    "TEKTRONIX,AFG":                 "Tektronix AFG function generator",
    "KEITHLEY INSTRUMENTS,MODEL 2260": "Keithley 2260 power supply",
    "KEITHLEY INSTRUMENTS,MODEL 2400": "Keithley 2400 SMU",
    "KEITHLEY INSTRUMENTS,MODEL 2450": "Keithley 2450 SMU",
    "NATIONAL INSTRUMENTS,PXI":      "NI PXI instrument",
}

# VISA ports used for LAN instrument probing
VISA_LAN_PORTS = {
    111:  "VXI-11 (portmapper)",
    4880: "HiSLIP",
    5025: "SCPI-RAW / SCPI-TCP",
}


# ── Data class ────────────────────────────────────────────────────────────────

@dataclass
class DiscoveredInstrument:
    source:  str               # "VISA", "LAN", or "AD2"
    address: str               # VISA resource string or IP
    idn:     Optional[str] = None
    label:   Optional[str] = None
    error:   Optional[str] = None
    port:    Optional[int] = None


# ── VISA discovery ────────────────────────────────────────────────────────────

def _idn_from_visa_resource(rm, resource_string: str, timeout_ms: int = 5000) -> tuple[Optional[str], Optional[str]]:
    try:
        res = rm.open_resource(resource_string)
        res.timeout = timeout_ms
        idn = res.query("*IDN?").strip()
        res.close()
        return idn, None
    except Exception as exc:
        return None, str(exc)


def discover_via_visa(timeout_ms: int = 5000) -> list[DiscoveredInstrument]:
    results: list[DiscoveredInstrument] = []
    try:
        import pyvisa
    except ImportError:
        print("[VISA] pyvisa not installed — skipping VISA discovery.")
        return results

    try:
        rm = pyvisa.ResourceManager()
    except Exception as exc:
        print(f"[VISA] Could not open ResourceManager: {exc}")
        return results

    resources = rm.list_resources()
    if not resources:
        print("[VISA] No VISA resources found.")
        rm.close()
        return results

    print(f"[VISA] Found {len(resources)} resource(s). Querying IDN...")
    for addr in resources:
        idn, err = _idn_from_visa_resource(rm, addr, timeout_ms)
        label = _identify(idn) if idn else None
        results.append(DiscoveredInstrument(
            source="VISA", address=addr, idn=idn, label=label, error=err,
        ))

    rm.close()
    return results


# ── LAN subnet scan ───────────────────────────────────────────────────────────

def _probe_host_port(ip: str, port: int, connect_timeout: float) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=connect_timeout):
            return True
    except OSError:
        return False


def _idn_via_scpi_raw(ip: str, port: int = 5025, timeout: float = 3.0) -> Optional[str]:
    try:
        with socket.create_connection((ip, port), timeout=timeout) as sock:
            sock.sendall(b"*IDN?\n")
            sock.settimeout(timeout)
            data = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data:
                    break
        return data.decode(errors="replace").strip()
    except OSError:
        return None


def _idn_via_visa_tcpip(ip: str, port: int, timeout_ms: int = 5000) -> Optional[str]:
    try:
        import pyvisa
        rm = pyvisa.ResourceManager()
    except Exception:
        return None

    candidates: list[str] = []
    if port == 4880:
        candidates = [f"TCPIP0::{ip}::hislip0::INSTR"]
    elif port == 111:
        candidates = [f"TCPIP0::{ip}::inst0::INSTR", f"TCPIP0::{ip}::0::INSTR"]
    else:
        candidates = [f"TCPIP0::{ip}::{port}::SOCKET"]

    for addr in candidates:
        try:
            res = rm.open_resource(addr)
            res.timeout = timeout_ms
            idn = res.query("*IDN?").strip()
            res.close()
            rm.close()
            return idn
        except Exception:
            continue

    rm.close()
    return None


def _scan_host(ip: str, connect_timeout: float, visa_timeout_ms: int) -> Optional[DiscoveredInstrument]:
    best_effort_result: Optional[DiscoveredInstrument] = None
    for port, protocol in VISA_LAN_PORTS.items():
        if _probe_host_port(ip, port, connect_timeout):
            idn = None
            if port == 5025:
                idn = _idn_via_scpi_raw(ip, port=5025, timeout=connect_timeout + 1.0)
            if idn is None:
                idn = _idn_via_visa_tcpip(ip, port, timeout_ms=visa_timeout_ms)

            label = _identify(idn) if idn else None
            result = DiscoveredInstrument(
                source="LAN", address=ip, idn=idn, label=label, port=port,
                error=None if idn else f"Port {port} open ({protocol}) but *IDN? failed",
            )
            if idn:
                return result
            if best_effort_result is None:
                best_effort_result = result
    return best_effort_result


def scan_subnet(subnet: str, connect_timeout: float = 0.5, max_workers: int = 64,
                visa_timeout_ms: int = 5000) -> list[DiscoveredInstrument]:
    ips = [f"{subnet}.{i}" for i in range(1, 255)]
    results: list[DiscoveredInstrument] = []

    print(f"[LAN] Scanning {subnet}.1–254 for VISA ports {list(VISA_LAN_PORTS.keys())} "
          f"({connect_timeout*1000:.0f} ms timeout, {max_workers} threads)...")

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_scan_host, ip, connect_timeout, visa_timeout_ms): ip for ip in ips}
        for fut in as_completed(futures):
            result = fut.result()
            if result is not None:
                results.append(result)

    results.sort(key=lambda r: [int(x) for x in r.address.split(".")])
    return results


# ── Analog Discovery detection ────────────────────────────────────────────────

def discover_analog_discovery() -> list[DiscoveredInstrument]:
    results: list[DiscoveredInstrument] = []

    try:
        import ctypes
        if sys.platform == "win32":
            dwf = ctypes.cdll.dwf
        elif sys.platform == "darwin":
            dwf = ctypes.cdll.LoadLibrary("/Library/Frameworks/dwf.framework/dwf")
        else:
            dwf = ctypes.cdll.LoadLibrary("libdwf.so")
    except OSError:
        print("[AD2] DWF library not found — Digilent WaveForms may not be installed.")
        return results

    c_int = ctypes.c_int
    count = c_int(0)
    dwf.FDwfEnum(c_int(0), ctypes.byref(count))
    n = count.value

    if n == 0:
        print("[AD2] No Digilent devices found.")
        return results

    print(f"[AD2] Found {n} Digilent device(s).")
    for i in range(n):
        name_buf = ctypes.create_string_buffer(64)
        sn_buf   = ctypes.create_string_buffer(64)
        dwf.FDwfEnumDeviceName(c_int(i), name_buf)
        dwf.FDwfEnumSN(c_int(i), sn_buf)
        name = name_buf.value.decode(errors="replace").strip()
        sn   = sn_buf.value.decode(errors="replace").strip()
        results.append(DiscoveredInstrument(
            source="AD2",
            address=f"DWF device index {i}",
            idn=f"{name} S/N:{sn}",
            label=f"Digilent {name}",
        ))

    return results


# ── Helpers ───────────────────────────────────────────────────────────────────

def _identify(idn: Optional[str]) -> Optional[str]:
    if not idn:
        return None
    idn_upper = idn.upper()
    for fragment, label in IDN_FINGERPRINTS.items():
        if fragment.upper() in idn_upper:
            return label
    return None


def visa_string_hint(instrument: DiscoveredInstrument) -> Optional[str]:
    """Suggest a VISA resource string for a LAN-discovered instrument."""
    if instrument.source != "LAN":
        return None
    ip   = instrument.address
    port = instrument.port
    if port == 4880:
        return f"TCPIP0::{ip}::hislip0::INSTR"
    if port == 111:
        return f"TCPIP0::{ip}::inst0::INSTR"
    if port == 5025:
        return f"TCPIP0::{ip}::5025::SOCKET"
    return None


# ── Output ────────────────────────────────────────────────────────────────────

def print_results(all_instruments: list[DiscoveredInstrument]) -> None:
    if not all_instruments:
        print("\nNo instruments discovered.")
        return

    print(f"\n{'='*70}")
    print(f"  DISCOVERED INSTRUMENTS ({len(all_instruments)} total)")
    print(f"{'='*70}")

    for inst in all_instruments:
        print(f"\n[{inst.source}] {inst.address}")
        if inst.port:
            print(f"  Port      : {inst.port} ({VISA_LAN_PORTS.get(inst.port, '?')})")
        if inst.label:
            print(f"  Type      : {inst.label}")
        if inst.idn:
            print(f"  IDN       : {inst.idn}")
        hint = visa_string_hint(inst)
        if hint:
            print(f"  VISA str  : {hint}")
        if inst.error and not inst.idn:
            print(f"  Note      : {inst.error}")

    # Config hint — map found instruments to dacdemo.toml [instruments] keys
    print(f"\n{'='*70}")
    print("  CONFIG HINT  (paste into config/dacdemo.toml [instruments])")
    print(f"{'='*70}")

    label_to_key = {
        "N9010B": "sa_addr",
        "MSO":    "scope_addr",
        "MXR":    "scope_addr",
        "UXR":    "scope_addr",
        "SMA100": "siggen_addr",
        "E363":   "psu_addr",
        "E364":   "psu_addr",
    }
    assigned: dict[str, str] = {}
    for inst in all_instruments:
        if inst.source == "AD2":
            continue
        addr  = inst.address if inst.source == "VISA" else (visa_string_hint(inst) or inst.address)
        label = (inst.label or "").upper()
        for keyword, key in label_to_key.items():
            if keyword in label and key not in assigned:
                assigned[key] = addr
                break

    if assigned:
        print()
        for key in ("siggen_addr", "scope_addr", "sa_addr", "psu_addr"):
            if key in assigned:
                print(f"  {key} = \"{assigned[key]}\"")
        for key, addr in assigned.items():
            if key not in ("siggen_addr", "scope_addr", "sa_addr", "psu_addr"):
                print(f"  {key} = \"{addr}\"")
    else:
        print("\n  (No recognized project instruments found)")

    print(f"\n{'='*70}\n")
