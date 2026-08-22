from smzdm_bot.models import AccountTaskResult, CheckinResult, VipInfo


def test_checkin_result_maps_api_fields_to_descriptive_names() -> None:
    checkin_result = CheckinResult(
        daily_num=7,
        cgold=2,
        cpoints=3,
        cexperience=4,
        rank=5,
        cards=1,
    )

    assert checkin_result.consecutive_days == 7
    assert checkin_result.gold_earned == 2
    assert checkin_result.points_earned == 3
    assert checkin_result.experience_earned == 4
    assert checkin_result.account_rank == 5
    assert checkin_result.makeup_cards == 1


def test_vip_info_maps_api_fields_to_membership_names() -> None:
    vip_info = VipInfo(
        exp_level=3,
        exp_current_level=120,
        exp_level_expire="2099-01-01",
    )

    assert vip_info.membership_level == 3
    assert vip_info.level_experience == 120
    assert vip_info.expiration_date == "2099-01-01"


def test_task_result_uses_user_id_in_message() -> None:
    task_result = AccountTaskResult(user_id="10001")

    assert "用户 ID: 10001" in task_result.to_message()
