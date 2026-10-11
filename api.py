import sys

import requests


def get_json(url: str) -> list[dict]:
    """Fetch a URL and return its decoded JSON, or exit with code 1."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as err:
        print(f"Error: could not fetch {url}: {err}")
        sys.exit(1)