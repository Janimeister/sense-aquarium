"""Sense HAT display and joystick helpers."""

from __future__ import annotations

from datetime import datetime
import math
import random
import threading
import time

import config


DISPLAY_MODES = ["aquarium", "sensor", "ecosystem", "debug"]
VIEWS = ["natural", "thermal", "genetic"]


class MockStick:
    def get_events(self):
        return []


class MockSenseHat:
    """Small development fallback for computers without Sense HAT hardware."""

    is_mock = True

    def __init__(self):
        self.stick = MockStick()
        self._started = time.monotonic()
        self._pixels = [[0, 0, 0] for _ in range(64)]

    def get_temperature(self):
        elapsed = time.monotonic() - self._started
        return 27.0 + math.sin(elapsed / 45.0) * 2.4 + random.uniform(-0.25, 0.25)

    def get_humidity(self):
        elapsed = time.monotonic() - self._started
        return 52.0 + math.sin(elapsed / 55.0) * 18.0 + random.uniform(-1.5, 1.5)

    def get_pressure(self):
        elapsed = time.monotonic() - self._started
        return 1013.0 + math.sin(elapsed / 80.0) * 7.0 + random.uniform(-0.6, 0.6)

    def set_pixels(self, pixels):
        self._pixels = pixels

    def clear(self, color=None):
        self._pixels = [color or [0, 0, 0] for _ in range(64)]
        print("Mock display cleared")

    def show_message(self, message, scroll_speed=0.06, text_colour=None, back_colour=None):
        print(f"[mock message] {message}")


def create_sense_hat(force_mock=False):
    if force_mock:
        print("Using mock Sense HAT")
        return MockSenseHat()
    try:
        from sense_hat import SenseHat

        sense = SenseHat()
        sense.low_light = True
        sense.clear()
        sense.is_mock = False
        return sense
    except Exception as exc:  # noqa: BLE001 - hardware import/init can fail in several ways.
        print(f"Sense HAT not detected ({exc}); using mock mode")
        return MockSenseHat()


class DisplayManager:
    def __init__(self, sense, brightness_index=None):
        self.sense = sense
        self.mode_index = 0
        self.view_index = 0
        self.brightness_index = (
            config.DEFAULT_BRIGHTNESS_INDEX if brightness_index is None else brightness_index
        )
        self._last_message_at = 0.0
        self.exit_requested = False
        self.last_interaction_at = time.monotonic()
        self._middle_pressed_at = None
        self._message_thread = None

    @property
    def mode(self):
        return DISPLAY_MODES[self.mode_index]

    @property
    def view(self):
        return VIEWS[self.view_index]

    def handle_joystick(self, aquarium):
        try:
            events = self.sense.stick.get_events()
        except AttributeError:
            return

        for event in events:
            direction = getattr(event, "direction", "")
            action = getattr(event, "action", "")

            if direction == "middle" and action == "released":
                # A short press cycles display mode on release, so holding to
                # exit does not also flip the mode.
                if (
                    self._middle_pressed_at is not None
                    and time.monotonic() - self._middle_pressed_at < 2.0
                ):
                    self.mode_index = (self.mode_index + 1) % len(DISPLAY_MODES)
                    self._last_message_at = 0.0
                self._middle_pressed_at = None
                self.last_interaction_at = time.monotonic()
                continue

            if action not in {"pressed", "held"}:
                continue
            self.last_interaction_at = time.monotonic()

            if direction == "middle" and action == "pressed":
                self._middle_pressed_at = time.monotonic()
            elif direction == "up":
                self.brightness_index = min(self.brightness_index + 1, len(config.BRIGHTNESS_STEPS) - 1)
            elif direction == "down":
                self.brightness_index = max(self.brightness_index - 1, 0)
            elif direction == "left":
                self.view_index = (self.view_index - 1) % len(VIEWS)
            elif direction == "right":
                self.view_index = (self.view_index + 1) % len(VIEWS)

        if self._middle_pressed_at is not None and time.monotonic() - self._middle_pressed_at >= 2.0:
            self.exit_requested = True

        if self.exit_requested:
            aquarium.lightning_frames = 0

    def render(self, aquarium, environment, now=None):
        now = now or datetime.now()
        if self.mode == "aquarium":
            if self._message_scrolling():
                return
            pixels = render_aquarium(aquarium, environment, self.view)
            self.sense.set_pixels(self._scale_pixels(pixels))
            return

        self._render_message_mode(aquarium, environment, now)

    def clear(self):
        thread = self._message_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=5.0)
        self.sense.clear([0, 0, 0])

    def _message_scrolling(self):
        return self._message_thread is not None and self._message_thread.is_alive()

    def _render_message_mode(self, aquarium, environment, now):
        if self._message_scrolling():
            return
        current_time = time.monotonic()
        if current_time - self._last_message_at < 7.0:
            self.sense.set_pixels(self._scale_pixels(render_status_icon(environment, self.mode)))
            return

        self._last_message_at = current_time
        if self.mode == "sensor":
            message = (
                f"T {environment.corrected_temp:.1f}C "
                f"H {environment.corrected_humidity:.0f}% "
                f"P {environment.pressure:.0f} {environment.pressure_trend}"
            )
        elif self.mode == "ecosystem":
            message = (
                f"{environment.event} {len(aquarium.alive_fish)} fish "
                f"{aquarium.dominant_species} {aquarium.tank_identity}"
            )
        else:
            message = (
                f"rawT {environment.raw_temp:.1f} off {config.TEMP_OFFSET_C:.1f} "
                f"rawH {environment.raw_humidity:.0f} off {config.HUMIDITY_OFFSET:.1f}"
            )

        # Scroll in a background thread so sensor reads, saves, and joystick
        # handling keep running while text moves across the matrix. Other LED
        # writes are suppressed until the scroll finishes.
        self._message_thread = threading.Thread(
            target=self._show_message_safe,
            args=(message,),
            daemon=True,
        )
        self._message_thread.start()

    def _show_message_safe(self, message):
        try:
            self.sense.show_message(
                message,
                scroll_speed=0.055,
                text_colour=self._scale_color([120, 220, 255]),
                back_colour=[0, 0, 0],
            )
        except Exception as exc:  # noqa: BLE001 - keep the loop alive on display errors.
            print(f"Message scroll failed ({exc})")

    def _brightness_scale(self):
        if time.monotonic() - self.last_interaction_at > config.SCREENSAVER_AFTER_SECONDS:
            return config.BRIGHTNESS_STEPS[config.SCREENSAVER_BRIGHTNESS_INDEX]
        return config.BRIGHTNESS_STEPS[self.brightness_index]

    def _scale_color(self, color):
        scale = self._brightness_scale()
        return [config.clamp_int(channel * scale) for channel in color]

    def _scale_pixels(self, pixels):
        return [self._scale_color(pixel) for pixel in pixels]


def render_aquarium(aquarium, environment, view):
    pixels = [environment.background_color.copy() for _ in range(64)]

    for x, y in aquarium.algae:
        _set(pixels, x, y, [0, 55 + random.randint(0, 25), 18])

    for x, y in aquarium.food:
        _blend_set(pixels, x, y, [35, 120, 35], 0.85)

    for x, y in aquarium.bubbles:
        _blend_set(pixels, x, y, [130, 210, 255], 0.65)

    for egg in aquarium.eggs:
        _blend_set(pixels, egg.x, egg.y, [95, 80, 35], 0.65)

    for fish in aquarium.alive_fish:
        color = _fish_color(fish, environment, view)
        _set(pixels, fish.x, fish.y, color)
        if fish.size == "large":
            tail_x = int(config.clamp(fish.x - fish.dx, 0, 7))
            tail_y = int(config.clamp(fish.y - fish.dy, 0, 7))
            _blend_set(pixels, tail_x, tail_y, color, 0.48)
        elif fish.species == "Stormtail" and environment.pressure_trend == "falling":
            tail_x = int(config.clamp(fish.x - fish.dx, 0, 7))
            tail_y = int(config.clamp(fish.y - fish.dy, 0, 7))
            _blend_set(pixels, tail_x, tail_y, [80, 80, 180], 0.45)

    if environment.event in {"plankton_bloom", "breeding_bloom"}:
        for _ in range(2):
            _blend_set(pixels, random.randrange(8), random.randrange(8), [60, 180, 70], 0.45)
    if environment.event == "volcanic_vent":
        for x in random.sample(range(8), k=2):
            _blend_set(pixels, x, 7, [180, 35, 5], 0.70)
    if aquarium.lightning_frames > 0:
        flash = [220, 220, 255] if environment.event != "deep_storm" else [170, 90, 255]
        for y in range(8):
            x = (y + random.choice([0, 1, 2])) % 8
            _blend_set(pixels, x, y, flash, 0.90)

    return pixels


def render_status_icon(environment, mode):
    pixels = [environment.background_color.copy() for _ in range(64)]
    if mode == "sensor":
        height = int(config.clamp((environment.corrected_temp - 10.0) / 25.0 * 8.0, 1, 8))
        color = [180, 50, 30] if environment.corrected_temp >= config.HOT_TEMP_C else [60, 160, 255]
        for y in range(7, 7 - height, -1):
            _set(pixels, 0, y, color)
        humidity_width = int(config.clamp(environment.corrected_humidity / 100.0 * 6.0, 1, 6))
        for x in range(2, 2 + humidity_width):
            _set(pixels, x, 6, [30, 120, 180])
    elif mode == "ecosystem":
        for x in range(8):
            _set(pixels, x, 7, [0, 65, 25])
        for x in [2, 3, 4, 5]:
            _set(pixels, x, 3, [90, 180, 255])
    else:
        for i in range(8):
            _set(pixels, i, i, [120, 40, 180])
            _set(pixels, 7 - i, i, [35, 160, 190])
    return pixels


def _fish_color(fish, environment, view):
    color = fish.color.copy()
    if view == "thermal":
        warmth = config.clamp((environment.corrected_temp - 12.0) / 20.0, 0.0, 1.0)
        color = [config.clamp_int(60 + warmth * 180), config.clamp_int(80 + fish.energy), config.clamp_int(220 - warmth * 140)]
    elif view == "genetic":
        color = [
            config.clamp_int(40 + fish.mutation_level * 18),
            config.clamp_int(80 + fish.age_days * 4),
            config.clamp_int(80 + fish.energy),
        ]

    if fish.pattern == "glowing" or fish.species in {"Lanternfish", "Abyss Elder"}:
        bonus = 1.0 + environment.glow_bonus
        color = [config.clamp_int(channel * bonus + 25) for channel in color]
    elif fish.pattern == "striped" and (fish.x + fish.y) % 2 == 0:
        color = [config.clamp_int(channel * 0.72) for channel in color]
    elif fish.pattern == "spotted" and random.random() < 0.35:
        color = [config.clamp_int(channel + 30) for channel in color]
    elif fish.pattern == "zigzag" and random.random() < 0.25:
        color = [config.clamp_int(color[0] + 35), color[1], config.clamp_int(color[2] + 35)]

    if environment.is_night and fish.pattern != "glowing":
        color = [config.clamp_int(channel * 0.68) for channel in color]
    return color


def _index(x, y):
    return int(y) * 8 + int(x)


def _set(pixels, x, y, color):
    if 0 <= x < 8 and 0 <= y < 8:
        pixels[_index(x, y)] = [config.clamp_int(channel) for channel in color]


def _blend_set(pixels, x, y, color, alpha):
    if not 0 <= x < 8 or not 0 <= y < 8:
        return
    index = _index(x, y)
    base = pixels[index]
    pixels[index] = [
        config.clamp_int(base[channel] * (1.0 - alpha) + color[channel] * alpha)
        for channel in range(3)
    ]
