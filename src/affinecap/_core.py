"""Registry-backed affine-style capabilities.

The public handle deliberately stores no payload. Runtime authority is the
combination of a random private registry coordinate and the exact weakly held
handle identity that the registry issued.
"""

from __future__ import annotations

import os
import secrets
import threading
import weakref
from collections.abc import Callable
from dataclasses import dataclass
from typing import (
    Any,
    Generic,
    Literal,
    NamedTuple,
    NoReturn,
    SupportsIndex,
    TypeVar,
    cast,
    final,
)

T = TypeVar("T")
U = TypeVar("U")
R = TypeVar("R")

Operation = Literal["issue", "transfer", "transition"]


class CapabilityError(RuntimeError):
    """Base class for capability lifecycle failures."""


class CapabilityConsumedError(CapabilityError):
    """The capability is spent, abandoned, or otherwise no longer live."""


class CapabilityProcessError(CapabilityError):
    """The capability crossed its issuing process or runtime epoch."""


class CapabilityIntegrityError(CapabilityError):
    """A handle is malformed or is not the exact object issued by the runtime."""


class LineageEntry(NamedTuple):
    """One immutable, non-authoritative entry in a live capability's ancestry."""

    capability_id: str
    parent_id: str | None
    generation: int
    operation: Operation
    label: str | None


@dataclass(slots=True)
class _Record:
    handle_ref: weakref.ReferenceType[Capability[Any]]
    payload: Any
    lineage: tuple[LineageEntry, ...]
    pid: int
    epoch: object


@dataclass(frozen=True, slots=True)
class _Claim(Generic[T]):
    payload: T
    lineage: tuple[LineageEntry, ...]
    pid: int
    epoch: object


_CONSTRUCTION_KEY = object()


@final
class Capability(Generic[T]):
    """An opaque, process-bound handle with at most one successful claim.

    Create capabilities with :func:`issue`. Normal construction, subclassing,
    copying, and pickling are intentionally unavailable.
    """

    __slots__ = ("__epoch", "__pid", "__token", "__weakref__")

    def __new__(cls, *, _key: object | None = None) -> Capability[Any]:
        if cls is not Capability or _key is not _CONSTRUCTION_KEY:
            raise TypeError("capabilities are created only by affinecap.issue()")
        return cast("Capability[Any]", super().__new__(cls))

    def __init__(self, *, _key: object | None = None) -> None:
        if _key is not _CONSTRUCTION_KEY:
            raise TypeError("capabilities are created only by affinecap.issue()")

    def __init_subclass__(cls, **kwargs: Any) -> NoReturn:
        del kwargs
        raise TypeError("Capability cannot be subclassed")

    @property
    def lineage(self) -> tuple[LineageEntry, ...]:
        """Return immutable registry-backed ancestry for this live handle."""

        return _RUNTIME.snapshot(self)

    @property
    def capability_id(self) -> str:
        """Return this live capability's public, non-authoritative identifier."""

        return self.lineage[-1].capability_id

    @property
    def generation(self) -> int:
        """Return the number of successor transitions since initial issuance."""

        return self.lineage[-1].generation

    def consume(self, consumer: Callable[[T], R]) -> R:
        """Spend this handle, then release its value to ``consumer``.

        Callable validation occurs before the claim. After the claim, every
        exception leaves the handle spent. The library does not constrain how
        trusted consumer code retains or uses the released value.
        """

        if not callable(consumer):
            raise TypeError("consumer must be callable")
        claim = _RUNTIME.claim(self)
        result = consumer(claim.payload)
        _RUNTIME.require_claim_process(claim)
        return result

    def transfer(self, *, label: str | None = None) -> Capability[T]:
        """Spend this handle and return a new handle for the same value."""

        _validate_label(label)
        claim = _RUNTIME.claim(self)
        return _RUNTIME.issue_successor(
            claim,
            claim.payload,
            operation="transfer",
            label=label,
        )

    def transition(
        self,
        transform: Callable[[T], U],
        *,
        label: str | None = None,
    ) -> Capability[U]:
        """Spend this handle and issue a successor for ``transform(value)``.

        No successor is issued if the transform raises. The old handle remains
        spent in every post-claim failure case.
        """

        if not callable(transform):
            raise TypeError("transform must be callable")
        _validate_label(label)
        claim = _RUNTIME.claim(self)
        successor_payload = transform(claim.payload)
        return _RUNTIME.issue_successor(
            claim,
            successor_payload,
            operation="transition",
            label=label,
        )

    def _coordinates(self) -> tuple[str, int, object]:
        try:
            token = object.__getattribute__(self, "_Capability__token")
            pid = object.__getattribute__(self, "_Capability__pid")
            epoch = object.__getattribute__(self, "_Capability__epoch")
        except (AttributeError, TypeError) as exc:
            raise CapabilityIntegrityError("capability handle is malformed") from exc
        if type(token) is not str or type(pid) is not int:
            raise CapabilityIntegrityError("capability handle is malformed")
        return token, pid, epoch

    def __repr__(self) -> str:
        return "<affinecap.Capability>"

    def __copy__(self) -> NoReturn:
        raise TypeError("capabilities cannot be copied")

    def __deepcopy__(self, memo: Any) -> NoReturn:
        del memo
        raise TypeError("capabilities cannot be deep-copied")

    def __reduce__(self) -> NoReturn:
        raise TypeError("capabilities cannot be serialized")

    def __reduce_ex__(self, protocol: SupportsIndex) -> NoReturn:
        del protocol
        raise TypeError("capabilities cannot be serialized")

    def __getstate__(self) -> NoReturn:
        raise TypeError("capabilities cannot be serialized")

    def __setstate__(self, state: object) -> NoReturn:
        del state
        raise TypeError("capabilities cannot be deserialized")


class _Runtime:
    """One interpreter-local authority registry."""

    def __init__(self) -> None:
        self._pid = os.getpid()
        self._epoch = object()
        self._lock = threading.Lock()
        self._records: dict[str, _Record] = {}
        self._fork_quarantine: tuple[object, ...] = ()

    def reset_after_fork(self) -> None:
        """Fence inherited authority without acquiring a possibly held lock."""

        # Keep inherited records alive until child shutdown. Clearing them here
        # could invoke arbitrary payload finalizers inside the at-fork hook.
        self._fork_quarantine = (self._records, self._fork_quarantine)
        self._pid = os.getpid()
        self._epoch = object()
        self._lock = threading.Lock()
        self._records = {}

    def _ensure_current_process_for_issue(self) -> None:
        if self._pid != os.getpid():
            # A fallback for Python/platform combinations where the registered
            # at-fork hook did not run. No other thread survives in the child.
            self.reset_after_fork()

    def issue(self, payload: T, *, label: str | None) -> Capability[T]:
        self._ensure_current_process_for_issue()
        capability_id = secrets.token_hex(16)
        lineage = (
            LineageEntry(
                capability_id=capability_id,
                parent_id=None,
                generation=0,
                operation="issue",
                label=label,
            ),
        )
        return self._issue(payload, lineage=lineage)

    def issue_successor(
        self,
        claim: _Claim[Any],
        payload: U,
        *,
        operation: Literal["transfer", "transition"],
        label: str | None,
    ) -> Capability[U]:
        self.require_claim_process(claim)
        parent = claim.lineage[-1]
        entry = LineageEntry(
            capability_id=secrets.token_hex(16),
            parent_id=parent.capability_id,
            generation=parent.generation + 1,
            operation=operation,
            label=label,
        )
        return self._issue(payload, lineage=(*claim.lineage, entry))

    def _issue(
        self,
        payload: T,
        *,
        lineage: tuple[LineageEntry, ...],
    ) -> Capability[T]:
        pid = os.getpid()
        if self._pid != pid:
            raise CapabilityProcessError("runtime process changed during issuance")
        epoch = self._epoch
        handle = cast("Capability[T]", Capability(_key=_CONSTRUCTION_KEY))
        with self._lock:
            if self._pid != pid or self._epoch is not epoch:
                raise CapabilityProcessError("runtime process changed during issuance")
            token = secrets.token_hex(32)
            while token in self._records:
                token = secrets.token_hex(32)
            object.__setattr__(handle, "_Capability__token", token)
            object.__setattr__(handle, "_Capability__pid", pid)
            object.__setattr__(handle, "_Capability__epoch", epoch)

            def abandon(
                observed_ref: weakref.ReferenceType[Capability[Any]],
                *,
                expected_token: str = token,
                expected_epoch: object = epoch,
            ) -> None:
                self._abandon(expected_token, expected_epoch, observed_ref)

            handle_ref = weakref.ref(handle, abandon)
            record = _Record(
                handle_ref=handle_ref,
                payload=payload,
                lineage=lineage,
                pid=pid,
                epoch=epoch,
            )
            self._records[token] = record
        return handle

    def _abandon(
        self,
        token: str,
        epoch: object,
        observed_ref: weakref.ReferenceType[Capability[Any]],
    ) -> None:
        if self._pid != os.getpid() or self._epoch is not epoch:
            return
        with self._lock:
            record = self._records.get(token)
            if record is not None and record.handle_ref is observed_ref:
                del self._records[token]

    def snapshot(self, handle: Capability[Any]) -> tuple[LineageEntry, ...]:
        token, pid, epoch = self._validate_coordinates(handle)
        with self._lock:
            record = self._require_record_locked(handle, token, pid, epoch)
            return record.lineage

    def claim(self, handle: Capability[T]) -> _Claim[T]:
        token, pid, epoch = self._validate_coordinates(handle)
        with self._lock:
            record = self._require_record_locked(handle, token, pid, epoch)
            del self._records[token]
        return _Claim(
            payload=cast("T", record.payload),
            lineage=record.lineage,
            pid=record.pid,
            epoch=record.epoch,
        )

    def _validate_coordinates(self, handle: Capability[Any]) -> tuple[str, int, object]:
        if type(handle) is not Capability:
            raise CapabilityIntegrityError("capability type is not exact")
        token, pid, epoch = handle._coordinates()
        if pid != os.getpid():
            raise CapabilityProcessError("capability cannot cross a process boundary")
        if self._pid != pid or self._epoch is not epoch:
            raise CapabilityProcessError(
                "capability belongs to a different runtime epoch"
            )
        return token, pid, epoch

    def _require_record_locked(
        self,
        handle: Capability[Any],
        token: str,
        pid: int,
        epoch: object,
    ) -> _Record:
        record = self._records.get(token)
        if record is None:
            raise CapabilityConsumedError("capability has already been consumed")
        if (
            record.pid != pid
            or record.epoch is not epoch
            or record.handle_ref() is not handle
        ):
            raise CapabilityIntegrityError(
                "capability is not the exact live handle issued by this runtime"
            )
        return record

    def require_claim_process(self, claim: _Claim[Any]) -> None:
        if (
            os.getpid() != claim.pid
            or self._pid != claim.pid
            or self._epoch is not claim.epoch
        ):
            raise CapabilityProcessError(
                "capability operation crossed a process boundary"
            )


def _validate_label(label: str | None) -> None:
    if label is not None and type(label) is not str:
        raise TypeError("label must be str or None")


_RUNTIME = _Runtime()

if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_RUNTIME.reset_after_fork)


def issue(payload: T, *, label: str | None = None) -> Capability[T]:
    """Issue one process-local affine-style capability for ``payload``."""

    _validate_label(label)
    return _RUNTIME.issue(payload, label=label)
