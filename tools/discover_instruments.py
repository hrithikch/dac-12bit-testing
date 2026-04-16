"""
Instrument Discovery Tool
=========================
Finds VISA instruments (LAN + USB) and Analog Discovery devices on the local machine.

Three discovery modes run in sequence:
  1. VISA layer   — queries pyvisa.ResourceManager().list_resources() and IDN-identifies each
  2. LAN scan     — probes a subnet for hosts listening on VXI-11 (port 111) or HiSLIP (port 4880),
                    then attempts *IDN? on anything that responds
  3. Analog Discovery — checks for Digilent AD2/AD3 devices via the DWF ctypes library

Usage
-----
  python discover_instruments.py                       # VISA + AD2 only, no LAN scan
  python discover_instruments.py --subnet 192.168.1    # also scan 192.168.1.1–254
  python discover_instruments.py --subnet 10.0.0 --timeout 0.3  # faster scan, 300 ms per host

Output is printed to stdout.  Use --json to write machine-readable results to a file.

Requirements
------------
  pyvisa   (pip install pyvisa)
  NI-VISA or Keysight IO Libraries Suite installed for VISA to work.
  Digilent Waveforms installed for AD2 detection to work.

  The LAN scan uses only stdlib (socket, concurrent.futures) — no extra packages needed.
"""

import argparse
import json
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from typing import Optional

# ── Known instrument fingerprints ────────────────────────────────────────────
# Maps a substring found in *IDN? response to a human-readable label.
# Primary entries match instruments used in this project; extras kept for lab context.
IDN_FINGERPRINTS = {
    # ── Project instruments ────────────────────────────────────────────────────
    # Keysight N9010B EXA signal analyzer  →  KeysightEXA driver
    "KEYSIGHT TECHNOLOGIES,N9010B": "Keysight N9010B EXA signal analyzer",
    # Keysight MSOS054A oscilloscope  →  KeysightOscilloscope driver
    "KEYSIGHT TECHNOLOGIES,MSOS": "Keysight MSO oscilloscope",
    "KEYSIGHT TECHNOLOGIES,MXR":  "Keysight MXR oscilloscope",
    # Keysight E36300-series power supply  →  KeysightPowerSupply driver
    "KEYSIGHT TECHNOLOGIES,E363": "Keysight E363xx power supply",
    "KEYSIGHT TECHNOLOGIES,E364": "Keysight E364xx power supply",
    # Keithley 2230-30-1 power supply  →  KeithleyPowerSupply driver
    "KEITHLEY INSTRUMENTS,MODEL 2230": "Keithley 2230 power supply",
    # R&S SMA100B signal generator  →  RohdeAndSchwarzSignalGenerator driver
    "ROHDE&SCHWARZ,SMA100": "R&S SMA100B signal generator",

    # ── Other common lab instruments ───────────────────────────────────────────
    "KEYSIGHT TECHNOLOGIES,DSO": "Keysight DSO oscilloscope",
    "KEYSIGHT TECHNOLOGIES,33": "Keysight 33xxx function/arb generator",
    "KEYSIGHT TECHNOLOGIES,N57": "Keysight N57xx signal generator",
    "ROHDE&SCHWARZ,SMB100": "R&S SMB100 signal generator",
    "ROHDE&SCHWARZ,SMW200": "R&S SMW200A vector signal generator",
    "ROHDE&SCHWARZ,RTO": "R&S RTO oscilloscope",
    "ROHDE&SCHWARZ,RTM": "R&S RTM oscilloscope",
    "ROHDE&SCHWARZ,FSW": "R&S FSW signal/spectrum analyzer",
    "TEKTRONIX,MSO": "Tektronix MSO oscilloscope",
    "TEKTRONIX,DPO": "Tektronix DPO oscilloscope",
    "TEKTRONIX,AFG": "Tektronix AFG function generator",
    "KEITHLEY INSTRUMENTS,MODEL 2260": "Keithley 2260 power supply",
    "KEITHLEY INSTRUMENTS,MODEL 2400": "Keithley 2400 SMU",
    "KEITHLEY INSTRUMENTS,MODEL 2450": "Keithley 2450 SMU",
    "NATIONAL INSTRUMENTS,PXI": "NI PXI instrument",
}

# VISA ports used for LAN instrument probing
VISA_LAN_PORTS = {
    111: "VXI-11 (portmapper)",
    4880: "HiSLIP",
    5025: "SCPI-RAW / SCPI-TCP",
}


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class DiscoveredInstrument:
    source: str               # "VISA", "LAN", or "AD2"
    address: str              # VISA resource string or IP:port
    idn: Optional[str] = None
    label: Optional[str] = None
    error: Optional[str] = None
    port: Optional[int] = None


# ── VISA discovery ────────────────────────────────────────────────────────────

def _idn_from_visa_resource(rm, resource_string: str, timeout_ms: int = 5000) -> tuple[Optional[str], Optional[str]]:
    """Open a VISA resource, send *IDN?, return (idn, error)."""
    try:
        res = rm.open_resource(resource_string)
        res.timeout = timeout_ms
        idn = res.query("*IDN?").strip()
        res.close()
        return idn, None
    except Exception as exc:
        return None, str(exc)


def discover_via_visa(timeout_ms: int = 5000) -> list[DiscoveredInstrument]:
    """Return all instruments visible through the VISA resource manager."""
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
            source="VISA",
            address=addr,
            idn=idn,
            label=label,
            error=err,
        ))

    rm.close()
    return results


# ── LAN subnet scan ───────────────────────────────────────────────────────────

def _probe_host_port(ip: str, port: int, connect_timeout: float) -> bool:
    """Return True if <ip>:<port> is open (TCP connect succeeds)."""
    try:
        with socket.create_connection((ip, port), timeout=connect_timeout):
            return True
    except OSError:
        return False


def _idn_via_scpi_raw(ip: str, port: int = 5025, timeout: float = 3.0) -> Optional[str]:
    """
    Query *IDN? over a raw TCP socket (port 5025 SCPI-TCP).
    Returns the response string or None on failure.
    """
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
    """
    Attempt *IDN? using pyvisa over TCPIP, trying HiSLIP then VXI-11 resource strings.
    Returns the IDN string or None.
    """
    try:
        import pyvisa
        rm = pyvisa.ResourceManager()
    except Exception:
        return None

    candidates = []
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
    """
    Check a single IP for VISA LAN ports.  Returns a DiscoveredInstrument if
    any VISA port is open, otherwise None.
    """
    best_effort_result: Optional[DiscoveredInstrument] = None
    for port, protocol in VISA_LAN_PORTS.items():
        if _probe_host_port(ip, port, connect_timeout):
            # Try SCPI-RAW first (fastest), then VISA
            idn = None
            if port == 5025:
                idn = _idn_via_scpi_raw(ip, port=5025, timeout=connect_timeout + 1.0)
            if idn is None:
                idn = _idn_via_visa_tcpip(ip, port, timeout_ms=visa_timeout_ms)

            label = _identify(idn) if idn else None
            result = DiscoveredInstrument(
                source="LAN",
                address=ip,
                idn=idn,
                label=label,
                port=port,
                error=None if idn else f"Port {port} open ({protocol}) but *IDN? failed",
            )
            if idn:
                return result
            if best_effort_result is None:
                best_effort_result = result
    return best_effort_result


def scan_subnet(subnet: str, connect_timeout: float = 0.5, max_workers: int = 64,
                visa_timeout_ms: int = 5000) -> list[DiscoveredInstrument]:
    """
    Scan all 254 host addresses in <subnet> (e.g. "192.168.1") for VISA ports.

    Args:
        subnet:          First three octets, e.g. "192.168.1"
        connect_timeout: TCP connect timeout per host/port (seconds)
        max_workers:     Thread pool size (higher = faster scan, more load)
        visa_timeout_ms: VISA IDN query timeout (milliseconds)

    Returns:
        List of DiscoveredInstrument for every host that had at least one VISA port open.
    """
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
    """
    Detect connected Digilent Analog Discovery devices via the DWF library.
    Returns one DiscoveredInstrument per device found.
    """
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
        print("[AD2] DWF library not found — Digilent Waveforms may not be installed.")
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
        sn_buf = ctypes.create_string_buffer(64)
        dwf.FDwfEnumDeviceName(c_int(i), name_buf)
        dwf.FDwfEnumSN(c_int(i), sn_buf)
        name = name_buf.value.decode(errors="replace").strip()
        sn = sn_buf.value.decode(errors="replace").strip()
        results.append(DiscoveredInstrument(
            source="AD2",
            address=f"DWF device index {i}",
            idn=f"{name} S/N:{sn}",
            label=f"Digilent {name}",
        ))

    return results


# ── Helpers ───────────────────────────────────────────────────────────────────

def _identify(idn: Optional[str]) -> Optional[str]:
    """Match an *IDN? string against known fingerprints."""
    if not idn:
        return None
    idn_upper = idn.upper()
    for fragment, label in IDN_FINGERPRINTS.items():
        if fragment.upper() in idn_upper:
            return label
    return None


def _visa_string_hint(instrument: DiscoveredInstrument) -> Optional[str]:
    """
    Suggest a VISA resource string for a LAN-discovered instrument.
    Not needed for VISA-discovered ones (address IS the resource string already).
    """
    if instrument.source != "LAN":
        return None
    ip = instrument.address
    port = instrument.port
    if port == 4880:
        return f"TCPIP0::{ip}::hislip0::INSTR"
    if port == 111:
        return f"TCPIP0::{ip}::inst0::INSTR"
    if port == 5025:
        return f"TCPIP0::{ip}::5025::SOCKET"
    return None


# ── Output formatting ─────────────────────────────────────────────────────────

def print_results(all_instruments: list[DiscoveredInstrument]) -> None:
    if not all_instruments:
        print("\nNo instruments discovered.")
        return

    print(f"\n{'='*70}")
    print(f"  DISCOVERED INSTRUMENTS ({len(all_instruments)} total)")
    print(f"{'='*70}")

    for inst in all_instruments:
        src_tag = f"[{inst.source}]"
        print(f"\n{src_tag} {inst.address}")
        if inst.port:
            print(f"  Port      : {inst.port} ({VISA_LAN_PORTS.get(inst.port, '?')})")
        if inst.label:
            print(f"  Type      : {inst.label}")
        if inst.idn:
            print(f"  IDN       : {inst.idn}")
        hint = _visa_string_hint(inst)
        if hint:
            print(f"  VISA str  : {hint}")
        if inst.error and not inst.idn:
            print(f"  Note      : {inst.error}")

    print(f"\n{'='*70}")
    print("  CONFIG HINT  (paste into config/dacdemo.toml [instruments])")
    print(f"{'='*70}")
    # Map label keywords → TOML key names from config/dacdemo.toml [instruments]
    label_to_key = {
        "N9010B": "sa_addr",
        "MSO":    "scope_addr",
        "MXR":    "scope_addr",
        "E363":   "scope_addr",   # not a scope, but won't collide in practice
        "SMA100": "siggen_addr",
    }
    assigned: dict[str, str] = {}
    for inst in all_instruments:
        if inst.source == "AD2":
            continue
        addr = inst.address if inst.source == "VISA" else (_visa_string_hint(inst) or inst.address)
        label = (inst.label or "").upper()
        for keyword, key in label_to_key.items():
            if keyword in label and key not in assigned:
                assigned[key] = addr
                break

    if assigned:
        print()
        # Preferred display order
        for key in ("siggen_addr", "scope_addr", "sa_addr"):
            if key in assigned:
                print(f"  {key} = \"{assigned[key]}\"")
        for key, addr in assigned.items():
            if key not in ("siggen_addr", "scope_addr", "sa_addr"):
                print(f"  {key} = \"{addr}\"")
    else:
        print("\n  (No recognized project instruments found)")

    print(f"\n{'='*70}\n")


# ── CLI entry point ───────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Discover VISA instruments (LAN + USB) and Analog Discovery devices.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--subnet", metavar="A.B.C",
        help="Scan this subnet (e.g. 192.168.1) for LAN instruments. Omit to skip LAN scan.",
    )
    parser.add_argument(
        "--timeout", type=float, default=0.5, metavar="SEC",
        help="TCP connect timeout per host during LAN scan (default: 0.5 s).",
    )
    parser.add_argument(
        "--visa-timeout", type=int, default=5000, metavar="MS",
        help="VISA IDN query timeout in milliseconds (default: 5000).",
    )
    parser.add_argument(
        "--threads", type=int, default=64,
        help="Thread pool size for LAN scan (default: 64).",
    )
    parser.add_argument(
        "--skip-visa", action="store_true",
        help="Skip VISA resource manager discovery.",
    )
    parser.add_argument(
        "--skip-ad2", action="store_true",
        help="Skip Analog Discovery device detection.",
    )
    parser.add_argument(
        "--json", metavar="FILE",
        help="Write results to FILE as JSON (in addition to stdout).",
    )
    args = parser.parse_args()

    all_results: list[DiscoveredInstrument] = []

    t0 = time.time()

    if not args.skip_visa:
        print("\n--- VISA Resource Manager ---")
        all_results += discover_via_visa(timeout_ms=args.visa_timeout)

    if args.subnet:
        # Validate format
        parts = args.subnet.split(".")
        if len(parts) != 3 or not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
            print(f"ERROR: --subnet must be three octets, e.g. 192.168.1  (got '{args.subnet}')")
            sys.exit(1)
        print("\n--- LAN Subnet Scan ---")
        all_results += scan_subnet(
            subnet=args.subnet,
            connect_timeout=args.timeout,
            max_workers=args.threads,
            visa_timeout_ms=args.visa_timeout,
        )

    if not args.skip_ad2:
        print("\n--- Analog Discovery ---")
        all_results += discover_analog_discovery()

    elapsed = time.time() - t0
    print_results(all_results)
    print(f"Discovery completed in {elapsed:.1f} s")

    if args.json:
        payload = [asdict(r) for r in all_results]
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"Results written to {args.json}")


if __name__ == "__main__":
    main()
