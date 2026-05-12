"""alpaca_test: probability-weighted rebalancing on Alpaca Broker API.

Run this once. It will:
  1. Fetch live odds from a Polymarket binary market.
  2. Map outcomes to thesis baskets and compute target weights.
  3. Create a sandbox customer account on Alpaca.
  4. Journal cash from the sandbox firm account into the customer account.
  5. Create a portfolio with the computed weights.
  6. Subscribe the customer account, which triggers an initial rebalance.
  7. Poll runs until completion, print the resulting orders.
"""

from __future__ import annotations

import sys

from dotenv import load_dotenv

import baskets
import polymarket
from alpaca import AlpacaError, BrokerClient

# ---- Demo configuration ----------------------------------------------------

MARKET_SLUG = "will-bitcoin-reach-85k-in-may-2026"
YES_BASKET = baskets.BTC_RALLIES
NO_BASKET = baskets.BTC_STALLS
CASH_WEIGHT = 0.05
FUNDING_AMOUNT = 50  # USD to journal into the customer account.
# Sandbox JNLC transaction limit defaults to $50. Bump in Broker Dashboard
# (Settings > Funding) for larger journals, e.g. $10K or $50K.


def main() -> int:
    load_dotenv()

    # --- 1. Live signal -----------------------------------------------------
    print("[1/6] Fetching live Polymarket odds...")
    market = polymarket.fetch_binary_market(MARKET_SLUG)
    print(f"      Q: {market.question}")
    print(f"         YES={market.yes_probability:.1%}  NO={market.no_probability:.1%}")

    # --- 2. Compute target portfolio ---------------------------------------
    print("\n[2/6] Computing probability-weighted target portfolio...")
    target = baskets.compute_target_weights(
        market, YES_BASKET, NO_BASKET, cash_weight=CASH_WEIGHT
    )
    print(baskets.format_weights(target))

    # --- 3. Alpaca: create customer account --------------------------------
    print("\n[3/6] Creating sandbox customer account...")
    client = BrokerClient()
    account = client.create_customer_account()
    customer_id = account["id"]
    print(f"      account_id: {customer_id}")
    print(f"      status:     {account.get('status')}")

    # Wait for sandbox auto-approval before any funding.
    print("      waiting for account approval...")
    client.wait_for_account_approval(customer_id)

    # --- 4. Fund via journal -----------------------------------------------
    print(f"\n[4/6] Journaling ${FUNDING_AMOUNT:,} from firm account...")
    firm_id = client.get_firm_account_id()
    print(f"      firm_id:    {firm_id}")
    funding_ok = False
    try:
        journal = client.journal_cash(firm_id, customer_id, FUNDING_AMOUNT)
        print(f"      journal_id: {journal.get('id')}  status: {journal.get('status')}")
        funding_ok = True
    except AlpacaError as e:
        print(f"      JOURNAL FAILED (continuing anyway):\n        {e}")
        print(
            "      NOTE: this is a known sandbox issue (500 with no detail).\n"
            "      Portfolio creation + subscription will still be exercised."
        )

    # --- 5. Create portfolio -----------------------------------------------
    print("\n[5/6] Creating portfolio in Alpaca...")
    portfolio_name = f"alpaca_test: {market.slug[:30]}"
    portfolio = client.create_portfolio(
        name=portfolio_name,
        description=(
            f"Probability-weighted via Polymarket. YES={market.yes_probability:.1%}, "
            f"NO={market.no_probability:.1%}"
        ),
        weights=target,
    )
    portfolio_id = portfolio["id"]
    print(f"      portfolio_id: {portfolio_id}")

    # --- 6. Subscribe + wait for rebalance ---------------------------------
    print("\n[6/6] Subscribing account (triggers initial rebalance)...")
    sub = client.subscribe(customer_id, portfolio_id)
    print(f"      subscription_id: {sub.get('id')}")

    if not funding_ok:
        print(
            "\nFunding step was skipped (see [4/6] above). Subscription is in place\n"
            "but no rebalance run will fire without cash. Verified end-to-end API\n"
            "surface up through subscription. View this account in the dashboard:"
        )
        print(f"  https://broker-app.alpaca.markets/accounts/{customer_id}")
        return 0

    print("\nPolling for the first rebalancing run to complete...")
    run = client.wait_for_run(customer_id, timeout_seconds=180)
    if not run:
        print("\n  Timed out waiting for run. Check the Broker Dashboard:")
        print(f"  https://broker-app.alpaca.markets/accounts/{customer_id}")
        print("  (Rebalances only fire 9:30 AM - 3:30 PM ET on trading days.)")
        return 1

    # Summarize the orders that fired.
    print(f"\n  Run {run.get('id')[:8]} completed with status {run.get('status')}")
    orders = run.get("orders", [])
    print(f"  {len(orders)} orders generated:\n")
    for o in orders:
        side = o.get("side", "?").upper()
        sym = o.get("symbol", "?")
        notional = o.get("notional") or o.get("filled_qty") or "?"
        status = o.get("status", "?")
        print(f"    {side:4} {sym:6}  ${notional}  ({status})")

    print(f"\nDone. View this account in the Broker Dashboard:")
    print(f"  https://broker-app.alpaca.markets/accounts/{customer_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())