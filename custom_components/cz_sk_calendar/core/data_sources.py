"""Data sources for CZ/SK Calendar - holidays, namedays, special days."""
from __future__ import annotations

import re
from datetime import date, timedelta
from functools import lru_cache
from typing import Optional

from ..const import COUNTRY_CZ, COUNTRY_SK
from .calculations import (
    calculate_easter_sunday,
    calc_summer_vacation,
    calc_autumn_vacation,
    calc_christmas_vacation,
    calc_semester_vacation,
    calc_spring_vacation,
    calc_easter_vacation,
    get_nth_weekday_of_month,
    get_school_year,
)


# ============================================================================
# HOLIDAYS
# ============================================================================

def _get_fixed_holidays_cz(year: int) -> dict[date, str]:
    """Get fixed holidays for Czech Republic."""
    return {
        date(year, 1, 1): "Nový rok / Den obnovy samostatného českého státu",
        date(year, 5, 1): "Svátek práce",
        date(year, 5, 8): "Den vítězství",
        date(year, 7, 5): "Den slovanských věrozvěstů Cyrila a Metoděje",
        date(year, 7, 6): "Den upálení mistra Jana Husa",
        date(year, 9, 28): "Den české státnosti",
        date(year, 10, 28): "Den vzniku samostatného československého státu",
        date(year, 11, 17): "Den boje za svobodu a demokracii",
        date(year, 12, 24): "Štědrý den",
        date(year, 12, 25): "1. svátek vánoční",
        date(year, 12, 26): "2. svátek vánoční",
    }


def _get_fixed_holidays_sk(year: int) -> dict[date, str]:
    """Get fixed holidays for Slovakia."""
    return {
        date(year, 1, 1): "Deň vzniku Slovenskej republiky",
        date(year, 1, 6): "Zjavenie Pána (Traja králi)",
        date(year, 5, 1): "Sviatok práce",
        date(year, 5, 8): "Deň víťazstva nad fašizmom",
        date(year, 7, 5): "Sviatok svätého Cyrila a Metoda",
        date(year, 8, 29): "Výročie SNP",
        date(year, 9, 1): "Deň Ústavy Slovenskej republiky",
        date(year, 9, 15): "Sedembolestná Panna Mária",
        date(year, 11, 1): "Sviatok všetkých svätých",
        date(year, 11, 17): "Deň boja za slobodu a demokraciu",
        date(year, 12, 24): "Štedrý deň",
        date(year, 12, 25): "Prvý sviatok vianočný",
        date(year, 12, 26): "Druhý sviatok vianočný",
    }


def _get_easter_holidays(year: int, country: str) -> dict[date, str]:
    """Get Easter-related holidays."""
    easter = calculate_easter_sunday(year)
    holidays = {}

    good_friday = easter - timedelta(days=2)
    if country == COUNTRY_CZ:
        holidays[good_friday] = "Velký pátek"
    else:
        holidays[good_friday] = "Veľký piatok"

    easter_monday = easter + timedelta(days=1)
    if country == COUNTRY_CZ:
        holidays[easter_monday] = "Velikonoční pondělí"
    else:
        holidays[easter_monday] = "Veľkonočný pondelok"

    return holidays


def _get_holidays_raw(year: int, country: str) -> dict[date, str]:
    """Get all holidays for a year (internal, for caching)."""
    if country == COUNTRY_CZ:
        holidays = _get_fixed_holidays_cz(year)
    else:
        holidays = _get_fixed_holidays_sk(year)
    holidays.update(_get_easter_holidays(year, country))
    return holidays


@lru_cache(maxsize=32)
def _get_holidays_cached(year: int, country: str) -> tuple[tuple[date, str], ...]:
    """Cache holidays as an immutable tuple of (date, name) pairs."""
    return tuple(sorted(_get_holidays_raw(year, country).items()))


def get_all_holidays(year: int, country: str) -> dict[date, str]:
    """Get all holidays for a given year and country.

    A fresh dict is returned on every call. Several callers merge multiple
    years into the returned value, which would otherwise grow the cached
    entry on every update.
    """
    return dict(_get_holidays_cached(year, country))


def get_holiday_name(check_date: date, country: str) -> Optional[str]:
    """Get the name of the holiday for a given date, or None."""
    holidays = get_all_holidays(check_date.year, country)
    return holidays.get(check_date)


def get_next_holiday(from_date: date, country: str) -> tuple[date, str]:
    """Get the next holiday from a given date."""
    current = from_date
    end_date = from_date + timedelta(days=730)

    while current <= end_date:
        holidays = get_all_holidays(current.year, country)
        if current in holidays:
            return current, holidays[current]
        current += timedelta(days=1)

    return from_date, "Unknown"


# ============================================================================
# VACATIONS
# ============================================================================

def _get_vacations_raw(
    school_year: int, country: str, region: str
) -> list[tuple[date, date, str]]:
    """Get all vacations for a school year (internal, for caching)."""
    vacations = []

    vacations.append(calc_autumn_vacation(school_year, country))
    vacations.append(calc_christmas_vacation(school_year, country))
    vacations.append(calc_semester_vacation(school_year, country))
    vacations.append(calc_spring_vacation(school_year, country, region))
    vacations.append(calc_easter_vacation(school_year + 1, country))
    vacations.append(calc_summer_vacation(school_year + 1, country))

    return vacations


@lru_cache(maxsize=32)
def _get_vacations_cached(
    school_year: int, country: str, region: str
) -> tuple[tuple[date, date, str], ...]:
    """Cache vacations as an immutable tuple, sorted by start date."""
    return tuple(
        sorted(_get_vacations_raw(school_year, country, region), key=lambda x: x[0])
    )


# ----------------------------------------------------------------------------
# Custom (user defined) school days off, e.g. "ředitelské volno"
# ----------------------------------------------------------------------------

# Keyed by (country, region) - a config entry is unique per country/region.
_CUSTOM_VACATIONS: dict[tuple[str, str], tuple[tuple[date, date, str], ...]] = {}

_DATE_PATTERN = r"(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}\.\s*\d{1,2}\.\s*\d{4})"
_CUSTOM_VACATION_RE = re.compile(
    rf"(?P<start>{_DATE_PATTERN})"
    rf"(?:\s*(?:-|–|—|\.\.|až|az|do)\s*(?P<end>{_DATE_PATTERN}))?"
)
_NAME_STRIP_CHARS = " \t\r\n|;,:-–—"


def _parse_vacation_date(value: str) -> date | None:
    """Parse YYYY-MM-DD or DD.MM.YYYY into a date."""
    value = value.replace(" ", "")
    try:
        if "." in value:
            day, month, year = (int(p) for p in value.split("."))
        else:
            year, month, day = (int(p) for p in value.split("-"))
        return date(year, month, day)
    except ValueError:
        return None


def default_custom_vacation_name(country: str) -> str:
    """Name used when a custom day off has no name."""
    return "Ředitelské volno" if country == COUNTRY_CZ else "Riaditeľské voľno"


def parse_custom_vacations(raw: str, country: str) -> list[tuple[date, date, str]]:
    """Parse user defined school days off.

    Every entry starts with a date or a date range and may be followed by a
    name (a default "ředitelské volno" name is used otherwise):
      - ``2026-11-16 | Ředitelské volno``
      - ``2026-11-16 - 2026-11-17 | Ředitelské volno``
      - ``16.11.2026 - 17.11.2026 Ředitelské volno``
    Several entries can be on one line; the next date starts a new entry.
    """
    if not raw:
        return []

    matches = list(_CUSTOM_VACATION_RE.finditer(raw))
    result: list[tuple[date, date, str]] = []
    for index, match in enumerate(matches):
        start = _parse_vacation_date(match.group("start"))
        end = _parse_vacation_date(match.group("end")) if match.group("end") else start
        if start is None or end is None:
            continue
        if end < start:
            start, end = end, start
        name_end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        name = raw[match.end():name_end].strip(_NAME_STRIP_CHARS)
        result.append((start, end, name or default_custom_vacation_name(country)))

    return result


def set_custom_vacations(
    country: str, region: str, vacations: list[tuple[date, date, str]]
) -> None:
    """Register user defined days off for a country/region."""
    key = (country, region)
    if vacations:
        _CUSTOM_VACATIONS[key] = tuple(sorted(vacations, key=lambda x: x[0]))
    else:
        _CUSTOM_VACATIONS.pop(key, None)


def clear_custom_vacations(country: str, region: str) -> None:
    """Remove user defined days off for a country/region."""
    _CUSTOM_VACATIONS.pop((country, region), None)


def get_all_vacations(
    school_year: int, country: str, region: str
) -> list[tuple[date, date, str]]:
    """Get all school vacations for a school year.

    Includes user defined days off (e.g. "ředitelské volno") whose start
    falls into the school year.

    A fresh list is returned on every call. Several callers extend the
    returned value with another school year, which would otherwise append to
    the cached entry over and over on every update.
    """
    vacations = list(_get_vacations_cached(school_year, country, region))
    custom = [
        vac
        for vac in _CUSTOM_VACATIONS.get((country, region), ())
        if get_school_year(vac[0]) == school_year
    ]
    if custom:
        vacations.extend(custom)
        vacations.sort(key=lambda x: x[0])
    return vacations


def get_vacation_name(check_date: date, country: str, region: str) -> Optional[str]:
    """Get the name of the vacation for a given date, or None."""
    school_year = get_school_year(check_date)

    for start, end, name in get_all_vacations(school_year, country, region):
        if start <= check_date <= end:
            return name

    if check_date.month <= 8:
        for start, end, name in get_all_vacations(school_year - 1, country, region):
            if start <= check_date <= end:
                return name

    return None


def get_next_vacation(
    from_date: date, country: str, region: str
) -> tuple[date, str, date]:
    """Get the next vacation from a given date. Returns (start, name, end)."""
    school_year = get_school_year(from_date)

    all_vacations = []
    all_vacations.extend(get_all_vacations(school_year, country, region))
    all_vacations.extend(get_all_vacations(school_year + 1, country, region))

    all_vacations.sort(key=lambda x: x[0])

    for start, end, name in all_vacations:
        if start > from_date:
            return start, name, end

    return from_date, "Unknown", from_date


# ============================================================================
# SPECIAL DAYS
# ============================================================================

def _get_special_days_cz(year: int) -> dict[date, str]:
    """Get special days for Czech Republic."""
    special_days = {
        date(year, 1, 6): "Tři králové",
        date(year, 2, 14): "Valentýn",
        date(year, 3, 8): "Mezinárodní den žen",
        date(year, 3, 28): "Den učitelů",
        date(year, 4, 1): "Apríl",
        date(year, 4, 22): "Den Země",
        date(year, 6, 1): "Mezinárodní den dětí",
        date(year, 9, 1): "Začátek školního roku",
        date(year, 10, 31): "Halloween",
        date(year, 11, 2): "Dušičky",
        date(year, 12, 5): "Mikuláš (předvečer)",
        date(year, 12, 6): "Mikuláš",
        date(year, 12, 31): "Silvestr",
    }

    # Mother's Day - second Sunday of May
    special_days[get_nth_weekday_of_month(year, 5, 6, 2)] = "Den matek"
    # Father's Day - third Sunday of June
    special_days[get_nth_weekday_of_month(year, 6, 6, 3)] = "Den otců"

    return special_days


def _get_special_days_sk(year: int) -> dict[date, str]:
    """Get special days for Slovakia."""
    special_days = {
        date(year, 1, 6): "Traja králi",
        date(year, 2, 14): "Valentín",
        date(year, 3, 8): "Medzinárodný deň žien",
        date(year, 3, 28): "Deň učiteľov",
        date(year, 4, 1): "Apríl",
        date(year, 4, 22): "Deň Zeme",
        date(year, 6, 1): "Medzinárodný deň detí",
        date(year, 9, 2): "Začiatok školského roka",
        date(year, 10, 31): "Halloween",
        date(year, 11, 2): "Pamiatka zosnulých",
        date(year, 12, 5): "Mikuláš (predvečer)",
        date(year, 12, 6): "Mikuláš",
        date(year, 12, 31): "Silvester",
    }

    special_days[get_nth_weekday_of_month(year, 5, 6, 2)] = "Deň matiek"
    special_days[get_nth_weekday_of_month(year, 6, 6, 3)] = "Deň otcov"

    return special_days


@lru_cache(maxsize=16)
def _get_special_days_cached(year: int, country: str) -> tuple[tuple[date, str], ...]:
    """Cache special days as an immutable tuple of (date, name) pairs."""
    if country == COUNTRY_CZ:
        special_days = _get_special_days_cz(year)
    else:
        special_days = _get_special_days_sk(year)
    return tuple(sorted(special_days.items()))


def get_all_special_days(year: int, country: str) -> dict[date, str]:
    """Get all special days for a given year and country.

    A fresh dict is returned on every call so callers may mutate it safely.
    """
    return dict(_get_special_days_cached(year, country))


def get_special_day_name(check_date: date, country: str) -> Optional[str]:
    """Get the name of the special day for a given date, or None."""
    return get_all_special_days(check_date.year, country).get(check_date)


def get_next_special_day(from_date: date, country: str) -> tuple[date, str]:
    """Get the next special day from a given date."""
    current = from_date
    end_date = from_date + timedelta(days=400)

    while current <= end_date:
        special_days = get_all_special_days(current.year, country)
        if current in special_days:
            return current, special_days[current]
        current += timedelta(days=1)

    return from_date, "Unknown"


# ============================================================================
# NAME DAYS
# ============================================================================

# Czech name days - official Czech calendar (abbreviated for brevity)
_NAMEDAYS_CZ: dict[tuple[int, int], str] = {
    (1, 1): "Nový rok", (1, 2): "Karina", (1, 3): "Radmila", (1, 4): "Diana",
    (1, 5): "Dalimil", (1, 6): "Tři králové", (1, 7): "Vilma", (1, 8): "Čestmír",
    (1, 9): "Vladan", (1, 10): "Břetislav", (1, 11): "Bohdana", (1, 12): "Pravoslav",
    (1, 13): "Edita", (1, 14): "Radovan", (1, 15): "Alice", (1, 16): "Ctirad",
    (1, 17): "Drahoslav", (1, 18): "Vladislav", (1, 19): "Doubravka", (1, 20): "Ilona",
    (1, 21): "Běla", (1, 22): "Slavomír", (1, 23): "Zdeněk", (1, 24): "Milena",
    (1, 25): "Miloš", (1, 26): "Zora", (1, 27): "Ingrid", (1, 28): "Otýlie",
    (1, 29): "Zdislava", (1, 30): "Robin", (1, 31): "Marika",
    (2, 1): "Hynek", (2, 2): "Nela", (2, 3): "Blažej", (2, 4): "Jarmila",
    (2, 5): "Dobromila", (2, 6): "Vanda", (2, 7): "Veronika", (2, 8): "Milada",
    (2, 9): "Apolena", (2, 10): "Mojmír", (2, 11): "Božena", (2, 12): "Slavěna",
    (2, 13): "Věnceslav", (2, 14): "Valentýn", (2, 15): "Jiřina", (2, 16): "Ljuba",
    (2, 17): "Miloslava", (2, 18): "Gizela", (2, 19): "Patrik", (2, 20): "Oldřich",
    (2, 21): "Lenka", (2, 22): "Petr", (2, 23): "Svatopluk", (2, 24): "Matěj",
    (2, 25): "Liliana", (2, 26): "Dorota", (2, 27): "Alexandr", (2, 28): "Lumír",
    (2, 29): "Horymír",
    (3, 1): "Bedřich", (3, 2): "Anežka", (3, 3): "Kamil", (3, 4): "Stela",
    (3, 5): "Kazimír", (3, 6): "Miroslav", (3, 7): "Tomáš", (3, 8): "Gabriela",
    (3, 9): "Františka", (3, 10): "Viktorie", (3, 11): "Anděla", (3, 12): "Řehoř",
    (3, 13): "Růžena", (3, 14): "Rút, Matylda", (3, 15): "Ida", (3, 16): "Elena, Herbert",
    (3, 17): "Vlastimil", (3, 18): "Eduard", (3, 19): "Josef", (3, 20): "Světlana",
    (3, 21): "Radek", (3, 22): "Leona", (3, 23): "Ivona", (3, 24): "Gabriel",
    (3, 25): "Marián", (3, 26): "Emanuel", (3, 27): "Dita", (3, 28): "Soňa",
    (3, 29): "Taťána", (3, 30): "Arnošt", (3, 31): "Kvido",
    (4, 1): "Hugo", (4, 2): "Erika", (4, 3): "Richard", (4, 4): "Ivana",
    (4, 5): "Miroslava", (4, 6): "Vendula", (4, 7): "Heřman, Hermína", (4, 8): "Ema",
    (4, 9): "Dušan", (4, 10): "Darja", (4, 11): "Izabela", (4, 12): "Julius",
    (4, 13): "Aleš", (4, 14): "Vincenc", (4, 15): "Anastázie", (4, 16): "Irena",
    (4, 17): "Rudolf", (4, 18): "Valérie", (4, 19): "Rostislav", (4, 20): "Marcela",
    (4, 21): "Alexandra", (4, 22): "Evženie", (4, 23): "Vojtěch", (4, 24): "Jiří",
    (4, 25): "Marek", (4, 26): "Oto", (4, 27): "Jaroslav", (4, 28): "Vlastislav",
    (4, 29): "Robert", (4, 30): "Blahoslav",
    (5, 1): "Svátek práce", (5, 2): "Zikmund", (5, 3): "Alexej", (5, 4): "Květoslav",
    (5, 5): "Klaudie", (5, 6): "Radoslav", (5, 7): "Stanislav", (5, 8): "Den vítězství",
    (5, 9): "Ctibor", (5, 10): "Blažena", (5, 11): "Svatava", (5, 12): "Pankrác",
    (5, 13): "Servác", (5, 14): "Bonifác", (5, 15): "Žofie", (5, 16): "Přemysl",
    (5, 17): "Aneta", (5, 18): "Nataša", (5, 19): "Ivo", (5, 20): "Zbyšek",
    (5, 21): "Monika", (5, 22): "Emil", (5, 23): "Vladimír", (5, 24): "Jana",
    (5, 25): "Viola", (5, 26): "Filip", (5, 27): "Valdemar", (5, 28): "Vilém",
    (5, 29): "Maxmilián", (5, 30): "Ferdinand", (5, 31): "Kamila",
    (6, 1): "Laura", (6, 2): "Jarmil", (6, 3): "Tamara", (6, 4): "Dalibor",
    (6, 5): "Dobroslav", (6, 6): "Norbert", (6, 7): "Iveta, Slavoj", (6, 8): "Medard",
    (6, 9): "Stanislava", (6, 10): "Gita", (6, 11): "Bruno", (6, 12): "Antonie",
    (6, 13): "Antonín", (6, 14): "Roland", (6, 15): "Vít", (6, 16): "Zbyněk",
    (6, 17): "Adolf", (6, 18): "Milan", (6, 19): "Leoš", (6, 20): "Květa",
    (6, 21): "Alois", (6, 22): "Pavla", (6, 23): "Zdeňka", (6, 24): "Jan",
    (6, 25): "Ivan", (6, 26): "Adriana", (6, 27): "Ladislav", (6, 28): "Lubomír",
    (6, 29): "Petr a Pavel", (6, 30): "Šárka",
    (7, 1): "Jaroslava", (7, 2): "Patricie", (7, 3): "Radomír", (7, 4): "Prokop",
    (7, 5): "Cyril a Metoděj", (7, 6): "Den upálení M. J. Husa", (7, 7): "Bohuslava",
    (7, 8): "Nora", (7, 9): "Drahoslava", (7, 10): "Libuše, Amálie", (7, 11): "Olga",
    (7, 12): "Bořek", (7, 13): "Markéta", (7, 14): "Karolína", (7, 15): "Jindřich",
    (7, 16): "Luboš", (7, 17): "Martina", (7, 18): "Drahomíra", (7, 19): "Čeněk",
    (7, 20): "Ilja", (7, 21): "Vítězslav", (7, 22): "Magdaléna", (7, 23): "Libor",
    (7, 24): "Kristýna", (7, 25): "Jakub", (7, 26): "Anna", (7, 27): "Věroslav",
    (7, 28): "Viktor", (7, 29): "Marta", (7, 30): "Bořivoj", (7, 31): "Ignác",
    (8, 1): "Oskar", (8, 2): "Gustav", (8, 3): "Miluše", (8, 4): "Dominik",
    (8, 5): "Kristian", (8, 6): "Oldřiška", (8, 7): "Lada", (8, 8): "Soběslav",
    (8, 9): "Roman", (8, 10): "Vavřinec", (8, 11): "Zuzana", (8, 12): "Klára",
    (8, 13): "Alena", (8, 14): "Alan", (8, 15): "Hana", (8, 16): "Jáchym",
    (8, 17): "Petra", (8, 18): "Helena", (8, 19): "Ludvík", (8, 20): "Bernard",
    (8, 21): "Johana", (8, 22): "Bohuslav", (8, 23): "Sandra", (8, 24): "Bartoloměj",
    (8, 25): "Radim", (8, 26): "Luděk", (8, 27): "Otakar", (8, 28): "Augustýn",
    (8, 29): "Evelína", (8, 30): "Vladěna", (8, 31): "Pavlína",
    (9, 1): "Linda, Samuel", (9, 2): "Adéla", (9, 3): "Bronislav", (9, 4): "Jindřiška",
    (9, 5): "Boris", (9, 6): "Boleslav", (9, 7): "Regína", (9, 8): "Mariana",
    (9, 9): "Daniela", (9, 10): "Irma", (9, 11): "Denisa", (9, 12): "Marie",
    (9, 13): "Lubor", (9, 14): "Radka", (9, 15): "Jolana", (9, 16): "Ludmila",
    (9, 17): "Naděžda", (9, 18): "Kryštof", (9, 19): "Zita", (9, 20): "Oleg",
    (9, 21): "Matouš", (9, 22): "Darina", (9, 23): "Berta", (9, 24): "Jaromír",
    (9, 25): "Zlata", (9, 26): "Andrea", (9, 27): "Jonáš", (9, 28): "Václav",
    (9, 29): "Michal", (9, 30): "Jeroným",
    (10, 1): "Igor", (10, 2): "Olívie, Oliver", (10, 3): "Bohumil", (10, 4): "František",
    (10, 5): "Eliška", (10, 6): "Hanuš", (10, 7): "Justýna", (10, 8): "Věra",
    (10, 9): "Štefan, Sára", (10, 10): "Marina", (10, 11): "Andrej", (10, 12): "Marcel",
    (10, 13): "Renáta", (10, 14): "Agáta", (10, 15): "Tereza", (10, 16): "Havel",
    (10, 17): "Hedvika", (10, 18): "Lukáš", (10, 19): "Michaela", (10, 20): "Vendelín",
    (10, 21): "Brigita", (10, 22): "Sabina", (10, 23): "Teodor", (10, 24): "Nina",
    (10, 25): "Beáta", (10, 26): "Erik", (10, 27): "Šarlota, Zoe", (10, 28): "Den vzniku ČSR",
    (10, 29): "Silvie", (10, 30): "Tadeáš", (10, 31): "Štěpánka",
    (11, 1): "Felix", (11, 2): "Památka zesnulých", (11, 3): "Hubert", (11, 4): "Karel",
    (11, 5): "Miriam", (11, 6): "Liběna", (11, 7): "Saskie", (11, 8): "Bohumír",
    (11, 9): "Bohdan", (11, 10): "Evžen", (11, 11): "Martin", (11, 12): "Benedikt",
    (11, 13): "Tibor", (11, 14): "Sáva", (11, 15): "Leopold", (11, 16): "Otmar",
    (11, 17): "Den boje za svobodu", (11, 18): "Romana", (11, 19): "Alžběta",
    (11, 20): "Nikola", (11, 21): "Albert", (11, 22): "Cecílie", (11, 23): "Klement",
    (11, 24): "Emílie", (11, 25): "Kateřina", (11, 26): "Artur", (11, 27): "Xenie",
    (11, 28): "René", (11, 29): "Zina", (11, 30): "Ondřej",
    (12, 1): "Iva", (12, 2): "Blanka", (12, 3): "Svatoslav", (12, 4): "Barbora",
    (12, 5): "Jitka", (12, 6): "Mikuláš", (12, 7): "Ambrož", (12, 8): "Květoslava",
    (12, 9): "Vratislav", (12, 10): "Julie", (12, 11): "Dana", (12, 12): "Simona",
    (12, 13): "Lucie", (12, 14): "Lýdie", (12, 15): "Radana", (12, 16): "Albína",
    (12, 17): "Daniel", (12, 18): "Miloslav", (12, 19): "Ester", (12, 20): "Dagmar",
    (12, 21): "Natálie", (12, 22): "Šimon", (12, 23): "Vlasta", (12, 24): "Adam a Eva",
    (12, 25): "1. svátek vánoční", (12, 26): "Štěpán", (12, 27): "Žaneta",
    (12, 28): "Bohumila", (12, 29): "Judita", (12, 30): "David", (12, 31): "Silvestr",
}

# Slovak name days - official Slovak calendar.
# Days with more than one name list them all, comma separated
# (e.g. 2. 9. is "Linda, Rebeka"), matching the published Slovak calendar.
_NAMEDAYS_SK: dict[tuple[int, int], str] = {
    (1, 1): "Nový rok", (1, 2): "Alexandra, Karina", (1, 3): "Daniela", (1, 4): "Drahoslav",
    (1, 5): "Andrea", (1, 6): "Antónia", (1, 7): "Bohuslava", (1, 8): "Severín",
    (1, 9): "Alexej", (1, 10): "Dáša", (1, 11): "Malvína", (1, 12): "Ernest",
    (1, 13): "Rastislav", (1, 14): "Radovan", (1, 15): "Dobroslav, Dobroslava", (1, 16): "Kristína",
    (1, 17): "Nataša", (1, 18): "Bohdana", (1, 19): "Drahomíra, Mário", (1, 20): "Dalibor",
    (1, 21): "Vincent", (1, 22): "Zora", (1, 23): "Miloš", (1, 24): "Timotej",
    (1, 25): "Gejza", (1, 26): "Tamara", (1, 27): "Bohuš", (1, 28): "Alfonz",
    (1, 29): "Gašpar", (1, 30): "Ema", (1, 31): "Emil",
    (2, 1): "Tatiana", (2, 2): "Erika, Erik", (2, 3): "Blažej", (2, 4): "Veronika",
    (2, 5): "Agáta", (2, 6): "Dorota", (2, 7): "Vanda", (2, 8): "Zoja",
    (2, 9): "Zdenko", (2, 10): "Gabriela", (2, 11): "Dezider", (2, 12): "Perla",
    (2, 13): "Arpád", (2, 14): "Valentín", (2, 15): "Pravoslav", (2, 16): "Ida, Liana",
    (2, 17): "Miloslava", (2, 18): "Jaromír", (2, 19): "Vlasta", (2, 20): "Lívia",
    (2, 21): "Eleonóra", (2, 22): "Etela", (2, 23): "Roman, Romana", (2, 24): "Matej",
    (2, 25): "Frederik, Frederika", (2, 26): "Viktor", (2, 27): "Alexander",
    (2, 28): "Zlatica", (2, 29): "Radomír",
    (3, 1): "Albín", (3, 2): "Anežka", (3, 3): "Bohumil, Bohumila", (3, 4): "Kazimír",
    (3, 5): "Fridrich", (3, 6): "Radoslav, Radoslava", (3, 7): "Tomáš", (3, 8): "Alan, Alana",
    (3, 9): "Františka", (3, 10): "Branislav, Bruno", (3, 11): "Angela, Angelika",
    (3, 12): "Gregor", (3, 13): "Vlastimil", (3, 14): "Matilda", (3, 15): "Svetlana",
    (3, 16): "Boleslav", (3, 17): "Ľubica", (3, 18): "Eduard", (3, 19): "Jozef",
    (3, 20): "Víťazoslav", (3, 21): "Blahoslav", (3, 22): "Beňadik", (3, 23): "Adrián",
    (3, 24): "Gabriel", (3, 25): "Marián", (3, 26): "Emanuel", (3, 27): "Alena",
    (3, 28): "Soňa", (3, 29): "Miroslav", (3, 30): "Vieroslava", (3, 31): "Benjamín",
    (4, 1): "Hugo", (4, 2): "Zita", (4, 3): "Richard", (4, 4): "Izidor",
    (4, 5): "Miroslava", (4, 6): "Irena", (4, 7): "Zoltán", (4, 8): "Albert",
    (4, 9): "Milena", (4, 10): "Igor", (4, 11): "Július", (4, 12): "Estera",
    (4, 13): "Aleš", (4, 14): "Justína", (4, 15): "Fedor", (4, 16): "Dana, Danica",
    (4, 17): "Rudolf, Rudolfa", (4, 18): "Valér", (4, 19): "Jela", (4, 20): "Marcel",
    (4, 21): "Ervín", (4, 22): "Slavomír", (4, 23): "Vojtech", (4, 24): "Juraj",
    (4, 25): "Marek", (4, 26): "Jaroslava", (4, 27): "Jaroslav", (4, 28): "Jarmila",
    (4, 29): "Lea", (4, 30): "Anastázia",
    (5, 1): "Sviatok práce", (5, 2): "Žigmund", (5, 3): "Galina, Timea", (5, 4): "Florián",
    (5, 5): "Lesana, Lesia", (5, 6): "Hermína", (5, 7): "Monika", (5, 8): "Ingrida",
    (5, 9): "Roland", (5, 10): "Viktória", (5, 11): "Blažena", (5, 12): "Pankrác",
    (5, 13): "Servác", (5, 14): "Bonifác", (5, 15): "Žofia, Sofia", (5, 16): "Svetozár",
    (5, 17): "Gizela", (5, 18): "Viola", (5, 19): "Gertrúda", (5, 20): "Bernard",
    (5, 21): "Zina", (5, 22): "Júlia, Juliana", (5, 23): "Želmíra", (5, 24): "Ela",
    (5, 25): "Urban", (5, 26): "Dušan", (5, 27): "Iveta", (5, 28): "Viliam",
    (5, 29): "Vilma", (5, 30): "Ferdinand", (5, 31): "Petronela, Petrana",
    (6, 1): "Žaneta", (6, 2): "Xénia, Oxana", (6, 3): "Karolína", (6, 4): "Lenka",
    (6, 5): "Laura", (6, 6): "Norbert", (6, 7): "Róbert", (6, 8): "Medard",
    (6, 9): "Stanislava", (6, 10): "Margaréta", (6, 11): "Dobroslava", (6, 12): "Zlatko",
    (6, 13): "Anton", (6, 14): "Vasil", (6, 15): "Vít", (6, 16): "Blanka, Bianka",
    (6, 17): "Adolf", (6, 18): "Vratislav", (6, 19): "Alfréd", (6, 20): "Valéria",
    (6, 21): "Alojz", (6, 22): "Paulína", (6, 23): "Sidónia", (6, 24): "Ján",
    (6, 25): "Tadeáš, Olívia", (6, 26): "Adriána", (6, 27): "Ladislav, Ladislava", (6, 28): "Beáta",
    (6, 29): "Peter, Pavol, Petra", (6, 30): "Melánia",
    (7, 1): "Diana", (7, 2): "Berta", (7, 3): "Miloslav", (7, 4): "Prokop",
    (7, 5): "Cyril, Metod", (7, 6): "Patrik, Patrícia", (7, 7): "Oliver", (7, 8): "Ivan",
    (7, 9): "Lujza", (7, 10): "Amália", (7, 11): "Milota", (7, 12): "Nina",
    (7, 13): "Margita", (7, 14): "Kamil", (7, 15): "Henrich", (7, 16): "Drahomír",
    (7, 17): "Bohuslav", (7, 18): "Kamila", (7, 19): "Dušana", (7, 20): "Iľja, Eliáš",
    (7, 21): "Daniel", (7, 22): "Magdaléna", (7, 23): "Oľga", (7, 24): "Vladimír",
    (7, 25): "Jakub, Timur", (7, 26): "Anna, Hana", (7, 27): "Božena", (7, 28): "Krištof",
    (7, 29): "Marta", (7, 30): "Libuša", (7, 31): "Ignác",
    (8, 1): "Božidara", (8, 2): "Gustáv", (8, 3): "Jerguš", (8, 4): "Dominik, Dominika",
    (8, 5): "Hortenzia", (8, 6): "Jozefína", (8, 7): "Štefánia", (8, 8): "Oskar",
    (8, 9): "Ľubomíra", (8, 10): "Vavrinec", (8, 11): "Zuzana", (8, 12): "Darina",
    (8, 13): "Ľubomír", (8, 14): "Mojmír", (8, 15): "Marcela", (8, 16): "Leonard",
    (8, 17): "Milica", (8, 18): "Elena, Helena", (8, 19): "Lýdia", (8, 20): "Anabela, Liliana",
    (8, 21): "Jana", (8, 22): "Tichomír", (8, 23): "Filip", (8, 24): "Bartolomej",
    (8, 25): "Ľudovít", (8, 26): "Samuel", (8, 27): "Silvia", (8, 28): "Augustín",
    (8, 29): "Nikola, Nikolaj", (8, 30): "Ružena", (8, 31): "Nora",
    (9, 1): "Drahoslava", (9, 2): "Linda, Rebeka", (9, 3): "Belo", (9, 4): "Rozália",
    (9, 5): "Regina", (9, 6): "Alica", (9, 7): "Marianna", (9, 8): "Miriama",
    (9, 9): "Martina", (9, 10): "Oleg", (9, 11): "Bystrík", (9, 12): "Mária",
    (9, 13): "Ctibor", (9, 14): "Ľudomil", (9, 15): "Jolana", (9, 16): "Ľudmila",
    (9, 17): "Olympia", (9, 18): "Eugénia", (9, 19): "Konštantín", (9, 20): "Ľuboslav, Ľuboslava",
    (9, 21): "Matúš", (9, 22): "Móric", (9, 23): "Zdenka", (9, 24): "Ľuboš, Ľubor",
    (9, 25): "Vladislav, Vladislava", (9, 26): "Edita", (9, 27): "Cyprián", (9, 28): "Václav",
    (9, 29): "Michal, Michaela", (9, 30): "Jarolím",
    (10, 1): "Arnold", (10, 2): "Levoslav", (10, 3): "Stela", (10, 4): "František",
    (10, 5): "Viera", (10, 6): "Natália", (10, 7): "Eliška", (10, 8): "Brigita",
    (10, 9): "Dionýz", (10, 10): "Slavomíra", (10, 11): "Valentína", (10, 12): "Maximilián",
    (10, 13): "Koloman", (10, 14): "Boris", (10, 15): "Terézia", (10, 16): "Vladimíra",
    (10, 17): "Hedviga", (10, 18): "Lukáš", (10, 19): "Kristián", (10, 20): "Vendelín",
    (10, 21): "Uršuľa", (10, 22): "Sergej", (10, 23): "Alojzia", (10, 24): "Kvetoslava",
    (10, 25): "Aurel", (10, 26): "Demeter", (10, 27): "Sabína", (10, 28): "Dobromila",
    (10, 29): "Klára", (10, 30): "Šimon, Simona", (10, 31): "Aurélia",
    (11, 1): "Denis, Denisa", (11, 2): "Pamiatka zosnulých", (11, 3): "Hubert",
    (11, 4): "Karol", (11, 5): "Imrich", (11, 6): "Renáta", (11, 7): "René",
    (11, 8): "Bohumír", (11, 9): "Teodor", (11, 10): "Tibor", (11, 11): "Martin, Maroš",
    (11, 12): "Svätopluk", (11, 13): "Stanislav", (11, 14): "Irma", (11, 15): "Leopold",
    (11, 16): "Agnesa", (11, 17): "Klaudia", (11, 18): "Eugen", (11, 19): "Alžbeta",
    (11, 20): "Félix", (11, 21): "Elvíra", (11, 22): "Cecília", (11, 23): "Klement",
    (11, 24): "Emília", (11, 25): "Katarína", (11, 26): "Kornel", (11, 27): "Milan",
    (11, 28): "Henrieta", (11, 29): "Vratko", (11, 30): "Ondrej, Andrej",
    (12, 1): "Edmund", (12, 2): "Bibiána", (12, 3): "Oldrich", (12, 4): "Barbora, Barbara",
    (12, 5): "Oto", (12, 6): "Mikuláš", (12, 7): "Ambróz", (12, 8): "Marína",
    (12, 9): "Izabela", (12, 10): "Radúz", (12, 11): "Hilda", (12, 12): "Otília",
    (12, 13): "Lucia", (12, 14): "Branislava, Bronislava", (12, 15): "Ivica",
    (12, 16): "Albína", (12, 17): "Kornélia", (12, 18): "Sláva, Slávka", (12, 19): "Judita",
    (12, 20): "Dagmara", (12, 21): "Bohdan", (12, 22): "Adela", (12, 23): "Nadežda",
    (12, 24): "Adam, Eva", (12, 25): "1. sviatok vianočný", (12, 26): "Štefan",
    (12, 27): "Filoména", (12, 28): "Ivana, Ivona", (12, 29): "Milada", (12, 30): "Dávid",
    (12, 31): "Silvester",
}


def get_nameday(check_date: date, country: str) -> Optional[str]:
    """Get the name day for a given date and country."""
    key = (check_date.month, check_date.day)
    namedays = _NAMEDAYS_CZ if country == COUNTRY_CZ else _NAMEDAYS_SK
    return namedays.get(key)


def get_nameday_names(check_date: date, country: str) -> list[str]:
    """Get all names celebrating their name day on a given date.

    The Slovak calendar in particular has several days shared by two or more
    names (2. 9. is "Linda, Rebeka"), so return them as a list rather than a
    single string.

    Args:
        check_date: Date to check
        country: Country code (CZ or SK)

    Returns:
        List of names, empty when the date carries no name
    """
    nameday = get_nameday(check_date, country)
    if not nameday:
        return []
    return [name.strip() for name in nameday.split(",") if name.strip()]


def get_namedays_in_week(from_date: date, country: str) -> dict[date, str]:
    """Get all name days for the week starting from the given date."""
    result = {}
    for i in range(7):
        check_date = from_date + timedelta(days=i)
        nameday = get_nameday(check_date, country)
        if nameday:
            result[check_date] = nameday
    return result
