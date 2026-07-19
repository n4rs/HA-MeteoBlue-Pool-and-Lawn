# Copyright 2026 n4rs. All rights reserved.
# See LICENSE for the terms that apply to HomeAssistant Pool and Lawn modifications.

"""Tests for the multi-day lawn irrigation calculator."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, timedelta, tzinfo
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from pool_and_lawn.irrigation import (
    IRRIGATION_FORECAST_DAYS,
    apply_rain_correction,
    calculate_irrigation_forecast,
    calculate_irrigation_level_for_day,
    cloud_points,
    group_hourly_forecast_by_local_date,
    gust_points,
    humidity_points,
    initial_irrigation_level,
    mean_wind_points,
    month_points,
    temperature_points,
)

UNITS_MS = {"windspeed": "ms-1", "gust": "ms-1"}


def _solar_provider(forecast_date: date, timezone: tzinfo) -> tuple[datetime, datetime]:
    """Return a deterministic dynamic solar period for tests."""
    return (
        datetime.combine(forecast_date, datetime.min.time(), timezone)
        + timedelta(hours=6),
        datetime.combine(forecast_date, datetime.min.time(), timezone)
        + timedelta(hours=20),
    )


def _hourly_day(  # noqa: PLR0913
    forecast_date: date,
    timezone: ZoneInfo,
    *,
    temperature: float = 35,
    humidity: float = 40,
    windspeed: float = 8,
    gust: float | None = 13,
    cloud_cover: float = 10,
    precipitation: float = 0,
    precipitation_probability: float | None = 0,
    include_daylight: bool = True,
) -> dict[datetime, dict[str, Any]]:
    """Build a complete local hourly forecast day."""
    result: dict[datetime, dict[str, Any]] = {}
    midnight = datetime.combine(forecast_date, datetime.min.time(), timezone)
    for hour in range(24):
        values: dict[str, Any] = {
            "temperature": temperature,
            "relativehumidity": humidity,
            "windspeed": windspeed,
            "totalcloudcover": cloud_cover,
            "precipitation": precipitation,
        }
        if gust is not None:
            values["gust"] = gust
        if precipitation_probability is not None:
            values["precipitation_probability"] = precipitation_probability
        if include_daylight:
            values["isdaylight"] = 6 <= hour < 20
        result[midnight + timedelta(hours=hour)] = values
    return result


@pytest.mark.parametrize(
    ("value", "expected"),
    [(17.99, 0), (18, 1), (23, 2), (28, 3), (33, 4)],
)
def test_temperature_score_boundaries(value: float, expected: int) -> None:
    """Temperature thresholds are inclusive at their lower bound."""
    assert temperature_points(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(75, 0), (74.99, 1), (60, 1), (59.99, 2), (45, 2), (44.99, 3)],
)
def test_humidity_score_boundaries(value: float, expected: int) -> None:
    """Humidity thresholds follow the specified descending ranges."""
    assert humidity_points(value) == expected


@pytest.mark.parametrize(
    ("scorer", "value", "expected"),
    [
        (mean_wind_points, 7.99, 0),
        (mean_wind_points, 8, 1),
        (mean_wind_points, 15, 2),
        (mean_wind_points, 25, 3),
        (gust_points, 19.99, 0),
        (gust_points, 20, 1),
        (gust_points, 30, 2),
        (gust_points, 45, 3),
        (cloud_points, 80, 0),
        (cloud_points, 79.99, 1),
        (cloud_points, 60, 1),
        (cloud_points, 59.99, 2),
        (cloud_points, 30, 2),
        (cloud_points, 29.99, 3),
    ],
)
def test_weather_score_boundaries(scorer: Any, value: float, expected: int) -> None:
    """Wind, gust, and cloud scoring honors every exact boundary."""
    assert scorer(value) == expected


def test_month_and_base_level_boundaries() -> None:
    """Season and base-score mappings use the concrete forecast month."""
    assert [month_points(month) for month in range(1, 13)] == [
        0,
        0,
        1,
        1,
        2,
        3,
        3,
        3,
        2,
        1,
        0,
        0,
    ]
    assert [initial_irrigation_level(score) for score in (0, 2, 3, 5, 6, 8)] == [
        0,
        0,
        1,
        1,
        2,
        2,
    ]
    assert [initial_irrigation_level(score) for score in (9, 11, 12, 14, 15, 16)] == [
        3,
        3,
        4,
        4,
        5,
        5,
    ]


@pytest.mark.parametrize(
    ("weighted", "expected"),
    [(0.49, 5), (0.5, 4), (1.5, 3), (3, 2), (5, 0)],
)
def test_rain_correction_boundaries(weighted: float, expected: int) -> None:
    """Weighted precipitation reduces the initial level at exact boundaries."""
    assert apply_rain_correction(5, weighted, weighted, 39) == expected


def test_significant_rain_forces_zero() -> None:
    """Significant gross rain with sufficient probability forces level zero."""
    assert apply_rain_correction(5, 0, 8, 40) == 0
    assert apply_rain_correction(5, 0, 8, 39.99) == 5


def test_grouping_converts_to_local_date_across_midnight_and_dst() -> None:
    """Grouping uses local dates and remains correct through a DST transition."""
    lisbon = ZoneInfo("Europe/Lisbon")
    forecast = {
        datetime(2026, 7, 18, 23, 30, tzinfo=UTC): {"temperature": 1},
        datetime(2026, 3, 29, 0, 30, tzinfo=UTC): {"temperature": 2},
        datetime(2026, 3, 29, 1, 30, tzinfo=UTC): {"temperature": 3},
        datetime(2026, 7, 19, 0, 30): {"temperature": 4},  # noqa: DTZ001
    }

    grouped = group_hourly_forecast_by_local_date(forecast, lisbon)

    assert grouped[date(2026, 7, 19)][0][0].hour == 0
    assert [period[0].hour for period in grouped[date(2026, 3, 29)]] == [0, 2]
    assert sum(len(periods) for periods in grouped.values()) == 3


def test_isdaylight_windows_exclude_night_gusts_and_use_mps_units() -> None:
    """Night gusts cannot inflate daytime demand and m/s is converted explicitly."""
    timezone = ZoneInfo("Europe/Lisbon")
    forecast_date = date(2026, 7, 19)
    forecast = _hourly_day(forecast_date, timezone, windspeed=3, gust=5)
    for timestamp, values in forecast.items():
        if not values["isdaylight"]:
            values["gust"] = 100
        if timestamp.hour == 23:
            values["temperature"] = 36

    day = calculate_irrigation_level_for_day(
        forecast_date,
        0,
        list(forecast.items()),
        UNITS_MS,
        timezone,
        _solar_provider,
    )

    assert day.result is not None
    assert day.result.temperature_max == 36
    assert day.result.gust_max_kmh == 18
    assert day.result.gust_points == 0
    assert day.result.solar_windows.source == "meteoblue_isdaylight"
    assert day.result.solar_windows.sunrise.hour == 6
    assert day.result.solar_windows.sunset.hour == 20
    assert day.result.core_periods_used == 10


def test_astral_fallback_for_future_day_without_isdaylight() -> None:
    """Astral-compatible per-date fallback supplies dynamic future solar windows."""
    timezone = ZoneInfo("Europe/Lisbon")
    forecast_date = date(2026, 12, 20)
    forecast = _hourly_day(
        forecast_date,
        timezone,
        include_daylight=False,
    )
    calls: list[date] = []

    def provider(day: date, zone: tzinfo) -> tuple[datetime, datetime]:
        calls.append(day)
        midnight = datetime.combine(day, datetime.min.time(), zone)
        return midnight + timedelta(hours=8), midnight + timedelta(hours=17)

    day = calculate_irrigation_level_for_day(
        forecast_date,
        3,
        list(forecast.items()),
        UNITS_MS,
        timezone,
        provider,
    )

    assert calls == [forecast_date]
    assert day.result is not None
    assert day.result.solar_windows.source == "astral"
    assert day.result.solar_windows.sunrise.hour == 8
    assert day.result.solar_windows.sunset.hour == 17
    assert day.result.forecast_day_offset == 3


def test_short_day_uses_documented_window_fallbacks() -> None:
    """Short solar periods use daylight observations instead of fixed civil hours."""
    timezone = ZoneInfo("UTC")
    forecast_date = date(2026, 12, 20)
    forecast = _hourly_day(forecast_date, timezone)
    for timestamp, values in forecast.items():
        values["isdaylight"] = 10 <= timestamp.hour < 14

    day = calculate_irrigation_level_for_day(
        forecast_date,
        0,
        list(forecast.items()),
        UNITS_MS,
        timezone,
        _solar_provider,
    )

    assert day.result is not None
    attributes = day.result.as_attributes()
    assert attributes["core_window_fallback_used"] is True
    assert attributes["core_window_used"] == "all_daylight"
    assert attributes["humidity_window_fallback_used"] is True
    assert attributes["humidity_window_used"] == "second_half_daylight"
    assert attributes["core_periods_used"] == 4
    assert attributes["humidity_periods_used"] == 2


def test_calculates_all_seven_stable_offsets_and_levels_zero_four_five() -> None:
    """A seven-day hourly horizon produces seven stable daily offsets."""
    timezone = ZoneInfo("UTC")
    first_date = date(2026, 7, 19)
    forecast: dict[datetime, dict[str, Any]] = {}
    for offset in range(IRRIGATION_FORECAST_DAYS):
        values = _hourly_day(first_date + timedelta(days=offset), timezone)
        forecast.update(values)

    # Day 0: all component scores zero. Day 1: score 12 gives level 4.
    for values in list(forecast.values())[:24]:
        values.update(
            temperature=10,
            relativehumidity=80,
            windspeed=1,
            gust=1,
            totalcloudcover=90,
            precipitation=0.5,
            precipitation_probability=100,
        )
    for values in list(forecast.values())[24:48]:
        values.update(
            temperature=29,
            relativehumidity=50,
            windspeed=5,
            gust=5,
            totalcloudcover=40,
        )

    days = calculate_irrigation_forecast(
        forecast,
        UNITS_MS,
        first_date,
        timezone,
        _solar_provider,
    )

    assert len(days) == IRRIGATION_FORECAST_DAYS
    assert [day.forecast_day_offset for day in days] == list(range(7))
    assert [day.forecast_date for day in days] == [
        first_date + timedelta(days=offset) for offset in range(7)
    ]
    assert all(day.result is not None for day in days)
    levels = [day.result.final_level for day in days if day.result is not None]
    assert levels[:3] == [0, 4, 5]


def test_missing_today_does_not_shift_tomorrow_into_offset_zero() -> None:
    """Calendar offsets remain stable when one forecast date is absent."""
    timezone = ZoneInfo("UTC")
    today = date(2026, 7, 19)
    tomorrow_forecast = _hourly_day(today + timedelta(days=1), timezone)

    days = calculate_irrigation_forecast(
        tomorrow_forecast,
        UNITS_MS,
        today,
        timezone,
        _solar_provider,
    )

    assert len(days) == IRRIGATION_FORECAST_DAYS
    assert days[0].forecast_date == today
    assert days[0].result is None
    assert days[0].unavailable_reason == "no_forecast_for_day"
    assert days[1].forecast_date == today + timedelta(days=1)
    assert days[1].result is not None


def test_weighted_rain_uses_unweighted_hours_when_probability_is_missing() -> None:
    """Missing probabilities do not discard corresponding precipitation."""
    timezone = ZoneInfo("UTC")
    forecast_date = date(2026, 7, 19)
    forecast = _hourly_day(forecast_date, timezone)
    periods = list(forecast.items())
    for _, values in periods:
        values["precipitation"] = 0
        values["precipitation_probability"] = 0
    periods[0][1].update(precipitation=2, precipitation_probability=80)
    periods[1][1].update(precipitation=1)
    periods[1][1].pop("precipitation_probability")
    periods[2][1].update(
        precipitation=math.nan,
        precipitation_probability=99,
    )

    day = calculate_irrigation_level_for_day(
        forecast_date, 0, periods, UNITS_MS, timezone, _solar_provider
    )

    assert day.result is not None
    assert day.result.gross_precipitation == 3
    assert day.result.weighted_precipitation == pytest.approx(2.6)
    assert day.result.max_precipitation_probability == 99
    assert day.result.final_level == 3


@pytest.mark.parametrize(
    ("field", "bad_value", "reason"),
    [
        ("temperature", math.nan, "missing_temperature"),
        ("relativehumidity", math.inf, "missing_humidity"),
        ("windspeed", math.nan, "missing_wind"),
        ("totalcloudcover", math.inf, "missing_cloud_cover"),
    ],
)
def test_missing_nan_and_infinite_essential_data_are_unavailable(
    field: str, bad_value: float, reason: str
) -> None:
    """Non-finite essential values never create a misleading irrigation level."""
    timezone = ZoneInfo("UTC")
    forecast_date = date(2026, 7, 19)
    forecast = _hourly_day(forecast_date, timezone)
    for values in forecast.values():
        values[field] = bad_value

    day = calculate_irrigation_level_for_day(
        forecast_date,
        0,
        list(forecast.items()),
        UNITS_MS,
        timezone,
        _solar_provider,
    )

    assert day.result is None
    assert day.unavailable_reason == reason


def test_unknown_wind_unit_is_unavailable() -> None:
    """Wind conversion never infers units from value magnitude."""
    timezone = ZoneInfo("UTC")
    forecast_date = date(2026, 7, 19)
    forecast = _hourly_day(forecast_date, timezone)

    day = calculate_irrigation_level_for_day(
        forecast_date,
        0,
        list(forecast.items()),
        {"windspeed": "knots"},
        timezone,
        _solar_provider,
    )

    assert day.result is None
    assert day.unavailable_reason == "missing_wind_unit"


def test_captured_meteoblue_payload_calculates_full_horizon(
    hourly_forecast_payload: dict[str, Any],
) -> None:
    """The real captured API shape provides seven available daily levels."""
    hourly = hourly_forecast_payload["forecast_data_hourly"]
    first_timestamp = min(hourly)
    timezone = first_timestamp.tzinfo
    assert timezone is not None

    days = calculate_irrigation_forecast(
        hourly,
        hourly_forecast_payload["units"],
        first_timestamp.date(),
        timezone,
        _solar_provider,
    )

    assert len(days) == IRRIGATION_FORECAST_DAYS
    assert all(day.result is not None for day in days)
    assert all(
        0 <= day.result.final_level <= 5 for day in days if day.result is not None
    )
    assert all(
        day.result.solar_windows.source == "meteoblue_isdaylight"
        for day in days
        if day.result is not None
    )
