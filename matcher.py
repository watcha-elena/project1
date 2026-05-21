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
      - "admin_only_ambiguous": KOBIS 0건이지만 admin이 여러 건 반환, 사용자 선택 필요
    """
    user_input: str
    status: str
    result: Optional[MatchResult] = None
    kobis_candidates: Optional[List[Movie]] = None
    admin_candidates: Optional[List[AdminMatch]] = None
    reason: str = ""


def pick_admin_match(
    kobis_movie: Movie, candidates: List[AdminMatch]
) -> Optional[AdminMatch]:
    """admin 후보 중 KOBIS와 일치하는 항목 선택.

    매칭 규칙:
      1. year가 KOBIS year와 동일한 후보만 남김
      2. 그 중 title이 KOBIS title 또는 title_en과 (대소문자 무시 후) 일치하는 게 있으면 그것
      3. 일치 없으면 (대소문자 무시 후) 부분 포함 — KOBIS title 또는 title_en이
         admin title에 포함되거나 그 반대인 첫 후보
      4. 위 어느 조건도 만족 못 하면 None (admin이 무관한 결과를 반환했을 가능성)

    예외: KOBIS year가 None이면 candidates의 첫 후보 반환 (정보 부족).
    """
    if not candidates:
        return None
    if kobis_movie.year is None:
        return candidates[0]

    same_year = [c for c in candidates if c.year == kobis_movie.year]
    if not same_year:
        return None

    kobis_titles = _normalize_title_set(kobis_movie)
    if not kobis_titles:
        # KOBIS title 정보가 모두 비어있으면 year만 일치하는 첫 후보 (드문 케이스)
        return same_year[0]

    # 1차: exact match (정규화 후)
    for c in same_year:
        if _normalize(c.title) in kobis_titles:
            return c

    # 2차: 부분 포함 match (한쪽이 다른 쪽에 포함)
    for c in same_year:
        admin_norm = _normalize(c.title)
        for kt in kobis_titles:
            if admin_norm and kt and (kt in admin_norm or admin_norm in kt):
                return c

    # 3차: title 관련성 부족 → admin이 무관한 기본 목록을 반환한 경우로 추정
    return None


def _normalize(text: str) -> str:
    """제목 비교용 정규화: lower + 모든 공백 제거."""
    import re
    return re.sub(r"\s+", "", text.lower())


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
