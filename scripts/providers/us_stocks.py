"""US-listed stocks via Alpha Vantage (free key; Yahoo, Stooq and Nasdaq disallow bots in robots.txt)."""
from __future__ import annotations

URL = "https://www.alphavantage.co/query"


def us_stock_tiles(config):
    return [
        {"id": f"us_{sym}", "label": sym, "section": "us_stocks", "unit": "USD", "symbol": sym}
        for sym in config.get("us_stocks", [])
    ]


def _one(client, ctx, symbol):
    key = ctx["env"].get("ALPHAVANTAGE_API_KEY")
    if not key:
        raise RuntimeError("ALPHAVANTAGE_API_KEY is not set")
    params = {"function": "TIME_SERIES_DAILY", "symbol": symbol, "outputsize": "compact", "apikey": key}
    data = client.get(URL, params=params).json()
    series = data.get("Time Series (Daily)")
    if not series:      # Alpha Vantage returns HTTP 200 with a "Note"/"Information" on rate limits
        raise RuntimeError(data.get("Note") or data.get("Information") or data.get("Error Message")
                           or "no time series in response")
    days = sorted(series)[-30:]
    closes = [(d, float(series[d]["4. close"])) for d in days]
    value, prev = closes[-1][1], (closes[-2][1] if len(closes) > 1 else None)
    return {
        "value": value,
        "change": value - prev if prev else None,
        "change_pct": (value - prev) / prev * 100 if prev else None,
        "as_of": closes[-1][0],
        "source_name": "Alpha Vantage (TIME_SERIES_DAILY)",
        "source_url": "https://www.alphavantage.co/documentation/",
        "history": [list(c) for c in closes],
    }


def us_stocks_provider(client, ctx):
    out = {}
    for sym in ctx["config"].get("us_stocks", []):
        try:
            out[f"us_{sym}"] = _one(client, ctx, sym)
        except Exception as exc:
            out[f"us_{sym}"] = exc
    return out
