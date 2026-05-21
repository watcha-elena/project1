# 편성 자동화 대시보드

OTT 플랫폼 개별구매 타이틀 편성 담당자를 위한 자동 매칭 대시보드.
작품명 리스트만 입력하면 KOBIS 개봉일과 사내 admin의 id/code를 자동으로 가져와 결과 표로 정리한다.

## 주요 기능

- 작품명 텍스트 입력 또는 엑셀 업로드 (최대 100개/회)
- KOBIS Open API로 개봉일 자동 조회
- admin.kubecha.com에서 id/code 자동 검색 (Playwright)
- 동명이작 자동 감지 → 사용자에게 선택 요청
- 결과를 통합 4컬럼 표로 표시
- 클립보드 복사 버튼 2개 (id/code/title 묶음 + 개봉일 단독)
- 4컬럼 엑셀 파일 다운로드
- 로그인 시도 횟수 제한 (5회 실패 시 5분 잠금)

## 로컬 개발

```bash
git clone <repository-url>
cd <repo>
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

`.streamlit/secrets.toml`을 만들고 KOBIS API 키를 넣어주세요:
```toml
KOBIS_API_KEY = "<발급받은 KOBIS Open API 키>"
```

실행:
```bash
streamlit run app.py
```

브라우저에 `http://localhost:8501`이 자동으로 열린다.

## 테스트

```bash
pytest tests/ -v
```

admin 자동화는 외부 사이트 의존이라 단위 테스트가 없다. 수동 검증:
```bash
ADMIN_EMAIL="..." ADMIN_PW="..." python scripts/manual_test_admin_login.py
ADMIN_EMAIL="..." ADMIN_PW="..." python scripts/manual_test_admin_search.py "어벤져스"
```

## 배포 (Streamlit Community Cloud)

1. 이 저장소를 GitHub에 푸시
2. https://streamlit.io/cloud → "New app" → 저장소 선택
3. Main file: `app.py`
4. Secrets에 추가:
   ```toml
   KOBIS_API_KEY = "<발급받은 키>"
   ```
5. Deploy

이후 git push만 하면 자동 재배포.

## 폴더 구조

```
.
├── app.py              # Streamlit 진입점
├── kobis.py            # KOBIS API 클라이언트
├── admin.py            # admin.kubecha.com 자동화 (Playwright)
├── excel.py            # 엑셀/TSV 생성
├── auth.py             # 로그인 시도 제한
├── matcher.py          # KOBIS↔admin 매칭 로직
├── tests/              # pytest 단위 테스트
├── scripts/            # 수동 검증 스크립트
├── .streamlit/         # Streamlit 설정 (테마, secrets)
├── requirements.txt
├── packages.txt        # Streamlit Cloud OS 패키지
└── docs/superpowers/   # 설계 문서 및 구현 계획
```

## 보안

- KOBIS API 키는 Streamlit Secrets로만 관리. 코드/저장소에 포함하지 않음.
- admin ID/PW는 메모리(세션)에만 존재. 디스크 저장 없음. 브라우저 탭 종료 시 자동 소멸.
- 로그인 시도 5회 실패 → 5분 잠금.
- 로그에는 민감 정보를 남기지 않음.

## 트러블슈팅

- **로그인 실패가 반복됨**: admin 페이지 폼이 변경되었을 수 있다. `admin.py`의 셀렉터를 확인.
- **Streamlit Cloud에서 Playwright 실패**: `packages.txt`의 의존성이 최신인지 확인. 메모리 부족 시 한 번에 처리 작품 수를 줄이거나 Fly.io 등 대안 호스팅 고려.
- **KOBIS API 한도 초과**: KOBIS 사이트에서 한도 확인. 필요시 새 키 발급.

## 라이선스

Internal use only.
