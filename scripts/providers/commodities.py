"""Brent spot (EIA), USD/INR (Frankfurter), gold spot (gold-api.com), GoldBeeS (NSE)."""
from __future__ import annotations

from datetime import date, timedelta

from .nse import nse_get_json, to_iso

COMMODITY_TILES = [
    {"id": "brent", "label": "Brent crude (spot)", "section": "commodities", "unit": "USD/bbl"},
    {"id": "usdinr", "label": "USD/INR", "section": "commodities", "unit": "₹"},
    {"id": "gold", "label": "Gold (spot)", "section": "commodities", "unit": "USD/oz"},
    {"id": "goldbees", "label": "GoldBeeS (NSE ETF)", "section": "commodities", "unit": "₹"},
]

EIA_URL = "https://api.eia.gov/v2/petroleum/pri/spt/data/"
FRANKFURTER_URL = "https://api.frankfurter.dev/v1/"
GOLD_URL = "https://api.gold-api.com/price/XAU"
GOLDBEES_PATH = ("api/NextApi/apiClient/GetQuoteApi"
                 "?functionName=getSymbolData&marketType=N&series=EQ&symbol=GOLDBEES")


def _pct(value, prev):
    return round((value - prev) / prev * 100, 4) if prev else None


def brent(client, ctx):
    key = ctx["env"].get("EIA_API_KEY")
    if not key:
        raise RuntimeError("EIA_API_KEY is not set")
    params = {
        "api_key": key, "frequency": "daily", "data[0]": "value",
        "facets[series][]": "RBRTE", "sort[0][column]": "period",
        "sort[0][direction]": "desc", "length": 30,
    }
    rows = client.get(EIA_URL, params=params).json()["response"]["data"]
    rows = [r for r in rows if r.get("value") not in (None, "")]
    latest, prev = rows[0], rows[1] if len(rows) > 1 else None
    value = float(latest["value"])
    change = value - float(prev["value"]) if prev else None
    return {
        "value": value, "change": change,
        "change_pct": _pct(value, float(prev["value"])) if prev else None,
        "as_of": latest["period"],
        "source_name": "US EIA (Brent spot RBRTE)", "source_url": EIA_URL,
        "history": [[r["period"], float(r["value"])] for r in reversed(rows)],
    }


def usdinr(client, ctx):
    start = (date.fromisoformat(ctx["today"]) - timedelta(days=45)).isoformat()
    url = f"{FRANKFURTER_URL}{start}..?base=USD&symbols=INR"
    rates = client.get(url).json()["rates"]
    days = sorted(rates)
    value = float(rates[days[-1]]["INR"])
    prev = float(rates[days[-2]]["INR"]) if len(days) > 1 else None
    return {
        "value": value, "change": value - prev if prev else None, "change_pct": _pct(value, prev),
        "as_of": days[-1],
        "source_name": "Frankfurter (ECB reference rate)", "source_url": "https://frankfurter.dev",
        "history": [[d, float(rates[d]["INR"])] for d in days],
    }


def gold(client, ctx):
    data = client.get(GOLD_URL).json()
    return {
        "value": float(data["price"]), "change": None, "change_pct": None,   # filled from history
        "as_of": data["updatedAt"][:10],
        "source_name": "gold-api.com (XAU spot)", "source_url": GOLD_URL,
    }


def goldbees(client, ctx):
    q = nse_get_json(client, GOLDBEES_PATH)["equityResponse"][0]
    meta = q["metaData"]
    return {
        "value": float(q["tradeInfo"]["lastPrice"]),
        "change": float(meta["change"]), "change_pct": float(meta["pChange"]),
        "as_of": to_iso(q["lastUpdateTime"]),
        "source_name": "NSE India (GOLDBEES quote)",
        "source_url": "https://www.nseindia.com/get-quotes/equity?symbol=GOLDBEES",
    }


def commodities_provider(client, ctx):
    out = {}
    for tile_id, fn in (("brent", brent), ("usdinr", usdinr), ("gold", gold), ("goldbees", goldbees)):
        try:
            out[tile_id] = fn(client, ctx)
        except Exception as exc:       # one failing source must not sink the others
            out[tile_id] = exc
    return out
