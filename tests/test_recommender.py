# tests/test_recommender.py
from recommender.recommender import WineRecommender

if __name__ == "__main__":
    print("🧪 Running standalone recommender test...\n")
    recommender = WineRecommender("data/wine_data.csv")

    test_cases = [
        {
            "label": "Test Case 1: Bold Red from France",
            "prefs": {
                "type": "red",
                "sweetness": "dry",
                "body": "bold",
                "flavor_notes": "spicy",
                "region": "france"
            }
        },
        {
            "label": "Test Case 2: Fruity White from Spain",
            "prefs": {
                "type": "white",
                "sweetness": "sweet",
                "body": "light",
                "flavor_notes": "fruity",
                "region": "spain"
            }
        },
        {
            "label": "Test Case 3: Earthy Medium Red from Italy",
            "prefs": {
                "type": "red",
                "sweetness": "dry",
                "body": "medium",
                "flavor_notes": "earthy",
                "region": "italy"
            }
        },
        {
            "label": "Test Case 4: Floral Light Rosé from USA",
            "prefs": {
                "type": "rosé",
                "sweetness": "off-dry",
                "body": "light",
                "flavor_notes": "floral",
                "region": "usa"
            }
        },
        {
            "label": "Test Case 5: Rich Full-Bodied White from Australia",
            "prefs": {
                "type": "white",
                "sweetness": "dry",
                "body": "full",
                "flavor_notes": "buttery oaky",
                "region": "australia"
            }
        }
    ]

    for test in test_cases:
        print(f"\n🔹 {test['label']}")
        results = recommender.recommend_by_preferences(test["prefs"])
        for wine in results:
            print(f"- {wine['Title']} ({wine['Country']}) — {wine['Grape']} - {wine['Style']}, {wine['Price']} (score: {wine['similarity_score']})")
