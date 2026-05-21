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
