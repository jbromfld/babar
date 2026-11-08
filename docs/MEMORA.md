# Memora: approved local application memory

Babar supplies a general-purpose, local MEMORA store over MCP. Applications own
approval policy, note semantics, and how recalled context is used. They connect
with a fixed application namespace, using the same protocol and memory core.

## Runtime and provisioning

Use this repository's pinned Python and `uv sync --locked --extra dev`.
PostgreSQL must have pgvector installed. Runtime uses only a dedicated local
memory database/login and an owner-only JSON file. No cloud fallback or model
installation occurs. Default offline model: `sentence-transformers/all-MiniLM-L6-v2`,
revision `c9745ed1d9f207416be6d2e6f8de32d1f16199bf`, dimension 384. Explicitly
acquire that exact model revision beforehand if it is not already cached.
`local_files_only=True`, offline environment flags, pinned revision, and disabled
remote code/telemetry apply when loading it. Changing weights/revision/dimension
requires explicit reindexing; runtime validates persisted model/schema identity.

For Abacus use its `scripts/setup_memory.py`; it provisions with the existing
local admin connection and writes runtime paths to Abacus without enabling memory.
For another local consumer, supply administrator `PGHOST`, `PGPORT`, `PGUSER`, and
`PGPASSWORD` through an owner-only environment or interactive tooling, then:

```sh
uv run --no-sync python -m memora.setup --config /absolute/private/memora-runtime.json --namespace my-app
# Optional: --database ANOTHER_MEMORY_DB --user ANOTHER_MEMORY_ROLE
MEMORA_CONFIG=/absolute/private/memora-runtime.json uv run --no-sync python -m memora.server
```

The server is stdio-only: stdout contains only MCP messages. Normal clients spawn
it lazily and keep it alive; there is no web port/cron/launch service to install.
It reads only the explicitly named runtime JSON, never Babar's `.env`.
The JSON contains host, port, database, user, password, fixed namespace, model,
revision, and dimension; namespace is required and has no application-specific default. To configure a
separate consumer, use a separate database/runtime login and set its namespace
before use. Never point CI clients at Abacus's private memory configuration.

Setup creates versioned Memora tables, maintains an explicit runtime grant list,
refuses unrelated/owning/member roles, and preserves routine passwords. Runtime
has CRUD only on `memora_notes`/`memora_revisions` and SELECT only on model and
migration metadata. Admin ownership stays outside the runtime. No automatic
future-table grants or PUBLIC privilege changes occur. Generated passwords enter
DDL as SCRAM verifiers, not plaintext. Runtime JSON writes are atomic with mode
0600; no credentials or password-bearing commands are printed. If a managed
role's credentials are missing or unusable, repeat setup with `--rotate-password`.
Role management markers bind to a database OID; a restored different database
needs a newly provisioned runtime role. Keep runtime files and dumps out of Git.

## Contract and semantics

Tools: `memory_status`, `memory_search(query,limit)`, `memory_list(offset,limit)`,
`memory_get(id)`, `memory_create(note,create_key)`,
`memory_update(id,note,expected_revision)`, and `memory_forget(id,expected_revision)`.
They return `{ok:true,data}` or safe `{ok:false,code,message}` envelopes. Backend
hosts decide when tools run; Abacus does not expose them to its chat model.

A note contains title (1–100), text (1–400), kind
(an application-defined lowercase type such as `intention`, `fact`, or `procedure`), ISO source date, approved source excerpt (up to
1,000), up to eight topic cues (each 1–50), and active/completed/abandoned status.
The store retains the MEMORA abstraction/vector/JSON/cue structure and adds UUID,
namespace, creation key, revisions, status, and timestamps. Every operation scopes
the server-fixed namespace, including UUID access; no tool accepts a namespace.

Semantic similarity plus text/cue signals ranks candidates deterministically.
Similarity never triggers updates or merges. Active notes alone enter recall;
completed/abandoned notes remain listed. Explicit updates require the inspected
revision and append history. Repeating an identical create key is idempotent;
changing its content conflicts. Forgetting atomically deletes the note, embedding,
source excerpts, and all revisions through cascading foreign keys.

This store does not assert goals were achieved, change financial records, archive
whole conversations, or execute instructions embedded in memory. The host supplies
user review/approval and treats recalled text as untrusted data. MCP itself is not
an OS sandbox: the child has its OS user's file/network access. Restricted database
permissions do not protect against a compromised OS/backend. Standard tool errors
are redacted; hosts should not forward private stderr/transport payloads to logs.

## Reindex and backups

Stop/disable clients, back up the memory database/runtime configuration, and edit
model/revision/dimension in the owner-only JSON. With separate admin PG credentials:

```sh
MEMORA_CONFIG=/absolute/private/memora-runtime.json uv run --no-sync python -m memora.reindex
```

Reindex holds an exclusive table lock, builds replacement vectors, then swaps the
column/index and model identity in one transaction. Failure rolls back to the
previous embeddings. No note revisions/source history change. Until successful,
runtime rejects mismatched identities rather than mixing vector spaces. If several
namespace profiles share a database, update every profile to the same identity
before restarting those clients.

Back up this database separately using `pg_dump -Fc`, and preserve model identity
and the matching offline cache. Restore using `pg_restore --no-owner --no-acl`
into a new empty database and provision its own managed login. Older backups can
retain forgotten notes; deletion does not erase independently retained dumps.

## Verification

Tests contain synthetic notes/model vectors only and refuse a database whose name
does not start with `babar_test`. Set `MEMORA_TEST_DSN` to the dedicated test
PostgreSQL database; default is `host=localhost dbname=babar_test_memory`.
Use a local admin capable of creating disposable roles and installing pgvector.

```sh
uv run --no-sync pytest tests/test_memora.py -q
```

They cover later recall, unrelated questions, namespaces, explicit revisions,
idempotency, completion/abandonment, forgetting, real stdio protocol with PostgreSQL,
permission denials, safe errors, pagination, model/config identity, and atomic
reindex failure/recovery. Offline model readiness can be checked separately with
`memory_status`; it does not read budget records or download model files.
