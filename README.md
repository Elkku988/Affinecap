# affinecap

[![CI](https://github.com/Elkku988/Affinecap/actions/workflows/ci.yml/badge.svg)](https://github.com/Elkku988/Affinecap/actions/workflows/ci.yml)

**One-shot runtime authority for Python.**

Python makes aliases freely. That is usually helpful, but it is awkward when
only one contender should be allowed to claim a value representing a deployment
approval, publication grant, or destructive-operation authority. `affinecap`
puts the value in a process-local registry and gives you an opaque handle. The
first caller to claim the handle receives the value; every stale alias fails.

```python
from affinecap import CapabilityConsumedError, issue

publish = issue(lambda: "published", label="review passed")

assert publish.consume(lambda action: action()) == "published"

try:
    publish.consume(lambda action: action())
except CapabilityConsumedError:
    print("already used")
```

This is a small runtime primitive for cooperative Python code. It provides
dynamic affine-style behavior; it does **not** add linear types to Python.

## What it enforces

- At most one `consume`, `transfer`, or `transition` claim wins.
- All aliases of a spent handle are stale.
- The registry accepts the exact handle object it issued, not a reconstructed
  lookalike.
- Claims are linearized across threads in one runtime, before user code runs.
- `copy`, `deepcopy`, pickle, inherited fork use, and multiprocessing pickling
  are rejected.
- Transfer and transition successors carry runtime-checked ancestry.
- Once callback execution begins, an exception leaves the predecessor spent.

## What it does not enforce

- It is not a sandbox against hostile code in the same interpreter.
- It cannot erase other references to the underlying value.
- It cannot stop the winning callback from retaining or repeatedly using the
  released value; callbacks are trusted application code.
- It does not authenticate who is allowed to call `issue`.
- It does not make external side effects transactional or exactly-once.
- Callback code that forks can continue in both processes; do not fork inside a
  capability callback when duplicate effects would matter.
- Its ancestry is not signed, durable provenance.
- Capabilities cannot be transferred between processes or survive restart.

The precise guarantee tiers and threat model are in the
[semantic contract](https://github.com/Elkku988/Affinecap/blob/main/docs/semantics.md).

## Installation

The package requires Python 3.10 or newer and has no runtime dependencies.
From a checkout:

```bash
python -m pip install .
```

The distribution is prepared as version `0.1.0`; it has not yet been uploaded
to PyPI.

## API

### `issue(value, *, label=None) -> Capability`

Creates one live capability. The public handle contains no payload; the value
is retained by the interpreter-local registry.

### `cap.consume(consumer)`

Claims the capability before calling `consumer(value)` and returns the
callback's result. A callback exception propagates and the capability remains
spent. This makes callback admission one-shot; it does not constrain how the
callback uses or retains `value` after release.

```python
approval = issue({"artifact": "sha256:..."})
receipt = approval.consume(deploy)
```

### `cap.transfer(*, label=None) -> Capability`

Returns a new handle for the same value and invalidates the old handle.
This is a logical custody handoff, not a Python or Rust memory move.

```python
worker_cap = approval.transfer(label="approval service -> worker")
```

### `cap.transition(transform, *, label=None) -> Capability`

Claims the predecessor, calls `transform(value)`, and puts the returned value
behind a new successor. If the transform fails, there is no successor.

```python
verified = acquired.transition(verify, label="verification passed")
```

### `cap.lineage`

Returns an immutable tuple of `LineageEntry` values for a live handle. Entries
record a public capability ID, parent ID, generation, operation, and optional
application label. IDs are newly generated random values, not durable or
authoritative identities. The private authority coordinate is never included.

## Realistic example

[`examples/deployment_approval.py`](https://github.com/Elkku988/Affinecap/blob/main/examples/deployment_approval.py)
places an
actual deployment action behind a trusted approval function, transfers its
handle to a worker, and demonstrates that the approver's old alias can no
longer deploy:

```bash
python examples/deployment_approval.py
```

The smaller executable version of the opening example is
[`examples/minimal.py`](https://github.com/Elkku988/Affinecap/blob/main/examples/minimal.py).

## Design notes

The registry stores the value, immutable lineage, issuing PID/runtime epoch,
and a weak reference to the exact handle. A lock atomically removes that record
before any callback is invoked. Transfer and transition issue a new record;
they never reactivate the predecessor. A fork hook replaces the child's lock,
epoch, and registry without touching potentially locked parent state.
Inherited records are quarantined until child shutdown so dropping them cannot
run arbitrary payload finalizers inside the fork hook. This may retain inherited
payload resources for the lifetime of a long-running child.

Dropping an unused handle is allowed—that is why the model is affine rather
than linear. A weak-reference callback releases the registry's payload
reference on a best-effort basis.

See [prior art](https://github.com/Elkku988/Affinecap/blob/main/docs/prior-art.md)
for comparisons with static affine/linear
systems, object-capability patterns, `contextvars.Token`, state-machine
libraries, and once primitives.

## Reverse Gravity ancestry

This abstraction was extracted from Reverse Gravity, where it originated as
machinery for enforcing evidence-custody and live-endpoint phase transitions in
a larger scientific pipeline. The standalone package retains the reusable
runtime mechanism and removes Solana schemas, RPC behavior, artifact layouts,
file-descriptor custody, and pipeline-specific transition graphs. The detailed
extraction map is in
[the ancestry note](https://github.com/Elkku988/Affinecap/blob/main/docs/rg-ancestry.md).

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
