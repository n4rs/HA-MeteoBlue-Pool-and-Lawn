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
"""Sensor platform for meteoblue."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)

from .const import SUBENTRY_TYPE_FORECAST_LOCATION
from .entity import MeteoBlueAccountEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .data import MeteoBlueConfigEntry

ENTITY_DESCRIPTIONS = (
    SensorEntityDescription(
        key="credits_used",
        name="Credits Used",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="credits",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: MeteoBlueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up an account-usage sensor on each location subentry device."""
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_FORECAST_LOCATION:
            continue
        async_add_entities(
            (
                MeteoBlueCreditsUsed(
                    coordinator=entry.runtime_data.account_coordinator,
                    subentry=subentry,
                    entity_description=entity_description,
                    platform_domain="sensor",
                )
                for entity_description in ENTITY_DESCRIPTIONS
            ),
            config_subentry_id=subentry.subentry_id,
        )


class MeteoBlueCreditsUsed(MeteoBlueAccountEntity, SensorEntity):
    """Sensor exposing the total MeteoBlue API credits consumed."""

    @property
    def native_value(self) -> int | None:
        """Return the sum of request_credits across all account usage items."""
        if not self.coordinator.data:
            return None
        items = self.coordinator.data.get("items") or []
        if not items:
            return None
        return sum(item.get("request_credits", 0) for item in items)
