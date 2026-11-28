"""1xGTAA auf den echten Bot-Reihen (Bot-Loader, USD), EMU Value vor AW1T-Start mit EZU verkettet (wie gtaa1x_long.py)."""
import os, sys, pickle, itertools, numpy as np, pandas as pd
B = os.environ["BOT_REPO_DIR"] + "/1xgtaa-signalbot"; sys.path.insert(0, B); cwd = os.getcwd(); os.chdir(B)
from strategies import runner as RR, gtaa_botcore as G, common as U
from strategies.constants import CFG
raw = RR._load_raw(); emu = raw["EMU_VALUE"]; ezu = U.fetch_close("EZU", 3); first = emu.index[0]
base = ezu[ezu.index <= first]; raw["EMU_VALUE"] = pd.concat([ezu[ezu.index < first] / base.iloc[-1] * emu.iloc[0], emu]).sort_index()
CL, _ = RR.closes_on_grid(raw); os.chdir(cwd)
irx = pickle.load(open("raw.pkl", "rb"))["^IRX"]; RF = (irx.reindex(CL.index, method="ffill") / 100 / 252).fillna(0)
RET = CL.pct_change().fillna(0).values; RFV = RF.values; COLS = list(CL.columns)
def run(S, L, lookbacks, cool, cost=0.001, start=None):
    cfg = dict(CFG, S=S, L=L, lookbacks=tuple(lookbacks), cooldown_days=cool); cfg.pop("prev", None)
    idx, allocs, cds, ind, _ = G.compute_series(CL, cfg, live=False)
    W = np.array([[a.get(c, 0.0) for c in COLS] for a in allocs]); W = np.vstack([np.zeros(len(COLS)), W[:-1]])
    first = idx.searchsorted(pd.Timestamp(start or "2012-09-01")); w = W[first].copy(); V = 1 - cost * w.sum(); eq = []
    for j in range(first, len(idx)):
        if j > first:
            g = 1 + RET[j] @ w + (1 - w.sum()) * RFV[j]; w = w * (1 + RET[j]) / g if g > 0 else w; V *= g
            if not np.allclose(W[j], W[j - 1]): V *= 1 - cost * np.abs(W[j] - w).sum(); w = W[j].copy()
        eq.append(V)
    return pd.Series(eq, index=idx[first:])
LK = {"1/3/6/12": (1, 3, 6, 12), "1/3/6/9": (1, 3, 6, 9)}
def job(a):
    S, L, c, lk = a; s = run(S, L, LK[lk], c); r = s.pct_change().dropna(); dd = (s / s.cummax() - 1).min()
    th = np.array_split(r.values, 3); sh = [x.mean() / x.std() * np.sqrt(252) for x in th]
    return dict(S=S, L=L, cool=c, lk=lk, Sharpe=r.mean() / r.std() * np.sqrt(252), CAGR=s.iloc[-1] ** (252 / len(r)) - 1, MaxDD=dd, p1=sh[0], p2=sh[1], p3=sh[2])
if __name__ == "__main__":
    from multiprocessing import Pool
    print("Daten", CL.index[0].date(), CL.index[-1].date(), COLS)
    jobs = list(itertools.product((6, 8, 10, 12, 14, 15, 16, 18, 20, 22, 25), (130, 140, 150, 160, 170, 180, 190), (8, 10, 12), ("1/3/6/12",)))
    with Pool(3) as p: out = p.map(job, jobs, chunksize=4)
    pd.DataFrame(out).to_csv("gtaa1x_real_fein.csv", index=False); print("fertig", len(out))
