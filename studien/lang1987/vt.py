import numpy as np, pandas as pd, sys
from multiprocessing import Pool
DAYS = list(range(0, 20)) + [-1]
RK = {"a": (1, 3, 6, 12), "b": (3, 6, 12)}
def job(a):
    import engine as E
    vt, K = a; rets, dds = [], []
    for d in DAYS:
        s, _ = E.run(rankings=RK, K=K, Ls=range(150, 251), vt=vt, day=d); s = s[s.index >= "1987-09-01"]; rets.append(s.pct_change()); dds.append((s / s.cummax() - 1).min())
    r = pd.concat(rets, axis=1).dropna().mean(axis=1); s = (1 + r).cumprod(); m = E.metrics(s)
    th = np.array_split(r.values, 3)
    return dict(vt=vt, K=K, Sharpe=m["Sharpe"], CAGR=m["CAGR"], MaxDD=m["MaxDD"], DD_tage=np.mean(dds), **{f"D{i+1}": x.mean() / x.std() * np.sqrt(252) for i, x in enumerate(th)})
if __name__ == "__main__":
    with Pool(3) as p: out = p.map(job, [(v, 50) for v in (0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70)])
    pd.DataFrame(out).to_csv("vt.csv", index=False); print(pd.DataFrame(out).round(3).to_string(index=False))
