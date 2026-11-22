"""1xGTAA ab 1995 mit dem Original-Botkern (gtaa_botcore.compute_series). Indexnahe Ersatzreihen:
EMU Value -> MSCI EMU (EZU, davor Vanguard Europe VEURX); EM Small Caps -> EM (EEM, davor VEIEX);
Rohstoffe DBC -> davor S&P GSCI; Cash BIL -> davor T-Bill. Invest = dieselben 1x-Reihen (USD), Cash verzinst T-Bill."""
import sys, pickle, numpy as np, pandas as pd, pandas_market_calendars as mcal
sys.path.insert(0, "" + __import__("os").environ.get("BOT_REPO_DIR", "../../..") + "/1xgtaa-signalbot")
from strategies import gtaa_botcore as G
from strategies.constants import CFG
import levdata as D
R = pickle.load(open("raw.pkl", "rb"))
sched = mcal.get_calendar("XNYS").schedule(start_date="1993-01-04", end_date=R["QQQ"].index[-1]); GRID = pd.DatetimeIndex(pd.to_datetime(sched.index.date))
on = lambda s: s.reindex(s.index.union(GRID)).ffill().reindex(GRID).where(GRID >= s.dropna().index[0])
RF = on(R["^IRX"]).ffill() / 100 / 252
ndx = (1 + R["^NDX"].pct_change().fillna(0) + 0.0056 / 252).cumprod(); t = R["^TNX"] / 100; dy = t.diff()
ief = (1 + t.shift(1) / 252 + 0.004 / 252 - 7.5 * dy + 0.5 * 56.25 * dy ** 2).fillna(1).cumprod()
gold = (1 + D.chain(R["GC=F"], R["GOLD_BOE"]).pct_change().fillna(0) - 0.004 / 252).cumprod()
bil = (1 + RF.fillna(0)).cumprod()
CL = pd.DataFrame({"NASDAQ100": on(D.chain(R["QQQ"], ndx)), "EM_SMALLCAP": on(D.chain(R["EEM"], R["VEIEX"])), "EMU_VALUE": on(D.chain(R["EZU"], R["VEURX"])),
                   "BONDS_7_10": on(D.chain(R["IEF"], ief)), "GOLD": on(D.chain(R["GLD"], gold)), "COMMODITIES": on(D.chain(R["DBC"], R["^SPGSCI"])),
                   "CASH_USD": on(D.chain(R["BIL"], bil))}).dropna()
RET = CL.pct_change().fillna(0).values; RFV = RF.reindex(CL.index).fillna(0).values; COLS = list(CL.columns)
def run(S=8, L=150, lookbacks=(1, 3, 6, 12), cool=10, weights=(0.4, 0.6), cost=0.001, start="1995-07-01"):
    cfg = dict(CFG, S=S, L=L, lookbacks=tuple(lookbacks), cooldown_days=cool, weights=list(weights))
    idx, allocs, cds, ind, _ = G.compute_series(CL, cfg, live=False)
    W = np.array([[a.get(c, 0.0) for c in COLS] for a in allocs]); W = np.vstack([np.zeros(len(COLS)), W[:-1]])   # Handel am Folgetag
    first = idx.searchsorted(pd.Timestamp(start)); w = W[first].copy(); V = 1 - cost * w.sum(); eq = []
    for j in range(first, len(idx)):
        if j > first:
            g = 1 + RET[j] @ w + (1 - w.sum()) * RFV[j]; w = w * (1 + RET[j]) / g if g > 0 else w; V *= g
            if not np.allclose(W[j], W[j - 1]): V *= 1 - cost * np.abs(W[j] - w).sum(); w = W[j].copy()
        eq.append(V)
    return pd.Series(eq, index=idx[first:])
