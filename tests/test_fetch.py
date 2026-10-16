"""Tests for the fetch script. All HTTP is mocked; nothing touches the network."""
from datetime import datetime, timezone

import pytest
import requests
import responses

import fetch_data
from httpclient import Client, RobotsDisallowed
from providers import Provider
from providers.fii_dii import fii_dii_provider
from providers.indices import indices_provider

NOW = datetime(2026, 10, 16, 13, 30, tzinfo=timezone.utc)       # 19:00 IST on 2026-10-16
TODAY = "2026-10-16"
DEF = {"id": "x", "label": "X", "section": "indices", "unit": ""}


def client():
    return Client(delay=0, sleep=lambda s: None)


def reading(value=100.0, as_of=TODAY, **extra):
    return {"value": value, "change": 1.0, "change_pct": 1.0, "as_of": as_of,
            "source_name": "test", "source_url": "http://test", **extra}


def provider(fn):
    return Provider("p", lambda cfg: [DEF], fn)


def run(prov, prev=None, history=None):
    return fetch_data.run([prov], client(), {}, {}, NOW, prev or {}, history or {})


# ---- HTTP client -------------------------------------------------------------

@responses.activate
def test_client_retries_then_succeeds():
    responses.get("https://a.test/robots.txt", status=404)
    responses.get("https://a.test/data", status=500)
    responses.get("https://a.test/data", json={"ok": 1})
    assert client().get("https://a.test/data").json() == {"ok": 1}


@responses.activate
def test_client_gives_up_after_three_attempts():
    responses.get("https://a.test/data", status=500)
    with pytest.raises(requests.HTTPError):
        client().get("https://a.test/data")
    assert len([c for c in responses.calls if c.request.url.endswith("/data")]) == 3


@responses.activate
def test_client_respects_robots_txt():
    responses.get("https://a.test/robots.txt", body="User-agent: *\nDisallow: /")
    with pytest.raises(RobotsDisallowed):
        client().get("https://a.test/data")


# ---- providers (mocked sources) ---------------------------------------------

@responses.activate
def test_fii_dii_provider_parses_nse_rows():
    responses.get("https://www.nseindia.com/api/fiidiiTradeReact", json=[
        {"category": "DII", "date": "15-Oct-2026", "netValue": "3319.39"},
        {"category": "FII/FPI", "date": "15-Oct-2026", "netValue": "-5285.37"},
    ])
    out = fii_dii_provider(client(), {})
    assert out["fii_net"]["value"] == -5285.37
    assert out["dii_net"]["as_of"] == "2026-10-15"


@responses.activate
def test_fii_dii_missing_row_is_an_error_not_a_crash():
    responses.get("https://www.nseindia.com/api/fiidiiTradeReact", json=[])
    out = fii_dii_provider(client(), {})
    assert isinstance(out["fii_net"], Exception)


@responses.activate
def test_indices_one_endpoint_failing_does_not_hide_the_others():
    responses.get("https://www.nseindia.com/api/allIndices", json={
        "timestamp": "16-Oct-2026 15:30",
        "data": [{"index": "NIFTY 50", "last": 22900, "variation": -50, "percentChange": -0.2},
                 {"index": "NIFTY BANK", "last": 55000, "variation": 100, "percentChange": 0.2}]})
    responses.get("https://www.nseindia.com/api/marketStatus", status=500)
    out = indices_provider(client(), {})
    assert out["nifty50"]["value"] == 22900
    assert isinstance(out["gift_nifty"], Exception)


# ---- orchestrator ------------------------------------------------------------

def test_ok_tile():
    latest, hist = run(provider(lambda c, x: {"x": reading()}))
    tile = latest["tiles"]["x"]
    assert tile["status"] == "ok" and tile["value"] == 100.0 and tile["fetched_at"].endswith("+05:30")
    assert hist["series"]["x"] == [[TODAY, 100.0]]


def test_failed_source_keeps_last_good_value_and_marks_stale():
    prev = {"tiles": {"x": {**DEF, "value": 90.0, "change": 1, "change_pct": 1, "as_of": "2026-10-15",
                            "status": "ok", "source_name": "test", "source_url": "u", "fetched_at": "t"}}}

    def boom(c, x):
        raise requests.ConnectionError("source down")

    latest, _ = run(provider(boom), prev)
    tile = latest["tiles"]["x"]
    assert tile["status"] == "stale"
    assert tile["value"] == 90.0 and tile["as_of"] == "2026-10-15"
    assert "source down" in tile["error"]


def test_failed_source_without_history_is_an_error_tile():
    latest, _ = run(provider(lambda c, x: {"x": RuntimeError("nope")}))
    tile = latest["tiles"]["x"]
    assert tile["status"] == "error" and tile["value"] is None


def test_missing_value_does_not_crash_and_is_not_ok():
    latest, _ = run(provider(lambda c, x: {"x": {"as_of": TODAY}}))
    assert latest["tiles"]["x"]["status"] == "error"


def test_tile_missing_from_provider_output_is_handled():
    latest, _ = run(provider(lambda c, x: {}))
    assert latest["tiles"]["x"]["status"] == "error"


def test_missing_date_marks_tile_stale():
    latest, _ = run(provider(lambda c, x: {"x": reading(as_of=None)}))
    assert latest["tiles"]["x"]["status"] == "stale"


def test_fresh_tile_is_not_refetched():
    prev = {"tiles": {"x": {**DEF, "value": 5.0, "as_of": TODAY, "status": "ok"}}}
    calls = []
    latest, _ = run(provider(lambda c, x: calls.append(1) or {"x": reading()}), prev)
    assert calls == [] and latest["tiles"]["x"]["value"] == 5.0


def test_closed_market_keeps_last_close_with_its_date():
    latest, _ = run(provider(lambda c, x: {"x": reading(as_of="2026-10-14")}))
    assert latest["tiles"]["x"]["as_of"] == "2026-10-14"


def test_change_is_filled_from_history_when_source_has_none():
    r = reading(value=110.0)
    r["change"] = r["change_pct"] = None
    hist = {"series": {"x": [["2026-10-14", 100.0]]}}
    latest, _ = run(provider(lambda c, x: {"x": r}), history=hist)
    assert latest["tiles"]["x"]["change"] == pytest.approx(10.0)
    assert latest["tiles"]["x"]["change_pct"] == pytest.approx(10.0)


def test_history_keeps_30_points():
    pts = [[f"2026-09-{d:02d}", float(d)] for d in range(1, 31)] + [["2026-10-01", 31.0]]
    merged = fetch_data.merge_history(pts[:-1], pts[-1:])
    assert len(merged) == 30 and merged[-1] == ["2026-10-01", 31.0]


def test_sample_data_is_replaced_on_first_real_run():
    prev = {"sample": True, "tiles": {"x": {**DEF, "value": 1.0, "as_of": TODAY, "status": "ok"}}}
    hist = {"series": {"x": [["2026-10-01", 1.0]]}}
    latest, hist = run(provider(lambda c, x: {"x": reading()}), prev, hist)
    assert "sample" not in latest and hist["series"]["x"] == [[TODAY, 100.0]]
