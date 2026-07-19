# 🌿 HomeAssistant Pool and Lawn

**HomeAssistant Pool and Lawn** is a Home Assistant custom integration for
building weather-based operating-time indicators for pool and lawn equipment. It
uses the [MeteoBlue](https://www.meteoblue.com/) Forecast, Image, and Account
APIs to expose weather forecasts, meteograms, and API credit usage in Home
Assistant.

This project started as a fork of
[HomeAssistant-MeteoBlue](https://github.com/dankeder/HomeAssistant-MeteoBlue)
by Dan Keder. Attribution to the original project and other upstream components
is preserved in [NOTICE](NOTICE).

## 🎯 Project goal

The goal of this integration is to make MeteoBlue weather data available in Home
Assistant in a form that can be used to calculate practical runtime indicators
for outdoor equipment, including:

- pool pump operating time for saltwater pools;
- pool pump operating time for standard/chlorine pools;
- salt chlorinator operating time;
- lawn irrigation duration.

The integration provides the weather inputs for those calculations, such as
hourly temperature, humidity, wind speed, wind gusts, precipitation,
precipitation probability, and cloud coverage. The actual control logic can then
be implemented with Home Assistant helpers, templates, automations, or scripts.

## ✨ Features

- 🌤️ **Weather entity** with current conditions and a daily or hourly forecast
  (selectable per location). Hourly forecasts include temperature, humidity,
  wind speed, wind gusts, precipitation, precipitation probability, and cloud
  coverage when returned by MeteoBlue.
<<<<<<< ours
=======
- 🌱 **Pool and lawn focused hourly data** suitable for deriving runtime
  indicators in Home Assistant automations/templates for:
  - pool circulation pumps, including saltwater and standard pool setups;
  - salt chlorinators;
  - lawn irrigation duration.
>>>>>>> theirs
- 🖼️ **Meteogram images** — the 7-day extended meteogram, available in both light
  and dark variants. The dark variant is generated locally by inverting the
  light image while preserving hue and saturation, so it stays readable in
  dark dashboards.
- 📊 **Credits sensor** showing total API credits consumed, so you can monitor
  your usage against your MeteoBlue plan.
- 🗺️ **Multiple locations per API key.** Each location is added as a subentry and
  uses either the Home Assistant configured location or custom coordinates
  (with optional elevation).
- 🎚️ **Independent toggles and update intervals** for the forecast and the
  meteogram, per location.

## 📋 Requirements

- Home Assistant **2025.3.0** or newer.
- Python version compatible with your Home Assistant runtime.
- A MeteoBlue API key from [my.meteoblue.com](https://my.meteoblue.com).

## 📦 Installation

### 🏪 HACS (recommended)

1. In HACS, open **Integrations** → menu → **Custom repositories**.
2. Add `https://github.com/n4rs/HA-MeteoBlue-Pool-and-Lawn` as an
   **Integration** repository.
3. Install **HomeAssistant Pool and Lawn** from the HACS list and restart Home
   Assistant.

### 🔧 Manual

1. Copy [custom_components/pool_and_lawn/](custom_components/pool_and_lawn/) into
   your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.

## ⚙️ Configuration

### 🔑 1. Add the API key

**Settings → Devices & Services → Add Integration → HomeAssistant Pool and Lawn**,
then enter:

- **Name** — a label for this API key (e.g. *Pool and Lawn*).
- **API key** — your key from [my.meteoblue.com](https://my.meteoblue.com).

The key is validated against the MeteoBlue Account API before the entry is
created.

### 📍 2. Add one or more forecast locations

Each location is a subentry on the API-key entry. Open the entry and choose
**Add forecast location**:

| Field | Description |
| -- | -- |
| **Name** | Display name for the location (used in entity IDs). |
| **Location mode** | `auto` uses the Home Assistant configured location; `custom` lets you pick a point on the map. |
| **Latitude / Longitude** *(custom mode)* | Picked via the map selector. |
| **Elevation** *(custom mode, optional)* | Meters above sea level. |
| **Enable forecast** | Whether to create the weather entity. |
| **Forecast type** | `daily` or `hourly`. Daily forecasts use MeteoBlue's `basic-day` package. Hourly forecasts always use `basic-1h`, and the integration also exposes a daily forecast that it derives locally from the hourly data. |
<<<<<<< ours
| **Additional hourly clouds and wind data** | Only shown for hourly forecasts. When enabled, the hourly Forecast API call adds `clouds-1h` and `wind-1h`, producing `basic-1h_clouds-1h_wind-1h`. |
=======
| **Additional hourly clouds and wind data** | Only shown after choosing an enabled hourly forecast. When enabled, the hourly Forecast API call adds `clouds-1h` and `wind-1h`, producing `basic-1h_clouds-1h_wind-1h`. |
>>>>>>> theirs
| **Forecast update interval** | Minimum 6 hours, default 6 hours. |
| **Enable meteogram** | Whether to create the meteogram image entities. |
| **Meteogram update interval** | Minimum 6 hours, default 6 hours. |

The 6-hour minimum reflects MeteoBlue's update cadence: forecast models run
[twice per day](https://content.meteoblue.com/en/research-education/specifications/processes/updating),
so polling more often just spends credits without delivering newer data.

## 🏷️ Entities

For a location named *Home*, the integration creates:

| Entity ID | Description |
| -- | -- |
| `weather.pool_and_lawn_home_weather` | Current conditions and forecast. Only created when **Enable forecast** is on. |
| `image.pool_and_lawn_home_meteogram` | 7-day extended meteogram (light). Only created when **Enable meteogram** is on. |
| `image.pool_and_lawn_home_meteogram_dark` | Same meteogram, tone-inverted for dark themes. |
| `sensor.pool_and_lawn_home_credits_used` | Total API credits consumed by your account, increasing over time. |

## 💳 MeteoBlue API credits

Free API tier provides 10mil credits for 1 year. Each request costs certain
amount of credits. The cost of API calls used by this integration are:

API package | Credits per request
-- | --
`basic-day` | 4000 credits/request
`basic-1h` | 8000 credits/request
`clouds-1h` | Optional add-on for hourly forecast requests
`wind-1h` | Optional add-on for hourly forecast requests
`meteogram_extended` | 16000 credits/request

Hourly forecasts always request `basic-1h`. If **Additional hourly clouds and
wind data** is enabled, the integration requests `basic-1h_clouds-1h_wind-1h`
in one Forecast API call so Home Assistant can receive hourly temperature,
humidity, wind speed, wind gusts, precipitation, precipitation probability, and
cloud coverage. Use the credits sensor and the MeteoBlue account dashboard to
confirm the exact charge for your plan and API package combination.

The weather entity exposes these values through Home Assistant's weather
attributes and forecast service. For example, hourly `weather.get_forecasts`
responses can include fields equivalent to:

```yaml
datetime: "2026-07-19T12:00:00+01:00"
temperature: 31.2
humidity: 42
wind_speed: 4.3
wind_gust_speed: 8.1
cloud_coverage: 18
precipitation: 0
precipitation_probability: 5
```
<<<<<<< ours

### ⏱️ Sizing your update intervals

A free-tier budget of 10M credits/year works out to roughly **27,000 credits
per day**. A few worked examples for one location:

- **Daily forecast every 12 h + meteogram every 24 h** — `2 × 4000 + 1 × 16000`
  = 24,000/day. Comfortably within the free tier.
- **Hourly forecast every 24 h + meteogram every 24 h** - `1 × 8000 + 1 × 16000`
  = 24,000/day. Fits into the free tier.
- **Daily forecast every 6 h + meteogram every 24 h** — `4 × 4000 + 1 × 16000`
  = 32,000/day. Slightly over budget of the free tier — bump the forecast to every 8 h.
- **Daily forecast every 8 h + meteogram every 24 h** — `3 × 4000 + 1 × 16000`
  = 32,000/day. Fits into the free tier.
- **Hourly forecast every 6 h + meteogram every 12 h** — `4 × 8000 + 2 × 16000`
  = 64,000/day. Requires a paid plan.

The credits sensor lets you confirm actual consumption against these
estimates.
=======
>>>>>>> theirs

## 🛠️ Development

The repository ships a small set of helper scripts in [scripts/](scripts/):

- [scripts/setup](scripts/setup) — install dependencies via `uv sync`.
- [scripts/run](scripts/run) — start Home Assistant with this integration
  loaded against the [config/](config/) stub.
- [scripts/lint](scripts/lint) — run `ruff format` and `ruff check`.
- [scripts/test](scripts/test) — run the test suite with `pytest`.

Set `POOL_AND_LAWN_USE_FAKE_CLIENT=1` before [scripts/run](scripts/run) to load
`FakeMeteoBlueApiClient`, which serves canned responses from
[tests/fixtures/](tests/fixtures/) instead of calling the MeteoBlue API.

## 🔗 Links

- MeteoBlue [Forecast API documentation](https://docs.meteoblue.com/en/weather-apis/forecast-api/overview)
  and [OpenAPI spec](https://my.meteoblue.com/packages/redoc#tag/Overview-Structure).
- MeteoBlue [Image API documentation](https://docs.meteoblue.com/en/weather-apis/images-api/overview).
- MeteoBlue [Account API documentation](https://docs.meteoblue.com/en/weather-apis/further-apis/account-api).
- [Issue tracker](https://github.com/n4rs/HA-MeteoBlue-Pool-and-Lawn/issues).

## 📄 License and attribution

This repository uses a composite license. Original upstream code remains under
its original Apache 2.0/MIT terms. HomeAssistant Pool and Lawn modifications and
additions are Copyright 2026 n4rs. All rights reserved. See [LICENSE](LICENSE)
and [NOTICE](NOTICE) for details.
