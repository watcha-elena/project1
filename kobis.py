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
