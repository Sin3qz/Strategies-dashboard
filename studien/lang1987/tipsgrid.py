import itertools, pickle, time, numpy as np, pandas as pd, tipsengine as TE
from engine import metrics
SP = range(160, 361, 20); TI = range(120, 321, 20); TL = range(120, 281, 40); CO = (0, 5, 10, 15, 20)
res, rets = [], {}
t = time.time()
for sp, ti, tl, co in itertools.product(SP, TI, TL, CO):
    s, _ = TE.run(sp, ti, tl, co); m = metrics(s); s2 = s[s.index >= "2001-06-01"]; m2 = metrics(s2 / s2.iloc[0])
    mm = []
    for n in (3, 5):
        for ix in np.array_split(np.arange(len(s)), n):
            x = s.iloc[ix]; mm.append((x.iloc[-1] / x.iloc[0]) ** (365.25 / (x.index[-1] - x.index[0]).days) - 1)
    res.append({"spy": sp, "tips": ti, "tlt": tl, "cool": co, **m, "MM3_CAGR": min(mm[:3]), "MM5_CAGR": min(mm[3:]),
                **{f"{k}_01": v for k, v in m2.items() if k in ("CAGR", "MaxDD", "Sharpe", "Calmar")}})
    rets[(sp, ti, tl, co)] = s.pct_change().astype("float32")
pd.DataFrame(res).to_csv("grid_levtips.csv", index=False); pickle.dump(rets, open("tips_rets.pkl", "wb"))
print(len(res), "Varianten in", round(time.time() - t), "s")
