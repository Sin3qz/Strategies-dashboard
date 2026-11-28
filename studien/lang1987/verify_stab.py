import pickle, math, sys, numpy as np, pandas as pd
sh = lambda x: x.mean() / x.std() * math.sqrt(252)
def mdd(x): v = (1 + x).cumprod(); return (v / v.cummax() - 1).min()
def comp(X, pairs, lab, start=None):
    R = pd.concat({k: X[k] for p in pairs for k in p}, axis=1).dropna()
    if start: R = R[R.index >= start]
    mid = R.index[len(R) // 2]; out = []
    for nm, Y in [("H1", R[R.index < mid]), ("H2", R[R.index >= mid]), ("gesamt", R)]:
        w = [sh(Y[a]) > sh(Y[b]) for a, b in pairs]; d = [sh(Y[a]) - sh(Y[b]) for a, b in pairs]; dd = [mdd(Y[a]) > mdd(Y[b]) for a, b in pairs]
        out.append(f"{nm} {Y.index[0].year}-{Y.index[-1].year}: besser in {np.mean(w)*100:.0f} % (ØΔSharpe {np.mean(d):+.3f}, MaxDD besser {np.mean(dd)*100:.0f} %)")
    print(lab, f"({len(pairs)} Paare) |", " | ".join(out))
w = sys.argv[1] if __name__ == "__main__" else None
if w is None: pass
elif w == "lev":
    L = pickle.load(open("joint_lev.pkl", "rb")); Ks = range(20, 81, 5); Ls = (150, 175, 200, 225, 250)
    comp(L, [(("13612+3612", K, c), ("1369+3612", K, c)) for K in Ks for c in Ls], "levGTAA 1/3/6/12+3/6/12 vs 1/3/6/9+3/6/12")
    comp(L, [((r, 50, c), (r, 30, c)) for r in ("13612+3612", "1369+3612") for c in Ls], "levGTAA SMA50 vs SMA30 (je Band/Rangliste)")
    comp(L, [((r, K, 200), (r, K, 175)) for r in ("13612+3612", "1369+3612") for K in range(30, 71, 5)], "levGTAA Band 150-250 vs 125-225")
    comp(L, [(("13612+3612", 50, 200), ("1369+3612", 30, 175))], "levGTAA neu vs alt")
elif w == "1x":
    X = pickle.load(open("joint_1x.pkl", "rb"))
    comp(X, [((S, L, c, "1/3/6/9"), (S, L, c, "1/3/6/12")) for S in range(3, 21) for L in range(130, 221, 10) for c in (8, 10, 12)], "1xGTAA 1/3/6/9 vs 1/3/6/12")
    comp(X, [((19, 160, c, lk), (8, 150, c, lk)) for c in (5, 8, 10, 12, 15) for lk in ("1/3/6/9", "1/3/6/12", "3/6/12", "3/6/9/12")], "1xGTAA 19/160 vs 8/150")
    comp(X, [((S, L, c, lk), (S2, L2, c, lk)) for c in (8, 10, 12) for lk in ("1/3/6/9", "1/3/6/12") for (S, L) in [(17, 160), (19, 160), (20, 170)] for (S2, L2) in [(7, 150), (8, 150), (9, 140)]], "1xGTAA Umgebung 19/160 vs 8/150")
elif w == "mr":
    M = pickle.load(open("mrgrid.pkl", "rb")); X = {k: v[0].astype(float) for k, v in M.items()}
    SB = [(50, 100), (75, 125), (100, 150)]; LB = [(150, 225), (175, 250), (200, 275)]; RB = [(35, 42, 50), (42, 50, 56), (56, 63, 75)]
    comp(X, [((s, l, r, (150, 200, 250)), (s, l, r, (100, 200, 250))) for s in SB for l in LB for r in RB], "MR Gate 150/200/250 vs 100/200/250")
else:
    T = pickle.load(open("tipsfine_rets.pkl", "rb"))
    comp(T, [((s, 190, t, c), (s, 220, t, c)) for s in range(200, 341, 10) for t in (160, 200, 240) for c in (5, 10, 15)], "levTips TIPS 190 vs 220")
    comp(T, [((s, t, 200, c), (s + 60, t, 200, c)) for s in (210, 220, 230) for t in range(160, 221, 10) for c in (5, 10, 15)], "levTips S&P 210-230 vs 270-290")
    comp(T, [((280, 190, 200, 10), (280, 220, 200, 10))], "levTips 280/190 vs 280/220", )
    comp(T, [((280, 190, 200, 10), (280, 220, 200, 10))], "  dto. ab 2001 (echte TIPS)", "2001-06-01")
    comp(T, [((220, 190, 200, 10), (280, 190, 200, 10))], "levTips 220/190 vs 280/190")
