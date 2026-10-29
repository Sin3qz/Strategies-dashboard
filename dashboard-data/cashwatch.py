"""Cash-Waechter fuer die wikifolios: schaetzt das wikifolio-Cash und meldet per ntfy, bevor es leer wird.

wikifolio entnimmt beide Gebuehren dem Cash, auch vor der Emission schon simulativ: Zertifikategebuehr 0,95 % p. a.
(je Kalendertag) und 5 % Performancegebuehr auf jedes neue Hoch ueber der High-Watermark. Ein negatives Cash muss bei
investierbaren wikifolios binnen 7 Tagen ausgeglichen werden; waehrend der Emission darf es nicht negativ werden.

Startpunkt der Schaetzung (je wikifolio):
  - deine Eingabe (data/wikifolio_holdings.json, Stand-Datum nach dem letzten Bot-Handel): Cash und Stueckzahlen
  - sonst: letzter Bot-Handel, Cash = Bot-Cash bzw. der Puffer-Vorschlag des Rechners an diesem Tag
Davon gehen die Gebuehren seit diesem Tag ab (Kurs und HWM aus der eigenen Aufzeichnung wikifolio_history.csv).
Warnung, wenn das Cash die Gebuehren der naechsten 2 Handelstage (bis 4 Kalendertage Zertifikategebuehr + Performance-
gebuehr bei einem starken 2-Tage-Anstieg, 95-%-Wert der Strategie) nicht mehr sicher deckt; Alarm, wenn es negativ ist.
Ergebnis in data/cash_watch.json (Anzeige auf der Seite wikifolios), Meldungen ueber notify_state.json entprellt.
"""
import csv, datetime as dt, json, math, os

URL = "https://sin3qz.github.io/Strategies-dashboard/#rechner"
STRAT = {"levgtaa": "levgtaa", "levtipsregime": "levtips"}
NAME = {"levgtaa": "LevGTAA", "levtipsregime": "LevTipsRegime"}
PRODUCT_KEYS = {"levgtaa": ("NDX3", "BTC1", "UST3", "GOLD3"), "levtipsregime": ("SPX3", "BTC1", "UST3")}


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


def reserve(w, ps, gap):
    """Gleiche Regel wie der Rechner (page.html reserveSuggest)."""
    st = stage(w)
    strong = ps.get("hi1m_q95" if st == "emission" else "hi1m_q90") or 0.2
    need = 1 / (1 + gap) - 1 if gap < 0 else 0.0
    fee, perf = float(w.get("fee_cert") or 0.0095) / 12, float(w.get("fee_perf") or 0.05)
    return min(0.01, max(0.0, math.ceil((fee + perf * max(0.0, strong - need)) * 2000) / 2000 + 0.0005))


def estimate(key, w, hist, strat, alloc, ps, holds, px, today):
    fee_c, fee_p = float(w.get("fee_cert") or 0.0095), float(w.get("fee_perf") or 0.05)
    p_now, hwm_now = float(w["price"]), float(w["high_watermark"])
    created = _d(w.get("created"))
    start_px = p_now / (1 + float(w.get("perf_since_start") or 0))
    rows = sorted((r for r in hist if r["key"] == key and r.get("price")), key=lambda r: r["date"])
    bot_cash = max(0.0, 1 - sum(float(a["weight"] or 0) for a in alloc if a["strategy"] == key and a["asset"] != "CASH"))
    out = {"key": key, "name": NAME[key], "stage": stage(w), "date": today.isoformat()}
    if bot_cash > 0.98:
        return {**out, "level": "ok", "cash": 1.0, "basis": "Bot steht in Cash",
                "detail": "Das wikifolio steht laut Bot komplett in Cash – die Gebühren sind gedeckt."}

    # letzter Bot-Handel (Puffer wird beim Handel gesetzt)
    s = next((x for x in strat if x["key"] == key), {})
    trade = _d(s.get("tradeDate")) or (_next_bd(_d(s["since"])) if s.get("since") else None) or created
    trade = max(trade, created) if created else trade

    # Startpunkt: deine Eingabe, wenn sie nach dem letzten Handel liegt
    h = [x for x in holds if x.get("wikifolio") == key]
    h_date = max((_d(x.get("stand")) for x in h if x.get("stand")), default=None)
    price_of = {x["key"]: float(x["price_eur"]) for x in px}
    val = sum(float(x.get("stueck") or 0) * float(x.get("kurs_eur") or price_of.get(x["product"], 0)) for x in h if x["product"] != "CASH")
    cash_eur = sum(float(x.get("stueck") or 0) for x in h if x["product"] == "CASH")

    def px_at(d):                                       # wikifolio-Kurs am Tag d (eigene Aufzeichnung, sonst Startkurs/heute)
        before = [r for r in rows if r["date"] <= d.isoformat()]
        if before:
            return float(before[-1]["price"])
        return start_px if created and d <= created + dt.timedelta(days=3) else (float(rows[0]["price"]) if rows else p_now)

    def hwm_at(d):
        before = [r for r in rows if r["date"] <= d.isoformat() and r.get("high_watermark")]
        if before:
            return float(before[-1]["high_watermark"])
        if created and d <= created + dt.timedelta(days=3):
            return start_px                             # Start: HWM = Startkurs
        return float(rows[0]["high_watermark"]) if rows and rows[0].get("high_watermark") else hwm_now

    if h_date and h_date >= trade and val + cash_eur > 0:
        d0, c0 = h_date, cash_eur / (val + cash_eur)
        basis = f"deine Eingabe vom {d0:%d.%m.%Y} ({cash_eur:,.0f} € Cash)".replace(",", ".")
        total_eur = (val + cash_eur) * p_now / px_at(d0)
    else:
        d0 = trade
        gap0 = min(0.0, px_at(d0) / hwm_at(d0) - 1)
        c0 = max(bot_cash, reserve(w, ps, gap0))
        basis = (f"Annahme: beim letzten Handel ({d0:%d.%m.%Y}) lag der Rechner-Vorschlag im Cash"
                 + (f" ({c0 * 100:.2f} %)".replace(".", ",")))
        total_eur = None

    # Gebuehren seit d0 in Indexpunkten (Cash in Indexpunkten = Anteil x Kurs)
    c = c0 * px_at(d0)
    d = d0
    while d < today:
        d += dt.timedelta(days=1)
        c -= fee_c / 365 * px_at(d)
    h0 = hwm_at(d0)
    c -= fee_p * max(0.0, hwm_now - h0)                 # jede HWM-Erhoehung = bezahlte Performancegebuehr
    cash = c / p_now

    gap = min(0.0, p_now / hwm_now - 1)
    need = 1 / (1 + gap) - 1 if gap < 0 else 0.0
    q2 = ps.get("hi2d_q95") or 0.08
    need2 = 4 * fee_c / 365 + fee_p * max(0.0, q2 - need)
    burn = fee_c / 365
    days = (cash / burn) if cash > 0 else 0
    target = reserve(w, ps, gap)
    top = max(0.0, target - cash)
    level = "neg" if cash < 0 else "warn" if cash < need2 else "ok"
    eur = (lambda x: f" (≈ {x * total_eur:,.0f} €)".replace(",", ".")) if total_eur else (lambda x: "")
    pc = lambda x: f"{x * 100:.2f} %".replace(".", ",").replace("-", "−")
    if level == "ok":
        detail = (f"Cash geschätzt {pc(cash)}{eur(cash)}, reicht für die Zertifikategebühr noch etwa {days:.0f} Tage; "
                  f"Reserve für die nächsten 2 Handelstage {pc(need2)}.")
    else:
        detail = (("Cash geschätzt NEGATIV: " if level == "neg" else "Cash-Puffer fast leer: ")
                  + f"{pc(cash)}{eur(cash)}, nötig für die nächsten 2 Handelstage bis {pc(need2)}. "
                  + f"Auf {pc(target)} auffüllen, also etwa {pc(top)}{eur(top)} verkaufen (Rechner zeigt die Order)."
                  + (" Emission läuft: das Cash darf nicht negativ werden." if out["stage"] == "emission" else
                     " Negatives Cash muss binnen 7 Tagen ausgeglichen werden." if out["stage"] == "invest" else ""))
    return {**out, "level": level, "cash": round(cash, 6), "cash_eur": round(cash * total_eur, 2) if total_eur else None,
            "need2": round(need2, 6), "days": round(days, 1), "target": target, "topup": round(top, 6),
            "topup_eur": round(top * total_eur, 2) if total_eur else None, "since": d0.isoformat(), "basis": basis, "detail": detail}


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
