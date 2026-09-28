# 02 · Ethernet & ARP

<a class="md-button" href="../../pdf/02-ethernet-arp.pdf">:material-file-pdf-box: Als PDF herunterladen</a>

!!! info "Termin T03 · Setup S1"
    Dieser Versuch läuft im Netz-Setup **S1 – statische Adresse**
    (siehe [Netz-Setup](../reference/netz-setup.md#s1-statische-adresse)).

--8<-- "konventionen.md"

Ein Ethernet-Frame braucht eine Ziel-MAC-Adresse; `ping 192.168.33.10` kennt
aber nur eine IP-Adresse. Das **Address Resolution Protocol** (ARP) schließt
diese Lücke: Es fragt per Broadcast, wer die IP-Adresse hat, und merkt sich die
Antwort in einem Cache. In diesem Versuch schreibt ihr den ARP-Parser des
Boards, schaut in die ARP-Tabelle von lwIP, sendet selbst ein Gratuitous ARP
und messt, wie lange eine Auflösung dauert und wie lange sich das Board eine
Antwort merkt.

## Lernziele

Nach dem Versuch könnt ihr …

- Aufbau und Felder eines ARP-Pakets (RFC 826) im Frame wiederfinden und die
  Varianten Request, Reply, **Gratuitous ARP** und **ARP-Probe** unterscheiden,
- an einer MAC-Adresse Broadcast/Multicast (I/G-Bit) und lokal verwaltete
  Adressen (U/L-Bit) erkennen,
- einen robusten ARP-Parser für Ethernet/IPv4 schreiben und testen,
- ARP-Auflösezeit und Cache-Lebensdauer aus Konfiguration und Aufbau
  **vorhersagen** (`ARP_MAXAGE` in lwIP, Polling des Boards) und am Board
  nachmessen,
- erklären, warum der erste Ping nach dem Leeren eines ARP-Caches länger
  dauert.

## Theorie-Bezug (Skript 5.15)

- **5.15 ARP:** ARP bildet logische (strukturierte) IP-Adressen auf
  physische (unstrukturierte) MAC-Adressen ab – im Skript als Dienstprotokoll
  zwischen der Netzzugangs- und der Internetschicht des TCP/IP-Modells, also
  zwischen OSI-Schicht 2 und 3. Ein **Request** geht per **Broadcast** an alle
  Stationen der Broadcast-Domäne; nur der Besitzer der gesuchten Adresse
  antwortet per **Reply** (Unicast). Beide Seiten legen das Ergebnis im
  **ARP-Cache** ab, um wiederholte Anfragen zu vermeiden.
- Das Skript nennt auch die Schwächen: Jeder kann antworten (ARP-Spoofing),
  und eine ausbleibende Antwort ist nicht von einer zu späten zu
  unterscheiden. Dieselbe Anfrage-Technik prüft vor der Adressvergabe, ob eine
  Adresse schon belegt ist (**Probe**, RFC 5227).
- Aus **5.11** (strukturierte und unstrukturierte Adressen): Die MAC-Adresse
  vergibt der Hersteller aus einem von der IEEE zugeteilten Block. Das zweite
  Bit des ersten Oktetts (U/L) markiert dagegen **lokal verwaltete** Adressen,
  das niedrigste Bit (I/G) Gruppenadressen – `ff:ff:ff:ff:ff:ff` ist der
  Broadcast.

ARP-Paket für Ethernet/IPv4 (28 Byte, direkt hinter dem Ethernet-Header mit
EtherType `0x0806`):

| Byte | Feld | Wert bei Ethernet/IPv4 |
|---|---|---|
| 0–1 | Hardware Type | `0x0001` (Ethernet) |
| 2–3 | Protocol Type | `0x0800` (IPv4) |
| 4 | Hardware Address Length | 6 |
| 5 | Protocol Address Length | 4 |
| 6–7 | Operation | 1 = Request, 2 = Reply |
| 8–13 | Sender Hardware Address (SHA) | MAC des Absenders |
| 14–17 | Sender Protocol Address (SPA) | IP des Absenders |
| 18–23 | Target Hardware Address (THA) | Request: `00:00:00:00:00:00` |
| 24–27 | Target Protocol Address (TPA) | gesuchte IP |

## Versuchsaufbau

```text
 Rechner 192.168.33.10/24 ── Ethernet ── ITS-Board 192.168.33.99/24
   Wireshark (Filter: arp)               lwIP-ARP-Tabelle (etharp), RX/TX-Hook
   rnlab.py (Telnet)                     rnlab_parse_arp() -> Zähler, Zeiten
   serielle Konsole
```

- Setup **S1**, Firmware aus eurem Fork mit eurer Lösung.
- Wireshark auf der Board-Schnittstelle mit Anzeigefilter `arp`.
- **Serielle Konsole** ([Referenz](../reference/serielle-konsole.md)) für die
  Schritte, bei denen Telnet stören würde: Jede Telnet-Verbindung ist selbst
  IP-Verkehr zwischen Rechner und Board und löst deshalb selbst eine
  ARP-Auflösung aus bzw. frischt den Cache auf.

## Versuchsablauf

1. Firmware-Aufgabe umsetzen (unten), Host-Tests grün, flashen.
2. **Adressen ansehen.** MAC des Boards aus `lab info`, dann beide ARP-Tabellen:

    ```bash
    python3 tools/rnlab.py lab 192.168.33.99 "lab info" "lab 02 arp"
    ```

    ```text
    > lab 02 arp
    ARP-Tabelle (ARP_TABLE_SIZE 10, ARP_MAXAGE … s)
      [0] 192.168.33.10  A0:CE:C8:61:5D:08
    ```

    === "macOS"

        ```bash
        arp -a -i en7                               # Gerät eurer Board-Schnittstelle
        sysctl net.link.ether.inet.max_age          # Lebensdauer eines Eintrags in s
        ```

    === "Windows"

        ```powershell
        arp -a -N 192.168.33.10
        netsh interface ipv4 show neighbors "Ethernet 2"
        netsh interface ipv4 show interface "Ethernet 2"   # Base/Reachable Time
        ```

    === "Linux"

        ```bash
        ip neigh show dev enx001122334455           # Zustand REACHABLE/STALE/...
        cat /proc/sys/net/ipv4/neigh/enx001122334455/base_reachable_time_ms
        ```

3. **Zählen.** Über die **serielle Konsole** `lab 02 watch reset`, einmal
   `python3 tools/rnlab.py ping 192.168.33.99 -c 3`, dann seriell
   `lab 02 watch` (per Telnet würde die Sitzung selbst mitgezählt). Wie viele ARP-Pakete hat das Board gesehen bzw. gesendet?
4. **Gratuitous ARP** senden und in Wireshark ansehen (Ziel-MAC, SPA, TPA,
   THA):

    ```bash
    python3 tools/rnlab.py lab 192.168.33.99 "lab 02 garp"
    ```

    ```text
    > lab 02 garp
    Gratuitous ARP gesendet: who-has 192.168.33.99 tell 192.168.33.99
    ```

5. **Auflösezeit messen (Board-Seite).** `lab 02 resolve` leert die
   ARP-Tabelle, fragt nach einer Adresse und misst die Zeit bis zur Antwort;
   das Board fragt den Treiber dabei ununterbrochen ab:

    ```bash
    python3 tools/rnlab.py lab 192.168.33.99 "lab 02 resolve 192.168.33.10" "lab 02 resolve 192.168.33.10"
    python3 tools/rnlab.py lab 192.168.33.99 "lab 02 resolve 192.168.33.77"   # niemand antwortet
    ```

    Beispielausgabe (Referenzplatz, dort hat der Rechner `192.168.33.1`):

    ```text
    > lab 02 resolve 192.168.33.1
    who-has 192.168.33.1 is-at A0:CE:C8:61:5D:08
    Tabelle nach … us, Request->Reply im Treiber … us
    > lab 02 resolve 192.168.33.77
    .....
    who-has 192.168.33.77: keine Antwort in 1 s
    ```

    „Tabelle nach …“ misst vom Senden bis zum Eintrag in der lwIP-Tabelle,
    „Request->Reply im Treiber“ die Zeit zwischen dem gesendeten Request im
    TX-Hook und dem Reply im RX-Hook (beides ausgewertet mit eurem Parser).
    Die Punkte erscheinen alle 200 ms, solange das Board wartet.

    Vergleicht mit der Zeitdifferenz Request → Reply in Wireshark.
6. **Auflösung im Normalbetrieb (Rechner-Seite).** Über die **serielle
   Konsole** `lab 02 arp flush` und `lab 02 watch reset` eingeben, dann auf
   dem Rechner sofort `python3 tools/rnlab.py ping 192.168.33.99 -c 4`
   (die Einzelwerte zeigt `--json`).
   Anschließend seriell
   `lab 02 watch`. Wiederholt das fünfmal und notiert jeweils die erste und
   die folgenden RTTs.
7. **Cache-Lebensdauer.** Seriell `lab 02 arp flush`, auf dem Rechner genau
   **ein** `python3 tools/rnlab.py ping 192.168.33.99 -c 1` (Uhrzeit
   notieren), danach **nur noch
   seriell** alle 5 s `lab 02 arp`, bis der Eintrag eures Rechners
   verschwindet. In dieser Zeit keinen Verkehr zum Board erzeugen – kein
   Telnet, kein Ping. Achtung: lwIP frischt einen vorhandenen Eintrag auch
   bei **jedem ARP-Paket** dieses Absenders auf, selbst bei einem Broadcast,
   der gar nicht dem Board gilt. Zeigt Wireshark in dieser Zeit ARP-Anfragen
   eures Rechners, beginnt die Uhr von dort an neu.

## Erwartungswert (vor der Messung notieren!)

**a) Auflösezeit, Board pollt selbst (`lab 02 resolve`).** Request und Reply
sind je ein Frame mit Mindestlänge. Rechnet die Serialisierungszeit bei
100 Mbit/s (Frame 64 B + 8 B Präambel/SFD + 12 B Pause) und schätzt die
Bearbeitung im Rechner inklusive USB-Ethernet-Adapter (Größenordnung
0,1–0,3 ms).

**b) Auflösung im Normalbetrieb.** Im Normalbetrieb fragt die Hauptschleife
des Boards den Netztreiber nur etwa **alle 10 ms** ab (Versuch 00). Das Board
sendet seinen ARP-Request, während es gerade einen empfangenen Echo Request
bearbeitet – also direkt **nach** einer Abfrage. Wann sieht es die Antwort
frühestens? Ist die Verzögerung eher gleichverteilt oder eher konstant?

**c) Erster Ping nach dem Leeren des Board-Caches.** Der Rechner kennt die
MAC des Boards noch, das Board die des Rechners nicht mehr. Um wie viel ist
die erste RTT länger als die folgenden?

**d) Cache-Lebensdauer im Board.** lwIP entfernt einen Eintrag nach
`ARP_MAXAGE` Aufrufen seines ARP-Timers, der alle `ARP_TMR_INTERVAL` ms läuft.
Sucht beide Werte: zuerst in `modules/net/include/lwipopts.h` des Forks – steht
er dort nicht, gilt der Standard aus `lib/lwip/src/include/lwip/opt.h` bzw.
`lib/lwip/src/include/lwip/etharp.h`. Wie lange bleibt ein Eintrag **ohne**
Verkehr? Was passiert bei **dauerndem** Verkehr (Hinweis:
`ARP_AGE_REREQUEST_USED_UNICAST` in `lib/lwip/src/core/ipv4/etharp.c`)?

**e) Und auf eurem Rechner?** Lest den entsprechenden Wert eures
Betriebssystems ab (Schritt 2) und vergleicht.

## Experiment (Firmware-Aufgabe)

Dateien in eurem Fork (Branch `praktikum/start`):

- [`apps/rnlab/src/l02_ethernet_arp_logic.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/l02_ethernet_arp_logic.c)
  mit Header
  [`l02_ethernet_arp_logic.h`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/l02_ethernet_arp_logic.h):
  reine Logik, **hier arbeitet ihr** (beide Stellen `TODO(L02)`).
- [`apps/rnlab/src/l02_ethernet_arp.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/l02_ethernet_arp.c):
  Board-Integration, fertig: `rnlab_l02_hook_rx_frame()`/`rnlab_l02_hook_tx_frame()`
  zählen jeden ARP-Frame mit eurem Parser, die Befehle nutzen die ARP-Funktionen
  von lwIP (`etharp_get_entry()`, `etharp_cleanup_netif()`,
  `etharp_gratuitous()`, `etharp_request()`, `etharp_find_addr()`).
- [`tests/unit/test_rnlab_l02.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/tests/unit/test_rnlab_l02.c):
  34 Unity-Tests mit **echten Frames** (Request als Broadcast und Unicast,
  Reply, Gratuitous ARP und Request des Boards, aufgefüllt auf 60 B), dazu
  jede zu kurze Länge und falsche Feldwerte.

| Funktion | Aufgabe |
|---|---|
| `rnlab_arp_result_t rnlab_parse_arp(const uint8_t* frame, size_t len, rnlab_arp_packet_t* out)` | Ethernet-Frame (ab Ziel-MAC, ohne FCS) prüfen und das ARP-Paket in `out` zerlegen |
| `rnlab_arp_kind_t rnlab_arp_classify(const rnlab_arp_packet_t* packet)` | Request, Reply, Gratuitous oder Probe |

Prüfreihenfolge in `rnlab_parse_arp()` – genau in der Reihenfolge der
Fehlercodes, `out` wird nur bei Erfolg beschrieben:

1. kürzer als 14 + 28 Byte (oder `NULL`) → `RNLAB_ARP_ERR_TRUNCATED`,
2. EtherType ≠ `0x0806` → `RNLAB_ARP_ERR_NOT_ARP`,
3. nicht Ethernet/IPv4 (`htype` 1, `ptype` 0x0800, `hlen` 6, `plen` 4) →
   `RNLAB_ARP_ERR_UNSUPPORTED`,
4. Operation weder 1 noch 2 → `RNLAB_ARP_ERR_BAD_OPER`,
5. sonst Felder kopieren (Mehrbyte-Felder in Host-Byte-Reihenfolge, Adressen
   als Bytes) → `RNLAB_ARP_OK`. Füllbytes hinter den 28 Byte ignorieren.

`rnlab_arp_classify()`: `NULL` oder falsche Operation → `INVALID`; Request mit
SPA `0.0.0.0` → `PROBE`; SPA = TPA → `GRATUITOUS` (Request- und Reply-Form);
sonst `REQUEST` bzw. `REPLY`.

```bash
cmake --build build/host && ctest --test-dir build/host -L rnlab-L02 --output-on-failure
```

Ohne Implementierung sind 28 der 34 Tests rot; `lab 02 arp`, `arp flush` und
`garp` funktionieren trotzdem (sie nutzen lwIP), `lab 02 watch` zählt aber
nichts, und `resolve` zeigt keine im Treiber gemessene Zeit.

## Auswertung

1. Zeichnet den ARP-Austausch aus Schritt 5 als Weg-Zeit-Diagramm (Board,
   Rechner) mit den Zeitstempeln aus Wireshark und dem Wert von
   `lab 02 resolve`. Wo geht die Zeit hin, wenn die Leitung nur euren Wert
   aus a) beiträgt?
2. Vergleicht erste und folgende RTTs aus Schritt 6 mit eurer Vorhersage c).
   Warum schwanken die folgenden RTTs stark, der Aufschlag beim ersten aber
   kaum?
3. Wann verschwand der Eintrag in Schritt 7? Passt das zu `ARP_MAXAGE`? Was
   hätte ein Telnet-Aufruf von `lab 02 arp` alle 5 s am Ergebnis geändert?
4. Gratuitous ARP: Welche Felder unterscheiden es von einem normalen Request?
   Wozu verschickt ein Host es (Hinweis: Adresswechsel, Adresskonflikt,
   Failover), und was hat das mit ARP-Spoofing aus 5.15 zu tun?
5. Lest die MAC eures Boards aus `lab info` ab. Was sagt das zweitniedrigste
   Bit des ersten Oktetts (U/L) über diese Adresse, was das niedrigste (I/G)?
   Warum darf eine lokal verwaltete Adresse im Praktikum mehrfach vorkommen,
   solange jedes Board an seinem eigenen Rechner hängt – und wann wäre das
   nicht mehr unkritisch?

--8<-- "issue-feedback.md"

## Potenzielle Herausforderungen

- **Telnet verfälscht die Messung:** Jeder `rnlab.py lab …`-Aufruf ist
  TCP-Verkehr zwischen Rechner und Board – er löst nach einem Flush selbst die
  ARP-Auflösung aus und frischt Einträge auf. Flush und Timeout-Messung deshalb
  über die serielle Konsole.
- **`resolve` auf eine stumme Adresse** wartet 1 s und schreibt dabei alle
  200 ms einen Punkt – sonst hielte `rnlab.py` die Antwort nach 0,5 s Stille
  für beendet.
- **Der erste Ping ist manchmal doch schnell:** Fragt euer Rechner zufällig
  selbst per ARP nach dem Board, trägt lwIP den Absender dieses Requests
  sofort in seine Tabelle ein – dann muss das Board nicht mehr fragen.
  Wireshark zeigt, wer zuerst gefragt hat.
- **`arp -d` braucht Administratorrechte** (auf allen drei Systemen). Für
  diesen Versuch ist es nicht nötig: Geleert wird der Cache des Boards.
- **Nach einem Board-Reset mit `net.mac_random`** (neue MAC bei jedem Boot)
  kennt der Rechner noch die alte MAC; Pings gehen verloren, bis er neu fragt.
  `lab 02 garp` behebt das in der Regel sofort: Wer schon einen Eintrag für die
  Absender-IP hat, aktualisiert ihn (RFC 826). Bleibt die MAC über einen
  Neustart gleich, tritt das Problem nicht auf.
- **Wireshark zeigt 42-Byte-Frames**, das Board sieht 60 Byte: Mitgeschnitten
  wird auf dem Rechner, bevor dessen Netzwerkkarte auf die Mindestlänge
  auffüllt (Versuch 01).
- **Byte-Reihenfolge:** `htype`, `ptype` und `oper` sind im Frame big-endian;
  `rnlab_be16()` ist vorbereitet.

## Quellen

- RN-Skript, Kap. 5.15 (ARP) und 5.11 (strukturierte und unstrukturierte
  Adressen).
- RFC 826 – An Ethernet Address Resolution Protocol.
- RFC 5227 – IPv4 Address Conflict Detection (Probe, Announcement).
- RFC 1122, Abschn. 2.3.2 – ARP-Cache-Verwaltung in Hosts.
- IEEE 802-2014, Abschn. 8 – MAC-Adressen (I/G- und U/L-Bit).
- lwIP: `src/core/ipv4/etharp.c` (`etharp_tmr`, `etharp_output_to_arp_index`),
  `src/include/lwip/opt.h` (`ARP_MAXAGE`, `ARP_TABLE_SIZE`, `ARP_QUEUEING`).
