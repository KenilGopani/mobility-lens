# ADR-001: FastAPI backend

**Status:** Accepted

## Context
The API is read-heavy, needs strict request/response validation, and should publish an OpenAPI contract the frontend and tests can rely on. The pipeline and scoring code is Python.

## Decision
Use FastAPI with Pydantic v2, SQLAlchemy 2.x, and Alembic.

## Consequences
- OpenAPI is generated automatically and used for contract tests.
- One language across API, pipeline, and scoring, so scoring logic is shared without reimplementation.
- Async is optional; sync SQLAlchemy sessions are acceptable at this scale. Revisit only if profiling justifies it.

## Alternatives considered
- Flask: no built-in validation or schema generation.
- Django/GeoDjango: heavier than a read API needs.
