import pymysql
import pytest

import main
from db import ConfigError


class FakeDatabase:
    """A database that records saves and closes, with canned report rows."""

    settings = {"database": "quicktask"}

    def __init__(self, below_half: list | None = None, broken: bool = False) -> None:
        """Set the report rows and whether queries should fail."""
        self.saved: tuple | None = None
        self.closed = False
        self.below_half = [] if below_half is None else below_half
        self.broken = broken

    def save_all(self, users: list, todos: list) -> None:
        """Record what was saved."""
        self.saved = (users, todos)

    def completion_by_user(self) -> list[tuple]:
        """Return one row, or fail like a lost connection."""
        if self.broken:
            raise pymysql.OperationalError(2013, "lost connection")
        return [("Ann", 20, 12, 60.0)]

    def users_below_half(self) -> list[tuple]:
        """Return the canned rows."""
        return self.below_half

    def cities_with_most_unfinished(self) -> list[tuple]:
        """Return a two-way tie."""
        return [("Oslo", 14), ("Rome", 14)]

    def close(self) -> None:
        """Record the close."""
        self.closed = True


def run_main(monkeypatch: pytest.MonkeyPatch, *argv: str) -> None:
    """Run main() as if the given arguments were typed on the command line."""
    monkeypatch.setattr("sys.argv", ["main.py", *argv])
    main.main()


def test_run_fetch_saves_what_the_api_returned(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    monkeypatch.setattr(main.api, "fetch_users", lambda: [{"id": 1}])
    monkeypatch.setattr(main.api, "fetch_todos", lambda: [{"id": 5}, {"id": 6}])
    database = FakeDatabase()
    main.run_fetch(database)
    assert database.saved == ([{"id": 1}], [{"id": 5}, {"id": 6}])
    assert "Saved 1 users and 2 todos to MySQL database 'quicktask'" in capsys.readouterr().out


def test_run_report_prints_all_three_sections(capsys: pytest.CaptureFixture) -> None:
    main.run_report(FakeDatabase(below_half=[("Ben", 20, 6, 30.0)]))
    out = capsys.readouterr().out
    assert "Completion by user" in out and "Ann" in out and "60.0%" in out
    assert "Users below 50% completion" in out and "Ben" in out
    assert "Oslo (14 unfinished)" in out and "Rome (14 unfinished)" in out


def test_run_report_says_none_when_nobody_is_below_half(capsys: pytest.CaptureFixture) -> None:
    main.run_report(FakeDatabase())
    assert "  none" in capsys.readouterr().out


def test_main_runs_the_chosen_command_and_closes_the_database(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    database = FakeDatabase()
    monkeypatch.setattr(main, "Database", lambda: database)
    run_main(monkeypatch, "report")
    assert "Completion by user" in capsys.readouterr().out
    assert database.closed


def test_main_exits_with_code_1_on_bad_settings(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    def bad_settings() -> None:
        raise ConfigError("DB_USER is not set")

    monkeypatch.setattr(main, "Database", bad_settings)
    with pytest.raises(SystemExit) as exit_info:
        run_main(monkeypatch, "report")
    assert exit_info.value.code == 1
    assert "bad database settings: DB_USER is not set" in capsys.readouterr().out


def test_main_exits_with_code_1_when_mysql_is_unreachable(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    def unreachable() -> None:
        raise pymysql.OperationalError(2003, "cannot connect")

    monkeypatch.setattr(main, "Database", unreachable)
    with pytest.raises(SystemExit) as exit_info:
        run_main(monkeypatch, "report")
    assert exit_info.value.code == 1
    assert "could not connect to MySQL" in capsys.readouterr().out


def test_main_exits_with_code_1_and_still_closes_when_a_query_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    database = FakeDatabase(broken=True)
    monkeypatch.setattr(main, "Database", lambda: database)
    with pytest.raises(SystemExit) as exit_info:
        run_main(monkeypatch, "report")
    assert exit_info.value.code == 1
    assert "database operation failed" in capsys.readouterr().out
    assert database.closed


def test_main_rejects_an_unknown_command(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(SystemExit) as exit_info:
        run_main(monkeypatch, "bogus")
    assert exit_info.value.code == 2
