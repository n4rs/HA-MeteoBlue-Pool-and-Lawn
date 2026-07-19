# Copyright 2026 Dan Keder
#
# Modifications Copyright 2026 n4rs. All rights reserved.
# See LICENSE for the terms that apply to HomeAssistant Pool and Lawn modifications.
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
"""Weather platform for Pool and Lawn."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.components.weather import (
    Forecast,
    WeatherEntity,
    WeatherEntityDescription,
    WeatherEntityFeature,
)
from homeassistant.const import (
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .const import (
    CONF_FORECAST_TYPE,
    FORECAST_TYPE_HOURLY,
    SUBENTRY_TYPE_FORECAST_LOCATION,
)
from .entity import MeteoBlueLocationEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .data import MeteoBlueConfigEntry

ENTITY_DESCRIPTIONS = (
    WeatherEntityDescription(
        key="weather",
        name="Weather",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: MeteoBlueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a weather entity for each location subentry."""
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_FORECAST_LOCATION:
            continue
        coordinator = entry.runtime_data.location_coordinators.get(
            subentry.subentry_id,
        )
        if coordinator is None:
            continue
        async_add_entities(
            (
                MeteoBlueWeather(
                    coordinator=coordinator,
                    entity_description=entity_description,
                    platform_domain="weather",
                )
                for entity_description in ENTITY_DESCRIPTIONS
            ),
            config_subentry_id=subentry.subentry_id,
        )


class MeteoBlueWeather(MeteoBlueLocationEntity, WeatherEntity):
    """Pool and Lawn weather class."""

    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_precipitation_unit = UnitOfLength.MILLIMETERS

    async def async_added_to_hass(self) -> None:
        """Register an hourly state refresh so dynamic properties stay current."""
        await super().async_added_to_hass()

        @callback
        def _refresh(_now: Any) -> None:
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_time_change(self.hass, _refresh, minute=0, second=0),
        )

    def _current_entry(self) -> tuple[dict[str, Any] | None, bool]:
        """
        Return (entry, is_hourly) for the forecast slot covering now.

        Selects hourly or daily entries based on the subentry's forecast type,
        then picks the latest key whose timestamp is at or before the current
        time. If the whole forecast is in the future, falls back to the first
        key. Returns (None, is_hourly) if no entries are available.
        """
        forecast_type = self.coordinator.subentry.data.get(CONF_FORECAST_TYPE)
        is_hourly = forecast_type == FORECAST_TYPE_HOURLY
        data = self.coordinator.data
        if not data:
            return None, is_hourly
        entries = (
            data.get("forecast_data_hourly" if is_hourly else "forecast_data_daily")
            or {}
        )
        if not entries:
            return None, is_hourly
        now = dt_util.now()
        keys = sorted(entries)
        chosen = keys[0]
        for key in keys:
            if key > now:
                break
            chosen = key
        return entries[chosen], is_hourly

    @property
    def supported_features(self) -> WeatherEntityFeature:
        """Returrn the list of supported features."""
        forecast_type = self.coordinator.subentry.data.get(CONF_FORECAST_TYPE)
        if forecast_type == FORECAST_TYPE_HOURLY:
            return (
                WeatherEntityFeature.FORECAST_DAILY
                | WeatherEntityFeature.FORECAST_HOURLY
            )
        return WeatherEntityFeature.FORECAST_DAILY

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        entry, _ = self._current_entry()
        if entry is None:
            return None
        return entry.get("condition")

    @property
    def native_temperature(self) -> float | None:
        """Return the current temperature."""
        entry, is_hourly = self._current_entry()
        if entry is None:
            return None
        return entry.get("temperature" if is_hourly else "temperature_instant")

    @property
    def native_apparent_temperature(self) -> float | None:
        """Return the current apparent (feels-like) temperature."""
        entry, is_hourly = self._current_entry()
        if entry is None:
            return None
        return entry.get("felttemperature" if is_hourly else "felttemperature_mean")

    @property
    def humidity(self) -> float | None:
        """Return the current humidity."""
        entry, is_hourly = self._current_entry()
        if entry is None:
            return None
        return entry.get("relativehumidity" if is_hourly else "relativehumidity_mean")

    @property
    def native_pressure(self) -> float | None:
        """Return the current pressure."""
        entry, is_hourly = self._current_entry()
        if entry is None:
            return None
        return entry.get("sealevelpressure" if is_hourly else "sealevelpressure_mean")

    @property
    def native_wind_speed(self) -> float | None:
        """Return the current wind speed."""
        entry, is_hourly = self._current_entry()
        if entry is None:
            return None
        return entry.get("windspeed" if is_hourly else "windspeed_mean")

    @property
    def native_wind_gust_speed(self) -> float | None:
        """Return the current wind gust speed."""
        entry, is_hourly = self._current_entry()
        if entry is None:
            return None
        if is_hourly:
            return entry.get("gust")
        return entry.get("gust_max")

    @property
    def wind_bearing(self) -> float | str | None:
        """Return the current wind bearing."""
        entry, _ = self._current_entry()
        if entry is None:
            return None
        return entry.get("winddirection")

    @property
    def cloud_coverage(self) -> float | None:
        """Return the current cloud coverage."""
        entry, is_hourly = self._current_entry()
        if entry is None:
            return None
        if is_hourly:
            return entry.get("totalcloudcover")
        return entry.get("totalcloudcover_mean")

    @property
    def uv_index(self) -> float | None:
        """Return the current UV index."""
        entry, _ = self._current_entry()
        if entry is None:
            return None
        return entry.get("uvindex")

    @property
    def native_visibility(self) -> float | None:
        """Return the current visibility."""
        return None

    @property
    def native_dew_point(self) -> float | None:
        """Return the current dew point."""
        return None

    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast."""
        data = self.coordinator.data
        if not data:
            return None
        entries = data.get("forecast_data_daily", {})
        cutoff = dt_util.now() - timedelta(days=1)
        forecasts: list[Forecast] = []
        for key in sorted(entries):
            if key <= cutoff:
                continue
            entry = entries[key]
            forecasts.append(
                Forecast(
                    datetime=key.isoformat(),
                    condition=entry.get("condition"),
                    native_temperature=entry.get("temperature_max"),
                    native_templow=entry.get("temperature_min"),
                    native_precipitation=entry.get("precipitation"),
                    precipitation_probability=entry.get("precipitation_probability"),
                    native_wind_speed=entry.get("windspeed_mean"),
                    native_wind_gust_speed=entry.get("gust_max"),
                    wind_bearing=entry.get("winddirection"),
                    cloud_coverage=entry.get("totalcloudcover_mean"),
                )
            )
        return forecasts

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast."""
        data = self.coordinator.data
        if not data:
            return None
        entries = data.get("forecast_data_hourly", {})
        cutoff = dt_util.now() - timedelta(hours=1)
        forecasts: list[Forecast] = []
        for key in sorted(entries):
            if key <= cutoff:
                continue
            entry = entries[key]
            forecasts.append(
                Forecast(
                    datetime=key.isoformat(),
                    condition=entry.get("condition"),
                    native_temperature=entry.get("temperature"),
                    native_apparent_temperature=entry.get("felttemperature"),
                    native_precipitation=entry.get("precipitation"),
                    precipitation_probability=entry.get("precipitation_probability"),
                    native_pressure=entry.get("sealevelpressure"),
                    native_wind_speed=entry.get("windspeed"),
                    native_wind_gust_speed=entry.get("gust"),
                    wind_bearing=entry.get("winddirection"),
                    humidity=entry.get("relativehumidity"),
                    cloud_coverage=entry.get("totalcloudcover"),
                )
            )
        return forecasts
