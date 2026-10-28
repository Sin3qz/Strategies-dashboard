# Strategien & wikifolios — Dashboard

Öffentliche Seite (GitHub Pages): **https://sin3qz.github.io/Strategies-dashboard/**

Zeigt die Bots **levGTAA · MR-Rebound-GTAA · levTipsRegime · 1xGTAA** und die wikifolios
**LevGTAA (WFXLEVGTAA)** und **LevTipsRegime (WFXTIPSREG)**. Keine Anlageberatung.

## Bereiche
- **Überblick** – wikifolio-Performance, levTipsRegime-Abstand zur Linie, levGTAA-Vola und je Strategie
  „gehalten vs. wenn heute gehandelt würde“ mit dem Anteil, der umgeschichtet würde.
- **wikifolios** – Kennzahlen von wikifolio.com (Index, High-Watermark, max. Verlust, Watchlistings, Rangliste,
  Gebühren, Kriterien zur Investierbarkeit), Bot-Position, Backtest-Referenz, eigener Indexverlauf.
- **Tagessignal** – für jeden US-Handelstag seit 2025 die Position, die die Bot-Regel auf dem Schlusskurs ergäbe
  (levGTAA/MR-Rebound: jeder Tag wie ein Monatsletzter; 1xGTAA/levTipsRegime: ohne Cooldown), mit Zeitraumfilter
  und Liste der Signalwechsel.
- **Strategien** – die vier Bot-Karten (wie die alte Ansicht `classic.html`) und der levGTAA-Allokationsverlauf.
- **Performance** – Equity der Strategien und deiner Mischungen mit den gehandelten Produkten in EUR, Kennzahlen,
  Monatsrenditen, Korrelation (`dashboard-data/equity.py`).
- **Rechner** – nur für deine wikifolios: Stückzahlen eintragen → Ist-Allokation, Ziel (Bot-Soll oder Tagessignal) mit
  Cash-Puffer für die wikifolio-Gebühren, Order in ganzen Stück. Positionen optional für alle Geräte in
  `data/wikifolio_holdings.json` speichern.
- **Push** – ntfy-Meldung, wenn das simulierte Tagessignal kippt oder ein wikifolio investierbar wird (Secret `NTFY_TOPIC`).
- **App** – auf dem Handy „Zum Home-Bildschirm“: öffnet sich wie eine App, zeigt offline den letzten Stand.
- **Studien** – `studien/STUDIE.md`: Robustheit levGTAA, levTipsRegime (inkl. IEF) und 1xGTAA mit Empfehlungen.

## Wie es sich aktualisiert
Die GitHub Action `.github/workflows/refresh-dashboard.yml` läuft 5× täglich (06:41, 08:11, 12:41, 16:11, 21:41 UTC)
und kann unter *Actions → Dashboard-Daten aktualisieren → Run workflow* auch von Hand gestartet werden. Sie
1. liest `status_*.json` und `history_levgtaa.txt` der Bot-Repos (öffentlich, Branch `main`),
2. rechnet das Tagessignal mit dem Code der Bot-Repos auf Yahoo-Kursen (`dashboard-data/daily_signals.py`),
3. liest die wikifolio-Kennzahlen aus den Seitendaten von wikifolio.com und hängt sie an `data/wikifolio_history.csv` an,
4. committet `data/`. Fällt eine Quelle aus, bleibt deren letzter gültiger Stand stehen und die Seite nennt den Fehler.

Die Seite lädt die Dateien aus `data/` beim Öffnen, alle 10 Minuten und beim Zurückkehren in den Tab.

Optional: ein Secret **`PAT_PUSH`** (wie in den Bot-Repos) lässt die Action in deinem Namen pushen; dann deaktiviert
GitHub den Zeitplan auch nach 60 Tagen ohne eigene Commits nicht.

## Dateien
- `index.html` – wird von `dashboard-data/build_page.py` aus `dashboard-data/page.html` (Seite) und
  `dashboard-data/shell.html` (Design + kleine Laufzeit) gebaut. Nach Änderungen: `python3 dashboard-data/build_page.py`.
- `dashboard-data/refresh.py` – baut alle Dateien in `data/` neu (lokal: `python3 dashboard-data/refresh.py`).
- `classic.html` – die bisherige Signal-Ansicht, lädt direkt die Bot-Repos.
