"""Command-line interface for SMZDM Bot.

Built with Typer for a beautiful CLI experience.

Usage:
    smzdm-bot run          Run tasks once
    smzdm-bot schedule     Run tasks on schedule
    smzdm-bot version      Show version
"""

import sys
from pathlib import Path
from typing import Annotated

import typer
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from smzdm_bot import __version__
from smzdm_bot.models import AccountTaskResult

# Initialize
app = typer.Typer(
    name="smzdm-bot",
    help="🛒 SMZDM Bot - 什么值得买每日签到",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()

# Log format
LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
    "<level>{message}</level>"
)


def setup_logging(
    enable_debug_logging: bool = False,
    log_file: Path | None = None,
) -> None:
    """Configure logging."""
    logger.remove()

    # Console output
    log_level = "DEBUG" if enable_debug_logging else "INFO"
    logger.add(sys.stderr, format=LOG_FORMAT, level=log_level, colorize=True)

    # File output
    if log_file:
        logger.add(
            log_file,
            format=LOG_FORMAT,
            level="DEBUG",
            rotation="10 MB",
            retention="7 days",
            compression="zip",
        )


def print_banner() -> None:
    """Print application banner."""
    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]SMZDM Bot[/bold cyan] [dim]v{__version__}[/dim]\n"
            "[italic]什么值得买 · 每日签到[/italic]",
            border_style="cyan",
        )
    )
    console.print()


def version_callback(show_version: bool) -> None:
    """Show version and exit."""
    if show_version:
        print_version()
        raise typer.Exit()


def print_version() -> None:
    """Render the installed package version."""
    console.print(f"smzdm-bot version [bold cyan]{__version__}[/bold cyan]")


def print_run_summary(task_results: list[AccountTaskResult]) -> None:
    """Render an execution summary without authentication secrets."""
    summary_table = Table(title="任务汇总", show_header=True)
    summary_table.add_column("#", justify="right")
    summary_table.add_column("用户")
    summary_table.add_column("状态")

    for account_index, task_result in enumerate(task_results, 1):
        result_status = "[green]成功[/green]" if task_result.success else "[red]失败[/red]"
        summary_table.add_row(
            str(account_index),
            task_result.user_id,
            result_status,
        )

    console.print(summary_table)


@app.callback()
def cli_callback(
    show_version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-v",
            help="Show version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """🛒 SMZDM Bot - 什么值得买每日签到工具."""
    pass


@app.command("version")
def version_command() -> None:
    """Show the installed package version."""
    print_version()


@app.command("run")
def run_command(
    enable_debug_logging: Annotated[
        bool,
        typer.Option("--debug", "-d", help="Enable debug logging."),
    ] = False,
    log_file: Annotated[
        Path | None,
        typer.Option("--log-file", "-l", help="Log file path."),
    ] = None,
) -> None:
    """Run check-in tasks once.

    Examples:
        smzdm-bot run
        smzdm-bot run --debug
        smzdm-bot run --log-file ./smzdm.log
    """
    setup_logging(enable_debug_logging, log_file)
    print_banner()

    from smzdm_bot.exceptions import SmzdmError
    from smzdm_bot.main import determine_exit_code, run_all_accounts

    try:
        task_results = run_all_accounts()
    except SmzdmError as error:
        console.print(f"[red]Error:[/red] {error}")
        raise typer.Exit(1) from None

    print_run_summary(task_results)
    raise typer.Exit(determine_exit_code(task_results))


@app.command("schedule")
def schedule_command(
    enable_debug_logging: Annotated[
        bool,
        typer.Option("--debug", "-d", help="Enable debug logging."),
    ] = False,
    log_file: Annotated[
        Path | None,
        typer.Option("--log-file", "-l", help="Log file path."),
    ] = None,
) -> None:
    """Run tasks on a schedule.

    The schedule time is determined by:
    - SMZDM_SCH_HOUR and SMZDM_SCH_MINUTE environment variables
    - Random time between 6-10 AM if not set

    Examples:
        smzdm-bot schedule
        SMZDM_SCH_HOUR=9 SMZDM_SCH_MINUTE=30 smzdm-bot schedule
    """
    setup_logging(enable_debug_logging, log_file)
    print_banner()

    console.print("[bold green]Starting scheduler...[/bold green]")
    console.print("[dim]Press Ctrl+C to exit[/dim]\n")

    from smzdm_bot.scheduler import run_scheduler

    run_scheduler()


@app.command("config")
def config_command() -> None:
    """Show current configuration without authentication secrets."""
    from smzdm_bot.config import get_settings
    from smzdm_bot.exceptions import ConfigurationError
    from smzdm_bot.protocol import parse_cookie_header

    print_banner()

    try:
        settings = get_settings()
        user_configs = settings.get_user_configs()
        notification_config = settings.build_notification_config()
        scheduler_config = settings.build_scheduler_config()
        task_policy = settings.build_task_policy()

        # Users table
        account_table = Table(title="👥 Users", show_header=True)
        account_table.add_column("User ID", style="cyan")
        account_table.add_column("Session")
        account_table.add_column("Identity")
        account_table.add_column("SK source")

        for account_index, user_config in enumerate(user_configs, 1):
            parsed_cookies = parse_cookie_header(user_config.cookie)
            session_status = (
                "[green]Ready[/green]" if parsed_cookies.get("sess") else "[red]Missing[/red]"
            )
            identity_ready = bool(
                parsed_cookies.get("smzdm_id") and parsed_cookies.get("device_id")
            )
            identity_status = (
                "[green]Ready[/green]" if identity_ready else "[yellow]Incomplete[/yellow]"
            )
            if user_config.security_key:
                security_key_source = "Configured"
            elif parsed_cookies.get("device_smzdm", "").lower() in {"iphone", "ios"}:
                security_key_source = "Not required"
            elif identity_ready:
                security_key_source = "Generated"
            else:
                security_key_source = "Unavailable"
            account_table.add_row(
                parsed_cookies.get("smzdm_id")
                or user_config.account_label
                or f"Account {account_index}",
                session_status,
                identity_status,
                security_key_source,
            )

        console.print(account_table)
        console.print()

        # Notification table
        notification_table = Table(title="🔔 Notifications", show_header=True)
        notification_table.add_column("Provider", style="cyan")
        notification_table.add_column("Status")

        from smzdm_bot.notifications.manager import CHANNEL_REGISTRY, NotificationManager

        enabled_names = {
            channel.name for channel in NotificationManager(notification_config).enabled_channels()
        }
        provider_configuration_statuses = [
            (name, name in enabled_names) for name in CHANNEL_REGISTRY
        ]

        for provider_name, is_configured in provider_configuration_statuses:
            provider_status = (
                "[green]✓ Enabled[/green]" if is_configured else "[dim]✗ Disabled[/dim]"
            )
            notification_table.add_row(provider_name, provider_status)

        console.print(notification_table)
        console.print()

        task_policy_table = Table(title="🧩 Optional tasks", show_header=True)
        task_policy_table.add_column("Task", style="cyan")
        task_policy_table.add_column("Status")
        optional_task_statuses = [
            ("Follow (reversible)", task_policy.enable_follow_tasks),
            ("Public testing", task_policy.enable_testing_tasks),
            ("Stage rewards", task_policy.enable_activity_reward_claims),
        ]
        for task_name, is_enabled in optional_task_statuses:
            task_status = "[green]✓ Enabled[/green]" if is_enabled else "[dim]✗ Disabled[/dim]"
            task_policy_table.add_row(task_name, task_status)
        console.print(task_policy_table)
        console.print()

        # Scheduler info
        if scheduler_config.hour is None and scheduler_config.minute is None:
            schedule_text = "random (06:00-10:59)"
        else:
            scheduled_hour = (
                f"{scheduler_config.hour:02d}" if scheduler_config.hour is not None else "06-10"
            )
            scheduled_minute = (
                f"{scheduler_config.minute:02d}" if scheduler_config.minute is not None else "00-59"
            )
            schedule_text = f"{scheduled_hour}:{scheduled_minute}"
        console.print(f"⏰ [bold]Schedule:[/bold] {schedule_text} ({scheduler_config.timezone})")

    except ConfigurationError as error:
        console.print(f"[red]Configuration error:[/red] {error.message}")
        raise typer.Exit(1) from None


# Entry points for pyproject.toml
def cli_entry() -> None:
    """CLI entry point."""
    app()


def scheduler_entry() -> None:
    """Scheduler entry point (shortcut)."""
    sys.argv = [sys.argv[0], "schedule"] + sys.argv[1:]
    app()


if __name__ == "__main__":
    app()
