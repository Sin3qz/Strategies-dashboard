import math, numpy as np, pandas as pd
def metrics(s, rf=None):
    r = s.pct_change().dropna(); y = (s.index[-1] - s.index[0]).days / 365.25; dd = s / s.cummax() - 1
    ex = r - (rf.reindex(r.index).fillna(0) if rf is not None else 0); cagr = (s.iloc[-1] / s.iloc[0]) ** (1 / y) - 1
    mm = [((s.iloc[i].iloc[-1] / s.iloc[i].iloc[0]) ** (365.25 / (s.iloc[i].index[-1] - s.iloc[i].index[0]).days) - 1) for i in np.array_split(np.arange(len(s)), 5)]
    return {"CAGR": cagr, "MaxDD": dd.min(), "Sharpe": ex.mean() / r.std() * math.sqrt(252), "Calmar": cagr / -dd.min(), "MM5_CAGR": min(mm)}
