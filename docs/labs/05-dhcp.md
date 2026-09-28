# 05 · DHCP

<a class="md-button" href="../../pdf/05-dhcp.pdf">:material-file-pdf-box: Als PDF herunterladen</a>

!!! info "Termin T06 · Setup S2"
    Dieser Versuch läuft im Netz-Setup **S2 – Internetfreigabe**
    (siehe [Netz-Setup](../reference/netz-setup.md#s2-internetfreigabe)).

--8<-- "konventionen.md"

Bisher hatte das Board eine feste Adresse. Ab heute holt es sie sich selbst:
Euer Rechner teilt seinen Internetzugang und ist damit DHCP-Server für das
Board. Ihr schaut dem Board dabei zu, und zwar von beiden Seiten des Kabels:
in Wireshark und mit einem Protokoll, das das Board selbst von jeder
DHCP-Nachricht mit Zeitstempel führt. So seht ihr nicht nur die vier
Schritte aus der Vorlesung, sondern auch, was davor, dazwischen und danach
passiert: Wiederholungen mit wachsenden Abständen, eine Adressprüfung per ARP
und die Uhr, die bis zur Verlängerung der Lease läuft.

## Lernziele

Nach dem Versuch könnt ihr …

- den DORA-Ablauf (DISCOVER, OFFER, REQUEST, ACK) mit Absender, Empfänger,
  Broadcast/Unicast und Transaktionsnummer (`xid`) in einem Mitschnitt
  zeigen und erklären,
- eine DHCP-Nachricht (BOOTP-Kopf, Magic Cookie, Optionen) byteweise
  zerlegen und robust gegen fehlerhafte Eingaben parsen,
- T1 und T2 aus der Lease berechnen und begründen, warum ein Client vor
  Ablauf der Lease zweimal versucht zu verlängern,
- das Wiederholungsverhalten (Backoff) eines Clients ohne Server messen
  und mit RFC 2131 vergleichen,
- erklären, warum zwischen ACK und nutzbarer Adresse Sekunden vergehen
  (Address Conflict Detection),
- einschätzen, was ein zweiter (falscher) DHCP-Server im selben Netz
  anrichtet.

## Theorie-Bezug (Skript 5.22)

- **DHCP** verteilt Adresse, Netzmaske, Gateway, DNS-Server und mehr
  zentral und automatisch. Server lauschen auf **UDP-Port 67**, Clients auf
  **68**. UDP mit Broadcast ist zwingend: Der Client hat noch keine Adresse,
  mit der er eine Verbindung aufbauen könnte.
- **Vier Schritte:** (1) DISCOVER – der Client sucht einen Server, (2) OFFER
  – ein Server bietet eine Adresse an, (3) REQUEST – der Client fordert
  genau dieses Angebot an (und lehnt damit alle anderen ab), (4) ACK – der
  Server bestätigt.
- **Lease:** Die Adresse gilt nur für eine Lease-Zeit. Nach der Hälfte
  (**T1**) versucht der Client, sie beim selben Server zu verlängern; RFC 2131
  ergänzt einen zweiten Zeitpunkt **T2** (7/8 der Lease), ab dem er jeden
  Server fragt. Bekommt er bis zum Ende keine Verlängerung, beginnt alles
  von vorn.
- **Freigabe (RELEASE):** Der Client kann die Adresse zurückgeben.
- **Sicherheit:** DHCP hat keine Authentifizierung. Ein Angreifer, der schneller
  antwortet als der echte Server, verteilt falsche Gateways und DNS-Server
  (Man-in-the-Middle). Im Versuch seht ihr, was schon ein harmloser zweiter
  Server auslöst.

## Versuchsaufbau

```
 Internet ── WLAN ── Rechner (Internetfreigabe) ── Ethernet ── ITS-Board
                     DHCP-Server, DNS-Weiterleiter, NAT       DHCP-Client (lwIP)
                     macOS 192.168.2.1 / Windows 192.168.137.1 / Linux 10.42.0.1
```

- Setup **S2** nach [Netz-Setup](../reference/netz-setup.md#s2-internetfreigabe):
  Internetfreigabe auf den Board-Adapter, eine noch gesetzte S1-Adresse vorher
  entfernen.
- **Wireshark** auf der Board-Schnittstelle (macOS: meist `bridge100`), Filter
  `udp.port == 67 || udp.port == 68 || arp`.
- **[Serielle Konsole](../reference/serielle-konsole.md)** des Boards. Mit DHCP ändert sich die
  Adresse des Boards, eine Telnet-Verbindung auf die alte Adresse reißt ab.
  Die `lab`-Befehle gehen deshalb am sichersten über die serielle Konsole. Wer
  per Telnet arbeitet, holt sich die neue Adresse mit `lab info` und verbindet
  neu, z. B. `python3 tools/rnlab.py lab <board-ip> "lab 05 log"` (Windows:
  `py tools\rnlab.py …`; siehe
  [`rnlab.py lab`](../reference/rnlab-tool.md#lab-telnet)).

!!! info "Werkzeug: `lab 05`"
    | Befehl | Wirkung |
    |---|---|
    | `lab 05 log` | jede DHCP-Nachricht, die das Board sendet (`tx`) oder empfängt (`rx`), mit Zeit in ms seit Reset und Abstand zur vorigen Zeile |
    | `lab 05 log clear` | Protokoll leeren |
    | `lab 05 dhcp` | lwIPs Zustand und Lease-Zeiten neben dem, was euer Parser aus dem letzten ACK gelesen hat, dazu die Restzeiten |
    | `lab 05 renew` | sofort verlängern (wie bei Ablauf von T1) |
    | `lab 05 ignore <ip>` / `all` / `off` | Antworten dieses Servers (bzw. aller) verwerfen, bevor lwIP sie sieht; im Protokoll als `rx*` |

    Die `xid` wählt das Board bei jedem Start zufällig. Eure `xid`s,
    Adressen und Zeitstempel weichen deshalb von allen Beispielen auf dieser
    Seite ab.

## Versuchsablauf

1. Firmware-Aufgabe umsetzen, Host-Tests grün, flashen (Abschnitt
   *Experiment*).
2. **Erwartungswerte** notieren (nächster Abschnitt).
3. **A – DORA.** Wireshark starten, dann auf der Konsole:

    ```text
    lab 05 log clear
    lab net dhcp
    lab 05 log
    lab 05 dhcp
    lab info
    ```

    Ordnet jede Zeile von `lab 05 log` einem Paket in Wireshark zu. Notiert
    je Nachricht: Quell-/Ziel-IP, Broadcast-Flag, `xid`, Optionen 53, 50, 51,
    54, 1, 3, 6.
4. **B – nach dem ACK.** Sucht in Wireshark die ARP-Pakete **nach** dem ACK.
   Wer sendet sie, mit welcher Absender-IP, in welchen Abständen? Ab wann zeigt
   `lab info` die Adresse, ab wann antwortet das Board auf `ping`?
5. **C – Verlängern.**

    ```text
    lab 05 log clear
    lab 05 renew
    lab 05 log
    lab 05 dhcp
    ```

    Vergleicht den REQUEST mit dem aus A (Ziel-IP, `ciaddr`, Option 50/54).
6. **D – ohne Server (Backoff).** Das Board soll keinen Server hören:

    ```text
    lab 05 log clear
    lab 05 ignore all
    lab net dhcp
    ```

    Gut 2 Minuten warten, dann `lab 05 log` und `lab 05 dhcp`. Die
    Server-Antworten stehen als `rx*` im Protokoll, lwIP sieht sie nicht.
    Danach `lab 05 ignore off` und `lab net dhcp`.
7. **E – Lease-Zeiten (optional).** Lest aus `lab 05 dhcp` die Lease eures Servers ab und
   vergleicht sie mit einem Kommilitonen, der ein anderes Betriebssystem
   nutzt.

## Erwartungswert (vor der Messung notieren!)

**1. DORA-Zeitverlauf.** Welche der vier Nachrichten gehen als Broadcast
(`255.255.255.255`), welche als Unicast, und warum? Das Board verarbeitet
empfangene Frames nur, wenn seine Hauptschleife `cads_net_poll()` aufruft;
aus Versuch 04 kennt ihr die Periode *T* dieser Schleife im Menü. Ein Server
auf eurem Rechner antwortet nach etwa 1–2 ms. Schätzt:

- wann (relativ zum DISCOVER) das Board das OFFER **sieht** (frühestens,
  spätestens),
- wie lange DORA im Protokoll des Boards insgesamt dauert,
- wie lange es auf dem Kabel (Wireshark) dauert.

**2. T1 und T2.** Für eine Lease *L* ohne Optionen 58/59 gilt
T1 = ½·*L*, T2 = ⅞·*L*. Rechnet für *L* = 3600 s und *L* = 86 400 s. lwIP führt
diese Zeiten nicht sekundengenau: In
[`lib/lwip/src/core/ipv4/dhcp.c`](https://github.com/lwip-tcpip/lwip/blob/STABLE-2_2_1_RELEASE/src/core/ipv4/dhcp.c)
setzt `SET_TIMEOUT_FROM_OFFERED` sie in Ticks des Grobtimers um
(`DHCP_COARSE_TIMER_SECS`). Welche Tickwerte zeigt `lab 05 dhcp` für T1, T2
und die Lease? Wie genau verlängert lwIP also bei einer Lease von 90 s?

**3. Adressprüfung.** lwIP prüft eine neue Adresse nach RFC 5227, bevor es
sie benutzt. Die Konstanten stehen in `lib/lwip/src/include/lwip/prot/acd.h`:
`PROBE_WAIT` (zufällig 0 … 1 s), dann `PROBE_NUM` ARP-Proben im Abstand
`PROBE_MIN` … `PROBE_MAX`, dann `ANNOUNCE_WAIT`. Wie viel Zeit vergeht
mindestens, höchstens und im Mittel zwischen ACK und nutzbarer Adresse?

**4. Backoff ohne Server.** RFC 2131 (Abschn. 4.1) empfiehlt für die
Wiederholung eines DISCOVER 4 s, danach jeweils das Doppelte bis höchstens 64 s (4, 8, 16, 32, 64 s), jeweils ±1 s zufällig.
lwIP rechnet mit `DHCP_REQUEST_BACKOFF_SEQUENCE(tries)` in derselben Datei.
Sagt die Abstände der ersten sieben DISCOVER voraus. Beachtet: Der
Feintimer von lwIP tickt alle `DHCP_FINE_TIMER_MSECS`. Was bedeutet das für
den ersten Abstand?

## Experiment (Firmware-Aufgabe)

Dateien in eurem Fork (Branch `praktikum/start`, gleiche Pfade im eigenen Repository; die Links zeigen auf die Vorlage):

- [`apps/rnlab/src/l05_dhcp_logic.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/l05_dhcp_logic.c)
  mit [`l05_dhcp_logic.h`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/l05_dhcp_logic.h):
  reine Logik, **hier arbeitet ihr** (`TODO(L05)`). Der Kopfkommentar der
  `.h` zeigt den Aufbau einer DHCP-Nachricht mit allen Offsets.
- [`apps/rnlab/src/l05_dhcp.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/l05_dhcp.c):
  Hooks und Befehle, fertig.
- [`tests/unit/test_rnlab_l05.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/tests/unit/test_rnlab_l05.c):
  die Spezifikation. Die Frames darin sind echte Mitschnitte vom Laborplatz.

| Funktion | Aufgabe |
|---|---|
| `bool rnlab_l05_parse(const uint8_t* msg, size_t len, rnlab_dhcp_msg_t* out)` | DHCP-Nachricht (UDP-Nutzdaten ab `op`) prüfen und zerlegen: Mindestlänge 240 B, `op` 1/2, Magic Cookie `99.130.83.99`, dann die Optionsliste (Code, Länge, Wert; 0 = Pad, 255 = Ende). Übernehmen: 53, 51, 58, 59, 1, 3, 6, 50, 54. Unbekannte Optionen überspringen, unmögliche Längen und Optionen über das Ende hinaus → `false`; ohne Option 53 ist es kein DHCP → `false`. |
| `bool rnlab_l05_timers(const rnlab_dhcp_msg_t* msg, uint32_t* t1_s, uint32_t* t2_s)` | T1/T2 nach RFC 2131 §4.4.5: Optionen 58/59, sonst ½ und ⅞ der Lease (abgerundet); unendliche Lease (`0xFFFFFFFF`) → beide unendlich; ohne Lease → `false`. |

Fertig vorgegeben sind `rnlab_l05_find_dhcp()` (findet die DHCP-Nachricht
in einem Ethernet-Frame) und `rnlab_l05_type_name()`.

**So kommen die Nachrichten zu eurem Parser.** Der Netztreiber ruft für jeden
empfangenen und jeden gesendeten Frame die Hooks `rnlab_l05_hook_rx_frame()`
und `rnlab_l05_hook_tx_frame()` auf. Sie stempeln die Zeit
(`cads_hal_ticks_ms()`), suchen die DHCP-Nachricht und geben sie an
`rnlab_l05_parse()`. Die `xid` liest der Hook selbst, deshalb seht ihr die
Wiederholungen schon vor eurer Implementierung. Die Typen (`?`) und
`lab 05 dhcp` → „Eigener Parser“ brauchen euren Code. `lab 05 ignore` sitzt im
Hook `rnlab_l05_hook_rx_drop()`: Er verwirft Server-Antworten (`op` 2) nach
IP-Absender, bevor lwIP sie sieht.

```bash
cmake --build build/host && ctest --test-dir build/host -L rnlab-L05 --output-on-failure
```

!!! warning "Die Bytes kommen aus dem Netz"
    Jeder Zugriff auf `msg[i]` braucht vorher die Prüfung `i < len`. Eine
    Option, die „4 Byte“ behauptet, aber hinter dem Ende liegt, darf euren
    Parser nicht aus dem Puffer lesen lassen: So entstehen echte
    Sicherheitslücken in DHCP-Clients. Die Tests enthalten solche Nachrichten.

??? example "Vertiefung (optional): 7/8 in 32 Bit"
    lwIP rechnet T2 als `(offered_t0_lease * 7U) / 8U` in 32 Bit. Ab welcher
    Lease läuft das über, und welches T2 käme dann heraus? Der Test
    `test_timers_large_lease_does_not_overflow` verlangt es richtig.

## Auswertung

1. Zeichnet das Weg-Zeit-Diagramm von DORA mit euren Zeiten aus
   `lab 05 log` **und** aus Wireshark. Wo liegen die Unterschiede, und
   woher kommen sie (Erwartungswert 1)?
2. Welche Nachricht verrät dem Server, dass das Board sein Angebot annimmt,
   welche den **anderen** Servern, dass es ihres ablehnt? Belegt es mit
   Option 54.
3. Stimmen T1/T2 eures Parsers mit lwIPs Werten (`lab 05 dhcp`) überein? Rechnet
   die Tickwerte nach.
4. Wie lange dauerte es vom ACK bis zur ersten ARP-Ankündigung
   („who-has *eigene IP* tell *eigene IP*“)? Liegt das im erwarteten Fenster?
   Warum fragt das Board mit Absender `0.0.0.0`?
5. Vergleicht den REQUEST beim Verlängern (C) mit dem aus A. Warum ist er
   Unicast, und warum fehlen Option 50 und 54?
6. Tragt die gemessenen DISCOVER-Abstände (D) neben RFC 2131 und eure
   Vorhersage für lwIP. Was spricht für und gegen die Zufallskomponente
   des RFC, wenn nach einem Stromausfall 200 Geräte gleichzeitig starten?

??? example "Vertiefung (optional): zwei DHCP-Server, zwei Subnetze, ein Kabel"
    Was passiert, wenn auf demselben Ethernet-Segment **zwei** Server (oder ein
    Server mit zwei Adresspools für zwei Subnetze) auf jedes DISCOVER antworten?
    Die Betreuung kann das an einem Platz nachstellen, z. B. mit einer zweiten
    Freigabe auf demselben Switch.

    1. **Vorhersage:** Welches OFFER nimmt der Client? Was antwortet der Server,
       dessen Pool nicht zum angeforderten Subnetz passt, auf den REQUEST? Was
       tut lwIP nach einem NAK? Lest `dhcp_handle_nak()` in `dhcp.c` und
       vergleicht mit RFC 2131 Abschn. 3.1 Schritt 5 / 4.4.
    2. **Messung:** `lab 05 log clear`, `lab net dhcp`, nach 3 s `lab 05 log`;
       Wireshark-Statistik *Statistiken → Konversationen* bzw. Paketzahl über
       60 s.
    3. **Abhilfe:** `lab 05 ignore <ip des falschen Servers>`; im Netz selbst:
       DHCP-Snooping am Switch, nur ein Server je Segment.

--8<-- "issue-feedback.md"

## Potenzielle Herausforderungen

- **Board bekommt keine Adresse, `lab 05 log` zeigt nur DISCOVER:** Die
  Freigabe ist nicht auf dem Board-Adapter aktiv, oder eine lokale Firewall
  blockiert Port 67 (Linux: firewalld/ufw, siehe
  [Netz-Setup](../reference/netz-setup.md#s2-internetfreigabe)). Prüft in
  Wireshark, ob überhaupt ein OFFER kommt.
- **DHCP-Sturm: DISCOVER, OFFER, REQUEST, NAK alle ≈ 10 ms, keine Adresse:**
  Zwei DHCP-Server bzw. zwei Adresspools im selben Segment (Freigabe doppelt,
  zweiter Adapter, Router am selben Switch). Das unveränderte lwIP startet nach
  einem NAK ohne Pause neu; am Laborplatz gemessen: ≈ 228 DHCP-Pakete/s (siehe
  Vertiefung). Die Praktikums-Firmware wartet nach wiederholten NAKs länger,
  `lab info` zählt sie unter `dhcp_naks`. `lab 05 log` zeigt nur die letzten
  24 Nachrichten. Einen Server abschalten oder mit `lab 05 ignore <ip>` wählen.
- **`lab 05 ignore all` vergessen:** Das Board bekommt nie wieder eine
  Adresse, bis `lab 05 ignore off` (oder ein Reset).
- **Telnet hängt nach `lab net dhcp`:** Die Adresse hat sich geändert. Neue
  Adresse mit `lab info` über die serielle Konsole holen.
- **Typ `?` im Protokoll, „Eigener Parser: noch kein ACK erkannt“:**
  `rnlab_l05_parse()` liefert noch `false`. Erst die Host-Tests grün machen.
- **Bytereihenfolge:** Alle Felder sind big-endian. Eine `xid 0x1a2b3c4d`
  steht im Frame als `1a 2b 3c 4d`.
- **T1 wird nie erreicht:** Bei 3600 s Lease dauert das 30 min. Für den
  Versuch nehmt ihr `lab 05 renew`.

## Quellen

- RN-Skript, Kap. 5.22 (DHCP).
- RFC 2131 – Dynamic Host Configuration Protocol (Abschn. 3.1 Ablauf, 4.1
  Wiederholungen, 4.4.5 T1/T2).
- RFC 2132 – DHCP Options and BOOTP Vendor Extensions (Optionen 1, 3, 6, 50,
  51, 53, 54, 58, 59).
- RFC 951 – Bootstrap Protocol (BOOTP-Kopf).
- RFC 5227 – IPv4 Address Conflict Detection.
- lwIP: `src/core/ipv4/dhcp.c` (`DHCP_REQUEST_BACKOFF_SEQUENCE`,
  `SET_TIMEOUT_FROM_OFFERED`, `dhcp_handle_nak`), `src/core/ipv4/acd.c`,
  `src/include/lwip/prot/acd.h`.
