"""SMZDM HTTP 客户端 - 只负责请求和签名。"""

import json
import random
import re
import time
from urllib.parse import urlsplit

import httpx
from loguru import logger

from smzdm_bot.config import UserConfig
from smzdm_bot.exceptions import APIError, ConfigurationError
from smzdm_bot.protocol import (
    DEFAULT_APP_PROFILE,
    AppProfile,
    compute_request_signature,
    generate_security_key,
    parse_cookie_header,
)


def parse_jsonp_response(response_text: str) -> dict | None:
    """解析 JSONP 响应。"""
    json_object_match = re.search(r"\{.*\}", response_text)
    return json.loads(json_object_match.group()) if json_object_match else None


class SmzdmClient:
    """SMZDM HTTP 客户端。"""

    API_BASE_URL = "https://user-api.smzdm.com"
    WEB_BASE_URL = "https://zhiyou.smzdm.com"
    SUBSCRIPTION_API_BASE_URL = "https://dingyue-api.smzdm.com"
    ARTICLE_API_BASE_URL = "https://article-api.smzdm.com"
    BRAND_API_BASE_URL = "https://brand-api.smzdm.com"
    REQUEST_TIMEOUT_SECONDS = 30.0

    def __init__(
        self,
        user_config: UserConfig,
        app_profile: AppProfile = DEFAULT_APP_PROFILE,
    ) -> None:
        self._cookie_header = user_config.cookie.strip()
        self._parsed_cookies = parse_cookie_header(self._cookie_header)
        self._app_profile = app_profile

        if not self._parsed_cookies.get("sess"):
            raise APIError("Cookie 缺少 sess 字段")

        self.smzdm_user_id = self._parsed_cookies.get("smzdm_id", "")

        # 设备信息
        self._app_version = self._parsed_cookies.get("device_smzdm_version", app_profile.version)
        self._platform_name = self._parsed_cookies.get("device_smzdm", "android")
        self._device_id = self._parsed_cookies.get("device_id", "")

        # SK: 优先使用配置，否则自动生成
        if user_config.security_key:
            self._security_key = user_config.security_key
        else:
            missing_cookie_fields = [
                field_name
                for field_name, field_value in (
                    ("smzdm_id", self.smzdm_user_id),
                    ("device_id", self._device_id),
                )
                if not field_value
            ]
            if missing_cookie_fields:
                missing_field_names = ", ".join(missing_cookie_fields)
                raise ConfigurationError(f"自动生成 SK 需要 Cookie 包含字段: {missing_field_names}")
            self._security_key = generate_security_key(
                self.smzdm_user_id,
                self._device_id,
                app_profile,
            )
            logger.debug("SK 自动生成成功")

        self._http_client = httpx.Client(timeout=self.REQUEST_TIMEOUT_SECONDS)

    @property
    def security_key(self) -> str:
        """Return the configured or generated request security key."""
        return self._security_key

    def close(self) -> None:
        self._http_client.close()

    def __enter__(self) -> "SmzdmClient":
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # ========== 请求头 ==========

    def _build_app_headers(self) -> dict[str, str]:
        """APP 请求头。"""
        version_code = self._parsed_cookies.get(
            "device_smzdm_version_code",
            self._app_profile.version_code,
        )
        device_model = self._parsed_cookies.get("device_type", "Redmi")
        system_version = self._parsed_cookies.get("device_system_version", "10")
        platform_label = self._platform_name.capitalize()
        user_agent = (
            f"smzdm_{self._platform_name}_V{self._app_version} rv:{version_code} "
            f"({device_model};{platform_label}{system_version};zh)smzdmapp"
        )
        return {
            "User-Agent": user_agent,
            "Content-Type": "application/x-www-form-urlencoded",
            "Cookie": self._cookie_header,
            "request_key": str(random.randint(10**15, 10**16)),
        }

    def _build_web_headers(self, referer_url: str | None = None) -> dict[str, str]:
        """Web 请求头。"""
        version_code = self._parsed_cookies.get(
            "device_smzdm_version_code",
            self._app_profile.version_code,
        )
        user_agent = (
            f"Mozilla/5.0 (Linux; Android 10; Redmi) AppleWebKit/537.36 "
            f"Chrome/95.0.4638.74 Mobile Safari/537.36 "
            f"smzdm_android_V{self._app_version} rv:{version_code} smzdmapp"
        )
        headers = {
            "Cookie": self._cookie_header,
            "User-Agent": user_agent,
        }
        if referer_url:
            headers["Referer"] = referer_url
            parsed_referer_url = urlsplit(referer_url)
            headers["Origin"] = f"{parsed_referer_url.scheme}://{parsed_referer_url.netloc}"
        return headers

    # ========== 请求方法 ==========

    def _build_signed_form(
        self,
        extra_form_fields: dict | None = None,
        *,
        include_session_fields: bool = True,
    ) -> dict:
        """构建签名表单。"""
        form_fields = {
            "weixin": "1",
            "basic_v": "0",
            "f": self._platform_name,
            "v": self._app_version,
            "time": f"{int(time.time())}000",
        }
        if include_session_fields:
            form_fields["token"] = self._parsed_cookies.get("sess", "")
            if self._security_key:
                form_fields["sk"] = self._security_key
        if extra_form_fields:
            form_fields.update(extra_form_fields)
        form_fields["sign"] = compute_request_signature(
            form_fields,
            self._app_profile,
        )
        return form_fields

    def post(
        self,
        endpoint_path: str,
        extra_form_fields: dict | None = None,
        base_url: str | None = None,
        *,
        include_session_fields: bool = True,
    ) -> dict:
        """发送签名 POST 请求。"""
        request_url = (base_url or self.API_BASE_URL) + endpoint_path
        response = self._http_client.post(
            request_url,
            data=self._build_signed_form(
                extra_form_fields,
                include_session_fields=include_session_fields,
            ),
            headers=self._build_app_headers(),
        )
        response.raise_for_status()

        response_payload = response.json()
        api_error_code = response_payload.get("error_code")
        if api_error_code is not None and str(api_error_code) != "0":
            numeric_error_code = (
                int(api_error_code) if str(api_error_code).lstrip("-").isdigit() else None
            )
            raise APIError(
                response_payload.get("error_msg", "API error"),
                error_code=numeric_error_code,
                details=(
                    None if numeric_error_code is not None else {"error_code": str(api_error_code)}
                ),
            )
        return response_payload

    def get(
        self,
        endpoint_path: str,
        query_fields: dict | None = None,
        base_url: str | None = None,
        *,
        include_session_fields: bool = True,
    ) -> dict:
        """Send a signed GET request and return its API payload."""
        request_url = (base_url or self.API_BASE_URL) + endpoint_path
        response = self._http_client.get(
            request_url,
            params=self._build_signed_form(
                query_fields,
                include_session_fields=include_session_fields,
            ),
            headers=self._build_app_headers(),
        )
        response.raise_for_status()

        response_payload = response.json()
        api_error_code = response_payload.get("error_code")
        if api_error_code is not None and str(api_error_code) != "0":
            numeric_error_code = (
                int(api_error_code) if str(api_error_code).lstrip("-").isdigit() else None
            )
            raise APIError(
                response_payload.get("error_msg", "API error"),
                error_code=numeric_error_code,
                details=(
                    None if numeric_error_code is not None else {"error_code": str(api_error_code)}
                ),
            )
        return response_payload

    def post_unsigned_web(
        self,
        request_url: str,
        form_fields: dict,
        referer_url: str | None = None,
    ) -> dict:
        """发送 Web POST 请求（不签名）。"""
        response = self._http_client.post(
            request_url,
            data=form_fields,
            headers=self._build_web_headers(referer_url),
        )
        response.raise_for_status()
        return response.json()

    def _get_unsigned_web_response(
        self,
        request_url: str,
        query_params: dict | None = None,
        referer_url: str | None = None,
        origin_url: str | None = None,
    ) -> httpx.Response:
        """发送 Web GET 请求。"""
        headers = self._build_web_headers(referer_url)
        if origin_url:
            headers["Origin"] = origin_url
        response = self._http_client.get(
            request_url,
            params=query_params,
            headers=headers,
        )
        response.raise_for_status()
        return response

    def get_unsigned_web_json(
        self,
        request_url: str,
        query_params: dict | None = None,
        referer_url: str | None = None,
        origin_url: str | None = None,
    ) -> dict:
        """Send an unsigned web GET request and return JSON."""
        response = self._get_unsigned_web_response(
            request_url,
            query_params,
            referer_url,
            origin_url,
        )
        return response.json()

    def get_jsonp_payload(
        self,
        request_url: str,
        query_params: dict | None = None,
    ) -> dict | None:
        """发送请求并解析 JSONP。"""
        response = self._get_unsigned_web_response(request_url, query_params)
        return parse_jsonp_response(response.text)

    def get_html(self, request_url: str) -> str:
        """获取网页 HTML。"""
        response = self._get_unsigned_web_response(request_url)
        return response.text
