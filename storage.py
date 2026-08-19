"""Persistence and optional CSV logging."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import tempfile

import config


STATE_VERSION = 1


def load_state(path=None):
    path = Path(path or config.STATE_FILE)
    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError(f"State file {path} does not contain a JSON object")

    try:
        version = int(data["state_version"])
    except (KeyError, TypeError, ValueError):
        version = None
    if version is not None and version > STATE_VERSION:
        raise ValueError(
            f"State file {path} has version {version}, but this release only supports up to {STATE_VERSION}"
        )
    return data


def save_state(state, path=None):
    path = Path(path or config.STATE_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    state = dict(state)
    state["state_version"] = STATE_VERSION

    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=str(path.parent), delete=False
    ) as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        temp_name = handle.name

    try:
        Path(temp_name).replace(path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    # Best-effort directory fsync so the rename is visible after power loss.
    # os.O_DIRECTORY is Linux-only; fall back to 0 on platforms that lack it.
    o_directory_flag = getattr(os, "O_DIRECTORY", 0)
    try:
        dir_fd = os.open(str(path.parent), os.O_RDONLY | o_directory_flag)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass


def _rotate_sensor_log_if_needed(path):
    """Keep the CSV log bounded: rotate to <name>.1 once it exceeds the cap."""
    try:
        if path.stat().st_size < config.SENSOR_LOG_MAX_BYTES:
            return
    except OSError:
        return
    try:
        path.replace(path.with_name(path.name + ".1"))
    except OSError:
        pass


def append_sensor_log(environment, tank_identity, fish_count, path=None):
    path = Path(path or config.SENSOR_LOG_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    _rotate_sensor_log_if_needed(path)

    with path.open("a", encoding="utf-8", newline="") as handle:
        should_write_header = handle.tell() == 0
        writer = csv.writer(handle)
        if should_write_header:
            writer.writerow(
                [
                    "day",
                    "hour",
                    "raw_temp_c",
                    "corrected_temp_c",
                    "raw_humidity",
                    "corrected_humidity",
                    "pressure_hpa",
                    "pressure_trend",
                    "pressure_delta_hpa",
                    "event",
                    "tank_identity",
                    "fish_count",
                ]
            )
        writer.writerow(
            [
                environment.day,
                environment.hour,
                f"{environment.raw_temp:.2f}",
                f"{environment.corrected_temp:.2f}",
                f"{environment.raw_humidity:.2f}",
                f"{environment.corrected_humidity:.2f}",
                f"{environment.pressure:.2f}",
                environment.pressure_trend,
                f"{environment.pressure_delta:.2f}",
                environment.event,
                tank_identity,
                fish_count,
            ]
        )
