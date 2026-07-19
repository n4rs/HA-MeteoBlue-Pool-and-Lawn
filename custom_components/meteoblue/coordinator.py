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
"""DataUpdateCoordinators for meteoblue."""

from __future__ import annotations

import asyncio
import math
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any, NamedTuple

from dateutil.parser import parse as dateutil_parse
from dateutil.tz import tzoffset
from homeassistant.const import CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    ApiPackage,
    MeteoBlueApiClient,
    MeteoBlueApiClientAuthenticationError,
    MeteoBlueApiClientError,
    MeteoBlueApiTimeoutError,
)
from .const import (
    CONF_ENABLE_HOURLY_CLOUDS_AND_WIND,
    CONF_FORECAST_TYPE,
    CONF_FORECAST_UPDATE_INTERVAL,
    CONF_LOCATION_MODE,
    CONF_METEOGRAM_UPDATE_INTERVAL,
    DOMAIN,
    FORECAST_TYPE_HOURLY,
    LOCATION_MODE_CUSTOM,
    LOGGER,
    PICTOCODE_DAILY_TO_CONDITION,
    PICTOCODE_HOURLY_TO_CONDITION,
)
from .image_utils import invert_png, remove_background

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.config_entries import ConfigSubentry
    from homeassistant.core import HomeAssistant

    from .data import MeteoBlueConfigEntry


ACCOUNT_USAGE_UPDATE_INTERVAL = timedelta(hours=6)
FORECAST_UPDATE_INTERVAL = timedelta(hours=6)
METEOGRAM_UPDATE_INTERVAL = timedelta(hours=6)


class MeteogramImage(NamedTuple):
    """Meteogram image payload exposed by ``MeteogramCoordinator``."""

    content: bytes
    content_type: str


class MeteogramImageSet(NamedTuple):
    """Pair of meteogram variants exposed by ``MeteogramCoordinator``."""

    meteogram_light: MeteogramImage
    meteogram_dark: MeteogramImage


def _interval_from_subentry(
    data: Mapping[str, Any],
    key: str,
    default: timedelta,
) -> timedelta:
    """Convert a DurationSelector dict from subentry data to a timedelta."""
    raw = data.get(key)
    if not raw:
        return default
    return timedelta(
        hours=raw.get("hours", 0),
        minutes=raw.get("minutes", 0),
        seconds=raw.get("seconds", 0),
    )


def _build_tz(metadata: dict[str, Any]) -> tzoffset:
    """Build a tz-aware offset from MeteoBlue metadata."""
    abbrev = metadata["timezone_abbrevation"]
    offset_hours = metadata["utc_timeoffset"]
    return tzoffset(abbrev, int(offset_hours * 3600))


def _aggregate_hourly_to_daily(
    forecast_data_hourly: dict[datetime, dict[str, Any]],
    tz: tzoffset,
) -> dict[datetime, dict[str, Any]]:
    """
    Build daily forecast entries by aggregating per-hour values.

    Aggregation mirrors the MeteoBlue daily package: max/min temperature,
    sum precipitation, max precipitation probability, mean wind speed,
    wind-speed-weighted circular mean for bearing, and the midday pictocode
    for the condition.

    If the pictocode (condition) is missing for the midday entry the day will be
    skipped. This usually happens on the last day for which hourly data is available.
    """
    grouped: dict[date, list[datetime]] = {}
    for key in forecast_data_hourly:
        grouped.setdefault(key.date(), []).append(key)

    result: dict[datetime, dict[str, Any]] = {}
    for day, keys in grouped.items():
        entries = [forecast_data_hourly[k] for k in keys]

        # Skip the day for which the midday entry is missing, as condition
        # cannot be resolved without it.
        midday_entry = forecast_data_hourly.get(
            datetime(day.year, day.month, day.day, 12, tzinfo=tz)
        )
        if midday_entry is None:
            continue

        # Aggregate temperature
        temperatures = [v for e in entries if (v := e.get("temperature")) is not None]

        # Aggregate precipitation and probability
        precipitations = [
            v for e in entries if (v := e.get("precipitation")) is not None
        ]
        probabilities = [
            v for e in entries if (v := e.get("precipitation_probability")) is not None
        ]

        # Aggregate wind speed and bearing
        windspeeds = [v for e in entries if (v := e.get("windspeed")) is not None]
        gusts = [v for e in entries if (v := e.get("gust")) is not None]
        cloud_covers = [
            v for e in entries if (v := e.get("totalcloudcover")) is not None
        ]
        u = 0.0
        v_sum = 0.0
        for e in entries:
            speed = e.get("windspeed")
            direction = e.get("winddirection")
            if speed is None or direction is None:
                continue
            rad = math.radians(direction)
            u += speed * math.sin(rad)
            v_sum += speed * math.cos(rad)
        bearing = (
            (math.degrees(math.atan2(u, v_sum)) + 360) % 360
            if u != 0.0 or v_sum != 0.0
            else None
        )

        midnight = datetime(day.year, day.month, day.day, tzinfo=tz)
        result[midnight] = {
            "temperature_max": max(temperatures) if temperatures else None,
            "temperature_min": min(temperatures) if temperatures else None,
            "precipitation": sum(precipitations) if precipitations else None,
            "precipitation_probability": (
                max(probabilities) if probabilities else None
            ),
            "windspeed_mean": (
                sum(windspeeds) / len(windspeeds) if windspeeds else None
            ),
            "gust_max": max(gusts) if gusts else None,
            "winddirection": bearing,
            "totalcloudcover_mean": (
                sum(cloud_covers) / len(cloud_covers) if cloud_covers else None
            ),
            "condition": midday_entry.get("condition"),
        }
    return result


def _parse_section(
    section: dict[str, Any] | None,
    tz: tzoffset,
    mapping: dict[int, str],
) -> dict[datetime, dict[str, Any]]:
    """Parse a column-oriented forecast section into a dict keyed by datetime."""
    entries: dict[datetime, dict[str, Any]] = {}
    if not section:
        return entries
    times = section.get("time", [])
    isdaylight = section.get("isdaylight")
    for i, ts in enumerate(times):
        key = dateutil_parse(ts).replace(tzinfo=tz)
        entry: dict[str, Any] = {}
        for field, values in section.items():
            if field in ("time", "isdaylight"):
                continue
            if field == "pictocode":
                condition = mapping.get(int(values[i]))
                # MeteoBlue's hourly pictogram set has no separate code for a
                # clear night, so map "sunny" to "clear-night" when the API
                # marks the hour as non-daylight.
                if (
                    condition == "sunny"
                    and isdaylight is not None
                    and not isdaylight[i]
                ):
                    condition = "clear-night"
                entry["condition"] = condition
            else:
                entry[field] = values[i]
        entries[key] = entry
    return entries


def _reshape_forecast_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Reshape a MeteoBlue forecast response from column- to row-oriented shape."""
    metadata = payload.get("metadata", {})
    units = payload.get("units", {})
    tz = _build_tz(metadata)
    data_1h = payload.get("data_1h")
    data_day = payload.get("data_day")

    forecast_data_hourly = _parse_section(data_1h, tz, PICTOCODE_HOURLY_TO_CONDITION)
    forecast_data_daily = _parse_section(data_day, tz, PICTOCODE_DAILY_TO_CONDITION)
    if not data_day and forecast_data_hourly:
        forecast_data_daily = _aggregate_hourly_to_daily(forecast_data_hourly, tz)

    return {
        "metadata": metadata,
        "units": units,
        "forecast_data_hourly": forecast_data_hourly,
        "forecast_data_daily": forecast_data_daily,
    }


class AccountUsageCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches MeteoBlue account usage for the API key."""

    config_entry: MeteoBlueConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MeteoBlueConfigEntry,
        client: MeteoBlueApiClient,
    ) -> None:
        """Initialize the account usage coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=f"{DOMAIN}_account_usage",
            update_interval=ACCOUNT_USAGE_UPDATE_INTERVAL,
            config_entry=config_entry,
        )
        self._client = client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch account usage via the MeteoBlue API."""
        try:
            return await self._client.async_get_account_usage()
        except MeteoBlueApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except MeteoBlueApiTimeoutError as exception:
            raise UpdateFailed(exception) from exception
        except MeteoBlueApiClientError as exception:
            raise UpdateFailed(exception) from exception


class ForecastCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches MeteoBlue forecast data for a single location subentry."""

    config_entry: MeteoBlueConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MeteoBlueConfigEntry,
        subentry: ConfigSubentry,
        client: MeteoBlueApiClient,
    ) -> None:
        """Initialize the forecast coordinator for a location subentry."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=f"{DOMAIN}_forecast_{subentry.subentry_id}",
            update_interval=_interval_from_subentry(
                subentry.data,
                CONF_FORECAST_UPDATE_INTERVAL,
                FORECAST_UPDATE_INTERVAL,
            ),
            config_entry=config_entry,
        )
        self.subentry = subentry
        self._client = client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch forecast data for this location."""
        data = self.subentry.data
        if data.get(CONF_LOCATION_MODE) == LOCATION_MODE_CUSTOM:
            latitude = data[CONF_LATITUDE]
            longitude = data[CONF_LONGITUDE]
        else:
            latitude = self.hass.config.latitude
            longitude = self.hass.config.longitude
        if data.get(CONF_FORECAST_TYPE) == FORECAST_TYPE_HOURLY:
            api_packages = [ApiPackage.BASIC_1H]
            if data.get(CONF_ENABLE_HOURLY_CLOUDS_AND_WIND, True):
                api_packages.extend(
                    [
                        ApiPackage.CLOUDS_1H,
                        ApiPackage.WIND_1H,
                    ]
                )
        else:
            api_packages = [ApiPackage.BASIC_DAY]
        try:
            raw = await self._client.async_get_forecast(
                latitude=latitude,
                longitude=longitude,
                asl=data.get(CONF_ELEVATION),
                api_packages=api_packages,
            )
        except MeteoBlueApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except MeteoBlueApiTimeoutError as exception:
            raise UpdateFailed(exception) from exception
        except MeteoBlueApiClientError as exception:
            raise UpdateFailed(exception) from exception
        return _reshape_forecast_payload(raw)


class MeteogramCoordinator(DataUpdateCoordinator[MeteogramImageSet]):
    """Fetches the MeteoBlue extended meteogram image for a single location subentry."""

    config_entry: MeteoBlueConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MeteoBlueConfigEntry,
        subentry: ConfigSubentry,
        client: MeteoBlueApiClient,
    ) -> None:
        """Initialize the meteogram coordinator for a location subentry."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=f"{DOMAIN}_meteogram_{subentry.subentry_id}",
            update_interval=_interval_from_subentry(
                subentry.data,
                CONF_METEOGRAM_UPDATE_INTERVAL,
                METEOGRAM_UPDATE_INTERVAL,
            ),
            config_entry=config_entry,
        )
        self.subentry = subentry
        self._client = client

    async def _async_update_data(self) -> MeteogramImageSet:
        """Fetch the extended meteogram image for this location."""
        data = self.subentry.data
        if data.get(CONF_LOCATION_MODE) == LOCATION_MODE_CUSTOM:
            latitude = data[CONF_LATITUDE]
            longitude = data[CONF_LONGITUDE]
        else:
            latitude = self.hass.config.latitude
            longitude = self.hass.config.longitude
        try:
            raw_bytes = await self._client.async_get_meteogram_extended(
                latitude=latitude,
                longitude=longitude,
                location_name=self.subentry.title,
            )
            light_bytes = await asyncio.to_thread(remove_background, raw_bytes)
            dark_bytes = await asyncio.to_thread(invert_png, light_bytes)
        except MeteoBlueApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except MeteoBlueApiTimeoutError as exception:
            raise UpdateFailed(exception) from exception
        except MeteoBlueApiClientError as exception:
            raise UpdateFailed(exception) from exception
        return MeteogramImageSet(
            meteogram_light=MeteogramImage(
                content=light_bytes, content_type="image/png"
            ),
            meteogram_dark=MeteogramImage(content=dark_bytes, content_type="image/png"),
        )
