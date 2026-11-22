import numpy as np, pandas as pd, engine as E
cand = {"aktuell": dict(), "C2 13612 K1": dict(rankings={"a": (1, 3, 6, 12)}, K=1), "C3 13612 K30": dict(rankings={"a": (1, 3, 6, 12)})}
print("A) Alle 21 Handelstage des Monats (Entscheidungstag 0 = 1. Handelstag ... -1 = Monatsletzter): CAGR / MaxDD")
for n, kw in cand.items():
    rs = [E.metrics(E.run(day=d, **kw)[0]) for d in list(range(0, 20)) + [-1]]
    c = np.array([r["CAGR"] for r in rs]); dd = np.array([r["MaxDD"] for r in rs]); sh = np.array([r["Sharpe"] for r in rs])
    print(f"   {n:14s} CAGR {c.min()*100:.1f}-{c.max()*100:.1f} % (Mittel {c.mean()*100:.1f}, Monatsletzter {c[-1]*100:.1f}) | MaxDD {dd.min()*100:.0f} bis {dd.max()*100:.0f} % | Sharpe Mittel {sh.mean():.3f}")
print("B) Kosten 0,2 % statt 0,1 % je umgeschichtetem Betrag:")
for n, kw in cand.items():
    m = E.metrics(E.run(cost=0.002, **kw)[0]); print(f"   {n:14s} CAGR {m['CAGR']*100:.1f} % MaxDD {m['MaxDD']*100:.1f} % Sharpe {m['Sharpe']:.3f}")
print("C) Bootstrap (Block 63 Tage, 2000 Pfade à 39 Jahre): Wahrscheinlichkeit MaxDD unter -50 % / -75 %, Median-CAGR")
rng = np.random.default_rng(1)
for n, kw in cand.items():
    r = np.log(E.run(**kw)[0]).diff().dropna().values; L = len(r); out = []
    for _ in range(2000):
        st = rng.integers(0, L - 63, L // 63 + 1); x = np.concatenate([r[s:s + 63] for s in st])[:L]
        eq = np.exp(np.cumsum(x)); out.append(((eq / np.maximum.accumulate(eq) - 1).min(), np.exp(x.sum() / (L / 252)) - 1))
    o = np.array(out); print(f"   {n:14s} P(DD<-50%) {np.mean(o[:,0] < -.5)*100:4.1f} % | P(DD<-75%) {np.mean(o[:,0] < -.75)*100:4.1f} % | Median-CAGR {np.median(o[:,1])*100:.1f} % | 5%-Quantil CAGR {np.percentile(o[:,1],5)*100:.1f} %")
print("D) Weitere Parameter (aktuelle Ranglisten/SMA): Vol-Target und Tilt")
for vt in (None, 0.40, 0.50, 0.55, 0.60, 0.70):
    m = E.metrics(E.run(vt=vt)[0]); print(f"   Vol-Target {('aus' if vt is None else f'{vt*100:.0f} %'):6s} CAGR {m['CAGR']*100:.1f} % MaxDD {m['MaxDD']*100:.1f} % Sharpe {m['Sharpe']:.3f} Calmar {m['Calmar']:.3f}")
for t in ((0.3, 0.7), (0.4, 0.6), (0.5, 0.5), (0.6, 0.4)):
    m = E.metrics(E.run(tilt=t)[0]); print(f"   Tilt {t[0]*100:.0f}/{t[1]*100:.0f}      CAGR {m['CAGR']*100:.1f} % MaxDD {m['MaxDD']*100:.1f} % Sharpe {m['Sharpe']:.3f} Calmar {m['Calmar']:.3f}")
