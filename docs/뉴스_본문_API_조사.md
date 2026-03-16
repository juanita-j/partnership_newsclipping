# 뉴스 기사 본문(전문) 확보 방법 조사

## 1. 네이버 공식 API

- **검색 API (뉴스)**: [네이버 개발자센터 - 뉴스 검색](https://developers.naver.com/docs/serviceapi/search/news/news.md)
- **제공 항목**: 제목(`title`), 링크(`link`), 요약(`description`), 발행일(`pubDate`) 등
- **본문**: **제공하지 않음**. 기사 전문(본문)은 API로 받을 수 없습니다.

## 2. 본문 확보 방법

### (1) 직접 크롤링

- 각 기사 **URL**을 HTTP로 요청한 뒤 HTML에서 본문 영역을 파싱합니다.
- **네이버/언론사별 본문 셀렉터 예시** (카테고리·구도에 따라 다를 수 있음):
  - 일반: `#articleBodyContents`, `#newsct_article`, `#dic_area`
  - 연예: `#articeBody`
  - 스포츠: `#newsEndContents`
- 검색 결과 링크는 실제 기사 페이지로 **리다이렉트**될 수 있으므로, 최종 URL 기준으로 셀렉터를 선택해야 합니다.
- `robots.txt` 및 이용약관을 확인한 뒤, 필요 시 지연 시간·요청량 조절 등으로 수집 강도를 조절하는 것이 좋습니다.

### (2) URL → 본문 텍스트 API (Jina Reader)

- **방식**: `https://r.jina.ai/{기사URL}` 로 GET 요청 시, 해당 URL 페이지의 본문을 정제된 형태(마크다운/텍스트)로 반환합니다.
- **특징**:
  - 별도 API 키 없이 호출 가능 (무료 사용 시 제한 있을 수 있음).
  - 언론사·페이지 구조에 상관없이 동일한 방식으로 사용 가능해, 리다이렉트된 외부 언론사 URL도 처리하기 쉽습니다.
- **문서**: [jina-ai/reader](https://github.com/jina-ai/reader)

## 3. 본 프로젝트 반영 사항

- **`article_body_fetcher.py`**
  - 위 (1) 직접 크롤링(네이버·일반 셀렉터)과 (2) Jina Reader를 모두 사용할 수 있도록 구현했습니다.
  - 기본: 먼저 직접 크롤링 시도 → 실패 또는 본문이 비어 있으면 Jina Reader로 재시도.
  - 환경 변수:
    - `FETCH_ARTICLE_BODY=1`: 기사 본문 수집 수행.
    - `USE_JINA_READER=1`: 크롤링 없이 Jina Reader만 사용.

- **`send_exec_news_timed.py`**
  - 수집된 기사 리스트에 대해 `fetch_bodies_for_articles()`를 호출해 각 기사에 `body` 필드를 채웁니다.
  - 요약·[간결한 버전]/[추가 내용] 생성 시, `body`가 있으면 본문을 우선 사용하고 없으면 기존처럼 제목·요약만 사용합니다.

## 4. 정리

| 방법 | 본문 제공 여부 | 비고 |
|------|----------------|------|
| 네이버 검색 API | ❌ | 제목·링크·요약·날짜만 제공 |
| 직접 크롤링 | ✅ | URL 요청 후 HTML 파싱 필요, 셀렉터 유지보수 |
| Jina Reader (r.jina.ai) | ✅ | API 키 없이 URL만으로 본문 추출 가능 |

뉴스 정확도를 위해 **기사 전문을 반드시 확인**하려면, 위와 같이 **직접 크롤링** 또는 **Jina Reader 같은 URL→본문 API**를 사용해야 합니다. 본 프로젝트는 두 방식 모두 사용할 수 있도록 구현되어 있습니다.
