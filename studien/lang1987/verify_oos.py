import pickle, sys, math, itertools, numpy as np, pandas as pd
def load(which):
    if which == "1x":
        X = pickle.load(open("joint_1x.pkl", "rb")); dims = [("S", 3), ("L", 2), ("cool", 1), ("lk", 0)]; old = (8, 150, 10, "1/3/6/12"); new = (19, 160, 10, "1/3/6/9")
    elif which == "lev":
        X = pickle.load(open("joint_lev.pkl", "rb")); dims = [("rank", 0), ("K", 1), ("Lmid", 1)]; old = ("1369+3612", 30, 175); new = ("13612+3612", 50, 200)
    elif which == "tips":
        X = pickle.load(open("tipsfine_rets.pkl", "rb")); dims = [("spy", 2), ("tips", 2), ("tlt", 1), ("cool", 1)]; old = (280, 220, 200, 10); new = (220, 190, 200, 10)
    else:
        M = pickle.load(open("mrgrid.pkl", "rb")); X = {k: v[0].astype(float) for k, v in M.items()}; dims = [("S", 1), ("L", 1), ("R", 1), ("G", 1)]
        old = ((75, 125), (175, 250), (42, 50, 56), (100, 200, 250)); new = ((75, 125), (175, 250), (42, 50, 56), (150, 200, 250))
    keys = list(X); R = pd.concat([X[k] for k in keys], axis=1).dropna(); R.columns = range(len(keys))
    return keys, R.astype("float32"), dims, old, new
def neigh(keys, dims):
    vals = [sorted(set(k[i] for k in keys), key=str if any(isinstance(k[i], str) for k in keys) else None) for i in range(len(dims))]
    pos = [{v: j for j, v in enumerate(vs)} for vs in vals]; idx = {k: n for n, k in enumerate(keys)}; NB = []
    for k in keys:
        rng = [[vals[i][j] for j in range(max(0, pos[i][k[i]] - r), min(len(vals[i]), pos[i][k[i]] + r + 1))] for i, (_, r) in enumerate(dims)]
        NB.append([idx[c] for c in itertools.product(*rng) if c in idx])
    return NB
which = sys.argv[1]; keys, R, dims, old, new = load(which); NB = neigh(keys, dims)
sh = lambda X: (X.mean() / X.std() * math.sqrt(252)).values
mid = R.index[len(R) // 2]; halves = [("1. Haelfte -> 2.", R[R.index < mid], R[R.index >= mid]), ("2. Haelfte -> 1.", R[R.index >= mid], R[R.index < mid])]
ko, kn = keys.index(old), keys.index(new); full = sh(R); fs = np.array([full[nb].mean() for nb in NB])
print(which, len(keys), "Varianten,", R.index[0].date(), "-", R.index[-1].date(), "| Gesamt: Plateau-Mitte", keys[int(fs.argmax())], "Gipfel", keys[int(full.argmax())])
for lab, A, B in halves:
    sa, sb = sh(A), sh(B); smo = np.array([sa[nb].mean() for nb in NB]); kp, kc = int(sa.argmax()), int(smo.argmax())
    pct = lambda j: round((sb < sb[j]).mean() * 100)
    print(f" {lab}: Wahl Plateau {keys[kc]} -> OOS Sharpe {sb[kc]:.3f} (Perzentil {pct(kc)}) | Gipfel {keys[kp]} -> {sb[kp]:.3f} ({pct(kp)}) | "
          f"alt {sb[ko]:.3f} ({pct(ko)}) | neu {sb[kn]:.3f} ({pct(kn)}) | Median {np.median(sb):.3f}")
