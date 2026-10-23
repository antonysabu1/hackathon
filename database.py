import sqlite3
import json
from datetime import datetime

DB_FILE = "racing_telemetry.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('''
    CREATE TABLE IF NOT EXISTS drivers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    c.execute('''
    CREATE TABLE IF NOT EXISTS laps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        driver_id INTEGER NOT NULL,
        track TEXT NOT NULL,
        car TEXT NOT NULL,
        lap_time REAL,
        telemetry_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (driver_id) REFERENCES drivers(id)
    )
    ''')
    
    c.execute('''
    CREATE TABLE IF NOT EXISTS insights (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lap_id INTEGER NOT NULL,
        corner TEXT,
        issue TEXT,
        insight_text TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (lap_id) REFERENCES laps(id)
    )
    ''')
    
    c.execute('''
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lap_id INTEGER NOT NULL,
        question TEXT,
        answer TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (lap_id) REFERENCES laps(id)
    )
    ''')
    
    conn.commit()
    conn.close()

def get_or_create_driver(name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("SELECT id FROM drivers WHERE name = ?", (name,))
    result = c.fetchone()
    
    if result:
        driver_id = result[0]
    else:
        c.execute("INSERT INTO drivers (name) VALUES (?)", (name,))
        driver_id = c.lastrowid
    
    conn.commit()
    conn.close()
    return driver_id

def save_lap(driver_id, track, car, lap_time, telemetry_json):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('''
    INSERT INTO laps (driver_id, track, car, lap_time, telemetry_json)
    VALUES (?, ?, ?, ?, ?)
    ''', (driver_id, track, car, lap_time, json.dumps(telemetry_json)))
    
    lap_id = c.lastrowid
    conn.commit()
    conn.close()
    return lap_id

def get_lap(lap_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("SELECT * FROM laps WHERE id = ?", (lap_id,))
    result = c.fetchone()
    conn.close()
    
    if result:
        return {
            "id": result[0],
            "driver_id": result[1],
            "track": result[2],
            "car": result[3],
            "lap_time": result[4],
            "telemetry": json.loads(result[5]),
            "created_at": result[6]
        }
    return None

def get_leaderboard(limit=10):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('''
    SELECT l.id, d.name, l.lap_time, l.track, l.car, l.created_at
    FROM laps l
    JOIN drivers d ON l.driver_id = d.id
    ORDER BY l.lap_time ASC
    LIMIT ?
    ''', (limit,))
    
    results = c.fetchall()
    conn.close()
    
    return [
        {
            "lap_id": r[0],
            "driver": r[1],
            "lap_time": r[2],
            "track": r[3],
            "car": r[4],
            "created_at": r[5]
        }
        for r in results
    ]

def save_insight(lap_id, corner, issue, insight_text):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('''
    INSERT INTO insights (lap_id, corner, issue, insight_text)
    VALUES (?, ?, ?, ?)
    ''', (lap_id, corner, issue, insight_text))
    
    conn.commit()
    conn.close()

def get_insights(lap_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("SELECT corner, issue, insight_text FROM insights WHERE lap_id = ?", (lap_id,))
    results = c.fetchall()
    conn.close()
    
    return [{"corner": r[0], "issue": r[1], "insight": r[2]} for r in results]

init_db()

