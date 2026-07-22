from google.adk.agents import Agent
import os

import requests

# -----------------------------
# Helper Function
# -----------------------------
def send_to_recommender(preferences: dict):
    """Send preferences or a wine name to the recommendation API."""
    backend_url = os.getenv("RECOMMENDER_API_URL", "http://127.0.0.1:8000")
    wine_name = preferences.get("wine_name") or preferences.get("title")
    if wine_name:
        url = f"{backend_url}/recommend/title"
        payload = {"title": wine_name}
    else:
        url = f"{backend_url}/recommend/preferences"
        payload = {
            key: value if value not in [None, "null", ""] else ""
            for key, value in preferences.items()
        }
        if payload.get("country") and not payload.get("region"):
            payload["region"] = payload["country"]
        payload.pop("country", None)

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.Timeout:
        return {"error": "The recommendation service timed out."}
    except requests.HTTPError as error:
        if error.response.status_code == 404:
            detail = error.response.json().get("detail", {})
            if isinstance(detail, dict) and "wine_not_found" in detail:
                return detail
        return {"error": "The recommendation service returned an error."}
    except requests.RequestException:
        return {"error": "The recommendation service is unavailable."}


# -----------------------------
# Sommelier Agent Definition
# -----------------------------
sommelier_agent = Agent(
    name="sommelier_agent",
    model="gemini-3.6-flash",
    description=(
        "A friendly virtual sommelier that collects basic wine preferences "
        "and sends them to the backend recommendation API. "
        "It returns structured tool results to the manager."
    ),
    instruction=(
        "You are the Sommelier Agent in a multi-agent wine recommendation system.\n\n"
        "Your role:\n"
        "• Handle all recommendations that use the internal wine dataset.\n"
        "• Accept user preferences (type, sweetness, body, flavor_notes, region) or a specific wine name.\n"
        "• Always call send_to_recommender with either structured preferences or {'wine_name': 'Name'}.\n"
        "Workflow:\n"
        "1️⃣ When given preferences:\n"
        "   - Pass type, sweetness, body, flavor_notes, and region to send_to_recommender.\n"
        "   - Return the tool result without inventing or changing recommendations.\n\n"
        "2️⃣ When given a wine name:\n"
        "   - Pass the name as wine_name to send_to_recommender.\n"
        "   - Return wine_not_found unchanged so the Manager can use search_agent.\n\n"
        "Output:\n"
        "Return concise structured data to the Manager Agent.\n"
        "Do not write a user-facing summary.\n\n"
        "Your tone and behavior:\n"
        "• Analytical, precise, and data-driven.\n"
        "• Operate silently in the background—do not communicate with the user.\n"
        "• Never generate recommendations; use only the recommender tool output.\n"

    ),
)
sommelier_agent.tools = [send_to_recommender]
