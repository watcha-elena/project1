# 편성 자동화 대시보드 — 설계 문서

- 작성일: 2026-05-21
- 대상 사용자: OTT 플랫폼 개별구매 타이틀 편성 담당자 (비개발자)
- 배포 환경: Streamlit Community Cloud (공개 URL, `*.streamlit.app`)
- 시간 제약: 없음 (충실히 구현 후 데모 + 이후 본인이 계속 사용)

---

## 1. 목적과 배경

### 1.1 문제
신규 편성 요청 작품에 대해 매번 두 가지를 수작업으로 처리하고 있다.
1. KOBIS(영화진흥위원회) 사이트에서 작품의 국내 개봉일 조회
2. 사내 admin(`admin.kubecha.com/brew/galaxy/movies`)에서 해당 작품의 id, code 조회
3. 두 정보를 사내 엑셀 양식에 옮겨 적기

이 작업이 작품당 1~2분씩, 한 회당 10~50개 처리해야 하므로 큰 시간 비용 발생.

### 1.2 목표
- 작품명 리스트만 입력하면 KOBIS 개봉일과 admin id/code를 자동 매칭
- 결과를 사내 엑셀 양식에 바로 붙여넣을 수 있도록 클립보드 복사 또는 엑셀 파일 다운로드 제공
- 동명이작 등 매칭이 애매한 경우 사용자에게 선택을 요청

### 1.3 성공 기준
- 30개 작품 기준 처리 시간이 기존 30~60분 → 3분 이내로 단축
- 데모 자리에서 미리 준비한 작품 5~10개로 끝까지 정상 동작
- 데모 후 본인이 브라우저로 공개 URL에 접속해 매일 사용 가능
- 향후 팀원에게 URL만 공유해도 즉시 사용 가능한 형태로 배포

---

## 2. 사용자 요구사항 (확정)

| 항목 | 결정 |
|---|---|
| 처리 단위 | 10~50개 배치 |
| 결과 엑셀 컬럼 | id, code, title, 개봉일 (4개) |
| admin 인증 | ID/PW (사용자가 도구 실행 시 직접 입력) |
| 매칭 흐름 | 자동 매칭 + 애매할 때 사람 개입 (질문 4의 D 방식) |
| 동명이작 처리 | KOBIS 결과 2건 이상이면 무조건 사용자가 선택 (질문 9의 A) |
| 도구 형태 | 공개 웹 대시보드 (`*.streamlit.app` 주소로 누구나 접속) |
| 프레임워크 | Python + Streamlit |
| 배포 | Streamlit Community Cloud (GitHub 연동, 무료) |
| 디자인 자유도 | 레벨 1(테마) + 레벨 2(CSS) |
| 세션 정책 | 브라우저 탭 닫을 때까지 로그인 유지, 닫으면 자격증명 완전 삭제 |
| 로그인 보안 | 로그인 실패 5회 시 5분간 잠금 (브라우저 세션 기준) |
| 데이터 출력 | 통합 4컬럼 결과표 표시 + 복사 버튼 2개(① id/code/title 3컬럼, ② 개봉일 1컬럼 — 모두 헤더 없이 데이터만) + 엑셀 파일 다운로드(4컬럼 통합) |
| KOBIS API 키 | 발급 완료. Streamlit Cloud Secrets로 보관, 코드/저장소에 포함 안 함 |

---

## 3. 시스템 구조

```
[사용자 (어디서든, 브라우저)]
        │  https://<앱이름>.streamlit.app
        ▼
[Streamlit Community Cloud]
   └ Streamlit 대시보드 앱 (24/7 호스팅)
        ├─ kobis.py   ──→  KOBIS Open API
        ├─ admin.py   ──→  admin.kubecha.com (Playwright, headless Chromium)
        └─ excel.py        엑셀 생성 + TSV 클립보드 텍스트 생성

       (KOBIS API 키는 Streamlit Cloud Secrets에 안전 보관)
```

### 3.1 배포 모델
- 코드를 **GitHub 저장소**에 보관 (private 또는 public)
- **Streamlit Community Cloud**가 GitHub 저장소를 감시하다가 코드 변경 시 자동 재배포
- 사용자는 `https://<앱이름>.streamlit.app` URL로 어디서든 접속
- 본인 Mac을 켜둘 필요 없음 — Streamlit Cloud가 항상 띄워둠

### 3.2 구성 요소
- **app.py**: Streamlit 메인. 로그인 화면, 입력 화면, 결과 화면 등 UI 전체 담당.
- **kobis.py**: KOBIS Open API 호출 (영화 검색 + 개봉일 추출). `requests` 라이브러리 사용.
- **admin.py**: 사내 admin 자동화. Playwright로 헤드리스 크롬을 띄워 로그인 + 검색 + id/code 추출.
- **excel.py**: 매칭 결과를 받아 `.xlsx` 파일과 TSV(탭 구분 텍스트) 둘 다 생성.
- **auth.py**: 로그인 시도 횟수 추적 및 잠금 처리.
- **.streamlit/config.toml**: 테마(색/폰트) 설정.
- **.streamlit/secrets.toml** (로컬 개발용, GitHub에는 안 올림): KOBIS API 키 보관. **배포 환경에서는 Streamlit Cloud의 Secrets 관리 화면에서 입력.**
- **packages.txt**: Streamlit Cloud에 알리는 시스템 패키지 목록(Playwright의 Chromium 의존성 설치용).
- **requirements.txt**: Python 패키지 목록.
- **.gitignore**: `secrets.toml`, `.env`, `app.log` 등 민감 파일 제외.

### 3.3 기술 스택
- 언어: Python 3.10+
- UI: Streamlit
- HTTP 클라이언트: `requests`
- 브라우저 자동화: `playwright` (Chromium, headless)
- 엑셀: `openpyxl`
- 비밀 정보 관리: Streamlit Secrets (`st.secrets`)

### 3.4 분리 원칙
KOBIS 모듈, admin 모듈, 엑셀 모듈, UI는 각각 독립된 파일로 분리하여 한 곳이 깨져도 다른 곳에 영향이 없도록 한다. admin 사이트 개편 시 `admin.py`만 수정하면 된다.

---

## 4. 사용자 화면 흐름

### 4.1 로그인 화면
- ID, 비밀번호(마스킹) 입력 필드 + 로그인 버튼
- 성공 시 메인 대시보드 이동, 실패 시 에러 메시지
- 세션 상태(`st.session_state`)로 admin 자격증명 보관 (브라우저 탭 종료 시 자동 소멸)
- **로그인 시도 횟수 제한**: 같은 브라우저 세션에서 5회 연속 실패 시 5분간 잠금 (남은 잠금 시간 표시)
- **5회 잠금 후에도 계속 시도하는 경우**: 잠금 해제까지 카운트다운만 표시

### 4.2 작품 리스트 입력 화면
- 텍스트 영역에 한 줄 한 작품씩 붙여넣기 또는
- 엑셀 파일 업로드 (첫 컬럼이 작품명)
- "매칭 시작" 버튼

### 4.3 매칭 진행 화면
- 진행률 막대 + 현재 처리 중인 작품명 + KOBIS/admin 단계 표시

### 4.4 결과 화면
다음 세 영역을 동시에 표시:
- **자동 매칭 성공** — id/code/title/개봉일 4컬럼 표
- **동명이작 선택 필요** — 검색어별로 KOBIS 후보(개봉연도, 감독, 장르 포함)를 라디오 버튼으로 보여주고 사용자가 선택
- **매칭 실패** — 작품명 + 실패 사유 목록

### 4.5 결과 출력 (통합 표 + 분리된 두 복사 버튼 + 엑셀 다운로드)

결과는 **하나의 통합 4컬럼 표**로 표시한다. 사용자가 title과 개봉일의 행 정렬을 한눈에 검증할 수 있어야 하기 때문이다. 클립보드 복사 기능만 두 개의 별도 버튼으로 분리한다.

- **통합 결과표 표시**
  - 컬럼 순서: id, code, title, 개봉일 (4컬럼)
  - 매칭 성공 작품만 이 표에 포함 (동명이작 선택 대기, 매칭 실패는 별도 영역에 표시)
- **버튼 1. "id/code/title 복사" (3컬럼)**
  - 클립보드 형식: 탭 구분(`id\tcode\ttitle\n`), 헤더 없음
  - 위 통합 표의 앞 3컬럼만 복사
- **버튼 2. "개봉일만 복사" (1컬럼)**
  - 클립보드 형식: 단순 줄바꿈 구분(`개봉일\n`), 헤더 없음
  - 위 통합 표의 4번째 컬럼만 복사
- **엑셀 파일 다운로드**
  - `편성_매칭결과_YYYY-MM-DD_HH-MM.xlsx` 파일. id, code, title, 개봉일 4컬럼 통합본. 백업용 또는 파일로 전달이 필요할 때 사용.

두 복사 버튼이 같은 결과표에서 파생되므로 행 순서는 자동으로 일치한다.

---

## 5. 데이터 가져오기 로직

### 5.1 KOBIS Open API

- **사용 API**: `searchMovieList` (영화 목록 검색)
- **응답 처리**:
  - 0건: 매칭 실패 처리
  - 1건: 자동 매칭
  - 2건 이상: 사용자 선택 대기

- **검색 전처리** (정확도 향상):
  - 양 끝 공백 제거
  - 콜론(`:`), 마침표(`.`) 등 특수문자 제거
  - 연속 공백 1칸으로 압축
  - 결과 0건이면 공백 제거 버전으로 1회 재시도

- **재시도 정책**: 네트워크 오류 시 3회 (1초, 2초, 4초 간격)

### 5.2 admin 자동화 (Playwright)

- 도구 실행 시 헤드리스 Chromium 1개 띄움 (사용자에게 보이지 않음)
- 사용자 입력 ID/PW로 admin 로그인
- 로그인된 브라우저 세션을 메모리에 유지
- 각 작품마다 admin 검색창에 작품명 입력 → 결과 페이지 로딩 대기 → id, code 추출

- **admin 동명이작 매칭**:
  - KOBIS에서 결정된 작품의 개봉연도 + 한글 제목으로 admin 결과와 비교
  - 일치하는 행 자동 선택
  - 모호하면 화면 4의 동명이작 선택 영역에 함께 표시

- **타임아웃**: 작품당 admin 응답 최대 10초

### 5.3 결과 합치기
- title은 KOBIS 공식 제목으로 표준화 (사용자 입력 원본 대체)
- 최종 형식: `{ id, code, title (KOBIS 기준), 개봉일 (KOBIS 기준) }`

### 5.4 사전 확인 필요
admin.kubecha.com의 실제 페이지 구조(로그인 폼 위치, 검색창 위치, 결과 페이지에서 id/code 표시 위치)를 모르므로, 구현 시작 시점에 사용자가 화면을 시연하거나 캡처를 제공해야 한다.

---

## 6. 에러 / 예외 처리

### 6.1 핵심 원칙
**부분 실패 허용**: 일부 작품에 문제 발생해도 나머지 작품 처리는 멈추지 않는다.

처리 결과 요약을 항상 표시:
- ✅ 매칭 성공
- ⚠️ 사용자 선택 필요(동명이작)
- ❌ 매칭 실패

### 6.2 단계별 대응

| 단계 | 상황 | 대응 |
|---|---|---|
| 입력 | 빈 리스트 | "1개 이상 입력" 안내 |
| 입력 | 중복 | 자동 제거 + 알림 |
| 입력 | 100개 초과 | "최대 100개" 안내 |
| KOBIS | 네트워크 오류 | 3회 재시도 |
| KOBIS | API 키 한도 초과 | 명확한 경고 |
| KOBIS | 결과 0건 | 해당 작품만 실패 처리 |
| admin | 로그인 실패 | 실패 카운트 +1, 로그인 화면 유지 + "ID/PW 확인" 안내 |
| admin | 로그인 5회 연속 실패 | 5분간 잠금 + 남은 시간 카운트다운 표시 |
| admin | 검색 결과 없음 | 해당 작품만 실패 처리 (id/code 빈칸) |
| admin | Playwright 멈춤 | 자동 재시작 후 재개 |
| 출력 | 클립보드 복사 실패 | 표를 텍스트로 노출하여 수동 선택-복사 안내 |

### 6.3 로그
- 로컬 개발 환경: `app.log` 파일 자동 생성
- 배포 환경(Streamlit Cloud): 표준 출력(stdout/stderr)으로 출력 → Streamlit Cloud 관리 화면에서 조회
- 각 작품의 KOBIS/admin 호출 결과와 에러 원인 기록
- **비밀번호 등 민감 정보는 절대 기록하지 않음**

---

## 7. 보안

### 7.1 자격증명 처리
- 사용자 admin ID/PW는 디스크에 저장하지 않음 (Streamlit `st.session_state` 메모리만 사용)
- 비밀번호 입력 필드는 마스킹 처리
- 브라우저 탭 종료 또는 세션 만료 시 메모리 자동 정리되어 자격증명 사라짐

### 7.2 KOBIS API 키
- **GitHub 저장소에는 절대 포함하지 않음**
- 배포 환경: Streamlit Cloud의 Secrets 관리 화면에 `KOBIS_API_KEY` 등록
- 로컬 개발: `.streamlit/secrets.toml`에 보관, `.gitignore`로 차단
- 코드에서는 `st.secrets["KOBIS_API_KEY"]`로 접근
- 데모/배포 후 가능하면 KOBIS에서 새 키 발급받고 기존 키 폐기 권장

### 7.3 무차별 대입 공격 방어
- 같은 브라우저 세션에서 admin 로그인 5회 연속 실패 시 5분간 잠금
- 잠금 해제 후 카운터 리셋

### 7.4 공개 URL 노출 고려사항
- 앱 URL을 아는 누구나 로그인 화면까지 접근 가능 (의도된 동작)
- 실제 기능 접근은 admin ID/PW가 있는 사람만 가능
- 데모 후 URL 공유 범위를 본인이 직접 관리

### 7.5 로깅
- 각 요청의 KOBIS/admin 호출 결과를 Streamlit Cloud의 표준 로그에 출력 (관리 화면에서 조회)
- **비밀번호, KOBIS 키, 사용자 ID 등 민감 정보는 절대 로그에 남기지 않음**

---

## 8. 개발 및 배포 절차

### 8.1 로컬 개발 환경 (작업 중인 본인 Mac)
1. Python 3.10 이상 설치 확인 (`python3 --version`)
2. 의존성 설치:
   ```bash
   cd /Users/gim-yun-yeong/project1
   pip install -r requirements.txt
   playwright install chromium
   ```
3. `.streamlit/secrets.toml` 파일 생성 (Git 제외 대상):
   ```toml
   KOBIS_API_KEY = "<발급받은 키>"
   ```
4. 로컬 실행으로 개발/테스트:
   ```bash
   streamlit run app.py
   ```
   → 브라우저에 `http://localhost:8501` 자동 열림

### 8.2 GitHub 저장소 셋업
1. GitHub에 새 저장소 생성 (예: `pyeonseong-dashboard`)
   - **Private 권장** (코드 공개 불필요, 다만 KOBIS 키는 어차피 Secrets로 분리하므로 Public도 가능)
2. 로컬 코드를 저장소에 푸시:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin git@github.com:<username>/pyeonseong-dashboard.git
   git push -u origin main
   ```
3. `.gitignore`에 다음이 포함됨 (KOBIS 키 노출 방지):
   ```
   .streamlit/secrets.toml
   .env
   __pycache__/
   *.pyc
   app.log
   ```

### 8.3 Streamlit Community Cloud 배포 (최초 1회)
1. https://streamlit.io/cloud 접속 → GitHub 계정으로 가입/로그인
2. "New app" → 위에서 만든 저장소 선택
3. Main file path: `app.py`
4. Python version: 3.10 (또는 그 이상)
5. **Secrets 설정** (배포 화면 우측 "Advanced settings" → "Secrets"):
   ```toml
   KOBIS_API_KEY = "<발급받은 키>"
   ```
6. Deploy 클릭 → 몇 분 후 `https://<앱이름>.streamlit.app` URL 생성됨

### 8.4 이후 업데이트 흐름
- 로컬에서 코드 수정 → `git push` → Streamlit Cloud가 자동 감지하여 재배포 (수동 작업 없음)
- 의존성 변경 시 `requirements.txt` 업데이트

### 8.5 매일 사용 (배포 후)
- 본인이든 팀원이든 `https://<앱이름>.streamlit.app` 접속
- admin ID/PW 입력 → 사용
- 본인 Mac을 켜둘 필요 없음

### 8.6 폴더 구조
```
/Users/gim-yun-yeong/project1/
├── app.py
├── kobis.py
├── admin.py
├── excel.py
├── auth.py                       # 로그인 시도 카운터/잠금
├── .gitignore
├── .streamlit/
│   ├── config.toml               # 테마
│   └── secrets.toml              # 로컬 개발용 KOBIS 키 (Git 제외)
├── requirements.txt
├── packages.txt                  # Playwright 의존 OS 패키지
├── README.md                     # 저장소 설명, 배포 가이드
└── docs/superpowers/specs/       # 설계 문서
```

---

## 9. 테스트 시나리오 (데모 직전)

### 9.1 테스트 데이터 (사전 준비)
```
어벤져스: 엔드게임      ← 정상 케이스 (KOBIS 1건 + admin 있음)
인사이드 아웃 2        ← 최근 영화
듄: 파트2             ← 콜론 포함 (전처리 검증)
알라딘                ← 동명이작 (선택 화면 검증)
이상한작품명없음      ← 실패 케이스
```

### 9.2 검증 흐름
1. 잘못된 비밀번호 → 에러 메시지 확인
2. **5회 연속 실패 → 5분 잠금 메시지 + 카운트다운 표시** (로그인 시도 제한 검증)
3. 올바른 비밀번호 → 메인 진입
4. 5개 작품 입력 → 매칭 실행
5. 진행률 표시 확인
6. 결과 화면에서 자동 매칭 / 동명이작 선택 / 실패 모두 확인
7. **영역 1 복사 (id/code/title) → 엑셀에 붙여넣기 → 3컬럼 정렬 확인**
8. **영역 2 복사 (개봉일) → 엑셀의 다른 컬럼에 붙여넣기 → 행 순서가 영역 1과 동일한지 확인**
9. 엑셀 파일 다운로드 → 열어서 4컬럼 데이터 확인
10. **로컬과 배포 환경 둘 다에서 동일하게 동작 확인**

### 9.3 데모 자리 원칙
미리 검증된 안전한 작품 리스트만 사용. 모르는 작품을 즉석에서 입력하지 않는다.

---

## 10. 구현 단계와 위험요소

### 10.1 구현 순서 (논리적 의존성 기준)
시간 제약은 없으므로 단계별로 충실히 구현. 각 단계 끝에 동작 확인 후 다음 단계로 진행.

1. **프로젝트 셋업** — 폴더 구조 생성, `requirements.txt`, `.gitignore`, 로컬 환경 검증
2. **KOBIS 모듈 (`kobis.py`)** — API 호출 + 검색 전처리 + 재시도 + 단위 테스트
3. **엑셀/클립보드 모듈 (`excel.py`)** — TSV 생성, `.xlsx` 생성 (KOBIS와 admin 모듈에 의존 없음, 일찍 검증 가능)
4. **admin 자동화 모듈 (`admin.py`)** — Playwright 로그인 + 검색 + 추출 (admin 페이지 구조 파악 필요)
5. **인증 모듈 (`auth.py`)** — 로그인 시도 카운터, 잠금 처리
6. **Streamlit UI (`app.py`)** — 로그인 화면 → 입력 → 진행 → 결과 화면 연결
7. **테마/CSS 적용** — `.streamlit/config.toml` + CSS 주입
8. **로컬에서 통합 테스트** — 9번 섹션 검증 시나리오 수행
9. **GitHub 저장소 셋업 + 푸시**
10. **Streamlit Community Cloud 배포** — Secrets 설정 포함
11. **배포 환경에서 최종 검증** — 로컬과 동일 시나리오 수행
12. **README 작성** — 사용법, 배포 절차, 트러블슈팅

### 10.2 위험요소와 완화책

| 위험 | 영향 | 완화책 |
|---|---|---|
| admin 페이지 구조 파악 실패 | 자동화 자체 불가 | 구현 시작 시 사용자가 화면 시연 또는 캡처 제공. 셀렉터(요소 위치) 정확히 파악. 변경 가능성 대비해 admin.py를 깔끔히 분리 |
| Streamlit Cloud에서 Playwright 실행 실패 | 클라우드 배포 불가 | `packages.txt`에 Chromium 의존 OS 패키지 명시. 메모리 한도(1GB) 고려해 한 사용자 세션 내에서 작품을 순차(직렬) 처리. 실패 시 Fly.io 등 대안 환경 검토 |
| admin 사이트가 봇 트래픽 차단 | 자동화 차단 | User-Agent 정상화, 적절한 대기 시간, 너무 빈번한 요청 자제 |
| 같은 URL을 여러 사람이 동시 사용 시 자원 경합 | 응답 지연 | Streamlit 세션 분리로 사용자별 독립 상태 유지. 동시 사용자 적은 환경이라 큰 문제 아님 |
| KOBIS API 키 노출 | 한도 소진 | Streamlit Secrets 사용, GitHub 푸시 전 `.gitignore` 확인. 데모 후 키 회전 |

### 10.3 예상 작업 시간 (참고용, 강제 아님)
- 셋업 + KOBIS: 1~2시간
- 엑셀/TSV: 30분
- admin (Playwright): 2~4시간 (사이트 구조에 따라 변동 큼)
- auth + Streamlit UI: 2~3시간
- 테마/CSS: 1시간
- GitHub + Streamlit Cloud 배포: 1시간
- 통합 테스트 + 디버깅: 1~2시간

→ 합계 **하루~이틀 정도**의 집중 작업으로 안정적인 결과물 가능

---

## 11. 데모 후 운영

### 11.1 일상 사용 흐름
편성 요청 수신 → 브라우저로 `https://<앱이름>.streamlit.app` 접속 → admin 로그인 → 작품 리스트 입력 → 결과 검토 → 클립보드 복사 → 사내 엑셀 양식에 붙여넣기

### 11.2 향후 확장 후보 (별도 일정)
- 매칭 이력 저장 (다음에 같은 작품 입력 시 재사용)
- 작품 추가 정보(장르, 등급) 컬럼 추가
- 동명이작 선택 화면에 포스터 이미지 표시
- 사내 SSO 연동 (KubeCha 계정으로 로그인)
- 커스텀 도메인 연결 (`*.streamlit.app` 대신 회사 도메인 사용)

### 11.3 유지보수
- admin 사이트 개편 시 `admin.py`만 수정
- KOBIS API 응답 형식 변경 시 `kobis.py`만 수정
- 화면 디자인 변경 시 `app.py` 및 `.streamlit/config.toml`만 수정

---

## 12. 미해결 항목 / 후속 결정 필요

- **admin 페이지 구조 파악**: 구현 시작 시 사용자 시연 또는 캡처 제공 필요. 다음을 확인해야 함:
  - 로그인 페이지의 ID/PW 입력 필드와 로그인 버튼의 HTML 구조
  - `admin.kubecha.com/brew/galaxy/movies` 페이지에서 검색 동작 방식 (검색창, 결과 표시 위치)
  - 검색 결과에서 id와 code가 어떻게 표시되는지 (테이블 컬럼? 상세 페이지? URL?)
- **GitHub 저장소명 결정**: 예: `pyeonseong-dashboard` (사용자 결정 필요)
- **Streamlit Cloud 앱명 결정**: URL의 서브도메인이 됨 (예: `pyeonseong.streamlit.app`)
- **데모 대상과 일정**: 명시되지 않음. 데모 자리에서 강조할 포인트를 데모 대상에 맞춰 후속 조정.
- **데모 후 KOBIS API 키 회전**: 대화 중 노출된 키는 가능하면 새 키로 교체
