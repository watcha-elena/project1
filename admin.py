"""admin.kubecha.com 자동화 클라이언트.

Playwright headless Chromium으로 다음 작업을 수행:
  1. /brew/session/new 로그인
  2. /brew/galaxy/movies 에서 작품 검색 → id/code/title/year 추출

Streamlit 환경에서는 인스턴스를 `st.session_state`에 보관해 세션 동안
브라우저 1개를 재사용한다.
"""
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

    def login(self, email: str, password: str) -> bool:
        """admin 로그인. 성공 여부를 bool로 반환.

        성공 판정: 로그인 후 /brew/galaxy/movies 페이지에서 검색 입력 필드 존재.
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

    def search(self, title: str) -> "list[AdminMatch]":
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

    def _extract_results(self, page: Page) -> "list[AdminMatch]":
        """테이블의 각 행에서 id, code, title, year 추출.

        admin 테이블 컬럼 순서: id, code, poster, title, year, genre, ...
        """
        results: list = []
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

            # 헤더의 필터 행은 빈 셀이거나 input만 있음 — id가 숫자가 아니면 스킵
            if not id_text or not id_text.isdigit():
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

    @property
    def logged_in(self) -> bool:
        return self._logged_in
