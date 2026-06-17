# StayOps — Short-term rental management API

A production-grade FastAPI + PostgreSQL booking platform. Phase 1 of the StayOps learning project.

## Stack

- **FastAPI** — async REST API framework
- **SQLAlchemy 2.0 (async)** — ORM with asyncpg driver
- **PostgreSQL 16** — primary database
- **Pydantic v2** — request/response validation
- **Alembic** — database migrations
- **JWT (python-jose)** — stateless auth with access + refresh tokens
- **PyTest + pytest-asyncio** — async integration tests

## Project structure

```
stayops/
├── app/
│   ├── api/
│   │   ├── deps.py              # Auth dependencies (get_current_user, require_host)
│   │   └── routes/
│   │       ├── auth.py          # POST /register, POST /login
│   │       ├── properties.py    # CRUD for property listings
│   │       └── bookings.py      # Create, list, cancel bookings
│   ├── core/
│   │   ├── config.py            # Pydantic Settings v2 — reads from .env
│   │   └── security.py          # JWT encode/decode, bcrypt hashing
│   ├── db/
│   │   └── session.py           # Async engine, session factory, get_db dependency
│   ├── models/                  # SQLAlchemy ORM models
│   │   ├── user.py
│   │   ├── property.py
│   │   └── booking.py           # Composite index + CheckConstraint on dates
│   ├── schemas/                 # Pydantic v2 request/response schemas
│   │   ├── user.py
│   │   ├── property.py
│   │   └── booking.py
│   ├── services/                # Business logic layer
│   │   ├── user_service.py
│   │   └── booking_service.py   # Availability check, double-booking prevention
│   └── main.py                  # FastAPI app, routers, CORS, lifespan
├── alembic/
│   └── env.py                   # Async Alembic setup
├── tests/
│   ├── conftest.py              # Fixtures: in-memory SQLite test DB, async client
│   └── test_bookings.py         # Integration tests for auth + booking flows
├── docker-compose.yml           # Postgres + Redis + API
├── Dockerfile
├── requirements.txt
└── .env.example
```

## Quick start

```bash
# 1. Clone and set up environment
cp .env.example .env

# 2. Start Postgres and Redis
docker compose up db redis -d

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run migrations
alembic upgrade head

# 5. Start the API
uvicorn app.main:app --reload

# 6. Open interactive docs
open http://localhost:8000/api/v1/docs
```

## Run tests (no Postgres needed — uses SQLite in-memory)

```bash
pip install aiosqlite   # only needed for tests
pytest -v --cov=app
```

## Key design decisions

### Async throughout
Every DB operation uses `async/await` with `asyncpg` for non-blocking I/O.
The `get_db` dependency commits on success and rolls back on any exception.

### Double-booking prevention
`booking_service.check_availability` uses the overlap formula:
`existing.check_in < new.check_out AND existing.check_out > new.check_in`
This catches all overlap cases (full overlap, partial overlap, containment).
A composite index on `(property_id, check_in, check_out)` makes this query fast.

### Pydantic v2 patterns
- `model_dump(exclude_unset=True)` on PATCH requests — only updates provided fields
- `@model_validator(mode="after")` for cross-field validation (date ordering)
- Separate `UserPublic` vs `UserInDB` schemas — the hashed password never leaks

### Role-based access
Three roles: `guest`, `host`, `admin`. FastAPI dependencies (`require_host`,
`require_admin`) enforce roles at the route level before any business logic runs.

## Phase 2 next steps

- [ ] Add Redis caching for property listings (cache-aside pattern)
- [ ] Split into 3 microservices: booking-service, property-service, user-service
- [ ] Add Docker Compose Nginx reverse proxy
- [ ] Add Prometheus metrics endpoint
