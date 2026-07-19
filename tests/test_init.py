"""Tests for Pool and Lawn integration setup helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, call

from homeassistant.const import Platform
from pool_and_lawn import _remove_legacy_meteogram_entities
from pool_and_lawn.const import DOMAIN

if TYPE_CHECKING:
    import pytest


def test_remove_legacy_meteogram_entities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Obsolete image entities are removed from the entity registry."""
    registry = MagicMock()
    registry.async_get_entity_id.side_effect = [
        "image.pool_and_lawn_home_meteogram",
        "image.pool_and_lawn_home_meteogram_dark",
    ]
    monkeypatch.setattr("pool_and_lawn.er.async_get", lambda _hass: registry)

    subentry = MagicMock(subentry_id="location-id")
    entry = MagicMock()
    entry.subentries = {subentry.subentry_id: subentry}

    _remove_legacy_meteogram_entities(MagicMock(), entry)

    assert registry.async_get_entity_id.call_args_list == [
        call(Platform.IMAGE, DOMAIN, "location-id-meteogram"),
        call(Platform.IMAGE, DOMAIN, "location-id-meteogram_dark"),
    ]
    assert registry.async_remove.call_args_list == [
        call("image.pool_and_lawn_home_meteogram"),
        call("image.pool_and_lawn_home_meteogram_dark"),
    ]
