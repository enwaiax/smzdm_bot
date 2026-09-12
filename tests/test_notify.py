from types import SimpleNamespace
from typing import Any

import pytest

from smzdm_bot.config import NotificationConfig
from smzdm_bot.notify import send_bark_notification, send_configured_notifications


def test_send_bark_notification_uses_configured_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_request: dict[str, Any] = {}

    def fake_post(
        request_url: str,
        *,
        json: dict,
        timeout: float,
    ) -> SimpleNamespace:
        captured_request.update(
            {
                "url": request_url,
                "json": json,
                "timeout": timeout,
            }
        )
        return SimpleNamespace(status_code=200, json=lambda: {"code": 200})

    monkeypatch.setattr("smzdm_bot.notifications.base.httpx.post", fake_post)

    succeeded = send_bark_notification(
        "https://api.day.app/device-key",
        "SMZDM",
        "Task completed",
    )

    assert succeeded is True
    assert captured_request["url"] == "https://api.day.app/device-key"
    assert captured_request["json"] == {
        "title": "SMZDM",
        "body": "Task completed",
        "group": "SMZDM Bot",
    }


def test_configured_notifications_include_bark(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delivered_notifications: list[tuple[str, str, str]] = []

    from smzdm_bot.notifications.base import NotificationResult

    def fake_send_bark(self, title: str, content: str) -> NotificationResult:
        delivered_notifications.append((self.config.bark_push_url, title, content))
        return NotificationResult("bark", True, delivered=1)

    monkeypatch.setattr(
        "smzdm_bot.notifications.channels.BarkChannel.send",
        fake_send_bark,
    )

    delivery_count = send_configured_notifications(
        NotificationConfig(bark_push_url="https://api.day.app/device-key"),
        title="SMZDM",
        content="Task completed",
    )

    assert delivery_count == 1
    assert delivered_notifications == [
        ("https://api.day.app/device-key", "SMZDM", "Task completed")
    ]
