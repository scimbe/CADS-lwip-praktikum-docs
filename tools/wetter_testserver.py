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
"""wetter_testserver.py - lokaler Ersatz fuer die Wetter-API (Versuche 10/11).

Antwortet wie ``api.open-meteo.com`` (aufgezeichnet am 2026-09-28), aber auf
dem eigenen Rechner - fuer Tests ohne Internet, ohne DNS und mit gezielt
eingebauten Fehlern. Nur Python-Standardbibliothek, macOS/Linux/Windows,
keine Administratorrechte (Port >= 1024).

Verhalten wie das Original:
  * Anfrage HTTP/1.0 -> Body ohne Content-Length, Ende = Verbindungsabbau
  * Anfrage HTTP/1.1 -> Transfer-Encoding: chunked, danach Verbindungsabbau
  * Statuszeile immer "HTTP/1.1 200 OK"

Beispiele:
    python3 wetter_testserver.py --bind 192.168.33.1 --port 8080
    python3 wetter_testserver.py --port 8080 --vary          # Werte aendern sich
    python3 wetter_testserver.py --port 8080 --fault 500     # Fehlerfall testen
    python3 wetter_testserver.py --port 8080 --chunk 100     # mehrere Chunks

Board: ``lab 10 get 192.168.33.1:8080`` (Pfad ist der Default des Boards).
Rechner: ``curl -0 -v http://192.168.33.1:8080/v1/forecast``.
"""

from __future__ import annotations

import argparse
import json
import socket
import socketserver
import struct
import sys
import threading
import time
from email.utils import formatdate
from typing import Any, Dict, List, Optional

__version__ = "1.0"

# Aufgezeichnete Antwort (Koordinaten des Beispielstandorts, 2026-09-28).
RECORDED: Dict[str, Any] = {
    "latitude": 53.54, "longitude": 10.0, "generationtime_ms": 0.10251998901367188,
    "utc_offset_seconds": 0, "timezone": "GMT", "timezone_abbreviation": "GMT",
    "elevation": 13.0,
    "current_units": {"time": "iso8601", "interval": "seconds", "temperature_2m": "°C",
                      "relative_humidity_2m": "%", "wind_speed_10m": "km/h",
                      "weather_code": "wmo code"},
    "current": {"time": "2026-09-28T12:30", "interval": 900, "temperature_2m": 23.2,
                "relative_humidity_2m": 54, "wind_speed_10m": 4.1, "weather_code": 3},
}

FAULTS = ("none", "404", "500", "garbage", "truncate", "nojson", "slow", "reset", "silent")


def body_for(request_no: int, vary: bool, base: Optional[Dict[str, Any]] = None) -> bytes:
    """JSON-Body wie open-meteo (kompakt, UTF-8). Mit ``vary`` aendern sich die
    Werte je Anfrage deterministisch, damit eine Anzeige etwas zu tun hat."""
    data = json.loads(json.dumps(base or RECORDED))
    if vary:
        cur = data["current"]
        cur["temperature_2m"] = round(cur["temperature_2m"] + ((request_no % 7) - 3) * 0.4, 1)
        cur["relative_humidity_2m"] = int(cur["relative_humidity_2m"] + (request_no % 5) * 2)
        cur["wind_speed_10m"] = round(cur["wind_speed_10m"] + (request_no % 4) * 1.3, 1)
        cur["weather_code"] = [0, 1, 2, 3, 45, 61, 71, 95][request_no % 8]
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def chunked(payload: bytes, size: int) -> bytes:
    """Transfer-Encoding: chunked; size <= 0 -> ein einziger Chunk (wie das Original)."""
    size = len(payload) if size <= 0 else size
    out = bytearray()
    for pos in range(0, len(payload), max(size, 1)):
        piece = payload[pos:pos + size]
        out += b"%x\r\n" % len(piece) + piece + b"\r\n"
    out += b"0\r\n\r\n"
    return bytes(out)


def build_response(request_line: str, request_no: int, vary: bool = False, fault: str = "none",
                   chunk: int = 0) -> bytes:
    """Die komplette Antwort als Bytes (fuer ``slow``/``reset``/``silent`` nur der normale Teil)."""
    parts = request_line.split()
    version = parts[2] if len(parts) == 3 else "HTTP/1.0"
    path = parts[1] if len(parts) >= 2 else "/"
    date = formatdate(usegmt=True)

    if fault == "garbage":
        return b"SSH-2.0-nicht-http\r\n"
    if fault in ("404", "500") or not path.startswith("/v1/forecast"):
        code = fault if fault in ("404", "500") else "404"
        reason = {"404": "Not Found", "500": "Internal Server Error"}[code]
        payload = json.dumps({"error": True, "reason": reason}).encode()
        head = (f"HTTP/1.1 {code} {reason}\r\nDate: {date}\r\n"
                f"Content-Type: application/json; charset=utf-8\r\n"
                f"Content-Length: {len(payload)}\r\nConnection: close\r\n\r\n")
        return head.encode("ascii") + payload

    payload = body_for(request_no, vary)
    if fault == "nojson":
        payload = b'{"current":{"time":"2026-09-28T12:30","interval":900}}'
    head = f"HTTP/1.1 200 OK\r\nDate: {date}\r\nContent-Type: application/json; charset=utf-8\r\n"
    if version == "HTTP/1.1":
        wire = (head + "Transfer-Encoding: chunked\r\nConnection: close\r\n\r\n").encode("ascii")
        wire += chunked(payload, chunk)
    else:
        wire = (head + "Connection: close\r\n\r\n").encode("ascii") + payload
    if fault == "truncate":
        # Mitten im JSON abbrechen; bei chunked fehlt ausserdem der 0-Chunk.
        wire = wire[:len(wire) - len(payload) // 2]
    return wire


class _Handler(socketserver.BaseRequestHandler):
    server: "WetterServer"

    def handle(self) -> None:
        srv = self.server
        sock: socket.socket = self.request
        sock.settimeout(10.0)
        t0 = time.perf_counter()
        raw = b""
        try:
            while b"\r\n\r\n" not in raw and b"\n\n" not in raw and len(raw) < 8192:
                data = sock.recv(4096)
                if not data:
                    break
                raw += data
        except (socket.timeout, OSError):
            pass
        head = raw.split(b"\n", 1)[0].decode("latin-1").strip()
        with srv.lock:
            srv.count += 1
            no = srv.count
        fault = srv.fault
        entry = {"no": no, "client": f"{self.client_address[0]}:{self.client_address[1]}",
                 "request_line": head, "request_bytes": len(raw), "fault": fault}
        if fault == "silent":
            time.sleep(srv.delay or 15.0)  # nie antworten: Timeout beim Client
            entry["response_bytes"] = 0
        elif fault == "reset":
            # SO_LINGER mit Zeit 0: close() sendet RST statt FIN.
            fmt = "HH" if sys.platform == "win32" else "ii"
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack(fmt, 1, 0))
            # Selbst schliessen: socketserver ruft sonst erst shutdown(SHUT_WR)
            # auf, und dann kommt beim Client ein FIN vor dem RST an.
            sock.close()
            entry["response_bytes"] = 0
        else:
            wire = build_response(head, no, srv.vary, fault, srv.chunk)
            if fault == "slow" or srv.delay:
                time.sleep(srv.delay or 3.0)
            try:
                sock.sendall(wire)
            except OSError:
                pass
            entry["response_bytes"] = len(wire)
        entry["ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
        srv.log(entry)


class WetterServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, bind: str, port: int, vary: bool = False, fault: str = "none",
                 chunk: int = 0, delay: float = 0.0, quiet: bool = False,
                 as_json: bool = False) -> None:
        super().__init__((bind, port), _Handler)
        self.vary, self.fault, self.chunk, self.delay = vary, fault, chunk, delay
        self.quiet, self.as_json = quiet, as_json
        self.count = 0
        self.lock = threading.Lock()
        self.entries: List[Dict[str, Any]] = []

    def log(self, entry: Dict[str, Any]) -> None:
        self.entries.append(entry)
        if self.quiet:
            return
        if self.as_json:
            print(json.dumps(entry), flush=True)
        else:
            print(f"#{entry['no']} {entry['client']} \"{entry['request_line']}\" "
                  f"-> {entry['response_bytes']} B ({entry['fault']}, {entry['ms']} ms)", flush=True)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=__doc__.split("\n\n", 1)[1])
    p.add_argument("--bind", default="0.0.0.0",
                   help="Adresse, z. B. die eigene im Board-Netz (Default: alle)")
    p.add_argument("--port", type=int, default=8080, help="TCP-Port (Default 8080, >= 1024)")
    p.add_argument("--vary", action="store_true", help="Werte je Anfrage aendern")
    p.add_argument("--fault", choices=FAULTS, default="none",
                   help="Fehler einbauen: 404/500 Status, garbage kein HTTP, truncate abgeschnitten, "
                        "nojson Werte fehlen, slow verzoegert, reset RST, silent keine Antwort")
    p.add_argument("--chunk", type=int, default=0,
                   help="bei HTTP/1.1: Chunk-Groesse in Byte (Default: ein Chunk wie das Original)")
    p.add_argument("--delay", type=float, default=0.0, help="Sekunden bis zur Antwort")
    p.add_argument("--json", action="store_true", help="eine JSON-Zeile je Anfrage")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = p.parse_args(argv)

    try:
        srv = WetterServer(args.bind, args.port, args.vary, args.fault, args.chunk, args.delay,
                           as_json=args.json)
    except OSError as exc:
        print(f"Fehler: {args.bind}:{args.port} nicht belegbar ({exc}). Adresse im Board-Netz "
              f"konfiguriert? Port frei?", file=sys.stderr)
        return 2
    host, port = srv.server_address[:2]
    print(f"Wetter-Testserver auf http://{host}:{port}/v1/forecast "
          f"(fault={args.fault}, vary={args.vary}) - Ende mit Strg+C", file=sys.stderr, flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
