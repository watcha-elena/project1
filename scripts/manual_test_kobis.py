"""KOBIS Open API 키와 검색 응답을 직접 확인하는 진단 스크립트.

사용법:
    cd /Users/gim-yun-yeong/project1
    source .venv/bin/activate
    python scripts/manual_test_kobis.py "어벤져스"
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests


KOBIS_API_KEY = "bc595edc3946f4e849bf27e28c19258b"
KOBIS_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieList.json"
)


def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "어벤져스"
    print(f"검색어: {query}")
    print(f"URL: {KOBIS_URL}")
    print(f"키: {KOBIS_API_KEY[:8]}... (앞 8자만)")

    try:
        r = requests.get(
            KOBIS_URL,
            params={"key": KOBIS_API_KEY, "movieNm": query},
            timeout=10,
        )
    except Exception as exc:
        print(f"\n네트워크 오류: {exc}")
        sys.exit(1)

    print(f"\nHTTP Status: {r.status_code}")
    print(f"Content-Type: {r.headers.get('content-type', '')}")
    print(f"Response body (앞 800자):")
    print("-" * 60)
    print(r.text[:800])
    print("-" * 60)

    # 파싱 시도
    try:
        data = r.json()
        movie_list = data.get("movieListResult", {}).get("movieList", [])
        print(f"\n파싱된 영화 수: {len(movie_list)}")
        for m in movie_list[:5]:
            print(
                f"  - {m.get('movieNm')} / {m.get('movieNmEn')} / "
                f"{m.get('openDt')} / 감독: "
                f"{[d.get('peopleNm') for d in m.get('directors', [])]}"
            )
        if len(movie_list) > 5:
            print(f"  ... 외 {len(movie_list) - 5}건")

        # 에러 응답 점검
        if "faultInfo" in data:
            print(f"\n⚠️ KOBIS faultInfo 발견:")
            print(data["faultInfo"])
    except Exception as exc:
        print(f"\nJSON 파싱 실패: {exc}")


if __name__ == "__main__":
    main()
