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
    """한 작품의 처리 결과 + 상태."""
    user_input: str
    status: str  # "success", "kobis_not_found", "admin_not_found", "kobis_ambiguous"
    result: Optional[MatchResult] = None
    kobis_candidates: Optional[List[Movie]] = None  # for kobis_ambiguous
    reason: str = ""


def pick_admin_match(
    kobis_movie: Movie, candidates: List[AdminMatch]
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
