from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo


# Русские месяцы
RUSSIAN_MONTHS = {
    "январ": 1, "феврал": 2, "март": 3, "апрел": 4,
    "ма": 5, "июн": 6, "июл": 7, "август": 8,
    "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12
}


def parse_russian_date(text: str) -> datetime:
    """
    Парсинг даты в русском формате. Всегда использует таймзону Europe/Moscow (+3).
    
    Поддерживаемые форматы:
    - 20 декабря 2025 19:00
    - 20.12.2025 19:00
    - 20-12-2025 19:00
    - 20/12/2025 19:00
    """
    text = text.strip().lower()
    tz = ZoneInfo("Europe/Moscow")
    
    # Формат: 20 декабря 2025 19:00
    for month_name, month_num in RUSSIAN_MONTHS.items():
        if month_name in text:
            # Ищем день, год и время
            match = re.search(r'(\d{1,2})\s+\w+\s+(\d{4})\s+(\d{1,2}):(\d{2})', text)
            if match:
                day = int(match.group(1))
                year = int(match.group(2))
                hour = int(match.group(3))
                minute = int(match.group(4))
                naive = datetime(year, month_num, day, hour, minute)
                aware = naive.replace(tzinfo=tz)
                return aware.astimezone(ZoneInfo("UTC"))
    
    # Формат: 20.12.2025 19:00 или 20-12-2025 19:00 или 20/12/2025 19:00
    match = re.search(r'(\d{1,2})[\.\-/](\d{1,2})[\.\-/](\d{4})\s+(\d{1,2}):(\d{2})', text)
    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3))
        hour = int(match.group(4))
        minute = int(match.group(5))
        naive = datetime(year, month, day, hour, minute)
        aware = naive.replace(tzinfo=tz)
        return aware.astimezone(ZoneInfo("UTC"))
    
    raise ValueError("Не удалось распознать дату")


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
 
