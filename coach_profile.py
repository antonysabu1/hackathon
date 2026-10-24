"""Driver profiles, session details (car, setup, tyres, fuel) and the AI coach chat.

This file plugs into the existing FastAPI app with two lines in main.py:

    from coach_profile import router as profile_router
    app.include_router(profile_router)

It uses the same SQLite file as database.py and adds its own tables, so nothing else changes.
"""
import json
import sqlite3
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

import database

router = APIRouter()


# ---------------------------------------------------------------- storage

def _conn():
    conn = sqlite3.connect(database.DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_tables():
    conn = _conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lap_id INTEGER NOT NULL,
            driver TEXT NOT NULL,
            track TEXT NOT NULL,
            car TEXT NOT NULL,
            setup_json TEXT,
            tyre_json TEXT,
            fuel_json TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


init_tables()


def _num(v):
    """Turn form input into a float, or None when it is empty or not a number."""
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def derive(tyre: dict, fuel: dict) -> dict:
    """Per lap fuel use and tyre wear, from the start/end values the driver typed in."""
    out = {}
    laps = _num(tyre.get("laps_run")) or _num(fuel.get("laps_run"))
    f0, f1 = _num(fuel.get("start")), _num(fuel.get("end"))
    if laps and laps > 0 and f0 is not None and f1 is not None and f0 >= f1:
        out["fuel_per_lap"] = round((f0 - f1) / laps, 2)
    w0, w1 = _num(tyre.get("wear_start")), _num(tyre.get("wear_end"))
    if laps and laps > 0 and w0 is not None and w1 is not None and w1 >= w0:
        out["wear_per_lap"] = round((w1 - w0) / laps, 2)
    return out


def save_session(lap_id, driver, track, car, setup, tyre, fuel, notes):
    conn = _conn()
    cur = conn.execute(
        "INSERT INTO sessions (lap_id, driver, track, car, setup_json, tyre_json, fuel_json, notes)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (lap_id, driver, track, car, json.dumps(setup), json.dumps(tyre), json.dumps(fuel), notes),
    )
    sid = cur.lastrowid
    conn.commit()
    conn.close()
    return sid


def list_sessions(driver: str):
    conn = _conn()
    rows = conn.execute(
        "SELECT s.*, l.lap_time FROM sessions s LEFT JOIN laps l ON l.id = s.lap_id"
        " WHERE lower(s.driver) = lower(?) ORDER BY s.id DESC",
        (driver,),
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        tyre = json.loads(r["tyre_json"] or "{}")
        fuel = json.loads(r["fuel_json"] or "{}")
        out.append(
            {
                "id": r["id"],
                "lap_id": r["lap_id"],
                "track": r["track"],
                "car": r["car"],
                "lap_time": r["lap_time"],
                "setup": json.loads(r["setup_json"] or "{}"),
                "tyre": tyre,
                "fuel": fuel,
                "derived": derive(tyre, fuel),
                "notes": r["notes"] or "",
                "created_at": r["created_at"],
            }
        )
    return out


def group_by_track(sessions):
    """track -> car -> sessions, with the best lap of each car."""
    tracks = {}
    for s in sessions:
        cars = tracks.setdefault(s["track"], {})
        cars.setdefault(s["car"], []).append(s)
    result = []
    for track, cars in tracks.items():
        car_list = []
        for car, items in cars.items():
            times = [x["lap_time"] for x in items if x["lap_time"]]
            car_list.append({"car": car, "best": min(times) if times else None, "sessions": items})
        car_list.sort(key=lambda c: (c["best"] is None, c["best"] or 0))
        result.append({"track": track, "cars": car_list})
    return result


# ---------------------------------------------------------------- AI coach

COACH_RULES = """You are Apex Coach, a friendly sim racing coach. The driver is a beginner who does not know how to build a setup.

How to answer:
* Use plain words. Explain any racing term the first time you use it.
* Use only the sessions listed below. If the data does not show something, say so. Never invent lap times, setup values or telemetry.
* Before blaming the setup, check whether their inputs could explain the problem (braking too late, throttle too early, abrupt steering). Say which it looks like and why.
* When you suggest a setup change, suggest ONE change at a time, say which direction and a small step (for example "1 or 2 clicks"), explain what it should do in simple terms, and say what to watch for on the next laps.
* Setup advice depends on the car and the track. Call it an experiment to try, not a guaranteed fix. Setup menus differ between games, so tell them to look for the setting by name.
* Tyre wear and fuel numbers are typed in by the driver, so treat them as approximate.
* Keep it short: at most about 150 words unless they ask for detail. Do not use dashes as punctuation."""


def build_context(driver: str, track: Optional[str], car: Optional[str], lap_id: Optional[int]) -> str:
    sessions = list_sessions(driver)
    if track:
        sessions = [s for s in sessions if s["track"].lower() == track.lower()]
    if car:
        sessions = [s for s in sessions if s["car"].lower() == car.lower()]
    sessions = sessions[:12]
    if not sessions:
        return "No saved sessions for this driver yet."
    lines = []
    for s in sessions:
        lt = f"{s['lap_time']:.3f}s" if s["lap_time"] else "unknown"
        setup = ", ".join(f"{k}={v}" for k, v in s["setup"].items() if v not in ("", None)) or "not recorded"
        tyre = ", ".join(f"{k}={v}" for k, v in s["tyre"].items() if v not in ("", None)) or "not recorded"
        fuel = ", ".join(f"{k}={v}" for k, v in s["fuel"].items() if v not in ("", None)) or "not recorded"
        extra = ", ".join(f"{k}={v}" for k, v in s["derived"].items())
        insights = database.get_insights(s["lap_id"])
        found = "; ".join(f"{i['issue']} ({i['corner']}): {i['insight']}" for i in insights) or "none saved"
        lines.append(
            f"Lap #{s['lap_id']}{' (the lap on screen)' if lap_id == s['lap_id'] else ''}: track {s['track']}, car {s['car']}, "
            f"lap time {lt}. Setup: {setup}. Tyres: {tyre}. Fuel: {fuel}. Derived: {extra or 'n/a'}. "
            f"Driver notes: {s['notes'] or 'none'}. Coach findings vs reference: {found}."
        )
    return "\n".join(lines)


def ask_claude(driver, question, track, car, lap_id, history):
    from claude_integration import client  # imported late so the profile pages work without it

    system = COACH_RULES + "\n\nSaved sessions for " + driver + ":\n" + build_context(driver, track, car, lap_id)
    messages = []
    for m in (history or [])[-8:]:
        if m.get("role") in ("user", "assistant") and m.get("text"):
            messages.append({"role": m["role"], "content": m["text"]})
    messages.append({"role": "user", "content": question})
    res = client.messages.create(model="claude-sonnet-5-5", max_tokens=700, system=system, messages=messages)
    for block in res.content:
        if block.type == "text":
            return block.text
    return "No answer came back."


# ---------------------------------------------------------------- API

class SessionIn(BaseModel):
    lap_id: int
    driver: str
    track: str = "Unknown"
    car: str = "Unknown"
    setup: dict = Field(default_factory=dict)
    tyre: dict = Field(default_factory=dict)
    fuel: dict = Field(default_factory=dict)
    notes: str = ""


class ChatIn(BaseModel):
    driver: str
    question: str
    track: Optional[str] = None
    car: Optional[str] = None
    lap_id: Optional[int] = None
    history: list = Field(default_factory=list)


@router.post("/profile/session")
def add_session(body: SessionIn):
    sid = save_session(body.lap_id, body.driver, body.track, body.car, body.setup, body.tyre, body.fuel, body.notes)
    return {"status": "success", "session_id": sid}


@router.get("/profile/{driver}")
def get_profile(driver: str):
    sessions = list_sessions(driver)
    return {"driver": driver, "total_sessions": len(sessions), "tracks": group_by_track(sessions)}


@router.post("/coach/chat")
def coach_chat(body: ChatIn):
    q = body.question.strip()
    if not q:
        return {"status": "error", "message": "Ask a question first."}
    try:
        answer = ask_claude(body.driver, q, body.track, body.car, body.lap_id, body.history)
    except Exception as e:  # missing key, network, quota
        return {"status": "error", "message": f"The coach could not answer: {e}"}
    try:
        conn = _conn()
        conn.execute(
            "INSERT INTO chat_history (lap_id, question, answer) VALUES (?, ?, ?)", (body.lap_id or 0, q, answer)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass
    return {"status": "success", "answer": answer}
