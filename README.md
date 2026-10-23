# Apex Coach

An AI coach for sim racers. It reads a lap, compares it with a reference, finds where the time went,
names the cause in plain words, and tells you whether a snap or spin is your inputs or the car setup.

## How it works

1. **Parse**: `lap_io.py` reads a telemetry CSV (most export column names work).
2. **Analyse**: `analysis.py` finds the corners, measures brake point, brake release, minimum speed,
   throttle pickup, grip usage and counter steering, then diagnoses each corner with explainable rules.
3. **Explain**: `chat.py` sends only the computed findings to Claude, which turns them into coaching.
   The LLM never reads raw telemetry, so the numbers stay correct.
4. **Show**: a React dashboard with linked charts, a ranked list of corner losses and a coach chat.

Without an API key the chat falls back to a rule based coach, so the demo never breaks.

## Tech stack

| Layer | Choice |
| --- | --- |
| Backend | Python, FastAPI, NumPy, pandas, SQLite |
| AI | Claude API for explanation, rule based diagnosis for the numbers |
| Frontend | React 18, Vite, hand built SVG charts, plain CSS |

## Run it on Windows (PowerShell)

Install once: Python 3.11+ (tick "Add python.exe to PATH"), Node.js LTS, Git.

**Terminal 1, backend**

```powershell
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
notepad .env
uvicorn main:app --reload --port 8000
```

If Activate.ps1 is blocked, run `Set-ExecutionPolicy -Scope Process Bypass` first.
In `.env`, paste your key after `ANTHROPIC_API_KEY=`. Never commit `.env` or share the key.
You can skip the key to test, the app then uses the offline coach.

**Terminal 2, frontend**

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and click **Try the sample lap**.

Check the backend at http://127.0.0.1:8000/api/health

## Using your own laps

The sample is a synthetic lap with deliberate mistakes (early brake in T3, abrupt brake release and snap in T4,
late throttle in T5, unused grip in T2). Assetto Corsa does not export CSV by itself. Tools like Content Manager,
ACTI or MoTeC export laps to CSV. Needed columns: speed plus distance or time. Better: throttle, brake, steer, g_lat, g_lon.
`python sample_data.py` writes example files into `backend/sample_laps/` showing the format.

## What is built vs future work

Built: upload, linked traces, corner detection, cause diagnosis, snap detection with driver vs setup reasoning,
grip usage, projected gain range, coach chat.

Future work: live capture from the game, setup file parsing and A/B setup comparison, driver fingerprint across
sessions, similar driver comparison, lap time only leaderboards with private telemetry, practice plans,
more sims (iRacing, ACC, F1 25).

## Honest limits

* Cause rules are thresholds tuned on synthetic laps, they need validation on real laps.
* The projected gain is an estimate shown as a range.
* Setup advice is a list of experiments to try one at a time, not a guaranteed fix.
* Grip usage is relative to the best grip seen across the two laps, not an absolute tyre limit.

## Questions judges may ask

* **Why rules and not ML?** Rules are explainable and deterministic. We keep the LLM away from raw numbers
  so it cannot invent telemetry. ML for driver profiling is the next step once we have user data.
* **What is new?** Not the telemetry viewer, that exists. The new part is cause diagnosis, checking inputs before
  blaming the setup, and verifying setup changes over several laps.
* **Does it need the game?** No, it reads exported lap files.
