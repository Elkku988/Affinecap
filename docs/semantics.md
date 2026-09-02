# Semantic contract

`affinecap` provides process-local, affine-style handles for Python values. A
handle is an ordinary Python object, but the value and the authority to claim
its release through this library live in a private runtime registry. The
registry accepts only the exact handle object that it issued.

The library is a runtime coordination primitive. It is not a Python type-system
extension, a sandbox, or a durable transaction manager.

## Operations

```python
cap = issue(value, label="approved")
result = cap.consume(consumer)
```

- `issue(value)` creates one live capability.
- `consume(consumer)` atomically spends the capability, then invokes
  `consumer(value)` in the winning call's current execution path.
- `transfer()` atomically spends the old handle and returns a new handle for
  the same value.
- `transition(transform)` atomically spends the old handle, invokes
  `transform(value)`, and, if it returns, issues a new handle for the returned
  value.
- `lineage` returns immutable, registry-backed ancestry for a live handle.

The callable and label arguments are checked before a claim. Once a valid
operation claims a capability, there is no rollback. If user code raises any
`BaseException`, or successor creation fails, the old capability remains spent
and no usable successor is returned.

## Enforced invariants

Under the assumptions below, the implementation enforces:

1. **At-most-once library claim.** At most one `consume`, `transfer`, or
   `transition` call can successfully claim a capability. This says nothing
   about how many times the winning callback uses the released payload.
2. **Stale-holder rejection.** After a claim, every alias of the old handle is
   unusable.
3. **Exact-handle custody.** Reconstructing an object with the same visible or
   private field values does not recreate authority; the live registry entry
   also binds the exact issued object identity.
4. **Thread linearization.** A lock protects the claim. Simultaneous contenders
   have at most one winner, and the user callback runs outside the registry
   lock.
5. **Reentrancy rejection.** The handle is spent before user code runs, so a
   callback cannot reenter through the same handle.
6. **Standard duplication barriers.** `copy.copy`, `copy.deepcopy`, and the
   standard pickle protocols are rejected explicitly.
7. **Process binding.** A handle is valid only in its issuing process/runtime
   epoch. A forked child removes inherited records from the active registry;
   inherited handles fail, while newly issued child handles use a new epoch.
8. **Successor ancestry.** Transfer and transition successors have a newly
   generated random 128-bit public ID, an incremented generation, and an
   immutable lineage entry that names the parent ID and operation. Global ID
   uniqueness is probabilistic, not an authority invariant.
9. **Fail-closed callback boundary.** The claim precedes the callback. An
   exception or partial side effect cannot make the old handle live again.

These are runtime properties of library-mediated operations. “Exactly once” is
not claimed: a callback can perform a partial external side effect and then
raise, the process can crash, callback code can fork into two continuing
processes, or an external system can independently repeat an operation.

## Assumptions

The guarantees apply to normal Python code that uses the public API and does
not deliberately mutate or replace `affinecap` internals. The process,
interpreter, imported module, and standard synchronization primitives are
trusted. Native extensions are assumed not to corrupt Python memory.

Possession of a capability is necessary to ask this library to release its
registered value. The library does not decide who is entitled to call `issue`;
an application must place issuance behind its own trusted validation boundary.

## Deliberate limits

- Python reflection, monkeypatching, a debugger, `ctypes`, unsafe native code,
  or direct mutation of private module state can bypass process-local Python
  conventions. This is not a hostile same-process isolation boundary.
- Issuing a capability cannot erase other references that already exist to the
  underlying value. A winning consumer or transform can also retain the value,
  return it, or use it repeatedly. Issuers must avoid retaining aliases, and
  callbacks must be trusted to perform the intended bounded operation rather
  than leak its payload.
- A recipient can copy references to a newly transferred handle. Those aliases
  still share one claim, but the library cannot prove which thread, component,
  person, or machine is the “real” holder.
- Lineage is runtime-checked metadata, not a signature, durable audit log, or
  authenticity proof. Standalone lineage tuples can be fabricated and grant no
  authority.
- Pickle rejection does not promise interception of every third-party
  serializer or memory-inspection technique.
- Handles do not survive interpreter shutdown or restart. There is no recovery,
  distributed consensus, cross-process transfer, crash durability, or external
  side-effect rollback.
- If callback code calls `fork()`, Python duplicates the callback's execution
  path. The inherited handle and any attempted child successor are rejected,
  but arbitrary callback code may already have run in both processes. Avoid
  forking inside a callback when duplicate effects matter.
- The child fork hook quarantines inherited registry records instead of
  releasing them, because release could run arbitrary payload finalizers while
  the runtime is being repaired. A long-running forked child may therefore keep
  inherited payload resources alive until that child shuts down.
- Garbage-collection abandonment releases the registry's reference to a value
  on a best-effort basis. Correct resource cleanup must use explicit
  consumption and application-level cleanup logic.

## Why “affine-style”

In an affine discipline a value may be used at most once; use is not mandatory.
Python cannot statically enforce such a discipline. This library applies the
analogy only to claiming capability authority, and dropping a live capability
is permitted. The payload released to trusted callback code is an ordinary
Python value. `affinecap` therefore uses the deliberately narrow phrase
**runtime affine-style capability**, never “linear types for Python.”
