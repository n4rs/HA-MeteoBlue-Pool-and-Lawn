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
"""MeteoBlue entity base classes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import ATTRIBUTION, DOMAIN
from .coordinator import AccountUsageCoordinator, ForecastCoordinator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigSubentry
    from homeassistant.helpers.entity import EntityDescription


def _build_entity_id(
    platform_domain: str,
    subentry: ConfigSubentry,
    entity_description: EntityDescription,
) -> str:
    """Build an entity_id of the form ``{platform}.pool_and_lawn_{title}_{name}``."""
    return (
        f"{platform_domain}.pool_and_lawn_"
        f"{slugify(str(subentry.title))}_"
        f"{slugify(str(entity_description.key))}"
    )


class MeteoBlueAccountEntity(CoordinatorEntity[AccountUsageCoordinator]):
    """Base class for account-usage entities attached to a location device."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AccountUsageCoordinator,
        subentry: ConfigSubentry,
        entity_description: EntityDescription,
        platform_domain: str,
    ) -> None:
        """Initialize an account-level entity bound to a location device."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{subentry.subentry_id}-{entity_description.key}"
        self.entity_id = _build_entity_id(platform_domain, subentry, entity_description)
        self._attr_device_info = DeviceInfo(
            identifiers={(f"{DOMAIN}_location", subentry.subentry_id)},
            name=subentry.title,
            manufacturer="MeteoBlue",
        )


class MeteoBlueLocationEntity(CoordinatorEntity[ForecastCoordinator]):
    """Base class for entities tied to a MeteoBlue location subentry."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ForecastCoordinator,
        entity_description: EntityDescription,
        platform_domain: str,
    ) -> None:
        """Initialize a location-level entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        subentry: ConfigSubentry = coordinator.subentry
        self._attr_unique_id = f"{subentry.subentry_id}-{entity_description.key}"
        self.entity_id = _build_entity_id(platform_domain, subentry, entity_description)
        self._attr_device_info = DeviceInfo(
            identifiers={(f"{DOMAIN}_location", subentry.subentry_id)},
            name=subentry.title,
            manufacturer="MeteoBlue",
        )
