import sys

import requests
USERS_URL = "https://jsonplaceholder.typicode.com/users"
TODOS_URL = "https://jsonplaceholder.typicode.com/todos"

def get_json(url: str) -> list[dict]:
    """Fetch a URL and return its decoded JSON, or exit with code 1."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as err:
        print(f"Error: could not fetch {url}: {err}")
        sys.exit(1)
        
def parse_user(raw: dict) -> dict:
    """flatten one API user into columns the user table needs.""" 
    return{
        "id": raw["id"],
        "name": raw["name"],
        "username": raw["username"],
        "email": raw["email"],
        "city": raw["address"]["city"],
        
    }
def parse_todo(raw: dict) -> dict:
    """flatten one api todo into the columns"""
    return{
        "id": raw["id"],
        "user_id": raw["user_id"],
        "title": raw["title"],
        "completed": int(raw["completed"]),

    }

def fetch_users() -> list[dict]:
    """download all users and return them parsed"""
    return[parse_user(raw) for raw in get_json(USERS_URL)]

def fetch_todos() -> list[dict]:
    """download all todos and return them parced."""
    return [parse_todo(raw) for raw in get_json(TODOS_URL)]
