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
def test_search_movies_with_fallback_uses_preprocessed_first():
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
    # 전처리 결과 "듄 파트2"로 호출됐는지 확인 (URL 쿼리에 인코딩된 형태로 들어감)
    request_url = responses.calls[0].request.url
    # 한글이 URL 인코딩되어 들어가므로 movieNm 파라미터에 값이 있다는 것만 확인
    assert "movieNm=" in request_url
    assert len(responses.calls) == 1


@responses.activate
def test_search_movies_with_fallback_falls_back_to_compact():
    # 첫 호출은 0건, 두 번째 호출(공백 제거)은 1건
    responses.add(
        method="GET",
        url=KOBIS_URL,
        json={"movieListResult": {"movieList": []}},
    )
    responses.add(
        method="GET",
        url=KOBIS_URL,
        json={
            "movieListResult": {
                "movieList": [
                    {
                        "movieCd": "2",
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
    assert len(responses.calls) == 2


@responses.activate
def test_search_movies_with_fallback_no_compact_when_already_no_spaces():
    # "단어"는 공백이 없으므로 compact_title 결과가 동일 → 폴백 안 함
    responses.add(
        method="GET",
        url=KOBIS_URL,
        json={"movieListResult": {"movieList": []}},
    )
    movies = search_movies_with_fallback("단어", api_key="testkey")
    assert movies == []
    assert len(responses.calls) == 1
