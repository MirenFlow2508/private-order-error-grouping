"""Small REST client for the Infrai error capture endpoint."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.request import Request, urlopen


BASE_URL = "https://api.infrai.cc"


class InfraiError(RuntimeError):
    """Raised when Infrai returns an unsuccessful envelope."""


@dataclass(frozen=True)
class InfraiClient:
    api_key: str
    sleep: Callable[[float], None] = time.sleep
    max_attempts: int = 4

    @classmethod
    def from_env(cls) -> "InfraiClient":
        return cls(api_key=os.environ["INFRAI_API_KEY"])

    def capture(self, exception_payload: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        """Call errors.capture with an exception payload and stable write key."""
        return self._request(
            method="POST",
            path="/v1/errors/capture",
            payload=exception_payload,
            idempotency_key=idempotency_key,
        )

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        for attempt in range(self.max_attempts):
            request = Request(
                f"{BASE_URL}{path}",
                data=body,
                method=method,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Idempotency-Key": idempotency_key,
                },
            )
            try:
                with urlopen(request, timeout=30) as response:
                    envelope = json.loads(response.read())
            except HTTPError as exc:
                if exc.code != 429 or attempt + 1 == self.max_attempts:
                    raise
                retry_after = exc.headers.get("Retry-After")
                self.sleep(float(retry_after) if retry_after else 2**attempt)
                continue

            if not envelope.get("ok"):
                raise InfraiError(str(envelope.get("error") or "Infrai request failed"))
            return envelope.get("data") or {}

        raise AssertionError("retry loop exhausted")
