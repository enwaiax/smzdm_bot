"""Application-level account and notification orchestration."""

from loguru import logger

from smzdm_bot.client import SmzdmClient
from smzdm_bot.config import Settings, TaskPolicyConfig, UserConfig, get_settings
from smzdm_bot.models import AccountTaskResult
from smzdm_bot.notify import send_configured_notifications
from smzdm_bot.protocol import parse_cookie_header
from smzdm_bot.tasks import AccountTaskRunner


def run_account_tasks(
    user_config: UserConfig,
    task_policy: TaskPolicyConfig | None = None,
) -> AccountTaskResult:
    """Execute all tasks for a single user."""
    user_id = (
        parse_cookie_header(user_config.cookie).get("smzdm_id")
        or user_config.account_label
        or "unknown"
    )
    try:
        with SmzdmClient(user_config) as smzdm_client:
            task_runner = AccountTaskRunner(
                smzdm_client,
                user_id=smzdm_client.smzdm_user_id or user_id,
                task_policy=task_policy,
            )
            return task_runner.execute_tasks()
    except Exception as error:
        logger.error(f"用户 {user_id} 失败: {error}")
        return AccountTaskResult(
            user_id=user_id,
            success=False,
            error=str(error),
        )


def run_all_accounts(settings: Settings | None = None) -> list[AccountTaskResult]:
    """Execute tasks for all users."""
    settings = settings or get_settings()
    user_configs = settings.get_user_configs()
    task_policy = settings.build_task_policy()

    logger.info(f"Running tasks for {len(user_configs)} user(s)")
    task_results = [run_account_tasks(user_config, task_policy) for user_config in user_configs]

    # Send notification
    notification_config = settings.build_notification_config()
    all_succeeded = bool(task_results) and all(result.success for result in task_results)
    should_notify = (
        notification_config.notify_on_success
        if all_succeeded
        else notification_config.notify_on_failure
    )
    if notification_config.notify_enabled and should_notify and task_results:
        successful_account_count = sum(1 for task_result in task_results if task_result.success)
        try:
            send_configured_notifications(
                notification_config,
                title=f"什么值得买签到 ({successful_account_count}/{len(task_results)})",
                content="\n\n".join(task_result.to_message() for task_result in task_results),
            )
        except Exception:
            logger.warning("Notification failed; account results are unchanged")

    return task_results


def determine_exit_code(task_results: list[AccountTaskResult]) -> int:
    """Return a process exit code for task results."""
    return 0 if task_results and all(task_result.success for task_result in task_results) else 1
