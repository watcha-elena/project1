# 편성 자동화 대시보드 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** OTT 편성 담당자가 작품명 리스트를 입력하면 KOBIS Open API에서 개봉일을, admin.kubecha.com에서 id/code를 자동 매칭해 결과 표/엑셀로 출력하는 웹 대시보드를 빌드 후 Streamlit Community Cloud에 배포한다.

**Architecture:** Python + Streamlit 기반 단일 앱. 각 책임을 작은 모듈로 분리(`kobis.py`, `admin.py`, `excel.py`, `auth.py`, `matcher.py`), UI는 `app.py`에서 통합. admin 자동화는 Playwright headless Chromium. KOBIS API 키는 Streamlit Secrets 사용. GitHub 저장소를 Streamlit Cloud에 연결해 자동 재배포.

**Tech Stack:** Python 3.10+, Streamlit, requests, Playwright (Chromium), openpyxl, pytest, responses (HTTP mocking)

**Reference:** 설계 문서 — `docs/superpowers/specs/2026-05-21-pyeonseong-automation-dashboard-design.md`

---

## 파일 구조 (최종)

```
project1/
├── app.py                       # Streamlit 메인 (라우팅, 화면)
├── kobis.py                     # KOBIS API 클라이언트
├── admin.py                     # admin Playwright 자동화
├── excel.py                     # 엑셀/TSV 생성
├── auth.py                      # 로그인 시도 카운터
├── matcher.py                   # KOBIS↔admin 매칭 로직
├── tests/
│   ├── __init__.py
│   ├── test_kobis.py
│   ├── test_excel.py
│   ├── test_auth.py
│   └── test_matcher.py
├── .streamlit/
│   ├── config.toml              # 테마
│   └── secrets.toml             # 로컬 개발용 KOBIS 키 (Git 제외)
├── .gitignore                   # 이미 존재
├── requirements.txt
├── packages.txt                 # Streamlit Cloud OS 패키지
├── README.md
└── docs/superpowers/            # 이미 존재
```

각 파일의 책임:
- **kobis.py**: KOBIS API 호출, 응답 파싱, 검색어 전처리, 재시도. 순수 함수 + 단순 dataclass.
- **admin.py**: Playwright로 admin 로그인 및 검색. 외부 상태(브라우저 세션) 보유.
- **excel.py**: 매칭 결과 리스트를 받아 TSV 문자열 2개와 `.xlsx` 바이트 생성. 순수 함수.
- **auth.py**: 로그인 시도 카운터 및 잠금. 시간 기반 상태.
- **matcher.py**: KOBIS 검색 결과와 admin 검색 결과를 결합. 동명이작 처리. 순수 함수.
- **app.py**: Streamlit UI. 위 모듈들을 호출하고 결과를 화면에 표시.

---

## Task 1: 프로젝트 셋업 — requirements.txt, packages.txt, config

**Files:**
- Create: `requirements.txt`
- Create: `packages.txt`
- Create: `.streamlit/config.toml`
- Create: `tests/__init__.py`
- Modify: `.gitignore` (확인만)

- [ ] **Step 1: `requirements.txt` 생성**

Create `/Users/gim-yun-yeong/project1/requirements.txt`:
```
streamlit>=1.30
requests>=2.31
playwright>=1.40
openpyxl>=3.1
pytest>=7.4
responses>=0.24
```

- [ ] **Step 2: `packages.txt` 생성 (Streamlit Cloud용 OS 패키지)**

Create `/Users/gim-yun-yeong/project1/packages.txt`:
```
libnss3
libnspr4
libatk1.0-0
libatk-bridge2.0-0
libcups2
libdrm2
libdbus-1-3
libxkbcommon0
libxcomposite1
libxdamage1
libxfixes3
libxrandr2
libgbm1
libpango-1.0-0
libcairo2
libasound2
```

(Playwright Chromium이 Linux에서 필요로 하는 시스템 라이브러리들)

- [ ] **Step 3: Streamlit 테마 설정 생성**

Create `/Users/gim-yun-yeong/project1/.streamlit/config.toml`:
```toml
[theme]
primaryColor = "#FF4B4B"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F5F5F5"
textColor = "#262730"
font = "sans serif"

[server]
headless = true
runOnSave = true
```

- [ ] **Step 4: 테스트 디렉토리 초기화**

Create `/Users/gim-yun-yeong/project1/tests/__init__.py` (빈 파일).

- [ ] **Step 5: `.gitignore` 확인**

기존 `.gitignore`에 다음이 포함되어 있는지 확인 (이미 포함되어 있음, 확인만):
- `.streamlit/secrets.toml`
- `__pycache__/`
- `*.pyc`

- [ ] **Step 6: 로컬 가상환경 생성 및 의존성 설치**

Run in terminal:
```bash
cd /Users/gim-yun-yeong/project1
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```
Expected: 모든 패키지 설치 성공, Chromium 다운로드 완료.

`.gitignore`에 `.venv/`가 있는지 확인 후 없으면 추가.

- [ ] **Step 7: 커밋**

```bash
git add requirements.txt packages.txt .streamlit/config.toml tests/__init__.py .gitignore
git commit -m "chore: project scaffold and Streamlit theme

- Add requirements.txt with Streamlit, Playwright, openpyxl, pytest
- Add packages.txt for Streamlit Cloud OS-level deps
- Add .streamlit/config.toml with brand theme
- Add empty tests package"
```

---

## Task 2: KOBIS 모듈 — 검색어 전처리 (TDD)

**Files:**
- Create: `tests/test_kobis.py`
- Create: `kobis.py`

- [ ] **Step 1: 전처리 실패 테스트 작성**

Create `/Users/gim-yun-yeong/project1/tests/test_kobis.py`:
```python
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
```

- [ ] **Step 2: 테스트 실행하여 실패 확인**

Run: `pytest tests/test_kobis.py -v`
Expected: 모든 테스트 FAIL (ImportError: cannot import name 'preprocess_title').

- [ ] **Step 3: `kobis.py`에 전처리 함수 구현**

Create `/Users/gim-yun-yeong/project1/kobis.py`:
```python
import re


def preprocess_title(title: str) -> str:
    """KOBIS 검색 정확도를 높이기 위한 전처리."""
    title = title.strip()
    title = re.sub(r"[:]", " ", title)
    title = re.sub(r"[.]", "", title)
    title = re.sub(r"\s+", " ", title)
    return title.strip()


def compact_title(title: str) -> str:
    """모든 공백을 제거한 폴백 검색어."""
    return re.sub(r"\s+", "", title)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_kobis.py -v`
Expected: 모든 테스트 PASS.

- [ ] **Step 5: 커밋**

```bash
git add tests/test_kobis.py kobis.py
git commit -m "feat(kobis): title preprocessing for search accuracy"
```

---

## Task 3: KOBIS 모듈 — Movie 데이터 클래스

**Files:**
- Modify: `tests/test_kobis.py`
- Modify: `kobis.py`

- [ ] **Step 1: Movie 데이터클래스 테스트 추가**

Append to `tests/test_kobis.py`:
```python
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
```

- [ ] **Step 2: 테스트 실행하여 실패 확인**

Run: `pytest tests/test_kobis.py -v`
Expected: 새 테스트들 FAIL (cannot import name 'Movie').

- [ ] **Step 3: Movie 데이터클래스 구현**

Append to `kobis.py`:
```python
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Movie:
    code: str
    title: str
    release_date: str
    directors: list[str] = field(default_factory=list)
    genres: list[str] = field(default_factory=list)

    @property
    def year(self) -> Optional[int]:
        if not self.release_date or len(self.release_date) < 4:
            return None
        try:
            return int(self.release_date[:4])
        except ValueError:
            return None
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_kobis.py -v`
Expected: 모든 테스트 PASS.

- [ ] **Step 5: 커밋**

```bash
git add tests/test_kobis.py kobis.py
git commit -m "feat(kobis): Movie dataclass with year derivation"
```

---

## Task 4: KOBIS 모듈 — search_movies (API 호출 + 재시도)

**Files:**
- Modify: `tests/test_kobis.py`
- Modify: `kobis.py`

- [ ] **Step 1: 검색 함수 테스트 작성**

Append to `tests/test_kobis.py`:
```python
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
    # 첫 두 번은 500 에러, 세 번째는 정상 응답
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
```

- [ ] **Step 2: 테스트 실행하여 실패 확인**

Run: `pytest tests/test_kobis.py -v`
Expected: 새 테스트들 FAIL (cannot import name 'search_movies').

- [ ] **Step 3: `search_movies` 구현**

Append to `kobis.py`:
```python
import time
import requests


KOBIS_API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieList.json"
)
DEFAULT_RETRY_DELAYS = [1.0, 2.0, 4.0]


def search_movies(
    title: str,
    api_key: str,
    retry_delays: Optional[list[float]] = None,
) -> list[Movie]:
    """KOBIS Open API로 영화를 검색하고 Movie 리스트를 반환.

    네트워크 또는 5xx 응답 시 최대 retry_delays 횟수만큼 재시도.
    재시도 모두 실패하면 마지막 예외를 그대로 raise.
    """
    delays = retry_delays if retry_delays is not None else DEFAULT_RETRY_DELAYS
    last_exception: Optional[Exception] = None

    for attempt, delay in enumerate(delays):
        if attempt > 0:
            time.sleep(delay)
        try:
            response = requests.get(
                KOBIS_API_URL,
                params={"key": api_key, "movieNm": title},
                timeout=5,
            )
            if response.status_code >= 500:
                last_exception = Exception(
                    f"KOBIS server error: {response.status_code}"
                )
                continue
            response.raise_for_status()
            data = response.json()
            return _parse_movie_list(data)
        except requests.RequestException as e:
            last_exception = e
            continue

    raise last_exception or Exception("KOBIS search failed without exception detail")


def _parse_movie_list(data: dict) -> list[Movie]:
    raw_list = data.get("movieListResult", {}).get("movieList", [])
    movies = []
    for item in raw_list:
        movies.append(
            Movie(
                code=item.get("movieCd", ""),
                title=item.get("movieNm", ""),
                release_date=_format_release_date(item.get("openDt", "")),
                directors=[
                    d.get("peopleNm", "") for d in item.get("directors", [])
                ],
                genres=[
                    g.strip() for g in item.get("genreAlt", "").split(",") if g.strip()
                ],
            )
        )
    return movies


def _format_release_date(raw: str) -> str:
    """KOBIS는 'YYYYMMDD' 형식. 'YYYY-MM-DD'로 변환."""
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    return raw
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_kobis.py -v`
Expected: 모든 테스트 PASS.

- [ ] **Step 5: 커밋**

```bash
git add tests/test_kobis.py kobis.py
git commit -m "feat(kobis): search_movies with retry and response parsing"
```

---

## Task 5: KOBIS 모듈 — 검색 폴백 (전처리 + compact 재시도)

**Files:**
- Modify: `tests/test_kobis.py`
- Modify: `kobis.py`

- [ ] **Step 1: 폴백 검색 테스트 작성**

Append to `tests/test_kobis.py`:
```python
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
    # 첫 호출은 전처리된 "듄 파트2"여야 함
    assert "movieNm=%EB%93%84+%ED%8C%8C%ED%8A%B82" in responses.calls[0].request.url or \
           "movieNm=듄 파트2" in responses.calls[0].request.url


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
```

- [ ] **Step 2: 테스트 실행하여 실패 확인**

Run: `pytest tests/test_kobis.py -v`
Expected: 새 테스트들 FAIL.

- [ ] **Step 3: `search_movies_with_fallback` 구현**

Append to `kobis.py`:
```python
def search_movies_with_fallback(title: str, api_key: str) -> list[Movie]:
    """전처리 후 검색, 결과 0건이면 공백 제거 버전으로 1회 폴백."""
    primary = preprocess_title(title)
    movies = search_movies(primary, api_key)
    if movies:
        return movies

    fallback = compact_title(primary)
    if fallback == primary:
        return []
    return search_movies(fallback, api_key)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_kobis.py -v`
Expected: 모든 테스트 PASS.

- [ ] **Step 5: 커밋**

```bash
git add tests/test_kobis.py kobis.py
git commit -m "feat(kobis): fallback search with compact title when zero results"
```

---

## Task 6: 엑셀 모듈 — TSV 및 xlsx 생성 (TDD)

**Files:**
- Create: `tests/test_excel.py`
- Create: `excel.py`

- [ ] **Step 1: 엑셀 모듈 테스트 작성**

Create `/Users/gim-yun-yeong/project1/tests/test_excel.py`:
```python
from excel import (
    MatchResult,
    tsv_id_code_title,
    tsv_release_date,
    xlsx_bytes,
)


def make_result(id="1842", code="M001", title="어벤져스 엔드게임", date="2019-04-24"):
    return MatchResult(id=id, code=code, title=title, release_date=date)


def test_tsv_id_code_title_single_row():
    results = [make_result()]
    assert tsv_id_code_title(results) == "1842\tM001\t어벤져스 엔드게임"


def test_tsv_id_code_title_multiple_rows():
    results = [
        make_result(id="1", code="A", title="x"),
        make_result(id="2", code="B", title="y"),
    ]
    assert tsv_id_code_title(results) == "1\tA\tx\n2\tB\ty"


def test_tsv_id_code_title_empty():
    assert tsv_id_code_title([]) == ""


def test_tsv_release_date_single_row():
    assert tsv_release_date([make_result(date="2019-04-24")]) == "2019-04-24"


def test_tsv_release_date_multiple_rows():
    results = [
        make_result(date="2019-04-24"),
        make_result(date="2024-06-12"),
    ]
    assert tsv_release_date(results) == "2019-04-24\n2024-06-12"


def test_tsv_release_date_empty_dates_become_blank_lines():
    results = [
        make_result(date="2019-04-24"),
        make_result(date=""),
    ]
    assert tsv_release_date(results) == "2019-04-24\n"


def test_xlsx_bytes_produces_valid_workbook():
    from openpyxl import load_workbook
    import io
    blob = xlsx_bytes([make_result()])
    wb = load_workbook(io.BytesIO(blob))
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    # 첫 행은 헤더
    assert rows[0] == ("id", "code", "title", "개봉일")
    assert rows[1] == ("1842", "M001", "어벤져스 엔드게임", "2019-04-24")
```

- [ ] **Step 2: 테스트 실행하여 실패 확인**

Run: `pytest tests/test_excel.py -v`
Expected: 모든 테스트 FAIL.

- [ ] **Step 3: `excel.py` 구현**

Create `/Users/gim-yun-yeong/project1/excel.py`:
```python
import io
from dataclasses import dataclass

from openpyxl import Workbook


@dataclass
class MatchResult:
    """최종 매칭 결과 한 건. UI/엑셀에 표시될 형태."""
    id: str
    code: str
    title: str
    release_date: str


def tsv_id_code_title(results: list[MatchResult]) -> str:
    """탭 구분, 한 행에 id/code/title. 헤더 없음."""
    return "\n".join(f"{r.id}\t{r.code}\t{r.title}" for r in results)


def tsv_release_date(results: list[MatchResult]) -> str:
    """줄바꿈 구분, 한 행에 개봉일. 헤더 없음."""
    return "\n".join(r.release_date for r in results)


def xlsx_bytes(results: list[MatchResult]) -> bytes:
    """4컬럼(id/code/title/개봉일) 엑셀 바이너리 반환."""
    wb = Workbook()
    ws = wb.active
    ws.title = "매칭결과"
    ws.append(["id", "code", "title", "개봉일"])
    for r in results:
        ws.append([r.id, r.code, r.title, r.release_date])
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_excel.py -v`
Expected: 모든 테스트 PASS.

- [ ] **Step 5: 커밋**

```bash
git add tests/test_excel.py excel.py
git commit -m "feat(excel): MatchResult dataclass with TSV and xlsx exporters"
```

---

## Task 7: 인증(로그인 시도 제한) 모듈 — TDD

**Files:**
- Create: `tests/test_auth.py`
- Create: `auth.py`

- [ ] **Step 1: 로그인 시도 제한 테스트 작성**

Create `/Users/gim-yun-yeong/project1/tests/test_auth.py`:
```python
from auth import LoginRateLimiter


def test_initially_not_locked():
    limiter = LoginRateLimiter(max_failures=5, lockout_seconds=300, now=lambda: 0.0)
    assert not limiter.is_locked()
    assert limiter.remaining_lockout_seconds() == 0


def test_below_threshold_not_locked():
    limiter = LoginRateLimiter(max_failures=5, lockout_seconds=300, now=lambda: 0.0)
    for _ in range(4):
        limiter.record_failure()
    assert not limiter.is_locked()


def test_locked_at_threshold():
    t = [0.0]
    limiter = LoginRateLimiter(max_failures=5, lockout_seconds=300, now=lambda: t[0])
    for _ in range(5):
        limiter.record_failure()
    assert limiter.is_locked()
    assert limiter.remaining_lockout_seconds() == 300


def test_lockout_expires():
    t = [0.0]
    limiter = LoginRateLimiter(max_failures=5, lockout_seconds=300, now=lambda: t[0])
    for _ in range(5):
        limiter.record_failure()
    t[0] = 301.0
    assert not limiter.is_locked()
    assert limiter.remaining_lockout_seconds() == 0


def test_success_resets_counter():
    limiter = LoginRateLimiter(max_failures=5, lockout_seconds=300, now=lambda: 0.0)
    for _ in range(4):
        limiter.record_failure()
    limiter.record_success()
    for _ in range(4):
        limiter.record_failure()
    assert not limiter.is_locked()


def test_remaining_lockout_decreases_with_time():
    t = [0.0]
    limiter = LoginRateLimiter(max_failures=5, lockout_seconds=300, now=lambda: t[0])
    for _ in range(5):
        limiter.record_failure()
    t[0] = 100.0
    assert limiter.remaining_lockout_seconds() == 200
```

- [ ] **Step 2: 테스트 실행하여 실패 확인**

Run: `pytest tests/test_auth.py -v`
Expected: 모든 테스트 FAIL.

- [ ] **Step 3: `auth.py` 구현**

Create `/Users/gim-yun-yeong/project1/auth.py`:
```python
import time
from typing import Callable, Optional


class LoginRateLimiter:
    """브라우저 세션 단위의 로그인 시도 제한.

    Streamlit `st.session_state`에 인스턴스를 보관해 사용.
    `now` 인자는 테스트에서 시간을 주입할 수 있게 의존성 분리.
    """

    def __init__(
        self,
        max_failures: int = 5,
        lockout_seconds: int = 300,
        now: Callable[[], float] = time.time,
    ):
        self.max_failures = max_failures
        self.lockout_seconds = lockout_seconds
        self._now = now
        self._failure_count = 0
        self._lockout_started_at: Optional[float] = None

    def record_failure(self) -> None:
        self._failure_count += 1
        if self._failure_count >= self.max_failures and self._lockout_started_at is None:
            self._lockout_started_at = self._now()

    def record_success(self) -> None:
        self._failure_count = 0
        self._lockout_started_at = None

    def is_locked(self) -> bool:
        return self.remaining_lockout_seconds() > 0

    def remaining_lockout_seconds(self) -> int:
        if self._lockout_started_at is None:
            return 0
        elapsed = self._now() - self._lockout_started_at
        remaining = self.lockout_seconds - elapsed
        if remaining <= 0:
            # 잠금 자동 해제
            self._failure_count = 0
            self._lockout_started_at = None
            return 0
        return int(remaining)

    @property
    def remaining_attempts(self) -> int:
        """남은 시도 횟수 (0이면 잠금)."""
        return max(0, self.max_failures - self._failure_count)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_auth.py -v`
Expected: 모든 테스트 PASS.

- [ ] **Step 5: 커밋**

```bash
git add tests/test_auth.py auth.py
git commit -m "feat(auth): LoginRateLimiter with time-based lockout"
```

---

## Task 8: 매칭 로직 모듈 — KOBIS↔admin 결합 (TDD)

**Files:**
- Create: `tests/test_matcher.py`
- Create: `matcher.py`

- [ ] **Step 1: 매칭 로직 테스트 작성**

Create `/Users/gim-yun-yeong/project1/tests/test_matcher.py`:
```python
from dataclasses import dataclass

from kobis import Movie
from matcher import AdminMatch, pick_admin_match, MatchOutcome, build_outcome


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


def test_pick_admin_match_year_only_when_title_differs():
    candidates = [
        admin(id="1", title="DUNE 2", year=2024),
        admin(id="2", title="DUNE 1", year=2021),
    ]
    chosen = pick_admin_match(kobis(), candidates)
    assert chosen.id == "1"


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
```

- [ ] **Step 2: 테스트 실행하여 실패 확인**

Run: `pytest tests/test_matcher.py -v`
Expected: 모든 테스트 FAIL.

- [ ] **Step 3: `matcher.py` 구현**

Create `/Users/gim-yun-yeong/project1/matcher.py`:
```python
from dataclasses import dataclass
from typing import Optional

from kobis import Movie
from excel import MatchResult


@dataclass
class AdminMatch:
    """admin.kubecha.com 검색 결과 한 행."""
    id: str
    code: str
    title: str
    year: Optional[int]


@dataclass
class MatchOutcome:
    """한 작품의 처리 결과 + 상태."""
    user_input: str
    status: str  # "success", "kobis_not_found", "admin_not_found", "kobis_ambiguous"
    result: Optional[MatchResult] = None
    kobis_candidates: Optional[list[Movie]] = None  # for kobis_ambiguous
    reason: str = ""


def pick_admin_match(
    kobis_movie: Movie, candidates: list[AdminMatch]
) -> Optional[AdminMatch]:
    """admin 후보 중 KOBIS와 가장 잘 맞는 항목 선택.

    매칭 전략:
      1. year가 동일한 후보만 남김
      2. title 정확히 일치하면 그것
      3. title 비교 무관하게 year 일치하는 첫 항목 선택 (admin 검색 자체가
         title로 이미 필터링한 결과이므로 year만 맞으면 같은 작품으로 간주)
      4. year 일치 후보 없으면 None
    """
    if not candidates:
        return None
    if kobis_movie.year is None:
        # year 정보 없으면 admin 첫 결과 사용
        return candidates[0]

    same_year = [c for c in candidates if c.year == kobis_movie.year]
    if not same_year:
        return None

    exact_title = [c for c in same_year if c.title == kobis_movie.title]
    if exact_title:
        return exact_title[0]

    return same_year[0]


def build_outcome(
    user_input: str,
    kobis_movie: Optional[Movie],
    admin_match: Optional[AdminMatch],
) -> MatchOutcome:
    """단일 작품에 대한 최종 처리 결과 생성."""
    if kobis_movie is None:
        return MatchOutcome(
            user_input=user_input,
            status="kobis_not_found",
            reason="KOBIS 검색 결과 없음",
        )
    if admin_match is None:
        return MatchOutcome(
            user_input=user_input,
            status="admin_not_found",
            reason="admin에서 일치하는 작품을 찾지 못함",
        )
    return MatchOutcome(
        user_input=user_input,
        status="success",
        result=MatchResult(
            id=admin_match.id,
            code=admin_match.code,
            title=kobis_movie.title,
            release_date=kobis_movie.release_date,
        ),
    )
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_matcher.py -v`
Expected: 모든 테스트 PASS.

- [ ] **Step 5: 커밋**

```bash
git add tests/test_matcher.py matcher.py
git commit -m "feat(matcher): KOBIS↔admin matching and outcome builder"
```

---

## Task 9: admin 모듈 — Playwright 클라이언트 스켈레톤

**Files:**
- Create: `admin.py`

이 모듈은 외부 사이트에 의존하므로 자동 단위 테스트는 어렵다. 대신 수동 확인 절차를 포함하고, 셀렉터를 명확히 분리해 변경 시 한 곳만 수정 가능하게 한다.

- [ ] **Step 1: `admin.py` 스켈레톤 생성**

Create `/Users/gim-yun-yeong/project1/admin.py`:
```python
"""admin.kubecha.com 자동화 클라이언트.

Playwright headless Chromium으로 다음 작업을 수행:
  1. /brew/session/new 로그인
  2. /brew/galaxy/movies 에서 작품 검색 → id/code/title/year 추출

Streamlit 환경에서는 인스턴스를 `st.session_state`에 보관해 세션 동안
브라우저 1개를 재사용한다.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
)

from matcher import AdminMatch


ADMIN_LOGIN_URL = "https://admin.kubecha.com/brew/session/new"
ADMIN_MOVIES_URL = "https://admin.kubecha.com/brew/galaxy/movies"


class AdminClient:
    """Playwright 기반 admin 자동화 클라이언트."""

    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._logged_in = False

    def start(self) -> None:
        """Playwright와 헤드리스 브라우저 시작."""
        if self._playwright is not None:
            return
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        self._context = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        self._page = self._context.new_page()

    def stop(self) -> None:
        """브라우저 종료. 메모리 정리."""
        if self._context:
            self._context.close()
            self._context = None
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None
        self._page = None
        self._logged_in = False

    @property
    def logged_in(self) -> bool:
        return self._logged_in
```

- [ ] **Step 2: 스켈레톤 import 확인용 단위 테스트 작성**

Create `/Users/gim-yun-yeong/project1/tests/test_admin_import.py`:
```python
def test_admin_module_imports():
    from admin import AdminClient, ADMIN_LOGIN_URL, ADMIN_MOVIES_URL
    client = AdminClient()
    assert not client.logged_in
```

Run: `pytest tests/test_admin_import.py -v`
Expected: PASS.

- [ ] **Step 3: 커밋**

```bash
git add admin.py tests/test_admin_import.py
git commit -m "feat(admin): Playwright client skeleton with lifecycle"
```

---

## Task 10: admin 모듈 — 로그인 메서드

**Files:**
- Modify: `admin.py`

- [ ] **Step 1: `login` 메서드 추가**

Append to `AdminClient` class in `/Users/gim-yun-yeong/project1/admin.py`:
```python
    def login(self, email: str, password: str) -> bool:
        """admin 로그인. 성공 여부를 bool로 반환.

        성공 판정: 로그인 페이지가 아닌 다른 URL로 이동했고,
                 영화 페이지의 검색 입력 필드가 존재.
        """
        if self._page is None:
            self.start()
        page = self._page
        assert page is not None

        page.goto(ADMIN_LOGIN_URL, wait_until="domcontentloaded")

        # 다중 셀렉터 fallback: email 필드
        email_input = page.locator(
            'input[type="email"], input[name*="email"], input[id*="email"]'
        ).first
        if email_input.count() == 0:
            email_input = page.locator("input").nth(0)
        email_input.fill(email)

        # password 필드
        password_input = page.locator('input[type="password"]').first
        if password_input.count() == 0:
            password_input = page.locator("input").nth(1)
        password_input.fill(password)

        # 제출 버튼: 텍스트 "제출" 우선
        submit = page.locator('button:has-text("제출"), input[type="submit"]').first
        submit.click()

        # 로그인 후 영화 페이지로 이동 시도
        page.wait_for_load_state("domcontentloaded")

        # 로그인 성공 검증: 영화 페이지로 직접 이동해 검색 박스 존재 확인
        page.goto(ADMIN_MOVIES_URL, wait_until="domcontentloaded")
        search_input = page.locator(
            'input[placeholder*="Search for title"]'
        )
        self._logged_in = search_input.count() > 0
        return self._logged_in
```

- [ ] **Step 2: 수동 로그인 테스트 스크립트 생성**

Create `/Users/gim-yun-yeong/project1/scripts/manual_test_admin_login.py`:
```python
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
```

Run:
```bash
mkdir -p scripts
# (위 파일 작성)
```

- [ ] **Step 3: 수동 로그인 검증**

사용자에게 직접 실행을 요청:
```bash
ADMIN_EMAIL="<본인 admin email>" ADMIN_PW="<본인 admin pw>" python scripts/manual_test_admin_login.py
```
Expected: "로그인 성공" 출력.

실패 시: `login_fail.png` 캡처를 확인해 셀렉터 조정 필요.

- [ ] **Step 4: 커밋**

```bash
git add admin.py scripts/manual_test_admin_login.py
git commit -m "feat(admin): login flow with multi-selector fallback"
```

---

## Task 11: admin 모듈 — 작품 검색 메서드

**Files:**
- Modify: `admin.py`

- [ ] **Step 1: `search` 메서드 추가**

Append to `AdminClient` class:
```python
    def search(self, title: str) -> list[AdminMatch]:
        """admin에서 작품명 검색. 결과 테이블에서 id/code/title/year 추출.

        선행 조건: login()이 성공해 self._logged_in == True.
        실패 시: RuntimeError 발생.
        """
        if not self._logged_in or self._page is None:
            raise RuntimeError("Not logged in. Call login() first.")
        page = self._page

        # 영화 페이지로 이동
        if "/brew/galaxy/movies" not in page.url:
            page.goto(ADMIN_MOVIES_URL, wait_until="domcontentloaded")

        # 검색창에 입력 (기존 값 클리어 후)
        search_input = page.locator(
            'input[placeholder*="Search for title"]'
        ).first
        search_input.fill(title)

        # Search 버튼 클릭
        search_btn = page.locator('button:has-text("Search")').first
        if search_btn.count() == 0:
            search_btn = page.locator('input[type="submit"][value="Search"]').first
        search_btn.click()

        # 결과 테이블 로드 대기
        page.wait_for_load_state("networkidle", timeout=10000)

        # 결과 테이블 파싱
        return self._extract_results(page)

    def _extract_results(self, page: Page) -> list[AdminMatch]:
        """테이블의 각 행에서 id, code, title, year 추출.

        admin 테이블 컬럼 순서: id, code, poster, title, year, genre, ...
        """
        results: list[AdminMatch] = []
        rows = page.locator("table tbody tr")
        count = rows.count()
        for i in range(count):
            row = rows.nth(i)
            cells = row.locator("td")
            if cells.count() < 5:
                continue
            id_text = cells.nth(0).inner_text().strip()
            code_text = cells.nth(1).inner_text().strip()
            # cells.nth(2) = poster image
            title_text = cells.nth(3).inner_text().strip()
            year_text = cells.nth(4).inner_text().strip()

            # 헤더의 필터 행은 빈 셀이거나 input만 있음
            if not id_text or not id_text.isdigit() and not id_text.replace("-", "").isdigit():
                continue

            # title 셀에는 한글 제목 + 언어 태그가 함께 있을 수 있음
            # 첫 줄(또는 ko 태그 이전)을 제목으로 간주
            title_clean = title_text.split("\n")[0].strip()

            try:
                year_val = int(year_text) if year_text else None
            except ValueError:
                year_val = None

            results.append(
                AdminMatch(
                    id=id_text,
                    code=code_text,
                    title=title_clean,
                    year=year_val,
                )
            )
        return results
```

- [ ] **Step 2: 수동 검색 테스트 스크립트 생성**

Create `/Users/gim-yun-yeong/project1/scripts/manual_test_admin_search.py`:
```python
"""admin 검색 수동 검증 스크립트.

사용법:
    ADMIN_EMAIL="..." ADMIN_PW="..." python scripts/manual_test_admin_search.py "어벤져스"
"""
import os
import sys

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
```

- [ ] **Step 3: 수동 검색 검증**

사용자에게 다음 실행 요청:
```bash
ADMIN_EMAIL="..." ADMIN_PW="..." python scripts/manual_test_admin_search.py "어벤져스"
```
Expected: id/code/title/year가 표시된 결과 1건 이상.

여러 작품으로 추가 검증:
- 정상 케이스: "어벤져스: 엔드게임"
- 동명이작: "알라딘"
- 없는 작품: "이상한작품명없음" → 결과 0건

- [ ] **Step 4: 커밋**

```bash
git add admin.py scripts/manual_test_admin_search.py
git commit -m "feat(admin): movie search with table row extraction"
```

---

## Task 12: Streamlit 앱 — 로그인 화면

**Files:**
- Create: `app.py`

- [ ] **Step 1: `app.py` 초기 구조 + 로그인 화면**

Create `/Users/gim-yun-yeong/project1/app.py`:
```python
"""편성 자동화 대시보드 Streamlit 진입점."""
import streamlit as st

from admin import AdminClient
from auth import LoginRateLimiter


PAGE_TITLE = "편성 자동화 대시보드"


def init_session_state() -> None:
    """세션 상태 초기화 (한 번만)."""
    if "rate_limiter" not in st.session_state:
        st.session_state.rate_limiter = LoginRateLimiter()
    if "admin_client" not in st.session_state:
        st.session_state.admin_client = None
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "results" not in st.session_state:
        st.session_state.results = None


def render_login_screen() -> None:
    st.title(f"📺 {PAGE_TITLE}")
    st.caption("사내 admin 계정으로 로그인하세요.")

    limiter: LoginRateLimiter = st.session_state.rate_limiter

    if limiter.is_locked():
        remaining = limiter.remaining_lockout_seconds()
        st.error(
            f"로그인 시도가 너무 많아 잠금되었습니다. "
            f"남은 시간: {remaining // 60}분 {remaining % 60}초"
        )
        return

    with st.form("login_form"):
        email = st.text_input("email", autocomplete="username")
        password = st.text_input(
            "password", type="password", autocomplete="current-password"
        )
        submitted = st.form_submit_button("로그인")

    if submitted:
        if not email or not password:
            st.warning("email과 password를 모두 입력하세요.")
            return
        with st.spinner("admin 로그인 중..."):
            client = AdminClient()
            client.start()
            try:
                ok = client.login(email, password)
            except Exception as exc:
                client.stop()
                limiter.record_failure()
                st.error(f"로그인 중 오류: {exc}")
                return
        if ok:
            limiter.record_success()
            st.session_state.admin_client = client
            st.session_state.logged_in = True
            st.rerun()
        else:
            client.stop()
            limiter.record_failure()
            remaining_attempts = limiter.remaining_attempts
            if remaining_attempts > 0:
                st.error(
                    f"ID 또는 비밀번호가 올바르지 않습니다. "
                    f"남은 시도: {remaining_attempts}회"
                )
            else:
                st.error("로그인 시도 초과. 5분간 잠금됩니다.")


def render_main_screen() -> None:
    st.title(f"📺 {PAGE_TITLE}")
    st.success("로그인됨. (메인 화면은 다음 Task에서 구현됨)")
    if st.button("로그아웃"):
        if st.session_state.admin_client:
            st.session_state.admin_client.stop()
        st.session_state.admin_client = None
        st.session_state.logged_in = False
        st.session_state.results = None
        st.rerun()


def main() -> None:
    st.set_page_config(page_title=PAGE_TITLE, page_icon="📺", layout="wide")
    init_session_state()

    if st.session_state.logged_in:
        render_main_screen()
    else:
        render_login_screen()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: `secrets.toml` 로컬 생성 (Git 제외)**

Create `/Users/gim-yun-yeong/project1/.streamlit/secrets.toml`:
```toml
KOBIS_API_KEY = "bc595edc3946f4e849bf27e28c19258b"
```

`.gitignore`에 `.streamlit/secrets.toml`이 포함되어 있는지 재확인.

- [ ] **Step 3: 수동 실행 검증**

Run:
```bash
streamlit run app.py
```
브라우저에서 `http://localhost:8501` 자동 열림.

검증:
1. 로그인 화면 표시 확인
2. 잘못된 비밀번호로 5회 시도 → 잠금 메시지 표시 확인
3. 올바른 비밀번호 → 메인 화면(placeholder) 진입 확인
4. 로그아웃 → 로그인 화면 복귀 확인

- [ ] **Step 4: 커밋**

```bash
git add app.py
git commit -m "feat(ui): login screen with rate limiting"
```

---

## Task 13: Streamlit 앱 — 작품 리스트 입력 화면

**Files:**
- Modify: `app.py`

- [ ] **Step 1: `render_main_screen` 확장 — 입력 폼**

Replace `render_main_screen` in `app.py` with:
```python
import io
import pandas as pd


MAX_TITLES = 100


def render_main_screen() -> None:
    st.title(f"📺 {PAGE_TITLE}")
    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button("로그아웃", use_container_width=True):
            if st.session_state.admin_client:
                st.session_state.admin_client.stop()
            st.session_state.admin_client = None
            st.session_state.logged_in = False
            st.session_state.results = None
            st.rerun()

    if st.session_state.results is not None:
        render_result_screen()
        return

    st.subheader("작품 리스트 입력")
    st.caption("최대 100개까지 한 번에 처리할 수 있습니다.")

    tab_text, tab_file = st.tabs(["📝 텍스트 붙여넣기", "📂 엑셀 파일 업로드"])

    titles: list[str] = []

    with tab_text:
        raw = st.text_area(
            "한 줄에 작품 하나씩 입력",
            height=200,
            placeholder="어벤져스: 엔드게임\n인사이드 아웃 2\n듄: 파트2",
        )
        if raw:
            titles = [t.strip() for t in raw.splitlines() if t.strip()]

    with tab_file:
        uploaded = st.file_uploader(
            "엑셀 파일 (첫 컬럼이 작품명)",
            type=["xlsx", "xls"],
            accept_multiple_files=False,
        )
        if uploaded is not None:
            try:
                df = pd.read_excel(uploaded)
                first_col = df.iloc[:, 0].dropna().astype(str).tolist()
                titles = [t.strip() for t in first_col if t.strip()]
            except Exception as exc:
                st.error(f"엑셀 파일을 읽는 중 오류: {exc}")

    # 중복 제거 + 개수 검증
    deduped = list(dict.fromkeys(titles))
    removed = len(titles) - len(deduped)
    if removed > 0:
        st.info(f"중복 {removed}건이 자동 제거되었습니다.")
    titles = deduped

    if len(titles) > MAX_TITLES:
        st.warning(f"최대 {MAX_TITLES}개까지만 처리할 수 있습니다. 처음 {MAX_TITLES}개만 사용됩니다.")
        titles = titles[:MAX_TITLES]

    st.write(f"**처리 대기: {len(titles)}건**")

    if st.button(
        "🔍 매칭 시작",
        type="primary",
        disabled=len(titles) == 0,
    ):
        st.session_state.pending_titles = titles
        st.rerun()


def render_result_screen() -> None:
    """결과 화면 — Task 15에서 구현."""
    st.info("결과 화면은 다음 Task에서 구현됨")
    if st.button("입력으로 돌아가기"):
        st.session_state.results = None
        st.rerun()
```

Add `import io` and `import pandas as pd` at top of file. Add `pandas` to `requirements.txt`:

```
pandas>=2.0
```

Run `pip install pandas` after updating.

- [ ] **Step 2: 수동 실행 검증**

Run: `streamlit run app.py`

검증:
1. 로그인 후 입력 화면 표시
2. 텍스트 영역에 3개 작품 입력 → "처리 대기: 3건" 표시
3. 같은 작품 중복 입력 → "중복 1건 자동 제거됨" 알림
4. 101개 입력 → "최대 100개" 경고
5. 0개 입력 시 "매칭 시작" 버튼 비활성화
6. 매칭 시작 클릭 → 다음 화면 진입 (placeholder)

- [ ] **Step 3: 커밋**

```bash
git add app.py requirements.txt
git commit -m "feat(ui): title list input with text and Excel modes"
```

---

## Task 14: Streamlit 앱 — 매칭 오케스트레이션

**Files:**
- Modify: `app.py`

- [ ] **Step 1: 매칭 오케스트레이션 함수 추가**

Append to `app.py` (after existing functions):
```python
from kobis import search_movies_with_fallback
from matcher import MatchOutcome, build_outcome, pick_admin_match


def run_matching(titles: list[str]) -> list[MatchOutcome]:
    """모든 작품에 대해 KOBIS + admin 매칭을 순차 실행.

    중간에 한 작품이 실패해도 다음 작품은 계속 처리.
    """
    api_key = st.secrets["KOBIS_API_KEY"]
    admin_client: AdminClient = st.session_state.admin_client

    progress_bar = st.progress(0.0)
    status_text = st.empty()
    outcomes: list[MatchOutcome] = []

    total = len(titles)
    for i, title in enumerate(titles, start=1):
        status_text.text(f"[{i}/{total}] {title} 처리 중...")

        # KOBIS
        try:
            kobis_results = search_movies_with_fallback(title, api_key)
        except Exception as exc:
            outcomes.append(
                MatchOutcome(
                    user_input=title,
                    status="kobis_not_found",
                    reason=f"KOBIS 오류: {exc}",
                )
            )
            progress_bar.progress(i / total)
            continue

        if not kobis_results:
            outcomes.append(build_outcome(title, None, None))
            progress_bar.progress(i / total)
            continue

        if len(kobis_results) > 1:
            outcomes.append(
                MatchOutcome(
                    user_input=title,
                    status="kobis_ambiguous",
                    kobis_candidates=kobis_results,
                )
            )
            progress_bar.progress(i / total)
            continue

        kobis_movie = kobis_results[0]

        # admin
        try:
            admin_candidates = admin_client.search(kobis_movie.title)
        except Exception as exc:
            outcomes.append(
                MatchOutcome(
                    user_input=title,
                    status="admin_not_found",
                    reason=f"admin 오류: {exc}",
                )
            )
            progress_bar.progress(i / total)
            continue

        admin_match = pick_admin_match(kobis_movie, admin_candidates)
        outcomes.append(build_outcome(title, kobis_movie, admin_match))
        progress_bar.progress(i / total)

    status_text.text("완료")
    return outcomes
```

- [ ] **Step 2: `render_main_screen`에서 매칭 트리거 연결**

Modify `render_main_screen` — replace the section that handles `pending_titles`:

먼저 `init_session_state`에 추가:
```python
    if "pending_titles" not in st.session_state:
        st.session_state.pending_titles = None
```

그리고 `render_main_screen` 시작 부분(로그아웃 버튼 이후, results 분기 이전)에 추가:
```python
    if st.session_state.pending_titles is not None:
        with st.spinner("매칭 진행 중..."):
            outcomes = run_matching(st.session_state.pending_titles)
        st.session_state.results = outcomes
        st.session_state.pending_titles = None
        st.rerun()
```

- [ ] **Step 3: 수동 실행 검증**

Run: `streamlit run app.py`

검증:
1. 로그인 → 작품 5개 입력 (예: "어벤져스: 엔드게임", "인사이드 아웃 2", "이상한작품명없음", "알라딘", "듄: 파트2")
2. "매칭 시작" 클릭
3. 진행률 막대와 현재 작품명 표시 확인
4. 완료 후 결과 화면(placeholder) 진입
5. 콘솔에서 outcomes 리스트가 채워졌는지 확인 (`st.session_state.results`)

- [ ] **Step 4: 커밋**

```bash
git add app.py
git commit -m "feat(ui): matching orchestration with progress display"
```

---

## Task 15: Streamlit 앱 — 결과 화면 (통합 표 + 분리된 복사 버튼 + 엑셀 다운로드)

**Files:**
- Modify: `app.py`

- [ ] **Step 1: 결과 화면 렌더링 함수 작성**

Replace `render_result_screen` in `app.py`:
```python
import pandas as pd
from excel import MatchResult, tsv_id_code_title, tsv_release_date, xlsx_bytes


def render_result_screen() -> None:
    outcomes: list[MatchOutcome] = st.session_state.results

    successes = [o for o in outcomes if o.status == "success"]
    ambiguous = [o for o in outcomes if o.status == "kobis_ambiguous"]
    failures = [
        o for o in outcomes if o.status in ("kobis_not_found", "admin_not_found")
    ]

    # 요약 카드
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("총 작품", len(outcomes))
    c2.metric("✅ 매칭 성공", len(successes))
    c3.metric("⚠️ 동명이작 선택", len(ambiguous))
    c4.metric("❌ 매칭 실패", len(failures))

    # 동명이작 선택 영역
    if ambiguous:
        st.divider()
        st.subheader("⚠️ 동명이작 선택이 필요한 작품")
        for idx, o in enumerate(ambiguous):
            with st.container(border=True):
                st.markdown(f"**검색어**: {o.user_input}")
                options = []
                for c in o.kobis_candidates:
                    year = c.year if c.year else "?"
                    directors = ", ".join(c.directors) if c.directors else "감독 정보 없음"
                    genres = ", ".join(c.genres) if c.genres else "장르 정보 없음"
                    options.append(
                        f"{c.title} ({year}) — {directors}, {genres}"
                    )
                options.append("선택 안 함 (실패로 처리)")
                pick = st.radio(
                    "선택",
                    options=options,
                    key=f"ambig_{idx}",
                    label_visibility="collapsed",
                )
                if st.button("이걸로 결정", key=f"confirm_{idx}"):
                    if pick == options[-1]:
                        outcomes[outcomes.index(o)] = MatchOutcome(
                            user_input=o.user_input,
                            status="kobis_not_found",
                            reason="사용자가 동명이작 중 선택 안 함",
                        )
                    else:
                        chosen_idx = options.index(pick)
                        chosen_kobis = o.kobis_candidates[chosen_idx]
                        # admin 검색
                        admin_client: AdminClient = st.session_state.admin_client
                        try:
                            admin_candidates = admin_client.search(chosen_kobis.title)
                            admin_match = pick_admin_match(chosen_kobis, admin_candidates)
                            outcomes[outcomes.index(o)] = build_outcome(
                                o.user_input, chosen_kobis, admin_match
                            )
                        except Exception as exc:
                            outcomes[outcomes.index(o)] = MatchOutcome(
                                user_input=o.user_input,
                                status="admin_not_found",
                                reason=f"admin 오류: {exc}",
                            )
                    st.session_state.results = outcomes
                    st.rerun()

    # 매칭 실패
    if failures:
        st.divider()
        st.subheader("❌ 매칭 실패")
        for o in failures:
            st.markdown(f"- **{o.user_input}** — {o.reason}")

    # 성공 결과 표
    st.divider()
    st.subheader("✅ 매칭 성공 결과")
    if not successes:
        st.info("매칭 성공한 작품이 없습니다.")
    else:
        results: list[MatchResult] = [o.result for o in successes]
        df = pd.DataFrame(
            [(r.id, r.code, r.title, r.release_date) for r in results],
            columns=["id", "code", "title", "개봉일"],
        )
        st.dataframe(df, use_container_width=True, hide_index=True)

        # 클립보드 복사 영역 (Streamlit의 st.code는 우상단에 복사 버튼 내장)
        st.markdown("**📋 id / code / title 복사** (3컬럼)")
        st.code(tsv_id_code_title(results), language=None)

        st.markdown("**📋 개봉일만 복사** (1컬럼)")
        st.code(tsv_release_date(results), language=None)

        # 엑셀 다운로드
        from datetime import datetime

        ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
        st.download_button(
            label="💾 엑셀 파일 받기 (4컬럼)",
            data=xlsx_bytes(results),
            file_name=f"편성_매칭결과_{ts}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # 새 작업 시작
    st.divider()
    if st.button("새 작품 리스트로 시작"):
        st.session_state.results = None
        st.rerun()
```

- [ ] **Step 2: 수동 실행 검증**

Run: `streamlit run app.py`

검증 (이전 Task의 5개 작품 시나리오 활용):
1. 매칭 완료 후 결과 화면 진입
2. 요약 카드 4개(총/성공/동명이작/실패) 표시 확인
3. 동명이작(알라딘) 선택 영역 표시 → 후보 선택 → "이걸로 결정" 클릭 → 성공으로 이동 확인
4. 매칭 실패(이상한작품명없음)가 별도 영역에 표시되는지 확인
5. 성공 결과 표에 id/code/title/개봉일 4컬럼 표시 확인
6. "id/code/title 복사" 코드 블록 우상단 복사 아이콘 클릭 → 다른 곳(메모장)에 붙여넣기 → 탭 구분 3컬럼 확인
7. "개봉일만 복사" → 줄바꿈 1컬럼 확인
8. 엑셀 파일 다운로드 → 열어서 4컬럼 헤더+데이터 확인
9. "새 작품 리스트로 시작" → 입력 화면 복귀 확인

- [ ] **Step 3: 커밋**

```bash
git add app.py
git commit -m "feat(ui): result screen with split copy buttons and Excel download"
```

---

## Task 16: 디자인 다듬기 — CSS 주입

**Files:**
- Modify: `app.py`

- [ ] **Step 1: CSS 주입 추가**

In `app.py`, append to `main()` (right after `st.set_page_config`):
```python
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 1100px;
            padding-top: 2rem;
        }
        button[kind="primary"] {
            border-radius: 8px;
            font-weight: 600;
        }
        .stMetric {
            background-color: #FAFAFA;
            padding: 12px;
            border-radius: 8px;
            border: 1px solid #EEE;
        }
        h1, h2, h3 {
            letter-spacing: -0.02em;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
```

- [ ] **Step 2: 수동 실행 검증**

Run: `streamlit run app.py`

검증:
1. 페이지 전체 폭이 1100px로 제한되는지 확인
2. "매칭 시작" 같은 primary 버튼이 둥근 모서리 + 굵은 글씨인지 확인
3. 요약 metric 카드가 회색 배경 박스로 보이는지 확인
4. 제목들의 자간이 살짝 좁아 깔끔하게 보이는지 확인

- [ ] **Step 3: 커밋**

```bash
git add app.py
git commit -m "style(ui): CSS polish for layout, buttons, metric cards"
```

---

## Task 17: README 작성

**Files:**
- Create: `README.md`

- [ ] **Step 1: README.md 작성**

Create `/Users/gim-yun-yeong/project1/README.md`:
````markdown
# 편성 자동화 대시보드

OTT 플랫폼 개별구매 타이틀 편성 담당자를 위한 자동 매칭 대시보드.
작품명 리스트만 입력하면 KOBIS 개봉일과 사내 admin의 id/code를 자동으로 가져와 결과 표로 정리한다.

## 주요 기능

- 작품명 텍스트 입력 또는 엑셀 업로드 (최대 100개/회)
- KOBIS Open API로 개봉일 자동 조회
- admin.kubecha.com에서 id/code 자동 검색 (Playwright)
- 동명이작 자동 감지 → 사용자에게 선택 요청
- 결과를 통합 4컬럼 표로 표시
- 클립보드 복사 버튼 2개 (id/code/title 묶음 + 개봉일 단독)
- 4컬럼 엑셀 파일 다운로드
- 로그인 시도 횟수 제한 (5회 실패 시 5분 잠금)

## 로컬 개발

```bash
git clone <repository-url>
cd <repo>
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

`.streamlit/secrets.toml`을 만들고 KOBIS API 키를 넣어주세요:
```toml
KOBIS_API_KEY = "<발급받은 KOBIS Open API 키>"
```

실행:
```bash
streamlit run app.py
```

브라우저에 `http://localhost:8501`이 자동으로 열린다.

## 테스트

```bash
pytest tests/ -v
```

admin 자동화는 외부 사이트 의존이라 단위 테스트가 없다. 수동 검증:
```bash
ADMIN_EMAIL="..." ADMIN_PW="..." python scripts/manual_test_admin_login.py
ADMIN_EMAIL="..." ADMIN_PW="..." python scripts/manual_test_admin_search.py "어벤져스"
```

## 배포 (Streamlit Community Cloud)

1. 이 저장소를 GitHub에 푸시
2. https://streamlit.io/cloud → "New app" → 저장소 선택
3. Main file: `app.py`
4. Secrets에 추가:
   ```toml
   KOBIS_API_KEY = "<발급받은 키>"
   ```
5. Deploy

이후 git push만 하면 자동 재배포.

## 폴더 구조

```
.
├── app.py              # Streamlit 진입점
├── kobis.py            # KOBIS API 클라이언트
├── admin.py            # admin.kubecha.com 자동화 (Playwright)
├── excel.py            # 엑셀/TSV 생성
├── auth.py             # 로그인 시도 제한
├── matcher.py          # KOBIS↔admin 매칭 로직
├── tests/              # pytest 단위 테스트
├── scripts/            # 수동 검증 스크립트
├── .streamlit/         # Streamlit 설정 (테마, secrets)
├── requirements.txt
├── packages.txt        # Streamlit Cloud OS 패키지
└── docs/superpowers/   # 설계 문서 및 구현 계획
```

## 보안

- KOBIS API 키는 Streamlit Secrets로만 관리. 코드/저장소에 포함하지 않음.
- admin ID/PW는 메모리(세션)에만 존재. 디스크 저장 없음. 브라우저 탭 종료 시 자동 소멸.
- 로그인 시도 5회 실패 → 5분 잠금.
- 로그에는 민감 정보를 남기지 않음.

## 트러블슈팅

- **로그인 실패가 반복됨**: admin 페이지 폼이 변경되었을 수 있다. `admin.py`의 셀렉터를 확인.
- **Streamlit Cloud에서 Playwright 실패**: `packages.txt`의 의존성이 최신인지 확인. 메모리 부족 시 한 번에 처리 작품 수를 줄이거나 Fly.io 등 대안 호스팅 고려.
- **KOBIS API 한도 초과**: KOBIS 사이트에서 한도 확인. 필요시 새 키 발급.

## 라이선스

Internal use only.
````

- [ ] **Step 2: 커밋**

```bash
git add README.md
git commit -m "docs: add README with setup, deploy, and troubleshooting"
```

---

## Task 18: 로컬 통합 테스트 (전 흐름 종단간)

이 Task는 코드 변경 없이 검증만 수행한다.

- [ ] **Step 1: 로컬 통합 테스트 시나리오 실행**

Run: `streamlit run app.py`

검증 시나리오 (설계 문서 9.2 참조):
1. **잘못된 비밀번호 5회 → 잠금 메시지 확인** ✓
2. **잠금 카운트다운이 줄어드는지 확인** ✓
3. **올바른 비밀번호로 진입** ✓
4. 테스트 작품 5개 입력 (어벤져스: 엔드게임 / 인사이드 아웃 2 / 듄: 파트2 / 알라딘 / 이상한작품명없음)
5. 매칭 진행률 표시 확인 ✓
6. 결과 화면에서 자동 매칭 3건, 동명이작 1건, 실패 1건 확인 ✓
7. 동명이작 선택 → 성공으로 이동 확인 ✓
8. id/code/title 복사 → 엑셀에 붙여넣기 → 3컬럼 정렬 확인 ✓
9. 개봉일 복사 → 엑셀의 다른 컬럼에 붙여넣기 → 행 순서 일치 확인 ✓
10. 엑셀 파일 다운로드 → 4컬럼 데이터 확인 ✓

모두 통과해야 다음 Task로 진행.

- [ ] **Step 2: 단위 테스트 전체 통과 확인**

Run: `pytest tests/ -v`
Expected: 모든 테스트 PASS.

- [ ] **Step 3: 커밋 (필요 시)**

통합 테스트 중 발견된 버그 수정이 있으면 별도 커밋:
```bash
git add <fixed files>
git commit -m "fix(<scope>): <description>"
```

없으면 다음 Task로.

---

## Task 19: GitHub 저장소 푸시

- [ ] **Step 1: 사용자에게 GitHub 저장소 생성 요청**

사용자에게 다음을 직접 수행하도록 안내:
1. https://github.com/new 접속
2. Repository name: `pyeonseong-dashboard` (또는 본인 선호 이름)
3. **Private** 선택 권장 (코드 공개 불필요)
4. README, .gitignore, license는 추가하지 말 것 (이미 로컬에 있음)
5. "Create repository" 클릭

생성 후 표시되는 URL 형식: `git@github.com:<username>/pyeonseong-dashboard.git`

- [ ] **Step 2: 로컬 저장소를 GitHub에 연결 및 푸시**

사용자가 알려준 URL로:
```bash
cd /Users/gim-yun-yeong/project1
git remote add origin <user-provided-url>
git branch -M main
git push -u origin main
```

Expected: 모든 커밋 푸시 성공. GitHub 페이지 새로고침 시 코드 표시됨.

- [ ] **Step 3: 푸시 후 GitHub에서 `.streamlit/secrets.toml`이 없는지 재확인**

GitHub 저장소 페이지에서 `.streamlit/` 폴더를 열어 `secrets.toml`이 없는지 확인.
**있으면 즉시 키 회전 및 git history 정리 필요.**

---

## Task 20: Streamlit Community Cloud 배포

- [ ] **Step 1: Streamlit Cloud에 앱 생성**

사용자에게 안내:
1. https://share.streamlit.io 접속
2. GitHub 계정으로 로그인 (처음이면 권한 요청 승인)
3. "New app" 또는 "Deploy an app" 클릭
4. Repository: 방금 푸시한 저장소 선택
5. Branch: `main`
6. Main file path: `app.py`
7. App URL: 원하는 서브도메인 (예: `pyeonseong`) → 결과 URL: `https://pyeonseong.streamlit.app`

- [ ] **Step 2: Secrets 등록**

"Advanced settings" → "Secrets" 탭에 다음 입력:
```toml
KOBIS_API_KEY = "bc595edc3946f4e849bf27e28c19258b"
```

(데모 후 키 회전 권장 — 설계 문서 7.2 참조)

- [ ] **Step 3: Deploy 클릭 → 빌드 대기**

빌드 로그를 보며 대기 (3~5분):
- Python 패키지 설치
- `packages.txt`의 OS 패키지 설치
- Playwright Chromium 다운로드
- 앱 시작

Expected: "Your app is now live!" 메시지 + URL 표시.

- [ ] **Step 4: 배포 환경에서 전 흐름 검증**

브라우저로 `https://<앱이름>.streamlit.app` 접속 후 Task 18의 검증 시나리오 전체 재수행.

- 로그인 + 잠금
- 작품 5개 매칭
- 결과 표, 두 복사 버튼, 엑셀 다운로드 모두 확인

배포 환경 특이 이슈가 있으면 (예: Playwright timeout 더 김) `admin.py`의 timeout 값을 늘려 대응.

- [ ] **Step 5: 배포 결과 알림**

사용자에게 배포 URL 공유. 데모 시 사용할 안전한 작품 리스트 5~10개를 미리 정해두라고 안내.

---

## 자가 점검

이 계획서를 마치고 다음을 자체 점검한다:

- [ ] 설계 문서의 각 섹션이 한 개 이상의 Task로 다뤄짐
- [ ] 모든 Task가 실제 코드/명령을 포함 (placeholder 없음)
- [ ] 각 Task가 독립적으로 검증 가능
- [ ] TDD가 가능한 모듈(kobis, excel, auth, matcher)은 테스트 먼저
- [ ] Playwright 같은 외부 의존 모듈은 수동 검증 절차 포함
- [ ] 커밋이 작고 의미 단위로 분리됨
- [ ] 최종 단계가 배포된 URL에서의 전 흐름 검증

---

## 실행 방식 선택

이 계획서는 완성되어 `docs/superpowers/plans/2026-05-21-pyeonseong-automation-dashboard.md`에 저장됨.

**두 가지 실행 옵션:**

**1. Subagent-Driven (추천)** — 매 Task마다 새로운 subagent를 디스패치, 사이마다 review, 빠른 반복

**2. Inline Execution** — 이 세션에서 executing-plans 스킬로 직접 실행, batch + checkpoint

어떤 방식으로 진행할지 알려주세요.
