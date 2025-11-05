import pandas as pd
import numpy as np
import math
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class WineRecommender:
    def __init__(self, csv_path):
        print(f"📂 Loading wine data from: {csv_path}")
        self.wine_df = pd.read_csv(csv_path)
        print(f"✅ Loaded wine data: {self.wine_df.shape}")
        print(f"📊 Columns: {list(self.wine_df.columns)}")

        # Combine descriptive fields for TF-IDF
        self.wine_df["combined_text"] = (
            self.wine_df["Description"].fillna('') + ' ' +
            3 * self.wine_df["Grape"].fillna('') + ' ' +
            self.wine_df["Style"].fillna('') + ' ' +
            self.wine_df["Characteristics"].fillna('') + ' ' +
            self.wine_df["Region"].fillna('') + ' ' +
            self.wine_df["Country"].fillna('')
        )

        # Build TF-IDF matrix once
        self.vectorizer = TfidfVectorizer(stop_words='english')
        self.tfidf_matrix = self.vectorizer.fit_transform(self.wine_df["combined_text"])
        print("✅ TF-IDF matrix built successfully.\n")

    def recommend_by_preferences(self, prefs):
        """Recommend wines using cosine similarity with TF-IDF features."""
        try:
            # Build query text from preferences
            query_text = " ".join([
                prefs.get("type", ""),
                prefs.get("sweetness", ""),
                prefs.get("body", ""),
                prefs.get("flavor_notes", ""),
                prefs.get("region", "")
            ])

            # Transform the query and compute similarity
            query_vec = self.vectorizer.transform([query_text])
            similarity_scores = cosine_similarity(query_vec, self.tfidf_matrix)[0]

            # Get top 5 matches
            top_indices = similarity_scores.argsort()[-5:][::-1]
            results = self.wine_df.iloc[top_indices][
                ["Title", "Grape", "Country", "Region", "Style", "Price"]
            ].copy()

            # Add similarity score
            results["similarity_score"] = [round(similarity_scores[i], 3) for i in top_indices]

            # Convert to JSON-safe dict
            results = results.replace([np.nan, np.inf, -np.inf], "").to_dict(orient="records")

            print(f"🔍 Top 5 similarity scores: {sorted(similarity_scores, reverse=True)[:5]}")
            print(f"🍷 Returning {len(results)} recommendations.\n")
            return results

        except Exception as e:
            print(f"⚠️ ERROR in recommender: {e}")
            return [{"error": str(e)}]

