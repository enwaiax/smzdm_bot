"""Shared channel contract and bounded, secret-safe HTTP delivery."""

from dataclasses import dataclass
from typing import Protocol

import httpx

from smzdm_bot.config import NotificationConfig


@dataclass(frozen=True)
class NotificationResult:
    channel: str
    success: bool
    message: str = "ok"
    delivered: int = 0
    total: int = 1


class NotificationChannel(Protocol):
    name: str

    def enabled(self) -> bool: ...
    def send(self, title: str, content: str) -> NotificationResult: ...


class Channel:
    """Common enable policy and HTTP handling, independent of account tasks."""

    name: str = ""
    credential_fields: tuple[str, ...] = ()
    response_codes: tuple[str, ...] = ("code",)
    success_code: int | bool = 0

    def __init__(self, config: NotificationConfig) -> None:
        self.config = config

    def configured(self) -> bool:
        return all(str(getattr(self.config, name)).strip() for name in self.credential_fields)

    def enabled(self) -> bool:
        explicit = getattr(self.config, f"notify_{self.name}_enabled", None)
        return self.config.notify_enabled and (self.configured() if explicit is None else explicit)

    def post(
        self,
        url: str,
        *,
        json: dict[str, object] | None = None,
        data: dict[str, str] | None = None,
    ) -> NotificationResult:
        if not self.configured():
            return NotificationResult(self.name, False, "missing credentials")
        try:
            kwargs = {"json": json} if json is not None else {"data": data}
            response = httpx.post(url, timeout=self.config.notify_timeout, **kwargs)
            if not 200 <= response.status_code < 300:
                return NotificationResult(self.name, False, f"HTTP {response.status_code}")
            payload = response.json()
            if not isinstance(payload, dict):
                return NotificationResult(self.name, False, "invalid JSON object")
            codes = [payload[key] for key in self.response_codes if key in payload]
            if not codes:
                return NotificationResult(self.name, False, "missing business status")
            if self.success_code is True:
                success = all(code is True for code in codes)
            else:
                success = all(
                    not isinstance(code, bool) and str(code) == str(self.success_code)
                    for code in codes
                )
            if success:
                return NotificationResult(self.name, True, delivered=1)
            # Never echo response messages or arbitrary status strings: either can
            # contain credentials, request bodies or full webhook URLs.
            code = next((c for c in codes if type(c) is int), None)
            message = f"business error code={code}" if code is not None else "business error"
            return NotificationResult(self.name, False, message)
        except httpx.TimeoutException:
            return NotificationResult(self.name, False, "request timeout")
        except httpx.RequestError:
            return NotificationResult(self.name, False, "network error")
        except ValueError:
            return NotificationResult(self.name, False, "invalid JSON or request")
        except Exception:
            return NotificationResult(self.name, False, "delivery exception")
