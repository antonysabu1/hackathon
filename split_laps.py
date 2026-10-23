import json

with open("real_telemetry_lap1.json") as f:
    data = json.load(f)

frames = data["frames"]
total_frames = len(frames)

# Split into 5 equal segments (5 recorded laps in this dataset)
num_laps = 5
chunk_size = total_frames // num_laps

for lap_num in range(num_laps):
    start = lap_num * chunk_size
    end = (lap_num + 1) * chunk_size if lap_num < num_laps - 1 else total_frames
    
    lap_frames = frames[start:end]
    
    # Normalize timestamps to start from 0 for this lap
    first_t = lap_frames[0]["t"]
    for fr in lap_frames:
        fr["t"] = fr["t"] - first_t
    
    lap_time = lap_frames[-1]["t"]
    
    output = {
        "lap_time": lap_time,
        "frames": lap_frames
    }
    
    filename = f"real_lap_{lap_num + 1}.json"
    with open(filename, "w") as f:
        json.dump(output, f)
    
    print(f"Lap {lap_num + 1}: {len(lap_frames)} frames, {lap_time:.2f}s -> {filename}")
