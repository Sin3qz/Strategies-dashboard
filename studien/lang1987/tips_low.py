import itertools, pandas as pd, tipsengine as TE, met
from multiprocessing import Pool
def job(a):
    sp, ti, co = a; s, _ = TE.run(sp, ti, 200, co); m = met.metrics(s, TE.RF); s2 = s[s.index >= "2001-06-01"]; m2 = met.metrics(s2 / s2.iloc[0], TE.RF)
    return dict(spy=sp, tips=ti, cool=co, Sharpe=m["Sharpe"], MaxDD=m["MaxDD"], Sharpe_01=m2["Sharpe"], MaxDD_01=m2["MaxDD"])
if __name__ == "__main__":
    jobs = list(itertools.product((210, 220, 230), range(60, 151, 10), (5, 10, 15)))
    with Pool(4) as p: out = p.map(job, jobs)
    pd.DataFrame(out).to_csv("tips_low.csv", index=False); print("fertig", len(out))
