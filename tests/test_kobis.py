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
