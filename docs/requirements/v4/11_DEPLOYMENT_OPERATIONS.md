# Deployment and operations

## Runtime
Docker/Compose gives a reproducible local topology with API, frontend, PostgreSQL, Redis/Valkey and durable worker. Production uses managed secrets, TLS, object storage for generated media, health/readiness, bounded jobs, external API timeouts, queue leases, dead letters, idempotent retries, structured logs/metrics and alerts.

## Release controls
Migrate before API start using Alembic; verify the target head and metadata drift. Back up the database and demonstrate restore before destructive schema changes. Store the exact deployed SHA, image digest, migration revision, last backup, health/readiness and rollback target.

## Reliability
Test SIGTERM, worker crash/restart, lease expiry/races, duplicate delivery, retry after external success, scheduler concurrency, DB disconnect, stale queues, dead-letter replay and rollback. External publication/email/ads/financial writes stay off until explicitly authorized.

## Status
The repository now includes Dockerfile/Compose and an Alembic baseline/gate. A real hosted staging deployment, PostgreSQL upgrade/restore, production domain/secret setup and monitoring/SLO evidence are not recorded, so no live status is claimed.


## Inbound reverse-proxy and client-IP trust
- Docker Compose binds the API to loopback by default. Rate-limit keys use `request.client.host`; do not treat a client-supplied `X-Forwarded-For` value as trusted identity.
- If deploying behind a reverse proxy, configure Uvicorn forwarded-header trust only for the exact proxy address(es)/CIDR(s) using `--forwarded-allow-ips`. The proxy must strip and replace inbound forwarding headers. Never use `--forwarded-allow-ips=*` on a public deployment.
- This repository does not define a trusted-proxy CIDR setting. Document and test the real ingress/proxy chain during staging; until then, assume the direct peer address is the rate-limit identity.
