from fastapi import FastAPI, HTTPException, Request, Form, status, Depends, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import asyncpg
import os
from dotenv import load_dotenv
from datetime import datetime
from typing import List, Optional
import ssl

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
    ssl_context = ssl.create_default_context()
    
    return await asyncpg.connect(DATABASE_URL, ssl=ssl_context)

async def initialize_database(conn):
    try:
        # Create sports table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sports (
                sport_id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL UNIQUE
            );
        """)

        # Create teams table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                team_id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                details TEXT
            );
        """)

        # Create venues table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS venues (
                venue_id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                location VARCHAR(255) NOT NULL,
                capacity INTEGER
            );
        """)

        # Create events table with sport_type as a foreign key referencing sports(sport_id)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id SERIAL PRIMARY KEY,
                sport_type INTEGER NOT NULL REFERENCES sports(sport_id) ON DELETE CASCADE,
                event_date DATE NOT NULL,
                event_time TIME NOT NULL,
                home_team_id INTEGER REFERENCES teams(team_id),
                away_team_id INTEGER REFERENCES teams(team_id),
                venue_id INTEGER REFERENCES venues(venue_id),
                description TEXT
            );
        """)
    except Exception as e:
        print(f"Error occurred while initializing the database: {e}")


async def get_db_connection_dependency():
    conn = await get_db_connection()
    try:
        yield conn
    finally:
        await conn.close()

async def get_sports(conn):
    try:
        sports = await conn.fetch("SELECT sport_id, name FROM sports")
        sports_list = [dict(sport) for sport in sports]
        print("Fetched sports:", sports_list)  # Debugging: log the fetched sports
        
        return sports_list
    except Exception as e:
        print(f"Error fetching sports: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error fetching sports")

async def add_sport(conn, name: str):
    try:
        # Check if sport already exists
        sport = await conn.fetchrow("SELECT sport_id FROM sports WHERE name = $1", name)
        if sport:
            return sport['sport_id']  # Return the existing sport ID
        else:
            # Insert new sport and return its ID
            return await conn.fetchval("INSERT INTO sports (name) VALUES ($1) RETURNING sport_id", name)
    except Exception as e:
        print(f"Error adding sport: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Error adding sport")

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
        teams_list = [dict(team) for team in teams]
        print("Fetched teams:", teams_list)  # Debugging: log the fetched teams
        return teams_list
    except Exception as e:
        print(f"Error fetching teams: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error fetching teams")

async def get_venues(conn):
    try:
        venues = await conn.fetch("SELECT venue_id, name FROM venues")
        venues_list = [dict(venue) for venue in venues]
        print("Fetched venues:", venues_list)  # Debugging: log the fetched venues
        return venues_list
    except Exception as e:
        print(f"Error fetching venues: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error fetching venues")
async def get_events(conn):
    query = """
    SELECT e.event_id, 
           s.name AS sport_name,  -- Fetch sport name from the sports table
           e.event_date, 
           e.event_time, 
           t1.name AS home_team_name, 
           t2.name AS away_team_name, 
           v.name AS venue_name, 
           e.description
    FROM events e
    JOIN sports s ON e.sport_type = s.sport_id  -- Join with sports table to get the sport name
    JOIN teams t1 ON e.home_team_id = t1.team_id
    JOIN teams t2 ON e.away_team_id = t2.team_id
    JOIN venues v ON e.venue_id = v.venue_id
    ORDER BY e.event_date, e.event_time;
    """
    
    rows = await conn.fetch(query)
    events = []
    today = datetime.now()

    for row in rows:
        event_date_time = datetime.combine(row['event_date'], row['event_time'])
        is_upcoming = event_date_time > today
        events.append({
            'event_id': row['event_id'],
            'sport_name': row['sport_name'],  # Use sport_name instead of sport_type ID
            'event_date': row['event_date'],
            'event_time': row['event_time'],
            'home_team_name': row['home_team_name'],
            'away_team_name': row['away_team_name'],
            'venue_name': row['venue_name'],
            'description': row['description'],
            'is_upcoming': is_upcoming
        })

    return events


    
@app.get("/events", response_class=HTMLResponse)
async def view_events(request: Request, conn=Depends(get_db_connection_dependency)):
    events = await get_events(conn)
    teams = await get_teams(conn)
    venues = await get_venues(conn)
    sports = await get_sports(conn) 
    today = datetime.now().date()
    
    return templates.TemplateResponse("events.html", {"request": request, "events": events, "today":today, "teams": teams, "venues": venues, "sports": sports})


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
    sport_type: str = Form(...),           # This will be either sport_id or 'other'
    event_date: str = Form(...),
    event_time: str = Form(...),
    home_team_id: Optional[str] = Form(None),
    away_team_id: Optional[str] = Form(None),
    venue_id: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    home_custom: Optional[str] = Form(None),
    away_custom: Optional[str] = Form(None),
    venue_custom: Optional[str] = Form(None),
    sport_custom: Optional[str] = Form(None),  # For custom sport name
    conn=Depends(get_db_connection_dependency)
):
    event_date_obj = datetime.strptime(event_date, "%Y-%m-%d").date()
    event_time_obj = datetime.strptime(event_time, "%H:%M").time()

    # Handle sport type
    if sport_custom:
        # Use the add_sport function to get sport ID
        sport_type = await add_sport(conn, sport_custom)
    elif sport_type is not None:
        # Ensure sport_type is an integer ID if it's not custom
        sport_type = int(sport_type)

    # Handle home team
    if home_custom:
        home_team_id = await conn.fetchval(
            """
            INSERT INTO teams (name) VALUES ($1) RETURNING team_id
            """,
            home_custom
        )
    elif home_team_id is not None:
        home_team_id = int(home_team_id)

    # Handle away team
    if away_custom:
        away_team_id = await conn.fetchval(
            """
            INSERT INTO teams (name) VALUES ($1) RETURNING team_id
            """,
            away_custom
        )
    elif away_team_id is not None:
        away_team_id = int(away_team_id)

    # Handle venue
    if venue_custom:
        venue_id = await conn.fetchval(
            """
            INSERT INTO venues (name, location) VALUES ($1, $1) RETURNING venue_id
            """,
            venue_custom
        )
    elif venue_id is not None:
        venue_id = int(venue_id)

    try:
        # Insert event into events table with sport_type as the foreign key to sports
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

    return RedirectResponse(url="/add-event?message=Event created successfully.", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/add-event", response_class=HTMLResponse)
async def add_event_form(request: Request, conn=Depends(get_db_connection_dependency), message: Optional[str] = None):
    teams = await get_teams(conn)
    venues = await get_venues(conn)
    sports = await get_sports(conn)  # Fetch available sports
    return templates.TemplateResponse("add_event.html", {"request": request, "teams": teams, "venues": venues, "sports": sports, "message": message})


@app.get("/", response_class=HTMLResponse)
async def read_events(request: Request, session_id: str = Cookie(None), conn=Depends(get_db_connection_dependency)):
    print(f"Accessing root: session_id={session_id}")  # Debugging
    if session_id != "authenticated":
        print("Redirecting to login due to unauthenticated session.")  # Debugging
        return RedirectResponse(url="/login")
    
    events = await get_events(conn)  # Fetch events from the database
    return templates.TemplateResponse("index.html", {
        "request": request,
        "events": events
    })



@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login", response_class=HTMLResponse)
async def login_post(request: Request, password: str = Form(...)):
    print(f"Received password: {password}")  # Debugging
    if password == PASSWORD:
        # If login is successful
        response = RedirectResponse(url="/", status_code=303)  # 303 See Other for redirects after a POST
        response.set_cookie(key="session_id", value="authenticated")
        print("Login successful, setting cookie and redirecting.")  # Debugging
        return response
    else:
        # If login fails
        print("Invalid password, returning to login.")  # Debugging
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid password"
        })

    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True, log_level="debug")
