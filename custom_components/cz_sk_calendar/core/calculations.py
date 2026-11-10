"""Core calculations for CZ/SK Calendar."""
from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

from ..const import COUNTRY_CZ, COUNTRY_SK, SK_REGION_GROUPS, CZ_SPRING_GROUPS


@lru_cache(maxsize=128)
def calculate_easter_sunday(year: int) -> date:
    """Calculate Easter Sunday using the Anonymous Gregorian algorithm (Computus).

    This algorithm calculates Easter Sunday for any year in the Gregorian calendar.
    Easter falls on the first Sunday after the first full moon on or after March 21.

    Args:
        year: The year to calculate Easter for

    Returns:
        Date of Easter Sunday
    """
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def get_nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    """Get the nth occurrence of a weekday in a month.

    Args:
        year: Year
        month: Month (1-12)
        weekday: Day of week (0=Monday, 6=Sunday)
        n: Occurrence (1=first, 2=second, etc. Use -1 for last)

    Returns:
        Date of the nth weekday
    """
    if n > 0:
        first_day = date(year, month, 1)
        days_until = (weekday - first_day.weekday()) % 7
        first_occurrence = first_day + timedelta(days=days_until)
        return first_occurrence + timedelta(weeks=n - 1)
    else:
        if month == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, month + 1, 1)
        last_day = next_month - timedelta(days=1)
        days_since = (last_day.weekday() - weekday) % 7
        return last_day - timedelta(days=days_since)


def get_school_year(check_date: date) -> int:
    """Get the school year for a given date.

    School year starts in September. Returns the year when school year started.

    Args:
        check_date: Date to check

    Returns:
        Year when school year started (e.g., 2023 for school year 2023/2024)
    """
    if check_date.month >= 9:
        return check_date.year
    return check_date.year - 1


def is_weekend(check_date: date) -> bool:
    """Check if date is a weekend (Saturday or Sunday).

    Args:
        check_date: Date to check

    Returns:
        True if weekend
    """
    return check_date.weekday() >= 5


def is_holiday(check_date: date, country: str) -> bool:
    """Check if a date is a public holiday.

    Args:
        check_date: Date to check
        country: Country code (CZ or SK)

    Returns:
        True if the date is a public holiday
    """
    from .data_sources import get_all_holidays
    holidays = get_all_holidays(check_date.year, country)
    return check_date in holidays


def is_workday(check_date: date, country: str) -> bool:
    """Check if a date is a workday (not weekend and not holiday).

    Args:
        check_date: Date to check
        country: Country code (CZ or SK)

    Returns:
        True if the date is a workday
    """
    if is_weekend(check_date):
        return False
    return not is_holiday(check_date, country)


def is_vacation(check_date: date, country: str, region: str) -> bool:
    """Check if a date is during school vacation.

    Args:
        check_date: Date to check
        country: Country code (CZ or SK)
        region: Region code

    Returns:
        True if the date is during vacation
    """
    from .data_sources import get_all_vacations

    school_year = get_school_year(check_date)

    # Check current school year vacations
    for start, end, _ in get_all_vacations(school_year, country, region):
        if start <= check_date <= end:
            return True

    # Also check previous school year (for summer vacation edge case)
    if check_date.month <= 8:
        for start, end, _ in get_all_vacations(school_year - 1, country, region):
            if start <= check_date <= end:
                return True

    return False


def is_school_day(check_date: date, country: str, region: str) -> bool:
    """Check if a date is a school day.

    A school day is a weekday that is not a holiday and not during vacation.

    Args:
        check_date: Date to check
        country: Country code (CZ or SK)
        region: Region code

    Returns:
        True if the date is a school day
    """
    if is_weekend(check_date):
        return False
    if is_holiday(check_date, country):
        return False
    if is_vacation(check_date, country, region):
        return False
    return True


# ============================================================================
# Vacation date calculations
# ============================================================================

def calc_summer_vacation(year: int, country: str) -> tuple[date, date, str]:
    """Calculate summer vacation dates (July 1 - August 31)."""
    name = "Letní prázdniny" if country == COUNTRY_CZ else "Letné prázdniny"
    return date(year, 7, 1), date(year, 8, 31), name


def calc_autumn_vacation(year: int, country: str) -> tuple[date, date, str]:
    """Calculate autumn vacation dates."""
    if country == COUNTRY_CZ:
        # Two days attached to the state holiday on October 28 (vyhláška
        # 16/2005 Sb.), placed by MŠMT so they join a weekend:
        #   28. 10. Mon -> Tue 29., Wed 30.     (2024)
        #   28. 10. Tue -> Mon 27., Wed 29.     (2025, holiday in between)
        #   28. 10. Wed -> Thu 29., Fri 30.     (2026)
        #   28. 10. Thu -> Wed 27., Fri 29.     (holiday in between)
        #   28. 10. Fri -> Wed 26., Thu 27.     (2022)
        #   28. 10. Sat -> Thu 26., Fri 27.     (2023)
        #   28. 10. Sun -> Thu 25., Fri 26.
        # The returned range may include October 28 itself, which is a
        # state holiday (no school) anyway.
        oct_28 = date(year, 10, 28)
        start_offset, end_offset = {
            0: (1, 2),
            1: (-1, 1),
            2: (1, 2),
            3: (-1, 1),
            4: (-2, -1),
            5: (-2, -1),
            6: (-3, -2),
        }[oct_28.weekday()]
        return (
            oct_28 + timedelta(days=start_offset),
            oct_28 + timedelta(days=end_offset),
            "Podzimní prázdniny",
        )
    else:
        # SK: the last two working days (Mon-Fri) right before
        # All Saints' Day (November 1), e.g.
        #   2023: Mon 30. - Tue 31. 10.   (1. 11. is Wednesday)
        #   2024: Wed 30. - Thu 31. 10.   (1. 11. is Friday)
        #   2025: Thu 30. - Fri 31. 10.   (1. 11. is Saturday)
        #   2026: Thu 29. - Fri 30. 10.   (1. 11. is Sunday)
        end = date(year, 10, 31)
        while end.weekday() >= 5:  # skip Saturday/Sunday
            end -= timedelta(days=1)
        start = end - timedelta(days=1)
        while start.weekday() >= 5:
            start -= timedelta(days=1)
        return start, end, "Jesenné prázdniny"


def calc_christmas_vacation(school_year: int, country: str) -> tuple[date, date, str]:
    """Calculate Christmas vacation dates.

    CZ: Dec 23 - Jan 2 (fixed)
    SK: Dec 22 - Jan 7 (fixed)
    """
    if country == COUNTRY_CZ:
        start = date(school_year, 12, 23)
        end = date(school_year + 1, 1, 2)
        return start, end, "Vánoční prázdniny"
    else:
        start = date(school_year, 12, 22)
        end = date(school_year + 1, 1, 7)
        return start, end, "Vianočné prázdniny"


def calc_semester_vacation(school_year: int, country: str) -> tuple[date, date, str]:
    """Calculate semester (half-term) vacation.

    CZ: Friday between January 29 and February 4 (first Friday after Jan 28)
    SK: First Monday of February
    """
    if country == COUNTRY_CZ:
        # Pololetní prázdniny jsou pátek mezi 29. lednem a 4. únorem
        # (první pátek po 28. lednu)
        jan_29 = date(school_year + 1, 1, 29)
        # Find Friday on or after Jan 29
        days_until_friday = (4 - jan_29.weekday()) % 7
        semester_friday = jan_29 + timedelta(days=days_until_friday)
        return semester_friday, semester_friday, "Pololetní prázdniny"
    else:
        # SK: First Monday of February
        feb_1 = date(school_year + 1, 2, 1)
        if feb_1.weekday() == 0:  # Monday
            first_monday = feb_1
        else:
            days_until_monday = (7 - feb_1.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            first_monday = feb_1 + timedelta(days=days_until_monday)
        return first_monday, first_monday, "Polročné prázdniny"


def calc_spring_vacation(school_year: int, country: str, region: str) -> tuple[date, date, str]:
    """Calculate spring vacation dates (varies by region/district).

    CZ: 6 groups of districts rotating over 6 weeks starting first Monday of February
    SK: 3 regional groups (west, central, east) rotating over 3 weeks starting third Monday of February
    """
    if country == COUNTRY_CZ:
        # Find which group (0-5) this district belongs to
        group_index = 0
        for i, group in enumerate(CZ_SPRING_GROUPS):
            if region in group:
                group_index = i
                break

        # Reference: school year 2025/2026 - groups are in order 1-6 for weeks 1-6
        # For other years, the groups rotate
        reference_year = 2025
        year_offset = school_year - reference_year
        # Groups rotate: each year the schedule shifts
        effective_group = (group_index + year_offset) % 6

        # Find first Monday of February
        feb_1 = date(school_year + 1, 2, 1)
        days_until_monday = (7 - feb_1.weekday()) % 7
        if feb_1.weekday() == 0:
            days_until_monday = 0
        first_monday = feb_1 + timedelta(days=days_until_monday)

        # Start date is first Monday + weeks offset
        start = first_monday + timedelta(weeks=effective_group)
        end = start + timedelta(days=4)  # Monday to Friday
        return start, end, "Jarní prázdniny"
    else:
        # Slovak spring vacation
        # 3 groups rotating over 3 weeks starting third Monday of February
        group_name = "west"
        for name, regions in SK_REGION_GROUPS.items():
            if region in regions:
                group_name = name
                break

        group_order = ["west", "central", "east"]
        group_index = group_order.index(group_name)

        # Reference: school year 2025/2026
        # Week 1 (Feb 16-20): West (Bratislavský, Nitrianský, Trnavský)
        # Week 2 (Feb 23-27): Central (Banskobystrický, Trenčianský, Žilinský)
        # Week 3 (Mar 2-6): East (Prešovský, Košický)
        reference_year = 2025
        year_offset = school_year - reference_year
        effective_slot = (group_index + year_offset) % 3

        feb_1 = date(school_year + 1, 2, 1)
        days_until_monday = (7 - feb_1.weekday()) % 7
        if feb_1.weekday() == 0:
            days_until_monday = 0
        first_monday = feb_1 + timedelta(days=days_until_monday)
        third_monday = first_monday + timedelta(weeks=2)

        start = third_monday + timedelta(weeks=effective_slot)
        end = start + timedelta(days=4)
        return start, end, "Jarné prázdniny"


def calc_easter_vacation(year: int, country: str) -> tuple[date, date, str]:
    """Calculate Easter vacation dates."""
    easter = calculate_easter_sunday(year)

    if country == COUNTRY_CZ:
        start = easter - timedelta(days=3)  # Maundy Thursday
        end = easter + timedelta(days=1)    # Easter Monday
        return start, end, "Velikonoční prázdniny"
    else:
        start = easter - timedelta(days=3)  # Thursday before Easter
        end = easter + timedelta(days=2)    # Tuesday after Easter
        return start, end, "Veľkonočné prázdniny"


def count_workdays_in_range(start_date: date, end_date: date, country: str) -> int:
    """Count workdays in a date range.

    Args:
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
        country: Country code

    Returns:
        Number of workdays in the range
    """
    count = 0
    current = start_date
    while current <= end_date:
        if is_workday(current, country):
            count += 1
        current += timedelta(days=1)
    return count


def count_school_days_in_range(
    start_date: date, end_date: date, country: str, region: str
) -> int:
    """Count school days in a date range.

    Args:
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
        country: Country code
        region: Region code

    Returns:
        Number of school days in the range
    """
    count = 0
    current = start_date
    while current <= end_date:
        if is_school_day(current, country, region):
            count += 1
        current += timedelta(days=1)
    return count
