from contextlib import contextmanager

import pytest
import pymysql

import db


class FakeCursor:
    """A cursor that records the SQL it is given and can be told to fail."""

    def __init__(self, conn: "FakeConnection") -> None:
        """Remember the connection that created this cursor."""
        self.conn = conn

    def __enter__(self) -> "FakeCursor":
        """Allow use in a with block."""
        return self

    def __exit__(self, *args: object) -> bool:
        """Never swallow exceptions."""
        return False

    def execute(self, sql: str) -> None:
        """Record the statement."""
        self.conn.statements.append(sql)

    def executemany(self, sql: str, rows: list) -> None:
        """Record the statement, or raise if the connection is set to fail."""
        if self.conn.fail_on_write:
            raise pymysql.OperationalError(1213, "deadlock")
        self.conn.statements.append(sql)
        self.conn.rows.extend(rows)

    def fetchall(self) -> list:
        """Return the canned rows."""
        return self.conn.result


class FakeConnection:
    """A connection that records commits and rollbacks."""

    def __init__(self) -> None:
        """Start with nothing recorded."""
        self.statements: list[str] = []
        self.rows: list = []
        self.result: list = []
        self.commits = 0
        self.rollbacks = 0
        self.fail_on_write = False

    def cursor(self) -> FakeCursor:
        """Return a new fake cursor."""
        return FakeCursor(self)

    def commit(self) -> None:
        """Count the commit."""
        self.commits += 1

    def rollback(self) -> None:
        """Count the rollback."""
        self.rollbacks += 1


class FakePool:
    """A stand-in for ConnectionPool that lends out one fake connection."""

    created = 0
    closed = 0
    fail = False
    conn = FakeConnection()

    def __init__(self, settings: dict, size: int = 3) -> None:
        """Count how many pools are created."""
        FakePool.created += 1

    @contextmanager
    def connection(self):
        """Lend the fake connection, or fail like an unreachable server."""
        if FakePool.fail:
            raise pymysql.OperationalError(2003, "cannot connect")
        yield FakePool.conn

    def close(self) -> None:
        """Count the close."""
        FakePool.closed += 1


@pytest.fixture
def fake_pool(monkeypatch: pytest.MonkeyPatch) -> type[FakePool]:
    """Replace the real pool and settings with fakes, and reset all shared state."""
    FakePool.created = 0
    FakePool.closed = 0
    FakePool.fail = False
    FakePool.conn = FakeConnection()
    monkeypatch.setattr(db, "ConnectionPool", FakePool)
    monkeypatch.setattr(db, "load_settings", lambda: {"database": "quicktask"})
    db.Database._instance = None
    yield FakePool
    db.Database._instance = None
