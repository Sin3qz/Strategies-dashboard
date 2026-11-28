import pandas as pd, pickle
from yahooquery import Ticker
T = ["3GOL.L","3TYL.L","3USL.L","BIL","BTC-USD","DBC","EEM","EZU","GBPUSD=X","GC=F","GLD","IEF","INDA","INR=X","QQQ","QQQ3.L","SPY","TIP","TLT",
     "VEIEX","VEURX","VFITX","VIPSX","VUSTX","^BSESN","^GSPC","^IRX","^NDX","^SP500TR","^SPGSCI","^TNX","3EML.L","IND3.L"]
raw = {}
for i in range(0, len(T), 8):
    part = T[i:i + 8]; h = Ticker(part, asynchronous=True).history(period="max", interval="1d", adj_ohlc=True)
    for t in part:
        s = h.loc[t]["close"]; s.index = pd.to_datetime([str(x)[:10] for x in s.index])
        s = pd.to_numeric(s, errors="coerce").dropna(); s = s[(s > 0) & ~s.index.duplicated(keep="last")].sort_index()
        raw[t] = s; print(f"{t:9s} {s.index[0].date()} .. {s.index[-1].date()} {len(s)}")
raw["GOLD_BOE"] = pd.read_csv("gold_daily_boe.csv", index_col=0, parse_dates=True)["usd"]
pickle.dump(raw, open("raw.pkl", "wb"))
