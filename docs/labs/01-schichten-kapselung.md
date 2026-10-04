# 01 · Schichten & Kapselung

<a class="md-button" href="../../pdf/01-schichten-kapselung.pdf">:material-file-pdf-box: Als PDF herunterladen</a>

!!! info "Termin T02 · Setup S1"
    Dieser Versuch läuft im Netz-Setup **S1 – statische Adresse**
    (siehe [Netz-Setup](../reference/netz-setup.md#s1-statische-adresse)).

--8<-- "konventionen.md"

Jede Schicht setzt ihren Header vor die Daten der Schicht darüber – aus
wenigen Byte Ping-Daten wird so ein deutlich längerer Ethernet-Frame, und auf
dem Draht kommt noch mehr dazu. In diesem Versuch schreibt ihr den Dekoder, der diese
Kapselung auf dem Board wieder aufschält: Er zerlegt jeden empfangenen und
gesendeten Frame Schicht für Schicht, und das Board zeigt euch das Ergebnis
mit den Header-Bytes jeder Schicht an. Aus denselben Zahlen berechnet ihr,
wie viel der Leitung tatsächlich für Nutzdaten verwendet wird.

!!! tip "Zeitplan (≈ 3 h)"
    Vorbereitung und Erwartungswert ≈ 30 min · Dekoder für Ethernet, IPv4 und
    ICMP bis zu den ersten grünen Tests ≈ 60 min · UDP/TCP, Abschneide- und
    Fehlerfälle ≈ 45 min · `rnlab_l01_overhead()` ≈ 15 min · Messung am Board
    und Auswertung ≈ 30 min. Alles unter „Vertiefung“ ist freiwillig.
    Empfohlene Reihenfolge: `ctest … -L rnlab-L01 --output-on-failure` laufen
    lassen und die Tests von oben nach unten grün machen.

## Lernziele

Nach dem Versuch könnt ihr …

- einen Ethernet-II-Frame in die Header von Sicherungs-, Vermittlungs- und
  Transportschicht zerlegen und jedem Byte seine Schicht zuordnen,
- die Protokolle eines Frames dem **OSI-Modell** (7 Schichten) und dem
  **TCP/IP-Modell** (4 Schichten) zuordnen,
- einen Parser schreiben, der Längenfelder aus dem Paket (IHL, Gesamtlänge,
  Data Offset) nutzt, aber niemals über das Ende der empfangenen Bytes liest,
- die **Protokolleffizienz** eines Pings für beliebige Nutzdatenlängen
  vorhersagen – mit ausdrücklich benannten Overhead-Anteilen (Header,
  Padding, FCS, Präambel/SFD, Interframe Gap) – und am Board nachmessen.

## Theorie-Bezug (Skript 5.6, 5.9)

- **5.6 Encapsulation und Protokolleffizienz:** Vor die Nutzdaten
  (**Payload**) setzt jede Schicht ihre Steuerdaten (**Header**) –
  Encapsulation; der Empfänger trennt sie wieder ab – Decapsulation. Das
  Steuerfeld hat meist eine **feste** Größe, unabhängig von der Menge der
  Nutzdaten; deshalb hängt die Effizienz stark von der Nachrichtengröße ab.
  Das Skript beschreibt die Effizienz über das Verhältnis von Steuer- zu
  Nutzdaten; hier verwenden wir den gleichwertigen Anteil der Nutzdaten an
  allen übertragenen Bytes:

    **η = Nutzdaten / (Nutzdaten + Steuerdaten)**

- **5.9 Referenzmodelle:** Das ISO-OSI-Modell hat sieben Schichten; das
  TCP/IP-Modell fasst sie zu vier zusammen. Der Dekoder arbeitet genau
  entlang dieser Grenzen:

| TCP/IP-Modell | OSI-Schicht | im Frame | Header |
|---|---|---|---|
| Anwendung | 5–7 Sitzung, Darstellung, Anwendung | Nutzdaten (z. B. Telnet-Text) | – |
| Transport | 4 Transport | UDP, TCP | 8 B bzw. 20–60 B |
| Internet | 3 Vermittlung (Netzwerk) | IPv4, ICMP | 20–60 B, ICMP 8 B |
| Netzzugang | 2 Sicherung (+ 1 Bitübertragung) | Ethernet II, ARP | 14 B + 4 B FCS |

  ICMP wird zwar **in** IPv4 transportiert, gehört aber zur Vermittlungsschicht
  (es ist das Steuerprotokoll von IP). ARP sitzt zwischen den Schichten 2 und 3:
  Es wird direkt in Ethernet gekapselt und bildet IP- auf MAC-Adressen ab
  (Versuch 02). Präambel, SFD und die Pause zwischen Frames gehören zur
  Bitübertragungsschicht – sie tauchen in keinem Mitschnitt auf, belegen aber
  die Leitung.

## Versuchsaufbau

```text
 Rechner 192.168.33.10/24 ── Ethernet 100 Mbit/s ── ITS-Board 192.168.33.99/24
   ping, rnlab.py, Wireshark                          RX/TX-Hook -> rnlab_decode_frame()
                                                      Ring der letzten 16 Frames
```

- Setup **S1**, Firmware aus eurem Fork mit eurer Lösung.
- Wireshark auf der Board-Schnittstelle, Anzeigefilter `icmp || arp || udp`.
  Unter *Ansicht → Paketbytes* seht ihr dieselben Bytes wie im Board-Trace.
- Das Board zeichnet in seinem Ethernet-Treiber jeden Frame auf, den es
  empfängt (RX) oder an die Hardware übergibt (TX) – die Frames der
  Telnet-Sitzung zum Board (TCP-Port 4242) ausgenommen, damit sich
  `lab 01 trace` nicht selbst aufzeichnet.

## Versuchsablauf

1. Firmware-Aufgabe umsetzen (unten), Host-Tests grün, bauen, flashen.
2. `lab 01 help`, dann Aufzeichnung leeren und genau einen Ping schicken:

    ```bash
    python3 tools/rnlab.py lab 192.168.33.99 "lab 01 clear"
    python3 tools/rnlab.py ping 192.168.33.99 -c 1 -s 32
    python3 tools/rnlab.py lab 192.168.33.99 "lab 01 trace 2"
    ```

    Erwartete Ausgabe (Zeiten, MAC-Adressen, die IP-Adresse eures Rechners –
    am Referenzplatz `.1` statt `.10` – und die IP-Kennung sind bei euch anders):

    ```text
    > lab 01 trace 2
    #1 RX t=6279 ms  74 B  [ok]
      OSI 2   Ethernet II A0:CE:C8:61:5D:08 > EE:5A:76:56:F0:9B  Typ 0x0800  14 B
              ee 5a 76 56 f0 9b a0 ce c8 61 5d 08 08 00
      OSI 3   IPv4 192.168.33.1 > 192.168.33.99  TTL 64  Proto 1  Laenge 60  20 B
              45 00 00 3c 3c 58 00 00 40 01 7a b4 c0 a8 21 01
              c0 a8 21 63
      OSI 3   ICMP Echo Request (Typ 8, Code 0)  8 B
              08 00 52 14 50 53 00 00
              Daten 32 B
    #2 TX t=6279 ms  74 B  [ok]
      OSI 2   Ethernet II EE:5A:76:56:F0:9B > A0:CE:C8:61:5D:08  Typ 0x0800  14 B
              a0 ce c8 61 5d 08 ee 5a 76 56 f0 9b 08 00
      OSI 3   IPv4 192.168.33.99 > 192.168.33.1  TTL 255  Proto 1  Laenge 60  20 B
              45 00 00 3c 3c 58 00 00 ff 01 bb b3 c0 a8 21 63
              c0 a8 21 01
      OSI 3   ICMP Echo Reply (Typ 0, Code 0)  8 B
              00 00 5a 14 50 53 00 00
              Daten 32 B
    (CLI-Frames auf TCP 4242 nicht aufgezeichnet: 15)
    ```

    Vergleicht jede Byte-Zeile mit dem Paket in Wireshark. Wo steht die
    Gesamtlänge `0x003c` = 60? Wo das Protokoll `01`?

3. Nachdem ihr den Erwartungswert (unten) notiert habt: dasselbe mit 0, 64
   und 1472 Byte Daten (`python3 tools/rnlab.py ping 192.168.33.99 -c 1 -s 0`,
   entsprechend `-s 64` und `-s 1472`). Achtet bei 0 Byte auf
   die Länge des Frames im Trace (RX und TX) und in Wireshark.
4. Effizienz der Aufzeichnung und die Vorhersage des Boards:

    ```bash
    python3 tools/rnlab.py lab 192.168.33.99 "lab 01 eff"
    python3 tools/rnlab.py lab 192.168.33.99 "lab 01 eff 0" "lab 01 eff 64" "lab 01 eff 1472"
    ```

## Erwartungswert (vor der Messung notieren!)

Berechnet für einen Ping (ICMP Echo Request) mit **P = 0, 64 und 1472 Byte**
ICMP-Daten (`rnlab.py ping … -s P`) die folgende Tabelle. Legt vorher fest und schreibt
auf, **was ihr als Overhead zählt**; hier gilt:

- **Nutzdaten** = nur das ICMP-Datenfeld (P Byte).
- **Header** = Ethernet 14 B + IPv4 20 B (ohne Optionen) + ICMP 8 B.
- **Padding**: Ein Ethernet-Frame ist ohne FCS mindestens 60 B lang; kürzere
  füllt der Sender mit Nullen auf.
- **FCS** 4 B (Prüfsumme am Frame-Ende).
- **Präambel + SFD** 8 B und **Interframe Gap** 12 B (96 Bitzeiten Pause):
  keine Frame-Bytes, belegen die Leitung aber genauso lange.
- Kein VLAN-Tag.

Zwei Effizienzen:

- **η_Rahmen** = P / (Frame inkl. Padding und FCS) – was ein Mitschnitt mit
  FCS zeigen würde,
- **η_Draht** = P / (Frame + Präambel/SFD + Interframe Gap) – der Anteil der
  Leitungszeit, der Nutzdaten trägt.

| P | IPv4-Paket | Padding | Frame inkl. FCS | auf dem Draht | η_Rahmen | η_Draht |
|---|---|---|---|---|---|---|
| 0 B | | | | | | |
| 64 B | | | | | | |
| 1472 B | | | | | | |

!!! question "Kurz nachgedacht"
    - Ab welcher Nutzdatenlänge P fällt kein Padding mehr an?
    - Warum ist 1472 die größte Nutzdatenlänge, die noch in **einen** Frame
      passt? Was passiert bei 1473?
    - Wie viele Frames pro Sekunde passen bei P = 1472 höchstens auf eine
      100-Mbit/s-Leitung, und welcher Nutzdatendurchsatz folgt daraus?
    - Das Skript nennt das Verhältnis **Steuerdaten : Nutzdaten**. Wie groß ist
      es für P = 64, und wie hängt es mit η zusammen?

## Experiment (Firmware-Aufgabe)

Dateien in eurem Fork (Branch `praktikum/start`):

- [`apps/rnlab/src/l01_schichten_kapselung_logic.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/l01_schichten_kapselung_logic.c)
  mit Header
  [`l01_schichten_kapselung_logic.h`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/l01_schichten_kapselung_logic.h):
  reine Logik ohne lwIP, **hier arbeitet ihr** (beide Stellen `TODO(L01)`).
- [`apps/rnlab/src/l01_schichten_kapselung.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/l01_schichten_kapselung.c):
  Board-Integration, fertig. `rnlab_l01_hook_rx_frame()` und
  `rnlab_l01_hook_tx_frame()` rufen für jeden Frame euren Dekoder auf und
  legen Ergebnis und die ersten 64 Byte in einem Ring der letzten 16 Frames ab;
  die Befehle `lab 01 trace`, `eff` und `clear` geben ihn aus.
- [`tests/unit/test_rnlab_l01.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/tests/unit/test_rnlab_l01.c):
  32 Unity-Tests mit **echten, mitgeschnittenen Frames** (ARP, Ping 0/64 B,
  UDP, ICMP Port Unreachable, TCP-SYN mit Optionen, …), gezielt beschädigten
  Varianten und jeder möglichen Abschneidelänge.

| Funktion | Aufgabe |
|---|---|
| `bool rnlab_decode_frame(const uint8_t* frame, size_t len, rnlab_frame_info_t* info)` | `frame` (ab Ziel-MAC, ohne FCS) Schicht für Schicht in `info` zerlegen; liefert `true` genau bei `info->status == RNLAB_L01_OK` |
| `bool rnlab_l01_overhead(const rnlab_frame_info_t* info, rnlab_l01_overhead_t* out)` | Nutzdaten, Header, Padding, Frame (≥ 64 B inkl. FCS), Draht (+ 20 B) und beide Effizienzen in 0,01 % |

`rnlab_frame_info_t` hält je Schicht, **wo** ihr Header im Frame beginnt
(`net_off`, `upper_off`, `payload_off`) und **wie lang** er ist
(`eth_hdr_len`, `net_hdr_len`, `upper_hdr_len`), dazu die wichtigsten Felder
(MAC- und IP-Adressen, EtherType, TTL, Protokoll, Ports, ICMP-Typ,
TCP-Flags) und die Zahl der Füllbytes (`pad_len`). Für jeden korrekt
dekodierten Frame gilt:

```text
frame_len = eth_hdr_len + net_hdr_len + upper_hdr_len + payload_len + pad_len
```

Anforderungen an `rnlab_decode_frame()`:

- **Ethernet II:** unter 14 B → `RNLAB_L01_ERR_TRUNC_ETH`. EtherType
  `0x0800` → IPv4, `0x0806` → ARP (das ganze 28-B-Paket ist Header, keine
  Nutzdaten), alles andere (IPv6, VLAN-Tag `0x8100`, …) →
  `RNLAB_L01_NET_OTHER`, der Rest des Frames gilt als Nutzdaten.
- **IPv4:** Version 4, **IHL** (Headerlänge in 32-Bit-Worten, ≥ 5),
  Gesamtlänge ≥ Headerlänge, sonst `RNLAB_L01_ERR_BAD_NET`. Das Paketende
  bestimmt die **Gesamtlänge**, nicht die Frame-Länge: Die Bytes dahinter sind
  Padding. Header kürzer als 20 B bzw. als IHL angibt →
  `RNLAB_L01_ERR_TRUNC_NET`; Gesamtlänge größer als der Rest des Frames →
  `RNLAB_L01_ERR_TRUNC_PAYLOAD` (Header bleiben dekodiert, `payload_len` =
  was tatsächlich da ist).
- **ICMP** (8 B), **UDP** (8 B, Länge ≥ 8), **TCP** (Data Offset · 4 ≥ 20 B,
  Optionen!). Abgeschnitten → `RNLAB_L01_ERR_TRUNC_UPPER`, ungültig →
  `RNLAB_L01_ERR_BAD_UPPER`, ein Fragment mit Offset ≠ 0 hat gar keinen
  Transport-Header.
- Nie außerhalb von `frame[0 .. len-1]` lesen. Was bis zum Fehler dekodiert
  wurde, bleibt in `info` stehen – der Trace zeigt dann die heilen Schichten
  und den Grund des Abbruchs.

```bash
cmake --build build/host && ctest --test-dir build/host -L rnlab-L01 --output-on-failure
```

Solange die Aufgabe offen ist, sind 29 der 32 Tests rot, und `lab 01 trace`
zeigt nur `[nicht dekodiert]` mit den rohen ersten Bytes – so seht ihr auf dem
Board sofort, ob euer Dekoder läuft.

??? example "Vertiefung (optional): 802.1Q"
    Ein VLAN-Tag schiebt 4 Byte zwischen Quell-MAC und EtherType
    (`0x8100`, 2 B Tag Control, dann der eigentliche EtherType). Erweitert den
    Dekoder so, dass er ein Tag überspringt. Wie ändern sich dann die
    Mindest-Nutzdaten ohne Padding und η für P = 1472?

## Auswertung

1. Tragt die Werte aus `lab 01 eff` neben eure Vorhersage. Stimmen sie
   überein? Wenn nicht: welcher Overhead-Anteil fehlt oder ist doppelt?
2. Beim Ping mit 0 Byte: Welche Länge zeigt Wireshark für den Echo Request
   eures Rechners, welche das Board im RX-Trace? Welche Länge hat die Antwort
   im TX-Trace des Boards und in Wireshark? Erklärt den Unterschied
   (Stichwort: **wo** wird aufgefüllt, und wo wird mitgeschnitten?).
3. `lab 01 eff` summiert am Ende über alle Frames. Warum ist die
   Gesamteffizienz **nicht** der Mittelwert der Einzelwerte?

??? example "Vertiefung (optional): Transportschicht sichtbar machen"
    Ein UDP-Datagramm an einen Port, an dem niemand lauscht, zeigt Schicht 4
    und die Antwort des Boards:

    ```bash
    python3 tools/rnlab.py udp-send 192.168.33.99 7007 -n 1 --size 18
    python3 tools/rnlab.py lab 192.168.33.99 "lab 01 trace 2"
    ```

    Ordnet jede Zeile des Traces einer Schicht des TCP/IP-Modells zu. Was
    antwortet das Board, und zu welcher Schicht gehört diese Antwort?

??? example "Vertiefung (optional): Kleine Pakete"
    Nach 5.6 lohnen große Nachrichten – warum schicken Sprach- und
    Videoanwendungen trotzdem oft kleine Pakete?

??? example "Vertiefung (optional): Warum war ein empfangener Frame 4 B länger?"
    Bei der ersten Referenzmessung (Firmware vor `praktikum/start` 41d52e9)
    war jeder **empfangene** Frame genau 4 Byte länger als der gesendete Frame
    desselben Pings, obwohl beide dasselbe IPv4-Paket trugen. Der Dekoder
    zeigte die 4 Byte hinter dem IPv4-Paket als „Padding“, und `lab 01 eff`
    lieferte für empfangene Frames eine etwas zu kleine Effizienz.

    1. Welches Feld des Ethernet-Frames ist genau 4 Byte lang und steht am Ende?
    2. Der STM32-MAC kann es beim Empfang entfernen. Das Bit `APCS` im
       Register `ETH_MACCR` tut das laut Referenzhandbuch (RM0090) aber nur
       für Frames, deren Längen-/Typfeld ≤ 1500 ist. Was steht bei unseren
       Frames in diesem Feld – und was unterscheidet einen IEEE-802.3-Frame
       mit **Längenfeld** von einem **Ethernet-II**-Frame mit **Typfeld**?
    3. Für Ethernet II gibt es das Bit `CSTF`. Wo in
       `targets/itsboard/hal/hal_eth_mac.c` wird es gesetzt?

--8<-- "issue-feedback.md"

## Potenzielle Herausforderungen

- **Byte-Reihenfolge:** Alle Mehrbyte-Felder stehen im Frame big-endian
  (Netz-Byte-Reihenfolge). `rnlab_l01_be16()` ist vorbereitet; ein Cast auf
  `uint16_t*` liefert auf dem Board die vertauschte Zahl – und kann auf
  ungerader Adresse sogar abstürzen.
- **IHL und Data Offset** zählen in 32-Bit-Worten, nicht in Byte.
- **Padding ist kein Header:** Ein aufgefüllter 60-B-Frame hat hinter dem
  IPv4-Paket Nullen. Wer das Paketende aus der Frame-Länge ableitet, zählt sie
  als TCP-Optionen oder Nutzdaten. Der Test `test_padding_is_not_a_header`
  prüft genau das.
- **Abgeschnittene Frames:** `test_every_truncation_of_tcp_syn` ruft euren
  Dekoder mit jeder Länge von 0 bis 77 Byte auf. Prüft jede Länge, **bevor**
  ihr ein Feld lest.
- **Nichts im Trace?** Frames der Telnet-Sitzung (Port 4242) werden bewusst
  nicht aufgezeichnet, und der Ring hält nur 16 Frames: erst `lab 01 clear`,
  dann den Verkehr erzeugen, dann `lab 01 trace`.
- **Bytes hinter dem IPv4-Paket:** Mindestframes kommen aufgefüllt an
  (60 B), und je nach Treiber können weitere Bytes hinter dem Paket stehen
  (siehe Vertiefung in der Auswertung). Bestimmt das Paketende deshalb immer aus der
  IPv4-Gesamtlänge; `test_trailing_fcs_stays_behind_the_packet` prüft das.
- **`..` in den Header-Bytes:** Das Board speichert nur die ersten 64 Byte
  eines Frames; längere Header (IPv4- oder TCP-Optionen) werden abgeschnitten
  angezeigt, dekodiert werden sie trotzdem vollständig.

## Quellen

- RN-Skript, Kap. 5.6 (Encapsulation und Protokolleffizienz) und 5.9
  (Referenzmodelle).
- IEEE 802.3, Abschn. 3 (MAC-Frame, Mindestlänge, FCS) und 4.4 (Interframe Gap).
- RFC 894 – IP über Ethernet; RFC 791 – IPv4; RFC 792 – ICMP; RFC 768 – UDP;
  RFC 9293 – TCP; RFC 826 – ARP.
- ISO/IEC 7498-1 – OSI-Referenzmodell; RFC 1122, Abschn. 1.1.3 – die Schichten
  der Internet-Architektur.
