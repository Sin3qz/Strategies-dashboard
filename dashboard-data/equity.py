"""Realitaetsnahe Equity-Kurven der Strategien mit den tatsaechlich gehandelten Produkten (EUR).

Ablauf je Strategie:
  - Entscheidungen aus dem Bot-Code (decisions_<mode>.csv, Signal auf dem Schlusskurs 'date').
  - Handel zum Schlusskurs des naechsten US-Handelstags; monatliche Strategien schichten an jedem Handelstag nach
    einem Monatssignal auf die Zielquoten um, taegliche nur, wenn sich die Allokation aendert.
  - Zwischen den Umschichtungen laufen die Gewichte mit den Kursen (buy & hold), Cash verzinst sich nicht.
  - Kosten: COST je umgeschichtetem Euro (Spread/Gebuehr, Annahme).
  - Kurse: Produktkurse von Yahoo (liquideste Notierung); USD- und Pence-Notierungen (London) mit EURUSD bzw. EURGBP
    in EUR umgerechnet. Bitcoin: BTC-EUR als
    Naeherung fuer ein 1x-Bitcoin-ETP (ohne dessen Gebuehr).
Mischungen: deine Aufteilungen, monatlich (1. Handelstag) auf die Zielanteile zurueckgesetzt.
"""
import json, math, os
import numpy as np, pandas as pd

COST = 0.001
PRODUCTS = {   # key: (Name, ISIN, Yahoo-Ticker, Waehrung)
    "NDX3": ("WisdomTree NASDAQ 100 3x Daily Leveraged", "IE00BLRPRL42", "QQQ3.L", "USD"),
    "SPX3": ("WisdomTree S&P 500 3x Daily Leveraged", "IE00B7Y34M31", "3USL.L", "USD"),
    "UST3": ("WisdomTree US Treasuries 10Y 3x Daily Leveraged", "IE00BKT09032", "3TYL.L", "GBp"),   # 3TYL.MI: zu viele Tage ohne Kurs
    "GOLD3": ("WisdomTree Gold 3x Daily Leveraged", "IE00B8HGT870", "3GOL.L", "USD"),
    "BTC1": ("Bitcoin (BTC-EUR, Näherung für ein 1x-Bitcoin-ETP)", "", "BTC-EUR", "EUR"),
    "EM3": ("WisdomTree Emerging Markets 3x Daily Leveraged", "IE00BYTYHN28", "3EML.L", "USD"),
    "IND3": ("Leverage Shares 3x Long India", "XS2595675302", "IND3.L", "USD"),
    "TLT5": ("Leverage Shares 5x Long 20+ Year Treasury Bond", "XS2595672036", "TLT5.L", "USD"),
    "NDX1": ("iShares Nasdaq 100 UCITS", "IE00B53SZB19", "SXRV.DE", "EUR"),
    "EMSC": ("SPDR MSCI EM Small Cap UCITS", "IE00B48X4842", "SPYX.DE", "EUR"),
    "EMUV": ("Amundi MSCI EMU Value UCITS", "LU1598690169", "AW1T.DE", "EUR"),
    "UST710": ("iShares $ Treasury 7-10y UCITS", "IE00B1FZS798", "IDTM.L", "USD"),
    "XGOLD": ("Xetra-Gold", "DE000A0S9GB0", "4GLD.DE", "EUR"),
    "CMDTY": ("WisdomTree Enhanced Commodity UCITS USD Acc", "IE00BYMLZY74", "WCOA.L", "USD"),
    "USDON": ("Xtrackers II USD Overnight Rate Swap 1C", "LU0321465469", "XFFE.DE", "EUR"),
}
MAP = {   # Strategie-Baustein -> Produkt
    "levgtaa": {"NASDAQ100": "NDX3", "BTC": "BTC1", "UST_IEF": "UST3", "GOLD": "GOLD3"},
    "mrrebound": {"NASDAQ100": "NDX3", "EM": "EM3", "INDIA": "IND3", "TLT_LONG": "TLT5"},
    "1xgtaa": {"NASDAQ100": "NDX1", "EM_SMALLCAP": "EMSC", "EMU_VALUE": "EMUV", "BONDS_7_10": "UST710", "GOLD": "XGOLD",
               "COMMODITIES": "CMDTY", "CASH_USD": "USDON"},
}
SPX_SHARE = 1.0     # levTipsRegime im Markt: 100 % 3x S&P 500 (seit 28.10.2026 ohne Bitcoin; Bot: SPX_WEIGHT)
STATE_W = {"MARKET": {"SPX3": SPX_SHARE, "BTC1": 1 - SPX_SHARE}, "IEF": {"UST3": 1.0}, "CASH": {}}
LABEL = {"levgtaa": "levGTAA", "levtips": "levTipsRegime", "levtips_old": "levTipsRegime (alte Regel ohne IEF)",
         "1xgtaa": "1xGTAA", "mrrebound": "MR-Rebound-GTAA",
         "mix_a": "Mix A: 1/3 levTipsRegime + 2/3 levGTAA", "mix_b": "Mix B: 1/3 levTipsRegime + 2/9 1xGTAA + 4/9 levGTAA"}
MIXES = {"mix_a": {"levtips": 1 / 3, "levgtaa": 2 / 3}, "mix_b": {"levtips": 1 / 3, "1xgtaa": 2 / 9, "levgtaa": 4 / 9}}
WF_START = "2026-10-01"   # Erstellung beider wikifolios (Index 100)


def load_prices(grid):
    from yahooquery import Ticker
    tick = sorted({p[2] for p in PRODUCTS.values()} | {"EURUSD=X", "EURGBP=X"})
    h = Ticker(tick, asynchronous=True).history(period="max", interval="1d", adj_ohlc=True)
    out, issues = {}, []
    for t in tick:
        try:
            s = h.loc[t]["close"]
        except KeyError:
            issues.append(f"{t}: keine Kurse"); continue
        s.index = pd.to_datetime([str(x)[:10] for x in s.index])
        s = pd.to_numeric(s, errors="coerce").dropna()
        s = s[(s > 0) & ~s.index.duplicated(keep="last")].sort_index()
        out[t] = s
    fx = {"USD": out["EURUSD=X"], "GBp": out["EURGBP=X"] * 100}    # Kurs in Fremdwaehrung je 1 EUR (Pence: x100)
    prices, last = {}, {}
    for k, (name, isin, t, ccy) in PRODUCTS.items():
        if t not in out:
            continue
        s = out[t]
        if ccy in fx:                                          # USD- bzw. Pence-Notierung -> EUR
            f = fx[ccy].reindex(s.index.union(fx[ccy].index)).ffill().reindex(s.index)
            s = (s / f).dropna()
        last[k] = (float(s.iloc[-1]), s.index[-1].date().isoformat())   # echter letzter Kurs in EUR (fuer den Rechner)
        r = s.pct_change()
        bad = r.abs() > 0.6                                    # Datenfehler (z. B. Pence/Dollar-Verwechslung)
        if bad.any():
            issues.append(f"{t}: {int(bad.sum())} unplausible Tagesbewegungen > 60 % ignoriert")
            r = r.mask(bad, 0.0)
            s = s.iloc[0] * (1 + r.fillna(0)).cumprod()
        on = s.reindex(s.index.union(grid)).ffill().reindex(grid)
        on[grid < s.index[0]] = np.nan
        prices[k] = on
    return prices, last, issues


def targets(mode, dec):
    """-> Liste (signal_date, {produkt: gewicht}, monatlich?)"""
    rows = []
    for _, r in dec.iterrows():
        if mode in ("levtips", "levtips_old"):
            w = dict(STATE_W[r["state" if mode == "levtips" else "state_old"]])
        else:
            w = {MAP[mode][a]: float(r[a]) for a in MAP[mode] if a in r and float(r[a]) > 1e-6}
        rows.append((pd.Timestamp(r["date"]), w, r["rebalance"] == "monthly"))
    return rows


def simulate(mode, dec, prices, grid):
    tg = targets(mode, dec)
    used = sorted({p for _, w, _ in tg for p in w} | ({"SPX3", "BTC1", "UST3"} if mode.startswith("levtips") else set()))
    first = max(prices[p].first_valid_index() for p in used)
    gi = {d: i for i, d in enumerate(grid)}
    execs = {}                                                 # Handelstag-Index -> Zielgewichte
    prev = None
    for d, w, monthly in tg:
        pos = grid.searchsorted(d, side="right")               # naechster Handelstag nach dem Signal
        if pos >= len(grid):
            continue
        sig = tuple(sorted((k, round(v, 4)) for k, v in w.items()))
        if monthly or sig != prev:
            execs[pos] = w
        prev = sig
    if not execs:
        raise RuntimeError(f"{mode}: keine Entscheidungen")
    start = max(grid.searchsorted(first), min(execs))         # erst, wenn alle Produkte Kurse haben und der Bot entschieden hat
    w0 = execs[max(p for p in execs if p <= start)]
    V, units, out = 100.0, {}, []
    for j in range(start, len(grid)):
        px = {p: prices[p].iloc[j] for p in used}
        if j > start:
            V = units.get("cash", 0.0) + sum(u * px[p] for p, u in units.items() if p != "cash")
        w = w0 if j == start else execs.get(j)
        if w is not None:
            cur = {p: (units.get(p, 0.0) * px[p]) for p in used}
            tgt = {p: V * w.get(p, 0.0) for p in used}
            turn = sum(abs(tgt[p] - cur[p]) for p in used) if j > start else V * sum(w.values())
            V -= COST * turn
            units = {p: V * w.get(p, 0.0) / px[p] for p in used if w.get(p, 0.0) > 0}
            units["cash"] = V * (1 - sum(w.values()))
            V = units["cash"] + sum(u * px[p] for p, u in units.items() if p != "cash")
        out.append(V)
    return pd.Series(out, index=grid[start:])


def mix(series, weights, grid):
    idx = grid[grid >= max(series[k].index[0] for k in weights)]
    eq = pd.DataFrame({k: series[k].reindex(idx) for k in weights}).ffill()
    V, units, out, month = 100.0, None, [], None
    for d, row in eq.iterrows():
        if units is not None:
            V = sum(units[k] * row[k] for k in weights)
        if units is None or d.month != month:                  # 1. Handelstag des Monats: auf Zielanteile
            units = {k: V * w / row[k] for k, w in weights.items()}
            month = d.month
        out.append(V)
    return pd.Series(out, index=idx)


def stats(s):
    r = s.pct_change().dropna()
    yrs = (s.index[-1] - s.index[0]).days / 365.25
    dd = s / s.cummax() - 1
    m = s.resample("ME").last()
    mr = m.pct_change().dropna()
    first_m = m.iloc[0] / s.iloc[0] - 1
    mr = pd.concat([pd.Series([first_m], index=[m.index[0]]), mr]) if len(m) else mr
    y0 = s[s.index < pd.Timestamp(f"{s.index[-1].year}-01-01")]
    a1 = s[s.index <= s.index[-1] - pd.Timedelta(days=365)]
    down = r[r < 0]
    return {
        "start": s.index[0].date().isoformat(), "end": s.index[-1].date().isoformat(), "years": round(yrs, 2),
        "total": s.iloc[-1] / s.iloc[0] - 1,
        "cagr": (s.iloc[-1] / s.iloc[0]) ** (1 / yrs) - 1 if yrs > 0.25 else None,
        "vol": r.std() * math.sqrt(252), "maxdd": dd.min(), "maxdd_date": dd.idxmin().date().isoformat(), "dd_now": dd.iloc[-1],
        "sharpe": (r.mean() / r.std() * math.sqrt(252)) if r.std() > 0 else None,
        "sortino": (r.mean() / down.std() * math.sqrt(252)) if len(down) > 1 and down.std() > 0 else None,
        "ytd": s.iloc[-1] / y0.iloc[-1] - 1 if len(y0) else None,
        "y1": s.iloc[-1] / a1.iloc[-1] - 1 if len(a1) else None,
        "best_month": mr.max(), "worst_month": mr.min(), "pos_months": float((mr > 0).mean()),
    }, mr


def run(work, out_dir, grid_start="2009-01-01"):
    import pandas_market_calendars as mcal
    end = pd.Timestamp.today().normalize()
    sched = mcal.get_calendar("XNYS").schedule(start_date=grid_start, end_date=end)
    grid = pd.DatetimeIndex(pd.to_datetime(sched.index.date))
    dec = {m: pd.read_csv(os.path.join(work, f"decisions_{m}.csv")) for m in ("levgtaa", "mrrebound", "1xgtaa", "levtips")}
    last_signal = max(pd.Timestamp(d["date"].iloc[-1]) for d in dec.values())
    grid = grid[grid <= grid[grid.searchsorted(last_signal, side="right")] if grid.searchsorted(last_signal, side="right") < len(grid) else grid[-1]]
    prices, last, issues = load_prices(grid)
    series = {}
    for m in ("levgtaa", "levtips", "1xgtaa", "mrrebound"):
        series[m] = simulate(m, dec[m], prices, grid)
    if "state_old" in dec["levtips"].columns:
        series["levtips_old"] = simulate("levtips_old", dec["levtips"], prices, grid)
    for k, w in MIXES.items():
        series[k] = mix(series, w, grid)

    # Kennzahlen, Monatsrenditen
    st, months = [], []
    for k, s in series.items():
        d, mr = stats(s)
        st.append({"key": k, "label": LABEL[k], **{a: (None if v is None or (isinstance(v, float) and not math.isfinite(v)) else
                                                       (round(v, 5) if isinstance(v, float) else v)) for a, v in d.items()}})
        months += [{"month": i.strftime("%Y-%m"), "key": k, "ret": round(float(v), 5)} for i, v in mr.items()]
    # Equity (Index 100 je Start), woechentlich ausgeduennt bis auf die letzten 400 Tage
    eq = pd.DataFrame(series)
    keep = (eq.index >= eq.index[-1] - pd.Timedelta(days=400)) | (eq.index.dayofweek == 4)
    eq = eq[keep].round(3)
    eq.index.name = "date"
    eq.reset_index().assign(date=lambda x: x["date"].dt.strftime("%Y-%m-%d")).to_csv(os.path.join(out_dir, "equity.csv"), index=False)
    # Korrelation der Tagesrenditen (gemeinsamer Zeitraum der vier Strategien)
    base = ["levgtaa", "levtips", "1xgtaa", "mrrebound"]
    R = pd.DataFrame({k: series[k] for k in base}).dropna().pct_change().dropna()
    corr = [{"a": a, "b": b, "corr": round(float(R[a].corr(R[b])), 3)} for a in base for b in base]
    # Bot-Soll ab Erstellung der wikifolios (Index 100 am Schluss des Erstellungstags)
    track = []
    for k, key in (("levgtaa", "levgtaa"), ("levtips", "levtipsregime")):
        s = series[k][series[k].index >= pd.Timestamp(WF_START)]
        if len(s):
            track += [{"date": d.date().isoformat(), "key": key, "bot": round(float(v / s.iloc[0] * 100), 3)} for d, v in s.items()]
    # aktuelle Produktkurse (Rechner)
    px = []
    for k, (name, isin, t, ccy) in PRODUCTS.items():
        if k in last:
            px.append({"key": k, "name": name, "isin": isin, "ticker": t, "quote": ccy, "price_eur": round(last[k][0], 4),
                       "date": last[k][1]})
    for name, obj in (("perf_stats.json", st), ("monthly_returns.json", months), ("correlation.json", corr),
                      ("tracking.json", track), ("prices.json", px)):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)
    return issues
