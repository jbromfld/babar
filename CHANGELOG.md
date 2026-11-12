# Changelog

## [0.3.0] — 2026-11-11

### Added

- Explicit operator-configured PostgreSQL endpoints with libpq TLS certificate
  fields and bounded connection timeouts. Existing loopback profiles remain valid.
- Shared administrator transport policy for setup/reindex and pre-provisioned
  schema/grant maintenance without database/role creation or password rotation.
- Optional `include_superseded=false` for current-note listing before pagination;
  the default listing retains historical sources for compatibility and Undo.
- Documentation for consumer-owned, pinned Linux container runtimes with private
  profiles and read-only offline model caches.

### Changed

- Dreaming candidate similarity threshold is now above **0.68** (cosine distance
  below 0.32). Candidate selection still grants no authority to consolidate.
- Distribution and lockfile version advance to 0.3.0. Database schema remains
  **3**; this release requires no schema migration or re-embedding from 0.2.0.

## [0.2.0](https://github.com/jbromfld/babar/compare/v0.1.0...v0.2.0)

This release adds explicit memory consolidation with retained source evidence and
an optional deterministic dreaming controller. Consumers continue to own write
authorization, scheduling, and model execution.

### Added

- Consolidation tools: `memory_dream_candidates`, `memory_consolidate`,
  `memory_consolidation_status`, `memory_undo_consolidation`, and
  `memory_forget_consolidation`.
- Bounded candidate selection from up to 200 recently updated active notes,
  returning up to five disjoint pairs of similar notes with matching kinds.
  Similarity proposes candidates; it does not authorize a merge.
- Atomic consolidation of two to five revision-checked sources into a canonical
  note, retaining source snapshots, dated provenance, and revision history.
  Operation keys support idempotent retries and recovery after a lost reply.
- Conditional undo that restores immediate sources while the canonical result
  and its inputs remain unchanged, plus explicit forgetting of an entire
  connected consolidation family, including nested and undone operations.
- Optional controller tools: `memory_dream_prepare`, `memory_dream_get`,
  `memory_dream_evaluate`, `memory_dream_commit`, and `memory_dream_cancel`.
  Babar persists source-bound proposal handles, review state, and policy versions;
  consumers execute the bounded model request through their own tool-free adapter.
- Conservative consolidation checks for conflicting amounts, currencies, periods,
  constraints, questions, missing evidence, and existing consolidation families.
  Automatic commits preserve distinct original texts within the note limit;
  cases requiring review need explicit consumer authorization.
- Commit-time source and policy revalidation, serialized commit/cancel operations,
  and cleanup of pending proposal evidence when source notes are forgotten.
- Synthetic PostgreSQL tests covering migration from populated schema versions 1
  and 2, consolidation lineage, retries, namespace boundaries, concurrent writes,
  undo/forget behavior, malformed or hostile model output, and review enforcement.
- [Dreaming contracts](https://github.com/jbromfld/babar/blob/v0.2.0/docs/DREAMING.md)
  and [future-state designs](https://github.com/jbromfld/babar/blob/v0.2.0/docs/future-state/README.md),
  with updated automation boundaries and README artwork.

### Changed

- Database schema advances from version **1** to **3**, adding `superseded_by`,
  `memora_consolidations`, and `memora_dreams`. Setup upgrades existing schemas
  transactionally and refreshes the runtime grant allowlist.
- `memory_status` now advertises `dreaming-v1` and `dreaming-controller-v1`.
- Note responses include `is_consolidated` and `superseded_by` fields;
  `memory_get` also returns consolidation evidence and an operation key when
  applicable. Search marks canonical consolidated results.
- Superseded sources remain inspectable but are excluded from recall and cannot
  be updated. Their original creation keys remain reserved for idempotency.
- Ordinary `memory_forget` refuses consolidation-family members. Consumers must
  explicitly authorize `memory_forget_consolidation` to delete the connected
  family and its retained evidence. Independently retained backups are unaffected.

### Upgrading from 0.1.0

1. Stop or disable affected MCP integrations and back up the memory database and
   private runtime profiles.
2. Install the new release and its locked dependencies with `uv sync --locked`
   from the checkout; add `--extra dev` when development tools are needed.
3. With administrator PostgreSQL credentials, rerun setup for each existing
   runtime profile, keeping its namespace:

   ```sh
   uv run --no-sync babar-setup \
     --config /absolute/private/project-memory.json \
     --namespace project-planner
   ```

4. Restart/reconnect the consumers and call `memory_status`. Check `dreaming-v1`
   before using consolidation primitives and `dreaming-controller-v1` before
   using controller tools.

Schema migration is required even when dreaming is disabled: the new runtime
requires schema version 3. Setup preserves existing notes, embeddings, revisions,
creation keys, and routine passwords. This release does not change the pinned
embedding model, so upgrading alone requires no reindex.

Ordinary memory tool signatures remain unchanged. Consumers can continue using
ordinary notes without enabling dreaming. Babar adds no scheduler, generative
model provider, or background agent; the controller's checks do not establish
semantic truth or provide an OS sandbox. See the
[release dreaming guide](https://github.com/jbromfld/babar/blob/v0.2.0/docs/DREAMING.md)
for integration and retention details.

### Included pull requests

- [#4 — Add dreaming feature](https://github.com/jbromfld/babar/pull/4)
- [#5 — Update package version to 0.2.0](https://github.com/jbromfld/babar/pull/5)
- [#7 — Add the optional controller and future-state documentation](https://github.com/jbromfld/babar/pull/7)
