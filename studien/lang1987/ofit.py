import itertools, math, pickle, numpy as np, pandas as pd
from statistics import NormalDist
ND = NormalDist()
df = pd.read_csv("grid_levgtaa.csv"); eqs = pickle.load(open("grid_eq.pkl", "rb"))
keys = [(r["rank"], int(r.K), r.L) for _, r in df.iterrows()]
M = pd.DataFrame({i: eqs[k].resample("ME").last().pct_change() for i, k in enumerate(keys)}).dropna()
CUR = keys.index(("1369+3612 (aktuell)", 30, "125-225 (aktuell)"))
C = {"aktuell": CUR, "C1 13612 K1 100-150": keys.index(("13612", 1, "100-150")), "C2 13612 K1 125-225": keys.index(("13612", 1, "125-225 (aktuell)")),
     "C3 13612 K30 125-225": keys.index(("13612", 30, "125-225 (aktuell)")), "C4 aktuelle Ranglisten K1": keys.index(("1369+3612 (aktuell)", 1, "125-225 (aktuell)"))}
pickle.dump((keys, C), open("cand.pkl", "wb"))

# 1) CSCV / PBO
S = 16; blocks = np.array_split(np.arange(len(M)), S); lam, deg = [], []
X = M.values
for comb in itertools.combinations(range(S), S // 2):
    m = np.zeros(len(M), bool); m[np.concatenate([blocks[i] for i in comb])] = True
    a, b = X[m], X[~m]
    s_is = a.mean(0) / a.std(0); s_oos = b.mean(0) / b.std(0)
    best = s_is.argmax(); rk = (s_oos < s_oos[best]).sum() + 1; w = rk / (len(s_oos) + 1)
    lam.append(math.log(w / (1 - w))); deg.append((s_oos[best] - np.median(s_oos)) * math.sqrt(12))
lam = np.array(lam)
print(f"1) PBO (CSCV, 16 Bloecke, {len(lam)} Aufteilungen): {np.mean(lam <= 0)*100:.1f} %  | Sharpe-Vorsprung der IS-besten Variante OOS ggü. Median: {np.mean(deg):+.3f}")

# 2) Deflated Sharpe Ratio (Monatsrenditen, N = 432 Versuche)
sr = (M.mean() / M.std()).values; N, T = len(sr), len(M); g = 0.5772156649
sr0 = math.sqrt(sr.var(ddof=1)) * ((1 - g) * ND.inv_cdf(1 - 1 / N) + g * ND.inv_cdf(1 - 1 / (N * math.e)))
def dsr(i, sr0):
    x = M.iloc[:, i]; s = x.mean() / x.std(); sk = ((x - x.mean()) ** 3).mean() / x.std() ** 3; ku = ((x - x.mean()) ** 4).mean() / x.std() ** 4
    return ND.cdf((s - sr0) * math.sqrt(T - 1) / math.sqrt(1 - sk * s + (ku - 1) / 4 * s * s)), s * math.sqrt(12)
print(f"2) Deflated Sharpe: erwartetes Maximum reiner Zufalls-Sharpe bei {N} Versuchen = {sr0*math.sqrt(12):.3f} (annualisiert)")
for n, i in C.items():
    p, s = dsr(i, sr0); p1, _ = dsr(i, 0.0)
    print(f"   {n:27s} Sharpe {s:.3f} | P(echt > 0) {p1*100:5.1f} % | DSR (gegen bestes Zufallsergebnis) {p*100:5.1f} %")

# 3) Walk-forward: alle 5 Jahre neu waehlen (Sharpe bzw. Gesamtkriterium auf allen Daten bis dahin), naechste 5 Jahre halten
def wf(score, start_years=range(1997, 2027, 5)):
    out = []
    for y0 in start_years:
        isd = M[M.index < f"{y0}-01-01"]; oos = M[(M.index >= f"{y0}-01-01") & (M.index < f"{y0+5}-01-01")]
        if len(oos) == 0: continue
        best = score(isd); out.append(oos.iloc[:, best]); print(f"     {y0}-{min(y0+4, 2026)}: gewählt {keys[best]}")
    return pd.concat(out)
def sc_sharpe(x): return int((x.mean() / x.std()).values.argmax())
def sc_mm(x):                       # robust: Mittel aus Sharpe-Rang und schlechtestem Drittel-Sharpe (Minimax3)
    th = np.array_split(np.arange(len(x)), 3); mm = np.min([x.iloc[t].mean().values / x.iloc[t].std().values for t in th], axis=0)
    r = pd.Series(x.mean().values / x.std().values).rank() + pd.Series(mm).rank(); return int(r.values.argmax())
for lbl, f in (("Sharpe", sc_sharpe), ("Sharpe+Minimax3", sc_mm)):
    print(f"3) Walk-forward (Auswahl nach {lbl}):")
    w = wf(f); c = M.iloc[:, CUR].reindex(w.index)
    cg = lambda r: (1 + r).prod() ** (12 / len(r)) - 1
    dd = lambda r: ((1 + r).cumprod() / (1 + r).cumprod().cummax() - 1).min()
    print(f"   OOS {w.index[0].date()}..{w.index[-1].date()}: Auswahl CAGR {cg(w)*100:.1f} % MaxDD {dd(w)*100:.1f} % Sharpe {w.mean()/w.std()*12**.5:.3f} | aktuell fest CAGR {cg(c)*100:.1f} % MaxDD {dd(c)*100:.1f} % Sharpe {c.mean()/c.std()*12**.5:.3f}")
