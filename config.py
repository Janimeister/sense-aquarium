"""Configuration for the 8x8 Generative Aquarium."""

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

STATE_FILE = BASE_DIR / "aquarium_state.json"
SENSOR_LOG_FILE = BASE_DIR / "sensor_log.csv"

# Sense HAT temperature is often warmed by the Raspberry Pi below it.
# These values are intentionally simple module constants so they can be edited
# without touching the simulation code.
TEMP_OFFSET_C = 7.0
HUMIDITY_OFFSET = 0.0

# Runtime cadence.
FRAME_INTERVAL_SECONDS = 0.35
SENSOR_INTERVAL_SECONDS = 20.0
EVOLUTION_INTERVAL_SECONDS = 45.0
SAVE_INTERVAL_SECONDS = 180.0
CONSOLE_INTERVAL_SECONDS = 12.0

# Tank population limits.
MIN_STARTING_FISH = 4
MAX_FISH = 11
MAX_EGGS = 8
MAX_FOOD = 16
MAX_ALGAE = 16
MAX_BUBBLES = 8

# Environmental thresholds.
COLD_TEMP_C = 18.0
COMFORT_TEMP_C = 23.0
HOT_TEMP_C = 28.0
DRY_HUMIDITY = 35.0
NORMAL_HUMIDITY = 60.0
HUMID_HUMIDITY = 75.0
LOW_PRESSURE_HPA = 1004.0
HIGH_PRESSURE_HPA = 1022.0
PRESSURE_TREND_MINUTES = 30
PRESSURE_TREND_TOLERANCE_MINUTES = 5
PRESSURE_TREND_THRESHOLD_HPA = 1.0
PRESSURE_HISTORY_HOURS = 48

# LED brightness scaling. Values are deliberately modest to reduce heat and
# eye strain on a Sense HAT mounted directly above the Raspberry Pi.
BRIGHTNESS_STEPS = [0.16, 0.25, 0.38, 0.55, 0.72]
DEFAULT_BRIGHTNESS_INDEX = 2
SCREENSAVER_AFTER_SECONDS = 600.0
SCREENSAVER_BRIGHTNESS_INDEX = 0

# Optional logging.
LOG_SENSOR_CSV = True


def clamp(value, lower, upper):
    """Return value constrained to the inclusive range lower..upper."""

    return max(lower, min(upper, value))


def clamp_int(value, lower=0, upper=255):
    """Clamp and convert a color channel to an integer."""

    return int(clamp(round(value), lower, upper))
