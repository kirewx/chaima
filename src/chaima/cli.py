"""ChAIMa CLI - Command-line interface for the ChAIMa server."""

from __future__ import annotations

from typing import Annotated

import typer
import uvicorn

app = typer.Typer(
    name="chaima",
    help="ChAIMa - Chemical AI Manager",
    no_args_is_help=True,
)

db_app = typer.Typer(
    name="db",
    help="Database management commands.",
    no_args_is_help=True,
)
app.add_typer(db_app, name="db")


@app.command()
def run(
    host: Annotated[
        str,
        typer.Option(help="Bind address."),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option(help="Bind port."),
    ] = 8000,
    reload: Annotated[
        bool,
        typer.Option("--reload", help="Enable auto-reload for development."),
    ] = False,
) -> None:
    """Start the ChAIMa server."""
    uvicorn.run(
        "chaima.app:app",
        host=host,
        port=port,
        reload=reload,
    )


@db_app.command()
def upgrade(
    revision: Annotated[
        str,
        typer.Argument(help="Target revision."),
    ] = "head",
) -> None:
    """Apply database migrations (alembic upgrade)."""
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    command.upgrade(cfg, revision)
    typer.echo(f"Database upgraded to {revision}.")


@db_app.command()
def revision(
    message: Annotated[
        str,
        typer.Option("-m", "--message", help="Revision message."),
    ] = "",
    autogenerate: Annotated[
        bool,
        typer.Option("--autogenerate", help="Auto-detect model changes."),
    ] = True,
) -> None:
    """Create a new database migration."""
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    command.revision(cfg, message=message, autogenerate=autogenerate)
    typer.echo("Migration created.")
