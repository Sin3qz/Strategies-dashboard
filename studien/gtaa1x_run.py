import numpy as np, pandas as pd, json, itertools, warnings
warnings.filterwarnings("ignore")
from gtaa1x_study import *
P = load()
START = P.index.searchsorted(pd.Timestamp("2013-01-02"))
res = []
def ev(tag, W, mode, **kw):
    s, tr = backtest(P, held(W, mode, idx=P.index, **kw), START)
    m = metrics(s, tr); m.update({"tag": tag, "mode": mode, **{k: v for k, v in kw.items()}}); m.update(periods(s)); res.append(m); return m
base, _ = fast_targets(P)
# E1 Rhythmus
for cd in (0, 2, 5, 10, 15, 20, 30, 40):
    ev("E1", base, "daily", cooldown=cd)
for d in [-1] + list(range(0, 21)):
    ev("E1", base, "monthly", day=d)
# E2 Parameter
LBS = [(1, 3, 6, 9), (1, 3, 6, 12), (3, 6, 12), (1, 3, 6), (3, 6, 9, 12), (1, 2, 3, 6)]
for S, L, lb in itertools.product((1, 5, 8, 10, 15, 20, 30), (100, 125, 150, 175, 200, 225, 250), LBS):
    W, _ = fast_targets(P, S=S, L=L, lookbacks=lb)
    for mode, kw in (("daily", {"cooldown": 10}), ("monthly", {"day": -1})):
        m = ev("E2", W, mode, **kw); m.update({"S": S, "L": L, "lb": "/".join(map(str, lb))})
# E3 Gewichte / Fallback
for wts, fb in itertools.product(((0.4, 0.6), (0.5, 0.5), (0.6, 0.4)), ("slotgate", "slotgate_floor")):
    W, _ = fast_targets(P, weights=wts, fallback=fb)
    for mode, kw in (("daily", {"cooldown": 10}), ("monthly", {"day": -1})):
        m = ev("E3", W, mode, **kw); m.update({"w": f"{int(wts[0]*100)}/{int(wts[1]*100)}", "fb": fb})
# E4 levGTAA-Ensemble
for name, rk, K in (("levGTAA 1/3/6/9+3/6/12, SMA30/125-225", {"a": (1, 3, 6, 9), "b": (3, 6, 12)}, 30),
                    ("nur 1/3/6/9, SMA30/125-225", {"a": (1, 3, 6, 9)}, 30),
                    ("1/3/6/9+3/6/12, SMA8/125-225", {"a": (1, 3, 6, 9), "b": (3, 6, 12)}, 8)):
    W, _ = ensemble_targets(P, rk, list(range(125, 226)), K)
    for mode, kw in (("daily", {"cooldown": 10}), ("daily", {"cooldown": 0}), ("monthly", {"day": -1}), ("monthly", {"day": 0})):
        m = ev("E4", W, mode, **kw); m["ens"] = name
pd.DataFrame(res).to_csv("results.csv", index=False)
print("Backtests:", len(res))
