# Copyright 2026 Dan Keder
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
"""Custom types for meteoblue."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .api import MeteoBlueApiClient
    from .coordinator import (
        AccountUsageCoordinator,
        ForecastCoordinator,
        MeteogramCoordinator,
    )


type MeteoBlueConfigEntry = ConfigEntry[MeteoBlueData]


@dataclass
class MeteoBlueData:
    """Runtime data for a MeteoBlue API-key config entry."""

    client: MeteoBlueApiClient
    account_coordinator: AccountUsageCoordinator
    location_coordinators: dict[str, ForecastCoordinator] = field(default_factory=dict)
    meteogram_coordinators: dict[str, MeteogramCoordinator] = field(
        default_factory=dict
    )
