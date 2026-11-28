import itertools, sys, pandas as pd
from multiprocessing import Pool
from joint import lev
jobs = list(itertools.product(["13612+3612", "1369+3612"], range(85, 141, 5), (150, 175, 200, 225, 250)))
if __name__ == "__main__":
    with Pool(4) as p: out = p.map(lev, jobs, chunksize=2)
    pd.DataFrame([o[0] for o in out]).to_csv("joint_lev_ext.csv", index=False); print("fertig", len(out))
