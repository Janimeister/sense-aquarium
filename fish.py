"""Fish, egg, and species helpers for the generative aquarium."""

from __future__ import annotations

from dataclasses import dataclass
import random
import uuid

import config
from config import clamp, clamp_int


PERSONALITIES = ["shy", "curious", "chaotic", "sleepy", "social"]
PATTERNS = ["plain", "striped", "glowing", "spotted", "zigzag"]
SIZES = ["small", "medium", "large"]

# Single allowed speed range for creation, persistence, and mutation.
SPEED_MIN = 0.25
SPEED_MAX = 2.25


# Species profiles keep the tiny ecosystem readable: environmental triggers
# select a species, while mutation nudges its traits over time.
SPECIES_PROFILES = {
    "Frostfin": {
        "colors": [[40, 150, 255], [50, 210, 240], [120, 220, 255]],
        "speed": 0.65,
        "size": "small",
        "preferred_depth": 6,
        "personality": "sleepy",
        "pattern": "striped",
    },
    "Sunscale": {
        "colors": [[255, 210, 50], [255, 150, 35], [240, 230, 95]],
        "speed": 1.35,
        "size": "medium",
        "preferred_depth": 3,
        "personality": "curious",
        "pattern": "plain",
    },
    "Emberfish": {
        "colors": [[255, 55, 20], [255, 110, 25], [210, 35, 20]],
        "speed": 1.55,
        "size": "small",
        "preferred_depth": 4,
        "personality": "chaotic",
        "pattern": "zigzag",
    },
    "Mossfin": {
        "colors": [[30, 170, 65], [70, 210, 90], [35, 120, 55]],
        "speed": 0.85,
        "size": "small",
        "preferred_depth": 5,
        "personality": "shy",
        "pattern": "spotted",
    },
    "Bubblemouth": {
        "colors": [[120, 230, 210], [80, 210, 180], [180, 240, 230]],
        "speed": 0.95,
        "size": "small",
        "preferred_depth": 4,
        "personality": "social",
        "pattern": "plain",
    },
    "Abyssfish": {
        "colors": [[40, 20, 120], [25, 45, 140], [70, 30, 120]],
        "speed": 0.8,
        "size": "medium",
        "preferred_depth": 7,
        "personality": "shy",
        "pattern": "glowing",
    },
    "Lanternfish": {
        "colors": [[60, 110, 255], [255, 230, 90], [80, 210, 255]],
        "speed": 1.0,
        "size": "small",
        "preferred_depth": 6,
        "personality": "curious",
        "pattern": "glowing",
    },
    "Stormtail": {
        "colors": [[110, 70, 255], [80, 170, 255], [190, 190, 255]],
        "speed": 1.6,
        "size": "small",
        "preferred_depth": 4,
        "personality": "chaotic",
        "pattern": "zigzag",
    },
    "Glassfin": {
        "colors": [[180, 230, 255], [220, 245, 255], [160, 210, 235]],
        "speed": 0.9,
        "size": "small",
        "preferred_depth": 3,
        "personality": "sleepy",
        "pattern": "plain",
    },
    "Crystal Ray": {
        "colors": [[160, 235, 255], [230, 250, 255], [110, 210, 255]],
        "speed": 0.55,
        "size": "large",
        "preferred_depth": 5,
        "personality": "social",
        "pattern": "striped",
    },
    "Thunder Fry": {
        "colors": [[180, 180, 255], [255, 255, 120], [80, 210, 255]],
        "speed": 1.8,
        "size": "small",
        "preferred_depth": 4,
        "personality": "chaotic",
        "pattern": "zigzag",
    },
    "Abyss Elder": {
        "colors": [[25, 10, 80], [80, 60, 180], [120, 180, 255]],
        "speed": 0.45,
        "size": "large",
        "preferred_depth": 7,
        "personality": "sleepy",
        "pattern": "glowing",
    },
}


@dataclass
class Fish:
    id: str
    x: int
    y: int
    color: list[int]
    species: str
    age_days: int
    energy: float
    speed: float
    size: str
    personality: str
    pattern: str
    mutation_level: int
    preferred_depth: int
    alive: bool
    dx: int
    dy: int
    nights_survived: int = 0

    def to_dict(self):
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "color": self.color,
            "species": self.species,
            "age_days": self.age_days,
            "energy": round(self.energy, 2),
            "speed": round(self.speed, 2),
            "size": self.size,
            "personality": self.personality,
            "pattern": self.pattern,
            "mutation_level": self.mutation_level,
            "preferred_depth": self.preferred_depth,
            "alive": self.alive,
            "dx": self.dx,
            "dy": self.dy,
            "nights_survived": self.nights_survived,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            id=str(data.get("id") or uuid.uuid4()),
            x=int(clamp(data.get("x", random.randrange(8)), 0, 7)),
            y=int(clamp(data.get("y", random.randrange(8)), 0, 7)),
            color=_parse_color(data.get("color", [80, 180, 255])),
            species=data.get("species", "Glassfin"),
            age_days=int(data.get("age_days", 0)),
            energy=float(clamp(data.get("energy", 75.0), 0.0, 120.0)),
            speed=float(clamp(data.get("speed", 1.0), SPEED_MIN, SPEED_MAX)),
            size=data.get("size", "small") if data.get("size") in SIZES else "small",
            personality=data.get("personality", "curious")
            if data.get("personality") in PERSONALITIES
            else "curious",
            pattern=data.get("pattern", "plain") if data.get("pattern") in PATTERNS else "plain",
            mutation_level=int(clamp(data.get("mutation_level", 0), 0, 99)),
            preferred_depth=int(clamp(data.get("preferred_depth", 4), 0, 7)),
            alive=bool(data.get("alive", True)),
            dx=int(clamp(data.get("dx", random.choice([-1, 1])), -1, 1)),
            dy=int(clamp(data.get("dy", 0), -1, 1)),
            nights_survived=int(data.get("nights_survived", 0)),
        )


@dataclass
class Egg:
    id: str
    x: int
    y: int
    species_hint: str
    age_days: int = 0
    hatch_after_days: int = 2
    storm_born: bool = False
    special: bool = False

    def to_dict(self):
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "species_hint": self.species_hint,
            "age_days": self.age_days,
            "hatch_after_days": self.hatch_after_days,
            "storm_born": self.storm_born,
            "special": self.special,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            id=str(data.get("id") or uuid.uuid4()),
            x=int(clamp(data.get("x", random.randrange(8)), 0, 7)),
            y=int(clamp(data.get("y", random.randrange(8)), 0, 7)),
            species_hint=data.get("species_hint", "Glassfin"),
            age_days=int(data.get("age_days", 0)),
            hatch_after_days=int(clamp(data.get("hatch_after_days", 2), 1, 5)),
            storm_born=bool(data.get("storm_born", False)),
            special=bool(data.get("special", False)),
        )


_DEFAULT_COLOR = [80, 180, 255]


def _parse_color(raw):
    """Normalize a color value to exactly 3 clamped ints."""
    if not isinstance(raw, list) or len(raw) < 3:
        return list(_DEFAULT_COLOR)
    return [clamp_int(channel) for channel in raw[:3]]


def make_fish(species, x=None, y=None, age_days=0):
    """Create a fish from a species profile with small natural variation."""

    if species not in SPECIES_PROFILES:
        species = "Glassfin"
    profile = SPECIES_PROFILES[species]
    base_color = random.choice(profile["colors"])
    color = [clamp_int(channel + random.randint(-18, 18)) for channel in base_color]
    speed = clamp(profile["speed"] + random.uniform(-0.15, 0.15), SPEED_MIN, SPEED_MAX)

    return Fish(
        id=str(uuid.uuid4()),
        x=random.randrange(8) if x is None else int(clamp(x, 0, 7)),
        y=random.randrange(8) if y is None else int(clamp(y, 0, 7)),
        color=color,
        species=species,
        age_days=age_days,
        energy=random.uniform(60.0, 95.0),
        speed=speed,
        size=profile["size"],
        personality=profile["personality"],
        pattern=profile["pattern"],
        mutation_level=0,
        preferred_depth=profile["preferred_depth"],
        alive=True,
        dx=random.choice([-1, 1]),
        dy=random.choice([-1, 0, 1]),
    )


def make_egg(x, y, species_hint, storm_born=False, special=False):
    return Egg(
        id=str(uuid.uuid4()),
        x=int(clamp(x, 0, 7)),
        y=int(clamp(y, 0, 7)),
        species_hint=species_hint,
        hatch_after_days=random.choice([1, 2, 2, 3]),
        storm_born=storm_born,
        special=special,
    )


def choose_species_for_environment(environment):
    """Pick a species whose trigger matches the current tiny climate."""

    temp = environment.corrected_temp
    humidity = environment.corrected_humidity
    low_pressure = environment.pressure < config.LOW_PRESSURE_HPA
    high_pressure = environment.pressure > config.HIGH_PRESSURE_HPA

    if temp < config.COLD_TEMP_C and high_pressure and environment.is_morning and random.random() < 0.25:
        return "Crystal Ray"
    if environment.event == "volcanic_vent":
        return random.choice(["Emberfish", "Emberfish", "Sunscale"])
    if environment.pressure_trend == "falling":
        return random.choice(["Stormtail", "Stormtail", "Abyssfish"])
    if low_pressure and environment.is_night:
        return random.choice(["Lanternfish", "Abyssfish"])
    if low_pressure:
        return "Abyssfish"
    if high_pressure:
        return "Glassfin"
    if temp > config.HOT_TEMP_C:
        return "Emberfish"
    if temp < config.COLD_TEMP_C:
        return "Frostfin"
    if humidity > config.NORMAL_HUMIDITY and environment.is_morning:
        return "Bubblemouth"
    if humidity > config.NORMAL_HUMIDITY:
        return "Mossfin"
    if temp > config.COMFORT_TEMP_C:
        return "Sunscale"

    return random.choice(["Glassfin", "Sunscale", "Mossfin", "Frostfin"])


def mutate_color(color, environment):
    """Nudge color toward the climate that caused the mutation."""

    red, green, blue = color
    if environment.corrected_temp < config.COLD_TEMP_C:
        blue += random.randint(20, 45)
        green += random.randint(5, 25)
        red -= random.randint(5, 18)
    elif environment.corrected_temp > config.HOT_TEMP_C:
        red += random.randint(25, 55)
        green += random.randint(0, 22)
        blue -= random.randint(10, 30)
    elif environment.corrected_temp > config.COMFORT_TEMP_C:
        red += random.randint(10, 35)
        green += random.randint(5, 25)

    if environment.corrected_humidity > config.NORMAL_HUMIDITY:
        green += random.randint(15, 45)
    if environment.pressure < config.LOW_PRESSURE_HPA:
        blue += random.randint(10, 35)
        red += random.randint(0, 20)
    if environment.pressure > config.HIGH_PRESSURE_HPA:
        red += random.randint(10, 25)
        green += random.randint(10, 25)
        blue += random.randint(15, 35)

    return [clamp_int(red), clamp_int(green), clamp_int(blue)]


def maybe_mutate_fish(fish, environment):
    """Apply a small evolutionary mutation and return True when it happens.

    Evolution in this aquarium is intentionally whimsical rather than realistic:
    climate stress raises mutation chance, and the mutation expresses as visible
    color warmth/coolness, a movement trait, or a tiny preference shift.
    """

    if not fish.alive or random.random() >= environment.mutation_chance:
        return False

    fish.mutation_level += 1
    fish.color = mutate_color(fish.color, environment)

    mutation_kind = random.choice(["pattern", "speed", "depth", "personality", "size"])
    if mutation_kind == "pattern":
        fish.pattern = random.choice(PATTERNS)
    elif mutation_kind == "speed":
        delta = 0.12 if environment.corrected_temp >= config.COMFORT_TEMP_C else -0.08
        fish.speed = clamp(fish.speed + delta + random.uniform(-0.05, 0.08), SPEED_MIN, SPEED_MAX)
    elif mutation_kind == "depth":
        if environment.pressure < config.LOW_PRESSURE_HPA or environment.corrected_temp < config.COLD_TEMP_C:
            fish.preferred_depth = int(clamp(fish.preferred_depth + 1, 0, 7))
        else:
            fish.preferred_depth = int(clamp(fish.preferred_depth + random.choice([-1, 1]), 0, 7))
    elif mutation_kind == "personality":
        fish.personality = random.choice(PERSONALITIES)
    elif mutation_kind == "size" and fish.age_days > 2 and fish.size != "large":
        fish.size = "medium" if fish.size == "small" else "large"

    if fish.nights_survived >= 14 and fish.species != "Abyss Elder" and random.random() < 0.2:
        elder = SPECIES_PROFILES["Abyss Elder"]
        fish.species = "Abyss Elder"
        fish.size = "large"
        fish.pattern = "glowing"
        fish.speed = elder["speed"]
        fish.preferred_depth = elder["preferred_depth"]
        fish.color = random.choice(elder["colors"]).copy()

    return True
