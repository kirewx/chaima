# ChAiMa — Chemical AI Manager

Inventory management for laboratory chemicals: track containers, locations,
hazard (GHS/H&P) statements, orders, and group-scoped access — with optional
AI label OCR (Gemini) to create containers from a photo.

- **API + web UI:** FastAPI backend serving a bundled frontend.
- **Auth:** user accounts, groups, invites (fastapi-users).
- **Data:** SQLite by default; Postgres supported via a single env var.

## Install

From PyPI:

```bash
pip install chaima
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install chaima
```

Then run the server (binds localhost by default):

```bash
chaima run                 # http://127.0.0.1:8000
chaima run --host 0.0.0.0  # expose on the network
chaima db upgrade head     # apply database migrations
```

Configuration is read from environment variables (prefix `CHAIMA_`) or a `.env`
file. Copy `.env.example` to `.env` and fill in the values — at minimum set a
real `CHAIMA_SECRET_KEY` and `CHAIMA_ADMIN_PASSWORD` before exposing the app.

## Docker

The published image is `ghcr.io/kirewx/chaima`. Database and uploads persist on
the `/data` volume. Migrations run automatically on container start.

### LAN / HTTP (homeserver test)

```bash
git clone https://github.com/kirewx/chaima && cd chaima
cp .env.example .env
# Edit .env: set CHAIMA_SECRET_KEY, CHAIMA_ADMIN_PASSWORD, CHAIMA_COOKIE_SECURE=false
docker compose up -d
```

The app is served on `http://<host>:8000`. A `watchtower` container polls GHCR
and auto-updates ChAiMa whenever a new `:latest` image is published (i.e. on
every push to `main`). The GHCR package must be public, or Watchtower needs
registry credentials.

### Public demo with HTTPS (Caddy)

Set `CHAIMA_DOMAIN` in `.env` (and `CHAIMA_COOKIE_SECURE=true`,
`CHAIMA_REQUIRE_SECURE_CONFIG=true`), point DNS at the host, open ports 80/443,
then:

```bash
docker compose -f docker-compose.yml -f docker-compose.caddy.yml up -d
```

Caddy obtains and renews a Let's Encrypt certificate automatically.

> If the host is behind CGNAT or blocks inbound 80/443, Let's Encrypt can't
> validate. Use a [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
> instead — point it at `chaima:8000` and drop the Caddy overlay.

## Configuration

All variables are prefixed `CHAIMA_`. See `.env.example` for the full list.

| Variable | Purpose | Default |
|---|---|---|
| `CHAIMA_SECRET_KEY` | JWT/login signing key — set a random private value | insecure placeholder |
| `CHAIMA_ADMIN_EMAIL` | Initial superuser, seeded on first start | `admin@example.com` |
| `CHAIMA_ADMIN_PASSWORD` | Initial superuser password | `changeme` |
| `CHAIMA_REQUIRE_SECURE_CONFIG` | Refuse to start with default secret/password | `false` |
| `CHAIMA_COOKIE_SECURE` | Mark auth cookies HTTPS-only | `true` |
| `CHAIMA_DATABASE_URL` | DB URL (SQLite or `postgresql+asyncpg://…`) | local SQLite |
| `CHAIMA_PUBLIC_BASE_URL` | Base URL for invite links | window origin |
| `CHAIMA_DOMAIN` | Domain for the Caddy overlay | empty |
| `CHAIMA_GEMINI_API_KEY` | Google AI key for label OCR (optional) | empty (feature off) |
| `CHAIMA_GEMINI_MODEL` | Gemini model for OCR | `gemini-2.5-flash` |

To use Postgres instead of SQLite, set e.g.
`CHAIMA_DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/chaima` (and add a
`db` service to the compose file).

## Development

```bash
uv sync                                    # install deps
uv run uvicorn chaima.app:app --reload     # dev server with auto-reload
uv run pytest                              # run the test suite
```

Migrations:

```bash
uv run alembic upgrade head                              # apply
uv run alembic revision --autogenerate -m "description"  # generate
```

The frontend lives in `frontend/` and is built automatically during the package
build (bun/npm via `hatch_build.py`).

## License

See [LICENSE](LICENSE).
