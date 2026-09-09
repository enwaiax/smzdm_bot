"""Platform-specific check-in request tests."""

from smzdm_bot.tasks.checkin import claim_extra_checkin_reward, fetch_vip_info


class RecordingCheckinClient:
    """Record calls made by check-in helpers."""

    def __init__(self, *, is_iphone: bool) -> None:
        self.is_iphone = is_iphone
        self.calls: list[tuple[str, dict | None]] = []

    def post(self, endpoint_path: str, extra_form_fields: dict | None = None) -> dict:
        self.calls.append((endpoint_path, extra_form_fields))
        if endpoint_path == "/vip":
            return {"error_code": "0", "data": {"vip": {}}}
        return {"error_code": "0", "data": {"rows": []}}


def test_iphone_vip_uses_captured_11_1_92_fields() -> None:
    client = RecordingCheckinClient(is_iphone=True)

    fetch_vip_info(client)  # type: ignore[arg-type]

    assert client.calls == [
        (
            "/vip",
            {
                "activity_is_new_user": "0",
                "create_center_view": "empty",
                "with_is_create": "1",
            },
        )
    ]


def test_iphone_checkin_view_uses_installation_flag() -> None:
    client = RecordingCheckinClient(is_iphone=True)

    assert claim_extra_checkin_reward(client) is False  # type: ignore[arg-type]

    assert client.calls == [("/checkin/show_view_v2", {"is_install_zhangdama": "0"})]


def test_android_checkin_helpers_preserve_existing_fields() -> None:
    client = RecordingCheckinClient(is_iphone=False)

    fetch_vip_info(client)  # type: ignore[arg-type]
    assert claim_extra_checkin_reward(client) is False  # type: ignore[arg-type]

    assert client.calls == [("/vip", None), ("/checkin/show_view_v2", None)]
