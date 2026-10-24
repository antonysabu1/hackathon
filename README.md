# Apex Coach

An AI coach for sim racers. Upload your lap and a reference lap. The app shows where you lost speed,
groups the problem spots into zones, and an AI coach explains the biggest one in plain words.

## Parts

| Part | Where | What it does |
| --- | --- | --- |
| Backend | repo root (`main.py`, `analysis.py`, `database.py`, `claude_integration.py`) | FastAPI. Stores laps in SQLite, compares your lap to a reference by distance, asks Claude for coaching |
| Frontend | `frontend/` | React 18 + Vite. Charts, problem zones, coach panel, lap time leaderboard |

## Run it (Windows PowerShell)

**1. Backend, from the repo root**

```powershell
pip install -r requirements.txt
notepad .env
```

Put this line in `.env`, using your own key, then save. Never commit `.env` or share the key:

```
ANTHROPIC_API_KEY=your-key-here
```

The backend will not start without a key, because it creates the Claude client when it loads.

```powershell
python -m uvicorn main:app --port 8000
```

Check http://127.0.0.1:8000/health shows `{"status":"ok"}`.

**2. Frontend, in a second window**

```powershell
cd frontend
npm install
npm run dev
```

If PowerShell blocks npm, run `Set-ExecutionPolicy -Scope Process Bypass` first.
Open http://localhost:5173 and click **Try the demo laps**.

## Backend endpoints used by the frontend

| Endpoint | Used for |
| --- | --- |
| `GET /health` | Status pill |
| `POST /upload` (file, driver_name) | Save a lap, returns `lap_id`, `lap_time`, `sectors` |
| `POST /analyze/{lap_id}?reference_lap_id=` | Find slow points, ask Claude, returns `issues`, `worst_issue` |
| `GET /lap/{lap_id}` | Telemetry plus the saved coaching text (`insights`) |
| `GET /leaderboard` | Lap times only |

The Vite dev server forwards `/api/...` to the backend on port 8000.

## Lap file format

```json
{ "lap_time": 92.456,
  "frames": [ { "t": 0.0, "speed": 180, "throttle": 1.0, "brake": 0.0, "steering": 0.0, "gear": 5, "dt": 0.01 } ] }
```

Speed is in km/h. Both laps must be complete laps of the same track.
The demo laps in `frontend/public/demo/` are synthetic, with deliberate mistakes.

## Known limits

* A point is flagged when you are more than 15 km/h slower than the reference at the same distance.
  Most flagged points are labelled "cause unclear", because the rules only compare pedal and steering values at that point.
* Distance is integrated from speed, so small errors build up over a long lap.
* The coach comments only on the single biggest gap.
* `real_lap_1` to `real_lap_5.json` are slices of one long recording, not separate laps, so do not compare them with each other.

## Future work

Corner detection and cause rules (early brake, late throttle, snap), grip usage, a chat with the coach,
setup comparison, driver fingerprint, practice plans, live capture from the game, more sims.
