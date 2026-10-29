"""Cash-Waechter fuer die wikifolios: schaetzt das wikifolio-Cash und meldet per ntfy, bevor es leer wird.

wikifolio entnimmt beide Gebuehren dem Cash, auch vor der Emission schon simulativ: Zertifikategebuehr 0,95 % p. a.
(je Kalendertag) und 5 % Performancegebuehr auf jedes neue Hoch ueber der High-Watermark. Ein negatives Cash muss bei
investierbaren wikifolios binnen 7 Tagen ausgeglichen werden; im Emissionsprozess darf es nicht negativ sein.

Grundlage ist NUR deine Eingabe (Rechner -> „Auf GitHub speichern“, data/wikifolio_holdings.json): Cash in EUR und
Stueckzahlen am Stand-Datum. Ohne Eingabe nach dem letzten Bot-Handel meldet der Waechter „unbekannt“ (keine Annahmen).
Geldmarkt-ETF (MM) zaehlt als Anlage, nicht als Cash. Wert des wikifolios = Summe deiner Positionen, sonst Index x 1.000
(wikifolio startet mit 100.000 EUR bei Index 100).
Von deinem Cash gehen ab: Zertifikategebuehr je Kalendertag (auf den Tageswert) und die Performancegebuehr jeder
HWM-Erhoehung seit dem Stand-Datum (eigene Aufzeichnung wikifolio_history.csv).
Warnung, wenn das Cash die Gebuehren der naechsten 2 Handelstage nicht mehr sicher deckt: bis 4 Kalendertage
Zertifikategebuehr + Performancegebuehr bei einem starken 2-Tage-Anstieg (95-%-Wert; anteilig nach Risiko-Anteil, der
Geldmarkt-Anteil steigt kaum). Alarm, wenn das Cash negativ ist. Ergebnis in data/cash_watch.json.
"""
import csv, datetime as dt, json, math, os

URL = "https://sin3qz.github.io/Strategies-dashboard/#rechner"
STRAT = {"levgtaa": "levgtaa", "levtipsregime": "levtips"}
NAME = {"levgtaa": "LevGTAA", "levtipsregime": "LevTipsRegime"}
MM_HI1M, MM_HI2D = 0.003, 0.0005        # Geldmarkt-ETF: hoechster Stand binnen 21 bzw. 2 Handelstagen (grosszuegig)


def _load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f) if path.endswith(".json") else list(csv.DictReader(f))
    except Exception:
        return default


def _d(s):
    return dt.date.fromisoformat(str(s)[:10]) if s else None


def _next_bd(d):
    d += dt.timedelta(days=1)
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d


def crit_met(w):
    pairs = (("test_days", "test_days_req"), ("reservations", "reservations_req"), ("capital_eur", "capital_req_eur"))
    return sum(1 for a, b in pairs if w.get(a) is not None and w.get(b) is not None and float(w[a]) >= float(w[b]))


def stage(w):
    return "invest" if w.get("status") == "Investierbar" else "emission" if crit_met(w) == 3 else "preview"


def reserve(w, ps, gap, risky=1.0):
    """Gleiche Regel wie der Rechner (page.html reserveSuggest); risky = Anteil in Risiko-Bausteinen (Rest Geldmarkt)."""
    st = stage(w)
    q = ps.get("hi1m_q95" if st == "emission" else "hi1m_q90") or 0.2
    strong = risky * q + (1 - risky) * MM_HI1M
    need = 1 / (1 + gap) - 1 if gap < 0 else 0.0
    fee, perf = float(w.get("fee_cert") or 0.0095) / 12, float(w.get("fee_perf") or 0.05)
    return min(0.01, max(0.0, math.ceil((fee + perf * max(0.0, strong - need)) * 2000) / 2000 + 0.0005))


def estimate(key, w, hist, strat, alloc, ps, holds, px, today):
    fee_c, fee_p = float(w.get("fee_cert") or 0.0095), float(w.get("fee_perf") or 0.05)
    p_now, hwm_now = float(w["price"]), float(w["high_watermark"])
    rows = sorted((r for r in hist if r["key"] == key and r.get("price")), key=lambda r: r["date"])
    out = {"key": key, "name": NAME[key], "stage": stage(w), "date": today.isoformat()}

    s = next((x for x in strat if x["key"] == key), {})
    created = _d(w.get("created"))
    trade = _d(s.get("tradeDate")) or (_next_bd(_d(s["since"])) if s.get("since") else None) or created
    trade = max(trade, created) if (trade and created) else trade

    h = [x for x in holds if x.get("wikifolio") == key]
    cash_row = next((x for x in h if x.get("product") == "CASH" and x.get("stand")), None)
    h_date = _d(cash_row["stand"]) if cash_row else None
    if not cash_row or (trade and h_date < trade):
        why = ("noch keine Eingabe" if not cash_row else
               f"deine Eingabe vom {h_date:%d.%m.%Y} liegt vor dem letzten Bot-Handel ({trade:%d.%m.%Y})")
        return {**out, "level": "unknown", "basis": why,
                "detail": f"Cash unbekannt ({why}). Im Rechner Stückzahlen und Cash eintragen und „Auf GitHub speichern“ "
                          "– dann rechnet der Wächter jeden Tag die Gebühren ab und meldet sich rechtzeitig."}

    price_of = {x["key"]: float(x["price_eur"]) for x in px}
    val = {x["product"]: float(x.get("stueck") or 0) * float(x.get("kurs_eur") or price_of.get(x["product"], 0) or 0)
           for x in h if x["product"] != "CASH"}
    cash_eur = float(cash_row.get("stueck") or 0)

    def px_at(d):                                       # wikifolio-Kurs am Tag d (eigene Aufzeichnung)
        before = [r for r in rows if r["date"] <= d.isoformat()]
        return float(before[-1]["price"]) if before else (float(rows[0]["price"]) if rows else p_now)

    def hwm_at(d):
        before = [r for r in rows if r["date"] <= d.isoformat() and r.get("high_watermark")]
        return float(before[-1]["high_watermark"]) if before else hwm_now

    p0 = px_at(h_date)
    pos = sum(val.values())
    total0 = pos + cash_eur if pos > 0 else p0 * 1000          # ohne Stueckzahlen: Index x 1.000
    units = total0 / p0                                         # Zertifikate-Einheiten (Wert = Einheiten x Index)
    bot_risky = min(1.0, sum(float(a.get("weight") or 0) for a in alloc if a["strategy"] == key and a["asset"] != "CASH"))
    risky = 1 - (val.get("MM", 0) / pos) if pos > 0 else bot_risky     # ohne Stueckzahlen: Risiko-Anteil laut Bot
    c = cash_eur
    d = h_date
    while d < today:
        d += dt.timedelta(days=1)
        c -= fee_c / 365 * px_at(d) * units
    c -= fee_p * max(0.0, hwm_now - hwm_at(h_date)) * units    # jede HWM-Erhoehung = bezahlte Performancegebuehr
    total = p_now * units
    cash = c / total

    gap = min(0.0, p_now / hwm_now - 1)
    need = 1 / (1 + gap) - 1 if gap < 0 else 0.0
    q2 = risky * (ps.get("hi2d_q95") or 0.08) + (1 - risky) * MM_HI2D
    need2 = 4 * fee_c / 365 + fee_p * max(0.0, q2 - need)
    burn = fee_c / 365
    days = (cash / burn) if cash > 0 else 0
    target = reserve(w, ps, gap, risky)
    top = max(0.0, target - cash)
    level = "neg" if cash < 0 else "warn" if cash < need2 else "ok"
    e = lambda x: f"{x * total:,.0f} €".replace(",", ".").replace("-", "−")
    pc = lambda x: f"{x * 100:.2f} %".replace(".", ",").replace("-", "−")
    if level == "ok":
        detail = (f"Cash geschätzt {e(cash)} ({pc(cash)}), reicht für die Zertifikategebühr noch etwa {days:.0f} Tage; "
                  f"Reserve für die nächsten 2 Handelstage {pc(need2)}.")
    else:
        detail = (("Cash NEGATIV: " if level == "neg" else "Cash-Puffer fast leer: ")
                  + f"geschätzt {e(cash)} ({pc(cash)}), nötig für die nächsten 2 Handelstage bis {pc(need2)}. "
                  + f"Auf {pc(target)} auffüllen: etwa {e(top)} verkaufen (Rechner zeigt die Order)."
                  + (" Emission läuft: das Cash darf im Emissionsprozess nicht negativ sein – heute ausgleichen."
                     if out["stage"] == "emission" else
                     " Negatives Cash muss binnen 7 Tagen ausgeglichen werden." if out["stage"] == "invest" else ""))
    return {**out, "level": level, "cash": round(cash, 6), "cash_eur": round(c, 2), "total_eur": round(total, 2),
            "need2": round(need2, 6), "days": round(days, 1), "target": target, "topup": round(top, 6),
            "topup_eur": round(top * total, 2), "since": h_date.isoformat(),
            "basis": f"deine Eingabe vom {h_date:%d.%m.%Y}: {cash_eur:,.2f} € Cash".replace(",", "X").replace(".", ",").replace("X", "."),
            "detail": detail}


def run(out_dir, state, send=None, today=None):
    """Schreibt cash_watch.json; gibt Liste (Titel, ok) gesendeter Meldungen zurueck. state = notify_state (wird ergaenzt)."""
    today = today or dt.date.today()
    j = lambda n, dflt: _load(os.path.join(out_dir, n), dflt)
    wfs, strat, alloc, holds, px = j("wikifolios.json", []), j("strategies.json", []), j("allocations.json", []), \
        j("wikifolio_holdings.json", []), j("prices.json", [])
    ps = {r["key"]: r for r in j("perf_stats.json", [])}
    hist = j("wikifolio_history.csv", [])
    res, sent = [], []
    rank = {"ok": 0, "warn": 1, "neg": 2}
    for w in wfs:
        if w["key"] not in STRAT:
            continue
        try:
            r = estimate(w["key"], w, hist, strat, alloc, ps.get(STRAT[w["key"]], {}), holds, px, today)
        except Exception as e:
            r = {"key": w["key"], "name": NAME.get(w["key"], w["key"]), "level": "unknown", "detail": f"Schätzung nicht möglich: {e}"}
        res.append(r)
        k = "cash_" + w["key"]
        old = state.get(k) or {}
        lv = r.get("level")
        if lv in ("warn", "neg") and send and (rank[lv] > rank.get(old.get("level"), 0) or (lv == "neg" and old.get("date") != today.isoformat())):
            ok = send(f"{r['name']}: Cash-Puffer {'negativ' if lv == 'neg' else 'fast leer'}",
                      r["detail"] + f"\nBasis: {r.get('basis', '')}\n\n{URL}", tags="moneybag")
            sent.append((f"Cash {r['name']}", ok))
            state[k] = {"level": lv, "date": today.isoformat()}
        elif lv in ("ok", "warn", "neg"):
            state[k] = {"level": lv if lv != "ok" else "ok", "date": old.get("date") if lv != "ok" else today.isoformat()}
    with open(os.path.join(out_dir, "cash_watch.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False)
    return sent
