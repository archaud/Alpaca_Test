"""Polymarket Gamma API client.

The Gamma API is public and unauthenticated. We only need one endpoint:
GET /markets — filterable by slug to return a single market's current state.

For a binary market, the response includes:
  outcomes:       ["Yes", "No"]
  outcomePrices:  ["0.495", "0.505"]   (strings — prices in dollars, sum to ~1.00)

The price of a YES share IS the market-implied probability of YES.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import requests

GAMMA_BASE = "https://gamma-api.polymarket.com"


@dataclass
class BinaryMarket:
    """A binary (YES/NO) prediction market with current odds."""

    slug: str
    question: str
    yes_price: float
    no_price: float
    volume_24h: float
    end_date: str

    @property
    def yes_probability(self) -> float:
        """YES share price is the market's implied probability of YES."""
        return self.yes_price

    @property
    def no_probability(self) -> float:
        return self.no_price


def fetch_binary_market(slug: str) -> BinaryMarket:
    """Fetch a single binary market by slug.

    Raises ValueError if the market does not exist, is non-binary, or has no prices.
    """
    resp = requests.get(f"{GAMMA_BASE}/markets", params={"slug": slug}, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    if not data:
        raise ValueError(f"No market found for slug '{slug}'")

    market = data[0]

    # outcomes and outcomePrices come back as JSON-encoded strings.
    outcomes = market.get("outcomes")
    prices_raw = market.get("outcomePrices")
    if isinstance(outcomes, str):
        outcomes = json.loads(outcomes)
    if isinstance(prices_raw, str):
        prices_raw = json.loads(prices_raw)

    if not outcomes or not prices_raw or len(outcomes) != 2:
        raise ValueError(f"Market '{slug}' is not binary (outcomes={outcomes})")

    prices = [float(p) for p in prices_raw]

    return BinaryMarket(
        slug=slug,
        question=market.get("question", ""),
        yes_price=prices[0],
        no_price=prices[1],
        volume_24h=float(market.get("volume24hr") or 0),
        end_date=market.get("endDate", ""),
    )


if __name__ == "__main__":
    # Quick sanity check.
    m = fetch_binary_market("will-bitcoin-reach-85k-in-may-2026")
    print(f"Market:    {m.question}")
    print(f"Slug:      {m.slug}")
    print(f"YES:       {m.yes_probability:.1%}")
    print(f"NO:        {m.no_probability:.1%}")
    print(f"Volume 24h: ${m.volume_24h:,.0f}")
    print(f"Ends:      {m.end_date}")
