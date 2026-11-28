import itertools, sys, pickle, time, pandas as pd
from multiprocessing import Pool
from joint import one
LKS = ("1/3/6/9", "1/3/6/12")
jobs = [a for a in itertools.product(range(3, 41), range(130, 261, 10), (8, 10, 12), LKS) if a[0] > 20 or a[1] > 220]
if __name__ == "__main__":
    if sys.argv[1:] == ["t"]:
        t = time.time(); print(one((25, 180, 10, "1/3/6/9"))[0], time.time() - t); sys.exit()
    with Pool(4) as p: out = p.map(one, jobs, chunksize=4)
    pd.DataFrame([o[0] for o in out]).to_csv("joint_1x_ext.csv", index=False)
    print("fertig", len(out))
