"""쿠키 기반 자격증명 영속화.

- Fernet 대칭 암호화로 자격증명을 묶어 단일 문자열로 만든다.
- 그 문자열을 `streamlit-cookies-controller`로 브라우저 쿠키에 저장.
- 새로고침 시 쿠키를 읽어 복호화 → 세션 복원.
- 24시간 후 자동 만료. 로그아웃 시 즉시 삭제.

비밀번호는 Fernet 키 없이는 풀 수 없고, 키는 Streamlit Secrets에만 있어
저장소/디스크에 평문이 남지 않는다.
"""
import json
import time
from typing import Optional, Tuple

import streamlit as st
from cryptography.fernet import Fernet, InvalidToken


COOKIE_NAME = "pyeonseong_auth"
COOKIE_TTL_SECONDS = 24 * 60 * 60  # 24시간


def _fernet() -> Fernet:
    key = st.secrets["COOKIE_FERNET_KEY"]
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def encrypt_credentials(email: str, password: str) -> str:
    """자격증명 + 만료시각을 암호화해 단일 문자열로 변환."""
    payload = {
        "email": email,
        "password": password,
        "expires_at": time.time() + COOKIE_TTL_SECONDS,
    }
    return _fernet().encrypt(json.dumps(payload).encode()).decode()


def decrypt_credentials(token: str) -> Optional[Tuple[str, str]]:
    """쿠키에서 읽은 암호문을 복호화. 만료/위변조 시 None 반환."""
    if not token:
        return None
    try:
        raw = _fernet().decrypt(token.encode())
        payload = json.loads(raw.decode())
        if payload.get("expires_at", 0) < time.time():
            return None
        return payload["email"], payload["password"]
    except (InvalidToken, ValueError, KeyError):
        return None
