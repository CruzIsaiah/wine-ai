# main.py
from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from recommender.recommender import WineRecommender

# ----------------------------------------------------------------------
# 🌐 FastAPI app setup
# ----------------------------------------------------------------------
app = FastAPI(
    title="Wine AI Recommender API",
    description="Backend for the Wine Sommelier Agent — supports both title-based and taste-quiz recommendations.",
    version="1.0.0"
)

# Allow frontend or ADK agent to call the API locally or remotely
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # you can replace "*" with your ADK or frontend URL for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------------------------
# 🍷 Initialize recommender
# ----------------------------------------------------------------------
recommender = WineRecommender("data/wine_data.csv")


# ----------------------------------------------------------------------
# 1️⃣ Recommend by wine title (TF-IDF)
# ----------------------------------------------------------------------
@app.get("/recommend/title")
def recommend_by_title(title: str, n: int = 5):
    """
    Recommend wines similar to a given title.
    Example:
      /recommend/title?title=Pinot&n=5
    """
    results = recommender.recommend(title, n)
    return {"input": title, "recommendations": results}


# ----------------------------------------------------------------------
# 2️⃣ Recommend by user taste preferences (quiz-style)
# ----------------------------------------------------------------------
@app.post("/recommend/preferences")
def recommend_by_preferences(prefs: dict = Body(...)):
    """
    Recommend wines based on user's taste preferences.
    Example JSON body:
    {
      "red_intensity": 4,
      "sweet": false,
      "bold": true,
      "fruity": true,
      "earthy": false,
      "region": "California"
    }
    """
    results = recommender.recommend_by_preferences(prefs)
    return {"input_preferences": prefs, "recommendations": results}


# ----------------------------------------------------------------------
# 🏠 Health Check
# ----------------------------------------------------------------------
@app.get("/")
def root():
    return {
        "message": "🍷 Wine AI Recommender API is running!",
        "endpoints": {
            "GET /recommend/title": "Get similar wines by title (query param: ?title=Pinot)",
            "POST /recommend/preferences": "Get recommendations from taste preferences"
        }
    }
