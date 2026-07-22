import pytest

from recommender.recommender import WineRecommender


@pytest.fixture(scope="module")
def recommender():
    return WineRecommender("data/wine_data.csv")


def test_preferences_enforce_type_and_country(recommender):
    results = recommender.recommend_by_preferences(
        {
            "type": "red",
            "sweetness": "dry",
            "body": "bold",
            "flavor_notes": "spicy",
            "region": "France",
        }
    )

    assert len(results) == 5
    assert all(result["Country"] == "France" for result in results)
    assert all(result["similarity_score"] >= 0 for result in results)


def test_preferences_require_at_least_one_value(recommender):
    with pytest.raises(ValueError, match="At least one"):
        recommender.recommend_by_preferences({})


def test_country_aliases_are_normalized(recommender):
    results = recommender.recommend_by_preferences(
        {"type": "red", "region": "United States"}
    )

    assert results
    assert all(result["Country"] == "USA" for result in results)


def test_title_recommendations_exclude_selected_wine(recommender):
    results = recommender.recommend_by_title("The Guv'nor")

    assert len(results) == 5
    assert all("The Guv'nor, Spain" != result["Title"] for result in results)


def test_unknown_title_returns_none(recommender):
    assert recommender.recommend_by_title("Definitely Not A Real Wine") is None


def test_ratings_validate_range(recommender):
    with pytest.raises(ValueError, match="between 1 and 5"):
        recommender.recommend_by_user_ratings({"The Guv'nor, Spain": 6})


def test_disliked_wines_are_not_recommended(recommender):
    ratings = {
        "The Guv'nor, Spain": 5,
        "Bouvet Ladubay Saumur Brut, Loire": 1,
    }
    results = recommender.recommend_by_user_ratings(ratings)

    assert len(results) == 5
    assert not {result["Title"] for result in results} & ratings.keys()
