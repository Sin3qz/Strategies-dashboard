"""levTipsRegime mit den Original-Funktionen des Bots (target_series, machine). Signal Schluss Tag d, Handel Tag d+1."""
import sys, numpy as np, pandas as pd
class L:                     # woertliche Kopie aus levtipsregime-signalbot/strategies/levspybits.py (Identitaet geprueft)
    CASH, MARKET, IEF = 0, 1, 2
    @staticmethod
    def target_series(spy, tips, tlt, spy_sma, tips_sma, tlt_sma):
        ds = (spy / spy.rolling(spy_sma).mean() - 1).values
        dt = (tips / tips.rolling(tips_sma).mean() - 1).values
        dl = (tlt / tlt.rolling(tlt_sma).mean() - 1).values
        market = (np.nan_to_num(ds, nan=-1) > 0) & (np.nan_to_num(dt, nan=-1) > 0)
        ief = (np.nan_to_num(dt, nan=1) < 0) & (np.nan_to_num(dl, nan=-1) > 0) & ~market
        return np.where(market, 1, np.where(ief, 2, 0)).astype(int)
    @staticmethod
    def machine(target, cooldown):
        cur, frozen = 0, -1
        alloc = np.zeros(len(target), int); rem = np.zeros(len(target), int)
        for i, t in enumerate(target):
            t = int(t)
            if t != cur and i > frozen:
                cur = t; frozen = i + cooldown
            alloc[i] = cur; rem[i] = max(0, frozen - i)
        return alloc, rem
import tipsdata as T
GRID, SIG, RP, RF, _X = T.build()
RS, RI, RFV = np.nan_to_num(RP["SPX3"].values), np.nan_to_num(RP["UST3"].values), RF.values
def run(spy_sma=280, tips_sma=220, tlt_sma=200, cool=10, cost=0.001, start="1987-08-01", sig=SIG):
    tgt = L.target_series(sig["SPX"], sig["TIPS"], sig["TLT"], spy_sma, tips_sma, tlt_sma)
    alloc, _ = L.machine(tgt, cool)
    pos = np.roll(alloc, 1); pos[0] = L.CASH                        # Handel am Folgetag
    r = np.where(pos == L.MARKET, RS, np.where(pos == L.IEF, RI, RFV))
    sw = np.r_[0, (pos[1:] != pos[:-1]).astype(float)]
    turn = np.where(sw > 0, np.where((np.roll(pos, 1) == L.CASH) | (pos == L.CASH), 1.0, 2.0), 0.0)
    eq = pd.Series(np.cumprod((1 + r) * (1 - cost * turn)), index=GRID)
    eq = eq[eq.index >= start]
    return eq / eq.iloc[0], pd.Series(pos, index=GRID)
