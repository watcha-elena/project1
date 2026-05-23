"""편성작 검색기 Streamlit 진입점."""
import streamlit as st

from admin import AdminClient
from auth import LoginRateLimiter
import pandas as pd

import subprocess
import sys
from pathlib import Path


@st.cache_resource
def ensure_playwright_browser() -> bool:
    """Streamlit Cloud 환경 등에서 Chromium 바이너리가 없으면 자동 설치.

    @st.cache_resource 덕분에 세션당 1회만 실행된다.
    로컬 개발 환경(이미 chromium 설치됨)에서는 즉시 True 반환.
    """
    # Playwright가 기대하는 cache 경로 확인
    cache_dirs = [
        Path.home() / ".cache" / "ms-playwright",
        Path("/home/appuser/.cache/ms-playwright"),  # Streamlit Cloud 사용자
    ]
    for cache_dir in cache_dirs:
        if cache_dir.exists() and any(cache_dir.glob("chromium-*")):
            return True

    # 설치 시도
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
        return True
    except subprocess.CalledProcessError as exc:
        # 권한이나 네트워크 문제 등으로 실패. 앱은 죽이지 않고 False만 반환.
        return False
    except Exception:
        return False


PAGE_TITLE = "편성작 검색기"
MAX_TITLES = 100


def init_session_state() -> None:
    """세션 상태 초기화 (한 번만)."""
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


def render_login_screen() -> None:
    st.title(f"🔍 {PAGE_TITLE}")
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
        # 로그인 화면에서는 자격증명을 메모리에만 저장.
        # 실제 admin 인증은 매칭 시작 시점에 일어남 (lazy verification).
        # 이유: Streamlit Cloud처럼 Playwright 초기화가 느리거나 실패할 수
        # 있는 환경에서 로그인 자체가 안 되는 상황을 막기 위함.
        st.session_state.admin_email = email
        st.session_state.admin_password = password
        st.session_state.logged_in = True
        st.rerun()


def render_main_screen() -> None:
    st.title(f"🔍 {PAGE_TITLE}")
    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button("로그아웃", use_container_width=True):
            st.session_state.admin_email = None
            st.session_state.admin_password = None
            st.session_state.logged_in = False
            st.session_state.results = None
            st.session_state.pending_titles = None
            st.rerun()

    if st.session_state.pending_titles is not None:
        with st.spinner("매칭 진행 중..."):
            outcomes = run_matching(st.session_state.pending_titles)
        st.session_state.pending_titles = None
        # 빈 결과(로그인 실패 등)는 결과 화면으로 넘기지 않음.
        # run_matching이 이미 logged_in=False 처리했으면 로그인 화면으로 돌아감.
        if outcomes:
            st.session_state.results = outcomes
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
    from excel import xlsx_bytes, MatchResult
    from datetime import datetime

    outcomes = st.session_state.results

    # 상단 뒤로가기 버튼 (입력 화면으로 복귀)
    top_back_col, _ = st.columns([1, 11])
    with top_back_col:
        if st.button("←", key="back_to_input_top", help="새 작품 리스트로 시작"):
            st.session_state.results = None
            st.rerun()

    successes = [o for o in outcomes if o.status == "success"]
    kobis_ambiguous = [o for o in outcomes if o.status == "kobis_ambiguous"]
    admin_ambiguous = [o for o in outcomes if o.status == "admin_only_ambiguous"]
    admin_uncertain = [o for o in outcomes if o.status == "admin_uncertain"]
    ambiguous = kobis_ambiguous + admin_ambiguous + admin_uncertain  # for the summary count
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
    if kobis_ambiguous or admin_ambiguous or admin_uncertain:
        st.divider()
        st.subheader("⚠️ 선택이 필요한 작품")
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

        # admin_uncertain (KOBIS 찾았으나 admin 자동 매칭 실패, 후보는 있음)
        if admin_uncertain:
            st.markdown("### 🔍 admin 자동 매칭 불확실 (직접 확인 필요)")
            st.caption(
                "KOBIS에서는 찾았지만 admin 검색 결과가 자동 매칭 기준에 정확히 일치하지 않습니다. "
                "후보 중 직접 선택하세요. 개봉일은 KOBIS 값을 사용합니다."
            )
            for idx, o in enumerate(admin_uncertain):
                sorted_candidates = sort_admin_by_similarity(o.user_input, o.admin_candidates)
                options = list(sorted_candidates) + [None]
                def _fmt_uncertain(opt):
                    if opt is None:
                        return "선택 안 함 (실패로 처리)"
                    year = opt.year if opt.year else "?"
                    return f"{opt.title} ({year}) — id={opt.id}, code={opt.code}"
                with st.container(border=True):
                    km = o.kobis_movie
                    km_year = km.year if km and km.year else "?"
                    st.markdown(
                        f"**검색어**: {o.user_input}  ·  "
                        f"**KOBIS**: {km.title if km else '?'} ({km_year})"
                    )
                    st.radio(
                        "선택",
                        options=options,
                        format_func=_fmt_uncertain,
                        key=f"uncertain_{idx}",
                        label_visibility="collapsed",
                    )

        # 일괄 적용 버튼
        st.divider()
        if st.button("✅ 선택한 항목 모두 적용", type="primary", use_container_width=True):
            _apply_ambiguity_selections(kobis_ambiguous, admin_ambiguous, admin_uncertain, outcomes)
            st.session_state.results = outcomes
            st.rerun()

    # 최종 결과 표 (모든 outcome을 입력 순서대로, 실패는 빈 칸)
    st.divider()
    st.subheader("📋 최종 결과")
    st.caption("입력한 작품 순서 그대로. 매칭에 실패하거나 미선택인 항목은 id/code/개봉일이 빈 칸입니다.")

    rows = []
    for o in outcomes:
        if o.status == "success" and o.result is not None:
            rows.append((o.result.id, o.result.code, o.user_input, o.result.release_date))
        else:
            rows.append(("", "", o.user_input, ""))
    df = pd.DataFrame(rows, columns=["id", "code", "title", "개봉일"])
    st.dataframe(df, use_container_width=True, hide_index=True)

    # 엑셀 다운로드 (동일한 전체 행 사용)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    excel_rows = [
        MatchResult(id=r[0], code=r[1], title=r[2], release_date=r[3])
        for r in rows
    ]
    st.download_button(
        label="💾 엑셀 파일 받기 (4컬럼, 입력 순서)",
        data=xlsx_bytes(excel_rows),
        file_name=f"편성_매칭결과_{ts}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    # 새 작업 시작
    st.divider()
    if st.button("새 작품 리스트로 시작", key="back_to_input_bottom"):
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


def _apply_ambiguity_selections(kobis_ambiguous, admin_ambiguous, admin_uncertain, outcomes):
    """라디오 선택을 일괄로 outcomes에 반영.

    - admin_only_ambiguous: KOBIS 0건 → admin 단순 선택, release_date 빈 칸
    - admin_uncertain: KOBIS 있음 → admin 선택 + KOBIS release_date 사용
    - kobis_ambiguous: KOBIS 다건 → admin 재검색 필요 (AdminClient 1회 세션)
    """
    # admin_only_ambiguous (network 불필요)
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

    # admin_uncertain (network 불필요, KOBIS release_date 사용)
    for idx, o in enumerate(admin_uncertain):
        pick = st.session_state.get(f"uncertain_{idx}")
        outcome_idx = outcomes.index(o)
        if pick is None:
            outcomes[outcome_idx] = MatchOutcome(
                user_input=o.user_input,
                status="admin_not_found",
                reason="사용자가 admin 후보 중 선택 안 함",
            )
        else:
            km = o.kobis_movie
            outcomes[outcome_idx] = MatchOutcome(
                user_input=o.user_input,
                status="success",
                result=MatchResult(
                    id=pick.id,
                    code=pick.code,
                    title=km.title if km else pick.title,
                    release_date=km.release_date if km else "",
                ),
                reason="사용자가 admin 후보 중 직접 선택",
            )

    # KOBIS ambiguous (network 필요)
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

                    # 1차 실패 + 사용자 입력이 KOBIS 선택지와 다르면 2차 검색
                    if admin_match is None and o.user_input.strip() != pick.title.strip():
                        try:
                            extra = ad_client.search(o.user_input)
                            seen_ids = {c.id for c in admin_candidates}
                            for c in extra:
                                if c.id not in seen_ids:
                                    admin_candidates.append(c)
                            admin_match = pick_admin_match(pick, admin_candidates)
                        except Exception:
                            pass

                    relevant = _top_relevant_admin_candidates(
                        o.user_input, pick, admin_candidates, limit=10
                    )

                    if admin_match is not None:
                        outcomes[outcome_idx] = build_outcome(o.user_input, pick, admin_match)
                    elif 1 <= len(relevant) <= 10:
                        outcomes[outcome_idx] = MatchOutcome(
                            user_input=o.user_input,
                            status="admin_uncertain",
                            admin_candidates=relevant,
                            kobis_movie=pick,
                        )
                    else:
                        outcomes[outcome_idx] = build_outcome(o.user_input, pick, None)
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


def _top_relevant_admin_candidates(
    user_input: str,
    kobis_movie,
    candidates: list,
    limit: int = 10,
) -> list:
    """admin 후보 중 user_input 또는 KOBIS title과의 유사도가 높은 상위 N개를 반환.

    제목 표기가 다른 동일 영화 대응을 위해 두 가지 검색어로 정렬해 합친다.
    유사도 등급은 sort_admin_by_similarity가 부여(낮을수록 더 유사).
    """
    if not candidates:
        return []

    # 두 가지 쿼리로 각각 정렬 → 합집합에서 더 좋은 등급(더 작은 tier) 채택
    by_user = sort_admin_by_similarity(user_input, candidates)
    by_kobis = sort_admin_by_similarity(kobis_movie.title, candidates) if kobis_movie else by_user

    # 각 후보의 더 좋은(낮은) 인덱스 = 더 유사
    best_index = {}
    for i, c in enumerate(by_user):
        best_index[c.id] = min(best_index.get(c.id, i), i)
    for i, c in enumerate(by_kobis):
        best_index[c.id] = min(best_index.get(c.id, i), i)

    sorted_unique = sorted(candidates, key=lambda c: best_index[c.id])
    return sorted_unique[:limit]


def run_matching(titles: list) -> list:
    """모든 작품에 대해 KOBIS + admin 매칭을 순차 실행.

    매번 새 AdminClient를 생성하고 로그인한 후 모든 작품을 처리.
    중간에 한 작품이 실패해도 다음 작품은 계속 처리.

    admin 로그인은 여기서 lazy하게 시도. 실패 시 자격증명 클리어 + 로그인 화면 복귀.
    """
    api_key = st.secrets["KOBIS_API_KEY"]
    email = st.session_state.admin_email
    password = st.session_state.admin_password
    limiter: LoginRateLimiter = st.session_state.rate_limiter

    progress_bar = st.progress(0.0)
    status_text = st.empty()
    outcomes: list = []

    # AdminClient 시작 (Playwright/Chromium 초기화)
    admin_client = AdminClient()
    try:
        status_text.text("관리자 시스템 준비 중...")
        admin_client.start()
    except Exception as exc:
        st.error(
            f"관리자 검색 기능을 시작할 수 없습니다 (Playwright 초기화 실패): {exc}\n\n"
            "잠시 후 다시 시도하거나 관리자에게 문의해주세요."
        )
        return []

    try:
        # admin 인증 (lazy verification — 로그인 화면에서 미루어진 검증)
        status_text.text("admin에 로그인 중...")
        try:
            login_ok = admin_client.login(email, password)
        except Exception as exc:
            st.error(f"관리자 로그인 중 오류: {exc}")
            return []

        if not login_ok:
            # 자격증명 잘못됨 → 자격증명 클리어 + 로그인 화면 복귀
            limiter.record_failure()
            remaining = limiter.remaining_attempts
            st.session_state.admin_email = None
            st.session_state.admin_password = None
            st.session_state.logged_in = False
            st.session_state.results = None
            if remaining > 0:
                st.error(
                    f"ID 또는 비밀번호가 올바르지 않습니다. "
                    f"남은 시도: {remaining}회. 다시 로그인해주세요."
                )
            else:
                st.error("로그인 시도 초과. 5분간 잠금됩니다.")
            return []
        else:
            limiter.record_success()

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

            # 1차 실패 + 사용자 입력이 KOBIS 제목과 다르면 → 2차 admin 검색
            if admin_match is None and title.strip() != kobis_movie.title.strip():
                try:
                    extra = admin_client.search(title)
                    seen_ids = {c.id for c in admin_candidates}
                    for c in extra:
                        if c.id not in seen_ids:
                            admin_candidates.append(c)
                    admin_match = pick_admin_match(kobis_movie, admin_candidates)
                except Exception:
                    # 2차 검색 오류는 무시 — 1차 결과로 진행
                    pass

            # 표시용 후보는 유사도 순 정렬 후 상위 10건
            relevant = _top_relevant_admin_candidates(
                title, kobis_movie, admin_candidates, limit=10
            )

            if admin_match is not None:
                outcomes.append(build_outcome(title, kobis_movie, admin_match))
            elif 1 <= len(relevant) <= 10:
                outcomes.append(
                    MatchOutcome(
                        user_input=title,
                        status="admin_uncertain",
                        admin_candidates=relevant,
                        kobis_movie=kobis_movie,
                    )
                )
            else:
                # 후보 0건 또는 너무 많음 (기본 목록 추정) → 실패 처리
                outcomes.append(build_outcome(title, kobis_movie, None))
            progress_bar.progress(i / total)

        status_text.text("완료")
    finally:
        admin_client.stop()

    return outcomes


def main() -> None:
    st.set_page_config(page_title=PAGE_TITLE, page_icon="🔍", layout="wide")
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

    # Streamlit Cloud 등 Chromium 미설치 환경 대비: 한 번만 자동 설치 시도
    # 실패해도 앱은 계속 동작 (로그인 후 매칭 시점에 에러 표시됨)
    ensure_playwright_browser()

    if st.session_state.logged_in:
        render_main_screen()
    else:
        render_login_screen()


if __name__ == "__main__":
    main()
