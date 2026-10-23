"""Deterministic analysis engine.

Every number the app shows comes from here. The LLM only explains these
findings, it never reads raw telemetry.
"""
import numpy as np

STEP = 2.0


def _r(x, n=2):
    if x is None:
        return None
    return round(float(x), n)


# ---------------------------------------------------------------- resampling
def resample(lap, length):
    d = lap["distance"]
    grid = np.arange(0, length, STEP)
    out = {"d": grid}
    for k in ("speed", "throttle", "brake", "steer", "glat", "glon"):
        out[k] = np.interp(grid, d, lap[k]) if lap.get(k) is not None else None
    t = np.interp(grid, d, lap["time"])
    out["t"] = t - t[0]
    if out["glon"] is None:
        v = out["speed"] / 3.6
        out["glon"] = np.gradient(v, grid) * v / 9.81
    return out


# ------------------------------------------------------------ corner finding
def detect_corners(ref):
    v, d = ref["speed"], ref["d"]
    thresh = np.percentile(v, 95) * 0.82
    below = v < thresh
    segs, start = [], None
    for i, b in enumerate(below):
        if b and start is None:
            start = i
        if (not b or i == len(below) - 1) and start is not None:
            segs.append((start, i))
            start = None
    apexes = []
    for s, e in segs:
        if e - s >= 8:
            seg = v[s:e + 1]
            flat = np.where(seg <= seg.min() + 1.5)[0]
            apexes.append(s + int(np.mean(flat)))
    n = len(d)
    corners = []
    for k, ia in enumerate(apexes):
        i0 = max(0, ia - int(260 / STEP))
        i1 = min(n, ia + int(160 / STEP))
        if k > 0:
            i0 = max(i0, (apexes[k - 1] + ia) // 2)
        if k < len(apexes) - 1:
            i1 = min(i1, (apexes[k + 1] + ia) // 2)
        corners.append({"id": k + 1, "name": f"T{k + 1}", "ia": ia, "i0": i0, "i1": i1})
    return corners


# ----------------------------------------------------------------- features
def _features(lap, i0, i1, ia, gmax):
    g, sp, br, th, st = lap["d"], lap["speed"], lap["brake"], lap["throttle"], lap["steer"]
    lo, hi = max(i0, ia - 30), min(i1 - 1, ia + 30)
    iv = ia  # measure everything from the shared apex so the two laps line up
    f = {"apex_d": float(g[iv]), "min_speed": float(sp[lo:hi + 1].min())}

    # braking zone
    idx = np.where(br[i0:min(i1, iv + 3)] > 0.05)[0] + i0
    f.update(brake_start_d=None, brake_peak=None, release_len=None)
    if len(idx):
        last = int(idx[-1])
        start = last
        while start - 1 >= i0 and br[start - 1] > 0.05:
            start -= 1
        peak = float(br[start:last + 1].max())
        seg = br[start:last + 1]
        l80 = start + int(np.where(seg >= 0.8 * peak)[0][-1])
        after = np.where(br[l80:last + 2] <= 0.1 * peak)[0]
        j = l80 + int(after[0]) if len(after) else last
        f["brake_start_d"] = float(g[start])
        f["brake_peak"] = peak
        f["release_len"] = max(float((j - l80) * STEP / 0.7), STEP)

    # throttle pickup
    i_on = None
    for i in range(max(i0, iv - 3), i1):
        if th[i] > 0.3:
            i_on = i
            break
    f["throttle_on_d"] = float(g[i_on] - g[iv]) if i_on is not None else None
    f["ramp_len"] = None
    if i_on is not None:
        j90 = np.where(th[i_on:i1] > 0.9)[0]
        if len(j90):
            f["ramp_len"] = float(g[i_on + j90[0]] - g[i_on])

    f["exit_speed"] = float(sp[min(iv + int(100 / STEP), i1 - 1)])

    # grip usage (friction circle share of the best grip seen on either lap)
    f["grip"] = None
    if lap["glat"] is not None and gmax:
        w0, w1 = max(i0, iv - int(40 / STEP)), min(i1, iv + int(40 / STEP))
        comb = np.hypot(lap["glat"][w0:w1], lap["glon"][w0:w1])
        f["grip"] = float(min(np.percentile(comb, 95) / gmax, 1.0))

    # snap: counter steering after the car has taken a set
    sign = np.sign(np.sum(st[max(i0, iv - 20):iv + 20])) or 1.0
    a, b = max(i0, iv - 30), min(i1, iv + 30)
    counter = -sign * st[a:b]
    hits = np.where(counter > 0.12)[0]
    f["snap"] = bool(len(hits))
    f["snap_d"] = float(g[a + hits[0]]) if len(hits) else None
    f["snap_mag"] = float(counter.max()) if len(hits) else 0.0

    f["time"] = float(lap["t"][i1 - 1] - lap["t"][i0])
    return f


SETUP_OPTIONS = {
    "entry": [
        "Move brake bias 1 or 2 clicks forward",
        "Add a little diff coast lock for stability on lift",
        "Soften the rear anti roll bar by 1 or 2 clicks",
    ],
    "exit": [
        "Reduce diff power lock",
        "Raise traction control by one step",
        "Soften the rear anti roll bar by 1 or 2 clicks",
    ],
}


def _diagnose(u, r, loss):
    issues = []
    dbs = None
    if u["brake_start_d"] is not None and r["brake_start_d"] is not None:
        dbs = r["brake_start_d"] - u["brake_start_d"]  # positive means you braked earlier
    dv = r["min_speed"] - u["min_speed"]  # positive means you were slower
    early = dbs is not None and dbs >= 8 and dv >= 3

    if early:
        issues.append(dict(
            type="early_brake", severity="high" if loss > 0.08 else "med",
            message=f"You started braking {dbs:.0f} m earlier than the reference and carried {dv:.0f} km/h less minimum speed.",
            fix=f"Brake about {dbs * 0.7:.0f} m later, then trail off smoothly towards the apex."))
    elif dbs is not None and dbs <= -10 and (r["exit_speed"] - u["exit_speed"]) >= 4:
        issues.append(dict(
            type="late_brake", severity="med",
            message=f"You braked {-dbs:.0f} m later than the reference but left the corner {r['exit_speed'] - u['exit_speed']:.0f} km/h slower.",
            fix="Brake slightly earlier so the car can rotate and you can get on the throttle sooner."))
    elif dv >= 5:
        issues.append(dict(
            type="over_slow", severity="med",
            message=f"Your minimum speed was {dv:.0f} km/h lower than the reference.",
            fix="Carry more speed to the apex. Release the brake a little earlier and let the car roll."))

    abrupt_release = False
    if u["release_len"] and r["release_len"]:
        if r["release_len"] - u["release_len"] >= 12 and u["release_len"] < 0.6 * r["release_len"]:
            abrupt_release = True
            issues.append(dict(
                type="abrupt_release", severity="high",
                message=f"You released the brake over about {u['release_len']:.0f} m, versus {r['release_len']:.0f} m on the reference. A fast release unloads the front tyres and lets the rear step out.",
                fix="Bleed the brake off slowly all the way to the apex. Aim for a release roughly as long as the reference."))

    late_throttle = False
    if u["throttle_on_d"] is not None and r["throttle_on_d"] is not None:
        gap = u["throttle_on_d"] - r["throttle_on_d"]
        abrupt = (u["ramp_len"] is not None and r["ramp_len"] is not None
                  and r["ramp_len"] - u["ramp_len"] >= 20 and u["ramp_len"] < 0.4 * r["ramp_len"])
        if gap >= 12:
            late_throttle = True
            extra = " The pickup was also very sharp." if abrupt else ""
            issues.append(dict(
                type="late_throttle", severity="high" if loss > 0.08 else "med",
                message=f"You got on the throttle {gap:.0f} m later than the reference.{extra}",
                fix="Start rolling onto the throttle earlier and more progressively once the steering unwinds."))
        elif abrupt:
            issues.append(dict(
                type="abrupt_throttle", severity="low",
                message="Your throttle pickup was much sharper than the reference.",
                fix="Ramp the throttle in over a longer distance to keep the rear settled."))

    if u["grip"] is not None and r["grip"] is not None and not early:
        diff = r["grip"] - u["grip"]
        if diff >= 0.08:
            issues.append(dict(
                type="under_grip", severity="med",
                message=f"You used {u['grip'] * 100:.0f}% of the available grip here, the reference used {r['grip'] * 100:.0f}%. There is room to carry more speed.",
                fix="Commit to a bit more entry speed or turn in slightly earlier, in small steps."))

    snap_info = None
    if u["snap"] and not r["snap"]:
        phase = "entry" if u["snap_d"] <= u["apex_d"] + 6 else "exit"
        if phase == "entry":
            inputs_abrupt = abrupt_release
        else:
            inputs_abrupt = late_throttle or any(i["type"] == "abrupt_throttle" for i in issues)
        if inputs_abrupt:
            msg = (f"The car stepped out at {phase}. Your inputs were abrupt just before it, "
                   "so this is most likely a driving issue. Fix the inputs before touching the setup.")
            fix = "Smooth the release first. If it still snaps after that, we look at the setup."
            blame = "driver"
        else:
            msg = (f"The car stepped out at {phase} even though your inputs were smooth, "
                   "so the setup is the next suspect.")
            fix = "Try ONE change, then run 8 clean laps: " + "; ".join(SETUP_OPTIONS[phase]) + "."
            blame = "setup"
        snap_info = dict(phase=phase, blame=blame, options=SETUP_OPTIONS[phase] if blame == "setup" else [])
        issues.insert(0, dict(type="snap", severity="high", message=msg, fix=fix))

    return issues, snap_info


def _public(f):
    keys = ["apex_d", "min_speed", "brake_start_d", "brake_peak", "release_len",
            "throttle_on_d", "ramp_len", "exit_speed", "grip"]
    return {k: _r(f[k], 3 if k in ("grip", "brake_peak") else 1) for k in keys}


# ------------------------------------------------------------------- driver
def analyze(user_lap, ref_lap):
    L = min(user_lap["distance"][-1], ref_lap["distance"][-1])
    u, r = resample(user_lap, L), resample(ref_lap, L)
    corners = detect_corners(r)
    if not corners:
        raise ValueError("No corners were found on the reference lap.")

    gmax = None
    if u["glat"] is not None and r["glat"] is not None:
        gmax = max(np.percentile(np.hypot(u["glat"], u["glon"]), 99.5),
                   np.percentile(np.hypot(r["glat"], r["glon"]), 99.5))

    out_corners = []
    for c in corners:
        fu = _features(u, c["i0"], c["i1"], c["ia"], gmax)
        fr = _features(r, c["i0"], c["i1"], c["ia"], gmax)
        loss = fu["time"] - fr["time"]
        issues, snap = _diagnose(fu, fr, loss)
        out_corners.append(dict(
            id=c["id"], name=c["name"],
            start_d=_r(u["d"][c["i0"]], 0), end_d=_r(u["d"][c["i1"] - 1], 0),
            apex_d=_r(fr["apex_d"], 0), time_loss=_r(loss, 3),
            you=_public(fu), ref=_public(fr), issues=issues, snap=snap,
            clean=len(issues) == 0 and loss < 0.03,
        ))

    total_delta = float(u["t"][-1] - r["t"][-1])
    ranked = sorted(out_corners, key=lambda c: c["time_loss"], reverse=True)
    pos_total = sum(max(c["time_loss"], 0) for c in out_corners) or 1e-9
    top = [c for c in ranked[:3] if c["time_loss"] > 0.02]
    share = sum(c["time_loss"] for c in top) / pos_total if top else 0.0
    fixable = sum(max(c["time_loss"], 0) for c in out_corners if c["issues"])

    if total_delta <= 0.02:
        headline = "You are on the reference pace. Nice lap."
    elif top:
        names = ", ".join(c["name"] for c in top)
        headline = (f"You are {total_delta:.2f} s off the reference. {share * 100:.0f}% of the corner time loss "
                    f"comes from {names}.")
    else:
        headline = f"You are {total_delta:.2f} s off the reference, spread evenly across the lap."

    step = 1  # send every sample (900+ points is fine)
    traces = {
        "d": [_r(x, 1) for x in u["d"][::step]],
        "you": {k: [_r(x, 3) for x in u[k][::step]] for k in ("speed", "throttle", "brake", "steer")},
        "ref": {k: [_r(x, 3) for x in r[k][::step]] for k in ("speed", "throttle", "brake", "steer")},
        "delta": [_r(a - b, 3) for a, b in zip(u["t"][::step], r["t"][::step])],
    }

    return dict(
        summary=dict(
            you_time=_r(u["t"][-1], 3), ref_time=_r(r["t"][-1], 3), delta=_r(total_delta, 3),
            headline=headline,
            potential=dict(low=_r(fixable * 0.5, 2), high=_r(fixable, 2),
                           note="Estimated gain if the flagged issues were fixed. A range, not a promise."),
            track_length=_r(L, 0),
            grip_available=gmax is not None,
        ),
        corners=out_corners,
        ranking=[c["id"] for c in ranked],
        traces=traces,
        warnings=list(user_lap.get("warnings", [])) + list(ref_lap.get("warnings", [])),
    )
