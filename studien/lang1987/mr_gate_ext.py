import itertools, pandas as pd
from multiprocessing import Pool
from mrgrid import work
import met
S = [(75, 125), (100, 150)]; L = [(150, 225), (175, 250), (200, 275), (225, 300)]; R = [(42, 50, 56)]
G = [(100, 200, 250), (150, 200, 250), (200, 250, 300), (250, 300, 350), (300, 350, 400)]
def job(a):
    a, r, ms = work(a); s = (1 + r.astype(float)).cumprod(); m = met.metrics(s)
    return dict(S=str(a[0]), L=str(a[1]), G=str(a[3]), Sharpe=m["Sharpe"], CAGR=m["CAGR"], MaxDD=m["MaxDD"], DD_tage=ms[:, 2].mean())
if __name__ == "__main__":
    with Pool(4) as p: out = p.map(job, list(itertools.product(S, L, R, G)), chunksize=1)
    pd.DataFrame(out).to_csv("mr_gate_ext.csv", index=False); print("fertig", len(out))
