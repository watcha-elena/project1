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


from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class Movie:
    code: str
    title: str
    release_date: str
    directors: List[str] = field(default_factory=list)
    genres: List[str] = field(default_factory=list)

    @property
    def year(self) -> Optional[int]:
        if not self.release_date or len(self.release_date) < 4:
            return None
        try:
            return int(self.release_date[:4])
        except ValueError:
            return None


import time
import requests


KOBIS_API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieList.json"
)
DEFAULT_RETRY_DELAYS = [1.0, 2.0, 4.0]


def search_movies(
    title: str,
    api_key: str,
    retry_delays: Optional[List[float]] = None,
) -> List[Movie]:
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


def _parse_movie_list(data: dict) -> List[Movie]:
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
