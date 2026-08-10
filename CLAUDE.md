# PhraseFluency - Claude Code Instructions

Before implementing or modifying functionality, read the relevant
documents in `docs/`.

## Non-negotiable principles

1.  Do not change pedagogical rules without an explicit product
    decision.
2.  Keep business rules in the backend/domain layer, never in React
    components.
3.  PostgreSQL is the source of truth.
4.  Every meaningful user action is persisted automatically. There is no
    user-facing Save workflow.
5.  The backend must remain stateless between requests except for
    durable/shared stores.
6.  Configuration and secrets must be externalized.
7.  The application must run with Docker Compose but must not depend
    architecturally on Docker Compose.
8.  Preserve future Kubernetes/cloud portability.
9.  Use a modular monolith. Do not introduce microservices without a
    demonstrated requirement.
10. The UI must be polished, responsive, cohesive, and suitable for a
    commercial product.
11. OpenAI is the only linguistic evaluation engine in V1, behind an
    `EvaluationEngine` abstraction.
12. Never send user identity data to the LLM when it is unnecessary.
13. All learning-engine rules require automated tests.
14. Prompt/model changes require running the linguistic benchmark.
15. Do not add Redis, billing, OAuth, MFA, or other future features to
    V1 unless explicitly requested.

## Language

-   Product learning target: American English.
-   Development identifiers, code, API names, schemas, and technical
    artifacts: English.
