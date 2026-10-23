import json

with open("real_telemetry_lap1.json") as f:
    data = json.load(f)

frames = data["frames"]
print(f"Total frames: {len(frames)}")
print(f"Lap time (calculated): {data['lap_time']}")

print("\nFirst 5 frames:")
for f in frames[:5]:
    print(f)

print("\nLast 5 frames:")
for f in frames[-5:]:
    print(f)

speeds = [fr["speed"] for fr in frames]
print(f"\nSpeed range: {min(speeds)} to {max(speeds)} kph")

# Check how many times speed drops to near-zero (possible lap-start/finish or pit)
near_zero = [i for i, s in enumerate(speeds) if s < 5]
print(f"\nFrames with speed < 5 kph: {len(near_zero)}")
print(f"First few indices: {near_zero[:20]}")
