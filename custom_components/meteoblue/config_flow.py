# Copyright 2026 Dan Keder
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This file includes code modified from
# https://github.com/ludeeus/integration_blueprint/, which is licensed under
# the MIT License.
#
"""Config flow for MeteoBlue."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

import httpx
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigSubentryFlow, SubentryFlowResult
from homeassistant.const import (
    CONF_API_KEY,
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
)
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.loader import async_get_loaded_integration
from homeassistant.util import slugify

from .api import (
    MeteoBlueApiClient,
    MeteoBlueApiClientAuthenticationError,
    MeteoBlueApiClientCommunicationError,
    MeteoBlueApiClientError,
)
from .const import (
    CONF_ENABLE_FORECAST,
    CONF_ENABLE_METEOGRAM,
    CONF_FORECAST_TYPE,
    CONF_FORECAST_UPDATE_INTERVAL,
    CONF_LOCATION_MODE,
    CONF_METEOGRAM_UPDATE_INTERVAL,
    DOMAIN,
    FORECAST_TYPE_DAILY,
    FORECAST_TYPE_HOURLY,
    LOCATION_MODE_AUTO,
    LOCATION_MODE_CUSTOM,
    LOGGER,
    SUBENTRY_TYPE_FORECAST_LOCATION,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry


# According to MeteoBlue documentation, forecast models run 2x per day. Because
# of this it doesn't make sense to use very frequent updates.
# Source: https://content.meteoblue.com/en/research-education/specifications/processes/updating
MIN_UPDATE_INTERVAL = timedelta(hours=6)
DEFAULT_FORECAST_UPDATE_INTERVAL: dict[str, int] = {
    "hours": 12,
    "minutes": 0,
    "seconds": 0,
}
DEFAULT_METEOGRAM_UPDATE_INTERVAL: dict[str, int] = {
    "hours": 24,
    "minutes": 0,
    "seconds": 0,
}


def _duration_to_timedelta(value: Any) -> timedelta:
    """Convert a DurationSelector result to a timedelta."""
    if isinstance(value, timedelta):
        return value
    return timedelta(
        hours=value.get("hours", 0),
        minutes=value.get("minutes", 0),
        seconds=value.get("seconds", 0),
    )


class MeteoBlueFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for a MeteoBlue API key."""

    VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls,
        config_entry: ConfigEntry,  # noqa: ARG003
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the supported subentry types for this integration."""
        return {SUBENTRY_TYPE_FORECAST_LOCATION: ForecastLocationSubentryFlowHandler}

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            await self.async_set_unique_id(slugify(api_key))
            self._abort_if_unique_id_configured()
            try:
                await self._test_credentials(api_key=api_key)
            except MeteoBlueApiClientAuthenticationError as exception:
                LOGGER.warning(exception)
                errors["base"] = "auth"
            except MeteoBlueApiClientCommunicationError as exception:
                LOGGER.error(exception)
                errors["base"] = "connection"
            except MeteoBlueApiClientError as exception:
                LOGGER.exception(exception)
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_NAME: user_input[CONF_NAME],
                        CONF_API_KEY: api_key,
                    },
                )

        integration = async_get_loaded_integration(self.hass, DOMAIN)
        assert integration.documentation is not None, (  # noqa: S101
            "Integration documentation URL is not set in manifest.json"
        )
        return self.async_show_form(
            step_id="user",
            description_placeholders={
                "documentation_url": integration.documentation,
            },
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME,
                        default=(user_input or {}).get(CONF_NAME, vol.UNDEFINED),
                    ): selector.TextSelector(),
                    vol.Required(
                        CONF_API_KEY,
                        default=(user_input or {}).get(CONF_API_KEY, vol.UNDEFINED),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        ),
                    ),
                },
            ),
            errors=errors,
        )

    async def _test_credentials(self, api_key: str) -> None:
        """Validate credentials via the MeteoBlue Account API."""
        async with httpx.AsyncClient() as http_client:
            client = MeteoBlueApiClient(
                client=http_client,
                api_key=api_key,
            )
            await client.async_get_account_usage()


class ForecastLocationSubentryFlowHandler(ConfigSubentryFlow):
    """Subentry flow for adding or reconfiguring a forecast location."""

    def __init__(self) -> None:
        """Initialize the subentry flow."""
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> SubentryFlowResult:
        """Collect the location name and mode."""
        return await self._async_step_name_and_mode(user_input, step_id="user")

    async def async_step_reconfigure(
        self,
        user_input: dict | None = None,
    ) -> SubentryFlowResult:
        """Reconfigure an existing location subentry."""
        if not self._data:
            self._data = dict(self._get_reconfigure_subentry().data)
        return await self._async_step_name_and_mode(user_input, step_id="reconfigure")

    async def _async_step_name_and_mode(
        self,
        user_input: dict | None,
        step_id: str,
    ) -> SubentryFlowResult:
        """Shared implementation for user and reconfigure steps."""
        if user_input is not None:
            self._data[CONF_NAME] = user_input[CONF_NAME]
            self._data[CONF_LOCATION_MODE] = user_input[CONF_LOCATION_MODE]
            if user_input[CONF_LOCATION_MODE] == LOCATION_MODE_CUSTOM:
                return await self.async_step_location()
            self._data.pop(CONF_LATITUDE, None)
            self._data.pop(CONF_LONGITUDE, None)
            self._data.pop(CONF_ELEVATION, None)
            return await self.async_step_forecast()

        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME,
                        default=self._data.get(CONF_NAME, vol.UNDEFINED),
                    ): selector.TextSelector(),
                    vol.Required(
                        CONF_LOCATION_MODE,
                        default=self._data.get(CONF_LOCATION_MODE, LOCATION_MODE_AUTO),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key=CONF_LOCATION_MODE,
                            options=[LOCATION_MODE_AUTO, LOCATION_MODE_CUSTOM],
                        ),
                    ),
                },
            ),
            last_step=False,
        )

    async def async_step_location(
        self,
        user_input: dict | None = None,
    ) -> SubentryFlowResult:
        """Collect the custom forecast location."""
        errors: dict[str, str] = {}
        if user_input is not None:
            location = user_input.get(CONF_LOCATION)
            if not location:
                errors[CONF_LOCATION] = "location_required"
            else:
                self._data[CONF_LATITUDE] = location["latitude"]
                self._data[CONF_LONGITUDE] = location["longitude"]
                elevation = user_input.get(CONF_ELEVATION)
                if elevation is not None:
                    self._data[CONF_ELEVATION] = elevation
                else:
                    self._data.pop(CONF_ELEVATION, None)
                return await self.async_step_forecast()

        default_location = {
            "latitude": self._data.get(CONF_LATITUDE, self.hass.config.latitude),
            "longitude": self._data.get(CONF_LONGITUDE, self.hass.config.longitude),
        }
        return self.async_show_form(
            step_id="location",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_LOCATION,
                        default=default_location,
                    ): selector.LocationSelector(
                        selector.LocationSelectorConfig(radius=False),
                    ),
                    vol.Optional(
                        CONF_ELEVATION,
                        default=self._data.get(CONF_ELEVATION, vol.UNDEFINED),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            mode=selector.NumberSelectorMode.BOX,
                            unit_of_measurement="m",
                            step=1,
                        ),
                    ),
                },
            ),
            errors=errors,
            last_step=False,
        )

    async def async_step_forecast(
        self,
        user_input: dict | None = None,
    ) -> SubentryFlowResult:
        """Collect the forecast configuration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if (
                user_input[CONF_ENABLE_FORECAST]
                and _duration_to_timedelta(user_input[CONF_FORECAST_UPDATE_INTERVAL])
                < MIN_UPDATE_INTERVAL
            ):
                errors[CONF_FORECAST_UPDATE_INTERVAL] = "update_interval_too_short"

            self._data[CONF_ENABLE_FORECAST] = user_input[CONF_ENABLE_FORECAST]
            self._data[CONF_FORECAST_TYPE] = user_input[CONF_FORECAST_TYPE]
            self._data[CONF_FORECAST_UPDATE_INTERVAL] = user_input[
                CONF_FORECAST_UPDATE_INTERVAL
            ]

            if not errors:
                return await self.async_step_meteogram()

        return self.async_show_form(
            step_id="forecast",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENABLE_FORECAST,
                        default=self._data.get(CONF_ENABLE_FORECAST, True),
                    ): selector.BooleanSelector(),
                    vol.Required(
                        CONF_FORECAST_TYPE,
                        default=self._data.get(CONF_FORECAST_TYPE, FORECAST_TYPE_DAILY),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key=CONF_FORECAST_TYPE,
                            options=[FORECAST_TYPE_DAILY, FORECAST_TYPE_HOURLY],
                        ),
                    ),
                    vol.Required(
                        CONF_FORECAST_UPDATE_INTERVAL,
                        default=self._data.get(
                            CONF_FORECAST_UPDATE_INTERVAL,
                            DEFAULT_FORECAST_UPDATE_INTERVAL,
                        ),
                    ): selector.DurationSelector(
                        selector.DurationSelectorConfig(
                            enable_day=False,
                            allow_negative=False,
                        ),
                    ),
                },
            ),
            errors=errors,
            last_step=False,
        )

    async def async_step_meteogram(
        self,
        user_input: dict | None = None,
    ) -> SubentryFlowResult:
        """Collect the meteogram configuration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if (
                user_input[CONF_ENABLE_METEOGRAM]
                and _duration_to_timedelta(user_input[CONF_METEOGRAM_UPDATE_INTERVAL])
                < MIN_UPDATE_INTERVAL
            ):
                errors[CONF_METEOGRAM_UPDATE_INTERVAL] = "update_interval_too_short"

            self._data[CONF_ENABLE_METEOGRAM] = user_input[CONF_ENABLE_METEOGRAM]
            self._data[CONF_METEOGRAM_UPDATE_INTERVAL] = user_input[
                CONF_METEOGRAM_UPDATE_INTERVAL
            ]

            if not errors:
                return await self._async_finalize()

        return self.async_show_form(
            step_id="meteogram",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENABLE_METEOGRAM,
                        default=self._data.get(CONF_ENABLE_METEOGRAM, True),
                    ): selector.BooleanSelector(),
                    vol.Required(
                        CONF_METEOGRAM_UPDATE_INTERVAL,
                        default=self._data.get(
                            CONF_METEOGRAM_UPDATE_INTERVAL,
                            DEFAULT_METEOGRAM_UPDATE_INTERVAL,
                        ),
                    ): selector.DurationSelector(
                        selector.DurationSelectorConfig(
                            enable_day=False,
                            allow_negative=False,
                        ),
                    ),
                },
            ),
            errors=errors,
        )

    async def _async_finalize(self) -> SubentryFlowResult:
        """Create or update the location subentry."""
        name = self._data[CONF_NAME]
        unique_id = self._build_unique_id()
        if self.source == config_entries.SOURCE_RECONFIGURE:
            return self.async_update_and_abort(
                self._get_entry(),
                self._get_reconfigure_subentry(),
                title=name,
                data=self._data,
                unique_id=unique_id,
            )
        return self.async_create_entry(
            title=name,
            data=self._data,
            unique_id=unique_id,
        )

    def _build_unique_id(self) -> str:
        """Build a stable unique id for the subentry."""
        mode = self._data[CONF_LOCATION_MODE]
        if mode == LOCATION_MODE_CUSTOM:
            lat = self._data[CONF_LATITUDE]
            lon = self._data[CONF_LONGITUDE]
            return slugify(f"custom-{lat}-{lon}")
        return LOCATION_MODE_AUTO
