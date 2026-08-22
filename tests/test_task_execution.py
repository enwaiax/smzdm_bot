from smzdm_bot.tasks.execution import (
    TaskDefinition,
    execute_task_definitions,
    wait_for_random_delay,
)


def test_task_executor_records_explicit_result_fields() -> None:
    execution_results = execute_task_definitions(
        [
            TaskDefinition(
                task_name="example",
                operation=lambda: "completed",
                delay_seconds_range=(0, 0),
            )
        ]
    )

    assert len(execution_results) == 1
    assert execution_results[0].task_name == "example"
    assert execution_results[0].completed_without_error is True
    assert execution_results[0].return_value == "completed"
    assert execution_results[0].error_message is None


def test_task_executor_stops_after_non_recoverable_failure() -> None:
    executed_task_names: list[str] = []

    def fail() -> None:
        executed_task_names.append("failing")
        raise RuntimeError("expected failure")

    def must_not_run() -> None:
        executed_task_names.append("must-not-run")

    execution_results = execute_task_definitions(
        [
            TaskDefinition(
                task_name="failing",
                operation=fail,
                continue_on_failure=False,
                delay_seconds_range=(0, 0),
            ),
            TaskDefinition(
                task_name="must-not-run",
                operation=must_not_run,
                delay_seconds_range=(0, 0),
            ),
        ]
    )

    assert executed_task_names == ["failing"]
    assert execution_results[0].completed_without_error is False
    assert execution_results[0].error_message == "expected failure"


def test_random_delay_uses_duration_within_configured_range(monkeypatch) -> None:
    slept_durations: list[float] = []
    monkeypatch.setattr(
        "smzdm_bot.tasks.execution.random.uniform",
        lambda minimum, maximum: 2.5,
    )
    monkeypatch.setattr(
        "smzdm_bot.tasks.execution.time.sleep",
        slept_durations.append,
    )

    selected_duration = wait_for_random_delay((2, 7))

    assert selected_duration == 2.5
    assert slept_durations == [2.5]
