import itertools, sys, pickle, numpy as np, pandas as pd
from multiprocessing import Pool
DAYS = list(range(0, 20)) + [-1]
RK = {"1369+3612": {"a": (1, 3, 6, 9), "b": (3, 6, 12)}, "13612+3612": {"a": (1, 3, 6, 12), "b": (3, 6, 12)},
      "13612": {"a": (1, 3, 6, 12)}, "3612": {"a": (3, 6, 12)}}
LK = {"1/3/6/12": (1, 3, 6, 12), "1/3/6/9": (1, 3, 6, 9), "3/6/12": (3, 6, 12), "3/6/9/12": (3, 6, 9, 12)}
def lev(a):
    import engine as E
    rk, K, c = a; rets, dds = [], []
    for d in DAYS:
        s, _ = E.run(rankings=RK[rk], K=K, Ls=range(c - 50, c + 51), day=d); s = s[s.index >= "1987-09-01"]; rets.append(s.pct_change()); dds.append((s / s.cummax() - 1).min())
    r = pd.concat(rets, axis=1).dropna().mean(axis=1); s = (1 + r).cumprod(); m = E.metrics(s)
    return dict(rank=rk, K=K, Lmid=c, Sharpe=m["Sharpe"], CAGR=m["CAGR"], MaxDD=m["MaxDD"], DD_tage=np.mean(dds), DD_schl=min(dds), y87=m.get("1987"), y00=m.get("2000"), y10=m.get("2010")), r.astype("float32")
def one(a):
    import gtaa1x as X, met
    S, L, co, lk = a; s = X.run(S, L, LK[lk], co); m = met.metrics(s, X.RF)
    f = lambda x, y: met.metrics(s[x:y] / s[x:y].iloc[0], X.RF)["Sharpe"]
    return dict(S=S, L=L, cool=co, lk=lk, Sharpe=m["Sharpe"], CAGR=m["CAGR"], MaxDD=m["MaxDD"], s95=f("1995", "2005"), s06=f("2006", "2015"), s16=f("2016", "2026")), s.pct_change().astype("float32")
JOBS = {"lev": (lev, list(itertools.product(RK, range(20, 81, 5), (150, 175, 200, 225, 250)))),
        "1x": (one, list(itertools.product(range(3, 21), range(130, 221, 10), (5, 8, 10, 12, 15), LK)))}
if __name__ == "__main__":
    f, jobs = JOBS[sys.argv[1]]
    with Pool(4) as p: out = p.map(f, jobs, chunksize=4)
    pd.DataFrame([o[0] for o in out]).to_csv(f"joint_{sys.argv[1]}.csv", index=False)
    pickle.dump({tuple(o[0][k] for k in (["rank", "K", "Lmid"] if sys.argv[1] == "lev" else ["S", "L", "cool", "lk"])): o[1] for o in out}, open(f"joint_{sys.argv[1]}.pkl", "wb"))
    print(sys.argv[1], "fertig", len(out))
