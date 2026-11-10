# Babar

![A wise elephant recalling a glowing note from an organized archive of memories](docs/images/babar-memory.png)

Babar is a local application-memory service implementing the **MEMORA** pattern.
It stores sourced notes, retrieves relevant context, and preserves explicit
revisions across conversations and application restarts. Applications connect
through **MCP over stdio** using their own fixed namespace.

Abacus Budget advisor is one consumer: it can remember an approved intention to
reduce discretionary spending, then recall it during a later savings discussion.
Other applications can use namespaces such as `writing-assistant`, `project-planner`,
or `developer-notes`. The implemented service is the memory core; consumers supply
application workflow and authorization.

## How it works

```text
Application requests relevant context
  → local pinned embeddings + text/topic-cue matching
  → namespace-scoped PostgreSQL/pgvector search
  → bounded source notes returned to the application

Application authorizes a memory write
  → explicit create or revision-checked update
  → note + provenance + revision committed atomically
```

Similarity helps retrieval and duplicate suggestions. It **never** silently merges
or overwrites records. The application decides what to remember, when approval is
required, how much context to supply to its model, and what conclusions that context
supports. The current core does not run generative models or execute instructions
in notes.

## Place in the local stack

[Lassy](../lassy/README.md) indexes research documents and returns evidence chunks;
Babar stores bounded application notes with provenance and explicit revisions.
They can use the same PostgreSQL host but keep separate databases, credentials
and embedding identities. Babar defaults to 384-dimensional MiniLM embeddings;
Lassy defaults to 768-dimensional MPNet embeddings.

There is no automatic connection to [Lalaland](../lalaland/README.md), Lassy or
[local-mcp-server](../local-mcp-server/README.md). An application must explicitly
configure Babar as its memory consumer. Its host spawns the stdio MCP process;
there is no HTTP endpoint, Temporal/Ollama dependency, Argo workload or login
service to start. [local-agent-environment](../local-agent-environment/README.md)
provides shared runtime/model preparation and the stack's management overview.

Applications own write authorization: Abacus uses explicit user approval;
automated consumers need their own configured policy and validation. An automation
runner is not implemented here. The optional design is described in
[orchestration notes](docs/AUTOMATION.md), separate from normal setup.

## The MEMORA abstraction

| Field | Purpose |
| --- | --- |
| `primary_abstraction` | Concise concept/title |
| `primary_embedding` | Local vector for semantic retrieval |
| `memory_value` | JSONB note, application-defined type, source date, and approved source excerpt |
| `cue_anchors` | Topic tags for matching/filtering |

Records also have an application namespace, UUID, idempotent creation key,
revision, active/completed/abandoned status, and timestamps. Revisions retain
provenance; forgetting deletes the record, embedding, source excerpts, and history.
Completed/abandoned records remain inspectable but are excluded from recall.

## Quick start

Use PostgreSQL with **pgvector**, this repository's pinned CPython **3.13.16**, and
`uv`. Install dependencies:

```sh
uv sync --locked --extra dev
```

Prepare the pinned offline embedding model manually before use:
`sentence-transformers/all-MiniLM-L6-v2`, revision
`c9745ed1d9f207416be6d2e6f8de32d1f16199bf`, dimension 384. Babar never downloads
weights automatically, uses cloud embeddings, or enables remote tracing.

Provide local administrator PostgreSQL credentials through your environment
(`PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`; optional `PGDATABASE` for bootstrap).
`.env.example` documents these; no `.env` is implicitly loaded. Then provision:

```sh
uv run --no-sync python -m memora.setup \
  --config /absolute/private/memora-runtime.json \
  --namespace developer-notes
```

Setup creates the separate `babar_memory` database, versioned tables, and a
restricted managed `babar_memory` runtime role. Optional `--database` and `--user`
select another dedicated memory database/login. Generated runtime credentials are
stored only in the owner-only JSON file; they are never printed. Routine setup
preserves passwords. Use `--rotate-password` explicitly for managed-role recovery.

Run through an MCP host, or directly for protocol testing:

```sh
MEMORA_CONFIG=/absolute/private/memora-runtime.json \
  uv run --no-sync python -m memora.server
```

The server uses stdin/stdout for MCP, not a terminal chat interface or HTTP port.
Configure your host with an absolute `.venv/bin/python` executable, arguments
`["-m", "memora.server"]`, and only `MEMORA_CONFIG` plus necessary OS/offline flags.
Do not forward the host's application, administrator, cloud, or search credentials.

## Application namespaces

Each runtime JSON fixes exactly one namespace; tool callers cannot override it.
Every search, list, UUID lookup, update, and forget scopes that namespace. Multiple
application profiles can use the same memory database/model identity with different
namespaces, or separate databases/logins for stronger application separation.
Profiles are configured by their operator, not by model-generated arguments.
For example, add another trusted application's profile with a distinct managed login:

```sh
uv run --no-sync python -m memora.setup \
  --config /absolute/private/writing-memory.json --namespace writing-assistant \
  --database babar_memory --user writing_memory
```

Namespace scoping is an application boundary inside a trusted local service, not
multi-user database authorization: the runtime role has access to memory tables.
For mutually untrusted consumers, use separate databases/logins and OS isolation.
Abacus uses its own memory database/login, separate from its financial database.

The current note contract supports title, short text, application-defined kind,
source date/excerpt, topic cues, and lifecycle status. A consumer can constrain
kinds further: Abacus accepts intentions, preferences, and decisions. See the
[protocol and operations guide](docs/MEMORA.md) for limits and error semantics.

## MCP operations

- `memory_status`
- `memory_search(query, limit)`
- `memory_list(offset, limit)` and `memory_get(id)`
- `memory_create(note, create_key)`
- `memory_update(id, note, expected_revision)`
- `memory_forget(id, expected_revision)`

The service fixes namespace/model configuration and provides no arbitrary SQL,
file tools, network searches, or sampling. Hosts authorize mutations through user
approval or a configured workflow policy and treat returned memory as untrusted
context. Model output alone does not authorize a write; the core does not enforce
application evidence/approval policy on the host's behalf.
MCP itself is **not an OS sandbox**; the service runs with its OS user's access.

## Documentation and verification

- [Protocol, permissions, setup/recovery, reindexing, and backups](docs/MEMORA.md)
- [Architecture and extension boundaries](docs/ARCHITECTURE.md)
- [Optional automation, evidence gates, and CaMeL](docs/AUTOMATION.md)
- [Abacus integration](../abacus/docs/advisor-memory.md)

Synthetic PostgreSQL and real stdio tests use a dedicated database whose name
starts with `babar_test` (default `babar_test_memory`). Set `MEMORA_TEST_DSN` for
another isolated test database with that prefix. The test administrator needs
role/extension-management privileges; password-verifier tests require a superuser.

```sh
uv run --no-sync pytest tests/test_memora.py -q
```

The dependency source of truth is `pyproject.toml` and `uv.lock`. Shared runtime
provisioning is documented in [local-agent-environment](../local-agent-environment/README.md).
Linux ARM64 uses pinned CPU PyTorch wheels; macOS ARM64 uses standard macOS wheels.
