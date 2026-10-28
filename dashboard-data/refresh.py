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
        for a in d["allocation"]:
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
            out = os.path.join(OUT, f"daily_{mode}.csv"); tmp = out + ".tmp"
            subprocess.run([sys.executable, script, d, mode, tmp], check=True)
            with open(tmp, encoding="utf-8") as f:
                n = sum(1 for _ in f) - 1
            assert n > 300, f"nur {n} Zeilen"
            os.replace(tmp, out)
        except Exception as e:
            ERRORS.append(f"Tagessignal {mode}: {e}")
            traceback.print_exc()


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
    investable = bool(cert.get("isin"))
    row = {
        "key": key, "name": wf["shortDescription"], "symbol": md["symbol"]["value"], "strategy": meta["strategy"],
        "url": f"https://www.wikifolio.com/de/de/w/{meta['symbol']}",
        "trader": data["trader"]["nickName"], "created": md["creationDate"]["value"][:10],
        "perf_since_start": data["structuredData"]["performanceSinceCreation"],
        "perf_ytd": rank(perf, "Seit Jahresbeginn"),
        "max_loss": rank(risk[:1], "Maximaler Verlust"),
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
    cols = ["date", "key", "price", "perf_since_start", "max_loss", "reservations", "capital_eur", "watchlistings"]
    old = []
    if os.path.exists(HIST):
        with open(HIST, encoding="utf-8") as f:
            old = [r for r in csv.DictReader(f) if not (r["date"] == NOW.date().isoformat() and r["key"] in {x["key"] for x in fresh})]
    new = old + [{"date": NOW.date().isoformat(), **{c: r[c] for c in cols[1:]}} for r in fresh]
    new.sort(key=lambda r: (r["date"], r["key"]))
    with open(HIST, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(new)


MANIFEST = {
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


def main():
    os.makedirs(OUT, exist_ok=True); os.makedirs(WORK, exist_ok=True)
    st = step("Bot-Status", bots)
    daily()
    step("wikifolio", wikifolios)
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
