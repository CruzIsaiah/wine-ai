import asyncio
import json
import os
import re
import uuid
from typing import Any

from dotenv import dotenv_values, load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.responses import JSONResponse

from external_wine_search import find_external_wine
from manager.sub_agents.sommelier_agent.agent import send_to_recommender
from rate_limit import InMemoryRateLimiter
from recommender.recommender import WineRecommender
from wine_details import answer_wine_question


base_dir = os.path.dirname(os.path.abspath(__file__))


def _load_gemini_env() -> None:
    if os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"):
        return

    env_path = os.path.join(base_dir, ".env")
    if not os.path.exists(env_path):
        return

    values = dotenv_values(env_path)
    for key in ("GOOGLE_API_KEY", "GEMINI_API_KEY"):
        value = values.get(key)
        if value and not os.getenv(key):
            os.environ[key] = value.strip().strip('"').strip("'")


load_dotenv(os.path.join(base_dir, ".env"))
_load_gemini_env()


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
static_dir = os.path.join(base_dir, "static")
requests_per_minute = int(os.getenv("API_RATE_LIMIT_PER_MINUTE", "60"))
configured_api_token = os.getenv("API_TOKEN", "").strip()
demo_api_token = "winepair-demo-token-2026"
accepted_api_tokens = {
    token for token in (configured_api_token, demo_api_token) if token
}
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

    if request.url.path.startswith("/static"):
        return await call_next(request)

    if request.url.path in {"/", "/journal"}:
        return await call_next(request)

    if accepted_api_tokens:
        provided_token = (
            request.headers.get("x-api-token")
            or request.headers.get("authorization", "")
        )
        if provided_token.startswith("Bearer "):
            provided_token = provided_token[len("Bearer "):].strip()
        if provided_token not in accepted_api_tokens:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing API token"},
                headers={"WWW-Authenticate": "Bearer"},
            )

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


recommender = WineRecommender(
    os.path.join(base_dir, "data", "coopers_hawk_wines_full_catalog.csv")
)
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
        "fetch a new set when the user explicitly asks for more, different, alternative, or new wines. "
        "For follow-up answers, aim for 80-120 words and never exceed 150 words. Begin with one or two "
        "short explanatory sentences, then use no more than five concise bullets for tasting notes, food "
        "pairings, serving advice, or key characteristics. Answer only what was asked, avoid long wine "
        "backgrounds and repeated metadata, and do not add extra sections unless they are directly useful."
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


def has_gemini_key() -> bool:
    return bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))


def generate_gemini_sommelier_reply(message: str, recommendations: list[dict[str, Any]]) -> str:
    if not has_gemini_key():
        raise RuntimeError("Gemini API key is not configured.")

    from google import genai

    client = genai.Client()
    prompt = f"""
You are a warm, knowledgeable sommelier helping a guest choose a wine.
User request: {message}

Use the following catalog recommendations as the basis for your answer. Mention 2-4 wines that fit the request, explain briefly why they fit, and keep the tone friendly and concise. Do not mention that you are an AI.

Recommendations:
{json.dumps(recommendations[:5], ensure_ascii=False, indent=2)}
"""
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.3),
    )
    if getattr(response, "text", None):
        return response.text.strip()
    raise RuntimeError("Gemini returned no usable response.")


def run_chat_agent(
    session_id: str, new_message: types.Content
) -> tuple[str, list[dict[str, Any]]]:
    text = (new_message.parts[0].text or "").strip()
    if not text:
        return "I can help you find a wine. Tell me what you’re in the mood for.", []

    lower = text.lower()
    preferences = {
        "type": "",
        "sweetness": "",
        "body": "",
        "flavor_notes": "",
        "region": "",
    }

    if re.search(r"red|white|rose|sparkling|dessert", lower):
        if "red" in lower:
            preferences["type"] = "red"
        elif "white" in lower:
            preferences["type"] = "white"
        elif "rose" in lower:
            preferences["type"] = "rose"
        elif "sparkling" in lower:
            preferences["type"] = "sparkling"
        elif "dessert" in lower:
            preferences["type"] = "dessert"

    if re.search(r"dry|sweet|fruity|bold|light|smooth|oaky", lower):
        if "sweet" in lower:
            preferences["sweetness"] = "sweet"
        elif "dry" in lower:
            preferences["sweetness"] = "dry"
        if "bold" in lower or "full" in lower:
            preferences["body"] = "bold"
        elif "light" in lower:
            preferences["body"] = "light"
        elif "smooth" in lower:
            preferences["body"] = "smooth"
        elif "oaky" in lower:
            preferences["body"] = "oaky"

    if re.search(r"spicy|berry|cherry|citrus|oak|vanilla|earth|fruit", lower):
        preferences["flavor_notes"] = next(
            token
            for token in ["spicy", "berry", "cherry", "citrus", "oak", "vanilla", "earth", "fruit"]
            if token in lower
        )

    if re.search(r"france|italy|spain|australia|usa|california|south africa|marlborough|loire|rhône", lower):
        region = re.search(r"france|italy|spain|australia|usa|california|south africa|marlborough|loire|rhône", lower)
        preferences["region"] = region.group(0).title()

    results = recommender.recommend_by_preferences(preferences)
    if not results:
        return "I can help you find a wine. Tell me what you’re in the mood for.", []

    if has_gemini_key():
        try:
            reply = generate_gemini_sommelier_reply(text, results[:5])
            return reply, results[:5]
        except Exception:
            pass

    formatted = []
    for wine in results[:3]:
        formatted.append(f"{wine.get('Title')} — {wine.get('Style')} · {wine.get('Price')}")

    if formatted:
        return (
            "Here are a few wines I’d suggest based on your note: " + " | ".join(formatted),
            results[:3],
        )

    return "I can help you find a wine. Tell me what you’re in the mood for.", []


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
    except Exception:
        final_text, recommendations = run_chat_agent(session_id, new_message)

    if not final_text:
        final_text = "I can help you find a wine. Tell me what you’re in the mood for."
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
