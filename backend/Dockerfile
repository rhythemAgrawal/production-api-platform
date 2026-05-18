# syntax=docker/dockerfile:1.7
# ─── Stage 1: builder ──────────────────────────────────────────────
# A heavier image with build tools. We only use it to compile wheels.
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# psycopg[binary] ships pre-built wheels, but argon2-cffi and grpcio
# sometimes need a C toolchain on slim images. Install it only here.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy ONLY requirements first. This layer is cached unless requirements.txt changes.
COPY backend/requirements.txt .

# Install into a dedicated venv so we can copy it whole into the runtime stage.
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install -r requirements.txt

# ─── Stage 2: runtime ──────────────────────────────────────────────
# Tiny final image. No compilers, no apt cache, no source tarballs.
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Create a non-root user. Running as root inside a container is a
# defense-in-depth failure even though namespaces sandbox most things.
RUN groupadd --system app && useradd --system --gid app --home /app app

WORKDIR /app

# Copy the prebuilt venv from the builder stage. This is the magic of
# multi-stage: the final image never sees build-essential or pip caches.
COPY --from=builder /opt/venv /opt/venv

# Now copy the source. Lives in its own layer so code changes don't
# bust the (much larger) venv layer above.
COPY --chown=app:app backend ./backend

USER app

# Documents intent only; doesn't actually publish the port. The -p flag
# at `docker run`, or `ports:` in compose, is what publishes.
EXPOSE 8000

# Use exec form (JSON array) so the process is PID 1 and receives SIGTERM
# directly when Docker stops the container. Shell form would wrap it in
# /bin/sh -c which swallows signals → slow shutdowns.
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]