# Optional memory dreaming

Babar supplies atomic storage operations. A consumer runs its own model and
explicitly authorizes each consolidation. Abacus implements an opt-in idle worker;
Babar itself has no scheduler, Ollama integration, cloud calls, or agent loop.

Setup upgrades existing version-1 databases transactionally to version 2, adding
`superseded_by` and `memora_consolidations`, and refreshes the runtime grant
allowlist. Existing notes, creation keys, embeddings and revisions remain intact.
Old consumers can continue ordinary operations after setup; consumers must check
`memory_status.capabilities` for `dreaming-v1` before consolidation.

`memory_dream_candidates(limit=5)` compares at most 200 recently updated active
notes in the fixed namespace. It returns disjoint pairs with matching kinds and
cosine distance below 0.3. Similarity only proposes candidates. Consolidation
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
