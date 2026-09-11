"""Environment-backed application settings."""

import json
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AliasChoices, Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from smzdm_bot.config.models import (
    NotificationConfig,
    NotificationOptions,
    SchedulerConfig,
    TaskPolicyConfig,
    UserConfig,
)
from smzdm_bot.exceptions import ConfigurationError


class Settings(BaseSettings, NotificationOptions):
    """Application settings loaded from ``SMZDM_*`` environment variables."""

    cookie: str = ""
    security_key: str = Field(
        default="",
        validation_alias=AliasChoices("SMZDM_SK", "security_key", "sk"),
    )
    users_json: str = Field(
        default="",
        validation_alias=AliasChoices("SMZDM_USERS", "users_json", "users"),
    )

    bark_push_url: str = Field(
        default="",
        validation_alias=AliasChoices(
            "SMZDM_BARK_PUSH",
            "SMZDM_BARK_URL",
            "bark_push_url",
            "bark_push",
        ),
    )
    push_plus_token: str = ""
    server_chan_key: str = Field(
        default="",
        validation_alias=AliasChoices("SMZDM_SC_KEY", "server_chan_key", "sc_key"),
    )
    wecom_webhook: str = ""
    telegram_bot_token: str = Field(
        default="",
        validation_alias=AliasChoices(
            "SMZDM_TG_BOT_TOKEN",
            "telegram_bot_token",
            "tg_bot_token",
        ),
    )
    telegram_chat_id: str = Field(
        default="",
        validation_alias=AliasChoices(
            "SMZDM_TG_USER_ID",
            "telegram_chat_id",
            "tg_user_id",
        ),
    )
    telegram_api_base_url: str = Field(
        default="",
        validation_alias=AliasChoices(
            "SMZDM_TG_API_BASE",
            "telegram_api_base_url",
            "tg_api_base",
        ),
    )

    enable_follow_tasks: bool = True
    enable_testing_tasks: bool = False
    enable_activity_reward_claims: bool = True

    schedule_hour: int | None = Field(
        default=None,
        ge=0,
        le=23,
        validation_alias=AliasChoices(
            "SMZDM_SCH_HOUR",
            "schedule_hour",
            "sch_hour",
        ),
    )
    schedule_minute: int | None = Field(
        default=None,
        ge=0,
        le=59,
        validation_alias=AliasChoices(
            "SMZDM_SCH_MINUTE",
            "schedule_minute",
            "sch_minute",
        ),
    )
    timezone: str = "Asia/Shanghai"
    debug: bool = False

    model_config = SettingsConfigDict(
        env_prefix="SMZDM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, timezone_name: str) -> str:
        """Ensure APScheduler receives a valid IANA timezone."""
        try:
            ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as error:
            raise ValueError(f"Unknown timezone: {timezone_name}") from error
        return timezone_name

    def get_user_configs(self) -> list[UserConfig]:
        """Build account configurations from single- or multi-account settings."""
        user_configs: list[UserConfig] = []

        if self.users_json:
            user_configs.extend(self._parse_user_configs())

        if not user_configs and self.cookie:
            user_configs.append(
                UserConfig(
                    cookie=self.cookie,
                    security_key=self.security_key,
                    account_label="default",
                )
            )

        if not user_configs:
            raise ConfigurationError(
                "No users configured. Set SMZDM_COOKIE or SMZDM_USERS environment variable."
            )

        return user_configs

    def _parse_user_configs(self) -> list[UserConfig]:
        """Parse and validate the ``SMZDM_USERS`` JSON value."""
        try:
            users_payload = json.loads(self.users_json)
        except json.JSONDecodeError as error:
            raise ConfigurationError(f"Invalid SMZDM_USERS JSON format: {error}") from error

        if not isinstance(users_payload, list):
            raise ConfigurationError("SMZDM_USERS must be a JSON array")

        user_configs: list[UserConfig] = []
        for user_index, user_payload in enumerate(users_payload, 1):
            if not isinstance(user_payload, dict) or not user_payload.get("cookie"):
                raise ConfigurationError(
                    f"SMZDM_USERS item {user_index} must contain a non-empty cookie"
                )

            user_configs.append(
                UserConfig(
                    cookie=user_payload["cookie"],
                    security_key=user_payload.get(
                        "security_key",
                        user_payload.get("sk", ""),
                    ),
                    account_label=user_payload.get(
                        "account_label",
                        user_payload.get("name", f"User{user_index}"),
                    ),
                )
            )

        return user_configs

    def build_notification_config(self) -> NotificationConfig:
        """Build the provider-neutral notification configuration."""
        return NotificationConfig(
            **{name: getattr(self, name) for name in NotificationOptions.model_fields},
            bark_push_url=self.bark_push_url,
            push_plus_token=self.push_plus_token,
            server_chan_key=self.server_chan_key,
            wecom_webhook=self.wecom_webhook,
            telegram_bot_token=self.telegram_bot_token,
            telegram_chat_id=self.telegram_chat_id,
            telegram_api_base_url=self.telegram_api_base_url,
        )

    def build_scheduler_config(self) -> SchedulerConfig:
        """Build the scheduler configuration."""
        return SchedulerConfig(
            hour=self.schedule_hour,
            minute=self.schedule_minute,
            timezone=self.timezone,
        )

    def build_task_policy(self) -> TaskPolicyConfig:
        """Build the optional-task execution policy."""
        return TaskPolicyConfig(
            enable_follow_tasks=self.enable_follow_tasks,
            enable_testing_tasks=self.enable_testing_tasks,
            enable_activity_reward_claims=self.enable_activity_reward_claims,
        )


_cached_settings: Settings | None = None


def _load_settings() -> Settings:
    """Load settings while keeping validation errors secret-safe."""
    try:
        return Settings()
    except ValidationError as error:
        validation_messages = "; ".join(
            f"{'.'.join(map(str, validation_error['loc']))}: {validation_error['msg']}"
            for validation_error in error.errors(include_input=False)
        )
        raise ConfigurationError(f"Invalid configuration: {validation_messages}") from error


def get_settings() -> Settings:
    """Return the lazily loaded process-wide settings instance."""
    global _cached_settings
    if _cached_settings is None:
        _cached_settings = _load_settings()
    return _cached_settings


def reload_settings() -> Settings:
    """Reload and return the process-wide settings instance."""
    global _cached_settings
    _cached_settings = _load_settings()
    return _cached_settings


__all__ = ["Settings", "get_settings", "reload_settings"]
