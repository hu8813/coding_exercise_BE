from fastapi import FastAPI, HTTPException, Request, Form, status, Depends, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import asyncpg
import os
from dotenv import load_dotenv
from datetime import datetime
from typing import List, Optional

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in the environment variables.")

app = FastAPI()
templates = Jinja2Templates(directory="templates")

PASSWORD = os.getenv('ADMIN_PWD')
if not PASSWORD:
    PASSWORD = 'demo123'


async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)


async def initialize_database(conn):
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


async def get_db_connection_dependency():
    conn = await get_db_connection()
    try:
        yield conn
    finally:
        await conn.close()


@app.on_event("startup")
async def startup_event():
    conn = await get_db_connection()
    try:
        await initialize_database(conn)
    finally:
        await conn.close()


async def get_teams(conn):
    try:
        teams = await conn.fetch("SELECT team_id, name FROM teams")
        return [dict(team) for team in teams]
    except Exception as e:
        print(f"Error fetching teams: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error fetching teams")


async def get_venues(conn):
    try:
        venues = await conn.fetch("SELECT venue_id, name FROM venues")
        return [dict(venue) for venue in venues]
    except Exception as e:
        print(f"Error fetching venues: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error fetching venues")


async def get_events(conn) -> List[dict]:
    try:
        events = await conn.fetch("SELECT * FROM events ORDER BY event_date ASC, event_time ASC")
        return [dict(event) for event in events]
    except Exception as e:
        print(f"Error fetching events: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error fetching events")


@app.get("/events", response_class=HTMLResponse)
async def view_events(request: Request, conn=Depends(get_db_connection_dependency)):
    events = await get_events(conn)  # Fetch all events from the database
    return templates.TemplateResponse("events.html", {"request": request, "events": events})


@app.get("/api/events", response_model=List[dict])
async def get_all_events(conn=Depends(get_db_connection_dependency)):
    return await get_events(conn)


@app.get("/api/teams", response_model=List[dict])
async def get_all_teams(conn=Depends(get_db_connection_dependency)):
    return await get_teams(conn)


@app.get("/api/venues", response_model=List[dict])
async def get_all_venues(conn=Depends(get_db_connection_dependency)):
    return await get_venues(conn)


@app.get("/api/event/{event_id}")
async def get_event_details(event_id: int, conn=Depends(get_db_connection_dependency)):
    try:
        event = await conn.fetchrow(""" 
            SELECT e.event_id, e.sport_type, e.event_date, e.event_time,
                   ht.name as home_team, at.name as away_team,
                   v.name as venue_name, e.description
            FROM events e
            LEFT JOIN teams ht ON e.home_team_id = ht.team_id
            LEFT JOIN teams at ON e.away_team_id = at.team_id
            LEFT JOIN venues v ON e.venue_id = v.venue_id
            WHERE e.event_id = $1
        """, event_id)

        if event is None:
            raise HTTPException(status_code=404, detail="Event not found")

        return dict(event)

    except Exception as e:
        print(f"Error fetching event details: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error fetching event details")


@app.post("/api/events")
async def create_event(
    sport_type: str = Form(...),
    event_date: str = Form(...),
    event_time: str = Form(...),
    home_team_id: Optional[int] = Form(None),
    away_team_id: Optional[int] = Form(None),
    venue_id: Optional[int] = Form(None),
    description: Optional[str] = Form(None),
    conn=Depends(get_db_connection_dependency)
):
    event_date_obj = datetime.strptime(event_date, "%Y-%m-%d").date()
    event_time_obj = datetime.strptime(event_time, "%H:%M").time()

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

    # Redirect to /add-event with success message
    return RedirectResponse(url="/add-event?message=Event created successfully.", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/add-event", response_class=HTMLResponse)
async def add_event_form(request: Request, conn=Depends(get_db_connection_dependency), message: Optional[str] = None):
    teams = await get_teams(conn)
    venues = await get_venues(conn)
    return templates.TemplateResponse("add_event.html", {"request": request, "teams": teams, "venues": venues, "message": message})


@app.get("/", response_class=HTMLResponse)
async def read_events(request: Request, session_id: str = Cookie(None), conn=Depends(get_db_connection_dependency)):
    if session_id != "authenticated":
        return RedirectResponse(url="/login")  # Redirect to login if not authenticated
    
    events = await get_events(conn)  # Fetch events from the database
    return templates.TemplateResponse("index.html", {"request": request, "events": events})


@app.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login", response_class=HTMLResponse)
async def login_post(request: Request, password: str = Form(...)):
    print(f"Received password: {password}")  # Debugging: print received password
    print(f"Stored password: {PASSWORD}")  # Debugging: print stored password

    if password == PASSWORD:
        response = RedirectResponse(url="/")
        response.set_cookie(key="session_id", value="authenticated")
        return response
    else:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid password"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True, log_level="debug")
