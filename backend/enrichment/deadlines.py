"""Deterministic deadline normalization."""

import re
from datetime import date, datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}
WEEKDAY_PATTERN = "|".join(WEEKDAYS)


def normalize_deadline(
    deadline_value: Optional[str],
    reference_date: Optional[datetime] = None,
) -> Optional[str]:
    """Return a supported deadline as an ISO timestamp in IST.

    Relative values use ``reference_date``. When it is omitted (the upload
    fallback), the current timezone-aware IST time is used. A naive reference is
    interpreted as IST rather than being converted through the host timezone.

    Plain relative dates end at 23:59 IST. EOD is 18:00 IST, and EOW is Friday
    at 18:00 IST. Plain and ``this`` weekdays mean the next matching weekday,
    including today; ``next`` weekdays mean the matching day in the following
    week.
    """
    if not isinstance(deadline_value, str) or not deadline_value.strip():
        return None

    reference = _as_ist(reference_date)
    value = " ".join(deadline_value.strip().lower().split())

    if value == "today":
        return _at_time(reference.date(), hour=23, minute=59)
    if value == "tomorrow":
        return _at_time(reference.date() + timedelta(days=1), hour=23, minute=59)
    if value in {"eod", "by eod today"}:
        return _at_time(reference.date(), hour=18)
    if value == "by eod tomorrow":
        return _at_time(reference.date() + timedelta(days=1), hour=18)
    if value == "eow":
        return _weekday_deadline(reference, WEEKDAYS["friday"], hour=18)

    eod_weekday = re.fullmatch(rf"by eod ({WEEKDAY_PATTERN})", value)
    if eod_weekday:
        return _weekday_deadline(
            reference,
            WEEKDAYS[eod_weekday.group(1)],
            hour=18,
        )

    weekday = re.fullmatch(rf"(?:(this|next) )?({WEEKDAY_PATTERN})", value)
    if weekday:
        week_offset = 7 if weekday.group(1) == "next" else 0
        return _weekday_deadline(
            reference,
            WEEKDAYS[weekday.group(2)],
            hour=23,
            minute=59,
            week_offset=week_offset,
        )

    return _normalize_absolute(deadline_value.strip())


def _as_ist(reference_datetime: Optional[datetime]) -> datetime:
    if reference_datetime is None:
        return datetime.now(IST)
    if reference_datetime.tzinfo is None:
        return reference_datetime.replace(tzinfo=IST)
    return reference_datetime.astimezone(IST)


def _weekday_deadline(
    reference: datetime,
    target_weekday: int,
    *,
    hour: int,
    minute: int = 0,
    week_offset: int = 0,
) -> str:
    days_ahead = (target_weekday - reference.weekday()) % 7 + week_offset
    target_date = reference.date() + timedelta(days=days_ahead)
    return _at_time(target_date, hour=hour, minute=minute)


def _at_time(target_date: date, *, hour: int, minute: int = 0) -> str:
    return datetime.combine(
        target_date,
        time(hour=hour, minute=minute),
        tzinfo=IST,
    ).isoformat()


def _normalize_absolute(value: str) -> Optional[str]:
    try:
        parsed_date = date.fromisoformat(value)
    except ValueError:
        parsed_date = None
    if parsed_date is not None:
        return _at_time(parsed_date, hour=23, minute=59)

    try:
        parsed_datetime = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _as_ist(parsed_datetime).isoformat()
