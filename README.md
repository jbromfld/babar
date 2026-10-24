# babar

A CI/CD Agentic Memory Remediation System. When a pipeline fails, this framework retrieves past solutions from a vector memory store, attempts automated remediation, and consolidates new solutions into long-term memory — getting smarter with every incident it resolves.

## How it works

```
CI/CD failure webhook
    → P-Agent searches pgvector memory for past solutions
    → Apply known fix  OR  devise new fix
    → Q-Agent validates and classifies the result (INSERT vs. UPDATE)
    → Memory committed to PostgreSQL after successful merge
```

The memory loop closes only after a human-reviewed PR merges and CI passes. A UUID correlation ID ties the proposed fix branch (`agent-remediation/fix-{uuid}`) back to the agent's pending state, triggering the final memory commit.

## Architecture

Two design patterns drive this system:

**MEMORA** — every memory is stored as four fields:
- `primary_abstraction` — generalized error label (e.g. `"NPM Dependency Conflict"`)
- `primary_embedding` — vector of that label for similarity search
- `memory_value` — JSONB remediation steps
- `cue_anchors` — metadata tags for fast filtering (e.g. `["repo:frontend", "stage:build"]`)

**CaMeL** (dual-LLM) — separates concerns between two agents:
- **P-Agent (Privileged)** (ReAct, Anthropic) — orchestrates the full flow: search, fix, commit
- **Q-Agent (Quarantined)** (structured output, Anthropic) — sandboxed judge that returns `{"action": "INSERT"|"UPDATE", "merged_content": "..."}`

## Quick start

```bash
uv sync --locked --extra dev
source .venv/bin/activate
cp .env.example .env        # fill in DB credentials, API keys, model names
python memory/migrate.py    # creates agent_memory table with correct VECTOR(N) column
```

## Configuration

All runtime config is in `.env`. Key variables:

| Variable | Default | Notes |
|---|---|---|
| `DB_HOST/PORT/NAME/USER/PASSWORD` | `localhost:5432` | PostgreSQL connection |
| `EMBEDDING_PROVIDER` | `local` | `local` (MiniLM) or `openai` |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Must match `EMBEDDING_DIM` |
| `EMBEDDING_DIM` | `384` | Must match model output and schema column |
| `MEMORY_SIMILARITY_THRESHOLD` | `0.80` | Cosine similarity cutoff for memory upsert |
| `P_AGENT_MODEL` | `claude-sonnet-4-6` | P-Agent LLM |
| `Q_AGENT_MODEL` | `claude-haiku-4-5-20251001` | Q-Agent LLM |
| `LANGCHAIN_TRACING_V2` | `false` | Set to `true` to enable LangSmith tracing |

See `.env.example` for the full list with comments.

## Local simulation

The agent entrypoints are not yet built. The planned local test harness (from `ARCHITECTURE.md`) uses:
- `mock_ci.py` — simulates a build; writes to `error.log` on failure, `success.log` on pass
- `agent_flow.py` — LangGraph app watching `error.log`; outputs a `.patch` file for human review
- Human applies the patch, reruns `mock_ci.py`, and the agent completes the memory commit on success

## Stack

- **PostgreSQL + pgvector** — vector similarity store
- **LangChain / LangGraph** — agent orchestration
- **sentence-transformers** — local embeddings (default)
- **Anthropic Claude** — P-Agent and Q-Agent LLMs (default)
- **LangSmith** — tracing (opt-in via `.env`)

## Standardized environment

Use CPython **3.13.16** and `uv sync --locked` for this repository. The dependency
source of truth is `pyproject.toml` plus committed `uv.lock`. Use
`uv sync --locked --extra dev` when development extras are needed (where defined).
Shared Ansible provisioning and runtime version checks are documented in [local-agent-environment](../local-agent-environment/README.md).
Its `.tools/bin/uv` provides the pinned uv version independently of PATH.

Set `EMBEDDING_MODEL_REVISION` to pin the local model's Hugging Face commit.
Preserve the model and dimension when adopting existing embeddings; changing
weights requires an explicit re-embedding migration.

Linux ARM64 uses the explicit PyTorch CPU wheel index; CUDA dependencies are
excluded from this environment. macOS ARM64 uses the regular macOS wheel.
