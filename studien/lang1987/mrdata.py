"""MR-Rebound ab 1995: Signale (^NDX, EM, ^BSESN, TLT) und Produktrenditen (USD, echte Produkte ab Start)."""
import pickle, numpy as np, pandas as pd, pandas_market_calendars as mcal, levdata as D
AL = ["NASDAQ100", "EM", "INDIA", "TLT_LONG"]
def build():
    R = pickle.load(open("raw.pkl", "rb"))
    sched = mcal.get_calendar("XNYS").schedule(start_date="1993-01-04", end_date=R["^NDX"].index[-1]); grid = pd.DatetimeIndex(pd.to_datetime(sched.index.date))
    on = lambda s: s.reindex(s.index.union(grid)).ffill().reindex(grid).where(grid >= s.dropna().index[0])
    em = D.chain(R["EEM"], R["VEIEX"])
    P = pd.DataFrame({"NASDAQ100": on(R["^NDX"]), "EM": on(em), "INDIA": on(R["^BSESN"]), "TLT_LONG": on(D.chain(R["TLT"], R["VUSTX"]))})
    rf = on(R["^IRX"]).ffill() / 100 / 252
    inr = R["INR=X"]; sx = R["^BSESN"]
    sx_usd = (sx / inr.reindex(sx.index, method="ffill")).dropna()
    pre = sx[sx.index < sx_usd.index[0]] * (1 - 0.036) ** ((sx_usd.index[0] - sx[sx.index < sx_usd.index[0]].index).days / 365.25)   # INR vor 12/2003: -3,6 % p. a.
    india = D.chain(R["INDA"], D.chain(sx_usd, pre))
    _, _, _, RPg, _ = D.build()
    def lev(base, c): r = on(base).pct_change(); return 3 * r - 2 * rf - c / 252
    RP = pd.DataFrame({"NASDAQ100": RPg["NASDAQ100"].reindex(grid), "EM": lev(em, 0.028), "INDIA": lev(india, 0.066), "TLT_LONG": RPg["UST_IEF"].reindex(grid)})
    for a, t in (("EM", "3EML.L"), ("INDIA", "IND3.L")):
        s = D.despike(R[t]); r = s.pct_change(); s = s.iloc[0] * (1 + r.mask(r.abs() > .6, 0).fillna(0)).cumprod()
        RP[a] = RP[a].where(grid <= s.index[0], on(s).pct_change())
    return grid, P, RP, rf
