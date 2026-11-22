"""levGTAA: alle 432 Varianten an allen 21 Entscheidungstagen. Je Variante: Kennzahlen je Tag und das
Tranchen-Portfolio (Mittel der 21 Tages-Varianten, taeglich gemittelte Renditen)."""
import itertools, pickle, numpy as np, pandas as pd
from multiprocessing import Pool
from grid import RANK, KS, LB
DAYS = list(range(0, 20)) + [-1]
def work(args):
    import engine as E
    rn, K, ln = args; rets, ms = [], []
    for d in DAYS:
        s, _ = E.run(rankings=RANK[rn], K=K, Ls=LB[ln], day=d)
        s = s[s.index >= "1987-09-01"]; rets.append(s.pct_change()); m = E.metrics(s); ms.append((m["CAGR"], m["Sharpe"], m["MaxDD"]))
    R = pd.concat(rets, axis=1).dropna().mean(axis=1).astype("float32")
    return args, R, np.array(ms)
if __name__ == "__main__":
    combos = list(itertools.product(RANK, KS, LB))
    with Pool(4) as p:
        out = p.map(work, combos, chunksize=4)
    pickle.dump({a: (r, m) for a, r, m in out}, open("daygrid.pkl", "wb")); print("fertig", len(out))
