# 매일 오전 10시 임원인사 뉴스 메일

- **수신**: juan.jung@navercorp.com  
- **제목**: `x월 xx일 오전 10시 임원인사 현황`  
- **키워드**: 인사변동, 임원인사, 내정, 선임, 교체  
- **기사 수**: 10건  

---

## 1. 사전 준비

### 네이버 검색 API 키 발급

1. [네이버 개발자 센터](https://developers.naver.com/apps/#/register)에서 애플리케이션 등록  
2. **사용 API**에서 **검색** 선택  
3. **클라이언트 ID**와 **클라이언트 시크릿** 복사  

### 환경 변수 설정 (둘 중 하나)

**방법 A – .env 파일 (권장)**  

1. 이 폴더에 `.env` 파일 생성  
2. 아래 내용 입력 후 저장 (실제 값으로 교체):

```env
NAVER_CLIENT_ID=발급받은_클라이언트_ID
NAVER_CLIENT_SECRET=발급받은_클라이언트_시크릿
```

3. `.env` 로드용 패키지 설치:

```bash
pip install python-dotenv
```

**방법 B – 시스템 환경 변수**  

- Windows: `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` 사용자 또는 시스템 환경 변수로 설정  

### 패키지 설치

```bash
pip install -r requirements.txt
```

---

## 2. 매일 오전 10시 자동 실행 (Windows 작업 스케줄러)

1. **작업 스케줄러** 실행 (Win + R → `taskschd.msc`)  
2. **기본 작업 만들기**  
   - 이름: `임원인사 뉴스 메일`  
   - 트리거: **매일**, 오전 **10:00**  
   - 동작: **프로그램 시작**  
   - 프로그램: `python` (또는 `py`)  
   - 인수: `"C:\Users\USER\.cursor\daily-exec-news\send_daily_exec_news.py"`  
   - **시작 위치**: `C:\Users\USER\.cursor\daily-exec-news`  
3. **일반** 탭에서 “사용자 로그온 여부에 관계없이 실행” 선택 시,  
   **동작**의 “시작 위치”와 환경 변수가 작업 스케줄러 환경에서 적용되는지 확인합니다.  
   (로그온 시 실행으로 두면 현재 사용자 .env/환경 변수가 사용됩니다.)  

또는 **배치 파일**로 실행하도록 할 수 있습니다.

- 프로그램: `C:\Users\USER\.cursor\daily-exec-news\run_daily.bat`  
- 인수: (비움)  
- 시작 위치: `C:\Users\USER\.cursor\daily-exec-news`  

---

## 3. 메일 실제 발송 방법

스크립트는 매일 실행 시 **제목·본문을 `email_content.json`에 저장**합니다.  
실제로 메일을 보내는 방법은 두 가지입니다.

### 방법 A – Cursor에서 WORKS 메일로 보내기 (MCP)

1. 매일 10시에 스크립트가 실행되면 `email_content.json`이 갱신됩니다.  
2. Cursor를 연 뒤 채팅에서 아래처럼 요청합니다.  
   - **“오늘자 임원인사 뉴스 메일 보내줘”**  
   - 또는 **“`daily-exec-news/email_content.json` 내용으로 juan.jung@navercorp.com 에 WORKS 메일 보내줘”**  
3. Cursor가 `email_content.json`을 읽고 **naver-works** MCP의 **mail_send**로 발송합니다.  

즉, **수집은 매일 10시 자동**, **발송은 Cursor에서 한 번 요청**하는 흐름입니다.

### 방법 B – SMTP로 완전 자동 발송

회사 메일 SMTP 정보가 있다면 스크립트에서 바로 발송할 수 있습니다.

`.env` 또는 시스템 환경 변수에 추가:

```env
SMTP_HOST=smtp.회사도메인
SMTP_PORT=587
SMTP_USER=본인_메일주소
SMTP_PASSWORD=메일_비밀번호_또는_앱비밀번호
```

이렇게 설정하면 스크립트 실행 시 **수집 + SMTP 발송**까지 한 번에 수행됩니다.  
(매일 10시 작업만 등록하면 메일도 매일 10시에 자동 발송됩니다.)

---

## 4. 수동 실행

```bash
cd C:\Users\USER\.cursor\daily-exec-news
python send_daily_exec_news.py
```

또는 `run_daily.bat` 더블클릭.

---

## 파일 설명

| 파일 | 설명 |
|------|------|
| `send_daily_exec_news.py` | 뉴스 수집 + 메일 본문 생성(및 선택 시 SMTP 발송) |
| `email_content.json` | 생성된 제목·본문 (Cursor에서 mail_send 시 사용) |
| `run_daily.bat` | 작업 스케줄러용 실행 스크립트 |
| `.env` | API 키·SMTP 설정 (직접 생성, Git 제외 권장) |
