"""Theoretische Tagesposition je Handelstag (als ob an diesem Tag gehandelt wuerde).
Aufruf: python3 daily_signals.py <repo-dir> <levgtaa|mrrebound|1xgtaa|levtips> <out.csv>
Nutzt die Kernfunktionen des jeweiligen Bot-Repos unveraendert."""
import sys, os
repo, mode, out = sys.argv[1], sys.argv[2], os.path.abspath(sys.argv[3])
os.chdir(repo); sys.path.insert(0, repo)
import numpy as np, pandas as pd
START = "2025-01-02"

if mode == "levgtaa":
    from strategies import runner as R, momentum_core as MC
    from strategies.constants import RANKINGS, SMA_LONG, SMA_SHORT, TILT, VT_TARGET, VT_WINDOWS
    grid, P, RET, stale, warns, fr = R.prepare(R.load_data())
    rows = np.where(P.index >= pd.Timestamp(START))[0]
    W, det = MC.decision_weights(P, rows, RANKINGS, SMA_LONG, SMA_SHORT, TILT)
    sc = MC.vt_scale(RET.values, rows, W, VT_TARGET, VT_WINDOWS)
    WF = W * sc[:, None]
    df = pd.DataFrame(WF, columns=R.AL).round(4)
    df.insert(0, "date", [d.date().isoformat() for d in P.index[rows]])
    df["cash"] = (1 - df[R.AL].sum(axis=1)).clip(lower=0).round(4)
    df["vt_factor"] = np.round(sc, 4)
    p1 = det["P1"]
    df["platz1"] = [R.AL[int(np.argmax(r))] if r.max() > 0 else "CASH" for r in p1]

elif mode == "mrrebound":
    from strategies import runner as R
    grid, P, stale, warns, fr = R.prepare(R.load_data())
    rows = np.where(P.index >= pd.Timestamp(START))[0]
    W, info = R.compute(P, rows)
    df = pd.DataFrame(np.asarray(W), columns=R.AL).round(4)
    df.insert(0, "date", [d.date().isoformat() for d in P.index[rows]])
    df["cash"] = (1 - df[R.AL].sum(axis=1)).clip(lower=0).round(4)

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
        r = {"date": d.date().isoformat()}
        r.update({a: round(tgt.get(a, 0.0), 4) for a in assets})
        r["cash"] = round(1 - sum(tgt.values()), 4)
        r["held"] = G.alloc_signature(allocs[i])
        r["cooldown"] = int(cds[i])
        recs.append(r)
    df = pd.DataFrame(recs)

else:  # levtips
    from strategies import levspybits as L, common as U
    from strategies.constants import SPY_TICKER, TIPS_TICKER, TRY_COUNT, GRID_START, SPY_SMA, TIPS_SMA
    raw = {t: U.fetch_close(t, TRY_COUNT) for t in (SPY_TICKER, TIPS_TICKER)}
    grid = U.build_grid(GRID_START, us_series=[raw[SPY_TICKER], raw[TIPS_TICKER]])
    spy = U.oncal(raw[SPY_TICKER], grid); tips = U.oncal(raw[TIPS_TICKER], grid)
    tgt = L.target_series(spy, tips)
    alloc, rem = L.machine(tgt)
    sd = spy / spy.rolling(SPY_SMA).mean() - 1; td = tips / tips.rolling(TIPS_SMA).mean() - 1
    m = grid >= pd.Timestamp(START)
    df = pd.DataFrame({"date": [d.date().isoformat() for d in grid[m]],
                       "market": tgt[m].astype(int), "held": alloc[m].astype(int), "cooldown": rem[m],
                       "spy_dist": sd.values[m].round(5), "tips_dist": td.values[m].round(5)})

df.to_csv(out, index=False)
print(mode, len(df), df.tail(3).to_string())
