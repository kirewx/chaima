# Docker Deployment & 0.2.0 Release — Design

Date: 2026-07-09
Status: Approved (design), pending implementation plan

## Goal

Three deliverables in one release cycle:

1. **PyPI release 0.2.0** — cut a new version via the existing tag → CI flow.
2. **README** — replace the stub with real install / Docker / configuration docs.
3. **Docker + deploy pipeline** — containerize ChAiMa so it can be deployed
   with minimal effort on a homeserver (test/demo) and later on a netcup VPS,
   with hands-off updates.

These are related but independently shippable. Docker is the substantive work.

## Decisions (locked)

| Topic | Decision |
|---|---|
| Deploy flow | CI builds image on merge-to-`main` **and** on tags → pushes to GHCR → **Watchtower** on the server auto-pulls `:latest` |
| Image build | **Multi-stage from source** (bun frontend build → `uv build` → install wheel). Decoupled from PyPI so any commit is deployable for testing. |
| Registry | GitHub Container Registry (`ghcr.io/kirewx/chaima`) via `GITHUB_TOKEN` |
| Architecture | **Multi-arch `amd64` + `arm64`** (homeserver = Intel/amd64; netcup VPS may be ARM or x86) |
| Network/TLS | Base compose = LAN HTTP on `:8000`. **Caddy** as an optional overlay for the public demo (auto-HTTPS). cloudflared remains a documented fallback for CGNAT'd home connections. |
| Database | **SQLite on a named volume**. Postgres documented as a config-only switch for later. |
| PyPI | Unchanged track: new git tag → GitHub Release → existing `publish.yaml`. |

## Grounding facts (verified in code)

- CLI (`src/chaima/cli.py`): `chaima run --host --port` (default host **`127.0.0.1`**),
  `chaima db upgrade [head]`. The container **must** pass `--host 0.0.0.0`.
- `chaima db upgrade` loads `Config("alembic.ini")` from the CWD → the runtime
  image **must** include `alembic.ini` + the `alembic/` scripts dir (they are
  **not** in the wheel, which only packages `src/chaima`).
- Uploads dir: `src/chaima/services/files.py` reads
  `CHAIMA_UPLOADS_DIR` (default `uploads`, relative). Set it to `/data/uploads`.
- DB URL: `CHAIMA_DATABASE_URL` (default relative sqlite). Set it to an
  **absolute** path `sqlite+aiosqlite:////data/chaima.db` so it lands on the volume
  regardless of `WORKDIR`.
- Version: `hatch-vcs` derives the version from git history → the builder stage
  needs `.git` available (or a pretend-version build arg).
- Alembic `env.py` must honour `CHAIMA_DATABASE_URL` for container migrations —
  **verify during implementation**; adjust if it hard-codes a URL.

## Files

### `Dockerfile` (multi-stage)

**Builder stage** — `python:3.13-slim`:
- Install `uv` and `bun` (frontend build hook needs a JS package manager).
- Copy the repo including `.git` (for `hatch-vcs`).
- `uv build` → produces `dist/*.whl` with the frontend baked in.

**Runtime stage** — `python:3.13-slim`:
- Create a non-root user.
- `pip install` the wheel from the builder stage.
- `COPY alembic.ini` and `alembic/` into `WORKDIR=/app` (needed by `chaima db upgrade`).
- `ENV` defaults: `CHAIMA_DATABASE_URL=sqlite+aiosqlite:////data/chaima.db`,
  `CHAIMA_UPLOADS_DIR=/data/uploads`.
- `EXPOSE 8000`.
- Entrypoint script: `chaima db upgrade head && exec chaima run --host 0.0.0.0 --port 8000`.

### `.dockerignore`
Exclude `.venv`, `node_modules`, `frontend/node_modules`, `chaima.db*`,
`uploads/`, `notebooks/`, `__pycache__`, `.pytest_cache`. **Keep `.git`**
(version derivation).

### `docker-compose.yml` (base — LAN/HTTP)
- `chaima` service: `image: ghcr.io/kirewx/chaima:latest`, `env_file: .env`,
  `ports: ["8000:8000"]`, `restart: unless-stopped`,
  volume `chaima-data:/data`, Watchtower-enable label.
- `watchtower` service: scoped by label to `chaima`, polls GHCR, cleans up old images.
- Named volume `chaima-data` holds **both** the SQLite DB and uploads.

### `docker-compose.caddy.yml` (overlay — public demo)
- Adds `caddy` service: ports `80:80` + `443:443`, config from `Caddyfile`,
  volumes for certs/data. Reverse-proxies to `chaima:8000`.
- Brought up with `-f docker-compose.yml -f docker-compose.caddy.yml`.

### `Caddyfile`
```
{$CHAIMA_DOMAIN} {
    reverse_proxy chaima:8000
}
```

### `.github/workflows/docker.yaml` (new)
- Triggers: `push` to `main`, `push` tags `v*`.
- `permissions: packages: write`, login to GHCR with `GITHUB_TOKEN`.
- `docker/setup-qemu-action` + `docker/setup-buildx-action` for multi-arch.
- `docker/build-push-action`: platforms `linux/amd64,linux/arm64`, tags
  `latest` (main), `<version>` + `<sha>` (tags). Build context includes `.git`.

### `README.md` (rewritten)
Sections: intro + what ChAiMa is · Install (`pip install chaima`, `uv`) ·
Docker quickstart (LAN + public demo) · Configuration table of `CHAIMA_*`
vars · Development · Migrations.

### `.env.example` (extended)
Add `CHAIMA_DOMAIN=` (for Caddy) and a note that DB + uploads live under `/data`
in the container.

## Operational flows

**Homeserver first-time setup:**
```
git clone … && cd chaima
cp .env.example .env    # set CHAIMA_SECRET_KEY, CHAIMA_ADMIN_*, COOKIE_SECURE=false for LAN
docker compose up -d    # pulls image, migrates, serves on :8000
```
Thereafter: merge to `main` → CI builds `:latest` → Watchtower updates automatically.

**Public demo (once port 80/domain are ready):**
```
docker compose -f docker-compose.yml -f docker-compose.caddy.yml up -d
```

**PyPI release 0.2.0:**
```
git tag v0.2.0 && git push origin v0.2.0
# create GitHub Release "published" → publish.yaml uploads to PyPI
# docker.yaml also builds the versioned image
```

## Security notes

- **No secrets in the image.** `CHAIMA_SECRET_KEY`, `CHAIMA_ADMIN_PASSWORD`,
  `CHAIMA_GEMINI_API_KEY` come in at runtime via `.env` / env vars only.
- For the public demo set `CHAIMA_REQUIRE_SECURE_CONFIG=true` and
  `CHAIMA_COOKIE_SECURE=true` (Caddy terminates TLS). LAN HTTP uses
  `COOKIE_SECURE=false`.
- Runtime container runs as a non-root user.

## Out of scope (YAGNI)

- Postgres service (documented switch only).
- cloudflared overlay (documented as fallback; not built unless CGNAT bites).
- Automated rollback / blue-green. Watchtower recreate is sufficient for a test box.

## Open items to verify during implementation

1. `alembic/env.py` reads `CHAIMA_DATABASE_URL` (else patch it).
2. Exact `hatch-vcs` pretend-version handling if `.git` is excluded from context.
3. Whether netcup VPS ends up ARM or x86 (multi-arch covers both regardless).
