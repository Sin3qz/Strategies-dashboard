"""Push-Hinweise (ntfy) des Dashboards — zusaetzlich zu den Handels-Pushes der Bots.

Meldet je einmal, wenn
  - das simulierte Tagessignal einer Strategie die Bausteine wechselt (levTipsRegime: Markt / 3x IEF / Cash),
  - ein wikifolio investierbar wird,
  - das wikifolio-Cash bald nicht mehr fuer die Gebuehren reicht (cashwatch.py, 2 Handelstage Vorlauf).
Mit NTFY_TEST=true (Schalter beim „Run workflow“) geht zusaetzlich eine Test-Nachricht raus.
Zustand in data/notify_state.json (verhindert Doppelmeldungen bei 5 Laeufen am Tag). Ohne Secret NTFY_TOPIC wird nur
der Zustand gefuehrt, nichts gesendet. Der erste Lauf meldet nichts, er merkt sich nur den Stand.
"""
import csv, datetime as dt, json, os
from zoneinfo import ZoneInfo

import cashwatch
from send_ntfy import send_ntfy

URL = "https://sin3qz.github.io/Strategies-dashboard/#signale"
NAMES = {"NASDAQ100": "Nasdaq", "BTC": "Bitcoin", "UST_IEF": "UST 7-10y", "GOLD": "Gold", "EM": "EM", "INDIA": "India",
         "TLT_LONG": "UST 7-10y", "EM_SMALLCAP": "EM Small", "EMU_VALUE": "EMU Value", "BONDS_7_10": "UST 7-10y",
         "COMMODITIES": "Rohstoffe", "CASH_USD": "Geldmarkt"}
LABEL = {"levgtaa": "levGTAA", "mrrebound": "MR-Rebound-GTAA", "1xgtaa": "1xGTAA", "levtips": "levTipsRegime"}
QUIET = (22, 7)        # Nachtruhe (Berlin): keine Hinweise von 22 bis 7 Uhr, sie kommen mit dem ersten Lauf danach
SKIP = {"date", "cash", "vt_factor", "platz1", "held", "cooldown", "btc_date", "btc_final"}


def _num(v):
    """Quote als Zahl; Text (z. B. ein Datum in einer neuen Spalte) -> None statt Abbruch des ganzen Laufs."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
TIPS_TEXT = {"MARKET": "Markt (100 % 3x S&P 500)", "IEF": "3x IEF (US-Treasury 7-10y)", "CASH": "Cash"}


def _last(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))[-1]


def _signal(mode, row):
    """-> (Schluessel fuer den Vergleich, lesbarer Text)"""
    if mode == "levtips":
        st = row.get("state") or ("MARKET" if row.get("market") == "1" else "CASH")
        return st, TIPS_TEXT.get(st, st)
    w = sorted(((k, _num(v)) for k, v in row.items() if k not in SKIP and (_num(v) or 0) > 0.0005), key=lambda x: -x[1])
    key = "|".join(sorted(k for k, _ in w)) or "CASH"
    txt = " · ".join(f"{x * 100:.1f} % {NAMES.get(k, k)}".replace(".", ",") for k, x in w) or "100 % Cash"
    return key, txt


def run(out_dir, now=None):
    path = os.path.join(out_dir, "notify_state.json")
    try:
        state = json.load(open(path, encoding="utf-8"))
    except Exception:
        state = {}
    first = not state
    sent, msgs = [], []
    h = (now or dt.datetime.now(ZoneInfo("Europe/Berlin"))).hour
    quiet = h >= QUIET[0] or h < QUIET[1]
    keep = dict(state)                                    # Nachtruhe: Zustand nicht weiterschreiben, damit nichts verloren geht
    for mode in LABEL:
        f = os.path.join(out_dir, f"daily_{mode}.csv")
        if not os.path.exists(f):
            continue
        row = _last(f)
        key, txt = _signal(mode, row)
        old = state.get(mode)
        if old and old.get("key") != key and old.get("date") != row["date"]:
            msgs.append((f"{LABEL[mode]}: Tagessignal gekippt",
                         f"Simuliertes Signal (Schluss {row['date']}):\n{old.get('text')} -> {txt}\n\n"
                         f"Das ist das Signal, WENN heute gehandelt wuerde; der Bot selbst handelt nach seinem Zeitplan."))
        state[mode] = {"key": key, "text": txt, "date": row["date"]}
    try:
        wfs = json.load(open(os.path.join(out_dir, "wikifolios.json"), encoding="utf-8"))
    except Exception:
        wfs = []
    for w in wfs:
        k = "wf_" + w["key"]
        if state.get(k) and state[k] != w["status"] and w["status"] == "Investierbar":
            msgs.append((f"wikifolio {w['name']} ist investierbar", f"{w['name']} ({w['symbol']}) ist jetzt investierbar.\n{w['url']}"))
        state[k] = w["status"]
    if quiet and not first:
        if msgs:
            print(f"Nachtruhe ({h} Uhr): {len(msgs)} Hinweis(e) kommen mit dem ersten Lauf ab {QUIET[1]} Uhr")
        state = keep
    elif not first:
        for title, body in msgs:
            ok = send_ntfy(title, body + "\n\n" + URL, tags="chart_with_upwards_trend")
            sent.append((title, ok))
    try:
        # nachts: cash_watch.json aktualisieren, aber nicht melden und den Meldezustand nicht weiterschreiben
        sent += cashwatch.run(out_dir, dict(state) if quiet else state, send=None if quiet else send_ntfy)
    except Exception as e:
        print("Cash-Waechter nicht gelaufen:", e)
    if (os.environ.get("NTFY_TEST") or "").lower() == "true":
        ok = send_ntfy("Dashboard: Test-Nachricht", "ntfy funktioniert – so sehen die Hinweise des Dashboards aus.\n\n" + URL,
                       tags="white_check_mark")
        sent.append(("Test-Nachricht", ok))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    return sent
