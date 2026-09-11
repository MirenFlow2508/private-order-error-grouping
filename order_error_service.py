"""Capture operational failures without sending customer details."""

from __future__ import annotations

import argparse
import hashlib
import json
import traceback
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, TypeVar

from infrai_errors import InfraiClient


T = TypeVar("T")


class OrderStage(str, Enum):
    CHECKOUT = "checkout"
    FULFILLMENT = "fulfillment"
    RECEIPT = "receipt"
    CUSTOMER_UPDATE = "customer_order_update"


@dataclass(frozen=True)
class OrderOperation:
    order_id: str
    stage: OrderStage
    status: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "OrderOperation":
        return cls(
            order_id=str(value["order_id"]),
            stage=OrderStage(value["stage"]),
            status=str(value["status"]),
        )


def private_order_ref(order_id: str) -> str:
    return hashlib.sha256(order_id.encode("utf-8")).hexdigest()[:16]


def capture_order_failure(
    operation: OrderOperation,
    exc: Exception,
    client: InfraiClient,
) -> dict[str, Any]:
    """Group by stage and exception type, excluding direct customer identifiers."""
    exception_type = type(exc).__name__
    order_ref = private_order_ref(operation.order_id)
    payload = {
        "title": f"Order {operation.stage.value} failed",
        "message": f"{exception_type}: {exc}",
        "level": "error",
        "fingerprint": ["commerce-order", operation.stage.value, exception_type],
        "exception": "".join(traceback.format_exception(exc)),
        "context": {
            "order_ref": order_ref,
            "stage": operation.stage.value,
            "status": operation.status,
        },
    }
    write_key = f"order-error:{order_ref}:{operation.stage.value}:{exception_type}"
    return client.capture(payload, idempotency_key=write_key)


def run_order_operation(
    operation: OrderOperation,
    work: Callable[[], T],
    client: InfraiClient,
) -> T:
    try:
        return work()
    except Exception as exc:
        capture_order_failure(operation, exc, client)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, help="JSON order operation")
    args = parser.parse_args()
    operation = OrderOperation.from_dict(json.loads(args.request))

    def send_receipt() -> None:
        raise ValueError("receipt template is missing")

    try:
        run_order_operation(operation, send_receipt, InfraiClient.from_env())
    except ValueError:
        print(json.dumps({"captured": True, "stage": operation.stage.value}))


if __name__ == "__main__":
    main()
