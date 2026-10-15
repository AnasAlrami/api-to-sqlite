this is my first task as a trainee in progineer technologies

# api-to-sqlite

A Python command-line tool that fetches users and todos from the JSONPlaceholder API, stores them in SQLite, and prints three SQL reports.

## Setup

1. Clone the repository and open the folder.
2. Create and activate a virtual environment:

   ```
   python -m venv .venv
   ```

   Activate it with `source .venv/Scripts/activate` in Git Bash, or `.venv\Scripts\Activate.ps1` in PowerShell.

3. Install the requirements:

   ```
   pip install -r requirements.txt
   ```

## Usage

```
python main.py fetch
python main.py report
```

- `fetch` downloads 10 users and 200 todos and saves them to `quicktask.db`. Running it again updates the existing rows instead of adding duplicates.
- `report` prints three reports from the database.

If a request fails, the tool prints a readable message and exits with code 1.

## Table design

- `users (id PRIMARY KEY, name, username, email, city)`: `city` comes from the nested `address` object in the API response.
- `todos (id PRIMARY KEY, user_id REFERENCES users(id), title, completed)`: `completed` is stored as 0 or 1.

Foreign keys are enabled on every connection. Rows are saved with parameterized queries and `INSERT ... ON CONFLICT ... DO UPDATE` (an upsert), so repeated fetches don't duplicate data.

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
