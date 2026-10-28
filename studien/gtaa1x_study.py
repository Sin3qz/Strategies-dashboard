"""1xGTAA-Studie: Handelsrhythmus (taeglich+Cooldown vs. monatlich) und Parameter.

Signale und Renditen auf 1x-USD-Kursen der Bot-Bausteine (QQQ, EEMS, EMU Value, IEF, GLD, DBC, BIL).
EMU Value: AW1T.DE x EURUSD ab 08/2022, davor EZU (MSCI EMU) als Naeherung (Renditen verkettet).
Kern unveraendert aus gtaa_botcore (per_asset_indicators / target_gtaa); Ensemble wie levGTAA (momentum_core).
Handel: Signal Schluss d -> Handel Schluss d+1; Kosten 0,1 % je umgeschichtetem Euro.
"""
import os as _os
import os
BOTS = _os.environ.get("BOT_REPO_DIR", _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..")))
import sys, itertools, json, math, pickle, os
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(BOTS, "1xgtaa-signalbot"))
from strategies import gtaa_botcore as G, common as U

HERE = os.path.dirname(os.path.abspath(__file__))
COST = 0.001
ASSETS = ["NASDAQ100", "EM_SMALLCAP", "EMU_VALUE", "BONDS_7_10", "GOLD", "COMMODITIES", "CASH_USD"]
TICK = {"NASDAQ100": "QQQ", "EM_SMALLCAP": "EEMS", "BONDS_7_10": "IEF", "GOLD": "GLD", "COMMODITIES": "DBC", "CASH_USD": "BIL"}


def load():
    f = os.path.join(HERE, "closes.pkl")
    if os.path.exists(f):
        return pickle.load(open(f, "rb"))
    raw = {a: U.fetch_close(t, 3) for a, t in TICK.items()}
    aw, fx, ezu = U.fetch_close("AW1T.DE", 3), U.fetch_close("EURUSD=X", 3), U.fetch_close("EZU", 3)
    awu = (aw * fx.reindex(aw.index).ffill()).dropna()
    grid = U.build_grid("2011-08-18", us_series=[raw[a] for a in TICK])
    P = pd.DataFrame({a: U.oncal(raw[a], grid) for a in TICK})
    ez, au = U.oncal(ezu, grid), U.oncal(awu, grid)
    r = ez.pct_change()
    ra = au.pct_change()
    r[au.notna() & au.shift(1).notna()] = ra[au.notna() & au.shift(1).notna()]       # ab AW1T-Start echte Reihe
    P["EMU_VALUE"] = 100 * (1 + r.fillna(0)).cumprod()
    P = P[ASSETS].dropna()
    pickle.dump(P, open(f, "wb"))
    return P


def bot_targets(P, S=8, L=150, lookbacks=(1, 3, 6, 9), trend_mode="smax", weights=(0.4, 0.6), fallback="slotgate"):
    """Taegliche Zielallokation (ohne Rebalancing-Regel) mit dem Bot-Kern."""
    ind = G.per_asset_indicators(P, S, L, lookbacks, trend_mode)
    need = max(L, max(G.MONTH_DAYS[m] for m in lookbacks))
    W = np.zeros((len(P), len(ASSETS)))
    for i in range(need, len(P)):
        t = G.target_gtaa(ASSETS, ind["trend"].iloc[i], ind["mom"].iloc[i], 2, list(weights), False, fallback)
        for a, w in t.items():
            W[i, ASSETS.index(a)] = w
    return W, need


def ensemble_targets(P, rankings, Ls, K, tilt=(0.4, 0.6)):
    """levGTAA-Ensemble: Mittel ueber Ranglisten und Lang-SMA-Laengen (Slotfloor 50 %)."""
    import importlib.util                                      # levGTAA-Kern direkt laden (Paketname kollidiert)
    spec = importlib.util.spec_from_file_location("lev_mc", os.path.join(BOTS, "levgtaa-signalbot", "strategies/momentum_core.py"))
    MC = importlib.util.module_from_spec(spec); spec.loader.exec_module(MC)
    need = max(max(Ls), 21 * max(max(r) for r in rankings.values()))
    rows = np.arange(need, len(P))
    W, _ = MC.decision_weights(P, rows, rankings, Ls, K, tilt)
    out = np.zeros((len(P), len(ASSETS))); out[rows] = W
    return out, need


def held(W, mode, cooldown=10, day=None, idx=None):
    """Aus taeglichen Zielen die tatsaechlich gehaltenen Entscheidungen (Signal am Schluss i)."""
    H = np.zeros_like(W); cur = np.zeros(W.shape[1]); frozen = -1
    T = np.zeros(len(W), bool)                                  # an diesem Signaltag wird umgeschichtet
    if mode == "daily":
        for i in range(len(W)):
            if i > frozen and (np.round(W[i], 4) != np.round(cur, 4)).any():
                cur = W[i].copy(); frozen = i + cooldown; T[i] = True
            H[i] = cur
    else:                                                       # monatlich: Entscheidung am Tag 'day' des Monats (-1 = letzter)
        per = pd.DatetimeIndex(idx).to_period("M")
        flags = np.zeros(len(W), bool)
        for _, g in pd.Series(np.arange(len(W)), index=per).groupby(level=0):
            k = len(g) - 1 if day == -1 else min(day, len(g) - 1)
            flags[g.iloc[k]] = True
        for i in range(len(W)):
            if flags[i]:
                cur = W[i].copy(); T[i] = True                  # monatlich immer auf Zielquoten zuruecksetzen
            H[i] = cur
    return H, T


def backtest(P, HT, start):
    H, T = HT
    R = P.pct_change().fillna(0).values
    eq, V, w = [], 1.0, np.zeros(H.shape[1])
    trades = 0
    for i in range(start, len(P)):
        if i > start:
            g = 1 + R[i] @ w                                   # Cash-Rest 0 % (Geldmarkt ist eigener Baustein BIL)
            w = w * (1 + R[i]) / g if g > 0 else w
            V *= g
        if i == start or T[i - 1]:                             # Signal Schluss i-1 -> Handel Schluss i
            tgt = H[i - 1]
            turn = np.abs(tgt - w).sum()
            if turn > 1e-6:
                V *= (1 - COST * turn); w = tgt.copy(); trades += 1
        eq.append(V)
    return pd.Series(eq, index=P.index[start:]), trades


def metrics(s, trades=None):
    r = s.pct_change().dropna(); yrs = (s.index[-1] - s.index[0]).days / 365.25
    dd = (s / s.cummax() - 1).min()
    cagr = (s.iloc[-1] / s.iloc[0]) ** (1 / yrs) - 1
    down = r[r < 0].std() * math.sqrt(252)
    out = {"cagr": cagr, "maxdd": dd, "vol": r.std() * math.sqrt(252), "sharpe": r.mean() / r.std() * math.sqrt(252),
           "sortino": (r.mean() * 252) / down if down > 0 else np.nan, "calmar": cagr / -dd if dd < 0 else np.nan}
    if trades is not None:
        out["trades_pa"] = trades / yrs
    return out


def periods(s):
    out = {}
    for a, b in (("2012-06-01", "2016-12-31"), ("2017-01-01", "2021-12-31"), ("2022-01-01", "2026-12-31")):
        x = s[(s.index >= a) & (s.index <= b)]
        if len(x) > 100:
            out[a[:4] + "-" + b[2:4]] = metrics(x / x.iloc[0])["cagr"]
    return out


def fast_targets(P, S=8, L=150, lookbacks=(1, 3, 6, 9), weights=(0.4, 0.6), fallback="slotgate", mom_mode="sum"):
    """Gleiche Regel wie gtaa_botcore.target_gtaa (slotgate / slotgate_floor), vektorisiert."""
    X = P.values
    smaL = P.rolling(L).mean().values
    smaS = X if S <= 1 else P.rolling(S).mean().values
    trend = smaS > smaL
    mom = sum(X / P.shift(G.MONTH_DAYS[m]).values - 1 for m in lookbacks)
    if mom_mode == "mean":
        mom = mom / len(lookbacks)
    need = max(L, max(G.MONTH_DAYS[m] for m in lookbacks))
    W = np.zeros_like(X)
    key = np.where(np.isnan(mom), -np.inf, mom)
    order = np.argsort(-key, axis=1, kind="stable")[:, :2]
    for i in range(need, len(X)):
        surv = [(k, j) for k, j in enumerate(order[i]) if np.isfinite(key[i, j]) and trend[i, j] and mom[i, j] > 0]
        if fallback == "slotgate_floor" and len(surv) == 1:
            k, j = surv[0]; W[i, j] = max(weights[k], 0.5)
        else:
            for k, j in surv:
                W[i, j] = weights[k]
    return W, need
