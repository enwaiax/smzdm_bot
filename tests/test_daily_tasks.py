import pytest

from smzdm_bot.tasks.daily import DailyTaskExecutor, _extract_task_payloads


def _response_with_activity(activity_payload: dict) -> dict:
    return {
        "data": {
            "rows": [
                {
                    "cell_data": {
                        "activity_task": activity_payload,
                    }
                }
            ]
        }
    }


def test_extracts_current_default_task_list() -> None:
    first_task = {"task_id": "1"}
    second_task = {"task_id": "2"}
    response_payload = _response_with_activity(
        {
            "default_list_v2": [
                {"task_list": [first_task, second_task]},
            ],
            "accumulate_list": [],
        }
    )

    assert _extract_task_payloads(response_payload) == [first_task, second_task]


@pytest.mark.parametrize(
    "accumulate_list",
    [
        [{"task_list": [{"task_id": "1"}]}],
        {"task_list_v2": [{"task_list": [{"task_id": "1"}]}]},
    ],
)
def test_extracts_current_and_historical_accumulate_lists(
    accumulate_list: list | dict,
) -> None:
    response_payload = _response_with_activity(
        {
            "default_list_v2": [],
            "accumulate_list": accumulate_list,
        }
    )

    assert _extract_task_payloads(response_payload) == [{"task_id": "1"}]


def test_ignores_malformed_activity_rows() -> None:
    assert _extract_task_payloads({"data": {"rows": [[], None, "invalid"]}}) == []


def test_daily_task_request_failures_are_not_reported_as_success() -> None:
    class FailingClient:
        def post(self, _endpoint_path: str) -> dict:
            raise RuntimeError("task list failed")

    executor = DailyTaskExecutor(FailingClient())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="task list failed"):
        executor.execute()
