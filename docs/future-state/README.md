# Future state: optional memory automation

Babar is a memory service that applications can choose to use. Ordinary memory
requires no dreaming, generative model, agent, scheduler, or cloud account. An
application must remain useful when memory is disabled or unavailable. Consumers
can use ordinary notes indefinitely without enabling automation.

## Implemented boundary

The optional `dreaming-controller-v1` workflow is deterministic application code:

```text
Consumer authorizes and schedules a bounded pass
  → Babar selects and snapshots sources, returning proposal handles
  → consumer model adapter executes Babar's bounded request without tools
  → Babar evaluates untrusted output against its stored sources and policy
  → automatic eligible merge OR consumer presents review
  → Babar rechecks sources/policy and atomically commits
```

Babar owns source binding, proposal state, policy versions and storage invariants.
Consumers own enablement, model selection, scheduling, approvals and presentation.
Abacus is one consumer; none of Babar's controller code imports Abacus. Model
adapters receive messages and an output schema, never database credentials or a
memory client. Babar itself does not call a generative model.

This is an **application interface boundary**, not operating-system isolation. The
consumer process holds its own credentials, and its trusted adapter can call its
configured model transport. A compromised application, administrator or database
is outside this protection. Existing direct write/consolidation tools remain
trusted consumer operations and are not restricted by the optional controller.

Schema validation does not establish truth. Compatibility heuristics can miss
contradictions; review can also be mistaken. Source text, model summaries and
retained evidence remain untrusted after consolidation or approval. Automatic
summaries preserve original wording; they do not verify intentions or outcomes.
The current design has no privileged LLM and is not a CaMeL implementation.

## Possible enhancements

These are proposals, not installed features or commitments.

| Enhancement | When it helps | Cost and limitations |
| --- | --- | --- |
| Credential-free generation worker | Adapters grow beyond a simple model call or process-level containment is required | A separate process needs a bounded protocol, lifecycle/recovery management and explicit environment isolation. It still needs access to the selected model endpoint. |
| Operating-system restrictions | A worker must be unable to read files, open arbitrary connections or spawn programs | Platform-specific sandbox and deployment work. A second prompt or process alone does not enforce these restrictions. |
| Capability-scoped controller access | Automated clients should be unable to bypass review through ordinary write tools | Separate principals/tool allowlists or authenticated capabilities, permission migration and compatibility work. Current runtime credentials are not this boundary. |
| Stronger evidence validation | More varied facts, constraints, currencies and lifecycle claims require reliable checks | Domain-supplied typed evidence and deterministic validators. Neither similarity nor a model confidence score proves semantic compatibility. |
| Independent critique model | Additional contradiction or omission detection improves review quality | Extra latency and inference cost; correlated failures remain. A critique model should have no tools and cannot authorize writes. |
| Broader candidate grouping | Recent disjoint pairs miss useful relationships in larger histories | Retrieval/index tuning, bounded groups, nested-lineage handling and performance evaluation. Similarity remains a suggestion. |
| Adversarial evaluation corpus | Policies, prompts or model providers change | Maintain synthetic hostile notes, misleading decisions and conflicting dated evidence; track false merges and missed merges. Passing a finite corpus is not a security proof. |
| Privileged planner and information-flow runtime | Future workflows need dynamic planning and multiple powerful tools | Keep untrusted content and generated prose away from privileged planning; use opaque references and enforced capability/provenance policies. Consider CaMeL-style designs only with explicit threat models and dedicated testing. |
| Independent background service | Multiple consumers need shared scheduling independent of application uptime | Authentication, service operations, leases, cancellation and model contention become necessary. The current stdio service has no independent scheduler. |

Adopt additional machinery only when a concrete use case justifies its operational
cost. Preserve all three modes: no memory, ordinary memory, and optional dreaming.

See [current dreaming contracts](../DREAMING.md) and
[broader automation design](../AUTOMATION.md).
