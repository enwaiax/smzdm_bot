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


class NotificationOptions(BaseModel):
    """Shared notification controls; None preserves credential-based opt-in."""

    notify_enabled: bool = True
    notify_channels: str = ""
    notify_timeout: float = Field(default=10.0, gt=0, allow_inf_nan=False)
    notify_on_success: bool = True
    notify_on_failure: bool = True
    notify_bark_enabled: bool | None = None
    notify_feishu_enabled: bool | None = None
    notify_dingtalk_enabled: bool | None = None
    notify_telegram_enabled: bool | None = None
    notify_wecom_enabled: bool | None = None
    notify_pushplus_enabled: bool | None = None
    notify_serverchan_enabled: bool | None = None
    feishu_webhook: str = Field(default="", repr=False)
    feishu_secret: str = Field(default="", repr=False)
    dingtalk_webhook: str = Field(default="", repr=False)
    dingtalk_secret: str = Field(default="", repr=False)


class NotificationConfig(NotificationOptions):
    """Configuration for enabled notification providers."""

    bark_push_url: str = Field(default="", repr=False)
    push_plus_token: str = Field(default="", repr=False)
    server_chan_key: str = Field(default="", repr=False)
    wecom_webhook: str = Field(default="", repr=False)
    telegram_bot_token: str = Field(default="", repr=False)
    telegram_chat_id: str = Field(default="", repr=False)
    telegram_api_base_url: str = Field(default="", repr=False)

    @property
    def has_any_provider(self) -> bool:
        """Return whether at least one complete provider configuration exists."""
        return any(
            [
                self.bark_push_url,
                self.push_plus_token,
                self.server_chan_key,
                self.wecom_webhook,
                self.feishu_webhook,
                self.dingtalk_webhook,
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
