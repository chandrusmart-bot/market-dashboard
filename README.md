# Market Dashboard

A static dashboard with a daily snapshot of Indian and global markets, hosted on GitHub Pages.
A GitHub Actions job fetches the data once a day and commits it to `data/`. The page only reads
those saved files. The **Refresh** button re-reads `data/latest.json`; it never scrapes live data.

Tiles: FII/DII net flows, NIFTY 50, BANK NIFTY, GIFT NIFTY, Brent, USD/INR, gold, GoldBeeS,
and US stocks (WDC, SNDK, MU, STX by default). Each tile shows the value, change, % change,
the "as of" date, fetch time (IST), a 30-day sparkline and a warning badge when stale.

## Data sources and terms

All free. Every value records its source, URL and fetch time in `data/latest.json`.

| Tile | Source | Notes |
|---|---|---|
| FII / DII | NSE `api/fiidiiTradeReact` | NSE's terms restrict automated use. NSE may block GitHub's cloud IPs; if so the tile goes stale. |
| NIFTY 50, BANK NIFTY | NSE `api/allIndices` | Same NSE caveats. |
| GIFT NIFTY | NSE `api/marketStatus` (GIFT Nifty future) | Same NSE caveats. |
| GoldBeeS | NSE `GetQuoteApi` | Same NSE caveats. |
| Brent spot | US EIA API, series `RBRTE` | Free key. EIA data lags by a few days. |
| USD/INR | Frankfurter (ECB reference rates) | No key. Published once per working day. |
| Gold spot (USD/oz) | gold-api.com | No key. Change is computed from our own history. |
| US stocks | Alpha Vantage `TIME_SERIES_DAILY` | Free key, 25 requests/day. |

**Why not Yahoo Finance, Stooq or Nasdaq's API?** Their `robots.txt` files disallow automated
access, and this project respects robots.txt. The HTTP client checks robots.txt on every host.

The client sends `User-Agent: Mozilla/5.0 market-dashboard/1.0 (personal project)`, waits at least
1 second between requests to a host, uses a 15 s timeout, and tries each request 3 times with
exponential backoff. (NSE tarpits User-Agents that contain a URL, so none is included.)

## Reliability behaviour

- A failed source keeps the last good value and sets `status: "stale"`. With no earlier value the tile is `"error"`.
- Missing fields render as "—" and the tile is flagged. The script never crashes on a missing field.
- If a market is closed, the last close stays and the tile shows its own "as of" date.
- The 20:00 IST fallback run skips tiles that already hold a good value for today's date.

## Enable GitHub Pages

1. Repo **Settings → Pages**.
2. Source: **Deploy from a branch**, branch `main`, folder `/ (root)`.
3. Open `https://<your-user>.github.io/market-dashboard/`.

## Secrets (free keys)

Add under **Settings → Secrets and variables → Actions**:

- `EIA_API_KEY`: free at <https://www.eia.gov/opendata/register.php>
- `ALPHAVANTAGE_API_KEY`: free at <https://www.alphavantage.co/support/#api-key>

Without them only the Brent and US-stock tiles show "no data"; everything else still works.

## Run the update manually

On GitHub: **Actions → Daily market update → Run workflow** (the page also has a "Run update now" link).

Locally:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
EIA_API_KEY=... ALPHAVANTAGE_API_KEY=... .venv/bin/python scripts/fetch_data.py
python3 -m http.server 8000   # then open http://localhost:8000
```

Output: `data/latest.json`, `data/history/YYYY-MM-DD.json`, `data/history.json` (rolling 30 days).
The committed files start as clearly labelled **sample data** (`"sample": true`); the first real run replaces them.

## Change the US stocks

Edit `config.json` (`"us_stocks": ["WDC", "SNDK", "MU", "STX"]`). Tiles for removed tickers are dropped from history.

## Add a provider

A provider is a function `fn(client, ctx) -> {tile_id: reading_or_exception}` (see `scripts/providers/__init__.py`).

1. Create `scripts/providers/my_source.py` with the function and a list of tile definitions
   (`id`, `label`, `section`, `unit`).
2. Add one line to `PROVIDERS` in `scripts/providers/__init__.py`.

The orchestrator handles stale handling, history, change calculation and file output, so nothing
else changes. A provider backed by the Trendlyne AI connector (MCP) would be added the same way,
or can replace a provider by swapping its entry in the registry.

## Run the tests

```bash
.venv/bin/python -m pytest
```

HTTP is mocked, so no network is needed. The suite includes a failed-source case that checks stale handling.

## DISCLAIMER

This dashboard is for personal reference only and is **not investment advice**. Data may be
delayed, incomplete or wrong. Each data source's own terms of use apply, and you are responsible
for complying with them.
