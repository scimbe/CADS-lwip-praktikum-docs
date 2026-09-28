/**
 * Fuellt den wiederkehrenden "Verbesserung vorschlagen"-Link
 * (docs/.snippets/issue-feedback.md, Klasse .cads-issue-feedback-link) mit
 * der aktuellen Seite (Titel + URL) als GitHub-Issue-Formularfeld "seite".
 *
 * Warum client-seitig statt fest im Markdown eingetragen: der Linktext ist
 * an jeder Einbindestelle identisch (ein Include ueber pymdownx.snippets,
 * siehe mkdocs.yml) - niemand muesste beim Hinzufuegen einer neuen
 * Einbindestelle eine Blatt-/Seitenkennung von Hand nachtragen oder bei
 * einer Blattumbenennung an mehreren Stellen aktualisieren. Die tatsaechliche
 * Fundstelle (Titel + volle URL, inkl. Anker bei Verlinkung auf einen
 * Abschnitt) ist ausserdem nur zur Laufzeit im Browser bekannt.
 *
 * navigation.instant (siehe mkdocs.yml) ersetzt bei Seitenwechseln nur den
 * Seiteninhalt per fetch(), ohne vollstaendigen Reload - "DOMContentLoaded"
 * feuert dabei kein zweites Mal. Deshalb ueber das von Material for MkDocs
 * bereitgestellte "document$"-Observable neu ausfuehren, das bei jedem
 * Instant-Navigation-Tausch erneut ausloest (siehe Material-Dokumentation
 * zu "Additional JavaScript" / instant loading).
 */
(function () {
  "use strict";

  function fillIssueFeedbackLinks() {
    var links = document.querySelectorAll("a.cads-issue-feedback-link");
    links.forEach(function (link) {
      try {
        var url = new URL(link.href, window.location.href);
        var pageTitle = (document.title || "").replace(/\s*[-–|].*$/, "").trim();
        var pageUrl = window.location.href;
        var seite = pageTitle ? pageTitle + " (" + pageUrl + ")" : pageUrl;
        url.searchParams.set("title", "Doku: " + (pageTitle || pageUrl));
        url.searchParams.set("seite", seite);
        link.href = url.toString();
      } catch (fehler) {
        /* Statischer href aus dem Markdown bleibt als Fallback stehen. */
      }
    });
  }

  if (typeof document$ !== "undefined" && document$ && typeof document$.subscribe === "function") {
    document$.subscribe(fillIssueFeedbackLinks);
  } else {
    document.addEventListener("DOMContentLoaded", fillIssueFeedbackLinks);
  }
})();
