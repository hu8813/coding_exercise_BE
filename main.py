from fastapi import FastAPI, HTTPException, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import sqlite3
import os
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Serve static files from the "static" directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Database file path
DATABASE = "events.db"

# Initialize the database connection
def init_db():
    try:
        # Create the database file if it doesn't exist
        if not os.path.exists(DATABASE):
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
                        venue TEXT
                    )
                ''')
                conn.commit()
    except sqlite3.Error as e:
        print(f"Error initializing database: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database initialization failed.")

# Call the initialization function at startup
@app.on_event("startup")
def startup_event():
    init_db()

# Display form for adding a new event
@app.get("/add-event", response_class=HTMLResponse)
async def add_event_form(request: Request):
    return templates.TemplateResponse("add_event.html", {"request": request})

# Add error-handling and data validation to the event creation route
@app.post("/event/")
async def create_event(
    sport: str = Form(...),
    date: str = Form(...),
    time: str = Form(...),
    home_team: str = Form(...),
    away_team: str = Form(...),
    venue: str = Form(None)
):
    try:
        # Validate date format (YYYY-MM-DD)
        datetime.strptime(date, "%Y-%m-%d")
        # Validate time format (HH:MM)
        datetime.strptime(time, "%H:%M")

        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO events (sport, date, time, home_team, away_team, venue)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (sport, date, time, home_team, away_team, venue))
            conn.commit()

        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to add event to the database.")
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred.")

# Display all events
@app.get("/", response_class=HTMLResponse)
async def read_events(request: Request):
    try:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM events ORDER BY date ASC, time ASC")
            rows = cursor.fetchall()
            events = [{"id": row[0], "sport": row[1], "date": row[2], "time": row[3], "home_team": row[4], "away_team": row[5], "venue": row[6]} for row in rows]
        return templates.TemplateResponse("index.html", {"request": request, "events": events})
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch events.")

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

    try:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            events = [{"id": row[0], "sport": row[1], "date": row[2], "time": row[3], "home_team": row[4], "away_team": row[5], "venue": row[6]} for row in rows]
        
        return templates.TemplateResponse("events.html", {"request": request, "events": events})
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch events.")

# Route to get one event by ID
@app.get("/event/{event_id}")
async def get_event(event_id: int, request: Request):
    try:
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
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch event.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
