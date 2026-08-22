"""Notification module for SMZDM Bot.

Simple functions to send notifications via various providers.
"""

import httpx
from loguru import logger

from smzdm_bot.config import NotificationConfig

REQUEST_TIMEOUT_SECONDS = 30.0


def send_bark_notification(
    bark_push_url: str,
    notification_title: str,
    notification_content: str,
) -> bool:
    """Send a notification through a Bark push endpoint."""
    if not bark_push_url:
        return False

    try:
        response = httpx.post(
            bark_push_url,
            json={
                "title": notification_title,
                "body": notification_content,
                "group": "SMZDM Bot",
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if response.json().get("code") == 200:
            logger.success("✅ Bark: 发送成功")
            return True
        logger.warning(f"Bark 发送失败，HTTP {response.status_code}")
    except Exception as error:
        logger.warning(f"Bark 发送异常: {type(error).__name__}")
    return False


def send_push_plus_notification(
    push_plus_token: str,
    notification_title: str,
    notification_content: str,
) -> bool:
    """Send via PushPlus."""
    if not push_plus_token:
        return False

    try:
        response = httpx.post(
            "https://www.pushplus.plus/send",
            json={
                "token": push_plus_token,
                "title": notification_title,
                "content": notification_content,
                "template": "html",
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if response.json().get("code") == 200:
            logger.success("✅ PushPlus: sent")
            return True
        logger.warning(f"PushPlus failed with HTTP {response.status_code}")
    except Exception as error:
        logger.warning(f"PushPlus error: {type(error).__name__}")
    return False


def send_server_chan_notification(
    server_chan_key: str,
    notification_title: str,
    notification_content: str,
) -> bool:
    """Send via ServerChan."""
    if not server_chan_key:
        return False

    try:
        response = httpx.post(
            f"https://sctapi.ftqq.com/{server_chan_key}.send",
            data={"title": notification_title, "desp": notification_content},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if response.json().get("code") == 0:
            logger.success("✅ ServerChan: sent")
            return True
        logger.warning(f"ServerChan failed with HTTP {response.status_code}")
    except Exception as error:
        logger.warning(f"ServerChan error: {type(error).__name__}")
    return False


def send_wecom_notification(
    webhook_url: str,
    notification_title: str,
    notification_content: str,
) -> bool:
    """Send via WeCom Bot."""
    if not webhook_url:
        return False

    try:
        response = httpx.post(
            webhook_url,
            json={
                "msgtype": "text",
                "text": {"content": f"{notification_title}\n{notification_content}"},
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if response.json().get("errcode") == 0:
            logger.success("✅ WeCom: sent")
            return True
        logger.warning(f"WeCom failed with HTTP {response.status_code}")
    except Exception as error:
        logger.warning(f"WeCom error: {type(error).__name__}")
    return False


def send_telegram_notification(
    bot_token: str,
    chat_id: str,
    notification_title: str,
    notification_content: str,
    api_base_url: str = "",
) -> bool:
    """Send via Telegram Bot."""
    if not bot_token or not chat_id:
        return False

    telegram_api_base_url = api_base_url.rstrip("/") if api_base_url else "https://api.telegram.org"
    request_url = f"{telegram_api_base_url}/bot{bot_token}/sendMessage"

    try:
        response = httpx.post(
            request_url,
            json={
                "chat_id": chat_id,
                "text": f"*{notification_title}*\n\n{notification_content}",
                "parse_mode": "Markdown",
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if response.json().get("ok"):
            logger.success("✅ Telegram: sent")
            return True
        logger.warning(f"Telegram failed with HTTP {response.status_code}")
    except Exception as error:
        logger.warning(f"Telegram error: {type(error).__name__}")
    return False


def send_configured_notifications(
    notification_config: NotificationConfig,
    title: str,
    content: str,
) -> int:
    """Send notification via all configured providers.

    Returns:
        Number of successful sends.
    """
    if not notification_config.has_any_provider:
        logger.info("No notification providers configured")
        return 0

    successful_delivery_count = 0

    if notification_config.bark_push_url:
        successful_delivery_count += send_bark_notification(
            notification_config.bark_push_url,
            title,
            content,
        )

    if notification_config.push_plus_token:
        successful_delivery_count += send_push_plus_notification(
            notification_config.push_plus_token,
            title,
            content,
        )

    if notification_config.server_chan_key:
        successful_delivery_count += send_server_chan_notification(
            notification_config.server_chan_key,
            title,
            content,
        )

    if notification_config.wecom_webhook:
        successful_delivery_count += send_wecom_notification(
            notification_config.wecom_webhook,
            title,
            content,
        )

    if notification_config.telegram_bot_token and notification_config.telegram_chat_id:
        successful_delivery_count += send_telegram_notification(
            notification_config.telegram_bot_token,
            notification_config.telegram_chat_id,
            title,
            content,
            notification_config.telegram_api_base_url,
        )

    logger.info(f"通知发送成功: {successful_delivery_count}")
    return successful_delivery_count
