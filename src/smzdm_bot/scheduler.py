"""Task scheduler for SMZDM Bot.

Provides scheduled task execution using APScheduler.
"""

import signal
import sys
from random import randint

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from smzdm_bot.config import get_settings
from smzdm_bot.main import run_all_accounts


def resolve_schedule_time() -> tuple[int, int, str]:
    """Determine scheduled execution time.

    Returns:
        Tuple of (hour, minute, timezone).
    """
    settings = get_settings()
    scheduler_config = settings.build_scheduler_config()

    scheduled_hour = scheduler_config.hour
    scheduled_minute = scheduler_config.minute
    timezone_name = scheduler_config.timezone

    if scheduled_hour is None:
        scheduled_hour = randint(6, 10)
        logger.info(f"No SMZDM_SCH_HOUR set, using random hour: {scheduled_hour}")

    if scheduled_minute is None:
        scheduled_minute = randint(0, 59)
        logger.info(f"No SMZDM_SCH_MINUTE set, using random minute: {scheduled_minute}")

    return scheduled_hour, scheduled_minute, timezone_name


def run_scheduled_tasks() -> None:
    """Execute scheduled tasks."""
    logger.info("=" * 50)
    logger.info("Starting scheduled task execution")
    logger.info("=" * 50)

    try:
        run_all_accounts()
    except Exception as error:
        logger.exception(f"Scheduled task failed: {error}")

    logger.info("Scheduled task completed")


def run_scheduler() -> None:
    """Start the task scheduler.

    1. Runs tasks immediately on startup
    2. Schedules future runs at the configured time
    3. Handles graceful shutdown
    """
    # Run immediately on startup
    logger.info("Running initial task execution...")
    try:
        run_all_accounts()
    except Exception as error:
        logger.error(f"Initial task execution failed: {error}")

    # Get schedule time
    scheduled_hour, scheduled_minute, timezone_name = resolve_schedule_time()
    logger.info(f"Scheduled time: {scheduled_hour:02d}:{scheduled_minute:02d} ({timezone_name})")

    # Create scheduler
    blocking_scheduler = BlockingScheduler(timezone=timezone_name)

    cron_trigger = CronTrigger(
        hour=scheduled_hour,
        minute=scheduled_minute,
        timezone=timezone_name,
    )
    blocking_scheduler.add_job(
        run_scheduled_tasks,
        trigger=cron_trigger,
        id="smzdm_checkin",
        name="SMZDM Daily Check-in",
        replace_existing=True,
    )

    # Graceful shutdown
    def handle_shutdown_signal(_signal_number: int, _stack_frame: object) -> None:
        logger.info("Shutting down scheduler...")
        blocking_scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown_signal)
    signal.signal(signal.SIGTERM, handle_shutdown_signal)

    # Start
    logger.info("Scheduler started. Waiting for next run...")

    try:
        blocking_scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    run_scheduler()
