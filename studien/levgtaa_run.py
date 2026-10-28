import os, sys, time, pandas as pd, numpy as np, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from levgtaa_robust import *
rows = []
def ev(tag, **k):
    name = k.pop("name", None); m = run(**k); m["name"] = name; m.update({"tag": tag, **{a: (str(v) if not isinstance(v, (int, float)) else v) for a, v in k.items()}}); rows.append(m); return m
t = time.time(); ev("base"); print("Basis", {k: round(v, 3) for k, v in rows[-1].items() if isinstance(v, float)}, f"{time.time()-t:.1f}s")
for K in (10, 20, 30, 40, 50, 60): ev("K", K=K)
for lo, hi in ((100, 200), (125, 225), (150, 250), (175, 275), (100, 250), (150, 200)): ev("L", Ls=range(lo, hi + 1), K=30)
for nm, rk in (("1/3/6/9", {"a": (1, 3, 6, 9)}), ("3/6/12", {"b": (3, 6, 12)}), ("1/3/6/12", {"a": (1, 3, 6, 12)}),
               ("1/3/6/9+3/6/12", {"a": (1, 3, 6, 9), "b": (3, 6, 12)}), ("1/3/6/12+3/6/12", {"a": (1, 3, 6, 12), "b": (3, 6, 12)}),
               ("1/3/6+6/9/12", {"a": (1, 3, 6), "b": (6, 9, 12)})):
    ev("rank", rankings=rk, name=nm)
for tl in ((0.4, 0.6), (0.5, 0.5), (0.6, 0.4), (0.3, 0.7)): ev("tilt", tilt=tl)
for v in (None, 0.40, 0.50, 0.55, 0.60, 0.70, 0.85): ev("vt", vt=v)
for d in [-1] + list(range(0, 21)): ev("day", day=d)
pd.DataFrame(rows).to_csv(os.path.join(H, "levgtaa_results.csv"), index=False); print(len(rows), "Laeufe", f"{time.time()-t:.0f}s")
