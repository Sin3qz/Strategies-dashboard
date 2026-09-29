# Strategien — Signal-Dashboard

Statische Seite (GitHub Pages) für **levGTAA · levSpyBits · MR-Rebound-GTAA · 1xGTAA** (in dieser Reihenfolge).
Sie rechnet nichts selbst, sondern zeigt den zuletzt committeten Stand der vier Bot-Repos (`status_*.json`).
Wenn die Bots per GitHub Action laufen und committen, zeigt die Seite beim nächsten Laden automatisch den neuen Stand.

## Einrichtung
1. `index.html` in dieses Repo (public) hochladen.
2. Oben in `index.html` steht `const USER = "Sin3qz";` und der `SOURCES`-Block mit den Repo-Namen.
   Für MR-Rebound-GTAA werden der Reihe nach `mrreboundgtaa-signalbot`, `mr-rebound-gtaa-signalbot` und das alte
   `reversegtaa-signalbot` probiert (jeweils `status_mrreboundgtaa.json`) — die Seite funktioniert also vor und nach der
   Umbenennung. Die alte Datei `status_reversegtaa.json` wird nicht mehr gelesen (bitte im Repo löschen).
3. Settings → Pages → Deploy from branch → main / root.

Voraussetzung: Die Bot-Repos sind public und haben ihre Statusdatei mindestens einmal mit der neuen Version committet.

## Was die Karten zeigen
- Aktuelle Allokation mit echtem Invest-Hebel (levGTAA 3x/1x/5x/3x, MR-Rebound 3x/3x/3x und 5x TLT mit voller Quote);
  levGTAA und MR-Rebound mit einer Nachkommastelle inkl. Cash; bei levGTAA die Vola relativ zum 55-%-Cap.
- Handelssignal heute (BUY / SELL / Umschichtung / Monatswechsel, ggf. „verspätet“), ausstehende Wechsel/Monatssignale (⏳).
- Rebalancing: bei levGTAA und MR-Rebound-GTAA Signal- und Handelstag (Monatsletzter → 1. Handelstag) und der nächste Termin;
  bei levSpyBits und 1xGTAA der Cooldown.
- Kursstand, Frische und Datenwarnungen (fehlende Tage, Sprünge > 30 %).
- Signaltabelle, wie der Bot sie liefert.
- **Zeitbalken:** levGTAA = Platz 1 der letzten 120 Monatsentscheidungen; MR-Rebound-GTAA = gehaltenes Asset auf
  Platz 3 von 3 (schwächster SMA-Rang, Flop); 1xGTAA = Platz 1 der letzten 120 Handelstage; levSpyBits = im Markt
  (grün) oder Cash (grau) der letzten 120 Handelstage. Grau = Cash.

Dark/Light umschaltbar. **KEINE ANLAGEBERATUNG.**
