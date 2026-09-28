# 03 · IPv4 & Subnetting

<a class="md-button" href="../../pdf/03-ipv4-subnetting.pdf">:material-file-pdf-box: Als PDF herunterladen</a>

!!! info "Termin T04 · Setup S1"
    Dieser Versuch läuft im Netz-Setup **S1 – statische Adresse**
    (siehe [Netz-Setup](../reference/netz-setup.md#s1-statische-adresse)).

--8<-- "konventionen.md"

Ein Host entscheidet bei **jedem** Paket, das er senden will, anhand seiner
Netzmaske: Liegt das Ziel in meinem Subnetz, dann direkt zustellen (ARP für
das Ziel), sonst an den Router (ARP für das Gateway). In diesem Versuch stellt
ihr am Board absichtlich falsche Netzmasken ein und seht, dass Erreichbarkeit
dadurch **richtungsabhängig** wird: Eine Anfrage kommt an, die Antwort
aber nicht zurück.

## Lernziele

Nach dem Versuch könnt ihr …

- aus Adresse und Netzmaske (bzw. Präfixlänge) Netzadresse, Broadcast-Adresse
  und Hostbereich berechnen und eine Maske auf Gültigkeit prüfen,
- die Zustellentscheidung eines Hosts („direkt oder über das Gateway“) für ein
  beliebiges Ziel vorhersagen,
- erklären, warum eine falsche Maske auf **einer** Seite zu asymmetrischer
  Erreichbarkeit führt, und das mit Wireshark belegen,
- empfangene IPv4-Pakete im Stack über einen Eingangs-Hook klassifizieren
  (eigene Adresse, Broadcast, Multicast, fremd) und filtern.

## Theorie-Bezug (Skript 5.11–5.14)

- **5.11 Strukturierte Adressen:** Eine IPv4-Adresse besteht aus
  **Netz-ID** und **Host-ID**; die MAC-Adresse ist dagegen unstrukturiert.
  Genau diese Struktur erlaubt die Entscheidung „ist das Ziel in meinem Netz?“.
- **5.12 IPv4 / 5.13 Subnetting:** Die **Netzmaske** (Subnetzmaske) legt mit
  führenden Einsen fest, welcher Teil der Adresse zur Netz-ID gehört;
  Präfixnotation `/24` ≙ `255.255.255.0`. Pro Subnetz gibt es eine
  **Netzadresse** (alle Host-Bits 0) und eine **Broadcast-Adresse** (alle
  Host-Bits 1), dazwischen liegen 2^Host-Bits − 2 Hostadressen.
- **5.14 IPv4-Header:** Quell- und Zieladresse stehen in den Bytes 12–15 und
  16–19 des Headers; dort liest euer Hook sie aus.

Router (Vermittlungsknoten) verbinden Netze; ein Host schickt alles, was nicht
in seinem eigenen Subnetz liegt, an seinen Router, das **Gateway**.

## Versuchsaufbau

```
 Rechner                         ITS-Board
 192.168.33.10/24  ── Ethernet ──  192.168.33.99/<Maske>
 (kein Gateway)                   Gateway 192.168.33.1 (existiert nicht!)
```

- Setup **S1**: Rechner `192.168.33.10/24`, **ohne** Router-Eintrag; das Board
  hat nach dem Flashen `192.168.33.99/24` mit Gateway `192.168.33.1`. Diese
  Gateway-Adresse gibt es in eurem Aufbau nicht, und genau das macht den
  Versuch interessant.
- Wireshark auf der Board-Schnittstelle, Anzeigefilter `arp || icmp`.
- Befehle an das Board mit [`python3 tools/rnlab.py lab …`](../reference/rnlab-tool.md#lab-telnet)
  über Telnet (Windows: `py tools\rnlab.py …`) oder über die
  [serielle Konsole](../reference/serielle-konsole.md). Haltet die serielle
  Konsole bereit: Nicht jede Maske lässt die Telnet-Verbindung bestehen.

## Versuchsablauf

1. Firmware-Aufgabe umsetzen (siehe unten), Host-Tests grün, flashen.
2. `lab 03 help` und `lab 03 show` ausführen:

    ```text
    $ python3 tools/rnlab.py lab 192.168.33.99 "lab 03 show"
    ip:        192.168.33.99
    maske:     255.255.255.0 (/24)
    netz:      192.168.33.0
    broadcast: 192.168.33.255
    gateway:   192.168.33.1 (im Netz)
    ```

3. **Erwartungswerte** eintragen (nächster Abschnitt), erst dann messen.
4. Für jede Maske `/24`, `/25`, `/16`, `/30` nacheinander:

    ```bash
    python3 tools/rnlab.py lab 192.168.33.99 "lab 03 netmask /25" "lab 03 reset"
    python3 tools/rnlab.py ping 192.168.33.99 -c 3     # vom Rechner aus
    python3 tools/rnlab.py lab 192.168.33.99 "lab 03 stats" \
        "lab 03 probe 192.168.33.10" "lab 03 probe 192.168.33.1" \
        "lab 03 probe 192.168.33.255" "lab 03 probe 192.168.34.10"
    ```

    `lab 03 netmask` ändert nur die Maske, Adresse und Gateway bleiben. Reißt
    die Telnet-Verbindung ab, dann dieselben Befehle über die serielle Konsole
    eingeben (ohne `python3 tools/rnlab.py lab …`, also z. B. `lab 03 stats`,
    siehe [serielle Konsole](../reference/serielle-konsole.md)).
    `lab 03 probe` zeigt die Zielklasse, den Next Hop, das ARP-Ergebnis für den
    Next Hop und ob ein Ping beantwortet wurde; jeder Schritt wartet höchstens 400 ms.
5. Bei jeder Maske in Wireshark festhalten: Welche ARP-Anfragen stellt das
   Board (`who-has … tell 192.168.33.99`)? Kommen Echo Requests an, gehen
   Echo Replies raus?
6. Filter ausprobieren (über die **serielle Konsole**, weil ihr euch damit
   selbst aussperren könnt): `lab 03 filter 192.168.33.0/24`, dann
   `lab 03 filter 192.168.34.0/24`, jeweils vom Rechner pingen, `lab 03 stats`,
   zum Schluss `lab 03 filter off`.
7. Zum Schluss `lab 03 netmask /24` (oder Reset), damit die folgenden Versuche
   wieder den Normalzustand vorfinden.

## Erwartungswert (vor der Messung notieren!)

**Schritt 1 – rechnen.** Das Board hat `192.168.33.99`; das letzte Oktett ist
`99 = 0110 0011₂`. Füllt die Tabelle mit Rechenweg aus:

| Maske | Host-Bits | Netzadresse | Broadcast | Hostbereich | Rechner .10 im Netz? | Gateway .1 im Netz? |
|---|---|---|---|---|---|---|
| /24 | 8 | 192.168.33.0 | 192.168.33.255 | .1 – .254 | ja | ja |
| /25 | 7 | | | | | |
| /16 | 16 | | | | | |
| /30 | 2 | | | | | |

Hinweis zur /30: Die Host-Bits von `.99` sind `11`. Was bedeutet das für die
Adresse des Boards?

**Schritt 2 – Zustellentscheidung vorhersagen.** Der Rechner behält `/24`. Für
jede Zeile: Schickt das Board **direkt** (ARP für das Ziel) oder **über das
Gateway** (ARP für `.1`)? Gibt es eine Antwort? Rechnet dabei mit eurem Aufbau,
in dem `192.168.33.1` nicht existiert.

| Board-Maske | Rechner → Board (`ping .99`) | Board → `.10` | Board → `.1` | Board → `.255` | Board → `192.168.34.10` |
|---|---|---|---|---|---|
| /24 | | | | | |
| /25 | | | | | |
| /16 | | | | | |
| /30 | | | | | |

!!! question "Kurz nachgedacht"
    Der Rechner schickt bei **jeder** Board-Maske seinen Echo Request direkt an
    `.99`, denn für ihn liegt `.99` in seinem `/24`. Das Board nimmt jedes Paket
    an seine eigene Adresse an, egal aus welchem Netz es kommt. Wann scheitert
    dann trotzdem der Ping, und in welcher Richtung?

## Experiment (Firmware-Aufgabe)

Dateien in eurem Fork (Branch `praktikum/start`):

- [`apps/rnlab/src/l03_ipv4_subnetting_logic.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/l03_ipv4_subnetting_logic.c)
  mit Header [`l03_ipv4_subnetting_logic.h`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/l03_ipv4_subnetting_logic.h):
  reine Logik, **hier arbeitet ihr** (alle Stellen `TODO(L03)`).
- [`apps/rnlab/src/l03_ipv4_subnetting.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/l03_ipv4_subnetting.c):
  Board-Integration (Hook, Befehle), fertig. Lesen lohnt sich.
- [`tests/unit/test_rnlab_l03.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/tests/unit/test_rnlab_l03.c):
  die Spezifikation als Unity-Tests.

Alle Adressen sind `uint32_t` in **Host-Byte-Reihenfolge**
(`192.168.33.99` = `0xC0A82163`, `/24` = `0xFFFFFF00`).

| Funktion | Aufgabe |
|---|---|
| `bool rnlab_l03_mask_valid(uint32_t mask)` | „erst Einsen, dann nur Nullen“? (`0.0.0.0` und `255.255.255.255` gültig) |
| `int rnlab_l03_mask_to_prefix(uint32_t mask)` | Präfixlänge 0–32, `-1` bei ungültiger Maske |
| `uint32_t rnlab_l03_prefix_to_mask(unsigned prefix)` | `/24` → `0xFFFFFF00`; `0` für prefix > 32. Achtung: `x << 32` ist in C undefiniert. |
| `uint32_t rnlab_l03_network(ip, mask)` / `rnlab_l03_broadcast(ip, mask)` | Host-Bits löschen bzw. setzen |
| `bool rnlab_same_subnet(ip_a, ip_b, mask)` | gleiche Netz-ID? |
| `rnlab_l03_classify_dst(dst, own_ip, mask)` | eigene Adresse → Limited Broadcast `255.255.255.255` → Multicast `224.0.0.0/4` → gerichteter Broadcast (nicht bei /31, /32) → sonst `OTHER` |
| `uint32_t rnlab_l03_next_hop(own_ip, mask, gateway, dst)` | `dst` selbst, wenn im Netz (oder `255.255.255.255`), sonst `gateway` (0 = keins) |

So kommt die Logik aufs Board: lwIP ruft über `LWIP_HOOK_IP4_INPUT` für jedes
empfangene IPv4-Paket `rnlab_l03_hook_ip4_input(p, inp)` auf, **bevor** es den
Header selbst prüft. Der Hook liest Quell- und Zieladresse, zählt nach
`classify_dst` × `same_subnet(Quelle)` und gibt `0` zurück („weiter an lwIP“).
Bei aktivem Filter und Quelle außerhalb des Präfixes gibt er `1` zurück und
gibt den Puffer selbst frei (`pbuf_free`), dann sieht lwIP das Paket nie.

```bash
cmake --build build/host && ctest --test-dir build/host -L rnlab-L03 --output-on-failure
```

Ohne Implementierung sind die Tests rot und das Board bleibt benutzbar:
`lab 03 netmask` lehnt jede Maske ab, der Filter lässt sich nicht einschalten.
Bauen und flashen wie in [Firmware-Labor-Image](../reference/firmware-lab-image.md#bauen-testen-flashen).

??? example "Vertiefung (optional): Warum `~mask`?"
    Das Komplement einer gültigen Maske ist `0…01…1 = 2^k − 1`. Addiert man 1,
    läuft der Übertrag durch alle Einsen und es bleibt kein gemeinsames Bit
    übrig. Findet ihr damit einen Einzeiler ohne Schleife?

## Auswertung

1. Vergleicht eure Vorhersagetabelle mit den Messungen. Jede Abweichung
   begründen: Next Hop aus `lab 03 probe` und ARP in Wireshark.
2. Bei welcher Maske funktioniert die Verbindung nur in einer Richtung? Belegt
   es mit einem Wireshark-Ausschnitt: das Paket, das ankommt, und was das
   Board daraufhin sendet. Wonach fragt es, und warum?
3. `lab 03 stats` nach genau dieser Messung: In welcher Zeile/Spalte landen
   eure Pings, und in welcher bei /24? Welche Pakete zählen als Broadcast oder
   Multicast, obwohl ihr sie nicht geschickt habt (z. B. mDNS `224.0.0.251`
   eures Rechners)?
4. Filter: Warum ist der Filter „nur Quellen aus Präfix X“ kein Schutz gegen
   einen Angreifer im selben Ethernet? (Stichwort: Quelladresse fälschen.)

--8<-- "issue-feedback.md"

## Potenzielle Herausforderungen

- **Telnet-Verbindung reißt nach einem Maskenwechsel ab:** kein Fehler der
  Firmware; warum, klärt ihr in der Auswertung. Weiter über die serielle
  Konsole; `lab 03 netmask /24` oder ein Reset stellt den Normalzustand her.
- **Selbst ausgesperrt** mit `lab 03 filter`: seriell `lab 03 filter off`.
- **Byte-Reihenfolge:** Die Logik rechnet in Host-Reihenfolge; lwIP speichert
  Adressen in Netz-Reihenfolge (`ip4_addr_get_u32()` + `lwip_ntohl()`, siehe
  Board-Datei).
- **`1u << 32`** ist undefiniert (auf ARM ergibt es oft 0, auf x86 oft 1).
  Die Host-Tests fangen das ab.
- **ARP-Cache:** Nach einem Maskenwechsel können alte ARP-Einträge noch eine
  Weile passen. Im Zweifel vor der Messung `arp -d` auf dem Rechner bzw.
  Board-Reset.
- **Broadcast-Pings** beantwortet je nach Betriebssystem der **Rechner selbst**.
  Prüft in Wireshark, wer antwortet.

## Quellen

- RN-Skript, Kap. 5.11–5.14 (Adressierung, IPv4, Subnetting, IPv4-Header).
- RFC 791 – Internet Protocol; RFC 950 – Internet Standard Subnetting Procedure.
- RFC 4632 – Classless Inter-domain Routing (CIDR); RFC 3021 – 31-Bit-Präfixe
  auf Punkt-zu-Punkt-Verbindungen.
- RFC 1122, Abschn. 3.3.1 – Zustellentscheidung eines Hosts („local/remote“).
- lwIP: `src/core/ipv4/ip4.c` (`ip4_input`, `LWIP_HOOK_IP4_INPUT`),
  `src/core/ipv4/etharp.c` (`etharp_output`: Wahl des Next Hop).
