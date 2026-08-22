"""Account-level task orchestration."""

from functools import partial

from loguru import logger

from smzdm_bot.client import SmzdmClient
from smzdm_bot.config import TaskPolicyConfig
from smzdm_bot.models import (
    AccountTaskResult,
    CheckinResult,
    LotteryResult,
    RewardInfo,
    TaskItemResult,
    TaskOutcome,
    TaskReport,
    VipInfo,
)
from smzdm_bot.tasks.checkin import (
    claim_extra_checkin_reward,
    fetch_normal_checkin_reward,
    fetch_vip_info,
    perform_daily_checkin,
)
from smzdm_bot.tasks.daily import DailyTaskExecutor
from smzdm_bot.tasks.execution import (
    TaskDefinition,
    TaskExecutionResult,
    TaskPriority,
    execute_task_definitions,
)
from smzdm_bot.tasks.lottery import (
    enter_free_crowd_lotteries,
    perform_task_lottery,
)
from smzdm_bot.tasks.testing import TestingTaskExecutor

CHECKIN_TASK_NAME = "签到"
REPORT_TASK_NAMES = frozenset({"每日任务", "全民众测"})


class AccountTaskRunner:
    """Build, execute, and summarize tasks for one account."""

    def __init__(
        self,
        smzdm_client: SmzdmClient,
        user_id: str = "",
        task_policy: TaskPolicyConfig | None = None,
    ) -> None:
        self.smzdm_client = smzdm_client
        self.user_id = user_id or "unknown"
        self.task_policy = task_policy or TaskPolicyConfig()
        self._daily_task_executor = DailyTaskExecutor(smzdm_client, self.task_policy)
        self._testing_task_executor = TestingTaskExecutor(
            smzdm_client,
            self.task_policy,
        )

    def execute_tasks(self) -> AccountTaskResult:
        """Execute the account task plan and return its combined result."""
        logger.info(f"===== 用户 ID: {self.user_id} =====")
        execution_results = execute_task_definitions(self._build_task_definitions())
        return self._combine_results(execution_results)

    def _build_task_definitions(self) -> tuple[TaskDefinition, ...]:
        """Return the explicit task plan in registration order."""
        task_definitions = [
            TaskDefinition(
                task_name=CHECKIN_TASK_NAME,
                operation=partial(perform_daily_checkin, self.smzdm_client),
                priority=TaskPriority.HIGH,
                continue_on_failure=False,
            ),
            TaskDefinition(
                task_name="VIP信息",
                operation=partial(fetch_vip_info, self.smzdm_client),
                priority=TaskPriority.HIGH,
            ),
            TaskDefinition(
                task_name="签到奖励",
                operation=partial(
                    fetch_normal_checkin_reward,
                    self.smzdm_client,
                ),
            ),
            TaskDefinition(
                task_name="额外奖励",
                operation=partial(
                    claim_extra_checkin_reward,
                    self.smzdm_client,
                ),
            ),
            TaskDefinition(
                task_name="任务抽奖",
                operation=partial(perform_task_lottery, self.smzdm_client),
                priority=TaskPriority.LOW,
                delay_seconds_range=(2, 5),
            ),
            TaskDefinition(
                task_name="幸运屋抽奖",
                operation=partial(
                    enter_free_crowd_lotteries,
                    self.smzdm_client,
                ),
                priority=TaskPriority.LOW,
                delay_seconds_range=(2, 5),
            ),
            TaskDefinition(
                task_name="每日任务",
                operation=self._daily_task_executor.execute,
                priority=TaskPriority.LOW,
                delay_seconds_range=(2, 5),
            ),
        ]
        if self.task_policy.enable_testing_tasks:
            task_definitions.append(
                TaskDefinition(
                    task_name="全民众测",
                    operation=self._testing_task_executor.execute,
                    priority=TaskPriority.LOW,
                    delay_seconds_range=(2, 5),
                )
            )
        return tuple(task_definitions)

    def _combine_results(
        self,
        execution_results: list[TaskExecutionResult],
    ) -> AccountTaskResult:
        """Combine typed task return values into one account result."""
        combined_result = AccountTaskResult(user_id=self.user_id)

        for execution_result in execution_results:
            return_value = execution_result.return_value
            if isinstance(return_value, CheckinResult):
                combined_result.checkin = return_value
            elif isinstance(return_value, VipInfo):
                combined_result.vip_info = return_value
            elif isinstance(return_value, RewardInfo):
                combined_result.reward = return_value
            elif isinstance(return_value, LotteryResult):
                combined_result.lottery = return_value
            elif isinstance(return_value, TaskReport):
                combined_result.task_reports.append(return_value)
            elif (
                execution_result.task_name in REPORT_TASK_NAMES
                and not execution_result.completed_without_error
            ):
                combined_result.task_reports.append(
                    TaskReport(
                        title=execution_result.task_name,
                        items=[
                            TaskItemResult(
                                task_name="请求",
                                outcome=TaskOutcome.FAILED,
                                message=execution_result.error_message or "未知错误",
                            )
                        ],
                    )
                )

        checkin_execution_result = next(
            (
                execution_result
                for execution_result in execution_results
                if execution_result.task_name == CHECKIN_TASK_NAME
            ),
            None,
        )
        combined_result.success = (
            checkin_execution_result is not None
            and checkin_execution_result.completed_without_error
        )

        if not combined_result.success and checkin_execution_result:
            combined_result.error = checkin_execution_result.error_message

        return combined_result


__all__ = ["AccountTaskRunner"]
