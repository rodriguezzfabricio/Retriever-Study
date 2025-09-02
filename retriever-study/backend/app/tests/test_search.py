import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Fixture to create some sample groups in the database
@pytest.fixture(scope="module", autouse=True)
def setup_test_database():
    # Use a separate test database or mock the database calls
    # For this example, we'll assume the existing dev database is used
    # In a real-world scenario, you would use a dedicated test database

    # Clear existing groups to ensure a clean slate
    # (Requires a helper in db module, e.g., db.clear_table('groups'))

    # Group 1: A standard calculus group
    client.post("/groups?owner_id=user_search_test_1", json={
        "courseCode": "MATH101",
        "title": "Calculus Study Group",
        "description": "Weekly group to review calculus concepts and solve problems.",
        "tags": ["quiet", "problem-solving", "homework"],
        "timePrefs": ["Wednesday evenings"],
        "location": "Library Room 402"
    })

    # Group 2: A loud, discussion-focused programming group
    client.post("/groups?owner_id=user_search_test_2", json={
        "courseCode": "CS101",
        "title": "Programming Bootcamp Prep",
        "description": "Intensive sessions for aspiring coders. We talk a lot.",
        "tags": ["loud", "energetic", "coding", "discussions"],
        "timePrefs": ["Weekend afternoons"],
        "location": "Computer Lab B"
    })

    # Group 3: A group focused on proofs in discrete math
    client.post("/groups?owner_id=user_search_test_3", json={
        "courseCode": "MATH202",
        "title": "Discrete Math Proofs Workshop",
        "description": "A group dedicated to mastering mathematical proofs.",
        "tags": ["proofs", "theory", "quiet"],
        "timePrefs": ["Friday mornings"],
        "location": "Math Department Lounge"
    })

def test_search_semantic_match():
    """Tests that a semantic query finds the most relevant group without exact keyword overlap."""
    # This query is semantically similar to the calculus group
    query = "a quiet place to do math homework"
    response = client.get(f"/search?q={query}")

    assert response.status_code == 200
    results = response.json()
    assert len(results) > 0

    # The top result should be the "Calculus Study Group"
    # because the query embedding should be closest to its embedding
    top_result_title = results[0]['title']
    assert top_result_title == "Calculus Study Group"

def test_search_specific_keyword():
    """Tests that a query with a specific, less common keyword finds the right group."""
    query = "help with mathematical proofs"
    response = client.get(f"/search?q={query}")

    assert response.status_code == 200
    results = response.json()
    assert len(results) > 0

    # The top result should be the Discrete Math group
    top_result_title = results[0]['title']
    assert top_result_title == "Discrete Math Proofs Workshop"

def test_search_no_results():
    """Tests that a nonsensical query returns no results or very low similarity matches."""
    query = "where can i buy a flying car"
    response = client.get(f"/search?q={query}")

    assert response.status_code == 200
    results = response.json()
    # Depending on the model, it might still find *some* match, but it should be a very low score.
    # For a simple test, we can assert that the most relevant groups are not returned.
    if results:
        top_result_title = results[0]['title']
        assert top_result_title not in ["Calculus Study Group", "Discrete Math Proofs Workshop"]

def test_search_empty_query():
    """Tests that an empty query returns a 400 Bad Request error."""
    response = client.get("/search?q=")
    assert response.status_code == 400
    assert response.json() == {"detail": "Query parameter 'q' cannot be empty"}
