from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import json
import database
from parser import parse_assetto_corsa_telemetry
from analysis import analyze_lap

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/upload")
async def upload_lap(file: UploadFile = File(...), driver_name: str = "Driver", track: str = "Unknown", car: str = "Unknown"):
    try:
        contents = await file.read()
        telemetry_data = json.loads(contents)
        
        parsed = parse_assetto_corsa_telemetry(telemetry_data)
        
        driver_id = database.get_or_create_driver(driver_name)
        lap_id = database.save_lap(driver_id, track, car, parsed["lap_time"], telemetry_data)
        
        return {
            "status": "success",
            "lap_id": lap_id,
            "lap_time": parsed["lap_time"],
            "sectors": parsed["sectors"]
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/lap/{lap_id}")
def get_lap(lap_id: int):
    lap = database.get_lap(lap_id)
    if lap:
        insights = database.get_insights(lap_id)
        lap["insights"] = insights
        return lap
    return {"error": "Lap not found"}

@app.get("/leaderboard")
def leaderboard(limit: int = 10):
    return database.get_leaderboard(limit)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
