"""Alpaca Broker API client (sandbox).

Wraps the endpoints needed for the end-to-end demo:

  1. Create a customer account            POST /v1/accounts
  2. Find the firm account                GET  /v1/accounts            (filtered)
  3. Journal cash from firm -> customer   POST /v1/journals
  4. Create a portfolio                   POST /v1/beta/rebalancing/portfolios
  5. Subscribe account to portfolio       POST /v1/beta/rebalancing/subscriptions
  6. List runs for an account             GET  /v1/beta/rebalancing/runs
  7. Get the account snapshot             GET  /v1/trading/accounts/{id}/account

Auth is HTTP Basic with API_KEY:API_SECRET.
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any, Dict, List, Optional

import requests
from requests.auth import HTTPBasicAuth


class AlpacaError(Exception):
    """Raised when the API returns a non-2xx response."""


class BrokerClient:
    """Thin Broker API wrapper. One client per sandbox tenant."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or os.environ["ALPACA_API_KEY"]
        self.api_secret = api_secret or os.environ["ALPACA_API_SECRET"]
        self.base_url = (
            base_url
            or os.environ.get("ALPACA_BASE_URL")
            or "https://broker-api.sandbox.alpaca.markets"
        ).rstrip("/")
        self.auth = HTTPBasicAuth(self.api_key, self.api_secret)

    # ---- internals ------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self.base_url}{path}"
        resp = requests.request(method, url, auth=self.auth, timeout=20, **kwargs)
        if not resp.ok:
            raise AlpacaError(
                f"{method} {path} -> {resp.status_code}\n{resp.text}"
            )
        if resp.status_code == 204 or not resp.text:
            return None
        return resp.json()

    # ---- 1. Accounts ----------------------------------------------------

    def create_customer_account(self) -> Dict[str, Any]:
        """Create a sandbox customer account with placeholder data.

        Returns the created account dict; .['id'] is the account_id.
        Email is randomized so this is re-runnable.
        """
        suffix = uuid.uuid4().hex[:8]
        payload = {
            "contact": {
                "email_address": f"alpaca_test.demo.{suffix}@example.com",
                "phone_number": "555-555-1234",
                "street_address": ["20 N San Mateo Dr"],
                "city": "San Mateo",
                "state": "CA",
                "postal_code": "94401",
                "country": "USA",
            },
            "identity": {
                "given_name": "Demo",
                "family_name": f"User{suffix}",
                "date_of_birth": "1990-01-15",
                "tax_id_type": "USA_SSN",
                "tax_id": "555-12-3456",
                "country_of_citizenship": "USA",
                "country_of_birth": "USA",
                "country_of_tax_residence": "USA",
                "funding_source": ["employment_income"],
            },
            "disclosures": {
                "is_control_person": False,
                "is_affiliated_exchange_or_finra": False,
                "is_politically_exposed": False,
                "immediate_family_exposed": False,
            },
            "agreements": [
                {
                    "agreement": "customer_agreement",
                    "signed_at": "2026-01-01T12:00:00Z",
                    "ip_address": "127.0.0.1",
                },
                {
                    "agreement": "margin_agreement",
                    "signed_at": "2026-01-01T12:00:00Z",
                    "ip_address": "127.0.0.1",
                },
            ],
        }
        return self._request("POST", "/v1/accounts", json=payload)

    def list_accounts(self) -> List[Dict[str, Any]]:
        return self._request("GET", "/v1/accounts") or []

    def get_firm_account_id(self) -> str:
        """Return the firm (sponsor) account ID.

        If ALPACA_FIRM_ACCOUNT_ID is set in env, use that directly (most reliable).
        Otherwise, fall back to scanning the account list for the pre-funded firm
        account. The fallback heuristic varies between sandbox tenants, so the env
        var override is the recommended approach.
        """
        explicit = os.environ.get("ALPACA_FIRM_ACCOUNT_ID")
        if explicit:
            return explicit

        accounts = self.list_accounts()
        # Firm account is typically ACTIVE and not one of the demo accounts we created.
        for a in accounts:
            status = a.get("status")
            email = (a.get("contact") or {}).get("email_address", "")
            if status == "ACTIVE" and not email.startswith("alpaca_test.demo"):
                return a["id"]

        # Couldn't find it. Dump what we saw to help debug.
        print("\nCould not auto-detect firm account. Accounts visible:")
        for a in accounts:
            print(
                f"  id={a.get('id')}  status={a.get('status')}  "
                f"email={(a.get('contact') or {}).get('email_address')}"
            )
        raise AlpacaError(
            "Set ALPACA_FIRM_ACCOUNT_ID in .env to the firm account ID above."
        )

    def get_account(self, account_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/v1/accounts/{account_id}")

    def wait_for_account_approval(
        self,
        account_id: str,
        timeout_seconds: int = 90,
        poll_interval: int = 2,
    ) -> str:
        """Poll until the account reaches ACTIVE. Returns the final status.

        APPROVED means KYC passed but the brokerage account isn't provisioned
        yet for cash operations. ACTIVE is the state where journals and
        trading can happen.
        """
        deadline = time.time() + timeout_seconds
        last_status = None
        while time.time() < deadline:
            acct = self.get_account(account_id)
            status = acct.get("status")
            if status != last_status:
                print(f"  account status: {status}")
                last_status = status
            if status == "ACTIVE":
                return status
            if status in ("REJECTED", "DISABLED"):
                raise AlpacaError(f"Account {account_id} is {status}, cannot fund")
            time.sleep(poll_interval)
        raise AlpacaError(
            f"Account {account_id} did not reach ACTIVE within {timeout_seconds}s "
            f"(last status: {last_status})"
        )

    def get_trading_account(self, account_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/v1/trading/accounts/{account_id}/account")

    # ---- 2. Funding via journal -----------------------------------------

    def journal_cash(self, from_account: str, to_account: str, amount: float) -> Dict[str, Any]:
        """Move cash between accounts instantly (sandbox firm -> customer)."""
        payload = {
            "from_account": from_account,
            "to_account": to_account,
            "entry_type": "JNLC",
            "amount": str(amount),
        }
        return self._request("POST", "/v1/journals", json=payload)

    # ---- 3. Portfolios + subscriptions ----------------------------------

    @staticmethod
    def _to_weights_payload(weights: Dict[str, float]) -> List[Dict[str, str]]:
        """Convert our {symbol: weight} dict to Alpaca's array format.

        Percent is a string and represents whole-number percentage (e.g. "32.30").
        """
        out: List[Dict[str, str]] = []
        for symbol, w in weights.items():
            pct = f"{w * 100:.2f}"
            if symbol == "CASH":
                out.append({"type": "cash", "percent": pct})
            else:
                out.append({"type": "asset", "symbol": symbol, "percent": pct})
        return out

    def create_portfolio(
        self,
        name: str,
        description: str,
        weights: Dict[str, float],
        cooldown_days: int = 1,
        drift_band_percent: float = 5.0,
    ) -> Dict[str, Any]:
        payload = {
            "name": name,
            "description": description,
            "weights": self._to_weights_payload(weights),
            "cooldown_days": cooldown_days,
            "rebalance_conditions": [
                {
                    "type": "drift_band",
                    "sub_type": "absolute",
                    "percent": str(drift_band_percent),
                }
            ],
        }
        return self._request("POST", "/v1/beta/rebalancing/portfolios", json=payload)

    def subscribe(self, account_id: str, portfolio_id: str) -> Dict[str, Any]:
        """Subscribe account to portfolio. This triggers the initial full rebalance."""
        payload = {"account_id": account_id, "portfolio_id": portfolio_id}
        return self._request("POST", "/v1/beta/rebalancing/subscriptions", json=payload)

    def list_runs(self, account_id: str) -> List[Dict[str, Any]]:
        data = self._request(
            "GET",
            "/v1/beta/rebalancing/runs",
            params={"account_id": account_id},
        )
        if isinstance(data, dict):
            return data.get("runs", [])
        return data or []

    def wait_for_run(
        self,
        account_id: str,
        timeout_seconds: int = 120,
        poll_interval: int = 5,
    ) -> Optional[Dict[str, Any]]:
        """Poll runs until we see one that's completed (or timeout)."""
        deadline = time.time() + timeout_seconds
        last_status = None
        while time.time() < deadline:
            runs = self.list_runs(account_id)
            if runs:
                latest = runs[0]
                status = latest.get("status")
                if status != last_status:
                    print(f"  run status: {status}")
                    last_status = status
                if status and status.startswith("COMPLETED"):
                    return latest
            time.sleep(poll_interval)
        return None