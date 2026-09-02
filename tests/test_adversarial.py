from __future__ import annotations

import copy
import pickle
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest

from affinecap import (
    Capability,
    CapabilityConsumedError,
    CapabilityIntegrityError,
    issue,
)


def test_normal_construction_is_rejected() -> None:
    with pytest.raises(TypeError, match="created only"):
        Capability()  # type: ignore[call-arg]


def test_runtime_subclassing_is_rejected() -> None:
    with pytest.raises(TypeError, match="cannot be subclassed"):

        class ForgedCapability(Capability[object]):
            pass


def test_shallow_copy_deepcopy_and_every_pickle_protocol_are_rejected() -> None:
    cap = issue(["payload"])

    with pytest.raises(TypeError, match="cannot be copied"):
        copy.copy(cap)
    with pytest.raises(TypeError, match="cannot be deep-copied"):
        copy.deepcopy(cap)
    for protocol in range(pickle.HIGHEST_PROTOCOL + 1):
        with pytest.raises(TypeError, match="cannot be serialized"):
            pickle.dumps(cap, protocol=protocol)

    assert cap.consume(tuple) == ("payload",)


def test_forged_shell_with_cloned_slots_has_no_authority() -> None:
    cap = issue("registered")
    forged = object.__new__(Capability)
    for name in (
        "_Capability__token",
        "_Capability__pid",
        "_Capability__epoch",
    ):
        object.__setattr__(forged, name, object.__getattribute__(cap, name))

    with pytest.raises(CapabilityIntegrityError, match="exact live handle"):
        forged.consume(lambda value: value)
    assert cap.consume(lambda value: value) == "registered"


def test_incomplete_reconstructed_shell_is_rejected() -> None:
    forged = object.__new__(Capability)

    with pytest.raises(CapabilityIntegrityError, match="malformed"):
        forged.consume(lambda value: value)


def test_reentrant_consume_observes_pre_callback_claim() -> None:
    cap = issue("once")
    reentrant_errors: list[BaseException] = []

    def consumer(value: str) -> str:
        try:
            cap.consume(lambda nested: nested)
        except BaseException as exc:
            reentrant_errors.append(exc)
        return value

    assert cap.consume(consumer) == "once"
    assert len(reentrant_errors) == 1
    assert isinstance(reentrant_errors[0], CapabilityConsumedError)


def test_reentrant_transition_cannot_reuse_parent() -> None:
    cap = issue(5)

    def transform(value: int) -> int:
        with pytest.raises(CapabilityConsumedError):
            cap.transfer()
        return value + 1

    successor = cap.transition(transform)
    assert successor.consume(lambda value: value) == 6


def test_simultaneous_consumers_have_exactly_one_winner() -> None:
    contender_count = 32
    cap = issue("permit")
    barrier = threading.Barrier(contender_count)
    callback_calls: list[int] = []
    callback_lock = threading.Lock()

    def contend(index: int) -> tuple[str, int]:
        barrier.wait(timeout=10)

        def consume(_value: str) -> int:
            with callback_lock:
                callback_calls.append(index)
            return index

        try:
            return "won", cap.consume(consume)
        except CapabilityConsumedError:
            return "lost", index

    with ThreadPoolExecutor(max_workers=contender_count) as pool:
        results = list(pool.map(contend, range(contender_count)))

    assert [status for status, _ in results].count("won") == 1
    assert [status for status, _ in results].count("lost") == contender_count - 1
    assert len(callback_calls) == 1


def test_simultaneous_transfers_publish_exactly_one_successor() -> None:
    contender_count = 16
    cap = issue(object())
    barrier = threading.Barrier(contender_count)

    def contend(index: int) -> tuple[str, Any]:
        barrier.wait(timeout=10)
        try:
            return "won", cap.transfer(label=f"thread-{index}")
        except CapabilityConsumedError as exc:
            return "lost", exc

    with ThreadPoolExecutor(max_workers=contender_count) as pool:
        results = list(pool.map(contend, range(contender_count)))

    successors = [value for status, value in results if status == "won"]
    assert len(successors) == 1
    assert [status for status, _ in results].count("lost") == contender_count - 1
    assert successors[0].consume(lambda value: value) is not None


def test_consume_and_transfer_race_has_one_claim_winner() -> None:
    cap = issue("payload")
    barrier = threading.Barrier(2)

    def consume() -> tuple[str, Any]:
        barrier.wait(timeout=10)
        try:
            return "consume", cap.consume(lambda value: value)
        except CapabilityConsumedError as exc:
            return "lost", exc

    def transfer() -> tuple[str, Any]:
        barrier.wait(timeout=10)
        try:
            return "transfer", cap.transfer()
        except CapabilityConsumedError as exc:
            return "lost", exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [pool.submit(consume), pool.submit(transfer)]
        results = [future.result(timeout=10) for future in outcomes]

    winners = [(kind, value) for kind, value in results if kind != "lost"]
    assert len(winners) == 1
    if winners[0][0] == "transfer":
        assert winners[0][1].consume(lambda value: value) == "payload"
