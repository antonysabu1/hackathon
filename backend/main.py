import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import analysis
import chat
import store
from lap_io import LapError, parse_lap
from sample_data import make_laps

load_dotenv()

app = FastAPI(title="Apex Coach API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _run(user_lap, ref_lap):
    try:
        result = analysis.analyze(user_lap, ref_lap)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    result["id"] = store.save(result)
    return result


@app.get("/api/health")
def health():
    return {"ok": True, "claude": bool(os.getenv("ANTHROPIC_API_KEY", "").strip())}


@app.get("/api/sample")
def sample():
    ref, drv = make_laps()
    return _run(drv, ref)


@app.post("/api/analyze")
async def analyze_upload(lap: UploadFile = File(...), reference: Optional[UploadFile] = File(None)):
    try:
        user_lap = parse_lap(await lap.read(), lap.filename or "your lap")
        if reference is not None and reference.filename:
            ref_lap = parse_lap(await reference.read(), reference.filename)
        else:
            ref_lap, _ = make_laps()
    except LapError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _run(user_lap, ref_lap)


class ChatIn(BaseModel):
    analysis_id: str
    message: str
    history: list = []


@app.post("/api/chat")
def chat_endpoint(body: ChatIn):
    data = store.load(body.analysis_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Analysis not found. Upload a lap again.")
    return chat.reply(data, body.message, body.history)
