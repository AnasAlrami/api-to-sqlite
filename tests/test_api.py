import pytest
import requests

import api

RAW_USER = {
    "id": 1,
    "name": "Leanne Graham",
    "username": "Bret",
    "email": "Sincere@april.biz",
    "address": {"street": "Kulas Light", "city": "Gwenborough"},
    "phone": "1-770-736-8031",
}
RAW_TODO = {"userId": 1, "id": 7, "title": "illo expedita consequatur", "completed": True}


class FakeResponse:
    """A response whose status check and JSON decoding can be told to fail."""

    def __init__(self, payload: object = None, error: Exception | None = None, bad_json: bool = False) -> None:
        """Store what the fake response should do."""
        self.payload = payload
        self.error = error
        self.bad_json = bad_json

    def raise_for_status(self) -> None:
        """Raise the configured error, like a 404 or 500 response would."""
        if self.error:
            raise self.error

    def json(self) -> object:
        """Return the payload, or fail like a response that isn't JSON."""
        if self.bad_json:
            raise ValueError("not json")
        return self.payload


def test_parse_user_keeps_the_needed_fields_and_flattens_the_city() -> None:
    assert api.parse_user(RAW_USER) == {
        "id": 1,
        "name": "Leanne Graham",
        "username": "Bret",
        "email": "Sincere@april.biz",
        "city": "Gwenborough",
    }


def test_parse_todo_renames_user_id_and_stores_completed_as_an_integer() -> None:
    assert api.parse_todo(RAW_TODO) == {
        "id": 7,
        "user_id": 1,
        "title": "illo expedita consequatur",
        "completed": 1,
    }
    assert api.parse_todo({**RAW_TODO, "completed": False})["completed"] == 0


def test_get_json_returns_the_decoded_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api.requests, "get", lambda url, timeout: FakeResponse([{"id": 1}]))
    assert api.get_json("https://example.test/users") == [{"id": 1}]


def test_get_json_always_sets_a_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    def fake_get(url: str, timeout: float) -> FakeResponse:
        seen["timeout"] = timeout
        return FakeResponse([])

    monkeypatch.setattr(api.requests, "get", fake_get)
    api.get_json("https://example.test/users")
    assert seen["timeout"] == 10


@pytest.mark.parametrize(
    "response",
    [
        FakeResponse(error=requests.HTTPError("404 Not Found")),
        FakeResponse(bad_json=True),
    ],
    ids=["http-error", "invalid-json"],
)
def test_get_json_exits_with_code_1_and_a_readable_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, response: FakeResponse
) -> None:
    monkeypatch.setattr(api.requests, "get", lambda url, timeout: response)
    with pytest.raises(SystemExit) as exit_info:
        api.get_json("https://example.test/users")
    assert exit_info.value.code == 1
    assert "Error: could not fetch https://example.test/users" in capsys.readouterr().out


def test_get_json_exits_with_code_1_when_the_network_is_down(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    def no_network(url: str, timeout: float) -> FakeResponse:
        raise requests.ConnectionError("network down")

    monkeypatch.setattr(api.requests, "get", no_network)
    with pytest.raises(SystemExit) as exit_info:
        api.get_json("https://example.test/users")
    assert exit_info.value.code == 1
    assert "network down" in capsys.readouterr().out


def test_fetch_users_and_todos_parse_every_item(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "get_json", lambda url: [RAW_USER] if url == api.USERS_URL else [RAW_TODO])
    assert [u["city"] for u in api.fetch_users()] == ["Gwenborough"]
    assert [t["user_id"] for t in api.fetch_todos()] == [1]
