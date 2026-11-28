import pickle, math, numpy as np, pandas as pd
def boot(ra, rb, B=2000, block=63, seed=7):
    j = pd.concat([ra, rb], axis=1).dropna(); x0 = j.values; n = len(x0); rng = np.random.default_rng(seed); ds, dc, dd = [], [], []
    def mdd(x): v = np.cumprod(1 + x, 0); return (v / np.maximum.accumulate(v, 0) - 1).min(0)
    for _ in range(B):
        st = rng.integers(0, n - block, n // block + 1); x = np.concatenate([x0[s:s + block] for s in st])[:n]
        s = x.mean(0) / x.std(0) * math.sqrt(252); c = np.exp(np.log1p(x).sum(0) * 252 / n) - 1; m = mdd(x)
        ds.append(s[0] - s[1]); dc.append(c[0] - c[1]); dd.append(m[0] - m[1])
    ds, dc, dd = map(np.array, (ds, dc, dd)); s = x0.mean(0) / x0.std(0) * math.sqrt(252); m = mdd(x0)
    return dict(Sh_neu=round(s[0], 3), Sh_alt=round(s[1], 3), MaxDD_neu=round(m[0], 3), MaxDD_alt=round(m[1], 3),
                P_Sharpe=round((ds > 0).mean(), 2), KI90_Sharpe=(round(np.percentile(ds, 5), 3), round(np.percentile(ds, 95), 3)),
                P_CAGR=round((dc > 0).mean(), 2), P_MaxDD=round((dd > 0).mean(), 2), Jahre=round(n / 252, 1))
out = {}
L = pickle.load(open("joint_lev.pkl", "rb")); out["levGTAA"] = boot(L[("13612+3612", 50, 200)], L[("1369+3612", 30, 175)]); del L
X = pickle.load(open("joint_1x.pkl", "rb"))
out["1xGTAA (Cooldown 10)"] = boot(X[(19, 160, 10, "1/3/6/9")], X[(8, 150, 10, "1/3/6/12")])
ens = lambda S, L, lk: pd.concat([X[(S, L, c, lk)] for c in (8, 10, 12)], axis=1).mean(axis=1)
out["1xGTAA (Ø Cooldown 8/10/12)"] = boot(ens(19, 160, "1/3/6/9"), ens(8, 150, "1/3/6/12")); del X
M = pickle.load(open("mrgrid.pkl", "rb")); k = lambda g: ((75, 125), (175, 250), (42, 50, 56), g)
out["MR"] = boot(M[k((150, 200, 250))][0].astype(float), M[k((100, 200, 250))][0].astype(float)); del M
T = pickle.load(open("tipsfine_rets.pkl", "rb")); out["levTips"] = boot(T[(220, 190, 200, 10)], T[(280, 220, 200, 10)])
for a, b in out.items(): print(a, b)
