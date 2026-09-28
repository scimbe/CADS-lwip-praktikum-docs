#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# veroeffentlichen: ja
# Copyright (c) 2026 CADS AG
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""rnlab.py - Host-Werkzeug fuer das lwIP-Praktikum auf cads-zero.

Laeuft auf macOS, Linux und Windows mit Python >= 3.9, nur Standardbibliothek,
ohne Raw-Sockets und ohne Administratorrechte. Jeder Unterbefehl liefert mit
``--json`` ein maschinenlesbares Ergebnis.

Beispiele:
    python3 rnlab.py ping 192.168.33.99 -c 20
    python3 rnlab.py udp-send 192.168.33.99 7007 -n 1000 --rate 500 --burst 10
    python3 rnlab.py iperf2 192.168.33.99 -t 10
    python3 rnlab.py http "http://api.open-meteo.com/v1/forecast?latitude=53.55&longitude=9.99&current=temperature_2m"
    python3 rnlab.py lab 192.168.33.99 "lab info"
    python3 rnlab.py check --board 192.168.33.99
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import locale
import math
import os
import platform
import re
import shutil
import socket
import statistics
import struct
import subprocess
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlsplit

__version__ = "0.1.0"

DEFAULT_BOARD = "192.168.33.99"
TELNET_PORT = 4242
IPERF_PORT = 5001

# UDP-Datagrammformat (udp-send/udp-recv, Gegenstueck: Firmware-Versuch 07):
#   Byte 0-3   Sequenznummer, uint32 big-endian, beginnt bei 0
#   Byte 4-11  Sendezeitpunkt in Mikrosekunden seit Unix-Epoche, uint64 big-endian
#   Rest       mit 0x00 aufgefuellt bis zur gewaehlten Groesse
UDP_HEADER = struct.Struct("!IQ")

# Setup-Erkennung: Adresse des Rechners je Setup (siehe docs/reference/netz-setup.md).
SETUP_ADDRESSES = [
    ("S1", "192.168.33.10", "statische Adresse"),
    ("S2", "192.168.2.1", "Internetfreigabe macOS"),
    ("S2", "192.168.137.1", "Internetfreigabe Windows (ICS)"),
    ("S2", "10.42.0.1", "Internetfreigabe Linux (NetworkManager)"),
]


class RnlabError(Exception):
    """Erwarteter Fehler mit verstaendlicher Meldung (Exit-Code 2)."""


class BoardBusy(RnlabError):
    """Das Board bedient schon eine andere Telnet-Sitzung (Exit-Code 3)."""


def _now_us() -> int:
    return time.time_ns() // 1000


def _rate(bytes_: int, seconds: float) -> Optional[float]:
    return bytes_ * 8 / seconds if seconds > 0 else None


def _fmt_bps(bps: Optional[float]) -> str:
    if bps is None:
        return "-"
    for unit, div in (("Gbit/s", 1e9), ("Mbit/s", 1e6), ("kbit/s", 1e3)):
        if bps >= div:
            return f"{bps / div:.2f} {unit}"
    return f"{bps:.0f} bit/s"


def _fmt_ms(value: Optional[float]) -> str:
    return "-" if value is None else f"{value:.3f} ms"


def _stats(values: List[float]) -> Dict[str, Optional[float]]:
    """min/avg/max/stddev (Populations-Standardabweichung wie ping -mdev)."""
    if not values:
        return {"min": None, "avg": None, "max": None, "stddev": None}
    return {
        "min": min(values),
        "avg": statistics.fmean(values),
        "max": max(values),
        "stddev": statistics.pstdev(values) if len(values) > 1 else 0.0,
    }


# ---------------------------------------------------------------------------
# ping
# ---------------------------------------------------------------------------

PING_DEFAULT_SIZE = 56


def build_ping_command(host: str, count: int, size: Optional[int], interval: Optional[float],
                       timeout: Optional[float], system: Optional[str] = None,
                       df: bool = False) -> List[str]:
    """System-ping mit den Optionen des jeweiligen Betriebssystems."""
    system = system or platform.system()
    if system == "Windows":
        cmd = ["ping", "-n", str(count)]
        if size is not None:
            cmd += ["-l", str(size)]
        if timeout is not None:
            cmd += ["-w", str(int(timeout * 1000))]
        if df:
            cmd += ["-f"]
        # Windows-ping kennt kein Sendeintervall (fest 1 s).
        return cmd + [host]
    cmd = ["ping", "-c", str(count)]
    if size is not None:
        cmd += ["-s", str(size)]
    if df:
        cmd += ["-D"] if system == "Darwin" else ["-M", "do"]
    if interval is not None:
        cmd += ["-i", str(interval)]
    if timeout is not None:
        if system == "Darwin":
            cmd += ["-W", str(int(timeout * 1000))]  # macOS: Millisekunden
        else:
            cmd += ["-W", str(max(1, math.ceil(timeout)))]  # Linux: Sekunden
    return cmd + [host]


_RE_REPLY_RTT = re.compile(r"(?:time|zeit)\s*([=<])\s*([\d.,]+)\s*ms", re.IGNORECASE)
_RE_REPLY_TTL = re.compile(r"\bttl\s*=\s*(\d+)", re.IGNORECASE)
_RE_UNIX_SUMMARY = re.compile(
    r"(?:rtt|round-trip)\s+min/avg/max/(?:mdev|stddev)\s*=\s*"
    r"([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)\s*ms")
_RE_UNIX_COUNTS = re.compile(
    r"(\d+)\s+packets transmitted,\s*(\d+)\s+(?:packets\s+)?received.*?([\d.]+)%\s+packet loss",
    re.IGNORECASE)
_RE_WIN_COUNTS = re.compile(
    r"(?:Sent|Gesendet)\s*=\s*(\d+),\s*(?:Received|Empfangen)\s*=\s*(\d+),\s*"
    r"(?:Lost|Verloren)\s*=\s*(\d+)\s*\((\d+)%", re.IGNORECASE)
_RE_WIN_SUMMARY = re.compile(
    r"Minimum\s*=\s*(\d+)\s*ms,\s*Maximum\s*=\s*(\d+)\s*ms,\s*(?:Average|Mittelwert)\s*=\s*(\d+)\s*ms",
    re.IGNORECASE)


def parse_ping_output(text: str) -> Dict[str, Any]:
    """Wertet die Ausgabe von ping unter Linux, macOS und Windows (de/en) aus.

    Die Einzel-RTTs werden immer aus den Antwortzeilen gelesen. Min/avg/max/
    stddev stammen aus der Zusammenfassung von ping, wo es sie gibt; Windows
    liefert keine Standardabweichung (und nur ganze Millisekunden), dort wird
    aus den Einzelwerten gerechnet.
    """
    rtts: List[float] = []
    ttls: List[int] = []
    below_resolution = 0
    for line in text.splitlines():
        m = _RE_REPLY_RTT.search(line)
        if not m:
            continue
        rtts.append(float(m.group(2).replace(",", ".")))
        if m.group(1) == "<":
            below_resolution += 1
        t = _RE_REPLY_TTL.search(line)
        if t:
            ttls.append(int(t.group(1)))
    result: Dict[str, Any] = {"transmitted": None, "received": None, "loss_percent": None,
                              "rtt_ms": _stats(rtts), "rtt_source": "computed",
                              "replies_ms": rtts, "below_resolution": below_resolution,
                              "ttl": sorted(set(ttls))}
    m = _RE_UNIX_COUNTS.search(text)
    if m:
        result["transmitted"], result["received"] = int(m.group(1)), int(m.group(2))
        result["loss_percent"] = float(m.group(3))
    m = _RE_WIN_COUNTS.search(text)
    if m:
        result["transmitted"], result["received"] = int(m.group(1)), int(m.group(2))
        result["loss_percent"] = float(m.group(4))
    m = _RE_UNIX_SUMMARY.search(text)
    if m:
        mn, avg, mx, sd = (float(x) for x in m.groups())
        result["rtt_ms"] = {"min": mn, "avg": avg, "max": mx, "stddev": sd}
        result["rtt_source"] = "ping"
    elif _RE_WIN_SUMMARY.search(text) and rtts:
        # Windows: min/max/avg ganzzahlig; Streuung nur aus Einzelwerten ermittelbar.
        result["rtt_source"] = "computed"
    if result["transmitted"] and result["received"] is not None and result["loss_percent"] is None:
        result["loss_percent"] = 100.0 * (1 - result["received"] / result["transmitted"])
    return result


def percentiles(values: List[float], ps=(50, 90, 99)) -> Dict[str, Optional[float]]:
    """Perzentile nach dem Rangverfahren (nearest rank), z. B. p50 = Median."""
    ordered = sorted(values)
    out: Dict[str, Optional[float]] = {}
    for p in ps:
        out[f"p{p}"] = ordered[max(0, math.ceil(p / 100 * len(ordered)) - 1)] if ordered else None
    return out


def histogram(values: List[float], width: float) -> List[Dict[str, float]]:
    """Klassen [k*width, (k+1)*width) von 0 bis zum groessten Wert, auch leere Klassen."""
    if not values or width <= 0:
        return []
    counts: Dict[int, int] = {}
    for v in values:
        k = int(v // width)
        counts[k] = counts.get(k, 0) + 1
    return [{"from_ms": k * width, "to_ms": (k + 1) * width, "count": counts.get(k, 0)}
            for k in range(0, max(counts) + 1)]


# Windows: ICMP-Echo ueber die ICMP-API (iphlpapi.dll, ohne Administratorrechte).
# Das System-ping misst dort nur ganze Millisekunden; die Laufzeiten zum Board
# liegen darunter. Gemessen wird deshalb mit perf_counter um IcmpSendEcho; der
# Wert enthaelt den Aufrufaufwand der API (typisch einige 10 us).
IP_SUCCESS, IP_REQ_TIMED_OUT, IP_PACKET_TOO_BIG = 0, 11010, 11009
IP_FLAG_DF = 0x02


def icmp_api_ping(host: str, count: int, size: int = 32, interval: float = 1.0,
                  timeout: float = 1.0, df: bool = False) -> Dict[str, Any]:
    import ctypes
    from ctypes import wintypes

    class IpOptionInformation(ctypes.Structure):
        _fields_ = [("Ttl", ctypes.c_ubyte), ("Tos", ctypes.c_ubyte), ("Flags", ctypes.c_ubyte),
                    ("OptionsSize", ctypes.c_ubyte), ("OptionsData", ctypes.c_void_p)]

    class IcmpEchoReply(ctypes.Structure):
        _fields_ = [("Address", wintypes.ULONG), ("Status", wintypes.ULONG),
                    ("RoundTripTime", wintypes.ULONG), ("DataSize", wintypes.USHORT),
                    ("Reserved", wintypes.USHORT), ("Data", ctypes.c_void_p),
                    ("Options", IpOptionInformation)]

    api = ctypes.WinDLL("iphlpapi.dll")
    api.IcmpCreateFile.restype = wintypes.HANDLE
    api.IcmpSendEcho.argtypes = [wintypes.HANDLE, wintypes.ULONG, ctypes.c_void_p, wintypes.WORD,
                                 ctypes.POINTER(IpOptionInformation), ctypes.c_void_p,
                                 wintypes.DWORD, wintypes.DWORD]
    api.IcmpSendEcho.restype = wintypes.DWORD
    api.IcmpCloseHandle.argtypes = [wintypes.HANDLE]

    address = socket.getaddrinfo(host, None, socket.AF_INET)[0][4][0]
    dest = struct.unpack("<I", socket.inet_aton(address))[0]
    payload = ctypes.create_string_buffer(bytes((i % 256 for i in range(size))), size)
    options = IpOptionInformation(Ttl=128, Flags=IP_FLAG_DF if df else 0)
    reply_size = ctypes.sizeof(IcmpEchoReply) + size + 8 + 64
    reply_buf = ctypes.create_string_buffer(reply_size)
    handle = api.IcmpCreateFile()
    if not handle or handle == wintypes.HANDLE(-1).value:
        raise RnlabError("IcmpCreateFile fehlgeschlagen.")
    rtts: List[float] = []
    api_ms: List[int] = []
    ttls: List[int] = []
    statuses: Dict[str, int] = {}
    t0 = time.perf_counter()
    try:
        for i in range(count):
            if i:
                delay = t0 + i * interval - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)
            start = time.perf_counter()
            n = api.IcmpSendEcho(handle, dest, payload, size, ctypes.byref(options), reply_buf,
                                 reply_size, int(timeout * 1000))
            elapsed = (time.perf_counter() - start) * 1000.0
            reply = IcmpEchoReply.from_buffer(reply_buf)
            status = reply.Status if n else IP_REQ_TIMED_OUT
            if n and status == IP_SUCCESS:
                rtts.append(elapsed)
                api_ms.append(reply.RoundTripTime)
                ttls.append(reply.Options.Ttl)
            else:
                key = {IP_REQ_TIMED_OUT: "timeout", IP_PACKET_TOO_BIG: "packet_too_big"}.get(
                    status, str(status))
                statuses[key] = statuses.get(key, 0) + 1
    finally:
        api.IcmpCloseHandle(handle)
    return {"transmitted": count, "received": len(rtts),
            "loss_percent": 100.0 * (count - len(rtts)) / count if count else None,
            "rtt_ms": _stats(rtts), "rtt_source": "icmp-api+perf_counter", "replies_ms": rtts,
            "api_rtt_ms": api_ms, "below_resolution": 0, "ttl": sorted(set(ttls)),
            "errors": statuses}


def cmd_ping(args: argparse.Namespace) -> Dict[str, Any]:
    engine = args.engine
    if engine == "auto":
        engine = "api" if platform.system() == "Windows" else "system"
    if engine == "api":
        if platform.system() != "Windows":
            raise RnlabError("--engine api gibt es nur unter Windows.")
        result = icmp_api_ping(args.host, args.count, args.size,
                               1.0 if args.interval is None else args.interval,
                               1.0 if args.timeout is None else args.timeout, args.df)
        result.update({"host": args.host, "engine": "api"})
    else:
        result = _system_ping(args)
    result["percentiles_ms"] = percentiles(result["replies_ms"])
    if args.hist:
        result["histogram"] = histogram(result["replies_ms"], args.hist)
    return result


def _system_ping(args: argparse.Namespace) -> Dict[str, Any]:
    if shutil.which("ping") is None:
        raise RnlabError("Kein 'ping' im Suchpfad gefunden.")
    cmd = build_ping_command(args.host, args.count, args.size, args.interval, args.timeout,
                             df=args.df)
    encoding = locale.getpreferredencoding(False)
    if platform.system() == "Windows":
        # Die Konsolenprogramme schreiben in der OEM-Codepage (z. B. cp850).
        encoding = "oem" if _has_codec("oem") else encoding
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          encoding=encoding, errors="replace",
                          timeout=args.count * max(args.interval or 1.0, 1.0) + 30)
    result = parse_ping_output(proc.stdout)
    result.update({"host": args.host, "engine": "system", "command": cmd,
                   "exit_code": proc.returncode})
    if args.raw:
        result["raw"] = proc.stdout
    return result


def _has_codec(name: str) -> bool:
    import codecs
    try:
        codecs.lookup(name)
        return True
    except LookupError:
        return False


def format_ping(r: Dict[str, Any]) -> str:
    rtt = r["rtt_ms"]
    lines = [f"ping {r['host']}: {r['transmitted']} gesendet, {r['received']} empfangen, "
             f"Verlust {r['loss_percent']} %"]
    lines.append(f"RTT min/avg/max/stddev = {_fmt_ms(rtt['min'])} / {_fmt_ms(rtt['avg'])} / "
                 f"{_fmt_ms(rtt['max'])} / {_fmt_ms(rtt['stddev'])}  (Quelle: {r['rtt_source']})")
    pc = r.get("percentiles_ms") or {}
    if pc.get("p50") is not None:
        lines.append(f"Median {_fmt_ms(pc['p50'])}, p90 {_fmt_ms(pc['p90'])}, p99 {_fmt_ms(pc['p99'])}")
    if r.get("ttl"):
        lines.append("TTL der Antworten: " + ", ".join(str(t) for t in r["ttl"]))
    if r.get("errors"):
        lines.append("Ohne Antwort: " + ", ".join(f"{k} x{v}" for k, v in r["errors"].items()))
    if r.get("below_resolution"):
        lines.append(f"Hinweis: {r['below_resolution']} Antworten unter der Aufloesung von ping "
                     "(Windows: '<1ms' wird als 1 ms gezaehlt).")
    if r.get("histogram"):
        peak = max(b["count"] for b in r["histogram"]) or 1
        for b in r["histogram"]:
            bar = "#" * max(1 if b["count"] else 0, round(40 * b["count"] / peak))
            lines.append(f"{b['from_ms']:8.3f}-{b['to_ms']:<8.3f} ms {b['count']:>5}  {bar}")
    if r.get("raw"):
        lines.append(r["raw"].rstrip())
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# UDP
# ---------------------------------------------------------------------------

def udp_send(host: str, port: int, count: int, size: int = 64, rate: float = 0.0,
             burst: int = 1, start_seq: int = 0) -> Dict[str, Any]:
    """Sendet `count` Datagramme; `rate` in Datagrammen/s (0 = so schnell wie moeglich).

    Mit `burst` > 1 gehen jeweils `burst` Datagramme direkt hintereinander raus,
    danach wird so lange gewartet, dass die mittlere Rate `rate` eingehalten wird.
    """
    if size < UDP_HEADER.size:
        raise RnlabError(f"--size muss mindestens {UDP_HEADER.size} Byte sein.")
    if burst < 1:
        raise RnlabError("--burst muss >= 1 sein.")
    addr = socket.getaddrinfo(host, port, type=socket.SOCK_DGRAM)[0]
    sock = socket.socket(addr[0], socket.SOCK_DGRAM)
    padding = bytes(size - UDP_HEADER.size)
    sent = errors = 0
    t0 = time.perf_counter()
    try:
        for seq in range(start_seq, start_seq + count):
            if rate > 0 and (seq - start_seq) % burst == 0:
                due = t0 + (seq - start_seq) / rate
                delay = due - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)
            payload = UDP_HEADER.pack(seq & 0xFFFFFFFF, _now_us()) + padding
            try:
                sock.sendto(payload, addr[4])
                sent += 1
            except OSError:
                # z. B. ENOBUFS bei sehr hohen Raten; wird gezaehlt, nicht abgebrochen.
                errors += 1
    finally:
        sock.close()
    duration = time.perf_counter() - t0
    return {"host": host, "port": port, "sent": sent, "send_errors": errors, "size": size,
            "bytes": sent * size, "duration_s": duration,
            "rate_pps": sent / duration if duration > 0 else None,
            "payload_bps": _rate(sent * size, duration), "burst": burst, "target_rate_pps": rate}


def cmd_udp_send(args: argparse.Namespace) -> Dict[str, Any]:
    return udp_send(args.host, args.port, args.count, args.size, args.rate, args.burst)


def format_udp_send(r: Dict[str, Any]) -> str:
    rate = "-" if r["rate_pps"] is None else f"{r['rate_pps']:.1f}"
    return (f"UDP an {r['host']}:{r['port']}: {r['sent']} Datagramme a {r['size']} Byte "
            f"in {r['duration_s']:.3f} s ({rate} pps, Nutzdaten {_fmt_bps(r['payload_bps'])}), "
            f"Sendefehler {r['send_errors']}")


def udp_recv(port: int, bind: str = "0.0.0.0", count: Optional[int] = None,
             idle_timeout: float = 3.0, first_timeout: float = 60.0,
             ready: Optional[threading.Event] = None,
             bound_port: Optional[List[int]] = None,
             expect: Optional[int] = None) -> Dict[str, Any]:
    """Empfaengt Datagramme im rnlab-Format und wertet Verlust, Reihenfolge und Jitter aus.

    Ende: nach `count` Datagrammen oder `idle_timeout` s Ruhe nach dem ersten.
    Ohne `expect` wird die erwartete Anzahl aus der kleinsten und groessten
    empfangenen Sequenznummer geschaetzt - Verluste am Anfang und Ende des
    Stroms fallen dann nicht auf. Mit `expect` (= -n des Senders) schon.
    Jitter nach RFC 3550, Abschnitt 6.4.1 (J += (|D| - J)/16); er haengt nur von
    Laufzeitdifferenzen ab und ist daher auch bei nicht synchronen Uhren gueltig.
    Die Einweg-Laufzeit dagegen nur bei gemeinsamer Uhr (z. B. Loopback).
    """
    family = socket.AF_INET6 if ":" in bind else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_DGRAM)
    sock.bind((bind, port))
    if bound_port is not None:
        bound_port.append(sock.getsockname()[1])
    if ready is not None:
        ready.set()
    received = bytes_ = duplicates = reordered = malformed = 0
    seen = set()
    highest = -1
    first_seq: Optional[int] = None
    jitter = 0.0
    prev_transit: Optional[float] = None
    delays: List[float] = []
    t_first = t_last = None
    sock.settimeout(first_timeout)
    try:
        while count is None or received < count:
            try:
                data, _peer = sock.recvfrom(65535)
            except socket.timeout:
                break
            now_us = _now_us()
            t_last = time.perf_counter()
            if t_first is None:
                t_first = t_last
                sock.settimeout(idle_timeout)
            if len(data) < UDP_HEADER.size:
                malformed += 1
                continue
            seq, sent_us = UDP_HEADER.unpack_from(data)
            received += 1
            bytes_ += len(data)
            if first_seq is None:
                first_seq = seq
            if seq in seen:
                duplicates += 1
                continue
            seen.add(seq)
            if seq < highest:
                reordered += 1
            highest = max(highest, seq)
            transit = (now_us - sent_us) / 1000.0
            delays.append(transit)
            if prev_transit is not None:
                jitter += (abs(transit - prev_transit) - jitter) / 16.0
            prev_transit = transit
    finally:
        sock.close()
    unique = len(seen)
    if expect is not None:
        expected = expect
    else:
        expected = (highest - min(seen) + 1) if seen else 0
    duration = (t_last - t_first) if t_first is not None and t_last is not None else 0.0
    return {"port": port, "received": received, "unique": unique, "bytes": bytes_,
            "first_seq": first_seq, "lowest_seq": min(seen) if seen else None,
            "highest_seq": highest if seen else None, "expected": expected,
            "lost": expected - unique, "loss_percent": 100.0 * (expected - unique) / expected if expected else None,
            "duplicates": duplicates, "reordered": reordered, "malformed": malformed,
            "duration_s": duration, "payload_bps": _rate(bytes_, duration),
            "jitter_ms": jitter if unique > 1 else None,
            "one_way_delay_ms": _stats(delays),
            "note": "one_way_delay_ms nur bei gemeinsamer Uhr von Sender und Empfaenger aussagekraeftig"}


def cmd_udp_recv(args: argparse.Namespace) -> Dict[str, Any]:
    if not args.json:
        print(f"Warte auf UDP an {args.bind}:{args.port} ...", file=sys.stderr)
    return udp_recv(args.port, args.bind, args.count, args.idle, args.wait, expect=args.expect)


def format_udp_recv(r: Dict[str, Any]) -> str:
    if not r["received"]:
        return f"UDP :{r['port']}: nichts empfangen."
    loss = "-" if r["loss_percent"] is None else f"{r['loss_percent']:.2f} %"
    jit = "-" if r["jitter_ms"] is None else f"{r['jitter_ms']:.3f} ms"
    return (f"UDP :{r['port']}: {r['unique']} von {r['expected']} erwarteten Datagrammen "
            f"(Seq {r['lowest_seq']}..{r['highest_seq']}), Verlust {r['lost']} ({loss}), "
            f"Duplikate {r['duplicates']}, umsortiert {r['reordered']}, fehlerhaft {r['malformed']}\n"
            f"Dauer {r['duration_s']:.3f} s, {_fmt_bps(r['payload_bps'])}, Jitter (RFC 3550) {jit}")


# ---------------------------------------------------------------------------
# TCP
# ---------------------------------------------------------------------------

def _connect(host: str, port: int, timeout: float) -> tuple:
    t0 = time.perf_counter()
    sock = socket.create_connection((host, port), timeout=timeout)
    return sock, (time.perf_counter() - t0) * 1000.0


def _send_stream(sock: socket.socket, total: Optional[int], seconds: Optional[float], chunk: int,
                 fill: Callable[[int, int], bytes], offset: int = 0,
                 interval: Optional[float] = None) -> Dict[str, Any]:
    """Sendet bis `total` Byte oder `seconds` Sekunden erreicht sind."""
    sent = 0
    t0 = time.perf_counter()
    intervals: List[Dict[str, float]] = []
    next_mark = t0 + interval if interval else None
    last_mark, last_bytes = t0, 0
    while True:
        now = time.perf_counter()
        if total is not None and sent >= total:
            break
        if seconds is not None and now - t0 >= seconds:
            break
        n = chunk if total is None else min(chunk, total - sent)
        sock.sendall(fill(offset + sent, n))
        sent += n
        if next_mark is not None and time.perf_counter() >= next_mark:
            now = time.perf_counter()
            intervals.append({"start_s": last_mark - t0, "end_s": now - t0,
                              "bytes": sent - last_bytes,
                              "bps": _rate(sent - last_bytes, now - last_mark) or 0.0})
            last_mark, last_bytes = now, sent
            next_mark = now + interval
    return {"bytes": sent, "send_time_s": time.perf_counter() - t0, "intervals": intervals, "t0": t0}


def _finish_send(sock: socket.socket, wait: float) -> Optional[float]:
    """Halb-Schliessen und auf das FIN der Gegenseite warten.

    Liefert den Zeitpunkt (perf_counter), zu dem die Gegenseite geschlossen hat,
    oder None, falls sie das innerhalb von `wait` s nicht tut. Erst dieser Zeitpunkt
    belegt, dass alle Daten angekommen sind; sendall() kehrt schon zurueck, wenn
    die Daten im lokalen Sendepuffer liegen.
    """
    try:
        sock.shutdown(socket.SHUT_WR)
    except OSError:
        return None
    sock.settimeout(wait)
    try:
        while sock.recv(65536):
            pass
        return time.perf_counter()
    except (socket.timeout, OSError):
        return None


def tcp_send(host: str, port: int, total: Optional[int] = None, seconds: Optional[float] = None,
             chunk: int = 1460, wait: float = 5.0, timeout: float = 5.0) -> Dict[str, Any]:
    if total is None and seconds is None:
        total = 1_000_000
    sock, connect_ms = _connect(host, port, timeout)
    sock.settimeout(None)
    try:
        s = _send_stream(sock, total, seconds, chunk, lambda _o, n: bytes(n))
        t_end = _finish_send(sock, wait)
    finally:
        sock.close()
    until_close = (t_end - s["t0"]) if t_end is not None else None
    return {"host": host, "port": port, "chunk": chunk, "bytes": s["bytes"],
            "connect_ms": connect_ms, "send_time_s": s["send_time_s"],
            "send_side_bps": _rate(s["bytes"], s["send_time_s"]),
            "until_peer_close_s": until_close,
            "goodput_bps": _rate(s["bytes"], until_close) if until_close else None,
            "peer_closed": t_end is not None}


def cmd_tcp_send(args: argparse.Namespace) -> Dict[str, Any]:
    return tcp_send(args.host, args.port, args.bytes, args.time, args.chunk, args.wait)


def format_tcp_send(r: Dict[str, Any]) -> str:
    lines = [f"TCP an {r['host']}:{r['port']}: {r['bytes']} Byte in Bloecken zu {r['chunk']} Byte, "
             f"Verbindungsaufbau {r['connect_ms']:.3f} ms",
             f"Sendeseite (bis letzter sendall): {r['send_time_s']:.3f} s, {_fmt_bps(r['send_side_bps'])}"]
    if r["peer_closed"]:
        lines.append(f"Goodput (bis FIN der Gegenseite): {r['until_peer_close_s']:.3f} s, "
                     f"{_fmt_bps(r['goodput_bps'])}")
    else:
        lines.append("Gegenseite hat nicht geschlossen - Goodput nur sendeseitig "
                     "(ueberschaetzt um den Sendepuffer).")
    return "\n".join(lines)


def tcp_recv(port: int, bind: str = "0.0.0.0", timeout: float = 60.0,
             ready: Optional[threading.Event] = None,
             bound_port: Optional[List[int]] = None) -> Dict[str, Any]:
    family = socket.AF_INET6 if ":" in bind else socket.AF_INET
    srv = socket.socket(family, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((bind, port))
    srv.listen(1)
    if bound_port is not None:
        bound_port.append(srv.getsockname()[1])
    if ready is not None:
        ready.set()
    srv.settimeout(timeout)
    try:
        conn, peer = srv.accept()
    except socket.timeout:
        srv.close()
        raise RnlabError(f"Keine Verbindung innerhalb von {timeout} s.")
    srv.close()
    conn.settimeout(timeout)
    total = reads = 0
    t0 = time.perf_counter()
    t_first = None
    try:
        while True:
            data = conn.recv(65536)
            if not data:
                break
            if t_first is None:
                t_first = time.perf_counter()
            total += len(data)
            reads += 1
    finally:
        conn.close()
    t_end = time.perf_counter()
    return {"port": port, "peer": f"{peer[0]}:{peer[1]}", "bytes": total, "reads": reads,
            "duration_s": t_end - t0, "goodput_bps": _rate(total, t_end - t0),
            "first_byte_ms": (t_first - t0) * 1000.0 if t_first else None}


def cmd_tcp_recv(args: argparse.Namespace) -> Dict[str, Any]:
    if not args.json:
        print(f"Warte auf TCP an {args.bind}:{args.port} ...", file=sys.stderr)
    return tcp_recv(args.port, args.bind, args.wait)


def format_tcp_recv(r: Dict[str, Any]) -> str:
    return (f"TCP :{r['port']} von {r['peer']}: {r['bytes']} Byte in {r['duration_s']:.3f} s "
            f"({r['reads']} recv-Aufrufe), Goodput {_fmt_bps(r['goodput_bps'])}")


# ---------------------------------------------------------------------------
# iperf2 (Client gegen lwiperf auf dem Board)
# ---------------------------------------------------------------------------

# iperf2-Client-Header (6 x int32, Netzbyteordnung), wie ihn lwIPs lwiperf
# (struct _lwiperf_settings) auswertet: flags, num_threads, remote_port,
# buffer_len, win_band, amount. flags = 0 heisst: kein Dual-/Tradeoff-Test,
# der Server misst nur. amount < 0 bedeutet Zeit in 10-ms-Einheiten.
IPERF_HEADER = struct.Struct("!iiiiii")
_DIGITS = b"0123456789"


def iperf_pattern(offset: int, length: int) -> bytes:
    """iperf2-Nutzdatenmuster: Byte an Stromposition p ist '0' + p % 10."""
    start = offset % 10
    reps = (start + length) // 10 + 1
    return (_DIGITS * reps)[start:start + length]


def iperf2_header(seconds: Optional[float], total: Optional[int], port: int, buf_len: int) -> bytes:
    amount = -int(round(seconds * 100)) if seconds is not None else int(total or 0)
    return IPERF_HEADER.pack(0, 1, port, buf_len, 0, amount)


def iperf2_client(host: str, port: int = IPERF_PORT, seconds: Optional[float] = 10.0,
                  total: Optional[int] = None, length: int = 8192,
                  interval: Optional[float] = None, timeout: float = 5.0,
                  wait: float = 5.0) -> Dict[str, Any]:
    if total is not None:
        seconds = None
    header = iperf2_header(seconds, total, port, 0)
    sock, connect_ms = _connect(host, port, timeout)
    sock.settimeout(None)

    def fill(offset: int, n: int) -> bytes:
        data = bytearray(iperf_pattern(offset, n))
        if offset < len(header):
            k = min(len(header) - offset, n)
            data[:k] = header[offset:offset + k]
        return bytes(data)

    try:
        s = _send_stream(sock, total, seconds, length, fill, 0, interval)
        t_end = _finish_send(sock, wait)
    finally:
        sock.close()
    t_ref = (t_end - s["t0"]) if t_end is not None else s["send_time_s"]
    return {"host": host, "port": port, "bytes": s["bytes"], "length": length,
            "connect_ms": connect_ms, "duration_s": t_ref, "bps": _rate(s["bytes"], t_ref),
            "peer_closed": t_end is not None, "intervals": s["intervals"]}


def cmd_iperf2(args: argparse.Namespace) -> Dict[str, Any]:
    return iperf2_client(args.host, args.port, args.time, args.bytes, args.len, args.interval)


def format_iperf2(r: Dict[str, Any]) -> str:
    lines = [f"iperf2 an {r['host']}:{r['port']} (Blockgroesse {r['length']} Byte, "
             f"Verbindungsaufbau {r['connect_ms']:.3f} ms)"]
    for iv in r["intervals"]:
        lines.append(f"[{iv['start_s']:6.2f}-{iv['end_s']:6.2f} s] {iv['bytes']:>12} Byte  {_fmt_bps(iv['bps'])}")
    ref = "bis FIN der Gegenseite" if r["peer_closed"] else "nur sendeseitig"
    lines.append(f"[gesamt] {r['bytes']} Byte in {r['duration_s']:.3f} s = {_fmt_bps(r['bps'])} ({ref})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def _dechunk(body: bytes) -> tuple:
    """Dekodiert Transfer-Encoding: chunked. Liefert (Nutzdaten, Anzahl Chunks)."""
    out = bytearray()
    pos = chunks = 0
    while True:
        eol = body.find(b"\r\n", pos)
        if eol < 0:
            break
        size_field = body[pos:eol].split(b";", 1)[0].strip()
        try:
            size = int(size_field, 16)
        except ValueError:
            break
        pos = eol + 2
        if size == 0:
            break
        out += body[pos:pos + size]
        pos += size + 2
        chunks += 1
    return bytes(out), chunks


def http_get(url: str, version: str = "1.0", timeout: float = 10.0,
             extra_headers: Optional[List[str]] = None) -> Dict[str, Any]:
    parts = urlsplit(url)
    if parts.scheme != "http":
        raise RnlabError("Nur http:// wird unterstuetzt (das Board spricht kein TLS).")
    host = parts.hostname or ""
    port = parts.port or 80
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query
    host_header = host if parts.port in (None, 80) else f"{host}:{port}"
    lines = [f"GET {path} HTTP/{version}", f"Host: {host_header}", f"User-Agent: rnlab/{__version__}"]
    if version == "1.1":
        lines.append("Connection: close")
    lines += extra_headers or []
    request = ("\r\n".join(lines) + "\r\n\r\n").encode("ascii")

    t0 = time.perf_counter()
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    t_dns = time.perf_counter()
    family, _, _, _, sockaddr = infos[0]
    sock = socket.socket(family, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(sockaddr)
        t_conn = time.perf_counter()
        sock.sendall(request)
        chunks: List[bytes] = []
        t_first = None
        while True:
            data = sock.recv(65536)
            if not data:
                break
            if t_first is None:
                t_first = time.perf_counter()
            chunks.append(data)
    finally:
        sock.close()
    t_end = time.perf_counter()
    raw = b"".join(chunks)
    sep = raw.find(b"\r\n\r\n")
    head, body = (raw[:sep + 4], raw[sep + 4:]) if sep >= 0 else (raw, b"")
    head_lines = head.decode("iso-8859-1").split("\r\n")
    headers: Dict[str, str] = {}
    for line in head_lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    chunked = "chunked" in headers.get("transfer-encoding", "").lower()
    payload, n_chunks = _dechunk(body) if chunked else (body, 0)
    ms = lambda a, b: (b - a) * 1000.0 if a is not None and b is not None else None  # noqa: E731
    return {"url": url, "address": sockaddr[0], "port": port, "http_version": version,
            "status_line": head_lines[0] if head_lines else "", "headers": headers,
            "timing_ms": {"dns": ms(t0, t_dns), "connect": ms(t_dns, t_conn),
                          "first_byte": ms(t_conn, t_first), "transfer": ms(t_first, t_end),
                          "total": ms(t0, t_end)},
            "request_bytes": len(request), "header_bytes": len(head), "body_wire_bytes": len(body),
            "chunked": chunked, "chunks": n_chunks, "body_bytes": len(payload),
            "chunk_overhead_bytes": len(body) - len(payload) if chunked else 0,
            "header_share_percent": 100.0 * len(head) / len(raw) if raw else None,
            "body": payload.decode("utf-8", errors="replace")}


def cmd_http(args: argparse.Namespace) -> Dict[str, Any]:
    r = http_get(args.url, args.http_version, args.timeout, args.header)
    if not args.body:
        r.pop("body")
    return r


def format_http(r: Dict[str, Any]) -> str:
    t = r["timing_ms"]
    lines = [f"{r['status_line']}  ({r['address']}:{r['port']}, Anfrage HTTP/{r['http_version']})",
             f"Zeiten: DNS {_fmt_ms(t['dns'])} | Verbindung {_fmt_ms(t['connect'])} | "
             f"erstes Byte {_fmt_ms(t['first_byte'])} | Uebertragung {_fmt_ms(t['transfer'])} | "
             f"gesamt {_fmt_ms(t['total'])}",
             f"Bytes: Anfrage {r['request_bytes']} | Antwort-Header {r['header_bytes']} | "
             f"Body auf der Leitung {r['body_wire_bytes']} | Body-Nutzdaten {r['body_bytes']}"]
    if r["header_share_percent"] is not None:
        lines.append(f"Header-Anteil an der Antwort: {r['header_share_percent']:.1f} %")
    if r["chunked"]:
        lines.append(f"Transfer-Encoding chunked: {r['chunks']} Chunks, "
                     f"{r['chunk_overhead_bytes']} Byte Chunk-Overhead")
    if "body" in r:
        lines += ["", r["body"]]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Telnet-/lab-Client
# ---------------------------------------------------------------------------

IAC, DONT, DO, WONT, WILL, SB, SE = 255, 254, 253, 252, 251, 250, 240


def telnet_filter(data: bytes) -> tuple:
    """Entfernt Telnet-Steuersequenzen. Liefert (Text, Antwort-Bytes).

    Optionswuensche werden abgelehnt (DO -> WONT, WILL -> DONT); die Firmware
    braucht keine ausgehandelten Optionen. Sequenzen, die am Pufferende
    abgeschnitten sind, werden verworfen - fuer einen Zeilenclient genuegt das.
    """
    out = bytearray()
    reply = bytearray()
    i = 0
    while i < len(data):
        b = data[i]
        if b != IAC:
            out.append(b)
            i += 1
            continue
        if i + 1 >= len(data):
            break
        cmd = data[i + 1]
        if cmd == IAC:
            out.append(IAC)
            i += 2
        elif cmd in (DO, DONT, WILL, WONT):
            if i + 2 < len(data):
                opt = data[i + 2]
                if cmd == DO:
                    reply += bytes([IAC, WONT, opt])
                elif cmd == WILL:
                    reply += bytes([IAC, DONT, opt])
            i += 3
        elif cmd == SB:
            end = data.find(bytes([IAC, SE]), i + 2)
            i = len(data) if end < 0 else end + 2
        else:
            i += 2
    return bytes(out), bytes(reply)


def _read_until_quiet(sock: socket.socket, idle: float, overall: float,
                      prompt: Optional[str]) -> tuple:
    """Liest bis Prompt, Ruhe oder Gesamt-Timeout. Liefert (Text, Gegenseite geschlossen)."""
    buf = bytearray()
    eof = False
    deadline = time.monotonic() + overall
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        sock.settimeout(min(idle, remaining))
        try:
            data = sock.recv(4096)
        except socket.timeout:
            break
        if not data:
            eof = True
            break
        text, reply = telnet_filter(data)
        if reply:
            sock.sendall(reply)
        buf += text
        if prompt and buf.decode("utf-8", errors="replace").endswith(prompt):
            break
    return buf.decode("utf-8", errors="replace"), eof


def _clean_output(text: str, command: str, prompt: Optional[str]) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    if lines and lines[0].strip() == command.strip():
        lines = lines[1:]  # Echo der Eingabe
    if prompt and lines and lines[-1] == prompt:
        lines = lines[:-1]
    return "\n".join(lines).strip("\n")


# Board-CLI (cads-zero, apps/rnlab): Prompt "> " nach jeder Zeile (CR, LF,
# CRLF und CR NUL zaehlen je einmal), kein Echo, Telnet-Optionen werden
# gefiltert und nicht beantwortet, Zeilen max. 95 Zeichen, Fehlerzeilen
# beginnen mit "? ". Nach `lab net ...` schliesst das Board die Verbindung.
BOARD_PROMPT = "> "
BOARD_MAX_LINE = 95
# Ruhezeit, nach der eine Ausgabe ohne Prompt als fertig gilt. Das Board
# antwortet waehrend eines Vollbild-Blits (PA7) ~0,45 s lang nicht
# (fw-framework, gemessen) - 0,5 s waren zu knapp. Der Prompt beendet frueher.
BOARD_IDLE = 1.0
# Das Board puffert je Befehl 1 KB Ausgabe; bei Ueberlauf endet sie hiermit.
BOARD_TRUNCATED = "? Ausgabe gekuerzt"
# Zweite Verbindung: das Board sendet diese Zeile und schliesst. Aeltere
# Firmware nimmt die Verbindung an und schweigt (kein Banner) oder schliesst
# sie sofort - beides gilt ebenfalls als belegt; das Banner kommt sonst sofort.
BOARD_BUSY = "? belegt"


def _open_session(host: str, port: int, idle: float, overall: float, prompt: Optional[str],
                  timeout: float) -> tuple:
    """Verbindet und liest das Banner. Wirft BoardBusy, wenn das Board belegt ist."""
    sock, connect_ms = _connect(host, port, timeout)
    try:
        text, closed = _read_until_quiet(sock, idle, overall, prompt)
    except ConnectionResetError:
        sock.close()
        raise BoardBusy(f"{host}:{port} hat die Verbindung sofort zurueckgesetzt "
                        "(andere Sitzung aktiv?)")
    if BOARD_BUSY in text or not text.strip():
        sock.close()
        line = next((l for l in text.splitlines() if BOARD_BUSY in l), "").strip()
        how = "ohne Begruessung geschlossen" if closed else "angenommen, aber keine Begruessung gesendet"
        raise BoardBusy(line or f"{host}:{port} hat die Verbindung {how} (andere Sitzung aktiv?)")
    return sock, connect_ms, text, closed


def _open_session_retry(host: str, port: int, idle: float, overall: float,
                        prompt: Optional[str], timeout: float, retry: int) -> tuple:
    """Wie _open_session, bei belegtem Board bis zu `retry` weitere Versuche.

    Wartezeit 0,5 s, 1 s, 2 s, dann jeweils 4 s. "connection refused" und ein
    Timeout beim Verbindungsaufbau werden ebenfalls wiederholt: waehrend das
    Board eine Sitzung bedient oder beendet, nimmt es kurz keine neue an.
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            return _open_session(host, port, idle, overall, prompt, timeout) + (attempt,)
        except (BoardBusy, ConnectionRefusedError, socket.timeout):
            if attempt > retry:
                raise
            time.sleep(min(0.5 * 2 ** (attempt - 1), 4.0))


def telnet_run(host: str, commands: List[str], port: int = TELNET_PORT, idle: float = BOARD_IDLE,
               overall: float = 5.0, prompt: Optional[str] = BOARD_PROMPT,
               timeout: float = 5.0, retry: int = 0) -> Dict[str, Any]:
    too_long = [c for c in commands if len(c) > BOARD_MAX_LINE]
    if too_long:
        raise RnlabError(f"Befehl laenger als {BOARD_MAX_LINE} Zeichen (verwirft das Board): "
                         f"{too_long[0][:40]}...")
    sock, connect_ms, text, closed, attempts = _open_session_retry(
        host, port, idle, overall, prompt, timeout, retry)
    results: List[Dict[str, Any]] = []
    try:
        banner = _clean_output(text, "", prompt)
        for command in commands:
            if closed:
                break
            t0 = time.perf_counter()
            try:
                # Nur CR: aeltere Firmware wertete CRLF als zwei Zeilenenden
                # (zwei Prompts); CR allein ist mit jeder Version eindeutig.
                sock.sendall(command.encode("utf-8") + b"\r")
                out, closed = _read_until_quiet(sock, idle, overall, prompt)
            except OSError:
                closed = True
                break
            output = _clean_output(out, command, prompt)
            results.append({"command": command, "output": output,
                            "error": output.startswith("? "),
                            "truncated": output.endswith(BOARD_TRUNCATED),
                            "elapsed_ms": (time.perf_counter() - t0) * 1000.0})
    finally:
        sock.close()
    skipped = commands[len(results):]
    return {"host": host, "port": port, "connect_ms": connect_ms, "banner": banner,
            "attempts": attempts, "busy": False,
            "results": results, "connection_closed": closed, "not_sent": skipped}


def telnet_interactive(host: str, port: int = TELNET_PORT, timeout: float = 5.0) -> None:
    sock, _ = _connect(host, port, timeout)
    sock.settimeout(None)
    print(f"Verbunden mit {host}:{port}. Beenden mit Strg+D (Windows: Strg+Z, Enter).",
          file=sys.stderr)

    def reader() -> None:
        while True:
            try:
                data = sock.recv(4096)
            except OSError:
                break
            if not data:
                break
            text, reply = telnet_filter(data)
            if reply:
                try:
                    sock.sendall(reply)
                except OSError:
                    break
            sys.stdout.write(text.decode("utf-8", errors="replace"))
            sys.stdout.flush()
        print("\n[Verbindung geschlossen]", file=sys.stderr)
        os._exit(0)

    threading.Thread(target=reader, daemon=True).start()
    try:
        for line in sys.stdin:
            sock.sendall(line.rstrip("\r\n").encode("utf-8") + b"\r")
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()


def cmd_telnet(args: argparse.Namespace) -> Optional[Dict[str, Any]]:
    if not args.commands:
        if args.json:
            raise RnlabError("--json braucht mindestens einen Befehl.")
        telnet_interactive(args.host, args.port)
        return None
    return telnet_run(args.host, args.commands, args.port, args.idle, args.overall,
                      args.prompt or None, retry=args.retry)


def format_telnet(r: Dict[str, Any]) -> str:
    parts = []
    for item in r["results"]:
        if len(r["results"]) > 1:
            parts.append(f"> {item['command']}")
        parts.append(item["output"])
    if r.get("not_sent"):
        parts.append("[Verbindung vom Board geschlossen - nicht gesendet: "
                     + ", ".join(r["not_sent"]) + "]")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------

def local_address_bound(address: str) -> bool:
    """True, wenn `address` auf einer lokalen Schnittstelle konfiguriert ist.

    bind() auf eine fremde Adresse schlaegt mit EADDRNOTAVAIL fehl - das klappt
    auf allen drei Systemen ohne Rechte und ohne Schnittstellen-API.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.bind((address, 0))
        return True
    except OSError:
        return False
    finally:
        s.close()


def source_address_for(dest: str) -> Optional[str]:
    """Quelladresse, die das Betriebssystem fuer `dest` waehlen wuerde.

    connect() auf einem UDP-Socket sendet nichts, fuehrt aber die
    Routenauswahl aus; getsockname() zeigt die gewaehlte lokale Adresse.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((dest, 9))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


S1_NET = ipaddress.ip_network("192.168.33.0/24")
_RE_IFC_HEAD = re.compile(r"^([A-Za-z0-9_.-]+): flags=")
_RE_IFC_INET = re.compile(r"^\s+inet (\d+\.\d+\.\d+\.\d+)")
_RE_IFC_MEMBER = re.compile(r"^\s+member: (\S+)")
_RE_IP_ADDR = re.compile(r"^\d+:\s+(\S+?)(?:@\S+)?\s+inet\s+(\d+\.\d+\.\d+\.\d+)/")
_RE_NETSH_HEAD = re.compile(r'^(?:Konfiguration f\S+r Schnittstelle|Configuration for interface)\s+"([^"]+)"')
_RE_NETSH_IP = re.compile(r"^\s*(?:IP-Adresse|IP Address):\s+(\d+\.\d+\.\d+\.\d+)")


def parse_ifconfig(text: str) -> tuple:
    """macOS/BSD `ifconfig`: ({Schnittstelle: [IPv4]}, {Bridge: [Mitglieder]})."""
    addrs: Dict[str, List[str]] = {}
    members: Dict[str, List[str]] = {}
    current = None
    for line in text.splitlines():
        m = _RE_IFC_HEAD.match(line)
        if m:
            current = m.group(1)
            addrs.setdefault(current, [])
            continue
        if current is None:
            continue
        m = _RE_IFC_INET.match(line)
        if m:
            addrs[current].append(m.group(1))
        m = _RE_IFC_MEMBER.match(line)
        if m:
            members.setdefault(current, []).append(m.group(1))
    return addrs, members


def parse_ip_addr(text: str) -> Dict[str, List[str]]:
    """Linux `ip -o -4 addr show`."""
    addrs: Dict[str, List[str]] = {}
    for line in text.splitlines():
        m = _RE_IP_ADDR.match(line)
        if m:
            addrs.setdefault(m.group(1), []).append(m.group(2))
    return addrs


def parse_ip_link_master(text: str) -> Dict[str, List[str]]:
    """Linux `ip -o link show`: {Bridge: [Mitglieder]} aus "master <bridge>"."""
    members: Dict[str, List[str]] = {}
    for line in text.splitlines():
        m = re.match(r"^\d+:\s+(\S+?)(?:@\S+)?:.*\smaster\s+(\S+)", line)
        if m:
            members.setdefault(m.group(2), []).append(m.group(1))
    return members


def parse_netsh_addresses(text: str) -> Dict[str, List[str]]:
    """Windows `netsh interface ipv4 show addresses` (de/en)."""
    addrs: Dict[str, List[str]] = {}
    current = None
    for line in text.splitlines():
        m = _RE_NETSH_HEAD.match(line.strip())
        if m:
            current = m.group(1)
            addrs.setdefault(current, [])
            continue
        m = _RE_NETSH_IP.match(line)
        if m and current is not None:
            addrs[current].append(m.group(1))
    return addrs


def _run_quiet(cmd: List[str]) -> Optional[str]:
    try:
        encoding = "oem" if platform.system() == "Windows" and _has_codec("oem") else None
        return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5,
                              encoding=encoding or locale.getpreferredencoding(False),
                              errors="replace").stdout
    except (OSError, subprocess.SubprocessError):
        return None


def interface_map(system: Optional[str] = None) -> Optional[tuple]:
    """({Schnittstelle: [IPv4]}, {Bridge: [Mitglieder]}) oder None, falls nicht ermittelbar."""
    system = system or platform.system()
    if system == "Windows":
        out = _run_quiet(["netsh", "interface", "ipv4", "show", "addresses"])
        return (parse_netsh_addresses(out), {}) if out else None
    if system == "Linux" and shutil.which("ip"):
        out = _run_quiet(["ip", "-o", "-4", "addr", "show"])
        links = _run_quiet(["ip", "-o", "link", "show"]) or ""
        return (parse_ip_addr(out), parse_ip_link_master(links)) if out else None
    if shutil.which("ifconfig"):
        out = _run_quiet(["ifconfig"])
        return parse_ifconfig(out) if out else None
    return None


def assess_setup(ifmap: Optional[tuple]) -> Dict[str, Any]:
    """Ermittelt S1-Adressen (192.168.33.0/24), S2-Freigabeadressen und ob beide
    im selben Ethernet-Segment liegen (gleiche Schnittstelle oder gleiche Bridge)."""
    s2_known = {a: d for _s, a, d in SETUP_ADDRESSES if _s == "S2"}
    s1: List[Dict[str, Optional[str]]] = []
    s2: List[Dict[str, Optional[str]]] = []
    same: Optional[bool] = None
    if ifmap is not None:
        addrs, members = ifmap
        bridge_of = {m: b for b, ms in members.items() for m in ms}
        for ifc, ips in addrs.items():
            for ip in ips:
                if ipaddress.ip_address(ip) in S1_NET:
                    s1.append({"address": ip, "interface": ifc})
                elif ip in s2_known:
                    s2.append({"address": ip, "interface": ifc, "kind": s2_known[ip]})
        if s1 and s2:
            seg = lambda ifc: bridge_of.get(ifc, ifc)  # noqa: E731
            same = any(seg(a["interface"]) == seg(b["interface"]) for a in s1 for b in s2)
    else:
        src = source_address_for(DEFAULT_BOARD)
        if src and ipaddress.ip_address(src) in S1_NET and local_address_bound(src):
            s1.append({"address": src, "interface": None})
        s2 = [{"address": a, "interface": None, "kind": d}
              for a, d in s2_known.items() if local_address_bound(a)]
    return {"s1": s1, "s2": s2, "same_segment": same}


def _describe(entries: List[Dict[str, Optional[str]]]) -> str:
    return ", ".join(e["address"] + (f" auf {e['interface']}" if e["interface"] else "")
                     for e in entries)


def _tcp_reachable(host: str, port: int, timeout: float) -> Dict[str, Any]:
    t0 = time.perf_counter()
    try:
        socket.create_connection((host, port), timeout=timeout).close()
        return {"ok": True, "connect_ms": (time.perf_counter() - t0) * 1000.0}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}


def _find_wireshark() -> Optional[str]:
    for name in ("wireshark", "tshark", "Wireshark"):
        path = shutil.which(name)
        if path:
            return path
    candidates = ["/Applications/Wireshark.app",
                  os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Wireshark",
                               "Wireshark.exe")]
    return next((c for c in candidates if os.path.exists(c)), None)


def run_check(board: Optional[str], timeout: float = 2.0,
              ifmap: Optional[tuple] = None) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    def add(name: str, status: str, detail: str) -> None:
        checks.append({"name": name, "status": status, "detail": detail})

    py_ok = sys.version_info >= (3, 9)
    add("python", "ok" if py_ok else "fail",
        f"Python {platform.python_version()} ({'>= 3.9' if py_ok else 'zu alt, >= 3.9 noetig'})")
    add("os", "ok", f"{platform.system()} {platform.release()} ({platform.machine()})")

    st = assess_setup(interface_map() if ifmap is None else ifmap)
    s1, s2 = st["s1"], st["s2"]
    if s1 and not s2:
        setup = "S1"
        note = "" if any(e["address"] == "192.168.33.10" for e in s1) else \
            " (abweichend von der Vorgabe 192.168.33.10)"
        add("setup", "ok", f"S1 aktiv: {_describe(s1)}{note}")
    elif s2 and not s1:
        setup = "S2"
        add("setup", "ok", "S2 aktiv: " + ", ".join(f"{e['address']} ({e['kind']})" for e in s2))
    elif not s1:
        setup = None
        add("setup", "warn", "Weder S1 (192.168.33.10) noch eine S2-Freigabeadresse lokal "
            "konfiguriert - siehe Netz-Setup.")
    else:
        setup = "S1+S2"
        if st["same_segment"]:
            add("setup", "warn", f"S1-Netz ({_describe(s1)}) und Internetfreigabe ({_describe(s2)}) "
                "im selben Ethernet-Segment: zwei IPv4-Subnetze auf einem Kabel. Das Board "
                "bekaeme per DHCP eine Adresse der Freigabe, und Broadcasts/ARP beider Netze "
                "mischen sich (vgl. Versuch 05) - fuer S1 die Freigabe abschalten, fuer S2 die "
                "S1-Adresse entfernen.")
        elif st["same_segment"] is False:
            add("setup", "warn", f"S1 ({_describe(s1)}) und Internetfreigabe ({_describe(s2)}) auf "
                "verschiedenen Adaptern - pruefen, an welchem das Board haengt.")
        else:
            add("setup", "warn", f"S1 ({_describe(s1)}) und Internetfreigabe ({_describe(s2)}) "
                "gleichzeitig konfiguriert; ob im selben Segment, liess sich nicht ermitteln.")

    target = board or (DEFAULT_BOARD if s1 else None)
    if target:
        src = source_address_for(target)
        expected = {e["address"] for e in s1 + s2}
        same_net = src is not None and ipaddress.ip_address(src) in \
            ipaddress.ip_network(f"{target}/24", strict=False)
        if src is None:
            add("route", "fail", f"Keine Route zu {target}.")
        elif expected and src not in expected and not same_net:
            add("route", "warn", f"{target} wuerde ueber {src} erreicht, nicht ueber die "
                f"Board-Adresse ({', '.join(sorted(expected))}) - falsche Schnittstelle?")
        else:
            add("route", "ok", f"{target} wird ueber lokale Adresse {src} erreicht.")
        tel = _tcp_reachable(target, TELNET_PORT, timeout)
        if tel["ok"]:
            add("board", "ok", f"Telnet {target}:{TELNET_PORT} erreichbar "
                f"(Verbindungsaufbau {tel['connect_ms']:.2f} ms).")
        else:
            add("board", "fail", f"Telnet {target}:{TELNET_PORT} nicht erreichbar: {tel['error']}")
    else:
        add("board", "skip", "Keine Board-Adresse bekannt (in S2 mit --board angeben).")

    ws = _find_wireshark()
    add("wireshark", "ok" if ws else "warn", ws or "Wireshark nicht gefunden - siehe Netz-Setup.")
    ok = all(c["status"] != "fail" for c in checks)
    return {"ok": ok, "setup": setup, "board": target, "same_segment": st["same_segment"],
            "checks": checks}


def cmd_check(args: argparse.Namespace) -> Dict[str, Any]:
    return run_check(args.board, args.timeout)


def format_check(r: Dict[str, Any]) -> str:
    marks = {"ok": "OK  ", "warn": "WARN", "fail": "FAIL", "skip": "--  "}
    return "\n".join(f"[{marks[c['status']]}] {c['name']:<10} {c['detail']}" for c in r["checks"])


# ---------------------------------------------------------------------------
# Kommandozeile
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    # SUPPRESS: ein --json vor dem Unterbefehl wird nicht ueberschrieben.
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="Ergebnis als JSON ausgeben")

    p = argparse.ArgumentParser(prog="rnlab.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--json", action="store_true", help="Ergebnis als JSON ausgeben")
    p.add_argument("--version", action="version", version=f"rnlab {__version__}")
    sub = p.add_subparsers(dest="command", metavar="BEFEHL")
    sub.required = True

    s = sub.add_parser("ping", parents=[common], help="ICMP-Echo mit RTT-Statistik")
    s.add_argument("host")
    s.add_argument("-c", "--count", type=int, default=10, help="Anzahl Echo-Requests (10)")
    # Immer explizit uebergeben: die Systeme haben verschiedene Standards (Unix 56 B,
    # Windows-ping und ICMP-API 32 B) - Reihen waeren sonst nicht vergleichbar.
    s.add_argument("-s", "--size", type=int, default=PING_DEFAULT_SIZE,
                   help=f"ICMP-Nutzdaten in Byte ({PING_DEFAULT_SIZE}, auf allen Systemen gleich)")
    s.add_argument("-i", "--interval", type=float,
                   help="Sendeabstand in s (Windows nur mit --engine api, dem Standard)")
    s.add_argument("-W", "--timeout", type=float, help="Wartezeit je Antwort in s")
    s.add_argument("--df", action="store_true", help="Don't-Fragment-Bit setzen")
    s.add_argument("--hist", type=float, metavar="MS", help="Histogramm mit Klassenbreite MS ausgeben")
    s.add_argument("--engine", choices=["auto", "system", "api"], default="auto",
                   help="system = ping des Betriebssystems; api = Windows-ICMP-API mit "
                        "us-Aufloesung (Standard unter Windows)")
    s.add_argument("--raw", action="store_true", help="Originalausgabe von ping mit ausgeben")
    s.set_defaults(func=cmd_ping, fmt=format_ping)

    s = sub.add_parser("udp-send", parents=[common], help="UDP-Datagramme mit Sequenznummer senden")
    s.add_argument("host")
    s.add_argument("port", type=int)
    s.add_argument("-n", "--count", type=int, default=100, help="Anzahl Datagramme (100)")
    s.add_argument("--size", type=int, default=64, help="Nutzdaten je Datagramm in Byte (64, min. 12)")
    s.add_argument("--rate", type=float, default=100.0, help="Datagramme/s, 0 = unbegrenzt (100)")
    s.add_argument("--burst", type=int, default=1, help="Datagramme je Burst (1)")
    s.set_defaults(func=cmd_udp_send, fmt=format_udp_send)

    s = sub.add_parser("udp-recv", parents=[common], help="UDP-Datagramme empfangen und auswerten")
    s.add_argument("port", type=int)
    s.add_argument("--bind", default="0.0.0.0")
    s.add_argument("-n", "--count", type=int, help="nach N Datagrammen beenden")
    s.add_argument("--idle", type=float, default=3.0, help="Ende nach s Ruhe (3)")
    s.add_argument("--wait", type=float, default=60.0, help="max. Wartezeit auf das erste Datagramm (60)")
    s.add_argument("--expect", type=int, help="gesendete Anzahl (Seq 0..N-1) fuer exakte Verlustrate")
    s.set_defaults(func=cmd_udp_recv, fmt=format_udp_recv)

    s = sub.add_parser("tcp-send", parents=[common], help="TCP-Massendaten senden, Goodput messen")
    s.add_argument("host")
    s.add_argument("port", type=int)
    g = s.add_mutually_exclusive_group()
    g.add_argument("-b", "--bytes", type=int, help="Datenmenge in Byte (Standard 1000000)")
    g.add_argument("-t", "--time", type=float, help="Sendedauer in s")
    s.add_argument("--chunk", type=int, default=1460, help="Bytes je send-Aufruf (1460)")
    s.add_argument("--wait", type=float, default=5.0, help="max. Wartezeit auf FIN der Gegenseite (5)")
    s.set_defaults(func=cmd_tcp_send, fmt=format_tcp_send)

    s = sub.add_parser("tcp-recv", parents=[common], help="eine TCP-Verbindung annehmen und messen")
    s.add_argument("port", type=int)
    s.add_argument("--bind", default="0.0.0.0")
    s.add_argument("--wait", type=float, default=60.0, help="max. Wartezeit auf Verbindung/Daten (60)")
    s.set_defaults(func=cmd_tcp_recv, fmt=format_tcp_recv)

    s = sub.add_parser("iperf2", parents=[common], help="iperf2-TCP-Client (z. B. gegen lwiperf :5001)")
    s.add_argument("host")
    s.add_argument("-p", "--port", type=int, default=IPERF_PORT)
    g = s.add_mutually_exclusive_group()
    g.add_argument("-t", "--time", type=float, default=10.0, help="Dauer in s (10)")
    g.add_argument("-n", "--bytes", type=int, help="Datenmenge in Byte statt Dauer")
    s.add_argument("-l", "--len", type=int, default=8192, help="Blockgroesse in Byte (8192)")
    s.add_argument("-i", "--interval", type=float, help="Zwischenberichte alle s")
    s.set_defaults(func=cmd_iperf2, fmt=format_iperf2)

    s = sub.add_parser("http", parents=[common], help="HTTP-GET mit Zeit- und Byte-Aufschluesselung")
    s.add_argument("url")
    s.add_argument("--http-version", choices=["1.0", "1.1"], default="1.0")
    s.add_argument("-H", "--header", action="append", help="zusaetzliche Kopfzeile 'Name: Wert'")
    s.add_argument("--body", action="store_true", help="Body mit ausgeben")
    s.add_argument("--timeout", type=float, default=10.0)
    s.set_defaults(func=cmd_http, fmt=format_http)

    s = sub.add_parser("lab", aliases=["telnet"], parents=[common],
                       help="lab-Befehle per Telnet (:4242) auf dem Board ausfuehren")
    s.add_argument("host")
    s.add_argument("commands", nargs="*", metavar="BEFEHL",
                   help='z. B. "lab info"; ohne Befehl interaktiv')
    s.add_argument("-p", "--port", type=int, default=TELNET_PORT)
    s.add_argument("--prompt", default=BOARD_PROMPT,
                   help='Prompt der Board-CLI, beendet das Lesen sofort ("> "; "" = nur Ruhezeit)')
    s.add_argument("--idle", type=float, default=BOARD_IDLE,
                   help=f"Ausgabe gilt nach s Ruhe als fertig ({BOARD_IDLE})")
    # Hoch, weil Board-Befehle (z. B. Messreihen) laenger laufen duerfen, solange
    # sie mindestens alle 400 ms etwas ausgeben; das Ende erkennt der Prompt.
    s.add_argument("--overall", type=float, default=30.0, help="max. Wartezeit je Befehl in s (30)")
    s.add_argument("--retry", type=int, default=0,
                   help="bei belegtem Board bis zu N weitere Versuche mit wachsender Pause (0)")
    s.set_defaults(func=cmd_telnet, fmt=format_telnet)

    s = sub.add_parser("check", parents=[common], help="Umgebung pruefen (Python, Setup, Board)")
    s.add_argument("--board", help=f"Board-Adresse (in S1 Standard {DEFAULT_BOARD})")
    s.add_argument("--timeout", type=float, default=2.0)
    s.set_defaults(func=cmd_check, fmt=format_check)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = args.func(args)
    except BoardBusy as exc:
        if args.json:
            print(json.dumps({"error": str(exc), "busy": True}, ensure_ascii=False))
        else:
            print(f"Board belegt: {exc}", file=sys.stderr)
        return 3
    except RnlabError as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        else:
            print(f"Fehler: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        else:
            print(f"Netzwerkfehler: {exc}", file=sys.stderr)
        return 1
    if result is None:
        return 0
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(args.fmt(result))
    if args.command == "check" and not result["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
