import uuid
from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from manager.agent import root_agent as manager

load_dotenv()

session_service = InMemorySessionService()

initial_state = {
    "user_name": "Isaiah C",
    "rated_wines": {
        "The Guv'nor, Spain": 5,
        "Oyster Bay Sauvignon Blanc 2022, Marlborough": 4,
        "Bread & Butter Chardonnay 2020/21, California": 3,
        "LB7 Red 2020/21, Lisbon": 2,
        "Bouvet Ladubay Saumur Brut, Loire": 1
    }
}

APP_NAME = "wine_recommender_app"
USER_ID = "user_123"
SESSION_ID = str(uuid.uuid4())

stateful_session = session_service.create_session(
    app_name=APP_NAME,
    user_id=USER_ID,
    session_id=SESSION_ID,
    state=initial_state
)

print(f"🆔 Created session with ID: {SESSION_ID}\n")

runner = Runner(
    agent=manager, 
    app_name=APP_NAME,
    session_service=session_service,
)

new_message = types.Content(
    role="user",
    parts=[types.Part(text="what wines does the user like")]
)

for event in runner.run(
    user_id=USER_ID,
    session_id=SESSION_ID,
    new_message=new_message,
):
    if event.is_final_response():
        if event.content and event.content.parts:
            print(f"💬 Final Response: {event.content.parts[0].text}")

print("===== Session Event Exploration =====")
session = session_service.get_session(
    app_name=APP_NAME,
    user_id=USER_ID,
    session_id=SESSION_ID,
)
print(session.state)
