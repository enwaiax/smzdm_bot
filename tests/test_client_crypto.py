import pytest

from smzdm_bot.client import SmzdmClient
from smzdm_bot.config import UserConfig
from smzdm_bot.exceptions import ConfigurationError
from smzdm_bot.protocol import (
    IPHONE_APP_PROFILE,
    AppProfile,
    compute_request_signature,
    generate_security_key,
    parse_cookie_header,
)

SYNTHETIC_SMZDM_USER_ID = "1234567890"
SYNTHETIC_DEVICE_ID = "A" * 32
EXPECTED_SECURITY_KEY = "vdAAnkDyJamAB72pBIuZ3Dc9rAKa8xjBNz2sAprzGME3PawCmvMYwTgUFJgc/1p1"


def test_generate_security_key_matches_synthetic_vector() -> None:
    assert (
        generate_security_key(SYNTHETIC_SMZDM_USER_ID, SYNTHETIC_DEVICE_ID) == EXPECTED_SECURITY_KEY
    )


@pytest.mark.parametrize(
    ("smzdm_user_id", "device_id"),
    [
        ("", SYNTHETIC_DEVICE_ID),
        (SYNTHETIC_SMZDM_USER_ID, ""),
    ],
)
def test_generate_security_key_rejects_missing_identity(
    smzdm_user_id: str,
    device_id: str,
) -> None:
    with pytest.raises(ValueError):
        generate_security_key(smzdm_user_id, device_id)


def test_request_signature_matches_vector_regardless_of_input_order() -> None:
    form_fields = {
        "token": "synthetic-session",
        "time": "1700000000000",
        "v": "10.4.26",
        "f": "android",
        "sk": "synthetic-sk",
        "basic_v": "0",
        "weixin": "1",
    }
    reversed_form_fields = dict(reversed(list(form_fields.items())))

    assert compute_request_signature(form_fields) == "3EF3E1F1EC9C7A13919F6A60A27E456E"
    assert compute_request_signature(reversed_form_fields) == compute_request_signature(form_fields)


def test_request_signature_ignores_empty_values_and_removes_ascii_spaces() -> None:
    assert compute_request_signature({"value": "a b c", "empty": ""}) == compute_request_signature(
        {"value": "abc"}
    )


def test_request_signature_preserves_non_space_whitespace_like_android_app() -> None:
    assert compute_request_signature({"value": "a\tb\n"}) != compute_request_signature(
        {"value": "ab"}
    )


def test_request_signature_accepts_a_versioned_app_profile() -> None:
    app_profile = AppProfile(
        version="test",
        version_code="1",
        sign_key="test-sign-key",
        sk_key="12345678",
    )

    assert (
        compute_request_signature({"value": "abc"}, app_profile)
        == "D6854AE2D892FB744E219B261089942D"
    )


def test_parse_cookie_header_decodes_values_without_trailing_semicolon() -> None:
    parsed_cookies = parse_cookie_header("sess=session%2Bvalue; smzdm_id=1234567890")

    assert parsed_cookies == {"sess": "session+value", "smzdm_id": "1234567890"}


def test_client_generates_security_key_from_cookie_identity() -> None:
    user_config = UserConfig(
        cookie=(
            f"sess=synthetic-session; smzdm_id={SYNTHETIC_SMZDM_USER_ID}; "
            f"device_id={SYNTHETIC_DEVICE_ID};"
        )
    )

    with SmzdmClient(user_config) as smzdm_client:
        assert smzdm_client.security_key == EXPECTED_SECURITY_KEY


def test_client_requires_device_identity_for_automatic_sk() -> None:
    user_config = UserConfig(cookie=f"sess=synthetic-session; smzdm_id={SYNTHETIC_SMZDM_USER_ID};")

    with pytest.raises(ConfigurationError, match="device_id"):
        SmzdmClient(user_config)


def test_configured_security_key_does_not_require_device_identity() -> None:
    user_config = UserConfig(
        cookie="sess=synthetic-session;",
        security_key="configured-sk",
    )

    with SmzdmClient(user_config) as smzdm_client:
        assert smzdm_client.security_key == "configured-sk"


def test_client_uses_apk_verified_default_app_version() -> None:
    user_config = UserConfig(
        cookie="sess=synthetic-session;",
        security_key="configured-sk",
    )

    with SmzdmClient(user_config) as smzdm_client:
        assert smzdm_client._build_app_headers()["User-Agent"] == (
            "smzdm_android_V11.1.90 rv:1190 (Redmi;Android10;zh)smzdmapp"
        )


def test_client_selects_iphone_profile_and_cookie_version() -> None:
    user_config = UserConfig(
        cookie=(
            "sess=synthetic-session; smzdm_id=1234567890; device_id=device; "
            "device_smzdm=iphone; v=11.1.92; device_smzdm_version_code=172.4;"
        )
    )

    with SmzdmClient(user_config) as smzdm_client:
        assert smzdm_client.is_iphone is True
        assert smzdm_client.security_key == ""
        assert smzdm_client._app_profile is IPHONE_APP_PROFILE
        assert smzdm_client._app_version == "11.1.92"


def test_iphone_checkin_signature_matches_captured_11_1_92_vector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_config = UserConfig(
        cookie=(
            "sess=synthetic-session; smzdm_id=1234567890; device_id=device; "
            "device_smzdm=iphone; v=11.1.92;"
        )
    )
    monkeypatch.setattr("smzdm_bot.client.time.time", lambda: 1788879771)

    with SmzdmClient(user_config) as smzdm_client:
        signed_form = smzdm_client._build_signed_form()

    assert signed_form == {
        "basic_v": "0",
        "f": "iphone",
        "sign": "3BFD756803D6619AEC658294B4BAB0A2",
        "time": "1788879771000",
        "v": "11.1.92",
        "weixin": "1",
        "zhuanzai_ab": "d",
    }


def test_signed_form_can_omit_user_api_session_fields() -> None:
    user_config = UserConfig(
        cookie="sess=synthetic-session;",
        security_key="configured-sk",
    )

    with SmzdmClient(user_config) as smzdm_client:
        signed_form = smzdm_client._build_signed_form(
            {"page": 1},
            include_session_fields=False,
        )

    assert "token" not in signed_form
    assert "sk" not in signed_form
    assert signed_form["page"] == 1
    assert signed_form["sign"]


def test_signed_form_includes_user_api_session_fields_by_default() -> None:
    user_config = UserConfig(
        cookie="sess=synthetic-session;",
        security_key="configured-sk",
    )

    with SmzdmClient(user_config) as smzdm_client:
        signed_form = smzdm_client._build_signed_form({"page": 1})

    assert signed_form["token"] == "synthetic-session"
    assert signed_form["sk"] == "configured-sk"
    assert signed_form["sign"]


def test_web_origin_uses_only_referer_origin() -> None:
    user_config = UserConfig(
        cookie="sess=synthetic-session;",
        security_key="configured-sk",
    )

    with SmzdmClient(user_config) as smzdm_client:
        headers = smzdm_client._build_web_headers(
            "https://example.com/user/crowd/p/123/",
        )

    assert headers["Referer"] == "https://example.com/user/crowd/p/123/"
    assert headers["Origin"] == "https://example.com"
