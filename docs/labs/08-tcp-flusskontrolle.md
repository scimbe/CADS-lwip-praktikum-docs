# 08 · TCP-Flusskontrolle

<a class="md-button" href="../../pdf/08-tcp-flusskontrolle.pdf">:material-file-pdf-box: Als PDF herunterladen</a>

!!! info "Termin T09 · Setup S1"
    Dieser Versuch läuft im Netz-Setup **S1 – statische Adresse**
    (siehe [Netz-Setup](../reference/netz-setup.md#s1-statische-adresse)).

--8<-- "konventionen.md"

Ein TCP-Empfänger schützt sich selbst: Er sagt dem Sender in jedem ACK, wie
viele Byte er noch aufnehmen kann – das **Empfangsfenster**. Mehr darf nicht
unterwegs sein. Daraus folgt eine einfache Obergrenze für den Durchsatz: ein
Fenster pro Round-Trip. In diesem Versuch baut ihr auf dem Board eine
TCP-Senke mit lwIPs Raw-API, deren Fenster ihr per Build-Option verändert und
deren „Anwendung“ ihr absichtlich langsam lesen lasst. Ihr sagt den Durchsatz
vorher, messt ihn und verfolgt den Schutz des Empfängers bis hinunter in die
Netzwerkkarte: Fenster, Poll-Intervall, Empfangsring und CPU begrenzen
nacheinander – und nicht immer dort, wo man es erwartet.

## Lernziele

Nach dem Versuch könnt ihr …

- Flusskontrolle („Schutz des Empfängers“) von Überlastkontrolle („Schutz des
  Netzes“, Versuch 09) abgrenzen,
- erklären, wie das Empfangsfenster in lwIP entsteht und wieder aufgeht
  (`TCP_WND`, `tcp_recved()`),
- den Goodput als Minimum aus Fenstergrenze *W*/RTT, Leitungsgrenze und
  Leserate der Anwendung vorhersagen und das Ergebnis begründet bewerten,
- Nullfenster, Zero-Window-Probe, Window Update und die Vermeidung des
  Silly-Window-Syndroms in einem Mitschnitt erkennen,
- die Grenzen eines gepollten Embedded-Empfängers benennen (Poll-Periode,
  DMA-Ring, Kopieraufwand).

## Theorie-Bezug (Skript 5.26–5.30)

- **TCP** (5.26) ist verbindungsorientiert: Drei-Wege-Handshake mit SYN,
  SYN-ACK, ACK; Abbau mit FIN/ACK. Jedes Byte hat eine Sequenznummer, ACKs
  sind **kumulativ**.
- **ARQ und Sliding Window** (5.27, 5.28): Ein Sender darf ein ganzes Fenster
  unbestätigter Daten unterwegs haben. TCP mischt GoBackN (ein Timer für das
  älteste Segment, kumulative ACKs) mit Selective Repeat (der Empfänger puffert
  Segmente außer der Reihe).
- **Transportprotokollmechanismen** (5.29): Für eine stabile Übertragung
  braucht es ARQ, Flow Control und Congestion Control.
- **Schutz des Empfängers** (5.30): Die Flusskontrolle („Receiver Window Flow
  Control“) steckt im Feld **Window** des TCP-Headers: So viele Byte ab der
  bestätigten Sequenznummer darf der Sender noch schicken. Zusammen mit dem
  Überlastfenster (Versuch 09) bestimmt es das Sendefenster:
  *W*<sub>Senden</sub> = min(cwnd, rwnd).

!!! question "Kurz nachgedacht: Warum ist die ISN zufällig?"
    Die erste Sequenznummer einer Verbindung (Initial Sequence Number) seht
    ihr in Wireshark im SYN, wenn ihr unter *Protokolleinstellungen → TCP*
    „Relative Sequenznummern“ ausschaltet. Ein Stack mit festem Startwert
    beginnt nach jedem Reset mit derselben ISN (lwIP ohne eigene
    ISN-Funktion: 6510). Das Board rechnet sie nach RFC 6528 aus einem Hash
    über die vier Adressen/Ports und eine 4-µs-Uhr; über drei Resets ergab
    das 3614473351, 2397320143 und 232723522. Welche zwei Probleme löst das? Denkt an ein altes Segment
    einer früheren Verbindung mit demselben 4-Tupel und an einen Angreifer,
    der Segmente in eine fremde Verbindung einschleusen will (Skript 5.26,
    SYN-Angriffe und IP-Spoofing).

- Ausblick 5.31: **Silly-Window-Syndrom** – öffnet ein Empfänger sein Fenster
  in winzigen Schritten und füllt der Sender jede Lücke sofort, entstehen
  Kleinstsegmente mit großem Header-Anteil. Beide Seiten vermeiden das
  (RFC 1122, 4.2.3.3 und 4.2.3.4).

## Versuchsaufbau

```
 Rechner 192.168.33.10/24  ── Ethernet 100 Mbit/s, direkt ──  ITS-Board 192.168.33.99/24
 rnlab.py tcp-send (Sender), Wireshark                       TCP-Senke :7008, lwIP Raw-API
```

- Setup **S1**, Wireshark auf der Board-Schnittstelle, Filter `tcp.port == 7008`.
- Sender ist [`rnlab.py tcp-send`](../reference/rnlab-tool.md#tcp-send-tcp-recv);
  sein Goodput „bis FIN der Gegenseite“ ist der Wert, der zählt.
- Die Senke nimmt eine Verbindung an, zählt die Daten und verwirft sie. Wie
  schnell die „Anwendung“ liest, stellt ihr ein. Gelesen heißt in lwIP: Die
  Anwendung ruft `tcp_recved(pcb, n)` – erst dann geht das Fenster um *n* Byte
  wieder auf.
- Fenster und Segmentgröße sind **Build-Optionen** (siehe
  [`apps/rnlab/README.md`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/README.md),
  Abschnitt „TCP-Parameter“):

    | CMake-Option | Standard | Bereich | lwIP |
    |---|---:|---|---|
    | `CADS_RNLAB_TCP_MSS` | 536 | 536 oder 1460 | `TCP_MSS` |
    | `CADS_RNLAB_TCP_WND_MSS` | 8 | 2 … 32 | `TCP_WND = n · TCP_MSS` (höchstens 46 720 B) |
    | `CADS_RNLAB_TCP_SND_BUF_MSS` | 4 | 2 … 16 | `TCP_SND_BUF = n · TCP_MSS` |
    | `CADS_RNLAB_ETH_RX_COUNT` | 8 | 4 … 32 | Deskriptoren im Empfangsring der Netzwerkkarte, je 1536 B SRAM |

    ```bash
    bash scripts/build.sh Debug -DCADS_RNLAB_TCP_MSS=1460 -DCADS_RNLAB_TCP_WND_MSS=16 -DCADS_RNLAB_ETH_RX_COUNT=32
    ```

    Die Optionen bleiben im Build-Ordner gespeichert. Nach dem Versuch wieder
    auf `-DCADS_RNLAB_TCP_MSS=536 -DCADS_RNLAB_TCP_WND_MSS=8 -DCADS_RNLAB_TCP_SND_BUF_MSS=4 -DCADS_RNLAB_ETH_RX_COUNT=8`
    zurücksetzen. Nicht jede Kombination passt ins SRAM: 1460/32 mit
    `TCP_SND_BUF_MSS` 16 geht nur bis RX 20 (der Linker bricht sonst ab; Tabelle im README).

| Befehl | Wirkung |
|---|---|
| `lab 08 sink start` | Senke auf Port 7008 öffnen (eine Verbindung zur Zeit) |
| `lab 08 sink rate <kB/s>` | Leserate der Anwendung, `0` = liest sofort alles; gilt auch mitten in einer Übertragung |
| `lab 08 sink pause` / `resume` | Anwendung liest gar nicht mehr / wieder |
| `lab 08 sink stats` | Bytes, Goodput, Fenster jetzt/minimal, ungelesene Bytes, Nullfenster (Anzahl, Dauer), Window Updates |
| `lab 08 sink stop` | Senke schließen |
| `lab 08 info` | `TCP_MSS`, `TCP_WND`, `TCP_SND_BUF`, `PBUF_POOL_SIZE` dieses Builds |
| `lab 08 calc <rtt_us> [kB/s]` | eure Vorhersage (Firmware-Aufgabe) für diesen Build |
| `lab poll [ms]` | Poll-Intervall des Netzes im Menü anzeigen/setzen (1 … 10 ms, Standard 10) |
| `lab info` | u. a. `rx: … (… verworfen)` (kein pbuf) und `rx_ring_overruns` (Frames ohne freien Deskriptor), seit dem Boot |

## Versuchsablauf

!!! info "Zeitplan: rund 3 Stunden Pflicht"
    **Pflicht:** Firmware-Aufgabe, Erwartungswerte, Versuch A, aus der Matrix B
    die fünf Varianten 536/2/8, 536/8/8, 536/16/8, 536/16/32 und 1460/16/32,
    jeweils mit `lab poll 10` und `lab poll 2` (Versuch E; kein neues
    Flashen), dazu C und D; Auswertung 1–4, 6, 7. **Vertiefung:** die übrigen
    Matrix-Varianten, `lab poll 1` und der Konsolen-Prompt (`lab key quit`),
    Auswertung 5 und die Vertiefungs-Kästen. In der Gruppe lohnt es sich, die
    Matrix aufzuteilen.

1. Firmware-Aufgabe umsetzen, Host-Tests grün, Standard-Build flashen.
2. **Erwartungswerte** notieren (nächster Abschnitt).
3. **A – RTT:** `lab 08 info`, dann 30 Pings:
   `python3 tools/rnlab.py ping 192.168.33.99 -c 30 -i 0.1`.
4. **B – Messmatrix:** für jede Variante bauen, flashen, dann

    ```bash
    python3 tools/rnlab.py lab 192.168.33.99 "lab 08 info" "lab 08 sink start"
    python3 tools/rnlab.py tcp-send 192.168.33.99 7008 --bytes 1000000
    python3 tools/rnlab.py tcp-send 192.168.33.99 7008 --bytes 1000000
    python3 tools/rnlab.py lab 192.168.33.99 "lab 08 sink stats"
    ```

    Windows: `py tools\rnlab.py …` statt `python3 tools/rnlab.py …`.

    Notiert vorher und nachher `rx_ring_overruns` aus `lab info`. Varianten
    (MSS/*W* in Segmenten/RX-Ring) – **Pflicht:** 536/2/8, 536/8/8, 536/16/8,
    536/16/32, 1460/16/32; **Vertiefung:** 536/4/8, 1460/4/8, 1460/8/8,
    1460/16/8, 1460/32/8, 1460/32/20. Teilt die Varianten in der Gruppe auf. In Wireshark zählt ihr
    Wiederholungen
    (`tcp.analysis.retransmission`) und seht euch unter *Statistiken →
    TCP-Stream-Graphen → Fenstergröße* bzw. *Zeit/Sequenz (Stevens)* an, wie
    die Daten kommen.
5. **C – langsame Anwendung** (Standard-Build 536/8):

    ```bash
    python3 tools/rnlab.py lab 192.168.33.99 "lab 08 sink rate 100"
    python3 tools/rnlab.py tcp-send 192.168.33.99 7008 --bytes 200000 --wait 30
    python3 tools/rnlab.py lab 192.168.33.99 "lab 08 sink stats" "lab 08 sink rate 20"
    python3 tools/rnlab.py tcp-send 192.168.33.99 7008 --bytes 200000 --wait 30
    python3 tools/rnlab.py lab 192.168.33.99 "lab 08 sink stats" "lab 08 sink rate 0"
    ```

    Wireshark-Filter: `tcp.analysis.window_full || tcp.analysis.window_update || tcp.analysis.zero_window`.
6. **D – Anwendung hält an:** Übertragung starten, nach einer halben Sekunde
   `pause`, **15 s** warten, `resume`:

    ```bash
    python3 tools/rnlab.py tcp-send 192.168.33.99 7008 --bytes 1000000 --wait 40 &
    sleep 0.5; python3 tools/rnlab.py lab 192.168.33.99 "lab 08 sink pause"
    sleep 15;  python3 tools/rnlab.py lab 192.168.33.99 "lab 08 sink stats" "lab 08 sink resume"; wait
    ```

    Unter Windows startet ihr `tcp-send` in einem zweiten Terminal. Filter:
    `tcp.analysis.zero_window || tcp.analysis.zero_window_probe || tcp.analysis.window_update`.
7. **E – kürzeres Poll-Intervall:** `lab poll 2` lässt das Board im Menü alle
   2 ms statt alle 10 ms pollen (Vertiefung: `lab poll 1`). Wiederholt B für
   eure Varianten – die Messmatrix bekommt damit ihre dritte Achse. Nach dem
   Versuch `lab poll 10` (ein Reset setzt es ebenfalls zurück).
   Noch einen Schritt weiter (Vertiefung, über die
   [serielle Konsole](../reference/serielle-konsole.md) oder Telnet):
   `lab key quit` beendet das Menü;
   am Konsolen-Prompt läuft das Netz ohne GUI-Tick alle 2 ms weiter.
   Vergleicht mit `lab poll 2` und kehrt mit `lab key menu` zurück.

## Erwartungswert (vor der Messung notieren!)

**1. Fenstergrenze.** Ein Sender kann höchstens ein Fenster *W* pro Round-Trip
übertragen: Goodput ≤ *W*/RTT. Berechnet *W* in Byte für eure
Varianten (Pflicht: die fünf aus dem Zeitplan) und daraus *W*/RTT mit dem
**Mittelwert** eurer Ping-RTT aus A.

**2. Leitungsgrenze.** Jedes volle Segment trägt MSS Byte Nutzdaten, belegt auf
dem Kabel aber MSS + 78 Byte (Präambel/SFD 8, Ethernet 14, FCS 4, Interframe
Gap 12, IPv4 20, TCP 20). Welcher Goodput ist bei 100 Mbit/s mit MSS 536 bzw.
1460 höchstens möglich?

**3. Welche RTT?** Das Board pollt im Menü nur alle *T* ≈ 10 ms (Versuch 04).
Überlegt, was mit einem Fenster von 2 Segmenten geschieht: Der Rechner schickt
beide sofort; sie warten im Empfangsring, bis das Board das nächste Mal pollt;
das Board bestätigt; der Rechner schickt sofort das nächste Fenster – und das
wartet wieder … Wie groß ist die RTT, die ein **Fenster** erlebt, im Vergleich
zum Mittelwert der Ping-RTT? Rechnet *W*/*T* für eure Varianten.

**4. Zweite Stufe: die Netzwerkkarte und die CPU.** Das Fenster ist nur die
erste Grenze. Darunter liegen drei weitere:

- **Ring/Poll:** Pro Poll kann das Board höchstens so viele Frames abholen, wie
  im Empfangsring Platz haben (*R* Deskriptoren; `cads_net_poll()` holt bei
  *R* ≤ 16 bis zu 16 ab). Grenze: *R*·MSS/*T*.
- **Leitung:** aus 2.
- **CPU:** Jeder Frame wird aus dem DMA-Puffer in einen pbuf kopiert, die
  Prüfsumme in Software gerechnet, TCP verarbeitet und ein ACK gebaut. Nehmt
  für ein 1460-B-Segment etwa 0,3 ms an (in E prüft ihr das nach).

Goodput ≈ min(*W*/*T*<sub>eff</sub>, *R*·MSS/*T*, Leitung, CPU). Welche
Grenze greift in jeder Zeile eurer Matrix – bei `lab poll 10` und bei
`lab poll 2`?

**Verlust.** Der Rechner schickt ein Fenster mit Leitungsgeschwindigkeit
(ein 1460-B-Frame alle 123 µs), das Board holt ihn
frühestens beim nächsten Poll ab und braucht dann ≈ 0,3 ms pro Frame. Was
passiert, wenn *W* größer als *R* ist? Ändert ein kürzeres Poll-Intervall
etwas daran?

**5. Langsame Anwendung.** Welcher Goodput ergibt sich bei einer Leserate von
100 kB/s und von 20 kB/s? Rechnet damit, dass das Fenster dabei ständig auf 0
fällt – oder nicht? (lwIP öffnet das Fenster nach außen erst, wenn es um
`TCP_WND_UPDATE_THRESHOLD` = min(*W*/4, 4·MSS) gewachsen ist.)

**6. Anhalten.** Was darf der Sender tun, solange das Fenster 0 ist, und woran
merkt er, dass es wieder aufgeht, wenn das Window Update verloren geht?
(RFC 9293, 3.8.6.1: Persist-Timer, Zero-Window-Probe.)

## Experiment (Firmware-Aufgabe)

Dateien in eurem Fork (Branch `praktikum/start`):

- [`apps/rnlab/src/l08_tcp_flusskontrolle_logic.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/l08_tcp_flusskontrolle_logic.c)
  mit [`l08_tcp_flusskontrolle_logic.h`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/l08_tcp_flusskontrolle_logic.h):
  **hier arbeitet ihr** (`TODO(L08)`).
- [`apps/rnlab/src/l08_tcp_flusskontrolle.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/l08_tcp_flusskontrolle.c):
  die Senke mit Raw-API-Callbacks (`tcp_accept`, `tcp_recv`, `tcp_err`),
  10-ms-Timer und Befehlen, fertig. Lest sie: Sie zeigt, wo `tcp_recved()`
  aufgerufen wird.
- [`tests/unit/test_rnlab_l08.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/tests/unit/test_rnlab_l08.c):
  die Spezifikation (17 Tests).

| Funktion | Aufgabe |
|---|---|
| `uint64_t rnlab_l08_window_limit_bps(uint32_t window_bytes, uint32_t rtt_us)` | *W*/RTT in bit/s; 0 bei RTT 0. Achtung: *W*·8·10⁶ passt nicht in 32 Bit |
| `uint64_t rnlab_l08_link_limit_bps(uint32_t link_bps, uint32_t mss)` | link · MSS/(MSS + 78) |
| `uint64_t rnlab_l08_predict_bps(W, rtt_us, link_bps, mss, app_bytes_per_s)` | Minimum aus Fenster-, Leitungs- und Anwendungsgrenze (0 = keine) |
| `uint32_t rnlab_l08_limiter_release(rnlab_l08_limiter_t* l, uint32_t now_ms, uint32_t pending)` | Token-Bucket: Wie viele der ungelesenen Byte hat die Anwendung bis `now_ms` gelesen? Guthaben in **Milli-Byte**, gedeckelt auf 100 ms der Rate (mindestens 1 Byte) |

**So hängt es zusammen.** Kommt ein Segment an, ruft lwIP `l08_recv()` auf.
Die Senke zählt die Bytes, gibt den pbuf sofort frei und merkt sich die Bytes
als „ungelesen“. Das Fenster ist damit um genau diese Bytes kleiner – lwIP hat
sie zugestellt, die Anwendung hat sie noch nicht quittiert. Alle 10 ms fragt
der Timer `l08_tick()` euren Begrenzer, wie viel die Anwendung inzwischen
gelesen hat, und ruft dafür `tcp_recved()`. Ohne Leserate (`rate 0`) ruft die
Senke `tcp_recved()` sofort im Callback – das funktioniert schon ohne eure
Implementierung, damit ihr B vor C messen könnt.

```bash
cmake --build build/host && ctest --test-dir build/host -L rnlab-L08 --output-on-failure
```

Ohne Implementierung zeigt `lab 08 calc` überall 0, und mit gesetzter
Leserate bleibt das Fenster für immer zu.

!!! warning "Schließen erst nach dem Lesen"
    Kommt das FIN des Senders, während noch ungelesene Daten im Fenster
    stehen, beantwortet lwIP ein `tcp_close()` mit **RST** statt FIN
    (`tcp_close_shutdown()` in `lib/lwip/src/core/tcp.c`). Die Senke schließt
    deshalb erst, wenn die Anwendung alles gelesen hat – so wie eine echte
    Anwendung erst den Rest liest und dann schließt.

??? example "Vertiefung (optional): Wer bestimmt die Segmentgröße?"
    Schaut euch im SYN des Rechners und im SYN-ACK des Boards die Option
    **MSS** an. Welcher Wert gilt für die Verbindung? `rnlab.py tcp-send`
    schreibt in Blöcken zu 1460 Byte (`--chunk`). Was macht der Rechner
    daraus bei MSS 536 (Wireshark: Längen 536, 536, 388 …)? Wie ändert sich
    das mit `--chunk 536`?

??? example "Aus der Praxis (optional): Nagle trifft PA7"
    Die Telnet-CLI des Boards schrieb die Antwort auf `lab key` in zwei
    kleinen Stücken. Das zweite kam beim Rechner erst **540 ms** später an.
    Nachdem die CLI `tcp_nagle_disable()` (TCP_NODELAY) setzte, waren es
    etwa 40 ms.

    - Warum hält der Nagle-Algorithmus (Skript 5.31) das zweite kleine
      Segment überhaupt zurück, und worauf wartet er?
    - Warum dauerte das hier so lange? Denkt an Delayed ACK beim Rechner und
      an den Display-Blit, der den Ethernet-Empfang über PA7 stilllegt
      (Versuch 07).
    - Wann ist „Nagle aus“ die richtige Wahl, wann schadet es?
    - Die Fortsetzung: Mit Nagle aus ging `lab info` als rund 35
      Kleinstsegmente hinaus, und `rx_ring_overruns` stieg, obwohl keine
      Daten verloren gingen. Was lief über, und warum? Wie sähe eine bessere
      Lösung aus?

## Auswertung

1. Tragt die Matrix ein: je Variante *W*, *W*/RTT<sub>avg</sub>, *W*/*T*,
   Ring-Grenze, gemessener Goodput (`lab poll 10` und `lab poll 2`),
   `rx_ring_overruns`
   und Wiederholungen. Markiert je Zeile die Grenze, die greift.
2. Für *W* = 2 Segmente: Welche Vorhersage trifft, *W*/RTT<sub>avg</sub> oder
   *W*/*T*? Wie liegt die Messung für *W* ≥ 4 im Vergleich zu *W*/*T*? Seht euch in Wireshark
   die Zeitstempel an (*Zeit/Sequenz*): Wie viele Segmente verarbeitet das
   Board pro Poll? Vergleicht mit der Fenstergröße und erklärt den Befund
   (Hinweis: Wie schnell antwortet der Rechner auf ein ACK, und wie lange
   braucht das Board für einen Frame?)
3. Vergleicht 536/16/8 mit 536/16/32: gleiches Fenster, anderer Ring. Belegt
   den Unterschied mit `rx_ring_overruns` und Wireshark. (Vertiefung: Wie
   verhalten sich 1460/16/8, 1460/32/8 und 1460/32/20?)
4. `lab poll 10` gegen `lab poll 2`: Wie skaliert der Goodput mit 1/*T*? Welche Zeile
   erreicht das Maximum, und welche Grenze greift dort? Berechnet aus diesem
   Maximum die Verarbeitungszeit pro Frame und vergleicht mit 0,3 ms.
5. Erreicht das Board die Leitungsgrenze aus Erwartung 2? Wenn nicht, nennt die
   Schritte, die pro Frame Rechenzeit kosten (Treiber, lwIP, ACK).
6. Versuch C: Stimmt der Goodput mit der Leserate überein? Wie viele
   Nullfenster und Window Updates zählen Board und Wireshark? Warum so wenige
   Nullfenster?
7. Versuch D: Zeichnet den Ablauf als Sequenzdiagramm (Zeitstempel aus
   Wireshark): letztes Datensegment, Nullfenster, Zero-Window-Probe(s),
   Window Update. In welchem Abstand kommen die Probes, und was macht der
   Rechner mit einem kleinen, aber nicht leeren Restfenster?

--8<-- "issue-feedback.md"

## Potenzielle Herausforderungen

- **„Gegenseite hat nicht geschlossen“ bei `tcp-send`:** Die Senke war nicht
  gestartet, gestoppt oder pausiert (FIN kommt erst nach `resume`); `--wait`
  großzügig wählen.
- **Zweite Verbindung wird abgewiesen (RST):** Die Senke nimmt nur eine
  Verbindung zur Zeit an – `tcp-send` nicht parallel starten.
- **Build-Option wirkt nicht:** Sie gilt für den ganzen Build-Ordner und
  bleibt dort stehen. `lab 08 info` zeigt, was wirklich geflasht ist.
- **1460/32 mit `TCP_SND_BUF_MSS` 16 geht nur bis RX 20:** größere Ringe passen nicht mehr ins SRAM,
  der Linker bricht ab (Tabelle im README).
- **Überlauf in `window_limit`:** 4288 · 8 · 10⁶ passt nicht in 32 Bit – der
  Test `test_window_limit_no_overflow` zeigt es.
- **Leserate unter 100 B/s bleibt bei 0:** In ganzen Byte ergibt
  Rate · 10 ms bei jedem Timer-Aufruf 0 – deshalb Milli-Byte.
- **Keine Zero-Window-Probe zu sehen:** Viele Stacks warten beim ersten Mal
  etwa 5 s. Mindestens 15 s pausieren.

## Quellen

- RN-Skript, Kap. 5.26–5.30 (TCP, ARQ, GoBackN/Selective Repeat,
  Transportprotokollmechanismen, Schutz des Empfängers) und 5.31 (SWS).
- RFC 9293 – Transmission Control Protocol, 3.8.6 (Fenster, Zero-Window-Probe).
- RFC 1122 – Host Requirements, 4.2.3.3/4.2.3.4 (SWS-Vermeidung bei Empfänger
  und Sender).
- RFC 6691 – TCP Options and Maximum Segment Size.
- RFC 896 – Congestion Control in IP/TCP Internetworks (Nagle-Algorithmus).
- lwIP: `src/core/tcp.c` (`tcp_recved`, `tcp_update_rcv_ann_wnd`,
  `tcp_close_shutdown`), `src/core/tcp_in.c` (`tcp_receive`),
  `src/include/lwip/opt.h` (`TCP_WND_UPDATE_THRESHOLD`).
- Firmware: `modules/net/src/cads_net_board.c` (Empfangspumpe),
  `modules/net/include/lwipopts.h` (abgeleitete Pools).
