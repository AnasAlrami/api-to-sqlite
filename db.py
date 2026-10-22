import os
import queue
import threading
from collections.abc import Iterator
from contextlib import contextmanager

import pymysql

POOL_SIZE = 3

SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id       INT PRIMARY KEY,
        name     VARCHAR(255) NOT NULL,
        username VARCHAR(255) NOT NULL,
        email    VARCHAR(255) NOT NULL,
        city     VARCHAR(255) NOT NULL
    ) ENGINE=InnoDB
    """,
    """
    CREATE TABLE IF NOT EXISTS todos (
        id        INT PRIMARY KEY,
        user_id   INT NOT NULL,
        title     VARCHAR(500) NOT NULL,
        completed TINYINT NOT NULL CHECK (completed IN (0, 1)),
        FOREIGN KEY (user_id) REFERENCES users(id)
    ) ENGINE=InnoDB
    """,
]

USERS_UPSERT = """
    INSERT INTO users (id, name, username, email, city)
    VALUES (%s, %s, %s, %s, %s) AS new
    ON DUPLICATE KEY UPDATE
        name = new.name,
        username = new.username,
        email = new.email,
        city = new.city
"""

TODOS_UPSERT = """
    INSERT INTO todos (id, user_id, title, completed)
    VALUES (%s, %s, %s, %s) AS new
    ON DUPLICATE KEY UPDATE
        user_id = new.user_id,
        title = new.title,
        completed = new.completed
"""

COMPLETION_BY_USER = """
    SELECT u.name,
           COUNT(t.id) AS total,
           SUM(t.completed) AS done,
           ROUND(100.0 * SUM(t.completed) / COUNT(t.id), 1) AS pct
    FROM users AS u
    JOIN todos AS t ON t.user_id = u.id
    GROUP BY u.id, u.name
    ORDER BY pct DESC
"""

USERS_BELOW_HALF = """
    SELECT u.name,
           COUNT(t.id) AS total,
           SUM(t.completed) AS done,
           ROUND(100.0 * SUM(t.completed) / COUNT(t.id), 1) AS pct
    FROM users AS u
    JOIN todos AS t ON t.user_id = u.id
    GROUP BY u.id, u.name
    HAVING 100.0 * SUM(t.completed) / COUNT(t.id) < 50
    ORDER BY pct ASC
"""

CITIES_MOST_UNFINISHED = """
    SELECT u.city, COUNT(t.id) AS unfinished
    FROM todos AS t
    JOIN users AS u ON u.id = t.user_id
    WHERE t.completed = 0
    GROUP BY u.city
    HAVING COUNT(t.id) = (
        SELECT MAX(city_count) FROM (
            SELECT COUNT(*) AS city_count
            FROM todos AS t2
            JOIN users AS u2 ON u2.id = t2.user_id
            WHERE t2.completed = 0
            GROUP BY u2.city
        ) AS counts
    )
    ORDER BY u.city
"""


class ConfigError(Exception):
    """Raised when the database settings are missing or invalid."""


def load_settings() -> dict:
    """Read the MySQL connection settings from environment variables."""
    user = os.environ.get("DB_USER")
    if not user:
        raise ConfigError("DB_USER is not set (also set DB_PASSWORD, and DB_PORT if MySQL is not on 3306)")
    port = os.environ.get("DB_PORT", "3306")
    if not port.isdigit():
        raise ConfigError(f"DB_PORT must be a number, but it is '{port}'")
    return {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": int(port),
        "user": user,
        "password": os.environ.get("DB_PASSWORD", ""),
        "database": os.environ.get("DB_NAME", "quicktask"),
    }


class ConnectionPool:
    """Keeps a fixed set of MySQL connections and lends them out one at a time."""

    def __init__(self, settings: dict, size: int = POOL_SIZE) -> None:
        """Open size connections to MySQL and put them in the pool."""
        self._idle: queue.Queue[pymysql.connections.Connection] = queue.Queue()
        try:
            for _ in range(size):
                self._idle.put(pymysql.connect(**settings))
        except pymysql.MySQLError:
            self.close()  # don't leak the connections that did open
            raise

    @contextmanager
    def connection(self) -> Iterator[pymysql.connections.Connection]:
        """Borrow a connection, reconnecting if it dropped, and return it when done."""
        conn = self._idle.get()  # waits if every connection is in use
        try:
            conn.ping(reconnect=True)
            yield conn
        finally:
            self._idle.put(conn)

    def close(self) -> None:
        """Close every connection that is sitting in the pool."""
        while not self._idle.empty():
            self._idle.get().close()


class Database:
    """Runs every query through the one shared MySQL connection pool (a singleton)."""

    _instance: "Database | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "Database":
        """Return the one shared Database, creating and connecting it on first use."""
        with cls._lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                instance._connect()  # raises on failure, so a half-built instance is never kept
                cls._instance = instance
            return cls._instance

    def _connect(self) -> None:
        """Connect using the environment settings and create the tables."""
        self.settings = load_settings()
        self.pool = ConnectionPool(self.settings)
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cursor:
                    for statement in SCHEMA_STATEMENTS:
                        cursor.execute(statement)
                conn.commit()
        except pymysql.MySQLError:
            self.pool.close()  # don't leak connections when setup fails
            raise

    def close(self) -> None:
        """Close the pool, so the next Database() call creates a fresh one."""
        with Database._lock:
            self.pool.close()
            Database._instance = None

    def save_all(self, users: list[dict], todos: list[dict]) -> None:
        """Save users and todos in one transaction, so either both are saved or neither is."""
        with self.pool.connection() as conn:
            try:
                with conn.cursor() as cursor:
                    cursor.executemany(
                        USERS_UPSERT,
                        [(u["id"], u["name"], u["username"], u["email"], u["city"]) for u in users],
                    )
                    cursor.executemany(
                        TODOS_UPSERT,
                        [(t["id"], t["user_id"], t["title"], t["completed"]) for t in todos],
                    )
                conn.commit()
            except pymysql.MySQLError:
                conn.rollback()
                raise

    def _fetch(self, sql: str) -> list[tuple]:
        """Run a read-only query and return all rows."""
        with self.pool.connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql)
                return cursor.fetchall()

    def completion_by_user(self) -> list[tuple]:
        """Return each user's todo counts and completion percentage, highest first."""
        return self._fetch(COMPLETION_BY_USER)

    def users_below_half(self) -> list[tuple]:
        """Return the users whose completion percentage is below 50."""
        return self._fetch(USERS_BELOW_HALF)

    def cities_with_most_unfinished(self) -> list[tuple]:
        """Return every city tied for the most unfinished todos, with its count."""
        return self._fetch(CITIES_MOST_UNFINISHED)
