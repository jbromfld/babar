# Babar architecture

Babar implements reusable, local MEMORA storage over MCP. Application workflow and
approval policy belong to consumers; namespace filtering, validation, persistence,
semantic retrieval, provenance, and revisions belong to Babar.

`memora.config` loads an explicit owner-only runtime profile. A profile fixes local
PostgreSQL credentials, namespace, and pinned embedding identity. The service does
not inherit application/admin credentials or implicitly read dotenv files.
`memora.embedding` lazily loads offline sentence-transformer weights.
`memora.store` validates and parameterizes namespace-scoped operations, uses pgvector
plus lexical/cue signals, and manages revisions/idempotency atomically.
`memora.server` exposes that core through stdio MCP with redacted errors.

Provisioning and reindexing are explicit administrator operations outside runtime.
Schema/model metadata is versioned; runtime rejects incompatible identities or
schema versions. Runtime owns no objects and has an explicit table grant allowlist.
A failed reindex rolls back embeddings and identity together.

A namespace is fixed per server profile, never accepted from a tool argument.
Several trusted local applications may share a database/model with different
namespaces. This is query scoping, not SQL-level tenant authorization. Independent
databases/logins and OS isolation are needed between untrusted consumers.

The note kind is application-defined. Hosts may enforce smaller schemas, context
budgets, confirmation flows, and interpretations; Babar does not infer that an
intention happened, alter application records, run an agent loop, or merge similar
records automatically. Additional transports and consumers should reuse the core
and keep their capabilities out of the storage layer.

## Optional orchestration above the core

The current service implements storage/retrieval only. The architecture permits
three layers with separate responsibilities:

| Layer | Responsibility |
| --- | --- |
| MEMORA core | Namespaces, retrieval, schema validation, provenance, idempotency, revisions, atomic writes |
| Optional automation runner | Candidate extraction, applicability decisions, evidence gates, review/retry handling, authorized MCP calls |
| Application policy | Trusted triggers, acceptable outcomes, permitted operations, and when human approval is required |

Abacus uses user approval. Other consumers may use preconfigured automation policies
that authorize persistence only after a verified outcome. The core does not enforce
those application policies: valid MCP creates/updates are applied immediately.
An automation runner, pending-review state, and P/Q orchestration are not currently
implemented and must not be inferred from the existing MCP interface.

For bounded workflows, deterministic orchestration and an isolated structured-data
extractor can be sufficient. Broader agents may need CaMeL-style separation of
privileged planning, quarantined data processing, and a runtime that enforces
provenance/capability policies. Two models alone do not provide that boundary;
execution security also does not establish memory quality or factual correctness.
See [optional orchestration](AUTOMATION.md) for the proposed flow, applicability
rules, CaMeL references, and verification requirements.
