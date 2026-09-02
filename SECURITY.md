# Security and threat model

`affinecap` is designed to prevent accidental reuse and to arbitrate
cooperating concurrent callers. It is **not** a security boundary against
hostile code running in the same Python interpreter.

The complete assumptions and non-guarantees are part of the
[semantic contract](docs/semantics.md). In particular, do not use this package
as a substitute for process isolation, operating-system permissions,
cryptographic authorization, durable idempotency records, or external
transaction semantics.

The protected event is one registry-mediated claim, not every use of the
payload after release. A consumer or transform receives an ordinary Python
object and can retain, return, alias, or invoke it repeatedly. Treat callback
code as trusted, keep issuance behind the application's authorization checks,
and make the payload operation itself enforce any stronger limits required.

In particular, process binding is not an exactly-once side-effect guarantee.
If a capability callback calls `fork()`, both resulting processes can continue
executing arbitrary callback code. The child cannot reuse the inherited handle
or publish a transition successor, but the library cannot undo effects that ran
before that rejection.

The child fork hook deliberately retains inherited registry records outside the
new active registry. This prevents arbitrary payload finalizers from running in
the hook, but it can retain payload resources until the child exits. Applications
that fork long-lived children should minimize live capabilities at the fork
boundary and independently close inherited operating-system resources where
appropriate.

Potential vulnerabilities include a public-API path that permits two claims of
one issued handle, inherited authority that remains usable after fork, payload
exposure through a public handle before a successful claim, or a standard
copy/pickle path that yields usable duplicate authority. Reflection or direct
mutation of private module state is outside the stated threat model, though
reports of an avoidable bypass are still welcome.

After publication, report suspected vulnerabilities through the repository's
private GitHub Security Advisory form. Please include the Python version,
platform, minimal reproducer, and the guarantee you believe is violated. Do not
include real credentials or production authority values.
