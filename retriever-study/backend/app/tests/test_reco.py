import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.data.local_db import db
import time

client = TestClient(app)

# Using a fixture to set up the database once for the module
@pytest.fixture(scope="module", autouse=True)
def setup_test_database():
    """This fixture runs once to set up the necessary users and groups for testing recommendations."""
    # Ensure the database is clean before running tests
    db._clear_all_tables()

    # Create a user with a clear preference for quiet study
    user_response = client.post("/users", json={
        "name": "Reco Test User",
        "email": "reco@test.com",
        "courses": ["MATH101"],
        "bio": "I really prefer quiet, focused study environments.",
        "prefs": {
            "studyStyle": ["quiet"],
            "timeSlots": ["evening"],
            "locations": ["library"]
        }
    })
    assert user_response.status_code == 201

    # Create a group that is a strong match
    client.post("/groups?owner_id=user_reco_test_1", json={
        "courseCode": "MATH101",
        "title": "Calculus Study Group",
        "description": "A quiet group for solving calculus problems.",
        "tags": ["quiet", "problem-solving"],
        "location": "Library"
    })

    # Create a group that is a clear mismatch
    client.post("/groups?owner_id=user_reco_test_2", json={
        "courseCode": "CS101",
        "title": "Loud Programming Bootcamp",
        "description": "High-energy, discussion-based coding sessions.",
        "tags": ["loud", "energetic", "discussions"],
        "location": "Common Area"
    })
    
    # Give a moment for embeddings to be processed and stored, avoiding race conditions in tests.
    time.sleep(2)

def test_get_recommendations_returns_correct_order():
    """ 
    Tests that the /recommendations endpoint returns groups sorted by similarity.
    The most similar group should appear first.
    """
    # The user was created in the setup fixture, but we need their ID.
    # In a real app, we might have a GET /users/{email} endpoint.
    # For this test, we'll re-create a user to reliably get their ID.
    user_response = client.post("/users", json={
        "name": "Test User for Reco",
        "email": "reco_test_2@test.com",
        "courses": ["MATH101"],
        "bio": "I need a quiet place to study.",
        "prefs": {"studyStyle": ["quiet"]}
    })
    assert user_response.status_code == 201
    user_id = user_response.json()["userId"]

    # Act: Get recommendations for this user
    response = client.get(f"/recommendations?userId={user_id}&limit=5")

    # Assert: Check the response
    assert response.status_code == 200
    recommendations = response.json()
    
    assert len(recommendations) > 0
    
    # The first recommendation MUST be the quiet calculus group
    assert recommendations[0]["title"] == "Calculus Study Group"
    
    # Verify the second one is the loud group, proving the sorting works
    if len(recommendations) > 1:
        assert recommendations[1]["title"] == "Loud Programming Bootcamp"
