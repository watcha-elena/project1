from kobis import Movie
from matcher import AdminMatch, pick_admin_match, build_outcome, sort_kobis_by_similarity, sort_admin_by_similarity


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


def test_sort_kobis_exact_match_first():
    from kobis import Movie
    candidates = [
        Movie(code="1", title="알라딘과 죽음의 램프", release_date="2012-01-01", directors=[], genres=[]),
        Movie(code="2", title="알라딘", release_date="2019-05-23", directors=[], genres=[]),
        Movie(code="3", title="저예산 알라딘", release_date="2020-01-01", directors=[], genres=[]),
    ]
    sorted_list = sort_kobis_by_similarity("알라딘", candidates)
    assert sorted_list[0].code == "2"  # exact match
    assert sorted_list[1].code == "1"  # starts with
    assert sorted_list[2].code == "3"  # contains


def test_sort_kobis_newest_first_within_same_tier():
    from kobis import Movie
    candidates = [
        Movie(code="old", title="알라딘", release_date="1992-01-01", directors=[], genres=[]),
        Movie(code="new", title="알라딘", release_date="2019-05-23", directors=[], genres=[]),
    ]
    sorted_list = sort_kobis_by_similarity("알라딘", candidates)
    assert sorted_list[0].code == "new"  # 2019 first


def test_sort_admin_by_similarity():
    candidates = [
        AdminMatch(id="1", code="a", title="알라딘 외 다수의 모험", year=2010),
        AdminMatch(id="2", code="b", title="알라딘", year=2019),
        AdminMatch(id="3", code="c", title="Random Movie", year=2020),
    ]
    sorted_list = sort_admin_by_similarity("알라딘", candidates)
    assert sorted_list[0].id == "2"  # exact match
    assert sorted_list[1].id == "1"  # starts with
    assert sorted_list[2].id == "3"  # no relation, last


def test_sort_handles_empty_query():
    from kobis import Movie
    candidates = [
        Movie(code="1", title="아무거나", release_date="2020-01-01", directors=[], genres=[]),
    ]
    result = sort_kobis_by_similarity("", candidates)
    assert len(result) == 1


def test_pick_admin_match_year_off_by_one_with_title_match():
    """KOBIS year=2013, admin year=2012, title 일치 → 매칭."""
    from kobis import Movie
    k = Movie(
        code="c",
        title="공정사회",
        release_date="2013-03-21",
        directors=[],
        genres=[],
    )
    candidates = [admin(id="1", title="공정사회", year=2012)]
    chosen = pick_admin_match(k, candidates)
    assert chosen is not None
    assert chosen.id == "1"


def test_pick_admin_match_year_off_by_two_rejected():
    """year 차이가 2 이상이면 매칭 안 함."""
    from kobis import Movie
    k = Movie(
        code="c",
        title="공정사회",
        release_date="2013-03-21",
        directors=[],
        genres=[],
    )
    candidates = [admin(id="1", title="공정사회", year=2010)]
    chosen = pick_admin_match(k, candidates)
    assert chosen is None


def test_pick_admin_match_prefers_exact_year_over_loose():
    """year 정확 일치가 ±1보다 우선."""
    from kobis import Movie
    k = Movie(
        code="c",
        title="공정사회",
        release_date="2013-03-21",
        directors=[],
        genres=[],
    )
    candidates = [
        admin(id="loose", title="공정사회", year=2012),
        admin(id="exact", title="공정사회", year=2013),
    ]
    chosen = pick_admin_match(k, candidates)
    assert chosen.id == "exact"


def test_normalize_strips_punctuation():
    """문장부호 차이도 정규화 후 무시."""
    from matcher import _normalize
    assert _normalize("섬. 사라진 사람들") == _normalize("섬, 사라진 사람들")
    assert _normalize("U.S. Movie") == _normalize("US Movie")
