"""
메일 발송: SMTP 또는 환경변수 기반.
발송 성공 시 storage.last_send에 기록하는 것은 run_batch에서 수행.
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def load_sender_config() -> dict:
    try:
        import yaml
        cfg = CONFIG_DIR / "sender.yaml"
        if cfg.exists():
            with open(cfg, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    except Exception:
        pass
    return {}


def send_mail(
    to: str | list[str],
    subject: str,
    body_html: str,
    from_addr: str | None = None,
) -> bool:
    """
    HTML 메일 발송.
    to: 수신자 이메일 또는 리스트
    환경변수: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SENDER_FROM, SENDER_TO
    """
    cfg = load_sender_config()
    smtp_cfg = cfg.get("smtp") or {}
    host = os.environ.get("SMTP_HOST") or smtp_cfg.get("host")
    port = int(os.environ.get("SMTP_PORT", smtp_cfg.get("port", 587)))
    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    from_addr = (
        from_addr
        or os.environ.get("SENDER_FROM")
        or (cfg.get("from") or "").strip()
        or user
    )
    if isinstance(to, str):
        to = [to]
    to_list = to or os.environ.get("SENDER_TO", "").split(",")
    to_list = [t.strip() for t in to_list if t.strip()]
    if not to_list:
        print("[send] 실패: 수신자(SENDER_TO) 미설정. GitHub Secrets에 SENDER_TO를 등록하세요.")
        return False
    if not host:
        print("[send] 실패: SMTP 호스트(SMTP_HOST) 미설정.")
        return False
    if not user:
        print("[send] 실패: SMTP 계정(SMTP_USER) 미설정.")
        return False
    if not password:
        print("[send] 실패: SMTP 비밀번호(SMTP_PASSWORD) 미설정. Gmail 앱 비밀번호를 Secrets에 등록하세요.")
        return False

    print(f"[send] 발송 시도: from={from_addr}, to={to_list}, host={host}:{port}")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_list)
    part = MIMEText(body_html, "html", "utf-8")
    msg.attach(part)

    try:
        use_tls = smtp_cfg.get("use_tls", True)
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            if use_tls:
                smtp.starttls()
            if user and password:
                smtp.login(user, password)
            smtp.sendmail(from_addr, to_list, msg.as_string())
        print(f"[send] 발송 성공: {to_list}")
        return True
    except Exception as e:
        print(f"[send] 발송 실패 (SMTP 오류): {e}")
        return False
