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
                    bt_label="Backtest 1993+ laut Bot-Repo (Anleihe-Baustein 3x IEF, Signal TLT)"),
    "levtipsregime": dict(symbol="wfxtipsreg", strategy="levTipsRegime", bt_cagr=0.361, bt_maxdd=-0.49, bt_sortino=1.13,
                          bt_label="Backtest 10/2004+ (studien/STUDIE.md: 100 % 3x S&P 500, 3x IEF bei TIPS < SMA220 und TLT > SMA200, synthetisch)"),
}
TZ = ZoneInfo("Europe/Berlin")
NOW = dt.datetime.now(TZ)


# ---------------------------------------------------------------------------
# Rückfallebenen beim Abruf
#  1. jede Anfrage bis zu 3 Versuche mit Wartezeit (5 s, 20 s)
#  2. Bot-Dateien: raw.githubusercontent.com -> GitHub-API -> jsDelivr-Spiegel; Bot-Code: git clone -> Tarball
#  3. fällt eine Quelle trotzdem aus, bleibt ihr letzter gültiger Stand (je Bot, je Tagessignal, je wikifolio)
#  4. zweiter Durchgang für alle ausgefallenen Quellen nach RETRY_WAIT Sekunden (in der Action 150 s)
#  5. nächster planmäßiger Lauf (stündlich); nach 3 gestörten Läufen in Folge ein ntfy-Push
# Jede Quelle landet mit Status, Grund, Weg und letztem Erfolg in data/health.json (Anzeige „Datenstatus“ auf der Seite).
# ---------------------------------------------------------------------------
HEALTH = {}                     # Quelle -> Eintrag für health.json
WAITS = (5, 20)


def reason(e):
    """Fehler in einen kurzen, verständlichen Grund übersetzen."""
    import urllib.error, socket
    if isinstance(e, urllib.error.HTTPError):
        return {404: "Datei nicht gefunden (HTTP 404)", 403: "Zugriff verweigert / Limit (HTTP 403)",
                429: "zu viele Anfragen (HTTP 429)"}.get(e.code, f"Server-Fehler HTTP {e.code}")
    if isinstance(e, (socket.timeout, TimeoutError)) or "timed out" in str(e):
        return "Zeitüberschreitung beim Abruf"
    if isinstance(e, urllib.error.URLError):
        return f"Netzwerkfehler ({e.reason})"
    if isinstance(e, subprocess.CalledProcessError):
        return f"Rechnung abgebrochen (Exit {e.returncode})"
    if isinstance(e, json.JSONDecodeError):
        return "Antwort ist kein gültiges JSON"
    if isinstance(e, (AssertionError, KeyError, ValueError, TypeError)):
        return f"Daten unvollständig/unplausibel: {e}"
    return f"{type(e).__name__}: {e}"


def attempt(fn, tries=3, label=""):
    """fn() bis zu tries-mal; gibt (Ergebnis, Versuche) zurück oder wirft den letzten Fehler (mit .tries)."""
    import time
    for k in range(tries):
        try:
            return fn(), k + 1
        except Exception as e:
            last = e
            print(f"{label}: Versuch {k + 1}/{tries} fehlgeschlagen: {reason(e)}")
            if k < tries - 1:
                time.sleep(WAITS[min(k, len(WAITS) - 1)])
    last.tries = tries
    raise last


def get(url, tries=3, headers=None):
    def once():
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache", **(headers or {})})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode("utf-8")
    return attempt(once, tries, url)[0]


def raw(repo, path, check=None):
    """Datei aus einem Bot-Repo (main): raw -> GitHub-API -> jsDelivr. Gibt (Text, Weg, Versuche) zurück."""
    cb = int(NOW.timestamp())                           # gegen den 5-Minuten-Zwischenspeicher von raw.githubusercontent.com
    ways = [("raw.githubusercontent.com", f"https://raw.githubusercontent.com/{USER}/{repo}/main/{path}?cb={cb}", None),
            ("GitHub-API (Ersatzweg)", f"https://api.github.com/repos/{USER}/{repo}/contents/{path}?ref=main",
             {"Accept": "application/vnd.github.raw"}),
            ("jsDelivr-Spiegel (Ersatzweg, bis 12 h verzögert)", f"https://cdn.jsdelivr.net/gh/{USER}/{repo}@main/{path}", None)]
    errs, n = [], 0
    for name, url, hd in ways:
        try:
            txt = get(url, tries=2 if n == 0 else 1, headers=hd)
            n += 1
            if check:
                check(txt)
            return txt, name, n
        except Exception as e:
            n += getattr(e, "tries", 1)
            errs.append(f"{name}: {reason(e)}")
    raise RuntimeError(" | ".join(errs))


def clone(repo):
    local = os.environ.get("BOT_REPO_DIR")              # lokal: vorhandene Checkouts statt frischem Klon (Tests)
    if local and os.path.isdir(os.path.join(local, repo)):
        return os.path.join(local, repo), "lokal"
    d = os.path.join(WORK, repo)

    def git():
        if os.path.isdir(os.path.join(d, ".git")):
            subprocess.run(["git", "-C", d, "fetch", "-q", "--depth", "1", "origin", "main"], check=True)
            subprocess.run(["git", "-C", d, "reset", "-q", "--hard", "origin/main"], check=True)
        else:
            shutil.rmtree(d, ignore_errors=True)
            subprocess.run(["git", "clone", "-q", "--depth", "1", f"https://github.com/{USER}/{repo}.git", d], check=True)
    try:
        attempt(git, 2, f"git clone {repo}")
        return d, "git"
    except Exception:                                   # Ersatzweg: Tarball von codeload.github.com
        import io, tarfile
        def tar():
            req = urllib.request.Request(f"https://codeload.github.com/{USER}/{repo}/tar.gz/refs/heads/main",
                                         headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as t:
                for m in t.getmembers():
                    m.name = m.name.split("/", 1)[1] if "/" in m.name else ""
                    if m.name and not m.name.startswith(("/", "..")) and ".." not in m.name.split("/"):
                        t.extract(m, d)
        attempt(tar, 2, f"Tarball {repo}")
        return d, "Tarball (Ersatzweg)"


def load_prev(name, default):
    try:
        with open(os.path.join(OUT, name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


PREV_HEALTH = {}                # letzter Stand aus data/health.json (für „letzter Erfolg“)


def mark(sid, name, group, status, detail="", via="", tries=1, data_asof=None):
    prev = PREV_HEALTH.get(sid, {})
    ok = status in ("ok", "retry_ok", "warn")
    HEALTH[sid] = {"id": sid, "name": name, "group": group, "status": status, "detail": detail, "via": via,
                   "tries": tries, "data_asof": data_asof or (None if ok else prev.get("data_asof")),
                   "last_ok": NOW.isoformat(timespec="minutes") if ok else prev.get("last_ok"),
                   "since": prev.get("since") if (not ok and prev.get("status") not in ("ok", "retry_ok", "warn", None)) else
                   (None if ok else NOW.isoformat(timespec="minutes"))}
    if not ok:
        ERRORS.append(f"{name}: {detail}")


def wjson(name, obj):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


# ---------------------------------------------------------------------------
def bot_row(key, d):
    row = {"key": key, "updated": d.get("updated"), "asOf": d.get("asOf"), "rebalance": d.get("rebalance"),
           "decisionDate": d.get("decisionDate"), "tradeDate": d.get("tradeDate"), "nextDecision": d.get("nextDecision"),
           "nextRebalance": d.get("nextRebalance"), "cooldown": d.get("cooldown"), "changeType": d.get("changeType"),
           "pendingDecision": d.get("pendingDecision"), "pendingTrade": d.get("pendingTrade"), "late": bool(d.get("late")),
           "needsRetry": bool(d.get("needsRetry")), "refreshLater": bool(d.get("refreshLater")), "warnings": " · ".join(d.get("dataWarnings") or []),
           # levGTAA: Bitcoin-Tagesschluss der Entscheidung (juengster vor dem Handel), Zieltag und ob endgueltig
           "btcDate": d.get("btcDate"), "btcTarget": d.get("btcTarget"), "btcFinal": d.get("btcFinal"),
           "weightDecimals": d.get("weightDecimals") or 0, "since": d.get("since"),
           "vola_cap": None, "vola_factor": None, "vola_decision": None, "vola_now": None, "vola_pre": None, "vola_windows": None,
           "note": (d.get("table") or {}).get("note"), "tl_span": (d.get("timeline") or {}).get("span"),
           "tl_what": (d.get("timeline") or {}).get("what")}
    v = d.get("vola")
    if v:
        row.update(vola_cap=v["cap"], vola_factor=v["factor"], vola_decision=v["decisionDate"],
                   vola_now=v["holdingNowMean"], vola_pre=v["signalPreMean"], vola_windows="/".join(map(str, v["windows"])))
    al = d["allocation"]
    if key == "levtipsregime" and any(a.get("weight") is None for a in al):     # alter Bot-Stand (Gewichtung frei): 100 % 3x S&P 500
        al = [dict(a, weight=1.0) for a in al if a["asset"] == "SP500"] or al
    alloc = [{"strategy": key, "asset": a["asset"], "display": a["display"], "weight": a["weight"],
              "leverage": a["leverage"], "product": a["product"], "isin": a["isin"]} for a in al]
    sig = [{"strategy": key, **dict(zip(SIG_COLS[key], r))} for r in d["table"]["rows"]]
    tl = [{"strategy": key, "date": t.get("date"), "lead": t.get("lead"), "allocation": t.get("allocation")}
          for t in (d.get("timeline") or {}).get("items") or []]
    return row, alloc, sig, tl


def check_status(txt):
    d = json.loads(txt)
    assert d.get("asOf") and d.get("allocation") is not None and d.get("table", {}).get("rows"), "Pflichtfelder fehlen"


NAMES = {"levgtaa": "levGTAA", "levtipsregime": "levTipsRegime", "mrreboundgtaa": "MR-Rebound-GTAA", "1xgtaa": "1xGTAA"}


def bots(only=None):
    """Bot-Status je Strategie. Fällt ein Bot aus, bleibt nur für ihn der letzte Stand (die anderen werden aktualisiert)."""
    prev = {"strategies.json": load_prev("strategies.json", []), "allocations.json": load_prev("allocations.json", []),
            "signals.json": load_prev("signals.json", []), "timeline.json": load_prev("timeline.json", [])}
    out = {"strategies": [], "alloc": [], "signals": [], "timeline": []}
    for key, (repo, fn) in REPOS.items():
        sid = f"bot_{key}"
        if only is not None and sid not in only:            # zweiter Durchgang: erfolgreiche Bots unverändert übernehmen
            res = None
        else:
            try:
                txt, via, n = raw(repo, fn, check_status)
                d = json.loads(txt)
                res = bot_row(key, d)
                age_h = (NOW - dt.datetime.fromisoformat(d["updated"]).astimezone(TZ)).total_seconds() / 3600 if d.get("updated") else 0
                if d.get("needsRetry"):
                    mark(sid, f"Bot {NAMES[key]}", "Bots", "warn", "Bot meldet veraltete Yahoo-Kurse und wiederholt selbst "
                         "(Sicherheitslauf 11:47 UTC); angezeigt wird sein letzter Stand", via, n, d.get("asOf"))
                elif age_h > 30:
                    mark(sid, f"Bot {NAMES[key]}", "Bots", "warn", f"Bot-Datei seit {age_h:.0f} h nicht erneuert (Bot-Lauf ausgefallen?)",
                         via, n, d.get("asOf"))
                else:
                    mark(sid, f"Bot {NAMES[key]}", "Bots", "ok" if (n == 1 and via.startswith("raw")) else "retry_ok",
                         "" if n == 1 else f"geladen nach {n} Versuchen", via, n, d.get("asOf"))
                if key == "levgtaa":
                    try:
                        hist, _, _ = raw(repo, "history_levgtaa.txt", lambda t: None if t.count("\n") > 50 else 1 / 0)
                        with open(os.path.join(OUT, "levgtaa_history.csv"), "w", encoding="utf-8") as f:
                            f.write(hist)
                    except Exception as e:
                        print("history_levgtaa.txt nicht geladen, alter Stand bleibt:", e)
            except Exception as e:
                res = None
                old = next((r for r in prev["strategies.json"] if r.get("key") == key), None)
                mark(sid, f"Bot {NAMES[key]}", "Bots", "fallback" if old else "error",
                     f"{e} → letzter gültiger Stand bleibt", "", getattr(e, "tries", 3), (old or {}).get("asOf"))
        if res is None:                                     # letzter Stand dieses Bots
            out["strategies"] += [r for r in prev["strategies.json"] if r.get("key") == key]
            out["alloc"] += [r for r in prev["allocations.json"] if r.get("strategy") == key]
            out["signals"] += [r for r in prev["signals.json"] if r.get("strategy") == key]
            out["timeline"] += [r for r in prev["timeline.json"] if r.get("strategy") == key]
        else:
            row, al, sg, tl = res
            out["strategies"].append(row); out["alloc"] += al; out["signals"] += sg; out["timeline"] += tl
    if not out["strategies"]:
        raise RuntimeError("kein Bot-Status ladbar und kein alter Stand vorhanden")
    order = list(REPOS)
    out["strategies"].sort(key=lambda r: order.index(r["key"]))
    wjson("strategies.json", out["strategies"])
    wjson("allocations.json", out["alloc"])
    wjson("signals.json", out["signals"])
    wjson("timeline.json", out["timeline"])
    return {r["key"]: r for r in out["strategies"]}


DAILY = (("levgtaa-signalbot", "levgtaa", "levGTAA"), ("mrreboundgtaa-signalbot", "mrrebound", "MR-Rebound-GTAA"),
         ("1xgtaa-signalbot", "1xgtaa", "1xGTAA"), ("levtipsregime-signalbot", "levtips", "levTipsRegime"))


EX_KEY = {"levgtaa": "levgtaa", "mrrebound": "mrreboundgtaa", "1xgtaa": "1xgtaa", "levtips": "levtipsregime"}


def daily(only=None):
    script = os.path.join(HERE, "daily_signals.py")
    prev = {r.get("key"): r for r in load_prev("explain.json", []) if isinstance(r, dict)}
    explain = dict(prev)                                   # Herleitung je Strategie; bei Fehler bleibt die letzte
    for repo, mode, name in DAILY:
        sid = f"daily_{mode}"
        if only is not None and sid not in only:
            continue
        try:
            d, via = clone(repo)
            tmp = os.path.join(WORK, f"daily_{mode}.csv")

            def run():
                subprocess.run([sys.executable, script, d, mode, tmp], check=True, timeout=900)
                with open(tmp, encoding="utf-8") as f:
                    rows = list(csv.DictReader(f))
                with open(tmp[:-4] + "_decisions.csv", encoding="utf-8") as f:
                    nd = sum(1 for _ in f) - 1
                assert len(rows) > 300 and nd > 100, f"nur {len(rows)} Tage / {nd} Entscheidungen"
                return rows[-1]["date"]
            last, n = attempt(run, 2, f"Tagessignal {mode}")
            shutil.copyfile(tmp, os.path.join(OUT, f"daily_{mode}.csv"))
            shutil.copyfile(tmp[:-4] + "_decisions.csv", os.path.join(WORK, f"decisions_{mode}.csv"))
            try:
                with open(tmp[:-4] + "_explain.json", encoding="utf-8") as f:
                    explain[EX_KEY[mode]] = {"key": EX_KEY[mode], **json.load(f)}
            except Exception as e:
                print("Herleitung", mode, "fehlt:", e)
            mark(sid, f"Tagessignal {name}", "Tagessignal (Yahoo + Bot-Code)", "ok" if n == 1 and via in ("git", "lokal") else "retry_ok",
                 "" if n == 1 else f"gerechnet im {n}. Versuch", f"Bot-Code per {via}", n, last)
        except Exception as e:
            traceback.print_exc()
            f = os.path.join(OUT, f"daily_{mode}.csv")
            last = None
            if os.path.exists(f):
                with open(f, encoding="utf-8") as fh:
                    last = (list(csv.DictReader(fh)) or [{}])[-1].get("date")
            mark(sid, f"Tagessignal {name}", "Tagessignal (Yahoo + Bot-Code)", "fallback" if last else "error",
                 f"{reason(e)} → letzter gültiger Verlauf bleibt", "", getattr(e, "tries", 2), last)

    wjson("explain.json", [explain[k] for k in ("levgtaa", "levtipsregime", "1xgtaa", "mrreboundgtaa") if k in explain])


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
    h = get(f"https://www.wikifolio.com/de/de/w/{meta['symbol']}", tries=2)
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


def wikifolios(only=None):
    prev = {}
    try:
        with open(os.path.join(OUT, "wikifolios.json"), encoding="utf-8") as f:
            prev = {r["key"]: r for r in json.load(f)}
    except Exception:
        pass
    rows, fresh = [], []
    for k, m in WIKIFOLIOS.items():
        sid, nm = f"wf_{k}", f"wikifolio {m['symbol'].upper()}"
        if only is not None and sid not in only:
            if k in prev:
                rows.append(prev[k])
            continue
        try:
            r, n = attempt(lambda: wikifolio(k, m), 2, nm)
            rows.append(r); fresh.append(r)
            mark(sid, nm, "wikifolio.com", "ok" if n == 1 else "retry_ok", "" if n == 1 else f"geladen im {n}. Versuch",
                 "Seitendaten wikifolio.com", n, r["asOf"])
        except Exception as e:                      # letzter gueltiger Stand bleibt (asOf zeigt sein Alter)
            mark(sid, nm, "wikifolio.com", "fallback" if k in prev else "error",
                 f"{reason(e)} → letzter Stand bleibt", "", getattr(e, "tries", 2), (prev.get(k) or {}).get("asOf"))
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
    "timeline": ("timeline.json", "Zeitbalken der Bots", "Gehaltene Position der letzten 120 Handelstage bzw. Monatsentscheidungen je Strategie (timeline aus status_*.json)."),
    "holdings_log": ("holdings_log.csv", "Gespeicherte Positionen (Verlauf)", "Jede Speicherung aus dem Rechner: Zeitpunkt, Stand, wikifolio, Produkt, Stück, Kurs und Wert in EUR (save_holdings.py)."),
    "cash_watch": ("cash_watch.json", "Cash-Wächter", "Geschätztes Cash je wikifolio nach Gebühren seit dem letzten Handel bzw. deiner Eingabe, Reserve für 2 Handelstage, Auffüll-Vorschlag (cashwatch.py)."),
    "health": ("health.json", "Datenstatus", "Status jeder Datenquelle des letzten Laufs: ok, mit Wiederholung geladen, Warnung, letzter Stand (Rückfallebene) oder Fehler, mit Grund, Weg und letztem Erfolg."),
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
    "explain": ("explain.json", "Herleitung der Signale",
                "Je Strategie alle Zwischenwerte (Renditen, Momentum, Trend, Ranglisten, Plätze, Vol-Target bzw. Abstände und Regeln) für das heute simulierte Signal und die Entscheidung der gehaltenen Position; gerechnet mit dem Code der Bot-Repos."),
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
    {"wikifolio": "levgtaa", "product": p, "stueck": 0, "kurs_eur": None, "stand": None} for p in ("NDX3", "BTC1", "BTCW", "UST3", "GOLD3", "MM")
] + [{"wikifolio": "levtipsregime", "product": p, "stueck": 0, "kurs_eur": None, "stand": None} for p in ("SPX3", "BTC1", "UST3", "MM")
] + [{"wikifolio": w, "product": "CASH", "stueck": 0, "kurs_eur": 1, "stand": None} for w in ("levgtaa", "levtipsregime")]


def holdings():
    path = os.path.join(OUT, "wikifolio_holdings.json")
    if not os.path.exists(path):
        wjson("wikifolio_holdings.json", HOLDINGS_TEMPLATE)


def kick_status():
    """Ergebnis des Zeitgebers (kick_bots.py) in den Datenstatus übernehmen."""
    f = os.environ.get("KICK_FILE")
    if not f or not os.path.exists(f):
        return
    rows = json.load(open(f, encoding="utf-8"))
    kicked = [r for r in rows if r.get("action") == "kicked"]
    miss = [r for r in rows if r.get("action") == "missing_token"]
    err = [r for r in rows if r.get("action") == "error"]
    parts = [f"{r['name']}: {r['detail']}" for r in kicked + miss + err]
    status = "warn" if (miss or err) else "ok"
    detail = " · ".join(parts) if parts else "alle Bots heute schon gelaufen bzw. noch nicht fällig"
    HEALTH["kick"] = {"id": "kick", "name": "Zeitgeber (Bots anstoßen)", "group": "Bots", "status": status, "detail": detail,
                      "via": "GitHub-API workflow_dispatch", "tries": 1, "data_asof": NOW.date().isoformat(),
                      "last_ok": NOW.isoformat(timespec="minutes"), "since": None}


def push_status(sent):
    """Zeile „Push (ntfy)“ im Datenstatus: Topic gesetzt? letzte Sendung ok?"""
    import send_ntfy as N
    url, topic, err = N._target()
    prev = PREV_HEALTH.get("push", {})
    if not topic and not err:
        st, det = "warn", "Secret NTFY_TOPIC fehlt im Repo Strategies-dashboard – Hinweise werden nicht gesendet"
    elif err:
        st, det = "warn", err
    elif any(ok is False for _, ok in sent):
        st, det = "warn", "Senden fehlgeschlagen: " + (N.LAST_ERROR or "unbekannter Fehler") + " (nächster Lauf wiederholt)"
    elif sent:
        st, det = "ok", "gesendet: " + ", ".join(t for t, _ in sent)
    else:
        st, det = "ok", "Topic gesetzt; nichts zu melden" + (f" (zuletzt: {prev.get('last_sent')})" if prev.get("last_sent") else "")
    HEALTH["push"] = {"id": "push", "name": "Push (ntfy)", "group": "Hinweise", "status": st, "detail": det, "via": "ntfy.sh",
                      "tries": 1, "data_asof": NOW.date().isoformat(), "last_ok": NOW.isoformat(timespec="minutes"), "since": None,
                      "last_sent": (", ".join(t for t, ok in sent if ok) + NOW.strftime(" am %d.%m. %H:%M")) if any(ok for _, ok in sent)
                      else prev.get("last_sent")}


def performance(equity):
    try:
        issues, n = attempt(lambda: equity.run(WORK, OUT), 2, "Performance")
        for x in issues or []:
            print("Hinweis Kursdaten:", x)
        mark("perf", "Performance (Produktkurse Yahoo)", "Performance", "ok" if n == 1 else "retry_ok",
             "; ".join(issues or []) or ("" if n == 1 else f"gerechnet im {n}. Versuch"), "Yahoo (yahooquery)", n,
             NOW.date().isoformat())
    except Exception as e:
        traceback.print_exc()
        old = load_prev("perf_stats.json", [])
        mark("perf", "Performance (Produktkurse Yahoo)", "Performance", "fallback" if old else "error",
             f"{reason(e)} → letzte gültige Kennzahlen und Kurven bleiben", "", getattr(e, "tries", 2),
             (old[0].get("end") if old else None))


BAD = ("fallback", "error")


def alert(health, streak, alerted):
    """ntfy, wenn die Aktualisierung 3 Läufe in Folge gestört ist, und einmal, wenn sie sich erholt hat."""
    try:
        from send_ntfy import send_ntfy
    except Exception:
        return alerted
    bad = [h for h in health if h["status"] in BAD]
    if bad and streak >= 3 and not alerted:
        body = "\n".join(f"• {h['name']}: {h['detail']}" for h in bad[:6])
        ok = send_ntfy("Dashboard: Aktualisierung gestoert", f"Seit {streak} Läufen gestört (alte Stände werden angezeigt):\n{body}"
                       "\n\nhttps://sin3qz.github.io/Strategies-dashboard/", tags="warning")
        return bool(ok)
    if not bad and alerted:
        send_ntfy("Dashboard: wieder aktuell", "Alle Quellen wurden wieder geladen.\n\nhttps://sin3qz.github.io/Strategies-dashboard/",
                  tags="white_check_mark")
        return False
    return alerted


def us_closes():
    """Letzter abgeschlossener und naechster NYSE-Handelstag (Bezug fuer „aktuell“ auf der Seite)."""
    c = calendars()
    return c.get("last_close"), c.get("next_close")


def calendars():
    """Handelskalender fuer die Seite: NYSE-Sitzungen (+-30 Tage; Signale beruhen auf US-Schlusskursen) und Tage, an
    denen deutsche Boersen (Xetra-Kalender) an Werktagen geschlossen sind, mit dem naechsten Boersentag (gehandelt wird im
    wikifolio)."""
    try:
        import pandas as pd, pandas_market_calendars as mcal
        now = pd.Timestamp.now(tz="UTC")
        sch = mcal.get_calendar("XNYS").schedule(start_date=(now - pd.Timedelta(days=30)).date(), end_date=(now + pd.Timedelta(days=30)).date())
        done, nxt = sch[sch["market_close"] <= now], sch[sch["market_close"] > now]
        de = mcal.get_calendar("XETR").schedule(start_date=now.date(), end_date=(now + pd.Timedelta(days=100)).date())
        de_days = {d.date() for d in de.index}
        closed = []
        for d in pd.bdate_range(now.date(), (now + pd.Timedelta(days=90)).date()):
            if d.date() not in de_days:
                after = [x for x in sorted(de_days) if x > d.date()]
                closed.append({"date": d.date().isoformat(), "next": after[0].isoformat() if after else None})
        # Massstab fuer „aktuell“ wie in den Bots (common.expected_session_date): letzte Sitzung bis gestern (Berlin) –
        # die Bots rechnen den Schluss eines Tages planmaessig am naechsten Morgen
        yday = (now.tz_convert("Europe/Berlin") - pd.Timedelta(days=1)).date()
        exp = [d.date() for d in sch.index if d.date() <= yday]
        return {"last_close": done.index[-1].date().isoformat() if len(done) else None,
                "expected_close": exp[-1].isoformat() if exp else None,
                "next_close": nxt.index[0].date().isoformat() if len(nxt) else None,
                "nyse_sessions": " ".join(d.date().isoformat() for d in sch.index),
                "de_closed": " ".join(f"{c['date']}>{c['next']}" for c in closed)}
    except Exception as e:
        print("Handelskalender nicht verfügbar:", e)
        return {}


def main():
    import time
    os.makedirs(OUT, exist_ok=True); os.makedirs(WORK, exist_ok=True)
    rows = load_prev("health.json", [])
    rows = rows if isinstance(rows, list) else []
    prev = next((r for r in rows if r.get("kind") == "run"), {})
    PREV_HEALTH.update({h["id"]: h for h in rows if h.get("kind") == "source"})
    sys.path.insert(0, HERE)
    import equity, notify

    def run_all(only=None):
        st = None
        try:
            st = bots(only)
        except Exception as e:
            traceback.print_exc(); ERRORS.append(f"Bot-Status: {reason(e)}")
        daily(only)
        step("TLT-Zeile", tlt_row)
        try:
            wikifolios(only)
        except Exception as e:
            traceback.print_exc(); ERRORS.append(f"wikifolio: {reason(e)}")
        if only is None or "perf" in only or any(x.startswith("daily_") for x in only):
            performance(equity)
        return st

    kick_status()
    st = run_all()
    passes = 1
    failed = {k for k, h in HEALTH.items() if h["status"] in BAD}
    wait = int(os.environ.get("RETRY_WAIT", "0"))
    if failed and wait > 0:                             # Rückfallebene 4: zweiter Durchgang nur für die ausgefallenen Quellen
        print(f"Zweiter Durchgang in {wait} s für: {', '.join(sorted(failed))}")
        time.sleep(wait)
        for k in failed:
            HEALTH.pop(k, None)
        del ERRORS[:]
        st = run_all(failed) or st
        passes = 2
        for k in failed:
            if k in HEALTH and HEALTH[k]["status"] not in BAD:
                HEALTH[k]["detail"] = ("erst im zweiten Durchgang geladen" + (f"; {HEALTH[k]['detail']}" if HEALTH[k]["detail"] else ""))
                HEALTH[k]["status"] = "retry_ok" if HEALTH[k]["status"] == "ok" else HEALTH[k]["status"]
        ERRORS[:] = [f"{h['name']}: {h['detail']}" for h in HEALTH.values() if h["status"] in BAD]
    holdings()
    try:
        sent = notify.run(OUT) or []
        for t, ok in sent:
            print("Push:", t, "->", ok)
        push_status(sent)
    except Exception as e:
        traceback.print_exc(); print("Push-Hinweise nicht geprüft:", reason(e))

    order = ["kick"] + [f"bot_{k}" for k in REPOS] + [f"daily_{m}" for _, m, _ in DAILY] + [f"wf_{k}" for k in WIKIFOLIOS] + ["perf", "push"]
    health = sorted(HEALTH.values(), key=lambda h: order.index(h["id"]) if h["id"] in order else 99)
    worst = "error" if any(h["status"] == "error" for h in health) else "fallback" if any(h["status"] == "fallback" for h in health) \
        else "warn" if any(h["status"] == "warn" for h in health) else "retry_ok" if any(h["status"] == "retry_ok" for h in health) else "ok"
    streak = (prev.get("streak", 0) + 1) if worst in BAD else 0
    alerted = alert(health, streak, prev.get("alerted", False))
    run_url = (f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
               if os.environ.get("GITHUB_RUN_ID") else None)
    # Tabelle: erste Zeile = Lauf, danach je Quelle eine Zeile (gleiche Form wie die übrigen Datensätze)
    wjson("health.json", [{"kind": "run", "id": "run", "built": NOW.isoformat(timespec="minutes"), "overall": worst, "passes": passes,
                           "streak": streak, "alerted": alerted, "run_url": run_url}] + [{"kind": "source", **h} for h in health])
    man = {k: {"file": f, "title": t, "description": d} for k, (f, t, d) in MANIFEST.items()}
    missing = [k for k, m in man.items() if not os.path.exists(os.path.join(OUT, m["file"]))]
    wjson("manifest.json", {"datasets": man})
    cal = calendars()
    wjson("build.json", [{"built": NOW.isoformat(timespec="minutes"), "errors": " · ".join(ERRORS),
                          "botAsOf": (st or {}).get("levgtaa", {}).get("asOf"), **cal}])
    print(json.dumps({"built": NOW.isoformat(), "overall": worst, "passes": passes, "errors": ERRORS, "missing": missing},
                     ensure_ascii=False))
    if not any(h["status"] not in BAD for h in health):
        sys.exit(1)                                     # gar nichts geladen -> Action schlägt fehl (E-Mail von GitHub)


if __name__ == "__main__":
    main()
