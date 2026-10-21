this is my first task as a trainee in progineer technologies

# api-to-sqlite

A Python command-line tool that fetches users and todos from the JSONPlaceholder API, stores them in a MySQL database, and prints three SQL reports. It also has an optional web API with Swagger documentation.

The repository keeps its original assignment name, `api-to-sqlite`, but the database layer now uses MySQL.

## Requirements

- Python 3.10 or newer
- MySQL 8.0.19 or newer, running on your computer

## Setup

1. Clone the repository and open the folder.
2. Create and activate a virtual environment:

   ```
   python -m venv .venv
   ```

   On Windows, if that prints `Python was not found`, use `py -m venv .venv` instead.

   Activate it with `source .venv/Scripts/activate` in Git Bash, or `.venv\Scripts\Activate.ps1` in PowerShell. If PowerShell blocks the script, use Git Bash.

3. Install the requirements:

   ```
   pip install -r requirements.txt
   ```

## Create the database and user

Run this in MySQL as an admin user, for example in MySQL Workbench. Replace `your-password-here` with a password you choose:

```sql
CREATE DATABASE IF NOT EXISTS quicktask;
CREATE USER 'quicktask'@'localhost' IDENTIFIED BY 'your-password-here';
GRANT ALL PRIVILEGES ON quicktask.* TO 'quicktask'@'localhost';
```

## Configure the connection

The tool reads its settings from environment variables, so no password is stored in the code.

| Variable | Meaning | Default |
| --- | --- | --- |
| `DB_USER` | MySQL user | required |
| `DB_PASSWORD` | MySQL password | empty |
| `DB_HOST` | MySQL host | `localhost` |
| `DB_PORT` | MySQL port | `3306` |
| `DB_NAME` | Database name | `quicktask` |

Copy `.env.example` to `.env`, fill in your values, and load it in Git Bash:

```
set -a; source .env; set +a
```

`.env` is ignored by Git. Never commit it.

## Usage

```
python main.py fetch
python main.py report
```

- `fetch` downloads 10 users and 200 todos and saves them in one transaction, so either everything is saved or nothing is. Running it again updates the existing rows instead of adding duplicates.
- `report` prints three reports from the database.

If a request or a database operation fails, the tool prints a readable message and exits with code 1.

## Web API and Swagger

```
uvicorn app:app --reload
```

Open http://127.0.0.1:8000/docs for the Swagger page, where you can try each endpoint.

| Endpoint | Returns |
| --- | --- |
| `GET /health` | Whether the server is running |
| `GET /reports/completion` | Each user's completion percentage, highest first |
| `GET /reports/below-half` | Users below 50% completion |
| `GET /reports/unfinished-cities` | The cities with the most unfinished todos |

The API only reads data. Run `python main.py fetch` first so the tables have data.

## Tests

```
pip install -r requirements-dev.txt
pytest
```

The tests use saved sample data and fake database connections, so they need neither the internet nor MySQL.

## Table design

- `users (id INT PRIMARY KEY, name, username, email, city)`: `city` comes from the nested `address` object in the API response.
- `todos (id INT PRIMARY KEY, user_id INT REFERENCES users(id), title, completed TINYINT)`: `completed` is stored as 0 or 1.

The ids come from the API, and rows are saved with parameterized queries and `INSERT ... ON DUPLICATE KEY UPDATE` (an upsert), so repeated fetches don't duplicate data.

## How the code is organized

- `api.py` downloads and parses the API data.
- `db.py` holds the `Database` class, a singleton that shares one pool of MySQL connections, plus the schema and the queries.
- `main.py` is the command-line entry point.
- `app.py` is the optional web API.
- `tests/` holds the pytest tests.

## Sample report output

```
Completion by user
  Clementina DuBuque         12/20   60.0%
  Chelsey Dietrich           12/20   60.0%
  Nicholas Runolfsdottir V   11/20   55.0%
  Leanne Graham              11/20   55.0%
  Kurtis Weissnat             9/20   45.0%
  Glenna Reichert             8/20   40.0%
  Ervin Howell                8/20   40.0%
  Clementine Bauch            7/20   35.0%
  Mrs. Dennis Schulist        6/20   30.0%
  Patricia Lebsack            6/20   30.0%

Users below 50% completion
  Patricia Lebsack            6/20   30.0%
  Mrs. Dennis Schulist        6/20   30.0%
  Clementine Bauch            7/20   35.0%
  Ervin Howell                8/20   40.0%
  Glenna Reichert             8/20   40.0%
  Kurtis Weissnat             9/20   45.0%

City with the most unfinished todos
  South Christy (14 unfinished)
  South Elvis (14 unfinished)
```
