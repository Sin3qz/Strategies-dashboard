#!/usr/bin/env python3
"""Speichert deine Positionen aus dem Rechner (Workflow save-holdings.yml, Eingabe per Umgebungsvariable HOLDINGS).

Prueft die Eingabe streng (nur bekannte wikifolios/Produkte, Zahlen, Datum), schreibt data/wikifolio_holdings.json
und haengt jede Speicherung an data/holdings_log.csv an (Verlauf: Datum, Stueck, Kurs, Wert je Position).
"""
import csv, datetime as dt, json, math, os, sys
from zoneinfo import ZoneInfo

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
ALLOWED = {"levgtaa": {"NDX3", "BTC1", "UST3", "GOLD3", "MM", "CASH"}, "levtipsregime": {"SPX3", "BTC1", "UST3", "MM", "CASH"}}


def num(v, name, neg=False):
    if v is None or v == "":
        return None
    x = float(v)
    if not math.isfinite(x) or abs(x) > 1e9 or (x < 0 and not neg):
        raise ValueError(f"{name}: ungültige Zahl {v!r}")
    return x


def main():
    raw = os.environ.get("HOLDINGS", "")
    rows = json.loads(raw)
    assert isinstance(rows, list) and 0 < len(rows) <= 40, "Liste mit 1–40 Positionen erwartet"
    now = dt.datetime.now(ZoneInfo("Europe/Berlin"))
    saved = now.isoformat(timespec="minutes")
    try:
        prices = {p["key"]: float(p["price_eur"]) for p in json.load(open(os.path.join(OUT, "prices.json"), encoding="utf-8"))}
    except Exception:
        prices = {}
    clean, seen = [], set()
    for r in rows:
        wf, pr = str(r.get("wikifolio")), str(r.get("product"))
        assert wf in ALLOWED and pr in ALLOWED[wf], f"unbekannt: {wf}/{pr}"
        assert (wf, pr) not in seen, f"doppelt: {wf}/{pr}"
        seen.add((wf, pr))
        st = str(r.get("stand") or now.date().isoformat())[:10]
        dt.date.fromisoformat(st)
        q = num(r.get("stueck"), f"{wf}/{pr} Stück", neg=(pr == "CASH")) or 0.0
        k = 1.0 if pr == "CASH" else num(r.get("kurs_eur"), f"{wf}/{pr} Kurs")
        clean.append({"wikifolio": wf, "product": pr, "stueck": q, "kurs_eur": None if pr != "CASH" and not k else k,
                      "stand": st, "saved_at": saved})
    with open(os.path.join(OUT, "wikifolio_holdings.json"), "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=1)
    log = os.path.join(OUT, "holdings_log.csv")
    new = not os.path.exists(log)
    with open(log, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["saved_at", "stand", "wikifolio", "product", "stueck", "kurs_eur", "wert_eur"])
        for c in clean:
            px = c["kurs_eur"] if c["kurs_eur"] else prices.get(c["product"])
            w.writerow([saved, c["stand"], c["wikifolio"], c["product"], c["stueck"], c["kurs_eur"] or "",
                        round(c["stueck"] * px, 2) if px else ""])
    print(f"{len(clean)} Positionen gespeichert ({saved})")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("::error::Eingabe abgelehnt:", e)
        sys.exit(1)
