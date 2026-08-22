"""Check-in, membership, and reward operations."""

from loguru import logger

from smzdm_bot.client import SmzdmClient
from smzdm_bot.models import CheckinResult, RewardInfo, VipInfo


def perform_daily_checkin(smzdm_client: SmzdmClient) -> CheckinResult:
    """Perform the account's daily check-in."""
    response_payload = smzdm_client.post("/checkin")
    checkin_result = CheckinResult(**response_payload.get("data", {}))
    logger.info(f"连续签到 {checkin_result.consecutive_days} 天")
    return checkin_result


def fetch_vip_info(smzdm_client: SmzdmClient) -> VipInfo:
    """Fetch current VIP membership information."""
    response_payload = smzdm_client.post("/vip")
    vip_info = VipInfo(**response_payload.get("data", {}).get("vip", {}))
    logger.info(f"VIP 等级: {vip_info.membership_level}")
    return vip_info


def fetch_normal_checkin_reward(smzdm_client: SmzdmClient) -> RewardInfo:
    """Fetch the normal reward associated with today's check-in."""
    try:
        response_payload = smzdm_client.post("/checkin/all_reward")
    except Exception:
        return RewardInfo()

    reward_payload = response_payload.get("data", {}).get("normal_reward", {}).get("gift", {})
    reward_info = RewardInfo(**reward_payload)
    if reward_info.has_reward:
        logger.info(f"奖励: {reward_info.title or reward_info.content}")
    return reward_info


def claim_extra_checkin_reward(smzdm_client: SmzdmClient) -> bool:
    """Claim an available consecutive check-in reward."""
    response_payload = smzdm_client.post("/checkin/show_view_v2")
    for response_row in response_payload.get("data", {}).get("rows", []):
        if response_row.get("cell_type") != "18001":
            continue

        checkin_payload = response_row.get("cell_data", {}).get(
            "checkin_continue",
            {},
        )
        if checkin_payload.get("continue_checkin_reward_show"):
            smzdm_client.post("/checkin/extra_reward")
            logger.info("额外奖励已领取!")
            return True

    logger.info("无额外奖励")
    return False


__all__ = [
    "claim_extra_checkin_reward",
    "fetch_normal_checkin_reward",
    "fetch_vip_info",
    "perform_daily_checkin",
]
