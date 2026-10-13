import argparse

import api
import db


def run_fetch() -> None:
    """Download users and todos, then save them to the database."""
    users = api.fetch_users()
    todos = api.fetch_todos()
    conn = db.connect()
    db.save_users(conn, users)  # users first, so todos can reference them
    db.save_todos(conn, todos)
    conn.close()
    print(f"Saved {len(users)} users and {len(todos)} todos to {db.DB_PATH}")


def print_completion_rows(rows: list[tuple]) -> None:
    """Print name, done/total, and percentage for each row."""
    for name, total, done, pct in rows:
        print(f"  {name:<25} {done:>3}/{total:<3} {pct:>5}%")


def run_report() -> None:
    """Print the three reports from the database."""
    conn = db.connect()

    print("Completion by user")
    print_completion_rows(db.completion_by_user(conn))

    print("\nUsers below 50% completion")
    rows = db.users_below_half(conn)
    if rows:
        print_completion_rows(rows)
    else:
        print("  none")

    print("\nCity with the most unfinished todos")
    for city, unfinished in db.cities_with_most_unfinished(conn):
        print(f"  {city} ({unfinished} unfinished)")

    conn.close()


def main() -> None:
    """Parse the command line and run fetch or report."""
    parser = argparse.ArgumentParser(description="API to SQLite report tool")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("fetch", help="download data into the database")
    subparsers.add_parser("report", help="print reports from the database")
    args = parser.parse_args()

    if args.command == "fetch":
        run_fetch()
    elif args.command == "report":
        run_report()


if __name__ == "__main__":
    main()
