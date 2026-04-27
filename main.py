"""Main loop for the 8x8 Generative Aquarium."""

from __future__ import annotations

import argparse
from datetime import datetime
import random
import time

from aquarium import Aquarium
import config
from display import DisplayManager, create_sense_hat
from environment import EnvironmentReader
import storage


def parse_args():
    parser = argparse.ArgumentParser(description="8x8 Generative Aquarium for Raspberry Pi Sense HAT")
    parser.add_argument("--mock", action="store_true", help="force mock sensors and console output")
    parser.add_argument("--once", action="store_true", help="run a few mock-friendly ticks and exit")
    parser.add_argument("--state", default=str(config.STATE_FILE), help="path to JSON state file")
    parser.add_argument("--no-log", action="store_true", help="disable CSV sensor logging")
    parser.add_argument("--temp-offset", type=float, default=config.TEMP_OFFSET_C, help="temperature calibration offset in C")
    parser.add_argument("--humidity-offset", type=float, default=config.HUMIDITY_OFFSET, help="humidity calibration offset")
    return parser.parse_args()


def main():
    args = parse_args()
    config.TEMP_OFFSET_C = args.temp_offset
    config.HUMIDITY_OFFSET = args.humidity_offset
    random.seed()
    sense = create_sense_hat(force_mock=args.mock)
    display = DisplayManager(sense)
    reader = EnvironmentReader(
        sense,
        temp_offset_c=args.temp_offset,
        humidity_offset=args.humidity_offset,
    )

    try:
        state = storage.load_state(args.state)
    except Exception as exc:  # noqa: BLE001 - keep the aquarium alive if state is corrupt.
        print(f"Could not load state ({exc}); starting a new aquarium")
        state = None

    aquarium = Aquarium(state)
    now = datetime.now()
    try:
        environment = reader.read(aquarium.pressure_history, now)
    except Exception as exc:  # noqa: BLE001 - keep the aquarium alive on transient sensor failure at startup.
        print(f"Initial sensor read failed ({exc}); using safe defaults")
        from environment import build_environment
        environment = build_environment(
            raw_temp=config.COMFORT_TEMP_C + config.TEMP_OFFSET_C,
            corrected_temp=config.COMFORT_TEMP_C,
            raw_humidity=50.0 + config.HUMIDITY_OFFSET,
            corrected_humidity=50.0,
            pressure=1013.0, pressure_trend="stable", pressure_delta=0.0,
            now=now,
        )
    aquarium.daily_update(environment, now)

    if args.once:
        run_once(aquarium, environment, display, args)
        return

    run_forever(aquarium, reader, display, args, environment)


def run_once(aquarium, environment, display, args):
    for _ in range(3):
        aquarium.animation_tick(environment, datetime.now())
        aquarium.evolution_tick(environment, datetime.now())
        display.render(aquarium, environment, datetime.now())
    storage.save_state(aquarium.to_state(), args.state)
    print(aquarium.summary(environment))
    display.clear()


def run_forever(aquarium, reader, display, args, environment):
    start = time.monotonic()
    last_sensor = start
    last_frame = start
    last_evolution = start
    last_save = start
    last_console = start
    last_log = start

    print("8x8 Generative Aquarium is running. Hold the joystick middle button to save and exit.")
    try:
        while not display.exit_requested:
            monotonic_now = time.monotonic()
            wall_now = datetime.now()

            if monotonic_now - last_sensor >= config.SENSOR_INTERVAL_SECONDS:
                try:
                    environment = reader.read(aquarium.pressure_history, wall_now)
                    aquarium.daily_update(environment, wall_now)
                except Exception as exc:  # noqa: BLE001 - keep running on transient sensor failure.
                    print(f"Sensor read failed ({exc}); skipping daily update this cycle")
                last_sensor = monotonic_now

            display.handle_joystick(aquarium)

            if monotonic_now - last_frame >= config.FRAME_INTERVAL_SECONDS:
                aquarium.animation_tick(environment, wall_now)
                display.render(aquarium, environment, wall_now)
                last_frame = monotonic_now

            if monotonic_now - last_evolution >= config.EVOLUTION_INTERVAL_SECONDS:
                aquarium.evolution_tick(environment, wall_now)
                last_evolution = monotonic_now

            if not args.no_log and config.LOG_SENSOR_CSV and monotonic_now - last_log >= config.SENSOR_INTERVAL_SECONDS:
                storage.append_sensor_log(environment, aquarium.tank_identity, len(aquarium.alive_fish))
                last_log = monotonic_now

            if monotonic_now - last_save >= config.SAVE_INTERVAL_SECONDS:
                storage.save_state(aquarium.to_state(), args.state)
                last_save = monotonic_now

            if getattr(display.sense, "is_mock", False) and monotonic_now - last_console >= config.CONSOLE_INTERVAL_SECONDS:
                print(aquarium.summary(environment))
                last_console = monotonic_now

            time.sleep(0.04)
    except KeyboardInterrupt:
        print("Stopping aquarium")
    finally:
        try:
            storage.save_state(aquarium.to_state(), args.state)
            print(f"Saved aquarium state to {args.state}")
        except Exception as exc:  # noqa: BLE001 - best-effort save during shutdown.
            print(f"Could not save state ({exc})")
        display.clear()


if __name__ == "__main__":
    main()
