from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import sqlite3

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Database setup
DATABASE = "events.db"

def init_db():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sport TEXT NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                venue TEXT NOT NULL
            )
        ''')
        conn.commit()

@app.on_event("startup")
def startup_event():
    init_db()

# Pydantic model for the event data
class Event(BaseModel):
    sport: str
    date: str
    time: str
    home_team: str
    away_team: str
    venue: str

# Route to add a new event
@app.post("/event/")
async def add_event(
    sport: str = Form(...),
    date: str = Form(...),
    time: str = Form(...),
    home_team: str = Form(...),
    away_team: str = Form(...),
    venue: str = Form(...)
):
    try:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO events (sport, date, time, home_team, away_team, venue)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (sport, date, time, home_team, away_team, venue))
            conn.commit()
        return {"message": "Event added successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Route to get all events with optional filters
@app.get("/events/")
async def get_events(request: Request, sport: Optional[str] = None, date: Optional[str] = None):
    query = "SELECT * FROM events"
    params = []

    if sport or date:
        query += " WHERE"
    if sport:
        query += " sport = ?"
        params.append(sport)
    if date:
        if sport:
            query += " AND"
        query += " date = ?"
        params.append(date)

    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        events = [{"id": row[0], "sport": row[1], "date": row[2], "time": row[3], "home_team": row[4], "away_team": row[5], "venue": row[6]} for row in rows]
    
    return templates.TemplateResponse("events.html", {"request": request, "events": events})

# Route to get one event by ID
@app.get("/event/{event_id}")
async def get_event(event_id: int, request: Request):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Event not found")
        event = {
            "id": row[0], "sport": row[1], "date": row[2], "time": row[3],
            "home_team": row[4], "away_team": row[5], "venue": row[6]
        }
    return templates.TemplateResponse("event.html", {"request": request, "event": event})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
