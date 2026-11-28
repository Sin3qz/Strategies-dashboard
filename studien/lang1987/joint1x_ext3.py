import itertools, pandas as pd
from multiprocessing import Pool
from joint import one
jobs = list(itertools.product(range(10, 31, 2), range(90, 131, 10), (8, 10, 12), ("1/3/6/12", "1/3/6/9")))
if __name__ == "__main__":
    with Pool(2) as p: out = p.map(one, jobs, chunksize=4)
    pd.DataFrame([o[0] for o in out]).to_csv("joint_1x_ext3.csv", index=False); print("fertig", len(out))
