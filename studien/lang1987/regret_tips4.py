import pickle, math, numpy as np, pandas as pd
Z = pickle.load(open("tips_zz.pkl", "rb")); R = pd.concat(Z, axis=1).dropna(); R.columns.names = ["spy", "tips", "cool"]
cuts = [("1987", "2001"), ("2001", "2009"), ("2009", "2018"), ("2018", "2027")]
P = [R[(R.index >= a) & (R.index < b)] for a, b in cuts]
sh = lambda X: X.mean() / X.std() * math.sqrt(252)
def mdd(X): v = (1 + X).cumprod(); return (v / v.cummax() - 1).min()
keys = list(R.columns); S4 = [sh(p) for p in P]; DD = mdd(R); DDp = [mdd(p) for p in P]
nb = lambda k: [c for c in keys if abs(c[0] - k[0]) <= 20 and abs(c[1] - k[1]) <= 20 and abs(c[2] - k[2]) <= 5]
rows = []
for k in keys:
    n = nb(k); rows.append({"spy": k[0], "tips": k[1], "cool": k[2], **{f"P{i+1}": np.mean([S4[i][c] for c in n]) for i in range(4)},
                            "tailr": np.mean([DD[c] < -0.65 for c in n]), "DD": np.mean([DD[c] for c in n]), "DDmax_p": np.mean([min(DDp[i][c] for i in range(4)) for c in n]),
                            "Sh": np.mean([sh(R[c]) for c in n])})
G = pd.DataFrame(rows)
for i in range(1, 5): G[f"r{i}"] = G[f"P{i}"].max() - G[f"P{i}"]
G["maxregret"] = G[[f"r{i}" for i in range(1, 5)]].max(axis=1); G.to_csv("regret_tips4.csv", index=False)
ok = G[G.tailr <= 0.2]; print("Minimax-Regret ueber 4 Perioden 1987-2000 / 2001-08 / 2009-17 / 2018-26 (geglaettet S&P/TIPS +-20, Cooldown +-5):")
print(ok.sort_values("maxregret").head(12).round(3).to_string(index=False))
b = ok.maxregret.min(); r = ok[ok.maxregret <= b + 0.01]
print(f"Robuster Bereich (<= {b:.3f}+0,01): n={len(r)}; S&P {sorted(r.spy.unique())}, TIPS {sorted(r.tips.unique())}, Cooldown {sorted(r.cool.unique())} | Mitte S&P {r.spy.mean():.0f}, TIPS {r.tips.mean():.0f}, CD {r.cool.mean():.1f}")
print("Profil TIPS bei S&P 220, Cooldown 10:"); print(G[(G.spy == 220) & (G.cool == 10)][["tips", "P1", "P2", "P3", "P4", "maxregret", "Sh", "DD"]].round(3).to_string(index=False))
print("Profil S&P bei TIPS 180, Cooldown 10:"); print(G[(G.tips == 180) & (G.cool == 10)][["spy", "P1", "P2", "P3", "P4", "maxregret", "tailr", "Sh", "DD"]].round(3).to_string(index=False))
