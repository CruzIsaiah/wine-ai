import os
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.responses import JSONResponse

from rate_limit import InMemoryRateLimiter
from recommender.recommender import WineRecommender


class WinePreferences(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str = Field(default="", max_length=50)
    sweetness: str = Field(default="", max_length=50)
    body: str = Field(default="", max_length=50)
    flavor_notes: str = Field(default="", max_length=200)
    region: str = Field(default="", max_length=100)

    @field_validator("type", "sweetness", "body", "flavor_notes", "region")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()


class WineTitleRequest(BaseModel):
    title: str = Field(min_length=2, max_length=200)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return value.strip()


class RecommendationResponse(BaseModel):
    recommendations: list[dict[str, Any]]


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
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def home():
    return FileResponse(os.path.join(static_dir, "index.html"))


@app.get("/health")
def health():
    return {"status": "ok", "wines_loaded": len(recommender.wine_df)}


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
    if results is None:
        raise HTTPException(status_code=404, detail={"wine_not_found": request.title})
    return RecommendationResponse(recommendations=results)
