"""Provider protocols. Register new channels without changing account business code."""

import time
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from loguru import logger

from smzdm_bot.notifications.base import Channel, NotificationResult
from smzdm_bot.notifications.signatures import dingtalk_signature, feishu_signature


def bark_targets(value: str) -> list[str]:
    """Accept bare keys and legacy full URLs, preserving order."""
    return [part.strip() for part in value.split(",") if part.strip()]


class BarkChannel(Channel):
    name = "bark"
    credential_fields = ("bark_push_url",)
    success_code = 200

    def configured(self) -> bool:
        return bool(bark_targets(self.config.bark_push_url))

    def send(self, title: str, content: str) -> NotificationResult:
        targets = bark_targets(self.config.bark_push_url)
        delivered = 0
        for index, target in enumerate(targets, 1):
            url = target if "://" in target else f"https://api.day.app/{quote(target, safe='')}"
            try:
                result = self.post(
                    url, json={"title": title, "body": content, "group": "SMZDM Bot"}
                )
            except Exception:
                result = NotificationResult(self.name, False, "delivery exception")
            delivered += result.success
            logger.info(
                "Bark notification {}/{} {}",
                index,
                len(targets),
                "success" if result.success else f"failed: {result.message}",
            )
        success = bool(targets) and delivered == len(targets)
        status = "success" if success else "partial success" if delivered else "failed"
        message = f"{status} ({delivered}/{len(targets)})" if targets else "missing credentials"
        return NotificationResult(self.name, success, message, delivered, len(targets))


class FeishuChannel(Channel):
    name = "feishu"
    credential_fields = ("feishu_webhook",)
    response_codes = ("code", "StatusCode")

    def send(self, title: str, content: str) -> NotificationResult:
        payload: dict[str, object] = {
            "msg_type": "text",
            "content": {"text": f"{title}\n{content}"},
        }
        if self.config.feishu_secret:
            timestamp = int(time.time())
            payload.update(
                timestamp=str(timestamp),
                sign=feishu_signature(self.config.feishu_secret, timestamp),
            )
        return self.post(self.config.feishu_webhook, json=payload)


class DingTalkChannel(Channel):
    name = "dingtalk"
    credential_fields = ("dingtalk_webhook",)
    response_codes = ("errcode",)

    def send(self, title: str, content: str) -> NotificationResult:
        url = self.config.dingtalk_webhook
        if self.config.dingtalk_secret:
            timestamp = int(time.time() * 1000)
            parts = urlsplit(url)
            query = [
                (k, v)
                for k, v in parse_qsl(parts.query, keep_blank_values=True)
                if k not in {"timestamp", "sign"}
            ]
            query.extend(
                [
                    ("timestamp", str(timestamp)),
                    ("sign", dingtalk_signature(self.config.dingtalk_secret, timestamp)),
                ]
            )
            url = urlunsplit(parts._replace(query=urlencode(query)))
        return self.post(url, json={"msgtype": "text", "text": {"content": f"{title}\n{content}"}})


class TelegramChannel(Channel):
    name = "telegram"
    credential_fields = ("telegram_bot_token", "telegram_chat_id")
    response_codes = ("ok",)
    success_code = True

    def send(self, title: str, content: str) -> NotificationResult:
        base = self.config.telegram_api_base_url.rstrip("/") or "https://api.telegram.org"
        return self.post(
            f"{base}/bot{self.config.telegram_bot_token}/sendMessage",
            json={
                "chat_id": self.config.telegram_chat_id,
                "text": f"*{title}*\n\n{content}",
                "parse_mode": "Markdown",
            },
        )


class WeComChannel(Channel):
    name = "wecom"
    credential_fields = ("wecom_webhook",)
    response_codes = ("errcode",)

    def send(self, title: str, content: str) -> NotificationResult:
        return self.post(
            self.config.wecom_webhook,
            json={"msgtype": "text", "text": {"content": f"{title}\n{content}"}},
        )


class PushPlusChannel(Channel):
    name = "pushplus"
    credential_fields = ("push_plus_token",)
    success_code = 200

    def send(self, title: str, content: str) -> NotificationResult:
        return self.post(
            "https://www.pushplus.plus/send",
            json={
                "token": self.config.push_plus_token,
                "title": title,
                "content": content,
                "template": "html",
            },
        )


class ServerChanChannel(Channel):
    name = "serverchan"
    credential_fields = ("server_chan_key",)

    def send(self, title: str, content: str) -> NotificationResult:
        return self.post(
            f"https://sctapi.ftqq.com/{self.config.server_chan_key}.send",
            data={"title": title, "desp": content},
        )
