import pickle, numpy as np, pandas as pd
R = pickle.load(open("raw.pkl", "rb"))
on = lambda s, i: s.reindex(s.index.union(i)).ffill().reindex(i)
def cagr(s): y = (s.index[-1]-s.index[0]).days/365.25; return (s.iloc[-1]/s.iloc[0])**(1/y)-1
def cmp(name, a, b, start=None):
    j = pd.concat([a, b], axis=1, keys=["proxy", "echt"]).dropna()
    if start: j = j[j.index >= start]
    w = j.resample("W-FRI").last().pct_change().dropna()
    beta = np.polyfit(w.proxy, w.echt, 1)[0]
    print(f"{name:34s} {j.index[0].date()}..{j.index[-1].date()} Wochen-Korr {w.corr().iloc[0,1]:.3f} Beta {beta:.2f} "
          f"Vola {w.proxy.std()*52**.5*100:4.1f}/{w.echt.std()*52**.5*100:4.1f} % CAGR {cagr(j.proxy)*100:5.2f}/{cagr(j.echt)*100:5.2f} %")
print("== Signale")
cmp("TLT-Signal: VUSTX vs TLT", R["VUSTX"], R["TLT"])
cmp("Gold-Signal: BoE vs GC=F", R["GOLD_BOE"], R["GC=F"])
print("== Investment-Basis")
cmp("Nasdaq: ^NDX (Preis) vs QQQ (TR)", R["^NDX"], R["QQQ"])
cmp("IEF: VFITX vs IEF", R["VFITX"], R["IEF"])
# synthetische 7-10J-Anleihe aus ^TNX: r = y/252 - D*dy + 0.5*C*dy^2
t = R["^TNX"]/100; dy = t.diff()
for D in (6.5, 7.0, 7.5, 8.0):
    syn = (1 + t.shift(1)/252 - D*dy + 0.5*D*D*dy**2).fillna(1).cumprod()
    cmp(f"IEF: ^TNX-Nachbau D={D}", syn, R["IEF"])
cmp("Gold: Kassapreis vs GLD", on(R["GOLD_BOE"].combine_first(R["GC=F"]), R["GLD"].index), R["GLD"])
print("== Kalibrierung Hebelprodukte (Kosten ueber Finanzierung, USD)")
gbp = R["GBPUSD=X"]
prod = {"QQQ3.L": (R["QQQ3.L"], "QQQ"), "3TYL.L": ((R["3TYL.L"]/100*on(gbp, R["3TYL.L"].index)).dropna(), "IEF"), "3GOL.L": (R["3GOL.L"], "GLD")}
rf = R["^IRX"]/100
for k, (p, b) in prod.items():
    r = p.pct_change(); p = p.iloc[0]*(1+r.mask(r.abs() > .6, 0).fillna(0)).cumprod()
    base = R[b][(R[b].index >= p.index[0]) & (R[b].index <= p.index[-1])]
    rb = base.pct_change().dropna(); f = on(rf, rb.index)/252
    yrs = (p.index[-1]-p.index[0]).days/365.25; cp = (p.iloc[-1]/p.iloc[0])**(1/yrs)-1
    lo, hi = -0.5, 0.8
    for _ in range(60):
        c = (lo+hi)/2; g = (1+3*rb-2*f-c/252).cumprod().iloc[-1]**(1/yrs)-1
        lo, hi = (c, hi) if g > cp else (lo, c)
    syn = (1+3*rb-2*f-c/252).cumprod()
    w = pd.concat([p, syn], axis=1).dropna().resample("W-FRI").last().pct_change().dropna()
    print(f"{k:7s} vs 3x {b}: {p.index[0].date()}..{p.index[-1].date()} Restkosten c = {c*100:.2f} % p.a. | Wochen-Korr {w.corr().iloc[0,1]:.3f}")
