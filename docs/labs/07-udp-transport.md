# 07 · UDP-Transport

<a class="md-button" href="../../pdf/07-udp-transport.pdf">:material-file-pdf-box: Als PDF herunterladen</a>

!!! info "Termin T08 · Setup S1"
    Dieser Versuch läuft im Netz-Setup **S1 – statische Adresse**
    (siehe [Netz-Setup](../reference/netz-setup.md#s1-statische-adresse)).

--8<-- "konventionen.md"

UDP verspricht nichts: keine Reihenfolge, keine Vollständigkeit, keine
Rückmeldung. Wer wissen will, ob seine Datagramme angekommen sind, muss selbst
nummerieren und selbst zählen. Genau das baut ihr in diesem Versuch: eine
UDP-Senke auf dem Board, die Verluste, Umsortierungen und Duplikate an den
Sequenznummern erkennt. Dann schickt ihr ihr Bursts und Dauerströme und findet
heraus, **wo** im Board die Datagramme verloren gehen – und dass manche
Verluste in keinem einzigen Zähler auftauchen.

## Lernziele

Nach dem Versuch könnt ihr …

- erklären, welche Dienste UDP gegenüber IP hinzufügt (Ports, Prüfsumme) und
  welche nicht (Reihenfolge, Vollständigkeit, Flusskontrolle),
- Sequenznummern in Netzbyteordnung dekodieren und mit Serienarithmetik
  (RFC 1982) über den 32-Bit-Überlauf hinweg vergleichen,
- Verlust, Umsortierung und Duplikat mit einem Empfangsfenster unterscheiden,
- aus der Konfiguration eines Empfängers (DMA-Ring, Poll-Periode, Puffer-Pool)
  vorhersagen, ab welcher Burstlänge und welcher Rate er Datagramme verliert,
- Verluste der richtigen Schicht zuordnen – auch solchen, die kein Zähler sieht.

## Theorie-Bezug (Skript 5.25)

- IP ist **Best Effort**: Pakete können verloren gehen, sich überholen oder
  doppelt ankommen. Transportprotokolle setzen darauf Dienste auf – alle außer
  UDP.
- **UDP** fügt nur zwei Dinge hinzu: **Multiplexing** über 16-Bit-Ports und
  eine **Prüfsumme** (Einerkomplement, mit Pseudo-Header aus IP-Adressen).
  Der Header hat 8 Byte: Quellport, Zielport, Länge, Prüfsumme.
- UDP ist **zustandslos** und verbindungslos: Der Sender weiß nicht, ob der
  Empfänger existiert oder bereit ist. Das eignet sich für weiche
  Echtzeitanwendungen (Streaming, RTP) und als Unterbau eigener Protokolle
  (QUIC) – die dann Nummerierung und Wiederholung selbst mitbringen müssen.
- „Schon ein einziges verlorenes Paket kann zu Aussetzern führen“: Wie viele es
  sind, sieht nur, wer mitzählt. Das tut ihr hier auf Anwendungsebene, so wie
  RTP es mit seiner Sequenznummer tut.

## Versuchsaufbau

```
 Rechner 192.168.33.10/24  ── Ethernet 100 Mbit/s, direkt ──  ITS-Board 192.168.33.99/24
 rnlab.py udp-send / udp-recv, Wireshark                     UDP-Senke :7007, lwIP NO_SYS
```

- Setup **S1**, Wireshark auf der Board-Schnittstelle, Filter `udp.port == 7007`.
- Sender ist [`rnlab.py udp-send`](../reference/rnlab-tool.md#udp-send-udp-recv).
  Jedes Datagramm trägt in den ersten 12 Byte eine Sequenznummer (`uint32`)
  und einen Zeitstempel (`uint64`, µs), beide **big-endian**.
- Befehle an das Board mit [`rnlab.py lab`](../reference/rnlab-tool.md#lab-telnet).
- Das Board läuft nach dem Reset im **Menü** (App-Baum). Wie in Versuch 04
  ruft die Hauptschleife dort `cads_net_poll()` etwa alle 10 ms auf; empfangene
  Frames warten bis dahin im Empfangsring des Ethernet-Controllers.

| Befehl | Wirkung |
|---|---|
| `lab 07 udp start [echo <port>]` | Senke auf Port 7007 öffnen, Zähler auf 0; mit `echo` geht jedes Datagramm an den Absender (dessen IP, dieser Port) zurück |
| `lab 07 udp stats` | Zähler: empfangen, erwartet, verloren, umsortiert, Duplikate, veraltet, fehlerhaft, Rate; dazu die Zähler **darunter**: Treiber (kein pbuf) und MAC (kein RX-Deskriptor, FIFO-Überlauf) |
| `lab 07 udp reset` | Zähler auf 0 – **vor jedem `udp-send`-Lauf**, denn jeder Lauf beginnt wieder bei Sequenznummer 0 |
| `lab 07 udp stop` | Senke schließen |
| `lab 07 blit [ms]` | Display-Last: zeichnet für `ms` Millisekunden immer wieder ein kleines Rechteck oben rechts und pollt dazwischen das Netz (ein Punkt alle 300 ms als Lebenszeichen) |
| `lab info` | u. a. `rx_ring_overruns`: Frames, für die der Controller seit dem Boot keinen freien Deskriptor hatte |

## Versuchsablauf

!!! info "Zeitplan: rund 3 Stunden Pflicht"
    **Pflicht:** Firmware-Aufgabe, Erwartungswerte, Versuche A–D, Auswertung
    1–4. **Vertiefung**, wenn Zeit bleibt: Versuch E (Echo/RTT), Auswertung
    5–6 und die aufklappbaren Vertiefungs-Kästen (`lab poll`, tieferer Ring,
    Jitter).

1. Firmware-Aufgabe umsetzen, Host-Tests grün, flashen.
2. **Erwartungswerte** notieren (nächster Abschnitt).
3. **A – Grundlinie:** Senke starten, 1000 kleine Datagramme mit 100/s.

    ```bash
    python3 tools/rnlab.py lab 192.168.33.99 "lab 07 udp start"
    python3 tools/rnlab.py udp-send 192.168.33.99 7007 -n 1000 --rate 100
    python3 tools/rnlab.py lab 192.168.33.99 "lab 07 udp stats"
    ```

    Windows: `py tools\rnlab.py …` statt `python3 tools/rnlab.py …`.

4. **B – Bursts:** Je 20 Bursts der Länge *B* = 4, 8, 12, 16, 32 im
   Abstand von 100 ms (`--rate` = 10·*B*); 24 und 64 als Vertiefung. Vor jedem Lauf `udp reset`.

    ```bash
    python3 tools/rnlab.py lab 192.168.33.99 "lab 07 udp reset"
    python3 tools/rnlab.py udp-send 192.168.33.99 7007 -n 240 --burst 12 --rate 120
    python3 tools/rnlab.py lab 192.168.33.99 "lab 07 udp stats"
    ```

5. **C – Dauerstrom:** 3000 Datagramme mit 500, 1000, 2000, 5000 und
   „unbegrenzt“ (`--rate 0`) Datagrammen/s; danach einmal 2000 × 1400 Byte
   mit 500/s (`--size 1400`).
6. **D – Display:** Strom mit 500/s über 6 s, in der Mitte 2 s Display-Last:

    ```bash
    python3 tools/rnlab.py lab 192.168.33.99 "lab 07 udp reset"
    python3 tools/rnlab.py udp-send 192.168.33.99 7007 -n 3000 --rate 500 &
    sleep 2; python3 tools/rnlab.py lab 192.168.33.99 "lab 07 blit 2000"; wait
    python3 tools/rnlab.py lab 192.168.33.99 "lab 07 udp stats"
    ```

    Unter Windows (PowerShell) startet ihr `udp-send` in einem zweiten
    Terminal und den `blit`-Befehl nach etwa 2 s im ersten.

7. **E – Echo und RTT:** Das Board schickt jedes Datagramm an euren Rechner
   zurück. Weil dann Sende- und Empfangszeitstempel von **derselben** Uhr
   stammen, zeigt `udp-recv` als „Einweg-Laufzeit“ die RTT.

    ```bash
    python3 tools/rnlab.py lab 192.168.33.99 "lab 07 udp start echo 7070"
    python3 tools/rnlab.py udp-recv 7070 --expect 1000 &
    python3 tools/rnlab.py udp-send 192.168.33.99 7007 -n 1000 --rate 200; wait
    ```

    Unter Windows (PowerShell) startet ihr `udp-recv` in einem zweiten
    Terminal (`py tools\rnlab.py udp-recv 7070 --expect 1000`) und dann
    `udp-send` im ersten. Die Firewall eures Rechners muss eingehendes UDP auf
    Port 7070 zulassen (macOS fragt beim ersten Mal nach, Windows ebenso).

## Erwartungswert (vor der Messung notieren!)

**1. Die Leitung.** Ein Datagramm mit 64 Byte Nutzdaten ist ein Frame aus
14 B Ethernet + 20 B IPv4 + 8 B UDP + 64 B + 4 B FCS; auf dem Kabel kommen 8 B
Präambel/SFD und 12 B Interframe Gap dazu. Wie lange belegt es die Leitung bei
100 Mbit/s, und wie viele solcher Datagramme passen höchstens in eine Sekunde?
Dasselbe für 1400 Byte Nutzdaten. Welche Rate erreicht `udp-send --rate 0`
laut seiner eigenen Ausgabe?

**2. Die Puffer im Board.** Zwischen Kabel und eurem Callback liegen drei
Puffer. Sucht ihre Größe im Quelltext:

| Puffer | Wo | Größe |
|---|---|---|
| Empfangsring (DMA-Deskriptoren) des Ethernet-Controllers | `CADS_ETH_RX_COUNT` in [`targets/itsboard/hal/hal_eth_mac.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/targets/itsboard/hal/hal_eth_mac.c) | |
| Frames, die ein `cads_net_poll()` höchstens abholt | `CADS_NET_RX_BUDGET_PER_POLL` in [`modules/net/src/cads_net_board.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/modules/net/src/cads_net_board.c) | |
| lwIP-Pufferpool (pbufs) | `PBUF_POOL_SIZE` in [`modules/net/include/lwipopts.h`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/modules/net/include/lwipopts.h) | |

Lest `cads_net_receive_pump()` und euren Callback `l07_recv()`: Wann wird ein
pbuf belegt, wann wieder frei? Welcher der drei Puffer läuft bei einem Burst
**zuerst** über? Die naheliegende Hypothese „Verlust ab Burst > `PBUF_POOL_SIZE`“
– stimmt sie?

**3. Bursts.** Der Rechner schickt einen Burst in wenigen Hundert
Mikrosekunden; das Board pollt nur alle *T* ≈ 10 ms (Versuch 04). Sagt für
jede Burstlänge *B* die Verluste pro Burst und die Verlustrate voraus.

**4. Dauerstrom.** Wenn pro Poll höchstens so viele Frames ankommen können,
wie der kleinste Puffer fasst: Welche Rate hält das Board im Menü dauerhaft
durch? Sagt die Verlustrate für 500, 1000, 2000 und 5000 Datagramme/s voraus.
Ändert sich etwas bei 1400 statt 64 Byte (und warum nicht)?

**5. Display.** Auf dem ITS-Board teilen sich Display-SPI (MOSI) und der
Ethernet-Empfang (RMII CRS_DV) einen Pin, **PA7**. Lest den Kopfkommentar von
[`targets/itsboard/hal/hal_spi.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/targets/itsboard/hal/hal_spi.c):
Was passiert mit dem Ethernet-Empfang, solange ein Rechteck auf das Display
übertragen wird? Welche der drei Zähler (verloren, Treiber, MAC) steigen dabei,
welche nicht?

## Experiment (Firmware-Aufgabe)

Dateien in eurem Fork (Branch `praktikum/start`):

- [`apps/rnlab/src/l07_udp_transport_logic.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/l07_udp_transport_logic.c)
  mit [`l07_udp_transport_logic.h`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/l07_udp_transport_logic.h):
  reine Logik, **hier arbeitet ihr** (`TODO(L07)`). Der Header beschreibt das
  Datagrammformat und die genaue Semantik jedes Zählers.
- [`apps/rnlab/src/l07_udp_transport.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/l07_udp_transport.c):
  Senke, Echo, Display-Last und Befehle, fertig.
- [`tests/unit/test_rnlab_l07.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/tests/unit/test_rnlab_l07.c):
  die Spezifikation (20 Tests, u. a. Überlauf bei 0xFFFFFFFF).

| Funktion | Aufgabe |
|---|---|
| `bool rnlab_l07_parse_header(const uint8_t* data, size_t len, uint32_t* seq, uint64_t* sent_us)` | Sequenznummer (Byte 0–3) und Zeitstempel (Byte 4–11) big-endian dekodieren; `false` bei weniger als 12 Byte |
| `rnlab_seq_event_t rnlab_seq_update(rnlab_seq_tracker_t* t, uint32_t seq)` | eine Sequenznummer verbuchen und einordnen: `FIRST`, `IN_ORDER`, `GAP`, `LATE`, `DUPLICATE`, `STALE` |

**Das Empfangsfenster.** Der Tracker merkt sich die höchste Nummer (`next` − 1)
und in einem 32-Bit-Wort `window`, welche der 32 Nummern darunter schon da
waren (Bit *i* ↔ Nummer `next − 1 − i`). Eine neue, höhere Nummer schiebt das
Fenster; die übersprungenen zählen erst einmal als **verloren**. Kommt eine
davon später doch noch (Bit nicht gesetzt), war sie nur **umsortiert**:
`lost` sinkt wieder. Ist das Bit schon gesetzt, ist es ein **Duplikat**. Was
älter als 32 ist, lässt sich nicht mehr zuordnen und zählt als **veraltet**.

**Serienarithmetik.** `seq < next` ist falsch, sobald der Zähler überläuft:
0x00000001 ist *neuer* als 0xFFFFFFFF. Vergleicht über die vorzeichenbehaftete
Differenz `(int32_t)(seq - next)` – so macht es auch TCP mit seinen
Sequenznummern (RFC 1982, RFC 9293).

```bash
cmake --build build/host && ctest --test-dir build/host -L rnlab-L07 --output-on-failure
```

Ohne Implementierung zählt die Senke jedes Datagramm als „fehlerhaft“.

??? example "Vertiefung (optional): Kürzer pollen"
    `lab poll 2` bzw. `lab poll 1` lässt das Board im Menü alle 2 bzw. 1 ms
    pollen (Standard 10). Sagt für 5000 Datagramme/s die Verlustrate voraus
    und messt nach. Was kostet ein kürzeres Poll-Intervall die Oberfläche?

??? example "Vertiefung (optional): Ein tieferer Ring"
    Die Tiefe des Empfangsrings ist eine Build-Option:
    `-DCADS_RNLAB_ETH_RX_COUNT=16` (4 … 32, je Deskriptor 1536 B SRAM, siehe
    [`apps/rnlab/README.md`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/README.md),
    Abschnitt „TCP-Parameter“). Sagt voraus, wie sich Burst-Schwelle und
    Dauerrate aus B und C ändern, und messt nach. Warum ist ein tieferer Ring
    keine Lösung für Versuch D?

??? example "Vertiefung (optional): Jitter auf dem Board"
    `udp-recv` berechnet den Jitter nach RFC 3550 (6.4.1) aus
    Laufzeitdifferenzen. Das Board hat den Sendezeitstempel ebenfalls. Wie
    groß erwartet ihr den Jitter am Board im Menü, wenn Datagramme nur alle
    *T* abgeholt werden? Erweitert `l07_recv()` um die Rechnung (Zeitstempel
    in ganzen µs, `cads_hal_ticks_us()` als Empfangszeit – nur Differenzen
    zählen, die Uhren müssen nicht synchron sein).

## Auswertung

1. Tragt für B und C Erwartung und Messung in eine Tabelle ein (Verlust in %,
   dazu die Zähler `mac` und `treiber`). Wo liegt die Burst-Schwelle, und
   welcher Puffer bestimmt sie?
2. Die Zeile „erwartet“ des Boards endet bei der höchsten **empfangenen**
   Nummer. Vergleicht `verloren` mit dem MAC-Zähler und mit der Zahl der
   gesendeten Datagramme: Wie viele Verluste am Ende eines Laufs sieht die
   Senke nicht, und wie löst `udp-recv --expect` dieses Problem?
3. Welche Dauerrate hält das Board im Menü durch? Berechnet daraus *T* und
   vergleicht mit Versuch 04.
4. Versuch D: Wie viele Datagramme fehlen, wie viele davon hat irgendein Zähler
   des Boards gesehen? Welcher Anteil der Blit-Zeit war der Empfänger „taub“?
   Warum sieht auch Wireshark auf eurem Rechner nichts Auffälliges?
5. Versuch E: Vergleicht die RTT-Verteilung (min/avg/max) mit `ping` aus
   Versuch 04. Wo wartet das Datagramm?
6. Welche längsten Bursts sollte ein UDP-basiertes Protokoll mit Wiederholung
   (z. B. QUIC) diesem Board höchstens schicken, und warum? Was tut TCP an
   dieser Stelle (Ausblick auf Versuch 08/09)?

--8<-- "issue-feedback.md"

## Potenzielle Herausforderungen

- **„veraltet“ zählt hoch, „verloren“ bleibt 0:** `udp reset` vergessen. Der
  neue Lauf beginnt wieder bei 0, das ist aus Sicht des Trackers uralt.
- **Endianness:** Wer `*(uint32_t*)data` liest, bekommt auf dem Cortex-M4 und
  auf dem Host (beide little-endian) die Bytes vertauscht – und riskiert auf
  dem Board einen unausgerichteten Zugriff. Byteweise zusammensetzen.
- **Überlauf:** `if(seq < t->next)` scheitert am Test `test_wrap_*`;
  vorzeichenbehaftete Differenz verwenden.
- **Fenster schieben:** Bei `shift >= 32` ist `window << shift` in C
  undefiniert – vorher abfangen.
- **Echo kommt nicht an:** Firewall des Rechners für UDP 7070 öffnen; unter
  Windows das Netzprofil der Board-Schnittstelle auf „Privat“ stellen.
- **Windows sendet ungleichmäßig:** Bei hohen Raten kann der Zeitgeber von
  Windows die Bursts verklumpen; die mittlere Rate stimmt trotzdem, die
  Burstlänge `--burst` ist maßgeblich.

## Quellen

- RN-Skript, Kap. 5.25 (Dienste der Transportschicht, UDP).
- RFC 768 – User Datagram Protocol.
- RFC 1982 – Serial Number Arithmetic.
- RFC 3550 – RTP, Abschn. 6.4.1 (Jitter-Schätzung).
- lwIP: `src/core/udp.c` (`udp_input`, `udp_sendto`), `src/core/pbuf.c`.
- STM32F429 Reference Manual RM0090, Kap. Ethernet (DMA-Deskriptoren,
  `ETH_DMAMFBOCR`: Missed Frames).
- Firmware: `targets/itsboard/hal/hal_spi.c` (PA7-Arbitrierung),
  `modules/net/src/cads_net_board.c` (Empfangspumpe).
