"""
직전 메일 발송 시각 저장/조회.
배치에서 '직전 발송 이후 기사만' 수집할 때 사용.

- 로컬: data/last_send_at.txt (gitignore). 발송 성공 시에만 갱신.
- GitHub Actions: 동일 파일을 워크플로 캐시(actions/cache)로 실행 간 유지해야
  매 실행마다 7일치로만 보지 않고 직전 발송 시각 이후만 수집할 수 있음.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta

# 프로젝트 루트 기준 data 디렉터리
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LAST_SEND_FILE = DATA_DIR / "last_send_at.txt"
# 기본 fallback: 첫 실행 시 사용할 수집 기간(일)
DEFAULT_DAYS_BACK = 7


def _ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def get_last_send_at() -> datetime | None:
    """직전 발송 시각(KST) 반환. 없으면 None."""
    if not LAST_SEND_FILE.exists():
        return None
    try:
        text = LAST_SEND_FILE.read_text(encoding="utf-8").strip()
        if not text:
            return None
        # ISO format 저장 가정
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (ValueError, OSError):
        return None


def get_since_for_collect() -> datetime:
    """
    수집 시작 시점 반환 (KST).
    last_send_at이 있으면 그 시각, 없으면 now - DEFAULT_DAYS_BACK.
    """
    last = get_last_send_at()
    if last is not None:
        return last
    # KST = UTC+9
    now = datetime.now(timezone(timedelta(hours=9)))
    return now - timedelta(days=DEFAULT_DAYS_BACK)


def set_last_send_at(dt: datetime | None = None) -> None:
    """발송 성공 시 직전 발송 시각 기록. dt 없으면 현재 시각(KST)."""
    _ensure_data_dir()
    if dt is None:
        dt = datetime.now(timezone(timedelta(hours=9)))
    LAST_SEND_FILE.write_text(dt.isoformat(), encoding="utf-8")
