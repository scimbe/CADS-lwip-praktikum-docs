// Rendert die per `mkdocs build` erzeugten HTML-Seiten der Versuche
// (docs/labs/*.md -> site/labs/<slug>/index.html) per Playwright zu PDF
// (site/pdf/<slug>.pdf). Uebernommen aus dem Basispraktikum
// (scimbe/CADS-praktikum-docs); dort sind die Entscheidungen belegt:
// kein LaTeX/Pandoc, Playwright druckt die gebaute Site, damit das PDF genau
// dem veroeffentlichten Text entspricht.
//
// Sprachwurzeln: mkdocs-static-i18n baut die Default-Sprache nach site/ und
// jede weitere nach site/<locale>/. Gerendert wird fuer jede Wurzel mit
// labs/-Verzeichnis nach <wurzel>/pdf/<slug>.pdf. Der Knopf auf jeder
// Versuchsseite zeigt mit "../../pdf/<slug>.pdf" dorthin (Seite liegt unter
// /labs/<slug>/, zwei Ebenen hoch ist die Sprachwurzel).
//
// Aufruf (nach `mkdocs build`, im Verzeichnis mit node_modules/@playwright/test):
//   node scripts/render-lab-pdfs.mjs <site-verzeichnis> [<oeffentliche-basis-url>]
//
// Die Basis-URL (alternativ Umgebungsvariable PDF_BASE_URL) ist die
// oeffentliche Adresse von site/, z. B.
// "https://scimbe.github.io/CADS-lwip-praktikum-docs/". Ohne sie schreibt
// Chromium beim Druck aus einer file://-Quelle jeden Link als absolute
// file://-Adresse ins PDF - toter Link und Offenlegung des Build-Pfads.

import { chromium } from '@playwright/test';
import { mkdir, readdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const siteDir = resolve(process.argv[2] ?? 'site');
const baseUrlArg = process.argv[3] ?? process.env.PDF_BASE_URL ?? '';

if (!existsSync(siteDir)) {
  console.error(`Kein Site-Verzeichnis unter ${siteDir} gefunden - vorher "mkdocs build" ausfuehren.`);
  process.exit(1);
}

// Normalisierte Basis-URL mit genau einem Schraegstrich am Ende.
const baseUrl = baseUrlArg ? baseUrlArg.replace(/\/+$/, '') + '/' : '';
if (!baseUrl) {
  console.warn(
    'WARNUNG: Keine Basis-URL (Argument 2 oder PDF_BASE_URL). Linkziele werden auf ' +
      'site-relative Pfade gekuerzt, damit kein file://-Build-Pfad im PDF landet - ' +
      'anklickbar sind sie dann aber nicht.',
  );
}

// Druckregeln. mkdocs-material liefert praktisch kein Print-Stylesheet aus
// (der gesamte @media-print-Block der ausgelieferten main.css ist
// "@media print{.md-typeset{font-size:.68rem}}"), deshalb hier:
//  - Codebloecke, Tabellen und Bilder nicht ueber Seitengrenzen zerreissen,
//  - Ueberschriften nicht allein am Seitenende stehen lassen,
//  - den Knopf "Als PDF herunterladen" im PDF selbst ausblenden (er zeigt
//    auf das Dokument, das man gerade liest).
//
// BEWUSST NICHT enthalten: Regeln, die Tabellen umbauen (display:table,
// table-layout:fixed). Gemessen am 2026-09-24 wird KEINE Tabelle im Druck
// rechts abgeschnitten - alle Spalten aller Tabellen stehen vollstaendig im
// PDF, lange Kopfzellen sind lediglich auf zwei Zeilen umgebrochen. Ein
// Versuch mit table-layout:fixed machte es schlechter: die Spalte
// "Begruendung" in Blatt 01 verschwand und Blatt 04 verlor 17 Wort-Token
// an zusaetzlichen Umbruechen. Ohne belegtes Problem kein Eingriff.
const PRINT_CSS = `
  a.md-button[href$=".pdf"] { display: none !important; }
  .md-typeset pre, .md-typeset .highlight, .md-typeset table,
  .md-typeset figure, .md-typeset .admonition, .md-typeset details {
    break-inside: avoid; page-break-inside: avoid;
  }
  .md-typeset h1, .md-typeset h2, .md-typeset h3, .md-typeset h4 {
    break-after: avoid; page-break-after: avoid;
  }
  .md-typeset img { max-width: 100% !important; height: auto !important; }
`;

const FOOTER_TEMPLATE = `
  <div style="width:100%;font-size:8pt;color:#666;font-family:Helvetica,Arial,sans-serif;
              padding:0 15mm;display:flex;justify-content:space-between;">
    <span class="title"></span>
    <span>Seite <span class="pageNumber"></span> von <span class="totalPages"></span></span>
  </div>`;

async function findLocaleRoots(baseDir) {
  const roots = [];
  if (existsSync(join(baseDir, 'labs'))) {
    roots.push(baseDir);
  }
  const entries = await readdir(baseDir, { withFileTypes: true });
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const candidate = join(baseDir, entry.name);
    if (candidate !== join(baseDir, 'labs') && existsSync(join(candidate, 'labs'))) {
      roots.push(candidate);
    }
  }
  return roots;
}

const localeRoots = await findLocaleRoots(siteDir);

if (localeRoots.length === 0) {
  console.error(`Keine Sprachwurzel mit labs/-Verzeichnis unter ${siteDir} gefunden.`);
  process.exit(1);
}

// file://-Praefix der Site-Wurzel, gegen den die Linkziele gekuerzt werden.
const siteFileUrl = pathToFileURL(siteDir).href.replace(/\/+$/, '') + '/';

const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  for (const localeRoot of localeRoots) {
    const labsDir = join(localeRoot, 'labs');
    const pdfDir = join(localeRoot, 'pdf');
    await mkdir(pdfDir, { recursive: true });

    const entries = await readdir(labsDir, { withFileTypes: true });
    const slugs = entries.filter((e) => e.isDirectory()).map((e) => e.name);

    for (const slug of slugs) {
      const htmlPath = join(labsDir, slug, 'index.html');
      if (!existsSync(htmlPath)) continue;
      await page.goto(pathToFileURL(htmlPath).href, { waitUntil: 'networkidle' });

      // Aufklappbare Bloecke (`??? …` -> <details>) fuer den Druck vorbereiten.
      // Chromium druckt ein geschlossenes <details> nur mit seiner Titelzeile.
      // - normale Bloecke: oeffnen, damit ihr Inhalt im PDF steht;
      // - Bloecke mit Klasse "druck-zu" (`??? info druck-zu "Titel"`, z. B. ein
      //   Erwartungshorizont): bewusst zu lassen, der Titel bekommt nur im
      //   Druck den Hinweis "Im Online-Blatt aufklappbar".
      const { opened, kept } = await page.evaluate((hint) => {
        let opened = 0;
        let kept = 0;
        for (const d of document.querySelectorAll('details')) {
          if (d.classList.contains('druck-zu')) {
            d.open = false;
            const summary = d.querySelector(':scope > summary');
            if (summary && !summary.querySelector('.druck-zu-hinweis')) {
              const span = document.createElement('span');
              span.className = 'druck-zu-hinweis';
              span.style.fontWeight = 'normal';
              span.textContent = ` – ${hint}`;
              summary.appendChild(span);
            }
            kept += 1;
          } else if (!d.open) {
            d.open = true;
            opened += 1;
          }
        }
        return { opened, kept };
      }, 'Im Online-Blatt aufklappbar');

      // Lazy geladene Bilder wuerden im Druck fehlen, weil nie gescrollt
      // wird: erst eager schalten, dann auf Bilder und Schriften warten.
      await page.evaluate(async () => {
        for (const img of document.querySelectorAll('img[loading="lazy"]')) {
          img.loading = 'eager';
        }
        await Promise.all(
          [...document.images]
            .filter((i) => !i.complete)
            .map((i) => i.decode().catch(() => {})),
        );
        await document.fonts.ready;
      });

      // Linkziele von file:// auf die oeffentliche Adresse umschreiben.
      const rewritten = await page.evaluate(
        ({ siteFileUrl, baseUrl }) => {
          let n = 0;
          for (const a of document.querySelectorAll('a[href]')) {
            const abs = a.href;
            if (!abs.startsWith(siteFileUrl)) continue;
            const rest = abs.slice(siteFileUrl.length).replace(/(^|\/)index\.html/, '$1');
            a.setAttribute('href', baseUrl ? baseUrl + rest : '/' + rest);
            n += 1;
          }
          return n;
        },
        { siteFileUrl, baseUrl },
      );

      await page.addStyleTag({ content: PRINT_CSS });

      const pdfPath = join(pdfDir, `${slug}.pdf`);
      await page.pdf({
        path: pdfPath,
        format: 'A4',
        margin: { top: '20mm', bottom: '20mm', left: '15mm', right: '15mm' },
        printBackground: true,
        // Lesezeichen und Struktur: ein 20-seitiges Aufgabenblatt ohne
        // Outline ist nicht navigierbar. Braucht Playwright >= 1.49.
        outline: true,
        tagged: true,
        // Eigene Vorlagen sind Pflicht: Chromiums Standard-Kopf/Fuss
        // wuerde die file://-Quelladresse in das PDF drucken.
        displayHeaderFooter: true,
        headerTemplate: '<div></div>',
        footerTemplate: FOOTER_TEMPLATE,
      });
      console.log(
        `OK  ${relative(siteDir, htmlPath)} -> ${relative(siteDir, pdfPath)}  ` +
          `(${rewritten} Links umgeschrieben, ${opened} Bloecke aufgeklappt, ${kept} bewusst zu)`,
      );
    }
  }
} finally {
  await browser.close();
}
