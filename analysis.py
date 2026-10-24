import numpy as np

def compute_distance(frames):
    """Compute cumulative distance traveled (in meters) for each frame."""
    distances = [0.0]
    for i in range(1, len(frames)):
        speed_ms = frames[i]["speed"] / 3.6  # kph to m/s
        dt = frames[i].get("dt", 0.01)
        distances.append(distances[-1] + speed_ms * dt)
    return distances


def resample_by_distance(frames, distances, grid):
    """Resample telemetry fields onto a fixed distance grid via interpolation."""
    speed = np.interp(grid, distances, [f["speed"] for f in frames])
    throttle = np.interp(grid, distances, [f["throttle"] for f in frames])
    brake = np.interp(grid, distances, [f["brake"] for f in frames])
    steering = np.interp(grid, distances, [f["steering"] for f in frames])
    time = np.interp(grid, distances, [f["t"] for f in frames])

    resampled = []
    for i in range(len(grid)):
        resampled.append({
            "distance": grid[i],
            "speed": speed[i],
            "throttle": throttle[i],
            "brake": brake[i],
            "steering": steering[i],
            "t": time[i]
        })
    return resampled


def analyze_lap(your_telemetry, reference_telemetry):
    your_frames = your_telemetry.get("frames", [])
    ref_frames = reference_telemetry.get("frames", [])

    your_distances = compute_distance(your_frames)
    ref_distances = compute_distance(ref_frames)

    # Don't extrapolate past whichever lap covered less ground
    max_distance = min(your_distances[-1], ref_distances[-1])

    # Scale buffer and step size to the lap's actual length (works for both short test laps and long real ones)
    buffer = max(2.0, max_distance * 0.05)  # 5% of lap length, minimum 2m
    step = max(0.5, max_distance / 100)      # about 100 sample points across the lap

    if max_distance <= buffer * 2:
        # Lap too short for buffering, just use the whole thing
        grid = np.arange(0, max_distance, step)
    else:
        grid = np.arange(buffer, max_distance - buffer, step)
    your_resampled = resample_by_distance(your_frames, your_distances, grid)
    ref_resampled = resample_by_distance(ref_frames, ref_distances, grid)

    issues = []

    for i in range(len(grid)):
        your_point = your_resampled[i]
        ref_point = ref_resampled[i]

        speed_delta = ref_point["speed"] - your_point["speed"]
        brake_delta = your_point["brake"] - ref_point["brake"]
        throttle_delta = ref_point["throttle"] - your_point["throttle"]

        if 15 < speed_delta < 80:
            issue_type = classify_issue(your_point, ref_point, speed_delta, brake_delta, throttle_delta)
            issues.append({
                "distance_m": round(float(grid[i]), 1),
                "time": round(float(your_point["t"]), 2),
                "your_speed": round(float(your_point["speed"]), 1),
                "ref_speed": round(float(ref_point["speed"]), 1),
                "speed_delta": round(float(speed_delta), 1),
                "issue_type": issue_type
            })

    worst_issue = max(issues, key=lambda x: x["speed_delta"]) if issues else None

    return {
        "issues": issues,
        "worst_issue": worst_issue,
        "total_issues_found": len(issues)
    }


def classify_issue(your_point, ref_point, speed_delta, brake_delta, throttle_delta):
    if brake_delta > 0.2:
        return "braking_too_hard_or_too_late"
    elif throttle_delta > 0.2:
        return "throttle_too_conservative"
    elif your_point["steering"] > ref_point["steering"] + 0.2:
        return "excess_steering_input"
    else:
        return "unclear_technique_issue"
