from smzdm_bot import scheduler
from smzdm_bot.config import Settings


def test_resolve_schedule_time_uses_validated_configuration(monkeypatch) -> None:
    settings = Settings(
        schedule_hour=9,
        schedule_minute=30,
        timezone="Asia/Shanghai",
        _env_file=None,
    )
    monkeypatch.setattr(scheduler, "get_settings", lambda: settings)

    assert scheduler.resolve_schedule_time() == (9, 30, "Asia/Shanghai")


def test_run_scheduled_tasks_calls_run_all_accounts(monkeypatch) -> None:
    invocation_count = 0

    def fake_run_all_accounts() -> list[object]:
        nonlocal invocation_count
        invocation_count += 1
        return []

    monkeypatch.setattr(
        scheduler,
        "run_all_accounts",
        fake_run_all_accounts,
    )

    scheduler.run_scheduled_tasks()

    assert invocation_count == 1
