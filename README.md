# PhraseFluency

PhraseFluency is a web application for acquiring natural American
English through repeated active production, contextual exposure, audio,
and optional explanations.

The initial deployment target is Docker Compose on a local machine. The
architecture must remain portable to Kubernetes/cloud deployment without
major application rewrites.

## Core stack

-   Frontend: React + TypeScript
-   Backend: Python + FastAPI
-   Database: PostgreSQL
-   ORM: SQLAlchemy
-   Migrations: Alembic
-   LLM: OpenAI API
-   Runtime: Docker Compose
-   Future deployment: Kubernetes-compatible
-   Redis: not used in V1

## Documentation

-   `docs/product-requirements.md`
-   `docs/learning-engine.md`
-   `docs/ui-ux-specification.md`
-   `docs/data-model.md`
-   `docs/architecture.md`
-   `docs/llm-integration.md`
-   `docs/linguistic-benchmark.md`
-   `docs/text-generation-guidelines.md`
-   `docs/decisions/`

These documents are the source of truth for implementation.
