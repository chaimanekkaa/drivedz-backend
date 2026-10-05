from datetime import date, datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Africa/Algiers")


def now_dz() -> datetime:
    return datetime.now(TZ)


def today_dz() -> date:
    return now_dz().date()
