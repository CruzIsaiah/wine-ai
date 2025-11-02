from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from recommender.recommender import WineRecommender

app = FastAPI()

# CORS so ADK can talk to it
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize recommender
recommender = WineRecommender("data/wine_data.csv")

@app.get("/")
def home():
    return {"message": "Wine recommender backend running 🍷"}

@app.post("/recommend/preferences")
async def recommend_preferences(request: Request):
    prefs = await request.json()
    results = recommender.recommend_by_preferences(prefs)
    return {"recommendations": results}
