import io
from dataclasses import dataclass
from typing import List

from openpyxl import Workbook


@dataclass
class MatchResult:
    """최종 매칭 결과 한 건. UI/엑셀에 표시될 형태."""
    id: str
    code: str
    title: str
    release_date: str


def tsv_id_code_title(results: List[MatchResult]) -> str:
    """탭 구분, 한 행에 id/code/title. 헤더 없음."""
    return "\n".join(f"{r.id}\t{r.code}\t{r.title}" for r in results)


def tsv_release_date(results: List[MatchResult]) -> str:
    """줄바꿈 구분, 한 행에 개봉일. 헤더 없음."""
    return "\n".join(r.release_date for r in results)


def xlsx_bytes(results: List[MatchResult]) -> bytes:
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
