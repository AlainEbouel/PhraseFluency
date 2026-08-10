# ADR 0001 - Modular Monolith

## Decision

Use a modular monolith for V1.

## Rationale

The product needs strong domain boundaries and future extensibility but
does not currently justify distributed-system complexity.

## Consequences

-   one backend deployment unit initially;
-   domain modules remain separated;
-   future extraction is possible if real scaling/operational needs
    emerge;
-   no microservices, message bus, or service mesh in V1.
