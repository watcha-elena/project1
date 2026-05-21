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

    @property
    def logged_in(self) -> bool:
        return self._logged_in
