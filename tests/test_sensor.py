# Copyright 2026 n4rs. All rights reserved.
# See LICENSE for the terms that apply to HomeAssistant Pool and Lawn modifications.

"""Tests for Pool and Lawn sensor entities."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pool_and_lawn.const import (
    CONF_CHLORINATOR_OUTPUT_GH,
    CONF_ENABLE_HOURLY_CLOUDS_AND_WIND,
    CONF_ENABLE_POOL,
    CONF_FORECAST_TYPE,
    CONF_HYDRAULIC_EFFICIENCY_FACTOR,
    CONF_LOCATION_MODE,
    CONF_POOL_VOLUME_M3,
    CONF_PUMP_NOMINAL_FLOW_M3H,
    CONF_TARGET_FREE_CHLORINE_PPM,
    FORECAST_TYPE_DAILY,
    FORECAST_TYPE_HOURLY,
    LOCATION_MODE_AUTO,
    SUBENTRY_TYPE_FORECAST_LOCATION,
)
from pool_and_lawn.irrigation import IrrigationForecastDay
from pool_and_lawn.pool import PoolForecastDay
from pool_and_lawn.sensor import (
    IRRIGATION_ENTITY_DESCRIPTIONS,
    POOL_PUMP_ENTITY_DESCRIPTIONS,
    IrrigationForecastManager,
    MeteoBlueIrrigationLevel,
    MeteoBluePoolPumpHours,
    PoolForecastManager,
    async_setup_entry,
)


def _coordinator(subentry: Any, data: dict[str, Any] | None = None) -> MagicMock:
    coordinator = MagicMock()
    coordinator.subentry = subentry
    coordinator.data = data
    coordinator.last_update_success = True
    return coordinator


def test_irrigation_entity_has_stable_identity_and_unavailable_diagnostics() -> None:
    """Identity is location/offset based and missing forecast is explained."""
    subentry = SimpleNamespace(
        subentry_id="garden-location",
        title="Back Garden",
        data={CONF_LOCATION_MODE: LOCATION_MODE_AUTO},
    )
    coordinator = _coordinator(subentry, {})
    manager = MagicMock(spec=IrrigationForecastManager)
    manager.coordinator = coordinator
    manager.get_day.return_value = IrrigationForecastDay(
        forecast_date=date(2026, 7, 20),
        forecast_day_offset=1,
        result=None,
        unavailable_reason="missing_cloud_cover",
    )
    entity = MeteoBlueIrrigationLevel(
        manager,
        1,
        IRRIGATION_ENTITY_DESCRIPTIONS[1],
    )

    assert entity.unique_id == "garden-location-irrigation_level_1"
    assert entity.entity_id == "sensor.pool_and_lawn_back_garden_irrigation_level_1"
    assert entity.icon == "mdi:sprinkler-variant"
    assert entity.native_unit_of_measurement is None
    assert entity.device_class is None
    assert entity.state_class is None
    assert entity.suggested_display_precision == 0
    assert entity.native_value is None
    assert entity.available is False
    assert entity.extra_state_attributes == {
        "forecast_date": "2026-07-20",
        "forecast_day_offset": 1,
        "unavailable_reason": "missing_cloud_cover",
    }
    assert entity.translation_placeholders == {"day_offset": "1"}


def test_irrigation_entity_exposes_integer_and_calculation_attributes() -> None:
    """Available entities expose only the integer state and diagnostics separately."""
    subentry = SimpleNamespace(
        subentry_id="garden-location",
        title="Garden",
        data={CONF_LOCATION_MODE: LOCATION_MODE_AUTO},
    )
    coordinator = _coordinator(subentry, {})
    result = MagicMock()
    result.final_level = 4
    result.as_attributes.return_value = {
        "forecast_date": "2026-07-19",
        "forecast_day_offset": 0,
        "base_score": 13,
        "final_level": 4,
    }
    manager = MagicMock(spec=IrrigationForecastManager)
    manager.coordinator = coordinator
    manager.get_day.return_value = IrrigationForecastDay(date(2026, 7, 19), 0, result)
    entity = MeteoBlueIrrigationLevel(
        manager,
        0,
        IRRIGATION_ENTITY_DESCRIPTIONS[0],
    )

    assert entity.available is True
    assert entity.native_value == 4
    assert isinstance(entity.native_value, int)
    assert entity.extra_state_attributes["base_score"] == 13
    assert entity.translation_placeholders == {}


def test_pool_entity_has_stable_identity_hours_and_diagnostics() -> None:
    """Pool entity identity uses location/offset and exposes hours plus diagnostics."""
    subentry = SimpleNamespace(
        subentry_id="pool-location",
        title="Main Pool",
        data={CONF_LOCATION_MODE: LOCATION_MODE_AUTO},
    )
    coordinator = _coordinator(subentry, {})
    result = MagicMock()
    result.recommended_pump_hours = 7.7
    result.as_attributes.return_value = {
        "forecast_date": "2026-07-20",
        "forecast_day_offset": 1,
        "calculation_type": "open_loop_weather_estimate",
    }
    manager = MagicMock(spec=PoolForecastManager)
    manager.coordinator = coordinator
    manager.get_day.return_value = PoolForecastDay(date(2026, 7, 20), 1, result)
    entity = MeteoBluePoolPumpHours(
        manager,
        1,
        POOL_PUMP_ENTITY_DESCRIPTIONS[1],
    )

    assert entity.unique_id == "pool-location-pool_pump_hours_1"
    assert entity.entity_id == "sensor.pool_and_lawn_main_pool_pool_pump_hours_1"
    assert entity.native_unit_of_measurement == "h"
    assert entity.suggested_display_precision == 1
    assert entity.native_value == 7.7
    assert entity.available is True
    assert entity.extra_state_attributes["calculation_type"] == (
        "open_loop_weather_estimate"
    )
    assert entity.translation_placeholders == {"day_offset": "1"}


@pytest.mark.asyncio
async def test_setup_creates_daily_sensors_and_one_midnight_listener_per_location() -> (
    None
):
    """Sensor setup has a fixed horizon and does not duplicate midnight listeners."""
    hourly = SimpleNamespace(
        subentry_id="hourly-location",
        subentry_type=SUBENTRY_TYPE_FORECAST_LOCATION,
        title="Hourly",
        data={
            CONF_FORECAST_TYPE: FORECAST_TYPE_HOURLY,
            CONF_LOCATION_MODE: LOCATION_MODE_AUTO,
            CONF_ENABLE_HOURLY_CLOUDS_AND_WIND: True,
            CONF_ENABLE_POOL: True,
            CONF_POOL_VOLUME_M3: 90,
            CONF_PUMP_NOMINAL_FLOW_M3H: 21.5,
            CONF_HYDRAULIC_EFFICIENCY_FACTOR: 0.75,
            CONF_CHLORINATOR_OUTPUT_GH: 25,
            CONF_TARGET_FREE_CHLORINE_PPM: 2,
        },
    )
    daily = SimpleNamespace(
        subentry_id="daily-location",
        subentry_type=SUBENTRY_TYPE_FORECAST_LOCATION,
        title="Daily",
        data={
            CONF_FORECAST_TYPE: FORECAST_TYPE_DAILY,
            CONF_LOCATION_MODE: LOCATION_MODE_AUTO,
        },
    )
    entry = MagicMock()
    entry.subentries = {
        hourly.subentry_id: hourly,
        daily.subentry_id: daily,
    }
    entry.runtime_data = SimpleNamespace(
        account_coordinator=MagicMock(),
        location_coordinators={
            hourly.subentry_id: _coordinator(hourly),
            daily.subentry_id: _coordinator(daily),
        },
    )
    add_entities = MagicMock()
    unsubscribe = MagicMock()
    hass = MagicMock()
    hass.config.latitude = 38.72
    hass.config.longitude = -9.14
    hass.config.time_zone = "Europe/Lisbon"

    with patch(
        "pool_and_lawn.sensor.async_track_time_change", return_value=unsubscribe
    ) as track_time:
        await async_setup_entry(hass, entry, add_entities)

    assert add_entities.call_count == 2
    hourly_entities = add_entities.call_args_list[0].args[0]
    daily_entities = add_entities.call_args_list[1].args[0]
    assert len(hourly_entities) == 15  # credits plus seven irrigation and pool offsets
    assert len(daily_entities) == 1
    irrigation_entities = [
        entity
        for entity in hourly_entities
        if isinstance(entity, MeteoBlueIrrigationLevel)
    ]
    assert [entity.forecast_day_offset for entity in irrigation_entities] == list(
        range(7)
    )
    pool_entities = [
        entity
        for entity in hourly_entities
        if isinstance(entity, MeteoBluePoolPumpHours)
    ]
    assert [entity.forecast_day_offset for entity in pool_entities] == list(range(7))
    track_time.assert_called_once()
    assert track_time.call_args.args[0] is hass
    assert track_time.call_args.kwargs == {"hour": 0, "minute": 0, "second": 0}
    entry.async_on_unload.assert_called_once_with(unsubscribe)

    irrigation_manager = irrigation_entities[0].manager
    pool_manager = pool_entities[0].manager
    irrigation_manager.invalidate = MagicMock()
    pool_manager.invalidate = MagicMock()
    for entity in [*irrigation_entities, *pool_entities]:
        entity.async_write_ha_state = MagicMock()
    midnight_callback = track_time.call_args.args[1]
    midnight_callback(None)

    irrigation_manager.invalidate.assert_called_once_with()
    pool_manager.invalidate.assert_called_once_with()
    for entity in [*irrigation_entities, *pool_entities]:
        entity.async_write_ha_state.assert_called_once_with()
