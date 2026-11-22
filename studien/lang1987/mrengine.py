import sys, numpy as np, pandas as pd
sys.path.insert(0, "" + __import__("os").environ.get("BOT_REPO_DIR", "../../..") + "/mrreboundgtaa-signalbot")
from strategies import dip_core as DC
from strategies.constants import BASKETS
import mrdata as M
GRID, P, RP, RF = M.build(); RPV = np.nan_to_num(RP.values); RFV = RF.values; IDX = P.index; per = IDX.to_period("M")
START = "1995-06-01"
def rows_for(day):
    out = np.array([g.iloc[len(g) - 1] if day == -1 else g.iloc[min(day, len(g) - 1)] for _, g in pd.Series(np.arange(len(IDX)), index=per).groupby(level=0)])
    return out[(IDX[out] >= pd.Timestamp(START) - pd.Timedelta(days=40)) & (out < len(IDX) - 1)]
ROWS = {}
def run(S=(75, 125), L=(175, 250), R=(42, 50, 56), G=(100, 200, 250), tilt=(1 / 3, 2 / 3), day=-1, step=5, cost=0.001):
    rows = ROWS.setdefault(day, rows_for(day))
    W, _ = DC.dip_weights(P, rows, BASKETS, list(range(S[0], S[1] + 1, step)), list(range(L[0], L[1] + 1, step)), list(R), list(G), tilt)
    ex = {r + 1: W[i] for i, r in enumerate(rows)}; first = min(p for p in ex if IDX[p] >= pd.Timestamp(START))
    w = ex[max(p for p in ex if p <= first)].copy(); V = 1 - cost * np.abs(w).sum(); eq = []
    for j in range(first, len(IDX)):
        if j > first:
            g = 1 + RPV[j] @ w + (1 - w.sum()) * RFV[j]; w = w * (1 + RPV[j]) / g if g > 0 else w; V *= g
            if j in ex: t = ex[j]; V *= 1 - cost * np.abs(t - w).sum(); w = t.copy()
        eq.append(V)
    return pd.Series(eq, index=IDX[first:])
