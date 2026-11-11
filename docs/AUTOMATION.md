# Optional orchestration for automated memory

Babar's implemented service is the MEMORA storage/retrieval core. It supports both
human-approved and policy-authorized consumers through the same MCP operations.
An optional deterministic dreaming controller now supplies source-bound proposals,
conservative consolidation policy and atomic commit/recovery through MCP. Consumers
supply scheduling and tool-free model adapters. General automation runners, P/Q
LLMs and CaMeL interpreters remain architectural extensions.
The earlier CI-specific prototype was scaffolding, not a working CaMeL engine.

## Responsibilities

| Layer | Responsibility | Current status |
| --- | --- | --- |
| MEMORA core | Namespace-scoped retrieval, schema validation, provenance, idempotent creates, explicit revisions, and atomic writes | Implemented |
| Optional dreaming controller | Bind candidates, evaluate proposals, revalidate policy/revisions, and commit atomically | Implemented; see [dreaming](DREAMING.md) |
| General automation runner | Interpret external events and authoritative outcome evidence | Extension design |
| Application policy | Define trusted events, acceptable evidence, allowed actions, and review requirements | Supplied by each consumer |

Abacus uses explicit user approval: a local model drafts a note, the user reviews
it, and the application requests persistence. Its model cannot call memory tools.
An automated consumer can instead authorize narrowly defined writes through an
operator-configured workflow policy. Both approaches keep application decisions
outside the storage layer and preserve application namespaces.

The core validates note fields, namespace scoping, creation keys, and revisions.
It does not verify that a deployment succeeded, a source is authoritative, a user
accepted a recommendation, or a workflow is entitled to remember a claim. A
schema-valid MCP write is applied immediately; callers must enforce authorization
before invoking it. The ordinary write API has no pending-approval queue. The optional dreaming
controller persists bounded review proposals separately.

## A bounded automated workflow

For a predefined workflow, start with deterministic control flow and use a model
only where unstructured evidence needs extraction:

```text
Trusted workflow event
  → retrieve related memories
  → extract a structured candidate from supporting evidence
  → evaluate application policy and outcome evidence
  → ignore / create / revise / request review
  → invoke an authorized MEMORA operation
```

A runner should apply these rules:

- **Trusted trigger and evidence:** accept authenticated workflow events and verify
  outcomes against the authoritative system. Text in a log saying “success” does
  not establish that a change merged or checks passed.
- **Isolated extraction:** give an extraction model only the evidence it needs,
  without credentials or tool access. Treat its structured output as untrusted;
  validate fields, supporting references, and application constraints in code.
- **Explicit applicability:** ignore transient chatter, unsupported claims, and
  unchanged knowledge. Ask for review when applicability or evidence is ambiguous.
  A model's confidence score alone cannot authorize persistence.
- **Controlled record selection:** similarity suggests related records; it never
  authorizes overwriting one. Revisions require a policy-approved target record
  and the revision inspected. Conflicting facts go to review rather than being
  resolved by forcing an update or creating an accidental duplicate.
- **Reliable commits:** derive a stable creation UUID from the namespace, workflow,
  source event, and candidate identity. Retry an identical create with the same key.
  Preserve the expected revision on update retries; a conflict requires a fresh
  decision, not an unconditional overwrite.
- **Narrow capabilities:** fix the namespace and permitted operations in trusted
  configuration. Automatic creation/revision does not imply permission to forget
  memories, change configuration, or act in another application.
- **Audit and failure handling:** retain event identity, evidence references, policy
  version, decision, and commit result in the runner's workflow/audit state. Keep
  private evidence out of general logs. Missing evidence or extraction/validation
  failures produce no write. Reconcile uncertain commit outcomes through existing
  creation keys/revisions before deciding what to do next.

These are requirements for a future runner, not additional fields or endpoints in
current MEMORA. Existing notes retain their bounded source date/excerpt; a runner
must manage any richer evidence, approval, and audit state separately.

Examples include remembering a runbook procedure after a verified successful run,
retaining document facts only after checking an approved source, or learning a
remediation after a merged change and passing checks. The application defines the
required evidence; a CI workflow is one consumer, not Babar's organizing model.
For Abacus, a stated intention to cut spending remains an intention until supported
by fresh financial evidence, and it never directly changes budget calculations.

## When CaMeL applies

Memory applicability and execution security are separate concerns. A classifier or
reviewer can help decide whether a candidate is useful, but that decision alone
does not contain prompt injection or prove a claim is true.

CaMeL separates privileged planning from untrusted data processing and enforces
information-flow policies in an execution layer. Its components include:

- A **privileged model (P-LLM)** plans from the trusted task and permitted APIs,
  without receiving raw untrusted tool results or the quarantined model's output
  as planning instructions.
- A **quarantined model (Q-LLM)** processes untrusted material into a predefined
  structure and has no tool access. Structured output still needs validation and
  does not become authoritative merely because it matches a schema.
- A **controlled runtime** tracks data provenance/capabilities and checks policies
  when tools are called. It prevents untrusted data from acquiring authority over
  the plan or unauthorized destinations.

This describes the research architecture, not security guarantees implemented by
Babar. See the [CaMeL paper](https://arxiv.org/abs/2503.18813) and
[reference implementation](https://github.com/google-research/camel-prompt-injection).
A proposer and a second model acting as an approval judge are not, by themselves,
a CaMeL implementation. Neither MCP nor a prompt saying “read-only” supplies that
execution boundary.

A deterministic workflow with an isolated extractor is a smaller starting point
for bounded automation. A broader agent that plans tool use while processing
untrusted documents, logs, or retrieved memories may justify a fuller CaMeL-style
runtime. Such an integration would remain optional and separate from the MEMORA
core. Its applicability/evidence rules are still necessary: CaMeL's execution
security does not decide which lessons deserve to become long-term memory.

## Extension and verification boundaries

An automation runner should be independently configurable so manual consumers do
not acquire agent dependencies, extra model calls, or automatic write behavior.
Abacus keeps its existing approval flow. A future runner should reuse the core's
MCP operations rather than introduce direct SQL writes or hidden similarity merges.

Before enabling automatic persistence, test verified/failed outcomes, irrelevant
and conflicting candidates, duplicate event delivery, retries after lost responses,
revision conflicts, and review escalation. Include hostile source text attempting
to change the namespace, target a different record, invent an outcome, delete
history, or disclose private data. Verify denied actions leave memory unchanged
and that no model receives credentials or capabilities outside its configured role.

The [future-state README](future-state/README.md) distinguishes the implemented
controller boundary from stronger isolation and agent enhancements.
