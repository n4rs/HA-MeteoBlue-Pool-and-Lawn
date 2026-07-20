# Copyright 2026 n4rs. All rights reserved.
# See LICENSE for the terms that apply to HomeAssistant Pool and Lawn modifications.

"""Tests for the open-loop saltwater pool runtime calculator."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, timedelta, tzinfo
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from pool_and_lawn.pool import (
    DailyPoolWeather,
    PoolSettings,
    aggregate_daily_pool_weather,
    calculate_chlorine_demand,
    calculate_pool_pump_forecast,
    calculate_pool_pump_runtime,
    group_hourly_forecast_by_local_date,
)

UNITS_MS = {"windspeed": "ms-1", "gust": "ms-1"}


def _settings(**changes: float) -> PoolSettings:
    """Return representative pool settings with optional replacements."""
    values = {
        "volume_m3": 90.0,
        "pump_nominal_flow_m3h": 21.5,
        "hydraulic_efficiency_factor": 0.75,
        "chlorinator_output_gh": 25.0,
        "target_free_chlorine_ppm": 2.0,
    }
    values.update(changes)
    return PoolSettings(**values)


def _weather(**changes: Any) -> DailyPoolWeather:
    """Return weather matching the documented 2.15 ppm example."""
    values = {
        "forecast_date": date(2026, 7, 21),
        "forecast_day_offset": 1,
        "temperature_max": 32.0,
        "uv_index_max": 8.0,
        "uv_source": "meteoblue",
        "daylight_hours": 14.2,
        "cloud_cover_mean": 20.0,
        "precipitation_total": 0.0,
        "wind_mean_kmh": 8.0,
        "gust_max_kmh": 18.0,
    }
    values.update(changes)
    return DailyPoolWeather(**values)


def _solar_provider(forecast_date: date, timezone: tzinfo) -> tuple[datetime, datetime]:
    """Return a deterministic solar period for local-only tests."""
    midnight = datetime.combine(forecast_date, datetime.min.time(), timezone)
    return midnight + timedelta(hours=6), midnight + timedelta(hours=20)


def _hourly_day(  # noqa: PLR0913
    forecast_date: date,
    timezone: tzinfo,
    *,
    include_daylight: bool = True,
    include_uv: bool = True,
    include_cloud: bool = True,
    include_temperature: bool = True,
    include_wind: bool = True,
    include_gust: bool = True,
    include_rain: bool = True,
) -> dict[datetime, dict[str, Any]]:
    """Build one complete local hourly MeteoBlue-shaped day."""
    midnight = datetime.combine(forecast_date, datetime.min.time(), timezone)
    result: dict[datetime, dict[str, Any]] = {}
    for hour in range(24):
        values: dict[str, Any] = {}
        if include_temperature:
            values["temperature"] = 32
        if include_uv:
            values["uvindex"] = 8 if 6 <= hour < 20 else 0
        if include_cloud:
            values["totalcloudcover"] = 20
        if include_wind:
            values["windspeed"] = 8 / 3.6
        if include_gust:
            values["gust"] = 18 / 3.6
        if include_rain:
            values["precipitation"] = 0
        if include_daylight:
            values["isdaylight"] = 6 <= hour < 20
        result[midnight + timedelta(hours=hour)] = values
    return result


def test_documented_production_demand_and_runtime_example() -> None:
    """The documented 90 m³ and 25 g/h example produces about 7.74 hours."""
    result = calculate_pool_pump_runtime(_settings(), _weather())

    assert result.demand.estimated_ppm == pytest.approx(2.15)
    assert result.chlorine_production_ppm_per_hour == pytest.approx(25 / 90)
    assert result.chlorination_hours == pytest.approx(7.74, abs=0.01)
    assert result.raw_recommended_hours == result.chlorination_hours
    assert result.recommended_pump_hours == 7.7
    assert result.effective_flow_m3h == pytest.approx(16.125)
    assert result.estimated_circulated_volume_m3 == pytest.approx(124.1625)
    assert result.estimated_turnovers == pytest.approx(1.379583, abs=1e-6)


def test_no_turnover_minimum_is_applied() -> None:
    """A six-hour turnover cannot raise a three-hour chlorination runtime."""
    weather = _weather()
    demand = calculate_chlorine_demand(weather).estimated_ppm
    settings = _settings(
        pump_nominal_flow_m3h=20,
        hydraulic_efficiency_factor=0.75,
        chlorinator_output_gh=demand * 90 / 3,
    )

    result = calculate_pool_pump_runtime(settings, weather)

    assert settings.volume_m3 / result.effective_flow_m3h == pytest.approx(6)
    assert result.chlorination_hours == pytest.approx(3)
    assert result.recommended_pump_hours == 3


def test_pump_flow_only_changes_hydraulic_diagnostics() -> None:
    """Nominal pump flow never affects recommended chlorination hours."""
    slower = calculate_pool_pump_runtime(
        _settings(pump_nominal_flow_m3h=10), _weather()
    )
    faster = calculate_pool_pump_runtime(
        _settings(pump_nominal_flow_m3h=30), _weather()
    )

    assert slower.recommended_pump_hours == faster.recommended_pump_hours
    assert slower.chlorination_hours == faster.chlorination_hours
    assert slower.effective_flow_m3h != faster.effective_flow_m3h
    assert slower.estimated_circulated_volume_m3 != (
        faster.estimated_circulated_volume_m3
    )
    assert slower.estimated_turnovers != faster.estimated_turnovers


def test_target_only_changes_target_related_diagnostics() -> None:
    """Starting and ending at the same target makes runtime target-independent."""
    target_two = calculate_pool_pump_runtime(
        _settings(target_free_chlorine_ppm=2), _weather()
    )
    target_three = calculate_pool_pump_runtime(
        _settings(target_free_chlorine_ppm=3), _weather()
    )

    assert target_two.recommended_pump_hours == target_three.recommended_pump_hours
    assert target_two.chlorination_hours == target_three.chlorination_hours
    assert target_two.estimated_free_chlorine_without_generation == 0
    assert target_three.estimated_free_chlorine_without_generation == pytest.approx(
        0.85
    )
    assert target_two.as_attributes()["starting_free_chlorine_ppm"] == 2
    assert target_three.as_attributes()["starting_free_chlorine_ppm"] == 3
    assert (
        target_two.as_attributes()["estimated_free_chlorine_after_recommended_runtime"]
        == 2
    )
    assert (
        target_three.as_attributes()[
            "estimated_free_chlorine_after_recommended_runtime"
        ]
        == 3
    )


def test_runtime_is_physically_limited_to_twenty_four_hours() -> None:
    """An undersized chlorinator reports the raw value and caps the state."""
    result = calculate_pool_pump_runtime(_settings(chlorinator_output_gh=1), _weather())

    assert result.raw_recommended_hours > 24
    assert result.recommended_pump_hours == 24
    assert result.runtime_limited is True


def test_grouping_uses_local_dates_instead_of_utc_dates() -> None:
    """UTC timestamps around midnight are assigned to their Lisbon local date."""
    lisbon = ZoneInfo("Europe/Lisbon")
    forecast = {
        datetime(2026, 7, 20, 22, 30, tzinfo=UTC): {"temperature": 1},
        datetime(2026, 7, 20, 23, 30, tzinfo=UTC): {"temperature": 2},
    }

    grouped = group_hourly_forecast_by_local_date(forecast, lisbon)

    assert list(grouped) == [date(2026, 7, 20), date(2026, 7, 21)]


def test_multiple_forecast_days_produce_independent_stable_offsets() -> None:
    """Every available local date receives its own stable-offset calculation."""
    timezone = ZoneInfo("UTC")
    today = date(2026, 7, 20)
    forecast: dict[datetime, dict[str, Any]] = {}
    for offset in range(3):
        forecast.update(_hourly_day(today + timedelta(days=offset), timezone))
    for values in list(forecast.values())[24:48]:
        values["temperature"] = 17

    days = calculate_pool_pump_forecast(
        forecast,
        UNITS_MS,
        _settings(),
        today,
        timezone,
        _solar_provider,
        maximum_days=3,
    )

    assert [day.forecast_date for day in days] == [
        today + timedelta(days=offset) for offset in range(3)
    ]
    assert [day.forecast_day_offset for day in days] == [0, 1, 2]
    assert all(day.result is not None for day in days)
    assert days[0].result is not None
    assert days[1].result is not None
    assert days[0].result.recommended_pump_hours > days[1].result.recommended_pump_hours


def test_daylight_aggregations_use_flags_interval_and_explicit_wind_units() -> None:
    """Daylight weather excludes night values and converts m/s through metadata."""
    timezone = ZoneInfo("UTC")
    forecast_date = date(2026, 7, 20)
    forecast = _hourly_day(forecast_date, timezone)
    for timestamp, values in forecast.items():
        if timestamp.hour == 23:
            values.update(temperature=35, gust=100, totalcloudcover=100)
        if timestamp.hour == 2:
            values["precipitation"] = 3

    weather, reason = aggregate_daily_pool_weather(
        forecast_date,
        0,
        list(forecast.items()),
        UNITS_MS,
        timezone,
        _solar_provider,
    )

    assert reason is None
    assert weather is not None
    assert weather.temperature_max == 35
    assert weather.uv_index_max == 8
    assert weather.daylight_hours == 14
    assert weather.cloud_cover_mean == 20
    assert weather.precipitation_total == 3
    assert weather.wind_mean_kmh == pytest.approx(8)
    assert weather.gust_max_kmh == pytest.approx(18)


def test_missing_optional_wind_gust_and_rain_use_neutral_defaults() -> None:
    """Missing wind, gust, and rain remain valid and do not add demand."""
    timezone = ZoneInfo("UTC")
    forecast_date = date(2026, 7, 20)
    forecast = _hourly_day(
        forecast_date,
        timezone,
        include_wind=False,
        include_gust=False,
        include_rain=False,
    )

    weather, reason = aggregate_daily_pool_weather(
        forecast_date,
        0,
        list(forecast.items()),
        {},
        timezone,
        _solar_provider,
    )

    assert reason is None
    assert weather is not None
    assert weather.wind_mean_kmh is None
    assert weather.gust_max_kmh is None
    assert weather.precipitation_total == 0
    assert calculate_chlorine_demand(weather).wind_adjustment_ppm == 0
    assert calculate_chlorine_demand(weather).rain_adjustment_ppm == 0


def test_missing_uv_is_estimated_from_daylight_and_cloud_cover() -> None:
    """UV fallback uses dynamic daylight length and mean daytime clouds."""
    timezone = ZoneInfo("UTC")
    forecast_date = date(2026, 7, 20)
    forecast = _hourly_day(forecast_date, timezone, include_uv=False)
    for values in forecast.values():
        values["totalcloudcover"] = 80

    weather, reason = aggregate_daily_pool_weather(
        forecast_date,
        0,
        list(forecast.items()),
        UNITS_MS,
        timezone,
        _solar_provider,
    )

    assert reason is None
    assert weather is not None
    assert weather.uv_source == "estimated"
    assert weather.uv_index_max == 5


@pytest.mark.parametrize(
    ("day_kwargs", "solar_provider", "expected_reason"),
    [
        ({"include_temperature": False}, _solar_provider, "missing_temperature"),
        (
            {"include_uv": False, "include_cloud": False},
            _solar_provider,
            "missing_uv_and_cloud_cover",
        ),
        (
            {"include_daylight": False},
            lambda _date, _timezone: None,
            "missing_solar_period",
        ),
    ],
)
def test_missing_essential_data_makes_day_unavailable(
    day_kwargs: dict[str, bool],
    solar_provider: Any,
    expected_reason: str,
) -> None:
    """Temperature, UV/cloud, and solar period are essential inputs."""
    timezone = ZoneInfo("UTC")
    forecast_date = date(2026, 7, 20)
    forecast = _hourly_day(forecast_date, timezone, **day_kwargs)

    weather, reason = aggregate_daily_pool_weather(
        forecast_date,
        0,
        list(forecast.items()),
        UNITS_MS,
        timezone,
        solar_provider,
    )

    assert weather is None
    assert reason == expected_reason


def test_non_finite_and_non_numeric_values_are_ignored() -> None:
    """NaN, infinity, strings, and None do not contaminate daily aggregates."""
    timezone = ZoneInfo("UTC")
    forecast_date = date(2026, 7, 20)
    forecast = _hourly_day(forecast_date, timezone)
    values = list(forecast.values())
    values[0].update(temperature=math.nan, precipitation=math.inf)
    values[1].update(temperature="bad", precipitation=None)

    weather, reason = aggregate_daily_pool_weather(
        forecast_date,
        0,
        list(forecast.items()),
        UNITS_MS,
        timezone,
        _solar_provider,
    )

    assert reason is None
    assert weather is not None
    assert weather.temperature_max == 32
    assert weather.precipitation_total == 0


def test_captured_meteoblue_hourly_payload_calculates_full_horizon(
    hourly_forecast_payload: dict[str, Any],
) -> None:
    """The captured API field names and units produce seven local estimates."""
    hourly = hourly_forecast_payload["forecast_data_hourly"]
    first_timestamp = min(hourly)
    timezone = first_timestamp.tzinfo
    assert timezone is not None

    days = calculate_pool_pump_forecast(
        hourly,
        hourly_forecast_payload["units"],
        _settings(),
        first_timestamp.date(),
        timezone,
        _solar_provider,
    )

    assert len(days) == 7
    assert all(day.result is not None for day in days)
    assert all(
        day.result.weather.uv_source == "meteoblue"
        for day in days
        if day.result is not None
    )
    assert all(
        day.result.weather.wind_mean_kmh is not None
        for day in days
        if day.result is not None
    )
