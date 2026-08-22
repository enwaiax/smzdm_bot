from typer.testing import CliRunner

from smzdm_bot.cli import app
from smzdm_bot.config import Settings
from smzdm_bot.exceptions import ConfigurationError
from smzdm_bot.models import AccountTaskResult

cli_runner = CliRunner()


def test_cli_without_command_shows_help() -> None:
    result = cli_runner.invoke(app)

    assert "Usage:" in result.output
    assert "run" in result.output


def test_version_command() -> None:
    result = cli_runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert "smzdm-bot version" in result.output


def test_config_command_never_prints_cookie_values(monkeypatch) -> None:
    secret = "synthetic-secret-cookie"
    settings = Settings(
        cookie=f"sess={secret}; smzdm_id=123; device_id=device;",
        _env_file=None,
    )
    monkeypatch.setattr("smzdm_bot.config.get_settings", lambda: settings)

    result = cli_runner.invoke(app, ["config"])

    assert result.exit_code == 0
    assert "Ready" in result.output
    assert "Generated" in result.output
    assert secret not in result.output


def test_config_command_marks_automatic_sk_as_unavailable_without_identity(monkeypatch) -> None:
    settings = Settings(cookie="sess=synthetic-session;", _env_file=None)
    monkeypatch.setattr("smzdm_bot.config.get_settings", lambda: settings)

    result = cli_runner.invoke(app, ["config"])

    assert result.exit_code == 0
    assert "Incomplete" in result.output
    assert "Unavailable" in result.output


def test_run_command_renders_summary(monkeypatch) -> None:
    monkeypatch.setattr(
        "smzdm_bot.main.run_all_accounts",
        lambda: [
            AccountTaskResult(user_id="10001", success=True),
            AccountTaskResult(user_id="10002", success=False),
        ],
    )

    result = cli_runner.invoke(app, ["run"])

    assert result.exit_code == 1
    assert "任务汇总" in result.output
    assert "成功" in result.output
    assert "失败" in result.output
    assert "10001" in result.output
    assert "10002" in result.output


def test_run_command_handles_configuration_error(monkeypatch) -> None:
    def raise_configuration_error() -> list[AccountTaskResult]:
        raise ConfigurationError("missing configuration")

    monkeypatch.setattr(
        "smzdm_bot.main.run_all_accounts",
        raise_configuration_error,
    )

    result = cli_runner.invoke(app, ["run"])

    assert result.exit_code == 1
    assert "missing configuration" in result.output
