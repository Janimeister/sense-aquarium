"""Sense HAT sensor reading and environmental rule mapping."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import math

import config


@dataclass
class Environment:
    raw_temp: float
    corrected_temp: float
    raw_humidity: float
    corrected_humidity: float
    pressure: float
    pressure_trend: str
    pressure_delta: float
    hour: int
    day: str
    event: str
    speed_modifier: float
    mutation_chance: float
    food_spawn_chance: float
    breeding_chance: float
    current_strength: int
    glow_bonus: float
    algae_growth: float
    background_color: list[int]

    @property
    def is_night(self):
        return self.hour >= 22 or self.hour < 6

    @property
    def is_morning(self):
        return 6 <= self.hour < 9

    @property
    def is_day(self):
        return 9 <= self.hour < 18

    @property
    def is_evening(self):
        return 18 <= self.hour < 22


class EnvironmentReader:
    """Read sensors and convert them into aquarium-specific conditions."""

    def __init__(self, sense, temp_offset_c=None, humidity_offset=None):
        self.sense = sense
        self.temp_offset_c = config.TEMP_OFFSET_C if temp_offset_c is None else temp_offset_c
        self.humidity_offset = (
            config.HUMIDITY_OFFSET if humidity_offset is None else humidity_offset
        )

    def read(self, pressure_history, now=None):
        now = now or datetime.now()
        raw_temp = float(self.sense.get_temperature())
        raw_humidity = float(self.sense.get_humidity())
        pressure = float(self.sense.get_pressure())

        pressure_history.append({"time": now.isoformat(timespec="seconds"), "pressure": pressure})
        prune_pressure_history(pressure_history, now)

        corrected_temp = raw_temp - self.temp_offset_c
        corrected_humidity = config.clamp(raw_humidity + self.humidity_offset, 0.0, 100.0)
        pressure_trend, pressure_delta = calculate_pressure_trend(pressure_history, pressure, now)

        return build_environment(
            raw_temp=raw_temp,
            corrected_temp=corrected_temp,
            raw_humidity=raw_humidity,
            corrected_humidity=corrected_humidity,
            pressure=pressure,
            pressure_trend=pressure_trend,
            pressure_delta=pressure_delta,
            now=now,
        )


def calculate_pressure_trend(pressure_history, current_pressure, now):
    """Compare pressure with a reading from roughly 30 minutes ago."""

    target = now - timedelta(minutes=config.PRESSURE_TREND_MINUTES)
    max_distance_seconds = timedelta(minutes=config.PRESSURE_TREND_TOLERANCE_MINUTES).total_seconds()
    best = None
    best_distance = None

    for item in pressure_history:
        try:
            item_time = _safe_time(item["time"])
            pressure = float(item["pressure"])
        except (KeyError, TypeError, ValueError):
            continue
        if item_time is None:
            continue

        distance = abs((item_time - target).total_seconds())
        if best is None or distance < best_distance:
            best = pressure
            best_distance = distance

    if best is None or best_distance is None or best_distance > max_distance_seconds:
        return "stable", 0.0

    delta = current_pressure - best
    if delta <= -config.PRESSURE_TREND_THRESHOLD_HPA:
        return "falling", delta
    if delta >= config.PRESSURE_TREND_THRESHOLD_HPA:
        return "rising", delta
    return "stable", delta


def prune_pressure_history(pressure_history, now):
    cutoff = now - timedelta(hours=config.PRESSURE_HISTORY_HOURS)
    kept = []
    for item in pressure_history:
        if not isinstance(item, dict):
            continue
        item_time = _safe_time(item.get("time"))
        if item_time is not None and item_time >= cutoff:
            kept.append(item)
    pressure_history[:] = kept


def build_environment(
    raw_temp,
    corrected_temp,
    raw_humidity,
    corrected_humidity,
    pressure,
    pressure_trend,
    pressure_delta,
    now,
):
    """Map room climate into aquarium behavior knobs and a named event."""

    hour = now.hour
    is_nighttime = hour >= 22 or hour < 6
    is_morning = 6 <= hour < 9
    is_daytime = 9 <= hour < 18
    is_evening = 18 <= hour < 22

    speed_modifier = 1.0
    mutation_chance = 0.010
    food_spawn_chance = 0.08
    breeding_chance = 0.018
    current_strength = 0
    glow_bonus = 0.0
    algae_growth = 0.015
    background_color = [0, 4, 14]
    event = "balanced_current"

    cold = corrected_temp < config.COLD_TEMP_C
    warm = config.COMFORT_TEMP_C <= corrected_temp < config.HOT_TEMP_C
    hot = corrected_temp >= config.HOT_TEMP_C
    dry = corrected_humidity < config.DRY_HUMIDITY
    humid = config.NORMAL_HUMIDITY <= corrected_humidity < config.HUMID_HUMIDITY
    very_humid = corrected_humidity >= config.HUMID_HUMIDITY
    low_pressure = pressure < config.LOW_PRESSURE_HPA
    high_pressure = pressure > config.HIGH_PRESSURE_HPA

    if cold:
        speed_modifier *= 0.65
        mutation_chance += 0.006
        background_color = [0, 7, 20]
        event = "cold_drift"
    elif warm:
        speed_modifier *= 1.18
        breeding_chance += 0.012
        background_color = [0, 8, 18]
        event = "tropical_bloom"
    elif hot:
        speed_modifier *= 1.35
        mutation_chance += 0.018
        breeding_chance += 0.006
        background_color = [8, 2, 10]
        event = "heat_stress"

    if dry:
        food_spawn_chance *= 0.45
        speed_modifier *= 0.9
        event = "dry_tank"
    elif humid:
        food_spawn_chance += 0.06
        breeding_chance += 0.012
        algae_growth += 0.025
        event = "lush_water"
    elif very_humid:
        food_spawn_chance += 0.08
        breeding_chance += 0.018
        mutation_chance += 0.010
        algae_growth += 0.050
        glow_bonus += 0.12
        event = "swamp_bloom"

    if high_pressure:
        speed_modifier *= 0.92
        mutation_chance *= 0.75
        background_color = [2, 10, 20]
        event = "crystal_clarity"
    elif low_pressure:
        mutation_chance += 0.008
        glow_bonus += 0.15
        background_color = [2, 1, 12]
        event = "abyss_zone"

    if pressure_trend == "falling":
        speed_modifier *= 1.18
        mutation_chance += 0.016
        current_strength = -1 if math.floor(now.timestamp()) % 2 else 1
        glow_bonus += 0.12
        event = "storm_current"
    elif pressure_trend == "rising":
        breeding_chance += 0.006
        food_spawn_chance += 0.025
        event = "clearing_water"

    if is_morning:
        food_spawn_chance += 0.10
        breeding_chance += 0.004
    elif is_daytime:
        speed_modifier *= 1.06
    elif is_evening:
        breeding_chance += 0.020
        background_color = [4, 4, 14]
    elif is_nighttime:
        speed_modifier *= 0.72
        glow_bonus += 0.25
        food_spawn_chance *= 0.55
        background_color = [0, 1, 8]

    # Combined events intentionally override single-condition events. These are
    # the ecosystem's evolution pressure: good combinations breed, stressful
    # combinations mutate, and pressure swings make odd species more likely.
    if warm and (humid or very_humid):
        event = "plankton_bloom"
        food_spawn_chance += 0.12
        breeding_chance += 0.020
        algae_growth += 0.025
        background_color = [0, 10, 14]
    if hot and dry:
        event = "evaporation_stress"
        speed_modifier *= 0.72
        mutation_chance += 0.018
        food_spawn_chance *= 0.45
        background_color = [12, 1, 5]
    if cold and high_pressure:
        event = "crystal_freeze"
        speed_modifier *= 0.70
        mutation_chance *= 0.75
        background_color = [4, 12, 22]
    if low_pressure and (humid or very_humid):
        event = "deep_storm"
        current_strength = current_strength or 1
        mutation_chance += 0.018
        glow_bonus += 0.20
        background_color = [4, 0, 16]
    if pressure_trend == "falling" and is_nighttime:
        event = "abyss_migration"
        current_strength = current_strength or -1
        glow_bonus += 0.28
        mutation_chance += 0.012
        background_color = [0, 0, 10]
    if pressure_trend == "rising" and is_morning:
        event = "clear_sunrise"
        breeding_chance += 0.010
        food_spawn_chance += 0.08
        background_color = [8, 10, 12]
    if hot and low_pressure:
        event = "volcanic_vent"
        mutation_chance += 0.022
        glow_bonus += 0.10
        background_color = [12, 1, 4]
    if (humid or very_humid) and is_evening:
        event = "breeding_bloom"
        breeding_chance += 0.035
        algae_growth += 0.030
    if high_pressure and is_daytime:
        event = "crystal_clarity"
        mutation_chance *= 0.70
        speed_modifier *= 0.85
        background_color = [2, 12, 20]

    return Environment(
        raw_temp=raw_temp,
        corrected_temp=corrected_temp,
        raw_humidity=raw_humidity,
        corrected_humidity=corrected_humidity,
        pressure=pressure,
        pressure_trend=pressure_trend,
        pressure_delta=pressure_delta,
        hour=hour,
        day=now.date().isoformat(),
        event=event,
        speed_modifier=config.clamp(speed_modifier, 0.25, 2.3),
        mutation_chance=config.clamp(mutation_chance, 0.0, 0.12),
        food_spawn_chance=config.clamp(food_spawn_chance, 0.0, 0.45),
        breeding_chance=config.clamp(breeding_chance, 0.0, 0.18),
        current_strength=int(config.clamp(current_strength, -1, 1)),
        glow_bonus=config.clamp(glow_bonus, 0.0, 0.8),
        algae_growth=config.clamp(algae_growth, 0.0, 0.18),
        background_color=background_color,
    )


def _safe_time(value):
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed
