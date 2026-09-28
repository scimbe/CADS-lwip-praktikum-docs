# Serielle Konsole

Das Board hat neben Telnet (TCP 4242) eine **serielle Konsole** über den
ST-LINK auf dem Board: dieselbe CLI mit denselben `lab …`-Befehlen, aber
unabhängig vom Netz. Ihr braucht sie immer dann, wenn das Board (noch) nicht
per Ethernet erreichbar ist – etwa um in S2 mit `lab net dhcp` DHCP zu starten
und mit `lab info` die erhaltene Adresse abzulesen.

--8<-- "issue-feedback.md"

## Im Firmware-Labor-Image (empfohlen)

Das [Firmware-Labor-Image](firmware-lab-image.md) öffnet die Konsole direkt im
Browser (WebSerial). Nötig ist **Chrome oder Chromium**; das Board hängt per
USB an eurem Rechner.

1. **Board verbinden** – einmal je Browser-Sitzung: in der Statusleiste unten
   auf `Board: getrennt` klicken und **Board verbinden (USB/Serial freigeben)**
   wählen, oder <kbd>F1</kbd> und `CaDS Board: Verbinden (USB/Serial freigeben)`.
   Der Browser fragt nach dem Gerät; das Board (STMicroelectronics) auswählen.
   Die Statusleiste zeigt danach `Board: verbunden`.
2. **Konsole öffnen:** <kbd>F1</kbd>, `CaDS Board: Konsole öffnen` tippen,
   <kbd>Enter</kbd>. Es erscheint das Terminal **CaDS Board Console** (115200
   Baud); die Statusleiste zeigt zusätzlich `· Konsole`. Alternativ über die
   Statusleiste: `Board: verbunden` → **Konsole öffnen**.
3. Befehle eintippen, z. B. `lab info`, mit <kbd>Enter</kbd> abschicken.

Gut zu wissen:

- Flashen und Konsole gehen **gleichzeitig**; die Konsole bleibt beim Flashen
  offen.
- Das Schließen des Terminals blendet nur die Anzeige aus – die serielle
  Verbindung bleibt bestehen. Freigegeben wird sie erst mit <kbd>F1</kbd>
  `CaDS Board: Trennen`. Das ist nötig, bevor ein lokales Programm (siehe
  unten) die Schnittstelle öffnen kann.
- Das Board gehört immer genau **einem** Browser-Tab. Für einen anderen Tab:
  `CaDS Board: Board freigeben (für einen anderen Tab)`.

## Lokal auf dem eigenen Rechner (Fallback)

Wer ohne Image arbeitet, öffnet die Schnittstelle des ST-LINK direkt. Die
Einstellungen sind auf allen Systemen gleich:

| Einstellung | Wert |
|---|---|
| Geschwindigkeit | 115200 Baud |
| Rahmen | 8 Datenbits, keine Parität, 1 Stoppbit (8N1) |
| Flusskontrolle | keine |
| Zeilenende beim Senden | CR (<kbd>Enter</kbd>); LF und CRLF versteht das Board ebenfalls |

Das Board sendet eure Eingabe **nicht** zurück (kein Echo). Ohne lokales Echo
tippt ihr also „blind“ – die Ausgabe des Befehls erscheint trotzdem.

=== "macOS"

    ```bash
    ls /dev/cu.usbmodem*                     # Gerät finden, z. B. /dev/cu.usbmodem1303
    screen /dev/cu.usbmodem1303 115200
    ```

    Beenden: <kbd>Ctrl</kbd>+<kbd>A</kbd>, dann <kbd>K</kbd> und mit
    <kbd>y</kbd> bestätigen. `screen` hat kein lokales Echo; wer es möchte,
    nimmt `picocom` (`brew install picocom`) wie unter Linux.

=== "Linux"

    ```bash
    ls /dev/ttyACM*                          # meist /dev/ttyACM0
    sudo usermod -aG dialout "$USER"         # einmalig, danach neu anmelden
    picocom -b 115200 --echo /dev/ttyACM0
    ```

    Beenden: <kbd>Ctrl</kbd>+<kbd>A</kbd>, dann <kbd>Ctrl</kbd>+<kbd>X</kbd>.
    Die Gruppe heißt je nach Distribution `dialout` (Debian/Ubuntu, Fedora)
    oder `uucp` (Arch); ohne sie meldet `picocom` „Permission denied“.

=== "Windows"

    1. **Geräte-Manager** → *Anschlüsse (COM & LPT)*: Der Eintrag
       *STMicroelectronics STLink Virtual COM Port (COMx)* nennt die Nummer.
    2. **PuTTY**: Connection type **Serial**, Serial line `COMx`, Speed
       `115200`. Unter *Connection → Serial* 8 Data bits, 1 Stop bit, Parity
       *None*, Flow control *None*.
    3. Für sichtbare Eingaben: *Terminal → Local echo: Force on*.

## Tasten des Boards fernbedienen

Die Taster des Boards lassen sich per Befehl drücken – auf der seriellen
Konsole ebenso wie per Telnet, also auch ohne Hand am Board:

```text
lab key down 3        # dreimal "runter"
lab key ok
lab key help          # alle Namen anzeigen
```

| Name | Wirkung |
|---|---|
| `up` `down` `left` `right` `ok` `back` `f1` `f2` | Taste im Menü drücken |
| `s0` … `s7` | dieselben acht Taster nach ihrer Position S0 … S7 (in der Reihenfolge oben) |
| `quit` | Menü verlassen; es bleibt der Prompt, das Netz läuft weiter |
| `menu` | vom Prompt zurück ins Menü |

Mit einer Zahl dahinter (1 … 20) wird die Taste so oft gedrückt;
Groß-/Kleinschreibung spielt keine Rolle. Das Board bestätigt mit
`key: ok` bzw. `key: down x3`. Fehler beginnen mit `? `, etwa wenn das Menü
nicht läuft – dann zuerst `lab key menu`.

!!! warning "Nur ein Programm gleichzeitig"
    Eine serielle Schnittstelle kann nur ein Programm öffnen. Hält der Browser
    sie (Image verbunden), melden lokale Programme „Resource busy“ bzw.
    „Zugriff verweigert“ – im Image vorher `CaDS Board: Trennen`.

--8<-- "issue-feedback.md"
