from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import json
import database
from analysis import analyze_lap
from claude_integration import get_insight_from_claude
from parser import parse_assetto_corsa_telemetry
from analysis import analyze_lap

from coach_profile import router as profile_router

app = FastAPI()
app.include_router(profile_router)  # <-- this line must be here, after app = FastAPI()

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

@app.post("/analyze/{lap_id}")
def analyze(lap_id: int, reference_lap_id: int):
    your_lap = database.get_lap(lap_id)
    ref_lap = database.get_lap(reference_lap_id)
    
    if not your_lap or not ref_lap:
        return {"error": "Lap not found"}
    
    result = analyze_lap(your_lap["telemetry"], ref_lap["telemetry"])
    
    if result["worst_issue"]:
        issue = result["worst_issue"]

        coaching_text = get_insight_from_claude({}, {
            "corner": f"{issue['distance_m']}m mark",
            "issue": issue["issue_type"],
            "their_speed": issue["your_speed"],
            "ref_speed": issue["ref_speed"],
            "speed_delta": issue["speed_delta"]
        })
        database.save_insight(lap_id, f"distance_{issue['distance_m']}m", issue["issue_type"], coaching_text)    
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
