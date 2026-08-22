"""Validated runtime configuration models."""

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class UserConfig(BaseModel):
    """Configuration for one SMZDM account."""

    cookie: str
    security_key: str = Field(
        default="",
        validation_alias=AliasChoices("security_key", "sk"),
    )
    account_label: str = Field(
        default="",
        validation_alias=AliasChoices("account_label", "name"),
    )

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("cookie")
    @classmethod
    def validate_cookie(cls, cookie_value: str) -> str:
        """Reject empty cookie values and remove surrounding whitespace."""
        if not cookie_value or not cookie_value.strip():
            raise ValueError("Cookie cannot be empty")
        return cookie_value.strip()


class NotificationConfig(BaseModel):
    """Configuration for enabled notification providers."""

    bark_push_url: str = ""
    push_plus_token: str = ""
    server_chan_key: str = ""
    wecom_webhook: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_api_base_url: str = ""

    @property
    def has_any_provider(self) -> bool:
        """Return whether at least one complete provider configuration exists."""
        return any(
            [
                self.bark_push_url,
                self.push_plus_token,
                self.server_chan_key,
                self.wecom_webhook,
                self.telegram_bot_token and self.telegram_chat_id,
            ]
        )


class SchedulerConfig(BaseModel):
    """Resolved scheduler configuration."""

    hour: int | None = Field(default=None, ge=0, le=23)
    minute: int | None = Field(default=None, ge=0, le=59)
    timezone: str = "Asia/Shanghai"


class TaskPolicyConfig(BaseModel):
    """Safety and opt-in policy for optional account tasks."""

    enable_follow_tasks: bool = True
    enable_testing_tasks: bool = False
    enable_activity_reward_claims: bool = True


__all__ = [
    "NotificationConfig",
    "SchedulerConfig",
    "TaskPolicyConfig",
    "UserConfig",
]
