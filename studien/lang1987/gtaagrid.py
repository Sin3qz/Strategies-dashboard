import itertools, pickle, numpy as np, pandas as pd
from multiprocessing import Pool
SS = [3, 5, 8, 10, 15, 20, 30]; LL = [100, 125, 150, 175, 200, 250]
LK = {"1/3/6/12 (aktuell)": (1, 3, 6, 12), "1/3/6/9": (1, 3, 6, 9), "3/6/12": (3, 6, 12), "1/3/6": (1, 3, 6), "6/12": (6, 12), "3/6/9/12": (3, 6, 9, 12)}
CO = [0, 5, 10, 15, 20]
def work(a):
    import gtaa1x as X, met
    S, L, lk, co = a; s = X.run(S, L, LK[lk], co); m = met.metrics(s, X.RF)
    s2 = s[s.index >= "2009-01-01"]; m2 = met.metrics(s2 / s2.iloc[0], X.RF)
    return {"S": S, "L": L, "lk": lk, "cool": co, **m, "CAGR_09": m2["CAGR"], "Sharpe_09": m2["Sharpe"], "MaxDD_09": m2["MaxDD"]}, s.pct_change().astype("float32")
if __name__ == "__main__":
    combos = list(itertools.product(SS, LL, LK, CO))
    with Pool(2) as p: out = p.map(work, combos, chunksize=8)
    pd.DataFrame([o[0] for o in out]).to_csv("grid_1xgtaa.csv", index=False)
    pickle.dump({c: o[1] for c, o in zip(combos, out)}, open("gtaa_rets.pkl", "wb")); print("fertig", len(out))
