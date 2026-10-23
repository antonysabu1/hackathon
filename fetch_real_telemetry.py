import pandas as pd
import json

# Download the Spa-Francorchamps dataset (real Assetto Corsa telemetry)
url = "https://huggingface.co/datasets/Nasim435/spa-francorchamps-lap-data/resolve/main/telemetry.parquet"

print("Downloading real telemetry data...")
df = pd.read_parquet(url)

print(f"Loaded {len(df)} rows")
print(df.columns.tolist())

# Filter to just lap 1 (or adjust lap_progress logic to isolate one lap)
# This dataset is one continuous stream across 5 laps, so we need to find lap boundaries
# lap_progress resets to 0 at the start of each new lap
lap_starts = df[df['lap_progress'] < df['lap_progress'].shift(1)].index.tolist()

print(f"Detected lap boundaries at rows: {lap_starts[:5]}")

# Take the first full lap
if lap_starts:
    start = 0
    end = lap_starts[0] if lap_starts else len(df)
else:
    start = 0
    end = len(df)

lap_df = df.iloc[start:end]

# Convert to your app's expected JSON format
frames = []
for _, row in lap_df.iterrows():
    frames.append({
        "t": float(row.get("timestamp", 0)),
        "speed": float(row.get("speed_kmh", 0)),
        "throttle": float(row.get("throttle", 0)),
        "brake": float(row.get("brake", 0)),
        "steering": float(row.get("steer_angle", 0)),
        "gear": int(row.get("gear", 0)),
        "dt": 0.01  # 100Hz sampling = 10ms per frame
    })

lap_time = len(frames) * 0.01  # approx, based on frame count at 100Hz

output = {
    "lap_time": lap_time,
    "frames": frames
}

with open("real_telemetry_lap1.json", "w") as f:
    json.dump(output, f)

print(f"Saved {len(frames)} frames to real_telemetry_lap1.json")
print(f"Approx lap time: {lap_time:.2f}s")
