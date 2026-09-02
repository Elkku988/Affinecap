"""A deployment approval handed from a verifier to a worker.

The backend is stateful but simulated. The capability permits at most one
admission to it; it does not make a real deployment an exactly-once effect.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256

from affinecap import Capability, CapabilityConsumedError, issue


@dataclass(frozen=True)
class Artifact:
    name: str
    contents: bytes

    @property
    def digest(self) -> str:
        return sha256(self.contents).hexdigest()


class SimulatedDeploymentBackend:
    """Record simulated effects owned by trusted application code."""

    def __init__(self) -> None:
        self.deployment_log: list[str] = []

    def deploy(self, artifact: Artifact, environment: str) -> str:
        receipt = f"deployed {artifact.name}@{artifact.digest[:12]} to {environment}"
        self.deployment_log.append(receipt)
        return receipt


DeploymentAction = Callable[[], str]


def approve_deployment(
    artifact: Artifact,
    *,
    approved_digest: str,
    environment: str,
    backend: SimulatedDeploymentBackend,
) -> Capability[DeploymentAction]:
    """Validate first, then place the simulated privileged action behind a handle."""

    if artifact.digest != approved_digest:
        raise ValueError("artifact digest was not approved")

    # The action closes over backend authority. The caller receives the
    # capability, not a second direct reference to the action.
    return issue(
        value=lambda: backend.deploy(artifact, environment),
        label=f"{artifact.name} approved for {environment}",
    )


def exercise_deployment_approval(
    approval: Capability[DeploymentAction],
) -> str:
    """Admit one caller to the simulated backend through this handle."""

    return approval.consume(lambda action: action())


def main() -> None:
    artifact = Artifact("payments", b"release artifact bytes")

    # In a real workflow this arrives from a separately authenticated release
    # manifest, not from the Artifact object being checked.
    approved_digest_from_manifest = (
        "1d2fb4429ec3072ed09844b433cfdd6fd7a2d21c830a164dbf5fbca3216342ba"
    )
    backend = SimulatedDeploymentBackend()
    approver_cap = approve_deployment(
        artifact,
        approved_digest=approved_digest_from_manifest,
        environment="production",
        backend=backend,
    )

    # A logical custody handoff: the old handle is invalid before the worker acts.
    worker_cap = approver_cap.transfer(label="approver -> deployment worker")

    try:
        exercise_deployment_approval(approver_cap)
    except CapabilityConsumedError:
        print("approver handle is stale")

    print(exercise_deployment_approval(worker_cap))

    try:
        exercise_deployment_approval(worker_cap)
    except CapabilityConsumedError:
        print("deployment approval is spent")

    print(f"simulated backend records: {len(backend.deployment_log)}")


if __name__ == "__main__":
    main()
