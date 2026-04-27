"""Core ecosystem simulation for the 8x8 Generative Aquarium."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import random

import config
from fish import (
    Egg,
    Fish,
    choose_species_for_environment,
    make_egg,
    make_fish,
    maybe_mutate_fish,
)


class Aquarium:
    def __init__(self, state=None):
        state = state or {}
        self.fish = [Fish.from_dict(item) for item in state.get("fish", [])]
        self.eggs = [Egg.from_dict(item) for item in state.get("eggs", [])]
        self.algae = _load_points(state.get("algae", []))
        self.pressure_history = list(state.get("pressure_history", []))
        self.climate_history = list(state.get("climate_history", []))
        self.generation_count = int(state.get("generation_count", 0))
        self.last_midnight_event_date = state.get("last_midnight_event_date")
        self.last_daily_update_date = state.get("last_daily_update_date")
        self.tank_identity = state.get("tank_identity", "Crystal Pond")
        self.dominant_species = state.get("dominant_species", "Glassfin")
        self.food = _load_points(state.get("food", []))
        self.bubbles = _load_points(state.get("bubbles", []))
        self.lightning_frames = 0

        if not self.alive_fish:
            self.seed_starting_fish()

    @property
    def alive_fish(self):
        return [fish for fish in self.fish if fish.alive]

    def seed_starting_fish(self):
        starter_species = ["Glassfin", "Sunscale", "Mossfin", "Frostfin"]
        self.fish = [make_fish(species) for species in starter_species[: config.MIN_STARTING_FISH]]
        self.generation_count = max(self.generation_count, 1)

    def to_state(self):
        return {
            "fish": [fish.to_dict() for fish in self.fish if fish.alive],
            "eggs": [egg.to_dict() for egg in self.eggs],
            "algae": [[x, y] for x, y in sorted(self.algae)],
            "pressure_history": self.pressure_history,
            "climate_history": self.climate_history[-30:],
            "generation_count": self.generation_count,
            "last_midnight_event_date": self.last_midnight_event_date,
            "last_daily_update_date": self.last_daily_update_date,
            "tank_identity": self.tank_identity,
            "dominant_species": self.dominant_species,
        }

    def animation_tick(self, environment, now=None):
        now = now or datetime.now()
        self._spawn_food(environment)
        self._grow_or_trim_algae(environment)
        self._update_bubbles(environment)
        self._move_and_feed_fish(environment)
        self._maybe_lightning(environment)
        self._maybe_midnight_event(environment, now)

    def evolution_tick(self, environment, now=None):
        now = now or datetime.now()
        self._breed(environment)
        self._mutate(environment)
        self._hatch_ready_eggs(environment, now, accelerated=False)
        self._gentle_retirement(environment)
        self._update_dominant_species()

    def daily_update(self, environment, now=None):
        now = now or datetime.now()
        today = now.date().isoformat()
        if self.last_daily_update_date is None:
            self._record_climate(environment)
            self._update_tank_identity()
            self.last_daily_update_date = today
            return
        if self.last_daily_update_date == today:
            return

        for fish in self.alive_fish:
            fish.age_days += 1
            fish.energy = config.clamp(fish.energy + 3.0, 0.0, 120.0)
            if environment.is_night or now.hour < 9:
                fish.nights_survived += 1

        for egg in self.eggs:
            egg.age_days += 1

        self._hatch_ready_eggs(environment, now, accelerated=environment.event == "clear_sunrise")
        self._record_climate(environment)
        self._update_tank_identity()
        self._evolve_dominant_trait(environment)
        self.last_daily_update_date = today

    def summary(self, environment):
        species = Counter(fish.species for fish in self.alive_fish)
        dominant = species.most_common(1)[0][0] if species else "none"
        return (
            f"{self.tank_identity} | {environment.event} | "
            f"fish={len(self.alive_fish)} eggs={len(self.eggs)} "
            f"dominant={dominant} temp={environment.corrected_temp:.1f}C "
            f"hum={environment.corrected_humidity:.0f}% p={environment.pressure:.1f}hPa "
            f"trend={environment.pressure_trend}"
        )

    def _spawn_food(self, environment):
        if len(self.food) >= config.MAX_FOOD:
            return
        chance = environment.food_spawn_chance
        if environment.is_morning:
            chance += 0.04
        if random.random() < chance:
            self.food.add((random.randrange(8), random.randrange(8)))

    def _grow_or_trim_algae(self, environment):
        if len(self.algae) < config.MAX_ALGAE and random.random() < environment.algae_growth:
            edge_positions = []
            for x in range(8):
                edge_positions.append((x, 7))
            for y in range(4, 8):
                edge_positions.append((0, y))
                edge_positions.append((7, y))
            self.algae.add(random.choice(edge_positions))

        if environment.corrected_humidity < config.DRY_HUMIDITY and self.algae and random.random() < 0.04:
            self.algae.remove(random.choice(tuple(self.algae)))

    def _update_bubbles(self, environment):
        new_bubbles = set()
        for x, y in self.bubbles:
            if y > 0 and random.random() < 0.85:
                new_bubbles.add((x, y - 1))

        self.bubbles = new_bubbles
        bubble_species = any(fish.species == "Bubblemouth" for fish in self.alive_fish)
        if bubble_species and len(self.bubbles) < config.MAX_BUBBLES and random.random() < 0.12:
            source = random.choice(self.alive_fish)
            self.bubbles.add((source.x, max(0, source.y - 1)))

    def _move_and_feed_fish(self, environment):
        occupied = {(fish.x, fish.y) for fish in self.alive_fish}
        for fish in self.alive_fish:
            self._drain_or_restore_energy(fish, environment)
            if fish.energy <= 0 and random.random() < 0.025:
                fish.alive = False
                continue

            if not self._should_move(fish, environment):
                continue

            old_position = (fish.x, fish.y)
            dx, dy = self._choose_direction(fish, environment, occupied)
            fish.dx = dx
            fish.dy = dy
            fish.x = int(config.clamp(fish.x + dx, 0, 7))
            fish.y = int(config.clamp(fish.y + dy, 0, 7))
            occupied.discard(old_position)
            occupied.add((fish.x, fish.y))

            if (fish.x, fish.y) in self.food:
                self.food.remove((fish.x, fish.y))
                fish.energy = config.clamp(fish.energy + 18.0, 0.0, 120.0)

            if (fish.x, fish.y) in self.algae and fish.species in {"Mossfin", "Bubblemouth"}:
                fish.energy = config.clamp(fish.energy + 4.0, 0.0, 120.0)

    def _drain_or_restore_energy(self, fish, environment):
        drain = 0.18 * fish.speed
        if environment.corrected_temp < config.COLD_TEMP_C:
            drain *= 0.65
        elif environment.corrected_temp >= config.HOT_TEMP_C:
            drain *= 1.65
        if environment.corrected_humidity < config.DRY_HUMIDITY and fish.size == "small":
            drain *= 0.78
        if environment.event == "evaporation_stress":
            drain *= 1.35
        if environment.is_night and fish.species not in {"Lanternfish", "Abyssfish", "Abyss Elder"}:
            drain *= 0.55
        if environment.pressure_trend == "rising" or environment.event == "clear_sunrise":
            fish.energy = config.clamp(fish.energy + 0.35, 0.0, 120.0)

        fish.energy = config.clamp(fish.energy - drain, 0.0, 120.0)

    def _should_move(self, fish, environment):
        move_chance = fish.speed * environment.speed_modifier * 0.58
        if environment.is_night and fish.species not in {"Lanternfish", "Abyssfish", "Abyss Elder"}:
            move_chance *= 0.45
        if fish.personality == "sleepy":
            move_chance *= 0.72
        elif fish.personality == "chaotic":
            move_chance *= 1.20
        return random.random() < config.clamp(move_chance, 0.05, 0.95)

    def _choose_direction(self, fish, environment, occupied):
        if fish.personality == "curious" and self.food and random.random() < 0.65:
            target_x, target_y = min(
                self.food,
                key=lambda point: abs(point[0] - fish.x) + abs(point[1] - fish.y),
            )
            dx = _sign(target_x - fish.x)
            dy = _sign(target_y - fish.y)
        elif fish.personality == "social" and len(self.alive_fish) > 1 and random.random() < 0.55:
            neighbors = [other for other in self.alive_fish if other.id != fish.id]
            target = min(neighbors, key=lambda other: abs(other.x - fish.x) + abs(other.y - fish.y))
            dx = _sign(target.x - fish.x)
            dy = _sign(target.y - fish.y)
        elif fish.personality == "shy" and occupied and random.random() < 0.55:
            crowded_x = sum(x for x, _ in occupied) / max(1, len(occupied))
            crowded_y = sum(y for _, y in occupied) / max(1, len(occupied))
            dx = _sign(fish.x - crowded_x)
            dy = _sign(fish.y - crowded_y)
        else:
            dx = fish.dx if random.random() < 0.52 else random.choice([-1, 0, 1])
            dy = random.choice([-1, 0, 1])

        target_depth = fish.preferred_depth
        if environment.corrected_temp < config.COLD_TEMP_C or environment.pressure < config.LOW_PRESSURE_HPA:
            target_depth = min(7, target_depth + 1)
        if environment.event == "abyss_migration":
            target_depth = max(0, target_depth - 1)
        if environment.pressure > config.HIGH_PRESSURE_HPA and fish.personality != "shy":
            target_depth = random.choice([2, 3, 4, 5])

        if fish.y < target_depth and random.random() < 0.55:
            dy = 1
        elif fish.y > target_depth and random.random() < 0.55:
            dy = -1

        if environment.current_strength and random.random() < 0.70:
            dx = environment.current_strength
        if environment.pressure_trend == "falling" or fish.species == "Stormtail":
            dy = random.choice([-1, 1]) if random.random() < 0.55 else dy
        if fish.personality == "chaotic":
            dx = random.choice([-1, 0, 1]) if random.random() < 0.35 else dx
            dy = random.choice([-1, 0, 1]) if random.random() < 0.35 else dy

        if dx == 0 and dy == 0:
            dx = random.choice([-1, 1])
        return dx, dy

    def _breed(self, environment):
        if len(self.alive_fish) >= config.MAX_FISH or len(self.eggs) >= config.MAX_EGGS:
            return
        adults = [fish for fish in self.alive_fish if fish.energy > 55.0 and fish.age_days >= 1]
        if len(adults) < 2:
            return

        chance = environment.breeding_chance
        if environment.is_evening:
            chance += 0.025
        if environment.event in {"plankton_bloom", "breeding_bloom", "clear_sunrise"}:
            chance += 0.035
        if random.random() >= chance:
            return

        parent_a, parent_b = random.sample(adults, 2)
        species_hint = random.choice([parent_a.species, parent_b.species, choose_species_for_environment(environment)])
        storm_born = environment.pressure_trend == "falling" or environment.event in {"storm_current", "deep_storm"}
        special = environment.event in {"deep_storm", "volcanic_vent", "crystal_freeze"}
        egg_x = round((parent_a.x + parent_b.x) / 2)
        egg_y = round((parent_a.y + parent_b.y) / 2)
        self.eggs.append(make_egg(egg_x, egg_y, species_hint, storm_born=storm_born, special=special))
        parent_a.energy = config.clamp(parent_a.energy - 10.0, 0.0, 120.0)
        parent_b.energy = config.clamp(parent_b.energy - 10.0, 0.0, 120.0)

    def _mutate(self, environment):
        for fish in self.alive_fish:
            maybe_mutate_fish(fish, environment)

    def _hatch_ready_eggs(self, environment, now, accelerated=False):
        if not self.eggs or len(self.alive_fish) >= config.MAX_FISH:
            return

        survivors = []
        for egg in self.eggs:
            ready = egg.age_days >= egg.hatch_after_days
            if accelerated and egg.age_days >= max(0, egg.hatch_after_days - 1):
                ready = True
            if environment.is_morning and random.random() < 0.08:
                ready = True
            if not ready or len(self.alive_fish) >= config.MAX_FISH:
                survivors.append(egg)
                continue

            if egg.storm_born and environment.pressure_trend == "falling":
                species = "Thunder Fry"
            elif egg.special and environment.event == "crystal_freeze":
                species = "Crystal Ray"
            elif egg.special and environment.event == "volcanic_vent":
                species = "Emberfish"
            else:
                species = egg.species_hint
            self.fish.append(make_fish(species, x=egg.x, y=egg.y))
            self.generation_count += 1

        self.eggs = survivors[: config.MAX_EGGS]

    def _gentle_retirement(self, environment):
        for fish in self.alive_fish:
            if fish.age_days < 60:
                continue
            old_age_chance = 0.0015 * max(1, fish.age_days - 59)
            if fish.energy < 12.0:
                old_age_chance *= 2.0
            if random.random() < min(old_age_chance, 0.05):
                fish.alive = False

    def _maybe_lightning(self, environment):
        if self.lightning_frames > 0:
            self.lightning_frames -= 1
            return
        if environment.event in {"storm_current", "deep_storm", "abyss_migration"} and random.random() < 0.035:
            self.lightning_frames = random.choice([1, 2])

    def _maybe_midnight_event(self, environment, now):
        if now.hour != 0 or self.last_midnight_event_date == environment.day:
            return
        self.last_midnight_event_date = environment.day
        for fish in self.alive_fish:
            if random.random() < environment.mutation_chance * 4.0:
                maybe_mutate_fish(fish, environment)
        if environment.pressure < config.LOW_PRESSURE_HPA and random.random() < 0.35:
            self.eggs.append(
                make_egg(
                    random.randrange(8),
                    random.randrange(5, 8),
                    "Lanternfish",
                    storm_born=environment.pressure_trend == "falling",
                    special=True,
                )
            )
            self.eggs = self.eggs[-config.MAX_EGGS :]

    def _record_climate(self, environment):
        self.climate_history.append(
            {
                "day": environment.day,
                "corrected_temp": round(environment.corrected_temp, 2),
                "corrected_humidity": round(environment.corrected_humidity, 2),
                "pressure": round(environment.pressure, 2),
                "pressure_trend": environment.pressure_trend,
                "pressure_delta": round(environment.pressure_delta, 2),
                "event": environment.event,
            }
        )
        self.climate_history = self.climate_history[-30:]

    def _update_tank_identity(self):
        recent = self.climate_history[-10:]
        if not recent:
            return
        warm_days = sum(1 for item in recent if item.get("corrected_temp", 0.0) >= config.COMFORT_TEMP_C)
        cold_days = sum(1 for item in recent if item.get("corrected_temp", 99.0) < config.COLD_TEMP_C)
        humid_days = sum(1 for item in recent if item.get("corrected_humidity", 0.0) >= config.NORMAL_HUMIDITY)
        low_pressure_days = sum(1 for item in recent if item.get("pressure", 9999.0) < config.LOW_PRESSURE_HPA)
        pressure_swings = sum(1 for item in recent if abs(item.get("pressure_delta", 0.0)) >= 2.0)

        if pressure_swings >= max(3, len(recent) // 2):
            self.tank_identity = "Storm Aquarium"
        elif low_pressure_days >= max(3, len(recent) // 2):
            self.tank_identity = "Abyss Zone"
        elif humid_days >= max(3, len(recent) // 2):
            self.tank_identity = "Swamp Garden"
        elif warm_days >= max(3, len(recent) // 2):
            self.tank_identity = "Tropical Reef"
        elif cold_days >= max(3, len(recent) // 2):
            self.tank_identity = "Arctic Tank"
        else:
            self.tank_identity = "Crystal Pond"

    def _evolve_dominant_trait(self, environment):
        if random.random() > 0.18 or not self.alive_fish:
            return
        species_counts = Counter(fish.species for fish in self.alive_fish)
        dominant_species = species_counts.most_common(1)[0][0]
        candidates = [fish for fish in self.alive_fish if fish.species == dominant_species]
        if not candidates:
            return

        fish = random.choice(candidates)
        maybe_mutate_fish(fish, environment)

    def _update_dominant_species(self):
        counts = Counter(fish.species for fish in self.alive_fish)
        self.dominant_species = counts.most_common(1)[0][0] if counts else "none"


def _load_points(items):
    points = set()
    for item in items:
        try:
            x, y = item
            points.add((int(config.clamp(x, 0, 7)), int(config.clamp(y, 0, 7))))
        except (TypeError, ValueError):
            continue
    return points


def _sign(value):
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0
