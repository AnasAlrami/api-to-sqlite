import sqlite3

DB_PATH = "quicktask.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id       INTEGER PRIMARY KEY,
    name     TEXT NOT NULL,
    username TEXT NOT NULL,
    email    TEXT NOT NULL,
    city     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS todos (
    id        INTEGER PRIMARY KEY,
    user_id   INTEGER NOT NULL REFERENCES users(id),
    title     TEXT NOT NULL,
    completed INTEGER NOT NULL CHECK (completed IN (0, 1))
);
"""


def connect() -> sqlite3.Connection:
    """Open the database, create the tables, and enable foreign keys."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")  # SQLite leaves this off by default
    conn.executescript(SCHEMA)
    return conn


def save_users(conn: sqlite3.Connection, users: list[dict]) -> None:
    """Insert new users and update existing ones, keyed by id."""
    conn.executemany(
        """
        INSERT INTO users (id, name, username, email, city)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            username = excluded.username,
            email = excluded.email,
            city = excluded.city
        """,
        [(u["id"], u["name"], u["username"], u["email"], u["city"]) for u in users],
    )
    conn.commit()


def save_todos(conn: sqlite3.Connection, todos: list[dict]) -> None:
    """Insert new todos and update existing ones, keyed by id."""
    conn.executemany(
        """
        INSERT INTO todos (id, user_id, title, completed)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            user_id = excluded.user_id,
            title = excluded.title,
            completed = excluded.completed
        """,
        [(t["id"], t["user_id"], t["title"], t["completed"]) for t in todos],
    )
    conn.commit()


def completion_by_user(conn: sqlite3.Connection) -> list[tuple]:
    """Return each user's todo counts and completion percentage, highest first."""
    return conn.execute(
        """
        SELECT u.name,
               COUNT(t.id) AS total,
               SUM(t.completed) AS done,
               ROUND(100.0 * SUM(t.completed) / COUNT(t.id), 1) AS pct
        FROM users AS u
        JOIN todos AS t ON t.user_id = u.id
        GROUP BY u.id
        ORDER BY pct DESC
        """
    ).fetchall()


def users_below_half(conn: sqlite3.Connection) -> list[tuple]:
    """Return the users whose completion percentage is below 50."""
    return conn.execute(
        """
        SELECT u.name,
               COUNT(t.id) AS total,
               SUM(t.completed) AS done,
               ROUND(100.0 * SUM(t.completed) / COUNT(t.id), 1) AS pct
        FROM users AS u
        JOIN todos AS t ON t.user_id = u.id
        GROUP BY u.id
        HAVING 100.0 * SUM(t.completed) / COUNT(t.id) < 50
        ORDER BY pct ASC
        """
    ).fetchall()


def cities_with_most_unfinished(conn: sqlite3.Connection) -> list[tuple]:
    """Return every city tied for the most unfinished todos, with its count."""
    return conn.execute(
        """
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
            )
        )
        ORDER BY u.city
        """
    ).fetchall()
