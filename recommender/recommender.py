import pandas as pd
import numpy as np
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class WineRecommender:
    CURRENCY_TO_GBP = {"GBP": 1.0, "USD": 0.79, "EUR": 0.86}

    def __init__(self, csv_path):
        print(f"📂 Loading wine data from: {csv_path}")
        self.wine_df = pd.read_csv(csv_path)
        self.wine_df["price_gbp"] = self.wine_df["Price"].apply(self._parse_price)
        self.wine_df["is_case_product"] = (
            self.wine_df["Title"].fillna("").str.contains(
                r"\bcase\b", case=False, regex=True
            )
            | self.wine_df["Price"].fillna("").str.contains(
                "per case", case=False, regex=False
            )
        )

        # Weighted descriptive fields
        self.wine_df["combined_text"] = (
            (self.wine_df["Type"].fillna('') + ' ') * 3 +
            (self.wine_df["Style"].fillna('') + ' ') * 2 +
            (self.wine_df["Characteristics"].fillna('') + ' ') * 5 +
            (self.wine_df["Grape"].fillna('') + ' ') * 3 +
            self.wine_df["Description"].fillna('') + ' ' +
            (self.wine_df["Region"].fillna('') + ' ') * 2 +
            self.wine_df["Country"].fillna('')
        ).str.lower()

        # TF-IDF with bigrams to capture phrases like “dry red” or “fruity white”
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        self.tfidf_matrix = self.vectorizer.fit_transform(self.wine_df["combined_text"])
        print("✅ TF-IDF matrix built successfully.\n")

    @staticmethod
    def _parse_price(value):
        match = re.search(r"(?:£|\$|€)?\s*(\d+(?:\.\d{1,2})?)", str(value))
        return float(match.group(1)) if match else np.nan

    def _serialize_results(self, indices, similarity_scores, currency="GBP"):
        columns = ["Title", "Grape", "Country", "Region", "Style", "Price"]
        results = self.wine_df.loc[indices, columns].copy()
        results["similarity_score"] = [
            round(float(similarity_scores[index]), 3) for index in indices
        ]
        results = results.replace([np.inf, -np.inf], None)
        results = results.astype(object).where(pd.notna(results), None)
        if currency != "GBP":
            results["Price"] = results["Price"].apply(
                lambda value: self._format_price(value, currency)
            )
        return results.to_dict(orient="records")

    @classmethod
    def _format_price(cls, value, currency):
        price_gbp = cls._parse_price(value)
        if np.isnan(price_gbp):
            return value
        conversion = cls.CURRENCY_TO_GBP.get(currency, 1.0)
        converted = price_gbp / conversion
        symbol = {"USD": "$", "EUR": "€"}.get(currency, "£")
        unit_match = re.search(r"\b(per bottle|per case|each)\b", str(value), re.I)
        unit = f" {unit_match.group(1).lower()}" if unit_match else ""
        return f"{symbol}{converted:.2f}{unit}"

    # ------------------------------
    # 1️⃣ User Preference Recommender
    # ------------------------------
    def recommend_by_preferences(self, prefs):
        """
        Recommend wines based on explicit user preferences.
        prefs should include: type, sweetness, body, flavor_notes, region
        """
        query_text = " ".join([
            prefs.get("type", ""),
            prefs.get("sweetness", ""),
            prefs.get("body", ""),
            prefs.get("flavor_notes", ""),
            prefs.get("region", "")
        ]).lower()
        min_price = prefs.get("min_price")
        max_price = prefs.get("max_price")
        if not query_text.strip() and min_price is None and max_price is None:
            raise ValueError("At least one wine preference is required.")

        query_vec = self.vectorizer.transform([query_text])
        similarity_scores = cosine_similarity(query_vec, self.tfidf_matrix)[0]

        similarity_scores = np.nan_to_num(
            similarity_scores, nan=0.0, posinf=0.0, neginf=0.0
        )

        candidate_mask = ~self.wine_df["is_case_product"]
        wine_type = prefs.get("type", "").strip().lower().replace(" wine", "")
        if wine_type and wine_type != "any":
            candidate_mask &= self.wine_df["Type"].fillna("").str.contains(
                wine_type, case=False, regex=False
            )

        region = prefs.get("region", "").strip()
        region = {
            "united states": "USA",
            "united states of america": "USA",
            "us": "USA",
            "u.s.": "USA",
            "uk": "United Kingdom",
        }.get(region.lower(), region)
        if region and region.lower() != "any":
            candidate_mask &= (
                self.wine_df["Region"].fillna("").str.contains(region, case=False, regex=False)
                | self.wine_df["Country"].fillna("").str.contains(region, case=False, regex=False)
            )

        currency = str(prefs.get("currency") or "GBP").upper()
        conversion = self.CURRENCY_TO_GBP.get(currency, 1.0)
        if min_price is not None:
            candidate_mask &= self.wine_df["price_gbp"] >= float(min_price) * conversion
        if max_price is not None:
            candidate_mask &= self.wine_df["price_gbp"] <= float(max_price) * conversion

        candidate_indices = self.wine_df.index[candidate_mask].to_numpy()
        if not len(candidate_indices):
            return []

        ranked_candidates = candidate_indices[
            similarity_scores[candidate_indices].argsort()[::-1]
        ]
        return self._serialize_results(
            ranked_candidates[:5], similarity_scores, currency=currency
        )

    def recommend_by_title(self, title):
        matches = self.wine_df[
            self.wine_df["Title"].fillna("").str.contains(title, case=False, regex=False)
        ]
        if matches.empty:
            return None

        exact_matches = matches[matches["Title"].str.casefold() == title.casefold()]
        selected_index = exact_matches.index[0] if not exact_matches.empty else matches.index[0]
        similarity_scores = cosine_similarity(
            self.tfidf_matrix[selected_index], self.tfidf_matrix
        )[0]
        similarity_scores[selected_index] = -1
        similarity_scores[self.wine_df["is_case_product"].to_numpy()] = -1
        top_indices = similarity_scores.argsort()[::-1][:5]
        return self._serialize_results(top_indices, similarity_scores)

    # ------------------------------
    # 2️⃣ User Rating Recommender
    # ------------------------------
    def recommend_by_user_ratings(self, rated_wines):
        """
        Recommend wines based on user's rated wines.
        rated_wines should be a dict of {wine_title: rating (1-5)}.
        """
        rated_df = self.wine_df[self.wine_df["Title"].isin(rated_wines.keys())].copy()
        if rated_df.empty:
            return []

        ratings = np.array([rated_wines[title] for title in rated_df["Title"]], dtype=float)
        if np.any((ratings < 1) | (ratings > 5)):
            raise ValueError("Ratings must be between 1 and 5.")

        rated_df["profile_text"] = (
            rated_df["Type"].fillna('') + ' ' +
            rated_df["Style"].fillna('') + ' ' +
            rated_df["Characteristics"].fillna('') + ' ' +
            rated_df["Region"].fillna('') + ' ' +
            rated_df["Country"].fillna('')
        ).str.lower()

        rated_vecs = self.vectorizer.transform(rated_df["profile_text"]).toarray()
        positive_mask = ratings > 3
        if not positive_mask.any():
            return []

        positive_weights = ratings[positive_mask] - 3
        positive_profile = np.average(
            rated_vecs[positive_mask], axis=0, weights=positive_weights
        )
        similarity_scores = cosine_similarity([positive_profile], self.tfidf_matrix)[0]

        negative_mask = ratings < 3
        if negative_mask.any():
            negative_weights = 3 - ratings[negative_mask]
            negative_profile = np.average(
                rated_vecs[negative_mask], axis=0, weights=negative_weights
            )
            similarity_scores -= 0.5 * cosine_similarity(
                [negative_profile], self.tfidf_matrix
            )[0]

        similarity_scores = np.nan_to_num(
            similarity_scores, nan=0.0, posinf=0.0, neginf=0.0
        )
        eligible_indices = self.wine_df.index[
            ~self.wine_df["Title"].isin(rated_wines.keys())
            & ~self.wine_df["is_case_product"]
        ].to_numpy()
        ranked_indices = eligible_indices[
            similarity_scores[eligible_indices].argsort()[::-1]
        ][:5]
        return self._serialize_results(ranked_indices, similarity_scores)
