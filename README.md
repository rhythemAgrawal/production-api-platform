# Production API Platform

A small FastAPI service built to practise the parts of a production API that sit around the business logic: authentication, rate limiting, structured logging, tracing, metrics and containerised deployment.

The business logic itself is deliberately trivial (an `items` resource). The interest is in everything around it.

## What it does

- **Authentication.** Passwords are hashed with Argon2. Login returns a short-lived RS256 JWT access token and sets a refresh token in an HttpOnly cookie.
- **Refresh token rotation.** Each refresh token works once. Using it returns a new one and revokes the old one. Replaying a revoked token revokes every refresh token the user has, since it suggests the token was stolen.
- **Rate limiting.** A token bucket per caller, kept in Redis and updated by a Lua script so the check is atomic. Limits are set per path.
- **Structured logs.** JSON logs through structlog, with a request ID and the current trace and span IDs on every line.
- **Tracing and metrics.** OpenTelemetry sends both to an OpenTelemetry Collector, which forwards traces to Jaeger and exposes metrics to Prometheus. Grafana is provisioned with both datasources and a dashboard.
- **Docker.** A multi-stage image that runs as a non-root user, and a Compose file for the whole stack.

```
client ──> FastAPI app ──> Postgres   (users, refresh tokens, items)
               │  └──────> Redis      (token buckets)
               │ OTLP
               v
        OTel Collector ──> Jaeger     (traces)
               └─────────> Prometheus ──> Grafana
```

## Running it

You need Docker and OpenSSL.

**1. Generate the key pair used to sign access tokens.** The keys are not in the repository.

```bash
mkdir -p backend/.secrets
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out backend/.secrets/jwt_private_key.pem
openssl rsa -pubout -in backend/.secrets/jwt_private_key.pem -out backend/.secrets/jwt_public_key.pem
```

**2. Start the stack.**

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| API (interactive docs at `/docs`) | http://localhost:8000 |
| Grafana (login `admin` / `admin`, dashboard under "API Platform") | http://localhost:3000 |
| Jaeger | http://localhost:16686 |
| Prometheus | http://localhost:9090 |

Postgres and Redis are published on their usual ports, 5432 and 6379. If you already run either on your machine, stop it or change the published port in `docker-compose.yml`.

`docker-compose.override.yml` is applied automatically and runs the API with live reload against the mounted source. To run the image as built, use `docker compose -f docker-compose.yml up --build`.

## API

| Method and path | Auth | What it does |
|---|---|---|
| `GET /health` | none | Liveness check |
| `POST /signup` | none | Creates a user. Returns 201 with an access token and sets the refresh cookie. 409 if the username is taken |
| `POST /login` | none | Returns an access token and sets the refresh cookie. 401 on a wrong username or password |
| `POST /refresh` | refresh cookie | Rotates the refresh token and returns a new access token |
| `POST /logout` | refresh cookie | Revokes the refresh token and clears the cookie |
| `POST /items`, `GET /items`, `GET /items/{id}` | access token | A sample protected resource |

```bash
curl -X POST localhost:8000/signup -H 'content-type: application/json' \
  -d '{"username": "alice", "password": "correct horse battery staple"}'
```

Send the returned `access_token` as `Authorization: Bearer <token>`.

## Rate limiting

Each caller has a bucket of tokens that refills at a fixed rate. A request takes one token; with none left the API answers 429.

| Path | Burst | Refill |
|---|---|---|
| `/login` | 5 | 1 per second |
| everything else | 100 | 2 per second |

- The caller is the user ID from the access token, or `anonymous` when there is none.
- Every response carries `X-RateLimit-Remaining`. A 429 also carries `Retry-After` in seconds.
- The script reads the time from Redis, so several API servers agree on it.
- If Redis cannot be reached the request is allowed and a warning is logged.

The rules live in `backend/config.py` and the script in `backend/app/scripts/token_bucket.lua`.

## Observability

- **Logs** go to stdout as JSON. Each line has `request_id`, `path` and `method`, plus `trace_id` and `span_id` so a log line can be matched to its trace. The request ID is taken from an incoming `X-Request-ID` header, or generated, and is returned on the response.
- **Traces** cover every HTTP request.
- **Metrics** are the standard HTTP server metrics plus three custom ones:
  - `auth_login_attempts_total`, by outcome
  - `rate_limit_decisions_total`, by outcome and path
  - `rate_limit_check_duration_seconds`
- **Dashboard.** "API Overview" shows request rate and latency percentiles by route, error rate, active requests, rate-limit rejections and login attempts.

## Running the API without Docker

Start only the backing services, then run the API on your machine.

```bash
docker compose up postgres redis otel-collector jaeger prometheus grafana
```

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements-dev.txt
cp .env.example .env
uvicorn backend.app.main:app --reload
```

Run these from the repository root; the key paths in `.env` are relative to it.

## Tests

```bash
pytest
```

The tests use a temporary SQLite database and generate their own key pair. The rate-limit tests need Redis on `localhost:6379` and are skipped without it; they use database 15 and only touch `rate_limit:*` keys.

The refresh-token test needs Postgres, because SQLite does not keep time zones. Point `TEST_DATABASE_URL` at a scratch database to run it:

```bash
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/scratch pytest
```

The tests drop and recreate every table in that database.

## Layout

```
backend/
  config.py                 settings and rate-limit rules
  app/
    main.py                 app setup
    api.py                  routes
    auth.py                 JWT creation and verification
    services.py             rate-limit check, user lookup
    middlewares.py          rate limiting, request logging
    models.py, schemas.py   database tables, request and response shapes
    observability/          tracing, metrics, custom instruments
    scripts/token_bucket.lua
observability/              Collector, Prometheus and Grafana configuration
tests/
```

## Known limitations

- All unauthenticated callers share one `anonymous` bucket. There is no per-IP limit, so one client can use up the login allowance for everyone.
- Rate-limit rules are fixed in code. There are no per-user tiers.
- The rate-limit check is a blocking Redis call inside async middleware.
- Tables are created at startup. There are no migrations.
- Database queries are not traced.
- The refresh cookie is marked `Secure`, so browsers only send it over HTTPS or to localhost.
- The Compose file is for local use: default passwords, and every port published to the host.
