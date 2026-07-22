from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["wines_loaded"] > 0


def test_api_responses_include_rate_limit_headers():
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "WinePair" in response.text
    assert response.headers["X-RateLimit-Limit"] == "60"
    assert int(response.headers["X-RateLimit-Remaining"]) >= 0


def test_preferences_endpoint_returns_json_safe_results():
    response = client.post(
        "/recommend/preferences",
        json={
            "type": "red",
            "sweetness": "dry",
            "body": "bold",
            "flavor_notes": "spicy",
            "region": "France",
        },
    )

    assert response.status_code == 200
    recommendations = response.json()["recommendations"]
    assert len(recommendations) == 5
    assert all(wine["Country"] == "France" for wine in recommendations)


def test_empty_preferences_are_rejected():
    response = client.post("/recommend/preferences", json={})

    assert response.status_code == 400


def test_title_endpoint_returns_similar_wines():
    response = client.post("/recommend/title", json={"title": "The Guv'nor"})

    assert response.status_code == 200
    assert len(response.json()["recommendations"]) == 5


def test_unknown_title_returns_not_found():
    response = client.post(
        "/recommend/title", json={"title": "Definitely Not A Real Wine"}
    )

    assert response.status_code == 404
