# Architecture

## Architectural style

Use a modular monolith.

Do not use microservices in V1.

## Runtime

Local:

Docker Compose - frontend - backend - PostgreSQL

Optional speech/audio dependencies may be added behind provider
abstractions.

Future:

Kubernetes/cloud - frontend Deployment + Service - backend Deployment +
Service - ConfigMap - Secret - Ingress/Gateway - managed PostgreSQL or
suitable persistent deployment - optional object storage - optional
Redis only if a demonstrated requirement exists

Application code must not depend on Docker Compose.

## Frontend

React + TypeScript.

Conceptual structure:

-   `features/auth`
-   `features/learning`
-   `features/tests`
-   `features/statistics`
-   `features/texts`
-   `features/conversations`
-   `features/settings`
-   `features/admin`
-   `components`
-   `design-system`
-   `api`
-   `hooks`
-   `types`
-   `app`

Frontend responsibilities:

-   presentation;
-   temporary UI state;
-   API interaction;
-   draft editing;
-   audio/microphone interaction.

Frontend must not own:

-   mastery calculations;
-   review scheduling;
-   test composition;
-   LLM credentials;
-   direct database access.

## Backend

Python + FastAPI.

Conceptual modules:

-   auth
-   users
-   texts
-   learning
-   tests
-   evaluations
-   conversations
-   statistics
-   imports
-   audio
-   admin
-   shared

Domain services include:

-   `LearningEngine`
-   `EvaluationEngine`
-   `SpeechToTextProvider`
-   `TextToSpeechProvider`
-   `AudioStorage`

V1:

`EvaluationEngine -> OpenAIEvaluationEngine`

## API

REST API, versioned from the start:

`/api/v1/...`

Use explicit request/response schemas.

## Database

PostgreSQL is the durable source of truth.

Use SQLAlchemy and Alembic.

Important multi-record actions use database transactions.

Do not auto-create production schemas magically on application startup.

## Authentication

Email/password.

Prefer secure HttpOnly cookie-based authentication.

Do not store authentication tokens in browser localStorage.

Backend scaling must not depend on process-local session state.

## Configuration

Use externalized configuration/environment variables.

Examples:

-   DATABASE_URL
-   OPENAI_API_KEY
-   FRONTEND_URL
-   API_BASE_URL
-   ENVIRONMENT
-   SESSION_SECRET
-   storage/audio provider configuration

No hardcoded environment addresses.

## Secrets

Never commit secrets or bake them into images.

Local: - `.env` ignored by Git; - `.env.example` documents required
values.

Kubernetes: - Secrets/secret-management solution.

## Storage abstraction

Local V1 audio cache may use filesystem/volume.

Code depends on an `AudioStorage` interface, allowing later object
storage:

-   GCS
-   S3
-   Azure Blob

## Stateless backend

Durable user/application state belongs in PostgreSQL or durable/shared
storage.

Do not rely on backend process memory for correctness.

## Health

Provide:

-   `/health`: process alive;
-   `/ready`: critical dependencies usable.

Designed for Docker health checks and Kubernetes probes.

## Logging

Structured logs to stdout/stderr.

No required local log files.

## Reliability

-   idempotency key/submission ID for Submit;
-   atomic persistence of evaluation + attempt + progress changes;
-   LLM failure never advances progress;
-   persistence failure never displays a false success.

## Redis

Not used in V1.

Possible future uses:

-   distributed rate limiting;
-   server-side sessions;
-   job queues;
-   short-lived cache;
-   distributed locks.

PostgreSQL remains source of truth.

## Future commercialization boundaries

Prepare, but do not implement prematurely:

-   public registration;
-   email verification/recovery;
-   OAuth/MFA;
-   quotas;
-   plans/billing;
-   Redis;
-   workers;
-   organization accounts.

Track AI usage from V1 so future per-user economics are measurable.

## Privacy

Send the minimum required content to AI providers.

Do not send email, account identity, or unrelated history for linguistic
evaluation.

Account deletion must allow removal of user-specific data without
deleting global pedagogical content.
