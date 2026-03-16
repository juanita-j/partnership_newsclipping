# -*- coding: utf-8 -*-
"""
email_content.json 을 읽어 Gmail로 발송.
GitHub Actions 등에서 send_daily_exec_news.py 실행 후 이 스크립트를 실행하면 됨.
환경 변수 GMAIL_APP_PASSWORD 필수. GMAIL_SENDER, GMAIL_TO 는 JSON 값으로 덮어쓸 수 있음.
"""

import json
import os
import smtplib
import ssl
import sys
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

OUTPUT_DIR = Path(__file__).resolve().parent
EMAIL_JSON = OUTPUT_DIR / "email_content.json"


def send_gmail_from_json(
    json_path: Path = EMAIL_JSON,
    password: str | None = None,
    sender: str | None = None,
):
    password = (password or os.environ.get("GMAIL_APP_PASSWORD") or "").replace(" ", "").strip()
    if not password:
        print("오류: GMAIL_APP_PASSWORD 환경 변수가 없습니다.")
        return 1

    if not json_path.exists():
        print(f"오류: {json_path} 파일이 없습니다. 먼저 send_daily_exec_news.py 를 실행하세요.")
        return 1

    with open(json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    to = payload.get("to", "").strip() or os.environ.get("GMAIL_TO", "juan.jung@navercorp.com")
    subject = payload.get("subject", "").strip()
    body = payload.get("body", "").strip()
    is_html = (payload.get("contentType") or "html").lower() == "html"

    sender = (sender or os.environ.get("GMAIL_SENDER", "wjdwndks99@gmail.com")).strip()

    if not subject or not body:
        print("오류: JSON에 subject 또는 body가 비어 있습니다.")
        return 1

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg.attach(MIMEText(body, "html" if is_html else "plain", "utf-8"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls(context=context)
            server.login(sender, password)
            server.sendmail(sender, to, msg.as_string())
        print(f"발송 완료: {to} / 제목: {subject}")
        return 0
    except Exception as e:
        print(f"Gmail 발송 실패: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(send_gmail_from_json())
