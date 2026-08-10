# ADR 0002 - PostgreSQL as Source of Truth, No Redis in V1

## Decision

Use PostgreSQL as the durable source of truth. Do not deploy Redis in
V1.

## Rationale

Current requirements do not need Redis. Adding it would increase
operational complexity without clear product value.

## Future

Redis may later support distributed rate limiting, queues, short-lived
cache, sessions, or locks. It must never replace PostgreSQL as the
durable learning-data source of truth.
