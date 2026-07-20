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
"""Tests for the MeteoBlue config flow helpers."""

from __future__ import annotations

from typing import Any

import pytest
from pool_and_lawn.config_flow import ForecastLocationSubentryFlowHandler
from pool_and_lawn.const import (
    CONF_CHLORINATOR_OUTPUT_GH,
    CONF_ENABLE_FORECAST,
    CONF_ENABLE_HOURLY_CLOUDS_AND_WIND,
    CONF_ENABLE_POOL,
    CONF_FORECAST_TYPE,
    CONF_FORECAST_UPDATE_INTERVAL,
    CONF_HYDRAULIC_EFFICIENCY_FACTOR,
    CONF_POOL_VOLUME_M3,
    CONF_PUMP_NOMINAL_FLOW_M3H,
    CONF_TARGET_FREE_CHLORINE_PPM,
    FORECAST_TYPE_DAILY,
    FORECAST_TYPE_HOURLY,
)

FORECAST_INTERVAL = {"hours": 12, "minutes": 0, "seconds": 0}


@pytest.fixture
def forecast_flow(
    monkeypatch: pytest.MonkeyPatch,
) -> ForecastLocationSubentryFlowHandler:
    """Return a forecast subentry flow with finalization stubbed."""
    flow = ForecastLocationSubentryFlowHandler()

    async def _finalize() -> dict[str, Any]:
        return {"type": "create_entry", "step_id": "finalize"}

    monkeypatch.setattr(flow, "_async_finalize", _finalize)
    return flow


async def test_forecast_step_routes_hourly_to_hourly_packages(
    forecast_flow: ForecastLocationSubentryFlowHandler,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hourly forecasts show the optional hourly package step next."""

    async def _hourly_packages() -> dict[str, Any]:
        return {"type": "form", "step_id": "hourly_packages"}

    monkeypatch.setattr(forecast_flow, "async_step_hourly_packages", _hourly_packages)

    result = await forecast_flow.async_step_forecast(
        {
            CONF_ENABLE_FORECAST: True,
            CONF_FORECAST_TYPE: FORECAST_TYPE_HOURLY,
            CONF_FORECAST_UPDATE_INTERVAL: FORECAST_INTERVAL,
        }
    )

    assert result["step_id"] == "hourly_packages"


async def test_forecast_step_skips_hourly_packages_for_daily(
    forecast_flow: ForecastLocationSubentryFlowHandler,
) -> None:
    """Daily forecasts skip optional hourly package options."""
    forecast_flow._data[CONF_ENABLE_HOURLY_CLOUDS_AND_WIND] = True  # noqa: SLF001
    forecast_flow._data[CONF_ENABLE_POOL] = True  # noqa: SLF001
    forecast_flow._data[CONF_POOL_VOLUME_M3] = 40  # noqa: SLF001
    forecast_flow._data[CONF_PUMP_NOMINAL_FLOW_M3H] = 10  # noqa: SLF001
    forecast_flow._data[CONF_HYDRAULIC_EFFICIENCY_FACTOR] = 0.75  # noqa: SLF001
    forecast_flow._data[CONF_CHLORINATOR_OUTPUT_GH] = 20  # noqa: SLF001
    forecast_flow._data[CONF_TARGET_FREE_CHLORINE_PPM] = 2  # noqa: SLF001

    result = await forecast_flow.async_step_forecast(
        {
            CONF_ENABLE_FORECAST: True,
            CONF_FORECAST_TYPE: FORECAST_TYPE_DAILY,
            CONF_FORECAST_UPDATE_INTERVAL: FORECAST_INTERVAL,
        }
    )

    assert result["step_id"] == "finalize"
    assert CONF_ENABLE_HOURLY_CLOUDS_AND_WIND not in forecast_flow._data  # noqa: SLF001
    assert CONF_ENABLE_POOL not in forecast_flow._data  # noqa: SLF001
    assert CONF_POOL_VOLUME_M3 not in forecast_flow._data  # noqa: SLF001
    assert CONF_PUMP_NOMINAL_FLOW_M3H not in forecast_flow._data  # noqa: SLF001
    assert CONF_HYDRAULIC_EFFICIENCY_FACTOR not in forecast_flow._data  # noqa: SLF001
    assert CONF_CHLORINATOR_OUTPUT_GH not in forecast_flow._data  # noqa: SLF001
    assert CONF_TARGET_FREE_CHLORINE_PPM not in forecast_flow._data  # noqa: SLF001


async def test_forecast_step_skips_hourly_packages_when_forecast_disabled(
    forecast_flow: ForecastLocationSubentryFlowHandler,
) -> None:
    """Disabled forecasts skip optional hourly package options."""
    forecast_flow._data[CONF_ENABLE_HOURLY_CLOUDS_AND_WIND] = True  # noqa: SLF001

    result = await forecast_flow.async_step_forecast(
        {
            CONF_ENABLE_FORECAST: False,
            CONF_FORECAST_TYPE: FORECAST_TYPE_HOURLY,
            CONF_FORECAST_UPDATE_INTERVAL: FORECAST_INTERVAL,
        }
    )

    assert result["step_id"] == "finalize"
    assert CONF_ENABLE_HOURLY_CLOUDS_AND_WIND not in forecast_flow._data  # noqa: SLF001


async def test_hourly_packages_step_stores_selection(
    forecast_flow: ForecastLocationSubentryFlowHandler,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Optional hourly package selection is stored before the pool step."""

    async def _pool() -> dict[str, Any]:
        return {"type": "form", "step_id": "pool"}

    monkeypatch.setattr(forecast_flow, "async_step_pool", _pool)

    result = await forecast_flow.async_step_hourly_packages(
        {
            CONF_ENABLE_HOURLY_CLOUDS_AND_WIND: True,
            CONF_ENABLE_POOL: True,
        }
    )

    assert result["step_id"] == "pool"
    assert forecast_flow._data[CONF_ENABLE_HOURLY_CLOUDS_AND_WIND] is True  # noqa: SLF001
    assert forecast_flow._data[CONF_ENABLE_POOL] is True  # noqa: SLF001


async def test_hourly_packages_step_skips_pool_configuration(
    forecast_flow: ForecastLocationSubentryFlowHandler,
) -> None:
    """Hourly forecasts can be configured without an associated pool."""
    forecast_flow._data[CONF_POOL_VOLUME_M3] = 40  # noqa: SLF001
    forecast_flow._data[CONF_PUMP_NOMINAL_FLOW_M3H] = 10  # noqa: SLF001
    forecast_flow._data[CONF_HYDRAULIC_EFFICIENCY_FACTOR] = 0.75  # noqa: SLF001
    forecast_flow._data[CONF_CHLORINATOR_OUTPUT_GH] = 20  # noqa: SLF001
    forecast_flow._data[CONF_TARGET_FREE_CHLORINE_PPM] = 2  # noqa: SLF001

    result = await forecast_flow.async_step_hourly_packages(
        {
            CONF_ENABLE_HOURLY_CLOUDS_AND_WIND: True,
            CONF_ENABLE_POOL: False,
        }
    )

    assert result["step_id"] == "finalize"
    assert forecast_flow._data[CONF_ENABLE_POOL] is False  # noqa: SLF001
    assert CONF_POOL_VOLUME_M3 not in forecast_flow._data  # noqa: SLF001
    assert CONF_PUMP_NOMINAL_FLOW_M3H not in forecast_flow._data  # noqa: SLF001
    assert CONF_HYDRAULIC_EFFICIENCY_FACTOR not in forecast_flow._data  # noqa: SLF001
    assert CONF_CHLORINATOR_OUTPUT_GH not in forecast_flow._data  # noqa: SLF001
    assert CONF_TARGET_FREE_CHLORINE_PPM not in forecast_flow._data  # noqa: SLF001


async def test_pool_requires_clouds_and_wind_packages(
    forecast_flow: ForecastLocationSubentryFlowHandler,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pool configuration is rejected without the required hourly packages."""

    def _show_form(**kwargs: Any) -> dict[str, Any]:
        return {"type": "form", **kwargs}

    monkeypatch.setattr(forecast_flow, "async_show_form", _show_form)

    result = await forecast_flow.async_step_hourly_packages(
        {
            CONF_ENABLE_HOURLY_CLOUDS_AND_WIND: False,
            CONF_ENABLE_POOL: True,
        }
    )

    assert result["step_id"] == "hourly_packages"
    assert result["errors"] == {CONF_ENABLE_POOL: "pool_requires_hourly_packages"}


async def test_pool_step_stores_configuration(
    forecast_flow: ForecastLocationSubentryFlowHandler,
) -> None:
    """Pool values are stored in the forecast location subentry."""
    result = await forecast_flow.async_step_pool(
        {
            CONF_POOL_VOLUME_M3: 42.5,
            CONF_PUMP_NOMINAL_FLOW_M3H: 9.5,
            CONF_HYDRAULIC_EFFICIENCY_FACTOR: 0.8,
            CONF_CHLORINATOR_OUTPUT_GH: 18.0,
            CONF_TARGET_FREE_CHLORINE_PPM: 2.5,
        }
    )

    assert result["step_id"] == "finalize"
    assert forecast_flow._data[CONF_POOL_VOLUME_M3] == 42.5  # noqa: SLF001
    assert forecast_flow._data[CONF_PUMP_NOMINAL_FLOW_M3H] == 9.5  # noqa: SLF001
    assert forecast_flow._data[CONF_HYDRAULIC_EFFICIENCY_FACTOR] == 0.8  # noqa: SLF001
    assert forecast_flow._data[CONF_CHLORINATOR_OUTPUT_GH] == 18.0  # noqa: SLF001
    assert forecast_flow._data[CONF_TARGET_FREE_CHLORINE_PPM] == 2.5  # noqa: SLF001
