# -*- coding: utf-8 -*-
"""
네이버 뉴스 검색 결과를 Selenium으로 수집하여 JSON 파일로 저장하는 스크립트.
- 지정 키워드(임원인사, 선임, 내정, 교체, 영입, 사임, 용퇴, 체제, 개편)별로 검색
- 스크롤 5회 반복 후 기사 목록 수집, 링크 기준 중복 제거
- 기사별 제목, 내용(요약), 링크를 JSON으로 저장
"""

import json
import time
from pathlib import Path
from urllib.parse import quote

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options


BASE_URL = "https://search.naver.com/search.naver?ssc=tab.news.all&where=news&sm=tab_jum&query={query}"

# 크롤링할 키워드 (OR 조건: 이 중 하나라도 포함된 뉴스 수집)
KEYWORDS = [
    "임원인사",
    "선임",
    "내정",
    "교체",
    "영입",
    "사임",
    "용퇴",
    "체제",
    "개편",
]

# 한 개 기사 요소 분석 기준 셀렉터 (동적 ID 대신 고정 클래스/속성 사용)
TITLE_LINK_SELECTOR = 'a[data-heatmap-target=".tit"]'
BODY_LINK_SELECTOR = 'a[data-heatmap-target=".body"]'

OUTPUT_JSON = Path(__file__).resolve().parent / "naver_news_키워드통합.json"


def scroll_and_wait(driver, times=5, wait_sec=0.5):
    """화면 맨 아래로 스크롤한 뒤 대기하는 과정을 times번 반복."""
    for _ in range(times):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(wait_sec)


def collect_news(driver):
    """
    뉴스 검색 결과에서 제목, 내용(요약), 링크를 수집.
    한 개 기사 요소: .tit 링크(제목+url), .body 링크(요약문) 셀렉터 사용.
    """
    wait = WebDriverWait(driver, 15)

    # 뉴스 기사가 로드될 때까지 대기 (제목 링크 기준)
    wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, TITLE_LINK_SELECTOR)))

    title_links = driver.find_elements(By.CSS_SELECTOR, TITLE_LINK_SELECTOR)
    body_links = driver.find_elements(By.CSS_SELECTOR, BODY_LINK_SELECTOR)

    # 제목/링크와 본문요약이 1:1 대응된다고 가정 (같은 개수만 사용)
    n = min(len(title_links), len(body_links))
    articles = []

    for i in range(n):
        try:
            title_el = title_links[i]
            body_el = body_links[i]
            title = (title_el.text or "").strip()
            link = (title_el.get_attribute("href") or "").strip()
            content = (body_el.text or "").strip()
            if title or link or content:
                articles.append({
                    "title": title,
                    "content": content,
                    "link": link,
                })
        except Exception as e:
            print(f"기사 {i} 수집 중 오류: {e}")
            continue

    return articles


def get_search_url(keyword):
    """키워드로 네이버 뉴스 검색 URL 생성."""
    return BASE_URL.format(query=quote(keyword))


def main():
    options = Options()
    # options.add_argument("--headless")  # 브라우저 창 없이 실행 시 주석 해제
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    # 링크 기준 중복 제거용 (link -> article)
    seen_links = {}
    all_articles = []

    driver = webdriver.Chrome(options=options)
    try:
        for keyword in KEYWORDS:
            url = get_search_url(keyword)
            print(f"검색 중: {keyword} -> {url}")
            driver.get(url)
            time.sleep(2)

            # 스크롤 5번: 맨 아래로 스크롤 → 0.5초 대기
            scroll_and_wait(driver, times=5, wait_sec=0.5)

            articles = collect_news(driver)
            added = 0
            for a in articles:
                link = (a.get("link") or "").strip()
                if link and link not in seen_links:
                    seen_links[link] = a
                    a_with_keyword = {**a, "matched_keyword": keyword}
                    all_articles.append(a_with_keyword)
                    added += 1
            print(f"  -> {len(articles)}건 수집, 신규 {added}건 추가 (누적 {len(all_articles)}건)")

        result = {
            "keywords": KEYWORDS,
            "count": len(all_articles),
            "articles": all_articles,
        }

        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"저장 완료: {OUTPUT_JSON} (키워드 {len(KEYWORDS)}개, 기사 {len(all_articles)}건)")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
