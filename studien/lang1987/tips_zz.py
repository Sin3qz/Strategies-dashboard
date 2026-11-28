import itertools, pickle, pandas as pd, numpy as np
from multiprocessing import Pool
import tipsengine as TE
def job(a):
    s, _ = TE.run(a[0], a[1], 200, a[2]); return a, s.pct_change().astype("float32")
if __name__ == "__main__":
    jobs = list(itertools.product(list(range(160, 200, 10)) + list(range(200, 341, 20)), range(150, 251, 10), (5, 10, 15)))
    with Pool(2) as p: out = p.map(job, jobs, chunksize=4)
    pickle.dump(dict(out), open("tips_zz.pkl", "wb")); print("fertig", len(out))
