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
"""
Custom integration to integrate meteoblue with Home Assistant.

For more details about this integration, please refer to
https://github.com/dankeder/HomeAssistant-MeteoBlue
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.helpers import httpx_client

from .api import FakeMeteoBlueApiClient, MeteoBlueApiClient
from .const import (
    CONF_ENABLE_FORECAST,
    CONF_ENABLE_METEOGRAM,
    SUBENTRY_TYPE_FORECAST_LOCATION,
)
from .coordinator import (
    AccountUsageCoordinator,
    ForecastCoordinator,
    MeteogramCoordinator,
)
from .data import MeteoBlueData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import MeteoBlueConfigEntry

PLATFORMS: list[Platform] = [
    Platform.IMAGE,
    Platform.SENSOR,
    Platform.WEATHER,
]

_LOGGER = logging.getLogger(__name__)


def _use_fake_client() -> bool:
    return os.environ.get("METEOBLUE_USE_FAKE_CLIENT", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeteoBlueConfigEntry,
) -> bool:
    """Set up a MeteoBlue API-key entry and its location subentries."""
    client_cls = FakeMeteoBlueApiClient if _use_fake_client() else MeteoBlueApiClient
    if client_cls is FakeMeteoBlueApiClient:
        _LOGGER.warning(
            "MeteoBlue: using FakeMeteoBlueApiClient (fixtures, no API calls). "
            "Unset METEOBLUE_USE_FAKE_CLIENT to use the real API.",
        )
    client = client_cls(
        client=httpx_client.get_async_client(hass),
        api_key=entry.data[CONF_API_KEY],
    )
    account_coordinator = AccountUsageCoordinator(
        hass=hass,
        config_entry=entry,
        client=client,
    )
    location_coordinators: dict[str, ForecastCoordinator] = {
        subentry.subentry_id: ForecastCoordinator(
            hass=hass,
            config_entry=entry,
            subentry=subentry,
            client=client,
        )
        for subentry in entry.subentries.values()
        if subentry.subentry_type == SUBENTRY_TYPE_FORECAST_LOCATION
        and subentry.data.get(CONF_ENABLE_FORECAST, True)
    }
    meteogram_coordinators: dict[str, MeteogramCoordinator] = {
        subentry.subentry_id: MeteogramCoordinator(
            hass=hass,
            config_entry=entry,
            subentry=subentry,
            client=client,
        )
        for subentry in entry.subentries.values()
        if subentry.subentry_type == SUBENTRY_TYPE_FORECAST_LOCATION
        and subentry.data.get(CONF_ENABLE_METEOGRAM, True)
    }
    entry.runtime_data = MeteoBlueData(
        client=client,
        account_coordinator=account_coordinator,
        location_coordinators=location_coordinators,
        meteogram_coordinators=meteogram_coordinators,
    )

    await asyncio.gather(
        account_coordinator.async_config_entry_first_refresh(),
        *(
            coordinator.async_config_entry_first_refresh()
            for coordinator in location_coordinators.values()
        ),
        *(
            coordinator.async_config_entry_first_refresh()
            for coordinator in meteogram_coordinators.values()
        ),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: MeteoBlueConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: MeteoBlueConfigEntry,
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
