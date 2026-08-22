from typing import Any

import pytest

from smzdm_bot.models import TaskOutcome
from smzdm_bot.tasks.daily import (
    DailyTaskExecutor,
    _extract_available_activity_rewards,
)
from smzdm_bot.tasks.lottery import enter_free_crowd_lotteries, perform_task_lottery
from smzdm_bot.tasks.testing import _extract_testing_task_payloads


@pytest.fixture(autouse=True)
def disable_random_delays(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "smzdm_bot.tasks.daily.wait_for_random_delay",
        lambda _delay_range: 0,
    )
    monkeypatch.setattr(
        "smzdm_bot.tasks.lottery.wait_for_random_delay",
        lambda _delay_range: 0,
    )


class RecordingClient:
    API_BASE_URL = "https://user-api.example"
    ARTICLE_API_BASE_URL = "https://article-api.example"
    BRAND_API_BASE_URL = "https://brand-api.example"
    SUBSCRIPTION_API_BASE_URL = "https://subscription-api.example"

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self.responses: dict[str, dict] = {}

    def post(
        self,
        endpoint_path: str,
        extra_form_fields: dict | None = None,
        base_url: str | None = None,
        **options: Any,
    ) -> dict:
        self.calls.append(
            (
                "post",
                endpoint_path,
                {
                    "fields": extra_form_fields or {},
                    "base_url": base_url,
                    **options,
                },
            )
        )
        return self.responses.get(endpoint_path, {})

    def get(
        self,
        endpoint_path: str,
        query_fields: dict | None = None,
        base_url: str | None = None,
        **options: Any,
    ) -> dict:
        self.calls.append(
            (
                "get",
                endpoint_path,
                {
                    "fields": query_fields or {},
                    "base_url": base_url,
                    **options,
                },
            )
        )
        return self.responses.get(endpoint_path, {})


@pytest.mark.parametrize(
    ("event_type", "expected_message"),
    [
        ("interactive.comment", "评论任务不受支持"),
        ("publish.biji_new", "内容发布任务不受支持"),
        ("interactive.rating", "无法读取账号原始点赞状态"),
        ("interactive.favorite", "无法读取账号原始收藏状态"),
        ("interactive.share", "分享任务流程未经当前版本验证"),
        ("guide.crowd", "幸运屋任务缺少已验证的目标映射"),
        ("interactive.view.zhanwai", "站外浏览任务需要真实打开目标页面"),
        (
            "interactive.open_third_party_app",
            "第三方 APP 任务无法由服务端脚本真实完成",
        ),
        (
            "interactive.download_zhangdama",
            "APP 下载任务无法由服务端脚本真实完成",
        ),
        (
            "guide.create_app_checkin_shortcut",
            "签到小组件任务需要真实 Android 桌面操作",
        ),
        ("guide.open_app_push", "推送开启任务需要真实 Android 系统设置"),
    ],
)
def test_unsupported_write_tasks_are_skipped(
    event_type: str,
    expected_message: str,
) -> None:
    client = RecordingClient()
    executor = DailyTaskExecutor(client)  # type: ignore[arg-type]

    result = executor._execute_task(
        {
            "task_status": "2",
            "task_name": "content task",
            "task_event_type": event_type,
            "task_id": "task-1",
            "task_redirect_url": {},
        }
    )

    assert result.outcome is TaskOutcome.SKIPPED
    assert result.message == expected_message
    assert client.calls == []


def test_reward_claim_uses_robot_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("smzdm_bot.tasks.daily.time.sleep", lambda _seconds: None)
    client = RecordingClient()
    client.responses["/robot/token"] = {"data": {"token": "robot-token"}}
    executor = DailyTaskExecutor(client)  # type: ignore[arg-type]

    result = executor._execute_task(
        {
            "task_status": "3",
            "task_name": "reward task",
            "task_id": "task-1",
            "task_redirect_url": {},
        }
    )

    assert result.outcome is TaskOutcome.COMPLETED
    assert [call[1] for call in client.calls] == [
        "/robot/token",
        "/task/activity_task_receive",
    ]
    assert client.calls[1][2]["fields"]["robot_token"] == "robot-token"


def test_event_type_takes_precedence_over_redirect_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("smzdm_bot.tasks.daily.time.sleep", lambda _seconds: None)
    client = RecordingClient()
    executor = DailyTaskExecutor(client)  # type: ignore[arg-type]
    monkeypatch.setattr(executor, "_execute_follow_task", lambda _payload: True)
    monkeypatch.setattr(
        executor,
        "_execute_article_view_task",
        lambda _payload: pytest.fail("follow task was dispatched as article view"),
    )
    monkeypatch.setattr(
        executor,
        "_claim_task_reward",
        lambda _task_id, _task_name: True,
    )

    result = executor._execute_task(
        {
            "task_status": "2",
            "task_name": "follow task",
            "task_event_type": "interactive.follow.user",
            "task_id": "task-1",
            "task_redirect_url": {"link_type": "yuanchuang"},
        }
    )

    assert result.outcome is TaskOutcome.COMPLETED


def test_supported_daily_task_waits_before_action_and_reward(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution_order: list[str] = []
    client = RecordingClient()
    executor = DailyTaskExecutor(client)  # type: ignore[arg-type]
    monkeypatch.setattr(
        "smzdm_bot.tasks.daily.wait_for_random_delay",
        lambda _delay_range: execution_order.append("wait"),
    )
    monkeypatch.setattr(
        executor,
        "_execute_follow_task",
        lambda _payload: execution_order.append("action") or True,
    )
    monkeypatch.setattr(
        executor,
        "_claim_task_reward",
        lambda _task_id, _task_name: execution_order.append("reward") or True,
    )

    result = executor._execute_task(
        {
            "task_status": "2",
            "task_name": "follow task",
            "task_event_type": "interactive.follow.user",
            "task_id": "task-1",
            "task_redirect_url": {"link_type": "guanzhu"},
        }
    )

    assert result.outcome is TaskOutcome.COMPLETED
    assert execution_order == ["wait", "action", "wait", "reward"]


def test_interaction_without_explicit_article_target_is_skipped() -> None:
    client = RecordingClient()
    executor = DailyTaskExecutor(client)  # type: ignore[arg-type]

    article_target = executor._resolve_article_target(
        {
            "article_id": "0",
            "task_redirect_url": {"link_val": "0"},
        }
    )

    assert article_target is None
    assert client.calls == []


def test_recommended_user_query_uses_service_specific_signing() -> None:
    client = RecordingClient()
    client.responses["/dy/user/dingyue/tuijian_search"] = {
        "data": {
            "rows": [
                {
                    "type": "user",
                    "keyword_id": "user-1",
                    "keyword": "user",
                    "is_follow": 0,
                }
            ]
        }
    }
    executor = DailyTaskExecutor(client)  # type: ignore[arg-type]

    recommended_user = executor._fetch_random_recommended_user()

    assert recommended_user is not None
    assert recommended_user["keyword_id"] == "user-1"
    assert client.calls[0][0:2] == (
        "post",
        "/dy/user/dingyue/tuijian_search",
    )
    assert client.calls[0][2]["fields"] == {"type": "user"}
    assert client.calls[0][2]["include_session_fields"] is False


def test_user_follow_action_uses_keyword_instead_of_keyword_id() -> None:
    client = RecordingClient()
    executor = DailyTaskExecutor(client)  # type: ignore[arg-type]

    assert executor._update_follow_state("user-1", "nickname", "user", "create")

    assert client.calls[0][0:2] == ("post", "/dingyue/create")
    assert client.calls[0][2]["fields"] == {
        "keyword": "user-1",
        "type": "user",
        "refer": "",
        "touchstone_event": "",
        "is_from_task": "0",
    }
    assert "keyword_id" not in client.calls[0][2]["fields"]
    assert client.calls[0][2]["include_session_fields"] is False


@pytest.mark.parametrize("target_type", ["tag", "brand"])
def test_tag_and_brand_follow_actions_use_keyword_id(target_type: str) -> None:
    client = RecordingClient()
    executor = DailyTaskExecutor(client)  # type: ignore[arg-type]

    assert executor._update_follow_state(
        "target-1",
        "target name",
        target_type,
        "destroy",
    )

    assert client.calls[0][0:2] == ("post", "/dingyue/destroy")
    assert client.calls[0][2]["fields"] == {
        "keyword_id": "target-1",
        "keyword": "target name",
        "type": target_type,
        "refer": "",
        "touchstone_event": "",
    }
    assert client.calls[0][2]["include_session_fields"] is False


def test_brand_task_uses_native_follow_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("smzdm_bot.tasks.daily.time.sleep", lambda _seconds: None)
    client = RecordingClient()
    client.responses["/brand/brand_basic"] = {
        "data": {
            "id": "brand-1",
            "title": "brand name",
            "follow_status": 0,
        }
    }
    executor = DailyTaskExecutor(client)  # type: ignore[arg-type]

    assert executor._execute_brand_follow_task("brand-1")

    assert [call[1] for call in client.calls] == [
        "/brand/brand_basic",
        "/dingyue/create",
        "/dingyue/destroy",
    ]
    assert all(call[2]["include_session_fields"] is False for call in client.calls)
    assert client.calls[1][2]["fields"]["type"] == "brand"
    assert client.calls[1][2]["fields"]["keyword_id"] == "brand-1"


def test_available_activity_rewards_are_extracted() -> None:
    response_payload = {
        "data": {
            "rows": [
                {
                    "cell_data": {
                        "activity_reward_status": "1",
                        "activity_id": "activity-1",
                        "activity_name": "Stage reward",
                    }
                },
                {
                    "cell_data": {
                        "activity_reward_status": "0",
                        "activity_id": "activity-2",
                    }
                },
            ]
        }
    }

    assert _extract_available_activity_rewards(response_payload) == [("activity-1", "Stage reward")]


class CrowdClient:
    WEB_BASE_URL = "https://crowd.example"

    def __init__(self, page_html: str) -> None:
        self.page_html = page_html
        self.entered_ids: list[str] = []

    def get_html(self, _request_url: str) -> str:
        return self.page_html

    def post_unsigned_web(
        self,
        _request_url: str,
        form_fields: dict,
        referer_url: str,
    ) -> dict:
        self.entered_ids.append(form_fields["crowd_id"])
        return {"error_code": 0, "data": {"msg": "success"}}


def _crowd_button(crowd_id: str, title: str, silver_cost: int) -> str:
    return (
        f'<button data-crowd_id="{crowd_id}" data-title="{title}">'
        f'<div>{title}</div><span class="reduceNumber">-{silver_cost}</span>'
        "</button>"
    )


def test_free_crowd_entry_ignores_paid_options() -> None:
    client = CrowdClient(
        _crowd_button("1", "free option", 0) + _crowd_button("5", "paid option", 5)
    )

    successful_entry_count = enter_free_crowd_lotteries(client)  # type: ignore[arg-type]

    assert successful_entry_count == 1
    assert client.entered_ids == ["1"]


def test_task_lottery_uses_current_app_endpoint() -> None:
    client = RecordingClient()
    client.responses["/task/lottery"] = {
        "error_code": "0",
        "data": {
            "gift_name": "test gift",
            "description": "test description",
        },
    }

    result = perform_task_lottery(client)  # type: ignore[arg-type]

    assert result.success is True
    assert result.message == "test gift"
    assert client.calls == [
        (
            "post",
            "/task/lottery",
            {"fields": {}, "base_url": None},
        )
    ]


def test_extracts_public_testing_tasks() -> None:
    task_payload = {"task_id": "testing-task"}
    activity_payload = {
        "activity_task": {
            "default_list": [{"task_list": [task_payload]}],
        }
    }

    assert _extract_testing_task_payloads(activity_payload) == [task_payload]


def test_extracts_current_flat_public_testing_tasks() -> None:
    task_payload = {"task_id": "testing-task"}
    activity_payload = {
        "activity_task": {
            "default_list": [task_payload],
        }
    }

    assert _extract_testing_task_payloads(activity_payload) == [task_payload]
