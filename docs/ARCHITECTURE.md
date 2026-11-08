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
