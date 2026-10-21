import threading

import pymysql
import pytest

import db


def test_load_settings_requires_db_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DB_USER", raising=False)
    with pytest.raises(db.ConfigError, match="DB_USER"):
        db.load_settings()


def test_load_settings_rejects_a_port_that_is_not_a_number(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_USER", "quicktask")
    monkeypatch.setenv("DB_PORT", "abc")
    with pytest.raises(db.ConfigError, match="DB_PORT"):
        db.load_settings()


def test_load_settings_uses_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_USER", "quicktask")
    for name in ("DB_HOST", "DB_PORT", "DB_PASSWORD", "DB_NAME"):
        monkeypatch.delenv(name, raising=False)
    assert db.load_settings() == {
        "host": "localhost",
        "port": 3306,
        "user": "quicktask",
        "password": "",
        "database": "quicktask",
    }


def test_load_settings_reads_every_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in {
        "DB_HOST": "db.example.test",
        "DB_PORT": "3305",
        "DB_USER": "someone",
        "DB_PASSWORD": "secret",
        "DB_NAME": "other",
    }.items():
        monkeypatch.setenv(name, value)
    assert db.load_settings() == {
        "host": "db.example.test",
        "port": 3305,
        "user": "someone",
        "password": "secret",
        "database": "other",
    }


def test_database_is_a_singleton(fake_pool) -> None:
    first = db.Database()
    second = db.Database()
    assert first is second
    assert fake_pool.created == 1


def test_database_creates_the_tables_once(fake_pool) -> None:
    db.Database()
    assert fake_pool.conn.statements == db.SCHEMA_STATEMENTS
    assert fake_pool.conn.commits == 1


def test_singleton_is_thread_safe(fake_pool) -> None:
    instances = []
    threads = [threading.Thread(target=lambda: instances.append(db.Database())) for _ in range(50)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len({id(instance) for instance in instances}) == 1
    assert fake_pool.created == 1


def test_close_closes_the_pool_and_allows_a_fresh_instance(fake_pool) -> None:
    first = db.Database()
    first.close()
    second = db.Database()
    assert second is not first
    assert fake_pool.closed == 1
    assert fake_pool.created == 2


def test_failed_setup_keeps_no_instance_and_closes_the_pool(fake_pool) -> None:
    fake_pool.fail = True
    with pytest.raises(pymysql.MySQLError):
        db.Database()
    assert db.Database._instance is None
    assert fake_pool.closed == 1
    fake_pool.fail = False
    assert db.Database() is db.Database()


def test_save_all_writes_users_before_todos_and_commits_once(fake_pool) -> None:
    database = db.Database()
    commits_before = fake_pool.conn.commits
    users = [{"id": 1, "name": "Ann", "username": "ann", "email": "a@x.test", "city": "Oslo"}]
    todos = [{"id": 5, "user_id": 1, "title": "Write tests", "completed": 1}]
    database.save_all(users, todos)
    assert fake_pool.conn.statements[-2:] == [db.USERS_UPSERT, db.TODOS_UPSERT]
    assert fake_pool.conn.rows == [(1, "Ann", "ann", "a@x.test", "Oslo"), (5, 1, "Write tests", 1)]
    assert fake_pool.conn.commits == commits_before + 1
    assert fake_pool.conn.rollbacks == 0


def test_save_all_rolls_back_and_reraises_when_a_write_fails(fake_pool) -> None:
    database = db.Database()
    commits_before = fake_pool.conn.commits
    fake_pool.conn.fail_on_write = True
    with pytest.raises(pymysql.OperationalError):
        database.save_all([{"id": 1, "name": "Ann", "username": "a", "email": "e", "city": "c"}], [])
    assert fake_pool.conn.rollbacks == 1
    assert fake_pool.conn.commits == commits_before


def test_report_methods_return_the_rows_from_the_database(fake_pool) -> None:
    database = db.Database()
    fake_pool.conn.result = [("Ann", 20, 12, 60.0)]
    assert database.completion_by_user() == [("Ann", 20, 12, 60.0)]
    assert database.users_below_half() == [("Ann", 20, 12, 60.0)]
    assert database.cities_with_most_unfinished() == [("Ann", 20, 12, 60.0)]


class FakeMySQLConnection:
    """A raw connection that counts pings and closes."""

    def __init__(self) -> None:
        """Start open."""
        self.closed = False
        self.pings = 0

    def ping(self, reconnect: bool) -> None:
        """Count the ping."""
        self.pings += 1

    def close(self) -> None:
        """Mark the connection closed."""
        self.closed = True


def test_pool_lends_connections_and_takes_them_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db.pymysql, "connect", lambda **settings: FakeMySQLConnection())
    pool = db.ConnectionPool({}, size=2)
    with pool.connection() as first, pool.connection() as second:
        assert first is not second
        assert first.pings == 1 and second.pings == 1
        assert pool._idle.qsize() == 0
    assert pool._idle.qsize() == 2


def test_pool_closes_connections_that_opened_when_a_later_one_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[FakeMySQLConnection] = []

    def flaky_connect(**settings: object) -> FakeMySQLConnection:
        if len(opened) == 2:
            raise pymysql.OperationalError(2003, "cannot connect")
        opened.append(FakeMySQLConnection())
        return opened[-1]

    monkeypatch.setattr(db.pymysql, "connect", flaky_connect)
    with pytest.raises(pymysql.MySQLError):
        db.ConnectionPool({}, size=3)
    assert len(opened) == 2
    assert all(conn.closed for conn in opened)


def test_pool_close_closes_every_idle_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[FakeMySQLConnection] = []

    def connect(**settings: object) -> FakeMySQLConnection:
        created.append(FakeMySQLConnection())
        return created[-1]

    monkeypatch.setattr(db.pymysql, "connect", connect)
    db.ConnectionPool({}, size=3).close()
    assert all(conn.closed for conn in created)
