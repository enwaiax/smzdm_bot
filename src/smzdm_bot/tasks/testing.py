"""Optional public-testing energy tasks."""

from loguru import logger

from smzdm_bot.client import SmzdmClient
from smzdm_bot.config import TaskPolicyConfig
from smzdm_bot.models import TaskItemResult, TaskOutcome, TaskReport
from smzdm_bot.tasks.daily import DailyTaskExecutor

TESTING_TASK_BASE_URL = "https://zhiyou.m.smzdm.com/task/task"
TESTING_CENTER_BASE_URL = "https://test.m.smzdm.com"


class TestingTaskExecutor(DailyTaskExecutor):
    """Execute optional public-testing tasks with their web reward endpoint."""

    def __init__(
        self,
        smzdm_client: SmzdmClient,
        task_policy: TaskPolicyConfig,
    ) -> None:
        super().__init__(smzdm_client, task_policy)

    def execute(self) -> TaskReport:
        """Discover the current activity and execute its supported tasks."""
        if not self.task_policy.enable_testing_tasks:
            return TaskReport(
                title="全民众测",
                items=[
                    TaskItemResult(
                        "全民众测",
                        TaskOutcome.SKIPPED,
                        "任务已关闭",
                    )
                ],
            )

        activity_id = self._fetch_activity_id()
        if not activity_id:
            return TaskReport(
                title="全民众测",
                items=[
                    TaskItemResult(
                        "全民众测",
                        TaskOutcome.SKIPPED,
                        "当前无活动",
                    )
                ],
            )

        activity_payload = self._fetch_activity_payload(activity_id)
        task_payloads = _extract_testing_task_payloads(activity_payload)
        task_report = self.execute_task_payloads(task_payloads, "全民众测")
        energy_summary = self._fetch_energy_summary()
        if energy_summary:
            task_report.details.append(energy_summary)
        return task_report

    def _fetch_activity_id(self) -> str:
        """Fetch the current public-testing activity identifier."""
        try:
            response_payload = self.smzdm_client.get_unsigned_web_json(
                f"{TESTING_TASK_BASE_URL}/ajax_get_activity_id",
                {"from": "zhongce"},
                referer_url=f"{TESTING_CENTER_BASE_URL}/",
                origin_url=TESTING_CENTER_BASE_URL,
            )
        except Exception:
            logger.exception("获取全民众测活动 ID 失败")
            return ""
        return str(response_payload.get("data", {}).get("activity_id", ""))

    def _fetch_activity_payload(self, activity_id: str) -> dict:
        """Fetch task data for one public-testing activity."""
        try:
            response_payload = self.smzdm_client.get_unsigned_web_json(
                f"{TESTING_TASK_BASE_URL}/ajax_get_activity_info",
                {"activity_id": activity_id},
                referer_url=f"{TESTING_CENTER_BASE_URL}/",
            )
        except Exception:
            logger.exception("获取全民众测活动信息失败")
            return {}
        activity_payload = response_payload.get("data", {})
        return activity_payload if isinstance(activity_payload, dict) else {}

    def _fetch_energy_summary(self) -> str:
        """Fetch current energy total and expiration information."""
        try:
            response_payload = self.smzdm_client.get_unsigned_web_json(
                f"{TESTING_CENTER_BASE_URL}/win_coupon/user_data",
                referer_url=f"{TESTING_CENTER_BASE_URL}/",
            )
        except Exception:
            return ""

        energy_payload = response_payload.get("data", {}).get("my_energy", {})
        if not isinstance(energy_payload, dict):
            return ""
        energy_total = energy_payload.get("my_energy_total", 0)
        expiration_time = energy_payload.get("energy_expired_time", "")
        return f"🎟️ 必中券: {energy_total}，过期时间: {expiration_time or '未知'}"

    def _claim_task_reward(self, task_id: str, task_name: str) -> bool:
        """Claim one public-testing task reward."""
        try:
            response_payload = self.smzdm_client.post_unsigned_web(
                f"{TESTING_TASK_BASE_URL}/ajax_activity_task_receive",
                {"task_id": task_id},
                referer_url=f"{TESTING_CENTER_BASE_URL}/",
            )
        except Exception:
            return False
        succeeded = str(response_payload.get("error_code", "")) == "0"
        if succeeded:
            logger.success(f"众测奖励: {task_name}")
        return succeeded


def _extract_testing_task_payloads(activity_payload: dict) -> list[dict]:
    """Flatten current and historical public-testing task groups."""
    activity_tasks = activity_payload.get("activity_task", {})
    if not isinstance(activity_tasks, dict):
        return []

    task_groups = activity_tasks.get("default_list_v2")
    if not isinstance(task_groups, list):
        task_groups = activity_tasks.get("default_list", [])
    if not isinstance(task_groups, list):
        return []

    if any(
        isinstance(task_payload, dict) and "task_id" in task_payload for task_payload in task_groups
    ):
        return [
            task_payload
            for task_payload in task_groups
            if isinstance(task_payload, dict) and "task_id" in task_payload
        ]

    task_payloads: list[dict] = []
    for task_group in task_groups:
        if not isinstance(task_group, dict):
            continue
        group_tasks = task_group.get("task_list", [])
        if isinstance(group_tasks, list):
            task_payloads.extend(
                task_payload for task_payload in group_tasks if isinstance(task_payload, dict)
            )
    return task_payloads


__all__ = ["TestingTaskExecutor"]
