# Banking Transaction Processing System

A production-oriented backend skeleton for a secure banking transaction platform.

This project was built for the DoubleStar backend architecture task and focuses on:

- Clean system design
- Strong separation of concerns
- Transaction consistency
- Idempotent money transfers
- Concurrency safety
- Extensible infrastructure abstractions
- Event-driven architecture readiness

The implementation intentionally prioritizes architecture, domain modeling, abstractions, and operational concerns over feature completeness.

---

# Tech Stack

- Python 3.12
- FastAPI
- SQLAlchemy
- PostgreSQL
- Redis
- Docker & Docker Compose
- Structlog
- Dependency Injector
- Pydantic
- Alembic
- Ruff + Pre-commit

---

# Architecture Style

The project uses **Hexagonal Architecture (Ports & Adapters)** combined with **DDD-inspired domain modeling**.

The system is organized around clear boundaries:

```text
                ┌──────────────────────┐
                │      FastAPI API     │
                │   HTTP Controllers   │
                └──────────┬───────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │   Application Layer  │
                │   Use Cases/Services │
                └──────────┬───────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌──────────────┐  ┌────────────────┐  ┌────────────────┐
│ Domain Model │  │ Ports/Contracts│  │ Domain Events  │
└──────────────┘  └────────────────┘  └────────────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │ Infrastructure Layer │
                │ DB/Redis/Messaging   │
                └──────────────────────┘
```

---

# Why Hexagonal Architecture?

Banking systems require:

- Strong consistency boundaries
- Isolated business rules
- Infrastructure replaceability
- High testability
- Deterministic transaction behavior

Hexagonal architecture allows the business logic to remain independent from:

- FastAPI
- SQLAlchemy
- Redis
- Kafka/RabbitMQ
- PostgreSQL

The application layer communicates only through interfaces (ports), making the system easy to test and extend.

---

# Project Structure

```text
src/
├── adapters/
│   ├── inbound/
│   │   └── http/
│   └── outbound/
│       ├── locking/
│       ├── messaging/
│       └── persistence/
│
├── application/
│   ├── dtos/
│   ├── ports/
│   │   ├── inbound/
│   │   └── outbound/
│   └── services/
│
├── domain/
│   ├── entities/
│   ├── events/
│   ├── exceptions/
│   └── value_objects/
│
├── infrastructure/
│   ├── cache/
│   ├── config/
│   ├── containers/
│   ├── database/
│   └── logging/
│
└── main.py
```

---

# Layer Responsibilities

## Domain Layer

Contains pure business logic.

### Includes

- Account entity
- Transaction entity
- Value objects
- Domain events
- Business exceptions
- Status enums

### Characteristics

- No framework dependency
- No database dependency
- No HTTP dependency
- Fully testable in isolation

---

## Application Layer

Contains use cases and orchestration logic.

### Responsibilities

- Coordinate transfers
- Enforce business workflows
- Manage idempotency
- Handle transaction lifecycle
- Interact with repositories via ports
- Publish domain events

### Important Services

- `AccountService`
- `TransferService`

---

## Ports (Interfaces)

The application layer depends only on contracts.

### Outbound Ports

- `AccountRepository`
- `TransactionRepository`
- `UnitOfWork`
- `LockManager`
- `EventBus`

### Inbound Ports

- `AccountService`
- `TransferService`

This allows infrastructure implementations to be replaced without modifying business logic.

---

## Infrastructure Layer

Implements technical concerns.

### Current Implementations

#### Persistence

- SQLAlchemy Unit of Work
- In-memory Unit of Work

#### Distributed Locking

- Redis lock manager
- In-memory lock manager

#### Messaging

- In-memory event bus

#### Observability

- Structured logging using Structlog

---

# Core Domain Models

## Account

Represents a bank account.

### Fields

```text
id
balance
currency
status
```

### Supported Behaviors

- Deposit money
- Withdraw money
- Validate balance
- Validate account state

---

## Transaction

Represents a money transfer operation.

### Fields

```text
id
from_account
to_account
amount
status
timestamp
```

### Transaction States

- Pending
- Completed
- Failed

---

# Transfer Flow

The transfer operation is the most important workflow in the system.

## High-Level Transfer Lifecycle

```text
Client Request
    ↓
API Validation
    ↓
Acquire Distributed Lock
    ↓
Start Unit Of Work
    ↓
Load Accounts
    ↓
Validate Business Rules
    ↓
Create Pending Transaction
    ↓
Withdraw From Sender
    ↓
Deposit To Receiver
    ↓
Mark Transaction Completed
    ↓
Commit Database Transaction
    ↓
Publish Domain Event
    ↓
Release Lock
```

---

# Concurrency Handling

One of the most critical banking concerns is preventing double spending.

The project includes a locking abstraction:

```text
LockManager
```

Current implementations:

- Redis-based distributed lock
- In-memory lock

## Why Locking Matters

Without locking:

```text
Account Balance = 100

Request A withdraws 80
Request B withdraws 80

Final balance becomes invalid
```

The lock ensures only one transfer modifies an account balance at a time.

---

# Idempotency Strategy

Banking APIs must safely handle retries.

Example:

```text
Client timeout
↓
Client retries transfer
↓
System must NOT transfer money twice
```

The architecture supports idempotent operations through:

- Transaction identifiers
- Persistent transaction records
- Transfer state validation
- Request deduplication design

This prevents duplicate transfers during:

- Network failures
- Client retries
- Message redelivery
- API gateway retries

---

# Consistency Model

The system prioritizes **strong consistency** for balance updates.

## Why Strong Consistency?

Bank balances are critical financial data.

Incorrect balances are unacceptable even temporarily.

### Strategy Used

- Database transaction boundaries
- Unit of Work pattern
- Distributed locking
- Atomic balance updates

---

# Scalability Considerations

The architecture is designed to scale horizontally.

## API Layer

FastAPI instances can scale independently behind a load balancer.

---

## Database Layer

Potential improvements:

- Read replicas
- Connection pooling
- Partitioned transaction tables
- CQRS read models

---

## Messaging Layer

The event bus abstraction allows migration to:

- Kafka
- RabbitMQ
- NATS

without changing business logic.

---

## Distributed Systems Readiness

The architecture already includes abstractions for:

- Distributed locking
- Event publishing
- Async workflows
- Saga orchestration evolution

---

# Event-Driven Architecture

The project includes domain event support.

### Example Events

- TransactionCreated
- TransactionCompleted
- AccountDebited
- AccountCredited

This enables future integrations such as:

- Notification services
- Fraud detection
- Ledger services
- Analytics pipelines
- Audit systems

---

# Saga Pattern Readiness

Although this project uses local ACID transactions, the architecture is compatible with future distributed workflows.

Example:

```text
Transfer Service
    ↓
Ledger Service
    ↓
Fraud Service
    ↓
Notification Service
```

In a microservice environment, Saga orchestration or choreography can coordinate distributed transactions.

---

# Security Considerations

The project includes placeholders and extension points for:

- Authentication
- Authorization
- API security
- Request validation
- Audit logging
- Sensitive data protection

Production systems would additionally include:

- JWT/OAuth2
- Rate limiting
- TLS enforcement
- Secret management
- Encryption at rest
- PCI compliance controls

---

# Observability

Operational visibility is critical in banking systems.

The project includes:

- Structured logging
- Centralized configuration
- Exception handling
- Service-level boundaries

Future improvements could include:

- OpenTelemetry tracing
- Prometheus metrics
- Grafana dashboards
- Distributed tracing
- Audit event streams

---

# API Endpoints

## Create Account

```http
POST /accounts
```

### Request

```json
{
  "currency": "USD",
  "initial_balance": 1000
}
```

---

## Get Account

```http
GET /accounts/{id}
```

---

## Transfer Money

```http
POST /transactions/transfer
```

### Request

```json
{
  "from_account_id": "uuid",
  "to_account_id": "uuid",
  "amount": 100,
  "currency": "USD",
  "idempotency_key": "external-request-id"
}
```

---

## Get Transaction

```http
GET /transactions/{id}
```

---

# Unit of Work Pattern

The project uses the Unit of Work pattern to guarantee atomic operations.

Benefits:

- Single transaction boundary
- Coordinated repository operations
- Commit/rollback control
- Better consistency guarantees

This is especially important in financial systems.

---

# Dependency Injection

The project uses a dedicated container for dependency management.

Benefits:

- Loose coupling
- Easier testing
- Environment-specific wiring
- Infrastructure swapping

---

# Running the Project

## Using Docker

```bash
docker compose up --build
```

---

## Local Development

### Install Dependencies

```bash
uv sync
```

### Run Application

```bash
uv run uvicorn src.main:app --reload
```

---

# Code Quality

The project includes:

- Ruff
- Pre-commit hooks
- Typed architecture
- Clean boundaries
- DTO separation
- Explicit contracts

---

# Design Trade-Offs

This project intentionally focuses on architecture rather than complete production implementation.

## Simplifications

- Minimal persistence implementation
- Simplified API layer
- In-memory event bus
- No real authentication provider
- No external message broker
- No ledger subsystem

---

# Production Improvements

Future enhancements could include:

- Kafka integration
- Outbox pattern
- CQRS
- Event sourcing
- Fraud detection service
- Multi-currency exchange engine
- Ledger service
- OpenTelemetry
- Distributed tracing
- Advanced retry policies
- Dead-letter queues
- Transaction reconciliation

---

# Why This Design Fits Banking Systems

This architecture prioritizes:

- Correctness
- Isolation
- Consistency
- Extensibility
- Testability
- Operational safety

The design intentionally models real-world financial system concerns:

- Double spending prevention
- Idempotent transfers
- Strong consistency
- Transaction lifecycle management
- Infrastructure abstraction
- Event-driven extensibility

---

# Final Notes

This repository is intentionally designed as a backend architecture foundation rather than a feature-complete banking platform.

The primary goal is demonstrating:

- Architectural thinking
- Real-world backend design
- Financial system awareness
- Scalable abstraction design
- Engineering maturity

The implementation can evolve incrementally into a production-grade distributed banking platform while preserving the same architectural boundaries.
