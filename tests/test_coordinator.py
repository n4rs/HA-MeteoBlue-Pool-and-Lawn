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
"""Tests for the MeteoBlue coordinator helpers."""

from __future__ import annotations

import math
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from dateutil.tz import tzoffset
<<<<<<< ours
from meteoblue.api import ApiPackage
from meteoblue.const import (
=======
from PIL import Image
from pool_and_lawn.api import ApiPackage
from pool_and_lawn.const import (
>>>>>>> theirs
    CONF_ENABLE_HOURLY_CLOUDS_AND_WIND,
    CONF_FORECAST_TYPE,
    FORECAST_TYPE_DAILY,
    FORECAST_TYPE_HOURLY,
    PICTOCODE_DAILY_TO_CONDITION,
    PICTOCODE_HOURLY_TO_CONDITION,
)
<<<<<<< ours
from meteoblue.coordinator import (
=======
from pool_and_lawn.coordinator import (
>>>>>>> theirs
    ForecastCoordinator,
    MeteogramCoordinator,
    MeteogramImageSet,
    _reshape_forecast_payload,
)

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
METEOGRAM_FIXTURE = Path(__file__).parent / "fixtures" / "meteogram_extended.png"

CEST = tzoffset("CEST", 2 * 3600)
METADATA_CEST: dict[str, Any] = {
    "timezone_abbrevation": "CEST",
    "utc_timeoffset": 2.0,
}


def test_reshape_splits_hourly_and_daily_sections() -> None:
    raw: dict[str, Any] = {
        "metadata": METADATA_CEST,
        "units": {"temperature": "C"},
        "data_1h": {
            "time": ["2026-04-20 00:00", "2026-04-20 01:00"],
            "temperature": [5.0, 4.5],
            "precipitation": [0.1, 0.0],
            "totalcloudcover": [18, 42],
            "gust": [8.1, 9.9],
            "pictocode": [31, 7],
            "isdaylight": [0, 0],
        },
        "data_day": {
            "time": ["2026-04-20"],
            "temperature_max": [12.0],
            "precipitation": [1.5],
            "pictocode": [16],
        },
    }

    result = _reshape_forecast_payload(raw)

    midnight_key = datetime(2026, 4, 20, 0, 0, tzinfo=CEST)
    next_hour_key = datetime(2026, 4, 20, 1, 0, tzinfo=CEST)

    assert result["metadata"] is raw["metadata"]
    assert result["units"] is raw["units"]

    # Hourly and daily entries live in separate dicts. Each entry carries a
    # pre-resolved HA condition string; the raw pictocode is dropped.
    assert set(result["forecast_data_hourly"]) == {midnight_key, next_hour_key}
    hourly_midnight = result["forecast_data_hourly"][midnight_key]
    assert hourly_midnight["temperature"] == 5.0
    assert hourly_midnight["precipitation"] == 0.1
    assert hourly_midnight["totalcloudcover"] == 18
    assert hourly_midnight["gust"] == 8.1
    assert "pictocode" not in hourly_midnight
    assert "isdaylight" not in hourly_midnight
    assert hourly_midnight["condition"] == PICTOCODE_HOURLY_TO_CONDITION[31]

    next_hour = result["forecast_data_hourly"][next_hour_key]
    assert next_hour["temperature"] == 4.5
    assert next_hour["totalcloudcover"] == 42
    assert next_hour["gust"] == 9.9
    assert "temperature_max" not in next_hour

    assert set(result["forecast_data_daily"]) == {midnight_key}
    daily_midnight = result["forecast_data_daily"][midnight_key]
    assert daily_midnight["temperature_max"] == 12.0
    assert daily_midnight["precipitation"] == 1.5
    assert "pictocode" not in daily_midnight
    assert daily_midnight["condition"] == PICTOCODE_DAILY_TO_CONDITION[16]


def test_reshape_with_only_daily_data() -> None:
    raw: dict[str, Any] = {
        "metadata": METADATA_CEST,
        "units": {},
        "data_day": {
            "time": ["2026-04-20", "2026-04-21"],
            "temperature_max": [12.0, 13.5],
            "pictocode": [3, 6],
        },
    }

    result = _reshape_forecast_payload(raw)

    day_one = datetime(2026, 4, 20, 0, 0, tzinfo=CEST)
    day_two = datetime(2026, 4, 21, 0, 0, tzinfo=CEST)

    assert result["forecast_data_hourly"] == {}
    assert set(result["forecast_data_daily"]) == {day_one, day_two}
    assert result["forecast_data_daily"][day_one]["temperature_max"] == 12.0
    assert (
        result["forecast_data_daily"][day_one]["condition"]
        == PICTOCODE_DAILY_TO_CONDITION[3]
    )
    assert (
        result["forecast_data_daily"][day_two]["condition"]
        == PICTOCODE_DAILY_TO_CONDITION[6]
    )


def test_reshape_with_only_hourly_data() -> None:
    raw: dict[str, Any] = {
        "metadata": METADATA_CEST,
        "units": {},
        "data_1h": {
            "time": ["2026-04-20 00:00", "2026-04-20 01:00"],
            "temperature": [5.0, 4.5],
            "pictocode": [31, 22],
            "isdaylight": [0, 0],
        },
    }

    result = _reshape_forecast_payload(raw)

    hour_zero = datetime(2026, 4, 20, 0, 0, tzinfo=CEST)
    hour_one = datetime(2026, 4, 20, 1, 0, tzinfo=CEST)

    assert set(result["forecast_data_hourly"]) == {hour_zero, hour_one}
    assert result["forecast_data_hourly"][hour_one]["temperature"] == 4.5
    assert "isdaylight" not in result["forecast_data_hourly"][hour_zero]
    assert (
        result["forecast_data_hourly"][hour_zero]["condition"]
        == PICTOCODE_HOURLY_TO_CONDITION[31]
    )
    assert (
        result["forecast_data_hourly"][hour_one]["condition"]
        == PICTOCODE_HOURLY_TO_CONDITION[22]
    )


def test_reshape_tolerates_missing_optional_cloud_and_gust_fields() -> None:
    """Optional cloud and gust fields may be absent from the hourly response."""
    raw: dict[str, Any] = {
        "metadata": METADATA_CEST,
        "units": {},
        "data_1h": {
            "time": ["2026-04-20 00:00"],
            "temperature": [5.0],
            "pictocode": [31],
        },
    }

    result = _reshape_forecast_payload(raw)

    hour_zero = datetime(2026, 4, 20, 0, 0, tzinfo=CEST)
    entry = result["forecast_data_hourly"][hour_zero]
    assert entry["temperature"] == 5.0
    assert "totalcloudcover" not in entry
    assert "gust" not in entry


def test_reshape_hourly_sunny_at_night_becomes_clear_night() -> None:
    """A "sunny" pictocode resolves to "clear-night" when the hour is non-daylight."""
    raw: dict[str, Any] = {
        "metadata": METADATA_CEST,
        "units": {},
        "data_1h": {
            "time": ["2026-04-20 00:00"],
            "pictocode": [1],
            "isdaylight": [0],
        },
    }

    result = _reshape_forecast_payload(raw)

    hour_zero = datetime(2026, 4, 20, 0, 0, tzinfo=CEST)
    assert result["forecast_data_hourly"][hour_zero]["condition"] == "clear-night"


def test_reshape_hourly_sunny_during_day_stays_sunny() -> None:
    """A "sunny" pictocode resolves to "sunny" when the hour is daylight."""
    raw: dict[str, Any] = {
        "metadata": METADATA_CEST,
        "units": {},
        "data_1h": {
            "time": ["2026-04-20 12:00"],
            "pictocode": [1],
            "isdaylight": [1],
        },
    }

    result = _reshape_forecast_payload(raw)

    hour_noon = datetime(2026, 4, 20, 12, 0, tzinfo=CEST)
    assert result["forecast_data_hourly"][hour_noon]["condition"] == "sunny"


def test_reshape_hourly_without_isdaylight_keeps_sunny() -> None:
    """If isdaylight is absent, "sunny" is preserved (no day/night refinement)."""
    raw: dict[str, Any] = {
        "metadata": METADATA_CEST,
        "units": {},
        "data_1h": {
            "time": ["2026-04-20 00:00"],
            "pictocode": [1],
        },
    }

    result = _reshape_forecast_payload(raw)

    hour_zero = datetime(2026, 4, 20, 0, 0, tzinfo=CEST)
    assert result["forecast_data_hourly"][hour_zero]["condition"] == "sunny"


def test_reshape_synthesizes_daily_from_hourly_when_data_day_absent() -> None:
    """With only hourly data, full days are aggregated and partial days skipped."""
    # First day: a full 24-hour set with every field populated.
    day_one_temps: list[float] = [5.0 + i * 0.25 for i in range(24)]
    day_one_precs: list[float] = [0.1] * 24
    day_one_probs: list[float] = [float(i * 4) for i in range(24)]
    day_one_clouds: list[float | None] = [float((i * 3) % 100) for i in range(24)]
    day_one_clouds[5] = None
    day_one_gusts: list[float | None] = [6.0 + i * 0.1 for i in range(24)]
    day_one_gusts[6] = None
    # Winds clustered around 90° (east) so the circular mean is well-defined
    # and not a near-zero floating-point cancellation.
    day_one_winds: list[float] = [3.0 + (i % 3) for i in range(24)]
    day_one_dirs: list[float] = [80.0 + (i * 2) % 20 for i in range(24)]
    day_one_pictocodes: list[int] = [4] * 24
    # Midday (12:00) gets a distinct pictocode to verify condition picks it.
    day_one_pictocodes[12] = 25

    # Second day: only a 00:00 entry, no midday — should be skipped.
    times = [f"2026-04-20 {h:02d}:00" for h in range(24)] + ["2026-04-21 00:00"]
    temperatures: list[float] = [*day_one_temps, -1.0]
    precipitations: list[float] = [*day_one_precs, 0.0]
    probabilities: list[float] = [*day_one_probs, 0.0]
    cloud_covers: list[float | None] = [*day_one_clouds, None]
    gusts: list[float | None] = [*day_one_gusts, None]
    windspeeds: list[float] = [*day_one_winds, 0.0]
    winddirections: list[float] = [*day_one_dirs, 0.0]
    pictocodes: list[int] = [*day_one_pictocodes, 4]

    raw: dict[str, Any] = {
        "metadata": METADATA_CEST,
        "units": {},
        "data_1h": {
            "time": times,
            "temperature": temperatures,
            "precipitation": precipitations,
            "precipitation_probability": probabilities,
            "totalcloudcover": cloud_covers,
            "gust": gusts,
            "windspeed": windspeeds,
            "winddirection": winddirections,
            "pictocode": pictocodes,
        },
    }

    result = _reshape_forecast_payload(raw)

    day_one = datetime(2026, 4, 20, 0, 0, tzinfo=CEST)
    day_two = datetime(2026, 4, 21, 0, 0, tzinfo=CEST)
    # Day two has no 12:00 entry, so aggregation skips it.
    assert set(result["forecast_data_daily"]) == {day_one}
    assert day_two not in result["forecast_data_daily"]

    aggregated = result["forecast_data_daily"][day_one]
    assert aggregated["temperature_max"] == max(day_one_temps)
    assert aggregated["temperature_min"] == min(day_one_temps)
    assert aggregated["precipitation"] == pytest.approx(sum(day_one_precs))
    assert aggregated["precipitation_probability"] == max(day_one_probs)
    valid_clouds = [v for v in day_one_clouds if v is not None]
    valid_gusts = [v for v in day_one_gusts if v is not None]
    assert aggregated["totalcloudcover_mean"] == pytest.approx(
        sum(valid_clouds) / len(valid_clouds)
    )
    assert aggregated["gust_max"] == max(valid_gusts)
    assert aggregated["windspeed_mean"] == pytest.approx(
        sum(day_one_winds) / len(day_one_winds)
    )
    u = sum(
        s * math.sin(math.radians(d))
        for s, d in zip(day_one_winds, day_one_dirs, strict=True)
    )
    v = sum(
        s * math.cos(math.radians(d))
        for s, d in zip(day_one_winds, day_one_dirs, strict=True)
    )
    expected_bearing = (math.degrees(math.atan2(u, v)) + 360) % 360
    assert aggregated["winddirection"] == pytest.approx(expected_bearing)
    # Condition comes from the midday pictocode via the hourly mapping table.
    assert aggregated["condition"] == PICTOCODE_HOURLY_TO_CONDITION[25]


class _StubForecastClient:
    """Minimal stand-in that records forecast package requests."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def async_get_forecast(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {
            "metadata": METADATA_CEST,
            "units": {},
            "data_day": {
                "time": ["2026-04-20"],
                "pictocode": [3],
            },
        }


@pytest.mark.parametrize(
    ("subentry_data", "expected_packages"),
    [
        (
            {
                CONF_FORECAST_TYPE: FORECAST_TYPE_HOURLY,
                CONF_ENABLE_HOURLY_CLOUDS_AND_WIND: True,
            },
            [ApiPackage.BASIC_1H, ApiPackage.CLOUDS_1H, ApiPackage.WIND_1H],
        ),
        (
            {
                CONF_FORECAST_TYPE: FORECAST_TYPE_HOURLY,
                CONF_ENABLE_HOURLY_CLOUDS_AND_WIND: False,
            },
            [ApiPackage.BASIC_1H],
        ),
        (
            {CONF_FORECAST_TYPE: FORECAST_TYPE_HOURLY},
            [
                ApiPackage.BASIC_1H,
                ApiPackage.CLOUDS_1H,
                ApiPackage.WIND_1H,
            ],
        ),
        (FORECAST_TYPE_DAILY, [ApiPackage.BASIC_DAY]),
    ],
)
async def test_forecast_coordinator_selects_expected_packages(
    subentry_data: dict[str, Any] | str,
    expected_packages: list[ApiPackage],
) -> None:
    """ForecastCoordinator requests the correct MeteoBlue packages per mode."""
    client = _StubForecastClient()
    coordinator = ForecastCoordinator.__new__(ForecastCoordinator)
    coordinator._client = client  # type: ignore[attr-defined]  # noqa: SLF001
    coordinator.subentry = MagicMock()
    coordinator.subentry.data = (
        {CONF_FORECAST_TYPE: subentry_data}
        if isinstance(subentry_data, str)
        else subentry_data
    )
    coordinator.hass = MagicMock()
    coordinator.hass.config.latitude = 50.0
    coordinator.hass.config.longitude = 14.0

    await coordinator._async_update_data()  # noqa: SLF001

    assert client.calls[0]["api_packages"] == expected_packages


class _StubMeteogramClient:
    """Minimal stand-in for MeteoBlueApiClient used by the coordinator test."""

    def __init__(self, image_bytes: bytes) -> None:
        self._image_bytes = image_bytes
        self.calls = 0

    async def async_get_meteogram_extended(
        self,
        **_kwargs: Any,
    ) -> bytes:
        self.calls += 1
        return self._image_bytes


async def test_meteogram_coordinator_returns_light_and_dark_variants() -> None:
    """Coordinator returns transparent light and inverted-transparent dark PNGs."""
    raw_bytes = METEOGRAM_FIXTURE.read_bytes()
    client = _StubMeteogramClient(raw_bytes)

    coordinator = MeteogramCoordinator.__new__(MeteogramCoordinator)
    coordinator._client = client  # type: ignore[attr-defined]  # noqa: SLF001
    coordinator.subentry = MagicMock()
    coordinator.subentry.title = "Test"
    coordinator.subentry.data = {}
    coordinator.hass = MagicMock()
    coordinator.hass.config.latitude = 50.0
    coordinator.hass.config.longitude = 14.0

    result = await coordinator._async_update_data()  # noqa: SLF001

    assert isinstance(result, MeteogramImageSet)
    assert result.meteogram_light.content_type == "image/png"
    assert result.meteogram_dark.content_type == "image/png"
    assert result.meteogram_light.content != raw_bytes
    assert result.meteogram_dark.content != result.meteogram_light.content
    assert result.meteogram_light.content.startswith(PNG_SIGNATURE)
    assert result.meteogram_dark.content.startswith(PNG_SIGNATURE)
    for variant in (result.meteogram_light, result.meteogram_dark):
        with Image.open(BytesIO(variant.content)) as img:
            img.load()
            assert img.mode == "RGBA"
            alpha_min, alpha_max = img.getchannel("A").getextrema()
            assert alpha_min < 10
            assert alpha_max == 255
    assert client.calls == 1
