"""CZ/SK School & Work Calendar integration for Home Assistant."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import CONF_COUNTRY, CONF_CUSTOM_VACATIONS, COUNTRY_CZ, COUNTRY_SK, DOMAIN
from .core import (
    clear_custom_vacations,
    get_nameday,
    get_nameday_names,
    parse_custom_vacations,
    set_custom_vacations,
)
from .entity import get_configured_country, get_configured_region

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.CALENDAR]

# The integration is configured through the UI only; declaring this keeps
# Home Assistant from warning about a missing config schema.
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_GET_NAMEDAY = "get_nameday"

_GET_NAMEDAY_SCHEMA = vol.Schema(
    {
        vol.Required("date"): cv.string,
        vol.Optional("country"): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the CZ/SK Calendar integration and register services."""

    async def handle_get_nameday(call: ServiceCall) -> dict[str, Any]:
        """Return the name day(s) for an arbitrary date."""
        date_str = call.data["date"]
        try:
            check_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError as err:
            raise ServiceValidationError(
                f"Neplatný formát data: {date_str}. Použijte YYYY-MM-DD."
            ) from err

        country = call.data.get("country")
        if country:
            country = country.upper()
            if country not in (COUNTRY_CZ, COUNTRY_SK):
                raise ServiceValidationError(f"Neznáma krajina: {country}")
        else:
            entries = hass.data.get(DOMAIN, {})
            first_entry = next(iter(entries.values()), None)
            country = first_entry.get(CONF_COUNTRY, COUNTRY_CZ) if first_entry else COUNTRY_CZ

        return {
            "date": check_date.isoformat(),
            "country": country,
            "nameday": get_nameday(check_date, country),
            "names": get_nameday_names(check_date, country),
        }

    if not hass.services.has_service(DOMAIN, SERVICE_GET_NAMEDAY):
        hass.services.async_register(
            DOMAIN,
            SERVICE_GET_NAMEDAY,
            handle_get_nameday,
            schema=_GET_NAMEDAY_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up CZ/SK Calendar from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # User defined school days off (e.g. "ředitelské volno") are treated as
    # vacations, so they affect school day / vacation sensors and calendars.
    country = get_configured_country(entry)
    region = get_configured_region(entry)
    set_custom_vacations(
        country,
        region,
        parse_custom_vacations(entry.options.get(CONF_CUSTOM_VACATIONS, ""), country),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        clear_custom_vacations(
            get_configured_country(entry), get_configured_region(entry)
        )

    return unload_ok
