"""SMZDM application protocol constants and cryptographic helpers."""

from __future__ import annotations

import base64
import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import unquote

from Crypto.Cipher import DES
from Crypto.Util.Padding import pad


@dataclass(frozen=True, slots=True)
class AppProfile:
    """Versioned Android application protocol profile."""

    version: str
    version_code: str
    sign_key: str
    sk_key: str


# Verified against com.smzdm.client.android 11.1.90 (versionCode 1190).
DEFAULT_APP_PROFILE = AppProfile(
    version="11.1.90",
    version_code="1190",
    sign_key="apr1$AwP!wRRT$gJ/q.X24poeBInlUJC",
    sk_key="geZm53XAspb02exN",
)

# Verified against decrypted com.smzdm.client.ios 11.1.92 and matching HAR requests.
IPHONE_APP_PROFILE = AppProfile(
    version="11.1.92",
    version_code="11.1.92",
    sign_key="zok5JtAq3$QixaA%mncn*jGWlEpSL3E1",
    sk_key="",
)


def resolve_app_profile(platform_name: str) -> AppProfile:
    """Return the verified protocol profile for a captured app platform."""
    if platform_name.strip().lower() in {"iphone", "ios"}:
        return IPHONE_APP_PROFILE
    return DEFAULT_APP_PROFILE


def parse_cookie_header(cookie_header: str) -> dict[str, str]:
    """Parse a Cookie header into decoded key-value pairs."""
    normalized_cookie_header = cookie_header if cookie_header.endswith(";") else f"{cookie_header};"
    return {
        cookie_name.strip(): unquote(cookie_value.strip())
        for cookie_name, cookie_value in re.findall(
            r"([^=;]+)=([^;]*);",
            normalized_cookie_header,
        )
    }


def compute_request_signature(
    form_fields: Mapping[str, object],
    app_profile: AppProfile = DEFAULT_APP_PROFILE,
) -> str:
    """Generate the uppercase MD5 request signature used by the Android app."""
    signature_components: list[str] = []
    for field_name, field_value in sorted(form_fields.items()):
        normalized_value = str(field_value).replace(" ", "")
        if normalized_value:
            signature_components.append(f"{field_name}={normalized_value}")

    signature_payload = "&".join(signature_components) + f"&key={app_profile.sign_key}"
    return hashlib.md5(signature_payload.encode()).hexdigest().upper()


def generate_security_key(
    smzdm_user_id: str,
    device_id: str,
    app_profile: AppProfile = DEFAULT_APP_PROFILE,
) -> str:
    """Generate Base64(DES-ECB-PKCS5(smzdm_user_id + device_id))."""
    if not smzdm_user_id:
        raise ValueError("smzdm_user_id must not be empty")
    if not device_id:
        raise ValueError("device_id must not be empty")

    des_key = app_profile.sk_key.encode()[: DES.block_size]
    plaintext_bytes = (smzdm_user_id + device_id).encode()
    des_cipher = DES.new(des_key, DES.MODE_ECB)
    ciphertext = des_cipher.encrypt(pad(plaintext_bytes, DES.block_size))
    return base64.b64encode(ciphertext).decode()


__all__ = [
    "AppProfile",
    "DEFAULT_APP_PROFILE",
    "IPHONE_APP_PROFILE",
    "compute_request_signature",
    "generate_security_key",
    "parse_cookie_header",
    "resolve_app_profile",
]
