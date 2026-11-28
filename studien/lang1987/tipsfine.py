import itertools, pickle, numpy as np, pandas as pd, tipsengine as TE, met
SP = range(200, 341, 10); TI = range(150, 251, 10); TL = (160, 200, 240); CO = (5, 10, 15)
rows, rets = [], {}
for sp, ti, tl, co in itertools.product(SP, TI, TL, CO):
    s, _ = TE.run(sp, ti, tl, co); m = met.metrics(s, TE.RF); s2 = s[s.index >= "2001-06-01"]; m2 = met.metrics(s2 / s2.iloc[0], TE.RF)
    rows.append(dict(spy=sp, tips=ti, tlt=tl, cool=co, Sharpe=m["Sharpe"], CAGR=m["CAGR"], MaxDD=m["MaxDD"], MM5=m["MM5_CAGR"], Sharpe_01=m2["Sharpe"], CAGR_01=m2["CAGR"], MaxDD_01=m2["MaxDD"]))
    rets[(sp, ti, tl, co)] = s.pct_change()
df = pd.DataFrame(rows); pickle.dump(rets, open("tipsfine_rets.pkl", "wb"))
import neutral as N
dims = ["spy", "tips", "tlt", "cool"]
df["glatt"] = N.smooth(df, dims, "Sharpe"); df["glatt_01"] = N.smooth(df, dims, "Sharpe_01")
df["glatt_DD"] = N.smooth(df, dims, "MaxDD"); df["score"] = df.glatt.rank(pct=True) + df.glatt_01.rank(pct=True)
df.to_csv("tipsfine.csv", index=False); print(len(df), "Varianten")
