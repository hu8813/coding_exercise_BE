from fastapi import FastAPI, HTTPException, Request, Form, status, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import asyncpg
import os
from dotenv import load_dotenv
from datetime import datetime
from typing import List, Optional

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

# Function to initialize the database tables
async def initialize_database(conn):
    # Create tables
    try:
        await conn.execute("""CREATE TABLE IF NOT EXISTS teams (
            team_id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            details TEXT
        );""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS venues (
            venue_id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            location VARCHAR(255) NOT NULL,
            capacity INTEGER
        );""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS events (
            event_id SERIAL PRIMARY KEY,
            sport_type VARCHAR(255) NOT NULL,
            event_date DATE NOT NULL,
            event_time TIME NOT NULL,
            home_team_id INTEGER REFERENCES teams(team_id),
            away_team_id INTEGER REFERENCES teams(team_id),
            venue_id INTEGER REFERENCES venues(venue_id),
            description TEXT
        );""")
    except Exception as e:
        print(f"Error occurred while initializing the database: {e}")

# Use lifespan event handler to manage database initialization
@app.on_event("startup")
async def startup_event():
    conn = await get_db_connection()  # Get the database connection
    try:
        await initialize_database(conn)
    finally:
        await conn.close()  # Ensure the connection is closed after initialization

# Dependency to get the database connection
async def get_db_connection_dependency():
    conn = await get_db_connection()
    try:
        yield conn
    finally:
        await conn.close()  # Close the connection after use

# Fetch teams from the database
async def get_teams(conn):
    try:
        teams = await conn.fetch("SELECT team_id, name FROM teams")
        return [dict(team) for team in teams]  # Convert to a list of dictionaries
    except Exception as e:
        print(f"Error fetching teams: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error fetching teams")

# Fetch venues from the database
async def get_venues(conn):
    try:
        venues = await conn.fetch("SELECT venue_id, name FROM venues")
        return [dict(venue) for venue in venues]  # Convert to a list of dictionaries
    except Exception as e:
        print(f"Error fetching venues: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error fetching venues")

# Fetch events from the database
async def get_events(conn):
    try:
        events = await conn.fetch("SELECT * FROM events ORDER BY event_date ASC, event_time ASC")
        return [dict(event) for event in events]  # Convert to a list of dictionaries
    except Exception as e:
        print(f"Error fetching events: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error fetching events")

# Display form for adding a new event
@app.get("/add-event", response_class=HTMLResponse)
async def add_event_form(request: Request, conn=Depends(get_db_connection_dependency)):
    teams = await get_teams(conn)  # Fetch teams
    venues = await get_venues(conn)  # Fetch venues
    return templates.TemplateResponse("add_event.html", {"request": request, "teams": teams, "venues": venues})

# Display all events (home page)
@app.get("/", response_class=HTMLResponse)
async def read_events(request: Request, conn=Depends(get_db_connection_dependency)):
    events = await get_events(conn)  # Fetch events
    return templates.TemplateResponse("index.html", {"request": request, "events": events})

@app.post("/api/event/")
async def create_event(
    sport_type: str = Form(...),
    event_date: Optional[str] = Form(None),  # Pass date as string in form
    event_time: Optional[str] = Form(None),  # Pass time as string in form
    home_team_id: int = Form(...),
    away_team_id: int = Form(...),
    venue_id: int = Form(...),
    description: Optional[str] = Form(None),
    conn=Depends(get_db_connection_dependency)
):
    # Debugging: Log the received data
    print("Received Data:")
    print(f"Sport Type: {sport_type}")
    print(f"Event Date: {event_date}")
    print(f"Event Time: {event_time}")
    print(f"Home Team ID: {home_team_id}")
    print(f"Away Team ID: {away_team_id}")
    print(f"Venue ID: {venue_id}")
    print(f"Description: {description}")

    # Default date and time if not provided
    event_date_obj = datetime.strptime(event_date, "%Y-%m-%d").date() if event_date else datetime.now().date()
    event_time_obj = datetime.strptime(event_time, "%H:%M").time() if event_time else datetime.now().time()

    # Proceed to insert event (assuming required foreign key validation exists)
    try:
        await conn.execute(
            """
            INSERT INTO events (sport_type, event_date, event_time, home_team_id, away_team_id, venue_id, description)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            sport_type, event_date_obj, event_time_obj, home_team_id, away_team_id, venue_id, description
        )
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error creating event")

    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
