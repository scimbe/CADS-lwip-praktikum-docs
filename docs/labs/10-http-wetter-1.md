# 10 · HTTP-Client für Wetterdaten

<a class="md-button" href="../../pdf/10-http-wetter-1.pdf">:material-file-pdf-box: Als PDF herunterladen</a>

!!! info "Termin T11 · Setup S2"
    Dieser Versuch läuft im Netz-Setup **S2 – Internetfreigabe**
    (siehe [Netz-Setup](../reference/netz-setup.md#s2-internetfreigabe)).
    Ohne Internet am Board (oder zum Testen vorab) geht alles bis auf DNS auch
    in **S1** mit dem lokalen Wetter-Testserver.

--8<-- "konventionen.md"

Ein Browser tippt man nicht in eine Zeile, aber ein Wetterabruf passt in eine:
Namen auflösen, TCP-Verbindung aufbauen, eine Textzeile `GET …` schicken,
Antwort lesen. In diesem Versuch baut ihr genau diesen HTTP/1.0-Client in die
Firmware des Boards und holt euch die aktuelle Temperatur von
[open-meteo.com](https://open-meteo.com/) – ohne Bibliothek, mit einem
Parser, der die Antwort Byte für Byte verarbeitet, egal wie TCP sie
zerschneidet. Nebenbei messt ihr, wie viele Round-Trips und wie viele Bytes
ein einziger Zahlenwert kostet.

## Lernziele

Nach dem Versuch könnt ihr …

- den Ablauf eines HTTP-Abrufs (DNS → TCP-Handshake → Anfrage → Antwort →
  Verbindungsabbau) mit Paketen und Round-Trips beschreiben und in Wireshark
  wiederfinden,
- eine HTTP-Antwort zerlegen: Statuszeile, Header, Leerzeile, Body; das Ende
  des Bodys bestimmen (Verbindungsende, `Content-Length`,
  `Transfer-Encoding: chunked`),
- einen **streamenden** Parser schreiben, der mit beliebig zerteilten
  TCP-Daten richtig umgeht, und das mit Host-Tests belegen,
- aus JSON gezielt einzelne Zahlen holen, ohne das Dokument zu speichern,
- Protokoll-Overhead (Header-Anteil, Chunk-Rahmen, TCP/IP) und die Zahl der
  Round-Trips pro Abruf vorab berechnen und messen.

## Theorie-Bezug (Skript 5.36, 5.23)

- **HTTP (5.36)** arbeitet nach dem Request-Reply-Prinzip über TCP. Eine
  Anfrage besteht aus der **Anfragezeile** (Methode, Pfad, Version), Header-
  Feldern und einer Leerzeile; die Antwort beginnt mit der **Statuszeile**
  (`HTTP/1.1 200 OK`, Statuscode-Gruppen 2xx/4xx/5xx), gefolgt von Headern,
  Leerzeile und Body.
- **HTTP/1.0** baut für jede Anfrage eine neue TCP-Verbindung auf und beendet
  sie danach; ohne `Content-Length` markiert das Verbindungsende das Ende des
  Bodys. **HTTP/1.1** hält Verbindungen offen (persistent) und muss deshalb
  das Body-Ende anders anzeigen – bei dynamisch erzeugten Antworten mit
  `Transfer-Encoding: chunked` (RFC 9112, Abschn. 7.1).
- **DNS (5.23)** löst `api.open-meteo.com` in eine Adresse auf. Das Board ist
  ein **Stub-Resolver** (wie in Versuch 06): Es fragt den DNS-Server, den es
  per DHCP gelernt hat – in S2 euren Rechner als **DNS-Weiterleiter**, der
  die Frage an einen rekursiven Resolver weitergibt. Die Antwort ist ein Resource Record vom Typ A mit
  **TTL**; so lange hält lwIP ihn im eigenen Cache, und ein zweiter Abruf
  kommt ohne DNS-Paket aus.
- Eine **RESTful API** wie open-meteo liefert Daten statt Seiten (hier JSON);
  der Client ist ein Programm, kein Mensch.

## Versuchsaufbau

```
 Board (DHCP)  ── Ethernet ──  Rechner (Internetfreigabe: DHCP, DNS, NAT)  ── WLAN ── Internet
 lwIP-Client                   Wireshark, rnlab.py, curl                            api.open-meteo.com:80
```

- Setup **S2** wie in der [Referenz](../reference/netz-setup.md#s2-internetfreigabe),
  auf dem Board `lab net dhcp`, dann `lab info` (Adresse und DNS-Server
  notieren).
- Wireshark auf der Board-Schnittstelle, Filter
  `dns || tcp.port == 80 || tcp.port == 8080`.
- Befehle an das Board mit [`rnlab.py lab`](../reference/rnlab-tool.md#lab-telnet),
  Vergleichsmessung am Rechner mit [`rnlab.py http`](../reference/rnlab-tool.md#http)
  und `curl`.
- **Wetter-Testserver** (`tools/wetter_testserver.py`, nur Python-
  Standardbibliothek): antwortet wie open-meteo, aber auf eurem Rechner –
  gleiche Bytes, ohne Internet und DNS, mit einbaubaren Fehlern
  (`--fault 500|garbage|truncate|nojson|slow|reset|silent`). Mit HTTP/1.0 kommt
  der Body bis zum Verbindungsende, mit HTTP/1.1 als ein Chunk, wie beim
  Original.

    Das Skript liegt wie `rnlab.py` im Ordner `tools/` des Doku-Repositorys;
    `<rechner>` ist die
    Adresse eures Rechners im Board-Netz (S1 `192.168.33.10`, S2 siehe
    [Referenz](../reference/netz-setup.md#s2-internetfreigabe)):

    ```bash
    python3 tools/wetter_testserver.py --bind <rechner> --port 8080   # Windows: py tools\wetter_testserver.py …
    ```

    Die Firewall eures Rechners muss eingehende Verbindungen auf Port 8080
    erlauben: macOS und Windows fragen beim ersten Start nach („Python“ bzw.
    `python.exe` zulassen, unter Windows für das private Netz).

!!! info "Werkzeug: `lab 10`"
    | Befehl | Wirkung |
    |---|---|
    | `lab 10 get [host[:port]] [pfad]` | Abruf mit HTTP/1.0 starten; ohne Argumente open-meteo mit der Standardabfrage |
    | `lab 10 get11 [host[:port]] [pfad]` | dasselbe mit HTTP/1.1 (Antwort chunked; braucht die Vertiefung) |
    | `lab 10 show` | Zustand, Zeiten je Phase, Bytes, Header-Anteil, die vier Werte |
    | `lab 10 head` / `lab 10 body` | empfangener Header / Anfang des Bodys |
    | `lab 10 abort` | laufenden Abruf abbrechen |

    `get` **startet** den Abruf nur und kehrt sofort zurück; das Ergebnis holt
    `show`. Warum? Ein Abruf über das Internet dauert Hunderte Millisekunden,
    ein toter Server bis zum Timeout 10 s. So lange würde ein wartender Befehl
    die Hauptschleife anhalten – Display, Tasten und andere Verbindungen
    stünden. Stattdessen erledigen lwIP-Callbacks DNS, Verbindung und Empfang
    nebenbei, genau so, wie es später die Wetter-App braucht. Steht als Host
    eine IP-Adresse (z. B. `<rechner>:8080`), entfällt DNS; ein Name wie
    `api.open-meteo.com` wird immer aufgelöst, mit oder ohne Port. Die ganze Abfrage-URL passt nicht in
    eine Befehlszeile (max. 95 Zeichen), deshalb ist der Pfad eingebaut:

    `/v1/forecast?latitude=53.55&longitude=9.99&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code`

## Versuchsablauf

1. Firmware-Aufgabe umsetzen, Pflicht-Tests grün
   (`ctest --test-dir build/host -L '^rnlab-L10$'`), flashen.
2. **Erwartungswerte** notieren (nächster Abschnitt).
3. **A – Referenz am Rechner** (derselbe Abruf, den das Board macht). A misst
   nur euren Rechner und darf deshalb vor dem Erwartungswert laufen – dessen
   Teil 2 und 3 bauen auf diesen Zahlen auf:

    ```bash
    URL="http://api.open-meteo.com/v1/forecast?latitude=53.55&longitude=9.99&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code"
    curl -0 -s -o /dev/null -w "dns %{time_namelookup} connect %{time_connect} ttfb %{time_starttransfer} total %{time_total} header %{size_header} body %{size_download}\n" "$URL"
    python3 tools/rnlab.py http "$URL" --http-version 1.0
    python3 tools/rnlab.py http "$URL" --http-version 1.1
    ```

    Unter Windows heißt es `curl.exe … -o NUL` statt `-o /dev/null`, die
    Variable setzt ihr mit `$URL="…"` (PowerShell), `rnlab.py` startet ihr mit
    `py tools\rnlab.py`. `-0` erzwingt HTTP/1.0.
4. **B – lokal, ohne Internet:** Testserver starten (siehe Aufbau), dann

    ```bash
    python3 tools/rnlab.py lab <board> "lab 10 get <rechner>:8080"
    python3 tools/rnlab.py lab <board> "lab 10 show"
    python3 tools/rnlab.py lab <board> "lab 10 head"
    ```

    Die HTTP/1.1-Antwort (chunked) messt ihr im Pflichtteil am **Rechner**:
    `python3 tools/rnlab.py http http://<rechner>:8080/v1/forecast --http-version 1.1`.
    **Vertiefung (optional):** Mit fertigem chunked-Parser dasselbe am Board,
    `lab 10 get11 <rechner>:8080` und `lab 10 show`.

    Das Board steht dabei im Menü (App-Baum). Wiederholt einmal am
    Konsolen-Prompt: App-Baum mit `lab key quit` verlassen, danach mit
    `lab key menu` zurück (siehe
    [serielle Konsole](../reference/serielle-konsole.md) und Versuch 04).
5. **C – Fehlerfälle:** Testserver nacheinander mit `--fault 500`,
    `garbage`, `truncate`, `nojson`, `reset` starten und jeweils `get` +
    `show`; außerdem ein Port, auf dem niemand lauscht (`:8081`), und eine
    Adresse ohne Gerät (Zeitüberschreitung nach 10 s).
6. **D – open-meteo über das Internet** (S2): `lab 10 get`, `lab 10 show`,
    sofort noch einmal (DNS-Cache!). In Wireshark die Pakete eines Abrufs
    zählen und den Ablauf als Sequenzdiagramm skizzieren.
7. **E – curl vs. Board:** Werte aus A und D vergleichen.

## Erwartungswert (vor der Messung notieren!)

**1. Round-Trips.** Zählt für einen Abruf mit HTTP/1.0, wie viele Round-Trips
zwischen Board und Server mindestens nötig sind, bis die Antwort da ist –
einmal mit leerem DNS-Cache, einmal mit gefülltem. Welche Pakete gehören zum
Verbindungsabbau, und zählen sie zur Wartezeit des Clients?

**2. Zeiten.** Die Hauptschleife des Boards verarbeitet empfangene Frames nur
bei jedem `cads_net_poll()`, im Menü etwa alle *T* ≈ 10 ms (Versuch 04).
Das Board sendet sofort, erfährt von der Antwort aber erst beim nächsten Poll.
Sagt für Messung B (Server im LAN, Leitungs-RTT < 1 ms) die Zeiten
„Verbindung“ und „1. Byte“ voraus. Für D: Nehmt die Zeiten von `curl` aus A
(DNS, Handshake = `connect − dns`, Server = `ttfb − connect`) und rundet jede
Wartephase auf ein Vielfaches von *T* auf.

**3. Bytes.** Die Anfrage des Boards besteht aus diesen Zeilen (jede endet mit
CR LF, danach eine Leerzeile):

```text
GET <pfad> HTTP/1.0
Host: api.open-meteo.com
User-Agent: cads-zero-rnlab
Accept: application/json
Connection: close
```

Berechnet ihre Länge mit dem eingebauten Pfad. Die Antwort auf HTTP/1.0 hat
laut `curl` in A einen Header von *H* Byte und einen Body von *B* Byte.
Berechnet

- den **Header-Anteil** *H* / (*H* + *B*),
- für HTTP/1.1 den zusätzlichen Header `Transfer-Encoding: chunked` und den
  Chunk-Rahmen bei **einem** Chunk: Größe hexadezimal + CR LF vor den Daten,
  CR LF danach, `0` CR LF CR LF zum Schluss,
- in wie viele TCP-Segmente die Antwort zerfällt, wenn das Board eine MSS von
  536 B ankündigt (`TCP_MSS` in lwIP),
- grob die Bytes auf dem Kabel für den ganzen Abruf (TCP/IP-Header 40 B und
  Ethernet 18 B je Segment, Handshake und Abbau als Frames ohne Nutzdaten zu
  64 B, DNS-Anfrage und -Antwort zusammen ≈ 200 B) und daraus die Effizienz
  Nutzdaten (die vier Zahlen, etwa 20 B) / Kabelbytes.

## Experiment (Firmware-Aufgabe)

Dateien in eurem Fork (Branch `praktikum/start`):

- [`apps/rnlab/src/l10_http_wetter_1_logic.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/l10_http_wetter_1_logic.c)
  mit [`l10_http_wetter_1_logic.h`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/l10_http_wetter_1_logic.h):
  reine Logik, **hier arbeitet ihr zuerst** (`TODO(L10)`). Der Header
  beschreibt jede Funktion genau.
- [`apps/rnlab/src/l10_http_wetter_1.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/l10_http_wetter_1.c):
  der lwIP-Client mit `lab 10`. Vier `TODO(L10)` für die lwIP-Aufrufe, der
  Rest (Zustände, Zeitmessung, Timeout, Ausgabe) ist fertig.
  [`l10_http_wetter_1.h`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/apps/rnlab/src/l10_http_wetter_1.h)
  ist seine Schnittstelle – die Wetter-App in Versuch 11 benutzt denselben
  Client.
- [`tests/unit/test_rnlab_l10.c`](https://github.com/scimbe/cads-zero-firmware/blob/praktikum/start/tests/unit/test_rnlab_l10.c):
  die Spezifikation. Die Antworten darin sind echte Aufzeichnungen von
  open-meteo; jede wird an **jeder** Stelle in zwei Teile und in Stücke von
  1, 2, 3, 7, … Byte geschnitten.

!!! info "Pflicht und Vertiefung"
    Verlangt ist ein **HTTP/1.0**-Client: Statuszeile, Header mit
    `Content-Length`, Body bis zum Verbindungsende, und JSON-Zahlen aus
    `current` (inkl. der `current_units`-Falle und abgeschnittener Eingaben).
    Dafür müssen die **34 Tests ohne `_v_`** im Namen grün werden. Die
    **12 Tests `test_v_…`** gehören zur Vertiefung: `chunked` mit Trailern,
    `1xx`/`204` (alles HTTP/1.1) sowie JSON-Escapes, Exponenten und kaputte
    Zahlen. **Pflichtteil ≈ 3 h:** die Funktionen für die Tests ohne `_v_`,
    die vier lwIP-Stellen und die Messungen **A, B, C, E**. Messung D
    (open-meteo über S2) gehört dazu, sobald S2 läuft; die Tests `test_v_…`
    sind **Vertiefung (optional)**.

| Funktion | Aufgabe |
|---|---|
| `size_t rnlab_http_build_get(out, size, host, port, path, http11)` | Anfrage wie oben; `:port` nur wenn ≠ 80; 0 bei zu kleinem Puffer oder unbrauchbarem Pfad (kein `/` am Anfang, Leer- oder Steuerzeichen – sonst könnte jemand eigene Header einschleusen) |
| `size_t rnlab_http_feed(http, data, len)` | Zustandsautomat über die Antwort: Statuszeile prüfen, Header zeilenweise (Groß-/Kleinschreibung egal) auf `Content-Length` und `Transfer-Encoding` untersuchen, Body an `on_body` weitergeben, `chunked` dekodieren. Zählt Header-, Leitungs- und Nutzbytes |
| `void rnlab_http_finish(http)` | Server hat geschlossen: Body ohne Länge ist jetzt fertig, alles andere Unfertige ist „abgeschnitten“ |
| `void rnlab_json_feed(json, data, len)` | Zeichenweiser JSON-Lexer; merkt sich nur die Zahlen, die **direkt** im Objekt `current` stehen, als Wert × 1000 |
| `bool rnlab_json_number(json, key, &milli)` | einen gemerkten Wert nachschlagen |

Im Board-Teil:

| Stelle in `l10_http_wetter_1.c` | Aufgabe |
|---|---|
| `rnlab_l10_fetch_start()`, DNS-Zweig | `dns_gethostbyname()` mit den drei Ergebnissen `ERR_OK` (Cache), `ERR_INPROGRESS`, Fehler |
| `l10_dns_found()` | Callback: Adresse → `l10_connect()`, `NULL` → DNS-Fehler |
| `l10_connected()` | Anfrage mit `tcp_write(…, TCP_WRITE_FLAG_COPY)` + `tcp_output()` senden |
| `l10_recv()` | die pbuf-**Kette** an den Parser geben, `tcp_recved()`, `pbuf_free()`; ist die Antwort fertig, auswerten und schließen |

**Die Fallen im JSON.** Die Antwort enthält jeden Schlüssel zweimal:

```json
"current_units":{"temperature_2m":"°C", …},"current":{"time":"2026-09-28T12:30","interval":900,"temperature_2m":23.2, …}
```

Wer einfach nach `"temperature_2m":` sucht, findet zuerst die Einheit. Die
Tests prüfen außerdem Schlüssel gleichen Namens in verschachtelten Objekten,
den Text `"current"` als Wert und abgeschnittene Eingaben: `…"wind_speed_10m":4` am Ende darf **nicht** als 4 gemeldet werden –
es könnte `4.1` gewesen sein. Escapes in Schlüsseln (`\"`, `\u0074`) und
Exponenten (`1e3`) prüft erst die Vertiefung.

```bash
cmake --build build/host
ctest --test-dir build/host -L '^rnlab-L10$' --output-on-failure            # Pflicht
ctest --test-dir build/host -L rnlab-L10-vertiefung --output-on-failure     # Vertiefung (optional)
```

Das Muster ist ein regulärer Ausdruck: ohne `^…$` passt `rnlab-L10` auch auf
`rnlab-L10-vertiefung`.

Ohne Implementierung bricht `lab 10 get` mit „Argument ungueltig“ ab, weil
`rnlab_http_build_get()` noch 0 liefert. Ist die Funktion fertig, baut das
Board mit einer IP-Adresse als Ziel schon die TCP-Verbindung auf und meldet
dann „noch nicht implementiert (TODO L10)“ – bis die lwIP-Stellen fertig sind.

??? example "Vertiefung (optional): der Parser als Zustandsautomat"
    Zeichnet den Automaten von `rnlab_http_feed()` (Zustände
    `rnlab_http_state_t`) mit den Übergängen, bevor ihr ihn programmiert. Wo
    braucht ihr einen Zeilenpuffer, wo reicht ein Zähler? Warum muss der
    Automat bei `Content-Length` weniger Bytes verbrauchen können, als ihm
    übergeben werden?

## Auswertung

1. Tragt die Zeiten aus A, B und D in eine Tabelle (DNS, Verbindung,
   1. Byte, gesamt) und vergleicht sie mit euren Erwartungswerten. Welcher
   Anteil der Board-Zeiten ist Netz, welcher Warten auf den nächsten Poll?
2. Bytes und Header-Anteil für HTTP/1.0 und 1.1: Stimmen eure Rechnung,
   `lab 10 show` (1.0) und `rnlab.py http` (1.0 und 1.1) überein? Was kostet
   `chunked` hier, und
   was würde es bei einer persistenten Verbindung einsparen?
3. Sequenzdiagramm aus Wireshark (D): Wie viele Pakete, wie viele Round-Trips?
   Wer schließt die Verbindung zuerst, und warum bei HTTP/1.0 zwingend der
   Server? Wie viele TCP-Segmente hatte die Antwort (`lab 10 show`:
   „Segmente“), passt das zur MSS?
4. Zweiter Abruf direkt danach: Wo ist die DNS-Anfrage geblieben? Wie lange
   würde lwIP den Eintrag behalten (TTL in der DNS-Antwort)?
5. Fehlerfälle (C): Welche Meldung erscheint jeweils, und in welcher Schicht
   liegt der Fehler (TCP, HTTP-Syntax, HTTP-Status, Anwendungsdaten)?
6. Effizienz: Wie viele Byte auf dem Kabel pro Nutzbyte? Was wäre mit TLS
   (HTTPS) zusätzlich nötig – Round-Trips und Bytes, grob?

--8<-- "issue-feedback.md"

## Potenzielle Herausforderungen

- **`ctest -L rnlab-L10` bleibt rot, obwohl der Pflichtteil fertig ist:** Das
  Muster erwischt auch `rnlab-L10-vertiefung` (chunked, JSON-Escapes,
  Exponenten); für den Pflichtteil `-L '^rnlab-L10$'` verwenden.
- **„kein DNS-Server“:** Das Board kennt einen DNS-Server nur per DHCP (S2,
  `lab net dhcp`, `lab info` zeigt ihn). In S1 mit IP-Adresse arbeiten.
- **Nichts kommt an, Zeitüberschreitung beim Testserver:** Firewall des
  Rechners lässt Port 8080 nicht durch, oder `--bind` ist nicht die Adresse im
  Board-Netz. Vom Rechner aus prüfen: `curl -0 http://<adresse>:8080/v1/forecast`.
- **`show` sagt „laeuft“:** `get` kehrt sofort zurück; einfach noch einmal
  `show`. Über das Internet dauert ein Abruf ≈ 0,1 s, im Menü etwas länger.
- **Test besteht einzeln, aber nicht zerschnitten:** Der Automat hat eine
  Annahme über Stückgrenzen (z. B. „CR und LF kommen zusammen“ oder „die
  Statuszeile ist in einem Stück“). Zustand gehört in die Struktur, nicht in
  lokale Variablen.
- **Temperatur ist 0 oder die Einheit:** Der Extraktor hat `current_units`
  erwischt oder `current_units` für `current` gehalten (Präfix!).
- **Nur die erste pbuf ausgewertet:** Eine Antwort kann als Kette ankommen
  (`p->next`); `p->len` ist die Länge eines Glieds, `p->tot_len` die der Kette.
- **lab-Befehl zu lang:** Das Board verwirft Zeilen über 95 Zeichen; deshalb
  der eingebaute Pfad.
- **Verbindung hängt nach Fehlern:** Jeder Fehlerpfad muss den PCB schließen
  oder abbrechen (`tcp_abort()` im Callback → `ERR_ABRT` zurückgeben). Es
  gibt nur 4 TCP-PCBs.

## Quellen

- RN-Skript, Kap. 5.36 (WWW und HTTP) und 5.23 (DNS).
- RFC 9110 – HTTP Semantics (Statuscodes, Header-Felder); RFC 9112 –
  HTTP/1.1 (Nachrichtenformat, `chunked`, Abschn. 6.3 Länge des Bodys);
  RFC 1945 – HTTP/1.0.
- RFC 8259 – The JavaScript Object Notation (JSON) Data Interchange Format.
- RFC 1035 – Domain Names (Resource Records, TTL).
- open-meteo: API-Dokumentation *Weather Forecast API*,
  <https://open-meteo.com/en/docs>.
- lwIP: `src/core/dns.c` (`dns_gethostbyname`, Cache), `src/core/tcp.c` /
  `tcp_out.c` (`tcp_connect`, `tcp_write`), Raw-API-Doku `doc/rawapi.txt`.
