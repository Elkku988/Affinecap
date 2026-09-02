# affinecap

[![CI](https://github.com/Elkku988/Affinecap/actions/workflows/ci.yml/badge.svg)](https://github.com/Elkku988/Affinecap/actions/workflows/ci.yml)

**One-shot runtime authority for Python.**

Python assignment freely creates aliases. That is usually helpful, but it is
awkward when only one contender should be allowed to claim a deployment
approval, publication grant, or destructive-operation authority. `affinecap`
keeps a value in an interpreter-local registry and gives the application an
opaque handle. The first library-mediated claim of that handle wins; every
alias of the spent handle becomes stale.

```python
from affinecap import CapabilityConsumedError, issue

publish = issue(value=lambda: "published", label="review passed")

assert publish.consume(lambda action: action()) == "published"

try:
    publish.consume(lambda action: action())
except CapabilityConsumedError:
    print("already used")
```

This is a small coordination primitive for cooperative Python code. It
provides dynamic affine-style behavior; it does **not** add linear types or a
security sandbox to Python.

## What it enforces

- At most one `consume`, `transfer`, or `transition` claim succeeds for each
  issued handle. A successor is a new handle with its own one-shot claim.
- All Python aliases of a spent handle are stale.
- The registry accepts the exact handle object it issued, not a reconstructed
  lookalike.
- Claims are linearized across threads in one interpreter before user code
  runs.
- Default `copy.copy`, `copy.deepcopy`, standard pickle protocols, inherited
  fork use, and multiprocessing pickling are rejected.
- Handles are bound to the issuing process ID and interpreter runtime epoch.
- Transfer and transition successors carry registry-maintained ancestry.
- Once callback execution begins, an exception leaves the predecessor spent.

## What it does not enforce

- It is not a boundary against hostile code in the same interpreter.
- It cannot erase references to the underlying value that exist outside the
  registry.
- It cannot stop the winning callback from retaining or repeatedly using the
  released value; callback code is trusted.
- It does not authenticate who may call `issue`.
- It does not make external effects transactional, durable, or exactly-once.
- Callback code that forks can continue executing in both processes. Do not
  fork inside a callback when duplicate effects would matter.
- Lineage is neither signed nor durable provenance.
- Capabilities cannot move between interpreters or processes, and they do not
  survive interpreter restart.
- The API is not safe to invoke from a signal handler or a user-defined
  `os.register_at_fork` callback.

The exact guarantee tiers and assumptions are in the
[semantic contract](https://github.com/Elkku988/Affinecap/blob/main/docs/semantics.md).

## Installation

The package supports CPython 3.10 through 3.14 and has no runtime dependencies.

```bash
python -m pip install affinecap
```

From a source checkout:

```bash
python -m pip install .
```

## API

### `issue(value, *, label=None) -> Capability`

Creates one live capability. The public handle stores no value or lineage in
its instance state; the interpreter-local registry retains both and binds the
record to the exact handle, current process ID, and runtime epoch.

Labels are application-supplied diagnostic metadata exposed through
`cap.lineage`. Do not put secrets, credentials, or sensitive personal data in
them.

### `cap.consume(consumer)`

Claims the capability before calling `consumer(value)` and returns the
callback's result. A callback exception propagates and the capability remains
spent. This makes callback admission one-shot; it does not constrain how the
callback uses or retains `value` after release.

```python
approval = issue(value={"artifact": "sha256:..."})
receipt = approval.consume(deploy)
```

Callbacks are invoked as ordinary synchronous Python calls. If an `async def`
function is supplied, calling it merely produces a coroutine; if a generator
function is supplied, calling it merely produces a generator. `consume`
returns that lazy object without executing it, and any later exception is
outside the capability callback boundary.

### `cap.transfer(*, label=None) -> Capability`

Returns a new handle for the same value and invalidates the old handle. This
is a logical custody handoff, not a Python or Rust memory move. Existing
references to the underlying value are unaffected.

```python
worker_cap = approval.transfer(label="approval service -> worker")
```

### `cap.transition(transform, *, label=None) -> Capability`

Claims the predecessor, synchronously calls `transform(value)`, and places the
returned value behind a new successor. If the synchronous call raises, there
is no successor and the predecessor stays spent.

```python
verified = acquired.transition(verify, label="verification passed")
```

As with `consume`, a coroutine, generator, iterator, or other lazy object
returned by `transform` is treated as the returned value itself. It becomes
the successor payload; later execution and failures are not observed by
`transition`. Run all work that must be covered by the fail-closed boundary
before the transform returns.

### Live-handle properties

- `cap.lineage` is an immutable tuple of registry-backed `LineageEntry`
  values.
- `cap.capability_id` is the current entry's random public identifier.
- `cap.generation` is the number of transfers or transitions since issuance.

These properties require a live handle. They raise a lifecycle error after
the handle is spent. A `LineageEntry` contains `capability_id`, `parent_id`,
`generation`, `operation`, and optional `label`. The identifiers and entries
are diagnostic metadata; they do not grant authority and are not authenticity
proofs.

### Exported types and errors

- `Capability[T]` is the final, opaque generic handle type. Applications create
  handles with `issue`, not by calling `Capability`.
- `LineageEntry` is the immutable public lineage record type.
- `CapabilityError` is the base class for lifecycle failures.
- `CapabilityConsumedError` means the handle is no longer live.
- `CapabilityProcessError` means an operation crossed a process or runtime
  boundary.
- `CapabilityIntegrityError` means a handle is malformed or is not the exact
  live object issued by this runtime.
- `__version__` reports the installed distribution version.

Construction, subclassing, and default standard-library copying and
serialization raise `TypeError` rather than a `CapabilityError` subclass.

## Realistic example

[`examples/deployment_approval.py`](https://github.com/Elkku988/Affinecap/blob/main/examples/deployment_approval.py)
checks an artifact against an independently supplied approved digest, hands
the authority to a worker, and records an action in a stateful simulated
deployment backend. It demonstrates at-most-one admission through the handle,
not exactly-once deployment semantics:

```bash
python examples/deployment_approval.py
```

The smaller executable version of the opening example is
[`examples/minimal.py`](https://github.com/Elkku988/Affinecap/blob/main/examples/minimal.py).

## Design notes

The registry stores the value, immutable lineage, issuing process ID/runtime
epoch, and a weak reference to the exact handle. The epoch is an in-memory
marker for the current registry instance and is replaced after a fork. A
synchronization lock atomically removes a claimed record before any callback is
invoked. Transfer and transition issue a new record; they never reactivate the
predecessor.

A fork hook replaces the child's lock, epoch, and active registry without
touching potentially locked parent state. Inherited records are quarantined
until child shutdown so dropping them cannot run arbitrary payload finalizers
inside the fork hook. A long-running child may therefore retain inherited
payload resources until it exits.

Dropping an unused handle is allowed—that is why the model is affine rather
than linear. A weak-reference callback releases the registry's value reference
on a best-effort basis. Do not rely on abandonment for resource cleanup. In
particular, if the registered value retains its own capability handle, the
registry-to-value-to-handle reference path keeps the handle alive and prevents
weak-reference abandonment; explicit consumption is required to break that
retention.

See [prior art](https://github.com/Elkku988/Affinecap/blob/main/docs/prior-art.md)
for comparisons with static affine/linear systems, object-capability patterns,
`contextvars.Token`, state-machine libraries, and once primitives.

## Design provenance

The design was generalized from selected mechanisms in Reverse Gravity, a
scientific data-processing system that needed one-shot custody handoffs and
fail-closed phase transitions. `affinecap` keeps the reusable in-memory
mechanism and omits that system's data formats, network access, artifact
layout, and workflow-specific transition rules. The package implementation is
a compact generalization, not a verbatim source copy. See the
[design provenance note](https://github.com/Elkku988/Affinecap/blob/main/docs/design-provenance.md).

## Development

```bash
python -m pip install -e '.[dev]'
pytest
ruff check .
ruff format --check .
mypy
python -m build
twine check dist/*
```

CI runs the tests on Python 3.10 through 3.14 and checks formatting, lint,
typing, distributions, and both examples.

## License

MIT
