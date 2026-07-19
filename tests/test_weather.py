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
"""Tests for the MeteoBlue weather entity."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

import pytest
from dateutil.tz import tzoffset
from pool_and_lawn.const import FORECAST_TYPE_DAILY, FORECAST_TYPE_HOURLY

if TYPE_CHECKING:
    from collections.abc import Callable

    from pool_and_lawn.weather import MeteoBlueWeather


INSTANT_PROPERTIES = (
    "condition",
    "native_temperature",
    "native_apparent_temperature",
    "humidity",
    "native_pressure",
    "native_wind_speed",
    "native_wind_gust_speed",
    "wind_bearing",
    "uv_index",
    "cloud_coverage",
)

CEST = tzoffset("CEST", 2 * 3600)

# The daily fixture covers 2026-04-16..2026-04-22; index 3 is 2026-04-19.
CURRENT_DAILY_INDEX = 3
CURRENT_DAILY_NOW = datetime(2026, 4, 19, 12, 0, tzinfo=CEST)

# The hourly fixture starts 2026-04-20 00:00 CEST; index 30 is 2026-04-21 06:00.
CURRENT_HOURLY_INDEX = 30
CURRENT_HOURLY_NOW = datetime(2026, 4, 21, 6, 30, tzinfo=CEST)


@pytest.fixture
def freeze_now(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[datetime], None]:
    """Pin dt_util.now() to a fixed value for the duration of the test."""

    def _freeze(value: datetime) -> None:
        monkeypatch.setattr("homeassistant.util.dt.now", lambda: value)

    return _freeze


def _current_daily_entry(payload: dict[str, Any]) -> dict[str, Any]:
    entries = payload["forecast_data_daily"]
    return entries[sorted(entries)[CURRENT_DAILY_INDEX]]


def _current_hourly_entry(payload: dict[str, Any]) -> dict[str, Any]:
    entries = payload["forecast_data_hourly"]
    return entries[sorted(entries)[CURRENT_HOURLY_INDEX]]


def test_condition_maps_current_daily_pictocode(
    make_weather: Callable[..., MeteoBlueWeather],
    daily_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    freeze_now(CURRENT_DAILY_NOW)
    weather = make_weather(daily_forecast_payload)
    # Fixture has pictocode[3] == 3 which maps to partlycloudy in the daily table.
    assert weather.condition == "partlycloudy"


def test_native_temperature_returns_current_daily_value(
    make_weather: Callable[..., MeteoBlueWeather],
    daily_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    freeze_now(CURRENT_DAILY_NOW)
    weather = make_weather(daily_forecast_payload)
    expected = _current_daily_entry(daily_forecast_payload)["temperature_instant"]
    assert weather.native_temperature == expected


def test_native_apparent_temperature_returns_current_daily_value(
    make_weather: Callable[..., MeteoBlueWeather],
    daily_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    freeze_now(CURRENT_DAILY_NOW)
    weather = make_weather(daily_forecast_payload)
    expected = _current_daily_entry(daily_forecast_payload)["felttemperature_mean"]
    assert weather.native_apparent_temperature == expected


def test_humidity_returns_current_daily_value(
    make_weather: Callable[..., MeteoBlueWeather],
    daily_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    freeze_now(CURRENT_DAILY_NOW)
    weather = make_weather(daily_forecast_payload)
    expected = _current_daily_entry(daily_forecast_payload)["relativehumidity_mean"]
    assert weather.humidity == expected


def test_native_pressure_returns_current_daily_value(
    make_weather: Callable[..., MeteoBlueWeather],
    daily_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    freeze_now(CURRENT_DAILY_NOW)
    weather = make_weather(daily_forecast_payload)
    expected = _current_daily_entry(daily_forecast_payload)["sealevelpressure_mean"]
    assert weather.native_pressure == expected


def test_native_wind_speed_returns_current_daily_value(
    make_weather: Callable[..., MeteoBlueWeather],
    daily_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    freeze_now(CURRENT_DAILY_NOW)
    weather = make_weather(daily_forecast_payload)
    expected = _current_daily_entry(daily_forecast_payload)["windspeed_mean"]
    assert weather.native_wind_speed == expected


def test_native_wind_gust_speed_returns_current_daily_value(
    make_weather: Callable[..., MeteoBlueWeather],
    daily_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    freeze_now(CURRENT_DAILY_NOW)
    weather = make_weather(daily_forecast_payload)
    expected = _current_daily_entry(daily_forecast_payload).get("gust_max")
    assert weather.native_wind_gust_speed == expected


def test_wind_bearing_returns_current_daily_value(
    make_weather: Callable[..., MeteoBlueWeather],
    daily_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    freeze_now(CURRENT_DAILY_NOW)
    weather = make_weather(daily_forecast_payload)
    expected = _current_daily_entry(daily_forecast_payload)["winddirection"]
    assert weather.wind_bearing == expected


def test_uv_index_returns_current_daily_value(
    make_weather: Callable[..., MeteoBlueWeather],
    daily_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    freeze_now(CURRENT_DAILY_NOW)
    weather = make_weather(daily_forecast_payload)
    expected = _current_daily_entry(daily_forecast_payload)["uvindex"]
    assert weather.uv_index == expected


def test_daily_falls_back_to_first_entry_when_now_precedes_forecast(
    make_weather: Callable[..., MeteoBlueWeather],
    daily_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    daily = daily_forecast_payload["forecast_data_daily"]
    first_key = sorted(daily)[0]
    freeze_now(datetime(2020, 1, 1, tzinfo=CEST))
    weather = make_weather(daily_forecast_payload)
    expected = daily[first_key]["temperature_instant"]
    assert weather.native_temperature == expected


def test_daily_uses_last_entry_when_now_exceeds_forecast(
    make_weather: Callable[..., MeteoBlueWeather],
    daily_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    daily = daily_forecast_payload["forecast_data_daily"]
    last_key = sorted(daily)[-1]
    freeze_now(datetime(2099, 1, 1, tzinfo=CEST))
    weather = make_weather(daily_forecast_payload)
    expected = daily[last_key]["temperature_instant"]
    assert weather.native_temperature == expected


def test_cloud_coverage_returns_current_daily_value(
    make_weather: Callable[..., MeteoBlueWeather],
    daily_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    freeze_now(CURRENT_DAILY_NOW)
    weather = make_weather(daily_forecast_payload)
    expected = _current_daily_entry(daily_forecast_payload).get("totalcloudcover_mean")
    assert weather.cloud_coverage == expected


def test_always_none_properties(
    make_weather: Callable[..., MeteoBlueWeather],
    daily_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    freeze_now(CURRENT_DAILY_NOW)
    weather = make_weather(daily_forecast_payload)
    assert weather.native_visibility is None
    assert weather.native_dew_point is None


@pytest.mark.parametrize("prop", INSTANT_PROPERTIES)
def test_properties_return_none_when_coordinator_data_missing(
    make_weather: Callable[..., MeteoBlueWeather],
    prop: str,
) -> None:
    weather = make_weather(None)
    assert getattr(weather, prop) is None


@pytest.mark.parametrize("prop", INSTANT_PROPERTIES)
def test_properties_return_none_when_field_missing(
    make_weather: Callable[..., MeteoBlueWeather],
    prop: str,
) -> None:
    weather = make_weather(
        {"forecast_data_hourly": {}, "forecast_data_daily": {}},
    )
    assert getattr(weather, prop) is None


def test_condition_maps_current_hourly_pictocode(
    make_weather: Callable[..., MeteoBlueWeather],
    hourly_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    freeze_now(CURRENT_HOURLY_NOW)
    weather = make_weather(hourly_forecast_payload, FORECAST_TYPE_HOURLY)
    # Fixture has pictocode[30] == 22 which maps to cloudy in the hourly table.
    assert weather.condition == "cloudy"


def test_native_temperature_returns_current_hourly_value(
    make_weather: Callable[..., MeteoBlueWeather],
    hourly_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    freeze_now(CURRENT_HOURLY_NOW)
    weather = make_weather(hourly_forecast_payload, FORECAST_TYPE_HOURLY)
    expected = _current_hourly_entry(hourly_forecast_payload)["temperature"]
    assert weather.native_temperature == expected


def test_native_apparent_temperature_returns_current_hourly_value(
    make_weather: Callable[..., MeteoBlueWeather],
    hourly_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    freeze_now(CURRENT_HOURLY_NOW)
    weather = make_weather(hourly_forecast_payload, FORECAST_TYPE_HOURLY)
    expected = _current_hourly_entry(hourly_forecast_payload)["felttemperature"]
    assert weather.native_apparent_temperature == expected


def test_humidity_returns_current_hourly_value(
    make_weather: Callable[..., MeteoBlueWeather],
    hourly_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    freeze_now(CURRENT_HOURLY_NOW)
    weather = make_weather(hourly_forecast_payload, FORECAST_TYPE_HOURLY)
    expected = _current_hourly_entry(hourly_forecast_payload)["relativehumidity"]
    assert weather.humidity == expected


def test_native_pressure_returns_current_hourly_value(
    make_weather: Callable[..., MeteoBlueWeather],
    hourly_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    freeze_now(CURRENT_HOURLY_NOW)
    weather = make_weather(hourly_forecast_payload, FORECAST_TYPE_HOURLY)
    expected = _current_hourly_entry(hourly_forecast_payload)["sealevelpressure"]
    assert weather.native_pressure == expected


def test_native_wind_speed_returns_current_hourly_value(
    make_weather: Callable[..., MeteoBlueWeather],
    hourly_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    freeze_now(CURRENT_HOURLY_NOW)
    weather = make_weather(hourly_forecast_payload, FORECAST_TYPE_HOURLY)
    expected = _current_hourly_entry(hourly_forecast_payload)["windspeed"]
    assert weather.native_wind_speed == expected


def test_native_wind_gust_speed_returns_current_hourly_value(
    make_weather: Callable[..., MeteoBlueWeather],
    hourly_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    freeze_now(CURRENT_HOURLY_NOW)
    weather = make_weather(hourly_forecast_payload, FORECAST_TYPE_HOURLY)
    expected = _current_hourly_entry(hourly_forecast_payload)["gust"]
    assert weather.native_wind_gust_speed == expected


def test_wind_bearing_returns_current_hourly_value(
    make_weather: Callable[..., MeteoBlueWeather],
    hourly_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    freeze_now(CURRENT_HOURLY_NOW)
    weather = make_weather(hourly_forecast_payload, FORECAST_TYPE_HOURLY)
    expected = _current_hourly_entry(hourly_forecast_payload)["winddirection"]
    assert weather.wind_bearing == expected


def test_cloud_coverage_returns_current_hourly_value(
    make_weather: Callable[..., MeteoBlueWeather],
    hourly_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    freeze_now(CURRENT_HOURLY_NOW)
    weather = make_weather(hourly_forecast_payload, FORECAST_TYPE_HOURLY)
    expected = _current_hourly_entry(hourly_forecast_payload)["totalcloudcover"]
    assert weather.cloud_coverage == expected


def test_uv_index_returns_current_hourly_value(
    make_weather: Callable[..., MeteoBlueWeather],
    hourly_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    freeze_now(CURRENT_HOURLY_NOW)
    weather = make_weather(hourly_forecast_payload, FORECAST_TYPE_HOURLY)
    expected = _current_hourly_entry(hourly_forecast_payload)["uvindex"]
    assert weather.uv_index == expected


def test_hourly_picks_entry_between_keys(
    make_weather: Callable[..., MeteoBlueWeather],
    hourly_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    # At 06:30 between 06:00 and 07:00, the 06:00 entry should be selected.
    hourly = hourly_forecast_payload["forecast_data_hourly"]
    key_at_six = sorted(hourly)[CURRENT_HOURLY_INDEX]
    freeze_now(key_at_six.replace(minute=30))
    weather = make_weather(hourly_forecast_payload, FORECAST_TYPE_HOURLY)
    expected = hourly[key_at_six]["temperature"]
    assert weather.native_temperature == expected


def test_daily_type_uses_daily_keys_even_if_hourly_present(
    make_weather: Callable[..., MeteoBlueWeather],
    daily_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    freeze_now(CURRENT_DAILY_NOW)
    weather = make_weather(daily_forecast_payload, FORECAST_TYPE_DAILY)
    expected = _current_daily_entry(daily_forecast_payload)["temperature_instant"]
    assert weather.native_temperature == expected


async def test_async_forecast_daily_builds_entries(
    make_weather: Callable[..., MeteoBlueWeather],
    daily_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    freeze_now(datetime(2026, 4, 16, 0, 0, tzinfo=CEST))
    weather = make_weather(daily_forecast_payload)
    result = await weather.async_forecast_daily()

    assert result is not None
    daily = daily_forecast_payload["forecast_data_daily"]
    daily_keys = sorted(daily)
    assert len(result) == len(daily_keys)

    first = result[0]
    first_entry = daily[daily_keys[0]]
    # First fixture date is 2026-04-16, CEST = UTC+2.
    assert first["datetime"] == "2026-04-16T00:00:00+02:00"
    assert first["condition"] == "partlycloudy"  # pictocode 3
    assert first["native_temperature"] == first_entry["temperature_max"]
    assert first["native_templow"] == first_entry["temperature_min"]
    assert first["native_precipitation"] == first_entry["precipitation"]
    assert (
        first["precipitation_probability"] == first_entry["precipitation_probability"]
    )
    assert first["native_wind_speed"] == first_entry["windspeed_mean"]
    assert first["native_wind_gust_speed"] == first_entry.get("gust_max")
    assert first["wind_bearing"] == first_entry["winddirection"]
    assert first["cloud_coverage"] == first_entry.get("totalcloudcover_mean")


async def test_async_forecast_daily_returns_none_when_no_data(
    make_weather: Callable[..., MeteoBlueWeather],
) -> None:
    weather = make_weather(None)
    assert await weather.async_forecast_daily() is None


async def test_async_forecast_daily_aggregates_from_hourly(
    make_weather: Callable[..., MeteoBlueWeather],
    hourly_only_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    freeze_now(datetime(2026, 4, 20, 0, 0, tzinfo=CEST))
    weather = make_weather(hourly_only_forecast_payload, FORECAST_TYPE_HOURLY)
    result = await weather.async_forecast_daily()

    assert result is not None
    daily = hourly_only_forecast_payload["forecast_data_daily"]
    daily_keys = sorted(daily)
    # One Forecast per aggregated daily entry produced by the coordinator.
    assert len(result) == len(daily_keys)
    assert [f["datetime"] for f in result] == [k.isoformat() for k in daily_keys]

    # The entity passes the coordinator's aggregated values through verbatim.
    first = result[0]
    first_entry = daily[daily_keys[0]]
    assert first["native_temperature"] == first_entry["temperature_max"]
    assert first["native_templow"] == first_entry["temperature_min"]
    assert first["native_precipitation"] == first_entry["precipitation"]
    assert (
        first["precipitation_probability"] == first_entry["precipitation_probability"]
    )
    assert first["native_wind_speed"] == first_entry["windspeed_mean"]
    assert first["native_wind_gust_speed"] == first_entry["gust_max"]
    assert first["wind_bearing"] == first_entry["winddirection"]
    assert first["cloud_coverage"] == first_entry["totalcloudcover_mean"]
    assert first["condition"] == first_entry["condition"]


async def test_async_forecast_daily_skips_partial_day(
    make_weather: Callable[..., MeteoBlueWeather],
    hourly_only_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    """A day without a 12:00 entry is skipped rather than aggregated."""
    freeze_now(datetime(2026, 4, 20, 0, 0, tzinfo=CEST))
    weather = make_weather(hourly_only_forecast_payload, FORECAST_TYPE_HOURLY)
    result = await weather.async_forecast_daily()

    assert result is not None
    # Fixture hourly series ends at 2026-04-27 00:00 (single entry, no midday);
    # that day must not appear in the aggregated daily forecast.
    result_dates = {f["datetime"][:10] for f in result}
    assert "2026-04-27" not in result_dates

    daily = hourly_only_forecast_payload["forecast_data_daily"]
    last_key = sorted(daily)[-1]
    assert last_key.date().isoformat() == "2026-04-26"
    last_entry = daily[last_key]
    last = result[-1]
    assert last["datetime"] == last_key.isoformat()
    assert last["native_temperature"] == last_entry["temperature_max"]
    assert last["native_templow"] == last_entry["temperature_min"]
    assert last["condition"] == last_entry["condition"]


async def test_async_forecast_daily_prefers_daily_when_both_present(
    make_weather: Callable[..., MeteoBlueWeather],
    hourly_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    """When the API returns data_day, those values win over hourly aggregates."""
    freeze_now(datetime(2026, 4, 16, 0, 0, tzinfo=CEST))
    weather = make_weather(hourly_forecast_payload, FORECAST_TYPE_HOURLY)
    result = await weather.async_forecast_daily()

    assert result is not None
    daily = hourly_forecast_payload["forecast_data_daily"]
    daily_keys = sorted(daily)
    assert len(result) == len(daily_keys)
    # First entry values come from the daily section (temperature_max), not
    # aggregated hourly data.
    first_entry = daily[daily_keys[0]]
    assert result[0]["native_temperature"] == first_entry["temperature_max"]


async def test_async_forecast_daily_returns_empty_when_keys_missing(
    make_weather: Callable[..., MeteoBlueWeather],
) -> None:
    weather = make_weather(
        {"forecast_data_hourly": {}, "forecast_data_daily": {}},
    )
    assert await weather.async_forecast_daily() == []


async def test_async_forecast_hourly_builds_entries(
    make_weather: Callable[..., MeteoBlueWeather],
    hourly_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    freeze_now(datetime(2026, 4, 20, 0, 0, tzinfo=CEST))
    weather = make_weather(hourly_forecast_payload, FORECAST_TYPE_HOURLY)
    result = await weather.async_forecast_hourly()

    assert result is not None
    hourly = hourly_forecast_payload["forecast_data_hourly"]
    hourly_keys = sorted(hourly)
    assert len(result) == len(hourly_keys)

    first = result[0]
    first_entry = hourly[hourly_keys[0]]
    # First fixture hour is 2026-04-20 00:00, CEST = UTC+2.
    assert first["datetime"] == "2026-04-20T00:00:00+02:00"
    # pictocode[0] == 31 is hourly-only and maps to "rainy".
    assert first["condition"] == "rainy"
    assert first["native_temperature"] == first_entry["temperature"]
    assert first["native_apparent_temperature"] == first_entry["felttemperature"]
    assert first["native_precipitation"] == first_entry["precipitation"]
    assert (
        first["precipitation_probability"] == first_entry["precipitation_probability"]
    )
    assert first["native_pressure"] == first_entry["sealevelpressure"]
    assert first["native_wind_speed"] == first_entry["windspeed"]
    assert first["native_wind_gust_speed"] == first_entry["gust"]
    assert first["wind_bearing"] == first_entry["winddirection"]
    assert first["humidity"] == first_entry["relativehumidity"]
    assert first["cloud_coverage"] == first_entry["totalcloudcover"]


async def test_async_forecast_hourly_returns_none_when_no_data(
    make_weather: Callable[..., MeteoBlueWeather],
) -> None:
    weather = make_weather(None)
    assert await weather.async_forecast_hourly() is None


async def test_async_forecast_hourly_returns_entries_regardless_of_forecast_type(
    make_weather: Callable[..., MeteoBlueWeather],
    hourly_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    # The method itself no longer gates on forecast type; gating lives in
    # supported_features, so HA only calls it when FORECAST_HOURLY is declared.
    freeze_now(datetime(2026, 4, 20, 0, 0, tzinfo=CEST))
    weather = make_weather(hourly_forecast_payload, FORECAST_TYPE_DAILY)
    result = await weather.async_forecast_hourly()
    assert result is not None
    assert len(result) == len(hourly_forecast_payload["forecast_data_hourly"])


async def test_async_forecast_hourly_filters_past_entries(
    make_weather: Callable[..., MeteoBlueWeather],
    hourly_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    """Past hourly entries are dropped; the current hour is kept."""
    hourly = hourly_forecast_payload["forecast_data_hourly"]
    keys = sorted(hourly)
    # Freeze 30 minutes into the entry at CURRENT_HOURLY_INDEX (06:00 → 06:30):
    # that entry covers the current hour and must be kept; entries before it
    # have already passed and must be excluded.
    current_key = keys[CURRENT_HOURLY_INDEX]
    freeze_now(current_key.replace(minute=30))

    weather = make_weather(hourly_forecast_payload, FORECAST_TYPE_HOURLY)
    result = await weather.async_forecast_hourly()

    assert result is not None
    expected_keys = [k for k in keys if k >= current_key]
    assert [f["datetime"] for f in result] == [k.isoformat() for k in expected_keys]
    assert result[0]["datetime"] == current_key.isoformat()


async def test_async_forecast_daily_filters_past_entries(
    make_weather: Callable[..., MeteoBlueWeather],
    daily_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    """Past daily entries are dropped; today's entry is kept."""
    daily = daily_forecast_payload["forecast_data_daily"]
    keys = sorted(daily)
    # CURRENT_DAILY_NOW is 2026-04-19 12:00; the 2026-04-19 midnight entry is
    # the current day and must be kept, while 2026-04-16..04-18 must be dropped.
    freeze_now(CURRENT_DAILY_NOW)

    weather = make_weather(daily_forecast_payload)
    result = await weather.async_forecast_daily()

    assert result is not None
    today_key = keys[CURRENT_DAILY_INDEX]
    expected_keys = [k for k in keys if k >= today_key]
    assert [f["datetime"] for f in result] == [k.isoformat() for k in expected_keys]
    assert result[0]["datetime"] == today_key.isoformat()


async def test_async_forecast_hourly_returns_empty_when_all_past(
    make_weather: Callable[..., MeteoBlueWeather],
    hourly_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    """When every hourly entry has already passed, an empty list is returned."""
    freeze_now(datetime(2099, 1, 1, tzinfo=CEST))
    weather = make_weather(hourly_forecast_payload, FORECAST_TYPE_HOURLY)
    assert await weather.async_forecast_hourly() == []


async def test_async_forecast_daily_returns_empty_when_all_past(
    make_weather: Callable[..., MeteoBlueWeather],
    daily_forecast_payload: dict[str, Any],
    freeze_now: Callable[[datetime], None],
) -> None:
    """When every daily entry has already passed, an empty list is returned."""
    freeze_now(datetime(2099, 1, 1, tzinfo=CEST))
    weather = make_weather(daily_forecast_payload)
    assert await weather.async_forecast_daily() == []
