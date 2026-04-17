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
"""MeteoBlue API Client."""

from __future__ import annotations

import asyncio
import json
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import httpx

API_BASE_URL = "https://my.meteoblue.com"

ACCOUNT_USAGE_PAGE_SIZE = 100


class ApiPackage(Enum):
    """MeteoBlue forecast API package identifiers."""

    BASIC_DAY = "basic-day"
    BASIC_1H = "basic-1h"


class MeteoBlueApiClientError(Exception):
    """Exception to indicate a general API error."""


class MeteoBlueApiClientCommunicationError(
    MeteoBlueApiClientError,
):
    """Exception to indicate a communication error."""


class MeteoBlueApiTimeoutError(
    MeteoBlueApiClientCommunicationError,
):
    """Exception to indicate an API timeout."""


class MeteoBlueApiClientAuthenticationError(
    MeteoBlueApiClientError,
):
    """Exception to indicate an authentication error."""


class MeteoBlueApiClient:
    """MeteoBlue API Client."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        api_key: str,
    ) -> None:
        """MeteoBlue API Client."""
        self._api_key = api_key
        self._client = client

    async def async_get_forecast(
        self,
        latitude: float,
        longitude: float,
        api_packages: list[ApiPackage],
        asl: float | None = None,
    ) -> Any:
        """Get weather forecast from the MeteoBlue Forecast API."""
        packages_path = "_".join(pkg.value for pkg in api_packages)
        params: dict[str, Any] = {
            "apikey": self._api_key,
            "lat": latitude,
            "lon": longitude,
            "format": "json",
            "timeformat": "iso8601",
            "temperatureUnit": "C",
            "windSpeedUnit": "m/s",
            "windDirectionUnit": "degree",
            "precipitationUnit": "metric",
        }
        if asl is not None:
            params["asl"] = asl
        return await self._api_wrapper(
            method="get",
            url=f"{API_BASE_URL}/packages/{packages_path}",
            params=params,
        )

    async def async_get_meteogram_extended(
        self,
        latitude: float,
        longitude: float,
        location_name: str,
    ) -> bytes:
        """Get the extended meteogram image from the MeteoBlue Image API."""
        params: dict[str, Any] = {
            "apikey": self._api_key,
            "lat": latitude,
            "lon": longitude,
            "location_name": location_name,
        }
        content, content_type = await self._api_wrapper(
            method="get",
            url=f"{API_BASE_URL}/images/meteogram_extended",
            params=params,
            response_type="bytes",
        )
        mime_type = content_type.split(";", 1)[0].strip().lower()
        if not mime_type.startswith("image/"):
            msg = f"Unexpected content-type from meteogram endpoint: {content_type!r}"
            raise MeteoBlueApiClientCommunicationError(msg)
        return content

    async def async_get_account_usage(self) -> Any:
        """Fetch account usage info, paging through all available records."""
        items: list[Any] = []
        page = 1
        while True:
            response = await self._api_wrapper(
                method="get",
                url=f"{API_BASE_URL}/account/usage",
                params={
                    "apikey": self._api_key,
                    "per": ACCOUNT_USAGE_PAGE_SIZE,
                    "page": page,
                },
            )
            page_items = response.get("items", [])
            metadata = response.get("metadata", {})
            items.extend(page_items)
            if not page_items or (len(items) >= metadata.get("total", 0)):
                return {"items": items, "metadata": metadata}
            page += 1

    async def _api_wrapper(  # noqa: PLR0913
        self,
        method: str,
        url: str,
        data: dict | None = None,
        headers: dict | None = None,
        params: dict | None = None,
        response_type: Literal["json", "bytes"] = "json",
    ) -> Any:
        """Get information from the API."""
        try:
            response = await self._client.request(
                method=method,
                url=url,
                headers=headers,
                json=data,
                params=params,
                timeout=10,
            )
            response.raise_for_status()
            if response_type == "bytes":
                return (
                    response.content,
                    response.headers.get("content-type", ""),
                )
            return response.json()

        except httpx.TimeoutException as exception:
            msg = f"Timeout error fetching information: {exception}"
            raise MeteoBlueApiTimeoutError(
                msg,
            ) from exception
        except httpx.HTTPStatusError as exception:
            if exception.response.status_code in (401, 403):
                msg = f"Invalid API key: {exception}"
                raise MeteoBlueApiClientAuthenticationError(
                    msg,
                ) from exception
            msg = f"Error fetching information: {exception}"
            raise MeteoBlueApiClientCommunicationError(
                msg,
            ) from exception
        except httpx.HTTPError as exception:
            msg = f"Error fetching information: {exception}"
            raise MeteoBlueApiClientCommunicationError(
                msg,
            ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            msg = f"Unexpected error occurred: {exception}"
            raise MeteoBlueApiClientError(
                msg,
            ) from exception


class FakeMeteoBlueApiClient(MeteoBlueApiClient):
    """Drop-in MeteoBlue API client that returns a canned response."""

    async def async_get_forecast(
        self,
        latitude: float,  # noqa: ARG002
        longitude: float,  # noqa: ARG002
        api_packages: list[ApiPackage],  # noqa: ARG002
        asl: float | None = None,  # noqa: ARG002
    ) -> Any:
        """Return the fixture response without hitting the API."""
        fixture_path = (
            Path(__file__).parent.parent.parent / "tests" / "fixtures" / "forecast.json"
        )
        return json.loads(await asyncio.to_thread(fixture_path.read_text))

    async def async_get_meteogram_extended(
        self,
        latitude: float,  # noqa: ARG002
        longitude: float,  # noqa: ARG002
        location_name: str,  # noqa: ARG002
    ) -> bytes:
        """Return the fixture PNG without hitting the API."""
        fixture_path = (
            Path(__file__).parent.parent.parent
            / "tests"
            / "fixtures"
            / "meteogram_extended.png"
        )
        return await asyncio.to_thread(fixture_path.read_bytes)

    async def async_get_account_usage(self) -> Any:
        """Return the fixture response without hitting the API."""
        fixture_path = (
            Path(__file__).parent.parent.parent
            / "tests"
            / "fixtures"
            / "account_usage.json"
        )
        return json.loads(await asyncio.to_thread(fixture_path.read_text))
