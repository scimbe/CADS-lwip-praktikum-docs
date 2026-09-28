# 09 · Congestion Control

<a class="md-button" href="../../pdf/09-congestion-control.pdf">:material-file-pdf-box: Als PDF herunterladen</a>

!!! info "Termin T10 · Setup S1"
    Dieser Versuch läuft im Netz-Setup **S1 – statische Adresse**
    (siehe [Netz-Setup](../reference/netz-setup.md#s1-statische-adresse)).

--8<-- "konventionen.md"

In Versuch 08 hat sich der Empfänger geschützt. Jetzt geht es um das Netz:
Ein TCP-Sender weiß nicht, wie viel die Strecke verkraftet, und tastet sich
deshalb heran – schnell wachsen, bei Verlust halbieren, langsam wieder wachsen.
Das Ergebnis ist der berühmte **Sägezahn** des Überlastfensters `cwnd`. Hier
sendet das Board, ihr lasst gezielt Segmente verschwinden und schaut lwIP
dabei in die Karten: Jedes ACK landet mit `cwnd`, `ssthresh` und
Empfangsfenster in einer Trace, daneben die `cwnd` eures eigenen Reno-Modells,
das dieselben Ereignisse sieht. Am Ende vergleicht ihr den Durchsatz mit der
Mathis-Formel – und seht, wann sie versagt.

## Lernziele

Nach dem Versuch könnt ihr …

- Überlastkontrolle („Schutz des Netzes“) von Flusskontrolle abgrenzen und das
  Sendefenster als min(cwnd, rwnd) erklären,
- Slow Start, Congestion Avoidance, Fast Retransmit und Fast Recovery (Reno,
  RFC 5681) als Zustandsautomat implementieren und an einer echten Trace
  wiedererkennen,
- begründen, warum AIMD einen Sägezahn erzeugt und wie groß er wird,
- den Durchsatz mit der Mathis-Formel ≈ (MSS/RTT) · 1,22/√*p* vorhersagen und
  die Annahmen benennen, unter denen sie gilt,
- den Unterschied zwischen einem Verlust, den Fast Retransmit repariert, und
  einem Retransmission Timeout am Durchsatz ablesen.

## Theorie-Bezug (Skript 5.31)

- **Feedback über ACKs:** Ein ACK heißt „keine Überlast“, das Fenster darf
  wachsen; ein fehlendes ACK (Timeout) oder drei **doppelte ACKs** gelten als
  Verlust und damit als Überlastsignal.
- **AIMD:** additiver Anstieg, multiplikativer Abfall. Nur diese Kombination
  führt mehrere Verbindungen zu einer fairen Aufteilung (Fairness-Index) – bei
  ähnlicher RTT.
- **Slow Start:** `cwnd` wächst je ACK um eine MSS, also Verdopplung pro RTT,
  bis zum **Slow Start Threshold** `ssthresh`. Danach **Congestion
  Avoidance:** etwa eine MSS pro RTT.
- **Fast Retransmit:** Nach drei doppelten ACKs wird das fehlende Segment
  sofort wiederholt, ohne auf den Timeout zu warten. **Fast Recovery**
  (RFC 2581/5681): `ssthresh` = halbes Fenster, `cwnd` = `ssthresh` + 3·MSS;
  jedes weitere doppelte ACK bläht `cwnd` um eine MSS auf, das nächste neue
  ACK setzt `cwnd` = `ssthresh`. Ergebnis: der Sägezahn.
- **RTO:** Der Retransmission Timeout aus der gemessenen RTT. Zu kurz →
  unnötige Wiederholungen, zu lang → Leerlauf. Nach einem Timeout beginnt
  `cwnd` wieder bei einer MSS.
- **MSS** = MTU − IP- und TCP-Header: bei Ethernet 1500 − 40 = **1460 B**.
  Das **Initial Window** ist die Datenmenge, mit der eine Verbindung startet.
- **SACK** verbessert Fast Recovery bei mehreren Verlusten pro Fenster. lwIP
  wertet als Sender keine SACK-Blöcke aus (es kann sie als Empfänger nur
  optional erzeugen, `LWIP_TCP_SACK_OUT`, hier aus) – das wird hier
  sichtbar. Reno und Cubic sind Varianten.

## Versuchsaufbau

```
 Rechner 192.168.33.10/24  ── Ethernet 100 Mbit/s, direkt ──  ITS-Board 192.168.33.99/24
 rnlab.py tcp-recv :7009 (Empfänger)                          TCP-Sender, Verlust vor dem MAC
 Wireshark                                                     Trace: ein Eintrag je ACK
```

- Setup **S1**. Diesmal **sendet das Board** – nur beim Sender sieht man
  `cwnd`. Empfänger ist [`rnlab.py tcp-recv`](../reference/rnlab-tool.md#tcp-send-tcp-recv)
  auf eurem Rechner. Die Firewall des Rechners muss eingehendes TCP auf Port
  7009 zulassen.
- **Verlust** entsteht im Board: Ein Treiber-Hook verwirft ausgewählte
  Datensegmente, **nachdem** lwIP sie „gesendet“ hat, aber bevor sie den
  Controller erreichen – für lwIP genau wie ein Verlust auf der Strecke.
- **Build für diesen Versuch:** MSS 1460 (Ethernet), großer Sendepuffer
  (8 Segmente), kleines Empfangsfenster (das Board empfängt hier nur ACKs):

    ```bash
    bash scripts/build.sh Debug -DCADS_RNLAB_TCP_MSS=1460 -DCADS_RNLAB_TCP_WND_MSS=4 -DCADS_RNLAB_TCP_SND_BUF_MSS=8 -DCADS_RNLAB_ETH_RX_COUNT=8
    ```

    Alle vier Optionen angeben: Der Build-Ordner merkt sich Werte aus Versuch 08
    (z. B. einen tieferen Ring), die sonst die Messung verändern. Danach wieder
    auf die Standardwerte zurücksetzen (`-DCADS_RNLAB_TCP_MSS=536
    -DCADS_RNLAB_TCP_WND_MSS=8 -DCADS_RNLAB_TCP_SND_BUF_MSS=4
    -DCADS_RNLAB_ETH_RX_COUNT=8`). Das Board empfängt hier nur ACKs, ein
    größeres Empfangsfenster bringt nichts.

| Befehl | Wirkung |
|---|---|
| `lab 09 loss <n>` | jedes *n*-te Datensegment verwerfen (*p* = 1/*n*) |
| `lab 09 loss p <prozent>` | jedes Datensegment mit Wahrscheinlichkeit *p* verwerfen, z. B. `p 2.5` |
| `lab 09 loss off` | kein künstlicher Verlust |
| `lab 09 cc start <ip> <port> [bytes]` | Verbindung zu `tcp-recv` aufbauen und `bytes` Nullen senden (300 000) |
| `lab 09 cc stop` | abbrechen |
| `lab 09 status` | Fortschritt, Goodput, RTT (min/avg/max), neue und doppelte ACKs, Fast Retransmits, Timeouts, verworfene Segmente, Trace-Füllstand |
| `lab 09 trace [ab]` | Trace als CSV, 25 Zeilen je Aufruf; die letzte Zeile nennt den nächsten Aufruf |
| `lab 09 calc [rtt_us]` | Mathis-Schätzung (eure Funktion) für die eingestellte Verlustrate und die gemessene (oder angegebene) RTT |

**Die Trace.** Eine Zeile je ACK (`A` neu, `D` doppelt) mit dem Zustand
**nach** dessen Verarbeitung durch lwIP, dazu Zeilen für verworfene Segmente
(`X`, Spalte `acked` = Position des Segments), Fast Retransmits (`F`) und
Timeouts (`R`). Spalten:

| Spalte | Bedeutung |
|---|---|
| `t_ms` | Zeit seit Verbindungsaufbau |
| `acked` | bis hier bestätigte Byte |
| `cwnd`, `ssthresh` | lwIPs Überlastfenster und Schwelle (Byte) |
| `snd_wnd` | Empfangsfenster des Rechners (unskaliert, daher meist 65535) |
| `flight` | unbestätigt unterwegs (`snd_nxt − snd_una`) |
| `rtt_us` | RTT-Probe, die dieses ACK abgeschlossen hat (sonst 0) |
| `model_cwnd` | `cwnd` **eures** Reno-Modells nach demselben Ereignis |
| `event`, `phase` | Ereignis; Phase aus lwIPs Werten: `S` Slow Start, `C` Congestion Avoidance, `F` Fast Recovery |

!!! info "Werkzeug: tools/l09_plot.py – Trace holen, speichern, zeichnen"
    `lab 09 trace` liefert die Trace seitenweise. `tools/l09_plot.py` holt alle
    Seiten über `tools/rnlab.py`, schreibt eine CSV-Datei und zeichnet `cwnd`,
    `ssthresh`, `model_cwnd` und `flight` über der Zeit, mit Markern für
    verworfene Segmente, Fast Retransmits und Timeouts:

    ```bash
    python3 tools/l09_plot.py 192.168.33.99 n20      # -> n20.csv (+ n20.png)
    python3 tools/l09_plot.py --csv n20.csv          # vorhandene CSV nur zeichnen
    ```

    Windows: `py tools\l09_plot.py …`. Das Bild entsteht nur mit `matplotlib`
    (`python3 -m pip install matplotlib`). Ohne öffnet ihr die CSV in einer
    Tabellenkalkulation (LibreOffice, Excel, Numbers) und zeichnet die Spalten
    als Linien über `t_ms`.

## Versuchsablauf

!!! info "Zeitplan: rund 3 Stunden Pflicht"
    **Pflicht:** Firmware-Aufgabe, Erwartungswerte, Versuche A, B und C (für C
    reichen *p* = 1 %, 2 % und 5 %), Auswertung 1, 2, 4 und 5.
    **Vertiefung:** das Timeout-Bild mit *p* = 3 %, Versuch D (natürliche
    Verluste), Auswertung 3, 6 und 7 und der NewReno-Kasten.

1. Firmware-Aufgabe umsetzen, Host-Tests grün, **Build für diesen Versuch**
   (siehe oben) flashen.
2. **Erwartungswerte** notieren (nächster Abschnitt).
3. **A – ohne Verlust:** 300 000 Byte, danach Status und Trace.

    ```bash
    python3 tools/rnlab.py tcp-recv 7009 &
    python3 tools/rnlab.py lab 192.168.33.99 "lab 09 loss off" "lab 09 cc start 192.168.33.10 7009"
    wait
    python3 tools/rnlab.py lab 192.168.33.99 "lab 09 status"
    python3 tools/l09_plot.py 192.168.33.99 ohne-verlust
    ```

    Windows: `py tools\rnlab.py …` statt `python3 tools/rnlab.py …`.

    Unter Windows (PowerShell) startet ihr `tcp-recv` in einem zweiten
    Terminal. Läuft die Verbindung nicht an, blockiert die Firewall Port 7009.
4. **B – regelmäßiger Verlust:** dasselbe mit `lab 09 loss 50`, `20` und `10`;
   nach jedem Lauf `status`, `calc` und die Trace (`python3 tools/l09_plot.py 192.168.33.99 n20` usw.).
5. **C – zufälliger Verlust:** `lab 09 loss p 1`, `p 2` und `p 5`, jeweils
   **2 000 000 Byte** (`… 7009 2000000`), `status` und `calc`. Die Trace fasst
   320 Einträge und ist bei diesen Läufen voll. Vertiefung: für ein Bild eines
   Timeouts `p 3` mit 200 000 Byte und die Trace dazu.
6. **D – natürliche Verluste (Vertiefung):** ohne künstlichen Verlust 4 MB senden, einmal
   ungestört und einmal mit Display-Last aus Versuch 07 mitten im Transfer:

    ```bash
    python3 tools/rnlab.py tcp-recv 7009 &
    python3 tools/rnlab.py lab 192.168.33.99 "lab 09 loss off" "lab 09 cc start 192.168.33.10 7009 4000000"
    python3 tools/rnlab.py lab 192.168.33.99 "lab 07 blit 1000"; wait
    python3 tools/rnlab.py lab 192.168.33.99 "lab 09 status" "lab info"
    ```

    Eine zweite natürliche Überlast habt ihr in Versuch 08 gesehen: Ist das
    Fenster größer als der Empfangsring, verwirft die Netzwerkkarte des
    Empfängers – dort reagiert die Überlastkontrolle des **Rechners**, die ihr
    im Mitschnitt (doppelte ACKs, Fast Retransmission) beobachten könnt.
7. In Wireshark (Filter `tcp.port == 7009`): `tcp.analysis.duplicate_ack`,
   `tcp.analysis.fast_retransmission`, `tcp.analysis.retransmission`; unter
   *Statistiken → TCP-Stream-Graphen → Zeit/Sequenz (Stevens)* seht ihr
   Lücken und Wiederholungen.

## Erwartungswert (vor der Messung notieren!)

**1. Start.** Sucht in lwIP (`lib/lwip/src/core/tcp.c`, Funktion
`tcp_alloc()`, und `tcp_in.c`, `LWIP_TCP_CALC_INITIAL_CWND`) die Startwerte
von `cwnd` und `ssthresh` für diesen Build. Wie viele ACKs dauert der Slow
Start, wenn jedes ACK eine MSS bestätigt?

**2. Ohne Verlust.** Unterwegs sein können höchstens `TCP_SND_BUF` = 8 MSS.
Das Board pollt alle *T* ≈ 10 ms und sieht ACKs nur dann. Welcher Goodput
ergibt sich, wenn pro Poll ein Sendepuffer voll hinausgeht?

**3. Sägezahn.** Mit „jedes *n*-te Segment“ geht pro Zyklus genau ein Segment
verloren. In Congestion Avoidance wächst `cwnd` von *W*/2 auf *W* in *W*/2
Round-Trips und überträgt dabei ≈ (3/8)·*W*² Segmente. Setzt das gleich *n*:
Wie groß wird *W* (in MSS) für *n* = 10, 20, 50? Wo greift stattdessen die
Grenze aus 2.?

**4. Mathis.** Mittleres Fenster ≈ ¾·*W* ergibt
Durchsatz ≈ (MSS/RTT) · √(3/(2*p*)) ≈ (MSS/RTT) · 1,22/√*p*. Rechnet mit
RTT = *T* für *p* = 1/10, 1/20, 1/50 und 1 %, 2 %, 3 %, 5 %. Welche
Annahmen stecken in der Formel (Verlustmuster, Timeouts, Fenstergrenzen)?

**5. Timeout.** lwIP rechnet Timer in Schritten von `TCP_SLOW_INTERVAL`
(`lib/lwip/src/include/lwip/priv/tcp_priv.h`). Wie lang wird ein RTO
mindestens, wenn die gemessene RTT weit unter einem Schritt liegt? Was kostet
ein einziger Timeout im Vergleich zu einem Fast Retransmit? Wann kommt es trotz
Fast Retransmit zum Timeout (lwIP wertet als Sender weder SACK aus noch
kennt es NewReno)?

**6. Display.** Während eines Blits ist der Empfänger des Boards taub
(Versuch 07). Das Board sendet hier aber – was geht dann verloren, und wie
reagiert TCP, wenn für ≈ 1 s kein ACK ankommt? Welche Zähler des Boards
steigen?

## Experiment (Firmware-Aufgabe)

Dateien in eurem Fork (Branch `praktikum/start`):

- [`apps/rnlab/src/l09_congestion_control_logic.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/l09_congestion_control_logic.c)
  mit [`l09_congestion_control_logic.h`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/l09_congestion_control_logic.h):
  **hier arbeitet ihr** (`TODO(L09)`).
- [`apps/rnlab/src/l09_congestion_control.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/l09_congestion_control.c):
  Sender, Treiber-Hooks (`rnlab_l09_hook_rx_frame`, `…_tx_frame`,
  `…_tx_drop`), Trace und Befehle, fertig. Der Kopfkommentar erklärt, wie die
  Trace den Zustand *nach* jedem ACK erfasst, ohne lwIP zu verändern.
- [`tests/unit/test_rnlab_l09.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/tests/unit/test_rnlab_l09.c):
  die Spezifikation (35 Tests, u. a. mit den Zahlen aus dem Skript).

| Funktion | Aufgabe |
|---|---|
| `void rnlab_reno_on_ack(rnlab_reno_t* r, uint32_t acked)` | neues ACK: Fast Recovery beenden (`cwnd = ssthresh`) oder Slow Start (+min(acked, MSS)) bzw. Congestion Avoidance (+MSS²/cwnd, mindestens 1 B) |
| `void rnlab_reno_on_dupack(rnlab_reno_t* r, uint32_t flight)` | doppeltes ACK: beim dritten `ssthresh = max(flight/2, 2·MSS)`, `cwnd = ssthresh + 3·MSS`, Fast Recovery; danach je +MSS |
| `void rnlab_reno_on_timeout(rnlab_reno_t* r, uint32_t flight)` | `ssthresh = max(flight/2, 2·MSS)`, `cwnd = MSS` |
| `rnlab_l09_phase_t rnlab_l09_phase(cwnd, ssthresh, in_fr)` | `FR`, sonst `SS` bei `cwnd < ssthresh`, sonst `CA` |
| `uint64_t rnlab_l09_mathis_bps(uint32_t mss, uint32_t rtt_us, uint32_t p_ppm)` | Mathis in bit/s, **ganzzahlig** (ohne `libm`, mit `rnlab_isqrt64()`); 0 bei RTT oder *p* = 0 |
| `bool rnlab_l09_dropper_decide(rnlab_l09_dropper_t* d)` | jedes *n*-te Segment bzw. mit Wahrscheinlichkeit *p* (xorshift32) verwerfen |

**Wie das Modell gefüttert wird.** Der Empfangs-Hook sieht jedes ACK **vor**
lwIP: Bestätigt es neue Daten, ruft er `rnlab_reno_on_ack()` mit der Anzahl
neuer Byte; ist es ein doppeltes ACK (gleiche Nummer, keine Daten, Daten
unterwegs), `rnlab_reno_on_dupack()`. Der Sende-Hook erkennt Wiederholungen;
kommt eine, ohne dass lwIP in Fast Recovery ist, hat der Timer zugeschlagen:
`rnlab_reno_on_timeout()`. Euer Modell sieht also dieselben Ereignisse wie
lwIP – Unterschiede in der Trace kommen aus den **Regeln**, nicht aus den
Eingaben.

```bash
cmake --build build/host && ctest --test-dir build/host -L rnlab-L09 --output-on-failure
```

Ohne Implementierung bleibt `model_cwnd` konstant, die Phase ist `?`,
`lab 09 loss` verwirft nichts und `lab 09 calc` meldet 0.

??? example "Vertiefung (optional): Ein Timeout pro Fenster verhindern"
    NewReno (RFC 6582) bleibt nach einem „partiellen ACK“ – es bestätigt neue
    Daten, aber nicht alles bis zum Stand beim dritten doppelten ACK – in Fast
    Recovery und wiederholt sofort das nächste fehlende Segment. Erweitert
    euer Modell um diese Regel (ihr braucht den Stand `recover`). Wie viele der
    Timeouts aus Versuch C hätte NewReno vermieden? Zählt dazu in der Trace
    die Fälle, in denen auf ein `F` kein zweites `F`, sondern ein `R` folgt.

## Auswertung

1. Zeichnet die Traces aus A und B. Markiert Slow Start, Congestion
   Avoidance, Fast Retransmit/Recovery. Wo steht der Sägezahn, wo klebt
   `cwnd` am Sendepuffer (`flight` = 8 MSS)?
2. Vergleicht an einem Fast Retransmit lwIPs Werte mit dem Skript: Wie groß ist
   `ssthresh` danach, ist `cwnd` = `ssthresh` + 3·MSS? Euer Modell setzt
   `ssthresh` = flight/2, lwIP = min(cwnd, snd_wnd)/2 – wie groß ist der
   Unterschied in eurer Trace, und welche Regel hat die RFC?
3. Wo weichen `cwnd` und `model_cwnd` sonst voneinander ab? Sucht in
   `tcp_in.c` (`tcp_receive`) nach „RFC 3465“: Wie zählt lwIP in Slow Start und
   Congestion Avoidance?
4. Tragt Goodput und Mathis-Schätzung (mit RTT = *T* und mit der gemessenen
   RTT aus `status`) für alle Läufe in eine Tabelle ein. Für welche Läufe passt
   die Formel, für welche nicht – und warum?
5. Versuch C mit *p* = 2 % und 5 %: Wie viele Timeouts meldet `status`?
   Schätzt aus der Laufzeit im Vergleich zum Lauf mit *p* = 1 %, wie lange
   ein Timeout dauert und welcher Anteil der Laufzeit auf Timeouts entfällt.
   (Vertiefung: die Dauer direkt in der Trace des *p*-3-%-Laufs ablesen,
   Abstand vom letzten Ereignis zum `R`.)
6. Warum ist regelmäßiger Verlust („jedes *n*-te“) für TCP so viel harmloser
   als zufälliger mit derselben Rate?
7. Versuch D (Vertiefung): Was ging während der Display-Last verloren, wie
   reagierte der Sender (`status`, Trace), und welcher Zähler des Boards hat es
   bemerkt? Vergleicht mit der natürlichen Überlast am Empfangsring aus
   Versuch 08.

--8<-- "issue-feedback.md"

## Potenzielle Herausforderungen

- **`cc start` hängt bei „verbinde“:** `tcp-recv` läuft nicht oder die
  Firewall des Rechners blockiert Port 7009 (macOS fragt beim ersten Start von
  Python, Windows ebenso; unter Linux `ufw`/`firewalld`).
- **Falsche Ziel-IP:** In S1 hat der Rechner `192.168.33.10`, nicht `.1`.
- **Trace voll:** 320 Einträge reichen für etwa 300 kB. Für Goodput-Messungen
  mit 2 MB ist das egal, der Status zählt weiter.
- **`rnlab.py lab … "lab 09 trace"` zeigt nur einen Teil:** Die Trace kommt
  seitenweise; `tools/l09_plot.py` holt alle Seiten.
- **Modell wächst in Congestion Avoidance nicht:** Ganzzahldivision
  MSS²/cwnd wird bei großem `cwnd` 0 – mindestens 1 Byte addieren.
- **Mathis-Überlauf:** MSS · 8 · 10⁶ · 1 224 745 braucht 64 Bit; erst
  multiplizieren, dann dividieren, sonst verliert ihr die Genauigkeit.
- **Nach `lab 09 loss p …` ist jeder Lauf anders:** Der Zufallsgenerator wird
  aus dem Hardware-RNG gesetzt. Für Vergleiche mehrere Läufe mitteln oder
  „jedes *n*-te“ nehmen.
- **Build vergessen zurückzusetzen:** Versuch 08 und die übrigen erwarten
  wieder die Standardwerte (MSS 536 / WND 8 / SND_BUF 4, RX-Ring 8).

## Quellen

- RN-Skript, Kap. 5.31 (Schutz des Netzes: AIMD, Slow Start, Congestion
  Avoidance, Fast Retransmit/Recovery, RTO, MSS).
- RFC 5681 – TCP Congestion Control; RFC 2581 (Vorgänger); RFC 6582 – NewReno;
  RFC 3390 – Initial Window; RFC 3465 – Appropriate Byte Counting;
  RFC 6298 – RTO-Berechnung.
- M. Mathis, J. Semke, J. Mahdavi, T. Ott: *The Macroscopic Behavior of the
  TCP Congestion Avoidance Algorithm.* ACM SIGCOMM CCR 27(3), 1997.
- J. Padhye, V. Firoiu, D. Towsley, J. Kurose: *Modeling TCP Throughput: A
  Simple Model and its Empirical Validation.* SIGCOMM 1998 (mit Timeouts).
- G. Marsaglia: *Xorshift RNGs.* Journal of Statistical Software 8(14), 2003.
- lwIP: `src/core/tcp_in.c` (`tcp_receive`), `src/core/tcp_out.c`
  (`tcp_rexmit_fast`), `src/core/tcp.c` (`tcp_alloc`, `tcp_slowtmr`).
