"""수동 admin 로그인 검증 스크립트.

사용법:
    cd /Users/gim-yun-yeong/project1
    source .venv/bin/activate
    ADMIN_EMAIL="<email>" ADMIN_PW="<password>" python scripts/manual_test_admin_login.py

성공 시: "로그인 성공" 출력 후 종료
실패 시: "로그인 실패" 출력 (스크린샷 `login_fail.png` 저장)
"""
import os
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from admin import AdminClient


def main():
    email = os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("ADMIN_PW")
    if not email or not password:
        print("ADMIN_EMAIL 및 ADMIN_PW 환경변수를 설정하세요.")
        sys.exit(1)

    client = AdminClient()
    try:
        client.start()
        ok = client.login(email, password)
        if ok:
            print("로그인 성공")
        else:
            print("로그인 실패")
            if client._page:
                client._page.screenshot(path="login_fail.png")
                print("실패 캡처: login_fail.png")
    finally:
        client.stop()


if __name__ == "__main__":
    main()
