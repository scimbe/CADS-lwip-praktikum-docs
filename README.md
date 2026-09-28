# CADS-lwip-praktikum-docs

Öffentliche Praktikumsaufgaben und Referenzdokumentation des
Rechnernetze-Praktikums mit lwIP auf dem ITS-Board (Firmware cads-zero,
Quelltext: [scimbe/cads-zero-firmware](https://github.com/scimbe/cads-zero-firmware)).

Veröffentlicht via GitHub Pages: https://scimbe.github.io/CADS-lwip-praktikum-docs/

Dieses Repository wird **automatisch generiert**; Änderungen hier werden
beim nächsten Abgleich überschrieben. Fehler und Verbesserungsvorschläge
bitte als [Issue](https://github.com/scimbe/CADS-lwip-praktikum-docs/issues/new?template=doku-verbesserung.yml)
melden.

## Inhalt

- `docs/` – Versuchsbeschreibungen (`docs/labs/`) und Referenzseiten
  (`docs/reference/`), gebaut mit MkDocs Material
- `tools/` – Host-Werkzeuge für den eigenen Rechner, u. a. `rnlab.py`
  (Python ≥ 3.9, nur Standardbibliothek)

## Lokal bauen

```bash
python3 -m venv .venv
.venv/bin/pip install -r docs/requirements.txt
.venv/bin/mkdocs serve
```

## Lizenz

- Dokumentation (`docs/`): [CC BY-SA 4.0](LICENSE)
- `tools/`: [MIT](LICENSE-tools)

© 2026 CADS AG
