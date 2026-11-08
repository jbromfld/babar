# Babar development

Babar is a reusable, local MEMORA memory service, not an application workflow.
Read README.md, docs/MEMORA.md, and docs/ARCHITECTURE.md before changes.

Use the pinned CPython 3.13.16 and uv.lock. `uv sync --locked --extra dev` installs
runtime/test dependencies. The package is `memora`; MCP is stdio-only.

Preserve fixed namespace scoping on every operation, offline pinned embeddings,
explicit revision/idempotency semantics, safe errors, and the runtime grant allowlist.
Do not introduce cloud providers, model-driven writes, or arbitrary SQL tools.
Consumers own approval policy and financial/workflow behavior.

Tests use synthetic data and refuse databases outside the `babar_test` prefix:
`uv run --no-sync pytest tests/test_memora.py -q`. Set MEMORA_TEST_DSN to an isolated
PostgreSQL database with pgvector and an admin capable of creating disposable roles.
Never run destructive tests against application databases or print runtime secrets.
