# Firmware-Labor-Image

Gebaut wird die Firmware nicht auf eurem Rechner, sondern in einer
browserbasierten Entwicklungsumgebung: dem Image **CADS Firmware-Labor**
(code-server mit ARM-Toolchain, CMake und Host-Tests). Gestartet wird es über
[rn-praktikum.bunsenbrenner.org](https://rn-praktikum.bunsenbrenner.org).
Board und Ethernet bleiben dabei an **eurem eigenen Rechner**; geflasht wird
per WebUSB direkt aus dem Browser.

!!! warning "In Aufbau"
    Die Image-Auswahl auf dem Portal wird gerade umgesetzt. Diese Seite
    beschreibt den **vorgesehenen Ablauf**; Abweichungen im Detail werden hier
    nachgetragen, sobald die Auswahl freigeschaltet ist.

--8<-- "issue-feedback.md"

## Image wählen und anmelden

1. [rn-praktikum.bunsenbrenner.org](https://rn-praktikum.bunsenbrenner.org)
   öffnen.
2. **Vor der Anmeldung** das Image **CADS Firmware-Labor** auswählen. Welche
   Images angeboten werden, hängt von eurer Praktikumsgruppe ab.
3. Per Single-Sign-on anmelden. Mit derselben Anmeldung erhält die Umgebung
   auch Zugriff auf euer GitLab-Konto der Hochschule – ein zweiter Login für
   `git clone`/`git push` ist nicht nötig.

Pro Person läuft **genau ein Image** gleichzeitig. Wer das Image wechseln
will (z. B. zum Desktop-Image anderer Praktika), meldet sich ab und wählt vor
der nächsten Anmeldung das andere Image.

## Eigener Fork

Ihr arbeitet in eurem eigenen Fork **`cads-zero-firmware`** in eurem
GitLab-Namespace (gleicher Name wie die Vorlage), Grundlage ist der Branch
**`praktikum/start`**. Denselben Stand könnt ihr öffentlich im Repository
[scimbe/cads-zero-firmware](https://github.com/scimbe/cads-zero-firmware/tree/praktikum/start)
lesen; die Links in den Versuchsbeschreibungen zeigen dorthin.

1. Im GitLab das Projekt `cads-zero-firmware` in euren Namespace forken
   (einmal zu Beginn, siehe [Onboarding](../labs/00-onboarding.md)).
2. Im Firmware-Labor den eigenen Fork klonen und `praktikum/start`
   auschecken.
3. Je Versuch committen und pushen; die Stellen, an denen ihr Code ergänzt,
   sind im Quelltext mit `TODO(LNN)` markiert (z. B. `TODO(L03)`).

## Bauen, testen, flashen

Im Terminal des code-servers:

```bash
# Host-Tests eines Versuchs (reine Logik, ohne Board)
ctest --test-dir build/host -L rnlab-L03
```

Die Lektions-Tests sind auf `praktikum/start` absichtlich **rot**: sie werden
grün, sobald eure Implementierung stimmt. Die genauen Build- und
Flash-Befehle stehen im jeweiligen Versuch.

Zum **Flashen** braucht ihr **Chrome oder Chromium**: Flashen (WebUSB) und
serielle Konsole (WebSerial) sind dort erprobt; Firefox und Safari unterstützen
beides nicht. Das Board
hängt per USB an eurem Rechner; der Browser fragt beim ersten Flashen, ob er
auf das Gerät zugreifen darf.

Unter Linux braucht der Browser Schreibrechte auf das USB-Gerät des
ST-LINK-Programmers; ohne passende udev-Regel erscheint das Board zwar in der
Geräteauswahl, der Zugriff schlägt aber fehl.

Die serielle Konsole des Boards öffnet ihr ebenfalls im Image, siehe
[Serielle Konsole](serielle-konsole.md).

## Messen

Gemessen wird auf eurem eigenen Rechner, nicht im Image: mit Wireshark auf
der Board-Schnittstelle und mit [`rnlab.py`](rnlab-tool.md). Das Image sieht
euer lokales Netz nicht – es läuft auf einem Server, das Board steckt bei
euch.

--8<-- "issue-feedback.md"
