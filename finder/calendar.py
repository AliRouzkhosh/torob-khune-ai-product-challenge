"""Small, deterministic contemporary Solar-Hijri year conversion (no service)."""
from datetime import datetime
from zoneinfo import ZoneInfo


def jalali_year(day):
    # Gregorian leap days, followed by the Solar-Hijri 33/4-year cycles.
    offsets = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)
    gy = day.year
    leap_year = gy + (day.month > 2)
    days = (355666 + 365 * gy + (leap_year + 3) // 4
            - (leap_year + 99) // 100 + (leap_year + 399) // 400
            + day.day + offsets[day.month - 1])
    year = -1595 + 33 * (days // 12053)
    days %= 12053
    year += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        year += (days - 1) // 365
    return year


def current_jalali_year():
    return jalali_year(datetime.now(ZoneInfo('Asia/Tehran')).date())


def new_build_min_year():
    return current_jalali_year() - 3
