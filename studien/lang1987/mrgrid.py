import itertools, pickle, numpy as np, pandas as pd
from multiprocessing import Pool
SB = [(25, 75), (50, 100), (75, 125), (100, 150), (125, 175)]; LB = [(125, 200), (150, 225), (175, 250), (200, 275), (225, 300)]
RB = [(21, 28, 35), (35, 42, 50), (42, 50, 56), (56, 63, 75), (63, 84, 105)]; GB = [(50, 100, 150), (100, 150, 200), (100, 200, 250), (150, 200, 250), (200, 250, 300)]
DAYS = list(range(0, 20)) + [-1]
def work(a):
    import mrengine as ME
    import met
    S, L, R, G = a; rets, ms = [], []
    for d in DAYS:
        s = ME.run(S, L, R, G, day=d); s = s[s.index >= "1995-07-01"]; rets.append(s.pct_change()); m = met.metrics(s, ME.RF); ms.append((m["CAGR"], m["Sharpe"], m["MaxDD"]))
    return a, pd.concat(rets, axis=1).dropna().mean(axis=1).astype("float32"), np.array(ms)
if __name__ == "__main__":
    with Pool(4) as p: out = p.map(work, list(itertools.product(SB, LB, RB, GB)), chunksize=4)
    pickle.dump({a: (r, m) for a, r, m in out}, open("mrgrid.pkl", "wb")); print("fertig", len(out))
