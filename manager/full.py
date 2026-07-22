import pandas as pd
import numpy as np
import json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class WineRecommender:
    def __init__(self, csv_path):
        # Load and preprocess wine data
        print(f"📂 Loading wine data from: {csv_path}")
        self.wine_df = pd.read_csv(csv_path)

        # Combine descriptive fields with weighting
        self.wine_df["combined_text"] = (
            3 * self.wine_df["Type"].fillna('') + ' ' +
            2 * self.wine_df["Style"].fillna('') + ' ' +
            5 * self.wine_df["Characteristics"].fillna('') + ' ' +
            3 * self.wine_df["Grape"].fillna('') + ' ' +
            self.wine_df["Description"].fillna('') + ' ' +
            2 * self.wine_df["Region"].fillna('') + ' ' +
            self.wine_df["Country"].fillna('')
        ).str.lower()

        # Build TF-IDF model
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        self.tfidf_matrix = self.vectorizer.fit_transform(self.wine_df["combined_text"])
        print("✅ TF-IDF matrix built successfully.\n")

    # Preference-based recommender
    def recommend_by_preferences(self, prefs):
        try:
            query_text = " ".join([
                prefs.get("type", ""),
                prefs.get("sweetness", ""),
                prefs.get("body", ""),
                prefs.get("flavor_notes", ""),
                prefs.get("region", "")
            ]).lower()

            query_vec = self.vectorizer.transform([query_text])
            similarity_scores = cosine_similarity(query_vec, self.tfidf_matrix)[0]

            top_indices = similarity_scores.argsort()[-5:][::-1]
            results = self.wine_df.iloc[top_indices][
                ["Title", "Grape", "Country", "Region", "Style", "Price"]
            ].copy()
            results["similarity_score"] = [round(similarity_scores[i], 3) for i in top_indices]

            return results.to_dict(orient="records")

        except Exception as e:
            print(f"ERROR in recommend_by_preferences: {e}")
            return [{"error": str(e)}]

    # Rating-based recommender
  
    def recommend_by_user_ratings(self, rated_wines):
        try:
            rated_df = self.wine_df[self.wine_df["Title"].isin(rated_wines.keys())].copy()
            if rated_df.empty:
                print("⚠️ No matching rated wines found.")
                return []

            # Weight user ratings
            weights = np.array([rated_wines[title] for title in rated_df["Title"]])
            weights = weights / weights.sum()

            # Build user taste profile
            rated_df["profile_text"] = (
                rated_df["Type"].fillna('') + ' ' +
                rated_df["Style"].fillna('') + ' ' +
                rated_df["Characteristics"].fillna('') + ' ' +
                rated_df["Region"].fillna('') + ' ' +
                rated_df["Country"].fillna('')
            ).str.lower()

            rated_vecs = self.vectorizer.transform(rated_df["profile_text"])
            weighted_profile = np.average(rated_vecs.toarray(), axis=0, weights=weights)

            # Compare against all wines
            similarity_scores = cosine_similarity([weighted_profile], self.tfidf_matrix)[0]
            self.wine_df["similarity_score"] = similarity_scores

            # Exclude wines already rated
            recommendations = self.wine_df[
                ~self.wine_df["Title"].isin(rated_wines.keys())
            ].sort_values(by="similarity_score", ascending=False).head(5)

            return recommendations[
                ["Title", "Grape", "Country", "Region", "Style", "Price", "similarity_score"]
            ].to_dict(orient="records")

        except Exception as e:
            print(f"ERROR in recommend_by_user_ratings: {e}")
            return [{"error": str(e)}]


# CLI

def ask_user_preferences():
    print("\n🍷 Let's find your perfect wine!")
    prefs = {
        "type": input("Type (red, white, rosé): ").strip(),
        "sweetness": input("Sweetness (dry, off-dry, sweet): ").strip(),
        "body": input("Body (light, medium, full): ").strip(),
        "flavor_notes": input("Flavor notes (e.g., fruity, spicy, earthy, floral, buttery): ").strip(),
        "region": input("Preferred region or country: ").strip()
    }
    print("\n✅ Preferences collected:")
    print(json.dumps(prefs, indent=2))
    return prefs


def ask_user_ratings():
    print("\n⭐ Rate a few wines you've tried (1–5 scale). Leave blank if not applicable.\n")
    sample_wines = [
        "The Guv'nor, Spain",
        "Oyster Bay Sauvignon Blanc 2022, Marlborough",
        "Bread & Butter Chardonnay 2020/21, California",
        "LB7 Red 2020/21, Lisbon",
        "Bouvet Ladubay Saumur Brut, Loire"
    ]
    ratings = {}
    for wine in sample_wines:
        val = input(f"Rate '{wine}' (1–5): ").strip()
        if val.isdigit() and 1 <= int(val) <= 5:
            ratings[wine] = int(val)

    print("\n✅ Ratings collected:")
    print(json.dumps(ratings, indent=2))
    return ratings


def display_results(results):
    print("\n🎯 Top 5 Recommended Wines:")
    print("-" * 60)
    for wine in results:
        print(f"- {wine['Title']} ({wine['Country']}) — {wine['Grape']} - {wine['Style']}, {wine['Price']} (score: {wine['similarity_score']})")
    print("-" * 60)


# Main Program

if __name__ == "__main__":
    print("🧪 Interactive Wine Recommender\n")
    recommender = WineRecommender("data/wine_data.csv")

    choice = input("Would you like recommendations by (1) Preference or (2) Ratings? Enter 1 or 2: ").strip()

    if choice == "1":
        prefs = ask_user_preferences()
        results = recommender.recommend_by_preferences(prefs)
        display_results(results)

    elif choice == "2":
        ratings = ask_user_ratings()
        results = recommender.recommend_by_user_ratings(ratings)
        display_results(results)

    else:
        print("❌ Invalid selection. Please run again and choose 1 or 2.")
