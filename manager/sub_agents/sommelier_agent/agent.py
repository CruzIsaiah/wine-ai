from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
import requests

# -----------------------------
# Helper Function
# -----------------------------
def send_to_recommender(preferences: dict):
    """Send collected preferences to the FastAPI backend and return formatted results."""
    url = "http://127.0.0.1:8000/recommend/preferences"
    headers = {"Content-Type": "application/json"}

    clean_prefs = {k: (v if v not in [None, "null", ""] else "") for k, v in preferences.items()}

    try:
        response = requests.post(url, json=clean_prefs, headers=headers)
        response.raise_for_status()
        data = response.json()

        recs = data.get("recommendations", [])
        if recs:
            output = "🍾 **Here are your wine recommendations:**\n\n"
            for wine in recs[:5]:
                title = wine.get("Title", "Unknown Wine")
                style = wine.get("Style", "No style info")
                region = wine.get("Region") or wine.get("Country", "Unknown region")
                price = wine.get("Price", "N/A")
                output += f"• **{title}** — {style} ({region}) • {price}\n"
        else:
            output = "😕 Sorry, no wines matched your preferences."

        return output

    except requests.exceptions.RequestException as e:
        return f"❌ Network error: {e}"
    except Exception as e:
        return f"⚠️ Unexpected error: {e}"


# -----------------------------
# Sommelier Agent Definition
# -----------------------------
sommelier_agent = Agent(
    name="sommelier_agent",
    model="gemini-2.0-flash",
    description=(
        "A friendly virtual sommelier that collects basic wine preferences "
        "and sends them to the backend recommendation API. "
        "It never creates its own results — only displays what the backend returns."
    ),
    instruction=(
        "Ask the user these simple, friendly questions:\n"
        "1️⃣ Do you prefer red, white, or rosé wine?\n"
        "2️⃣ Do you like sweet, dry, or in-between wines?\n"
        "3️⃣ Would you rather something light-bodied or bold-bodied?\n"
        "4️⃣ Do you enjoy fruity, spicy, or earthy flavors more?\n"
        "5️⃣ Any favorite region or country? (optional)\n\n"
        "Once all answers are collected, format them into a JSON object like:\n"
        "{\n"
        '  \"type\": \"white\",\n'
        '  \"sweetness\": \"sweet\",\n'
        '  \"body\": \"light\",\n'
        '  \"flavor_notes\": \"fruity\",\n'
        '  \"regiosommelier_agentn\": \"California\"\n'
        "}\n\n"
        "Then **call the Python function** `send_to_recommender(preferences)` "
        "to send that JSON to http://127.0.0.1:8000/recommend/preferences "
        "and display only the results provided by the backend, formatted neatly "
        "with each wine separated by a line."
        "Never generate your own recommendations."
    )
)
sommelier_agent.tools = [send_to_recommender]
