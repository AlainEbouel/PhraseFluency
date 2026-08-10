# ADR 0004 - Local-First, Cloud-Ready

## Decision

Run V1 with Docker Compose while designing application boundaries for
future Kubernetes/cloud deployment.

## Requirements

-   externalized configuration;
-   stateless backend;
-   durable database;
-   no Docker-Compose-specific application logic;
-   separate frontend/backend images;
-   health/readiness endpoints;
-   stdout/stderr logs;
-   storage provider abstractions;
-   no hardcoded local URLs.

## Goal

Future migration should primarily be an infrastructure/deployment
change, not an application rewrite.
