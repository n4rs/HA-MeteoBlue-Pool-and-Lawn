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
"""Constants for Pool and Lawn."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "pool_and_lawn"
ATTRIBUTION = "Data provided by https://meteoblue.com/"

CONF_LOCATION_MODE = "location_mode"
LOCATION_MODE_AUTO = "auto"
LOCATION_MODE_CUSTOM = "custom"

CONF_FORECAST_TYPE = "forecast_type"
FORECAST_TYPE_DAILY = "daily"
FORECAST_TYPE_HOURLY = "hourly"

CONF_FORECAST_UPDATE_INTERVAL = "forecast_update_interval"

CONF_ENABLE_FORECAST = "enable_forecast"
CONF_ENABLE_HOURLY_CLOUDS_AND_WIND = "enable_hourly_clouds_and_wind"
CONF_ENABLE_POOL = "enable_pool"
CONF_POOL_VOLUME = "pool_volume"
CONF_POOL_PUMP_CAPACITY = "pool_pump_capacity"
CONF_POOL_CHLORINATOR_CAPACITY = "pool_chlorinator_capacity"

SUBENTRY_TYPE_FORECAST_LOCATION = "forecast_location"

# Mapping of MeteoBlue pictograms to Home assistant conditions
#
# MeteoBlue pictograms docs: https://docs.meteoblue.com/en/meteo/variables/pictograms
# Note that there are two sets of pictogram codes, for daily and hourly forecast.
#
# HA conditions docs: https://developers.home-assistant.io/docs/core/entity/weather/#conditions
#
PICTOCODE_DAILY_TO_CONDITION: dict[int, str] = {
    1: "sunny",
    2: "sunny",
    3: "partlycloudy",
    4: "cloudy",
    5: "fog",
    6: "rainy",
    7: "rainy",
    8: "lightning-rainy",
    9: "snowy",
    10: "snowy",
    11: "snowy-rainy",
    12: "rainy",
    13: "snowy",
    14: "rainy",
    15: "snowy",
    16: "rainy",
    17: "snowy",
    20: "cloudy",
    21: "lightning",
    22: "lightning",
    23: "lightning-rainy",
    24: "lightning-rainy",
    25: "lightning-rainy",
}

PICTOCODE_HOURLY_TO_CONDITION: dict[int, str] = {
    1: "sunny",
    2: "sunny",
    3: "sunny",
    4: "partlycloudy",
    5: "partlycloudy",
    6: "partlycloudy",
    7: "partlycloudy",
    8: "partlycloudy",
    9: "partlycloudy",
    10: "lightning",
    11: "lightning",
    12: "lightning",
    13: "sunny",
    14: "sunny",
    15: "sunny",
    16: "fog",
    17: "fog",
    18: "fog",
    19: "cloudy",
    20: "cloudy",
    21: "cloudy",
    22: "cloudy",
    23: "rainy",
    24: "snowy",
    25: "pouring",
    26: "snowy",
    27: "lightning-rainy",
    28: "lightning-rainy",
    29: "snowy",
    30: "lightning-rainy",
    31: "rainy",
    32: "snowy",
    33: "rainy",
    34: "snowy",
    35: "snowy-rainy",
}
