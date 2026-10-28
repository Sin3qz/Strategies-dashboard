"""Push-Hinweise (ntfy) des Dashboards — zusaetzlich zu den Handels-Pushes der Bots.

Meldet je einmal, wenn
  - das simulierte Tagessignal einer Strategie die Bausteine wechselt (levTipsRegime: Markt / 3x IEF / Cash),
  - ein wikifolio investierbar wird.
Zustand in data/notify_state.json (verhindert Doppelmeldungen bei 5 Laeufen am Tag). Ohne Secret NTFY_TOPIC wird nur
der Zustand gefuehrt, nichts gesendet. Der erste Lauf meldet nichts, er merkt sich nur den Stand.
"""
import csv, json, os

from send_ntfy import send_ntfy

URL = "https://sin3qz.github.io/Strategies-dashboard/#signale"
NAMES = {"NASDAQ100": "Nasdaq", "BTC": "Bitcoin", "UST_IEF": "UST 7-10y", "GOLD": "Gold", "EM": "EM", "INDIA": "India",
         "TLT_LONG": "UST 20y+", "EM_SMALLCAP": "EM Small", "EMU_VALUE": "EMU Value", "BONDS_7_10": "UST 7-10y",
         "COMMODITIES": "Rohstoffe", "CASH_USD": "Geldmarkt"}
LABEL = {"levgtaa": "levGTAA", "mrrebound": "MR-Rebound-GTAA", "1xgtaa": "1xGTAA", "levtips": "levTipsRegime"}
SKIP = {"date", "cash", "vt_factor", "platz1", "held", "cooldown"}
TIPS_TEXT = {"MARKET": "Markt (100 % 3x S&P 500)", "IEF": "3x IEF (US-Treasury 7-10y)", "CASH": "Cash"}


def _last(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))[-1]


def _signal(mode, row):
    """-> (Schluessel fuer den Vergleich, lesbarer Text)"""
    if mode == "levtips":
        st = row.get("state") or ("MARKET" if row.get("market") == "1" else "CASH")
        return st, TIPS_TEXT.get(st, st)
    w = sorted(((k, float(v)) for k, v in row.items() if k not in SKIP and v not in ("", None) and float(v) > 0.0005),
               key=lambda x: -x[1])
    key = "|".join(sorted(k for k, _ in w)) or "CASH"
    txt = " · ".join(f"{x * 100:.1f} % {NAMES.get(k, k)}".replace(".", ",") for k, x in w) or "100 % Cash"
    return key, txt


def run(out_dir):
    path = os.path.join(out_dir, "notify_state.json")
    try:
        state = json.load(open(path, encoding="utf-8"))
    except Exception:
        state = {}
    first = not state
    sent, msgs = [], []
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
    if not first:
        for title, body in msgs:
            ok = send_ntfy(title, body + "\n\n" + URL, tags="chart_with_upwards_trend")
            sent.append((title, ok))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    return sent
