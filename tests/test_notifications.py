"""Notification compatibility, protocol, orchestration and secret-safety regressions."""

import json
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from loguru import logger
from pydantic import ValidationError

from smzdm_bot.config import NotificationConfig, Settings
from smzdm_bot.main import determine_exit_code, run_all_accounts
from smzdm_bot.models import AccountTaskResult
from smzdm_bot.notifications.channels import (
    BarkChannel,
    DingTalkChannel,
    FeishuChannel,
    bark_targets,
)
from smzdm_bot.notifications.manager import CHANNEL_REGISTRY, NotificationManager
from smzdm_bot.notifications.signatures import dingtalk_signature, feishu_signature


@pytest.fixture(autouse=True)
def isolate_environment(monkeypatch):
    import os

    for name in os.environ:
        if name.startswith("SMZDM_"):
            monkeypatch.delenv(name)

    def no_network(*args, **kwargs):
        raise AssertionError("Unexpected real HTTP request")

    monkeypatch.setattr("httpx.post", no_network)


@pytest.fixture
def credentials():
    return dict(
        bark_push_url="test-bark",
        feishu_webhook="https://example.test/feishu",
        dingtalk_webhook="https://example.test/dingtalk?access_token=test-token",
        telegram_bot_token="test-telegram",
        telegram_chat_id="test-chat",
        wecom_webhook="https://example.test/wecom",
        push_plus_token="test-pushplus",
        server_chan_key="test-serverchan",
    )


@pytest.mark.parametrize("name", list(CHANNEL_REGISTRY))
def test_legacy_enable_and_explicit_override(name, credentials, monkeypatch):
    assert CHANNEL_REGISTRY[name](NotificationConfig(**credentials)).enabled()
    monkeypatch.setenv(f"SMZDM_NOTIFY_{name.upper()}_ENABLED", "false")
    config = Settings(**credentials, _env_file=None).build_notification_config()
    assert not CHANNEL_REGISTRY[name](config).enabled()
    monkeypatch.setenv(f"SMZDM_NOTIFY_{name.upper()}_ENABLED", "true")
    config = Settings(**credentials, _env_file=None).build_notification_config()
    assert CHANNEL_REGISTRY[name](config).enabled()


def test_dotenv_options_and_environment_precedence(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        "SMZDM_NOTIFY_ENABLED=false\nSMZDM_NOTIFY_CHANNELS=feishu,bark,dingtalk\n"
        "SMZDM_NOTIFY_TIMEOUT=4.5\nSMZDM_NOTIFY_ON_SUCCESS=false\n"
        "SMZDM_NOTIFY_ON_FAILURE=true\nSMZDM_FEISHU_SECRET=test-secret\n"
        "SMZDM_DINGTALK_SECRET=test-secret\n"
    )
    config = Settings(_env_file=env).build_notification_config()
    assert not config.notify_enabled
    assert config.notify_timeout == 4.5
    assert not config.notify_on_success
    assert config.notify_on_failure
    assert config.feishu_secret == config.dingtalk_secret == "test-secret"
    assert NotificationManager(config).channel_names() == ["feishu", "bark", "dingtalk"]
    monkeypatch.setenv("SMZDM_NOTIFY_ENABLED", "true")
    assert Settings(_env_file=env).notify_enabled


@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan")])
def test_timeout_must_be_positive_finite(value):
    with pytest.raises(ValidationError):
        NotificationConfig(notify_timeout=value)


@pytest.mark.parametrize("raw", ["a,b,c", "a, b ,,c,"])
def test_bark_parses_targets(raw):
    assert bark_targets(raw) == ["a", "b", "c"]


def test_serial_bark_partial_and_channel_order(monkeypatch, credentials):
    calls = []

    def post(url, **kwargs):
        calls.append(url)
        assert kwargs["timeout"] == 3
        if url.endswith("/b"):
            raise httpx.ReadTimeout("SECRET URL must not leak")
        return httpx.Response(200, json={"code": 200 if "day.app" in url else 0, "errcode": 0})

    monkeypatch.setattr("httpx.post", post)
    config = NotificationConfig(
        **{**credentials, "bark_push_url": "a, b,,c,"},
        notify_timeout=3,
        notify_channels="feishu,bark,dingtalk",
    )
    results = NotificationManager(config).send("title", "content")
    assert calls == [
        credentials["feishu_webhook"],
        "https://api.day.app/a",
        "https://api.day.app/b",
        "https://api.day.app/c",
        credentials["dingtalk_webhook"],
    ]
    assert [r.channel for r in results] == ["feishu", "bark", "dingtalk"]
    assert results[1].message == "partial success (2/3)"
    assert results[1].delivered == 2 and not results[1].success
    assert results[-1].success


def test_manager_isolates_unexpected_channel_exception(monkeypatch, credentials):
    calls = []

    def broken(self, title, content):
        calls.append("feishu")
        raise RuntimeError("test-secret")

    def post(url, **kwargs):
        calls.append("bark" if "day.app" in url else "dingtalk")
        return httpx.Response(200, json={"code": 200, "errcode": 0})

    monkeypatch.setattr("httpx.post", post)
    monkeypatch.setattr(FeishuChannel, "send", broken)
    results = NotificationManager(
        NotificationConfig(**credentials, notify_channels="bark,feishu,dingtalk")
    ).send("title", "content")
    assert calls == ["bark", "feishu", "dingtalk"]
    assert [r.success for r in results] == [True, False, True]


def test_master_order_filter_unknown_and_duplicates(credentials):
    config = NotificationConfig(**credentials, notify_channels=" FEISHU,abc,bark,feishu")
    assert [c.name for c in NotificationManager(config).enabled_channels()] == ["feishu", "bark"]
    config.notify_enabled = False
    assert NotificationManager(config).send("title", "content") == []


def test_default_order_and_disabled_credentials(credentials):
    config = NotificationConfig(**credentials, notify_channels="")
    assert [c.name for c in NotificationManager(config).enabled_channels()] == [
        "bark",
        "feishu",
        "dingtalk",
        "telegram",
        "wecom",
        "pushplus",
        "serverchan",
    ]
    config.notify_bark_enabled = False
    assert "bark" not in [c.name for c in NotificationManager(config).enabled_channels()]
    assert NotificationManager(NotificationConfig()).enabled_channels() == []


def test_explicit_enabled_missing_credentials():
    results = NotificationManager(NotificationConfig(notify_feishu_enabled=True)).send("t", "c")
    assert len(results) == 1
    assert not results[0].success
    assert results[0].message == "missing credentials"


@pytest.mark.parametrize(
    ("channel", "payload", "expected"),
    [
        ("dingtalk", {"errcode": 0, "errmsg": "ok"}, True),
        ("dingtalk", {"errcode": 310000, "errmsg": "keywords not in content"}, False),
        ("feishu", {"code": 0}, True),
        ("feishu", {"StatusCode": 0}, True),
        ("feishu", {"code": 19021}, False),
        ("feishu", {"StatusCode": 1}, False),
        ("feishu", {"code": 0, "StatusCode": 1}, False),
        ("feishu", {}, False),
        ("feishu", [], False),
        ("bark", {"code": 200}, True),
        ("pushplus", {"code": 200}, True),
        ("serverchan", {"code": 0}, True),
        ("wecom", {"errcode": 0}, True),
        ("telegram", {"ok": True}, True),
        ("telegram", {"ok": "false"}, False),
    ],
)
def test_business_responses(channel, payload, expected, credentials, monkeypatch):
    monkeypatch.setattr("httpx.post", lambda *a, **k: httpx.Response(200, json=payload))
    result = CHANNEL_REGISTRY[channel](NotificationConfig(**credentials)).send("t", "c")
    assert result.success is expected


@pytest.mark.parametrize("failure", ["http", "json", "connect", "read", "network", "business"])
def test_failures_never_log_secrets(failure, credentials, monkeypatch):
    secret = "sensitive-cookie-and-webhook-token"
    logs = []
    sink = logger.add(lambda message: logs.append(str(message)))

    def post(url, **kwargs):
        if failure == "http":
            return httpx.Response(400, text=secret)
        if failure == "json":
            return httpx.Response(200, text=secret)
        if failure == "connect":
            raise httpx.ConnectTimeout(secret)
        if failure == "read":
            raise httpx.ReadTimeout(secret)
        if failure == "network":
            raise httpx.ConnectError(secret)
        return httpx.Response(200, json={"errcode": secret, "errmsg": secret})

    monkeypatch.setattr("httpx.post", post)
    try:
        config = NotificationConfig(**credentials, notify_channels="dingtalk")
        config.dingtalk_webhook = f"https://example.test/?access_token={secret}"
        result = NotificationManager(config).send(secret, secret)[0]
        assert not result.success
        assert secret not in result.message
        assert secret not in "".join(logs)
    finally:
        logger.remove(sink)


def test_signatures_match_fixed_vectors():
    assert dingtalk_signature("test-secret", 1700000000000) == (
        "BYMqUCZnSqbfPf1GCfZftO7Rg2g6P+Rp3/4+bLNtSGA="
    )
    assert feishu_signature("test-secret", 1700000000) == (
        "mbm4Y4oluIPQ00qlBIhX8vAZ0EKv3nw0LuTb91jPL84="
    )


@pytest.mark.parametrize("signed", [True, False])
def test_webhook_payloads_and_url_encoding(signed, monkeypatch, credentials):
    calls = []
    monkeypatch.setattr("smzdm_bot.notifications.channels.time.time", lambda: 1700000000)

    def post(url, **kwargs):
        calls.append((url, kwargs["json"]))
        return httpx.Response(200, json={"code": 0, "errcode": 0})

    monkeypatch.setattr("httpx.post", post)
    config = NotificationConfig(
        **credentials,
        feishu_secret="test-secret" if signed else "",
        dingtalk_secret="test-secret" if signed else "",
    )
    assert FeishuChannel(config).send("title", "content").success
    assert DingTalkChannel(config).send("title", "content").success
    assert calls[0][1]["content"] == {"text": "title\ncontent"}
    assert calls[1][1] == {"msgtype": "text", "text": {"content": "title\ncontent"}}
    query = parse_qs(urlsplit(calls[1][0]).query)
    assert query["access_token"] == ["test-token"]
    if signed:
        assert calls[0][1]["timestamp"] == "1700000000"
        assert calls[0][1]["sign"] == feishu_signature("test-secret", 1700000000)
        assert query["timestamp"] == ["1700000000000"]
        assert query["sign"] == [dingtalk_signature("test-secret", 1700000000000)]
        assert "%2B" in calls[1][0] and "%3D" in calls[1][0]
    else:
        assert "sign" not in calls[0][1]
        assert "sign" not in query


@pytest.mark.parametrize(
    ("success_switch", "failure_switch", "outcomes", "sends"),
    [
        (True, True, [True, True], True),
        (False, True, [True, True], False),
        (False, True, [True, False], True),
        (True, False, [True, False], False),
        (False, False, [False, False], False),
        (True, False, [True, True], True),
    ],
)
def test_account_notification_policy(success_switch, failure_switch, outcomes, sends, monkeypatch):
    results = iter(AccountTaskResult(user_id=str(i), success=s) for i, s in enumerate(outcomes))
    delivered = []
    monkeypatch.setattr("smzdm_bot.main.run_account_tasks", lambda *args: next(results))
    monkeypatch.setattr(
        "smzdm_bot.main.send_configured_notifications", lambda *a, **k: delivered.append(k)
    )
    settings = Settings(
        _env_file=None,
        users_json=json.dumps([{"cookie": "sess=test"}] * 2),
        notify_on_success=success_switch,
        notify_on_failure=failure_switch,
    )
    actual = run_all_accounts(settings)
    assert bool(delivered) is sends
    assert [r.success for r in actual] == outcomes
    if sends:
        assert delivered[0]["content"].count("📋 用户 ID:") == 2


def test_notification_failure_does_not_change_exit_code(monkeypatch):
    monkeypatch.setattr(
        "smzdm_bot.main.run_account_tasks",
        lambda *a: AccountTaskResult(user_id="test", success=True),
    )

    def broken(*a, **k):
        raise RuntimeError("secret")

    monkeypatch.setattr("smzdm_bot.main.send_configured_notifications", broken)
    assert determine_exit_code(run_all_accounts(Settings(_env_file=None, cookie="sess=test"))) == 0


def test_cli_reflects_effective_switches_without_credentials(monkeypatch, credentials):
    from typer.testing import CliRunner

    from smzdm_bot.cli import app

    settings = Settings(
        **credentials,
        _env_file=None,
        cookie="sess=synthetic-cookie",
        notify_channels="feishu,bark",
        notify_bark_enabled=False,
    )
    monkeypatch.setattr("smzdm_bot.config.get_settings", lambda: settings)
    output = CliRunner().invoke(app, ["config"])
    assert output.exit_code == 0
    lines = output.output.splitlines()
    assert any("feishu" in line and "Enabled" in line for line in lines)
    assert any("bark" in line and "Disabled" in line for line in lines)
    for secret in credentials.values():
        assert secret not in output.output
    assert "synthetic-cookie" not in output.output


def test_bark_unexpected_exception_continues_next_target(monkeypatch):
    calls = []
    from smzdm_bot.notifications.base import NotificationResult

    def post(self, url, **kwargs):
        calls.append(url)
        if len(calls) == 1:
            raise RuntimeError("secret")
        return NotificationResult("bark", True, delivered=1)

    monkeypatch.setattr(BarkChannel, "post", post)
    result = BarkChannel(NotificationConfig(bark_push_url="a,b")).send("t", "c")
    assert len(calls) == 2
    assert result.delivered == 1 and result.total == 2


def test_legacy_helpers_keep_protocols_and_return_types(monkeypatch):
    from smzdm_bot.notify import (
        send_push_plus_notification,
        send_server_chan_notification,
        send_telegram_notification,
        send_wecom_notification,
    )

    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        payload = (
            {"ok": True}
            if "/bot" in url
            else {"errcode": 0}
            if "wecom" in url
            else {"code": 0 if "sctapi" in url else 200}
        )
        return httpx.Response(200, json=payload)

    monkeypatch.setattr("httpx.post", post)
    assert send_push_plus_notification("test-push", "title", "content") is True
    assert send_server_chan_notification("test-server", "title", "content") is True
    assert send_wecom_notification("https://example.test/wecom", "title", "content") is True
    assert (
        send_telegram_notification(
            "test-bot", "test-chat", "title", "content", "https://example.test/proxy/"
        )
        is True
    )
    assert calls[0][1]["json"]["template"] == "html"
    assert calls[1][1]["data"] == {"title": "title", "desp": "content"}
    assert calls[3][0] == "https://example.test/proxy/bottest-bot/sendMessage"
    assert calls[3][1]["json"]["parse_mode"] == "Markdown"


def test_unknown_channel_warning_and_safe_config_repr(credentials):
    logs = []
    sink = logger.add(lambda message: logs.append(str(message)))
    try:
        config = NotificationConfig(**credentials, notify_channels="bark,abc,feishu")
        NotificationManager(config).enabled_channels()
        assert "Unknown notification channel: abc" in "".join(logs)
        assert all(value not in repr(config) for value in credentials.values())
    finally:
        logger.remove(sink)
