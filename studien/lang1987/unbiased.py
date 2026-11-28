"""Unvoreingenommene Auswahl: alle Varianten gleichberechtigt. Drittel des Zeitraums, geglaettete Sharpe je Drittel,
Regel A = gepoolt (Gesamtsharpe geglaettet), Regel B = Minimax (schlechtestes Drittel geglaettet). 3-fach-Gegenprobe."""
import sys, math, numpy as np, pandas as pd
from verify_oos import load, neigh
which = sys.argv[1]; keys, R, dims, old, new = load(which); NB = neigh(keys, dims)
sh = lambda X: (X.mean() / X.std() * math.sqrt(252)).values
def mdd(X): v = (1 + X).cumprod(); return (v / v.cummax() - 1).min().values
sm = lambda v: np.array([v[nb].mean() for nb in NB])
cut = [R.index[int(len(R) * q)] for q in (1 / 3, 2 / 3)]
P = [R[R.index < cut[0]], R[(R.index >= cut[0]) & (R.index < cut[1])], R[R.index >= cut[1]]]
S3 = [sh(p) for p in P]; G3 = [sm(s) for s in S3]
# Gegenprobe: je Drittel als Testzeitraum
res = {"A gepoolt": [], "B Minimax": [], "Gipfel": []}
for k in range(3):
    tr = [j for j in range(3) if j != k]; pooled = sm(sh(pd.concat([P[j] for j in tr])))
    mm = np.minimum(G3[tr[0]], G3[tr[1]]); raw = sh(pd.concat([P[j] for j in tr]))
    te = S3[k]; tes = G3[k]
    for lab, sc in (("A gepoolt", pooled), ("B Minimax", mm), ("Gipfel", raw)):
        j = int(sc.argmax()); res[lab].append(((te < te[j]).mean() * 100, (tes < tes[j]).mean() * 100))
print(which, len(keys), "Varianten; Drittel:", P[0].index[0].year, cut[0].year, cut[1].year, P[2].index[-1].year)
for lab, v in res.items():
    a = np.array(v); print(f"  Gegenprobe {lab:10s}: Testdrittel-Perzentil Punkt {np.round(a[:,0]).astype(int)} Ø {a[:,0].mean():.0f} | Umgebung {np.round(a[:,1]).astype(int)} Ø {a[:,1].mean():.0f}")
mmall = np.minimum.reduce(G3); full = sm(sh(R)); dd = sm(mdd(R)); dd3 = np.minimum.reduce([sm(mdd(p)) for p in P])
df = pd.DataFrame({"key": keys, "minimax": mmall, "gesamt": full, "MaxDD": dd, "MaxDD_schlechtestes_Drittel": dd3,
                   "D1": G3[0], "D2": G3[1], "D3": G3[2]})
df.to_pickle(f"unbiased_{which}.pkl")
print(df.sort_values("minimax", ascending=False).head(12).round(3).to_string(index=False))
for lab, k in (("alt", old), ("vorige Wahl", new)):
    r = df[df.key.apply(lambda x: x == k)]; print(" ", lab, r.round(3).to_string(index=False, header=False), "Rang", int((df.minimax > r.minimax.iloc[0]).sum()) + 1)
