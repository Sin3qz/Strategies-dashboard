"""Tagessignal und Entscheidungshistorie einer Strategie, gerechnet mit dem Code ihres Bot-Repos.

Aufruf: python3 daily_signals.py <repo-dir> <levgtaa|mrrebound|1xgtaa|levtips> <out.csv>
Schreibt
  <out.csv>            theoretische Position je US-Handelstag seit START (als ob an diesem Tag gehandelt wuerde):
                       levGTAA/MR-Rebound jeder Tag wie ein Monatsletzter, 1xGTAA/levTipsRegime ohne Cooldown;
  <out>_decisions.csv  was der Bot tatsaechlich entschieden hat (volle Historie, Signal auf dem Schlusskurs 'date',
                       Handel am naechsten Handelstag): monatlich je Monatsletztem bzw. taeglich mit Cooldown.
Die Kernfunktionen des Bot-Repos werden unveraendert benutzt."""
import sys, os
repo, mode, out = sys.argv[1], sys.argv[2], os.path.abspath(sys.argv[3])
dec_out = (out[:-4] if out.endswith(".csv") else out) + "_decisions.csv"
os.chdir(repo); sys.path.insert(0, repo)
import numpy as np, pandas as pd
START = "2025-01-02"
iso = lambda d: pd.Timestamp(d).date().isoformat()

if mode == "levgtaa":
    from strategies import runner as R, momentum_core as MC
    from strategies.constants import RANKINGS, SMA_LONG, SMA_SHORT, TILT, VT_TARGET, VT_WINDOWS
    grid, P, RET, stale, warns, fr = R.prepare(R.load_data())
    rows = np.where(P.index >= pd.Timestamp(START))[0]
    W, det = MC.decision_weights(P, rows, RANKINGS, SMA_LONG, SMA_SHORT, TILT)
    sc = MC.vt_scale(RET.values, rows, W, VT_TARGET, VT_WINDOWS)
    df = pd.DataFrame(W * sc[:, None], columns=R.AL).round(4)
    df.insert(0, "date", [iso(d) for d in P.index[rows]])
    df["cash"] = (1 - df[R.AL].sum(axis=1)).clip(lower=0).round(4)
    df["vt_factor"] = np.round(sc, 4)
    df["platz1"] = [R.AL[int(np.argmax(r))] if r.max() > 0 else "CASH" for r in det["P1"]]
    mrows, _, _, WF, _ = R.compute(P, RET)                                 # echte Monatsentscheidungen
    dec = pd.DataFrame(WF, columns=R.AL).round(4)
    dec.insert(0, "date", [iso(d) for d in P.index[mrows]])
    dec["rebalance"] = "monthly"

elif mode == "mrrebound":
    from strategies import runner as R, common as U
    from strategies.constants import HISTORY_START
    grid, P, stale, warns, fr = R.prepare(R.load_data())
    rows = np.where(P.index >= pd.Timestamp(START))[0]
    W, info = R.compute(P, rows)
    df = pd.DataFrame(np.asarray(W), columns=R.AL).round(4)
    df.insert(0, "date", [iso(d) for d in P.index[rows]])
    df["cash"] = (1 - df[R.AL].sum(axis=1)).clip(lower=0).round(4)
    mrows = np.where(U.month_end_flags(P.index) & (P.index >= pd.Timestamp(HISTORY_START)))[0]
    WM, _ = R.compute(P, mrows)
    dec = pd.DataFrame(np.asarray(WM), columns=R.AL).round(4)
    dec.insert(0, "date", [iso(d) for d in P.index[mrows]])
    dec["rebalance"] = "monthly"

elif mode == "1xgtaa":
    from strategies import runner as R, gtaa_botcore as G
    from strategies.constants import CFG
    closes, raw = R._load_closes()
    idx, allocs, cds, ind, _ = G.compute_series(closes, CFG, live=True)
    assets = list(closes.columns)
    recs = []
    for i, d in enumerate(idx):
        if d < pd.Timestamp(START):
            continue
        tgt = G.target_gtaa(assets, ind["trend"].iloc[i], ind["mom"].iloc[i], CFG["N"], CFG.get("weights"),
                            CFG.get("cash_fill", False), CFG.get("fallback", "concentrate"))
        r = {"date": iso(d)}
        r.update({a: round(tgt.get(a, 0.0), 4) for a in assets})
        r["cash"] = round(1 - sum(tgt.values()), 4)
        r["held"] = G.alloc_signature(allocs[i])
        r["cooldown"] = int(cds[i])
        recs.append(r)
    df = pd.DataFrame(recs)
    dec = pd.DataFrame([{a: round(al.get(a, 0.0), 4) for a in assets} for al in allocs])
    dec.insert(0, "date", [iso(d) for d in idx])
    dec["rebalance"] = "on_change"

else:  # levtips
    from strategies import levspybits as L, common as U
    from strategies import constants as C
    three = hasattr(C, "TLT_TICKER")                    # neue Regel mit 3x IEF (TIPS < SMA220, TLT > SMA200)
    tick = [C.SPY_TICKER, C.TIPS_TICKER] + ([C.TLT_TICKER] if three else [])
    raw = {t: U.fetch_close(t, C.TRY_COUNT) for t in tick}
    grid = U.build_grid(C.GRID_START, us_series=[raw[t] for t in tick])
    spy, tips = U.oncal(raw[C.SPY_TICKER], grid), U.oncal(raw[C.TIPS_TICKER], grid)
    if three:
        tlt = U.oncal(raw[C.TLT_TICKER], grid)
        tgt = L.target_series(spy, tips, tlt)
        names = L.STATE_NAMES
        tl = (tlt / tlt.rolling(C.TLT_SMA).mean() - 1).values
    else:
        tgt = L.target_series(spy, tips).astype(int)
        names = {0: "CASH", 1: "MARKET"}
        tl = np.full(len(grid), np.nan)
    alloc, rem = L.machine(tgt)
    sd = spy / spy.rolling(C.SPY_SMA).mean() - 1; td = tips / tips.rolling(C.TIPS_SMA).mean() - 1
    m = grid >= pd.Timestamp(START)
    st = np.array([names[int(x)] for x in tgt]); hd = np.array([names[int(x)] for x in alloc])
    df = pd.DataFrame({"date": [iso(d) for d in grid[m]], "state": st[m], "held_state": hd[m],
                       "market": (st[m] == "MARKET").astype(int), "held": (hd[m] == "MARKET").astype(int),
                       "ief": (st[m] == "IEF").astype(int), "cooldown": rem[m],
                       "spy_dist": sd.values[m].round(5), "tips_dist": td.values[m].round(5), "tlt_dist": np.round(tl[m], 5)})
    dec = pd.DataFrame({"date": [iso(d) for d in grid], "state": hd})
    # alte Regel (ohne IEF) zum Vergleich: gleiche Maschine, IEF-Tage als Cash
    if three:
        old, _ = L.machine(np.where(tgt == L.IEF, L.CASH, tgt))
        dec["state_old"] = [names[int(x)] for x in old]
    dec["rebalance"] = "on_change"

df.to_csv(out, index=False)
dec.to_csv(dec_out, index=False)
print(mode, len(df), "Tage;", len(dec), "Entscheidungen ->", os.path.basename(dec_out))
print(df.tail(2).to_string())
