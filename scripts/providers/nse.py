"""Shared helper for NSE's JSON endpoints (they need a cookie from the home page)."""
from __future__ import annotations

HOME = "https://www.nseindia.com/"


def nse_get_json(client, path):
    if "nse" not in client.state:
        client.state.add("nse")
        try:                                  # cookie warm-up; the JSON APIs usually work without it
            client.session.get(HOME, timeout=15)
        except Exception:
            pass
    resp = client.get(HOME + path, headers={"Referer": HOME, "Accept": "application/json"})
    return resp.json()


def to_iso(text):
    """'16-Oct-2026 09:40' or '15-Oct-2026' -> '2026-10-16'."""
    from datetime import datetime
    return datetime.strptime(text.strip()[:11], "%d-%b-%Y").strftime("%Y-%m-%d")
