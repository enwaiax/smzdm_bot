"""Ordered, sequential delivery with per-channel failure isolation."""

import re
from collections.abc import Callable, Mapping

from loguru import logger

from smzdm_bot.config import NotificationConfig
from smzdm_bot.notifications.base import NotificationChannel, NotificationResult
from smzdm_bot.notifications.channels import (
    BarkChannel,
    DingTalkChannel,
    FeishuChannel,
    PushPlusChannel,
    ServerChanChannel,
    TelegramChannel,
    WeComChannel,
)

CHANNEL_REGISTRY: dict[str, Callable[[NotificationConfig], NotificationChannel]] = {
    channel.name: channel
    for channel in (
        BarkChannel,
        FeishuChannel,
        DingTalkChannel,
        TelegramChannel,
        WeComChannel,
        PushPlusChannel,
        ServerChanChannel,
    )
}
DEFAULT_NOTIFICATION_CHANNELS = tuple(CHANNEL_REGISTRY)


class NotificationManager:
    def __init__(
        self,
        config: NotificationConfig,
        registry: Mapping[str, Callable[[NotificationConfig], NotificationChannel]] | None = None,
    ) -> None:
        self.config = config
        self.registry = CHANNEL_REGISTRY if registry is None else registry

    def channel_names(self) -> list[str]:
        names = [
            part.strip().lower() for part in self.config.notify_channels.split(",") if part.strip()
        ]
        return list(dict.fromkeys(names or DEFAULT_NOTIFICATION_CHANNELS))

    def enabled_channels(self) -> list[NotificationChannel]:
        if not self.config.notify_enabled:
            return []
        selected: list[NotificationChannel] = []
        for name in self.channel_names():
            factory = self.registry.get(name)
            if factory is None:
                # Unknown configuration can itself be an accidentally pasted credential.
                safe_name = name if re.fullmatch(r"[a-z]{1,16}", name) else "<redacted>"
                logger.warning("Unknown notification channel: {}", safe_name)
                continue
            try:
                channel = factory(self.config)
                if channel.enabled():
                    selected.append(channel)
            except Exception:
                logger.warning("Notification channel initialization failed")
        return selected

    def send(self, title: str, content: str) -> list[NotificationResult]:
        channels = self.enabled_channels()
        logger.info(
            "Notification enabled channels: {}", ", ".join(c.name for c in channels) or "none"
        )
        results: list[NotificationResult] = []
        for channel in channels:
            logger.info("Sending notification via {}...", channel.name)
            try:
                result = channel.send(title, content)
            except Exception:
                result = NotificationResult(channel.name, False, "delivery exception")
            results.append(result)
            logger.info("{}: {}", channel.name, result.message)
        successful = sum(result.success for result in results)
        logger.info(
            "Notification completed: {} success, {} failed", successful, len(results) - successful
        )
        return results
