# 파트너사 뉴스 클리핑

특정 파트너사의 주요 뉴스 요약본을 메일로 받는 배치 프로젝트입니다.

## 구조

- **config/** – 파트너사 목록(`partners.yaml`), 키워드(`keywords.yaml`), 발송 설정(`sender.yaml`)
- **collectors/** – 네이버 뉴스 API, Google News RSS 수집
- **filters/** – 키워드 필터(주요 뉴스만), 블로그 제외, URL 중복 제거
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

## 스케줄

GitHub Actions: 매주 월/수/금 15:00 KST (` .github/workflows/news-clipping.yml`).  
직전 발송 이후 기사만 수집합니다.
