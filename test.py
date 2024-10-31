from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_add_event():
    response = client.post("/event/", data={
        "sport": "Football",
        "date": "2024-10-31",
        "time": "18:00",
        "home_team": "Team A",
        "away_team": "Team B",
        "venue": "Stadium X"
    })
    assert response.status_code == 200
    assert response.json() == {"message": "Event added successfully"}

def test_get_events():
    response = client.get("/events/")
    assert response.status_code == 200
