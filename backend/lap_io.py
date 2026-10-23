"""Read a telemetry CSV into a clean dict of numpy arrays.

Assetto Corsa does not export CSV by itself. Tools such as Content Manager,
ACTI or MoTeC i2 export laps to CSV. This parser accepts the common column
names (see ALIASES), so most exports work without changes.
"""
import io
import re

import numpy as np
import pandas as pd


class LapError(ValueError):
    pass


ALIASES = {
    "distance": ["distance_m", "distance", "dist", "lapdist", "lap_distance", "lapdistance", "pos_m"],
    "time": ["time_s", "time", "t", "laptime", "lap_time", "currenttime", "current_time", "timestamp"],
    "speed": ["speed_kmh", "speed", "speedkmh", "velocity", "speed_kph"],
    "throttle": ["throttle", "gas", "throttle_pct", "accelerator"],
    "brake": ["brake", "brake_pct", "brakepressure", "brake_pressure"],
    "steer": ["steer", "steering", "steerangle", "steer_angle", "steering_angle"],
    "gear": ["gear"],
    "glat": ["g_lat", "glat", "lateral_g", "accg_x", "acc_x", "gx", "ay"],
    "glon": ["g_lon", "glon", "longitudinal_g", "accg_z", "acc_z", "gz", "ax"],
}


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9_]", "", str(name).strip().lower().replace(" ", "_"))


def parse_lap(data: bytes, filename: str = "lap.csv") -> dict:
    try:
        df = pd.read_csv(io.BytesIO(data), sep=None, engine="python")
    except Exception as e:  # noqa: BLE001
        raise LapError(f"{filename}: could not read this file as CSV ({e}).")

    cols = {_norm(c): c for c in df.columns}
    found = {}
    for key, names in ALIASES.items():
        for n in names:
            if n in cols:
                found[key] = pd.to_numeric(df[cols[n]], errors="coerce").to_numpy(dtype=float)
                break

    if "speed" not in found:
        raise LapError(
            f"{filename}: no speed column found. Expected something like speed_kmh. "
            f"Columns seen: {', '.join(map(str, df.columns[:12]))}"
        )
    if "distance" not in found and "time" not in found:
        raise LapError(f"{filename}: need either a distance column or a time column.")

    n = len(found["speed"])
    warnings = []
    lap = {k: found.get(k) for k in ALIASES}

    mask = np.isfinite(lap["speed"])
    for k in ("distance", "time"):
        if lap[k] is not None:
            mask &= np.isfinite(lap[k])
    for k in lap:
        if lap[k] is not None:
            lap[k] = lap[k][mask]

    if lap["time"] is not None:
        t = lap["time"] - lap["time"][0]
        if t.max() > 1000:  # milliseconds
            t = t / 1000.0
        lap["time"] = t

    v_ms = np.maximum(lap["speed"], 1.0) / 3.6
    if lap["distance"] is None:
        dt = np.diff(lap["time"], prepend=lap["time"][0])
        lap["distance"] = np.cumsum(v_ms * dt)
        warnings.append("Distance was missing and was integrated from speed and time.")
    if lap["time"] is None:
        dd = np.diff(lap["distance"], prepend=lap["distance"][0])
        lap["time"] = np.cumsum(dd / v_ms)
        warnings.append("Time was missing and was integrated from speed and distance.")

    # make distance strictly increasing
    d = np.maximum.accumulate(lap["distance"])
    keep = np.concatenate([[True], np.diff(d) > 0])
    for k in lap:
        if lap[k] is not None:
            lap[k] = lap[k][keep]
    if len(lap["distance"]) < 50:
        raise LapError(f"{filename}: too few usable rows ({len(lap['distance'])}). Is this a full lap?")

    for k in ("throttle", "brake"):
        if lap[k] is None:
            lap[k] = np.zeros_like(lap["speed"])
            warnings.append(f"No {k} column found, treating it as zero.")
        elif np.nanmax(lap[k]) > 1.5:
            lap[k] = lap[k] / 100.0
    if lap["steer"] is None:
        lap["steer"] = np.zeros_like(lap["speed"])
        warnings.append("No steering column found, snap detection is disabled.")
    else:
        m = np.nanmax(np.abs(lap["steer"]))
        if m > 1.5:
            lap["steer"] = lap["steer"] / m
    for k in ("glat", "glon"):
        if lap[k] is not None and np.nanmax(np.abs(lap[k])) > 8:
            lap[k] = lap[k] / 9.81
    if lap["glat"] is None:
        warnings.append("No lateral g column found, grip usage is unavailable.")

    lap["warnings"] = warnings
    lap["name"] = filename
    return lap
