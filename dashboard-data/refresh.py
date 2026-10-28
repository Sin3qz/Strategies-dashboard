#!/usr/bin/env python3
"""Baut alle Datendateien des Dashboards "Strategien & wikifolios" neu (GitHub Pages, Ordner data/).

Aufruf:  python3 dashboard-data/refresh.py [arbeitsordner]
Ergebnis: data/*.json|csv, data/build.json (Zeitpunkt, Fehler) und data/manifest.json (Dataset-Id -> Datei, Titel).
          data/wikifolio_history.csv wird je Tag um eine Zeile je wikifolio ergaenzt.
Laeuft per GitHub Action (.github/workflows/refresh-dashboard.yml) mehrmals taeglich.

Quellen:
  - status_*.json / history_levgtaa.txt der vier Bot-Repos (public, letzter Commit auf main)
  - Tagessignal-Simulation fuer levGTAA, MR-Rebound, 1xGTAA, levTipsRegime mit dem Code der Bot-Repos (daily_signals.py, Yahoo-Kurse)
  - wikifolio.com: eingebettete Seitendaten (__NEXT_DATA__) von WFXLEVGTAA und WFXTIPSREG
Faellt eine Quelle aus oder ist unplausibel, bleibt deren letzte gueltige Datei stehen und build.json nennt den Fehler.
Exit-Code != 0 nur, wenn gar nichts aktualisiert werden konnte.
"""
import csv, datetime as dt, json, os, re, shutil, subprocess, sys, traceback, urllib.request
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "work"))
OUT = os.path.join(os.path.dirname(HERE), "data")
HIST = os.path.join(OUT, "wikifolio_history.csv")
USER = "Sin3qz"
REPOS = {"levgtaa": ("levgtaa-signalbot", "status_levgtaa.json"),
         "levtipsregime": ("levtipsregime-signalbot", "letsgo_status.json"),
         "mrreboundgtaa": ("mrreboundgtaa-signalbot", "status_mrreboundgtaa.json"),
         "1xgtaa": ("1xgtaa-signalbot", "status_1xgtaa.json")}
SIG_COLS = {"levgtaa": ["baustein", "momentum", "trend", "vola", "ziel"],
            "levtipsregime": ["baustein", "linie", "abstand", "status"],
            "mrreboundgtaa": ["baustein", "rang", "rebound", "gate", "ziel"],
            "1xgtaa": ["baustein", "mom", "trend", "ziel"]}
# Backtest-Kennzahlen aus strategies/constants.py der Bot-Repos (Stand Freigabe 29.09./17.10.2026)
WIKIFOLIOS = {
    "levgtaa": dict(symbol="wfxlevgtaa", strategy="levGTAA", bt_cagr=0.319, bt_maxdd=-0.43, bt_sortino=1.23,
                    bt_label="Backtest 1993+ (3x IEF, Signal TLT)"),
    "levtipsregime": dict(symbol="wfxtipsreg", strategy="levTipsRegime", bt_cagr=0.301, bt_maxdd=-0.50, bt_sortino=0.93,
                          bt_label="Backtest 1987+ (Referenz 75 % 3x S&P 500 / 25 % 1x BTC)"),
}
TZ = ZoneInfo("Europe/Berlin")
NOW = dt.datetime.now(TZ)


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def raw(repo, path):
    return get(f"https://raw.githubusercontent.com/{USER}/{repo}/main/{path}")


def clone(repo):
    local = os.environ.get("BOT_REPO_DIR")              # lokal: vorhandene Checkouts statt frischem Klon (Tests)
    if local and os.path.isdir(os.path.join(local, repo)):
        return os.path.join(local, repo)
    d = os.path.join(WORK, repo)
    if os.path.isdir(os.path.join(d, ".git")):
        subprocess.run(["git", "-C", d, "fetch", "-q", "--depth", "1", "origin", "main"], check=True)
        subprocess.run(["git", "-C", d, "reset", "-q", "--hard", "origin/main"], check=True)
    else:
        subprocess.run(["git", "clone", "-q", "--depth", "1", f"https://github.com/{USER}/{repo}.git", d], check=True)
    return d


def wjson(name, obj):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


# ---------------------------------------------------------------------------
def bots():
    strategies, alloc, signals = [], [], []
    for key, (repo, fn) in REPOS.items():
        d = json.loads(raw(repo, fn))
        row = {"key": key, "updated": d.get("updated"), "asOf": d.get("asOf"), "rebalance": d.get("rebalance"),
               "decisionDate": d.get("decisionDate"), "tradeDate": d.get("tradeDate"), "nextDecision": d.get("nextDecision"),
               "nextRebalance": d.get("nextRebalance"), "cooldown": d.get("cooldown"), "changeType": d.get("changeType"),
               "pendingDecision": d.get("pendingDecision"), "pendingTrade": d.get("pendingTrade"), "late": bool(d.get("late")),
               "needsRetry": bool(d.get("needsRetry")), "warnings": " · ".join(d.get("dataWarnings") or []),
               "weightDecimals": d.get("weightDecimals") or 0, "since": d.get("since"),
               "vola_cap": None, "vola_factor": None, "vola_decision": None, "vola_now": None, "vola_pre": None, "vola_windows": None}
        v = d.get("vola")
        if v:
            row.update(vola_cap=v["cap"], vola_factor=v["factor"], vola_decision=v["decisionDate"],
                       vola_now=v["holdingNowMean"], vola_pre=v["signalPreMean"], vola_windows="/".join(map(str, v["windows"])))
        strategies.append(row)
        al = d["allocation"]
        if key == "levtipsregime" and any(a.get("weight") is None for a in al):     # alter Bot-Stand (Gewichtung frei): 100 % 3x S&P 500
            al = [dict(a, weight=1.0) for a in al if a["asset"] == "SP500"] or al
        for a in al:
            alloc.append({"strategy": key, "asset": a["asset"], "display": a["display"], "weight": a["weight"],
                          "leverage": a["leverage"], "product": a["product"], "isin": a["isin"]})
        for r in d["table"]["rows"]:
            rec = {"strategy": key}
            rec.update(dict(zip(SIG_COLS[key], r)))
            signals.append(rec)
        if key == "levgtaa":
            with open(os.path.join(OUT, "levgtaa_history.csv"), "w", encoding="utf-8") as f:
                f.write(raw(repo, "history_levgtaa.txt"))
    assert len(strategies) == 4 and alloc and signals
    wjson("strategies.json", strategies)
    wjson("allocations.json", alloc)
    wjson("signals.json", signals)
    return {s["key"]: s for s in strategies}


def daily():
    script = os.path.join(HERE, "daily_signals.py")
    for repo, mode in (("levgtaa-signalbot", "levgtaa"), ("mrreboundgtaa-signalbot", "mrrebound"),
                       ("1xgtaa-signalbot", "1xgtaa"), ("levtipsregime-signalbot", "levtips")):
        try:
            d = clone(repo)
            tmp = os.path.join(WORK, f"daily_{mode}.csv")
            subprocess.run([sys.executable, script, d, mode, tmp], check=True)
            with open(tmp, encoding="utf-8") as f:
                n = sum(1 for _ in f) - 1
            with open(tmp[:-4] + "_decisions.csv", encoding="utf-8") as f:
                nd = sum(1 for _ in f) - 1
            assert n > 300 and nd > 100, f"nur {n} Tage / {nd} Entscheidungen"
            shutil.copyfile(tmp, os.path.join(OUT, f"daily_{mode}.csv"))
            shutil.copyfile(tmp[:-4] + "_decisions.csv", os.path.join(WORK, f"decisions_{mode}.csv"))
        except Exception as e:
            ERRORS.append(f"Tagessignal {mode}: {e}")
            traceback.print_exc()


def tlt_row():
    """Bis der Bot-Branch mit dem IEF-Zweig auf main ist, fehlt die TLT-Zeile im Bot-Status: aus dem Tagessignal ergaenzen."""
    f, d = os.path.join(OUT, "signals.json"), os.path.join(OUT, "daily_levtips.csv")
    if not (os.path.exists(f) and os.path.exists(d)):
        return
    sig = json.load(open(f, encoding="utf-8"))
    if any(r["strategy"] == "levtipsregime" and "TLT" in str(r.get("baustein")) for r in sig):
        return
    last = list(csv.DictReader(open(d, encoding="utf-8")))[-1]
    if last.get("tlt_dist") in (None, ""):
        return
    v = float(last["tlt_dist"])
    sig.append({"strategy": "levtipsregime", "baustein": "US-Treasury 20y+ (TLT)", "linie": "SMA200",
                "abstand": round(v, 6), "status": "über" if v > 0 else "unter"})
    wjson("signals.json", sig)


def wikifolio(key, meta):
    h = get(f"https://www.wikifolio.com/de/de/w/{meta['symbol']}")
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', h, re.S)
    data = json.loads(m.group(1))["props"]["pageProps"]["data"]
    wf, kf, md, cert = data["wikifolio"], data["keyFigures"], data["masterData"], data["certificates"][0]

    def rank(groups, label):
        for g in groups:
            for r in g.get("rankings", []):
                if r["ranking"]["label"].lower().startswith(label.lower()):
                    return r["ranking"].get("value") if "place" not in r["ranking"] else r["ranking"]["place"]
        return None
    risk = kf.get("otherKeyRiskIndicators") or []
    perf = kf.get("kpis") or []
    top = [{"rankings": kf.get("topKpis") or []}]

    def single(name):                                    # Einzelkennzahl (investiertes Kapital, Handelsvolumen, ...)
        try:
            return (kf.get(name) or {}).get("ranking", {}).get("value")
        except AttributeError:
            return None
    investable = bool(cert.get("isin"))
    row = {
        "key": key, "name": wf["shortDescription"], "symbol": md["symbol"]["value"], "strategy": meta["strategy"],
        "url": f"https://www.wikifolio.com/de/de/w/{meta['symbol']}",
        "trader": data["trader"]["nickName"], "created": md["creationDate"]["value"][:10],
        "perf_since_start": data["structuredData"]["performanceSinceCreation"],
        "perf_ytd": rank(perf, "Seit Jahresbeginn"),
        "perf_1m": rank(top, "Performance (1 M)"),
        "vola": rank(top, "Volatilität"),
        "avg_pa": rank(perf[:1], "Ø-Performance pro Jahr (Max)"),
        "max_loss": rank(risk[:1], "Maximaler Verlust"),
        "sharpe": rank(risk[:1], "Sharpe Ratio"), "ret_risk": rank(risk[:1], "Rendite/Risiko"),
        "invested": single("totalInvestments"), "trading_volume": single("tradingVolume"),
        "liquidation": single("liquidationFigure"),
        "last_login": (data["trader"].get("lastLogin") or "")[:10] or None,
        "emission": (cert.get("emissionDate") or "")[:10] or None,
        "high_watermark": md["highWatermark"]["value"], "price": data["structuredData"]["price"],
        "watchlistings": rank(perf, "Watchlistings"), "rank_place": rank(perf, "wikifolio Rangliste"),
        "status": "Investierbar" if investable else "Vorschau", "isin": cert.get("isin"),
        "test_days": cert["testPhaseDays"]["currentValue"], "test_days_req": cert["testPhaseDays"]["requiredValue"],
        "reservations": cert["buyingInterests"]["currentValue"], "reservations_req": cert["buyingInterests"]["requiredValue"],
        "capital_eur": cert["reservedCapital"]["currentValue"], "capital_req_eur": cert["reservedCapital"]["requiredValue"],
        "fee_cert": wf["dailyFee"], "fee_perf": wf["performanceFee"],
        "bt_cagr": meta["bt_cagr"], "bt_maxdd": meta["bt_maxdd"], "bt_sortino": meta["bt_sortino"], "bt_label": meta["bt_label"],
        "asOf": NOW.date().isoformat(),
    }
    assert row["trader"] == "Sineqz" and row["price"] and row["price"] > 0, f"{key}: unerwartete wikifolio-Daten"
    return row


def wikifolios():
    prev = {}
    try:
        with open(os.path.join(OUT, "wikifolios.json"), encoding="utf-8") as f:
            prev = {r["key"]: r for r in json.load(f)}
    except Exception:
        pass
    rows, fresh = [], []
    for k, m in WIKIFOLIOS.items():
        try:
            rows.append(wikifolio(k, m)); fresh.append(rows[-1])
        except Exception as e:                      # letzter gueltiger Stand bleibt (asOf zeigt sein Alter)
            ERRORS.append(f"wikifolio {m['symbol']}: {e}")
            if k in prev:
                rows.append(prev[k])
    if not rows:
        raise RuntimeError("kein wikifolio ladbar")
    wjson("wikifolios.json", rows)
    cols = ["date", "key", "price", "perf_since_start", "max_loss", "reservations", "capital_eur", "watchlistings", "invested",
            "high_watermark"]
    old = []
    if os.path.exists(HIST):
        with open(HIST, encoding="utf-8") as f:
            old = [r for r in csv.DictReader(f) if not (r["date"] == NOW.date().isoformat() and r["key"] in {x["key"] for x in fresh})]
    new = old + [{"date": NOW.date().isoformat(), **{c: r.get(c) for c in cols[1:]}} for r in fresh]
    new.sort(key=lambda r: (r["date"], r["key"]))
    with open(HIST, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, restval=""); w.writeheader(); w.writerows(new)


MANIFEST = {
    "perf_stats": ("perf_stats.json", "Performance-Kennzahlen", "CAGR, Max-Drawdown, Volatilität, Sharpe usw. je Strategie und Mischung, gerechnet mit den gehandelten Produkten in EUR (dashboard-data/equity.py)."),
    "equity": ("equity.csv", "Equity-Kurven", "Wertentwicklung je Strategie und Mischung (Start 100), echte Produktkurse in EUR, Handel am Tag nach dem Signal, 0,1 % Kosten je Umschichtung."),
    "monthly_returns": ("monthly_returns.json", "Monatsrenditen", "Monatsrendite je Strategie und Mischung aus den Equity-Kurven."),
    "correlation": ("correlation.json", "Korrelation", "Korrelation der Tagesrenditen der vier Strategien im gemeinsamen Zeitraum."),
    "tracking": ("tracking.json", "Bot-Soll ab wikifolio-Start", "Equity der Bot-Allokation ab 01.10.2026 (Index 100) zum Vergleich mit dem wikifolio."),
    "prices": ("prices.json", "Produktkurse", "Letzter Kurs je gehandeltem Produkt in EUR (Yahoo; USD/Pence mit EURUSD/EURGBP umgerechnet)."),
    "holdings": ("wikifolio_holdings.json", "wikifolio-Positionen (deine Eingabe)", "Stückzahlen je Produkt in den wikifolios, von dir gepflegt (wikifolio zeigt Positionen nur angemeldet)."),
    "build": ("build.json", "Letzte Aktualisierung", "Zeitpunkt des letzten Laufs der Aktualisierung und Quellen, die dabei nicht geladen werden konnten."),
    "wikifolios": ("wikifolios.json", "wikifolio-Kennzahlen",
                   "Kennzahlen der wikifolios LevGTAA (WFXLEVGTAA) und LevTipsRegime (WFXTIPSREG) von wikifolio.com, dazu die Backtest-Werte aus den Bot-Repos."),
    "wikifolio_history": ("wikifolio_history.csv", "wikifolio-Verlauf (eigene Aufzeichnung)",
                          "Eine Zeile je Tag und wikifolio, täglich von wikifolio.com mitgeschrieben (seit 28.10.2026)."),
    "strategies": ("strategies.json", "Bot-Status je Strategie",
                   "Stand, Termine, Handelssignal und Vola aus status_*.json der vier Bot-Repos (letzter Commit)."),
    "allocations": ("allocations.json", "Aktuelle Allokationen", "Zielquoten, Hebel und Produkte je Strategie aus status_*.json der vier Bot-Repos."),
    "signals": ("signals.json", "Signaltabellen", "Kennzahlen je Baustein und Strategie aus status_*.json der vier Bot-Repos."),
    "levgtaa_history": ("levgtaa_history.csv", "levGTAA Monatsentscheidungen", "Jede Monatsentscheidung seit 2003 aus history_levgtaa.txt im Repo levgtaa-signalbot."),
    "daily_levgtaa": ("daily_levgtaa.csv", "levGTAA Tagessignal (simuliert)",
                      "Für jeden US-Handelstag seit 02.01.2025 die levGTAA-Zielquoten nach Vol-Target, als wäre der Tag ein Monatsletzter; gerechnet mit momentum_core.py aus levgtaa-signalbot auf Yahoo-Schlusskursen."),
    "daily_mrrebound": ("daily_mrrebound.csv", "MR-Rebound Tagessignal (simuliert)",
                        "Für jeden US-Handelstag seit 02.01.2025 die MR-Rebound-Zielquoten, als wäre der Tag ein Monatsletzter; gerechnet mit dip_core.py aus mrreboundgtaa-signalbot auf Yahoo-Schlusskursen."),
    "daily_1xgtaa": ("daily_1xgtaa.csv", "1xGTAA Tagessignal (simuliert)",
                     "Für jeden US-Handelstag seit 02.01.2025 die 1xGTAA-Zielquote ohne Cooldown, dazu die gehaltene Allokation und der Cooldown; gerechnet mit gtaa_botcore.py aus 1xgtaa-signalbot."),
    "daily_levtips": ("daily_levtips.csv", "levTipsRegime Tagessignal (simuliert)",
                      "Für jeden US-Handelstag seit 02.01.2025 Markt (1) oder Cash (0) ohne Cooldown, die gehaltene Position und die Abstände von S&P 500 TR zur SMA280 und TIPS zur SMA220; gerechnet mit levspybits.py aus levtipsregime-signalbot."),
}


ERRORS = []


def step(name, fn):
    try:
        return fn()
    except Exception as e:
        ERRORS.append(f"{name}: {e}")
        traceback.print_exc()
        return None


HOLDINGS_TEMPLATE = [   # wird nur angelegt, wenn die Datei fehlt; deine Eintraege ueberschreibt die Aktualisierung nie
    {"wikifolio": "levgtaa", "product": p, "stueck": 0, "kurs_eur": None, "stand": None} for p in ("NDX3", "BTC1", "UST3", "GOLD3")
] + [{"wikifolio": "levtipsregime", "product": p, "stueck": 0, "kurs_eur": None, "stand": None} for p in ("SPX3", "BTC1", "UST3")
] + [{"wikifolio": w, "product": "CASH", "stueck": 0, "kurs_eur": 1, "stand": None} for w in ("levgtaa", "levtipsregime")]


def holdings():
    path = os.path.join(OUT, "wikifolio_holdings.json")
    if not os.path.exists(path):
        wjson("wikifolio_holdings.json", HOLDINGS_TEMPLATE)


def main():
    os.makedirs(OUT, exist_ok=True); os.makedirs(WORK, exist_ok=True)
    st = step("Bot-Status", bots)
    daily()
    step("TLT-Zeile", tlt_row)
    step("wikifolio", wikifolios)
    holdings()
    sys.path.insert(0, HERE)
    import equity, notify
    issues = step("Performance", lambda: equity.run(WORK, OUT)) or []
    for i in issues:
        print("Hinweis Kursdaten:", i)
    sent = step("Push", lambda: notify.run(OUT)) or []
    for t, ok in sent:
        print("Push:", t, "->", ok)
    man = {k: {"file": f, "title": t, "description": d} for k, (f, t, d) in MANIFEST.items()}
    missing = [k for k, m in man.items() if not os.path.exists(os.path.join(OUT, m["file"]))]
    wjson("manifest.json", {"datasets": man})
    wjson("build.json", [{"built": NOW.isoformat(timespec="minutes"), "errors": " · ".join(ERRORS),
                          "botAsOf": (st or {}).get("levgtaa", {}).get("asOf")}])
    print(json.dumps({"built": NOW.isoformat(), "errors": ERRORS, "missing": missing}, ensure_ascii=False))
    if st is None and len(ERRORS) >= 6:
        sys.exit(1)


if __name__ == "__main__":
    main()
