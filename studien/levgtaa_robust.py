"""Robustheit levGTAA mit dem Bot-Kern (momentum_core). Synthetisch: gehebelte Tagesrenditen der Bot-Reihen
(RET aus runner.prepare: 3x QQQ, 1x BTC, 3x IEF, 3x GLD). Entscheidung am Tag 'day' des Monats (-1 = Monatsletzter),
Handel Schluss naechster Handelstag, monatlich auf Zielquoten, dazwischen Drift, 0,1 % Kosten."""
import os as _os
import os
BOTS = _os.environ.get("BOT_REPO_DIR", _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..")))
import sys, os, pickle, itertools, math
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(BOTS, "levgtaa-signalbot"))
os.chdir(os.path.join(BOTS, "levgtaa-signalbot"))
from strategies import runner as R, momentum_core as MC
H = os.path.dirname(os.path.abspath(__file__))
f = os.path.join(H, "lev_raw.pkl")
if not os.path.exists(f):
    pickle.dump(R.load_data(), open(f, "wb"))
grid, P, RET, *_ = R.prepare(pickle.load(open(f, "rb")))
RV = np.nan_to_num(RET.values, nan=0.0)
idx = P.index
START = idx.searchsorted(pd.Timestamp("2004-06-01"))


def rows_for(day):
    per = idx.to_period("M"); out = []
    for _, g in pd.Series(np.arange(len(idx)), index=per).groupby(level=0):
        k = len(g) - 1 if day == -1 else min(day, len(g) - 1)
        out.append(g.iloc[k])
    out = np.array(out)
    return out[(idx[out] >= pd.Timestamp("2003-08-01")) & (out < len(idx) - 1)]


def run(K=30, Ls=range(125, 226), rankings=None, tilt=(0.4, 0.6), vt=0.55, windows=(42, 63, 84), day=-1):
    rankings = rankings or {"a": (1, 3, 6, 9), "b": (3, 6, 12)}
    rows = rows_for(day)
    W, _ = MC.decision_weights(P, rows, rankings, list(Ls), K, tilt)
    sc = MC.vt_scale(RET.values, rows, W, vt, windows) if vt else np.ones(len(rows))
    WF = W * sc[:, None]
    ex = {r + 1: WF[i] for i, r in enumerate(rows)}             # Handel am naechsten Handelstag
    V, w, eq = 1.0, np.zeros(P.shape[1]), []
    first = min(p for p in ex if p >= START)
    for j in range(first, len(idx)):
        if j > first:
            g = 1 + RV[j] @ w; w = w * (1 + RV[j]) / g if g > 0 else w; V *= g
        if j in ex:
            t = ex[j]; V *= 1 - 0.001 * np.abs(t - w).sum(); w = t.copy()
        eq.append(V)
    s = pd.Series(eq, index=idx[first:]); r = s.pct_change().dropna(); yrs = (s.index[-1] - s.index[0]).days / 365.25
    sub = {}
    for a, b in (("2004-06-01", "2011-12-31"), ("2012-01-01", "2018-12-31"), ("2019-01-01", "2026-12-31")):
        x = s[(s.index >= a) & (s.index <= b)]; sub[a[:4]] = (x.iloc[-1] / x.iloc[0]) ** (365.25 / (x.index[-1] - x.index[0]).days) - 1
    return {"cagr": (s.iloc[-1] / s.iloc[0]) ** (1 / yrs) - 1, "maxdd": (s / s.cummax() - 1).min(),
            "sharpe": r.mean() / r.std() * math.sqrt(252), **sub}
