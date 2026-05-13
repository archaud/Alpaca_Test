# alpaca_test

A prototype that drives an Alpaca brokerage portfolio off live Polymarket
prediction-market odds. Built in a few hours to ground a product
conversation about signal-driven rebalancing.

The script does not currently run end-to-end: `POST /v1/rebalancing/portfolios`
returns `403 insufficient_permission` even after the API key is assigned
Rebalancing scope explicitly. See [ADDITIONAL_FINDINGS.md](ADDITIONAL_FINDINGS.md)
for the full reproduction and diagnostic trail.

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
2. Maps each outcome to a pre-defined equity basket and blends them by
   their probabilities, with a cash floor.
3. Creates a sandbox customer account on Alpaca's Broker API.
4. Funds it from the sandbox firm account via JNLC.
5. Pushes the probability-weighted portfolio to Alpaca's Rebalancing API.
6. Subscribes the account (triggers the initial rebalance), then polls
   and prints the resulting orders.

These map 1:1 to the `[1/6]`–`[6/6]` steps the script prints.

Single Python script, roughly 600 lines across four modules. No UI: the
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

Requires Python 3.8+.

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

Get a sandbox key at `https://broker-app.alpaca.markets`. The sandbox
includes a $50,000 pre-funded firm account that we journal from.

## Architecture

```
polymarket.py   live odds from gamma-api.polymarket.com
baskets.py      thesis-to-symbol mapping, weight math, cash floor
broker.py       Alpaca Broker API client (accounts, journals, rebalancing)
main.py         orchestrator
```

