"""Basket logic.

A Basket is a named set of equity weights that expresses a thesis
(e.g. "Bitcoin rallies" -> COIN, MSTR, MARA).

We blend two baskets by the live Polymarket probabilities for a binary
market, after carving out a cash floor:

    target[symbol] = (1 - cash) * (P_yes * basket_yes + P_no * basket_no)
    target["CASH"] = cash

Final weights sum to 1.0.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from polymarket import BinaryMarket


@dataclass
class Basket:
    """Equity basket expressing a thesis. Weights are within-basket (sum to 1)."""

    name: str
    weights: Dict[str, float]

    def __post_init__(self) -> None:
        total = sum(self.weights.values())
        if not (0.999 <= total <= 1.001):
            raise ValueError(
                f"Basket '{self.name}' weights sum to {total:.4f}, expected 1.0"
            )


def compute_target_weights(
    market: BinaryMarket,
    yes_basket: Basket,
    no_basket: Basket,
    cash_weight: float = 0.05,
) -> Dict[str, float]:
    """Probability-weighted blend of two baskets, with cash floor.

    Returns a dict of symbol -> weight summing to 1.0. Includes "CASH" key.
    """
    if not (0 <= cash_weight < 1):
        raise ValueError(f"cash_weight must be in [0, 1), got {cash_weight}")

    risk_budget = 1.0 - cash_weight
    target: Dict[str, float] = {}

    for symbol, w in yes_basket.weights.items():
        target[symbol] = target.get(symbol, 0.0) + risk_budget * market.yes_probability * w

    for symbol, w in no_basket.weights.items():
        target[symbol] = target.get(symbol, 0.0) + risk_budget * market.no_probability * w

    target["CASH"] = cash_weight

    # Sanity check.
    total = sum(target.values())
    assert 0.999 <= total <= 1.001, f"target weights sum to {total}, not 1.0"

    return target


def format_weights(weights: Dict[str, float]) -> str:
    """Pretty-print target weights, largest first."""
    lines = []
    for symbol, w in sorted(weights.items(), key=lambda x: -x[1]):
        lines.append(f"  {symbol:>6}  {w * 100:5.2f}%")
    return "\n".join(lines)


# ---- Sample baskets for the BTC market ---------------------------------

# Thesis: Bitcoin rallies above $85k by May 31
# Beneficiaries: crypto-correlated equities and BTC-treasury companies
BTC_RALLIES = Basket(
    name="BTC rallies",
    weights={
        "COIN": 0.30,   # Coinbase
        "MSTR": 0.30,   # MicroStrategy (BTC treasury)
        "MARA": 0.20,   # Marathon Digital (miner)
        "RIOT": 0.20,   # Riot Platforms (miner)
    },
)

# Thesis: Bitcoin stays below $85k
# Beneficiaries: defensive equities and inverse-correlated to crypto sentiment
BTC_STALLS = Basket(
    name="BTC stalls",
    weights={
        "SPY":  0.40,   # Broad market
        "TLT":  0.30,   # Long Treasuries (safe haven)
        "GLD":  0.20,   # Gold (alternative store of value)
        "XLU":  0.10,   # Utilities (defensive)
    },
)


if __name__ == "__main__":
    from polymarket import fetch_binary_market

    market = fetch_binary_market("will-bitcoin-reach-85k-in-may-2026")
    print(f"Market: {market.question}")
    print(f"  YES = {market.yes_probability:.1%}  NO = {market.no_probability:.1%}")
    print()
    print(f"YES basket ({BTC_RALLIES.name}):  {BTC_RALLIES.weights}")
    print(f"NO  basket ({BTC_STALLS.name}):  {BTC_STALLS.weights}")
    print()

    target = compute_target_weights(market, BTC_RALLIES, BTC_STALLS, cash_weight=0.05)
    print("Probability-weighted target portfolio:")
    print(format_weights(target))
