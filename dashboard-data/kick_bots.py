#!/usr/bin/env python3
"""Zeitgeber für die Bots: stößt jeden Bot an, der heute noch nicht erfolgreich gelaufen ist.

GitHub startet geplante Läufe (cron) teils Stunden später oder lässt sie aus (Oktober 2026: 05:17 UTC -> 10:40-11:25 UTC).
Diese Datei läuft zu Beginn jeder Dashboard-Aktualisierung. Wird die Aktualisierung von außen pünktlich gestartet
(z. B. cron-job.org alle 30 Minuten), kommen damit auch die Bot-Signale pünktlich.

Regeln je Bot (Status-Datei auf main):
  - nur zwischen 05:15 und 21:30 UTC (morgens liegt der US-Schluss des Vortags sicher vor; nachts keine Meldungen)
  - Kursstand (asOf) = letzte NYSE-Sitzung bis gestern (Handelskalender, Feiertage/Wochenende beachtet) und keine
    Wiederholung gemeldet (needsRetry / ntfyFailed) -> nichts tun; ohne Kalender: heute (Berlin) schon gelaufen -> nichts
  - läuft schon ein Lauf oder wartet einer -> nichts tun (keine Doppelmeldung in Discord)
  - Wiederholung gemeldet: frühestens 60 Minuten nach dem letzten Lauf erneut anstoßen
  - sonst: workflow_dispatch auf main (manueller Start rechnet im Bot immer)
Manuell mit Schalter „force“ (Run workflow): alle Bots sofort neu rechnen, egal ob heute schon gelaufen
(nur nicht, wenn gerade ein Lauf läuft). KICK_WAIT: so viele Sekunden höchstens warten, bis angestoßene Läufe fertig sind.
Benötigt ein Token mit „Actions: Read and write“ für die vier Bot-Repos (Secret PAT_DISPATCH, sonst PAT_PUSH).
Ohne Token wird nur geprüft.
Ergebnis als JSON-Liste nach KICK_FILE (für den Datenstatus der Seite).
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

USER = "Sin3qz"
BOTS = [("levgtaa", "levGTAA", "levgtaa-signalbot", "status_levgtaa.json", "notify.yaml"),
        ("levtipsregime", "levTipsRegime", "levtipsregime-signalbot", "letsgo_status.json", "notify2.yaml"),
        ("mrreboundgtaa", "MR-Rebound-GTAA", "mrreboundgtaa-signalbot", "status_mrreboundgtaa.json", "notify.yaml"),
        ("1xgtaa", "1xGTAA", "1xgtaa-signalbot", "status_1xgtaa.json", "notify.yaml")]
TZ = ZoneInfo("Europe/Berlin")
EARLIEST_UTC = (5, 15)
LATEST_UTC = (21, 30)


def call(url, token=None, data=None):
    h = {"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.github+json", "Cache-Control": "no-cache"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None, headers=h,
                                 method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read().decode("utf-8")
        return r.status, (json.loads(body) if body.strip().startswith(("{", "[")) else body)


def status(repo, fn, token):
    """Status-Datei über die GitHub-API (nicht zwischengespeichert, anders als raw.githubusercontent.com)."""
    url = f"https://api.github.com/repos/{USER}/{repo}/contents/{fn}?ref=main"
    h = {"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.github.raw"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def busy(repo, wf, token):
    n = 0
    for st in ("in_progress", "queued", "pending", "waiting"):
        _, d = call(f"https://api.github.com/repos/{USER}/{repo}/actions/workflows/{wf}/runs?status={st}&per_page=5", token)
        n += int(d.get("total_count", 0)) if isinstance(d, dict) else 0
    return n > 0


def expected_session(now):
    """Wie die Bots (common.expected_session_date): letzte NYSE-Sitzung <= gestern (Berlin) – deren Schlusskurs muss
    vorliegen. Feiertage/Wochenenden ueber den NYSE-Kalender; ohne Kalender None (dann alte Regel „heute gelaufen?“)."""
    try:
        import pandas_market_calendars as mcal
        yday = now.astimezone(TZ).date() - dt.timedelta(days=1)
        sch = mcal.get_calendar("XNYS").schedule(start_date=yday - dt.timedelta(days=20), end_date=yday)
        return sch.index[-1].date() if len(sch) else None
    except Exception as e:
        print("NYSE-Kalender nicht verfügbar:", e)
        return None


def decide(st, now, exp=None):
    """-> (anstoßen?, Grund)"""
    if (now.hour, now.minute) < EARLIEST_UTC or (now.hour, now.minute) > LATEST_UTC:
        return False, "außerhalb 05:15–21:30 UTC (nachts keine Anstöße)"
    upd = dt.datetime.fromisoformat(st.get("updated", "1970-01-01T00:00:00+00:00"))
    # levGTAA: Monatssignal vorlaeufig, bis der Bitcoin-Tagesschluss (UTC) vor dem Handelstag vorliegt; ist seit dem
    # letzten Lauf ein neuer Tagesschluss abgeschlossen, nachrechnen (hoechstens einmal je neuem Bitcoin-Tag)
    btc_new = (st.get("btcFinal") is False and st.get("btcDate")
               and dt.date.fromisoformat(str(st["btcDate"])[:10]) < now.astimezone(dt.timezone.utc).date() - dt.timedelta(days=1))
    retry = st.get("needsRetry") or st.get("ntfyFailed") or st.get("refreshLater") or btc_new   # refreshLater: Xetra-Kurs fehlte noch
    recent = (now - upd).total_seconds() < 3600
    if exp is not None:                                  # Regel nach Handelskalender: fehlt der erwartete Schlusskurs?
        asof = dt.date.fromisoformat(str(st.get("asOf") or "1970-01-01")[:10])
        if asof >= exp and not retry:
            return False, f"Kursstand aktuell (Schluss {asof:%d.%m.})"
        if recent:
            return False, "letzter Lauf vor weniger als 60 min – nächster Versuch später"
        return True, (f"Schluss {exp:%d.%m.} fehlt noch (Bot-Stand {asof:%d.%m.})" if asof < exp
                      else "Xetra-Kurs fehlte beim letzten Lauf – nachrechnen" if st.get("refreshLater") and not st.get("needsRetry")
                      else "neuer Bitcoin-Tagesschluss – vorläufiges Monatssignal nachrechnen" if btc_new and not st.get("needsRetry")
                      else "Wiederholung gemeldet (veraltete Kurse / Push fehlgeschlagen)")
    today = now.astimezone(TZ).date()
    ran_today = upd.astimezone(TZ).date() == today
    if ran_today and not retry:
        return False, f"heute schon gelaufen ({upd.astimezone(TZ):%H:%M} Uhr)"
    if ran_today and retry and recent:
        return False, "Wiederholung gemeldet, letzter Lauf vor weniger als 60 min"
    return True, ("Wiederholung gemeldet (veraltete Kurse / Push fehlgeschlagen)" if ran_today
                  else f"heute noch kein Lauf (letzter {upd.astimezone(TZ):%d.%m. %H:%M} Uhr)")


def wait_done(kicked, token, limit):
    """Warten, bis die angestoßenen Läufe fertig sind (höchstens limit Sekunden)."""
    t0 = time.time()
    time.sleep(min(30, limit))                         # der neue Lauf erscheint erst nach ein paar Sekunden als „queued“
    while time.time() - t0 < limit:
        left = [name for name, repo, wf in kicked if busy(repo, wf, token)]
        if not left:
            print(f"angestoßene Bots fertig nach {time.time() - t0:.0f} s")
            return True
        print(f"warte auf {', '.join(left)} …")
        time.sleep(20)
    print(f"nach {limit} s noch nicht fertig – ihr Ergebnis kommt mit der nächsten Aktualisierung")
    return False


def main():
    token = (os.environ.get("PAT_DISPATCH") or "").strip()
    force = (os.environ.get("KICK_FORCE") or "").lower() == "true"
    now = dt.datetime.now(dt.timezone.utc)
    out, kicked = [], []
    exp = expected_session(now)
    for key, name, repo, fn, wf in BOTS:
        rec = {"key": key, "name": name, "at": now.isoformat(timespec="minutes")}
        try:
            go, why = (True, "manuell erzwungen (Schalter force)") if force else decide(status(repo, fn, token or None), now, exp)
            if go and token and busy(repo, wf, token):
                go, why = False, "Lauf läuft bereits oder wartet"
            if go and not token:
                rec.update(action="missing_token", detail=f"{why} – Anstoß nicht möglich: kein Token (Secret PAT_PUSH bzw. PAT_DISPATCH)")
            elif go:
                code, _ = call(f"https://api.github.com/repos/{USER}/{repo}/actions/workflows/{wf}/dispatches", token, {"ref": "main"})
                rec.update(action="kicked" if code == 204 else "error", detail=f"angestoßen: {why}" if code == 204 else f"HTTP {code}")
                if code == 204:
                    kicked.append((name, repo, wf))
            else:
                rec.update(action="none", detail=why)
        except urllib.error.HTTPError as e:
            rec.update(action="error", detail=f"GitHub-API HTTP {e.code}" + (" (Token ohne Actions-Schreibrecht oder ohne Zugriff auf das Bot-Repo?)" if e.code in (403, 404) else ""))
        except Exception as e:
            rec.update(action="error", detail=f"{type(e).__name__}: {e}")
        print(f"{name}: {rec['action']} – {rec['detail']}")
        out.append(rec)
    wait = int(os.environ.get("KICK_WAIT") or 0)
    if kicked and wait > 0:
        try:
            wait_done(kicked, token, wait)
        except Exception as e:
            print("Warten abgebrochen:", e)
    path = os.environ.get("KICK_FILE")
    if path:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:                 # der Zeitgeber darf die Aktualisierung nie verhindern
        print("Zeitgeber übersprungen:", e)
    sys.exit(0)
