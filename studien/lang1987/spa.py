import pickle, math, numpy as np, pandas as pd
eqs = pickle.load(open("grid_eq.pkl", "rb")); keys, C = pickle.load(open("cand.pkl", "rb"))
R = pd.DataFrame({i: np.log(eqs[k]).diff() for i, k in enumerate(keys)}).dropna()
cur = C["aktuell"]; Dm = (R.values - R.values[:, [cur]]); Dm = np.delete(Dm, cur, axis=1)
n, K = Dm.shape; mu = Dm.mean(0); rng = np.random.default_rng(7)
def stat_boot(B=400, p=1/21):                       # stationaerer Bootstrap (Politis-Romano), mittlere Blocklaenge 21 Tage
    for _ in range(B):
        idx = np.empty(n, int); i = rng.integers(n)
        for t in range(n):
            idx[t] = i; i = rng.integers(n) if rng.random() < p else (i + 1) % n
        yield Dm[idx].mean(0)
om = np.sqrt(n) * Dm.std(0)
Tobs = max(0, (np.sqrt(n) * mu / om).max())
thr = -np.sqrt(2 * np.log(np.log(n))) * om / np.sqrt(n)      # Hansen SPA_c: nur "nicht klar schlechtere" Varianten zentrieren
mu_c = np.where(mu >= thr, mu, 0.0)
rc, spa = [], []
for mb in stat_boot():
    rc.append(max(0, (np.sqrt(n) * (mb - mu) / om).max())); spa.append(max(0, (np.sqrt(n) * (mb - mu_c) / om).max()))
print(f"White Reality Check / Hansen SPA (431 Alternativen gegen aktuell, Tagesrenditen, 400 Bootstraps):")
print(f"  bester Vorsprung: {mu.max()*252*100:+.2f} %-Punkte p.a. (log) | p-Wert RC {np.mean(np.array(rc) >= Tobs):.2f} | p-Wert SPA {np.mean(np.array(spa) >= Tobs):.2f}")
for nme, i in C.items():
    if i == cur: continue
    j = i if i < cur else i - 1; d = Dm[:, j]
    bm = np.array([m[j] for m in stat_boot(300)])
    print(f"  {nme:27s} Vorsprung {d.mean()*252*100:+.2f} %-Pkt p.a. | 90%-Intervall [{np.percentile(bm,5)*252*100:+.2f}, {np.percentile(bm,95)*252*100:+.2f}] | p(<=0) {np.mean(bm - d.mean() >= d.mean()):.2f}")
