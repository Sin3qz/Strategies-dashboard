"""1xGTAA mit langer Historie (nur Performance-Seite): Entscheidungen mit dem unveraenderten Code des 1xGTAA-Bots,
aber mit einer Ersatzreihe fuer EMU Value vor dem ersten Kurs des Amundi MSCI EMU Value (AW1T.DE, Yahoo ab 08/2022).

Der Bot selbst rechnet nur mit Tagen, an denen alle sieben Signalreihen einen Kurs haben, und braucht 252 Handelstage
Vorlauf (12-Monats-Momentum). Seine Historie beginnt deshalb erst 08/2022, das erste Jahr ist Cash (Vorlauf).
Hier wird EMU Value vor 08/2022 mit dem iShares MSCI EMU (EZU, USD; gleiche Region, breiter Index statt Value)
verkettet: dessen Tagesrenditen bis zum ersten AW1T-Kurs, ab dann AW1T unveraendert (wie im Bot nach USD umgerechnet).
Alle anderen Signalreihen, Parameter und Regeln sind die des Bots.

Aufruf: python3 gtaa1x_long.py <1xgtaa-repo-dir> <decisions_1xgtaa_long.csv>
"""
import os, sys
repo, out = sys.argv[1], os.path.abspath(sys.argv[2])
os.chdir(repo); sys.path.insert(0, repo)
import pandas as pd
from strategies import runner as R, gtaa_botcore as G, common as U
from strategies.constants import CFG

PROXY = "EZU"
raw = R._load_raw()
emu = raw["EMU_VALUE"]                                   # AW1T.DE in USD (wie im Bot)
ezu = U.fetch_close(PROXY, 3)
first = emu.index[0]
base = ezu[ezu.index <= first]
if not len(base):
    raise RuntimeError(f"{PROXY}: keine Kurse vor {first.date()}")
pre = ezu[ezu.index < first] / base.iloc[-1] * emu.iloc[0]   # am ersten AW1T-Tag auf dessen Kurs angeschlossen
raw["EMU_VALUE"] = pd.concat([pre, emu]).sort_index()
closes, _ = R.closes_on_grid(raw)
idx, allocs, cds, ind, _ = G.compute_series(closes, CFG, live=True)
assets = list(closes.columns)
dec = pd.DataFrame([{a: round(al.get(a, 0.0), 4) for a in assets} for al in allocs])
dec.insert(0, "date", [d.date().isoformat() for d in idx])
dec["rebalance"] = "on_change"
dec["proxy"] = [int(d < first) for d in idx]             # 1 = EMU Value aus der Ersatzreihe
dec.to_csv(out, index=False)
last = dec.iloc[-1]
print("1xGTAA lang:", len(dec), "Tage ab", dec["date"].iloc[0], "| Ersatzreihe bis", (first - pd.Timedelta(days=1)).date(),
      "| letzte", last["date"], {a: last[a] for a in assets if last[a] > 0} or "Cash")
