import pickle, math, numpy as np, pandas as pd
Z = pickle.load(open("tips_zz.pkl", "rb")); R = pd.concat(Z, axis=1).dropna(); R.columns.names = ["spy", "tips", "cool"]
t1, t2 = R.index[len(R) // 3], R.index[2 * len(R) // 3]
P = [R[R.index < t1], R[(R.index >= t1) & (R.index < t2)], R[R.index >= t2]]
sh = lambda X: X.mean() / X.std() * math.sqrt(252)
def mdd(X): v = (1 + X).cumprod(); return (v / v.cummax() - 1).min()
keys = list(R.columns); S3 = [sh(p) for p in P]; DD = mdd(R)
def smooth(s, k, rs=20, rt=20, rc=5):
    return np.mean([s[c] for c in keys if abs(c[0] - k[0]) <= rs and abs(c[1] - k[1]) <= rt and abs(c[2] - k[2]) <= rc])
G = pd.DataFrame([{"spy": k[0], "tips": k[1], "cool": k[2], **{f"D{i+1}": smooth(S3[i], k) for i in range(3)},
                   "tailr": np.mean([DD[c] < -0.65 for c in keys if abs(c[0] - k[0]) <= 20 and abs(c[1] - k[1]) <= 20 and abs(c[2] - k[2]) <= 5]),
                   "DD": smooth(DD, k)} for k in keys])
for i in (1, 2, 3): G[f"r{i}"] = G[f"D{i}"].max() - G[f"D{i}"]
G["maxregret"] = G[["r1", "r2", "r3"]].max(axis=1)
G.to_csv("regret_tips.csv", index=False)
ok = G[G.tailr <= 0.2]
print("Minimax-Regret (Sharpe je Drittel geglaettet, Umgebung S&P/TIPS +-20, Cooldown +-5; Tail-Anteil MaxDD<-65 % <= 20 %):")
print(ok.sort_values("maxregret").head(15).round(3).to_string(index=False))
best = ok.maxregret.min(); reg = ok[ok.maxregret <= best + 0.01]
print(f"\nRobuster Bereich (max. Regret <= {best:.3f} + 0,01): {len(reg)} Varianten; S&P {sorted(reg.spy.unique())}, TIPS {sorted(reg.tips.unique())}, Cooldown {sorted(reg.cool.unique())}")
print(f"Mitte: S&P {reg.spy.mean():.0f}, TIPS {reg.tips.mean():.0f}, Cooldown {reg.cool.mean():.1f}")
for k in [(220, 190, 10), (220, 200, 10), (240, 200, 10), (280, 200, 10), (280, 220, 10), (280, 210, 10)]:
    r = G[(G.spy == k[0]) & (G.tips == k[1]) & (G.cool == k[2])].iloc[0]; print(f"  {k}: max. Regret {r.maxregret:.3f} (D1 {r.r1:.3f} D2 {r.r2:.3f} D3 {r.r3:.3f}) | Tail {r.tailr*100:.0f} % | Ø MaxDD {r.DD:.3f}")
