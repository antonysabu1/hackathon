def parse_assetto_corsa_telemetry(telemetry_json):
    lap_time = telemetry_json.get("lap_time", 0)
    frames = telemetry_json.get("frames", [])
    
    sectors = []
    if frames:
        sector_size = len(frames) // 3
        for i in range(3):
            start = i * sector_size
            end = (i + 1) * sector_size if i < 2 else len(frames)
            sector_frames = frames[start:end]
            sector_time = sum(f.get("dt", 0) for f in sector_frames)
            sectors.append({"sector": i+1, "time": sector_time})
    
    return {
        "lap_time": lap_time,
        "sectors": sectors,
        "frame_count": len(frames)
    }

