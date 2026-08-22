"""Data models for SMZDM Bot."""

from dataclasses import dataclass, field
from enum import StrEnum

from pydantic import BaseModel, Field


class CheckinResult(BaseModel):
    """Check-in result with API field mapping."""

    consecutive_days: int = Field(alias="daily_num", default=0)
    gold_earned: int = Field(alias="cgold", default=0)
    points_earned: int = Field(alias="cpoints", default=0)
    experience_earned: int = Field(alias="cexperience", default=0)
    account_rank: int = Field(alias="rank", default=0)
    makeup_cards: int = Field(alias="cards", default=0)

    model_config = {"populate_by_name": True}

    def to_message(self) -> str:
        return (
            f"⭐ 签到成功 第{self.consecutive_days}天\n"
            f"🪙 金币: +{self.gold_earned}\n"
            f"💎 积分: +{self.points_earned}\n"
            f"📈 经验: +{self.experience_earned}\n"
            f"🏆 等级: {self.account_rank}\n"
            f"🎫 补签卡: {self.makeup_cards}"
        )


class VipInfo(BaseModel):
    """VIP membership info."""

    membership_level: int = Field(alias="exp_level", default=0)
    level_experience: int = Field(alias="exp_current_level", default=0)
    expiration_date: str = Field(alias="exp_level_expire", default="")

    model_config = {"populate_by_name": True}

    def to_message(self) -> str:
        return (
            f"👑 值会员: V{self.membership_level}\n"
            f"✨ 经验: {self.level_experience}\n"
            f"📅 有效期: {self.expiration_date}"
        )


class RewardInfo(BaseModel):
    """Daily reward info."""

    title: str = ""
    content: str = Field(alias="content_str", default="")
    sub_content: str = ""

    model_config = {"populate_by_name": True}

    @property
    def has_reward(self) -> bool:
        return bool(self.title or self.content)

    def to_message(self) -> str:
        if not self.has_reward:
            return "📦 今日无奖励"
        return f"🎁 {self.title or self.content}"


@dataclass
class LotteryResult:
    """Lottery draw result."""

    success: bool = False
    message: str = "没有抽奖机会"

    def to_message(self) -> str:
        return f"🎰 {self.message}"


class TaskOutcome(StrEnum):
    """Outcome of one optional business task."""

    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class TaskItemResult:
    """Result of one optional business task."""

    task_name: str
    outcome: TaskOutcome
    message: str = ""


@dataclass(slots=True)
class TaskReport:
    """Aggregated optional-task results for one task category."""

    title: str
    items: list[TaskItemResult] = field(default_factory=list)
    details: list[str] = field(default_factory=list)

    @property
    def completed_count(self) -> int:
        return sum(item.outcome is TaskOutcome.COMPLETED for item in self.items)

    @property
    def failed_count(self) -> int:
        return sum(item.outcome is TaskOutcome.FAILED for item in self.items)

    @property
    def skipped_count(self) -> int:
        return sum(item.outcome is TaskOutcome.SKIPPED for item in self.items)

    def to_message(self) -> str:
        summary = (
            f"🧩 {self.title}: 完成 {self.completed_count}, "
            f"跳过 {self.skipped_count}, 失败 {self.failed_count}"
        )
        item_details = [
            f"  • {item.task_name}: {item.message}"
            for item in self.items
            if item.outcome is not TaskOutcome.COMPLETED and item.message
        ]
        return "\n".join([summary, *item_details, *self.details])


@dataclass
class AccountTaskResult:
    """Result of all tasks for a user."""

    user_id: str
    success: bool = True
    checkin: CheckinResult | None = None
    vip_info: VipInfo | None = None
    reward: RewardInfo | None = None
    lottery: LotteryResult | None = None
    task_reports: list[TaskReport] = field(default_factory=list)
    error: str | None = None

    def to_message(self) -> str:
        lines = [f"📋 用户 ID: {self.user_id}", "─" * 20]

        if self.checkin:
            lines.append(self.checkin.to_message())
        if self.vip_info:
            lines.append(self.vip_info.to_message())
        if self.reward:
            lines.append(self.reward.to_message())
        if self.lottery:
            lines.append(self.lottery.to_message())
        lines.extend(task_report.to_message() for task_report in self.task_reports)
        if self.error:
            lines.append(f"❌ {self.error}")

        return "\n".join(lines)
