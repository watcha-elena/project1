"""쿠키 기반 자격증명 영속화.

EncryptedCookieManager가 쿠키 자체를 password로 암호화. 우리는 추가로
TTL(24h) 만료 검사를 페이로드에 넣는다.
"""
import json
import time
from typing import Optional, Tuple


COOKIE_PREFIX = "pyeonseong/"
COOKIE_KEY = "auth"
COOKIE_TTL_SECONDS = 24 * 60 * 60  # 24시간


def pack_credentials(email: str, password: str) -> str:
    """email + password + expires_at를 JSON 문자열로 직렬화."""
    payload = {
        "email": email,
        "password": password,
        "expires_at": time.time() + COOKIE_TTL_SECONDS,
    }
    return json.dumps(payload)


def unpack_credentials(token: str) -> Optional[Tuple[str, str]]:
    """JSON 문자열을 역직렬화. 만료/파손 시 None 반환."""
    if not token:
        return None
    try:
        payload = json.loads(token)
        if payload.get("expires_at", 0) < time.time():
            return None
        return payload["email"], payload["password"]
    except (ValueError, KeyError):
        return None
