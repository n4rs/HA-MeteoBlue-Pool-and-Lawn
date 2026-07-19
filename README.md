# 🌦️ MeteoBlue for Home Assistant

A Home Assistant integration for the [MeteoBlue](https://www.meteoblue.com/)
weather service. It exposes current conditions and forecasts as a weather
entity, renders 7-day extended meteograms as image entities (light and dark
variants), and tracks API credit usage as a sensor — all configured per
location through the UI.

## ✨ Features

- 🌤️ **Weather entity** with current conditions and a daily or hourly forecast
  (selectable per location). Hourly forecasts include temperature, humidity,
  wind speed, wind gusts, precipitation, precipitation probability, and cloud
  coverage when returned by MeteoBlue.
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

- Home Assistant **2026.3.2** or newer.
- Python **3.14.2** or newer (matches the supported Home Assistant runtime).
- A MeteoBlue API key from [my.meteoblue.com](https://my.meteoblue.com).

## 📦 Installation

### 🏪 HACS (recommended)

1. In HACS, open **Integrations** → menu → **Custom repositories**.
2. Add `https://github.com/dankeder/HomeAssistant-MeteoBlue` as an
   **Integration** repository.
3. Install **MeteoBlue** from the HACS list and restart Home Assistant.

### 🔧 Manual

1. Copy [custom_components/meteoblue/](custom_components/meteoblue/) into your
   Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.

## ⚙️ Configuration

### 🔑 1. Add the API key

**Settings → Devices & Services → Add Integration → MeteoBlue**, then enter:

- **Name** — a label for this API key (e.g. *MeteoBlue*).
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
| **Additional hourly clouds and wind data** | Only shown for hourly forecasts. When enabled, the hourly Forecast API call adds `clouds-1h` and `wind-1h`, producing `basic-1h_clouds-1h_wind-1h`. |
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
| `weather.meteoblue_home_weather` | Current conditions and forecast. Only created when **Enable forecast** is on. |
| `image.meteoblue_home_meteogram` | 7-day extended meteogram (light). Only created when **Enable meteogram** is on. |
| `image.meteoblue_home_meteogram_dark` | Same meteogram, tone-inverted for dark themes. |
| `sensor.meteoblue_home_credits_used` | Total API credits consumed by your account, increasing over time. |

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

## 🛠️ Development

The repository ships a small set of helper scripts in [scripts/](scripts/):

- [scripts/setup](scripts/setup) — install dependencies via `uv sync`.
- [scripts/run](scripts/run) — start Home Assistant with this integration
  loaded against the [config/](config/) stub.
- [scripts/lint](scripts/lint) — run `ruff format` and `ruff check`.
- [scripts/test](scripts/test) — run the test suite with `pytest`.

Set `METEOBLUE_USE_FAKE_CLIENT=1` before [scripts/run](scripts/run) to load
`FakeMeteoBlueApiClient`, which serves canned responses from
[tests/fixtures/](tests/fixtures/) instead of calling the MeteoBlue API.

## 🔗 Links

- MeteoBlue [Forecast API documentation](https://docs.meteoblue.com/en/weather-apis/forecast-api/overview)
  and [OpenAPI spec](https://my.meteoblue.com/packages/redoc#tag/Overview-Structure).
- MeteoBlue [Image API documentation](https://docs.meteoblue.com/en/weather-apis/images-api/overview).
- MeteoBlue [Account API documentation](https://docs.meteoblue.com/en/weather-apis/further-apis/account-api).
- [Issue tracker](https://github.com/dankeder/HomeAssistant-MeteoBlue/issues).

## 📄 License

Licensed under the [Apache License, Version 2.0](LICENSE).
