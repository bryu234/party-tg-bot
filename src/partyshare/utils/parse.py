from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def parse_event_datetime(value: str, default_tz: ZoneInfo) -> datetime:
    parts = value.strip().split()
    if len(parts) < 2:
        raise ValueError("Ожидается формат 'YYYY-MM-DD HH:MM [TZ]'")

    date_part, time_part = parts[0], parts[1]
    tz_name = parts[2] if len(parts) > 2 else default_tz.key

    try:
        tz = ZoneInfo(tz_name)
    except Exception as exc:
        raise ValueError("Неизвестная таймзона") from exc

    naive = datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H:%M")
    aware = naive.replace(tzinfo=tz)
    return aware.astimezone(ZoneInfo("UTC"))
 
