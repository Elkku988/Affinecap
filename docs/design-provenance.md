# Design provenance

`affinecap` grew out of a concrete coordination problem in Reverse Gravity, a
scientific data-processing system. That system needed to hand in-memory
authority between processing stages while rejecting stale holders and failing
closed when a transition became uncertain.

This repository does not depend on that system, and its implementation is not
a verbatim copy of a source module. The source mechanisms were entangled with
data formats, storage rules, network clients, and fixed workflow transitions.
The package is a compact generalization of the reusable design discovered by
auditing those mechanisms and their tests.

## Extraction map

| Source-system need | Reusable mechanism | Context removed | `affinecap` descendant |
| --- | --- | --- | --- |
| Give one stage temporary authority over verified in-memory data | Opaque handle backed by a private record and exact issued-object identity | Evidence formats and processing-stage names | Registry-backed `Capability` |
| Reject an earlier holder after a handoff | Atomically remove the predecessor record before creating a successor | Workflow-specific custody graph | `transfer()` and stale-alias rejection |
| Convert one kind of approved value into the next | Spend before calling transition code; never revive the predecessor after an indeterminate failure | Domain validation records and publication rules | Fail-closed `transition()` |
| Prevent inherited authority from remaining active after process creation | Process identifier and runtime-epoch binding, with child-state replacement after a fork | Network sessions and resource budgets | Process-bound handles and fork invalidation |
| Make ordinary duplication fail explicitly | Reject default standard copy, deep-copy, and pickle protocols | Source-specific wrapper classes | Uniform duplication barriers |
| Preserve useful diagnostic history across handoffs | Parent identifier, generation, operation, and application label | Durable audit artifacts and domain receipts | Immutable, registry-maintained `LineageEntry` values |

## What changed

The source system included multi-step transitions around external filesystem
effects. It could distinguish a reversible reservation from a later point
where failure had to poison a workflow. A general in-memory package cannot
infer that application-specific mutation boundary.

`affinecap` therefore uses a smaller rule: validate the callable and label,
atomically spend the predecessor, and only then invoke application code. Any
exception after the claim leaves the predecessor spent. There is no rollback,
transaction protocol, or attempt to model an application's external state.

The package also applies one documented set of copy, thread, process, and fork
rules to every public capability. The source system had multiple generations
of capability-like objects with different guarantees, so this project does not
claim that every such source object already implemented the public contract.

## What was left behind

- scientific evidence and artifact schemas;
- network providers, clients, and request budgets;
- filesystem and file-descriptor custody;
- fixed workflow sizes, stage names, and transition graphs;
- durable receipts, recovery markers, and cleanup protocols; and
- repository-specific orchestration and compatibility layers.

Those concerns matter to the system where the design originated. They are not
needed for a small, interpreter-local affine-style capability primitive.
