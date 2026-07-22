from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["wines_loaded"] > 0


def test_chat_endpoint_returns_session_and_response(monkeypatch):
    wine = {"Title": "Test Rioja", "Price": "£12.99 per bottle"}

    class ToolEvent:
        content = type(
            "Content",
            (),
            {
                "parts": [
                    type(
                        "Part",
                        (),
                        {
                            "text": None,
                            "function_response": type(
                                "FunctionResponse",
                                (),
                                {"response": {"recommendations": [wine]}},
                            )(),
                        },
                    )()
                ]
            },
        )()

        @staticmethod
        def is_final_response():
            return False

    class FinalEvent:
        content = type(
            "Content",
            (),
            {
                "parts": [
                    type(
                        "Part",
                        (),
                        {"text": "Try a Rioja.", "function_response": None},
                    )()
                ]
            },
        )()

        @staticmethod
        def is_final_response():
            return True

    monkeypatch.setattr(
        "main.chat_runner.run", lambda **kwargs: iter([ToolEvent(), FinalEvent()])
    )
    response = client.post("/chat", json={"message": "Recommend a red wine"})

    assert response.status_code == 200
    assert response.json()["message"] == "Try a Rioja."
    assert response.json()["session_id"]
    assert response.json()["recommendations"] == [wine]


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


def test_preferences_endpoint_enforces_price_range():
    response = client.post(
        "/recommend/preferences",
        json={
            "type": "white",
            "sweetness": "slightly sweet",
            "min_price": 15,
            "max_price": 20,
            "currency": "USD",
        },
    )

    assert response.status_code == 200
    recommendations = response.json()["recommendations"]
    assert recommendations
    prices = [float(wine["Price"].split("£")[1].split()[0]) for wine in recommendations]
    assert all(11.85 <= price <= 15.8 for price in prices)


def test_invalid_price_range_is_rejected():
    response = client.post(
        "/recommend/preferences",
        json={"type": "white", "min_price": 20, "max_price": 15, "currency": "USD"},
    )

    assert response.status_code == 422


def test_title_endpoint_returns_similar_wines():
    response = client.post("/recommend/title", json={"title": "The Guv'nor"})

    assert response.status_code == 200
    assert len(response.json()["recommendations"]) == 5


def test_unknown_title_returns_not_found():
    from unittest.mock import patch

    with patch("main.find_external_wine", return_value=None):
        response = client.post(
            "/recommend/title", json={"title": "Definitely Not A Real Wine"}
        )

    assert response.status_code == 404


def test_unknown_catalog_wine_uses_grounded_search():
    from unittest.mock import patch

    external_wine = {
        "Title": "Josh Cellars Cabernet Sauvignon, California",
        "Type": "Red",
        "Grape": "Cabernet Sauvignon",
        "Region": "California",
        "Country": "USA",
        "Style": "Full-bodied",
        "Characteristics": "blackberry, vanilla, oak",
        "Price": "$17",
    }
    with patch("main.find_external_wine", return_value=external_wine):
        response = client.post(
            "/recommend/title", json={"title": "Josh Cabernet Sauvignon"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "grounded_search"
    assert body["reference_wine"]["Title"].startswith("Josh Cellars")
    assert len(body["recommendations"]) == 5


def test_search_service_failure_returns_bad_gateway():
    from unittest.mock import patch

    with patch("main.find_external_wine", side_effect=RuntimeError("search unavailable")):
        response = client.post(
            "/recommend/title", json={"title": "Unknown External Wine"}
        )

    assert response.status_code == 502
