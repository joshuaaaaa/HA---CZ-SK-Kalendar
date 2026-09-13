"""Sensor platform for CZ/SK School & Work Calendar."""
from __future__ import annotations

import calendar
import re
from datetime import date, timedelta
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_CUSTOM_EVENTS,
    CONF_CUSTOM_BIRTHDAYS,
    CONF_CUSTOM_HOLIDAYS,
    CONF_REMINDER_DAYS,
    CONF_REMINDER_DAILY,
    COUNTRY_CZ,
)
from .entity import CZSKEntity, get_configured_country, get_configured_region
from .core import (
    get_all_vacations,
    get_holiday_name,
    get_nameday,
    get_nameday_names,
    get_next_holiday,
    get_next_vacation,
    get_school_year,
    get_special_day_name,
    get_next_special_day,
    get_vacation_name,
    is_holiday,
    is_school_day,
    is_vacation,
    is_workday,
)


_CUSTOM_ENTRY_RE = re.compile(
    r"^\s*(?P<date>(\d{4}-\d{1,2}-\d{1,2})|(\d{1,2}[.-]\d{1,2})|(\d{1,2}-\d{1,2}))\s*[-|;]\s*(?P<name>.+)$"
)

_DATE_ONLY_RE = re.compile(
    r"^\s*(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[.-]\d{1,2}|\d{1,2}-\d{1,2})\s*$"
)

# Start of a new ``date separator name`` entry inside a single chunk of text.
# Used to split lines where entries are separated by spaces or commas instead
# of ``|``, so the name of one entry does not swallow the following entries.
_ENTRY_START_RE = re.compile(
    r"(?:^|(?<=[\s,;|]))"
    r"(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[.-]\d{1,2})\s*[-|;]\s*"
)

_DATE_TOKEN = r"(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[.-]\d{1,2}\.?)"
_LEADING_DATE_RE = re.compile(r"^\s*" + _DATE_TOKEN + r"[\s,;|-]*")
_TRAILING_DATE_RE = re.compile(r"[\s,;|-]*" + _DATE_TOKEN + r"\s*$")


def _strip_redundant_date(name: str) -> str:
    """Remove a date that the user repeated inside the event name.

    The state of the ``next_*`` sensors is the plain event name, so a date
    typed into the name as well (``16-09 | Marie 16-09``) would be shown
    twice. The date itself stays available in the dedicated date sensor and
    in the ``date`` attribute.
    """
    for pattern in (_LEADING_DATE_RE, _TRAILING_DATE_RE):
        stripped = pattern.sub("", name).strip()
        if stripped:
            name = stripped
    return name


def _split_inline_entries(text: str) -> list[str]:
    """Split a chunk of text into individual ``date separator name`` entries.

    A single line may hold several entries separated by spaces, commas or
    semicolons (``16-09-Marie 30-09-Jeroným``). Without this split the name
    of the first entry would greedily swallow everything that follows.
    """
    cleaned = text.strip()
    if not cleaned:
        return []

    starts = [m.start() for m in _ENTRY_START_RE.finditer(cleaned)]
    if len(starts) <= 1:
        return [cleaned]

    if starts[0] != 0:
        starts.insert(0, 0)

    chunks: list[str] = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(cleaned)
        chunk = cleaned[start:end].strip().rstrip(",;|").strip()
        if chunk:
            chunks.append(chunk)
    return chunks


def _iter_custom_entries(raw: str) -> list[str]:
    """Split raw list into individual entry strings.

    Handles multiple formats:
      - One entry per line: ``03.02 | Narozeniny máma``
      - Multiple entries on one line separated by ``|``:
        ``03.02 | Narozeniny máma | 07.08 | Narozeniny táta``
      - Entries using ``-`` or ``;`` as date-name separator:
        ``03.02-Narozeniny máma | 07.08-Narozeniny táta``
    """
    entries: list[str] = []
    if not raw:
        return entries

    for line in raw.splitlines():
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#"):
            continue

        if "|" not in cleaned:
            entries.extend(_split_inline_entries(cleaned))
            continue

        # Split by | and reassemble date-name pairs
        parts = [p.strip() for p in cleaned.split("|")]
        i = 0
        while i < len(parts):
            part = parts[i]
            if not part:
                i += 1
                continue

            # If this part is a standalone date, combine with next part as name
            if _DATE_ONLY_RE.match(part) and i + 1 < len(parts) and parts[i + 1].strip():
                entries.extend(
                    _split_inline_entries(f"{part} | {parts[i + 1].strip()}")
                )
                i += 2
            else:
                # Already a complete entry (uses - or ; as date-name separator)
                entries.extend(_split_inline_entries(part))
                i += 1

    return entries


def _parse_custom_date(date_str: str) -> tuple[int | None, int, int] | None:
    """Parse date string into (year, month, day)."""
    if not date_str:
        return None

    if "." in date_str:
        parts = [p.strip() for p in date_str.split(".")]
        if len(parts) != 2:
            return None
        day, month = parts
        try:
            day_i = int(day)
            month_i = int(month)
        except ValueError:
            return None
        return None, month_i, day_i

    if date_str.count("-") == 2:
        parts = [p.strip() for p in date_str.split("-")]
        if len(parts[0]) == 4:
            try:
                year_i, month_i, day_i = (int(parts[0]), int(parts[1]), int(parts[2]))
            except ValueError:
                return None
            return year_i, month_i, day_i

    if date_str.count("-") == 1:
        left, right = [p.strip() for p in date_str.split("-")]
        try:
            left_i, right_i = int(left), int(right)
        except ValueError:
            return None
        if left_i > 12 and right_i <= 12:
            return None, right_i, left_i
        if right_i > 12 and left_i <= 12:
            return None, left_i, right_i
        return None, right_i, left_i

    return None


def _parse_custom_list(raw: str) -> list[dict[str, int | str | None]]:
    """Parse custom events list into structured entries.

    Supported formats per entry:
      - DD.MM-Název or DD.MM | Název (recurring yearly)
      - MM-DD | Název (recurring yearly)
      - YYYY-MM-DD | Název (one-off)
    """
    events: list[dict[str, int | str | None]] = []
    for entry in _iter_custom_entries(raw):
        match = _CUSTOM_ENTRY_RE.match(entry)
        if not match:
            continue
        date_part = match.group("date").strip()
        name = _strip_redundant_date(match.group("name").strip())
        parsed = _parse_custom_date(date_part)
        if not parsed or not name:
            continue
        year, month, day = parsed
        if not 1 <= month <= 12:
            continue
        if not 1 <= day <= 31:
            continue
        events.append({"year": year, "month": month, "day": day, "name": name})

    return events


def _get_custom_event_name(
    check_date: date, events: list[dict[str, int | str | None]]
) -> str | None:
    """Get combined custom event name for a date."""
    names: list[str] = []
    for event in events:
        event_year = event["year"]
        if event_year is not None and event_year != check_date.year:
            continue
        if int(event["month"]) == check_date.month and int(event["day"]) == check_date.day:
            names.append(str(event["name"]))

    if not names:
        return None
    return ", ".join(names)


def _get_next_custom_event(
    from_date: date, events: list[dict[str, int | str | None]]
) -> tuple[date | None, str | None]:
    """Get next custom event from a date."""
    current = from_date
    end_date = from_date + timedelta(days=400)

    while current <= end_date:
        name = _get_custom_event_name(current, events)
        if name:
            return current, name
        current += timedelta(days=1)

    return None, None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the CZ/SK Calendar sensors."""
    country = get_configured_country(config_entry)
    region = get_configured_region(config_entry)

    sensors = [
        # Boolean state sensors (kept for backwards compatibility)
        CZSKBooleanSensor(
            config_entry, "workday",
            "Pracovní den" if country == COUNTRY_CZ else "Pracovný deň",
            "mdi:briefcase",
            lambda e: is_workday(e.today, e._country),
        ),
        CZSKBooleanSensor(
            config_entry, "school_day",
            "Školní den" if country == COUNTRY_CZ else "Školský deň",
            "mdi:school",
            lambda e: is_school_day(e.today, e._country, e._region),
        ),
        CZSKBooleanSensor(
            config_entry, "holiday",
            "Svátek" if country == COUNTRY_CZ else "Sviatok",
            "mdi:party-popper",
            lambda e: is_holiday(e.today, e._country),
        ),
        CZSKBooleanSensor(
            config_entry, "vacation",
            "Prázdniny" if country == COUNTRY_CZ else "Prázdniny",
            "mdi:beach",
            lambda e: is_vacation(e.today, e._country, e._region),
        ),
        # Name sensors
        CZSKNameSensor(
            config_entry, "holiday_name",
            "Název svátku" if country == COUNTRY_CZ else "Názov sviatku",
            "mdi:calendar-star",
            lambda e: get_holiday_name(e.today, e._country),
        ),
        CZSKNameSensor(
            config_entry, "vacation_name",
            "Název prázdnin" if country == COUNTRY_CZ else "Názov prázdnin",
            "mdi:calendar-text",
            lambda e: get_vacation_name(e.today, e._country, e._region),
        ),
        CZSKNameSensor(
            config_entry, "special_day",
            "Významný den" if country == COUNTRY_CZ else "Významný deň",
            "mdi:star",
            lambda e: get_special_day_name(e.today, e._country),
        ),
        # Name day sensors (today / tomorrow / day after tomorrow)
        CZSKNamedaySensor(config_entry, country, 0),
        CZSKNamedaySensor(config_entry, country, 1),
        CZSKNamedaySensor(config_entry, country, 2),
        # Next event sensors
        CZSKNextHolidaySensor(config_entry, country),
        CZSKNextVacationSensor(config_entry, country, region),
        CZSKNextSpecialDaySensor(config_entry, country),
        CZSKNextBirthdaySensor(config_entry, country),
        CZSKNextFamilyHolidaySensor(config_entry, country),
        # Dates of the next custom events (name and date kept separate)
        CZSKNextBirthdayDateSensor(config_entry, country),
        CZSKNextFamilyHolidayDateSensor(config_entry, country),
        # Day name sensors
        CZSKTodayDayNameSensor(config_entry, country),
        CZSKTomorrowDayNameSensor(config_entry, country),
        # Today's custom event sensors
        CZSKTodayBirthdaySensor(config_entry, country),
        CZSKTodayFamilyHolidaySensor(config_entry, country),
        # Countdown sensors
        CZSKDaysToHolidaySensor(config_entry, country),
        CZSKDaysToVacationSensor(config_entry, country, region),
        CZSKDaysToSpecialDaySensor(config_entry, country),
        CZSKDaysToBirthdaySensor(config_entry, country),
        CZSKDaysToFamilyHolidaySensor(config_entry, country),
        CZSKWorkdaysToWeekendSensor(config_entry, country),
        # School year sensor
        CZSKSchoolYearSensor(config_entry, country, region),
        # Statistics sensors
        CZSKWorkdaysInMonthSensor(config_entry, country),
        CZSKSchoolDaysInMonthSensor(config_entry, country, region),
        CZSKVacationProgressSensor(config_entry, country, region),
    ]

    async_add_entities(sensors, True)


# ============================================================================
# Base sensor classes
# ============================================================================

class CZSKBaseSensor(CZSKEntity, SensorEntity):
    """Base class for CZ/SK Calendar sensors."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        entity_type: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the base sensor with custom events."""
        super().__init__(config_entry, entity_type, name, icon)
        options = self._config_entry.options
        raw_birthdays = options.get(CONF_CUSTOM_BIRTHDAYS, "")
        raw_holidays = options.get(CONF_CUSTOM_HOLIDAYS, "")
        legacy_events = options.get(CONF_CUSTOM_EVENTS, "")

        self._custom_birthdays = _parse_custom_list(raw_birthdays)
        self._custom_holidays = _parse_custom_list(raw_holidays)
        if legacy_events and not self._custom_holidays:
            self._custom_holidays = _parse_custom_list(legacy_events)

        reminder_days = options.get(CONF_REMINDER_DAYS, 3)
        try:
            reminder_days = int(reminder_days)
        except (TypeError, ValueError):
            reminder_days = 3
        self._reminder_days = max(0, reminder_days)
        self._reminder_daily = bool(options.get(CONF_REMINDER_DAILY, True))


class CZSKBooleanSensor(CZSKBaseSensor):
    """Sensor that returns True/False based on a condition."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        entity_type: str,
        name: str,
        icon: str,
        value_fn,
    ) -> None:
        """Initialize the boolean sensor."""
        super().__init__(config_entry, entity_type, name, icon)
        self._value_fn = value_fn

    @property
    def native_value(self) -> bool:
        """Return the sensor value."""
        return self._value_fn(self)


class CZSKNameSensor(CZSKBaseSensor):
    """Sensor that returns a name (holiday, vacation, etc.)."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        entity_type: str,
        name: str,
        icon: str,
        value_fn,
    ) -> None:
        """Initialize the name sensor."""
        super().__init__(config_entry, entity_type, name, icon)
        self._value_fn = value_fn

    @property
    def native_value(self) -> str | None:
        """Return the sensor value."""
        return self._value_fn(self)


# ============================================================================
# Specialized sensors
# ============================================================================

class CZSKCountdownSensor(CZSKBaseSensor):
    """Combined countdown sensor for holidays and vacations."""

    _attr_native_unit_of_measurement = "days"

    def __init__(self, config_entry: ConfigEntry, country: str) -> None:
        """Initialize the countdown sensor."""
        name = "Odpočet" if country == COUNTRY_CZ else "Odpočet"
        super().__init__(config_entry, "countdown", name, "mdi:timer-sand")

    @property
    def native_value(self) -> int:
        """Return days to next event (holiday or vacation)."""
        today = self.today

        # Days to next holiday
        if is_holiday(today, self._country):
            days_holiday = 0
        else:
            next_h, _ = get_next_holiday(today + timedelta(days=1), self._country)
            days_holiday = (next_h - today).days

        # Days to next vacation
        if is_vacation(today, self._country, self._region):
            days_vacation = 0
        else:
            next_v, _, _ = get_next_vacation(today, self._country, self._region)
            days_vacation = (next_v - today).days

        return min(days_holiday, days_vacation)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = super().extra_state_attributes.copy()
        today = self.today

        # Next holiday
        if is_holiday(today, self._country):
            attrs["days_to_holiday"] = 0
            attrs["holiday_name"] = get_holiday_name(today, self._country)
        else:
            next_h, name_h = get_next_holiday(today + timedelta(days=1), self._country)
            attrs["days_to_holiday"] = (next_h - today).days
            attrs["next_holiday"] = name_h
            attrs["next_holiday_date"] = next_h.isoformat()

        # Next vacation
        if is_vacation(today, self._country, self._region):
            attrs["days_to_vacation"] = 0
            attrs["vacation_name"] = get_vacation_name(today, self._country, self._region)
        else:
            next_v, name_v, end_v = get_next_vacation(today, self._country, self._region)
            attrs["days_to_vacation"] = (next_v - today).days
            attrs["next_vacation"] = name_v
            attrs["next_vacation_start"] = next_v.isoformat()
            attrs["next_vacation_end"] = end_v.isoformat()

        # Next special day
        next_s, name_s = get_next_special_day(today + timedelta(days=1), self._country)
        attrs["days_to_special_day"] = (next_s - today).days
        attrs["next_special_day"] = name_s
        attrs["next_special_day_date"] = next_s.isoformat()

        # Tomorrow's nameday
        tomorrow = today + timedelta(days=1)
        attrs["tomorrow_nameday"] = get_nameday(tomorrow, self._country)

        return attrs


class CZSKNextHolidaySensor(CZSKBaseSensor):
    """Sensor for next holiday."""

    def __init__(self, config_entry: ConfigEntry, country: str) -> None:
        """Initialize the next holiday sensor."""
        name = "Příští svátek" if country == COUNTRY_CZ else "Ďalší sviatok"
        super().__init__(config_entry, "next_holiday", name, "mdi:calendar-arrow-right")

    @property
    def native_value(self) -> str:
        """Return the name of the next holiday."""
        today = self.today
        _, name = get_next_holiday(today + timedelta(days=1), self._country)
        return name

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = super().extra_state_attributes.copy()
        today = self.today
        next_date, name = get_next_holiday(today + timedelta(days=1), self._country)
        attrs["date"] = next_date.isoformat()
        attrs["days_until"] = (next_date - today).days
        return attrs


class CZSKNextVacationSensor(CZSKBaseSensor):
    """Sensor for next vacation."""

    def __init__(
        self, config_entry: ConfigEntry, country: str, region: str
    ) -> None:
        """Initialize the next vacation sensor."""
        name = "Příští prázdniny" if country == COUNTRY_CZ else "Ďalšie prázdniny"
        super().__init__(config_entry, "next_vacation", name, "mdi:calendar-arrow-right")

    @property
    def native_value(self) -> str:
        """Return the name of the next vacation."""
        today = self.today
        if is_vacation(today, self._country, self._region):
            start, name, end = get_next_vacation(
                today + timedelta(days=1), self._country, self._region
            )
        else:
            start, name, end = get_next_vacation(today, self._country, self._region)
        return name

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = super().extra_state_attributes.copy()
        today = self.today
        if is_vacation(today, self._country, self._region):
            start, name, end = get_next_vacation(
                today + timedelta(days=1), self._country, self._region
            )
        else:
            start, name, end = get_next_vacation(today, self._country, self._region)
        attrs["start_date"] = start.isoformat()
        attrs["end_date"] = end.isoformat()
        attrs["days_until"] = (start - today).days
        attrs["duration_days"] = (end - start).days + 1
        return attrs


class CZSKNextSpecialDaySensor(CZSKBaseSensor):
    """Sensor for next special day (includes custom events)."""

    def __init__(self, config_entry: ConfigEntry, country: str) -> None:
        """Initialize the next special day sensor."""
        name = "Příští významný den" if country == COUNTRY_CZ else "Ďalší významný deň"
        super().__init__(config_entry, "next_special_day", name, "mdi:calendar-star")

    @property
    def native_value(self) -> str:
        """Return the name of the next special day."""
        today = self.today
        _, name = get_next_special_day(today + timedelta(days=1), self._country)
        return name

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = super().extra_state_attributes.copy()
        today = self.today
        next_date, name = get_next_special_day(today + timedelta(days=1), self._country)
        attrs["date"] = next_date.isoformat()
        attrs["days_until"] = (next_date - today).days
        attrs["name"] = name
        return attrs


class CZSKNextBirthdaySensor(CZSKBaseSensor):
    """Sensor for next custom birthday."""

    def __init__(self, config_entry: ConfigEntry, country: str) -> None:
        """Initialize the next birthday sensor."""
        name = "Příští narozeniny" if country == COUNTRY_CZ else "Ďalšie narodeniny"
        super().__init__(config_entry, "next_birthday", name, "mdi:cake")

    @property
    def native_value(self) -> str | None:
        """Return the name of the next birthday."""
        today = self.today
        _, name = _get_next_custom_event(today + timedelta(days=1), self._custom_birthdays)
        return name

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = super().extra_state_attributes.copy()
        today = self.today
        next_date, name = _get_next_custom_event(today + timedelta(days=1), self._custom_birthdays)
        attrs["reminder_days"] = self._reminder_days
        attrs["reminder_daily"] = self._reminder_daily

        if next_date and name:
            days_until = (next_date - today).days
            in_window = 0 <= days_until <= self._reminder_days
            should_notify = in_window if self._reminder_daily else days_until == self._reminder_days
            attrs["date"] = next_date.isoformat()
            attrs["days_until"] = days_until
            attrs["name"] = name
            attrs["in_reminder_window"] = in_window
            attrs["should_notify"] = should_notify

        return attrs


class CZSKNextFamilyHolidaySensor(CZSKBaseSensor):
    """Sensor for next custom family holiday."""

    def __init__(self, config_entry: ConfigEntry, country: str) -> None:
        """Initialize the next family holiday sensor."""
        name = "Příští rodinný svátek" if country == COUNTRY_CZ else "Ďalší rodinný sviatok"
        super().__init__(config_entry, "next_family_holiday", name, "mdi:party-popper")

    @property
    def native_value(self) -> str | None:
        """Return the name of the next family holiday."""
        today = self.today
        _, name = _get_next_custom_event(today + timedelta(days=1), self._custom_holidays)
        return name

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = super().extra_state_attributes.copy()
        today = self.today
        next_date, name = _get_next_custom_event(today + timedelta(days=1), self._custom_holidays)
        attrs["reminder_days"] = self._reminder_days
        attrs["reminder_daily"] = self._reminder_daily

        if next_date and name:
            days_until = (next_date - today).days
            in_window = 0 <= days_until <= self._reminder_days
            should_notify = in_window if self._reminder_daily else days_until == self._reminder_days
            attrs["date"] = next_date.isoformat()
            attrs["days_until"] = days_until
            attrs["name"] = name
            attrs["in_reminder_window"] = in_window
            attrs["should_notify"] = should_notify

        return attrs


class CZSKNextCustomEventDateSensor(CZSKBaseSensor):
    """Base sensor reporting the date of the next custom event.

    Companion to the ``next_*`` sensors, whose state is only the event name.
    """

    _attr_device_class = SensorDeviceClass.DATE

    @property
    def _events(self) -> list[dict[str, int | str | None]]:
        """Return the list of custom events to search."""
        raise NotImplementedError

    @property
    def native_value(self) -> date | None:
        """Return the date of the next custom event."""
        next_date, _ = _get_next_custom_event(
            self.today + timedelta(days=1), self._events
        )
        return next_date

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = super().extra_state_attributes.copy()
        today = self.today
        next_date, name = _get_next_custom_event(today + timedelta(days=1), self._events)
        attrs["reminder_days"] = self._reminder_days
        attrs["reminder_daily"] = self._reminder_daily

        if next_date and name:
            days_until = (next_date - today).days
            in_window = 0 <= days_until <= self._reminder_days
            should_notify = in_window if self._reminder_daily else days_until == self._reminder_days
            attrs["name"] = name
            attrs["days_until"] = days_until
            attrs["date_formatted"] = f"{next_date.day}. {next_date.month}. {next_date.year}"
            attrs["in_reminder_window"] = in_window
            attrs["should_notify"] = should_notify

        return attrs


class CZSKNextBirthdayDateSensor(CZSKNextCustomEventDateSensor):
    """Sensor for the date of the next custom birthday."""

    def __init__(self, config_entry: ConfigEntry, country: str) -> None:
        """Initialize the next birthday date sensor."""
        name = (
            "Datum příštích narozenin"
            if country == COUNTRY_CZ
            else "Dátum ďalších narodenín"
        )
        super().__init__(config_entry, "next_birthday_date", name, "mdi:calendar-account")

    @property
    def _events(self) -> list[dict[str, int | str | None]]:
        """Return the configured birthdays."""
        return self._custom_birthdays


class CZSKNextFamilyHolidayDateSensor(CZSKNextCustomEventDateSensor):
    """Sensor for the date of the next custom family holiday."""

    def __init__(self, config_entry: ConfigEntry, country: str) -> None:
        """Initialize the next family holiday date sensor."""
        name = (
            "Datum příštího rodinného svátku"
            if country == COUNTRY_CZ
            else "Dátum ďalšieho rodinného sviatku"
        )
        super().__init__(
            config_entry, "next_family_holiday_date", name, "mdi:calendar-heart"
        )

    @property
    def _events(self) -> list[dict[str, int | str | None]]:
        """Return the configured family holidays."""
        return self._custom_holidays


_CZ_DAY_NAMES = [
    "Pondělí", "Úterý", "Středa", "Čtvrtek", "Pátek", "Sobota", "Neděle"
]
_SK_DAY_NAMES = [
    "Pondelok", "Utorok", "Streda", "Štvrtok", "Piatok", "Sobota", "Nedeľa"
]


class CZSKNamedaySensor(CZSKBaseSensor):
    """Sensor for the name day of today, tomorrow or the day after tomorrow.

    The state is the full calendar entry for that day. Days shared by more
    than one name (the Slovak calendar has plenty, e.g. 2. 9. "Linda,
    Rebeka") keep every name in the state and also expose them one by one in
    the ``names`` attribute.
    """

    # offset in days -> (entity_type, Czech name, Slovak name, icon)
    _VARIANTS: dict[int, tuple[str, str, str, str]] = {
        0: ("nameday", "Jmeniny", "Meniny", "mdi:cake-variant"),
        1: ("nameday_tomorrow", "Jmeniny zítra", "Meniny zajtra", "mdi:cake"),
        2: (
            "nameday_day_after_tomorrow",
            "Jmeniny pozítří",
            "Meniny pozajtra",
            "mdi:cake-layered",
        ),
    }

    def __init__(
        self, config_entry: ConfigEntry, country: str, offset: int = 0
    ) -> None:
        """Initialize the name day sensor.

        Args:
            config_entry: The config entry
            country: Country code (CZ or SK)
            offset: Days from today (0 = today, 1 = tomorrow, 2 = day after)
        """
        entity_type, cz_name, sk_name, icon = self._VARIANTS[offset]
        name = cz_name if country == COUNTRY_CZ else sk_name
        super().__init__(config_entry, entity_type, name, icon)
        self._offset = offset

    @property
    def _target_date(self) -> date:
        """Date this sensor reports on."""
        return self.today + timedelta(days=self._offset)

    @property
    def native_value(self) -> str | None:
        """Return all names of the day, comma separated."""
        return get_nameday(self._target_date, self._country)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = super().extra_state_attributes.copy()
        target = self._target_date
        names = get_nameday_names(target, self._country)

        attrs["date"] = target.isoformat()
        attrs["offset_days"] = self._offset
        attrs["names"] = names
        attrs["names_count"] = len(names)
        return attrs


class CZSKTodayDayNameSensor(CZSKBaseSensor):
    """Sensor returning the name of today's day of the week."""

    def __init__(self, config_entry: ConfigEntry, country: str) -> None:
        name = "Dnešní den" if country == COUNTRY_CZ else "Dnešný deň"
        super().__init__(config_entry, "today_day_name", name, "mdi:calendar-today")

    @property
    def native_value(self) -> str:
        weekday = self.today.weekday()
        return _CZ_DAY_NAMES[weekday] if self._country == COUNTRY_CZ else _SK_DAY_NAMES[weekday]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = super().extra_state_attributes.copy()
        today = self.today
        attrs["date"] = today.isoformat()
        attrs["weekday_number"] = today.weekday()
        return attrs


class CZSKTomorrowDayNameSensor(CZSKBaseSensor):
    """Sensor returning the name of tomorrow's day of the week."""

    def __init__(self, config_entry: ConfigEntry, country: str) -> None:
        name = "Zítřejší den" if country == COUNTRY_CZ else "Zajtrajší deň"
        super().__init__(config_entry, "tomorrow_day_name", name, "mdi:calendar-arrow-right")

    @property
    def native_value(self) -> str:
        tomorrow = self.today + timedelta(days=1)
        weekday = tomorrow.weekday()
        return _CZ_DAY_NAMES[weekday] if self._country == COUNTRY_CZ else _SK_DAY_NAMES[weekday]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = super().extra_state_attributes.copy()
        tomorrow = self.today + timedelta(days=1)
        attrs["date"] = tomorrow.isoformat()
        attrs["weekday_number"] = tomorrow.weekday()
        return attrs


class CZSKTodayBirthdaySensor(CZSKBaseSensor):
    """Sensor for today's birthday from custom birthday list."""

    def __init__(self, config_entry: ConfigEntry, country: str) -> None:
        """Initialize the today's birthday sensor."""
        name = "Dnešní narozeniny" if country == COUNTRY_CZ else "Dnešné narodeniny"
        super().__init__(config_entry, "today_birthday", name, "mdi:cake-variant")

    @property
    def native_value(self) -> str | None:
        """Return today's birthday name or None."""
        return _get_custom_event_name(self.today, self._custom_birthdays)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = super().extra_state_attributes.copy()
        name = _get_custom_event_name(self.today, self._custom_birthdays)
        attrs["has_birthday"] = name is not None
        if name:
            attrs["name"] = name
        return attrs


class CZSKTodayFamilyHolidaySensor(CZSKBaseSensor):
    """Sensor for today's family holiday from custom holiday list."""

    def __init__(self, config_entry: ConfigEntry, country: str) -> None:
        """Initialize the today's family holiday sensor."""
        name = "Dnešní rodinný svátek" if country == COUNTRY_CZ else "Dnešný rodinný sviatok"
        super().__init__(config_entry, "today_family_holiday", name, "mdi:party-popper")

    @property
    def native_value(self) -> str | None:
        """Return today's family holiday name or None."""
        return _get_custom_event_name(self.today, self._custom_holidays)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = super().extra_state_attributes.copy()
        name = _get_custom_event_name(self.today, self._custom_holidays)
        attrs["has_holiday"] = name is not None
        if name:
            attrs["name"] = name
        return attrs


class CZSKDaysToHolidaySensor(CZSKBaseSensor):
    """Sensor for days until next holiday."""

    _attr_native_unit_of_measurement = "days"

    def __init__(self, config_entry: ConfigEntry, country: str) -> None:
        """Initialize the days to holiday sensor."""
        name = "Dní do svátku" if country == COUNTRY_CZ else "Dní do sviatku"
        super().__init__(config_entry, "days_to_holiday", name, "mdi:counter")

    @property
    def native_value(self) -> int:
        """Return days until next holiday."""
        today = self.today
        if is_holiday(today, self._country):
            return 0
        next_date, _ = get_next_holiday(today + timedelta(days=1), self._country)
        return (next_date - today).days

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = super().extra_state_attributes.copy()
        today = self.today
        if is_holiday(today, self._country):
            attrs["holiday_name"] = get_holiday_name(today, self._country)
        else:
            next_date, name = get_next_holiday(today + timedelta(days=1), self._country)
            attrs["next_holiday"] = name
            attrs["next_holiday_date"] = next_date.isoformat()
        return attrs


class CZSKDaysToVacationSensor(CZSKBaseSensor):
    """Sensor for days until next vacation."""

    _attr_native_unit_of_measurement = "days"

    def __init__(
        self, config_entry: ConfigEntry, country: str, region: str
    ) -> None:
        """Initialize the days to vacation sensor."""
        name = "Dní do prázdnin" if country == COUNTRY_CZ else "Dní do prázdnin"
        super().__init__(config_entry, "days_to_vacation", name, "mdi:counter")

    @property
    def native_value(self) -> int:
        """Return days until next vacation."""
        today = self.today
        if is_vacation(today, self._country, self._region):
            return 0
        start, _, _ = get_next_vacation(today, self._country, self._region)
        return (start - today).days

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = super().extra_state_attributes.copy()
        today = self.today
        if is_vacation(today, self._country, self._region):
            attrs["vacation_name"] = get_vacation_name(today, self._country, self._region)
        else:
            start, name, end = get_next_vacation(today, self._country, self._region)
            attrs["next_vacation"] = name
            attrs["next_vacation_start"] = start.isoformat()
            attrs["next_vacation_end"] = end.isoformat()
        return attrs


class CZSKDaysToSpecialDaySensor(CZSKBaseSensor):
    """Sensor for days until next special day (includes custom events)."""

    _attr_native_unit_of_measurement = "days"

    def __init__(self, config_entry: ConfigEntry, country: str) -> None:
        """Initialize the days to special day sensor."""
        name = "Dní do významného dne" if country == COUNTRY_CZ else "Dní do významného dňa"
        super().__init__(config_entry, "days_to_special_day", name, "mdi:counter")

    @property
    def native_value(self) -> int:
        """Return days until next special day."""
        today = self.today
        if get_special_day_name(today, self._country):
            return 0
        next_date, _ = get_next_special_day(today + timedelta(days=1), self._country)
        return (next_date - today).days

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = super().extra_state_attributes.copy()
        today = self.today
        if get_special_day_name(today, self._country):
            attrs["special_day_name"] = get_special_day_name(today, self._country)
        else:
            next_date, name = get_next_special_day(today + timedelta(days=1), self._country)
            attrs["next_special_day"] = name
            attrs["next_special_day_date"] = next_date.isoformat()
        return attrs


class CZSKDaysToBirthdaySensor(CZSKBaseSensor):
    """Sensor for days until next custom birthday."""

    _attr_native_unit_of_measurement = "days"

    def __init__(self, config_entry: ConfigEntry, country: str) -> None:
        """Initialize the days to birthday sensor."""
        name = "Dní do narozenin" if country == COUNTRY_CZ else "Dní do narodenín"
        super().__init__(config_entry, "days_to_birthday", name, "mdi:counter")

    @property
    def native_value(self) -> int | None:
        """Return days until next birthday."""
        today = self.today
        if _get_custom_event_name(today, self._custom_birthdays):
            return 0
        next_date, _ = _get_next_custom_event(today + timedelta(days=1), self._custom_birthdays)
        if not next_date:
            return None
        return (next_date - today).days

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = super().extra_state_attributes.copy()
        today = self.today
        attrs["reminder_days"] = self._reminder_days
        attrs["reminder_daily"] = self._reminder_daily

        if _get_custom_event_name(today, self._custom_birthdays):
            attrs["birthday_name"] = _get_custom_event_name(today, self._custom_birthdays)
            attrs["in_reminder_window"] = True
            attrs["should_notify"] = True
        else:
            next_date, name = _get_next_custom_event(today + timedelta(days=1), self._custom_birthdays)
            if next_date and name:
                days_until = (next_date - today).days
                in_window = 0 <= days_until <= self._reminder_days
                should_notify = in_window if self._reminder_daily else days_until == self._reminder_days
                attrs["next_birthday"] = name
                attrs["next_birthday_date"] = next_date.isoformat()
                attrs["in_reminder_window"] = in_window
                attrs["should_notify"] = should_notify
        return attrs


class CZSKDaysToFamilyHolidaySensor(CZSKBaseSensor):
    """Sensor for days until next custom family holiday."""

    _attr_native_unit_of_measurement = "days"

    def __init__(self, config_entry: ConfigEntry, country: str) -> None:
        """Initialize the days to family holiday sensor."""
        name = "Dní do rodinného svátku" if country == COUNTRY_CZ else "Dní do rodinného sviatku"
        super().__init__(config_entry, "days_to_family_holiday", name, "mdi:counter")

    @property
    def native_value(self) -> int | None:
        """Return days until next family holiday."""
        today = self.today
        if _get_custom_event_name(today, self._custom_holidays):
            return 0
        next_date, _ = _get_next_custom_event(today + timedelta(days=1), self._custom_holidays)
        if not next_date:
            return None
        return (next_date - today).days

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = super().extra_state_attributes.copy()
        today = self.today
        attrs["reminder_days"] = self._reminder_days
        attrs["reminder_daily"] = self._reminder_daily

        if _get_custom_event_name(today, self._custom_holidays):
            attrs["holiday_name"] = _get_custom_event_name(today, self._custom_holidays)
            attrs["in_reminder_window"] = True
            attrs["should_notify"] = True
        else:
            next_date, name = _get_next_custom_event(today + timedelta(days=1), self._custom_holidays)
            if next_date and name:
                days_until = (next_date - today).days
                in_window = 0 <= days_until <= self._reminder_days
                should_notify = in_window if self._reminder_daily else days_until == self._reminder_days
                attrs["next_family_holiday"] = name
                attrs["next_family_holiday_date"] = next_date.isoformat()
                attrs["in_reminder_window"] = in_window
                attrs["should_notify"] = should_notify
        return attrs


class CZSKWorkdaysToWeekendSensor(CZSKBaseSensor):
    """Sensor for workdays until weekend."""

    _attr_native_unit_of_measurement = "days"

    def __init__(self, config_entry: ConfigEntry, country: str) -> None:
        """Initialize the workdays to weekend sensor."""
        name = "Pracovní dny do víkendu" if country == COUNTRY_CZ else "Pracovné dni do víkendu"
        super().__init__(config_entry, "workdays_to_weekend", name, "mdi:calendar-weekend")

    @property
    def native_value(self) -> int:
        """Return workdays until weekend (Saturday)."""
        today = self.today

        # If it's weekend, return 0
        if today.weekday() >= 5:
            return 0

        # Count workdays until Saturday
        count = 0
        current = today
        while current.weekday() < 5:
            if is_workday(current, self._country):
                count += 1
            current += timedelta(days=1)

        return count

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = super().extra_state_attributes.copy()
        today = self.today

        days_to_saturday = (5 - today.weekday()) % 7
        if days_to_saturday == 0 and today.weekday() != 5:
            days_to_saturday = 7
        next_saturday = today + timedelta(days=days_to_saturday)

        attrs["next_weekend"] = next_saturday.isoformat()
        attrs["is_weekend"] = today.weekday() >= 5
        attrs["day_of_week"] = today.strftime("%A")
        return attrs


class CZSKSchoolYearSensor(CZSKBaseSensor):
    """Sensor for school year information."""

    def __init__(
        self, config_entry: ConfigEntry, country: str, region: str
    ) -> None:
        """Initialize the school year sensor."""
        name = "Školní rok" if country == COUNTRY_CZ else "Školský rok"
        super().__init__(config_entry, "school_year", name, "mdi:school")

    @property
    def native_value(self) -> str:
        """Return the current school year."""
        school_year = get_school_year(self.today)
        return f"{school_year}/{school_year + 1}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = super().extra_state_attributes.copy()
        today = self.today
        school_year = get_school_year(today)

        # School year dates
        start_day = 2 if self._country == "SK" else 1
        start_date = date(school_year, 9, start_day)
        end_date = date(school_year + 1, 6, 30)

        attrs["start_date"] = start_date.isoformat()
        attrs["end_date"] = end_date.isoformat()

        # Progress
        total_days = (end_date - start_date).days + 1
        elapsed = max(0, (today - start_date).days)
        remaining = max(0, (end_date - today).days)

        attrs["total_days"] = total_days
        attrs["elapsed_days"] = elapsed
        attrs["remaining_days"] = remaining
        attrs["progress_percent"] = round(min(100, (elapsed / total_days) * 100), 1)

        # Vacations list
        vacations = get_all_vacations(school_year, self._country, self._region)
        attrs["vacations"] = [
            {"name": name, "start": start.isoformat(), "end": end.isoformat()}
            for start, end, name in sorted(vacations, key=lambda x: x[0])
        ]

        return attrs


class CZSKWorkdaysInMonthSensor(CZSKBaseSensor):
    """Sensor for workdays in current month."""

    _attr_native_unit_of_measurement = "days"

    def __init__(self, config_entry: ConfigEntry, country: str) -> None:
        """Initialize the sensor."""
        name = "Pracovní dny v měsíci" if country == COUNTRY_CZ else "Pracovné dni v mesiaci"
        super().__init__(config_entry, "workdays_in_month", name, "mdi:calendar-month")

    @property
    def native_value(self) -> int:
        """Return remaining workdays in current month."""
        today = self.today
        _, last_day = calendar.monthrange(today.year, today.month)

        count = 0
        for day in range(today.day, last_day + 1):
            if is_workday(date(today.year, today.month, day), self._country):
                count += 1
        return count

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = super().extra_state_attributes.copy()
        today = self.today
        _, last_day = calendar.monthrange(today.year, today.month)

        total = sum(
            1 for d in range(1, last_day + 1)
            if is_workday(date(today.year, today.month, d), self._country)
        )
        elapsed = sum(
            1 for d in range(1, today.day)
            if is_workday(date(today.year, today.month, d), self._country)
        )

        attrs["total_in_month"] = total
        attrs["elapsed"] = elapsed
        attrs["month"] = today.strftime("%B")

        return attrs


class CZSKSchoolDaysInMonthSensor(CZSKBaseSensor):
    """Sensor for school days in current month."""

    _attr_native_unit_of_measurement = "days"

    def __init__(
        self, config_entry: ConfigEntry, country: str, region: str
    ) -> None:
        """Initialize the sensor."""
        name = "Školní dny v měsíci" if country == COUNTRY_CZ else "Školské dni v mesiaci"
        super().__init__(config_entry, "school_days_in_month", name, "mdi:calendar-month")

    @property
    def native_value(self) -> int:
        """Return remaining school days in current month."""
        today = self.today
        _, last_day = calendar.monthrange(today.year, today.month)

        count = 0
        for day in range(today.day, last_day + 1):
            if is_school_day(date(today.year, today.month, day), self._country, self._region):
                count += 1
        return count

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = super().extra_state_attributes.copy()
        today = self.today
        _, last_day = calendar.monthrange(today.year, today.month)

        total = sum(
            1 for d in range(1, last_day + 1)
            if is_school_day(date(today.year, today.month, d), self._country, self._region)
        )
        elapsed = sum(
            1 for d in range(1, today.day)
            if is_school_day(date(today.year, today.month, d), self._country, self._region)
        )

        attrs["total_in_month"] = total
        attrs["elapsed"] = elapsed
        attrs["month"] = today.strftime("%B")

        return attrs


class CZSKVacationProgressSensor(CZSKBaseSensor):
    """Sensor for vacation progress (when on vacation)."""

    _attr_native_unit_of_measurement = "days"

    def __init__(
        self, config_entry: ConfigEntry, country: str, region: str
    ) -> None:
        """Initialize the sensor."""
        name = "Zbývá dní prázdnin" if country == COUNTRY_CZ else "Zostáva dní prázdnin"
        super().__init__(config_entry, "vacation_remaining", name, "mdi:beach")

    @property
    def native_value(self) -> int | None:
        """Return remaining vacation days or None."""
        today = self.today
        vacation_name = get_vacation_name(today, self._country, self._region)

        if not vacation_name:
            return None

        # Find end of current vacation
        current = today
        while get_vacation_name(current, self._country, self._region) == vacation_name:
            current += timedelta(days=1)

        return (current - today).days

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = super().extra_state_attributes.copy()
        today = self.today
        vacation_name = get_vacation_name(today, self._country, self._region)

        attrs["on_vacation"] = vacation_name is not None

        if vacation_name:
            attrs["vacation_name"] = vacation_name

            # Find start
            start = today
            while get_vacation_name(start - timedelta(days=1), self._country, self._region) == vacation_name:
                start -= timedelta(days=1)

            # Find end
            end = today
            while get_vacation_name(end, self._country, self._region) == vacation_name:
                end += timedelta(days=1)
            end -= timedelta(days=1)

            total = (end - start).days + 1
            elapsed = (today - start).days

            attrs["start_date"] = start.isoformat()
            attrs["end_date"] = end.isoformat()
            attrs["total_days"] = total
            attrs["elapsed_days"] = elapsed
            attrs["progress_percent"] = round((elapsed / total) * 100, 1) if total > 0 else 0

        return attrs
