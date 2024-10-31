from fastapi import FastAPI, HTTPException, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import Column, Integer, String, Date, Time, Text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
import os
from datetime import datetime
from typing import Optional
from sqlalchemy import text

# Load environment variables from .env file
load_dotenv()

# Database URL from environment variable
DATABASE_URL = os.getenv('DATABASE_URL')

# Ensure the DATABASE_URL is not None
if DATABASE_URL is None:
    raise ValueError("DATABASE_URL is not set in the environment variables.")

# SQLAlchemy setup
engine = create_async_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

# Create FastAPI app instance
app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Define the Event model
class Event(Base):
    __tablename__ = 'events'
    id = Column(Integer, primary_key=True, autoincrement=True)
    sport = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    time = Column(Time, nullable=False)
    home_team = Column(String, nullable=False)
    away_team = Column(String, nullable=False)
    venue = Column(String)
    event_details = Column(Text)
    player_details = Column(Text)
    team_details = Column(Text)

# Initialize the database
@app.on_event("startup")
async def startup_event():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.on_event("shutdown")
async def shutdown_event():
    await engine.dispose()  # Properly dispose of the engine on shutdown

# Display form for adding a new event
@app.get("/add-event", response_class=HTMLResponse)
async def add_event_form(request: Request):
    return templates.TemplateResponse("add_event.html", {"request": request})

# Display all events using the new design from index.html
@app.get("/", response_class=HTMLResponse)
async def read_events(request: Request):
    async with SessionLocal() as session:
        result = await session.execute(text("SELECT * FROM events ORDER BY date ASC, time ASC"))
        events = result.fetchall()  # Fetch results as needed
        event_list = [
            {
                "id": row[0], "sport": row[1], "date": row[2], "time": row[3],
                "home_team": row[4], "away_team": row[5], "venue": row[6],
                "event_details": row[7], "player_details": row[8], "team_details": row[9]
            }
            for row in events
        ]
    return templates.TemplateResponse("index.html", {"request": request, "events": event_list})

# Create a new event
@app.post("/api/event/")
async def create_event(
    sport: str = Form(...),
    date: Optional[str] = Form(None),
    time: Optional[str] = Form(None),
    home_team: str = Form(...),
    away_team: str = Form(...),
    venue: Optional[str] = Form(None),
    event_details: Optional[str] = Form(None),
    player_details: Optional[str] = Form(None),
    team_details: Optional[str] = Form(None)
):
    try:
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        if time is None:
            time = datetime.now().strftime("%H:%M")

        # Validate date and time formats
        datetime.strptime(date, "%Y-%m-%d")
        datetime.strptime(time, "%H:%M")

        new_event = Event(
            sport=sport,
            date=datetime.strptime(date, "%Y-%m-%d").date(),
            time=datetime.strptime(time, "%H:%M").time(),
            home_team=home_team,
            away_team=away_team,
            venue=venue,
            event_details=event_details,
            player_details=player_details,
            team_details=team_details
        )

        async with SessionLocal() as session:
            session.add(new_event)
            await session.commit()

        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred.")

# Route to get one event by ID
@app.get("/event/{event_id}", response_class=HTMLResponse)
async def get_event(event_id: int, request: Request):
    async with SessionLocal() as session:
        result = await session.execute("SELECT * FROM events WHERE id = :id", {"id": event_id})
        row = result.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Event not found")
        event = {
            "id": row[0], "sport": row[1], "date": row[2], "time": row[3],
            "home_team": row[4], "away_team": row[5], "venue": row[6],
            "event_details": row[7], "player_details": row[8], "team_details": row[9]
        }
    return templates.TemplateResponse("event.html", {"request": request, "event": event})

# Route to filter events
@app.get("/events/", response_class=HTMLResponse)
async def get_events(request: Request, sport: Optional[str] = None, date: Optional[str] = None):
    query = "SELECT * FROM events"
    params = []

    if sport or date:
        query += " WHERE"
    if sport:
        query += " sport = :sport"  # Use named parameters
        params.append(sport)
    if date:
        if sport:
            query += " AND"
        query += " date = :date"  # Use named parameters
        params.append(date)

    async with SessionLocal() as session:
        result = await session.execute(query, {"sport": sport, "date": date})
        events = result.fetchall()

        event_list = [
            {
                "id": row[0], "sport": row[1], "date": row[2], "time": row[3],
                "home_team": row[4], "away_team": row[5], "venue": row[6],
                "event_details": row[7], "player_details": row[8], "team_details": row[9]
            }
            for row in events
        ]

    return templates.TemplateResponse("index.html", {"request": request, "events": event_list})

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
