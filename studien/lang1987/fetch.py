"""Rohdaten fuer die Langzeit-Backtests ab 1987 (Yahoo, USD, adjustierte Schlusskurse) -> raw.pkl"""
import pandas as pd, pickle, sys
from yahooquery import Ticker
T = ["^NDX", "QQQ", "BTC-USD", "TLT", "VUSTX", "IEF", "VFITX", "GC=F", "GLD", "^IRX", "^TNX", "^GSPC", "^SP500TR",
     "TIP", "VIPSX", "QQQ3.L", "3TYL.L", "3GOL.L", "3USL.L", "GBPUSD=X", "SPY"]
h = Ticker(T, asynchronous=True).history(period="max", interval="1d", adj_ohlc=True)
raw = {}
for t in T:
    s = h.loc[t]["close"]; s.index = pd.to_datetime([str(x)[:10] for x in s.index])
    s = pd.to_numeric(s, errors="coerce").dropna(); s = s[(s > 0) & ~s.index.duplicated(keep="last")].sort_index()
    raw[t] = s; print(f"{t:9s} {s.index[0].date()} .. {s.index[-1].date()} {len(s)}")
g = pd.read_csv("gold_daily_boe.csv", index_col=0, parse_dates=True)["usd"]; raw["GOLD_BOE"] = g
pickle.dump(raw, open("raw.pkl", "wb"))
