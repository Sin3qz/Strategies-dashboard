import itertools, sys, pandas as pd
from multiprocessing import Pool
import finecheck as F
WHICH = sys.argv[1]
JOBS = {"lev": [(F.lev, a) for a in itertools.product(range(25, 56, 5), (175, 188, 200, 212, 225))],
        "mr": [(F.mr, a) for a in itertools.product((-13, 0, 12), (-12, 0, 13))],
        "1x": [(F.one, a) for a in itertools.product(range(5, 26), range(150, 201, 5))]}
def call(j): return j[0](j[1])
if __name__ == "__main__":
    with Pool(4) as p: out = p.map(call, JOBS[WHICH], chunksize=2)
    pd.DataFrame(out, columns=["strat", "a", "b", "Sharpe", "CAGR", "MaxDD"]).to_csv(f"finecheck_{WHICH}.csv", index=False); print(WHICH, "fertig", len(out))
