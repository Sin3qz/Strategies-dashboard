"""Datenbasis levTipsRegime ab 1987: S&P 500 TR, TIPS-Signal, TLT-Signal, Produktrenditen 3x S&P 500 und 3x IEF."""
import pickle, numpy as np, pandas as pd, pandas_market_calendars as mcal
import levdata as D

def cleveland():
    x = pd.ExcelFile("clev.xlsx")
    e = x.parse("Expected Inflation"); e.columns = [str(c).strip() for c in e.columns]
    e = e.set_index(pd.to_datetime(e["Model Output Date"]))
    return e["10 year Expected Inflation"].astype(float), e["1 year Expected Inflation"].astype(float)

def gsw():
    raw = open("feds200805.csv").read().splitlines(); k = next(i for i, l in enumerate(raw) if l.startswith("Date"))
    d = pd.read_csv("feds200805.csv", skiprows=k, index_col=0, parse_dates=True)
    return pd.to_numeric(d["TIPSY10"], errors="coerce").dropna()

def tips_index(ry, infl1, D_=7.5):
    """Kursindex einer TIPS-Anleihe (Laufzeit ~10 J) aus der Realrendite (%) + Inflationsanpassung (erwartete Inflation)."""
    ry = ry / 100; inf = infl1.reindex(ry.index, method="ffill") / 100
    r = -D_ * ry.diff() + (ry.shift(1) + inf.shift(1)) / 252
    return (1 + r.fillna(0)).cumprod()

def build(raw_file="raw.pkl"):
    R = pickle.load(open(raw_file, "rb"))
    sched = mcal.get_calendar("XNYS").schedule(start_date="1985-10-01", end_date=R["^SP500TR"].index[-1])
    grid = pd.DatetimeIndex(pd.to_datetime(sched.index.date))
    on = lambda s: s.reindex(s.index.union(grid)).ffill().reindex(grid).where(grid >= s.dropna().index[0])
    e10, e1 = cleveland()
    tnx = R["^TNX"]
    ry_clev = (tnx - e10.reindex(tnx.index, method="ffill")).dropna()          # Realrendite-Naeherung vor 1999
    clev_idx = tips_index(ry_clev, e1, 5)          # Duration 5: beste Uebereinstimmung mit echten TIPS (80 %)
    gsw_idx = tips_index(gsw(), e1, 5)
    tips = D.chain(R["TIP"], D.chain(R["VIPSX"], D.chain(gsw_idx, clev_idx)))
    gspc_tr = (1 + R["^GSPC"].pct_change().fillna(0) + 0.03 / 252).cumprod()    # Preisindex + ~3 % Dividende (1987)
    spx = D.chain(R["^SP500TR"], gspc_tr)
    tlt = D.chain(R["TLT"], R["VUSTX"])
    sig = pd.DataFrame({"SPX": on(spx), "TIPS": on(tips), "TLT": on(tlt)})
    # Produktrenditen (USD): 3x S&P 500 (3USL.L ab Start, davor 3x SPY/S&P TR), 3x IEF wie levGTAA
    spy_tr = D.chain(R["SPY"], spx)
    rf = on(R["^IRX"]).ffill() / 100 / 252
    base_spx = on(spy_tr).pct_change()
    _, _, _, RP, _ = D.build(raw_file)
    rp = pd.DataFrame({"SPX3": 3 * base_spx - 2 * rf - COST_SPX3 / 252, "UST3": RP["UST_IEF"].reindex(grid)}, index=grid)
    s = D.despike(R["3USL.L"]); r = s.pct_change(); r = r.mask(r.abs() > .6, 0.0); s = s.iloc[0] * (1 + r.fillna(0)).cumprod()
    rp["SPX3"] = rp["SPX3"].where(grid <= s.index[0], on(s).pct_change())
    return grid, sig, rp, rf, {"clev": on(clev_idx), "gsw": on(gsw_idx), "vipsx": on(R["VIPSX"]), "tip": on(R["TIP"])}

COST_SPX3 = 0.0307                     # 3USL.L vs 3x SPY, 12/2012-11/2026
