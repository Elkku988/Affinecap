# Reverse Gravity extraction map

The public API is small because the reusable mechanism was separated from the
scientific workflow that forced it to exist.

The audit traced the committed RG tree at `bb0564170d729931eb87f98f5285ec1039de4a52`
and separately inspected the in-progress V6 working tree without modifying it.
The central rolling capability machinery entered RG in commit
`3b73c924f6ec7c17b19152ce2903fa6a8be40067`.

| Reverse Gravity component | Actual mechanism | Domain dependency removed | Generic descendant | Executable evidence in RG |
| --- | --- | --- | --- | --- |
| Rolling full-block validated-evidence capability | Opaque shell; private registry row; nonce/PID/generation/phase; exact weak-reference handle match; copy/pickle refusal | Solana body descriptors, intent IDs, fixed acquisition roots, parser results | Registry-backed `Capability` and exact-handle claim | Forged-slot/pickle, stale reissue, concurrent disposal, cleanup/finalizer tests |
| Rolling terminal-acquisition evidence capability | Many per-body authorities atomically replaced by one aggregate authority | Fixed 66-intent acquisition, five retained directories, terminal receipt schemas | One atomic predecessor claim and one successor authority | Aggregate swap, duplicate/alias rejection, post-swap cleanup tests |
| Terminal-evidence transition holder and broker | Reserve old authority, mark external mutation, validate component proof, publish adjacent successor; restore only before mutation and poison after uncertainty | Five named RG ledger/publication edges, component proof registry, root tombstones | `transfer` and `transition`; predecessor spent before user callback; no rollback after callback starts | All-edge chain, concurrent commit, pre/post-mutation abort, fault-injection, GC, and fork tests |
| Live endpoint capability and phase handles | PID-bound state, locked phase changes, stale-phase rejection, copy/pickle barriers, poisoning on non-quiescent transition | Helius endpoint capture, request/credit/byte budgets, HTTP sessions | Process/runtime binding and fail-closed lifecycle checks | 64-thread phase, stale phase, non-quiescent poison, copy/pickle/fork tests |
| V6 source permits and qualification issuance snapshots | Selected operations require exact issued-object identity before state mutation | Eight-role capsule protocol, source fence, constructor/profile bindings | Additional evidence for checked live identity, not a direct code ancestor | Permit admission/completion and marker/subclass/field-replacement tests |

## What changed in extraction

The standalone project intentionally does not reproduce RG's multi-call
reservation API. RG needs a distinction between a reversible reservation made
before an external filesystem mutation and an irreversible, poison-on-failure
state after it. A generic library cannot infer that seam safely.

Instead, `affinecap` exposes a narrower rule: input validation happens first;
then the predecessor is atomically spent; then user code runs. Any later failure
leaves the predecessor spent. This retains the important fail-closed behavior
without pretending to provide transaction rollback.

RG's rolling evidence capability handles carry no public evidence payload; the
private registry owns it. `affinecap` preserves that structure. The
implementation is a new, small generalization rather than a verbatim copy of
RG's domain-entangled source.

Not every RG class with capability-like terminology provides these guarantees.
The audit found newer V6 handoff/session/stage wrappers that ordinary copying
can duplicate, and a validation-proof holder whose `pickle.dumps()` succeeds
even though reconstructed shells cannot pass its exact-identity registry
check. `affinecap` therefore does not attribute package-wide copy, pickle,
thread, or fork semantics to RG. Its explicit barriers and uniform process
rules consolidate and harden mechanisms that existed only in selected RG
components.

## What was discarded

- Solana, Pump.fun, PumpSwap, Helius, and Chainstack concepts;
- artifact schemas, content-addressed stores, and scientific claim rules;
- endpoint capture and network budgets;
- filesystem inode and file-descriptor custody;
- fixed cardinalities and RG-specific phase names;
- component registries, transition proof types, and pipeline orchestration;
- durable terminal markers, cleanup tombstones, and recovery protocols.

Those mechanisms remain meaningful inside RG but are not prerequisites for a
general in-memory affine-style capability.
