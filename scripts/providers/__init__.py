"""Provider registry.

A provider is a function `fn(client, ctx) -> {tile_id: Reading | Exception}`.
A Reading is a dict with: value, change, change_pct (the last two may be None),
as_of (YYYY-MM-DD), source_name, source_url, and optionally `history`
(a list of [YYYY-MM-DD, value] pairs used to seed the sparklines).

`ctx` carries `today` (IST date string), `config` and `env`.

To add a provider (for example one backed by the Trendlyne MCP connector),
write a function with this signature and add one `Provider(...)` line to
PROVIDERS. Nothing else needs to change.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List

from .commodities import commodities_provider, COMMODITY_TILES
from .fii_dii import fii_dii_provider, FII_DII_TILES
from .indices import indices_provider, INDEX_TILES
from .us_stocks import us_stocks_provider, us_stock_tiles


@dataclass
class Provider:
    name: str
    tiles: Callable[[dict], List[dict]]      # config -> tile definitions
    fn: Callable                              # (client, ctx) -> {tile_id: reading}


PROVIDERS: List[Provider] = [
    Provider("fii_dii", lambda cfg: FII_DII_TILES, fii_dii_provider),
    Provider("indices", lambda cfg: INDEX_TILES, indices_provider),
    Provider("commodities", lambda cfg: COMMODITY_TILES, commodities_provider),
    Provider("us_stocks", us_stock_tiles, us_stocks_provider),
]
