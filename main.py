import argparse
import sys

import pymysql

import api
from db import ConfigError, Database


def run_fetch(database: Database) -> None:
    """Download users and todos, then save both in one transaction."""
    users = api.fetch_users()
    todos = api.fetch_todos()
    database.save_all(users, todos)  # users first, so todos can reference them
    name = database.settings["database"]
    print(f"Saved {len(users)} users and {len(todos)} todos to MySQL database '{name}'")


def print_completion_rows(rows: list[tuple]) -> None:
    """Print name, done/total, and percentage for each row."""
    for name, total, done, pct in rows:
        print(f"  {name:<25} {done:>3}/{total:<3} {pct:>5}%")


def run_report(database: Database) -> None:
    """Print the three reports from the shared connection pool."""
    print("Completion by user")
    print_completion_rows(database.completion_by_user())

    print("\nUsers below 50% completion")
    rows = database.users_below_half()
    if rows:
        print_completion_rows(rows)
    else:
        print("  none")

    print("\nCity with the most unfinished todos")
    for city, unfinished in database.cities_with_most_unfinished():
        print(f"  {city} ({unfinished} unfinished)")


def main() -> None:
    """Parse the command line, open the shared database, and run the command."""
    parser = argparse.ArgumentParser(description="API to MySQL report tool")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("fetch", help="download data into the database")
    subparsers.add_parser("report", help="print reports from the database")
    args = parser.parse_args()

    try:
        database = Database()  # one connection pool, shared by the command
    except ConfigError as err:
        print(f"Error: bad database settings: {err}")
        sys.exit(1)
    except pymysql.MySQLError as err:
        print(f"Error: could not connect to MySQL: {err}")
        sys.exit(1)

    try:
        if args.command == "fetch":
            run_fetch(database)
        elif args.command == "report":
            run_report(database)
    except pymysql.MySQLError as err:
        print(f"Error: database operation failed: {err}")
        sys.exit(1)
    finally:
        database.close()


if __name__ == "__main__":
    main()
