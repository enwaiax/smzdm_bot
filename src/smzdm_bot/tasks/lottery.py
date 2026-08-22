"""Lottery-related account operations."""

import re
from dataclasses import dataclass

from loguru import logger

from smzdm_bot.client import SmzdmClient
from smzdm_bot.models import LotteryResult
from smzdm_bot.tasks.execution import wait_for_random_delay

CROWD_MOBILE_BASE_URL = "https://zhiyou.m.smzdm.com"


@dataclass(frozen=True, slots=True)
class CrowdLotteryOption:
    """One crowd-lottery option parsed from the account page."""

    crowd_id: str
    title: str
    silver_cost: int


def perform_task_lottery(smzdm_client: SmzdmClient) -> LotteryResult:
    """Use the current APP task-lottery endpoint once."""
    try:
        response_payload = smzdm_client.post("/task/lottery")
    except Exception as error:
        logger.debug(f"任务抽奖不可用: {error}")
        return LotteryResult(success=False, message="没有抽奖机会")

    lottery_payload = response_payload.get("data", {})
    if not isinstance(lottery_payload, dict):
        return LotteryResult(success=False, message="抽奖响应格式异常")

    result_message = (
        lottery_payload.get("gift_name")
        or lottery_payload.get("description")
        or response_payload.get("error_msg")
        or "抽奖完成"
    )
    return LotteryResult(success=True, message=str(result_message))


def enter_free_crowd_lotteries(smzdm_client: SmzdmClient) -> int:
    """Enter all currently visible free crowd lotteries."""
    crowd_lottery_options = [
        option for option in _fetch_crowd_lottery_options(smzdm_client) if option.silver_cost == 0
    ]
    if not crowd_lottery_options:
        logger.info("无免费抽奖")
        return 0

    successful_entry_count = 0
    for crowd_lottery_option in crowd_lottery_options:
        successful_entry_count += _enter_crowd_lottery(
            smzdm_client,
            crowd_lottery_option.crowd_id,
        )
        wait_for_random_delay((3, 8))

    return successful_entry_count


def _fetch_crowd_lottery_options(
    smzdm_client: SmzdmClient,
) -> list[CrowdLotteryOption]:
    """Extract crowd-lottery identifiers, titles, and prices."""
    try:
        page_html = smzdm_client.get_html(f"{smzdm_client.WEB_BASE_URL}/user/crowd/")
    except Exception:
        return []

    button_pattern = re.compile(
        r"<button\s+(?P<attributes>[^>]*data-crowd_id=\"\d+\"[^>]*)>"
        r"(?P<body>[\s\S]*?)</button>",
        re.I,
    )
    crowd_lottery_options: list[CrowdLotteryOption] = []
    for button_match in button_pattern.finditer(page_html):
        attributes = button_match.group("attributes")
        body = button_match.group("body")
        crowd_id_match = re.search(r'data-crowd_id="(\d+)"', attributes, re.I)
        if crowd_id_match is None:
            continue
        title_match = re.search(r'data-title="([^"]*)"', attributes, re.I)
        price_match = re.search(
            r'class="reduceNumber"[^>]*>\s*-(\d+)\s*<',
            body,
            re.I,
        )
        if price_match is None:
            continue
        crowd_lottery_options.append(
            CrowdLotteryOption(
                crowd_id=crowd_id_match.group(1),
                title=title_match.group(1) if title_match else "",
                silver_cost=int(price_match.group(1)),
            )
        )
    return crowd_lottery_options


def _enter_crowd_lottery(
    smzdm_client: SmzdmClient,
    crowd_lottery_id: str,
) -> int:
    """Enter one crowd lottery and return one on success."""
    referer_url = f"{CROWD_MOBILE_BASE_URL}/user/crowd/p/{crowd_lottery_id}/"
    try:
        response_payload = smzdm_client.post_unsigned_web(
            f"{CROWD_MOBILE_BASE_URL}/user/crowd/ajax_participate",
            form_fields={
                "crowd_id": crowd_lottery_id,
                "sourcePage": referer_url,
                "client_type": "android",
                "sourceRoot": "个人中心",
                "sourceMode": "幸运屋抽奖",
                "price_id": 1,
            },
            referer_url=referer_url,
        )
    except Exception as error:
        logger.debug(f"幸运屋抽奖失败: {error}")
        return 0

    if str(response_payload.get("error_code", "")) != "0":
        return 0

    result_message = re.sub(
        r"<[^>]+>",
        "",
        response_payload.get("data", {}).get("msg", ""),
    )
    logger.info(f"幸运屋: {result_message}")
    return 1


__all__ = [
    "CrowdLotteryOption",
    "enter_free_crowd_lotteries",
    "perform_task_lottery",
]
