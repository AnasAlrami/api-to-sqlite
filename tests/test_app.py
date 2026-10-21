from collections.abc import Iterator
from decimal import Decimal

import pymysql
import pytest
from fastapi.testclient import TestClient

from app import app, get_database


class FakeDatabase:
    """A database that returns rows shaped like MySQL's, including Decimal values."""

    def completion_by_user(self) -> list[tuple]:
        """Return two users, highest percentage first."""
        return [
            ("Clementina DuBuque", 20, Decimal("12"), Decimal("60.0")),
            ("Patricia Lebsack", 20, Decimal("6"), Decimal("30.0")),
        ]

    def users_below_half(self) -> list[tuple]:
        """Return the one user below 50 percent."""
        return [("Patricia Lebsack", 20, Decimal("6"), Decimal("30.0"))]

    def cities_with_most_unfinished(self) -> list[tuple]:
        """Return a two-way tie."""
        return [("South Christy", 14), ("South Elvis", 14)]


class BrokenDatabase:
    """A database that has lost its connection."""

    def completion_by_user(self) -> list[tuple]:
        """Fail like a dropped connection."""
        raise pymysql.OperationalError(2013, "lost connection to server")


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Serve the app with a fake database, without opening a real MySQL connection."""
    app.dependency_overrides[get_database] = lambda: FakeDatabase()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health_reports_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_completion_report_returns_numbers_not_decimals(client: TestClient) -> None:
    response = client.get("/reports/completion")
    assert response.status_code == 200
    assert response.json()[0] == {"name": "Clementina DuBuque", "total": 20, "done": 12, "pct": 60.0}


def test_below_half_report_lists_only_the_low_completion_users(client: TestClient) -> None:
    response = client.get("/reports/below-half")
    assert response.status_code == 200
    assert [row["name"] for row in response.json()] == ["Patricia Lebsack"]


def test_unfinished_cities_report_includes_every_tied_city(client: TestClient) -> None:
    response = client.get("/reports/unfinished-cities")
    assert response.status_code == 200
    assert response.json() == [
        {"city": "South Christy", "unfinished": 14},
        {"city": "South Elvis", "unfinished": 14},
    ]


def test_database_errors_return_503_without_leaking_details() -> None:
    app.dependency_overrides[get_database] = lambda: BrokenDatabase()
    try:
        response = TestClient(app).get("/reports/completion")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.json() == {"detail": "Database is unavailable"}
    assert "lost connection" not in response.text


def test_swagger_ui_and_openapi_spec_are_served(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    spec = client.get("/openapi.json").json()
    assert set(spec["paths"]) == {
        "/health",
        "/reports/completion",
        "/reports/below-half",
        "/reports/unfinished-cities",
    }
    assert {"CompletionRow", "UnfinishedCity"} <= set(spec["components"]["schemas"])
