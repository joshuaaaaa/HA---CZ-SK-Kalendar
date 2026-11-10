"""Constants for CZ/SK School & Work Calendar integration."""
from typing import Final

DOMAIN: Final = "cz_sk_calendar"
CONF_COUNTRY: Final = "country"
CONF_REGION: Final = "region"
CONF_CUSTOM_EVENTS: Final = "custom_events"
CONF_CUSTOM_BIRTHDAYS: Final = "custom_birthdays"
CONF_CUSTOM_HOLIDAYS: Final = "custom_holidays"
CONF_CUSTOM_VACATIONS: Final = "custom_vacations"
CONF_REMINDER_DAYS: Final = "reminder_days"
CONF_REMINDER_DAILY: Final = "reminder_daily"

# Countries
COUNTRY_CZ: Final = "CZ"
COUNTRY_SK: Final = "SK"

# Czech districts (okresy) for spring vacation
# Spring vacation is determined by district, not region (kraj)
CZ_REGIONS: Final = {
    # Praha
    "praha_1_5": "Praha 1-5",
    "praha_6_10": "Praha 6-10",
    "praha_vychod": "Praha-východ",
    "praha_zapad": "Praha-západ",
    # Středočeský kraj
    "benesov": "Benešov",
    "beroun": "Beroun",
    "kladno": "Kladno",
    "kolin": "Kolín",
    "kutna_hora": "Kutná Hora",
    "melnik": "Mělník",
    "mlada_boleslav": "Mladá Boleslav",
    "nymburk": "Nymburk",
    "pribram": "Příbram",
    "rakovnik": "Rakovník",
    # Jihočeský kraj
    "ceske_budejovice": "České Budějovice",
    "cesky_krumlov": "Český Krumlov",
    "jindrichuv_hradec": "Jindřichův Hradec",
    "pisek": "Písek",
    "prachatice": "Prachatice",
    "strakonice": "Strakonice",
    "tabor": "Tábor",
    # Plzeňský kraj
    "domazlice": "Domažlice",
    "klatovy": "Klatovy",
    "plzen_mesto": "Plzeň-město",
    "plzen_jih": "Plzeň-jih",
    "plzen_sever": "Plzeň-sever",
    "rokycany": "Rokycany",
    "tachov": "Tachov",
    # Karlovarský kraj
    "cheb": "Cheb",
    "karlovy_vary": "Karlovy Vary",
    "sokolov": "Sokolov",
    # Ústecký kraj
    "decin": "Děčín",
    "chomutov": "Chomutov",
    "litomerice": "Litoměřice",
    "louny": "Louny",
    "most": "Most",
    "teplice": "Teplice",
    "usti_nad_labem": "Ústí nad Labem",
    # Liberecký kraj
    "ceska_lipa": "Česká Lípa",
    "jablonec_nad_nisou": "Jablonec nad Nisou",
    "liberec": "Liberec",
    "semily": "Semily",
    # Královéhradecký kraj
    "hradec_kralove": "Hradec Králové",
    "jicin": "Jičín",
    "nachod": "Náchod",
    "rychnov_nad_kneznou": "Rychnov nad Kněžnou",
    "trutnov": "Trutnov",
    # Pardubický kraj
    "chrudim": "Chrudim",
    "pardubice": "Pardubice",
    "svitavy": "Svitavy",
    "usti_nad_orlici": "Ústí nad Orlicí",
    # Kraj Vysočina
    "havlickuv_brod": "Havlíčkův Brod",
    "jihlava": "Jihlava",
    "pelhrimov": "Pelhřimov",
    "trebic": "Třebíč",
    "zdar_nad_sazavou": "Žďár nad Sázavou",
    # Jihomoravský kraj
    "blansko": "Blansko",
    "brno_mesto": "Brno-město",
    "brno_venkov": "Brno-venkov",
    "breclav": "Břeclav",
    "hodonin": "Hodonín",
    "vyskov": "Vyškov",
    "znojmo": "Znojmo",
    # Olomoucký kraj
    "jesenik": "Jeseník",
    "olomouc": "Olomouc",
    "prerov": "Přerov",
    "prostejov": "Prostějov",
    "sumperk": "Šumperk",
    # Zlínský kraj
    "kromeriz": "Kroměříž",
    "uherske_hradiste": "Uherské Hradiště",
    "vsetin": "Vsetín",
    "zlin": "Zlín",
    # Moravskoslezský kraj
    "bruntal": "Bruntál",
    "frydek_mistek": "Frýdek-Místek",
    "karvina": "Karviná",
    "novy_jicin": "Nový Jičín",
    "opava": "Opava",
    "ostrava_mesto": "Ostrava-město",
}

# Czech spring vacation groups (6 groups rotating)
# Based on school year 2025/2026 schedule
CZ_SPRING_GROUPS: Final = [
    # Group 1 (first week)
    [
        "chomutov", "jesenik", "jicin", "mlada_boleslav", "most", "olomouc",
        "opava", "prachatice", "pribram", "rychnov_nad_kneznou", "strakonice",
        "sumperk", "tabor", "usti_nad_labem"
    ],
    # Group 2 (second week)
    [
        "benesov", "beroun", "ceske_budejovice", "cesky_krumlov", "klatovy",
        "pardubice", "chrudim", "rokycany", "svitavy", "usti_nad_orlici",
        "ostrava_mesto", "prostejov"
    ],
    # Group 3 (third week)
    [
        "praha_1_5", "blansko", "brno_mesto", "brno_venkov", "breclav",
        "hodonin", "vyskov", "znojmo", "domazlice", "tachov", "louny", "karvina"
    ],
    # Group 4 (fourth week)
    [
        "praha_6_10", "cheb", "karlovy_vary", "sokolov", "nymburk",
        "jindrichuv_hradec", "litomerice", "decin", "prerov", "frydek_mistek"
    ],
    # Group 5 (fifth week)
    [
        "praha_vychod", "praha_zapad", "melnik", "rakovnik", "plzen_mesto",
        "plzen_jih", "plzen_sever", "hradec_kralove", "teplice", "novy_jicin",
        "uherske_hradiste", "vsetin", "zlin", "trutnov", "kromeriz"
    ],
    # Group 6 (sixth week)
    [
        "ceska_lipa", "jablonec_nad_nisou", "liberec", "semily",
        "havlickuv_brod", "jihlava", "pelhrimov", "trebic", "zdar_nad_sazavou",
        "kladno", "kolin", "kutna_hora", "pisek", "nachod", "bruntal"
    ],
]

# Slovak regions for spring vacation
SK_REGIONS: Final = {
    "bratislavsky": "Bratislavský kraj",
    "trnavsky": "Trnavský kraj",
    "nitriansky": "Nitriansky kraj",
    "trenciansky": "Trenčiansky kraj",
    "zilinsky": "Žilinský kraj",
    "banskobystricky": "Banskobystrický kraj",
    "presovsky": "Prešovský kraj",
    "kosicky": "Košický kraj",
}

# Slovak region groups for spring vacation rotation
SK_REGION_GROUPS: Final = {
    "west": ["bratislavsky", "trnavsky", "nitriansky"],
    "central": ["trenciansky", "zilinsky", "banskobystricky"],
    "east": ["presovsky", "kosicky"],
}

# Sensor types
SENSOR_TYPES: Final = {
    "workday": {
        "name": "Workday",
        "icon": "mdi:briefcase",
    },
    "school_day": {
        "name": "School Day",
        "icon": "mdi:school",
    },
    "holiday": {
        "name": "Holiday",
        "icon": "mdi:party-popper",
    },
    "vacation": {
        "name": "Vacation",
        "icon": "mdi:beach",
    },
    "vacation_name": {
        "name": "Vacation Name",
        "icon": "mdi:calendar-text",
    },
    "holiday_name": {
        "name": "Holiday Name",
        "icon": "mdi:calendar-star",
    },
    "next_vacation": {
        "name": "Next Vacation",
        "icon": "mdi:calendar-arrow-right",
    },
    "next_holiday": {
        "name": "Next Holiday",
        "icon": "mdi:calendar-arrow-right",
    },
    "days_to_vacation": {
        "name": "Days to Vacation",
        "icon": "mdi:counter",
    },
    "days_to_holiday": {
        "name": "Days to Holiday",
        "icon": "mdi:counter",
    },
}

# Calendar entity
CALENDAR_NAME: Final = "CZ/SK Calendar"
