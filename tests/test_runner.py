import pytest

from smzdm_bot.models import CheckinResult, TaskOutcome
from smzdm_bot.tasks.execution import TaskExecutionResult
from smzdm_bot.tasks.runner import AccountTaskRunner


@pytest.mark.parametrize("task_name", ["每日任务", "全民众测"])
def test_report_task_request_failure_is_included_in_account_result(task_name: str) -> None:
    runner = AccountTaskRunner(object(), user_id="10001")  # type: ignore[arg-type]
    execution_results = [
        TaskExecutionResult(
            task_name="签到",
            completed_without_error=True,
            return_value=CheckinResult(),
        ),
        TaskExecutionResult(
            task_name=task_name,
            completed_without_error=False,
            error_message="request failed",
        ),
    ]

    account_result = runner._combine_results(execution_results)

    assert account_result.success is True
    assert len(account_result.task_reports) == 1
    task_report = account_result.task_reports[0]
    assert task_report.title == task_name
    assert task_report.failed_count == 1
    assert task_report.items[0].outcome is TaskOutcome.FAILED
    assert task_report.items[0].message == "request failed"
