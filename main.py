import asyncio
import os
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.responses import JSONResponse

from rate_limit import InMemoryRateLimiter
from recommender.recommender import WineRecommender
from external_wine_search import find_external_wine
from manager.sub_agents.sommelier_agent.agent import send_to_recommender
from wine_details import answer_wine_question


load_dotenv()


class WinePreferences(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str = Field(default="", max_length=50)
    sweetness: str = Field(default="", max_length=50)
    body: str = Field(default="", max_length=50)
    flavor_notes: str = Field(default="", max_length=200)
    region: str = Field(default="", max_length=100)
    min_price: float | None = Field(default=None, ge=0, le=10000)
    max_price: float | None = Field(default=None, ge=0, le=10000)
    currency: str = Field(default="USD", pattern="^(GBP|USD|EUR)$")

    @field_validator("type", "sweetness", "body", "flavor_notes", "region")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("max_price")
    @classmethod
    def validate_price_range(cls, value: float | None, info):
        minimum = info.data.get("min_price")
        if value is not None and minimum is not None and value < minimum:
            raise ValueError("max_price must be greater than or equal to min_price")
        return value


class WineTitleRequest(BaseModel):
    title: str = Field(min_length=2, max_length=200)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return value.strip()


class RecommendationResponse(BaseModel):
    recommendations: list[dict[str, Any]]
    source: str = "catalog"
    reference_wine: dict[str, Any] | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    session_id: str | None = Field(default=None, max_length=100)


class ChatResponse(BaseModel):
    message: str
    session_id: str
    recommendations: list[dict[str, Any]] = Field(default_factory=list)


class WineDetailsRequest(BaseModel):
    wine: dict[str, Any]
    question: str = Field(min_length=2, max_length=500)


class WineDetailsResponse(BaseModel):
    answer: str


app = FastAPI(title="WinePair Recommendation API", version="1.0.0")
base_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(base_dir, "static")
requests_per_minute = int(os.getenv("API_RATE_LIMIT_PER_MINUTE", "60"))
rate_limiter = InMemoryRateLimiter(limit=requests_per_minute)

allowed_origins = os.getenv(
    "CORS_ORIGINS", "http://127.0.0.1:8001,http://localhost:8001"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins if origin.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def enforce_rate_limit(request, call_next):
    if request.url.path == "/health":
        return await call_next(request)

    client_key = request.client.host if request.client else "unknown"
    allowed, remaining, retry_after = rate_limiter.allow(client_key)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"detail": "API rate limit exceeded. Please retry later."},
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(requests_per_minute),
                "X-RateLimit-Remaining": "0",
            },
        )

    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(requests_per_minute)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    return response

recommender = WineRecommender(os.path.join(base_dir, "data", "wine_data.csv"))
chat_session_service = InMemorySessionService()
website_chat_agent = Agent(
    name="website_sommelier",
    model="gemini-3.6-flash",
    description="Conversational interface for the WinePair recommendation engine.",
    instruction=(
        "You are WinePair's friendly website sommelier. For each NEW recommendation request, "
        "call send_to_recommender before answering. Pass structured type, sweetness, body, "
        "flavor_notes, region, min_price, max_price, and currency when provided. For a named "
        "wine, pass {'wine_name': 'Name'}; the backend handles catalog and grounded-search lookup. "
        "Use only wines returned by the tool. Never invent or substitute wines, prices, regions, "
        "or product-specific tasting notes. Preserve stated budgets exactly and keep responses concise. "
        "When the user asks for more information, an explanation, tasting details, serving advice, "
        "or food pairings about wines already returned in the conversation, DO NOT call the tool again "
        "and DO NOT provide a new recommendation list. Discuss only the existing wine or wines. You may "
        "use established general sommelier knowledge for grape education, likely food pairings, serving "
        "temperature, and glassware, while keeping catalog facts unchanged. If 'tell me more' does not "
        "identify which wine, ask the user to choose one or briefly describe the existing list. Only "
        "fetch a new set when the user explicitly asks for more, different, alternative, or new wines."
    ),
    tools=[send_to_recommender],
)
chat_runner = Runner(
    agent=website_chat_agent,
    app_name="winepair_web",
    session_service=chat_session_service,
)
chat_session_ids: set[str] = set()
app.mount("/static", StaticFiles(directory=static_dir), name="static")


def run_chat_agent(
    session_id: str, new_message: types.Content
) -> tuple[str, list[dict[str, Any]]]:
    final_text = ""
    recommendations: list[dict[str, Any]] = []
    for event in chat_runner.run(
        user_id="website_user",
        session_id=session_id,
        new_message=new_message,
    ):
        for part in event.content.parts if event.content else []:
            if not part.function_response or not part.function_response.response:
                continue
            tool_response = part.function_response.response
            if isinstance(tool_response.get("result"), dict):
                tool_response = tool_response["result"]
            if isinstance(tool_response.get("recommendations"), list):
                recommendations = tool_response["recommendations"]
        if event.is_final_response() and event.content:
            final_text = "\n".join(
                part.text for part in event.content.parts or [] if part.text
            )
    return final_text, recommendations


@app.get("/")
def home():
    return FileResponse(os.path.join(static_dir, "index.html"))


@app.get("/journal")
def journal():
    return FileResponse(os.path.join(static_dir, "journal.html"))


@app.get("/health")
def health():
    return {"status": "ok", "wines_loaded": len(recommender.wine_df)}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())
    if session_id not in chat_session_ids:
        await chat_session_service.create_session(
            app_name="winepair_web",
            user_id="website_user",
            session_id=session_id,
        )
        chat_session_ids.add(session_id)

    new_message = types.Content(
        role="user",
        parts=[types.Part(text=request.message.strip())],
    )
    try:
        final_text, recommendations = await asyncio.to_thread(
            run_chat_agent, session_id, new_message
        )
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail="The sommelier is temporarily unavailable.",
        ) from error
    if not final_text:
        raise HTTPException(status_code=502, detail="The sommelier returned no response.")
    return ChatResponse(
        message=final_text,
        session_id=session_id,
        recommendations=recommendations,
    )


@app.post("/wine-details", response_model=WineDetailsResponse)
async def wine_details(request: WineDetailsRequest):
    if not request.wine.get("Title"):
        raise HTTPException(status_code=422, detail="Wine title is required.")
    try:
        answer = await asyncio.to_thread(
            answer_wine_question, request.wine, request.question.strip()
        )
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail="The sommelier could not answer that question right now.",
        ) from error
    return WineDetailsResponse(answer=answer)


@app.post("/recommend/preferences", response_model=RecommendationResponse)
def recommend_preferences(preferences: WinePreferences):
    try:
        results = recommender.recommend_by_preferences(preferences.model_dump())
        return RecommendationResponse(recommendations=results)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/recommend/title", response_model=RecommendationResponse)
def recommend_title(request: WineTitleRequest):
    results = recommender.recommend_by_title(request.title)
    if results is not None:
        return RecommendationResponse(recommendations=results)

    try:
        external_wine = find_external_wine(request.title)
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail="The online wine search is temporarily unavailable.",
        ) from error
    if external_wine is None:
        raise HTTPException(status_code=404, detail={"wine_not_found": request.title})

    preferences = {
        "type": external_wine["Type"],
        "sweetness": "",
        "body": external_wine["Style"],
        "flavor_notes": external_wine["Characteristics"],
        "region": external_wine["Country"],
    }
    results = recommender.recommend_by_preferences(preferences)
    if not results:
        preferences["region"] = ""
        results = recommender.recommend_by_preferences(preferences)
    return RecommendationResponse(
        recommendations=results,
        source="grounded_search",
        reference_wine=external_wine,
    )
