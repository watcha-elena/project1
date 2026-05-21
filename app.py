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
