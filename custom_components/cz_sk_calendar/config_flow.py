"""Config flow for CZ/SK School & Work Calendar integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback

from .const import (
    CONF_COUNTRY,
    CONF_REGION,
    CONF_CUSTOM_BIRTHDAYS,
    CONF_CUSTOM_HOLIDAYS,
    CONF_CUSTOM_VACATIONS,
    CONF_REMINDER_DAYS,
    CONF_REMINDER_DAILY,
    COUNTRY_CZ,
    COUNTRY_SK,
    CZ_REGIONS,
    DOMAIN,
    SK_REGIONS,
)

COUNTRIES = {
    COUNTRY_CZ: "Česká republika",
    COUNTRY_SK: "Slovensko",
}


class CZSKCalendarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for CZ/SK Calendar."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._country: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - country selection."""
        if user_input is not None:
            self._country = user_input[CONF_COUNTRY]
            return await self.async_step_region()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_COUNTRY): vol.In(COUNTRIES),
                }
            ),
        )

    async def async_step_region(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the region selection step."""
        if user_input is not None:
            # Check if already configured for this country/region
            await self.async_set_unique_id(
                f"{self._country}_{user_input[CONF_REGION]}"
            )
            self._abort_if_unique_id_configured()

            region_name = (
                CZ_REGIONS.get(user_input[CONF_REGION])
                if self._country == COUNTRY_CZ
                else SK_REGIONS.get(user_input[CONF_REGION])
            )
            country_name = COUNTRIES[self._country]

            return self.async_create_entry(
                title=f"{country_name} - {region_name}",
                data={
                    CONF_COUNTRY: self._country,
                    CONF_REGION: user_input[CONF_REGION],
                },
            )

        # Select regions based on country
        regions = CZ_REGIONS if self._country == COUNTRY_CZ else SK_REGIONS

        return self.async_show_form(
            step_id="region",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REGION): vol.In(regions),
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> CZSKCalendarOptionsFlow:
        """Get the options flow for this handler."""
        return CZSKCalendarOptionsFlow()


class CZSKCalendarOptionsFlow(OptionsFlow):
    """Handle options flow for CZ/SK Calendar.

    ``self.config_entry`` is provided by the options flow manager, so the
    entry must not be passed in (and stored) by the flow itself.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        country = self.config_entry.data.get(CONF_COUNTRY, COUNTRY_CZ)
        regions = CZ_REGIONS if country == COUNTRY_CZ else SK_REGIONS
        current_region = self.config_entry.options.get(
            CONF_REGION, self.config_entry.data.get(CONF_REGION)
        )
        current_birthdays = self.config_entry.options.get(CONF_CUSTOM_BIRTHDAYS, "")
        current_holidays = self.config_entry.options.get(CONF_CUSTOM_HOLIDAYS, "")
        current_vacations = self.config_entry.options.get(CONF_CUSTOM_VACATIONS, "")
        current_reminder_days = self.config_entry.options.get(CONF_REMINDER_DAYS, 3)
        current_reminder_daily = self.config_entry.options.get(CONF_REMINDER_DAILY, True)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REGION, default=current_region): vol.In(regions),
                    vol.Optional(CONF_CUSTOM_BIRTHDAYS, default=current_birthdays): str,
                    vol.Optional(CONF_CUSTOM_HOLIDAYS, default=current_holidays): str,
                    vol.Optional(CONF_CUSTOM_VACATIONS, default=current_vacations): str,
                    vol.Optional(
                        CONF_REMINDER_DAYS,
                        default=current_reminder_days,
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=365)),
                    vol.Optional(CONF_REMINDER_DAILY, default=current_reminder_daily): bool,
                }
            ),
        )
