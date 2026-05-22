"""한 작품의 매칭 전체 흐름을 진단하는 스크립트.

KOBIS 결과, admin 결과, 최종 매칭 판정을 단계별로 출력하므로
"왜 매칭이 안 됐는지" 정확히 파악할 수 있다.

사용법:
    cd /Users/gim-yun-yeong/project1
    source .venv/bin/activate
    ADMIN_EMAIL="..." ADMIN_PW="..." python scripts/manual_test_full_match.py "엽기적인 그녀"
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from admin import AdminClient
from kobis import search_movies_with_fallback
from matcher import pick_admin_match, build_outcome


KOBIS_API_KEY = "bc595edc3946f4e849bf27e28c19258b"


def main():
    if len(sys.argv) < 2:
        print("사용법: python scripts/manual_test_full_match.py '<작품명>'")
        sys.exit(1)

    title = sys.argv[1]
    email = os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("ADMIN_PW")
    if not email or not password:
        print("ADMIN_EMAIL / ADMIN_PW 환경변수를 설정하세요.")
        sys.exit(1)

    print("=" * 70)
    print(f"진단: '{title}'")
    print("=" * 70)

    # 1단계: KOBIS 검색
    print("\n[1] KOBIS 검색")
    print("-" * 70)
    try:
        kobis_movies = search_movies_with_fallback(title, KOBIS_API_KEY)
    except Exception as exc:
        print(f"  ❌ KOBIS 호출 오류: {exc}")
        return

    print(f"  결과: {len(kobis_movies)}건")
    for i, m in enumerate(kobis_movies[:10], start=1):
        print(
            f"    {i}. title='{m.title}' / title_en='{m.title_en}' / "
            f"year={m.year} / release_date='{m.release_date}'"
        )
    if len(kobis_movies) > 10:
        print(f"    ... 외 {len(kobis_movies) - 10}건")

    if not kobis_movies:
        print("\n  → KOBIS에서 못 찾음. admin-only 폴백으로 진행해야 함.")
    elif len(kobis_movies) > 1:
        print(
            f"\n  → KOBIS 다건. UI에서는 사용자 선택 화면이 뜸. "
            f"여기서는 첫 번째를 사용해 admin 매칭 검증."
        )

    # 2단계: admin 로그인 + 검색
    print("\n[2] admin 검색")
    print("-" * 70)
    client = AdminClient()
    try:
        client.start()
        if not client.login(email, password):
            print("  ❌ admin 로그인 실패")
            return
        print("  ✓ admin 로그인 성공")

        # admin은 KOBIS의 한글 제목으로 검색하는 게 우리 코드의 기본 전략
        # KOBIS 결과 있으면 그걸로, 없으면 사용자 입력으로 검색
        admin_query = kobis_movies[0].title if kobis_movies else title
        print(f"  admin 검색어: '{admin_query}'")

        admin_results = client.search(admin_query)
        print(f"  admin 결과: {len(admin_results)}건")
        for i, a in enumerate(admin_results[:15], start=1):
            print(f"    {i}. id={a.id} / code={a.code} / title='{a.title}' / year={a.year}")
        if len(admin_results) > 15:
            print(f"    ... 외 {len(admin_results) - 15}건")
    finally:
        client.stop()

    # 3단계: pick_admin_match 판정
    print("\n[3] pick_admin_match 판정 (KOBIS-admin 결합)")
    print("-" * 70)
    if not kobis_movies:
        print("  KOBIS가 0건이므로 pick_admin_match 호출 안 함.")
        if len(admin_results) == 1:
            print(f"  → admin 단일 결과: id={admin_results[0].id}, code={admin_results[0].code}")
            print(f"     UI 흐름: admin-only 자동 매칭 (개봉일 빈 칸)")
        elif 2 <= len(admin_results) <= 5:
            print(f"  → admin 2~5건: UI에서 사용자 선택 화면")
        elif len(admin_results) >= 6:
            print(f"  → admin {len(admin_results)}건: admin 기본 목록으로 추정, 실패 처리")
        else:
            print("  → admin도 0건: 최종 실패")
        return

    # KOBIS 다건일 때도 어차피 사용자 선택이 들어가므로, 진단에서는 첫 번째 사용
    chosen_kobis = kobis_movies[0]
    print(f"  KOBIS 선택 (진단용 첫 번째): '{chosen_kobis.title}' / year={chosen_kobis.year}")
    match = pick_admin_match(chosen_kobis, admin_results)
    if match is None:
        print(f"  → ❌ 매칭 None")
        print(f"     사유 분석:")
        same_year = [c for c in admin_results if c.year == chosen_kobis.year]
        if not admin_results:
            print(f"      - admin 결과 0건")
        elif chosen_kobis.year is None:
            print(f"      - KOBIS year가 None (release_date='{chosen_kobis.release_date}')")
        elif not same_year:
            print(f"      - KOBIS year={chosen_kobis.year} 와 일치하는 admin 후보 0건")
            print(f"        admin year 분포: {sorted(set(a.year for a in admin_results))}")
        else:
            print(f"      - year 일치 후보는 있으나 ({len(same_year)}건) title 관련성 미충족")
            print(f"        KOBIS title='{chosen_kobis.title}', title_en='{chosen_kobis.title_en}'")
            print(f"        year 일치 admin title들: {[a.title for a in same_year]}")
    else:
        print(f"  → ✅ 매칭됨")
        print(f"     id={match.id}, code={match.code}, title='{match.title}', year={match.year}")
        outcome = build_outcome(title, chosen_kobis, match)
        print(f"     최종 result: {outcome.result}")


if __name__ == "__main__":
    main()
