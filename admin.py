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

    @property
    def logged_in(self) -> bool:
        return self._logged_in
