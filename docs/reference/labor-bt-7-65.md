# Board-Adresse im Labor BT 7.65

Diese Seite gilt für euch, wenn ihr an den Rechnern im Labor **BT 7.65**
arbeitet. Dort hängt das Board nicht an einem eigenen Rechner im
Punkt-zu-Punkt-Netz (Setup S1 mit `192.168.33.99`), sondern im Labornetz
`172.16.0.0/16`. Das Board bekommt deshalb **nicht** seine Standardadresse,
sondern eine eigene aus diesem Netz. Ihr tragt sie einmal in der Datei
`config/factory.txt` ein, baut die Firmware neu und flasht sie.

--8<-- "issue-feedback.md"

## Eure Werte

| Einstellung | Wert |
|---|---|
| `net.ip` | `172.16.2.N` – **N** ist eure Platznummer (1 bis 254) |
| `net.netmask` | `255.255.0.0` |
| `net.gateway` | `172.16.0.1` |

Ersetzt **N** durch eure Platznummer, nie durch einen Wert, den schon ein
anderer Platz benutzt: zwei Boards mit derselben Adresse stören sich
gegenseitig. Beispiel für Platz 7: `172.16.2.7`.

## Schritt für Schritt

### 1. `config/factory.txt` öffnen

Im Firmware-Lab (VS Code im Browser) im Arbeitsbereich `cads-zero` die Datei
`config/factory.txt` öffnen. Sie ist die **eine** zentrale Stelle für die
Werkseinstellungen des Boards. Im Abschnitt `# network` stehen die
Standardwerte:

```text
net.dhcp = 0
net.ip = 192.168.33.99
net.netmask = 255.255.255.0
net.gateway = 192.168.33.1
```

### 2. Werte ändern

Ändert nur diese drei Zeilen. Alles andere in der Datei bleibt, wie es ist.
Mit Platz 7 sieht der Abschnitt so aus:

```text
net.dhcp = 0
net.ip = 172.16.2.7
net.netmask = 255.255.0.0
net.gateway = 172.16.0.1
```

Speichert die Datei. Prüft die drei Zeilen noch einmal: IP und Gateway müssen
im selben Netz liegen (hier beide in `172.16.x.x`), sonst erreicht das Board
sein Gateway nicht.

### 3. Neu bauen mit `scripts/build.sh`

Im Terminal des Firmware-Labs (*☰ → Terminal → New Terminal*, Ordner
`cads-zero`):

```bash
scripts/build.sh
```

Erst dieser Build bringt die neue Adresse in die Firmware. Ein bereits
vorhandenes `build/itsboard/cads-zero.bin` aus der Zeit vor eurer Änderung
enthält noch `192.168.33.99`. Das Ergebnis liegt wieder in
`build/itsboard/cads-zero.bin`.

!!! tip "Woran ihr merkt, dass der Build eure Änderung enthält"
    Der Build rechnet aus den Werten in `config/factory.txt` eine
    Werksrevision aus. Ändert ihr einen Wert, ändert sich die Revision. Das
    Board erkennt daran beim Start, dass die Firmware andere Werte trägt.
    Kommentare und Leerzeichen in der Datei zählen dabei nicht.

### 4. Flashen

Board an die ST-Link-Buchse anschließen und wie in
[Onboarding, Schritt 4](../labs/00-onboarding.md#4-board-verbinden-und-flashen)
verbinden und flashen: *F1* → **CaDS Board: Flash** oder die Task
**CaDS: Build + Flash**. Flasht dabei die Datei aus Schritt 3.

### 5. Prüfen

Nach dem Flashen startet das Board neu und übernimmt die Werte aus eurer
Firmware **einmal**. Prüft das über die serielle Konsole
(siehe [Serielle Konsole](serielle-konsole.md)):

```text
lab info
```

Dort müssen Adresse und Maske zu euren Werten passen (`172.16.2.N` und
`255.255.0.0`). Zeigt die Konsole noch `192.168.33.99`, lest unten den
Abschnitt „Wenn die alte Adresse bleibt“.

## Was ihr auf den Aufgabenseiten anders lest

Die Versuchsseiten nennen als Beispiel meist die Standardadresse
`192.168.33.99`. Im Labor BT 7.65 gilt überall stattdessen **eure**
Adresse `172.16.2.N`. Das betrifft vor allem `ping`, `rnlab.py` (Zieladresse)
und die Wireshark-Filter. Das Netz-Setup S1 mit `192.168.33.10/24` auf eurem
Rechner brauchen die Boards im Labornetz nicht.

## Wenn die alte Adresse bleibt

- **Es wurde nicht neu gebaut.** Ein Flash ohne vorherigen `scripts/build.sh`
  spielt die alte Firmware auf. Baut neu und flasht noch einmal.
- **Eine andere Datei wurde geändert.** Gebaut wird die `config/factory.txt` im
  Arbeitsbereich `cads-zero`. Eine Kopie an anderer Stelle wirkt nicht.
- **Der Build meldet einen Fehler in der Datei.** Der Build prüft die Werte
  (zum Beispiel eine IP-Adresse mit vier Zahlen). Lest die Meldung im Terminal
  und korrigiert die Zeile.
- **Das Board hat noch eine alte Konfiguration.** Mit *Settings → Factory
  reset* auf dem Board schreibt ihr die Werte der geflashten Firmware neu.
- **Adresse und Maske stimmen, aber nichts antwortet.** Prüft Kabel und den
  Link in `lab info` (`link: up`), dann ob schon ein anderer Platz eure Adresse
  benutzt.

## Alternative ohne Neubau

Wollt ihr die Adresse nur ausprobieren, geht es auch direkt am Board: auf dem
Display unter *Settings → Network*. Die Werte gelten dann nur, bis die
Firmware mit anderen Werten in `config/factory.txt` neu geflasht wird; ein
solcher Flash überschreibt sie. Für den Praktikumsbetrieb im Labor ist der
Weg über `config/factory.txt` der vorgesehene.

--8<-- "issue-feedback.md"
