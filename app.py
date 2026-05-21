"""편성 자동화 대시보드 Streamlit 진입점."""
import streamlit as st

from admin import AdminClient
from auth import LoginRateLimiter
import pandas as pd


PAGE_TITLE = "편성 자동화 대시보드"
MAX_TITLES = 100


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
    if "pending_titles" not in st.session_state:
        st.session_state.pending_titles = None


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
    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button("로그아웃", use_container_width=True):
            if st.session_state.admin_client:
                st.session_state.admin_client.stop()
            st.session_state.admin_client = None
            st.session_state.logged_in = False
            st.session_state.results = None
            st.rerun()

    if st.session_state.pending_titles is not None:
        with st.spinner("매칭 진행 중..."):
            outcomes = run_matching(st.session_state.pending_titles)
        st.session_state.results = outcomes
        st.session_state.pending_titles = None
        st.rerun()

    if st.session_state.results is not None:
        render_result_screen()
        return

    st.subheader("작품 리스트 입력")
    st.caption(f"최대 {MAX_TITLES}개까지 한 번에 처리할 수 있습니다.")

    tab_text, tab_file = st.tabs(["📝 텍스트 붙여넣기", "📂 엑셀 파일 업로드"])

    titles: list = []

    with tab_text:
        raw = st.text_area(
            "한 줄에 작품 하나씩 입력",
            height=200,
            placeholder="어벤져스: 엔드게임\n인사이드 아웃 2\n듄: 파트2",
        )
        if raw:
            titles = [t.strip() for t in raw.splitlines() if t.strip()]

    with tab_file:
        uploaded = st.file_uploader(
            "엑셀 파일 (첫 컬럼이 작품명)",
            type=["xlsx", "xls"],
            accept_multiple_files=False,
        )
        if uploaded is not None:
            try:
                df = pd.read_excel(uploaded)
                first_col = df.iloc[:, 0].dropna().astype(str).tolist()
                titles = [t.strip() for t in first_col if t.strip()]
            except Exception as exc:
                st.error(f"엑셀 파일을 읽는 중 오류: {exc}")

    # 중복 제거 + 개수 검증
    deduped = list(dict.fromkeys(titles))
    removed = len(titles) - len(deduped)
    if removed > 0:
        st.info(f"중복 {removed}건이 자동 제거되었습니다.")
    titles = deduped

    if len(titles) > MAX_TITLES:
        st.warning(f"최대 {MAX_TITLES}개까지만 처리할 수 있습니다. 처음 {MAX_TITLES}개만 사용됩니다.")
        titles = titles[:MAX_TITLES]

    st.write(f"**처리 대기: {len(titles)}건**")

    if st.button(
        "🔍 매칭 시작",
        type="primary",
        disabled=len(titles) == 0,
    ):
        st.session_state.pending_titles = titles
        st.rerun()


def render_result_screen() -> None:
    """결과 화면 placeholder — Task 14/15에서 구현."""
    st.info("결과 화면은 다음 Task에서 구현됨")
    if st.button("입력으로 돌아가기"):
        st.session_state.results = None
        st.rerun()


from kobis import search_movies_with_fallback
from matcher import MatchOutcome, build_outcome, pick_admin_match


def run_matching(titles: list) -> list:
    """모든 작품에 대해 KOBIS + admin 매칭을 순차 실행.

    중간에 한 작품이 실패해도 다음 작품은 계속 처리.
    """
    api_key = st.secrets["KOBIS_API_KEY"]
    admin_client: AdminClient = st.session_state.admin_client

    progress_bar = st.progress(0.0)
    status_text = st.empty()
    outcomes: list = []

    total = len(titles)
    for i, title in enumerate(titles, start=1):
        status_text.text(f"[{i}/{total}] {title} 처리 중...")

        # KOBIS
        try:
            kobis_results = search_movies_with_fallback(title, api_key)
        except Exception as exc:
            outcomes.append(
                MatchOutcome(
                    user_input=title,
                    status="kobis_not_found",
                    reason=f"KOBIS 오류: {exc}",
                )
            )
            progress_bar.progress(i / total)
            continue

        if not kobis_results:
            outcomes.append(build_outcome(title, None, None))
            progress_bar.progress(i / total)
            continue

        if len(kobis_results) > 1:
            outcomes.append(
                MatchOutcome(
                    user_input=title,
                    status="kobis_ambiguous",
                    kobis_candidates=kobis_results,
                )
            )
            progress_bar.progress(i / total)
            continue

        kobis_movie = kobis_results[0]

        # admin
        try:
            admin_candidates = admin_client.search(kobis_movie.title)
        except Exception as exc:
            outcomes.append(
                MatchOutcome(
                    user_input=title,
                    status="admin_not_found",
                    reason=f"admin 오류: {exc}",
                )
            )
            progress_bar.progress(i / total)
            continue

        admin_match = pick_admin_match(kobis_movie, admin_candidates)
        outcomes.append(build_outcome(title, kobis_movie, admin_match))
        progress_bar.progress(i / total)

    status_text.text("완료")
    return outcomes


def main() -> None:
    st.set_page_config(page_title=PAGE_TITLE, page_icon="📺", layout="wide")
    init_session_state()

    if st.session_state.logged_in:
        render_main_screen()
    else:
        render_login_screen()


if __name__ == "__main__":
    main()
