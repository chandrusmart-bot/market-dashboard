"""NIFTY 50, BANK NIFTY and GIFT NIFTY from NSE."""
from __future__ import annotations

from .nse import nse_get_json, to_iso

INDEX_TILES = [
    {"id": "nifty50", "label": "NIFTY 50", "section": "indices", "unit": ""},
    {"id": "banknifty", "label": "BANK NIFTY", "section": "indices", "unit": ""},
    {"id": "gift_nifty", "label": "GIFT NIFTY", "section": "indices", "unit": ""},
]

ALL_INDICES = ("NSE India (allIndices)", "https://www.nseindia.com/api/allIndices")
MARKET_STATUS = ("NSE India (marketStatus, GIFT Nifty future)", "https://www.nseindia.com/api/marketStatus")


def _reading(value, change, pct, stamp, source):
    return {
        "value": float(value),
        "change": float(change),
        "change_pct": float(pct),
        "as_of": to_iso(stamp),
        "source_name": source[0],
        "source_url": source[1],
    }


def indices_provider(client, ctx):
    out = {}
    try:
        data = nse_get_json(client, "api/allIndices")
        by_name = {row["index"]: row for row in data["data"]}
        for tile_id, name in (("nifty50", "NIFTY 50"), ("banknifty", "NIFTY BANK")):
            try:
                row = by_name[name]
                out[tile_id] = _reading(row["last"], row["variation"], row["percentChange"],
                                        data["timestamp"], ALL_INDICES)
            except (KeyError, TypeError, ValueError) as exc:
                out[tile_id] = ValueError(f"{name} missing or malformed: {exc!r}")
    except Exception as exc:
        out["nifty50"] = out["banknifty"] = exc
    try:
        gift = nse_get_json(client, "api/marketStatus")["giftnifty"]
        out["gift_nifty"] = _reading(gift["LASTPRICE"], gift["DAYCHANGE"], gift["PERCHANGE"],
                                     gift["TIMESTMP"], MARKET_STATUS)
    except Exception as exc:
        out["gift_nifty"] = exc
    return out
