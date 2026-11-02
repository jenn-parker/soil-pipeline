# Soil Pipeline — Architecture Diagrams

These pages explain how the Soil Pipeline coordinates PostgreSQL and S3-compatible object storage during CSV ingestion.

## Diagrams

- [CSV Upload and Reconciliation Flow](CSV%20Upload%20and%20Reconciliation%20Flow.md) — sequence diagram showing the upload, fencing, failure handling, and scheduled cleanup paths.
- [Archive State Machine](Archive%20State%20Machine.md) — archive lifecycle, transition conditions, and cleanup semantics.

## Core design principle

PostgreSQL and S3 do not share an atomic transaction. The pipeline first commits a durable upload intent in PostgreSQL, then writes the original CSV to S3, and finally commits a conditional database transition. A unique archive generation, time-limited lease, row locking, and a scheduled reconciler help prevent stale workers from finalizing invalid uploads and eventually remove orphaned objects.

> **Scope:** These diagrams describe the current upload, fencing, and reconciliation implementation. They are architectural explanations, not a guarantee that every infrastructure failure is recoverable synchronously.
