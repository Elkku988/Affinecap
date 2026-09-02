# Prior art and terminology

`affinecap` implements a known idea in a deliberately narrow ordinary-Python
form. It does not claim to invent affine capabilities.

## The accurate label

An affine discipline permits a value to be used at most once; a linear
discipline normally requires exactly one use. Because Python code may simply
drop a capability, this project uses **runtime affine-style capability object**
rather than “linear type.” The check is dynamic and does not invalidate Python
variable bindings.

## Comparisons

- Cardelli and Gordon's 1999
  [*Types for Mobile Ambients*](https://www.microsoft.com/en-us/research/wp-content/uploads/1999/01/popl99.pdf)
  describes “Affine Capability Types” as consumable, transferable access
  tokens. That is direct conceptual prior art.
- Pony documents a stronger language-supported
  [Single Use Object Capabilities](https://patterns.ponylang.io/object-capabilities/single-use/)
  pattern using isolated references. `affinecap` provides weaker dynamic
  behavior in ordinary CPython.
- Rust enforces ownership and moves statically. Python assignment creates an
  alias, so this package invalidates shared registry state seen by every
  cooperating alias instead. See the
  [Rust ownership chapter](https://doc.rust-lang.org/book/ch04-01-what-is-ownership.html).
- Python's [`contextvars.Token`](https://docs.python.org/3/library/contextvars.html#contextvars.Token)
  is a close standard-library analogue: it is opaque, bound to its originating
  variable/context, and accepted by `reset()` only once. It is purpose-specific
  and has no generic payload, successor transfer, or transition lineage.
- Go's [`sync.Once`](https://pkg.go.dev/sync#Once) linearizes one callback among
  concurrent callers and treats panic as completion. It does not make the
  authority transferable or record ancestry.
- General state-machine libraries such as
  [`transitions`](https://github.com/pytransitions/transitions),
  [`Automat`](https://github.com/glyph/automat), and
  [`python-statemachine`](https://python-statemachine.readthedocs.io/) model
  broader protocols. Their center of gravity is state-machine declaration,
  not exact-handle custody and one-shot authority.
- Provenance standards such as
  [W3C PROV](https://www.w3.org/TR/prov-primer/) represent history but do not
  control process-local one-shot use. `affinecap` lineage is much smaller and
  is explicitly non-cryptographic.

Object-capability literature typically assumes stronger isolation properties
than an ordinary Python module can provide. Python has no truly private object
fields, and native/reflection access can bypass conventions. This project uses
“capability” only for the scoped possession check performed by its trusted
runtime registry.

## Narrow differentiation

The project's focus is the combination of:

- dynamic stale-alias invalidation;
- exact issued-handle registry identity;
- PID and runtime-epoch scoping with fork invalidation;
- explicit refusal of default standard copy and pickle protocols;
- fail-closed successor transitions; and
- local, immutable transition ancestry.

This is an implementation focus, not a novelty claim. No bounded ecosystem
search can prove that no similar package exists.
