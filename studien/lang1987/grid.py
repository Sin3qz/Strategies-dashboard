import itertools, pickle, time, numpy as np, pandas as pd, engine as E
RANK = {"1369+3612 (aktuell)": {"a": (1, 3, 6, 9), "b": (3, 6, 12)}, "1369": {"a": (1, 3, 6, 9)}, "3612": {"a": (3, 6, 12)},
        "13612": {"a": (1, 3, 6, 12)}, "36912": {"a": (3, 6, 9, 12)}, "13612+36912": {"a": (1, 3, 6, 12), "b": (3, 6, 9, 12)},
        "612": {"a": (6, 12)}, "136": {"a": (1, 3, 6)}, "1369+612": {"a": (1, 3, 6, 9), "b": (6, 12)}}
KS = [1, 10, 20, 30, 40, 50]
LB = {"100-150": range(100, 151), "100-200": range(100, 201), "125-225 (aktuell)": range(125, 226), "150-250": range(150, 251),
      "175-275": range(175, 276), "200-250": range(200, 251), "150": [150], "200": [200]}
if __name__ == "__main__":
    res, eqs = [], {}
    t = time.time()
    for (rn, rk), K, (ln, L) in itertools.product(RANK.items(), KS, LB.items()):
        s, _ = E.run(rankings=rk, K=K, Ls=L)
        m = E.metrics(s); res.append({"rank": rn, "K": K, "L": ln, **m}); eqs[(rn, K, ln)] = s
    df = pd.DataFrame(res); df.to_csv("grid_levgtaa.csv", index=False); pickle.dump(eqs, open("grid_eq.pkl", "wb"))
    print(f"{len(df)} Varianten in {time.time()-t:.0f}s")
