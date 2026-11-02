# Soil Pipeline — Architecture Diagrams

These pages explain how the Soil Pipeline coordinates PostgreSQL and S3-compatible object storage during CSV ingestion.

## Diagrams

- [[CSV Upload and Reconciliation Flow]] — sequence diagram showing the upload, fencing, failure handling, and scheduled cleanup paths.
- [[Archive State Machine]] — archive lifecycle, transition conditions, and cleanup semantics.

## Core design principle

PostgreSQL and S3 do not share an atomic transaction. The pipeline first commits a durable upload intent in PostgreSQL, then writes the original CSV to S3, and finally commits a conditional database transition. A unique archive generation, time-limited lease, row locking, and a scheduled reconciler help prevent stale workers from finalizing invalid uploads and eventually remove orphaned objects.

> **Scope:** These diagrams describe the implementation reviewed through commit [`e3d3650`](https://github.com/jenn-parker/soil-pipeline/commit/e3d3650dff1b2aab8f9a91019cb6f32fe32e4f1f). They are architectural explanations, not a guarantee that every infrastructure failure is recoverable synchronously.
