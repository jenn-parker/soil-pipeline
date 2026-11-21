# Contributing

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/) for new
commits. The release workflow uses these prefixes to determine semantic
version bumps and generate the changelog.

```text
<type>[optional scope]: <description>
```

Common types:

- `feat`: a backward-compatible feature; increases the minor version.
- `fix`: a backward-compatible bug fix; increases the patch version.
- `docs`: documentation-only changes.
- `test`: test-only changes.
- `refactor`: behavior-preserving code changes.
- `chore`: maintenance that does not change the product behavior.

Use a breaking-change footer or `!` when an existing contract changes:

```text
feat(api)!: change the batch response contract

BREAKING CHANGE: remove the legacy response field.
```

Breaking changes increase the major version. Existing commit history is not
rewritten; these conventions apply to new work.

## Validation

Before opening a pull request, run the regular test suite and frontend checks:

```bash
python -m pytest -q
cd frontend && npm run lint && npm run build
```

Changes involving PostgreSQL, PostGIS, or LocalStack should also run the
integration suite through `scripts/run_integration_tests.sh`.
