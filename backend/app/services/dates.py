from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


def local_today(zone: ZoneInfo) -> date:
    return datetime.now(zone).date()


def day_start(day: date, zone: ZoneInfo) -> datetime:
    """The first instant of a calendar day in the given time zone."""
    return datetime.combine(day, time.min, tzinfo=zone)


def day_after(day: date, zone: ZoneInfo) -> datetime:
    """The first instant of the following day, an exclusive upper bound for `day`."""
    return day_start(day + timedelta(days=1), zone)
