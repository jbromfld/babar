# Optional memory dreaming

Babar supplies atomic storage operations. A consumer runs its own model and
explicitly authorizes each consolidation. Abacus implements an opt-in idle worker;
Babar itself has no scheduler, Ollama integration, cloud calls, or agent loop.

Setup upgrades existing version-1 or version-2 databases transactionally to version 3, adding
`superseded_by`, `memora_consolidations` and `memora_dreams`, and refreshes the runtime grant
allowlist. Existing notes, creation keys, embeddings and revisions remain intact.
Old consumers can continue ordinary operations after setup; consumers must check
`memory_status.capabilities` for `dreaming-v1` before consolidation.

`memory_dream_candidates(limit=5)` compares at most 200 recently updated active
notes in the fixed namespace. It returns disjoint pairs with matching kinds and
cosine distance below 0.32 (similarity above 0.68). Similarity only proposes candidates. Consolidation
accepts two to five sources, each `{id,revision}`, one validated note, and a UUID
operation key. Source kinds must match and the canonical source date is the
earliest source date; individual dates remain in retained source snapshots.

The service locks the namespace operation gate and source rows in stable order,
checks every source revision and availability, then inserts the canonical memory,
source revisions and operation evidence in one transaction. Exact retries return
the original result; changed requests conflict. `memory_consolidation_status`
reconciles lost replies. Original create keys remain reserved. Superseded inputs
are excluded from recall and cannot be edited; list/get retain them for inspection.

`memory_get` on a canonical record returns consolidation evidence and the operation
key. Search marks canonical results with `is_consolidated`; consumers can retrieve
dated source details within their context budgets. Undo restores the immediate
sources and abandons the generated record only while its result and inputs are
unchanged. Editing the result or merging it again makes automatic undo conflict.

Ordinary forget refuses a member of a consolidated family. Explicit
`memory_forget_consolidation(id,expected_revision)` deletes the connected family,
including prior/nested/undone consolidations, source records, revision history,
embeddings, request documents and retained snapshots atomically. Consumers must
clearly confirm family-wide forgetting and purge their own pending drafts/jobs.
Database backups can still retain forgotten information.

Memory content remains untrusted. These operations do not evaluate claim truth,
resolve semantic contradictions, or establish consumer authorization. No returned
note can choose another namespace or execute tools. Tests use only `babar_test*`
databases and synthetic evidence.

## Optional controller workflow (schema 3)

Setup now upgrades schema 1 or 2 transactionally to schema 3, adding
`memora_dreams` and its runtime grants. Ordinary tools retain their signatures;
no model provider, background service or additional model configuration is needed.
Check `memory_status.capabilities` for `dreaming-controller-v1` separately from
`dreaming-v1`, which advertises only the original storage primitives.

| Tool | Contract |
| --- | --- |
| `memory_dream_prepare(pass_key)` | Explicit opt-in trigger; UUID pass key makes preparation retryable. Returns at most five disjoint groups of two sources. Already considered source revisions are skipped unless cancelled. |
| `memory_dream_get(operation_key)` | Namespace-bound proposal/review state. A prepared proposal includes Babar-owned `model_request.messages` and `model_request.schema`; only these go to the consumer's tool-free model adapter. Committed/undone operations are distinguished. |
| `memory_dream_evaluate(operation_key, raw)` | Accepts up to 64 KiB of UTF-8 JSON; forbids extra fields, duplicate/foreign source references and diagnostic strings over 1,000 characters. Stores a `ready` or `review` decision. Invalid output performs no write. |
| `memory_dream_commit(operation_key, reviewed=false, note=null)` | Rechecks policy version, state, source revisions, kind, lifecycle and earliest date. Automatic content is rebuilt from originals; `reviewed=true` represents trusted consumer authorization and permits an edited note within storage invariants. |
| `memory_dream_cancel(operation_key)` | Cancels uncommitted work and removes its content. Cannot undo an already committed operation. |

Consumers keep scheduling references, not private proposal snapshots. Babar
persists controller-owned source IDs/revisions, evidence, policy version and
operation identity. Writes and controller state commit in one transaction using
the same namespace lock and stable source-row ordering. Retry a lost commit by
reading the same handle, not by creating a replacement operation. Cancellation
and commit serialize; cancellation that wins prevents all subsequent commits.
After a commit has won, undo is a separate explicitly authorized operation.

Automatic merges retain distinct original texts within 400 characters. Model
compatibility is necessary but insufficient: differing numeric values, monetary
units, named periods or constraints, questions/missing evidence and existing
families require review. These checks are conservative heuristics, not semantic
proof. Revisions are rechecked even after review; refresh changed sources through
a new preparation rather than overriding their expected revisions.

Normal forgetting deletes pending controller records containing the forgotten
source; family forgetting deletes controller records referencing any family
member. This includes generated summaries and diagnostics. Committed proposals
remove temporary evidence/model output; the storage lineage owns dated evidence.
Backups can still contain previous copies.

A consumer can disable dreaming without disabling ordinary memory. It must stop
new generation/commit requests, cancel pending handles, and retry cancellation
when Babar reconnects. Disabling memory must stop all Babar requests. No Babar
scheduler continues work after a consumer stops issuing calls. Consumers without
the controller capability can continue normal memory and explicitly authorized
storage operations. Direct `memory_consolidate` remains such a trusted primitive;
it does not certify that the controller reviewed the request.

The quarantine is an interface boundary, not an OS sandbox. Model text is always
untrusted, including after consolidation. See the
[future-state README](future-state/README.md) for stronger isolation and possible
agent designs.
