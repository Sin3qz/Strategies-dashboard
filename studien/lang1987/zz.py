import pickle, math, numpy as np, pandas as pd
Z = pickle.load(open("tips_zz.pkl", "rb")); R = pd.concat(Z, axis=1).dropna(); R.columns.names = ["spy", "tips", "cool"]
sh = lambda X: X.mean() / X.std() * math.sqrt(252)
mid = R.index[len(R) // 2]; t1, t2 = R.index[len(R) // 3], R.index[2 * len(R) // 3]
H = {"H1": R[R.index < mid], "H2": R[R.index >= mid], "D1": R[R.index < t1], "D2": R[(R.index >= t1) & (R.index < t2)], "D3": R[R.index >= t2],
     "ab2001": R[R.index >= "2001-06-01"], "gesamt": R}
S = {k: sh(v) for k, v in H.items()}
def comp(s):
    df = s.unstack("tips"); sm = df.T.rolling(5, center=True, min_periods=5).mean().T; return df, sm, df - sm
def corr(a, b):
    x, y = a.values.ravel(), b.values.ravel(); ok = ~np.isnan(x) & ~np.isnan(y); return np.corrcoef(x[ok], y[ok])[0, 1]
C = {k: comp(S[k]) for k in S}
print(f"Zickzack (Abweichung vom gleitenden 5er-Mittel ueber TIPS) – Korrelation zwischen unabhaengigen Zeitraeumen:")
print(f"  H1 vs H2 {corr(C['H1'][2], C['H2'][2]):+.2f} | D1 vs D2 {corr(C['D1'][2], C['D2'][2]):+.2f} | D1 vs D3 {corr(C['D1'][2], C['D3'][2]):+.2f} | D2 vs D3 {corr(C['D2'][2], C['D3'][2]):+.2f}")
cen = lambda df: (df.T - df.mean(axis=1)).T
print(f"Glatter Verlauf ueber TIPS (je Profil zentriert) – Korrelation:")
print(f"  H1 vs H2 {corr(cen(C['H1'][1]), cen(C['H2'][1])):+.2f} | D1 vs D2 {corr(cen(C['D1'][1]), cen(C['D2'][1])):+.2f} | D1 vs D3 {corr(cen(C['D1'][1]), cen(C['D3'][1])):+.2f} | D2 vs D3 {corr(cen(C['D2'][1]), cen(C['D3'][1])):+.2f}")
for k in ("H1", "H2"):
    z = C[k][2]; print(f"  Delle bei TIPS 200 (Abweichung vom glatten Verlauf, Mittel S&P 260-340, alle Cooldowns) {k}: {z.loc[z.index.get_level_values('spy') >= 260, 200].mean():+.3f}")
print("Glatter Verlauf (Mittel S&P 260-300, TIPS +-20, Cooldown 5/10/15):")
for k in ("gesamt", "ab2001", "D1", "D2", "D3"):
    s = S[k]; v = {t: np.mean([s[(sp, tt, co)] for sp in (260, 280, 300) for tt in range(t - 20, t + 21, 10) if 150 <= tt <= 250 for co in (5, 10, 15)]) for t in range(160, 241, 10)}
    print(f"  {k:7s} " + " ".join(f"{t}:{x:.3f}" for t, x in v.items()))
print("Glatter Verlauf ueber S&P (TIPS 170-230, Cooldown 5/10/15, S&P +-20):")
for k in ("gesamt", "ab2001", "D1", "D2", "D3"):
    s = S[k]; sp_all = sorted(set(R.columns.get_level_values("spy")))
    v = {p: np.mean([s[(q, tt, co)] for q in sp_all if abs(q - p) <= 20 for tt in range(170, 231, 10) for co in (5, 10, 15)]) for p in sp_all}
    print(f"  {k:7s} " + " ".join(f"{p}:{x:.3f}" for p, x in v.items()))
