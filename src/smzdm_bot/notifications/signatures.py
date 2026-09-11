"""Provider-specific HMAC signing; URL encoding belongs to the URL builder."""

import base64
import hashlib
import hmac


def dingtalk_signature(secret: str, timestamp: int) -> str:
    """Sign timestamp in milliseconds followed by a newline and the secret."""
    digest = hmac.new(secret.encode(), f"{timestamp}\n{secret}".encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def feishu_signature(secret: str, timestamp: int) -> str:
    """Use timestamp in seconds plus secret as the key, with an empty message."""
    digest = hmac.new(f"{timestamp}\n{secret}".encode(), b"", hashlib.sha256).digest()
    return base64.b64encode(digest).decode()
