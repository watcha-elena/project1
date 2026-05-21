"""admin 검색 수동 검증 스크립트.

사용법:
    cd /Users/gim-yun-yeong/project1
    source .venv/bin/activate
    ADMIN_EMAIL="..." ADMIN_PW="..." python scripts/manual_test_admin_search.py "어벤져스"
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from admin import AdminClient


def main():
    if len(sys.argv) < 2:
        print("사용법: python scripts/manual_test_admin_search.py '<작품명>'")
        sys.exit(1)

    title = sys.argv[1]
    email = os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("ADMIN_PW")
    if not email or not password:
        print("ADMIN_EMAIL/ADMIN_PW 환경변수를 설정하세요.")
        sys.exit(1)

    client = AdminClient()
    try:
        client.start()
        if not client.login(email, password):
            print("로그인 실패")
            sys.exit(2)
        print(f'"{title}" 검색 중...')
        results = client.search(title)
        print(f"결과 {len(results)}건:")
        for r in results:
            print(f"  - id={r.id}, code={r.code}, title={r.title}, year={r.year}")
    finally:
        client.stop()


if __name__ == "__main__":
    main()
