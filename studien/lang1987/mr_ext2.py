import itertools, pickle, pandas as pd, numpy as np
from multiprocessing import Pool
from mrgrid import work
import met
S = [(75, 125), (100, 150), (125, 175), (150, 200)]; L = [(175, 250), (200, 275)]
R = [(42, 50, 56), (56, 63, 75), (84, 105, 126)]; G = [(100, 200, 250), (150, 200, 250)]
def job(a):
    a, r, ms = work(a); s = (1 + r.astype(float)).cumprod(); m = met.metrics(s)
    return dict(S=str(a[0]), L=str(a[1]), R=str(a[2]), G=str(a[3]), Sharpe=m["Sharpe"], CAGR=m["CAGR"], MaxDD=m["MaxDD"], DD_tage=ms[:, 2].mean(),
                MM3=min(met.metrics(s[x:y] / s[x:y].iloc[0])["CAGR"] for x, y in (("1995", "2005"), ("2005", "2016"), ("2016", "2027")))), r
if __name__ == "__main__":
    with Pool(3) as p: out = p.map(job, list(itertools.product(S, L, R, G)), chunksize=1)
    pd.DataFrame([o[0] for o in out]).to_csv("mr_ext2.csv", index=False); pickle.dump({tuple(o[0][k] for k in "SLRG"): o[1] for o in out}, open("mr_ext2.pkl", "wb")); print("fertig", len(out))
