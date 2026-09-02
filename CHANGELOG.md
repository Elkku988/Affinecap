# Changelog

## 0.1.1 - 2026-09-02

- Prepared the initial PyPI release.
- Prevented cyclic garbage collection from deadlocking during registry
  operations.
- Standardized the public issuance keyword as `issue(value=...)`.
- Clarified per-handle claims, synchronous and lazy callback behavior,
  customized copy/pickle aliases, interpreter/process boundaries, signal and
  at-fork callback limitations, lineage-label visibility, and
  garbage-collection retention.
- Replaced source-system internals with a concise public design-provenance note.
- Made the deployment example validate against an independent approved digest
  and identify its backend effects as simulated.
- Added guarded Trusted Publishing automation with compatibility, artifact,
  remote-hash, and GitHub Release gates.

## 0.1.0 - 2026-09-02

- Pre-publication repository snapshot; this version was not uploaded to PyPI.
- Registry-backed `Capability` with `consume`, `transfer`, and `transition`.
- Immutable runtime lineage, process/fork binding, standard duplication
  barriers, and adversarial concurrency/process tests.
