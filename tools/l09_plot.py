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
"""l09_plot.py - cwnd-Trace aus Versuch 09 vom Board holen, speichern, zeichnen.

Laeuft auf macOS, Linux und Windows mit Python >= 3.9. Holt alle Seiten von
`lab 09 trace` ueber tools/rnlab.py, schreibt eine CSV-Datei und zeichnet sie,
wenn matplotlib installiert ist (sonst nur CSV - die laesst sich in jeder
Tabellenkalkulation als Liniendiagramm ueber t_ms darstellen).

Beispiele (aus dem Wurzelverzeichnis des Doku-Repositorys):
    python3 tools/l09_plot.py 192.168.33.99             # -> trace.csv (+ trace.png)
    python3 tools/l09_plot.py 192.168.33.99 n20         # -> n20.csv (+ n20.png)
    python3 tools/l09_plot.py --csv n20.csv             # nur zeichnen
Windows: py tools\\l09_plot.py ...
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path
from typing import Callable, List, Optional, Tuple

RNLAB = Path(__file__).resolve().with_name("rnlab.py")
HEADER_PREFIX = "t_ms,"
NEXT_PREFIX = "# weiter:"

Rows = List[List[str]]


def parse_page(text: str) -> Tuple[Optional[List[str]], Rows, Optional[int]]:
    """Eine Ausgabe von `lab 09 trace [ab]` zerlegen.

    Liefert (Spaltenkoepfe oder None, Datenzeilen, naechstes `ab` oder None am
    Ende). Befehlsecho ("> lab 09 trace 0"), Prompt und Leerzeilen werden
    ignoriert, ebenso Zeilen mit falscher Spaltenzahl.
    """
    header: Optional[List[str]] = None
    rows: Rows = []
    following: Optional[int] = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith(HEADER_PREFIX):
            header = line.split(",")
        elif line.startswith(NEXT_PREFIX):
            try:
                following = int(line.split()[-1])
            except ValueError:
                following = None
        elif line[:1].isdigit():
            fields = line.split(",")
            if len(fields) == 10:
                rows.append(fields)
    return header, rows, following


def run_rnlab(board: str, command: str) -> str:
    out = subprocess.run([sys.executable, str(RNLAB), "lab", board, "--idle", "1", command],
                         capture_output=True, text=True, check=True)
    return out.stdout


def fetch(board: str, runner: Callable[[str, str], str] = run_rnlab,
          max_pages: int = 100) -> Tuple[Optional[List[str]], Rows]:
    """Alle Seiten holen, bis das Board kein `# weiter:` mehr meldet."""
    header: Optional[List[str]] = None
    rows: Rows = []
    start = 0
    for _ in range(max_pages):
        page_header, page_rows, following = parse_page(runner(board, f"lab 09 trace {start}"))
        header = header or page_header
        rows.extend(page_rows)
        if following is None or following <= start:
            break
        start = following
    return header, rows


def save_csv(path: Path, header: List[str], rows: Rows) -> None:
    with open(path, "w", newline="") as f:
        csv.writer(f).writerows([header] + rows)


def load_csv(path: Path) -> Tuple[List[str], Rows]:
    with open(path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        return header, [r for r in reader if r]


def plot(header: List[str], rows: Rows, png: Path) -> bool:
    """Diagramm schreiben; False, wenn matplotlib fehlt."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    col = {name: i for i, name in enumerate(header)}
    t = [int(r[col["t_ms"]]) for r in rows]

    def series(name: str) -> List[float]:
        return [int(r[col[name]]) / 1000 for r in rows]

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.step(t, series("cwnd"), where="post", label="cwnd (lwIP)", linewidth=1.8)
    ax.step(t, series("ssthresh"), where="post", label="ssthresh (lwIP)", linestyle="--")
    ax.step(t, series("model_cwnd"), where="post", label="cwnd (euer Reno-Modell)", alpha=0.8)
    ax.step(t, series("flight"), where="post", label="unterwegs (flight)", linewidth=0.8, alpha=0.6)
    marks = {"X": ("verworfen", "v"), "F": ("Fast Retransmit", "o"), "R": ("Timeout (RTO)", "s")}
    for event, (label, marker) in marks.items():
        pts = [(ti, int(r[col["cwnd"]]) / 1000) for ti, r in zip(t, rows) if r[col["event"]] == event]
        if pts:
            ax.scatter(*zip(*pts), marker=marker, s=40, label=label, zorder=3)
    ax.set_xlabel("Zeit seit Verbindungsaufbau [ms]")
    ax.set_ylabel("Byte / 1000")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper right", fontsize="small")
    fig.tight_layout()
    fig.savefig(png, dpi=120)
    plt.close(fig)
    return True


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="l09_plot.py", description=__doc__.split("\n\n")[0])
    p.add_argument("board", nargs="?", default="192.168.33.99", help="Board-Adresse (192.168.33.99)")
    p.add_argument("name", nargs="?", default="trace", help="Dateiname ohne Endung (trace)")
    p.add_argument("--csv", type=Path, help="vorhandene CSV zeichnen, Board nicht fragen")
    args = p.parse_args(argv)

    if args.csv:
        path = args.csv
        header, rows = load_csv(path)
    else:
        path = Path(args.name + ".csv")
        header, rows = fetch(args.board)
        if not header or not rows:
            print("keine Trace-Daten - lief 'lab 09 cc start' schon?", file=sys.stderr)
            return 2
        save_csv(path, header, rows)
        print(f"{len(rows)} Zeilen -> {path}")
    png = path.with_suffix(".png")
    if plot(header, rows, png):
        print(f"Diagramm: {png}")
    else:
        print("matplotlib fehlt - nur CSV (python3 -m pip install matplotlib)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
