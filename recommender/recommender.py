# recommender/recommender.py
from pathlib import Path
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class WineRecommender:
    def __init__(self, csv_path="data/wine_data.csv"):
        try:
            csv_file = Path(__file__).parent.parent / csv_path
            print(f"📂 Loading wine data from: {csv_file.resolve()}")

            self.wine_df = pd.read_csv(csv_file)
            print("✅ Loaded wine data:", self.wine_df.shape)
            print("📊 Columns:", list(self.wine_df.columns))

        except Exception as e:
            print(f"❌ Failed to load CSV: {e}")
            self.wine_df = pd.DataFrame()
            return

        # ---------- Create Combined Profile Text ----------
        self.wine_df["profile_text"] = (
            self.wine_df.get("Grape", "").fillna("") * 3 + " " +
            self.wine_df.get("Region", "").fillna("") * 2 + " " +
            self.wine_df.get("Description", "").fillna("") + " " +
            self.wine_df.get("Type", "").fillna("")
        )

        # ---------- TF-IDF Vectorization ----------
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.tfidf_matrix = self.vectorizer.fit_transform(self.wine_df["profile_text"])

        # ---------- Cosine Similarity Matrix ----------
        self.cosine_sim = cosine_similarity(self.tfidf_matrix)
        print("✅ Recommender initialized successfully.\n")

    # ----------------------------------------------------------------------
    # 1️⃣ Wine-to-Wine Recommendation (by title)
    # ----------------------------------------------------------------------
    def recommend(self, title: str, n: int = 5):
        if self.wine_df.empty:
            return [{"message": "Dataset not loaded."}]

        title_col = None
        for col in self.wine_df.columns:
            if col.lower() in ["title", "wine", "name"]:
                title_col = col
                break

        if not title_col:
            return [{"message": "No title column found in dataset."}]

        matches = self.wine_df[self.wine_df[title_col].str.contains(title, case=False, na=False)]
        if matches.empty:
            return [{"message": f"No matches found for '{title}'."}]

        idx = matches.index[0]
        sim_scores = list(enumerate(self.cosine_sim[idx]))
        sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)[1:n + 1]
        recs = self.wine_df.iloc[[i[0] for i in sim_scores]]

        cols = [c for c in ["Title", "Wine", "Name", "Grape", "Country", "Region", "Style", "Price"] if c in self.wine_df.columns]

        # 🧹 Clean NaN values before returning JSON
        clean_recs = recs[cols].fillna("").replace({float("nan"): None})
        return clean_recs.to_dict(orient="records")

    # ----------------------------------------------------------------------
    # 2️⃣ Taste-Quiz Preference Recommendation
    # ----------------------------------------------------------------------
    def recommend_by_preferences(self, prefs: dict, n: int = 5):
        if self.wine_df.empty:
            return [{"message": "Dataset not loaded."}]

        df = self.wine_df.copy()
        df["score"] = 0.0

        # --- Red intensity weighting ---
        if "red_intensity" in prefs:
            df["score"] += df["Type"].str.contains("Red", case=False, na=False) * prefs["red_intensity"]

        # --- Sweetness preference ---
        if "sweet" in prefs:
            if prefs["sweet"]:
                df["score"] += df["Description"].str.contains("sweet", case=False, na=False) * 3
            else:
                df["score"] -= df["Description"].str.contains("sweet", case=False, na=False) * 2

        # --- Bold preference ---
        if prefs.get("bold"):
            df["score"] += df["Style"].str.contains("Full", case=False, na=False) * 2
            df["score"] += df["Description"].str.contains("bold", case=False, na=False) * 2

        # --- Fruity preference ---
        if prefs.get("fruity"):
            df["score"] += df["Description"].str.contains("fruit", case=False, na=False) * 2

        # --- Earthy preference ---
        if prefs.get("earthy"):
            df["score"] += df["Description"].str.contains("earth", case=False, na=False) * 2

        # --- Region preference ---
        if prefs.get("region"):
            df["score"] += df["Region"].str.contains(prefs["region"], case=False, na=False) * 3

        # --- Rank and return ---
        recs = df.sort_values("score", ascending=False).head(n)
        cols = [c for c in ["Title", "Wine", "Name", "Grape", "Country", "Region", "Style", "Price"] if c in df.columns]

        # Clean NaN values before returning JSON
        clean_recs = recs[cols + ["score"]].fillna("").replace({float("nan"): None})
        return clean_recs.to_dict(orient="records")
