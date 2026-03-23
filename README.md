# 파트너사 뉴스 클리핑

특정 파트너사의 주요 뉴스 요약본을 메일로 받는 배치 프로젝트입니다.

## 구조

- **config/** – 파트너사 목록(`partners.yaml`), 키워드(`keywords.yaml`), 발송 설정(`sender.yaml`)
- **collectors/** – 네이버 뉴스 API, Google News RSS 수집
- **filters/** – 키워드 필터(주요 뉴스만), 블로그 제외, URL 중복 제거 (글로벌 빅테크·AI는 `keywords.yaml`의 `ai_bigtech` 및 `partners.yaml` 별칭으로 누락 완화)
- **summarizers/** – LLM 기반 3~7줄 요약(OpenAI/Anthropic, 설정은 `config/summarizer.yaml`), 실패 시 규칙 기반 폴백
- **compose/** – 회사별 HTML 메일 본문 생성
- **sender/** – SMTP 메일 발송
- **storage/** – 직전 발송 시각 저장/조회
- **run_batch.py** – 수집 → 필터 → 요약 → 메일 생성 → 발송 오케스트레이션

## 실행

```bash
pip install -r requirements.txt
python run_batch.py           # 실제 발송 (요약은 LLM 사용)
python run_batch.py --dry-run # 수집·필터·요약만, 발송 생략
python run_batch.py --no-llm # LLM 없이 규칙 기반 요약만 사용
```

## 환경변수 / GitHub Secrets

- **네이버**: `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` ([네이버 개발자센터](https://developers.naver.com) 검색 API)
- **요약(LLM)**: `OPENAI_API_KEY` 또는 `ANTHROPIC_API_KEY` (설정: `config/summarizer.yaml`, provider: openai | anthropic)
- **메일**: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SENDER_FROM`, `SENDER_TO`
  - Gmail 사용 시: `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USER`·`SENDER_FROM`은 발신 Gmail 주소와 동일하게.
  - **앱 비밀번호**는 코드/저장소에 넣지 말고 아래에 등록합니다.

### Gmail 앱 비밀번호 등록 위치

| 실행 환경 | 등록 방법 |
|-----------|-----------|
| **로컬 (PowerShell 등)** | `SMTP_PASSWORD` 환경변수에 16자리 앱 비밀번호 설정. 예: `$env:SMTP_PASSWORD="xxxx xxxx xxxx xxxx"` (세션 한정) 또는 시스템 환경 변수에 영구 등록. `SMTP_USER`도 `naverpartnership@gmail.com`으로 맞출 것. |
| **GitHub Actions** | 저장소 **Settings → Secrets and variables → Actions → New repository secret** 에서 `SMTP_PASSWORD` 시크릿 생성 후 값에 앱 비밀번호 입력. 필요 시 `SMTP_USER`, `SENDER_FROM`도 같은 Gmail 주소로 시크릿 추가. |

Google 계정에서 [보안](https://myaccount.google.com/security) → 2단계 인증 사용 후 **앱 비밀번호**를 생성하면 됩니다.

## 스케줄

- **GitHub Actions**: 매주 **월·수·금 15:00 KST** (`.github/workflows/news-clipping.yml`의 `cron`, UTC `06:00`).
- **수집 범위**: 직전 **메일 발송 성공 시각** 이후에 발표된 기사만 대상 (`storage/last_send.py`).  
  - **Actions**에서는 `data/last_send_at.txt`를 **워크플로 캐시**로 넘겨 위 시각이 유지되도록 함.  
  - 최초 실행·캐시 없음 시에는 최근 **7일**로 폴백.
- GitHub 예약 실행은 **수 분~최대 약 1시간** 지연될 수 있음(플랫폼 특성).

### 외부 작업 스케줄러를 쓰는 경우

GitHub만 쓰면 **별도 스케줄러 등록은 필요 없음**.  
다음 경우에만 직접 등록:

- **Windows 작업 스케줄러 / cron / 클라우드 스케줄러** 등에서 돌리려면: 해당 환경에서 `python run_batch.py` 실행(또는 `workflow_dispatch`를 `gh workflow run` + PAT으로 트리거).
- **정확히 15:00:00에 실행**이 필수면: GitHub cron 대신 외부 스케줄러로 `workflow_dispatch` API 호출을 권장.
