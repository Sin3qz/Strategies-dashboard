import numpy as np, engine as E
DAYS = list(range(0, 20)) + [-1]
def avg(**kw):
    ms = [E.metrics(E.run(day=d, **kw)[0]) for d in DAYS]
    f = lambda k: np.mean([m[k] for m in ms])
    return f("CAGR"), f("MaxDD"), min(m["MaxDD"] for m in ms), f("Sharpe"), f("Calmar"), f("MM5_CAGR") if "MM5_CAGR" in ms[0] else np.nan
print("Tilt (Platz 1 / Platz 2) — Mittel über 21 Entscheidungstage")
for t in (0.25, 0.30, 0.35, 0.40, 0.45, 0.50):
    c, dd, ddw, sh, ca, _ = avg(tilt=(t, 1 - t))
    print(f"  {t*100:.0f}/{(1-t)*100:.0f}  CAGR {c*100:5.1f} %  MaxDD Ø {dd*100:5.1f} % (schlechtester Tag {ddw*100:5.1f} %)  Sharpe {sh:.3f}  Calmar {ca:.3f}")
print("Vol-Target — Mittel über 21 Entscheidungstage")
for vt in (None, 0.45, 0.50, 0.55, 0.60, 0.65, 0.75):
    c, dd, ddw, sh, ca, _ = avg(vt=vt)
    print(f"  {('aus' if vt is None else f'{vt*100:.0f} %'):5s}  CAGR {c*100:5.1f} %  MaxDD Ø {dd*100:5.1f} % (schlechtester Tag {ddw*100:5.1f} %)  Sharpe {sh:.3f}  Calmar {ca:.3f}")
s, WF = E.run(); sc = WF.sum(axis=1)
print(f"Vol-Target greift (Faktor < 1) in {np.mean(sc.values < 0.999 * (WF.div(sc, axis=0).sum(axis=1).values)) * 100:.0f} % der Monate? (Näherung)")
