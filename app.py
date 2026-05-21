"""편성 자동화 대시보드 Streamlit 진입점."""
import streamlit as st
from streamlit_cookies_controller import CookieController

from admin import AdminClient
from auth import LoginRateLimiter
from persist import (
    COOKIE_NAME,
    COOKIE_TTL_SECONDS,
    decrypt_credentials,
    encrypt_credentials,
)
import pandas as pd


PAGE_TITLE = "편성 자동화 대시보드"
MAX_TITLES = 100


def _get_cookie_controller() -> CookieController:
    """CookieController 인스턴스는 세션 단위로 1개 유지."""
    if "cookie_controller" not in st.session_state:
        st.session_state.cookie_controller = CookieController()
    return st.session_state.cookie_controller


def init_session_state() -> None:
    """세션 상태 초기화 + 쿠키 기반 자동 복원."""
    if "rate_limiter" not in st.session_state:
        st.session_state.rate_limiter = LoginRateLimiter()
    if "admin_email" not in st.session_state:
        st.session_state.admin_email = None
    if "admin_password" not in st.session_state:
        st.session_state.admin_password = None
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "results" not in st.session_state:
        st.session_state.results = None
    if "pending_titles" not in st.session_state:
        st.session_state.pending_titles = None

    # 쿠키에서 자격증명 복원 (이미 로그인 상태가 아닐 때만)
    if not st.session_state.logged_in:
        controller = _get_cookie_controller()
        token = controller.get(COOKIE_NAME)
        if token:
            restored = decrypt_credentials(token)
            if restored:
                st.session_state.admin_email = restored[0]
                st.session_state.admin_password = restored[1]
                st.session_state.logged_in = True
            else:
                # 만료/위변조 쿠키는 정리
                controller.remove(COOKIE_NAME)


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
            test_client = AdminClient()
            test_client.start()
            try:
                ok = test_client.login(email, password)
            except Exception as exc:
                limiter.record_failure()
                st.error(f"로그인 중 오류: {exc}")
                return
            finally:
                test_client.stop()
        if ok:
            limiter.record_success()
            # 자격증명만 메모리에 보관. 매칭 실행 시마다 새 브라우저로 재로그인.
            st.session_state.admin_email = email
            st.session_state.admin_password = password
            st.session_state.logged_in = True
            # 쿠키에 암호화된 자격증명 저장 (24시간 유지)
            controller = _get_cookie_controller()
            controller.set(
                COOKIE_NAME,
                encrypt_credentials(email, password),
                max_age=COOKIE_TTL_SECONDS,
            )
            st.rerun()
        else:
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
            # 쿠키 즉시 삭제
            controller = _get_cookie_controller()
            controller.remove(COOKIE_NAME)
            st.session_state.admin_email = None
            st.session_state.admin_password = None
            st.session_state.logged_in = False
            st.session_state.results = None
            st.session_state.pending_titles = None
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
    ):
        if not titles:
            st.warning("작품을 1개 이상 입력하세요.")
        else:
            st.session_state.pending_titles = titles
            st.rerun()


def render_result_screen() -> None:
    from excel import tsv_id_code_title, tsv_release_date, xlsx_bytes, MatchResult
    from datetime import datetime

    outcomes = st.session_state.results

    successes = [o for o in outcomes if o.status == "success"]
    kobis_ambiguous = [o for o in outcomes if o.status == "kobis_ambiguous"]
    admin_ambiguous = [o for o in outcomes if o.status == "admin_only_ambiguous"]
    ambiguous = kobis_ambiguous + admin_ambiguous  # for the summary count
    failures = [
        o for o in outcomes if o.status in ("kobis_not_found", "admin_not_found")
    ]

    # 요약 카드
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("총 작품", len(outcomes))
    c2.metric("✅ 매칭 성공", len(successes))
    c3.metric("⚠️ 동명이작 선택", len(ambiguous))
    c4.metric("❌ 매칭 실패", len(failures))

    # 동명이작 선택 영역 (KOBIS + admin 통합)
    if kobis_ambiguous or admin_ambiguous:
        st.divider()
        st.subheader("⚠️ 동명이작 선택이 필요한 작품")
        st.caption("후보 중 가장 유사한 항목이 기본 선택되어 있습니다. 확인 후 하단의 일괄 적용 버튼을 눌러주세요.")

        # KOBIS 동명이작
        if kobis_ambiguous:
            st.markdown("### 📡 KOBIS 동명이작")
            for idx, o in enumerate(kobis_ambiguous):
                sorted_candidates = sort_kobis_by_similarity(o.user_input, o.kobis_candidates)
                # 선택지: sorted candidates + None (실패로 처리)
                options = list(sorted_candidates) + [None]
                def _fmt_kobis(opt, _o=o):
                    if opt is None:
                        return "선택 안 함 (실패로 처리)"
                    year = opt.year if opt.year else "?"
                    directors = ", ".join(opt.directors) if opt.directors else "감독 정보 없음"
                    genres = ", ".join(opt.genres) if opt.genres else "장르 정보 없음"
                    return f"{opt.title} ({year}) — {directors}, {genres}"
                with st.container(border=True):
                    st.markdown(f"**검색어**: {o.user_input}")
                    st.radio(
                        "선택",
                        options=options,
                        format_func=_fmt_kobis,
                        key=f"kobis_ambig_{idx}",
                        label_visibility="collapsed",
                    )

        # admin-only 동명이작
        if admin_ambiguous:
            st.markdown("### 🗂️ admin 동명이작 (KOBIS 없음, 개봉일 빈 칸)")
            for idx, o in enumerate(admin_ambiguous):
                sorted_candidates = sort_admin_by_similarity(o.user_input, o.admin_candidates)
                options = list(sorted_candidates) + [None]
                def _fmt_admin(opt):
                    if opt is None:
                        return "선택 안 함 (실패로 처리)"
                    year = opt.year if opt.year else "?"
                    return f"{opt.title} ({year}) — id={opt.id}, code={opt.code}"
                with st.container(border=True):
                    st.markdown(f"**검색어**: {o.user_input}")
                    st.radio(
                        "선택",
                        options=options,
                        format_func=_fmt_admin,
                        key=f"admin_ambig_{idx}",
                        label_visibility="collapsed",
                    )

        # 일괄 적용 버튼
        st.divider()
        if st.button("✅ 선택한 항목 모두 적용", type="primary", use_container_width=True):
            _apply_ambiguity_selections(kobis_ambiguous, admin_ambiguous, outcomes)
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
from matcher import (
    MatchOutcome,
    build_outcome,
    pick_admin_match,
    sort_kobis_by_similarity,
    sort_admin_by_similarity,
)
from excel import MatchResult


def _apply_ambiguity_selections(kobis_ambiguous, admin_ambiguous, outcomes):
    """라디오 선택을 일괄로 outcomes에 반영.

    - KOBIS 동명이작 선택은 admin 재검색이 필요하므로 AdminClient 1개로 한꺼번에 처리
    - admin-only 동명이작은 admin 호출 없이 데이터 변환만
    """
    # admin-only first (no network needed)
    for idx, o in enumerate(admin_ambiguous):
        pick = st.session_state.get(f"admin_ambig_{idx}")
        outcome_idx = outcomes.index(o)
        if pick is None:
            outcomes[outcome_idx] = MatchOutcome(
                user_input=o.user_input,
                status="kobis_not_found",
                reason="사용자가 admin 결과 중 선택 안 함",
            )
        else:
            outcomes[outcome_idx] = MatchOutcome(
                user_input=o.user_input,
                status="success",
                result=MatchResult(
                    id=pick.id,
                    code=pick.code,
                    title=pick.title,
                    release_date="",
                ),
                reason="사용자가 admin 후보 중 선택 (개봉일 미상)",
            )

    # KOBIS ambiguous needs fresh admin session
    if not kobis_ambiguous:
        return

    email = st.session_state.admin_email
    password = st.session_state.admin_password

    progress_bar = st.progress(0.0)
    status_text = st.empty()
    total = len(kobis_ambiguous)

    ad_client = AdminClient()
    ad_client.start()
    try:
        status_text.text("admin 재로그인 중...")
        if not ad_client.login(email, password):
            for o in kobis_ambiguous:
                idx = outcomes.index(o)
                outcomes[idx] = MatchOutcome(
                    user_input=o.user_input,
                    status="admin_not_found",
                    reason="admin 재로그인 실패",
                )
            return

        for i, o in enumerate(kobis_ambiguous, start=1):
            status_text.text(f"[{i}/{total}] {o.user_input} 적용 중...")
            outcome_idx = outcomes.index(o)
            pick = st.session_state.get(f"kobis_ambig_{i - 1}")
            if pick is None:
                outcomes[outcome_idx] = MatchOutcome(
                    user_input=o.user_input,
                    status="kobis_not_found",
                    reason="사용자가 동명이작 중 선택 안 함",
                )
            else:
                try:
                    admin_candidates = ad_client.search(pick.title)
                    admin_match = pick_admin_match(pick, admin_candidates)
                    outcomes[outcome_idx] = build_outcome(o.user_input, pick, admin_match)
                except Exception as exc:
                    outcomes[outcome_idx] = MatchOutcome(
                        user_input=o.user_input,
                        status="admin_not_found",
                        reason=f"admin 오류: {exc}",
                    )
            progress_bar.progress(i / total)
        status_text.text("적용 완료")
    finally:
        ad_client.stop()


def run_matching(titles: list) -> list:
    """모든 작품에 대해 KOBIS + admin 매칭을 순차 실행.

    매번 새 AdminClient를 생성하고 로그인한 후 모든 작품을 처리.
    중간에 한 작품이 실패해도 다음 작품은 계속 처리.
    """
    api_key = st.secrets["KOBIS_API_KEY"]
    email = st.session_state.admin_email
    password = st.session_state.admin_password

    progress_bar = st.progress(0.0)
    status_text = st.empty()
    outcomes: list = []

    admin_client = AdminClient()
    admin_client.start()
    try:
        # admin 재로그인 (매칭 세션마다 새 브라우저)
        status_text.text("admin에 로그인 중...")
        if not admin_client.login(email, password):
            st.error("admin 로그인에 실패했습니다. 로그아웃 후 다시 시도해주세요.")
            return []

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
                # KOBIS 0건 → admin에서 직접 검색 시도 (개봉일은 빈 칸)
                try:
                    admin_candidates = admin_client.search(title)
                except Exception as exc:
                    outcomes.append(
                        MatchOutcome(
                            user_input=title,
                            status="kobis_not_found",
                            reason=f"KOBIS 결과 없음 + admin 오류: {exc}",
                        )
                    )
                    progress_bar.progress(i / total)
                    continue

                if not admin_candidates:
                    outcomes.append(
                        MatchOutcome(
                            user_input=title,
                            status="kobis_not_found",
                            reason="KOBIS와 admin 모두에서 찾지 못함",
                        )
                    )
                elif len(admin_candidates) == 1:
                    a = admin_candidates[0]
                    outcomes.append(
                        MatchOutcome(
                            user_input=title,
                            status="success",
                            result=MatchResult(
                                id=a.id,
                                code=a.code,
                                title=a.title,
                                release_date="",
                            ),
                            reason="KOBIS 없음 — admin 단일 결과로 매칭 (개봉일 미상)",
                        )
                    )
                elif len(admin_candidates) <= 5:
                    outcomes.append(
                        MatchOutcome(
                            user_input=title,
                            status="admin_only_ambiguous",
                            admin_candidates=admin_candidates,
                        )
                    )
                else:
                    outcomes.append(
                        MatchOutcome(
                            user_input=title,
                            status="kobis_not_found",
                            reason=f"KOBIS 결과 없음, admin이 {len(admin_candidates)}건 반환 (기본 목록 추정, 실제 매칭 없음)",
                        )
                    )
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
    finally:
        admin_client.stop()

    return outcomes


def main() -> None:
    st.set_page_config(page_title=PAGE_TITLE, page_icon="📺", layout="wide")
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 1100px;
            padding-top: 2rem;
        }
        button[kind="primary"] {
            border-radius: 8px;
            font-weight: 600;
        }
        .stMetric {
            background-color: #FAFAFA;
            padding: 12px;
            border-radius: 8px;
            border: 1px solid #EEE;
        }
        h1, h2, h3 {
            letter-spacing: -0.02em;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    init_session_state()

    if st.session_state.logged_in:
        render_main_screen()
    else:
        render_login_screen()


if __name__ == "__main__":
    main()
