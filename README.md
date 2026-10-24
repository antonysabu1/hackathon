# Apex Coach

An AI coach for sim racers. Upload your lap and a reference lap. The app shows where you lost speed,
groups the problem spots into zones, and an AI coach explains the biggest one in plain words.

## Parts

| Part | Where | What it does |
| --- | --- | --- |
| Backend | repo root (`main.py`, `analysis.py`, `database.py`, `claude_integration.py`, `coach_profile.py`) | FastAPI. Stores laps in SQLite, compares your lap to a reference by distance, asks Claude for coaching, keeps driver profiles and answers coach chat questions |
| Frontend | `frontend/` | React 18 + Vite. Charts, problem zones, coach panel, lap time leaderboard |

## Quick start on Windows (no commands to type)

Do the one-time setup first, then use the launcher every time after.

**One-time setup**

1. Install Python and Node.js, then open the project folder.
2. Install the packages: open PowerShell in the project folder and run `pip install -r requirements.txt`, then `cd frontend`, `npm.cmd install`, `cd ..`.
3. Create a file called `.env` in the project folder with one line: `ANTHROPIC_API_KEY=your-key-here`. Never commit this file or share the key.

**Every time**

1. Double-click **`start_apex.bat`** in the project folder.
2. Three windows open (backend, website, game recorder) and your browser opens the site after a few seconds.
3. Open Assetto Corsa and start a driving session. The recorder starts by itself, saves each lap as you finish it, and stops when you leave the session. Laps appear on the site automatically.

To stop everything, close the three windows. If the site shows "Not Found", an old backend is still running: open PowerShell, run `taskkill /F /IM python.exe`, close the windows and double-click `start_apex.bat` again.

The launcher records as the driver `Siva`. To use another name, open `start_apex.bat` in Notepad and change `--driver Siva`.

The sections below are the manual way of doing the same thing.

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
| `POST /profile/session` | Save car, setup, tyre and fuel details for a lap |
| `GET /profile/{driver}` | Profile grouped by track, then car, then laps |
| `POST /coach/chat` | Coach answers a question using the driver's saved laps |

The Vite dev server forwards `/api/...` to the backend on port 8000.

## Lap file format

```json
{ "lap_time": 92.456,
  "frames": [ { "t": 0.0, "speed": 180, "throttle": 1.0, "brake": 0.0, "steering": 0.0, "gear": 5, "dt": 0.01 } ] }
```

Speed is in km/h. Both laps must be complete laps of the same track.
The demo laps in `frontend/public/demo/` are synthetic, with deliberate mistakes.

## Profile and coach chat

`coach_profile.py` adds the profile and chat endpoints. `main.py` needs two extra lines after `app = FastAPI()`:

```python
from coach_profile import router as profile_router
app.include_router(profile_router)
```

Tyre wear and fuel are typed in by the driver (start and end of a stint), not read from the lap file, because the lap format has no tyre or fuel channels. Per lap numbers are worked out from those.
The coach gives general GT3 style advice, one change at a time, as an experiment to try. It does not know a specific car's exact setup ranges.

## Known limits

* A point is flagged when you are more than 15 km/h slower than the reference at the same distance.
  Most flagged points are labelled "cause unclear", because the rules only compare pedal and steering values at that point.
* Distance is integrated from speed, so small errors build up over a long lap.
* The coach comments only on the single biggest gap.
* `real_lap_1` to `real_lap_5.json` are slices of one long recording, not separate laps, so do not compare them with each other.

## Future work

Corner detection and cause rules (early brake, late throttle, snap), grip usage, a chat with the coach,
setup comparison, driver fingerprint, practice plans, live capture from the game, more sims.