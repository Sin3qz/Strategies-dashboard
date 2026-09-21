# GTAA Dashboard (alle 4 Strategien)

Neues, eigenständiges Dashboard für **1xGTAA · levGTAA · reverse-GTAA · levSpyBits**.
Es rechnet **nichts** selbst, sondern spiegelt den zuletzt committeten Stand der vier Bot-Repos
(Single Source of Truth = die Bots). Reine statische Seite — kein Server, keine Action nötig.

## Einrichtung
1. Repo (public) anlegen, `index.html` hochladen.
2. In `index.html` oben steht **`const USER = "Sin3qz";`** (dein GitHub-Name). Die vier Roh-URLs bauen sich daraus:
   `1xgtaa-signalbot/status_1xgtaa.json`, `levgtaa-signalbot/status_levgtaa.json`,
   `reversegtaa-signalbot/status_reversegtaa.json`, `levspybits-signalbot/letsgo_status.json` (+ History).
   Abweichende Repo-Namen → im `SOURCES`-Block anpassen (v.a. falls dein levSpyBits-Repo noch `letsgo-signalbot` heißt).
3. **Settings → Pages → Deploy from branch → main / root.** Fertig.

Voraussetzung: die vier Bot-Repos sind **public** (raw.githubusercontent liefert dann CORS-frei) und haben
ihre `status_*.json` schon einmal committet.

## Was die Karten zeigen
Pro Strategie: aktuelle Allokation (Bausteine + Gewicht + Hebel), Handelssignal heute (BUY/SELL/SWITCH),
Frische, „nächstes Rebalancing" bzw. Cooldown-Rest, aufklappbare Signal-Details und ein Allokations-Verlauf.

- **Sortierung:** Assets nach dem rangbestimmenden Baustein — 1x/levGTAA nach **Momentum** (absteigend),
  reverse-GTAA nach **SMA110/175-Rang** (aufsteigend, Flop zuerst). Der rangbestimmende Baustein steht **links**.
- **SMA-Spalten** zeigen den **absoluten Abstand** in % (grün = positiv, rot = negativ), nicht nur Haken/Kreuz.
- **Überschriften** je Strategie: 1x/lev „Momentum (1369M)“ + „SMA8/150“; reverse „SMA110/175-Rang“ + „Trend (123M)“;
  levSpyBits „Trend (SMA160)“ + „ΔSMA“.
- **reverse-GTAA:** angezeigte Allokation = Entscheidung des **Monatsletzten** (ntfy kommt zusätzlich am 1. Handelstag).
- **Verlaufsbalken** unten: Farbe = je Zeitpunkt gehaltenes Top-Asset, grau = Cash (reine Anzeige).

Dark/Light umschaltbar. **KEINE ANLAGEBERATUNG.**
