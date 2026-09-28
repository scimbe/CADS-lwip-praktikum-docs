# 04 · ICMP

<a class="md-button" href="../../pdf/04-icmp.pdf">:material-file-pdf-box: Als PDF herunterladen</a>

!!! info "Termin T05 · Setup S1"
    Dieser Versuch läuft im Netz-Setup **S1 – statische Adresse**
    (siehe [Netz-Setup](../reference/netz-setup.md#s1-statische-adresse)).

--8<-- "konventionen.md"

`ping` ist das erste Werkzeug, zu dem man bei Netzproblemen greift. Dabei
misst es mehr, als man denkt: nicht nur die Leitung, sondern auch, **wann** die
Gegenseite überhaupt dazu kommt zu antworten. In diesem Versuch baut ihr einen
eigenen Echo-Responder in den lwIP-Stack des Boards ein, messt RTT-Verteilungen
von beiden Seiten und findet heraus, woher die mehreren Millisekunden kommen,
die ein 100-Mbit/s-Kabel allein nicht erklärt.

## Lernziele

Nach dem Versuch könnt ihr …

- Aufbau und Prüfsumme (RFC 1071) einer ICMP-Echo-Nachricht erklären und
  selbst berechnen,
- einen ICMP-Responder über lwIPs RAW-API vor den eingebauten Responder
  schalten und das Zusammenspiel (`raw_input` vor `icmp_input`) erklären,
- die RTT auf einer direkten Ethernet-Verbindung aus Serialisierungs- und
  Verarbeitungszeit abschätzen,
- eine gemessene RTT-Verteilung (min/avg/max/stddev, Histogramm) auf ihre
  Ursachen zurückführen, insbesondere die Poll-Schleife eines `NO_SYS`-Systems,
- TTL und `traceroute` auf einer Verbindung ohne Router deuten.

## Theorie-Bezug (Skript 5.16)

- **ICMP** ist ein Dienstprotokoll auf IP-Ebene (Protokollnummer 1) für
  Fehler- und Diagnosemeldungen. **Echo Request** (Typ 8) und **Echo Reply**
  (Typ 0) bilden `ping`; Identifier und Sequenznummer ordnen Antworten den
  Anfragen zu, die Nutzdaten kommen unverändert zurück.
- `traceroute` nutzt das **TTL**-Feld des IPv4-Headers (Skript 5.14): Jeder
  Router verringert es um 1 und meldet bei 0 *Time Exceeded* (Typ 11). Das Ziel
  selbst antwortet mit *Port Unreachable* (Typ 3, Code 3) oder einem Echo Reply.
- Die **Header-Checksumme** (5.14) und die ICMP-Prüfsumme sind dieselbe
  Internet-Prüfsumme: Einerkomplement der Einerkomplement-Summe aller
  16-Bit-Wörter.
- Wie im Skript beschrieben, filtern viele Netze ICMP. Ein fehlender Echo Reply
  beweist deshalb nicht, dass ein Host nicht erreichbar ist. Das spielt ihr
  hier mit `lab 04 loss` nach.

## Versuchsaufbau

```
 Rechner 192.168.33.10/24  ── Ethernet 100 Mbit/s, direkt ──  ITS-Board 192.168.33.99/24
 rnlab.py ping / Wireshark                                    lwIP, NO_SYS=1 (Polling)
```

- Setup **S1**, Wireshark auf der Board-Schnittstelle, Filter `icmp`.
- Befehle an das Board mit [`python3 tools/rnlab.py lab …`](../reference/rnlab-tool.md#lab-telnet)
  (Windows: `py tools\rnlab.py …`). `lab 04 ping` gibt während der Messreihe
  je Anfrage ein Zeichen aus (`.` = Antwort, `x` = nach 400 ms keine),
  danach die Statistik.
- Messungen vom Rechner mit [`python3 tools/rnlab.py ping`](../reference/rnlab-tool.md#ping):
  auf allen Systemen dieselben Optionen, µs-Auflösung, TTL der Antworten,
  Median und Perzentile; `--hist 1` zeichnet ein Histogramm mit 1-ms-Klassen.

## Versuchsablauf

Pflicht sind die Schritte 1–7 (rund 3 Stunden einschließlich der
Firmware-Aufgabe); die Vertiefungen danach sind für alle, die schneller sind.

1. Firmware-Aufgabe umsetzen, Host-Tests grün, flashen.
2. **Erwartungswerte** notieren (nächster Abschnitt).
3. **A – lwIP antwortet** (Board im Menü):

    ```bash
    python3 tools/rnlab.py ping 192.168.33.99 -c 100 -i 0.2 --hist 1   # TTL notieren
    ```

4. **B – euer Responder antwortet:**

    ```bash
    python3 tools/rnlab.py lab 192.168.33.99 "lab 04 echo on"
    python3 tools/rnlab.py ping 192.168.33.99 -c 100 -i 0.2 --hist 1   # TTL jetzt?
    python3 tools/rnlab.py lab 192.168.33.99 "lab 04 stats"
    ```

    In Wireshark: Echo Request und Reply vergleichen (Identifier, Sequenz,
    Daten, Prüfsumme, TTL).
5. **C – das Board pingt:**

    ```bash
    python3 tools/rnlab.py lab 192.168.33.99 "lab 04 ping 192.168.33.10 100 56"
    ```

6. **D – Poll-Intervall verändern:** `lab poll <ms>` (1…10, Standard 10) legt
   fest, wie oft die Menü-Schleife lwIP bedient; `lab 04 pollgap` misst den
   tatsächlichen Abstand. Für 10, 5, 2 und 1 ms jeweils:

    ```bash
    python3 tools/rnlab.py lab 192.168.33.99 "lab poll 5" "lab 04 pollgap 200"
    python3 tools/rnlab.py lab 192.168.33.99 "lab 04 pollgap"          # nach ~3 s
    python3 tools/rnlab.py ping 192.168.33.99 -c 100 -i 0.2
    python3 tools/rnlab.py lab 192.168.33.99 "lab 04 ping 192.168.33.10 100 56"
    ```

    Zum Schluss `lab poll 10`.
7. **E – TTL/traceroute:**

    ```bash
    traceroute -n -q 1 -m 3 192.168.33.99      # Windows: tracert -d -h 3 192.168.33.99
    ```

??? example "Vertiefung (optional): Störungen, große Pakete, ohne Menü"
    - **F – Störungen:** `lab 04 delay 20`, 20 Pings; `lab 04 delay 0`;
      `lab 04 loss 30`, 100 Pings; `lab 04 loss 0`. Vorher Erwartungswert 3
      notieren.
    - **G – große Pakete:** `lab 04 ping 192.168.33.10 50 1472` und
      `python3 tools/rnlab.py ping 192.168.33.99 -c 50 -s 1472 -i 0.2 --df`.
    - **H – ohne Menü:** Das Menü (App-Baum) hält die Poll-Periode bei
      `lab poll` ms; am Konsolen-Prompt pollt die Firmware alle 2 ms, `lab poll`
      wirkt dort nicht. `lab key quit` verlässt das Menü (Antwort `key: quit`),
      `lab key menu` holt es zurück:

        ```bash
        python3 tools/rnlab.py lab 192.168.33.99 "lab key quit"
        python3 tools/rnlab.py ping 192.168.33.99 -c 100 -i 0.2 --hist 1
        python3 tools/rnlab.py lab 192.168.33.99 "lab 04 ping 192.168.33.10 100 56"
        python3 tools/rnlab.py lab 192.168.33.99 "lab key menu"
        ```

      Vergleicht mit eurer Messung bei `lab poll 2`. Am Prompt melden andere
      Tasten `? Menue laeuft nicht - erst 'lab key menu'`.

## Erwartungswert (vor der Messung notieren!)

**1. Leitungs-RTT.** Ein Ping mit 56 B Nutzdaten ist ein Ethernet-Frame aus
14 B Ethernet-Header + 20 B IPv4 + 8 B ICMP + 56 B Daten + 4 B FCS; dazu kommen
auf dem Kabel 8 B Präambel/SFD und 12 B Interframe Gap. Berechnet für 56 B und
1472 B Nutzdaten:

- Bytes auf dem Kabel je Richtung und Serialisierungszeit bei 100 Mbit/s,
- die Ausbreitungszeit auf 2 m Kabel (≈ 2·10⁸ m/s),
- eine Schätzung für die RTT, wenn beide Seiten „sofort“ antworten würden.

**2. Poll-Schleife.** Das Board hat kein Betriebssystem-Netzwerk mit
Interrupts: lwIP läuft mit `NO_SYS=1`, empfangene Frames bleiben im Ring des
Ethernet-Controllers liegen, bis die Hauptschleife das nächste Mal
`cads_net_poll()` aufruft. Findet im Quelltext heraus, wie oft das im Menü
passiert: In
[`apps/bringup/explorer_app_demo.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/bringup/explorer_app_demo.c)
steht die Schleife des App-Baums (sie wartet am Ende mit `rnlab_idle_ms(10u)`,
siehe
[`apps/rnlab/src/rnlab.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/rnlab.c)),
in
[`apps/bringup/explorer.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/bringup/explorer.c)
die des Konsolen-Prompts. Sucht nach `cads_net_poll`/`rnlab_poll` und nach
dem, was zwischen zwei Aufrufen passiert. Nennt die Periode *T*; im Menü
hängt sie von `lab poll` ab.

Ein Echo Request kommt zu einem zufälligen Zeitpunkt an, also gleichverteilt
in der Periode. Sagt für die Messung vom Rechner aus voraus:

| Größe | Formel | `lab poll 10` | `lab poll 2` |
|---|---|---|---|
| min | RTT_Leitung | | |
| avg | RTT_Leitung + *T*/2 | | |
| max | RTT_Leitung + *T* | | |
| stddev | *T*/√12 (Gleichverteilung) | | |

RTT_Leitung enthält hier auch die Verarbeitungszeit (Stack, Prüfsummen,
Kopien) auf beiden Seiten. Kurz: **avg RTT ≈ Verarbeitungszeit + *T*/2,
stddev ≈ *T*/√12.** Füllt dieselben Zeilen für `lab poll` 10, 5, 2 und 1 ms aus:

| `lab poll` | *T* | avg (Rechner) | stddev (Rechner) | avg (Board-Ping) |
|---|---|---|---|---|
| 10 | | | | |
| 5 | | | | |
| 2 | | | | |
| 1 | | | | |

und für `lab 04 ping` vom Board aus. Diese Messschleife ruft `cads_net_poll()`
**ohne Pause** auf. Wie sieht deren Verteilung aus?

**3. Delay und Loss (für Vertiefung F).** `lab 04 delay 20` parkt die Antwort in lwIPs Timerliste,
die ebenfalls nur bei jedem Poll geprüft wird. Welche RTT erwartet ihr
(min/avg/max)? Bei `loss 30` und 100 Pings: wie viele Verluste im Mittel,
und mit welcher Streuung (Binomialverteilung)?

## Experiment (Firmware-Aufgabe)

Dateien in eurem Fork (Branch `praktikum/start`):

- [`apps/rnlab/src/l04_icmp_logic.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/l04_icmp_logic.c)
  mit [`l04_icmp_logic.h`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/l04_icmp_logic.h):
  reine Logik, **hier arbeitet ihr** (`TODO(L04)`).
- [`apps/rnlab/src/l04_icmp.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/l04_icmp.c):
  Responder, Ping, Befehle, fertig. Der Kopfkommentar erklärt das
  Zusammenspiel mit lwIP.
- [`tests/unit/test_rnlab_l04.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/tests/unit/test_rnlab_l04.c):
  die Spezifikation (u. a. das Rechenbeispiel aus RFC 1071).

| Funktion | Aufgabe |
|---|---|
| `uint16_t rnlab_inet_checksum(const uint8_t* data, size_t len)` | RFC 1071: 16-Bit-Wörter big-endian in 32 Bit aufsummieren, ungerades letztes Byte mit 0 auffüllen, Überträge zurückfalten, Komplement. Über ein korrektes Paket ergibt sie 0. |
| `bool rnlab_l04_echo_to_reply(uint8_t* icmp, size_t len)` | Request prüfen (≥ 8 B, Typ 8, Code 0, Prüfsumme), in Reply umbauen (Typ 0, Prüfsumme neu), sonst `false` und Puffer unverändert |
| `unsigned rnlab_l04_hist_bin(uint32_t rtt_us)` | Bin 0: < 250 µs, dann je Verdopplung ein Bin, Bin 9: ≥ 64 ms |
| `void rnlab_l04_stats_add(stats, rtt_us)` | received, min, max, Σx, Σx², Histogramm |
| `rnlab_l04_stats_avg_us()` / `rnlab_l04_stats_stddev_us()` | Mittelwert; Standardabweichung in Populationsform wie `ping`, nur Ganzzahlen: n²·Var = n·Σx² − (Σx)², Wurzel mit `rnlab_l04_isqrt64()` |

**So übernimmt euer Responder.** `lab 04 echo on` legt mit
`raw_new(IP_PROTO_ICMP)` einen RAW-PCB an. lwIPs `ip4_input()` reicht jedes
Paket **zuerst** an `raw_input()` weiter, mit `p->payload` noch am IP-Header.
Die recv-Funktion des PCB entscheidet:

- Rückgabe **1** („gegessen“): Sie besitzt jetzt den Puffer und muss ihn
  freigeben; lwIP bricht ab, `icmp_input()`, der eingebaute Responder, läuft
  für dieses Paket nicht.
- Rückgabe **0**: Paket unverändert lassen, lwIP antwortet wie gewohnt.

Euer Responder antwortet mit TTL 64, lwIP mit TTL 255; so seht ihr schon in
der `ping`-Ausgabe, wer antwortet. Pings an Broadcast-/Multicast-Adressen gibt
er an lwIP zurück, das sie ignoriert. `lab 04 delay` darf nicht blockieren
(der Callback läuft mitten in `cads_net_poll()`), deshalb wird die Antwort mit
`sys_timeout()` in lwIPs Timerliste geparkt.

```bash
cmake --build build/host && ctest --test-dir build/host -L rnlab-L04 --output-on-failure
```

Ohne Implementierung verwirft `echo on` jede Anfrage als „fehlerhaft“, mit
`echo off` antwortet weiter lwIP.

!!! warning "Jeder RAW-PCB sieht jedes ICMP-Paket"
    Die Firmware hat drei RAW-PCBs; `cads_net_ping()` holt sich einen eigenen,
    auch wenn euer Responder läuft. Beide recv-Funktionen sehen dann dieselben
    Pakete, die zuerst gefragte kann ein fremdes Paket „essen“. Deshalb gibt
    die Funktion alles, was nicht eindeutig ihr gehört (Typ, Identifier,
    Sequenznummer), mit 0 zurück.

??? example "Vertiefung (optional): Prüfsumme inkrementell"
    Beim Umbau Request → Reply ändert sich nur das erste 16-Bit-Wort
    (`0x0800` → `0x0000`). Nach RFC 1624 kann man die neue Prüfsumme aus der
    alten berechnen, ohne das ganze Paket zu lesen. Wie? Der Test
    `test_echo_to_reply` prüft das Ergebnis.

## Auswertung

1. Tragt alle Messungen (A–E) in eine Tabelle min/avg/max/stddev ein und
   vergleicht sie mit euren Erwartungswerten.
2. **Wo kommt die Latenz her?** Begründet mit euren Zahlen, welcher Anteil der
   RTT vom Rechner aus auf die Leitung, welcher auf die Verarbeitung im Board
   und welcher aufs Warten entfällt. Belege: Board-Ping, `lab 04 stats`
   (Zeile „bearbeitung“: Zeit vom Aufruf eurer recv-Funktion bis zur Übergabe
   der Antwort an den MAC), `lab 04 pollgap`, die `lab poll`-Reihe.
3. Passt die Form der Verteilung zur Gleichverteilungs-Annahme? Prüft
   stddev ≈ *T*/√12 und das Histogramm.
4. Tragt avg und stddev der `lab poll`-Reihe über *T* auf. Wo schneidet die
   Gerade avg(*T*) die y-Achse, und was bedeutet dieser Wert? Wie stark
   ändert sich der Board-Ping mit *T* im Vergleich zum Mac-Ping, und warum?
   Was kostet ein kleineres *T* (Stichwort: Zeit, die der Schleife für
   Display und Eingabe bleibt)?
5. Was zeigt `traceroute` zum Board, und warum erreicht schon die erste
   Probe (TTL 1) das Board? Welche ICMP-Nachricht beantwortet die
   traceroute-Probe (Wireshark)?
6. *(Vertiefung G)* Board-Ping 56 B vs. 1472 B: Wie groß ist der Zuwachs pro Byte, und wie
   viel davon erklärt die Serialisierung (0,08 µs/B je Richtung)?
7. *(Vertiefung F)* Die Verlustrate bei `loss 30`: Liegt euer Wert im erwarteten Bereich?

--8<-- "issue-feedback.md"

## Potenzielle Herausforderungen

- **Prüfsumme falsch herum:** Wörter sind **big-endian** (Netz-Reihenfolge).
  Wer `uint16_t` direkt aus dem Puffer liest, rechnet auf dem Host
  (little-endian) mit vertauschten Bytes. Der RFC-1071-Test zeigt das sofort.
- **Überträge vergessen:** Eine einzige Faltung reicht nicht immer
  (`0xFFFF + 0xFFFF`); in einer Schleife falten, bis nichts mehr übrig ist.
- **stddev negativ/riesig:** E[x²] − E[x]² mit abgeschnittenen Ganzzahl-
  Divisionen kann unterlaufen; mit n·Σx² − (Σx)² rechnen.
- **Pings gehen verloren, ohne dass `loss` gesetzt ist:** Während das Display
  neu gezeichnet wird, teilen sich Display-SPI und Ethernet einen Pin (PA7); der
  Empfänger ist dann kurz abgeschaltet. Das seht ihr in Versuch 09 wieder.

## Quellen

- RN-Skript, Kap. 5.16 (ICMP) und 5.14 (IPv4-Header, TTL, Header-Checksumme).
- RFC 792 – Internet Control Message Protocol.
- RFC 1071 – Computing the Internet Checksum; RFC 1624 – inkrementelle
  Aktualisierung.
- RFC 1122, Abschn. 3.2.2.6 – Echo Request/Reply (Daten unverändert zurück).
- lwIP: `src/core/raw.c` (`raw_input`, Rückgabewert „eaten“),
  `src/core/ipv4/ip4.c` (Reihenfolge `raw_input` → `icmp_input`),
  `src/core/ipv4/icmp.c` (eingebauter Responder, `LWIP_BROADCAST_PING`).
- IEEE 802.3 – Präambel, SFD, Interframe Gap.
