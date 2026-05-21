from kobis import Movie
from matcher import AdminMatch, pick_admin_match, build_outcome


def admin(id="1", code="A", title="t", year=2020):
    return AdminMatch(id=id, code=code, title=title, year=year)


def kobis(title="듄: 파트2", date="2024-02-28"):
    return Movie(code="c", title=title, release_date=date, directors=[], genres=[])


def test_pick_admin_match_exact_year_and_title():
    candidates = [
        admin(id="1", title="듄: 파트2", year=2024),
        admin(id="2", title="듄", year=2021),
    ]
    chosen = pick_admin_match(kobis(), candidates)
    assert chosen.id == "1"


def test_pick_admin_match_returns_none_when_year_matches_but_title_unrelated():
    """admin이 검색결과 없을 때 기본 목록(연도 일치하지만 무관한 작품)을 반환하는 케이스 방어."""
    candidates = [
        admin(id="1", title="Random Movie", year=2024),
        admin(id="2", title="Another Unrelated", year=2024),
    ]
    assert pick_admin_match(kobis(), candidates) is None


def test_pick_admin_match_returns_none_for_no_candidates():
    assert pick_admin_match(kobis(), []) is None


def test_pick_admin_match_returns_none_when_year_mismatch():
    candidates = [admin(year=2010), admin(year=2015)]
    assert pick_admin_match(kobis(), candidates) is None


def test_build_outcome_success():
    k = kobis()
    a = admin(id="1842", code="M001")
    outcome = build_outcome(user_input="듄", kobis_movie=k, admin_match=a)
    assert outcome.status == "success"
    assert outcome.result.id == "1842"
    assert outcome.result.code == "M001"
    assert outcome.result.title == "듄: 파트2"
    assert outcome.result.release_date == "2024-02-28"


def test_build_outcome_admin_not_found():
    outcome = build_outcome(user_input="듄", kobis_movie=kobis(), admin_match=None)
    assert outcome.status == "admin_not_found"
    assert outcome.result is None


def test_build_outcome_no_kobis():
    outcome = build_outcome(user_input="x", kobis_movie=None, admin_match=None)
    assert outcome.status == "kobis_not_found"


def test_pick_admin_match_uses_english_title():
    """KOBIS title_en이 admin title과 일치하면 매칭."""
    from kobis import Movie
    k = Movie(
        code="c",
        title="듄: 파트2",
        release_date="2024-02-28",
        directors=[],
        genres=[],
        title_en="Dune: Part Two",
    )
    candidates = [
        admin(id="1", title="Dune: Part Two", year=2024),
        admin(id="2", title="Some Other Movie", year=2024),
    ]
    chosen = pick_admin_match(k, candidates)
    assert chosen.id == "1"


def test_pick_admin_match_case_insensitive():
    """대소문자/공백 차이 정규화 후 매칭."""
    from kobis import Movie
    k = Movie(
        code="c",
        title="듄: 파트2",
        release_date="2024-02-28",
        directors=[],
        genres=[],
        title_en="Dune: Part Two",
    )
    candidates = [admin(id="1", title="DUNE: PART TWO", year=2024)]
    chosen = pick_admin_match(k, candidates)
    assert chosen.id == "1"


def test_pick_admin_match_partial_contains():
    """admin title이 KOBIS title을 포함하는 경우 (또는 반대)."""
    from kobis import Movie
    k = Movie(
        code="c",
        title="아바타",
        release_date="2022-12-14",
        directors=[],
        genres=[],
        title_en="Avatar",
    )
    candidates = [admin(id="1", title="Avatar: The Way of Water", year=2022)]
    chosen = pick_admin_match(k, candidates)
    assert chosen.id == "1"
