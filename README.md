# Banking Transaction Processing System

A backend skeleton for a secure, scalable banking platform built with **Domain-Driven Design** and **Hexagonal Architecture** (Ports & Adapters).

> **Stack:** Python 3.11 · FastAPI · PostgreSQL · Redis · SQLAlchemy (async) · Alembic · dependency-injector · structlog

---

## Table of Contents

1. [Architecture Decisions](#1-architecture-decisions)
2. [Project Structure](#2-project-structure)
3. [Domain Model](#3-domain-model)
4. [Data Flow — Transfer Request](#4-data-flow--transfer-request)
5. [API Design](#5-api-design)
6. [Concurrency & Double-Spend Prevention](#6-concurrency--double-spend-prevention)
7. [Consistency Model](#7-consistency-model)
8. [Event-Driven Design & Outbox Pattern](#8-event-driven-design--outbox-pattern)
9. [Observability](#9-observability)
10. [Security](#10-security)
11. [Running the Project](#11-running-the-project)
12. [Scaling Strategy](#12-scaling-strategy)
13. [Trade-offs & Simplifications](#13-trade-offs--simplifications)
14. [What Would Be Added in Production](#14-what-would-be-added-in-production)

---

## 1. Architecture Decisions

### Why DDD + Hexagonal Architecture?

The task explicitly evaluates **system design clarity** and **separation of concerns**. In a banking domain these are not stylistic preferences — they are correctness requirements:

- A money transfer touches two accounts. If business logic leaks into the HTTP layer or the ORM layer, it becomes impossible to test the transfer rules without a running database and HTTP server.
- Regulatory compliance (PSD2) requires a full audit trail. Domain events emitted by aggregates provide this naturally without bolting on separate audit logging.
- The system must run as a monolith today and split into microservices tomorrow. Hexagonal Architecture makes this boundary explicit from day one.

**Hexagonal Architecture** means the domain has zero knowledge of FastAPI, SQLAlchemy and Redis. Those are adapters — plugged into ports (interfaces) defined by the application layer.

```
                        ┌─────────────────────────────┐
   HTTP Request ───────►│   Inbound Adapter (FastAPI) │
                        │   accounts router           │
                        │   transactions router       │
                        └────────────┬────────────────┘
                                     │ calls
                        ┌────────────▼────────────────-┐
                        │   Application Service        │
                        │   TransferService            │
                        │   AccountService             │
                        └──┬──────────────┬────────────┘
                           │              │ uses ports
              ┌────────────▼──┐     ┌─────▼──────────────┐
              │  Domain Layer │     │  Outbound Ports    │
              │  Account      │     │  IAccountRepository│
              │  Transaction  │     │  ITransactionRepo  │
              │  Money (VO)   │     │  ILockManager      │
              │  DomainEvents │     │  IEventBus         │
              └───────────────┘     └──────┬─────────────┘
                                           │ implemented by
                        ┌──────────────────▼──────────────┐
                        │   Outbound Adapters             │
                        │   PostgresAccountRepository     │
                        │   PostgresTransactionRepository │
                        │   RedisLockManager              │
                        │   InMemoryBus                   │
                        └─────────────────────────────────┘
```

### Why FastAPI over Django?

The job description calls for **microservices** and **event-driven systems**. FastAPI is:
- Lightweight — no ORM, no admin, no session middleware baked in
- Natively async — compatible with `asyncpg`
- Type-safe — Pydantic models serve as both validation and OpenAPI documentation

Django REST Framework is excellent for CRUD-heavy monoliths. This system is neither.

### Why PostgreSQL?

Money transfers require **ACID transactions**. The debit and credit of a transfer must succeed or fail atomically — no eventual consistency here. PostgreSQL provides:
- `NUMERIC(19, 4)` — exact decimal arithmetic (float causes rounding errors in banking)
- `SELECT FOR UPDATE` — row-level pessimistic locking for the second concurrency layer
- Native `ENUM` types for status columns; `CHECK` constraints for currency (migration-safe)
- `TIMESTAMPTZ` — all timestamps stored with timezone, never naive datetimes

---

## 2. Project Structure

```
banking-transaction-system/
│
├── src/
│   ├── domain/                          # Pure Python — zero framework imports
│   │   ├── aggregates/
│   │   │   ├── account.py               # Account aggregate root
│   │   │   └── transaction.py           # Transaction aggregate root
│   │   ├── events/
│   │   │   ├── account.py               # AccountCreated, BalanceDebited, ...
│   │   │   └── transaction.py           # TransactionInitiated, TransactionCompleted, ...
│   │   ├── exceptions/
│   │   │   ├── account.py               # AccountFrozenError, InsufficientFundsError, ...
│   │   │   ├── transaction.py           # DuplicateIdempotencyKeyError, ...
│   │   │   └── base.py                  # DomainException, CurrencyMismatchError
│   │   ├── value_objects/
│   │   │   ├── money.py                 # Money(amount: Decimal, currency: Currency)
│   │   │   ├── enums.py                 # Currency, AccountStatus, TransactionStatus
│   │   │   └── identifiers.py           # AccountId, TransactionId, IdempotencyKey (NewType)
│   │   └── entities/
│   │       └── base.py                  # AggregateRoot with domain event collection
│   │
│   ├── application/
│   │   ├── ports/
│   │   │   ├── inbound/                 # What the HTTP layer can call
│   │   │   │   ├── account_service.py   # IAccountService protocol
│   │   │   │   └── transfer_service.py  # ITransferService protocol
│   │   │   └── outbound/               # What the domain needs from infrastructure
│   │   │       ├── account_repository.py
│   │   │       ├── transaction_repository.py
│   │   │       ├── lock_manager.py      # ILockManager protocol
│   │   │       ├── event_bus.py         # IEventBus protocol
│   │   │       └── unit_of_work.py      # IUnitOfWork protocol
│   │   ├── services/
│   │   │   ├── account.py               # AccountService (stub)
│   │   │   └── transfer.py              # TransferService (stub)
│   │   └── dtos/
│   │       ├── account.py               # CreateAccountCommand, AccountDTO
│   │       └── transaction.py           # InitiateTransferCommand, TransactionDTO
│   │
│   ├── adapters/
│   │   ├── inbound/
│   │   │   └── http/
│   │   │       ├── routers/
│   │   │       │   ├── accounts.py      # POST /accounts, GET /accounts/{id}
│   │   │       │   ├── transactions.py  # POST /transactions/transfer, GET /transactions/{id}
│   │   │       │   ├── health.py        # GET /health
│   │   │       │   └── auth.py          # POST /auth/dev-token (dev only)
│   │   │       ├── middleware/
│   │   │       │   ├── request_id.py    # Injects X-Request-ID correlation header
│   │   │       │   └── auth.py          # Resolves AuthenticatedUser from token
│   │   │       └── exception_handlers.py
│   │   │
│   │   └── outbound/
│   │       ├── persistence/
│   │       │   ├── models/
│   │       │   │   ├── account_model.py     # AccountORM (SQLAlchemy)
│   │       │   │   ├── transaction_model.py # TransactionORM (SQLAlchemy)
│   │       │   │   ├── outbox_model.py      # OutboxMessageORM (SQLAlchemy)
│   │       │   │   └── shared.py            # _utcnow()
│   │       │   ├── mappers/
│   │       │   │   ├── account_mapper.py    # to_domain / to_new_orm / update_orm
│   │       │   │   └── transaction_mapper.py
│   │       │   ├── repositories/
│   │       │   │   └── postgres_account_repository.py
│   │       │   └── sqlalchemy_unit_of_work.py  # wraps both repos in one transaction
│   │       ├── messaging/
│   │       │   ├── in_memory_event_bus.py   # used when KAFKA_ENABLED=false
│   │       │   └── outbox_worker.py         # background task (skeleton)
│   │       └── locking/
│   │           └── redis_lock_manager.py    # RedisLockManager with retry loop
│   │
│   └── infrastructure/
│       ├── config/
│       │   └── settings.py              # Pydantic Settings — reads from .env
│       ├── containers/
│       │   └── container.py             # dependency-injector DI container
│       ├── database/
│       │   └── engine.py                # async SQLAlchemy engine + Base
│       └── logging/
│           └── setup.py                 # structlog configuration
│
├── alembic/
│   ├── env.py                           # wires Alembic to models + settings
│   ├── script.py.mako                   # migration file template
│   └── versions/
│       └── 20260529_0000_0001_initial_schema.py
│
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   │   ├── test_account.py          # Account.debit / credit / freeze / close
│   │   │   └── test_transaction.py      # Transaction state machine
│   │   └── application/
│   │       └── test_transfer_service.py
│   └── integration/
│       └── api/
│           └── test_accounts_api.py
│
├── scripts/
│   └── setup_local_db.sh                # creates local postgres role + db
│
├── Dockerfile                           # multi-stage, non-root user
├── docker-compose.yml                   # postgres + redis + app
├── alembic.ini
├── pyproject.toml
└── .env.example
```

---

## 3. Domain Model

### Account Aggregate

The `Account` aggregate root owns all balance mutations. Nothing outside the aggregate can change `_balance` directly — all changes go through `debit()` and `credit()` which enforce invariants before modifying state.

```
Account
  id:             AccountId (typed UUID)
  owner_id:       OwnerId
  account_number: str  (DE + 16 digits, production uses IBAN generator)
  _balance:       Money  (amount: Decimal, currency: Currency)
  currency:       Currency (derived from balance — single source of truth)
  status:         AccountStatus

Status transitions (state machine):
  ACTIVE ──► FROZEN ──► ACTIVE   (compliance hold / release)
  ACTIVE ──► CLOSED               (terminal — balance must be zero)
  FROZEN ──► CLOSED               (terminal)
```

**Why `_balance` is private:** The invariant "you cannot spend what you don't have" is enforced inside `Money.__sub__`. Making `_balance` private means no code path can subtract money without going through `Account.debit()` → `Money.__sub__` → `InsufficientFundsError`.

### Transaction Aggregate

The `Transaction` aggregate root owns the transfer lifecycle. It holds references to both accounts by `AccountId` only — never by object reference. This enforces aggregate isolation: loading a `Transaction` never triggers loading an `Account`.

```
Transaction
  id:               TransactionId
  idempotency_key:  IdempotencyKey
  from_account_id:  AccountId
  to_account_id:    AccountId
  _amount:          Money
  transaction_type: TransactionType
  status:           TransactionStatus
  failure_code:     str | None
  failure_reason:   str | None
  completed_at:     datetime | None

Status transitions (state machine):
  PENDING ──► PROCESSING ──► COMPLETED   (happy path)
  PENDING ──► FAILED                     (validation failure — no debit)
  PENDING ──► PROCESSING ──► FAILED      (runtime failure — debit may have applied)
  COMPLETED ──► (terminal, cannot be failed — create REVERSAL transaction instead)
```

### Value Objects

| Value Object | Description |
|---|---|
| `Money` | `Decimal` amount + `Currency`. Arithmetic only between same currency. `ROUND_HALF_UP` at 2 decimal places. `InsufficientFundsError` raised inside `__sub__` — impossible to bypass. |
| `Currency` | ISO 4217 `Enum`: `EUR`, `USD`, `GBP`, `IRR`. `EUR` is the primary SEPA currency. Stored as `String(3)` + `CHECK` constraint in DB — not a PostgreSQL `ENUM` type (migration-safe). |
| `AccountId` / `TransactionId` | `NewType` wrappers over `UUID`. Prevents passing a `TransactionId` where an `AccountId` is expected — caught by mypy, not at runtime. |
| `IdempotencyKey` | `NewType` over `str`. Max 64 chars. Enforced unique at DB level (`UNIQUE` constraint) as the final safety net against race conditions. |

### Domain Events

Every state-mutating operation on an aggregate records a domain event. Events are collected on the aggregate root and dispatched by the Unit of Work after the DB transaction commits — using the **Transactional Outbox** pattern.

| Event | Emitted by | Consumers |
|---|---|---|
| `AccountCreated` | `Account.create()` | Audit log, notification |
| `BalanceDebited` | `Account.debit()` | Ledger, fraud detection |
| `BalanceCredited` | `Account.credit()` | Ledger, notification |
| `AccountFrozen` | `Account.freeze()` | Compliance dashboard |
| `TransactionInitiated` | `Transaction.initiate()` | Fraud detection, rate limiter |
| `TransactionCompleted` | `Transaction.complete()` | Notification, statement generator |
| `TransactionFailed` | `Transaction.fail()` | Rollback handler, notification |
| `TransactionRolledBack` | `Transaction.mark_rolled_back()` | Ledger, notification |
| `DuplicateTransactionDetected` | Service layer | Fraud detection, audit |

---

## 4. Data Flow — Transfer Request

```
POST /api/v1/transactions/transfer
{
  "from_account_id": "uuid-A",
  "to_account_id":   "uuid-B",
  "amount":          "100.00",
  "currency":        "EUR",
  "idempotency_key": "client-uuid-xyz"
}
```

```
1. RequestIdMiddleware
   └─ generates / forwards X-Request-ID
   └─ binds request_id to structlog context vars
      (all log lines in this request carry request_id automatically)

2. AuthMiddleware
   └─ resolves AuthenticatedUser from Bearer token
   └─ attaches to request.state.user

3. TransactionRouter
   └─ parses and validates request body (Pydantic)
   └─ builds InitiateTransferCommand
   └─ calls TransferService.initiate(command)

4. TransferService.initiate()
   a. Check idempotency key in Redis cache
      └─ HIT  → return existing transaction (no re-execution)
      └─ MISS → continue

   b. Acquire distributed lock (RedisLockManager)
      └─ keys = sorted([str(from_id), str(to_id)])  ← deadlock prevention
      └─ retries up to wait_timeout=5s with 50ms backoff
      └─ raises ConcurrencyConflictError if timeout exhausted

   c. Open Unit of Work (one DB transaction for everything below)

   d. Load accounts with SELECT FOR UPDATE (pessimistic lock — layer 2)

   e. Create Transaction aggregate
      └─ Transaction.initiate(from_id, to_id, amount, idempotency_key)
      └─ validates: amount > 0, from_id ≠ to_id
      └─ records TransactionInitiated domain event

   f. transaction.mark_processing()
      └─ status: PENDING → PROCESSING
      └─ records TransactionProcessing event

   g. from_account.debit(amount, transaction.id)
      └─ checks: ACTIVE status, sufficient funds
      └─ balance -= amount
      └─ records BalanceDebited event

   h. to_account.credit(amount, transaction.id)
      └─ checks: not CLOSED
      └─ balance += amount
      └─ records BalanceCredited event

   i. transaction.complete()
      └─ status: PROCESSING → COMPLETED
      └─ sets completed_at
      └─ records TransactionCompleted event

   j. Unit of Work commits:
      └─ saves Transaction ORM row
      └─ updates Account ORM rows (with version check — optimistic locking)
      └─ writes all domain events to outbox_messages table
      └─ all in ONE atomic DB transaction

   k. Distributed lock released (finally block)

5. Outbox Worker (background task — runs separately)
   └─ polls outbox_messages WHERE published=false ORDER BY created_at
   └─ publishes each event to in_memory
   └─ sets published=true, published_at=now()
   └─ retries on failure up to MAX_RETRIES

6. HTTP Response 202 Accepted
   {
     "transaction_id": "uuid",
     "status": "completed",
     "amount": "100.00",
     "currency": "EUR"
   }
```

### Failure path (debit succeeded, credit failed)

```
   g. from_account.debit() ✅
   h. to_account.credit()  ❌ AccountFrozenError

   → transaction.fail(code="ACCOUNT_FROZEN", reason="...")
     rollback_required=True on TransactionFailed event
     (True because we were in PROCESSING when fail() was called)

   → from_account.credit(amount)  ← reverses the debit
   → transaction.mark_rolled_back()

   → UoW commits:
     transaction status=FAILED, failure_code set
     from_account balance restored
     TransactionFailed + TransactionRolledBack events written to outbox
```

---

## 5. API Design

All endpoints are prefixed `/api/v1`. Authentication via `Authorization: Bearer <token>`.

### Accounts

| Method | Path | Description | Status |
|---|---|---|---|
| `POST` | `/api/v1/accounts` | Create a new account | Skeleton |
| `GET` | `/api/v1/accounts/{id}` | Get account details | Skeleton |

**POST /api/v1/accounts — Request**
```json
{
  "currency": "EUR",
  "account_type": "checking"
}
```

**POST /api/v1/accounts — Response 201**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "account_number": "DE4829301827364910",
  "balance": "0.00",
  "currency": "EUR",
  "status": "active",
  "created_at": "2026-05-29T08:00:00Z"
}
```

### Transactions

| Method | Path | Description | Status |
|---|---|---|---|
| `POST` | `/api/v1/transactions/transfer` | Initiate a transfer | Skeleton |
| `GET` | `/api/v1/transactions/{id}` | Get transaction details | Skeleton |

**POST /api/v1/transactions/transfer — Request**
```json
{
  "from_account_id": "550e8400-e29b-41d4-a716-446655440000",
  "to_account_id":   "661f9511-f30c-52e5-b827-557766551111",
  "amount":          "250.00",
  "currency":        "EUR"
}
```

**Header:** `Idempotency-Key: <client-uuid>` (required)

**Response 202**
```json
{
  "transaction_id": "772aa622-...",
  "status": "completed",
  "amount": "250.00",
  "currency": "EUR",
  "completed_at": "2026-05-29T08:00:00.123Z"
}
```

### Error responses

All errors follow the same envelope:
```json
{
  "error": {
    "code": "INSUFFICIENT_FUNDS",
    "detail": "Account '...' has insufficient funds: required 250.00, available 45.00"
  }
}
```

| Code | HTTP | When |
|---|---|---|
| `INSUFFICIENT_FUNDS` | 422 | `Account.debit()` fails balance check |
| `ACCOUNT_FROZEN` | 422 | Account status is FROZEN |
| `ACCOUNT_CLOSED` | 422 | Account status is CLOSED |
| `DUPLICATE_TRANSFER` | 409 | Idempotency key already used — returns original |
| `CURRENCY_MISMATCH` | 422 | `from` and `to` accounts have different currencies |
| `CONCURRENT_MODIFICATION` | 503 + `Retry-After: 1` | Optimistic lock version mismatch |
| `ACCOUNT_NOT_FOUND` | 404 | Account ID does not exist |

### Development authentication

```bash
# 1. Get a dev token
curl -X POST http://localhost:8000/auth/dev-token

# 2. Use it
curl -H "Authorization: Bearer dev:<uuid>" \
     http://localhost:8000/api/v1/accounts
```

Or set `X-Dev-User-Id: <uuid>` header directly. Both methods disabled in production.

---

## 6. Concurrency & Double-Spend Prevention

Two-layer locking strategy — both layers must be breached simultaneously for a double-spend to occur.

### Layer 1 — Redis Distributed Lock

**Scope:** Cross-process, cross-pod. Prevents two application instances from processing a transfer for the same accounts simultaneously.

```python
keys = sorted([str(from_account_id), str(to_account_id)])
async with lock_manager.acquire(*keys, ttl_seconds=30):
    # only one pod runs this block at a time
```

**Why sort keys:** Without sorting, Transfer A→B and Transfer B→A acquire locks in opposite order — deadlock. Sorting guarantees both always acquire in the same order.

**Retry behaviour:** On contention, retries every 50ms up to `wait_timeout=5s`. Locks are held for ~10–100ms (one DB transaction). Failing immediately would make concurrent transfers to the same account permanently error — unacceptable.

**TTL safety net:** All locks have `ex=30s`. If the process crashes while holding a lock, Redis expires it automatically. The next request acquires it cleanly.

### Layer 2 — SELECT FOR UPDATE

**Scope:** Within the DB. Prevents a race condition if the Redis lock is lost (Redis crash, network partition).

```python
SELECT * FROM accounts WHERE id = $1 FOR UPDATE
```

The row-level lock is held for the duration of the DB transaction. Any other transaction attempting to modify the same row blocks until the first commits or rolls back.

### Idempotency

Every transfer request requires an `Idempotency-Key` header. The key is:
1. Checked in Redis cache before acquiring any locks
2. Stored in the `transactions` table with a `UNIQUE` constraint

The `UNIQUE` constraint is the final safety net — even if two requests with the same key pass the Redis check simultaneously (race condition), only one `INSERT` wins. The other gets a `UniqueViolation` which the repository converts to `DuplicateIdempotencyKeyError`.

---

## 7. Consistency Model

This system chooses **strong consistency (CP)** over eventual consistency (AP) for all money movements.

| Concern | Decision | Rationale |
|---|---|---|
| Transfer atomicity | Strong — single DB transaction | Debit and credit must succeed together or not at all |
| Balance reads | Strong — reads from primary | A balance read immediately after a transfer must reflect the transfer |
| Event publishing | Eventual — Outbox pattern | Kafka publish can lag behind DB commit by seconds; consumers handle idempotency |
| Idempotency cache | Eventual — Redis TTL 24h | If Redis is down, the DB `UNIQUE` constraint catches duplicates |

**CAP theorem position:** In a network partition, this system chooses to reject writes (remain consistent) rather than accept potentially conflicting writes (remain available). A banking system that allows inconsistent writes is incorrect regardless of how available it is.

---

## 8. Event-Driven Design & Outbox Pattern

### The Dual-Write Problem

A naive implementation publishes to Kafka inside the service:
```python
# ❌ WRONG — if crash occurs between commit and publish:
await uow.commit()          # DB updated ✅
await kafka.publish(event)  # Kafka never notified ❌
```

Downstream services (ledger, notifications) are out of sync. Money moved in the DB but the world doesn't know.

### The Outbox Solution

Domain events are written to the `outbox_messages` table **in the same DB transaction** as the balance changes:

```python
# ✅ CORRECT — both writes are atomic
async with uow:
    uow.accounts.save(from_account)    # balance changes
    uow.accounts.save(to_account)      # balance changes
    uow.transactions.save(transaction) # status change
    uow.outbox.add_all(domain_events)  # events queued
    await uow.commit()                 # ALL or NOTHING
```

A separate **Outbox Worker** (background task) polls `outbox_messages WHERE published=false` and publishes to Kafka:

```python
# outbox_worker.py (skeleton)
while True:
    messages = await repo.get_unpublished(batch_size=100)
    for msg in messages:
        await kafka.publish(topic=msg.aggregate_type, event=msg.payload)
        await repo.mark_published(msg.id)
    await asyncio.sleep(POLL_INTERVAL_SECONDS)
```

**Guarantees:**
- At-least-once delivery (worker retries on failure)
- No event lost on application crash
- Consumers must handle duplicate events via their own idempotency keys

---

## 9. Observability

### Structured Logging (structlog)

Every log line is JSON with consistent fields:

```json
{
  "event": "transfer_completed",
  "request_id": "97711d40-ae98-42a3-8604-51e939ef85b7",
  "transaction_id": "772aa622-...",
  "from_account_id": "550e8400-...",
  "amount": "250.00",
  "level": "info",
  "logger": "src.application.services.transfer",
  "timestamp": "2026-05-29T08:00:00.123456Z"
}
```

`request_id` is injected by `RequestIdMiddleware` at the start of each request and automatically attached to every log line via `structlog.contextvars` — no need to thread it through function signatures.

### Correlation IDs

Every response includes `X-Request-ID`. Clients can log this and provide it to support teams to trace a specific request across all services and log aggregators.

### Health Endpoints

```
GET /health         → liveness probe  (is the process alive?)
```

Used by Docker and Kubernetes to determine when to send traffic and when to restart.

---

## 10. Security

| Concern | Implementation |
|---|---|
| Authentication | JWT Bearer token placeholder. `get_current_user` FastAPI dependency resolves `AuthenticatedUser`. Swap `_validate_jwt()` stub with `python-jose` for production. |
| Authorization | `AuthenticatedUser.can_access_account(owner_id)` — users can only access their own accounts. Admin role bypasses ownership check. |
| Dev tokens | `POST /auth/dev-token` issues `dev:<uuid>` tokens. Raises HTTP 403 in production (`is_production` check). |
| Secrets | All credentials via environment variables. No secrets in `alembic.ini` or committed `.env` files. |
| Non-root container | Dockerfile creates `appuser:appgroup` (uid 1001). Process never runs as root. |
| API docs | Swagger UI (`/docs`) disabled in production via `docs_url=None`. |

---

## 11. Running the Project

### Prerequisites

- Docker + Docker Compose
- Python 3.11+

### Quick start

```bash
# Clone and enter
git clone <repo-url>
cd banking-transaction-system

# Copy environment file
cp .env.example .env

# Start infrastructure (postgres, redis)
docker compose up postgres redis -d

# Install dependencies
poetry install

# Run database migrations
alembic upgrade head

# Start the application
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### Full Docker start

```bash
docker compose up --build -d
```

### Useful Alembic commands

```bash
alembic upgrade head            # apply all pending migrations
alembic revision --autogenerate -m "add iban to accounts"
alembic history --verbose       # see migration history
alembic downgrade -1            # roll back one migration
alembic upgrade head --sql      # preview SQL without running
```

### Development authentication

```bash
# Get a token for Swagger
curl -X POST http://localhost:8000/auth/dev-token

# Use it in curl
curl -H "Authorization: Bearer dev:<uuid>" \
     http://localhost:8000/api/v1/accounts

# Or simpler — plain header
curl -H "X-Dev-User-Id: <any-uuid>" \
     http://localhost:8000/api/v1/accounts
```

---

## 12. Scaling Strategy

### Horizontal scaling (stateless application tier)

The application is stateless — all state lives in PostgreSQL and Redis. Running N replicas behind a load balancer requires no application changes. The two-layer locking strategy (Redis + `SELECT FOR UPDATE`) ensures correctness under concurrent load across all replicas.

### Database scaling

| Stage | Strategy |
|---|---|
| Single instance | Current implementation |
| Read scaling | Add PostgreSQL read replicas. Route `GET /accounts/{id}` to replicas, `POST /transactions/transfer` to primary only. |
| Write scaling | Partition `transactions` table by `created_at` (time-based) or by `from_account_id` (hash-based). Alembic migration handles partition creation. |
| Connection pooling | PgBouncer in transaction pooling mode in front of PostgreSQL. SQLAlchemy pool_size=10, max_overflow=20 per pod. |

### Redis scaling

Redis Cluster for the distributed lock if single-node Redis becomes a bottleneck. The `RedisLockManager` uses `SET NX EX` — compatible with Redis Cluster when key slots are correctly handled (Redlock algorithm for true distributed locking).

---

## 13. Trade-offs & Simplifications

| Simplification | What it means | Production solution |
|---|---|---|
| Services are stubs | `AccountService` and `TransferService` have the correct signatures and structure but business logic is not fully implemented | Implement the transfer flow described in Section 4 |
| In-memory event bus | `KAFKA_ENABLED=false` by default — events are logged locally | Set `KAFKA_ENABLED=true` and provide Kafka connection |
| Outbox worker is skeleton | Worker polls the DB but Kafka publish is not fully wired | Complete `KafkaEventBus.publish()` and wire into worker |
| No real JWT validation | `_validate_jwt()` raises immediately | Replace with `python-jose` RS256 validation against identity provider |
| Account number generation | `random.randint` — not guaranteed unique under concurrency | Use PostgreSQL sequence or dedicated IBAN generation service |
| No ForeignKey on transaction → account | Microservice-friendly but no DB referential integrity | Add `ForeignKey("accounts.id")` for monolith deployment |
| Single PostgreSQL instance | No read replica, no partitioning | See scaling strategy above |
| `IRR` in Currency enum | Iranian Rial included for personal context | Remove or keep depending on business requirements |

---

## 14. What Would Be Added in Production

**Domain:**
- Saga pattern for complex multi-step transfers (cross-currency, cross-bank)
- Account snapshot table for fast balance reconstruction without replaying all transactions
- `REVERSAL` transaction type for chargebacks

**Infrastructure:**
- PgBouncer connection pooler
- Redis Cluster with Redlock for true distributed locking
- Dead letter queue for outbox messages that fail after MAX_RETRIES
- Schema registry for Kafka event schemas (Avro/Protobuf)

**Observability:**
- OpenTelemetry distributed tracing (spans across HTTP → service → DB)
- Prometheus metrics (transfer latency, lock contention rate, outbox lag)
- Grafana dashboards

**Security:**
- RS256 JWT with rotating key pairs
- Rate limiting per account (prevent transfer flooding)
- mTLS between internal services

**Operations:**
- Kubernetes manifests with liveness/readiness probes wired to `/health`  
- Helm chart with configurable replica count and resource limits
- GitHub Actions CI/CD: lint → test → build → push → deploy
