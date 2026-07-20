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
"""Sensor platform for Pool and Lawn."""

from __future__ import annotations

from datetime import date, timedelta, tzinfo
from functools import partial
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, UnitOfTime
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CHLORINATOR_OUTPUT_GH,
    CONF_ENABLE_HOURLY_CLOUDS_AND_WIND,
    CONF_ENABLE_POOL,
    CONF_FORECAST_TYPE,
    CONF_HYDRAULIC_EFFICIENCY_FACTOR,
    CONF_LOCATION_MODE,
    CONF_POOL_VOLUME_M3,
    CONF_PUMP_NOMINAL_FLOW_M3H,
    CONF_TARGET_FREE_CHLORINE_PPM,
    FORECAST_TYPE_HOURLY,
    LOCATION_MODE_CUSTOM,
    SUBENTRY_TYPE_FORECAST_LOCATION,
)
from .entity import MeteoBlueAccountEntity, MeteoBlueLocationEntity
from .irrigation import (
    IRRIGATION_FORECAST_DAYS,
    IrrigationForecastDay,
    astral_solar_period,
    calculate_irrigation_forecast,
)
from .pool import (
    POOL_FORECAST_DAYS,
    PoolForecastDay,
    PoolSettings,
    calculate_pool_pump_forecast,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .coordinator import ForecastCoordinator
    from .data import MeteoBlueConfigEntry

ENTITY_DESCRIPTIONS = (
    SensorEntityDescription(
        key="credits_used",
        name="Credits Used",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="credits",
    ),
)

IRRIGATION_ENTITY_DESCRIPTIONS = tuple(
    SensorEntityDescription(
        key=f"irrigation_level_{offset}",
        translation_key=(
            "irrigation_level_today" if offset == 0 else "irrigation_level_future"
        ),
        icon="mdi:sprinkler-variant",
    )
    for offset in range(IRRIGATION_FORECAST_DAYS)
)

POOL_PUMP_ENTITY_DESCRIPTIONS = tuple(
    SensorEntityDescription(
        key=f"pool_pump_hours_{offset}",
        translation_key=(
            "pool_pump_hours_today" if offset == 0 else "pool_pump_hours_future"
        ),
        icon="mdi:pump",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.HOURS,
    )
    for offset in range(POOL_FORECAST_DAYS)
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeteoBlueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up account usage and irrigation sensors for each location."""
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_FORECAST_LOCATION:
            continue
        entities: list[SensorEntity] = [
            MeteoBlueCreditsUsed(
                coordinator=entry.runtime_data.account_coordinator,
                subentry=subentry,
                entity_description=entity_description,
                platform_domain="sensor",
            )
            for entity_description in ENTITY_DESCRIPTIONS
        ]
        coordinator = entry.runtime_data.location_coordinators.get(subentry.subentry_id)
        if (
            coordinator is not None
            and subentry.data.get(CONF_FORECAST_TYPE) == FORECAST_TYPE_HOURLY
        ):
            managers: list[IrrigationForecastManager | PoolForecastManager] = []
            forecast_entities: list[
                MeteoBlueIrrigationLevel | MeteoBluePoolPumpHours
            ] = []

            irrigation_manager = IrrigationForecastManager(hass, coordinator)
            managers.append(irrigation_manager)
            irrigation_entities = [
                MeteoBlueIrrigationLevel(
                    manager=irrigation_manager,
                    forecast_day_offset=offset,
                    entity_description=entity_description,
                )
                for offset, entity_description in enumerate(
                    IRRIGATION_ENTITY_DESCRIPTIONS
                )
            ]
            entities.extend(irrigation_entities)
            forecast_entities.extend(irrigation_entities)

            if subentry.data.get(CONF_ENABLE_POOL, False) and subentry.data.get(
                CONF_ENABLE_HOURLY_CLOUDS_AND_WIND, False
            ):
                pool_manager = PoolForecastManager(hass, coordinator)
                managers.append(pool_manager)
                pool_entities = [
                    MeteoBluePoolPumpHours(
                        manager=pool_manager,
                        forecast_day_offset=offset,
                        entity_description=entity_description,
                    )
                    for offset, entity_description in enumerate(
                        POOL_PUMP_ENTITY_DESCRIPTIONS
                    )
                ]
                entities.extend(pool_entities)
                forecast_entities.extend(pool_entities)

            @callback
            def _refresh_at_midnight(
                _now: object,
                managers: list[
                    IrrigationForecastManager | PoolForecastManager
                ] = managers,
                sensors: list[
                    MeteoBlueIrrigationLevel | MeteoBluePoolPumpHours
                ] = forecast_entities,
            ) -> None:
                for manager in managers:
                    manager.invalidate()
                for sensor in sensors:
                    sensor.async_write_ha_state()

            entry.async_on_unload(
                async_track_time_change(
                    hass,
                    _refresh_at_midnight,
                    hour=0,
                    minute=0,
                    second=0,
                )
            )

        async_add_entities(
            entities,
            config_subentry_id=subentry.subentry_id,
        )


class MeteoBlueCreditsUsed(MeteoBlueAccountEntity, SensorEntity):
    """Sensor exposing the total MeteoBlue API credits consumed."""

    @property
    def native_value(self) -> int | None:
        """Return the sum of request_credits across all account usage items."""
        if not self.coordinator.data:
            return None
        items = self.coordinator.data.get("items") or []
        if not items:
            return None
        return sum(item.get("request_credits", 0) for item in items)


class IrrigationForecastManager:
    """Cache pure irrigation calculations for one forecast coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: ForecastCoordinator,
    ) -> None:
        """Initialize the per-location irrigation calculation manager."""
        self.hass = hass
        self.coordinator = coordinator
        data = coordinator.subentry.data
        if data.get(CONF_LOCATION_MODE) == LOCATION_MODE_CUSTOM:
            self.latitude = data[CONF_LATITUDE]
            self.longitude = data[CONF_LONGITUDE]
        else:
            self.latitude = hass.config.latitude
            self.longitude = hass.config.longitude
        self._cache_key: tuple[int, date] | None = None
        self._cached_days: list[IrrigationForecastDay] = []

    def invalidate(self) -> None:
        """Discard cached calculations without fetching new API data."""
        self._cache_key = None

    def get_day(self, offset: int) -> IrrigationForecastDay | None:
        """Return the result assigned to a stable forecast-day offset."""
        data = self.coordinator.data
        if not data:
            return None
        hourly = data.get("forecast_data_hourly") or {}
        timezone = self._local_timezone(hourly)
        today = dt_util.now().astimezone(timezone).date()
        cache_key = (id(data), today)
        if self._cache_key != cache_key:
            provider = partial(
                astral_solar_period,
                latitude=self.latitude,
                longitude=self.longitude,
            )
            self._cached_days = calculate_irrigation_forecast(
                hourly,
                data.get("units") or {},
                today,
                timezone,
                provider,
            )
            self._cache_key = cache_key
        return self._cached_days[offset] if offset < len(self._cached_days) else None

    def local_today(self) -> date:
        """Return today in the forecast location's available timezone."""
        data = self.coordinator.data or {}
        hourly = data.get("forecast_data_hourly") or {}
        timezone = self._local_timezone(hourly)
        return dt_util.now().astimezone(timezone).date()

    def _local_timezone(self, hourly: dict) -> tzinfo:
        for timestamp in sorted(hourly):
            if timestamp.tzinfo is not None:
                return timestamp.tzinfo
        return ZoneInfo(str(self.hass.config.time_zone))


class MeteoBlueIrrigationLevel(MeteoBlueLocationEntity, SensorEntity):
    """Sensor exposing one stable-offset daily irrigation level."""

    _attr_suggested_display_precision = 0

    def __init__(
        self,
        manager: IrrigationForecastManager,
        forecast_day_offset: int,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize an irrigation sensor tied to a location coordinator."""
        super().__init__(
            coordinator=manager.coordinator,
            entity_description=entity_description,
            platform_domain="sensor",
        )
        self.manager = manager
        self.forecast_day_offset = forecast_day_offset
        if forecast_day_offset > 0:
            self._attr_translation_placeholders = {
                "day_offset": str(forecast_day_offset)
            }

    @property
    def available(self) -> bool:
        """Return whether all essential inputs exist for this forecast day."""
        day = self.manager.get_day(self.forecast_day_offset)
        return super().available and day is not None and day.result is not None

    @property
    def native_value(self) -> int | None:
        """Return an integer irrigation level from zero to five."""
        day = self.manager.get_day(self.forecast_day_offset)
        return day.result.final_level if day is not None and day.result else None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return diagnostics explaining the irrigation calculation."""
        day = self.manager.get_day(self.forecast_day_offset)
        if day is None:
            return {
                "forecast_date": (
                    self.manager.local_today()
                    + timedelta(days=self.forecast_day_offset)
                ).isoformat(),
                "forecast_day_offset": self.forecast_day_offset,
                "unavailable_reason": "no_forecast_for_day",
            }
        if day.result is None:
            return {
                "forecast_date": day.forecast_date.isoformat(),
                "forecast_day_offset": day.forecast_day_offset,
                "unavailable_reason": day.unavailable_reason,
            }
        return day.result.as_attributes()


class PoolForecastManager:
    """Cache pure pool runtime calculations for one forecast coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: ForecastCoordinator,
    ) -> None:
        """Initialize pool settings and the per-location result cache."""
        self.hass = hass
        self.coordinator = coordinator
        data = coordinator.subentry.data
        self.settings = PoolSettings(
            volume_m3=float(data[CONF_POOL_VOLUME_M3]),
            pump_nominal_flow_m3h=float(data[CONF_PUMP_NOMINAL_FLOW_M3H]),
            hydraulic_efficiency_factor=float(data[CONF_HYDRAULIC_EFFICIENCY_FACTOR]),
            chlorinator_output_gh=float(data[CONF_CHLORINATOR_OUTPUT_GH]),
            target_free_chlorine_ppm=float(data[CONF_TARGET_FREE_CHLORINE_PPM]),
        )
        if data.get(CONF_LOCATION_MODE) == LOCATION_MODE_CUSTOM:
            self.latitude = data[CONF_LATITUDE]
            self.longitude = data[CONF_LONGITUDE]
        else:
            self.latitude = hass.config.latitude
            self.longitude = hass.config.longitude
        self._cache_key: tuple[int, date] | None = None
        self._cached_days: list[PoolForecastDay] = []

    def invalidate(self) -> None:
        """Discard cached calculations without fetching new API data."""
        self._cache_key = None

    def get_day(self, offset: int) -> PoolForecastDay | None:
        """Return the pool estimate assigned to a stable forecast-day offset."""
        data = self.coordinator.data
        if not data:
            return None
        hourly = data.get("forecast_data_hourly") or {}
        timezone = self._local_timezone(hourly)
        today = dt_util.now().astimezone(timezone).date()
        cache_key = (id(data), today)
        if self._cache_key != cache_key:
            provider = partial(
                astral_solar_period,
                latitude=self.latitude,
                longitude=self.longitude,
            )
            self._cached_days = calculate_pool_pump_forecast(
                hourly,
                data.get("units") or {},
                self.settings,
                today,
                timezone,
                provider,
            )
            self._cache_key = cache_key
        return self._cached_days[offset] if offset < len(self._cached_days) else None

    def local_today(self) -> date:
        """Return today in the forecast location's available timezone."""
        data = self.coordinator.data or {}
        hourly = data.get("forecast_data_hourly") or {}
        timezone = self._local_timezone(hourly)
        return dt_util.now().astimezone(timezone).date()

    def _local_timezone(self, hourly: dict) -> tzinfo:
        for timestamp in sorted(hourly):
            if timestamp.tzinfo is not None:
                return timestamp.tzinfo
        return ZoneInfo(str(self.hass.config.time_zone))


class MeteoBluePoolPumpHours(MeteoBlueLocationEntity, SensorEntity):
    """Sensor exposing recommended saltwater pool pump hours for one day."""

    _attr_suggested_display_precision = 1

    def __init__(
        self,
        manager: PoolForecastManager,
        forecast_day_offset: int,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize a pool sensor tied to a stable location/day identity."""
        super().__init__(
            coordinator=manager.coordinator,
            entity_description=entity_description,
            platform_domain="sensor",
        )
        self.manager = manager
        self.forecast_day_offset = forecast_day_offset
        if forecast_day_offset > 0:
            self._attr_translation_placeholders = {
                "day_offset": str(forecast_day_offset)
            }

    @property
    def available(self) -> bool:
        """Return whether all essential inputs exist for this forecast day."""
        day = self.manager.get_day(self.forecast_day_offset)
        return super().available and day is not None and day.result is not None

    @property
    def native_value(self) -> float | None:
        """Return recommended pump runtime in hours, rounded to one decimal."""
        day = self.manager.get_day(self.forecast_day_offset)
        return (
            day.result.recommended_pump_hours
            if day is not None and day.result
            else None
        )

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return weather, chlorine, and hydraulic diagnostics."""
        day = self.manager.get_day(self.forecast_day_offset)
        if day is None:
            return {
                "forecast_date": (
                    self.manager.local_today()
                    + timedelta(days=self.forecast_day_offset)
                ).isoformat(),
                "forecast_day_offset": self.forecast_day_offset,
                "unavailable_reason": "no_forecast_for_day",
                "calculation_type": "open_loop_weather_estimate",
            }
        if day.result is None:
            return {
                "forecast_date": day.forecast_date.isoformat(),
                "forecast_day_offset": day.forecast_day_offset,
                "unavailable_reason": day.unavailable_reason,
                "calculation_type": "open_loop_weather_estimate",
            }
        return day.result.as_attributes()
