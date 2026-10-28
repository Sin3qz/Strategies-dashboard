"""Robustheit levTipsRegime: SMA-Laengen, Cooldown, IEF-Zweig. Synthetisch ab 10/2004.
Markt = 75 % 3x S&P 500 TR + 25 % Bitcoin (vor 10/2014: 100 % 3x S&P 500 TR), IEF = 3x IEF, Cash 0 %.
Signal Schluss d -> Handel Schluss d+1, 0,1 % Kosten je umgeschichtetem Euro."""
import os as _os
import os
BOTS = _os.environ.get("BOT_REPO_DIR", _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..")))
import sys, itertools, pickle, os, math
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(BOTS, "levtipsregime-signalbot"))
from strategies import common as U
H = os.path.dirname(os.path.abspath(__file__))
f = os.path.join(H, "tips_raw.pkl")
if not os.path.exists(f):
    pickle.dump({t: U.fetch_close(t, 3) for t in ("^SP500TR", "TIP", "TLT", "IEF", "BTC-USD")}, open(f, "wb"))
raw = pickle.load(open(f, "rb"))
grid = U.build_grid("1990-01-02", us_series=[raw["^SP500TR"], raw["TIP"], raw["TLT"]])
spy, tips, tlt, ief, btc = (U.oncal(raw[t], grid).values for t in ("^SP500TR", "TIP", "TLT", "IEF", "BTC-USD"))
r_spx = 3 * np.nan_to_num(np.diff(spy, prepend=np.nan) / np.roll(spy, 1), nan=0)
r_ief = 3 * np.nan_to_num(np.diff(ief, prepend=np.nan) / np.roll(ief, 1), nan=0)
r_btc = np.nan_to_num(np.diff(btc, prepend=np.nan) / np.roll(btc, 1), nan=0)
has_btc = grid >= pd.Timestamp("2014-10-01")
r_mkt = np.where(has_btc, 0.75 * r_spx + 0.25 * r_btc, r_spx)           # taeglich auf 75/25 (Naeherung)
START = grid.searchsorted(pd.Timestamp("2004-10-01"))


def sma_dist(x, n):
    s = pd.Series(x).rolling(n).mean().values
    return x / s - 1


def run(ss=280, ts=220, ls=200, cd=10, ief_on=True):
    ds, dt, dl = sma_dist(spy, ss), sma_dist(tips, ts), sma_dist(tlt, ls)
    mk = (np.nan_to_num(ds, nan=-1) > 0) & (np.nan_to_num(dt, nan=-1) > 0)
    ie = ief_on & (np.nan_to_num(dt, nan=1) < 0) & (np.nan_to_num(dl, nan=-1) > 0) & ~mk
    tgt = np.where(mk, 1, np.where(ie, 2, 0))
    cur, fro = 0, -1; st = np.zeros(len(tgt), int)
    for i, t in enumerate(tgt):
        if t != cur and i > fro:
            cur = t; fro = i + cd
        st[i] = cur
    held = np.roll(st, 2); held[:2] = 0                                 # Signal d -> Handel Schluss d+1 -> Rendite ab d+2
    r = np.where(held == 1, r_mkt, np.where(held == 2, r_ief, 0.0))
    chg = np.roll(st, 1) != np.roll(st, 2); chg[:2] = False
    r = r - chg * 0.001 * np.where((np.roll(st, 1) > 0) & (np.roll(st, 2) > 0), 2, 1)
    r = r[START:]; eq = np.cumprod(1 + r); yrs = (grid[-1] - grid[START]).days / 365.25
    dd = (eq / np.maximum.accumulate(eq) - 1).min()
    sub = {}
    for a, b in (("2004-10-01", "2011-12-31"), ("2012-01-01", "2018-12-31"), ("2019-01-01", "2026-12-31")):
        m = (grid[START:] >= a) & (grid[START:] <= b); x = np.cumprod(1 + r[m]); y = m.sum() / 252
        sub[a[:4]] = x[-1] ** (1 / y) - 1
    return {"cagr": eq[-1] ** (1 / yrs) - 1, "maxdd": dd, "sharpe": r.mean() / r.std() * math.sqrt(252),
            "switches_pa": int((np.diff(st[START:]) != 0).sum()) / yrs, **sub}


if __name__ == "__main__":
    rows = []
    for ss, ts, cd, on in itertools.product(range(200, 381, 20), range(140, 321, 20), (5, 10, 15, 20), (True, False)):
        rows.append({"ss": ss, "ts": ts, "ls": 200, "cd": cd, "ief": on, **run(ss, ts, 200, cd, on)})
    for ls in (100, 125, 150, 175, 200, 225, 250, 300):
        for ss, ts in ((280, 220), (260, 200), (300, 240)):
            rows.append({"ss": ss, "ts": ts, "ls": ls, "cd": 10, "ief": True, "tag": "tlt", **run(ss, ts, ls, 10, True)})
    pd.DataFrame(rows).to_csv(os.path.join(H, "tips_results.csv"), index=False)
    print(len(rows), "Laeufe")
