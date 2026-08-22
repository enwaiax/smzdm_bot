"""Execution of SMZDM activity tasks."""

import json
import random
import time

from loguru import logger

from smzdm_bot.client import SmzdmClient
from smzdm_bot.config import TaskPolicyConfig
from smzdm_bot.models import TaskItemResult, TaskOutcome, TaskReport
from smzdm_bot.tasks.execution import wait_for_random_delay

TASK_STATUS_INCOMPLETE = 2
TASK_STATUS_REWARD_AVAILABLE = 3
COMMENT_EVENT_TYPE = "interactive.comment"
PUBLISH_EVENT_PREFIX = "publish."
UNSUPPORTED_EVENT_MESSAGES = {
    "interactive.rating": "无法读取账号原始点赞状态",
    "interactive.favorite": "无法读取账号原始收藏状态",
    "interactive.share": "分享任务流程未经当前版本验证",
    "guide.crowd": "幸运屋任务缺少已验证的目标映射",
    "interactive.view.zhanwai": "站外浏览任务需要真实打开目标页面",
    "interactive.open_third_party_app": "第三方 APP 任务无法由服务端脚本真实完成",
    "interactive.download_zhangdama": "APP 下载任务无法由服务端脚本真实完成",
    "guide.create_app_checkin_shortcut": "签到小组件任务需要真实 Android 桌面操作",
    "guide.open_app_push": "推送开启任务需要真实 Android 系统设置",
}


class DailyTaskExecutor:
    """Execute the activity tasks returned by the daily task endpoint."""

    def __init__(
        self,
        smzdm_client: SmzdmClient,
        task_policy: TaskPolicyConfig | None = None,
    ) -> None:
        self.smzdm_client = smzdm_client
        self.task_policy = task_policy or TaskPolicyConfig()

    def execute(self) -> TaskReport:
        """Execute supported daily activity tasks and return a structured report."""
        response_payload = self.smzdm_client.post("/task/list_v2")
        task_payloads = _extract_task_payloads(response_payload)
        task_report = self.execute_task_payloads(task_payloads)
        task_report.items.extend(self._claim_available_activity_rewards(response_payload))
        logger.info(
            f"每日任务完成 {task_report.completed_count}, "
            f"跳过 {task_report.skipped_count}, 失败 {task_report.failed_count}"
        )
        return task_report

    def execute_task_payloads(
        self,
        task_payloads: list[dict],
        report_title: str = "每日任务",
    ) -> TaskReport:
        """Execute already extracted task payloads."""
        return TaskReport(
            title=report_title,
            items=[self._execute_task(task_payload) for task_payload in task_payloads],
        )

    def _execute_task(self, task_payload: dict) -> TaskItemResult:
        """Execute or claim one task."""
        task_status = _parse_integer(task_payload.get("task_status"), default=0)
        task_id = task_payload.get("task_id", "")
        task_name = task_payload.get("task_name", "") or "未命名任务"
        redirect_type = task_payload.get("task_redirect_url", {}).get(
            "link_type",
            "",
        )
        event_type = task_payload.get("task_event_type", "")

        if task_status == TASK_STATUS_INCOMPLETE:
            return self._execute_incomplete_task(
                task_payload,
                task_id,
                task_name,
                redirect_type,
                event_type,
            )

        if task_status == TASK_STATUS_REWARD_AVAILABLE:
            logger.info(f"领取: {task_name}")
            wait_for_random_delay((2, 7))
            if self._claim_task_reward(task_id, task_name):
                return TaskItemResult(task_name, TaskOutcome.COMPLETED, "奖励已领取")
            return TaskItemResult(task_name, TaskOutcome.FAILED, "奖励领取失败")

        return TaskItemResult(task_name, TaskOutcome.SKIPPED, "任务无需处理")

    def _execute_incomplete_task(
        self,
        task_payload: dict,
        task_id: str,
        task_name: str,
        redirect_type: str,
        event_type: str,
    ) -> TaskItemResult:
        """Execute one incomplete supported task and claim its reward."""
        logger.info(f"执行: {task_name}")

        if event_type == COMMENT_EVENT_TYPE:
            return TaskItemResult(task_name, TaskOutcome.SKIPPED, "评论任务不受支持")
        if event_type.startswith(PUBLISH_EVENT_PREFIX):
            return TaskItemResult(task_name, TaskOutcome.SKIPPED, "内容发布任务不受支持")
        if unsupported_message := UNSUPPORTED_EVENT_MESSAGES.get(event_type):
            return TaskItemResult(task_name, TaskOutcome.SKIPPED, unsupported_message)
        if event_type == "interactive.view.article":
            task_executor = self._execute_article_view_task
        elif event_type == "interactive.follow.user":
            if not self.task_policy.enable_follow_tasks:
                return TaskItemResult(task_name, TaskOutcome.SKIPPED, "关注任务已关闭")
            task_executor = self._execute_follow_task
        elif not event_type and redirect_type in (
            "faxian",
            "haojia",
            "article",
            "yuanchuang",
        ):
            task_executor = self._execute_article_view_task
        elif not event_type and redirect_type in ("guanzhu", "lanmu", "brand"):
            if not self.task_policy.enable_follow_tasks:
                return TaskItemResult(task_name, TaskOutcome.SKIPPED, "关注任务已关闭")
            task_executor = self._execute_follow_task
        else:
            return TaskItemResult(
                task_name,
                TaskOutcome.SKIPPED,
                f"暂不支持事件: {event_type or redirect_type}",
            )

        wait_for_random_delay((2, 7))
        task_completed = task_executor(task_payload)
        if not task_completed:
            return TaskItemResult(task_name, TaskOutcome.FAILED, "任务执行失败")

        wait_for_random_delay((3, 8))
        if self._claim_task_reward(task_id, task_name):
            return TaskItemResult(task_name, TaskOutcome.COMPLETED, "任务及奖励已完成")
        return TaskItemResult(task_name, TaskOutcome.FAILED, "任务完成但奖励领取失败")

    def _execute_article_view_task(self, task_payload: dict) -> bool:
        """Execute an article-view task."""
        article_target = self._resolve_article_target(task_payload)
        if article_target is None:
            return False

        article_id, channel_id, _ = article_target
        task_id = task_payload.get("task_id", "")
        required_view_seconds = _parse_integer(
            task_payload.get("view_seconds"),
            default=15,
        )

        logger.info(f"浏览文章 {article_id}...")
        time.sleep(required_view_seconds + random.randint(5, 15))

        try:
            self.smzdm_client.post(
                "/task/event_view_article_sync",
                {
                    "article_id": article_id,
                    "channel_id": channel_id,
                    "task_id": task_id,
                },
            )
            return True
        except Exception:
            return False

    def _resolve_article_target(
        self,
        task_payload: dict,
    ) -> tuple[str, str, dict] | None:
        """Resolve the article metadata required by an article task."""
        redirect_payload = task_payload.get("task_redirect_url", {})
        article_id = str(task_payload.get("article_id", "") or "")
        if article_id == "0":
            article_id = ""
        if not article_id:
            redirect_article_id = str(redirect_payload.get("link_val", "") or "")
            if redirect_article_id.isdigit() and redirect_article_id != "0":
                article_id = redirect_article_id

        if article_id:
            article_data = self._fetch_article_detail(article_id)
            channel_id = str(
                task_payload.get("channel_id")
                or article_data.get("channel_id")
                or article_data.get("article_channel_id")
                or "1"
            )
            return article_id, channel_id, article_data

        return None

    def _fetch_article_detail(self, article_id: str) -> dict:
        """Fetch article metadata used to resolve the channel."""
        try:
            response_payload = self.smzdm_client.get(
                f"/article_detail/{article_id}",
                {
                    "comment_flow": "",
                    "hashcode": "",
                    "lastest_update_time": "",
                    "uhome": 0,
                    "imgmode": 0,
                    "article_channel_id": 0,
                    "h5hash": "",
                },
                base_url=self.smzdm_client.ARTICLE_API_BASE_URL,
                include_session_fields=False,
            )
        except Exception:
            return {}
        article_data = response_payload.get("data", {})
        return article_data if isinstance(article_data, dict) else {}

    def _execute_follow_task(self, task_payload: dict) -> bool:
        """Execute a follow task and restore the original follow state."""
        redirect_payload = task_payload.get("task_redirect_url", {})
        link_type = redirect_payload.get("link_type", "")
        link_value = redirect_payload.get("link_val", "")
        event_type = task_payload.get("task_event_type", "")
        remaining_count = max(
            _parse_integer(task_payload.get("task_even_num"), default=1)
            - _parse_integer(task_payload.get("task_finished_num"), default=0),
            1,
        )

        if link_type == "guanzhu" or event_type == "interactive.follow.user":
            return all(self._execute_user_follow_task() for _ in range(remaining_count))

        if link_type == "lanmu" and link_value:
            target_name = redirect_payload.get("link_title", link_value)
            initially_followed = self._fetch_follow_state(target_name, "tag")
            if initially_followed is None:
                logger.warning("无法确认栏目关注状态，跳过以避免改变原状态")
                return False
            return self._follow_then_unfollow(
                link_value,
                target_name,
                "tag",
                initially_followed,
            )

        if link_type == "brand" and link_value:
            return self._execute_brand_follow_task(link_value)

        return False

    def _execute_user_follow_task(self) -> bool:
        """Follow and then unfollow one recommended user."""
        recommended_user = self._fetch_random_recommended_user()
        if not recommended_user:
            return False

        target_user_id = recommended_user.get("keyword_id") or recommended_user.get(
            "smzdm_id",
            "",
        )
        target_nickname = recommended_user.get("keyword") or recommended_user.get(
            "nickname",
            "",
        )
        if not target_user_id:
            return False
        return self._follow_then_unfollow(
            target_user_id,
            target_nickname,
            "user",
            initially_followed=str(recommended_user.get("is_follow", "0")) == "1",
        )

    def _follow_then_unfollow(
        self,
        target_id: str,
        target_name: str,
        target_type: str,
        initially_followed: bool = False,
    ) -> bool:
        """Toggle a follow target and restore its original state."""
        if initially_followed and not self._update_follow_state(
            target_id,
            target_name,
            target_type,
            "destroy",
        ):
            return False

        if not self._update_follow_state(
            target_id,
            target_name,
            target_type,
            "create",
        ):
            if initially_followed:
                self._update_follow_state(
                    target_id,
                    target_name,
                    target_type,
                    "create",
                )
            return False

        wait_for_random_delay((5, 10))
        if initially_followed:
            return True
        restored = self._update_follow_state(
            target_id,
            target_name,
            target_type,
            "destroy",
        )
        if not restored:
            restored = self._update_follow_state(
                target_id,
                target_name,
                target_type,
                "destroy",
            )
        return restored

    def _update_follow_state(
        self,
        target_id: str,
        target_name: str,
        target_type: str,
        follow_action: str,
    ) -> bool:
        """Send one follow or unfollow request."""
        request_fields = {
            "type": target_type,
            "refer": "",
            "touchstone_event": "",
        }
        if target_type == "user":
            request_fields.update(
                {
                    "keyword": target_id,
                    "is_from_task": "0",
                }
            )
        else:
            request_fields.update(
                {
                    "keyword_id": target_id,
                    "keyword": target_name,
                }
            )

        try:
            self.smzdm_client.post(
                f"/dingyue/{follow_action}",
                request_fields,
                base_url=self.smzdm_client.SUBSCRIPTION_API_BASE_URL,
                include_session_fields=False,
            )
            return True
        except Exception:
            return False

    def _fetch_follow_state(
        self,
        target_name: str,
        target_type: str,
    ) -> bool | None:
        """Read an existing follow state before toggling it."""
        try:
            response_payload = self.smzdm_client.post(
                "/dingyue/follow_status",
                {
                    "rules": json.dumps(
                        [{"type": target_type, "keyword": target_name}],
                        ensure_ascii=False,
                    )
                },
                base_url=self.smzdm_client.SUBSCRIPTION_API_BASE_URL,
                include_session_fields=False,
            )
        except Exception:
            return None
        return _find_nested_active_state(
            response_payload,
            ("is_follow", "is_followed", "follow_status"),
        )

    def _execute_brand_follow_task(self, brand_id: str) -> bool:
        """Follow and unfollow one brand."""
        try:
            brand_payload = self.smzdm_client.get(
                "/brand/brand_basic",
                {"brand_id": brand_id},
                base_url=self.smzdm_client.BRAND_API_BASE_URL,
                include_session_fields=False,
            )
            brand_data = brand_payload.get("data", {})
            brand_name = brand_data.get("title", brand_id)
            resolved_brand_id = str(brand_data.get("id", brand_id))
            if not resolved_brand_id:
                return False
            initially_followed = _find_nested_active_state(
                brand_data,
                ("is_follow", "is_followed", "is_subscribe", "follow_status"),
            )
            if initially_followed is None:
                logger.warning("无法确认品牌关注状态，跳过以避免改变原状态")
                return False
            return self._follow_then_unfollow(
                resolved_brand_id,
                brand_name,
                "brand",
                initially_followed,
            )
        except Exception:
            logger.exception("品牌关注任务失败")
            return False

    def _fetch_random_recommended_user(self) -> dict | None:
        """Fetch one random account from the current follow-task recommendation API."""
        try:
            response_payload = self.smzdm_client.post(
                "/dy/user/dingyue/tuijian_search",
                {
                    "type": "user",
                },
                base_url=self.smzdm_client.SUBSCRIPTION_API_BASE_URL,
                include_session_fields=False,
            )
        except Exception:
            return None

        response_data = response_payload.get("data", {})
        recommended_items = response_data.get("rows", []) if isinstance(response_data, dict) else []
        if not isinstance(recommended_items, list) or not recommended_items:
            recommended_items = response_payload.get("rows", [])
        if not isinstance(recommended_items, list):
            return None
        recommended_users = [
            item
            for item in recommended_items
            if isinstance(item, dict) and item.get("type") == "user"
        ]
        return random.choice(recommended_users) if recommended_users else None

    def _claim_task_reward(self, task_id: str, task_name: str) -> bool:
        """Claim the reward for one completed activity task."""
        try:
            robot_token_payload = self.smzdm_client.post("/robot/token")
            robot_token = (
                robot_token_payload.get("data", {}).get("token", "")
                if isinstance(robot_token_payload, dict)
                else ""
            )
            if not robot_token:
                logger.warning(f"无法获取任务奖励令牌: {task_name}")
                return False
            self.smzdm_client.post(
                "/task/activity_task_receive",
                {
                    "robot_token": robot_token,
                    "geetest_seccode": "",
                    "geetest_validate": "",
                    "geetest_challenge": "",
                    "captcha": "",
                    "task_id": task_id,
                },
            )
            logger.success(f"奖励: {task_name}")
            return True
        except Exception:
            return False

    def _claim_available_activity_rewards(
        self,
        response_payload: dict,
    ) -> list[TaskItemResult]:
        """Claim available stage rewards from task-list activity rows."""
        activity_rewards = _extract_available_activity_rewards(response_payload)
        if not activity_rewards:
            return []

        if not self.task_policy.enable_activity_reward_claims:
            return [
                TaskItemResult(
                    activity_name,
                    TaskOutcome.SKIPPED,
                    "阶段奖励领取已关闭",
                )
                for activity_id, activity_name in activity_rewards
            ]

        results: list[TaskItemResult] = []
        for activity_id, activity_name in activity_rewards:
            try:
                wait_for_random_delay((2, 7))
                self.smzdm_client.post(
                    "/task/activity_receive",
                    {"activity_id": activity_id},
                )
                results.append(
                    TaskItemResult(
                        activity_name,
                        TaskOutcome.COMPLETED,
                        "阶段奖励已领取",
                    )
                )
            except Exception:
                results.append(
                    TaskItemResult(
                        activity_name,
                        TaskOutcome.FAILED,
                        "阶段奖励领取失败",
                    )
                )
        return results


def _extract_task_payloads(response_payload: dict) -> list[dict]:
    """Extract task objects from current and historical response layouts."""
    response_data = response_payload.get("data", {})
    if not isinstance(response_data, dict):
        return []

    activity_rows = response_data.get("rows", [])
    if not isinstance(activity_rows, list):
        return []

    task_payloads: list[dict] = []
    for activity_row in activity_rows:
        if not isinstance(activity_row, dict):
            continue

        cell_data = activity_row.get("cell_data", {})
        if not isinstance(cell_data, dict):
            continue

        activity_payload = cell_data.get("activity_task", {})
        if not isinstance(activity_payload, dict):
            continue

        for task_group in _extract_task_groups(activity_payload):
            if not isinstance(task_group, dict):
                continue

            group_tasks = task_group.get("task_list", [])
            if isinstance(group_tasks, list):
                task_payloads.extend(
                    task_payload for task_payload in group_tasks if isinstance(task_payload, dict)
                )

    return task_payloads


def _extract_task_groups(activity_payload: dict) -> list:
    """Resolve task groups from current and historical activity fields."""
    default_task_groups = activity_payload.get("default_list_v2", [])
    if isinstance(default_task_groups, list) and default_task_groups:
        return default_task_groups

    accumulate_list = activity_payload.get("accumulate_list", [])
    if isinstance(accumulate_list, list):
        return accumulate_list
    if isinstance(accumulate_list, dict):
        historical_task_groups = accumulate_list.get("task_list_v2", [])
        if isinstance(historical_task_groups, list):
            return historical_task_groups

    return []


def _extract_available_activity_rewards(
    response_payload: dict,
) -> list[tuple[str, str]]:
    """Extract available stage-reward activity identifiers and names."""
    response_data = response_payload.get("data", {})
    if not isinstance(response_data, dict):
        return []

    activity_rows = response_data.get("rows", [])
    if not isinstance(activity_rows, list):
        return []

    activity_rewards: list[tuple[str, str]] = []
    for activity_row in activity_rows:
        if not isinstance(activity_row, dict):
            continue
        cell_data = activity_row.get("cell_data", {})
        if not isinstance(cell_data, dict):
            continue
        if str(cell_data.get("activity_reward_status", "")) != "1":
            continue
        activity_id = str(cell_data.get("activity_id", ""))
        if not activity_id:
            continue
        activity_name = str(cell_data.get("activity_name") or "限时累计活动")
        activity_rewards.append((activity_id, activity_name))
    return activity_rewards


def _read_active_state(
    payload: dict,
    candidate_keys: tuple[str, ...],
) -> bool | None:
    """Read an explicit boolean-like state without guessing when absent."""
    for candidate_key in candidate_keys:
        if candidate_key not in payload:
            continue
        state_value = payload[candidate_key]
        if isinstance(state_value, bool):
            return state_value
        if isinstance(state_value, int):
            return state_value != 0
        normalized_value = str(state_value).strip().lower()
        if normalized_value in {"1", "true", "yes", "create", "active"}:
            return True
        if normalized_value in {"0", "false", "no", "destroy", "inactive", ""}:
            return False
    return None


def _find_nested_active_state(
    payload: object,
    candidate_keys: tuple[str, ...],
) -> bool | None:
    """Find an explicit state value in a nested API payload."""
    if isinstance(payload, dict):
        direct_state = _read_active_state(payload, candidate_keys)
        if direct_state is not None:
            return direct_state
        for nested_value in payload.values():
            nested_state = _find_nested_active_state(nested_value, candidate_keys)
            if nested_state is not None:
                return nested_state
    elif isinstance(payload, list):
        for nested_value in payload:
            nested_state = _find_nested_active_state(nested_value, candidate_keys)
            if nested_state is not None:
                return nested_state
    return None


def _parse_integer(value: object, *, default: int) -> int:
    """Parse an API integer field without allowing malformed data to crash a run."""
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


__all__ = ["DailyTaskExecutor"]
