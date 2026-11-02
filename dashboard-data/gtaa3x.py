"""3xGTAA – Vergleichsmodell ohne eigenen Bot (nur Performance-Seite).

Regel wie levGTAA, nur mit diesen Abweichungen:
  - Korb aus 6 Bausteinen: die vier levGTAA-Bausteine (3x Nasdaq 100, 1x Bitcoin, 3x US-Treasury 7-10y, 3x Gold)
    plus 3x Euro Stoxx 50 und 2x WTI-Rohöl
  - eine Rangliste: Momentum = Mittel der 1/3/6/9-Monatsrenditen (21 Handelstage je Monat)
  - Trend nur SMA10 > SMA150 (kein Mittel über mehrere Längen)
  - zulässig: Momentum > 0 und Trend positiv; die besten 3 zulässigen je 1/3, fehlende Plätze -> Cash
  - kein Vol-Target
Gleich wie levGTAA: Signale auf 1x-Kursen (^NDX, BTC-USD, TLT, GC=F, dazu ^STOXX50E und der WTI-Future CL=F),
Signal am letzten US-Handelstag des Monats, Handel am ersten Handelstag danach, Bitcoin mit dem jüngsten
abgeschlossenen Tagesschluss vor dem Handelstag (Bot-Funktion btc_override).

Aufruf: python3 gtaa3x.py <levgtaa-repo-dir> <decisions_3xgtaa.csv>
"""
import os, sys
repo, out = sys.argv[1], os.path.abspath(sys.argv[2])
os.chdir(repo); sys.path.insert(0, repo)
import numpy as np, pandas as pd
from strategies import runner as R, common as U

EXTRA = {"EU50": "^STOXX50E", "WTI": "CL=F"}
ORDER = list(R.AL) + list(EXTRA)                     # NASDAQ100, BTC, UST_IEF, GOLD, EU50, WTI
MONTHS, S, L, N = (1, 3, 6, 9), 10, 150, 3
START = "2008-01-01"


def weights(Pi):
    """Zielgewichte am letzten Tag von Pi (Kurse bis einschließlich Entscheidungstag)."""
    last = Pi.iloc[-1]
    mom = sum(last / Pi.iloc[-1 - 21 * m] - 1 for m in MONTHS) / len(MONTHS) if len(Pi) > 21 * max(MONTHS) else last * np.nan
    trend = Pi.iloc[-S:].mean() / Pi.iloc[-L:].mean() - 1 if len(Pi) >= L else last * np.nan
    el = [a for a in ORDER if np.isfinite(mom[a]) and np.isfinite(trend[a]) and mom[a] > 0 and trend[a] > 0
          and Pi[a].iloc[-L:].notna().all()]
    el.sort(key=lambda a: -mom[a])                   # stabil: bei Gleichstand Korb-Reihenfolge
    return {a: 1.0 / N for a in el[:N]}


raw = R.load_data()
grid, P, RET, *_ = R.prepare(raw)
P = P[list(R.AL)].copy()
for k, t in EXTRA.items():
    s = U.fetch_close(t, 3)
    s = s.where(s > 0).ffill()                       # WTI-Future am 20.04.2020 negativ: letzter positiver Kurs
    P[k] = U.oncal(s, grid)
btc = R.btc_series(raw)
rows = np.where(U.month_end_flags(P.index) & (P.index >= pd.Timestamp(START)))[0]
recs = []
for i in rows:
    Pb, _ = R.btc_override(P[list(R.AL)], int(i), btc)   # nur die Bitcoin-Zeile des Entscheidungstags ersetzt
    Pi = P.iloc[:i + 1].copy()
    Pi["BTC"] = Pb["BTC"]
    w = weights(Pi.iloc[-(21 * max(MONTHS) + 5):])
    recs.append({"date": P.index[i].date().isoformat(), **{a: round(w.get(a, 0.0), 4) for a in ORDER}})
dec = pd.DataFrame(recs)
dec["rebalance"] = "monthly"
dec.to_csv(out, index=False)
last = dec.iloc[-1]
print("3xGTAA", len(dec), "Entscheidungen; letzte", last["date"], {a: last[a] for a in ORDER if last[a] > 0} or "Cash")
