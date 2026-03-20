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
        return False
    if not host:
        # 환경변수만으로는 발송 불가 시 False (실제 발송은 WORKS API 등으로 대체 가능)
        return False

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
        return True
    except Exception:
        return False
