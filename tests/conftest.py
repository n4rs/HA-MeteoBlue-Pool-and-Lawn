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
"""Shared pytest fixtures for MeteoBlue API tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import httpx
import pool_and_lawn.api
import pytest
from homeassistant.components.weather import WeatherEntityDescription
from pool_and_lawn.const import CONF_FORECAST_TYPE, FORECAST_TYPE_DAILY
from pool_and_lawn.coordinator import _reshape_forecast_payload
from pool_and_lawn.weather import MeteoBlueWeather

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable


@pytest.fixture(scope="session")
def raw_daily_forecast_payload() -> dict[str, Any]:
    """Load the captured daily forecast fixture in the raw API shape."""
    fixture_path = Path(__file__).parent / "fixtures" / "daily_forecast.json"
    return json.loads(fixture_path.read_text())


@pytest.fixture(scope="session")
def raw_hourly_forecast_payload() -> dict[str, Any]:
    """Load the captured hourly forecast fixture in the raw API shape."""
    fixture_path = Path(__file__).parent / "fixtures" / "forecast.json"
    return json.loads(fixture_path.read_text())


@pytest.fixture(scope="session")
def daily_forecast_payload(
    raw_daily_forecast_payload: dict[str, Any],
) -> dict[str, Any]:
    """Return the daily forecast payload reshaped into coordinator shape."""
    return _reshape_forecast_payload(raw_daily_forecast_payload)


@pytest.fixture(scope="session")
def hourly_forecast_payload(
    raw_hourly_forecast_payload: dict[str, Any],
) -> dict[str, Any]:
    """Return the hourly forecast payload reshaped into coordinator shape."""
    return _reshape_forecast_payload(raw_hourly_forecast_payload)


@pytest.fixture(scope="session")
def hourly_only_forecast_payload(
    raw_hourly_forecast_payload: dict[str, Any],
) -> dict[str, Any]:
    """Return an hourly-only payload (daily section stripped), reshaped."""
    raw = {k: v for k, v in raw_hourly_forecast_payload.items() if k != "data_day"}
    return _reshape_forecast_payload(raw)


@pytest.fixture
def make_weather() -> Callable[..., MeteoBlueWeather]:
    """Return a factory that builds a MeteoBlueWeather with a stub coordinator."""

    def _factory(
        data: dict[str, Any] | None,
        forecast_type: str = FORECAST_TYPE_DAILY,
    ) -> MeteoBlueWeather:
        coordinator = MagicMock()
        coordinator.subentry.subentry_id = "test-subentry"
        coordinator.subentry.title = "Test Location"
        coordinator.subentry.data = {CONF_FORECAST_TYPE: forecast_type}
        coordinator.data = data
        description = WeatherEntityDescription(key="weather", name="Pool and Lawn")
        return MeteoBlueWeather(
            coordinator=coordinator,
            entity_description=description,
            platform_domain="weather",
        )

    return _factory


@pytest.fixture
async def make_client() -> AsyncIterator[
    Callable[[Callable[[httpx.Request], httpx.Response]], Any]
]:
    """Return a factory that builds a MeteoBlueApiClient with a mocked transport."""
    clients: list[httpx.AsyncClient] = []

    def _factory(
        handler: Callable[[httpx.Request], httpx.Response],
    ) -> Any:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        clients.append(client)
        return pool_and_lawn.api.MeteoBlueApiClient(client=client, api_key="test-key")

    yield _factory

    for client in clients:
        await client.aclose()
