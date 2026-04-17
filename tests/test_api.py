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
"""Tests for the MeteoBlue API client."""

from __future__ import annotations

from typing import Any

import httpx
import meteoblue.api
import pytest

ApiPackage = meteoblue.api.ApiPackage
MeteoBlueApiClient = meteoblue.api.MeteoBlueApiClient
MeteoBlueApiClientError = meteoblue.api.MeteoBlueApiClientError
MeteoBlueApiClientCommunicationError = (
    meteoblue.api.MeteoBlueApiClientCommunicationError
)
MeteoBlueApiClientAuthenticationError = (
    meteoblue.api.MeteoBlueApiClientAuthenticationError
)


async def test_daily_forecast_sends_expected_request(
    make_client: Any,
    raw_daily_forecast_payload: dict,
) -> None:
    """Client hits /packages/basic-day with the right method and query params."""
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json=raw_daily_forecast_payload)

    client = make_client(handler)
    await client.async_get_forecast(
        latitude=47.558, longitude=7.573, api_packages=[ApiPackage.BASIC_DAY]
    )

    request = captured["request"]
    assert request.method == "GET"
    assert str(request.url).startswith("https://my.meteoblue.com/packages/basic-day")
    assert request.url.params["apikey"] == "test-key"
    assert request.url.params["lat"] == "47.558"
    assert request.url.params["lon"] == "7.573"
    assert request.url.params["format"] == "json"
    assert request.url.params["timeformat"] == "iso8601"
    assert request.url.params["temperatureUnit"] == "C"
    assert request.url.params["windSpeedUnit"] == "m/s"
    assert request.url.params["windDirectionUnit"] == "degree"
    assert request.url.params["precipitationUnit"] == "metric"


async def test_daily_forecast_returns_parsed_json(
    make_client: Any,
    raw_daily_forecast_payload: dict,
) -> None:
    """Client returns the decoded JSON response body."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=raw_daily_forecast_payload)

    client = make_client(handler)
    result = await client.async_get_forecast(
        latitude=47.558, longitude=7.573, api_packages=[ApiPackage.BASIC_DAY]
    )

    assert result == raw_daily_forecast_payload
    assert "data_day" in result
    assert result["data_day"]["time"][0] == "2026-04-16"


@pytest.mark.parametrize("status_code", [401, 403])
async def test_auth_errors_raise_authentication_error(
    make_client: Any,
    status_code: int,
) -> None:
    """401 and 403 responses surface as MeteoBlueApiClientAuthenticationError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"error": "nope"})

    client = make_client(handler)
    with pytest.raises(MeteoBlueApiClientAuthenticationError):
        await client.async_get_forecast(
            latitude=0.0, longitude=0.0, api_packages=[ApiPackage.BASIC_DAY]
        )


async def test_server_error_raises_communication_error(
    make_client: Any,
) -> None:
    """A 5xx response is wrapped as MeteoBlueApiClientCommunicationError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    client = make_client(handler)
    with pytest.raises(MeteoBlueApiClientCommunicationError):
        await client.async_get_forecast(
            latitude=0.0, longitude=0.0, api_packages=[ApiPackage.BASIC_DAY]
        )


async def test_timeout_raises_communication_error(make_client: Any) -> None:
    """Httpx timeouts are wrapped as MeteoBlueApiClientCommunicationError."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    client = make_client(handler)
    with pytest.raises(MeteoBlueApiClientCommunicationError) as excinfo:
        await client.async_get_forecast(
            latitude=0.0, longitude=0.0, api_packages=[ApiPackage.BASIC_DAY]
        )

    assert isinstance(excinfo.value.__cause__, httpx.TimeoutException)


async def test_transport_error_raises_communication_error(
    make_client: Any,
) -> None:
    """Non-timeout httpx errors are wrapped as MeteoBlueApiClientCommunicationError."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    client = make_client(handler)
    with pytest.raises(MeteoBlueApiClientCommunicationError) as excinfo:
        await client.async_get_forecast(
            latitude=0.0, longitude=0.0, api_packages=[ApiPackage.BASIC_DAY]
        )

    assert isinstance(excinfo.value.__cause__, httpx.HTTPError)


async def test_unexpected_error_raises_generic_api_error(
    make_client: Any,
) -> None:
    """Non-httpx exceptions fall through to MeteoBlueApiClientError."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise RuntimeError("something broke")

    client = make_client(handler)
    with pytest.raises(MeteoBlueApiClientError) as excinfo:
        await client.async_get_forecast(
            latitude=0.0, longitude=0.0, api_packages=[ApiPackage.BASIC_DAY]
        )

    assert not isinstance(excinfo.value, MeteoBlueApiClientCommunicationError)
    assert not isinstance(excinfo.value, MeteoBlueApiClientAuthenticationError)
    assert isinstance(excinfo.value.__cause__, RuntimeError)


PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-meteogram-body"


async def test_meteogram_sends_expected_request(make_client: Any) -> None:
    """Client hits /images/meteogram_extended with the right method and query params."""
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(
            200, content=PNG_BYTES, headers={"content-type": "image/png"}
        )

    client = make_client(handler)
    await client.async_get_meteogram_extended(
        latitude=49.1831,
        longitude=16.5948,
        location_name="Brno",
    )

    request = captured["request"]
    assert request.method == "GET"
    assert str(request.url).startswith(
        "https://my.meteoblue.com/images/meteogram_extended"
    )
    assert request.url.params["apikey"] == "test-key"
    assert request.url.params["lat"] == "49.1831"
    assert request.url.params["lon"] == "16.5948"
    assert request.url.params["location_name"] == "Brno"


async def test_meteogram_returns_png_bytes(make_client: Any) -> None:
    """Client returns the raw PNG response body and content-type."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=PNG_BYTES, headers={"content-type": "image/png"}
        )

    client = make_client(handler)
    result = await client.async_get_meteogram_extended(
        latitude=0.0, longitude=0.0, location_name="nowhere"
    )

    assert result == PNG_BYTES


async def test_meteogram_rejects_non_image_content_type(make_client: Any) -> None:
    """Non-image content-type from the meteogram endpoint raises a comms error."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"<html>oops</html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )

    client = make_client(handler)
    with pytest.raises(MeteoBlueApiClientCommunicationError):
        await client.async_get_meteogram_extended(
            latitude=0.0, longitude=0.0, location_name="nowhere"
        )


@pytest.mark.parametrize("status_code", [401, 403])
async def test_meteogram_auth_errors_raise_authentication_error(
    make_client: Any,
    status_code: int,
) -> None:
    """401 and 403 responses from the meteogram endpoint surface as auth errors."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"error": "nope"})

    client = make_client(handler)
    with pytest.raises(MeteoBlueApiClientAuthenticationError):
        await client.async_get_meteogram_extended(
            latitude=0.0, longitude=0.0, location_name="nowhere"
        )


PAGE_SIZE = meteoblue.api.ACCOUNT_USAGE_PAGE_SIZE


def _make_item(index: int) -> dict[str, Any]:
    return {
        "request_count": 1,
        "request_credits": 1000,
        "request_date": "2026-04-20",
        "request_type": f"item-{index}",
    }


async def test_account_usage_single_page(make_client: Any) -> None:
    """When total fits in one page, the client issues a single request."""
    requests: list[httpx.Request] = []
    items = [_make_item(i) for i in range(3)]

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "items": items,
                "metadata": {"page": 1, "per": PAGE_SIZE, "total": 3},
            },
        )

    client = make_client(handler)
    result = await client.async_get_account_usage()

    assert len(requests) == 1
    request = requests[0]
    assert request.method == "GET"
    assert str(request.url).startswith("https://my.meteoblue.com/account/usage")
    assert request.url.params["apikey"] == "test-key"
    assert request.url.params["per"] == str(PAGE_SIZE)
    assert request.url.params["page"] == "1"
    assert result == {
        "items": items,
        "metadata": {"page": 1, "per": PAGE_SIZE, "total": 3},
    }


async def test_account_usage_paginates_all_records(make_client: Any) -> None:
    """Client fetches every page and accumulates items in order."""
    total = 2 * PAGE_SIZE + 50
    all_items = [_make_item(i) for i in range(total)]
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        page = int(request.url.params["page"])
        start = (page - 1) * PAGE_SIZE
        page_items = all_items[start : start + PAGE_SIZE]
        return httpx.Response(
            200,
            json={
                "items": page_items,
                "metadata": {"page": page, "per": PAGE_SIZE, "total": total},
            },
        )

    client = make_client(handler)
    result = await client.async_get_account_usage()

    assert [r.url.params["page"] for r in requests] == ["1", "2", "3"]
    assert all(r.url.params["per"] == str(PAGE_SIZE) for r in requests)
    assert all(r.url.params["apikey"] == "test-key" for r in requests)
    assert result["items"] == all_items
    assert result["metadata"] == {"page": 3, "per": PAGE_SIZE, "total": total}


async def test_account_usage_stops_on_empty_page(make_client: Any) -> None:
    """A page returning no items ends the loop even if `total` claims more."""
    first_page = [_make_item(i) for i in range(PAGE_SIZE)]
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        page = int(request.url.params["page"])
        if page == 1:
            return httpx.Response(
                200,
                json={
                    "items": first_page,
                    "metadata": {"page": 1, "per": PAGE_SIZE, "total": 9999},
                },
            )
        return httpx.Response(
            200,
            json={
                "items": [],
                "metadata": {"page": page, "per": PAGE_SIZE, "total": 9999},
            },
        )

    client = make_client(handler)
    result = await client.async_get_account_usage()

    assert [r.url.params["page"] for r in requests] == ["1", "2"]
    assert result["items"] == first_page


async def test_account_usage_auth_error_on_later_page(make_client: Any) -> None:
    """A 401 on a later page surfaces as an authentication error."""
    first_page = [_make_item(i) for i in range(PAGE_SIZE)]

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        if page == 1:
            return httpx.Response(
                200,
                json={
                    "items": first_page,
                    "metadata": {
                        "page": 1,
                        "per": PAGE_SIZE,
                        "total": PAGE_SIZE + 10,
                    },
                },
            )
        return httpx.Response(401, json={"error": "nope"})

    client = make_client(handler)
    with pytest.raises(MeteoBlueApiClientAuthenticationError):
        await client.async_get_account_usage()
