from dataclasses import dataclass, field
from typing import List, Optional

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
    """한 작품의 처리 결과 + 상태.

    status 값:
      - "success": 매칭 성공 (result 포함)
      - "kobis_not_found": KOBIS와 admin 모두에서 찾지 못함
      - "admin_not_found": KOBIS는 찾았으나 admin에서 못 찾음
      - "kobis_ambiguous": KOBIS 결과가 여러 건이라 사용자 선택 필요
      - "admin_only_ambiguous": KOBIS 0건, admin 1~5건이라 사용자가 선택 (개봉일 빈 칸)
      - "admin_uncertain": KOBIS는 찾았으나 admin이 자동 매칭 못 함, admin 후보가
                          소수 존재하여 사용자가 직접 확인/선택 (개봉일은 KOBIS 값 사용)
    """
    user_input: str
    status: str
    result: Optional[MatchResult] = None
    kobis_candidates: Optional[List[Movie]] = None
    admin_candidates: Optional[List[AdminMatch]] = None
    kobis_movie: Optional[Movie] = None  # admin_uncertain일 때 매칭에 사용할 KOBIS 정보
    reason: str = ""


def pick_admin_match(
    kobis_movie: Movie, candidates: List[AdminMatch]
) -> Optional[AdminMatch]:
    """admin 후보 중 KOBIS와 일치하는 항목 선택.

    매칭 우선순위 (위에서 아래로 시도, 첫 매치 반환):
      1. year 정확 일치 + title (정규화 후) 정확 일치
      2. year 정확 일치 + title 부분 포함
      3. year ±1 일치 + title 정확 일치
      4. year ±1 일치 + title 부분 포함
    위 어느 조건도 만족 못 하면 None.

    예외:
      - candidates가 비어 있으면 None
      - kobis_movie.year가 None이면 candidates 첫 항목 반환 (정보 부족)
      - KOBIS의 title/title_en이 모두 비어 있으면 year만으로 첫 후보 선택
    """
    if not candidates:
        return None
    if kobis_movie.year is None:
        return candidates[0]

    kobis_titles = _normalize_title_set(kobis_movie)
    if not kobis_titles:
        same_year = [c for c in candidates if c.year == kobis_movie.year]
        return same_year[0] if same_year else None

    target = kobis_movie.year

    def _title_exact(c: AdminMatch) -> bool:
        return _normalize(c.title) in kobis_titles

    def _title_contains(c: AdminMatch) -> bool:
        admin_norm = _normalize(c.title)
        for kt in kobis_titles:
            if kt and admin_norm and (kt in admin_norm or admin_norm in kt):
                return True
        return False

    # Tier 1: year exact + title exact
    for c in candidates:
        if c.year == target and _title_exact(c):
            return c

    # Tier 2: year exact + title contains
    for c in candidates:
        if c.year == target and _title_contains(c):
            return c

    # Tier 3: year ±1 + title exact
    for c in candidates:
        if c.year is not None and abs(c.year - target) == 1 and _title_exact(c):
            return c

    # Tier 4: year ±1 + title contains
    for c in candidates:
        if c.year is not None and abs(c.year - target) == 1 and _title_contains(c):
            return c

    return None


def _normalize(text: str) -> str:
    """제목 비교용 정규화: lower + 공백/문장부호 제거.

    '\\W'는 Python re 모듈에서 word 문자가 아닌 것(공백, 문장부호, 기호 등)을 의미한다.
    한글은 word 문자에 포함되므로 보존된다. 영문 알파벳/숫자도 보존.
    """
    import re
    return re.sub(r"[\W_]+", "", text.lower())


def _normalize_title_set(kobis_movie: Movie) -> set:
    """KOBIS의 한글/영문 제목을 정규화한 집합. 빈 문자열은 제외."""
    titles = {
        _normalize(kobis_movie.title),
        _normalize(kobis_movie.title_en),
    }
    return {t for t in titles if t}


def sort_kobis_by_similarity(query: str, candidates: List[Movie]) -> List[Movie]:
    """KOBIS 후보를 검색어 유사도 순으로 정렬.

    우선순위:
      0 — title 또는 title_en 정확 일치 (대소문자/공백 정규화 후)
      1 — title이 검색어로 시작
      2 — 검색어가 title에 포함됨 (또는 title이 검색어에 포함됨)
      3 — 그 외 (KOBIS가 반환한 순서대로)
    같은 등급 내에서는 최신 작품 (year 큰 것) 먼저.
    """
    q = _normalize(query)
    if not q:
        return list(candidates)

    def rank(m: Movie):
        title_norm = _normalize(m.title)
        title_en_norm = _normalize(m.title_en)
        if title_norm == q or title_en_norm == q:
            tier = 0
        elif title_norm.startswith(q) or title_en_norm.startswith(q):
            tier = 1
        elif q in title_norm or q in title_en_norm or title_norm in q or title_en_norm in q:
            tier = 2
        else:
            tier = 3
        return (tier, -(m.year or 0))

    return sorted(candidates, key=rank)


def sort_admin_by_similarity(query: str, candidates: List[AdminMatch]) -> List[AdminMatch]:
    """admin 후보를 검색어 유사도 순으로 정렬. KOBIS와 동일한 규칙."""
    q = _normalize(query)
    if not q:
        return list(candidates)

    def rank(a: AdminMatch):
        title_norm = _normalize(a.title)
        if title_norm == q:
            tier = 0
        elif title_norm.startswith(q):
            tier = 1
        elif q in title_norm or title_norm in q:
            tier = 2
        else:
            tier = 3
        return (tier, -(a.year or 0))

    return sorted(candidates, key=rank)


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
