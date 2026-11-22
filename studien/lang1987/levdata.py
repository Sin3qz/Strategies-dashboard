"""Datenbasis levGTAA ab 1987: Signale (P), Vol-Target-Renditen wie im Bot (RVT = Hebel x Basisrendite) und realistische
Produktrenditen (RP: echte Hebelprodukte ab ihrem Start in USD, davor Hebel x Basis - (Hebel-1) x T-Bill - Restkosten,
kalibriert am echten Produkt). Cash verzinst mit T-Bill. Echte Reihen ab Verfuegbarkeit, Ersatz nur davor."""
import pickle, numpy as np, pandas as pd, pandas_market_calendars as mcal
AL = ["NASDAQ100", "BTC", "UST_IEF", "GOLD"]                       # Reihenfolge wie im Bot
LEV = np.array([3, 1, 3, 3.0])
COSTS = {"NASDAQ100": 0.0165, "UST_IEF": 0.0086, "GOLD": 0.0422}    # Restkosten ueber Finanzierung (am echten Produkt kalibriert; 3TYL nur ab 05/2018)
REAL_FROM = {"UST_IEF": "2018-05-01"}                                # 3TYL.L bei Yahoo vorher fehlerhaft (Einheitenwechsel 04/2017, eingefrorene Kurse, Sprung 04/2018)
BTC_FEE = 0.0025
NDX_DIV = 0.0056                                                     # ^NDX-Preisindex -> Gesamtrendite (QQQ 1999-2026)

def chain(real, proxy):
    """real ab seinem ersten Kurs, davor proxy (am ersten echten Tag angeschlossen)."""
    real = real.dropna(); p = proxy[proxy.index <= real.index[0]].dropna()
    pre = p[p.index < real.index[0]] / p.iloc[-1] * real.iloc[0]
    return pd.concat([pre, real]).sort_index()

def despike(s, jump=0.08, back=0.03):
    """Ein-Tages-Ausreisser (Kurs springt und am naechsten Tag zurueck, z. B. 3TYL.L 24.10.2025: 6025 -> 8020 -> 6000)
    durch den Vortageskurs ersetzen."""
    s = s.copy(); r = s.pct_change()
    for i in range(1, len(s) - 1):
        a, b = r.iloc[i], r.iloc[i + 1]
        if abs(a) > jump and abs(b) > jump and a * b < 0 and abs((1 + a) * (1 + b) - 1) < back:
            s.iloc[i] = s.iloc[i - 1]; r = s.pct_change()
    return s

def build(raw_file="raw.pkl"):
    R = pickle.load(open(raw_file, "rb"))
    sched = mcal.get_calendar("XNYS").schedule(start_date="1985-10-01", end_date=R["^NDX"].index[-1])
    grid = pd.DatetimeIndex(pd.to_datetime(sched.index.date))
    on = lambda s: s.reindex(s.index.union(grid)).ffill().reindex(grid).where(grid >= s.dropna().index[0])
    # --- Signale wie im Bot (^NDX, BTC-USD, TLT, GC=F) mit Ersatz davor
    P = pd.DataFrame({"NASDAQ100": on(R["^NDX"]), "BTC": on(R["BTC-USD"]),
                      "UST_IEF": on(chain(R["TLT"], R["VUSTX"])), "GOLD": on(chain(R["GC=F"], R["GOLD_BOE"]))})
    # --- Basisrenditen (ungehebelt, Gesamtrendite)
    ndx = R["^NDX"].pct_change() + NDX_DIV / 252
    qqq = chain(R["QQQ"], (1 + ndx.fillna(0)).cumprod())
    t = R["^TNX"] / 100; dy = t.diff()
    tnx = (1 + t.shift(1) / 252 + 0.004 / 252 - 7.5 * dy + 0.5 * 7.5 ** 2 * dy ** 2).fillna(1).cumprod()
    ief = chain(R["IEF"], tnx)
    gld = chain(R["GLD"], (1 + chain(R["GC=F"], R["GOLD_BOE"]).pct_change().fillna(0) - 0.004 / 252).cumprod())
    base = pd.DataFrame({"NASDAQ100": on(qqq), "BTC": on(R["BTC-USD"]), "UST_IEF": on(ief), "GOLD": on(gld)}).pct_change()
    rf = on(R["^IRX"]).ffill() / 100 / 252
    RVT = base * LEV                                                     # wie runner.prepare (Vol-Target)
    # --- realistische Produktrenditen
    RP = pd.DataFrame(index=grid)
    for k, a in enumerate(AL):
        L = LEV[k]
        RP[a] = L * base[a] - (L - 1) * rf - (COSTS.get(a, 0) if L > 1 else BTC_FEE) / 252
    gbp = R["GBPUSD=X"]
    real = {"NASDAQ100": R["QQQ3.L"], "UST_IEF": (R["3TYL.L"] / 100 * gbp.reindex(gbp.index.union(R["3TYL.L"].index)).ffill().reindex(R["3TYL.L"].index)).dropna(),
            "GOLD": R["3GOL.L"]}
    for a, s in real.items():
        s = despike(s[s.index >= REAL_FROM.get(a, "1900-01-01")])
        r = s.pct_change(); r = r.mask(r.abs() > 0.6, 0.0)
        s = s.iloc[0] * (1 + r.fillna(0)).cumprod()
        pr = on(s).pct_change()
        RP[a] = RP[a].where(grid <= s.index[0], pr)                     # ab dem 1. echten Kurs: echtes Produkt
    return grid, P, RVT, RP, rf
