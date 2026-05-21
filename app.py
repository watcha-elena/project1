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
    from excel import tsv_id_code_title, tsv_release_date, xlsx_bytes
    from datetime import datetime

    outcomes = st.session_state.results

    successes = [o for o in outcomes if o.status == "success"]
    ambiguous = [o for o in outcomes if o.status == "kobis_ambiguous"]
    failures = [
        o for o in outcomes if o.status in ("kobis_not_found", "admin_not_found")
    ]

    # 요약 카드
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("총 작품", len(outcomes))
    c2.metric("✅ 매칭 성공", len(successes))
    c3.metric("⚠️ 동명이작 선택", len(ambiguous))
    c4.metric("❌ 매칭 실패", len(failures))

    # 동명이작 선택 영역
    if ambiguous:
        st.divider()
        st.subheader("⚠️ 동명이작 선택이 필요한 작품")
        for idx, o in enumerate(ambiguous):
            with st.container(border=True):
                st.markdown(f"**검색어**: {o.user_input}")
                options = []
                for c in o.kobis_candidates:
                    year = c.year if c.year else "?"
                    directors = ", ".join(c.directors) if c.directors else "감독 정보 없음"
                    genres = ", ".join(c.genres) if c.genres else "장르 정보 없음"
                    options.append(
                        f"{c.title} ({year}) — {directors}, {genres}"
                    )
                options.append("선택 안 함 (실패로 처리)")
                pick = st.radio(
                    "선택",
                    options=options,
                    key=f"ambig_{idx}",
                    label_visibility="collapsed",
                )
                if st.button("이걸로 결정", key=f"confirm_{idx}"):
                    if pick == options[-1]:
                        outcomes[outcomes.index(o)] = MatchOutcome(
                            user_input=o.user_input,
                            status="kobis_not_found",
                            reason="사용자가 동명이작 중 선택 안 함",
                        )
                    else:
                        chosen_idx = options.index(pick)
                        chosen_kobis = o.kobis_candidates[chosen_idx]
                        # admin 검색
                        admin_client: AdminClient = st.session_state.admin_client
                        try:
                            admin_candidates = admin_client.search(chosen_kobis.title)
                            admin_match = pick_admin_match(chosen_kobis, admin_candidates)
                            outcomes[outcomes.index(o)] = build_outcome(
                                o.user_input, chosen_kobis, admin_match
                            )
                        except Exception as exc:
                            outcomes[outcomes.index(o)] = MatchOutcome(
                                user_input=o.user_input,
                                status="admin_not_found",
                                reason=f"admin 오류: {exc}",
                            )
                    st.session_state.results = outcomes
                    st.rerun()

    # 매칭 실패
    if failures:
        st.divider()
        st.subheader("❌ 매칭 실패")
        for o in failures:
            st.markdown(f"- **{o.user_input}** — {o.reason}")

    # 성공 결과 표
    st.divider()
    st.subheader("✅ 매칭 성공 결과")
    if not successes:
        st.info("매칭 성공한 작품이 없습니다.")
    else:
        results = [o.result for o in successes]
        df = pd.DataFrame(
            [(r.id, r.code, r.title, r.release_date) for r in results],
            columns=["id", "code", "title", "개봉일"],
        )
        st.dataframe(df, use_container_width=True, hide_index=True)

        # 클립보드 복사 영역 (Streamlit의 st.code는 우상단에 복사 버튼 내장)
        st.markdown("**📋 id / code / title 복사** (3컬럼)")
        st.code(tsv_id_code_title(results), language=None)

        st.markdown("**📋 개봉일만 복사** (1컬럼)")
        st.code(tsv_release_date(results), language=None)

        # 엑셀 다운로드
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
        st.download_button(
            label="💾 엑셀 파일 받기 (4컬럼)",
            data=xlsx_bytes(results),
            file_name=f"편성_매칭결과_{ts}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # 새 작업 시작
    st.divider()
    if st.button("새 작품 리스트로 시작"):
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
