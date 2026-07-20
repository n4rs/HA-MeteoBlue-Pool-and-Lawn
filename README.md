# 🌿 HomeAssistant Pool and Lawn

**HomeAssistant Pool and Lawn** is a Home Assistant custom integration for
building weather-based operating-time indicators for pool and lawn equipment. It
uses the [MeteoBlue](https://www.meteoblue.com/) Forecast and Account
APIs to expose weather forecasts and API credit usage in Home Assistant.

> [!IMPORTANT]
> Pool-control and lawn-irrigation data is only available when the forecast type
> is set to **Hourly** and **Additional hourly clouds and wind data** is enabled.
> This adds MeteoBlue's `clouds-1h` and `wind-1h` packages to the hourly request.

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
precipitation probability, and cloud coverage. It also calculates a daily lawn
irrigation-need level; other control logic can be implemented with Home Assistant
helpers, templates, automations, or scripts.

## ✨ Features

- 🌤️ **Weather entity** with current conditions and a daily or hourly forecast
  (selectable per location). Hourly forecasts include temperature, humidity,
  wind speed, wind gusts, precipitation, precipitation probability, and cloud
  coverage when returned by MeteoBlue.
- 🌱 **Pool and lawn focused hourly data** suitable for deriving runtime
  indicators in Home Assistant automations/templates for:
  - pool circulation pumps, including saltwater and standard pool setups;
  - salt chlorinators;
  - lawn irrigation duration.
- **Seven-day lawn irrigation need** as stable sensors with integer levels from
  0 (do not irrigate) to 5 (maximum need), calculated from the existing hourly
  forecast without another API request.
- 📊 **Credits sensor** showing total API credits consumed, so you can monitor
  your usage against your MeteoBlue plan.
- 🗺️ **Multiple locations per API key.** Each location is added as a subentry and
  uses either the Home Assistant configured location or custom coordinates
  (with optional elevation).
- 🎚️ **Configurable forecast update intervals** per location.

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
| **Additional hourly clouds and wind data** | Only shown after choosing an enabled hourly forecast. This must be enabled to provide data for lawn-irrigation and pool-control calculations. The hourly Forecast API call adds `clouds-1h` and `wind-1h`, producing `basic-1h_clouds-1h_wind-1h`. |
| **Pool configuration** *(hourly only, optional)* | Enables seven daily saltwater-pool pump runtime estimates. Requires **Additional hourly clouds and wind data**. |
| **Pool volume** | Water volume in m³; must be greater than zero. |
| **Nominal pump flow** | Pump flow in m³/h. Used only for hydraulic diagnostics, never as a runtime minimum. |
| **Hydraulic efficiency factor** | Effective-to-nominal flow ratio from `0.40` to `1.00`; default `0.75`. Diagnostic only. |
| **Nominal chlorinator output** | Chlorine production at 100% output in g/h; must be greater than zero. |
| **Daily free chlorine target** | Assumed starting and ending free chlorine in ppm; default `2.0`. It is not added to daily demand. |
| **Forecast update interval** | Minimum 6 hours, default 6 hours. |

The 6-hour minimum reflects MeteoBlue's update cadence: forecast models run
[twice per day](https://content.meteoblue.com/en/research-education/specifications/processes/updating),
so polling more often just spends credits without delivering newer data.

## 🏷️ Entities

For a location named *Home*, the integration creates:

| Entity ID | Description |
| -- | -- |
| `weather.pool_and_lawn_home_weather` | Current conditions and forecast. Only created when **Enable forecast** is on. |
| `sensor.pool_and_lawn_home_credits_used` | Total API credits consumed by your account, increasing over time. |
| `sensor.pool_and_lawn_home_irrigation_level_0` | Irrigation need for today, from 0 to 5. Requires an hourly forecast with the `clouds-1h` and `wind-1h` packages enabled. |
| `sensor.pool_and_lawn_home_irrigation_level_1` … `_6` | Irrigation need for the following six local forecast dates. Missing offsets remain unavailable. |
| `sensor.pool_and_lawn_home_pool_pump_hours_0` | Recommended saltwater-pool pump hours for today. Requires pool configuration. |
| `sensor.pool_and_lawn_home_pool_pump_hours_1` … `_6` | Recommended pump hours for the following six local forecast dates. |

### Lawn irrigation need

An hourly location creates seven fixed sensor entities, with offsets `0` through
`6`. Their unique IDs contain the location subentry ID and offset, so the same
entities are reused as dates advance. The concrete local date is exposed through
the `forecast_date` attribute. Sensors update with the existing forecast
coordinator and are recalculated locally at midnight; they make no additional
MeteoBlue requests.

The level has this meaning:

| Level | Meaning |
| --: | -- |
| 0 | Do not irrigate |
| 1 | Residual irrigation |
| 2 | Reduced irrigation |
| 3 | Moderate irrigation |
| 4 | High irrigation |
| 5 | Maximum irrigation |

For each local forecast date, the calculator uses the daily maximum temperature;
afternoon humidity; central-day wind, gusts, and total cloud cover; the forecast
month; and daily precipitation. MeteoBlue's hourly `isdaylight` values determine
sunrise and sunset. The main window runs from two hours after sunrise until two
hours before sunset, while humidity uses solar noon until two hours before
sunset. If `isdaylight` is absent, sunrise and sunset are calculated for that
date and location with Astral. No fixed civil-hour fallback is used.

Temperature, humidity, wind/gust, clouds, and month contribute a base score from
0 to 16. The score maps to an initial level from 0 to 5. Weighted precipitation
then reduces that level by one at 0.5 mm, two at 1.5 mm, three at 3 mm, and to
zero at 5 mm. It also forces zero when gross precipitation reaches 8 mm and the
maximum probability is at least 40%. Wind and gusts are normalized to km/h from
the explicit API units, never inferred from their magnitude.

The entity attributes explain the complete calculation. For example:

```yaml
forecast_date: "2026-07-20"
forecast_day_offset: 1
sunrise: "2026-07-20T06:00:00+01:00"
sunset: "2026-07-20T21:00:00+01:00"
solar_source: meteoblue_isdaylight
core_window_used: solar_core
humidity_window_used: solar_afternoon
temperature_max: 34.2
humidity_mean: 42.5
wind_mean_kmh: 12.4
gust_max_kmh: 31.8
cloud_cover_mean: 18.0
gross_precipitation: 1.0
weighted_precipitation: 0.6
base_score: 15
initial_level: 5
rain_level_reduction: 1
final_level: 4
```

If an essential input, a usable solar period, or an explicit supported wind unit
is missing, the relevant entity is unavailable and exposes an
`unavailable_reason` attribute instead of inventing weather values.

### Saltwater pool pump runtime estimate

When pool configuration is enabled, the integration creates seven sensors with
stable offsets `0` through `6`. They are local, open-loop weather estimates: no
pump is controlled and no real free-chlorine, ORP, CYA, water-temperature, or
pool-usage measurement is available. The result is not a guarantee that actual
free chlorine will reach the configured target.

For each local forecast date, hourly values are aggregated into maximum air
temperature, maximum daytime UV, daylight duration from `isdaylight`, mean
daytime cloud cover, total precipitation, mean daytime wind, and maximum daytime
gust. Wind is converted to km/h only from MeteoBlue's explicit units. Astral is
used for sunrise and sunset only when `isdaylight` is absent. Missing UV is
estimated from daylight duration and cloud cover; a day is unavailable when
temperature, the solar period, or both UV and cloud cover are unavailable.

Daily chlorine demand starts at `0.7 ppm`. The specified UV, temperature,
daylight, cloud, rain, and mean-wind bands adjust it, after which it is limited
to `0.4–2.8 ppm`. Chlorine production is:

```text
chlorine_production_ppm_per_hour = chlorinator_output_gh / pool_volume_m3
```

The assumed free chlorine starts and ends at the configured target, so only the
estimated daily loss is replaced. The target is not added to demand:

```text
chlorination_hours = estimated_chlorine_demand_ppm / chlorine_production_ppm_per_hour
recommended_pump_hours = min(24, chlorination_hours)
```

The final state is rounded to one decimal place. There is deliberately no
turnover or circulation minimum: recommended pump hours are exactly the required
chlorination hours, capped only at 24 hours. `runtime_limited` identifies days
where the uncapped result exceeds 24 hours.

Hydraulic values are attributes only:

```text
effective_flow_m3h = pump_nominal_flow_m3h * hydraulic_efficiency_factor
estimated_circulated_volume_m3 = effective_flow_m3h * recommended_pump_hours
estimated_turnovers = estimated_circulated_volume_m3 / pool_volume_m3
```

Changing nominal flow or hydraulic efficiency changes these diagnostics but can
never increase or reduce `recommended_pump_hours`.

## 💳 MeteoBlue API credits

Free API tier provides 10mil credits for 1 year. Each request costs certain
amount of credits. The cost of API calls used by this integration are:

API package | Credits per request
-- | --
`basic-day` | 4000 credits/request
`basic-1h` | 8000 credits/request
`clouds-1h` | Optional add-on for hourly forecast requests
`wind-1h` | Optional add-on for hourly forecast requests

Hourly forecasts always request `basic-1h`. If **Additional hourly clouds and
wind data** is enabled, the integration requests `basic-1h_clouds-1h_wind-1h`
in one Forecast API call so Home Assistant can receive hourly temperature,
humidity, wind speed, wind gusts, precipitation, precipitation probability, and
cloud coverage. This option is required for lawn-irrigation and pool-control
data. Use the credits sensor and the MeteoBlue account dashboard to
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
- MeteoBlue [Account API documentation](https://docs.meteoblue.com/en/weather-apis/further-apis/account-api).
- [Issue tracker](https://github.com/n4rs/HA-MeteoBlue-Pool-and-Lawn/issues).

## 📄 License and attribution

This repository uses a composite license. Original upstream code remains under
its original Apache 2.0/MIT terms. HomeAssistant Pool and Lawn modifications and
additions are Copyright 2026 n4rs. All rights reserved. See [LICENSE](LICENSE)
and [NOTICE](NOTICE) for details.
