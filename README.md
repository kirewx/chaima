# ChAIMa

Chemical AI Manager — inventory management for laboratory chemicals.

## Setup

```bash
uv sync
```

## Run

```bash
uv run uvicorn chaima.app:app --reload
```

## Test

```bash
uv run pytest
```

## Migrations

```bash
uv run alembic upgrade head           # apply
uv run alembic revision --autogenerate -m "description"  # generate
```
