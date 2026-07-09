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
