# Banking Transaction Processing System
 
A backend skeleton for a secure banking system supporting account management and money transfers.
Built with **FastAPI**, **Hexagonal Architecture**, and **Domain-Driven Design** principles.
 
---
## Architecture Overview
 
This system applies **Hexagonal Architecture (Ports & Adapters)** with DDD-influenced domain modeling.
 
The core principle: **the domain and application layers have zero dependency on frameworks, databases, or infrastructure.** They define what they need through interfaces (ports). Adapters implement those interfaces and live at the edges.

### Why Hexagonal over Layered MVC
 
| Concern | Layered MVC | Hexagonal |
|---|---|---|
| Framework coupling | High — domain imports ORM | None — domain is pure Python |
| Testability | Requires DB for service tests | Swap adapter with in-memory, zero config |
| Repository swap (Postgres → Mongo) | Touches multiple layers | Replace one adapter file |
| Explicit contracts | Implicit | Enforced via ABC ports |
 
In a banking system, the ability to test transfer logic without a database is not optional — it is a correctness requirement.
