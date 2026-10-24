# Apex Coach

An AI coach for sim racers. It records your laps straight from Assetto Corsa, finds the turns where you are slow, and explains in plain words what to try next.

Built for a hackathon by two people with no prior coding background: one on the frontend, one on the backend.

## The problem

Sim racing telemetry tools show a lot of lines and numbers, and they assume you already know how to read them. A beginner sees a speed trace and a brake trace and has no idea what to change. Setup advice is even harder, because setup menus are full of settings with names like "bump stop rate" and "packer range".

## The idea

Make the data readable for a beginner, and make it automatic:

1. **No typing.** Drive in Assetto Corsa. Laps, car, track, setup, tyre wear and fuel use are captured and saved on their own.
2. **Show where time is lost.** Compare any lap to your own best lap, find every turn, and show how many tenths you lose in each one.
3. **Say why, in plain words.** Rule based checks look at braking, throttle and steering at each slow spot. An AI coach explains the biggest one and answers questions about your saved laps and setups.

## What it does

* **Live lap recording** from Assetto Corsa. Starts when you begin a driving session, saves each completed lap, and stops when you leave the session. No buttons to press.
* **Valid and invalid laps.** Laps with the car off the track, or that the game did not count, are marked invalid and hidden by default. Your best time and comparisons use valid laps only.
* **Driver profile** grouped by track, then by car, then by lap. Each lap shows its setup, tyre compound and wear, fuel per lap, and weather.
* **Lap comparison** with speed, throttle, brake, steering and time gap charts, plus extra channels from the game (RPM, G forces, tyre slip, tyre and brake temperatures, suspension, fuel).
* **Turn by turn panel.** Every turn with the time you lose or gain against the reference, and your slowest speed in it against theirs. Slow turns are tagged and shown on a track map.
* **Problem zones.** Spots where you are more than 15 km/h slower than the reference, each labelled with the likely cause (braking too hard or late, throttle too cautious, too much steering, or unclear).
* **Ask the coach.** A chat box that answers questions about your saved sessions, one setup change at a time, as an experiment to try.
* **Leaderboard** of lap times.
* **One click launcher** for Windows (`start_apex.bat`).

## How it works

```
Assetto Corsa  ->  ac_recorder.py  ->  FastAPI backend  ->  SQLite database
 (shared memory)    (splits laps,       (/upload,            (laps, sessions,
                     checks validity,    /profile,            insights, chat)
                     reads setup file)   /analyze,
                                         /coach/chat)             |
                                                                  v
                                     React website  <--  Claude API (coaching text and chat)
```

1. Assetto Corsa publishes live car data in Windows shared memory. `ac_recorder.py` reads it about 60 times a second.
2. When a lap ends, the recorder saves it as a JSON file in `recorded_laps/` and sends it to the backend. Laps wait in a `pending` folder and are retried if the backend is off.
3. The backend stores the lap and its session details. When you ask for an analysis, it lines up two laps by distance, flags slow points, and asks Claude to explain the worst one.
4. The website polls for new laps and shows them as they arrive.

## Tech stack and tools

| Area | What we used |
| --- | --- |
| Game data | Assetto Corsa shared memory, read with Python `ctypes` (standard library only) |
| Recorder | Python 3 |
| Backend | Python, FastAPI, Uvicorn, Pydantic |
| Database | SQLite |
| AI coach | Anthropic Claude API (`claude-sonnet-5-5`) |
| Frontend | React 18, Vite, plain CSS, hand built SVG charts |
| Windows launcher | Batch file (`start_apex.bat`) |
| Development | Claude Code and Claude for writing and testing parts of the code, GitHub for the repo |

## Quick start on Windows (no commands to type)

**One time setup**

1. Install Python and Node.js.
2. In the project folder, create a file called `.env` with one line: `ANTHROPIC_API_KEY=your-key-here`. Never commit this file or share the key.

**Every time**

1. Double click **`start_apex.bat`**. The first run installs the website packages, which takes a few minutes.
2. Three windows open (backend, website, recorder) and your browser opens the site.
3. Start Assetto Corsa and begin a driving session. Laps appear on the site as you finish them.

To stop everything, close the three windows. If the site shows "Not Found", an old backend is still running. Open PowerShell, run `taskkill /F /IM python.exe`, close the windows and start `start_apex.bat` again.

The launcher records as the driver `Siva`. To change the name, edit `--driver Siva` in `start_apex.bat`.

No game handy? Open the site and click **Try the demo laps**.

## Run it by hand (Windows PowerShell)

```powershell
pip install -r requirements.txt
python -m uvicorn main:app --port 8000
```

Check http://127.0.0.1:8000/health shows `{"status":"ok"}`. In a second window:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open http://localhost:5173. In a third window, `python ac_recorder.py --driver YourName` starts the recorder.
`python ac_recorder.py --fake` replays the demo laps through the recorder to test it without the game.

## Backend endpoints

| Endpoint | Used for |
| --- | --- |
| `GET /health` | Status pill |
| `POST /upload` | Save a lap, returns `lap_id` and `lap_time` |
| `POST /analyze/{lap_id}?reference_lap_id=` | Find slow points, ask Claude, returns `issues` and `worst_issue` |
| `GET /lap/{lap_id}` | Telemetry plus saved coaching text |
| `GET /leaderboard` | Lap times |
| `POST /profile/session` | Save car, setup, tyre, fuel and validity for a lap |
| `GET /profile/{driver}` | Profile grouped by track, then car, then laps |
| `POST /coach/chat` | Coach answers a question using the driver's saved laps |

The Vite dev server forwards `/api/...` to the backend on port 8000.

## Lap file format

```json
{ "lap_time": 92.456,
  "frames": [ { "t": 0.0, "speed": 180, "throttle": 1.0, "brake": 0.0, "steering": 0.0, "gear": 5, "dt": 0.01 } ] }
```

Speed is in km/h. Recorded laps add many more channels plus car, track, setup, `valid` and `invalid_reason`.

## What is new and what is not

Telemetry readers and lap comparison tools already exist (Assetto Corsa apps, Motec, Garage 61 and others). We are not claiming to have invented lap comparison. What we built is the combination for beginners: automatic capture with no typing, a per turn list of where time is lost, and plain language coaching that stays tied to the driver's own saved laps and setups.

## Known limits

* **Invalid laps are inferred.** Assetto Corsa does not publish an "invalid lap" flag, so a lap is marked invalid when 3 or more tyres are off the track for 0.3 seconds or more, or when the game did not count a lap that should have been a new best. Some invalid laps can slip through, and an odd clean lap could be flagged.
* **Setup is a best guess.** The recorder uses the newest saved setup file for that car and track. If none is found, the lap is treated as the stock setup.
* **Tyre wear direction and some channels were not checked against the game for every car.**
* **Distance is integrated from speed**, so small errors build up over a long lap.
* **Cause labels are rule based.** Many slow points come out as "cause unclear", because the rules only compare pedal and steering values at that point.
* **The coach gives general advice.** It does not know a specific car's exact setup ranges, and treats every setup change as an experiment.
* **Windows and Assetto Corsa only** for live capture.
* **The demo laps** in `frontend/public/demo/` are synthetic, made with deliberate mistakes, and are not real driving. Laps in `recorded_laps/` are real.
* `real_lap_1.json` to `real_lap_5.json` are slices of one long recording, not separate laps.

## Future work

Cause rules for more situations, grip usage, setup A against setup B, a driver fingerprint, practice plans, reference laps from other drivers, an in game app to read the true invalid lap flag, and other sims.

## Team

* Frontend, game recorder and coach: Siva Gireesh
* Backend: teammate

## Credits

Built with the Anthropic Claude API, FastAPI, React, Vite, and the Assetto Corsa shared memory interface.
