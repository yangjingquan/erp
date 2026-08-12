from datetime import date, datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

from app.core.config import get_settings


@lru_cache
def app_timezone() -> ZoneInfo:
    return ZoneInfo(get_settings().app_timezone)


def local_now_aware() -> datetime:
    """Return the current ERP time with the configured timezone attached."""
    return datetime.now(app_timezone())


def local_now() -> datetime:
    """Return local ERP wall-clock time for MySQL DATETIME columns."""
    return local_now_aware().replace(tzinfo=None)


def local_today() -> date:
    return local_now_aware().date()


def to_local_naive(value: datetime) -> datetime:
    """Normalize API datetime input to the ERP wall-clock convention."""
    if value.tzinfo is None:
        return value
    return value.astimezone(app_timezone()).replace(tzinfo=None)
