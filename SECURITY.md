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

Callbacks are ordinary synchronous Python calls. An asynchronous function or
generator function initially returns a lazy object without executing its body.
`consume` returns that object, and `transition` places it behind the successor;
later awaiting, iteration, side effects, and failures are outside the
fail-closed callback boundary.

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

Abandonment cleanup is also best effort. If a registered value retains its own
capability handle, the registry-to-value-to-handle reference path prevents the
weak-reference cleanup callback from running. Explicitly consume capabilities
that protect resources instead of relying on garbage collection.

Do not call the API from Python signal handlers. A handler can interrupt a
registry operation at an internal point; `affinecap` does not claim
async-signal-safety or reentrant signal semantics.

Do not call the API from a user-defined `os.register_at_fork` callback. The
order of child-hook execution can cause a handle issued by an earlier hook to
be invalidated when `affinecap` subsequently fences inherited authority.

The default `copy`, `deepcopy`, and standard pickle paths are rejected. Python
allows callers to customize those mechanisms; a pre-populated `deepcopy` memo
or custom persistent-ID hook can return a handle the caller already holds.
That is another alias to the same one-shot registry claim, not duplicated
authority.

Lineage labels are visible through every live handle's `lineage` property.
They are diagnostic metadata, so do not put credentials, secrets, or sensitive
personal data in a label.

Potential vulnerabilities include a public-API path that permits two claims of
one issued handle, inherited authority that remains usable after fork, payload
exposure through a public handle before a successful claim, or a standard
copy/pickle path that yields usable duplicate authority. Reflection or direct
mutation of private module state is outside the stated threat model, though
reports of an avoidable bypass are still welcome.

Prefer the repository's
[private GitHub vulnerability report](https://github.com/Elkku988/Affinecap/security/advisories/new)
for suspected vulnerabilities. Include the Python version, platform, minimal
reproducer, and the guarantee you believe is violated. Do not include real
credentials or production authority values.

If GitHub reports that private vulnerability reporting is unavailable, open a
[minimal public issue](https://github.com/Elkku988/Affinecap/issues/new) asking
the maintainer to enable a private reporting channel. Do **not** put exploit
details, secrets, or an undisclosed vulnerability in that public issue.
