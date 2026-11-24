# Production and Release Readiness

This document describes the current repository state. It is not a claim that the application is ready for direct exposure to the public internet.

## Current Capabilities

| Area | Implemented | Remaining production work |
|------|-------------|---------------------------|
| API health | Liveness and database readiness endpoints | Add deployment-level probes and alerting |
| Persistence | SQLite quick start and SQLAlchemy-compatible PostgreSQL URL | Adopt Alembic and test forward/rollback migrations |
| Evaluation queue | Database task state, atomic claims, worker heartbeat leases, stale lease recovery, bounded manual retries | Workers still run inside API processes; no external broker or independently scaled worker pool |
| Agent traces | OTel-style trace normalization during ingestion | No OTLP exporter or collector integration |
| Agent sandbox | Declarative in-memory fixture replay with deterministic assertions | Does not execute arbitrary code inside an OS/container sandbox |
| Judge calibration | Labeled score comparison, MAE, repeat variance, versioned history | Add calibration thresholds and release gates |
| Reproducibility | Dataset, model, metric versions and hashed task snapshots | Add durable snapshot retention/export policy |
| CI | Backend regression suite and frontend build on pushes and pull requests | Add PostgreSQL and multi-process integration jobs |
| Secrets | API responses mask model and endpoint credentials | Database values are not encrypted at rest |

## Required Before Internet Exposure

- Add authentication and role-based authorization, then test cross-tenant resource isolation.
- Encrypt API credentials at rest and define rotation and backup-key procedures.
- Add append-only audit records for configuration changes, evaluation starts, cancellations, retries, and exports.
- Move task execution to a separately scaled broker-backed worker before running multiple API replicas under significant load.
- Use versioned database migrations and exercise forward migration and rollback against production-like PostgreSQL.
- Configure TLS, upload limits, network egress controls for endpoint evaluation, rate limits, backups, and alerting.
- Review Git history and repository contents for secrets, runtime databases, and uploaded data before publishing.

## Repository Hygiene

- Keep `.env`, databases, uploaded documents, WAL/SHM files, and IDE metadata out of version control.
- Use only placeholder credentials and non-routable example URLs in docs and fixtures.
- Do not publish local evaluation data or reports without reviewing them for personal and customer information.
- Rotate any credential that may have entered Git history or an uploaded artifact.

## Verification

```bash
cd backend
python -m pytest tests -q
cd ../frontend
npm ci
npm run build
```

The CI workflow runs the backend suite and frontend build. The local runtime schema helper supports incremental SQLite upgrades; it is not a substitute for a versioned migration system in production.
