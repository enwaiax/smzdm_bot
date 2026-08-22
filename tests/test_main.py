import json
from typing import Any

import pytest

from smzdm_bot.config import Settings
from smzdm_bot.main import run_all_accounts
from smzdm_bot.models import AccountTaskResult


def test_multi_user_results_and_notification_use_cookie_user_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_notification: dict[str, Any] = {}
    shared_cookie = "sess=shared-session; smzdm_id=10001"
    settings = Settings(
        users_json=json.dumps(
            [
                {"name": "账号 A", "cookie": shared_cookie},
                {"name": "账号 B", "cookie": shared_cookie},
            ]
        ),
        bark_push_url="https://api.day.app/device-key",
        _env_file=None,
    )

    monkeypatch.setattr(
        "smzdm_bot.main.run_account_tasks",
        lambda _user_config, _task_policy: AccountTaskResult(user_id="10001", success=True),
    )
    monkeypatch.setattr(
        "smzdm_bot.main.send_configured_notifications",
        lambda _config, **notification: captured_notification.update(notification),
    )

    task_results = run_all_accounts(settings)

    assert [result.user_id for result in task_results] == ["10001", "10001"]
    assert captured_notification["title"] == "什么值得买签到 (2/2)"
    assert captured_notification["content"].count("📋 用户 ID: 10001") == 2
