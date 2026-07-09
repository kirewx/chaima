# Docker Deployment & 0.2.0 Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Containerize ChAiMa with a multi-stage Docker image, a GHCR + Watchtower auto-deploy pipeline, an optional Caddy TLS overlay, a rewritten README, and cut the 0.2.0 PyPI release.

**Architecture:** A multi-stage `Dockerfile` builds the frontend (bun) and a wheel (`uv build`), then a slim runtime installs the wheel plus the Alembic config, runs migrations on start, and serves via `chaima run --host 0.0.0.0`. GitHub Actions builds multi-arch (`amd64`+`arm64`) images to `ghcr.io/kirewx/chaima` on every `main` push and `v*` tag; Watchtower on the server auto-pulls `:latest`. A base compose file covers LAN/HTTP; a Caddy overlay adds auto-HTTPS for the public demo.

**Tech Stack:** Docker (buildx multi-arch), docker-compose, GitHub Actions, GHCR, Watchtower, Caddy 2, hatch-vcs, Alembic, FastAPI/uvicorn.

---

## File Structure

- `Dockerfile` (create) — multi-stage build+runtime.
- `docker/entrypoint.sh` (create) — migrate then serve.
- `.dockerignore` (create) — trim context, keep `.git`.
- `docker-compose.yml` (create) — base LAN/HTTP stack + Watchtower.
- `docker-compose.caddy.yml` (create) — TLS overlay.
- `Caddyfile` (create) — reverse-proxy config.
- `.github/workflows/docker.yaml` (create) — multi-arch build & push to GHCR.
- `.env.example` (modify) — add `CHAIMA_DOMAIN` + `/data` note.
- `README.md` (modify) — full rewrite.

**Verified facts (do not re-investigate):**
- `chaima run` default host is `127.0.0.1` → container MUST pass `--host 0.0.0.0` (`src/chaima/cli.py:29`).
- `chaima db upgrade` = `alembic upgrade` via `Config("alembic.ini")` from CWD; needs `alembic.ini` + `alembic/` present (`src/chaima/cli.py:56-61`, `alembic.ini:8`).
- `alembic/env.py:14` uses `settings.database_url`; `Settings` reads `CHAIMA_*` env (`src/chaima/config.py:27`) → `CHAIMA_DATABASE_URL` is honored, no patch needed.
- Uploads dir from `CHAIMA_UPLOADS_DIR` (default `uploads`), `src/chaima/services/files.py:7`.
- Version from `hatch-vcs` → builder needs `.git` in the context; `.dockerignore` must NOT exclude it.
- The wheel packages only `src/chaima` (+ `src/chaima/static/`); `alembic*` and `README.md` (build-time) live at repo root.

**Note on verification (Docker is NOT installed locally):** The dev machine has
no Docker, so tasks are verified with **static checks only** (YAML parse, shell
`sh -n`, optional hadolint). The authoritative build verification happens in
**GitHub Actions**: `docker.yaml` builds the multi-arch image on every pull
request WITHOUT pushing (Task 5), so opening the PR proves the image builds on
`amd64`+`arm64`. Do NOT emit `docker build`/`docker run`/`docker compose`
commands as verification steps — they cannot run here.

---

## Task 1: `.dockerignore`

**Files:**
- Create: `.dockerignore`

- [ ] **Step 1: Write `.dockerignore`**

```
# Keep the build context small. .git is intentionally KEPT — hatch-vcs derives
# the package version from git history during `uv build`.

# Python / venv
.venv/
venv/
env/
**/__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/

# Node / frontend deps (the build hook reinstalls them)
node_modules/
frontend/node_modules/
frontend/dist/

# Local runtime data — must never leak into the image
.env
chaima.db
chaima.db-shm
chaima.db-wal
uploads/

# Dev-only / docs / CI dirs not needed to build the wheel
notebooks/
presentation/
docs/
tests/
.claude/
.agents/
.superpowers/
```

- [ ] **Step 2: Verify `.git` is not ignored**

Run: `git check-ignore -v .git 2>/dev/null; echo "exit=$?"`
Expected: `exit=1` (i.e. `.git` is NOT matched — nothing printed). This checks
the repo's `.gitignore`, but confirm the string `.git` does not appear as a line
in `.dockerignore` either.

- [ ] **Step 3: Commit**

```bash
git add .dockerignore
git commit -m "build(docker): add .dockerignore (keeps .git for hatch-vcs)"
```

---

## Task 2: Dockerfile + entrypoint

**Files:**
- Create: `Dockerfile`
- Create: `docker/entrypoint.sh`

- [ ] **Step 1: Write `docker/entrypoint.sh`**

```sh
#!/bin/sh
set -e

echo "Running database migrations..."
chaima db upgrade head

echo "Starting ChAiMa server on 0.0.0.0:8000..."
exec chaima run --host 0.0.0.0 --port 8000
```

- [ ] **Step 2: Write `Dockerfile`**

```dockerfile
# syntax=docker/dockerfile:1

# ---- Builder: frontend (bun) + wheel (uv) ----
FROM python:3.13-slim AS builder

# uv builds the wheel; bun runs the frontend build hook (hatch_build.py).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY --from=oven/bun:1 /usr/local/bin/bun /usr/local/bin/bun

WORKDIR /build

# Full source incl. .git so hatch-vcs can derive the version.
COPY . .

# Produce the wheel (runs bun frontend build, bakes in the version).
RUN uv build --wheel --out-dir /dist

# ---- Runtime: install wheel, migrate, serve ----
FROM python:3.13-slim AS runtime

# Non-root runtime user.
RUN groupadd --system chaima \
    && useradd --system --gid chaima --create-home chaima

WORKDIR /app

# Install the built wheel.
COPY --from=builder /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -f /tmp/*.whl

# Alembic config + scripts are NOT in the wheel but are required by
# `chaima db upgrade`; place them at the working dir.
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic

# Entrypoint.
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# DB + uploads live on the mounted volume; absolute paths so they resolve
# independently of WORKDIR.
ENV CHAIMA_DATABASE_URL=sqlite+aiosqlite:////data/chaima.db \
    CHAIMA_UPLOADS_DIR=/data/uploads \
    PYTHONUNBUFFERED=1
RUN mkdir -p /data && chown chaima:chaima /data
VOLUME ["/data"]

USER chaima
EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
```

- [ ] **Step 3: Static validation (no Docker locally)**

Run: `sh -n docker/entrypoint.sh && echo "entrypoint OK"`
Expected: prints `entrypoint OK` (valid POSIX shell syntax).

Then sanity-check the Dockerfile by eye against the verified facts: entrypoint
binds `--host 0.0.0.0`; `alembic.ini` + `alembic/` are COPYed into the runtime
`WORKDIR`; `CHAIMA_DATABASE_URL`/`CHAIMA_UPLOADS_DIR` point at `/data`; `.git`
is copied in the builder; no secret values appear in any `ENV`. (Optional, only
if the tool is already installed: `hadolint Dockerfile`.) The real build runs in
CI on the PR.

- [ ] **Step 4: Commit**

```bash
git add Dockerfile docker/entrypoint.sh
git commit -m "build(docker): multi-stage image (bun+uv build, migrate on start)"
```

---

## Task 3: Base compose (LAN/HTTP) + Watchtower

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Write `docker-compose.yml`**

```yaml
services:
  chaima:
    image: ghcr.io/kirewx/chaima:latest
    # To build locally from source instead of pulling the registry image,
    # run: docker compose up -d --build   (uncomment the next line)
    # build: .
    restart: unless-stopped
    env_file: .env
    ports:
      - "8000:8000"
    volumes:
      - chaima-data:/data
    labels:
      - "com.centurylinklabs.watchtower.enable=true"

  # Auto-updates the chaima container when a new :latest image is pushed.
  # Only touches containers labelled watchtower.enable=true.
  watchtower:
    image: containrrr/watchtower:latest
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    command: --label-enable --cleanup --interval 300
    labels:
      - "com.centurylinklabs.watchtower.enable=false"

volumes:
  chaima-data:
```

- [ ] **Step 2: Validate the compose YAML (no Docker locally)**

Run: `python -c "import yaml,sys; d=yaml.safe_load(open('docker-compose.yml')); assert 'chaima' in d['services'] and 'watchtower' in d['services']; assert d['services']['chaima']['volumes']==['chaima-data:/data']; assert 'chaima-data' in d['volumes']; print('compose OK')"`
Expected: prints `compose OK` (valid YAML; chaima+watchtower services present;
`chaima-data` volume mapped to `/data`). The composed stack itself is exercised
on the homeserver, not here.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "build(docker): base compose (LAN/HTTP) with Watchtower auto-update"
```

---

## Task 4: Caddy TLS overlay

**Files:**
- Create: `docker-compose.caddy.yml`
- Create: `Caddyfile`

- [ ] **Step 1: Write `Caddyfile`**

```
{$CHAIMA_DOMAIN} {
	reverse_proxy chaima:8000
}
```

- [ ] **Step 2: Write `docker-compose.caddy.yml`**

```yaml
# Overlay for the public demo: adds Caddy with automatic HTTPS.
# Usage:
#   docker compose -f docker-compose.yml -f docker-compose.caddy.yml up -d
# Requires CHAIMA_DOMAIN set in .env and ports 80/443 reachable from the
# internet with DNS pointing at this host.
services:
  caddy:
    image: caddy:2
    restart: unless-stopped
    depends_on:
      - chaima
    env_file: .env
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy-data:/data
      - caddy-config:/config

  chaima:
    # Caddy fronts the app; stop publishing 8000 to the host.
    # (!reset requires Docker Compose v2.24+.)
    ports: !reset []

volumes:
  caddy-data:
  caddy-config:
```

- [ ] **Step 3: Validate the overlay YAML (no Docker locally)**

Run: `python -c "import yaml; d=yaml.safe_load(open('docker-compose.caddy.yml')); assert 'caddy' in d['services']; print('caddy overlay OK')"`
Expected: prints `caddy overlay OK`. Note: `ports: !reset []` uses a Compose
custom tag that PyYAML's `safe_load` cannot parse — so in the `chaima` service
of THIS overlay file, write the reset without the tag if it breaks parsing, OR
validate only the `caddy` service by loading with a loader that ignores unknown
tags. Simplest: keep `!reset` (it needs Docker Compose v2.24+ at deploy time on
the server) and validate the file with the yaml round-trip below instead.

Alternative check that tolerates the tag:
`python -c "import yaml; yaml.add_multi_constructor('!', lambda l,s,n: None, Loader=yaml.SafeLoader); d=yaml.safe_load(open('docker-compose.caddy.yml')); assert 'caddy' in d['services'] and 'chaima' in d['services']; print('caddy overlay OK')"`
Expected: prints `caddy overlay OK`.

- [ ] **Step 4: Commit**

```bash
git add docker-compose.caddy.yml Caddyfile
git commit -m "build(docker): optional Caddy overlay for auto-HTTPS demo"
```

---

## Task 5: GitHub Actions — multi-arch build & push to GHCR

**Files:**
- Create: `.github/workflows/docker.yaml`

- [ ] **Step 1: Write `.github/workflows/docker.yaml`**

```yaml
name: Build and push Docker image

on:
  pull_request:
  push:
    branches:
      - main
    tags:
      - "v*"
  workflow_dispatch:

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  docker:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v5
        with:
          # hatch-vcs derives the version from git history during the build.
          fetch-depth: 0

      - name: Set up QEMU
        uses: docker/setup-qemu-action@v3

      - name: Set up Buildx
        uses: docker/setup-buildx-action@v3

      # Only log in when we intend to push (not on pull_request).
      - name: Log in to GHCR
        if: github.event_name != 'pull_request'
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Docker metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=raw,value=latest,enable={{is_default_branch}}
            type=semver,pattern={{version}}
            type=sha

      # On pull_request: build both arches to validate the Dockerfile, push=false.
      # On main / tags: build and push to GHCR.
      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: .
          platforms: linux/amd64,linux/arm64
          push: ${{ github.event_name != 'pull_request' }}
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
```

- [ ] **Step 2: Lint the workflow YAML**

Run: `docker run --rm -i rhysd/actionlint:latest -color < .github/workflows/docker.yaml || true`
Expected: no errors reported. (If `actionlint`/Docker pull is unavailable,
instead confirm the file parses as YAML — the workflow is fully exercised on the
first push to `main`. Do not block on tooling availability.)

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/docker.yaml
git commit -m "ci(docker): multi-arch build & push to GHCR on main and tags"
```

---

## Task 6: `.env.example` — Caddy domain + `/data` note

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Add `CHAIMA_DOMAIN` under the Deployment section**

Insert after the `CHAIMA_PUBLIC_BASE_URL=` block (currently ending at
`.env.example:39`):

```
# Domain for the Caddy reverse-proxy overlay (docker-compose.caddy.yml).
# Caddy obtains and renews a Let's Encrypt certificate for this name
# automatically. Requires ports 80/443 reachable from the internet and DNS
# pointing at the host. Leave empty for LAN/HTTP-only deployments.
CHAIMA_DOMAIN=

# In the Docker image the database and uploads default to the /data volume
# (CHAIMA_DATABASE_URL=sqlite+aiosqlite:////data/chaima.db,
# CHAIMA_UPLOADS_DIR=/data/uploads). Override only if you mount elsewhere.
```

- [ ] **Step 2: Verify no real secrets were added**

Run: `git diff .env.example`
Expected: only the two comment blocks + empty `CHAIMA_DOMAIN=` are added; no
real domain, key, or password values (per project rule: no personal values in
source).

- [ ] **Step 3: Commit**

```bash
git add .env.example
git commit -m "docs(config): document CHAIMA_DOMAIN and container /data paths"
```

---

## Task 7: README rewrite

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace `README.md` with the full content below**

````markdown
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
build (bun/npm via `hatch_build.py`). See
`docs/superpowers/project_chaima_dev_workflow` notes for bundled vs. Vite-dev mode.

## License

See [LICENSE](LICENSE).
````

- [ ] **Step 2: Verify no personal/real values leaked**

Run: `git diff README.md`
Expected: only generic placeholders (`admin@example.com`, `<host>`,
`chaima.example.com`-style) — no real domains, IPs, emails, or keys.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(readme): rewrite with install, Docker, and config reference"
```

---

## Task 8: Cut the 0.2.0 release

> Run this task LAST, after Tasks 1–7 are merged to `main` (so the 0.2.0 PyPI
> package and the `0.2.0` Docker image both include the new code). The version
> is derived from the git tag by `hatch-vcs` — there is no version string to
> bump in source.

**Files:** none (git tag + GitHub Release only).

- [ ] **Step 1: Confirm the working tree is clean on `main`**

Run: `git checkout main && git pull && git status`
Expected: on `main`, up to date, "nothing to commit, working tree clean".

- [ ] **Step 2: Confirm CI is green on `main`**

Run: `gh run list --branch main --limit 5`
Expected: the latest **Tests** run on `main` is `completed / success`.

- [ ] **Step 3: Create and push the tag**

```bash
git tag v0.2.0
git push origin v0.2.0
```
Expected: the tag pushes; the **Build and push Docker image** workflow starts
(it triggers on `v*`) and produces `ghcr.io/kirewx/chaima:0.2.0`.

- [ ] **Step 4: Publish the GitHub Release (triggers PyPI)**

```bash
gh release create v0.2.0 --title "v0.2.0" --generate-notes
```
Expected: the release is published; `publish.yaml` (trigger: release published)
builds and uploads `chaima 0.2.0` to PyPI via trusted publishing.

- [ ] **Step 5: Verify the release landed**

```bash
gh run list --workflow publish.yaml --limit 3
pip index versions chaima 2>/dev/null | head -1 || echo "check https://pypi.org/project/chaima/"
```
Expected: the `publish.yaml` run is `success`; `chaima 0.2.0` appears on PyPI
(may take a minute to index). Confirm `ghcr.io/kirewx/chaima:0.2.0` exists under
the repo's Packages.

---

## Self-Review

**Spec coverage:**
- Multi-stage image from source → Task 2. ✓
- CI build → GHCR, multi-arch amd64+arm64 → Task 5. ✓
- Watchtower auto-pull → Task 3. ✓
- SQLite on volume, absolute `/data` paths → Task 2 (env) + Task 3 (volume). ✓
- Caddy optional overlay + Caddyfile → Task 4. ✓
- cloudflared fallback documented → Task 7 README note. ✓
- `--host 0.0.0.0`, alembic files in image, `CHAIMA_UPLOADS_DIR` → Task 2. ✓
- README rewrite → Task 7. ✓
- `.env.example` `CHAIMA_DOMAIN` + `/data` note → Task 6. ✓
- PyPI 0.2.0 via tag/release, unchanged `publish.yaml` → Task 8. ✓
- No secrets in image (runtime env only) → Task 2 (no secret ENV) + verification steps. ✓

**Placeholder scan:** No TBD/TODO; every file has complete content; every
verification step has an exact command + expected output.

**Type/name consistency:** Image ref `ghcr.io/kirewx/chaima` consistent across
Dockerfile-less compose, Caddyfile target `chaima:8000`, service name `chaima`,
volume `chaima-data`, entrypoint `chaima db upgrade head` / `chaima run --host
0.0.0.0` all match the verified CLI. `CHAIMA_DATABASE_URL` / `CHAIMA_UPLOADS_DIR`
/ `CHAIMA_DOMAIN` consistent between Dockerfile, compose, `.env.example`, README.

**Open items from spec — resolved:** alembic env reads `CHAIMA_DATABASE_URL`
(no patch); `.git` kept in context for hatch-vcs; multi-arch covers ARM-or-x86
VPS.
