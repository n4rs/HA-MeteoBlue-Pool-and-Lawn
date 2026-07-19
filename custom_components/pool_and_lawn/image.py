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
"""Image platform for Pool and Lawn."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.image import Image, ImageEntity, ImageEntityDescription
from homeassistant.core import callback
from homeassistant.util import dt as dt_util

from .const import SUBENTRY_TYPE_FORECAST_LOCATION
from .entity import MeteoBlueMeteogramEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .coordinator import MeteogramCoordinator
    from .data import MeteoBlueConfigEntry

ENTITY_DESCRIPTIONS = (
    ImageEntityDescription(
        key="meteogram",
        name="Meteogram",
    ),
    ImageEntityDescription(
        key="meteogram_dark",
        name="Meteogram (dark)",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: MeteoBlueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a meteogram image entity for each location subentry."""
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_FORECAST_LOCATION:
            continue
        coordinator = entry.runtime_data.meteogram_coordinators.get(
            subentry.subentry_id,
        )
        if coordinator is None:
            continue
        async_add_entities(
            (
                MeteoBlueMeteogram(
                    coordinator=coordinator,
                    entity_description=entity_description,
                    platform_domain="image",
                )
                for entity_description in ENTITY_DESCRIPTIONS
            ),
            config_subentry_id=subentry.subentry_id,
        )


class MeteoBlueMeteogram(MeteoBlueMeteogramEntity, ImageEntity):
    """Image entity exposing the MeteoBlue extended meteogram."""

    entity_description: ImageEntityDescription

    def __init__(
        self,
        coordinator: MeteogramCoordinator,
        entity_description: ImageEntityDescription,
        platform_domain: str,
    ) -> None:
        """Initialize the meteogram image entity."""
        super().__init__(coordinator, entity_description, platform_domain)
        ImageEntity.__init__(self, coordinator.hass)
        self._meteogram_variant = (
            "meteogram_dark"
            if entity_description.key == "meteogram_dark"
            else "meteogram_light"
        )
        if coordinator.data is not None:
            image = getattr(coordinator.data, self._meteogram_variant)
            self._attr_content_type = image.content_type
            self._cached_image = Image(
                content_type=image.content_type,
                content=image.content,
            )
            self._attr_image_last_updated = dt_util.utcnow()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Refresh the cached image when the coordinator yields new data."""
        if self.coordinator.data is not None:
            image = getattr(self.coordinator.data, self._meteogram_variant)
            self._attr_content_type = image.content_type
            self._cached_image = Image(
                content_type=image.content_type,
                content=image.content,
            )
            self._attr_image_last_updated = dt_util.utcnow()
        super()._handle_coordinator_update()
