"""Web API that serves the three reports as JSON, documented with Swagger UI at /docs."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

import pymysql
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from db import ConfigError, Database

logger = logging.getLogger("uvicorn.error")


class CompletionRow(BaseModel):
    """One user's todo counts and completion percentage."""

    name: str = Field(description="The user's name")
    total: int = Field(description="Number of todos the user has")
    done: int = Field(description="Number of completed todos")
    pct: float = Field(description="Completion percentage, rounded to one decimal")


class UnfinishedCity(BaseModel):
    """A city and the number of unfinished todos held by its users."""

    city: str = Field(description="The city name")
    unfinished: int = Field(description="Number of unfinished todos in the city")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open the shared database pool when the server starts, and close it when it stops."""
    try:
        app.state.database = Database()
    except (ConfigError, pymysql.MySQLError) as err:
        logger.error("Cannot start: %s", err)  # say why before the server stops
        raise
    try:
        yield
    finally:
        app.state.database.close()


app = FastAPI(
    title="API to MySQL Reports",
    description="Read-only reports built from users and todos stored in MySQL.",
    version="1.0.0",
    lifespan=lifespan,
)


def get_database(request: Request) -> Database:
    """Return the Database created at startup."""
    return request.app.state.database


DatabaseDep = Annotated[Database, Depends(get_database)]


@app.exception_handler(pymysql.MySQLError)
async def handle_mysql_error(request: Request, exc: Exception) -> JSONResponse:
    """Return 503 with a generic message instead of exposing database internals."""
    return JSONResponse(status_code=503, content={"detail": "Database is unavailable"})


@app.get("/health", tags=["system"], summary="Check that the server is running")
def health() -> dict[str, str]:
    """Return a simple status so you can confirm the server is up."""
    return {"status": "ok"}


@app.get(
    "/reports/completion",
    response_model=list[CompletionRow],
    tags=["reports"],
    summary="Completion by user",
)
def completion_by_user(database: DatabaseDep) -> list[CompletionRow]:
    """Return each user's completion percentage, highest first."""
    return [
        CompletionRow(name=name, total=total, done=int(done), pct=float(pct))
        for name, total, done, pct in database.completion_by_user()
    ]


@app.get(
    "/reports/below-half",
    response_model=list[CompletionRow],
    tags=["reports"],
    summary="Users below 50% completion",
)
def users_below_half(database: DatabaseDep) -> list[CompletionRow]:
    """Return the users whose completion percentage is below 50."""
    return [
        CompletionRow(name=name, total=total, done=int(done), pct=float(pct))
        for name, total, done, pct in database.users_below_half()
    ]


@app.get(
    "/reports/unfinished-cities",
    response_model=list[UnfinishedCity],
    tags=["reports"],
    summary="Cities with the most unfinished todos",
)
def cities_with_most_unfinished(database: DatabaseDep) -> list[UnfinishedCity]:
    """Return every city tied for the most unfinished todos."""
    return [
        UnfinishedCity(city=city, unfinished=int(unfinished))
        for city, unfinished in database.cities_with_most_unfinished()
    ]