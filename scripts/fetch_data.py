"""Fetch all tiles and write data/latest.json, data/history/YYYY-MM-DD.json and data/history.json.

Usage: python scripts/fetch_data.py
Env:   EIA_API_KEY, ALPHAVANTAGE_API_KEY (both free-tier keys, stored as Actions secrets)
"""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from httpclient import Client          # noqa: E402
from providers import PROVIDERS        # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
ROOT = Path(__file__).resolve().parent.parent
HISTORY_DAYS = 30


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def is_fresh(tile, today):
    """A tile already holding a good value for today's date needs no refetch."""
    return bool(tile) and tile.get("status") == "ok" and tile.get("as_of") == today


def previous_close(series, as_of):
    """Latest history value dated before as_of (used when a source gives no change)."""
    older = [v for d, v in series if d < as_of]
    return older[-1] if older else None


def build_ok_tile(defn, reading, series, fetched_at):
    value = reading.get("value")
    if not is_number(value):
        raise ValueError("no usable value in response")
    change, pct = reading.get("change"), reading.get("change_pct")
    if not is_number(change) and reading.get("as_of"):
        prev = previous_close(series, reading["as_of"])
        if prev:
            change, pct = value - prev, (value - prev) / prev * 100
    as_of = reading.get("as_of")
    return {
        **defn,
        "value": value,
        "change": change if is_number(change) else None,
        "change_pct": pct if is_number(pct) else None,
        "as_of": as_of,
        "source_name": reading.get("source_name") or "—",
        "source_url": reading.get("source_url") or "",
        "fetched_at": fetched_at,
        "status": "ok" if as_of else "stale",   # a value with no date cannot be trusted as current
        "error": None if as_of else "source gave no date",
    }


def build_failed_tile(defn, prev, error, fetched_at):
    """Keep the last good value and mark it stale; with no earlier value, report an error tile."""
    if prev and is_number(prev.get("value")):
        return {**prev, **defn, "status": "stale", "error": str(error)}
    return {**defn, "value": None, "change": None, "change_pct": None, "as_of": None,
            "source_name": "—", "source_url": "", "fetched_at": fetched_at,
            "status": "error", "error": str(error)}


def merge_history(series, points, keep=HISTORY_DAYS):
    by_date = {d: v for d, v in series}
    by_date.update({d: v for d, v in points if is_number(v)})
    return [[d, by_date[d]] for d in sorted(by_date)][-keep:]


def run(providers, client, config, env, now, previous_latest, history):
    """Return (latest, history). `now` is a timezone-aware datetime."""
    today = now.astimezone(IST).strftime("%Y-%m-%d")
    fetched_at = now.astimezone(IST).isoformat(timespec="seconds")
    ctx = {"today": today, "config": config, "env": env}
    prev_tiles = (previous_latest or {}).get("tiles", {})
    if (previous_latest or {}).get("sample"):      # first real run discards the shipped sample data
        prev_tiles, history = {}, {}
    series = history.setdefault("series", {})
    tiles = {}

    for provider in providers:
        defs = provider.tiles(config)
        if all(is_fresh(prev_tiles.get(d["id"]), today) for d in defs):
            for d in defs:
                tiles[d["id"]] = prev_tiles[d["id"]]
            continue
        try:
            results = provider.fn(client, ctx) or {}
        except Exception as exc:
            results = {d["id"]: exc for d in defs}
        for d in defs:
            prev = prev_tiles.get(d["id"])
            if is_fresh(prev, today):
                tiles[d["id"]] = prev
                continue
            reading = results.get(d["id"], RuntimeError("provider returned nothing for this tile"))
            try:
                if isinstance(reading, Exception):
                    raise reading
                tile = build_ok_tile(d, reading, series.get(d["id"], []), fetched_at)
                points = list(reading.get("history") or [])
                if tile["as_of"]:
                    points.append([tile["as_of"], tile["value"]])
                series[d["id"]] = merge_history(series.get(d["id"], []), points)
            except Exception as exc:
                print(f"[warn] {d['id']}: {exc}", file=sys.stderr)
                tile = build_failed_tile(d, prev, exc, fetched_at)
            tiles[d["id"]] = tile

    for stale_id in set(series) - set(tiles):      # tile removed from config.json
        del series[stale_id]
    latest = {"generated_at": fetched_at, "trade_date": today, "tiles": tiles}
    return latest, history


def main():
    now = datetime.now(timezone.utc)
    config = load_json(ROOT / "config.json", {})
    data = ROOT / "data"
    latest, history = run(
        PROVIDERS, Client(), config, dict(os.environ), now,
        load_json(data / "latest.json", {}), load_json(data / "history.json", {}),
    )
    write_json(data / "latest.json", latest)
    write_json(data / "history.json", history)
    write_json(data / "history" / f"{latest['trade_date']}.json", latest)
    counts = {}
    for t in latest["tiles"].values():
        counts[t["status"]] = counts.get(t["status"], 0) + 1
    print("done:", counts)


if __name__ == "__main__":
    main()
