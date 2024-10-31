from fastapi import FastAPI, HTTPException, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import asyncpg
import os
from dotenv import load_dotenv
from datetime import datetime
from typing import List, Optional
from datetime import datetime as dt

# Load environment variables
load_dotenv()

# Database URL from environment variable
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in the environment variables.")

# FastAPI app instance
app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Function to connect to the PostgreSQL database
async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)

# Display form for adding a new event
@app.get("/add-event", response_class=HTMLResponse)
async def add_event_form(request: Request):
    return templates.TemplateResponse("add_event.html", {"request": request})

# Display all events
@app.get("/", response_class=HTMLResponse)
async def read_events(request: Request):
    conn = await get_db_connection()
    try:
        events = await conn.fetch("SELECT * FROM events ORDER BY date ASC, time ASC")
        event_list = [dict(event) for event in events]
    finally:
        await conn.close()
    return templates.TemplateResponse("index.html", {"request": request, "events": event_list})

# Create a new event
@app.post("/api/event/")
async def create_event(
    sport: str = Form(...),
    date: Optional[str] = Form(default_factory=lambda: dt.now().strftime("%Y-%m-%d")),
    time: Optional[str] = Form(default_factory=lambda: dt.now().strftime("%H:%M")),
    home_team: str = Form(...),
    away_team: str = Form(...),
    venue: Optional[str] = Form(None),
    event_details: Optional[str] = Form(None),
    player_details: Optional[str] = Form(None),
    team_details: Optional[str] = Form(None)
):
    conn = await get_db_connection()
    try:
        # Convert date string to a date object
        event_date = dt.strptime(date, "%Y-%m-%d").date() if date else dt.now().date()
        event_time = dt.strptime(time, "%H:%M").time() if time else dt.now().time()
        
        # Insert the new event into the database
        await conn.execute(
            """
            INSERT INTO events (sport, date, time, home_team, away_team, venue, event_details, player_details, team_details)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            sport, event_date, event_time, home_team, away_team, venue, event_details, player_details, team_details
        )
    except Exception as e:
        print(f"Error occurred: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An error occurred while creating the event.")
    finally:
        await conn.close()
    
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

# Route to get one event by ID
@app.get("/event/{event_id}", response_class=HTMLResponse)
async def get_event(event_id: int, request: Request):
    conn = await get_db_connection()
    try:
        event = await conn.fetchrow("SELECT * FROM events WHERE id = $1", event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="Event not found")
        event_data = dict(event)
    finally:
        await conn.close()
    return templates.TemplateResponse("event.html", {"request": request, "event": event_data})

# Route to filter events
@app.get("/events/", response_class=HTMLResponse)
async def get_events(request: Request, sport: Optional[str] = None, date: Optional[str] = None):
    conn = await get_db_connection()
    query = "SELECT * FROM events"
    params = []

    if sport or date:
        query += " WHERE"
    if sport:
        query += " sport = $1"
        params.append(sport)
    if date:
        if sport:
            query += " AND"
        query += " date = $2"
        params.append(date)

    try:
        events = await conn.fetch(query, *params)
        event_list = [dict(event) for event in events]
    finally:
        await conn.close()
    
    return templates.TemplateResponse("index.html", {"request": request, "events": event_list})

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
