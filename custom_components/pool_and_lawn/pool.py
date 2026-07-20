# Copyright 2026 n4rs. All rights reserved.
# See LICENSE for the terms that apply to HomeAssistant Pool and Lawn modifications.

"""Pure open-loop weather estimates for saltwater pool pump runtime."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, tzinfo
from itertools import pairwise
from statistics import median
from typing import Any

POOL_FORECAST_DAYS = 7
BASE_CHLORINE_DEMAND_PPM = 0.7
MIN_CHLORINE_DEMAND_PPM = 0.4
MAX_CHLORINE_DEMAND_PPM = 2.8
MAX_DAILY_RUNTIME_HOURS = 24.0
MIN_HYDRAULIC_EFFICIENCY_FACTOR = 0.4
MAX_HYDRAULIC_EFFICIENCY_FACTOR = 1.0
UV_DAYLIGHT_THRESHOLDS = (14, 12, 10)
CLOUD_COVER_THRESHOLDS = (80, 60, 30)

type HourlyPeriod = tuple[datetime, Mapping[str, Any]]
type SolarProvider = Callable[[date, tzinfo], tuple[datetime, datetime] | None]


@dataclass(frozen=True)
class PoolSettings:
    """User-provided physical settings for one saltwater pool."""

    volume_m3: float
    pump_nominal_flow_m3h: float
    hydraulic_efficiency_factor: float
    chlorinator_output_gh: float
    target_free_chlorine_ppm: float

    def __post_init__(self) -> None:
        """Reject physically invalid settings before calculating a result."""
        positive_values = (
            self.volume_m3,
            self.pump_nominal_flow_m3h,
            self.chlorinator_output_gh,
            self.target_free_chlorine_ppm,
        )
        if any(not math.isfinite(value) or value <= 0 for value in positive_values):
            msg = "Pool volume, flow, output, and chlorine target must be positive"
            raise ValueError(msg)
        if (
            not math.isfinite(self.hydraulic_efficiency_factor)
            or not MIN_HYDRAULIC_EFFICIENCY_FACTOR
            <= self.hydraulic_efficiency_factor
            <= MAX_HYDRAULIC_EFFICIENCY_FACTOR
        ):
            msg = "Hydraulic efficiency factor must be between 0.40 and 1.00"
            raise ValueError(msg)


@dataclass(frozen=True)
class DailyPoolWeather:
    """Weather values aggregated for one local forecast date."""

    forecast_date: date
    forecast_day_offset: int
    temperature_max: float
    uv_index_max: float
    uv_source: str
    daylight_hours: float
    cloud_cover_mean: float | None
    precipitation_total: float
    wind_mean_kmh: float | None
    gust_max_kmh: float | None


@dataclass(frozen=True)
class ChlorineDemand:
    """Estimated chlorine demand and each weather adjustment."""

    estimated_ppm: float
    base_ppm: float
    uv_adjustment_ppm: float
    temperature_adjustment_ppm: float
    daylight_adjustment_ppm: float
    cloud_adjustment_ppm: float
    rain_adjustment_ppm: float
    wind_adjustment_ppm: float


@dataclass(frozen=True)
class PoolPumpCalculationResult:
    """Recommended pump runtime and its open-loop diagnostic values."""

    weather: DailyPoolWeather
    settings: PoolSettings
    demand: ChlorineDemand
    recommended_pump_hours: float
    raw_recommended_hours: float
    runtime_limited: bool
    chlorine_production_ppm_per_hour: float
    chlorination_hours: float
    estimated_free_chlorine_without_generation: float
    effective_flow_m3h: float
    estimated_circulated_volume_m3: float
    estimated_turnovers: float

    def as_attributes(self) -> dict[str, Any]:
        """Return Home Assistant attributes explaining the estimate."""
        weather = self.weather
        settings = self.settings
        demand = self.demand
        return {
            "forecast_date": weather.forecast_date.isoformat(),
            "forecast_day_offset": weather.forecast_day_offset,
            "pool_volume_m3": _rounded(settings.volume_m3),
            "pump_nominal_flow_m3h": _rounded(settings.pump_nominal_flow_m3h),
            "hydraulic_efficiency_factor": _rounded(
                settings.hydraulic_efficiency_factor, 3
            ),
            "effective_flow_m3h": _rounded(self.effective_flow_m3h, 3),
            "chlorinator_output_gh": _rounded(settings.chlorinator_output_gh),
            "target_free_chlorine_ppm": _rounded(settings.target_free_chlorine_ppm),
            "starting_free_chlorine_ppm": _rounded(settings.target_free_chlorine_ppm),
            "estimated_free_chlorine_without_generation": _rounded(
                self.estimated_free_chlorine_without_generation
            ),
            "estimated_free_chlorine_after_recommended_runtime": _rounded(
                settings.target_free_chlorine_ppm
            ),
            "temperature_max": _rounded(weather.temperature_max),
            "uv_index_max": _rounded(weather.uv_index_max),
            "uv_source": weather.uv_source,
            "daylight_hours": _rounded(weather.daylight_hours),
            "cloud_cover_mean_daylight": _rounded(weather.cloud_cover_mean),
            "precipitation_total": _rounded(weather.precipitation_total),
            "wind_mean_daylight_kmh": _rounded(weather.wind_mean_kmh),
            "gust_max_daylight_kmh": _rounded(weather.gust_max_kmh),
            "base_chlorine_demand_ppm": _rounded(demand.base_ppm),
            "uv_adjustment_ppm": _rounded(demand.uv_adjustment_ppm),
            "temperature_adjustment_ppm": _rounded(demand.temperature_adjustment_ppm),
            "daylight_adjustment_ppm": _rounded(demand.daylight_adjustment_ppm),
            "cloud_adjustment_ppm": _rounded(demand.cloud_adjustment_ppm),
            "rain_adjustment_ppm": _rounded(demand.rain_adjustment_ppm),
            "wind_adjustment_ppm": _rounded(demand.wind_adjustment_ppm),
            "estimated_chlorine_demand_ppm": _rounded(demand.estimated_ppm),
            "required_chlorine_replacement_ppm": _rounded(demand.estimated_ppm),
            "chlorine_production_ppm_per_hour": _rounded(
                self.chlorine_production_ppm_per_hour, 3
            ),
            "chlorination_hours": _rounded(self.chlorination_hours),
            "raw_recommended_hours": _rounded(self.raw_recommended_hours),
            "recommended_pump_hours": self.recommended_pump_hours,
            "runtime_limited": self.runtime_limited,
            "estimated_circulated_volume_m3": _rounded(
                self.estimated_circulated_volume_m3
            ),
            "estimated_turnovers": _rounded(self.estimated_turnovers),
            "calculation_type": "open_loop_weather_estimate",
        }


@dataclass(frozen=True)
class PoolForecastDay:
    """Available or unavailable pool result for one stable day offset."""

    forecast_date: date
    forecast_day_offset: int
    result: PoolPumpCalculationResult | None
    unavailable_reason: str | None = None


def group_hourly_forecast_by_local_date(
    hourly_forecast: Mapping[datetime, Mapping[str, Any]],
    local_timezone: tzinfo,
) -> dict[date, list[HourlyPeriod]]:
    """Convert aware timestamps to the forecast timezone and group by local date."""
    grouped: dict[date, list[HourlyPeriod]] = {}
    for timestamp, values in hourly_forecast.items():
        if timestamp.tzinfo is None:
            continue
        local_timestamp = timestamp.astimezone(local_timezone)
        grouped.setdefault(local_timestamp.date(), []).append((local_timestamp, values))
    for periods in grouped.values():
        periods.sort(key=lambda item: item[0])
    return grouped


def aggregate_daily_pool_weather(  # noqa: PLR0913
    forecast_date: date,
    forecast_day_offset: int,
    periods: Sequence[HourlyPeriod],
    units: Mapping[str, Any],
    local_timezone: tzinfo,
    solar_provider: SolarProvider,
) -> tuple[DailyPoolWeather | None, str | None]:
    """Aggregate one local day, returning a reason when essentials are missing."""
    daylight_periods = _daylight_periods(
        periods, forecast_date, local_timezone, solar_provider
    )
    if not daylight_periods:
        return None, "missing_solar_period"

    temperature_max = _maximum(periods, "temperature")
    if temperature_max is None:
        return None, "missing_temperature"

    interval_hours = _forecast_interval(periods).total_seconds() / 3600
    daylight_hours = len(daylight_periods) * interval_hours
    cloud_cover_mean = _mean(daylight_periods, "totalcloudcover")
    uv_index_max = _maximum(daylight_periods, "uvindex")
    if uv_index_max is None:
        if cloud_cover_mean is None:
            return None, "missing_uv_and_cloud_cover"
        uv_index_max = estimate_uv_index(daylight_hours, cloud_cover_mean)
        uv_source = "estimated"
    else:
        uv_source = "meteoblue"

    wind_mean = _mean(daylight_periods, "windspeed")
    wind_mean_kmh, wind_unit_valid = _speed_to_kmh(wind_mean, units.get("windspeed"))
    if wind_mean is not None and not wind_unit_valid:
        return None, "missing_wind_unit"

    gust = _maximum(daylight_periods, "gust")
    gust_unit = units.get("gust", units.get("windspeed"))
    gust_max_kmh, _ = _speed_to_kmh(gust, gust_unit)

    return (
        DailyPoolWeather(
            forecast_date=forecast_date,
            forecast_day_offset=forecast_day_offset,
            temperature_max=temperature_max,
            uv_index_max=uv_index_max,
            uv_source=uv_source,
            daylight_hours=daylight_hours,
            cloud_cover_mean=cloud_cover_mean,
            precipitation_total=_precipitation_total(periods),
            wind_mean_kmh=wind_mean_kmh,
            gust_max_kmh=gust_max_kmh,
        ),
        None,
    )


def calculate_chlorine_demand(weather: DailyPoolWeather) -> ChlorineDemand:
    """Estimate daily chlorine loss from the specified weather thresholds."""
    uv_adjustment = _threshold_adjustment(
        weather.uv_index_max,
        ((3, 0.0), (5, 0.25), (7, 0.50), (9, 0.75)),
        1.0,
    )
    temperature_adjustment = _threshold_adjustment(
        weather.temperature_max,
        ((18, -0.20), (23, 0.0), (28, 0.20), (33, 0.40)),
        0.60,
    )
    daylight_adjustment = _threshold_adjustment(
        weather.daylight_hours,
        ((10, -0.10), (12, 0.0), (14, 0.10)),
        0.20,
    )
    cloud_adjustment = _cloud_adjustment(weather.cloud_cover_mean)
    rain_adjustment = _threshold_adjustment(
        weather.precipitation_total,
        ((2, 0.0), (8, 0.10)),
        0.20,
    )
    wind_adjustment = (
        0.0
        if weather.wind_mean_kmh is None
        else _threshold_adjustment(
            weather.wind_mean_kmh,
            ((10, 0.0), (20, 0.05)),
            0.10,
        )
    )
    estimated = (
        BASE_CHLORINE_DEMAND_PPM
        + uv_adjustment
        + temperature_adjustment
        + daylight_adjustment
        + cloud_adjustment
        + rain_adjustment
        + wind_adjustment
    )
    estimated = max(
        MIN_CHLORINE_DEMAND_PPM,
        min(MAX_CHLORINE_DEMAND_PPM, estimated),
    )
    return ChlorineDemand(
        estimated_ppm=estimated,
        base_ppm=BASE_CHLORINE_DEMAND_PPM,
        uv_adjustment_ppm=uv_adjustment,
        temperature_adjustment_ppm=temperature_adjustment,
        daylight_adjustment_ppm=daylight_adjustment,
        cloud_adjustment_ppm=cloud_adjustment,
        rain_adjustment_ppm=rain_adjustment,
        wind_adjustment_ppm=wind_adjustment,
    )


def calculate_pool_pump_runtime(
    settings: PoolSettings,
    weather: DailyPoolWeather,
) -> PoolPumpCalculationResult:
    """Calculate chlorination runtime; hydraulic values remain diagnostic only."""
    demand = calculate_chlorine_demand(weather)
    production = settings.chlorinator_output_gh / settings.volume_m3
    chlorination_hours = demand.estimated_ppm / production
    raw_recommended_hours = max(0.0, chlorination_hours)
    runtime_limited = raw_recommended_hours > MAX_DAILY_RUNTIME_HOURS
    recommended_pump_hours = round(
        min(MAX_DAILY_RUNTIME_HOURS, raw_recommended_hours), 1
    )

    effective_flow = (
        settings.pump_nominal_flow_m3h * settings.hydraulic_efficiency_factor
    )
    circulated_volume = effective_flow * recommended_pump_hours
    return PoolPumpCalculationResult(
        weather=weather,
        settings=settings,
        demand=demand,
        recommended_pump_hours=recommended_pump_hours,
        raw_recommended_hours=raw_recommended_hours,
        runtime_limited=runtime_limited,
        chlorine_production_ppm_per_hour=production,
        chlorination_hours=chlorination_hours,
        estimated_free_chlorine_without_generation=max(
            0.0, settings.target_free_chlorine_ppm - demand.estimated_ppm
        ),
        effective_flow_m3h=effective_flow,
        estimated_circulated_volume_m3=circulated_volume,
        estimated_turnovers=circulated_volume / settings.volume_m3,
    )


def calculate_pool_pump_forecast(  # noqa: PLR0913
    hourly_forecast: Mapping[datetime, Mapping[str, Any]],
    units: Mapping[str, Any],
    settings: PoolSettings,
    local_today: date,
    local_timezone: tzinfo,
    solar_provider: SolarProvider,
    *,
    maximum_days: int = POOL_FORECAST_DAYS,
) -> list[PoolForecastDay]:
    """Calculate stable-offset pool estimates for the hourly forecast horizon."""
    grouped = group_hourly_forecast_by_local_date(hourly_forecast, local_timezone)
    days: list[PoolForecastDay] = []
    for offset in range(maximum_days):
        forecast_date = local_today + timedelta(days=offset)
        periods = grouped.get(forecast_date)
        if not periods:
            days.append(_unavailable(forecast_date, offset, "no_forecast_for_day"))
            continue
        weather, reason = aggregate_daily_pool_weather(
            forecast_date,
            offset,
            periods,
            units,
            local_timezone,
            solar_provider,
        )
        if weather is None:
            days.append(
                _unavailable(forecast_date, offset, reason or "missing_weather_data")
            )
            continue
        days.append(
            PoolForecastDay(
                forecast_date,
                offset,
                calculate_pool_pump_runtime(settings, weather),
            )
        )
    return days


def estimate_uv_index(daylight_hours: float, cloud_cover_mean: float) -> float:
    """Estimate UV only when MeteoBlue UV is absent but cloud data exists."""
    long_day, medium_day, short_day = UV_DAYLIGHT_THRESHOLDS
    very_cloudy, cloudy, _ = CLOUD_COVER_THRESHOLDS
    if daylight_hours >= long_day:
        estimated = 7
    elif daylight_hours >= medium_day:
        estimated = 5
    elif daylight_hours >= short_day:
        estimated = 3
    else:
        estimated = 2
    if cloud_cover_mean >= very_cloudy:
        estimated -= 2
    elif cloud_cover_mean >= cloudy:
        estimated -= 1
    return float(max(0, estimated))


def _daylight_periods(
    periods: Sequence[HourlyPeriod],
    forecast_date: date,
    local_timezone: tzinfo,
    solar_provider: SolarProvider,
) -> list[HourlyPeriod]:
    flags = [_daylight_value(values.get("isdaylight")) for _, values in periods]
    if any(flag is not None for flag in flags):
        return [
            period for period, flag in zip(periods, flags, strict=True) if flag is True
        ]
    solar_period = solar_provider(forecast_date, local_timezone)
    if solar_period is None:
        return []
    sunrise, sunset = solar_period
    return [period for period in periods if sunrise <= period[0] < sunset]


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


def _mean(periods: Sequence[HourlyPeriod], field: str) -> float | None:
    values = _valid_values(periods, field)
    return sum(values) / len(values) if values else None


def _maximum(periods: Sequence[HourlyPeriod], field: str) -> float | None:
    values = _valid_values(periods, field)
    return max(values) if values else None


def _precipitation_total(periods: Sequence[HourlyPeriod]) -> float:
    return sum(value for value in _valid_values(periods, "precipitation") if value >= 0)


def _speed_to_kmh(value: float | None, unit: Any) -> tuple[float | None, bool]:
    if value is None:
        return None, True
    if not isinstance(unit, str):
        return None, False
    normalized = unit.strip().lower().replace(" ", "")
    if normalized in {"ms-1", "m/s", "m·s-1", "mps"}:
        return value * 3.6, True
    if normalized in {"kmh-1", "km/h", "kph", "kmph"}:
        return value, True
    return None, False


def _threshold_adjustment(
    value: float,
    thresholds: Sequence[tuple[float, float]],
    final_adjustment: float,
) -> float:
    return next(
        (adjustment for threshold, adjustment in thresholds if value < threshold),
        final_adjustment,
    )


def _cloud_adjustment(cloud_cover_mean: float | None) -> float:
    if cloud_cover_mean is None:
        return 0.0
    very_cloudy, cloudy, partly_cloudy = CLOUD_COVER_THRESHOLDS
    if cloud_cover_mean >= very_cloudy:
        return -0.20
    if cloud_cover_mean >= cloudy:
        return -0.10
    if cloud_cover_mean >= partly_cloudy:
        return 0.0
    return 0.10


def _unavailable(
    forecast_date: date,
    forecast_day_offset: int,
    reason: str,
) -> PoolForecastDay:
    return PoolForecastDay(
        forecast_date=forecast_date,
        forecast_day_offset=forecast_day_offset,
        result=None,
        unavailable_reason=reason,
    )


def _rounded(value: float | None, digits: int = 2) -> float | None:
    return round(value, digits) if value is not None else None
