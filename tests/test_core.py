from __future__ import annotations

import asyncio
import gc
import weakref
from typing import Any

import pytest

from affinecap import (
    Capability,
    CapabilityConsumedError,
    LineageEntry,
    issue,
)


def test_consume_invokes_callback_once_and_returns_its_result() -> None:
    calls: list[int] = []
    cap = issue(21)

    result = cap.consume(lambda value: calls.append(value) or value * 2)

    assert result == 42
    assert calls == [21]
    with pytest.raises(CapabilityConsumedError):
        cap.consume(lambda value: value)


def test_issue_accepts_value_as_its_public_keyword() -> None:
    cap = issue(value="authority")

    assert cap.consume(lambda value: value) == "authority"


def test_every_alias_becomes_stale_after_consumption() -> None:
    cap = issue("authority")
    alias = cap

    assert cap.consume(str.upper) == "AUTHORITY"
    with pytest.raises(CapabilityConsumedError):
        alias.consume(str.upper)
    with pytest.raises(CapabilityConsumedError):
        _ = alias.lineage


def test_winning_callback_can_retain_and_reuse_released_payload() -> None:
    calls: list[str] = []

    def action() -> None:
        calls.append("called")

    cap = issue(action)
    released = cap.consume(lambda value: value)

    released()
    released()
    assert calls == ["called", "called"]
    with pytest.raises(CapabilityConsumedError):
        cap.consume(lambda value: value)


def test_invalid_consumer_is_rejected_before_claim() -> None:
    cap = issue(3)

    with pytest.raises(TypeError, match="consumer must be callable"):
        cap.consume(None)  # type: ignore[arg-type]

    assert cap.consume(lambda value: value + 1) == 4


def test_transfer_spends_old_handle_and_preserves_payload() -> None:
    original = issue({"artifact": "sha256:abc"}, label="approved")

    successor = original.transfer(label="to deployer")

    with pytest.raises(CapabilityConsumedError):
        original.consume(lambda value: value)
    assert successor.consume(lambda value: value["artifact"]) == "sha256:abc"

    # The consumed successor is stale too.
    with pytest.raises(CapabilityConsumedError):
        _ = successor.capability_id


def test_transfer_lineage_names_exact_parent() -> None:
    original = issue("payload", label="issuer")
    original_id = original.capability_id
    successor = original.transfer(label="handoff")

    assert successor.generation == 1
    assert successor.lineage == (
        LineageEntry(original_id, None, 0, "issue", "issuer"),
        LineageEntry(
            successor.capability_id,
            original_id,
            1,
            "transfer",
            "handoff",
        ),
    )


def test_transition_replaces_payload_and_extends_lineage() -> None:
    original = issue(7, label="raw")
    original_id = original.capability_id

    successor = original.transition(lambda value: f"verified:{value}", label="verify")

    assert successor.generation == 1
    assert successor.lineage[-1].parent_id == original_id
    assert successor.lineage[-1].operation == "transition"
    assert successor.lineage[-1].label == "verify"
    assert successor.consume(lambda value: value) == "verified:7"


def test_multiple_successors_form_an_unbroken_lineage() -> None:
    first = issue(1)
    first_id = first.capability_id
    second = first.transfer(label="second")
    second_id = second.capability_id
    third = second.transition(lambda value: value + 1, label="third")

    entries = third.lineage
    assert [entry.generation for entry in entries] == [0, 1, 2]
    assert [entry.operation for entry in entries] == [
        "issue",
        "transfer",
        "transition",
    ]
    assert entries[0].capability_id == first_id
    assert entries[1].parent_id == first_id
    assert entries[1].capability_id == second_id
    assert entries[2].parent_id == second_id
    assert len({entry.capability_id for entry in entries}) == 3


@pytest.mark.parametrize("error", [RuntimeError("failure"), KeyboardInterrupt()])
def test_consumer_base_exception_leaves_capability_spent(error: BaseException) -> None:
    cap = issue("permit")

    def fail(_value: str) -> Any:
        raise error

    with pytest.raises(type(error)):
        cap.consume(fail)
    with pytest.raises(CapabilityConsumedError):
        cap.consume(lambda value: value)


def test_failed_transition_issues_no_reusable_parent() -> None:
    cap = issue("unverified")

    def fail(_value: str) -> str:
        raise ValueError("verification failed")

    with pytest.raises(ValueError, match="verification failed"):
        cap.transition(fail)
    with pytest.raises(CapabilityConsumedError):
        cap.transfer()


def test_async_consumer_return_is_an_ordinary_lazy_result() -> None:
    events: list[str] = []
    cap = issue("authority")

    async def consume_later(value: str) -> str:
        events.append(value)
        return value.upper()

    awaitable = cap.consume(consume_later)

    # Calling an async function only creates its coroutine. Affinecap's claim
    # boundary is the synchronous callback call, not its later execution.
    assert events == []
    with pytest.raises(CapabilityConsumedError):
        cap.consume(lambda value: value)
    assert asyncio.run(awaitable) == "AUTHORITY"
    assert events == ["authority"]


def test_lazy_transform_return_is_the_successor_payload() -> None:
    events: list[int] = []
    cap = issue(7)

    def transform_later(value: int) -> Any:
        def generated() -> Any:
            events.append(value)
            yield value + 1

        return generated()

    successor = cap.transition(transform_later)

    assert events == []
    generator = successor.consume(lambda value: value)
    assert list(generator) == [8]
    assert events == [7]


def test_async_transform_failure_happens_after_successor_issuance() -> None:
    cap = issue("unverified")

    async def fail_later(_value: str) -> str:
        raise ValueError("lazy verification failure")

    successor = cap.transition(fail_later)

    with pytest.raises(CapabilityConsumedError):
        cap.consume(lambda value: value)
    awaitable = successor.consume(lambda value: value)
    with pytest.raises(ValueError, match="lazy verification failure"):
        asyncio.run(awaitable)


@pytest.mark.parametrize("operation", ["transfer", "transition"])
def test_successor_issuance_failure_leaves_predecessor_spent(
    monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    from affinecap._core import _RUNTIME

    cap = issue("authority")

    def fail_issue(*_args: Any, **_kwargs: Any) -> Any:
        raise MemoryError("simulated successor allocation failure")

    monkeypatch.setattr(_RUNTIME, "_issue", fail_issue)
    with pytest.raises(MemoryError, match="simulated"):
        if operation == "transfer":
            cap.transfer()
        else:
            cap.transition(lambda value: value)

    with pytest.raises(CapabilityConsumedError):
        cap.consume(lambda value: value)


def test_invalid_transition_arguments_do_not_consume() -> None:
    cap = issue(10)

    with pytest.raises(TypeError, match="transform must be callable"):
        cap.transition(4)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="label must be str or None"):
        cap.transfer(label=4)  # type: ignore[arg-type]

    assert cap.consume(lambda value: value) == 10


def test_live_lineage_is_an_immutable_tuple_of_immutable_entries() -> None:
    cap = issue("payload")
    lineage = cap.lineage

    assert isinstance(lineage, tuple)
    with pytest.raises(TypeError):
        lineage[0][0] = "changed"  # type: ignore[index]
    with pytest.raises(AttributeError):
        lineage[0].generation = 99  # type: ignore[misc]


def test_repr_and_instance_storage_do_not_reveal_payload_or_label() -> None:
    secret = "do-not-render-this-value"
    cap = issue(secret, label="do-not-render-this-label")

    assert repr(cap) == "<affinecap.Capability>"
    assert secret not in repr(cap)
    with pytest.raises(TypeError):
        vars(cap)


class _Payload:
    pass


def test_abandoning_live_handle_releases_registry_payload_reference() -> None:
    payload = _Payload()
    payload_ref = weakref.ref(payload)
    cap = issue(payload)
    cap_ref = weakref.ref(cap)
    del payload

    assert payload_ref() is not None
    del cap
    for _ in range(3):
        gc.collect()

    assert cap_ref() is None
    assert payload_ref() is None


class _BackreferencingPayload:
    def __init__(self) -> None:
        self.capability: Capability[_BackreferencingPayload] | None = None


def test_payload_backreference_retains_live_handle_until_explicit_claim() -> None:
    payload = _BackreferencingPayload()
    cap = issue(payload)
    payload.capability = cap
    payload_ref = weakref.ref(payload)
    cap_ref = weakref.ref(cap)
    del payload, cap

    for _ in range(3):
        gc.collect()

    # The registry owns the payload, and the payload owns its handle. This is
    # a supported Python reference graph, not an ownership cycle the runtime
    # can infer or break automatically.
    retained_cap = cap_ref()
    assert retained_cap is not None
    assert payload_ref() is not None

    released_payload = retained_cap.consume(lambda value: value)
    released_payload.capability = None
    del retained_cap, released_payload
    for _ in range(3):
        gc.collect()

    assert cap_ref() is None
    assert payload_ref() is None
