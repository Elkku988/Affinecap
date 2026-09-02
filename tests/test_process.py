from __future__ import annotations

import multiprocessing.reduction
import os
import signal

import pytest

from affinecap import CapabilityProcessError, issue

requires_fork = pytest.mark.skipif(
    not hasattr(os, "fork"), reason="requires POSIX fork"
)


class _ForkFinalizerProbe:
    def __init__(self, write_fd: int) -> None:
        self.write_fd: int | None = write_fd

    def disarm(self) -> None:
        self.write_fd = None

    def __del__(self) -> None:
        if self.write_fd is not None:
            os.write(self.write_fd, b"F")


def _wait_success(pid: int) -> None:
    waited, status = os.waitpid(pid, 0)
    assert waited == pid
    assert os.WIFEXITED(status)
    assert os.WEXITSTATUS(status) == 0


@requires_fork
def test_inherited_handle_fails_in_child_parent_remains_live() -> None:
    cap = issue("parent")
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:  # pragma: no cover - asserted through pipe and exit status
        os.close(read_fd)
        signal.alarm(10)
        try:
            try:
                cap.consume(lambda value: value)
            except CapabilityProcessError:
                inherited = b"rejected"
            else:
                inherited = b"accepted"
            fresh = issue("child").consume(lambda value: value)
            os.write(write_fd, inherited + b":" + fresh.encode("ascii"))
        finally:
            os.close(write_fd)
        os._exit(0)

    os.close(write_fd)
    outcome = os.read(read_fd, 128)
    os.close(read_fd)
    _wait_success(pid)

    assert outcome == b"rejected:child"
    assert cap.consume(lambda value: value) == "parent"


@requires_fork
def test_at_fork_reset_does_not_inherit_a_locked_registry() -> None:
    # Importing the private runtime is deliberate adversarial verification, not
    # part of the supported API.
    from affinecap._core import _RUNTIME

    cap = issue("parent")
    read_fd, write_fd = os.pipe()
    _RUNTIME._lock.acquire()
    try:
        pid = os.fork()
    finally:
        if "pid" in locals() and pid != 0:
            _RUNTIME._lock.release()

    if pid == 0:  # pragma: no cover - asserted through pipe and exit status
        os.close(read_fd)
        signal.alarm(10)
        try:
            try:
                cap.consume(lambda value: value)
            except CapabilityProcessError:
                inherited = b"rejected"
            else:
                inherited = b"accepted"
            fresh = issue("fresh").consume(lambda value: value)
            os.write(write_fd, inherited + b":" + fresh.encode("ascii"))
        finally:
            os.close(write_fd)
        os._exit(0)

    os.close(write_fd)
    outcome = os.read(read_fd, 128)
    os.close(read_fd)
    _wait_success(pid)

    assert outcome == b"rejected:fresh"
    assert cap.consume(lambda value: value) == "parent"


@requires_fork
def test_child_fork_hook_does_not_run_payload_finalizers() -> None:
    read_fd, write_fd = os.pipe()
    payload = _ForkFinalizerProbe(write_fd)
    cap = issue(payload)
    del payload

    pid = os.fork()
    if pid == 0:  # pragma: no cover - asserted through pipe and exit status
        os.close(read_fd)
        signal.alarm(10)
        os.write(write_fd, b"C")
        os.close(write_fd)
        os._exit(0)

    _wait_success(pid)
    observed = os.read(read_fd, 16)
    cap.consume(lambda value: value.disarm())
    os.close(read_fd)
    os.close(write_fd)

    assert observed == b"C"


@requires_fork
def test_fork_during_transition_cannot_issue_a_child_successor() -> None:
    parent_pid = os.getpid()
    read_fd, write_fd = os.pipe()
    child_pid: list[int] = []
    cap = issue("payload")

    def fork_transform(value: str) -> str:
        pid = os.fork()
        if pid == 0:
            signal.alarm(10)
        else:
            child_pid.append(pid)
        return value + ":transitioned"

    try:
        successor = cap.transition(fork_transform)
    except CapabilityProcessError:
        if os.getpid() == parent_pid:
            raise
        os.close(read_fd)
        os.write(write_fd, b"child-successor-rejected")
        os.close(write_fd)
        os._exit(0)  # pragma: no cover - asserted through pipe and exit status

    if os.getpid() != parent_pid:  # pragma: no cover - failure sentinel
        os.close(read_fd)
        os.write(write_fd, b"child-successor-issued")
        os.close(write_fd)
        os._exit(1)

    os.close(write_fd)
    outcome = os.read(read_fd, 128)
    os.close(read_fd)
    assert len(child_pid) == 1
    _wait_success(child_pid[0])

    assert outcome == b"child-successor-rejected"
    assert successor.consume(lambda value: value) == "payload:transitioned"


def test_multiprocessing_pickler_cannot_transport_capability() -> None:
    cap = issue("payload")

    with pytest.raises(TypeError, match="cannot be serialized"):
        multiprocessing.reduction.ForkingPickler.dumps(cap)

    assert cap.consume(lambda value: value) == "payload"
