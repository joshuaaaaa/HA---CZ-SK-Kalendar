"""Core module for CZ/SK Calendar calculations and data."""
from .calculations import (
    calculate_easter_sunday,
    get_school_year,
    is_workday,
    is_school_day,
    is_vacation,
    is_holiday,
    get_nth_weekday_of_month,
)
from .data_sources import (
    get_all_holidays,
    get_holiday_name,
    get_next_holiday,
    get_all_vacations,
    get_vacation_name,
    get_next_vacation,
    parse_custom_vacations,
    set_custom_vacations,
    clear_custom_vacations,
    get_all_special_days,
    get_special_day_name,
    get_next_special_day,
    get_nameday,
    get_nameday_names,
    get_namedays_in_week,
)
from .cache import cached_date, clear_cache
from .validators import validate_country, validate_region

__all__ = [
    # Calculations
    "calculate_easter_sunday",
    "get_school_year",
    "is_workday",
    "is_school_day",
    "is_vacation",
    "is_holiday",
    "get_nth_weekday_of_month",
    # Data sources
    "get_all_holidays",
    "get_holiday_name",
    "get_next_holiday",
    "get_all_vacations",
    "get_vacation_name",
    "get_next_vacation",
    "parse_custom_vacations",
    "set_custom_vacations",
    "clear_custom_vacations",
    "get_all_special_days",
    "get_special_day_name",
    "get_next_special_day",
    "get_nameday",
    "get_nameday_names",
    "get_namedays_in_week",
    # Cache
    "cached_date",
    "clear_cache",
    # Validators
    "validate_country",
    "validate_region",
]
