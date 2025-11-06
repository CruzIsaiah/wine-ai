# tests/test_recommender_standalone.py
from recommender.recommender import WineRecommender

if __name__ == "__main__":
    print("🧪 Running standalone recommender test...\n")

    recommender = WineRecommender("data/wine_data.csv")

    prefs = {
        "type": "white",
        "sweetness": "sweet",
        "body": "light",
        "flavor_notes": "fruity",
        "region": "spain"
    }

    results = recommender.recommend_by_preferences(prefs)

    print("✅ The recommender (not the agent) generated these results:\n")
    for wine in results:
        print(f"- {wine['Title']} ({wine['Country']}) — {wine['Grape']} - {wine['Style']} | Score: {wine['similarity_score']}")


if __name__ == "__main__":
    # Initialize the recommender with your CSV
    recommender = WineRecommender("data/wine_data.csv")

    # Example user preferences 
    prefs = {
        "type": "white",
        "sweetness": "sweet",
        "body": "light",
        "flavor_notes": "fruity",
        "region": "spain"
    }

    # Get top recommendations
    results = recommender.recommend_by_preferences(prefs)

    # Pretty print results
    print("\n🍷 Recommended Wines:\n")
    for wine in results:
        print(f"- {wine['Title']} ({wine['Country']}) — {wine['Grape']} - {wine['Style']}, {wine['Price']} (score: {wine['similarity_score']})")