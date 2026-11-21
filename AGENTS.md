# Codex review guidance

This repository is a portfolio project, but changes should be evaluated against
production-quality engineering standards.

## Review priorities

- Treat authentication, authorization, ownership checks, token handling, and
  tenant isolation as high-risk areas. Flag bypasses, confused-deputy behavior,
  insecure defaults, and missing negative tests.
- For database changes, verify that Alembic revisions are linear, reversible
  where practical, safe for existing data, and represented in integration
  coverage. Flag model changes without a corresponding migration.
- Preserve the application's async behavior. Flag blocking I/O in async request
  paths and resource leaks involving database, HTTP, or object-storage clients.
- Check that API errors do not expose secrets, credentials, raw database details,
  or sensitive user data. Error responses should remain consistent with the
  application's request-ID and structured-logging conventions.
- Require tests for changed behavior, especially authorization failures,
  ownership boundaries, migration behavior, and error-handling branches.
- Keep infrastructure and external-service assumptions explicit. This project
  is designed to run locally without real AWS resources, so avoid introducing
  tests or application paths that require deployed AWS infrastructure.

## Review style

- Report only actionable findings supported by the diff and repository context.
- Prioritize correctness, security, data integrity, and operational regressions
  over formatting preferences.
- Include the affected file/line, why the behavior is a problem, and a concise
  remediation direction. Do not request speculative refactors.
