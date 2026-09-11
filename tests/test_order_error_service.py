from order_error_service import OrderOperation, OrderStage, capture_order_failure


class RecordingClient:
    def __init__(self) -> None:
        self.calls = []

    def capture(self, payload, idempotency_key):
        self.calls.append((payload, idempotency_key))
        return {"event_id": "evt_example"}


def test_receipt_failures_group_without_customer_identifier() -> None:
    client = RecordingClient()
    operation = OrderOperation(
        order_id="customer@example.test/order-1042",
        stage=OrderStage.RECEIPT,
        status="payment_captured",
    )

    result = capture_order_failure(operation, ValueError("template missing"), client)

    payload, write_key = client.calls[0]
    assert result == {"event_id": "evt_example"}
    assert payload["fingerprint"] == ["commerce-order", "receipt", "ValueError"]
    assert payload["context"]["status"] == "payment_captured"
    assert "customer@example.test" not in repr(payload)
    assert write_key.startswith("order-error:")
