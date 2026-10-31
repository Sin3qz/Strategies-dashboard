"""Tagessignal und Entscheidungshistorie einer Strategie, gerechnet mit dem Code ihres Bot-Repos.

Aufruf: python3 daily_signals.py <repo-dir> <levgtaa|mrrebound|1xgtaa|levtips> <out.csv>
Schreibt
  <out.csv>            theoretische Position je US-Handelstag seit START (als ob an diesem Tag gehandelt wuerde):
                       levGTAA/MR-Rebound jeder Tag wie ein Monatsletzter, 1xGTAA/levTipsRegime ohne Cooldown;
  <out>_decisions.csv  was der Bot tatsaechlich entschieden hat (volle Historie, Signal auf dem Schlusskurs 'date',
                       Handel am naechsten Handelstag): monatlich je Monatsletztem bzw. taeglich mit Cooldown;
  <out>_explain.json   Herleitung mit allen Zwischenwerten fuer den letzten Schluss (heute simuliert) und fuer die
                       Entscheidung, auf der die gehaltene Position beruht (Dashboard: „So kommt das Signal zustande“).
Die Kernfunktionen des Bot-Repos werden unveraendert benutzt."""
import sys, os, json
repo, mode, out = sys.argv[1], sys.argv[2], os.path.abspath(sys.argv[3])
dec_out = (out[:-4] if out.endswith(".csv") else out) + "_decisions.csv"
ex_out = (out[:-4] if out.endswith(".csv") else out) + "_explain.json"
os.chdir(repo); sys.path.insert(0, repo)
import numpy as np, pandas as pd
START = "2025-01-02"
iso = lambda d: pd.Timestamp(d).date().isoformat()
num = lambda x, n=6: None if x is None or not np.isfinite(float(x)) else round(float(x), n)
MD = {1: 21, 2: 42, 3: 63, 6: 126, 9: 189, 12: 252}                   # Monate -> Handelstage (wie in den Bots)


def ret_m(s, i, m):
    """Rendite ueber m Monate (21*m Handelstage) bis Zeile i."""
    return num(s.iloc[i] / s.iloc[i - MD[m]] - 1) if i >= MD[m] else None


def last_change(states):
    """Zeile, an der die zuletzt gehaltene Position entschieden wurde (letzter Wechsel)."""
    for i in range(len(states) - 1, 0, -1):
        if states[i] != states[i - 1]:
            return i
    return 0

if mode == "levgtaa":
    from strategies import runner as R, momentum_core as MC, common as U
    from strategies.constants import RANKINGS, SMA_LONG, SMA_SHORT, TILT, VT_TARGET, VT_WINDOWS
    raw = R.load_data()
    grid, P, RET, stale, warns, fr = R.prepare(raw)
    rows = np.where(P.index >= pd.Timestamp(START))[0]
    NEW = hasattr(R, "btc_override")                    # Bot mit Bitcoin-Regel (juengster Tagesschluss vor dem Handel)
    btc = R.btc_series(raw) if NEW else None
    if NEW:
        _, W, sc, WF_d, det, binfo = R.compute(P, RET, btc=btc, rows=rows)
    else:
        W, det = MC.decision_weights(P, rows, RANKINGS, SMA_LONG, SMA_SHORT, TILT)
        sc = MC.vt_scale(RET.values, rows, W, VT_TARGET, VT_WINDOWS); binfo = [None] * len(rows)
    df = pd.DataFrame(W * sc[:, None], columns=R.AL).round(4)
    df.insert(0, "date", [iso(d) for d in P.index[rows]])
    df["cash"] = (1 - df[R.AL].sum(axis=1)).clip(lower=0).round(4)
    df["vt_factor"] = np.round(sc, 4)
    df["platz1"] = [R.AL[int(np.argmax(r))] if r.max() > 0 else "CASH" for r in det["P1"]]
    # Bitcoin-Kursdatum je Zeile (juengster abgeschlossener Tagesschluss vor dem Handelstag) und ob endgueltig
    df["btc_date"] = [b["date"].isoformat() if b else "" for b in binfo]
    df["btc_final"] = [int(b["final"]) if b else 1 for b in binfo]
    res = R.compute(P, RET, btc=btc) if NEW else R.compute(P, RET)        # echte Monatsentscheidungen
    mrows, WF = res[0], res[3]
    dec = pd.DataFrame(WF, columns=R.AL).round(4)
    dec.insert(0, "date", [iso(d) for d in P.index[mrows]])
    dec["rebalance"] = "monthly"

    def ex_levgtaa(i):
        Pi, inf = R.btc_override(P, i, btc) if NEW else (P, None)   # Bitcoin: juengster Tagesschluss vor dem Handel
        Wd, dd = MC.decision_weights(Pi, [i], RANKINGS, SMA_LONG, SMA_SHORT, TILT)
        w = Wd[0]
        vols = MC.port_vols(RET.values, i, w, VT_WINDOWS)
        fac = [min(1.0, VT_TARGET / v) if v > 0 else 1.0 for v in vols]
        f = float(np.mean(fac)) if w.sum() > 0 and i >= max(VT_WINDOWS) else 1.0
        smaK = Pi.rolling(SMA_SHORT).mean().iloc[i]
        cross = np.array([(smaK / Pi.rolling(L).mean().iloc[i] - 1).values for L in SMA_LONG])   # (L x Assets)
        trade = P.index[i + 1].date() if i + 1 < len(P) else U.next_session_after(P.index[i].date())
        assets = []
        for k, a in enumerate(R.AL):
            s = Pi[a]
            cd = inf["date"] if (a == "BTC" and inf) else P.index[i].date()
            assets.append({"asset": a, "ticker": R.ASSETS[a]["signal"], "close": num(s.iloc[i], 4), "close_date": cd.isoformat(),
                           "r": {str(m): ret_m(s, i, m) for m in (1, 3, 6, 9, 12)},
                           "sma30": num(smaK[a], 4), "cross_share": num(np.mean(np.nan_to_num(cross[:, k], nan=-1) > 0), 4),
                           "trend": num(np.nanmean(cross[:, k])), "trend_min": num(np.nanmin(cross[:, k])), "trend_max": num(np.nanmax(cross[:, k])),
                           "w_pre": num(w[k], 4), "w": num(w[k] * f, 4)})
        ranks = []
        for name, months in RANKINGS.items():
            pr = dd["per_ranking"][name]
            mo = pr["MOM"][0]
            order = sorted(range(len(R.AL)), key=lambda k: -(mo[k] if np.isfinite(mo[k]) else -9))
            ranks.append({"name": name, "months": list(months), "rows": [
                {"asset": R.AL[k], "mom": num(mo[k]), "pos": pos + 1, "el": num(pr["EL"][0][k], 4),
                 "p1": num(pr["P1"][0][k], 4), "w": num(pr["W"][0][k], 4)} for pos, k in enumerate(order)]})
        return {"date": iso(P.index[i]), "trade": trade.isoformat(), "btc_final": bool(inf["final"]) if inf else True,
                "btc_target": (pd.Timestamp(trade) - pd.Timedelta(days=1)).date().isoformat(), "assets": assets, "rankings": ranks,
                "vt": {"target": VT_TARGET, "windows": list(VT_WINDOWS), "vols": [num(v, 4) for v in vols],
                       "factors": [num(x, 4) for x in fac], "factor": num(f, 4)},
                "params": {"sma_short": SMA_SHORT, "sma_long": [SMA_LONG[0], SMA_LONG[-1]], "n_long": len(SMA_LONG),
                           "tilt": list(TILT)},
                "cash": num(max(0.0, 1 - float((w * f).sum())), 4)}
    EX = {"today": ex_levgtaa(len(P) - 1), "held": ex_levgtaa(int(mrows[-1]))}

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
    from strategies import dip_core as DC
    from strategies.constants import BASKETS, BASKET_LABELS, SMA_SHORT, SMA_LONG, REBOUND_DAYS, GATE_SMA, TILT

    def ex_mr(i):
        Wt, _ = R.compute(P, [i])
        bks = []
        for b, lab in zip(BASKETS, BASKET_LABELS):
            Wb, inf = DC.dip_weights(P, [i], [b], SMA_SHORT, SMA_LONG, REBOUND_DAYS, GATE_SMA, TILT)
            J = [R.AL.index(a) for a in b]
            sma = {L: P[b].rolling(L).mean().iloc[i].values for L in set(SMA_SHORT) | set(SMA_LONG)}
            weak = np.zeros(len(b)); weak2 = np.zeros(len(b))
            for S in SMA_SHORT:
                for L in SMA_LONG:
                    x = sma[S] / sma[L] - 1
                    o = np.argsort(np.where(np.isnan(x), np.inf, x), kind="stable")[:2]
                    weak[o[0]] += 1; weak2[o[1]] += 1
            nv = len(SMA_SHORT) * len(SMA_LONG)
            rows = []
            for j, a in enumerate(b):
                s = P[a]
                rb = {str(Rd): num(s.iloc[i] / s.iloc[i - Rd] - 1) for Rd in REBOUND_DAYS}
                gt = {str(G): num(s.iloc[i] / s.rolling(G).mean().iloc[i] - 1) for G in GATE_SMA}
                rows.append({"asset": a, "ticker": R.ASSETS[a]["signal"], "close": num(s.iloc[i], 4),
                             "rank": num(inf["rank"][0][J[j]]), "weak1": num(weak[j] / nv, 4), "weak2": num(weak2[j] / nv, 4),
                             "rebound": rb, "gate": gt, "w": num(Wb[0][J[j]], 4)})
            bks.append({"label": lab, "rows": rows})
        return {"date": iso(P.index[i]), "baskets": bks, "w": {a: num(Wt[0][k], 4) for k, a in enumerate(R.AL)},
                "cash": num(max(0.0, 1 - float(np.sum(Wt[0]))), 4),
                "params": {"S": [SMA_SHORT[0], SMA_SHORT[-1]], "L": [SMA_LONG[0], SMA_LONG[-1]], "R": REBOUND_DAYS,
                           "G": GATE_SMA, "tilt": [round(t / sum(TILT), 4) for t in TILT],
                           "n": len(SMA_SHORT) * len(SMA_LONG) * len(REBOUND_DAYS) * len(GATE_SMA)}}
    EX = {"today": ex_mr(len(P) - 1), "held": ex_mr(int(mrows[-1]))}

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

    def ex_1x(i):
        mo, tr = ind["mom"].iloc[i], ind["trend"].iloc[i]
        order = sorted([a for a in assets if pd.notna(mo[a])], key=lambda a: mo[a], reverse=True)
        tgt = G.target_gtaa(assets, tr, mo, CFG["N"], CFG.get("weights"), CFG.get("cash_fill", False), CFG.get("fallback", "concentrate"))
        rows = []
        for a in assets:
            s = closes[a]
            pos = order.index(a) + 1 if a in order else None
            rows.append({"asset": a, "ticker": R.ASSETS[a]["ticker"], "close": num(s.iloc[i], 4),
                         "r": {str(m): ret_m(s, i, m) for m in CFG["lookbacks"]}, "mom": num(mo[a]),
                         "sma_s": num(ind["sma_s"][a].iloc[i], 4), "sma_l": num(ind["sma_l"][a].iloc[i], 4),
                         "trend": num(ind["sma_s"][a].iloc[i] / ind["sma_l"][a].iloc[i] - 1), "trend_ok": bool(tr[a]),
                         "pos": pos, "w": num(tgt.get(a, 0.0), 4)})
        rows.sort(key=lambda r: r["pos"] or 99)
        return {"date": iso(idx[i]), "rows": rows, "cash": num(1 - sum(tgt.values()), 4), "cooldown": int(cds[i]),
                "params": {"S": CFG["S"], "L": CFG["L"], "N": CFG["N"], "weights": list(CFG["weights"]),
                           "lookbacks": list(CFG["lookbacks"]), "cooldown": CFG["cooldown_days"]}}
    sig = [G.alloc_signature(a) for a in allocs]
    EX = {"today": ex_1x(len(idx) - 1), "held": ex_1x(last_change(sig)), "cooldown_now": int(cds[-1])}

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

    def ex_tips(i):
        def row(name, ticker, s, n):
            sma = s.rolling(n).mean().iloc[i]
            return {"name": name, "ticker": ticker, "close": num(s.iloc[i], 4), "sma": n, "sma_val": num(sma, 4),
                    "dist": num(s.iloc[i] / sma - 1)}
        rows = [row("S&P 500 Total Return", C.SPY_TICKER, spy, C.SPY_SMA), row("US-TIPS", C.TIPS_TICKER, tips, C.TIPS_SMA)]
        if three:
            rows.append(row("US-Treasury 20y+", C.TLT_TICKER, tlt, C.TLT_SMA))
        return {"date": iso(grid[i]), "rows": rows, "state": names[int(tgt[i])], "held": names[int(alloc[i])],
                "cooldown": int(rem[i]), "params": {"cooldown": C.COOLDOWN_DAYS}}
    EX = {"today": ex_tips(len(grid) - 1), "held": ex_tips(last_change(list(alloc))), "cooldown_now": int(rem[-1])}

df.to_csv(out, index=False)
dec.to_csv(dec_out, index=False)
with open(ex_out, "w", encoding="utf-8") as f:
    json.dump(EX, f, ensure_ascii=False)
print(mode, len(df), "Tage;", len(dec), "Entscheidungen ->", os.path.basename(dec_out))
print(df.tail(2).to_string())
