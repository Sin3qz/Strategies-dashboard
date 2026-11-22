"""Backtest-Maschine levGTAA mit dem unveraenderten Bot-Kern (momentum_core)."""
import sys, math, numpy as np, pandas as pd
sys.path.insert(0, "" + __import__("os").environ.get("BOT_REPO_DIR", "../../..") + "/levgtaa-signalbot")
from strategies import momentum_core as MC
import levdata as D
grid, P, RVT, RP, RF = D.build()
RPV = np.nan_to_num(RP.values, nan=0.0); RFV = RF.values; IDX = P.index
START = "1987-08-01"
per = IDX.to_period("M")

def rows_for(day=-1):
    out = []
    for _, g in pd.Series(np.arange(len(IDX)), index=per).groupby(level=0):
        out.append(g.iloc[len(g) - 1] if day == -1 else g.iloc[min(day, len(g) - 1)])
    out = np.array(out)
    return out[(IDX[out] >= pd.Timestamp(START) - pd.Timedelta(days=40)) & (out < len(IDX) - 1)]

ROWS = {-1: rows_for(-1)}
def run(rankings=None, K=30, Ls=range(125, 226), tilt=(0.4, 0.6), vt=0.55, windows=(42, 63, 84), day=-1, cost=0.001, start=START):
    rankings = rankings or {"a": (1, 3, 6, 9), "b": (3, 6, 12)}
    rows = ROWS.setdefault(day, rows_for(day))
    W, _ = MC.decision_weights(P, rows, rankings, list(Ls), K, tilt)
    sc = MC.vt_scale(RVT.values, rows, W, vt, windows) if vt else np.ones(len(rows))
    WF = W * sc[:, None]
    ex = {r + 1: WF[i] for i, r in enumerate(rows)}
    first = min(p for p in ex if IDX[p] >= pd.Timestamp(start))
    w0 = ex[max(p for p in ex if p <= first)]
    V, w, eq = 1.0, w0.copy(), []
    V *= 1 - cost * np.abs(w).sum()
    for j in range(first, len(IDX)):
        if j > first:
            r = RPV[j]; c = 1 - w.sum()
            g = 1 + r @ w + c * RFV[j]
            w = w * (1 + r) / g if g > 0 else w; V *= g
            if j in ex:
                t = ex[j]; V *= 1 - cost * np.abs(t - w).sum(); w = t.copy()
        eq.append(V)
    return pd.Series(eq, index=IDX[first:]), pd.DataFrame(WF, index=IDX[rows], columns=D.AL)

def metrics(s, rf=RF):
    r = s.pct_change().dropna(); y = (s.index[-1] - s.index[0]).days / 365.25
    dd = s / s.cummax() - 1; ex = r - rf.reindex(r.index).fillna(0)
    m = s.resample("ME").last(); y12 = (m / m.shift(12) - 1).dropna()
    uw = (dd < 0).astype(int); longest = uw.groupby((uw == 0).cumsum()).sum().max()
    cagr = (s.iloc[-1] / s.iloc[0]) ** (1 / y) - 1
    out = {"CAGR": cagr, "MaxDD": dd.min(), "Vola": r.std() * math.sqrt(252),
           "Sharpe": ex.mean() / r.std() * math.sqrt(252), "Sortino": ex.mean() / r[r < 0].std() * math.sqrt(252),
           "Calmar": cagr / -dd.min(), "Ulcer": math.sqrt((dd ** 2).mean()), "schl12M": y12.min(), "unterWasserJ": longest / 252}
    for a, b in (("1987-08-01", "1999-12-31"), ("2000-01-01", "2009-12-31"), ("2010-01-01", "2026-12-31")):
        x = s[(s.index >= a) & (s.index <= b)]
        if len(x) > 50: out[a[:4]] = (x.iloc[-1] / x.iloc[0]) ** (365.25 / (x.index[-1] - x.index[0]).days) - 1
    return out
