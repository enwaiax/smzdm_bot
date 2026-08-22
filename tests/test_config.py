import pytest
from pydantic import ValidationError

from smzdm_bot.config import Settings
from smzdm_bot.exceptions import ConfigurationError


def test_single_user_configuration() -> None:
    settings = Settings(
        cookie="sess=session; smzdm_id=123; device_id=device;",
        security_key="configured-sk",
        _env_file=None,
    )

    user_configs = settings.get_user_configs()

    assert len(user_configs) == 1
    assert user_configs[0].account_label == "default"
    assert user_configs[0].security_key == "configured-sk"


def test_multi_user_configuration_takes_precedence() -> None:
    settings = Settings(
        cookie="single-user-cookie",
        users_json=(
            '[{"account_label":"first","cookie":"first-cookie"},{"cookie":"second-cookie"}]'
        ),
        _env_file=None,
    )

    user_configs = settings.get_user_configs()

    assert [user_config.account_label for user_config in user_configs] == [
        "first",
        "User2",
    ]


@pytest.mark.parametrize(
    "users_json",
    [
        '{"cookie":"not-an-array"}',
        '[{"name":"missing-cookie"}]',
    ],
)
def test_invalid_multi_user_shape_is_rejected(users_json: str) -> None:
    settings = Settings(users_json=users_json, _env_file=None)

    with pytest.raises(ConfigurationError):
        settings.get_user_configs()


def test_invalid_multi_user_json_does_not_echo_secret() -> None:
    secret = "secret-cookie"
    settings = Settings(users_json=f"[{secret}", _env_file=None)

    with pytest.raises(ConfigurationError) as error:
        settings.get_user_configs()

    assert secret not in str(error.value)


@pytest.mark.parametrize(
    ("settings_field", "invalid_value"),
    [
        ("schedule_hour", 24),
        ("schedule_minute", 60),
    ],
)
def test_schedule_fields_are_bounded(settings_field: str, invalid_value: int) -> None:
    with pytest.raises(ValidationError):
        Settings(**{settings_field: invalid_value, "_env_file": None})


def test_timezone_must_be_valid() -> None:
    with pytest.raises(ValidationError):
        Settings(timezone="Not/A-Timezone", _env_file=None)


def test_optional_task_policy_defaults_are_explicit() -> None:
    task_policy = Settings(_env_file=None).build_task_policy()

    assert task_policy.enable_follow_tasks is True
    assert task_policy.enable_testing_tasks is False
    assert task_policy.enable_activity_reward_claims is True


def test_environment_names_map_to_descriptive_setting_fields(monkeypatch) -> None:
    monkeypatch.setenv("SMZDM_BARK_PUSH", "https://api.day.app/device-key")
    monkeypatch.setenv("SMZDM_SK", "configured-key")
    monkeypatch.setenv("SMZDM_SC_KEY", "server-chan-key")
    monkeypatch.setenv("SMZDM_TG_BOT_TOKEN", "telegram-token")
    monkeypatch.setenv("SMZDM_TG_USER_ID", "telegram-chat")
    monkeypatch.setenv("SMZDM_TG_API_BASE", "https://telegram.example")
    monkeypatch.setenv("SMZDM_SCH_HOUR", "9")
    monkeypatch.setenv("SMZDM_SCH_MINUTE", "30")

    settings = Settings(_env_file=None)

    assert settings.bark_push_url == "https://api.day.app/device-key"
    assert settings.security_key == "configured-key"
    assert settings.server_chan_key == "server-chan-key"
    assert settings.telegram_bot_token == "telegram-token"
    assert settings.telegram_chat_id == "telegram-chat"
    assert settings.telegram_api_base_url == "https://telegram.example"
    assert settings.schedule_hour == 9
    assert settings.schedule_minute == 30
