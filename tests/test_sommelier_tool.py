import requests

from manager.sub_agents.sommelier_agent.agent import send_to_recommender


class NotFoundResponse:
    status_code = 404

    def raise_for_status(self):
        raise requests.HTTPError(response=self)

    def json(self):
        return {"detail": {"wine_not_found": "Unknown Wine"}}


def test_unknown_wine_signal_is_preserved(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: NotFoundResponse())

    result = send_to_recommender({"wine_name": "Unknown Wine"})

    assert result == {"wine_not_found": "Unknown Wine"}
