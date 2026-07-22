# tests/test_ratings_recommender.py
from recommender.recommender import WineRecommender

if __name__ == "__main__":
    print("🧪 Running rating-based recommender test (real dataset)...\n")
    recommender = WineRecommender("data/wine_data.csv")

    test_cases = [
        {
            "label": "User A – Bold Red Fan",
            "ratings": {
                "The Guv'nor": 5,
                "LB7 Red 2020/21, Lisbon": 4,
                "Pasqua 'Desire, Lush & Zin' Primitivo 2021/22, Puglia": 5,
                "Two Hands 'Angels' Share' Shiraz 2021/22, McLaren Vale": 4,
                "Bouvet Ladubay Saumur Brut": 1
            }
        },
        {
            "label": "User B – Light & Fruity Whites",
            "ratings": {
                "Oyster Bay Sauvignon Blanc 2022, Marlborough": 5,
                "The Ned 'Waihopai River' Sauvignon Blanc 2023, Marlborough": 5,
                "Chosen By Majestic Greek White 2022, Peloponnese": 4,
                "Louis Latour Mâcon-Lugny 2021/22": 3,
                "LB7 Red 2020/21, Lisbon": 1
            }
        },
        {
            "label": "User C – Sparkling & Rosé Lover",
            "ratings": {
                "La Gioiosa Prosecco DOC, Treviso": 5,
                "Bouvet Ladubay Saumur Brut": 5,
                "Miraval Rosé 2021/22, Côtes de Provence": 4,
                "Caves d'Esclans 'Whispering Angel' Rosé 2022, Côtes de Provence": 4,
                "The Guv'nor": 1
            }
        },
        {
            "label": "User D – Old-World Earthy Reds",
            "ratings": {
                "LB7 Red 2020/21, Lisbon": 5,
                "Pasqua 'Desire, Lush & Zin' Primitivo 2021/22, Puglia": 4,
                "E. Guigal Saint-Joseph 2018/19": 5,
                "Cave de Tain 'Les Blasons' Crozes-Hermitage 2019/20": 4,
                "La Gioiosa Prosecco DOC, Treviso": 1
            }
        },
        {
            "label": "User E – Rich & Buttery Whites",
            "ratings": {
                "Bread & Butter 'Winemaker's Selection' Chardonnay 2020/21, California": 5,
                "Louis Latour Mâcon-Lugny 2021/22": 5,
                "Cave de Lugny 'Reserve' Mâcon-Chardonnay 2021/22": 4,
                "Bouvet Ladubay Saumur Brut": 2,
                "LB7 Red 2020/21, Lisbon": 1
            }
        }
    ]

    for test in test_cases:
        print(f"\n🔹 {test['label']}")
        results = recommender.recommend_by_user_ratings(test["ratings"])
        for wine in results:
            print(f"- {wine['Title']} ({wine['Country']}) — {wine['Grape']} - {wine['Style']}, {wine['Price']} (score: {wine['similarity_score']:.3f})")
