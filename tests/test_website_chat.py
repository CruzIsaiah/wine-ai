import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from google.adk.events import Event
from google.genai import types

import main


client = TestClient(main.app, headers={"x-api-token": main.demo_api_token})


def test_website_uses_expanded_catalog():
    assert client.get("/health").json()["wines_loaded"] == 184
    assert main.catalog_wine("Rieslingfreak 2025 No. 55 Riesling") is not None


@pytest.mark.parametrize("producer", ["Cooper's Hawk", "Cooper’s Hawk", "coopers hawk"])
def test_producer_exclusion_refines_engine_results_and_persists(producer):
    context = SimpleNamespace(state={})
    asyncio.run(main.recommend_wines({"type": "white", "sweetness": "off-dry"}, context))
    result = asyncio.run(main.recommend_wines({"excluded_producers": [producer]}, context))
    assert len(result["recommendations"]) == 5
    assert all("cooper" not in wine["Title"].lower() for wine in result["recommendations"])
    assert result["preferences"]["sweetness"] == "off-dry"
    refined = asyncio.run(main.recommend_wines({"max_price": 20}, context))
    assert refined["preferences"]["excluded_producers"] == [producer]
    assert all("cooper" not in wine["Title"].lower() for wine in refined["recommendations"])
    cleared = asyncio.run(main.recommend_wines({"excluded_producers": []}, context))
    assert cleared["preferences"]["excluded_producers"] == []


def tool_event(result):
    return Event(author="website_sommelier", content=types.Content(
        role="user", parts=[types.Part(function_response=types.FunctionResponse(
            name="recommend_wines", response=result,
        ))],
    ))


def final_event(text):
    return Event(author="website_sommelier", content=types.Content(
        role="model", parts=[types.Part(text=text)],
    ))


def test_chat_returns_engine_results_and_interpreted_preferences(monkeypatch):
    profile = {"type": "white", "sweetness": "off-dry", "max_price": 20, "currency": "USD"}
    expected = main.recommender.recommend_by_preferences(profile)
    assert expected

    async def runner(**kwargs):
        assert kwargs["new_message"].parts[0].text == "A slightly sweet white under $20"
        result = await main.recommend_wines(profile, SimpleNamespace(state={}))
        yield tool_event(result)
        yield final_event("Here are your closest matches.")

    monkeypatch.setattr(main, "has_gemini_key", lambda: True)
    monkeypatch.setattr(main.chat_runner, "run_async", runner)
    response = client.post("/chat", json={"message": "A slightly sweet white under $20"})
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"]
    assert body["message"] == "Here are your closest matches."
    assert body["recommendations"] == expected  # Including rank, prices and catalog facts.
    assert body["preferences"]["max_price"] == 20
    assert all(float(wine["Price"].split("$")[1].split()[0]) <= 20 for wine in body["recommendations"])


def test_refinement_retains_budget_and_region_and_can_clear_them():
    context = SimpleNamespace(state={})
    asyncio.run(main.recommend_wines({"type": "red", "region": "USA", "max_price": 30}, context))
    refined = asyncio.run(main.recommend_wines({"body": "light"}, context))
    assert refined["preferences"]["max_price"] == 30
    assert refined["preferences"]["region"] == "USA"
    assert refined["recommendations"] == main.recommender.recommend_by_preferences(refined["preferences"])
    cleared = asyncio.run(main.recommend_wines({"region": "", "max_price": None}, context))
    assert cleared["preferences"]["max_price"] is None
    assert cleared["preferences"]["region"] == ""
    fresh = asyncio.run(main.recommend_wines({"type": "white"}, context, reset=True))
    assert fresh["preferences"]["body"] == ""
    assert fresh["preferences"]["type"] == "white"


def test_invalid_budget_never_reaches_engine(monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("Invalid preferences reached the recommender")

    monkeypatch.setattr(main.recommender, "recommend_by_preferences", unexpected)
    context = SimpleNamespace(state={})
    result = asyncio.run(main.recommend_wines({"min_price": 30, "max_price": 20}, context))
    assert "error" in result
    assert context.state == {}


def test_follow_up_uses_same_session_and_does_not_repeat_cards(monkeypatch):
    session_ids = []

    async def runner(**kwargs):
        session_ids.append(kwargs["session_id"])
        yield final_event("Serve the first wine slightly cool.")

    monkeypatch.setattr(main, "has_gemini_key", lambda: True)
    monkeypatch.setattr(main.chat_runner, "run_async", runner)
    first = client.post("/chat", json={"message": "Tell me about a red wine"}).json()
    second = client.post("/chat", json={"message": "How do I serve it?", "session_id": first["session_id"]}).json()
    assert session_ids == [first["session_id"], first["session_id"]]
    assert second["recommendations"] == []
    assert second["preferences"] is None


def test_named_wine_uses_title_engine_and_converts_prices():
    title = main.recommender.wine_df.iloc[0]["Title"]
    expected = main.recommender.recommend_by_title(title)
    result = asyncio.run(main.recommend_wines({}, SimpleNamespace(state={}), wine_name=title))
    assert [wine["Title"] for wine in result["recommendations"]] == [wine["Title"] for wine in expected]
    assert all(wine["Price"].startswith("$") for wine in result["recommendations"])


def test_named_wine_with_budget_keeps_engine_constraints():
    title = main.recommender.wine_df.iloc[0]["Title"]
    result = asyncio.run(main.recommend_wines(
        {"max_price": 20, "currency": "EUR"}, SimpleNamespace(state={}), wine_name=title,
    ))
    assert result["preferences"]["max_price"] == 20
    assert result["recommendations"] == main.recommender.recommend_by_preferences(result["preferences"])


def test_empty_results_do_not_relax_constraints():
    result = asyncio.run(main.recommend_wines(
        {"type": "red", "max_price": 0.01}, SimpleNamespace(state={}),
    ))
    assert result["recommendations"] == []
    assert result["preferences"]["max_price"] == 0.01


def test_model_failure_after_tool_keeps_real_catalog_results(monkeypatch):
    wines = [{"Title": "Catalog bottle", "Price": "$19"}]

    async def runner(**kwargs):
        yield tool_event({"recommendations": wines, "preferences": {"max_price": 20}})
        raise RuntimeError("Provider unavailable")

    monkeypatch.setattr(main, "has_gemini_key", lambda: True)
    monkeypatch.setattr(main.chat_runner, "run_async", runner)
    response = client.post("/chat", json={"message": "A wine under $20"})
    assert response.status_code == 200
    assert response.json()["recommendations"] == wines
    assert "ranked" in response.json()["message"]


def test_model_failure_offers_manual_preferences_without_guessed_wines(monkeypatch):
    async def runner(**kwargs):
        raise RuntimeError("Provider unavailable")
        yield  # Make this a failing async iterator.

    monkeypatch.setattr(main, "has_gemini_key", lambda: True)
    monkeypatch.setattr(main.chat_runner, "run_async", runner)
    response = client.post("/chat", json={"message": "A wine under $20"})
    assert response.status_code == 503
    assert "Set preferences" in response.json()["detail"]


def test_missing_key_and_blank_input_are_handled(monkeypatch):
    monkeypatch.setattr(main, "has_gemini_key", lambda: False)
    assert client.post("/chat", json={"message": "A white wine"}).status_code == 503
    assert client.post("/chat", json={"message": "   "}).status_code == 422


def test_chat_requires_api_token():
    assert TestClient(main.app).post("/chat", json={"message": "A red wine"}).status_code == 401


@pytest.mark.parametrize("entries,expected", [
    ([], "don’t have any rated wines"),
    ([{"wine_name": "Some bottle", "rating": 3}], "4 or 5 stars"),
    ([{"wine_name": "Unknown favorite", "rating": 5}], "couldn’t match"),
])
def test_journal_fallbacks_do_not_invent_favorites(entries, expected):
    result = asyncio.run(main.recommend_from_journal(SimpleNamespace(state={"temp:journal_ratings": entries})))
    assert result["recommendations"] == []
    assert expected in result["message"]
    assert "Josh" not in result["message"]


def test_journal_uses_actual_ratings_engine_and_excludes_rated_wines():
    titles = main.recommender.wine_df["Title"].tolist()
    ratings = {titles[0]: 5, titles[1]: 4, titles[2]: 1}
    entries = [{"wine_name": title, "rating": rating} for title, rating in ratings.items()]
    # A stale earlier rating for the same bottle must not replace its latest rating.
    entries.append({"wine_name": titles[0].lower(), "rating": 1})
    context = SimpleNamespace(state={"temp:journal_ratings": entries})
    result = asyncio.run(main.recommend_from_journal(context))
    expected = main.recommender.recommend_by_user_ratings(ratings)
    assert [wine["Title"] for wine in result["recommendations"]] == [wine["Title"] for wine in expected]
    assert set(result["liked_wines"]) == {titles[0], titles[1]}
    assert all(wine["Title"] not in ratings for wine in result["recommendations"])
    assert all(wine["Price"].startswith("$") for wine in result["recommendations"])
    assert context.state["recommended_wines"]


def test_saving_resolves_only_real_recommendations_and_deduplicates():
    context = SimpleNamespace(state={})
    result = asyncio.run(main.recommend_wines({"type": "red"}, context))
    first = result["recommendations"][0]
    saved = main.add_wines_to_list([first["Title"], first["Title"].upper()], context)
    assert saved["list_additions"] == [first]
    assert "error" in main.add_wines_to_list(["An invented bottle"], context)
    assert "error" in main.add_wines_to_list([], context)
    assert "error" in main.add_wines_to_list([first["Title"], "An invented bottle"], context)


def test_journal_ratings_reach_tool_and_save_actions_reach_browser(monkeypatch):
    title = main.recommender.wine_df.iloc[0]["Title"]
    wine = {"Title": title, "Price": "$20"}

    async def runner(**kwargs):
        assert kwargs["state_delta"]["temp:journal_ratings"] == [{"wine_name": title, "rating": 5}]
        yield Event(author="website_sommelier", content=types.Content(role="user", parts=[
            types.Part(function_response=types.FunctionResponse(name="add_wines_to_list", response={"list_additions": [wine]}))
        ]))
        # Saving must still work if the final model response fails.
        raise RuntimeError("Provider unavailable after tool")

    monkeypatch.setattr(main, "has_gemini_key", lambda: True)
    monkeypatch.setattr(main.chat_runner, "run_async", runner)
    response = client.post("/chat", json={
        "message": "Add the first wine to my list",
        "journal_ratings": [{"wine_name": title, "rating": 5}],
    })
    assert response.status_code == 200
    assert response.json()["list_additions"] == [wine]
    assert response.json()["recommendations"] == []


def test_journal_ratings_are_validated():
    response = client.post("/chat", json={"message": "My favorites", "journal_ratings": [{"wine_name": "Wine", "rating": 8}]})
    assert response.status_code == 422


def test_save_named_catalog_bottle_without_prior_recommendations():
    title = main.recommender.wine_df.iloc[0]["Title"]
    result = main.add_wines_to_list([title], SimpleNamespace(state={}))
    assert result["list_additions"][0]["Title"] == title


def test_journal_action_allows_unrated_and_uses_browser_date():
    context = SimpleNamespace(state={"temp:local_date": "2026-10-07"})
    result = main.add_wine_to_journal("A favorite I tasted", context)
    entry = result["journal_additions"][0]
    assert entry["wine_name"] == "A favorite I tasted"
    assert entry["rating"] is None
    assert entry["date_tried"] == "2026-10-07"
    assert entry["notes"] == ""
    assert "error" in main.add_wine_to_journal("it", context)
    assert "error" in main.add_wine_to_journal("Wine name", context, rating=6)


def test_explore_context_and_both_actions_survive_lost_session(monkeypatch):
    wine = main.catalog_wine(main.recommender.wine_df.iloc[0]["Title"])

    async def runner(**kwargs):
        state = kwargs["state_delta"]
        assert wine["Title"].casefold() in state["recommended_wines"]
        assert wine["Title"] in kwargs["new_message"].parts[0].text
        context = SimpleNamespace(state=state)
        for name, result in [
            ("add_wines_to_list", main.add_wines_to_list([wine["Title"]], context)),
            ("add_wine_to_journal", main.add_wine_to_journal(wine["Title"], context, rating=4, notes="Lovely citrus")),
        ]:
            yield Event(author="website_sommelier", content=types.Content(role="user", parts=[
                types.Part(function_response=types.FunctionResponse(name=name, response=result))
            ]))
        yield final_event("Ready to save.")

    monkeypatch.setattr(main, "has_gemini_key", lambda: True)
    monkeypatch.setattr(main.chat_runner, "run_async", runner)
    response = client.post("/chat", json={
        "message": "Add this to My List and my journal, four stars. Lovely citrus.",
        "session_id": "expired-session", "selected_wine_title": wine["Title"], "local_date": "2026-10-07",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["list_additions"][0]["Title"] == wine["Title"]
    assert body["journal_additions"][0]["rating"] == 4
    assert body["journal_additions"][0]["date_tried"] == "2026-10-07"
    assert body["journal_additions"][0]["notes"] == "Lovely citrus"
    assert body["session_id"] != "expired-session"


FALSE_CATALOG_CLAIM = "Our catalog exclusively features Cooper's Hawk wines, so I cannot exclude them."


def test_false_catalog_claim_retries_with_real_engine_and_retains_preferences(monkeypatch):
    context = SimpleNamespace(state={})
    asyncio.run(main.recommend_wines({"type": "white", "sweetness": "off-dry"}, context))
    calls = []

    async def runner(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            yield final_event(FALSE_CATALOG_CLAIM)
        else:
            assert "not from coopers hawk" in kwargs["new_message"].parts[0].text
            result = await main.recommend_wines({"excluded_producers": ["coopers hawk"]}, context)
            yield tool_event(result)
            yield final_event("Here are wines from other producers.")

    monkeypatch.setattr(main, "has_gemini_key", lambda: True)
    monkeypatch.setattr(main.chat_runner, "run_async", runner)
    response = client.post("/chat", json={"message": "not from coopers hawk"})
    body = response.json()
    assert response.status_code == 200
    assert len(calls) == 2
    assert calls[0]["session_id"] == calls[1]["session_id"]
    assert len(body["recommendations"]) == 5
    assert all("cooper" not in w["Title"].lower() for w in body["recommendations"])
    assert body["preferences"]["sweetness"] == "off-dry"
    assert body["preferences"]["max_price"] is None


def test_repeated_false_claim_is_replaced_without_infinite_retry(monkeypatch):
    calls = []

    async def runner(**kwargs):
        calls.append(kwargs)
        yield final_event(FALSE_CATALOG_CLAIM)

    monkeypatch.setattr(main.chat_runner, "run_async", runner)
    message, wines, *_ = asyncio.run(main.run_chat_agent(
        "test", types.Content(role="user", parts=[types.Part(text="not from coopers hawk")])
    ))
    assert len(calls) == 2
    assert "couldn't complete" in message
    assert not wines
    assert not main.false_coopers_only_claim(message)


def test_false_explanation_preserves_successful_results_without_repeating_tools(monkeypatch):
    expected = main.recommender.recommend_by_preferences({"excluded_producers": ["coopers hawk"]})
    calls = []

    async def runner(**kwargs):
        calls.append(kwargs)
        yield tool_event({"recommendations": expected, "preferences": {"excluded_producers": ["coopers hawk"]}})
        yield final_event(FALSE_CATALOG_CLAIM)

    monkeypatch.setattr(main.chat_runner, "run_async", runner)
    result = asyncio.run(main.run_chat_agent("test", types.Content(role="user", parts=[types.Part(text="not from coopers hawk")])))
    assert len(calls) == 1
    assert result[1] == expected
    assert not main.false_coopers_only_claim(result[0])


@pytest.mark.parametrize("text", [
    "The catalog is not exclusively Cooper's Hawk.",
    "Our catalog doesn't only feature Cooper's Hawk wines.",
    "Only Cooper's Hawk bottles match those filters.",
    "Here are wines from other producers.",
])
def test_correct_statements_do_not_trigger_catalog_retry(text):
    assert not main.false_coopers_only_claim(text)


def test_lost_session_restores_confirmed_preferences_before_producer_refinement(monkeypatch):
    async def runner(**kwargs):
        state = kwargs["state_delta"]
        assert state["wine_preferences"]["sweetness"] == "off-dry"
        assert "Previous confirmed search preferences" in kwargs["new_message"].parts[0].text
        result = await main.recommend_wines(
            {"excluded_producers": ["coopers hawk"]}, SimpleNamespace(state=state)
        )
        yield tool_event(result)
        yield final_event("Here are your updated matches.")

    monkeypatch.setattr(main, "has_gemini_key", lambda: True)
    monkeypatch.setattr(main.chat_runner, "run_async", runner)
    body = client.post("/chat", json={
        "message": "not from coopers hawk", "session_id": "lost-session",
        "previous_preferences": {"type": "white", "sweetness": "off-dry", "max_price": 20},
    }).json()
    assert body["preferences"]["max_price"] == 20
    assert body["preferences"]["sweetness"] == "off-dry"
    assert body["recommendations"]
    assert all(w["Type"] == "White" and "cooper" not in w["Title"].lower() for w in body["recommendations"])


def test_restored_preferences_are_validated():
    response = client.post("/chat", json={
        "message": "not from coopers hawk", "previous_preferences": {"max_price": -1},
    })
    assert response.status_code == 422
