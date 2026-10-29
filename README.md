# Strategien & wikifolios — Dashboard

Öffentliche Seite (GitHub Pages): **https://sin3qz.github.io/Strategies-dashboard/**

Zeigt die Bots **levGTAA · MR-Rebound-GTAA · levTipsRegime · 1xGTAA** und die wikifolios
**LevGTAA (WFXLEVGTAA)** und **LevTipsRegime (WFXTIPSREG)**. Keine Anlageberatung.

## Bereiche
- **wikifolios** (Startseite) – je wikifolio (LevGTAA, LevTipsRegime) alle Kennzahlen von wikifolio.com (Performance, Monat, High-Watermark,
  Watchlistings, Rangliste, Gebühren, investiertes Kapital, Investierbarkeit), Bot-Soll mit Produkt und ISIN, deine
  Ist-Allokation, levTipsRegime-Abstand zur Linie; dazu Monatsperformance und wikifolio vs. Bot-Soll seit Start.
- **Signale** – je Bot (levGTAA, levTipsRegime, 1xGTAA, MR-Rebound-GTAA) Aufbau & Parameter (Idee, Bausteine mit Signal und
  ISIN, Auswahl, Gewichtung, Risiko, Zeitplan), die gehaltene Position und das Tagessignal
  („wenn heute gehandelt würde“; levGTAA/MR-Rebound: jeder Tag wie ein Monatsletzter, 1xGTAA/levTipsRegime ohne Cooldown),
  jeweils mit Produkt und ISIN, Abweichung, Verlauf seit 2025, Zeitbalken der gehaltenen Position, Signaltabelle des Bots;
  dazu „So laufen die Bots“ (Läufe, Datenprüfung, Meldungen), die Liste der Signalwechsel und der levGTAA-Allokationsverlauf.
- **Performance** – Equity der Strategien und deiner Mischungen (Mix A = 1/3 levTipsRegime + 2/3 levGTAA, Mix B = je 1/3
  levTipsRegime, 1xGTAA, levGTAA) mit den gehandelten Produkten in EUR, Kennzahlen,
  Monatsrenditen, Korrelation (`dashboard-data/equity.py`).
- **Rechner** – nur für deine wikifolios: Stückzahlen eintragen → Ist-Allokation, Ziel (Bot-Soll oder Tagessignal) mit
  Cash-Puffer für die wikifolio-Gebühren, Order in ganzen Stück. Positionen optional für alle Geräte in
  `data/wikifolio_holdings.json` speichern.
- **Push** – ntfy-Meldung, wenn das simulierte Tagessignal kippt oder ein wikifolio investierbar wird (Secret `NTFY_TOPIC`).
- **App** – auf dem Handy „Zum Home-Bildschirm“: öffnet sich wie eine App, zeigt offline den letzten Stand.
- **Studien** – `studien/STUDIE.md`: Robustheit levGTAA, levTipsRegime (inkl. IEF) und 1xGTAA mit Empfehlungen.

## Datenstatus und Rückfallebenen
Oben auf jeder Seite zeigt ein Punkt den Datenstatus (grün = alles aktuell, gelb = Hinweis oder letzter Stand, rot =
überfällig oder Fehler). Ein Klick öffnet die Liste aller Quellen mit Status, Datenstand, letztem Erfolg, Weg und Grund
(`data/health.json`). Rückfallebenen beim Abruf:
1. jede Anfrage bis zu 3 Versuche mit Pause,
2. Bot-Dateien über Ersatzwege (GitHub-API, jsDelivr-Spiegel), Bot-Code notfalls als Tarball,
3. fällt eine Quelle trotzdem aus, bleibt nur ihr letzter gültiger Stand (die anderen werden aktualisiert),
4. zweiter Durchgang für ausgefallene Quellen nach 150 s,
5. bricht der ganze Lauf ab, Neustart nach 5 Minuten (GitHub schickt bei endgültigem Fehlschlag eine E-Mail),
6. nächster stündlicher Lauf; nach 3 gestörten Läufen in Folge ein ntfy-Push mit dem Grund, nach der Erholung ein zweiter,
7. im Browser: je Datei 3 Ladeversuche; ohne Netz zeigt die Seite den zuletzt gespeicherten Stand und sagt das.
Die Seite erkennt außerdem, wenn die Action überfällig ist (GitHub startet geplante Läufe teils Stunden später).

## Pünktliche Läufe (empfohlen)
GitHub startet geplante Läufe oft Stunden später (Oktober 2026: Bot-Lauf 05:17 UTC kam um 10:40–11:25 UTC) oder lässt
sie aus. Deshalb gibt es einen **Zeitgeber**: Jede Dashboard-Aktualisierung stößt zwischen 05:15 und 21:30 UTC jeden Bot
an, der heute noch nicht erfolgreich gelaufen ist (`dashboard-data/kick_bots.py`, Ergebnis im Datenstatus). Pünktlich wird
das mit einem externen Anstoß der Aktualisierung:
1. **Ein Token für alles:** GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens →
   Generate new token. Repository access: Strategies-dashboard, levgtaa-signalbot, levtipsregime-signalbot,
   1xgtaa-signalbot, mrreboundgtaa-signalbot. Permissions: **Actions: Read and write**, **Contents: Read and write**.
2. Im Repo Strategies-dashboard: Settings → Secrets and variables → Actions → Secret **`PAT_PUSH`** = dieses Token.
3. https://cron-job.org (kostenlos): Cronjob mit URL
   `https://api.github.com/repos/Sin3qz/Strategies-dashboard/actions/workflows/refresh-dashboard.yml/dispatches`,
   alle 30 Minuten, Methode POST, Header `Authorization: Bearer <Token>`, `Accept: application/vnd.github+json`,
   `Content-Type: application/json`, Body `{"ref":"main"}`. Antwort 204 = ok.

**cron-job.org am schnellsten:** „Cronjob erstellen“ → unten **„CURL-Befehl importieren“** → diesen Befehl einfügen
(Token einsetzen) → Import; danach Terminplan „Alle 30 Minuten“ und **Testlauf** (Antwort 204):
```
curl -X POST -H "Authorization: Bearer DEIN_TOKEN" -H "Accept: application/vnd.github+json" -H "Content-Type: application/json" -d '{"ref":"main"}' https://api.github.com/repos/Sin3qz/Strategies-dashboard/actions/workflows/refresh-dashboard.yml/dispatches
```

## Positionen dauerhaft speichern
Im Tab **Rechner** Stückzahlen und Cash (auch negativ) eintragen → **„Auf GitHub speichern“**. Der Knopf startet den
Workflow `save-holdings.yml` (Token: Fine-grained, nur Strategies-dashboard, **Actions: Read and write** – dasselbe wie bei
cron-job.org; es bleibt nur im Browser). Der Workflow prüft die Eingabe, schreibt `data/wikifolio_holdings.json`, hängt den
Stand an `data/holdings_log.csv` an (Verlauf im Rechner) und rechnet das Dashboard neu. Nach jedem Handel bzw. zum
Monatswechsel speichern; der Cash-Wächter rechnet nur mit gespeicherten Ständen nach dem letzten Bot-Handel.
Cash-Baustein: Geldmarkt-ETF Xtrackers II EUR Overnight Rate Swap 1C (XEON, LU0290358497); der Rechner legt den
Bot-Cash-Anteil (abzüglich Gebühren-Puffer) dort an (Schalter „Bot-Cash im Geldmarkt-ETF halten“).

## Cash-Wächter und Push (ntfy)
Secret **`NTFY_TOPIC`** im Repo Strategies-dashboard (gleiches Topic wie bei den Bots). Das Dashboard meldet:
gekipptes Tagessignal, wikifolio investierbar, **Cash-Puffer fast leer** (Reserve für die nächsten 2 Handelstage reicht nicht
mehr) bzw. **negativ**. Der Cash-Wächter (`dashboard-data/cashwatch.py`) rechnet ab deinem gespeicherten Cash (ohne Eingabe: „unbekannt“, keine
Annahmen) die Zertifikategebühr je Tag und die Performancegebühr bei jedem neuen Hoch ab (zieht wikifolio auch vor der
Emission schon simulativ ab). Geldmarkt-ETF zählt als Anlage, nicht als Cash.
Test: *Run workflow* mit Haken **„Test-Nachricht an dein ntfy-Topic senden“**; der Datenstatus zeigt die Zeile „Push (ntfy)“.

## Alle Signale jetzt neu rechnen (von Hand)
Nur im Repo **Strategies-dashboard**: *Actions → Dashboard-Daten aktualisieren → Run workflow*. Ohne Haken stößt der Lauf
die Bots an, die heute noch nicht gerechnet haben; mit Haken **„Alle vier Bots jetzt neu rechnen lassen“** rechnen alle
vier sofort neu (Bots, die gerade laufen, werden übersprungen). Der Lauf wartet, bis die Bots fertig sind (höchstens 8 min),
und übernimmt ihr Ergebnis gleich in die Seite. In den einzelnen Bot-Repos musst du nichts starten.

## Wie es sich aktualisiert
Die GitHub Action `.github/workflows/refresh-dashboard.yml` läuft werktags stündlich (05:41–21:41 UTC) und am Wochenende 3×
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
