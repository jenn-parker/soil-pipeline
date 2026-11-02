# CSV Upload and Reconciliation Flow

The `POST /api/v1/soil-batches` endpoint coordinates CSV validation, a durable PostgreSQL intent, an S3 archive, and conditional finalization. A separate reconciliation job cleans up stale archives.

## Sequence diagram

```mermaid
sequenceDiagram
    autonumber
    participant C as API Client
    participant A as FastAPI
    participant D as PostgreSQL
    participant S as S3 / LocalStack
    participant R as Reconciliation Job

    C->>A: POST /api/v1/soil-batches (CSV)
    A->>A: Parse and validate CSV
    A->>D: Insert pending batch (generation, 2-hour lease, object key)
    D-->>A: Commit durable intent

    A->>S: PUT original CSV
    alt Archive operation reports failure
        A->>S: Attempt DELETE of archive key
        A->>D: Attempt to mark batch failed
        A-->>C: HTTP 503
    else Archive operation succeeds
        S-->>A: Archive stored
        A->>D: Lock batch row (FOR UPDATE)
        D-->>A: Current archive state and lease
        alt State, generation, or lease invalid
            A->>D: Roll back without overwriting state
            A-->>C: HTTP 409
        else Valid pending generation and lease
            A->>D: Stage soil rows and provenance changes
            A->>D: Conditional UPDATE to archived
            Note over A,D: Requires pending state, matching generation, unexpired lease
            alt Conditional UPDATE affects zero rows
                A->>D: Roll back staged changes
                A-->>C: HTTP 409
            else Conditional UPDATE succeeds
                A->>D: Commit soil data and final batch state
                alt Commit acknowledgement is uncertain
                    A->>A: Retain S3 archive; log failure
                    A-->>C: HTTP 503
                else Commit succeeds
                    A->>D: Refresh batch state
                    A-->>C: Batch result
                end
            end
        end
    end

    opt Scheduled reconciliation
        R->>S: List objects under soil-batches/
        R->>D: Check DB references and lease states
        alt Archived reference or active pending lease
            R->>R: Keep archive
        else Expired pending lease
            R->>D: Lock and refresh batch row
            R->>D: Mark abandoned and record fence metadata
            R->>D: Commit fencing decision
            R->>S: Delete only if stale and checks still permit
        else Unreferenced stale object
            R->>S: Delete after age and reference checks
        end
    end
```

## What the flow protects

1. **Durable intent before S3:** PostgreSQL records the intended object key, unique generation, and lease before the archive PUT begins.
2. **Fenced finalization:** The uploader must hold a valid lease and match the pending generation. A conditional database `UPDATE` is the final gate.
3. **Atomic database finalization:** Soil rows, provenance changes, and the batch's archived state commit together in PostgreSQL, or roll back together.
4. **Ambiguous commit handling:** If the database commit outcome is unknown, the uploader retains the S3 object instead of risking deletion of an archive referenced by a successful commit.
5. **Eventual cleanup:** The reconciler handles abandoned or unreferenced S3 objects after the configured grace period, with reference and lease checks.

## Important limitations and operational assumptions

- S3 and PostgreSQL do **not** share a distributed transaction. A late S3 PUT may leave an object that a later reconciliation pass must remove.
- The upload lease is **two hours**; uploads are expected to finish well within that window. There is no lease heartbeat in the reviewed implementation.
- Reconciliation is an **eventual** cleanup mechanism, not synchronous rollback of every external side effect.
- A successful archive finalization can have either a `completed` or `rejected` batch outcome, depending on row validation results.

See also: [[Archive State Machine]] · [[Home]]
