"""Backward-compatible notification helpers backed by the channel manager."""

from smzdm_bot.config import NotificationConfig
from smzdm_bot.notifications import NotificationManager
from smzdm_bot.notifications.channels import (
    BarkChannel,
    PushPlusChannel,
    ServerChanChannel,
    TelegramChannel,
    WeComChannel,
)


def send_bark_notification(
    bark_push_url: str,
    notification_title: str,
    notification_content: str,
) -> bool:
    return (
        BarkChannel(NotificationConfig(bark_push_url=bark_push_url))
        .send(notification_title, notification_content)
        .success
    )


def send_push_plus_notification(
    push_plus_token: str,
    notification_title: str,
    notification_content: str,
) -> bool:
    return (
        PushPlusChannel(NotificationConfig(push_plus_token=push_plus_token))
        .send(notification_title, notification_content)
        .success
    )


def send_server_chan_notification(
    server_chan_key: str,
    notification_title: str,
    notification_content: str,
) -> bool:
    return (
        ServerChanChannel(NotificationConfig(server_chan_key=server_chan_key))
        .send(notification_title, notification_content)
        .success
    )


def send_wecom_notification(
    webhook_url: str,
    notification_title: str,
    notification_content: str,
) -> bool:
    return (
        WeComChannel(NotificationConfig(wecom_webhook=webhook_url))
        .send(notification_title, notification_content)
        .success
    )


def send_telegram_notification(
    bot_token: str,
    chat_id: str,
    notification_title: str,
    notification_content: str,
    api_base_url: str = "",
) -> bool:
    return (
        TelegramChannel(
            NotificationConfig(
                telegram_bot_token=bot_token,
                telegram_chat_id=chat_id,
                telegram_api_base_url=api_base_url,
            )
        )
        .send(notification_title, notification_content)
        .success
    )


def send_configured_notifications(
    notification_config: NotificationConfig,
    title: str,
    content: str,
) -> int:
    """Return successful channel count (Bark counts once if all devices succeed)."""
    return sum(
        result.success for result in NotificationManager(notification_config).send(title, content)
    )
