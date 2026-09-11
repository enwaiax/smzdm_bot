"""Public notification API."""

from smzdm_bot.notifications.base import NotificationChannel, NotificationResult
from smzdm_bot.notifications.manager import NotificationManager

__all__ = ["NotificationChannel", "NotificationManager", "NotificationResult"]
