"""Synthetic Assetto Corsa style telemetry generator.

Used for demos and tests, so the app works without the game installed.
Run `python sample_data.py` to write CSV files into ./sample_laps/.

The "driver" lap has deliberate mistakes baked in:
  T2  under-uses grip (too cautious through a fast corner)
  T3  brakes about 22 m too early
  T4  releases the brake far too abruptly and the rear snaps (Lesmo style)
  T5  picks up the throttle late and abruptly
"""
import os

import numpy as np

STEP = 2.0
TRACK_LEN = 4500.0
VMAX = 270.0

BASE = dict(rel=45.0, th_on=5.0, ramp=70.0, peak=0.95, snap=False)

CORNERS = [
    dict(c=500, vmin=105, side=1, bl=174, el=280, steer=0.50, g=1.85),
    dict(c=1150, vmin=165, side=-1, bl=129, el=220, steer=0.35, g=1.95),
    dict(c=1850, vmin=88, side=1, bl=184, el=290, steer=0.65, g=1.70),
    dict(c=2550, vmin=185, side=1, bl=109, el=200, steer=0.30, g=2.00),
    dict(c=3300, vmin=120, side=-1, bl=165, el=270, steer=0.50, g=1.80),
    dict(c=4000, vmin=80, side=-1, bl=187, el=280, steer=0.70, g=1.65),
]

DRIVER_OVERRIDES = {
    1: dict(g=1.45, vmin=157),
    2: dict(bl=206, vmin=82),
    3: dict(rel=8.0, snap=True, vmin=183, el=218),
    4: dict(th_on=35.0, ramp=10.0, vmin=118, el=295),
    5: dict(vmin=79),
}


def _ss(u):
    u = np.clip(u, 0, 1)
    return u * u * (3 - 2 * u)


def _bell(d, c, w):
    return np.exp(-(((d - c) / w) ** 2))


def _build(driver: bool, seed: int):
    rng = np.random.default_rng(seed)
    d = np.arange(0, TRACK_LEN, STEP)
    v = np.full_like(d, VMAX)
    br = np.zeros_like(d)
    th = np.ones_like(d)
    steer = np.zeros_like(d)
    glat = np.zeros_like(d)
    snap_g = np.zeros_like(d)

    for i, base in enumerate(CORNERS):
        p = dict(BASE)
        p.update(base)
        if driver:
            p.update(DRIVER_OVERRIDES.get(i, {}))
        c, vmin, bl, el = p["c"], p["vmin"], p["bl"], p["el"]

        m = (d >= c - bl) & (d <= c)
        u = (d[m] - (c - bl)) / bl
        v[m] = np.minimum(v[m], VMAX - (VMAX - vmin) * _ss(u))
        m2 = (d > c) & (d <= c + el)
        u2 = (d[m2] - c) / el
        v[m2] = np.minimum(v[m2], vmin + (VMAX - vmin) * _ss(u2))

        # brake: quick ramp up, hold, linear release to the apex
        mb = (d >= c - bl) & (d <= c)
        pos = d[mb] - (c - bl)
        ramp_up = np.clip(pos / 10.0, 0, 1)
        release = np.clip((c - d[mb]) / p["rel"], 0, 1)
        br[mb] = p["peak"] * np.minimum(ramp_up, release)
        th[mb] = 0.0

        # throttle: maintenance, then ramp
        mm = (d > c) & (d < c + p["th_on"])
        th[mm] = 0.15
        mr = (d >= c + p["th_on"]) & (d <= c + p["th_on"] + p["ramp"])
        th[mr] = 0.15 + 0.85 * (d[mr] - (c + p["th_on"])) / p["ramp"]

        side = p["side"]
        steer += side * p["steer"] * _bell(d, c, 55)
        glat += side * p["g"] * _bell(d, c, 60)
        if p["snap"]:
            steer += -side * 0.65 * _bell(d, c - 12, 9)
            snap_g += 0.6 * _bell(d, c - 12, 9)

    v = v + rng.normal(0, 0.3, len(d))
    br = np.clip(br + rng.normal(0, 0.004, len(d)) * (br > 0), 0, 1)
    th = np.clip(th + rng.normal(0, 0.004, len(d)), 0, 1)
    steer = steer + rng.normal(0, 0.004, len(d))
    glat = np.abs(glat) + snap_g + rng.normal(0, 0.01, len(d))

    ms = v / 3.6
    glon = np.gradient(ms, d) * ms / 9.81
    t = np.concatenate([[0], np.cumsum(STEP / ((ms[1:] + ms[:-1]) / 2))])
    gear = 1 + np.digitize(v, [85, 120, 155, 190, 230])

    return {
        "distance": d, "time": t, "speed": v, "throttle": th, "brake": br,
        "steer": steer, "gear": gear.astype(float), "glat": glat, "glon": glon,
        "warnings": [],
    }


def make_laps():
    """Return (reference_lap, driver_lap) as dicts of numpy arrays."""
    return _build(False, 1), _build(True, 2)


def write_csv(lap, path):
    cols = ["distance", "time", "speed", "throttle", "brake", "steer", "gear", "glat", "glon"]
    names = ["distance_m", "time_s", "speed_kmh", "throttle", "brake", "steer", "gear", "g_lat", "g_lon"]
    with open(path, "w", newline="") as f:
        f.write(",".join(names) + "\n")
        n = len(lap["distance"])
        for i in range(n):
            f.write(",".join(f"{lap[c][i]:.4f}" for c in cols) + "\n")


if __name__ == "__main__":
    ref, drv = make_laps()
    out = os.path.join(os.path.dirname(__file__), "sample_laps")
    os.makedirs(out, exist_ok=True)
    write_csv(ref, os.path.join(out, "reference_lap.csv"))
    write_csv(drv, os.path.join(out, "your_lap.csv"))
    print(f"Reference lap {ref['time'][-1]:.2f}s, your lap {drv['time'][-1]:.2f}s")
    print("Wrote CSVs to", out)
