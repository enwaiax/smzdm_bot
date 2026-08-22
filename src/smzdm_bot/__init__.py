"""SMZDM Bot public package API.

Usage:
    export SMZDM_COOKIE="your_cookie"
    smzdm-bot run

Or in Python:
    >>> from smzdm_bot.main import run_all_accounts
    >>> account_results = run_all_accounts()
"""

from importlib.metadata import PackageNotFoundError, version

from smzdm_bot.client import SmzdmClient
from smzdm_bot.config import (
    NotificationConfig,
    Settings,
    TaskPolicyConfig,
    UserConfig,
    get_settings,
)
from smzdm_bot.exceptions import APIError, ConfigurationError, SmzdmError
from smzdm_bot.models import (
    AccountTaskResult,
    CheckinResult,
    LotteryResult,
    RewardInfo,
    VipInfo,
)
from smzdm_bot.protocol import (
    DEFAULT_APP_PROFILE,
    AppProfile,
    compute_request_signature,
    generate_security_key,
)

try:
    __version__ = version("smzdm-bot")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = [
    "APIError",
    "AccountTaskResult",
    "AppProfile",
    "CheckinResult",
    "ConfigurationError",
    "DEFAULT_APP_PROFILE",
    "LotteryResult",
    "NotificationConfig",
    "RewardInfo",
    "Settings",
    "SmzdmClient",
    "SmzdmError",
    "TaskPolicyConfig",
    "UserConfig",
    "VipInfo",
    "compute_request_signature",
    "generate_security_key",
    "get_settings",
]
