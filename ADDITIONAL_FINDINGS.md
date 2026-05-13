# Additional Findings

What I hit when actually running the prototype against the Broker API sandbox.
Two distinct platform-side issues, both reproduced extensively, both ultimately
gated on Alpaca-side enablement.


---

## Issue 1: 500 Internal Server Error on `POST /v1/journals` — RESOLVED

Initial state: every attempt to journal cash from the firm/sweep account to
a newly-funded customer account returned:

```
HTTP 500 Internal Server Error
{"code":50010000,"message":"internal server error occurred"}
```

Generic body, no actionable detail. Reproduced across three independent paths:

- Python script with `requests` library
- Raw curl with the exact same payload
- Alpaca's Broker Dashboard, which threw the same 500 with the user-facing
  error string "An error occurred fetching the trading account / Request
  failed with status code 500" on any customer account's overview page


The dashboard reproduction was the diagnostic key. The brokerage account
microservice (identity, KYC, approval status) worked normally throughout;
only operations touching the trading account microservice (journals on the
API side, balance/equity/positions fetch on the dashboard side) failed.
That isolated the issue to a single backend service on this sandbox tenant.

**Resolution:** the 500 no longer occurs — it cleared with no code change
on my side. A subsequent journal succeeded with status `queued` → executed,
and the customer account showed `cash: "50"`, `equity: "50"`, `status: "ACTIVE"`.


---

## Issue 2: 403 on the Rebalancing API — UNRESOLVED

Every request to the Rebalancing API endpoints returns:

```
HTTP 403 Forbidden
{"code":40310000,"message":"insufficient permission"}
```

This holds across:
- `GET /v1/rebalancing/portfolios`
- `POST /v1/rebalancing/portfolios`
- `GET /v1/beta/rebalancing/portfolios`
- `POST /v1/beta/rebalancing/portfolios`


### Reproduction surfaces (5 total)

1. Python script in this repo
2. Raw curl
3. Alpaca's official Postman collection (using their pre-built request body)
4. Broker Dashboard customer account views
5. Alpaca's in-dashboard API testing tool at `API/Devs > Testing`

All five return identical error codes with the same `40310000` code.

### Diagnostic trail to determine root cause

The 403 persisted across multiple credential strategies, each ruling out
a different hypothesis:

**Attempt 1:** Legacy credentials, "Full access" preset (default).
Result: 403.

**Attempt 2:** Legacy credentials regenerated with Custom access controls,
Rebalancing explicitly set to "Read & Write" alongside all other scopes.
The credential settings panel in the dashboard confirms Rebalancing is
granted for both read and write.
Result: 403.

**Attempt 3:** Client Secret credentials with Custom access including
Rebalancing. Tried to bootstrap via OAuth `client_credentials` grant.
Result: `{"error":"unauthorized_client"}` — the grant type isn't enabled
on freshly-generated credentials. So we can't even reach the Rebalancing
endpoints via the modern auth flow.

**Attempt 4:** Dashboard's own API testing tool (session auth, no API keys
involved). Result: 403.

### Conclusion

The Rebalancing API requires Alpaca-side feature flag enablement at the
tenant level, on top of credential scope. This is not discoverable from
the credential UI, the error response, or any documentation I could find.

The credential settings page shows Rebalancing access as granted. The API
rejects requests anyway with no indication that an additional tenant flag
is required.

**Product observation:**
There's a credential-scope-vs-tenant-gating mismatch in the developer
onboarding flow. A scope appears in the UI, can be assigned to credentials,
and shows as granted in the credential settings panel — but the underlying
permission isn't actually conferred without a separate tenant-level
enablement.

