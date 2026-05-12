# alpaca_test

A prototype that drives an Alpaca brokerage portfolio off live Polymarket
prediction-market odds. Built in a few hours to ground a product
conversation about signal-driven rebalancing.

## Thesis

Prediction markets produce probability estimates that move faster, with
more liquidity-tested conviction, than analyst consensus or sentiment
scores. For thematic equity portfolios, those probabilities are a
natural rebalancing signal.

No brokerage primitive today exposes "rebalance my portfolio when this
external probability changes." Alpaca's Rebalancing API is the closest
existing surface. This prototype tests whether Polymarket odds can drive
an Alpaca portfolio end-to-end and what gaps surface in the process.

## What it does

For a single binary prediction market (e.g. "Will Bitcoin reach $85,000
in May?"):

1. Pulls live YES/NO odds from Polymarket's public Gamma API.
2. Maps each outcome to a pre-defined equity basket.
3. Blends the baskets by their probabilities, with a cash floor.
4. Creates a sandbox customer account on Alpaca's Broker API.
5. Funds it from the sandbox firm account via JNLC.
6. Pushes the portfolio to Alpaca's Rebalancing API.
7. Subscribes the account, which triggers the initial rebalance.
8. Polls and prints the resulting orders.

Single Python script. About 400 lines across four modules. No UI: the
Alpaca Broker Dashboard is the visual layer.

## Example output

```
[1/6] Fetching live Polymarket odds...
      Q: Will Bitcoin reach $85,000 in May?
         YES=49.5%  NO=50.5%

[2/6] Computing probability-weighted target portfolio...
     SPY  19.19%
     TLT  14.39%
    COIN  14.11%
    MSTR  14.11%
     GLD   9.59%
    MARA   9.41%
    RIOT   9.41%
    CASH   5.00%
     XLU   4.80%
```

YES basket maps to a crypto-correlated equity basket (COIN, MSTR, MARA,
RIOT). NO basket maps to defensives (SPY, TLT, GLD, XLU). Blended by
the live market probability, the resulting portfolio is split roughly
evenly because the market is currently roughly 50/50.

If the Polymarket odds shifted to YES=70/NO=30 tomorrow, COIN/MSTR/MARA/RIOT
would all roughly double in target weight.

## Setup

```
pip install -r requirements.txt
python main.py
```

Create a `.env` file in the project root with your sandbox credentials:

```
ALPACA_API_KEY=...
ALPACA_API_SECRET=...
ALPACA_BASE_URL=https://broker-api.sandbox.alpaca.markets
ALPACA_FIRM_ACCOUNT_ID=...   # the pre-funded firm account, from the dashboard
```

Get a sandbox key at `broker-app.alpaca.markets`. The sandbox includes
a $50,000 pre-funded firm account that we journal from.

## Architecture

```
polymarket.py   live odds from gamma-api.polymarket.com
baskets.py      thesis-to-symbol mapping, weight math, cash floor
broker.py       Alpaca Broker API client (accounts, journals, rebalancing)
main.py         orchestrator
```

## Product observations from building this

Each of these is a real conversation about where the Rebalancing API
could grow.

1. **Cooldown is human-paced.** `cooldown_days` minimum is 1. Signal-
   driven rebalancing wants sub-daily cadence. A "tactical mode" with
   shorter cooldown, distinct from the strategic/calendar model, is a
   real product opportunity.

2. **Drift bands are symbol-level.** For a thesis-driven portfolio,
   meaningful drift is at the basket or theme level, not the leg. A
   higher-level abstraction would map cleanly to how this kind of
   product wants to think.

3. **No webhook-in primitive.** The signal source has to be polled by
   the customer, who then PATCHes the portfolio and triggers a run.
   Webhook-driven rebalancing as a first-class feature would unlock a
   lot of signal-driven products.

4. **Minimum $1 per asset.** For probability-weighted allocations
   where some legs go below the threshold, the current behavior is
   partial rebalance. A "round down to zero below threshold"
   instruction would be useful, as would a "round up to the
   threshold" inverse.

5. **Manual runs blocked on subscribed accounts.** Reasonable for
   safety, but creates an awkward unsubscribe/run/resubscribe dance
   for any product that wants to combine automated and event-driven
   rebalancing.

6. **Composability question.** Could the Rebalancing API support a
   "compute target weights from this callback URL" mode where the
   customer hosts the signal logic and Alpaca polls it?

## Out of scope

- Multi-outcome (non-binary) markets
- Real-time websocket signal updates
- Multi-account / advisor fan-out
- Production KYC flow (we use sandbox placeholder data)
- Error handling beyond the happy path
- Real money
