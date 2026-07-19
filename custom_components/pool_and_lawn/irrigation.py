# Copyright 2026 n4rs. All rights reserved.
# See LICENSE for the terms that apply to HomeAssistant Pool and Lawn modifications.

"""Pure multi-day lawn irrigation calculations."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, tzinfo
from itertools import pairwise
from statistics import median
from typing import Any, cast

from astral import Observer
from astral.sun import sun

IRRIGATION_FORECAST_DAYS = 7
MIN_WINDOW_VALUES = 2
MAX_PRECIPITATION_PROBABILITY = 100
SIGNIFICANT_RAIN_GROSS_MM = 8
SIGNIFICANT_RAIN_PROBABILITY = 40

TEMPERATURE_THRESHOLDS = (18, 23, 28, 33)
HUMIDITY_THRESHOLDS = (75, 60, 45)
MEAN_WIND_THRESHOLDS = (8, 15, 25)
GUST_THRESHOLDS = (20, 30, 45)
CLOUD_THRESHOLDS = (80, 60, 30)
BASE_SCORE_THRESHOLDS = (2, 5, 8, 11, 14)
RAIN_REDUCTION_THRESHOLDS = (
    (5.0, 5),
    (3.0, 3),
    (1.5, 2),
    (0.5, 1),
)

LEVEL_DESCRIPTIONS = {
    0: "No irrigation",
    1: "Residual",
    2: "Reduced",
    3: "Moderate",
    4: "High",
    5: "Maximum",
}

type HourlyPeriod = tuple[datetime, Mapping[str, Any]]
type SolarProvider = Callable[[date, tzinfo], tuple[datetime, datetime] | None]


@dataclass(frozen=True)
class SolarWindows:
    """Solar periods used by the irrigation calculation."""

    sunrise: datetime
    sunset: datetime
    solar_noon: datetime
    core_start: datetime
    core_end: datetime
    humidity_start: datetime
    humidity_end: datetime
    source: str
    core_fallback_used: bool = False
    humidity_fallback_used: bool = False
    core_period_source: str = "solar_core"
    humidity_period_source: str = "solar_afternoon"


@dataclass(frozen=True)
class IrrigationLevelResult:
    """Successful irrigation calculation for one local forecast date."""

    forecast_date: date
    forecast_day_offset: int
    final_level: int
    initial_level: int
    base_score: int
    temperature_max: float
    temperature_points: int
    humidity_mean: float
    humidity_points: int
    wind_mean_kmh: float
    gust_max_kmh: float | None
    wind_mean_points: int
    gust_points: int
    wind_points: int
    cloud_cover_mean: float
    cloud_points: int
    month_points: int
    gross_precipitation: float
    weighted_precipitation: float
    max_precipitation_probability: float | None
    rain_level_reduction: int
    solar_windows: SolarWindows
    hourly_periods_total: int
    daylight_periods_used: int
    core_periods_used: int
    humidity_periods_used: int

    def as_attributes(self) -> dict[str, Any]:
        """Return diagnostic Home Assistant state attributes."""
        windows = self.solar_windows
        return {
            "forecast_date": self.forecast_date.isoformat(),
            "forecast_day_offset": self.forecast_day_offset,
            "sunrise": windows.sunrise.isoformat(),
            "sunset": windows.sunset.isoformat(),
            "solar_noon": windows.solar_noon.isoformat(),
            "core_window_start": windows.core_start.isoformat(),
            "core_window_end": windows.core_end.isoformat(),
            "humidity_window_start": windows.humidity_start.isoformat(),
            "humidity_window_end": windows.humidity_end.isoformat(),
            "solar_source": windows.source,
            "core_window_fallback_used": windows.core_fallback_used,
            "humidity_window_fallback_used": windows.humidity_fallback_used,
            "core_window_used": windows.core_period_source,
            "humidity_window_used": windows.humidity_period_source,
            "temperature_max": _rounded(self.temperature_max),
            "temperature_points": self.temperature_points,
            "humidity_mean": _rounded(self.humidity_mean),
            "humidity_points": self.humidity_points,
            "wind_mean_kmh": _rounded(self.wind_mean_kmh),
            "gust_max_kmh": _rounded(self.gust_max_kmh),
            "wind_mean_points": self.wind_mean_points,
            "gust_points": self.gust_points,
            "wind_points": self.wind_points,
            "cloud_cover_mean": _rounded(self.cloud_cover_mean),
            "cloud_points": self.cloud_points,
            "month": self.forecast_date.month,
            "month_points": self.month_points,
            "base_score": self.base_score,
            "initial_level": self.initial_level,
            "gross_precipitation": _rounded(self.gross_precipitation),
            "weighted_precipitation": _rounded(self.weighted_precipitation),
            "max_precipitation_probability": _rounded(
                self.max_precipitation_probability
            ),
            "rain_level_reduction": self.rain_level_reduction,
            "final_level": self.final_level,
            "level_description": LEVEL_DESCRIPTIONS[self.final_level],
            "hourly_periods_total": self.hourly_periods_total,
            "daylight_periods_used": self.daylight_periods_used,
            "core_periods_used": self.core_periods_used,
            "humidity_periods_used": self.humidity_periods_used,
        }


@dataclass(frozen=True)
class IrrigationForecastDay:
    """Available or unavailable irrigation result for one stable offset."""

    forecast_date: date
    forecast_day_offset: int
    result: IrrigationLevelResult | None
    unavailable_reason: str | None = None


def group_hourly_forecast_by_local_date(
    hourly_forecast: Mapping[datetime, Mapping[str, Any]],
    local_timezone: tzinfo,
) -> dict[date, list[HourlyPeriod]]:
    """Convert timestamps to the location timezone and group by local date."""
    grouped: dict[date, list[HourlyPeriod]] = {}
    for timestamp, values in hourly_forecast.items():
        if timestamp.tzinfo is None:
            continue
        local_timestamp = timestamp.astimezone(local_timezone)
        grouped.setdefault(local_timestamp.date(), []).append((local_timestamp, values))
    for periods in grouped.values():
        periods.sort(key=lambda item: item[0])
    return grouped


def astral_solar_period(
    forecast_date: date,
    timezone: tzinfo,
    *,
    latitude: float,
    longitude: float,
) -> tuple[datetime, datetime] | None:
    """Calculate sunrise and sunset for a forecast date using Astral."""
    try:
        events = sun(
            Observer(latitude=latitude, longitude=longitude),
            date=forecast_date,
            tzinfo=timezone,
        )
    except ValueError:
        return None
    return events["sunrise"], events["sunset"]


def determine_solar_windows(
    periods: Sequence[HourlyPeriod],
    forecast_date: date,
    local_timezone: tzinfo,
    solar_provider: SolarProvider,
) -> tuple[SolarWindows, list[HourlyPeriod]] | None:
    """Determine dynamic solar windows, preferring MeteoBlue isdaylight."""
    daylight_flags = [
        _daylight_value(values.get("isdaylight")) for _, values in periods
    ]
    has_daylight_data = any(value is not None for value in daylight_flags)

    if has_daylight_data:
        daylight_periods = [
            period
            for period, is_daylight in zip(periods, daylight_flags, strict=True)
            if is_daylight is True
        ]
        if not daylight_periods:
            return None
        interval = _forecast_interval(periods)
        sunrise = daylight_periods[0][0]
        sunset = daylight_periods[-1][0] + interval
        source = "meteoblue_isdaylight"
    else:
        solar_period = solar_provider(forecast_date, local_timezone)
        if solar_period is None:
            return None
        sunrise, sunset = solar_period
        daylight_periods = [
            period for period in periods if sunrise <= period[0] < sunset
        ]
        if not daylight_periods:
            return None
        source = "astral"

    if sunset <= sunrise:
        return None
    solar_noon = sunrise + (sunset - sunrise) / 2
    return (
        SolarWindows(
            sunrise=sunrise,
            sunset=sunset,
            solar_noon=solar_noon,
            core_start=sunrise + timedelta(hours=2),
            core_end=sunset - timedelta(hours=2),
            humidity_start=solar_noon,
            humidity_end=sunset - timedelta(hours=2),
            source=source,
        ),
        daylight_periods,
    )


def calculate_irrigation_level_for_day(  # noqa: PLR0913
    forecast_date: date,
    forecast_day_offset: int,
    periods: Sequence[HourlyPeriod],
    units: Mapping[str, Any],
    local_timezone: tzinfo,
    solar_provider: SolarProvider,
) -> IrrigationForecastDay:
    """Calculate the irrigation level for one local forecast date."""
    solar = determine_solar_windows(
        periods, forecast_date, local_timezone, solar_provider
    )
    if solar is None:
        return _unavailable(forecast_date, forecast_day_offset, "missing_solar_period")
    windows, daylight_periods = solar

    core_periods = [
        period
        for period in periods
        if windows.core_start <= period[0] < windows.core_end
    ]
    core_fallback = (
        _valid_count(core_periods, "windspeed") < MIN_WINDOW_VALUES
        or _valid_count(core_periods, "totalcloudcover") < MIN_WINDOW_VALUES
    )
    if core_fallback:
        core_periods = daylight_periods
    core_period_source = "all_daylight" if core_fallback else "solar_core"

    humidity_periods = [
        period
        for period in periods
        if windows.humidity_start <= period[0] < windows.humidity_end
    ]
    humidity_fallback = (
        _valid_count(humidity_periods, "relativehumidity") < MIN_WINDOW_VALUES
    )
    if humidity_fallback:
        humidity_periods = daylight_periods[len(daylight_periods) // 2 :]
        humidity_period_source = "second_half_daylight"
        if _valid_count(humidity_periods, "relativehumidity") < MIN_WINDOW_VALUES:
            humidity_periods = daylight_periods
            humidity_period_source = "all_daylight"
    else:
        humidity_period_source = "solar_afternoon"

    windows = replace(
        windows,
        core_fallback_used=core_fallback,
        humidity_fallback_used=humidity_fallback,
        core_period_source=core_period_source,
        humidity_period_source=humidity_period_source,
    )

    temperature_max = _maximum(periods, "temperature")
    humidity_mean = _mean(humidity_periods, "relativehumidity")
    wind_mean = _mean(core_periods, "windspeed")
    cloud_cover_mean = _mean(core_periods, "totalcloudcover")
    missing = _missing_essential_reason(
        temperature_max,
        humidity_mean,
        wind_mean,
        cloud_cover_mean,
        humidity_count=_valid_count(humidity_periods, "relativehumidity"),
        wind_count=_valid_count(core_periods, "windspeed"),
        cloud_count=_valid_count(core_periods, "totalcloudcover"),
    )
    if missing is not None:
        return _unavailable(forecast_date, forecast_day_offset, missing)
    temperature_max = cast("float", temperature_max)
    humidity_mean = cast("float", humidity_mean)
    wind_mean = cast("float", wind_mean)
    cloud_cover_mean = cast("float", cloud_cover_mean)

    wind_unit = units.get("windspeed")
    wind_mean_kmh = _speed_to_kmh(wind_mean, wind_unit)
    if wind_mean_kmh is None:
        return _unavailable(forecast_date, forecast_day_offset, "missing_wind_unit")
    gust = _maximum(core_periods, "gust")
    gust_max_kmh = _speed_to_kmh(gust, units.get("gust", wind_unit))

    gross_precipitation, weighted_precipitation, max_probability = (
        _precipitation_totals(periods)
    )
    temperature_score = temperature_points(temperature_max)
    humidity_score = humidity_points(humidity_mean)
    wind_mean_score = mean_wind_points(wind_mean_kmh)
    gust_score = gust_points(gust_max_kmh)
    wind_score = max(wind_mean_score, gust_score)
    cloud_score = cloud_points(cloud_cover_mean)
    seasonal_score = month_points(forecast_date.month)
    base_score = (
        temperature_score + humidity_score + wind_score + cloud_score + seasonal_score
    )
    initial_level = initial_irrigation_level(base_score)
    final_level = apply_rain_correction(
        initial_level,
        weighted_precipitation,
        gross_precipitation,
        max_probability,
    )

    result = IrrigationLevelResult(
        forecast_date=forecast_date,
        forecast_day_offset=forecast_day_offset,
        final_level=final_level,
        initial_level=initial_level,
        base_score=base_score,
        temperature_max=temperature_max,
        temperature_points=temperature_score,
        humidity_mean=humidity_mean,
        humidity_points=humidity_score,
        wind_mean_kmh=wind_mean_kmh,
        gust_max_kmh=gust_max_kmh,
        wind_mean_points=wind_mean_score,
        gust_points=gust_score,
        wind_points=wind_score,
        cloud_cover_mean=cloud_cover_mean,
        cloud_points=cloud_score,
        month_points=seasonal_score,
        gross_precipitation=gross_precipitation,
        weighted_precipitation=weighted_precipitation,
        max_precipitation_probability=max_probability,
        rain_level_reduction=initial_level - final_level,
        solar_windows=windows,
        hourly_periods_total=len(periods),
        daylight_periods_used=len(daylight_periods),
        core_periods_used=len(core_periods),
        humidity_periods_used=len(humidity_periods),
    )
    return IrrigationForecastDay(forecast_date, forecast_day_offset, result)


def calculate_irrigation_forecast(  # noqa: PLR0913
    hourly_forecast: Mapping[datetime, Mapping[str, Any]],
    units: Mapping[str, Any],
    local_today: date,
    local_timezone: tzinfo,
    solar_provider: SolarProvider,
    *,
    maximum_days: int = IRRIGATION_FORECAST_DAYS,
) -> list[IrrigationForecastDay]:
    """Calculate stable-offset irrigation results for the available horizon."""
    grouped = group_hourly_forecast_by_local_date(hourly_forecast, local_timezone)
    results: list[IrrigationForecastDay] = []
    for offset in range(maximum_days):
        forecast_date = local_today + timedelta(days=offset)
        if forecast_date not in grouped:
            results.append(_unavailable(forecast_date, offset, "no_forecast_for_day"))
            continue
        results.append(
            calculate_irrigation_level_for_day(
                forecast_date,
                offset,
                grouped[forecast_date],
                units,
                local_timezone,
                solar_provider,
            )
        )
    return results


def temperature_points(value: float) -> int:
    """Score daily maximum temperature."""
    return sum(value >= threshold for threshold in TEMPERATURE_THRESHOLDS)


def humidity_points(value: float) -> int:
    """Score relevant afternoon humidity."""
    return sum(value < threshold for threshold in HUMIDITY_THRESHOLDS)


def mean_wind_points(value: float) -> int:
    """Score relevant mean wind in km/h."""
    return sum(value >= threshold for threshold in MEAN_WIND_THRESHOLDS)


def gust_points(value: float | None) -> int:
    """Score relevant maximum gust in km/h."""
    if value is None:
        return 0
    return sum(value >= threshold for threshold in GUST_THRESHOLDS)


def cloud_points(value: float) -> int:
    """Score relevant total cloud coverage."""
    return sum(value < threshold for threshold in CLOUD_THRESHOLDS)


def month_points(month: int) -> int:
    """Score the month belonging to the concrete forecast date."""
    if month in (11, 12, 1, 2):
        return 0
    if month in (3, 4, 10):
        return 1
    if month in (5, 9):
        return 2
    return 3


def initial_irrigation_level(base_score: int) -> int:
    """Convert the combined weather score to an initial level."""
    return sum(base_score > threshold for threshold in BASE_SCORE_THRESHOLDS)


def apply_rain_correction(
    initial_level: int,
    weighted_precipitation: float,
    gross_precipitation: float,
    maximum_probability: float | None,
) -> int:
    """Reduce irrigation demand using weighted and significant rainfall."""
    reduction = next(
        (
            level_reduction
            for threshold, level_reduction in RAIN_REDUCTION_THRESHOLDS
            if weighted_precipitation >= threshold
        ),
        0,
    )
    final_level = initial_level - reduction
    if (
        gross_precipitation >= SIGNIFICANT_RAIN_GROSS_MM
        and maximum_probability is not None
        and maximum_probability >= SIGNIFICANT_RAIN_PROBABILITY
    ):
        final_level = 0
    return max(0, min(5, final_level))


def _forecast_interval(periods: Sequence[HourlyPeriod]) -> timedelta:
    intervals = [
        later[0] - earlier[0]
        for earlier, later in pairwise(periods)
        if later[0] > earlier[0]
    ]
    return median(intervals) if intervals else timedelta(hours=1)


def _daylight_value(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    return None


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _valid_values(periods: Sequence[HourlyPeriod], field: str) -> list[float]:
    return [
        number
        for _, values in periods
        if (number := _finite_number(values.get(field))) is not None
    ]


def _valid_count(periods: Sequence[HourlyPeriod], field: str) -> int:
    return len(_valid_values(periods, field))


def _mean(periods: Sequence[HourlyPeriod], field: str) -> float | None:
    values = _valid_values(periods, field)
    return sum(values) / len(values) if values else None


def _maximum(periods: Sequence[HourlyPeriod], field: str) -> float | None:
    values = _valid_values(periods, field)
    return max(values) if values else None


def _speed_to_kmh(value: float | None, unit: Any) -> float | None:
    if value is None or not isinstance(unit, str):
        return None
    normalized = unit.strip().lower().replace(" ", "")
    if normalized in {"ms-1", "m/s", "m·s-1", "mps"}:
        return value * 3.6
    if normalized in {"kmh-1", "km/h", "kph", "kmph"}:
        return value
    return None


def _precipitation_totals(
    periods: Sequence[HourlyPeriod],
) -> tuple[float, float, float | None]:
    gross = 0.0
    weighted = 0.0
    probabilities: list[float] = []
    for _, values in periods:
        probability = _finite_number(values.get("precipitation_probability"))
        probability_is_valid = (
            probability is not None
            and 0 <= probability <= MAX_PRECIPITATION_PROBABILITY
        )
        if probability_is_valid:
            probabilities.append(cast("float", probability))
        precipitation = _finite_number(values.get("precipitation"))
        if precipitation is None or precipitation < 0:
            continue
        gross += precipitation
        if not probability_is_valid:
            weighted += precipitation
            continue
        probability = cast("float", probability)
        weighted += precipitation * probability / 100
    return gross, weighted, max(probabilities) if probabilities else None


def _missing_essential_reason(  # noqa: PLR0913
    temperature_max: float | None,
    humidity_mean: float | None,
    wind_mean: float | None,
    cloud_cover_mean: float | None,
    *,
    humidity_count: int,
    wind_count: int,
    cloud_count: int,
) -> str | None:
    if temperature_max is None:
        return "missing_temperature"
    if humidity_mean is None or humidity_count < MIN_WINDOW_VALUES:
        return "missing_humidity"
    if wind_mean is None or wind_count < MIN_WINDOW_VALUES:
        return "missing_wind"
    if cloud_cover_mean is None or cloud_count < MIN_WINDOW_VALUES:
        return "missing_cloud_cover"
    return None


def _unavailable(
    forecast_date: date,
    forecast_day_offset: int,
    reason: str,
) -> IrrigationForecastDay:
    return IrrigationForecastDay(
        forecast_date=forecast_date,
        forecast_day_offset=forecast_day_offset,
        result=None,
        unavailable_reason=reason,
    )


def _rounded(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None
