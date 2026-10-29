#!/usr/bin/env python3
"""Zeitgeber für die Bots: stößt jeden Bot an, der heute noch nicht erfolgreich gelaufen ist.

GitHub startet geplante Läufe (cron) teils Stunden später oder lässt sie aus (Oktober 2026: 05:17 UTC -> 10:40-11:25 UTC).
Diese Datei läuft zu Beginn jeder Dashboard-Aktualisierung. Wird die Aktualisierung von außen pünktlich gestartet
(z. B. cron-job.org alle 30 Minuten), kommen damit auch die Bot-Signale pünktlich.

Regeln je Bot (Status-Datei auf main):
  - nur zwischen 05:15 und 21:30 UTC (morgens liegt der US-Schluss des Vortags sicher vor; nachts keine Meldungen)
  - heute (Berlin) schon gelaufen und keine Wiederholung gemeldet (needsRetry / ntfyFailed) -> nichts tun
  - läuft schon ein Lauf oder wartet einer -> nichts tun (keine Doppelmeldung in Discord)
  - Wiederholung gemeldet: frühestens 60 Minuten nach dem letzten Lauf erneut anstoßen
  - sonst: workflow_dispatch auf main (manueller Start rechnet im Bot immer)
Benötigt ein Token mit „Actions: Read and write“ für die vier Bot-Repos (Secret PAT_DISPATCH, sonst PAT_PUSH).
Ohne Token wird nur geprüft.
Ergebnis als JSON-Liste nach KICK_FILE (für den Datenstatus der Seite).
"""
import datetime as dt
import json
import os
import sys
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


def decide(st, now):
    """-> (anstoßen?, Grund)"""
    if (now.hour, now.minute) < EARLIEST_UTC or (now.hour, now.minute) > LATEST_UTC:
        return False, "außerhalb 05:15–21:30 UTC (nachts keine Anstöße)"
    upd = dt.datetime.fromisoformat(st.get("updated", "1970-01-01T00:00:00+00:00"))
    today = now.astimezone(TZ).date()
    ran_today = upd.astimezone(TZ).date() == today
    retry = st.get("needsRetry") or st.get("ntfyFailed")
    if ran_today and not retry:
        return False, f"heute schon gelaufen ({upd.astimezone(TZ):%H:%M} Uhr)"
    if ran_today and retry and (now - upd).total_seconds() < 3600:
        return False, "Wiederholung gemeldet, letzter Lauf vor weniger als 60 min"
    return True, ("Wiederholung gemeldet (veraltete Kurse / Push fehlgeschlagen)" if ran_today
                  else f"heute noch kein Lauf (letzter {upd.astimezone(TZ):%d.%m. %H:%M} Uhr)")


def main():
    token = (os.environ.get("PAT_DISPATCH") or "").strip()
    now = dt.datetime.now(dt.timezone.utc)
    out = []
    for key, name, repo, fn, wf in BOTS:
        rec = {"key": key, "name": name, "at": now.isoformat(timespec="minutes")}
        try:
            go, why = decide(status(repo, fn, token or None), now)
            if go and token and busy(repo, wf, token):
                go, why = False, "Lauf läuft bereits oder wartet"
            if go and not token:
                rec.update(action="missing_token", detail=f"{why} – Anstoß nicht möglich: kein Token (Secret PAT_PUSH bzw. PAT_DISPATCH)")
            elif go:
                code, _ = call(f"https://api.github.com/repos/{USER}/{repo}/actions/workflows/{wf}/dispatches", token, {"ref": "main"})
                rec.update(action="kicked" if code == 204 else "error", detail=f"angestoßen: {why}" if code == 204 else f"HTTP {code}")
            else:
                rec.update(action="none", detail=why)
        except urllib.error.HTTPError as e:
            rec.update(action="error", detail=f"GitHub-API HTTP {e.code}" + (" (Token ohne Actions-Schreibrecht oder ohne Zugriff auf das Bot-Repo?)" if e.code in (403, 404) else ""))
        except Exception as e:
            rec.update(action="error", detail=f"{type(e).__name__}: {e}")
        print(f"{name}: {rec['action']} – {rec['detail']}")
        out.append(rec)
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
