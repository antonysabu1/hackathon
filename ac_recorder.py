"""Apex Coach live recorder for Assetto Corsa (Windows).

Run this while you drive. Assetto Corsa shares its live data through Windows shared memory,
so no mod is needed. Each completed lap is saved as a JSON file in the lap format Apex Coach reads
(with the car, track, fuel and tyre data from the game), then sent to the backend when it is running.

    python ac_recorder.py --driver Siva
    python ac_recorder.py --driver Siva --setup "C:\\Users\\you\\Documents\\Assetto Corsa\\setups\\ks_mclaren_720s_gt3\\monza\\mysetup.ini"
    python ac_recorder.py --fake            (no game: replays the demo laps to test the pipeline)

Only the Python standard library is used, so there is nothing to install.
"""
import argparse
import configparser
import ctypes
import json
import mmap
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

# ---------------------------------------------------------------- Assetto Corsa shared memory layout
# Field order follows the public AC shared memory reference (pack=4). Only the fields we need are
# declared, and every struct stops right after the last field we read.


class Physics(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ("packetId", ctypes.c_int),
        ("gas", ctypes.c_float),
        ("brake", ctypes.c_float),
        ("fuel", ctypes.c_float),
        ("gear", ctypes.c_int),
        ("rpms", ctypes.c_int),
        ("steerAngle", ctypes.c_float),
        ("speedKmh", ctypes.c_float),
        ("velocity", ctypes.c_float * 3),
        ("accG", ctypes.c_float * 3),
        ("wheelSlip", ctypes.c_float * 4),
        ("wheelLoad", ctypes.c_float * 4),
        ("wheelsPressure", ctypes.c_float * 4),
        ("wheelAngularSpeed", ctypes.c_float * 4),
        ("tyreWear", ctypes.c_float * 4),
        ("tyreDirtyLevel", ctypes.c_float * 4),
        ("tyreCoreTemperature", ctypes.c_float * 4),
        ("camberRAD", ctypes.c_float * 4),
        ("suspensionTravel", ctypes.c_float * 4),
        ("drs", ctypes.c_float),
        ("tc", ctypes.c_float),
        ("heading", ctypes.c_float),
        ("pitch", ctypes.c_float),
        ("roll", ctypes.c_float),
        ("cgHeight", ctypes.c_float),
        ("carDamage", ctypes.c_float * 5),
        ("numberOfTyresOut", ctypes.c_int),
        ("pitLimiterOn", ctypes.c_int),
        ("abs", ctypes.c_float),
        ("kersCharge", ctypes.c_float),
        ("kersInput", ctypes.c_float),
        ("autoShifterOn", ctypes.c_int),
        ("rideHeight", ctypes.c_float * 2),
        ("turboBoost", ctypes.c_float),
        ("ballast", ctypes.c_float),
        ("airDensity", ctypes.c_float),
        ("airTemp", ctypes.c_float),
        ("roadTemp", ctypes.c_float),
        ("localAngularVel", ctypes.c_float * 3),
        ("finalFF", ctypes.c_float),
        ("performanceMeter", ctypes.c_float),
        ("engineBrake", ctypes.c_int),
        ("ersRecoveryLevel", ctypes.c_int),
        ("ersPowerLevel", ctypes.c_int),
        ("ersHeatCharging", ctypes.c_int),
        ("ersIsCharging", ctypes.c_int),
        ("kersCurrentKJ", ctypes.c_float),
        ("drsAvailable", ctypes.c_int),
        ("drsEnabled", ctypes.c_int),
        ("brakeTemp", ctypes.c_float * 4),
        ("clutch", ctypes.c_float),
        ("tyreTempI", ctypes.c_float * 4),
        ("tyreTempM", ctypes.c_float * 4),
        ("tyreTempO", ctypes.c_float * 4),
        ("isAIControlled", ctypes.c_int),
        ("tyreContactPoint", ctypes.c_float * 12),
        ("tyreContactNormal", ctypes.c_float * 12),
        ("tyreContactHeading", ctypes.c_float * 12),
        ("brakeBias", ctypes.c_float),
    ]


class Graphics(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ("packetId", ctypes.c_int),
        ("status", ctypes.c_int),  # 0 off, 1 replay, 2 live, 3 pause
        ("session", ctypes.c_int),
        ("currentTime", ctypes.c_wchar * 15),
        ("lastTime", ctypes.c_wchar * 15),
        ("bestTime", ctypes.c_wchar * 15),
        ("split", ctypes.c_wchar * 15),
        ("completedLaps", ctypes.c_int),
        ("position", ctypes.c_int),
        ("iCurrentTime", ctypes.c_int),
        ("iLastTime", ctypes.c_int),
        ("iBestTime", ctypes.c_int),
        ("sessionTimeLeft", ctypes.c_float),
        ("distanceTraveled", ctypes.c_float),
        ("isInPit", ctypes.c_int),
        ("currentSectorIndex", ctypes.c_int),
        ("lastSectorTime", ctypes.c_int),
        ("numberOfLaps", ctypes.c_int),
        ("tyreCompound", ctypes.c_wchar * 33),
        ("replayTimeMultiplier", ctypes.c_float),
        ("normalizedCarPosition", ctypes.c_float),
        ("carCoordinates", ctypes.c_float * 3),
    ]


class Static(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ("smVersion", ctypes.c_wchar * 15),
        ("acVersion", ctypes.c_wchar * 15),
        ("numberOfSessions", ctypes.c_int),
        ("numCars", ctypes.c_int),
        ("carModel", ctypes.c_wchar * 33),
        ("track", ctypes.c_wchar * 33),
        ("playerName", ctypes.c_wchar * 33),
        ("playerSurname", ctypes.c_wchar * 33),
        ("playerNick", ctypes.c_wchar * 33),
        ("sectorCount", ctypes.c_int),
        ("maxTorque", ctypes.c_float),
        ("maxPower", ctypes.c_float),
        ("maxRpm", ctypes.c_int),
        ("maxFuel", ctypes.c_float),
        ("suspensionMaxTravel", ctypes.c_float * 4),
        ("tyreRadius", ctypes.c_float * 4),
        ("maxTurboBoost", ctypes.c_float),
        ("deprecated1", ctypes.c_float),
        ("deprecated2", ctypes.c_float),
        ("penaltiesEnabled", ctypes.c_int),
        ("aidFuelRate", ctypes.c_float),
        ("aidTireRate", ctypes.c_float),
    ]


WHEELS = ("fl", "fr", "rl", "rr")


def _ok(v, lo, hi):
    """Guards against garbage if a field offset is off: returns None for values outside a sane range."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if lo <= v <= hi and v == v else None


def pretty(name: str) -> str:
    """ks_mclaren_720s_gt3 -> Mclaren 720s Gt3 (readable and stable, so laps group together)."""
    name = name.strip()
    if name.lower().startswith("ks_"):
        name = name[3:]
    return name.replace("_", " ").title()


class ACSource:
    """Reads the live game through Windows shared memory. Raises FileNotFoundError while the game is not running."""

    def __init__(self):
        if sys.platform != "win32":
            raise RuntimeError("Live recording only works on Windows with Assetto Corsa running.")
        k = ctypes.windll.kernel32
        k.OpenFileMappingW.restype = ctypes.c_void_p
        k.OpenFileMappingW.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_wchar_p]
        k.MapViewOfFile.restype = ctypes.c_void_p
        k.MapViewOfFile.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_size_t]
        k.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
        k.CloseHandle.argtypes = [ctypes.c_void_p]
        self.k = k
        self.maps = []
        try:
            self.phys = self._open("Local\\acpmf_physics", Physics)
            self.gfx = self._open("Local\\acpmf_graphics", Graphics)
            self.stat = self._open("Local\\acpmf_static", Static)
        except Exception:
            self.close()
            raise
        self.last_packet = -1
        self.last_change = time.perf_counter()

    def _open(self, name, struct):
        # OpenFileMapping only attaches to an existing mapping, so it never creates one by accident
        # (creating it ourselves before the game starts could interfere with the game).
        h = self.k.OpenFileMappingW(4, False, name)  # 4 = FILE_MAP_READ
        if not h:
            raise FileNotFoundError(name)
        view = self.k.MapViewOfFile(h, 4, 0, 0, 0)
        if not view:
            self.k.CloseHandle(h)
            raise FileNotFoundError(name)
        self.maps.append((h, view))
        return view, struct

    def close(self):
        for h, view in self.maps:
            self.k.UnmapViewOfFile(view)
            self.k.CloseHandle(h)
        self.maps = []

    @staticmethod
    def _read(pair):
        view, struct = pair
        return struct.from_buffer_copy(ctypes.string_at(view, ctypes.sizeof(struct)))

    def read(self):
        p = self._read(self.phys)
        g = self._read(self.gfx)
        s = self._read(self.stat)
        now = time.perf_counter()
        if p.packetId != self.last_packet:
            self.last_packet = p.packetId
            self.last_change = now
        stale = now - self.last_change
        ch = {
            "rpm": p.rpms,
            "g_lat": p.accG[0],  # AC order is x lateral, y vertical, z longitudinal
            "g_vert": p.accG[1],
            "g_long": p.accG[2],
            "clutch": p.clutch,
            "turbo": p.turboBoost,
            "drs": p.drs,
            "abs": p.abs,
            "tc": p.tc,
            "heading": p.heading,
            "pitch": p.pitch,
            "roll": p.roll,
            "ride_front": p.rideHeight[0],
            "ride_rear": p.rideHeight[1],
            "tyres_out": p.numberOfTyresOut,
            "x": g.carCoordinates[0],
            "y": g.carCoordinates[1],
            "z": g.carCoordinates[2],
        }
        for i, w in enumerate(WHEELS):
            ch[f"slip_{w}"] = p.wheelSlip[i]
            ch[f"load_{w}"] = p.wheelLoad[i]
            ch[f"pressure_{w}"] = p.wheelsPressure[i]
            ch[f"tyre_temp_{w}"] = p.tyreCoreTemperature[i]
            ch[f"tyre_temp_in_{w}"] = p.tyreTempI[i]
            ch[f"tyre_temp_mid_{w}"] = p.tyreTempM[i]
            ch[f"tyre_temp_out_{w}"] = p.tyreTempO[i]
            ch[f"brake_temp_{w}"] = p.brakeTemp[i]
            ch[f"susp_{w}"] = p.suspensionTravel[i]
            ch[f"wear_{w}"] = 100.0 - p.tyreWear[i]
        meta = {
            "air_temp": _ok(p.airTemp, -30, 70),
            "road_temp": _ok(p.roadTemp, -30, 120),
            "brake_bias": _ok(p.brakeBias * 100, 30, 80),
            "max_rpm": _ok(s.maxRpm, 1000, 30000),
            "max_fuel": _ok(s.maxFuel, 1, 500),
            "aid_tyre_rate": _ok(s.aidTireRate, 0, 10),
            "aid_fuel_rate": _ok(s.aidFuelRate, 0, 10),
            "damage": max(p.carDamage),
        }
        return {
            "live": g.status == 2 and stale < 3.0,
            "status": g.status,
            "stale": stale,
            "best_ms": g.iBestTime,
            "tyres_out": p.numberOfTyresOut,
            "packet": p.packetId,
            "gas": p.gas,
            "brake": p.brake,
            "fuel": p.fuel,
            "gear": p.gear,
            "steer": p.steerAngle,
            "speed": p.speedKmh,
            "pressure": list(p.wheelsPressure),
            "wear": list(p.tyreWear),
            "laps": g.completedLaps,
            "last_ms": g.iLastTime,
            "in_pit": bool(g.isInPit),
            "compound": g.tyreCompound.strip(),
            "pos": g.normalizedCarPosition,
            "car": pretty(s.carModel),
            "track": pretty(s.track),
            "car_id": s.carModel,
            "track_id": s.track,
            "ch": ch,
            "meta": meta,
        }


class FakeSource:
    """Replays a lap JSON file as if it were the game, to test the pipeline without AC."""

    def __init__(self, files):
        self.laps = [json.load(open(f)) for f in files]
        self.lap_i = 0
        self.f_i = 0
        self.laps_done = 0
        self.last_ms = 0
        self.best_ms = 0

    def read(self):
        lap = self.laps[self.lap_i % len(self.laps)]
        frames = lap["frames"]
        fr = frames[self.f_i]
        self.f_i += 1
        if self.f_i >= len(frames):
            self.f_i = 0
            self.lap_i += 1
            self.laps_done += 1
            self.last_ms = int(lap["lap_time"] * 1000)
            if self.best_ms == 0 or self.last_ms < self.best_ms:
                self.best_ms = self.last_ms
        return {
            "live": True,
            "packet": 1,
            "gas": fr["throttle"],
            "brake": fr["brake"],
            "fuel": 40.0 - 0.02 * self.laps_done - 0.0005 * self.f_i,
            "gear": fr.get("gear", 3) + 1,
            "steer": fr["steering"],
            "speed": fr["speed"],
            "pressure": [27.5, 27.5, 27.0, 27.0],
            "wear": [100 - 0.3 * self.laps_done] * 4,
            "laps": self.laps_done,
            "last_ms": self.last_ms,
            "in_pit": False,
            "compound": "Medium",
            "pos": self.f_i / len(frames),
            "car": "Demo Car",
            "track": "Demo Track",
            "stale": 0.0,
            "status": 2,
            "best_ms": self.best_ms,
            "tyres_out": 0,
            "ch": {"rpm": 4000 + 40 * fr["speed"], "g_lat": fr["steering"] * 2.0},
            "meta": {"air_temp": 24.0, "road_temp": 31.0, "brake_bias": 58.0, "damage": 0.0},
        }


# ---------------------------------------------------------------- lap recording


class LapRecorder:
    """Turns a stream of samples into complete laps, each marked valid or probably invalid."""

    MIN_FRAMES = 200
    OFF_TRACK_LIMIT = 0.3  # seconds with 3 or more tyres off the track before a lap counts as invalid

    def __init__(self):
        self.reset()
        self.prev_laps = None
        self.prev_last = None
        self.pending = None
        self.best_seen = 0

    def reset(self):
        self.buf = []
        self.t0 = None
        self.last_t = None
        self.valid = False  # False until we see a lap start, so a partial first lap is dropped
        self.stall = False
        self.off_time = 0.0

    def feed(self, s, now):
        """Returns a list of laps that are finished (usually empty, sometimes one)."""
        out = []
        if self.prev_laps is None:
            self.prev_laps = s["laps"]
            self.prev_last = s["last_ms"]
        # Two signals say "a lap just ended": the game's lap counter went up, or it published a new last-lap time.
        # Some sessions update only one of them, so either one counts. Whichever comes second is ignored.
        counter_up = s["laps"] > self.prev_laps
        time_new = s["last_ms"] > 0 and s["last_ms"] != self.prev_last
        pos = s.get("pos", 0.0)
        crossed = (counter_up or time_new) and len(self.buf) >= 100
        if s["laps"] < self.prev_laps:  # session restarted
            self.reset()
            if self.pending:
                out.append(self.pending[0])
                self.pending = None
        elif crossed:  # crossed the line
            lap = self._finish(s)
            if self.pending:
                out.append(self.pending[0])
                self.pending = None
            if lap:
                # Wait half a second so the game can update its best time; that tells us if it counted the lap.
                self.pending = (lap, s["last_ms"], self.best_seen, now + 0.5)
            self.reset()
            self.valid = True
        self.prev_laps = s["laps"]
        self.prev_last = s["last_ms"]

        if self.pending:
            lap, last_ms, prev_best, t_end = self.pending
            counted = last_ms > 0 and s.get("best_ms", 0) == last_ms
            if counted or now >= t_end:
                self.pending = None
                if not counted and lap["valid"] and (prev_best == 0 or last_ms < prev_best):
                    lap["valid"] = False
                    lap["invalid_reason"] = "the game did not count it as a timed lap (probably invalidated)"
                out.append(lap)
        self.best_seen = s.get("best_ms", self.best_seen)

        if not s["live"]:
            if self.buf:
                self.stall = True  # paused or in replay: this lap is not trustworthy
            self.last_t = None
            return out
        if s["in_pit"]:
            self.stall = True
        if self.t0 is None:
            self.t0 = now
        dt = 0.01 if self.last_t is None else now - self.last_t
        self.last_t = now
        if dt > 0.5:
            self.stall = True
        if s.get("tyres_out", 0) >= 3:
            self.off_time += dt
        self.buf.append((now - self.t0, dt, s))
        return out

    def _finish(self, s):
        if not self.valid or self.stall or len(self.buf) < self.MIN_FRAMES or s["last_ms"] <= 0:
            return None
        lap_time = s["last_ms"] / 1000.0
        measured = self.buf[-1][0]
        if abs(measured - lap_time) > 1.5:  # we missed too much of the lap
            return None
        raw_steer = [abs(x[2]["steer"]) for x in self.buf]
        scale = max(raw_steer) if raw_steer and max(raw_steer) > 1.5 else 1.0  # make steering roughly -1..1
        frames = []
        for t, dt, x in self.buf:
            wear = 100.0 - sum(x["wear"]) / 4.0
            frames.append(
                {
                    "t": round(t, 4),
                    "speed": round(x["speed"], 2),
                    "throttle": round(max(0.0, min(1.0, x["gas"])), 3),
                    "brake": round(max(0.0, min(1.0, x["brake"])), 3),
                    "steering": round(x["steer"] / scale, 4),
                    "gear": max(0, x["gear"] - 1),
                    "dt": round(dt, 4),
                    "fuel": round(x["fuel"], 3),
                    "tyre_wear": round(max(0.0, wear), 2),
                }
            )
            for k, v in x.get("ch", {}).items():
                frames[-1][k] = round(float(v), 3)
        first, last = self.buf[0][2], self.buf[-1][2]
        extra = {k: v for k, v in first.get("meta", {}).items() if v is not None}
        extra["damage"] = round(max(x[2].get("meta", {}).get("damage", 0.0) for x in self.buf), 3)
        off = self.off_time >= self.OFF_TRACK_LIMIT
        return {
            **extra,
            "valid": not off,
            "invalid_reason": f"3 or more tyres off the track for {self.off_time:.1f} s" if off else "",
            "lap_time": lap_time,
            "car": first["car"],
            "track": first["track"],
            "tyre_compound": first["compound"],
            "tyre_pressure_avg": round(sum(first["pressure"]) / 4.0, 1),
            "recorded_by": "ac_recorder",
            "car_id": first.get("car_id", ""),
            "track_id": first.get("track_id", ""),
            "frames": frames,
        }


# ---------------------------------------------------------------- setup file


def read_setup(path):
    """Reads an Assetto Corsa setup .ini into {setting: value}. Settings are named by the game (e.g. WING_1)."""
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    cp.read(path, encoding="utf-8")
    out = {}
    for sec in cp.sections():
        if sec.upper() in ("CAR", "__EXT_PATCH"):
            continue
        if cp.has_option(sec, "VALUE"):
            out[sec] = cp.get(sec, "VALUE")
    return out


def setup_roots():
    roots = []
    for env in ("OneDrive", "OneDriveConsumer", "USERPROFILE"):
        base = os.environ.get(env)
        if base:
            roots.append(os.path.join(base, "Documents", "Assetto Corsa", "setups"))
    roots.append(os.path.join(os.path.expanduser("~"), "Documents", "Assetto Corsa", "setups"))
    seen = []
    for r in roots:
        if r not in seen and os.path.isdir(r):
            seen.append(r)
    return seen


def find_setup(car_id, track_id):
    """Best guess at the setup you drove: the newest saved setup file for this car on this track.
    Assetto Corsa does not say which setup is loaded, so this is a guess. Returns (path, values) or (None, {})."""
    best = None
    for root in setup_roots():
        car_dir = os.path.join(root, car_id)
        for folder, _dirs, files in os.walk(car_dir):
            rel = os.path.relpath(folder, car_dir).lower()
            if not (track_id.lower() in rel or rel.startswith("generic")):
                continue
            for name in files:
                if name.lower().endswith(".ini"):
                    path = os.path.join(folder, name)
                    mtime = os.path.getmtime(path)
                    if best is None or mtime > best[0]:
                        best = (mtime, path)
    if not best:
        return None, {}
    try:
        return best[1], read_setup(best[1])
    except Exception:
        return None, {}


# ---------------------------------------------------------------- saving and sending


def multipart(fields_file):
    boundary = uuid.uuid4().hex
    name, data = fields_file
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\n"
        "Content-Type: application/json\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    return boundary, body


def post_json(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def send_lap(path, api, driver, setup):
    """Uploads one saved lap and its session details. Returns the lap id or raises."""
    data = open(path, "rb").read()
    lap = json.loads(data)
    q = urllib.parse.urlencode({"driver_name": driver, "track": lap["track"], "car": lap["car"]})
    boundary, body = multipart((os.path.basename(path), data))
    req = urllib.request.Request(
        f"{api}/upload?{q}", data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        res = json.loads(r.read())
    if res.get("status") != "success":
        raise RuntimeError(res.get("message", "upload failed"))
    frames = lap["frames"]
    post_json(
        f"{api}/profile/session",
        {
            "lap_id": res["lap_id"],
            "driver": driver,
            "track": lap["track"],
            "car": lap["car"],
            "setup": {**({"brake_bias": lap["brake_bias"]} if lap.get("brake_bias") else {}), **lap.get("setup", {}), **setup},
            "tyre": {
                "compound": lap.get("tyre_compound", ""),
                "wear_start": frames[0]["tyre_wear"],
                "wear_end": frames[-1]["tyre_wear"],
                "laps_run": 1,
                "pressure_avg_psi": lap.get("tyre_pressure_avg", ""),
            },
            "fuel": {"start": frames[0]["fuel"], "end": frames[-1]["fuel"]},
            "valid": bool(lap.get("valid", True)),
            "invalid_reason": lap.get("invalid_reason", ""),
            "notes": "recorded live"
            + (f", setup file {lap['setup_file']} (newest for this car and track)" if lap.get("setup_file") else ", no saved setup file found (stock setup?)")
            + (f", air {lap['air_temp']:.0f}C" if lap.get("air_temp") is not None else "")
            + (f", road {lap['road_temp']:.0f}C" if lap.get("road_temp") is not None else ""),
        },
    )
    return res["lap_id"]


def main():
    ap = argparse.ArgumentParser(description="Record Assetto Corsa laps for Apex Coach")
    ap.add_argument("--driver", default="Siva")
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--out", default="recorded_laps")
    ap.add_argument("--setup", help="path to the setup .ini you are driving with")
    ap.add_argument("--no-upload", action="store_true", help="only save files, do not send to the backend")
    ap.add_argument("--resend-all", action="store_true", help="queue every lap already saved in the sent folder to be uploaded again")
    ap.add_argument("--fake", nargs="*", help="replay lap JSON files instead of the game (test mode)")
    ap.add_argument("--fast", action="store_true", help="with --fake, do not wait in real time")
    args = ap.parse_args()

    pending = os.path.join(args.out, "pending")
    sent = os.path.join(args.out, "sent")
    os.makedirs(pending, exist_ok=True)
    os.makedirs(sent, exist_ok=True)
    setup = read_setup(args.setup) if args.setup else {}
    if args.setup:
        print(f"Setup file read: {len(setup)} settings")

    def upload_pending():
        if args.no_upload:
            return
        for name in sorted(os.listdir(pending)):
            path = os.path.join(pending, name)
            try:
                lap_id = send_lap(path, args.api, args.driver, setup)
                os.replace(path, os.path.join(sent, name))
                print(f"  sent {name} to the backend as lap #{lap_id}")
            except (urllib.error.URLError, OSError, RuntimeError, ValueError) as e:
                print(f"  could not send {name} yet ({e}). It stays in {pending} and is retried after the next lap.")
                return

    if args.resend_all:
        for name in os.listdir(sent):
            os.replace(os.path.join(sent, name), os.path.join(pending, name))
        print("Queued every saved lap to be sent again.")
    fake = args.fake is not None
    fast = fake and args.fast
    stats = {"valid": 0, "invalid": 0}

    def save(lap):
        if not args.setup and lap.get("car_id"):
            path, values = find_setup(lap["car_id"], lap.get("track_id", ""))
            if path:
                lap["setup"] = values
                lap["setup_file"] = os.path.basename(path)
        mins, secs = divmod(lap["lap_time"], 60)
        ok = lap.get("valid", True)
        stats["valid" if ok else "invalid"] += 1
        name = f"{lap['track']}_{lap['car']}_{int(time.time())}_{stats['valid'] + stats['invalid']}.json".replace(" ", "_")
        with open(os.path.join(pending, name), "w") as f:
            json.dump(lap, f)
        tag = "" if ok else f"  INVALID: {lap.get('invalid_reason', '')}"
        print(f"\nLap saved: {int(mins)}:{secs:06.3f}  {lap['car']} at {lap['track']}{tag}")
        print("  setup:", lap.get("setup_file") or "no saved setup file found, treated as stock")
        upload_pending()

    def session(src):
        """One connection to the game. Starts recording when you start driving, ends when you leave the session."""
        rec = LapRecorder()
        clock = 0.0
        last_print = 0.0
        was_live = False
        off_since = None
        shown = None  # what we last told the user, so we only print changes
        while True:
            s = src.read()
            now = clock if fast else time.perf_counter()
            clock += 0.01
            status = s.get("status", 2)

            if s["live"] and not was_live:
                was_live = True
                print(f"\nSession started: {s['car']} at {s['track']}. Recording.")
            if was_live:
                # status 0 = out of the session (menu or exit). Pause (3) and replay (1) keep the session open.
                off_since = (off_since or now) if status == 0 else None
                if off_since is not None and now - off_since > 3:
                    return True
            if not fake and status != 3 and s["stale"] > 10:
                return was_live  # the game closed

            for lap in rec.feed(s, now):
                save(lap)

            state = "driving" if s["live"] else ("paused" if status == 3 else "waiting")
            if state != shown and was_live:
                shown = state
                if state != "driving":
                    print(f"\n  ({state})")
            if state == "driving" and now - last_print > 1.0:
                last_print = now
                print(f"\r  {s['car']} | {s['track']} | lap {s['laps'] + 1} | {s['speed']:5.0f} km/h      ", end="", flush=True)
            if not fast:
                time.sleep(0.016)  # about 60 samples per second
            if fake and src.lap_i >= len(src.laps) * 2:
                return True

    def summary():
        total = stats["valid"] + stats["invalid"]
        if total:
            print(f"Session ended. {stats['valid']} valid lap(s) saved, {stats['invalid']} invalid lap(s) marked.")
        stats["valid"] = stats["invalid"] = 0

    upload_pending()
    try:
        if fake:
            files = args.fake or ["frontend/public/demo/your_lap.json", "frontend/public/demo/reference_lap.json"]
            print("Test mode: replaying", ", ".join(files))
            session(FakeSource(files))
            summary()
        else:
            print("Ready. Open Assetto Corsa and start a driving session. Recording starts and stops by itself.")
            print("Leave this window open. You never need to press anything.")
            idle_note = False
            while True:
                try:
                    src = ACSource()
                except FileNotFoundError:
                    time.sleep(2)  # game not running yet
                    continue
                except RuntimeError as e:
                    print(e)
                    return
                try:
                    session(src)
                finally:
                    src.close()
                summary()
                print("Waiting for the next session.")
                time.sleep(3)
    except KeyboardInterrupt:
        summary()
        print("\nStopped.")


if __name__ == "__main__":
    main()
