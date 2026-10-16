"""FII / DII net buy-sell (INR crore) from NSE."""
from __future__ import annotations

from .nse import nse_get_json, to_iso

SOURCE = "NSE India (fiidiiTradeReact)"
URL = "https://www.nseindia.com/api/fiidiiTradeReact"

FII_DII_TILES = [
    {"id": "fii_net", "label": "FII / FPI net", "section": "flows", "unit": "₹ cr"},
    {"id": "dii_net", "label": "DII net", "section": "flows", "unit": "₹ cr"},
]


def fii_dii_provider(client, ctx):
    rows = nse_get_json(client, "api/fiidiiTradeReact")
    out = {}
    for tile_id, prefix in (("fii_net", "FII"), ("dii_net", "DII")):
        row = next((r for r in rows if r.get("category", "").startswith(prefix)), None)
        try:
            out[tile_id] = {
                "value": float(row["netValue"]),
                "change": None,        # filled from the previous day by fetch_data
                "change_pct": None,
                "as_of": to_iso(row["date"]),
                "source_name": SOURCE,
                "source_url": URL,
            }
        except (TypeError, KeyError, ValueError) as exc:
            out[tile_id] = ValueError(f"{prefix} row missing or malformed: {exc!r}")
    return out
