# GTAA Dashboard (alle 4 Strategien)

Neues, eigenständiges Dashboard für **1xGTAA · levGTAA · reverse-GTAA · 3xSpyTips+BTC**.
Es rechnet **nichts** selbst, sondern spiegelt den zuletzt committeten Stand der vier Bot-Repos
(Single Source of Truth = die Bots). Reine statische Seite — kein Server, keine Action nötig.

## Einrichtung
1. Repo (public) anlegen, `index.html` hochladen.
2. In `index.html` oben **`const USER = "DEIN_GITHUB_NAME";`** setzen. Die vier Roh-URLs bauen sich daraus:
   `1xgtaa-signalbot/status_1xgtaa.json`, `levgtaa-signalbot/status_levgtaa.json`,
   `reversegtaa-signalbot/status_reversegtaa.json`, `letsgo-signalbot/letsgo_status.json` (+ History).
   Abweichende Repo-Namen → im `SOURCES`-Block anpassen.
3. **Settings → Pages → Deploy from branch → main / root.** Fertig.

Voraussetzung: die vier Bot-Repos sind **public** (raw.githubusercontent liefert dann CORS-frei) und haben
ihre `status_*.json` schon einmal committet.

## Was die Karten zeigen
Pro Strategie: aktuelle Allokation (Bausteine + Gewicht + Hebel), Handelssignal heute (BUY/SELL/SWITCH),
Frische, „nächstes Rebalancing" bzw. Cooldown-Rest, aufklappbare Signal-Details und ein Allokations-Verlauf.
Dark/Light umschaltbar. **KEINE ANLAGEBERATUNG.**
