from datetime import datetime, timezone
from zoneinfo import ZoneInfo

LOCAL_TIMEZONE = ZoneInfo("America/Sao_Paulo")


def format_local_datetime(value: datetime | None, pattern: str = "%d/%m/%Y %H:%M") -> str:
    if value is None:
        return "—"
    source = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return source.astimezone(LOCAL_TIMEZONE).strftime(pattern)
