import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class WineRecommender:
    def __init__(self, csv_path):
        #https://www.kaggle.com/datasets/elvinrustam/wine-dataset
        print(f"📂 Loading wine data from: {csv_path}")
        self.wine_df = pd.read_csv(csv_path)
        print(f"✅ Loaded wine data: {self.wine_df.shape}")
        print(f"📊 Columns: {list(self.wine_df.columns)}")

        # Combine descriptive fields with weighting, then lowercase
        self.wine_df["combined_text"] = (
            3 * self.wine_df["Type"].fillna('') + ' ' +
            2 * self.wine_df["Style"].fillna('') + ' ' +
            5 * self.wine_df["Characteristics"].fillna('') + ' ' +
            3 * self.wine_df["Grape"].fillna('') + ' ' +
            self.wine_df["Description"].fillna('') + ' ' +
            2 * self.wine_df["Region"].fillna('') + ' ' +
            self.wine_df["Country"].fillna('')
        ).str.lower()

        # TF-IDF with n-grams (1, 2) to capture pairs like "fruity white"
        self.vectorizer = TfidfVectorizer(stop_words='english', ngram_range=(1, 2))
        self.tfidf_matrix = self.vectorizer.fit_transform(self.wine_df["combined_text"])
        print("✅ TF-IDF matrix built successfully.\n")

    def recommend_by_preferences(self, prefs):
        """Recommend wines using cosine similarity with TF-IDF features."""
        try:
            # Optional filtering by type (e.g., white, red)
            filtered_df = self.wine_df
            if prefs.get("type"):
                filtered_df = filtered_df[
                    filtered_df["Type"].str.lower() == prefs["type"].lower()
                ]
                if filtered_df.empty:
                    print("⚠️ No wines match the selected type. Using full dataset.")
                    filtered_df = self.wine_df

            # Combine text preferences into a single query string
            query_text = " ".join([
                prefs.get("type", ""),
                prefs.get("sweetness", ""),
                prefs.get("body", ""),
                prefs.get("flavor_notes", ""),
                prefs.get("region", "")
            ]).lower()

            # Vectorize the query and compute cosine similarity
            query_vec = self.vectorizer.transform([query_text])
            tfidf_matrix_subset = self.vectorizer.transform(filtered_df["combined_text"])
            similarity_scores = cosine_similarity(query_vec, tfidf_matrix_subset)[0]

            # Top 5 recommendations
            top_indices = similarity_scores.argsort()[-5:][::-1]
            results = filtered_df.iloc[top_indices][
                ["Title", "Grape", "Country", "Region", "Style", "Price"]
            ].copy()
            results["similarity_score"] = [round(similarity_scores[i], 3) for i in top_indices]
            results = results.replace([np.nan, np.inf, -np.inf], "").to_dict(orient="records")

            print(f"Top 5 similarity scores: {sorted(similarity_scores, reverse=True)[:5]}")
            print(f"Returning {len(results)} recommendations.\n")
            return results

        except Exception as e:
            print(f"ERROR in recommender: {e}")
            return [{"error": str(e)}]
