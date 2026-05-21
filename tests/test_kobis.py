from kobis import preprocess_title


def test_preprocess_trims_whitespace():
    assert preprocess_title("  어벤져스  ") == "어벤져스"


def test_preprocess_removes_colon():
    assert preprocess_title("듄: 파트2") == "듄 파트2"


def test_preprocess_removes_period():
    assert preprocess_title("U.S. 마샬") == "US 마샬"


def test_preprocess_collapses_spaces():
    assert preprocess_title("어벤져스   엔드게임") == "어벤져스 엔드게임"


def test_preprocess_compact_returns_no_space_version():
    from kobis import compact_title
    assert compact_title("어벤져스 엔드게임") == "어벤져스엔드게임"


from kobis import Movie


def test_movie_year_from_release_date():
    movie = Movie(
        code="20240001",
        title="듄: 파트2",
        release_date="2024-02-28",
        directors=["드니 빌뇌브"],
        genres=["SF"],
    )
    assert movie.year == 2024


def test_movie_year_returns_none_for_empty_release_date():
    movie = Movie(code="x", title="x", release_date="", directors=[], genres=[])
    assert movie.year is None


def test_movie_year_handles_unknown_format():
    movie = Movie(code="x", title="x", release_date="미정", directors=[], genres=[])
    assert movie.year is None


import responses
from kobis import search_movies


KOBIS_URL = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieList.json"


@responses.activate
def test_search_movies_returns_movies():
    responses.add(
        method="GET",
        url=KOBIS_URL,
        json={
            "movieListResult": {
                "movieList": [
                    {
                        "movieCd": "20240001",
                        "movieNm": "듄: 파트2",
                        "openDt": "20240228",
                        "directors": [{"peopleNm": "드니 빌뇌브"}],
                        "genreAlt": "SF,액션",
                    }
                ]
            }
        },
    )
    movies = search_movies("듄", api_key="testkey")
    assert len(movies) == 1
    assert movies[0].code == "20240001"
    assert movies[0].title == "듄: 파트2"
    assert movies[0].release_date == "2024-02-28"
    assert movies[0].year == 2024
    assert movies[0].directors == ["드니 빌뇌브"]
    assert movies[0].genres == ["SF", "액션"]


@responses.activate
def test_search_movies_returns_empty_for_no_results():
    responses.add(
        method="GET",
        url=KOBIS_URL,
        json={"movieListResult": {"movieList": []}},
    )
    movies = search_movies("이상한작품명없음", api_key="testkey")
    assert movies == []


@responses.activate
def test_search_movies_retries_on_network_error():
    # 첫 두 번은 500, 세 번째는 정상
    responses.add(method="GET", url=KOBIS_URL, status=500)
    responses.add(method="GET", url=KOBIS_URL, status=500)
    responses.add(
        method="GET",
        url=KOBIS_URL,
        json={"movieListResult": {"movieList": []}},
    )
    movies = search_movies("test", api_key="testkey", retry_delays=[0, 0, 0])
    assert movies == []
    assert len(responses.calls) == 3


@responses.activate
def test_search_movies_raises_after_max_retries():
    for _ in range(3):
        responses.add(method="GET", url=KOBIS_URL, status=500)
    import pytest
    with pytest.raises(Exception):
        search_movies("test", api_key="testkey", retry_delays=[0, 0, 0])


from kobis import search_movies_with_fallback


@responses.activate
def test_search_movies_with_fallback_uses_raw_first():
    """원본 그대로 보내서 결과 있으면 그것 반환 (전처리 안 거침)."""
    responses.add(
        method="GET",
        url=KOBIS_URL,
        json={
            "movieListResult": {
                "movieList": [
                    {
                        "movieCd": "1",
                        "movieNm": "듄: 파트2",
                        "openDt": "20240228",
                        "directors": [],
                        "genreAlt": "",
                    }
                ]
            }
        },
    )
    movies = search_movies_with_fallback("듄: 파트2", api_key="testkey")
    assert len(movies) == 1
    # 단 1회만 호출되었어야 함 (원본으로 찾음)
    assert len(responses.calls) == 1


@responses.activate
def test_search_movies_with_fallback_falls_back_to_preprocessed():
    """원본 0건이면 전처리 변형으로 재시도."""
    # 첫 호출(원본): 0건
    responses.add(
        method="GET",
        url=KOBIS_URL,
        json={"movieListResult": {"movieList": []}},
    )
    # 두 번째 호출(전처리): 1건
    responses.add(
        method="GET",
        url=KOBIS_URL,
        json={
            "movieListResult": {
                "movieList": [
                    {
                        "movieCd": "2",
                        "movieNm": "테스트",
                        "openDt": "20200101",
                        "directors": [],
                        "genreAlt": "",
                    }
                ]
            }
        },
    )
    # "테스트 :" 같은 입력 — 원본과 preprocessed가 다름
    movies = search_movies_with_fallback("테스트 :", api_key="testkey")
    assert len(movies) == 1
    assert len(responses.calls) == 2


@responses.activate
def test_search_movies_with_fallback_falls_back_to_compact():
    """원본/전처리 모두 0건이면 공백 제거 버전 시도.

    "어벤져스 엔드게임"은 preprocess_title 결과가 원본과 동일하므로
    변형 목록은 raw + compact 2개뿐 → API 호출도 2회.
    """
    # 첫 호출(원본 "어벤져스 엔드게임"): 0건
    responses.add(
        method="GET",
        url=KOBIS_URL,
        json={"movieListResult": {"movieList": []}},
    )
    # 두 번째 호출(compact "어벤져스엔드게임"): 1건
    responses.add(
        method="GET",
        url=KOBIS_URL,
        json={
            "movieListResult": {
                "movieList": [
                    {
                        "movieCd": "3",
                        "movieNm": "어벤져스엔드게임",
                        "openDt": "20190424",
                        "directors": [],
                        "genreAlt": "",
                    }
                ]
            }
        },
    )
    movies = search_movies_with_fallback("어벤져스 엔드게임", api_key="testkey")
    assert len(movies) == 1
    # 원본과 preprocessed가 동일해서 중복 제거 → raw + compact = 2회 호출
    assert len(responses.calls) == 2


@responses.activate
def test_search_movies_with_fallback_no_variation_for_simple_title():
    """공백/특수문자 없는 단어는 변형 후보가 1개뿐."""
    responses.add(
        method="GET",
        url=KOBIS_URL,
        json={"movieListResult": {"movieList": []}},
    )
    movies = search_movies_with_fallback("단어", api_key="testkey")
    assert movies == []
    assert len(responses.calls) == 1


@responses.activate
def test_search_movies_extracts_english_title():
    responses.add(
        method="GET",
        url=KOBIS_URL,
        json={
            "movieListResult": {
                "movieList": [
                    {
                        "movieCd": "1",
                        "movieNm": "듄: 파트2",
                        "movieNmEn": "Dune: Part Two",
                        "openDt": "20240228",
                        "directors": [],
                        "genreAlt": "",
                    }
                ]
            }
        },
    )
    movies = search_movies("듄", api_key="testkey")
    assert movies[0].title_en == "Dune: Part Two"


@responses.activate
def test_search_movies_missing_english_title_defaults_to_empty():
    responses.add(
        method="GET",
        url=KOBIS_URL,
        json={
            "movieListResult": {
                "movieList": [
                    {
                        "movieCd": "1",
                        "movieNm": "한글전용",
                        "openDt": "20200101",
                        "directors": [],
                        "genreAlt": "",
                    }
                ]
            }
        },
    )
    movies = search_movies("test", api_key="testkey")
    assert movies[0].title_en == ""
