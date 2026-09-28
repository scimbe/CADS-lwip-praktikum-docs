# rnlab.py – Host-Werkzeug

`rnlab.py` ist das Messwerkzeug für euren eigenen Rechner. Es erzeugt
definierten Verkehr zum Board (UDP, TCP, iperf2), wertet `ping` und HTTP-Abrufe
aus und führt `lab`-Befehle per Telnet auf dem Board aus.

- **Eine Datei, nur Python-Standardbibliothek** – nichts zu installieren
  außer Python ≥ 3.9.
- Läuft gleichwertig unter **macOS, Linux und Windows**.
- Braucht **keine Administratorrechte** und keine Raw-Sockets.
- Jeder Befehl liefert mit `--json` ein maschinenlesbares Ergebnis für die
  eigene Auswertung (Tabellen, Plots).

Die Datei liegt im Doku-Repository unter
[`tools/rnlab.py`](https://github.com/scimbe/CADS-lwip-praktikum-docs/blob/main/tools/rnlab.py)
und steht unter der MIT-Lizenz. Alle Aufrufe in dieser Dokumentation gehen vom
Wurzelverzeichnis des geklonten Repositorys aus:

```bash
git clone https://github.com/scimbe/CADS-lwip-praktikum-docs.git
cd CADS-lwip-praktikum-docs
```

--8<-- "issue-feedback.md"

## Aufruf

=== "macOS / Linux"

    ```bash
    python3 tools/rnlab.py <befehl> [optionen]
    python3 tools/rnlab.py <befehl> --help
    ```

=== "Windows"

    ```powershell
    py tools\rnlab.py <befehl> [optionen]
    py tools\rnlab.py <befehl> --help
    ```

`--json` darf vor oder nach dem Befehl stehen. Exit-Code `0` bedeutet Erfolg,
`1` einen Netzwerkfehler (bzw. bei `check` eine fehlgeschlagene Prüfung), `2`
eine falsche Eingabe, `3` ein belegtes Board (`lab`, siehe unten).

## Befehle im Überblick

| Befehl | Zweck | Typische Versuche |
|---|---|---|
| `check` | Python, aktives Netz-Setup, Route und Erreichbarkeit des Boards prüfen | alle |
| `lab` (alias `telnet`) | `lab …`-Befehle per Telnet (TCP 4242) ausführen | alle |
| `ping` | System-`ping` mit RTT-Statistik (min/avg/max/stddev) und Verlust | 00, 01, 04 |
| `udp-send` / `udp-recv` | Datagramme mit Sequenznummer und Zeitstempel senden bzw. auswerten | 07 |
| `tcp-send` / `tcp-recv` | Massendaten über TCP, Goodput | 08, 09 |
| `iperf2` | iperf2-kompatibler TCP-Client, z. B. gegen den iperf-Server des Boards (Port 5001) | 08, 09 |
| `http` | HTTP-GET mit Zeit- und Byte-Aufschlüsselung | 10, 11 |

## check

```bash
python3 tools/rnlab.py check --board 192.168.33.99
```

Prüft, ob die Adresse eines Setups lokal konfiguriert ist (S1:
`192.168.33.10`; S2: `192.168.2.1`, `192.168.137.1` oder `10.42.0.1`), über
welche lokale Adresse das Betriebssystem das Board erreichen würde und ob die
Telnet-Schnittstelle des Boards antwortet. In S1 ist `--board` optional.

Als S1 gilt jede lokale Adresse aus `192.168.33.0/24`; weicht sie von
`192.168.33.10` ab, steht das als Hinweis dabei. Sind S1-Netz und
Internetfreigabe **gleichzeitig** aktiv, liest `check` die Adressen je
Schnittstelle aus (`ifconfig`, `ip` bzw. `netsh`) und warnt, wenn beide im
selben Ethernet-Segment liegen – auf demselben Adapter oder, wie bei der
macOS-Internetfreigabe, in derselben Bridge. Dann teilen sich zwei
IPv4-Subnetze ein Kabel: Das Board erhält per DHCP eine Adresse der Freigabe,
und Broadcasts und ARP beider Netze mischen sich – in Versuch 05 verfälscht
das die Beobachtung von DHCP.

## lab / telnet

```bash
python3 tools/rnlab.py lab 192.168.33.99 "lab info"
python3 tools/rnlab.py lab 192.168.33.99 "lab 02 arp" "lab info"   # mehrere nacheinander
python3 tools/rnlab.py lab 192.168.33.99                            # interaktiv
```

Die Taster des Boards lassen sich so ebenfalls fernbedienen; welche Namen es
gibt, zeigt `lab key help` (Übersicht:
[Tasten des Boards fernbedienen](serielle-konsole.md#tasten-des-boards-fernbedienen)):

```bash
python3 tools/rnlab.py lab 192.168.33.99 "lab key help"
python3 tools/rnlab.py lab 192.168.33.99 "lab key down 3" "lab key ok"
```

Die Ausgabe eines Befehls gilt als vollständig, sobald der Prompt `> ` der
Board-CLI erscheint oder 1 s lang nichts mehr kommt (`--idle`; das Board
schweigt z. B. während eines Bildschirmaufbaus knapp eine halbe Sekunde). Länger
laufende Board-Befehle (Messreihen) geben deshalb mindestens alle 400 ms ein
Fortschrittszeichen aus. Spätestens nach `--overall` Sekunden (Standard 30)
geht es mit dem nächsten Befehl weiter. Weitere Eigenschaften der Board-CLI, die das Werkzeug
berücksichtigt:

- Befehlszeilen sind höchstens 95 Zeichen lang; längere verwirft das Board,
  `rnlab.py` lehnt sie vorher ab.
- Fehlermeldungen des Boards beginnen mit `? ` und erscheinen in der
  JSON-Ausgabe als `"error": true`.
- Das Board puffert je Befehl bis zu 1 KB Ausgabe und wartet bis zu 1 s darauf,
  dass der Client Daten quittiert. Erst wenn der Puffer danach noch voll ist
  (der Client liest nicht), endet die Ausgabe mit `? Ausgabe gekuerzt`
  (JSON: `"truncated": true`).
- Nach `lab net static …` oder `lab net dhcp` schließt das Board die
  Verbindung, weil sich seine Adresse ändern kann. Weitere Befehle im selben
  Aufruf werden dann nicht mehr gesendet und als `not_sent` gemeldet.
- Das Board erlaubt nur **eine** Telnet-Verbindung gleichzeitig. Eine zweite
  weist es mit `? belegt: andere Sitzung aktiv - bitte spaeter erneut` ab
  (ältere Firmware schließt sie ohne Meldung). `rnlab.py` meldet das als
  eigenen Fall: Exit-Code `3`, in JSON `"busy": true`. Mit `--retry N`
  versucht es bis zu `N`-mal erneut, mit wachsender Pause (0,5 s, 1 s, 2 s,
  danach 4 s); `"attempts"` nennt die Zahl der Versuche.

**Einzelbefehl ohne interaktive Sitzung.** Das Board führt einen Befehl auch
dann noch aus, wenn der Client direkt danach seine Senderichtung schließt.
Die netcat-Varianten unterscheiden sich allerdings in ihren Optionen:

=== "macOS"

    ```bash
    printf 'lab info\r\n' | nc -w 2 192.168.33.99 4242
    # gleichwertig, ohne Option:
    (printf 'lab info\r\n'; sleep 2) | nc 192.168.33.99 4242
    ```

    Das `nc` von macOS kennt `-N` nur mit anderer Bedeutung und bricht damit
    ab (`invalid tcp adaptive write timeout value`).

=== "Linux"

    ```bash
    printf 'lab info\r\n' | nc -N 192.168.33.99 4242     # OpenBSD-netcat (Debian/Ubuntu)
    printf 'lab info\r\n' | nc -q 1 192.168.33.99 4242   # traditionelles netcat
    (printf 'lab info\r\n'; sleep 2) | nc 192.168.33.99 4242   # jede Variante
    ```

=== "Windows"

    Windows bringt kein netcat mit; hier `rnlab.py` verwenden:

    ```powershell
    py tools\rnlab.py lab 192.168.33.99 "lab info"
    ```

Da das Board nur eine Verbindung gleichzeitig annimmt, kann ein direkt
folgender Aufruf mit „connection refused“ oder „reset“ scheitern – kurz warten
und erneut versuchen.

Für Automatisierung und Auswertung ist `rnlab.py` gedacht; zum interaktiven
Arbeiten eignen sich ebenso gut die üblichen Clients. Das Board versteht CR,
LF und CRLF als Zeilenende und ignoriert Telnet-Optionsaushandlung:

=== "macOS / Linux"

    ```bash
    nc 192.168.33.99 4242
    telnet 192.168.33.99 4242
    ```

=== "Windows"

    ```powershell
    telnet 192.168.33.99 4242
    ```

    Der Windows-Telnet-Client muss einmalig aktiviert werden
    (*Windows-Features → Telnet-Client*, oder
    `dism /online /Enable-Feature /FeatureName:TelnetClient` als
    Administrator). Alternativ PuTTY mit Verbindungstyp *Raw* oder *Telnet*,
    Port 4242.

## ping

```bash
python3 tools/rnlab.py ping 192.168.33.99 -c 100 -i 0.2
python3 tools/rnlab.py ping 192.168.33.99 -c 50 -s 1472 --df --hist 1
python3 tools/rnlab.py ping 192.168.33.99 -c 100 -i 0.2 --json > ping.json
```

| Option | Bedeutung |
|---|---|
| `-c N` | Anzahl Echo-Requests (Standard 10) |
| `-s BYTE` | ICMP-Nutzdaten, Standard 56 B wie unter Unix – auf allen Systemen gleich (Windows sendet von sich aus 32 B); 1472 füllt einen Ethernet-Rahmen mit MTU 1500 genau aus |
| `-i SEK` | Sendeabstand |
| `-W SEK` | Wartezeit je Antwort |
| `--df` | Don't-Fragment-Bit setzen: zu große Pakete werden nicht fragmentiert, sondern abgewiesen |
| `--hist MS` | Histogramm der RTTs mit Klassenbreite `MS` (auch leere Klassen) |

Ausgegeben werden gesendete/empfangene Pakete, Verlust, RTT
min/avg/max/Standardabweichung, Median sowie 90- und 99-Perzentil und die TTL
der Antworten. Mit `--json` kommen alle Einzelwerte (`replies_ms`) dazu – für
eigene Diagramme.

Unterschiede zwischen den Systemen, die ihr bei der Auswertung kennen solltet:

- **Linux/macOS:** `rnlab.py` ruft das `ping` des Systems mit den passenden
  Optionen auf (µs-Auflösung). Die Standardabweichung stammt dort direkt aus
  `ping` (Linux nennt sie `mdev`). Sehr kurze Sendeabstände (je nach
  `ping`-Version unter 0,2 s bzw. 0,1 s) verlangen Administratorrechte.
- **Windows:** Das System-`ping` misst nur ganze Millisekunden – die Laufzeiten
  zum Board liegen darunter und erschienen fast alle als `<1ms`. `rnlab.py`
  sendet deshalb unter Windows selbst über die ICMP-Schnittstelle von Windows
  (ohne Administratorrechte) und misst die Zeit um jeden Aufruf mit
  µs-Auflösung; der Wert enthält den Aufrufaufwand von typischerweise einigen
  10 µs. `-i` funktioniert damit auch unter Windows. Mit `--engine system`
  lässt sich das System-`ping` erzwingen.

## udp-send / udp-recv

```bash
python3 tools/rnlab.py udp-send 192.168.33.99 7007 -n 1000 --size 512 --rate 500 --burst 10
python3 tools/rnlab.py udp-recv 7007 --expect 1000
```

`--rate` ist die mittlere Rate in Datagrammen pro Sekunde (`0` = so schnell
wie möglich). Mit `--burst B` gehen jeweils `B` Datagramme direkt
hintereinander hinaus; die Pause danach hält die mittlere Rate ein.

Aufbau jedes Datagramms (Nutzdaten des UDP-Segments):

| Byte | Inhalt | Kodierung |
|---|---|---|
| 0–3 | Sequenznummer, beginnt bei 0 | `uint32`, Netzbyteordnung (big-endian) |
| 4–11 | Sendezeitpunkt in µs seit 1970-01-01 UTC | `uint64`, Netzbyteordnung |
| 12… | Auffüllung bis `--size` | `0x00` |

`udp-recv` zählt Verluste, Duplikate und umsortierte Datagramme und berechnet
den Jitter nach RFC 3550 (Abschnitt 6.4.1). Ohne `--expect` wird die erwartete
Anzahl aus kleinster und größter empfangener Sequenznummer geschätzt – Verluste
ganz am Anfang oder Ende fallen dann nicht auf. Die ausgewiesene
Einweg-Laufzeit ist nur aussagekräftig, wenn Sender und Empfänger dieselbe Uhr
haben; der Jitter dagegen hängt nur von Laufzeit*differenzen* ab.

## tcp-send / tcp-recv

```bash
python3 tools/rnlab.py tcp-send 192.168.33.99 7008 --bytes 1000000 --chunk 1460
python3 tools/rnlab.py tcp-send 192.168.33.99 7008 --time 10
python3 tools/rnlab.py tcp-recv 7008
```

`tcp-send` meldet zwei Werte: die **Sendeseite** (Zeit bis zum letzten
`send`-Aufruf) und den **Goodput bis zum FIN der Gegenseite**. Nur der zweite
belegt, dass alle Daten angekommen sind – `send` kehrt schon zurück, wenn die
Daten im lokalen Sendepuffer liegen. Schließt die Gegenseite nicht innerhalb
von `--wait` Sekunden, wird nur der Sendeseiten-Wert ausgegeben.

## iperf2

```bash
python3 tools/rnlab.py iperf2 192.168.33.99 -t 10 -i 1
```

Spricht das Protokoll des klassischen **iperf2**-Clients (TCP, Port 5001):
Zuerst ein 24-Byte-Kopf mit der Testbeschreibung, danach Nutzdaten im
iperf-Muster `0123456789…`. Damit funktioniert das Werkzeug gegen den
iperf-Server von lwIP (`lwiperf`) ebenso wie gegen `iperf -s` (Version 2) auf
einem anderen Rechner. Zu iperf3 ist es **nicht** kompatibel.

## http

```bash
python3 tools/rnlab.py http "http://api.open-meteo.com/v1/forecast?latitude=53.55&longitude=9.99&current=temperature_2m"
python3 tools/rnlab.py http "http://…" --http-version 1.1 --body
```

Zeigt die Zeiten für Namensauflösung, Verbindungsaufbau, erstes Byte der
Antwort und Übertragung sowie die Bytes für Anfrage, Antwort-Header und
Antwort-Body. Bei HTTP/1.1 wird `Connection: close` gesendet; liefert der
Server `Transfer-Encoding: chunked`, weist das Werkzeug Anzahl der Chunks und
deren Overhead aus. Nur `http://` – das Board spricht kein TLS.

--8<-- "issue-feedback.md"
