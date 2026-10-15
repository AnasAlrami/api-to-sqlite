import argparse

from api import fetch_todos, fetch_users


def main() -> None:
    """Parse the command line and dispatch to fetch or report."""
    parser = argparse.ArgumentParser(description="API to SQLite report tool")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("fetch", help="download users and todos")
    subparsers.add_parser("report", help="print reports from the database")
    args = parser.parse_args()

    if args.command == "fetch":
        users = fetch_users()
        todos = fetch_todos()
        print(f"Fetched {len(users)} users and {len(todos)} todos")
    elif args.command == "report":
        print("report goes here")


if __name__ == "__main__":
    main()
