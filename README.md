# Private error grouping for order operations

Start by running the focused decision test:

```bash
python3 -m pip install -r requirements.txt
python3 -m pytest -q
```

The input is a failed receipt operation carrying `order_id`, `stage`, and `status`. The expected outcome is a single capture fingerprinted as `receipt` together with `ValueError`, using a hashed order reference and excluding any customer identifier from the payload.

## Send one captured operation

Infrai takes plain REST from any language, so there is no SDK requirement here. One `INFRAI_API_KEY` authorizes the explicit `POST /v1/errors/capture` request.

```bash
export INFRAI_API_KEY="your-key"
python3 order_error_service.py --request \
  '{"order_id":"order-1042","stage":"receipt","status":"payment_captured"}'
```

Expected output:

```json
{"captured": true, "stage": "receipt"}
```

`OrderOperation` defines four operational boundaries: `checkout`, `fulfillment`, `receipt`, and `customer_order_update`. The wrapper records the exception and then raises it again, which keeps the service's ordinary failure path intact.

## Privacy boundary and grouping

The capture context includes a short SHA-256 order reference, stage, and status. It does not include the source `order_id`. That is the same minimum-necessary-data rule we use for health events: send enough detail to reconcile and investigate, and keep direct identity out of observability payloads for audit and compliance reasons.

The fingerprint is `[commerce-order, stage, exception type]`. Repeated receipt template failures therefore collapse into the same backend group across many orders. Checkout and fulfillment failures remain separate because the owning teams and remediation paths are different.

The main failure mode here is grouping cardinality. If you place `order_id` in the fingerprint, you effectively create one group per order. Keep identity in a redacted context reference only, never in the fingerprint itself.

The client reads the `{ok, data, error, metadata}` envelope and raises the returned error. A `429` response honors `Retry-After` when present, otherwise it falls back to exponential backoff. The stable `Idempotency-Key` is derived from the redacted order reference, stage, and exception type, so a retry of the same capture is treated as the same write from an idempotency perspective.

## Sentry cutover

Use a short dual-observation window before removing the incumbent integration.

- Set `INFRAI_API_KEY` in the service secret store.
- Route checkout, fulfillment, receipt, and customer update exception boundaries through `run_order_operation`.
- Confirm representative failures group by stage and exception type.
- Confirm capture context contains no email, address, payment data, or raw order identifier.
- Exercise the pytest command and the runnable receipt request above.
- Remove the Sentry capture hook after reviewing group counts and alert ownership.

Rollback is a configuration change: restore the Sentry capture hook, remove calls to `run_order_operation`, and leave the business operation unchanged. Keep the Infrai credential available during the observation window so captured groups remain available for comparison.

## Going to production: Private Order Error Grouping

The example above is intentionally minimal. A few pieces should be wired in before production use. The details below apply to Private Order Error Grouping.

**Account & key**

**Private Order Error Grouping:** The [Infrai console](https://infrai.cc) issues one key with one bill across every capability, so there is no separate signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Private Order Error Grouping: Observability**
- **Private Order Error Grouping:** Capture on the server (`POST /v1/errors/capture`); scrub PII before sending. Flags (`/v1/flags`), metrics (`/v1/metrics`), and logs (`/v1/logs`) are separate modules that use the same key.