# 06 · DNS & NAT

<a class="md-button" href="../../pdf/06-dns-nat.pdf">:material-file-pdf-box: Als PDF herunterladen</a>

!!! info "Termin T07 · Setup S2"
    Dieser Versuch läuft im Netz-Setup **S2 – Internetfreigabe**
    (siehe [Netz-Setup](../reference/netz-setup.md#s2-internetfreigabe)).

--8<-- "konventionen.md"

Seit Versuch 05 hat das Board eine Adresse aus eurem Netz und einen
DNS-Server. Heute fragt es ihn: `lab 06 resolve api.open-meteo.com`. Der
erste Aufruf braucht einige Millisekunden, der zweite keine, und es geht
dabei kein einziges Paket über das Kabel. Ihr messt, wo die Zeit bleibt,
wie lange die Antwort gilt (TTL), und zerlegt die Antwort selbst: DNS packt
Namen mit Zeigern zusammen, und ein Parser, der diesen Zeigern blind folgt,
lässt sich mit einem einzigen Paket in eine Endlosschleife schicken. Im
zweiten Teil schaut ihr eurem Rechner beim Übersetzen zu: Mit welcher
Adresse und welchem Port kommt die Anfrage des Boards im Internet an?

## Lernziele

Nach dem Versuch könnt ihr …

- Aufbau einer DNS-Nachricht (Header, Frage, Resource Records) erklären und
  Größen von Anfrage und Antwort vorab berechnen,
- Namenskompression (RFC 1035 §4.1.4) lesen und einen Parser schreiben, der
  auf jeder Eingabe terminiert und nie außerhalb des Puffers liest,
- den Zeitbedarf einer Auflösung (erste Anfrage vs. Cache) vorhersagen und
  messen,
- die Wirkung der TTL auf Caches beobachten und die Grenzen eines sehr
  kleinen Caches (lwIP, ein Eintrag) begründen,
- in Wireshark zeigen, wie eine NAT/PAT-Box Quelladresse und Quellport
  umschreibt, und einen DNS-Weiterleiter von einer NAT unterscheiden.

## Theorie-Bezug (Skript 5.21, 5.23)

- **DNS** (5.23) ist eine hierarchische, verteilte Datenbank. Der Resolver
  des Boards ist ein **Stub-Resolver**: Er fragt einen rekursiven Server (hier
  euren Rechner bzw. dessen Resolver) und bekommt einen fertigen **Resource
  Record** (Name, Typ, Klasse, **TTL**, Daten). Typ **A** trägt eine
  IPv4-Adresse, **CNAME** einen anderen Namen.
- **Caching:** Die TTL sagt, wie lange ein RR gespeichert werden darf. Jeder
  Cache auf dem Weg (Board, Rechner, Provider) zählt sie herunter.
- **NAT/PAT** (5.21): Die NAT-Box setzt private Adressen auf ihre öffentliche
  Adresse um. PAT übersetzt zusätzlich die **Ports**, damit viele Geräte eine
  öffentliche Adresse gleichzeitig nutzen können. Dafür führt sie eine
  Übersetzungstabelle und muss Prüfsummen neu berechnen. Die Ende-zu-Ende-
  Sicht geht verloren: Der Server sieht nur die NAT-Box.
- Eure Internetfreigabe ist genau so eine Box: DHCP-Server (Versuch 05),
  **DNS-Weiterleiter** und **NAT-Router** in einem.

## Versuchsaufbau

```
 ITS-Board ─ Ethernet ─ Rechner ─ WLAN ─ Router ─ Internet ─ Resolver (z. B. 1.1.1.1)
 192.168.2.x            192.168.2.1     öffentl./private Adresse des Rechners
 Stub-Resolver (lwIP)   DNS-Weiterleiter + NAT
```

- Setup **S2** wie in Versuch 05, Board mit `lab net dhcp`. `lab info` zeigt
  unter `dns:` die Adresse eures Rechners.
- **Wireshark zweimal**: auf der Board-Schnittstelle (macOS meist
  `bridge100`) **und** auf der Internet-Schnittstelle (meist WLAN), Filter
  `dns`.
- Befehle per [serieller Konsole](../reference/serielle-konsole.md) oder per
  Telnet auf die Adresse aus `lab info`:
  `python3 tools/rnlab.py lab <board-ip> "lab 06 resolve …"` (Windows:
  `py tools\rnlab.py …`; siehe
  [`rnlab.py lab`](../reference/rnlab-tool.md#lab-telnet)). Während lwIP auf eine Antwort wartet, gibt `lab 06 resolve` alle
  300 ms einen Punkt aus.

!!! info "Werkzeug: `lab 06`"
    | Befehl | Wirkung |
    |---|---|
    | `lab 06 resolve <name>` | Auflösung über lwIP (`dns_gethostbyname()`): Ergebnis, Gesamtzeit, Netzzeit (Anfrage → Antwort am Treiber), Quellport und ID der Anfrage, TTL laut eurem Parser |
    | `lab 06 cache` | alle Antworten, die euer Parser gelesen hat, mit TTL und Restzeit |
    | `lab 06 last` | die letzte Antwort Feld für Feld |
    | `lab 06 server [ip]` | DNS-Server anzeigen bzw. setzen (Standard: per DHCP) |

    Quellport und DNS-ID wählt das Board für jede Anfrage zufällig: Eure Werte
    weichen von allen Beispielen auf dieser Seite ab.

## Versuchsablauf

1. Firmware-Aufgabe umsetzen, Host-Tests grün, flashen.
2. **Erwartungswerte** notieren (nächster Abschnitt). Dazu vom Rechner aus
   messen: `python3 tools/rnlab.py ping 1.1.1.1 -c 10` sowie zweimal
   hintereinander `nslookup api.open-meteo.com 1.1.1.1` (auf allen drei
   Betriebssystemen vorhanden).
3. **A – erste Auflösung und Cache.**

    ```text
    lab net dhcp
    lab info
    lab 06 resolve api.open-meteo.com
    lab 06 resolve api.open-meteo.com
    lab 06 last
    lab 06 cache
    ```

    Zählt in Wireshark (Board-Seite) die DNS-Pakete je Aufruf. Vergleicht
    Größe und ID mit `lab 06 last`.
4. **B – ein Cache mit einem Platz.**

    ```text
    lab 06 resolve example.com
    lab 06 resolve api.open-meteo.com
    lab 06 resolve example.com
    ```

5. **C – TTL.** Sucht einen Namen mit kurzer TTL (`lab 06 last` zeigt sie;
   `www.github.com` hatte bei uns ≈ 60 s). Löst ihn auf, dann alle 10 s
   `lab 06 cache` und `lab 06 resolve <name>`, bis die TTL abgelaufen ist.
   Wann geht wieder ein Paket hinaus?
6. **D – Sonderfälle.** `lab 06 resolve www.github.com` (CNAME),
   `lab 06 resolve does-not-exist.invalid` (NXDOMAIN), jeweils `lab 06 last`.
7. **E – Weiterleiter oder NAT?** Mit dem Rechner als Server
   (Standard) eine noch nicht aufgelöste Adresse auflösen und in **beiden**
   Wireshark-Fenstern die Anfrage suchen. Dann direkt an einen öffentlichen
   Resolver:

    ```text
    lab 06 server 1.1.1.1
    lab 06 resolve wikipedia.org
    lab 06 resolve wikipedia.org     (Cache: kein Paket)
    lab 06 resolve heise.de
    ```

    Notiert je Anfrage auf beiden Seiten: Quell-IP, Quellport, Ziel,
    DNS-ID, IP-TTL. Danach `lab 06 server <Adresse eures Rechners>`.
8. **F – PAT (optional).** Während das Board auflöst, fragt euer Rechner selbst:
   `nslookup heise.de 1.1.1.1`. Wie hält die NAT-Box die beiden Antworten
   auseinander?

## Erwartungswert (vor der Messung notieren!)

**1. Größen.** Die Anfrage nach `api.open-meteo.com` (Typ A) besteht aus
12 B Header, dem Namen in Label-Form und 4 B Typ/Klasse. Die Antwort
wiederholt die Frage und hängt einen A-Record an; dessen Name ist ein
2-Byte-Zeiger. Berechnet die Größe beider DNS-Nachrichten und die Größe der
Ethernet-Frames (UDP 8 B, IPv4 20 B, Ethernet 14 B, ohne FCS).

**2. Zeitbedarf.** Das Board fragt euren Rechner, der Rechner (Weiterleiter)
fragt seinen Resolver. Schätzt die Zeit der **ersten** Auflösung aus
RTT Board ↔ Rechner (Versuch 04: Leitung + Poll-Wartezeit bis *T*),
RTT Rechner ↔ Resolver (euer `rnlab.py ping 1.1.1.1`) und gegebenenfalls der Rekursion
beim Resolver (erster `nslookup` minus zweiter). Wie lange dauert die
**zweite** Auflösung, wie viele Pakete gehen dabei hinaus?

**3. TTL und Cache.** lwIP zählt die TTL eines Eintrags einmal pro Sekunde
herunter (`dns_check_entry()` in `src/core/dns.c`) und hat hier
`DNS_TABLE_SIZE` = 1 Eintrag. Was erwartet ihr in B, was in C?

**4. Ohne Antwort.** Was passiert, wenn der Server nie antwortet? Lest in
`dns_check_entry()` nach, wie oft (`DNS_MAX_RETRIES` = 4) und nach welchen
Wartezeiten lwIP wiederholt (der Timer tickt alle `DNS_TMR_INTERVAL` =
1000 ms). Nach wie vielen Sekunden gibt `resolve` auf?

**5. NAT.** Welche Felder der Anfrage des Boards (Quell-IP, Quellport,
Ziel-IP, Zielport, DNS-ID, IP-TTL, UDP-Prüfsumme) sind auf der
Internet-Seite anders, wenn das Board **direkt** `1.1.1.1` fragt? Und welche,
wenn es den **Rechner** fragt?

## Experiment (Firmware-Aufgabe)

Dateien in eurem Fork (Branch `praktikum/start`, gleiche Pfade im eigenen Repository; die Links zeigen auf die Vorlage):

- [`apps/rnlab/src/l06_dns_nat_logic.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/l06_dns_nat_logic.c)
  mit [`l06_dns_nat_logic.h`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/l06_dns_nat_logic.h):
  reine Logik, **hier arbeitet ihr** (`TODO(L06)`). Der Kopfkommentar der
  `.h` zeigt den Aufbau einer DNS-Nachricht und der Namenskompression.
- [`apps/rnlab/src/l06_dns_nat.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/l06_dns_nat.c):
  `resolve`, Hooks, Cache-Spiegel und Befehle, fertig.
- [`tests/unit/test_rnlab_l06.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/tests/unit/test_rnlab_l06.c):
  die Spezifikation mit echten Antworten eines öffentlichen Resolvers und
  absichtlich kaputten Nachrichten.

| Funktion | Aufgabe |
|---|---|
| `rnlab_dns_status_t rnlab_l06_read_name(msg, len, offset, out, out_size, next)` | Namen ab `offset` als Text mit Punkten nach `out` lesen (Wurzel → `""`). Labels 1–63 B, `0` = Ende, `11xxxxxx xxxxxxxx` = Zeiger, `01…`/`10…` = Fehler. `*next` zeigt hinter den **ersten** Zeiger bzw. hinter die `0`. Nie außerhalb `msg[0 … len-1]` lesen, nie über `out_size` schreiben (dann `ERR_NAME_LONG`, aber `*next` trotzdem hinter den Namen setzen), auf **jeder** Eingabe terminieren. |
| `rnlab_dns_status_t rnlab_l06_parse(msg, len, out)` | Header (QR-Bit gesetzt, genau eine Frage), Frage (Name, Typ), alle `ancount` Antworten überlesen, höchstens 4 speichern (Typ, TTL, bei A/IN die Adresse, `rdlength` muss 4 sein). TTL mit gesetztem oberstem Bit gilt als 0 (RFC 2181 §8). |

Fertig vorgegeben: `rnlab_l06_min_ttl()`, `rnlab_l06_find_dns()`,
`rnlab_l06_status_name()`, `rnlab_l06_type_name()`.

**So kommt die Antwort zu eurem Parser.** `lab 06 resolve` ruft
`dns_gethostbyname()` auf; lwIP antwortet sofort aus seiner Tabelle
(`ERR_OK`) oder schickt eine Anfrage und ruft später einen Rückruf. Während
`resolve` wartet, pollt es selbst `cads_net_poll()`. Der Hook
`rnlab_l06_hook_tx_frame()` notiert Zeit, Quellport und ID der Anfrage,
`rnlab_l06_hook_rx_frame()` gibt jede Antwort (Quellport 53) an
`rnlab_l06_parse()` und trägt sie in den Cache-Spiegel ein. lwIPs eigene
Tabelle ist in `dns.c` versteckt (`static`) und nicht auslesbar.

```bash
cmake --build build/host && ctest --test-dir build/host -L rnlab-L06 --output-on-failure
```

!!! warning "Ein Paket, eine Endlosschleife"
    Ein Zeiger `C0 0C` an Offset 12 zeigt auf sich selbst. Ein Parser, der
    Zeigern einfach folgt, hängt damit für immer, und das Board mit ihm. Die
    Regel „ein Zeiger muss vor den Anfang der gerade gelesenen Labelfolge
    zeigen“ schließt Schleifen aus, ohne echte Antworten abzulehnen. Warum?

??? example "Vertiefung (optional): Warum zufällige ID und zufälliger Quellport? (RFC 5452, Kaminsky)"
    Eine gefälschte DNS-Antwort wird angenommen, wenn sie vor der echten
    ankommt und ID **und** Zielport der Anfrage trifft. Lest RFC 5452
    Abschn. 4–9 und rechnet: Wie viele Versuche braucht ein Angreifer im
    Mittel mit zufälliger 16-Bit-ID allein, und wie viele mit zufälliger ID
    und zufälligem Port (≈ 2¹⁶ · 2¹⁶)? Warum macht der Kaminsky-Angriff (2008)
    mit Anfragen nach immer neuen Unternamen aus „einmal pro TTL raten“ ein
    „beliebig oft raten“?

    Dann messt: Board resetten, `lab 06 resolve` mit einem neuen Namen, Port
    und ID notieren; das dreimal. lwIP wählt beide mit `LWIP_RAND()`. Sind sie
    wirklich zufällig? Was macht eine NAT-Box, die Ports der Reihe nach vergibt,
    aus dieser Schutzmaßnahme?

## Auswertung

1. Vergleicht die berechneten Größen mit Wireshark.
2. Tabelle für A–D: Gesamtzeit, Netzzeit, Pakete, TTL. Welcher Anteil der
   ersten Auflösung entfällt auf Board ↔ Rechner, welcher auf Rechner ↔
   Resolver? Belegt es mit den Zeitstempeln beider Wireshark-Fenster.
3. Warum geht in B jede zweite Anfrage ins Netz, obwohl die TTL noch läuft?
   Was kostet ein größerer Cache an RAM (`struct dns_table_entry` in
   `dns.c`, `DNS_MAX_NAME_LENGTH` = 256)?
4. C: Wann genau ging wieder ein Paket hinaus? Stimmt die TTL der neuen
   Antwort mit der alten überein, und warum (nicht)?
5. E/F: Zeichnet die Übersetzungstabelle eurer NAT-Box (innen IP:Port ↔ außen
   IP:Port ↔ Ziel) für eure Anfragen. Behält euer Betriebssystem den
   Quellport des Boards bei? Woran erkennt ihr, dass der Rechner als
   DNS-Server **keine** NAT, sondern ein Weiterleiter ist?
6. Ein Server im Internet will das Board direkt ansprechen (z. B. Telnet auf
   Port 4242). Warum klappt das in S2 nicht, und was müsste man auf dem
   Rechner einrichten?

--8<-- "issue-feedback.md"

## Potenzielle Herausforderungen

- **`kein DNS-Server`:** Das Board ist noch statisch (S1) oder hat ohne
  Option 6 eine Lease bekommen. `lab net dhcp`, sonst `lab 06 server <ip>`.
- **`lwIP-Tabelle belegt (Anfrage laeuft noch)`:** Die vorige Anfrage wartet
  noch auf Antwort (bis zu 6,5 s). Mit einem Tabellenplatz kann lwIP nur einen
  Namen gleichzeitig auflösen.
- **`keine Antwort vom Server`:** Server nicht erreichbar. Mit
  `server 1.1.1.1` fehlt oft die NAT (Freigabe aus, Firewall), mit dem Rechner
  als Server der Weiterleiter. Prüft in Wireshark, ob die Anfrage den Rechner
  überhaupt erreicht.
- **Parser meldet `Name zu lang`:** Die Frage passt nicht in 63 Zeichen
  (`RNLAB_DNS_NAME_MAX`). Nehmt einen kürzeren Namen; lwIP selbst löst ihn
  trotzdem auf.
- **Test hängt:** Endlosschleife bei Zeigern, siehe Warnkasten.
- **Wireshark zeigt auf der WLAN-Seite nichts:** Falsche Schnittstelle, oder
  der Rechner hatte den Namen schon im eigenen Cache (dann geht nichts
  hinaus). Einen frischen Namen nehmen.
- **Quellport außen gleich innen:** Kein Fehler. Viele NAT-Implementierungen
  behalten den Port, solange er frei ist (RFC 4787, „port preservation“).

## Quellen

- RN-Skript, Kap. 5.21 (NAT) und 5.23 (DNS).
- RFC 1035 – Domain Names: Implementation and Specification (§4.1 Format,
  §4.1.4 Kompression).
- RFC 2181 – Clarifications to the DNS Specification (§8 TTL).
- RFC 5452 – Measures for Making DNS More Resilient against Forged Answers.
- RFC 3022 – Traditional IP Network Address Translator; RFC 4787 – NAT
  Behavioral Requirements for Unicast UDP.
- lwIP: `src/core/dns.c` (`dns_gethostbyname`, `dns_check_entry`,
  `LWIP_DNS_SECURE`), `src/include/lwip/opt.h` (`DNS_TABLE_SIZE`,
  `DNS_MAX_RETRIES`).
