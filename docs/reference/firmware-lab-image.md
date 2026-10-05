# Firmware-Labor-Image

Gebaut wird die Firmware nicht auf eurem Rechner, sondern in einer
browserbasierten Entwicklungsumgebung: dem Image **CADS Firmware-Lab**
(code-server mit ARM-Toolchain, CMake und Host-Tests). Gestartet wird es über
[rn-praktikum.bunsenbrenner.org](https://rn-praktikum.bunsenbrenner.org).
Board und Ethernet bleiben dabei an **eurem eigenen Rechner**; geflasht wird
per WebUSB direkt aus dem Browser.

--8<-- "issue-feedback.md"

## Anmelden und Umgebung starten

1. Am Praktikumsportal
   [rn-praktikum.bunsenbrenner.org](https://rn-praktikum.bunsenbrenner.org)
   mit dem eigenen Konto anmelden.
2. Nach der Anmeldung zeigt das Portal die Seite **Umgebung wählen**. Dort
   den Eintrag **CADS Firmware-Lab** wählen.
3. Das Firmware-Lab öffnet VS Code im Browser; ein weiteres Passwort ist
   nicht nötig.

Pro Person läuft **genau eine Umgebung**. Die Seite „Umgebung wählen“
erscheint, wenn keine läuft; läuft eine, öffnet das Portal diese direkt, und
die Wahl gilt bis zum Abmelden.

## Abmelden und Umgebung wechseln

Im Firmware-Lab steht unten rechts in der Statusleiste der rote Knopf
**Abmelden** (auch *F1* → **CaDS: Abmelden**). Es erscheint die Rückfrage
„Vom Firmware-Labor abmelden? Offene Dateien werden vorher gespeichert, die
Verbindung zum Board wird getrennt.“ mit **Abmelden** und **Cancel**. Nach
der nächsten Anmeldung zeigt das Portal wieder die Seite „Umgebung wählen“.

Der Wechsel geht in beide Richtungen, zwischen **CADS Firmware-Lab** und
**Rechnernetze-Praktikum**: abmelden, neu anmelden, wählen. Im Desktop des
Rechnernetze-Praktikums ist das der Knopf **Logout** oben rechts.

Das Abmelden übersteht nur der Ordner `~/workspace`, also der Arbeitsbereich
`cads-zero` mit Branches, Commits und den Dateien, die Git nicht verfolgt.
Alles andere im Home-Verzeichnis und in `/tmp` bleibt nicht erhalten. Daraus
folgt:

- Name und E-Mail-Adresse für Commits im Repository setzen, also
  `git config user.name …` und `git config user.email …` **ohne** `--global`
  im Ordner `cads-zero`; `~/.gitconfig` gehört nicht zu `~/workspace`.
- Regelmäßig committen und in den eigenen Fork pushen.

## Eigener Fork

Ihr arbeitet in eurem eigenen Fork **`cads-zero-firmware`** in eurem
GitLab-Namespace (gleicher Name wie die Vorlage), Grundlage ist der Branch
**`praktikum/start`**. Denselben Stand könnt ihr öffentlich im Repository
[scimbe/cads-zero-firmware](https://github.com/scimbe/cads-zero-firmware/tree/praktikum/start)
lesen; die Links in den Versuchsbeschreibungen zeigen dorthin.

1. Im GitLab die Vorlage `cads-zero-firmware` in euren Namespace forken
   (einmalig).
2. Der Arbeitsbereich `cads-zero` (Ordner `/home/coder/workspace/cads-zero`)
   enthält die Firmware auf `praktikum/start` (samt Submodulen und Tasks),
   klonen ist nicht nötig. `origin` zeigt dort auf die öffentliche Vorlage;
   mit eurem Fork verbindet ihr den Arbeitsbereich wie in
   [Onboarding, Schritt 2](../labs/00-onboarding.md#2-arbeitsbereich-und-eigener-fork)
   beschrieben.
3. Je Versuch committen und pushen; die Stellen, an denen ihr Code ergänzt,
   sind im Quelltext mit `TODO(LNN)` markiert (z. B. `TODO(L03)`).

## Bauen, testen, flashen

Über *☰ → Terminal → Run Task…* stehen die Tasks bereit: **CaDS: Build**
baut die Firmware, **CaDS: Flash** und **CaDS: Build + Flash** bringen sie
auf das Board, **CaDS: Host tests (Rahmen)** führt die Tests des Rahmens aus
und **CaDS: Lektionstests** die Tests eines Versuchs (fragt nach der Nummer).
Die Tests gibt es auch im Terminal des code-servers:

```bash
# Host-Tests eines Versuchs (reine Logik, ohne Board)
ctest --test-dir build/host -L '^rnlab-L03$'
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
