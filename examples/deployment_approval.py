"""A deployment approval handed from a verifier to a worker."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from affinecap import Capability, CapabilityConsumedError, issue


@dataclass(frozen=True)
class Artifact:
    name: str
    digest: str


class DeploymentBackend:
    """Represents credentials and effects owned by trusted application code."""

    def deploy(self, artifact: Artifact, environment: str) -> str:
        return f"deployed {artifact.name}@{artifact.digest[:12]} to {environment}"


DeploymentAction = Callable[[], str]


def approve_deployment(
    artifact: Artifact,
    *,
    expected_digest: str,
    environment: str,
    backend: DeploymentBackend,
) -> Capability[DeploymentAction]:
    """Validate first, then place the privileged action behind one handle."""

    if artifact.digest != expected_digest:
        raise ValueError("artifact digest was not approved")

    # The action closes over backend authority. The caller receives the
    # capability, not a second direct reference to the action.
    return issue(
        lambda: backend.deploy(artifact, environment),
        label=f"{artifact.name} approved for {environment}",
    )


def deploy_once(approval: Capability[DeploymentAction]) -> str:
    return approval.consume(lambda action: action())


artifact = Artifact("payments", "4f9f2cab703ad3a5473cec08316a2931")
approver_cap = approve_deployment(
    artifact,
    expected_digest=artifact.digest,
    environment="production",
    backend=DeploymentBackend(),
)

# A logical custody handoff: the old handle is invalid before the worker acts.
worker_cap = approver_cap.transfer(label="approver -> deployment worker")

try:
    deploy_once(approver_cap)
except CapabilityConsumedError:
    print("approver handle is stale")

print(deploy_once(worker_cap))

try:
    deploy_once(worker_cap)
except CapabilityConsumedError:
    print("deployment approval is spent")
