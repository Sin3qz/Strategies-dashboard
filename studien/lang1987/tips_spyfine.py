import itertools, pickle, math, numpy as np, pandas as pd
from multiprocessing import Pool
import tipsengine as TE
def job(a):
    s, _ = TE.run(a[0], a[1], 200, a[2]); return a, s.pct_change().astype("float32")
if __name__ == "__main__":
    jobs = list(itertools.product(range(185, 266, 5), (160, 170, 180, 190, 200), (8, 10, 12)))
    with Pool(3) as p: out = dict(p.map(job, jobs, chunksize=3))
    pickle.dump(out, open("tips_spyfine.pkl", "wb"))
    R = pd.concat(out, axis=1).dropna(); sh = lambda X: X.mean() / X.std() * math.sqrt(252)
    def mdd(X): v = (1 + X).cumprod(); return (v / v.cummax() - 1).min()
    P = {"gesamt": R, "ab2001": R[R.index >= "2001-06-01"], "2000-03": R[(R.index >= "1999-06-01") & (R.index < "2004-01-01")], "2018-26": R[R.index >= "2018-01-01"]}
    rows = []
    for spy in range(185, 266, 5):
        c = [k for k in R.columns if k[0] == spy]
        rows.append({"S&P": spy, **{f"Sh_{k}": sh(v[c]).mean() for k, v in P.items()}, "MaxDD": mdd(R[c]).mean(), "MaxDD_schlechteste": mdd(R[c]).min(), "MaxDD_2000-03": mdd(P["2000-03"][c]).mean(), "Anteil<-65%": (mdd(R[c]) < -0.65).mean()})
    print(pd.DataFrame(rows).round(3).to_string(index=False))
