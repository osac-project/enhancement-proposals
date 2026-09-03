# Clarification Log - OSAC-4884

## Status

- Rounds completed: 4
- Open gaps: 0
- Exit criteria met: Yes

## Round 1 - Scope and observable behavior

### R1.Q1: Direct users of attach and detach

Who directly requests volume attach and detach in milestone 0.3? The current Volume API is private and the named consumers are the CSI driver and BMaaS workflows.

#### Answer

Expose attach and detach through the public API so users can invoke them, while also supporting system components such as the OSAC CSI driver. Public exposure of the Volume API is already proposed in [osac#743](https://github.com/osac-project/osac/pull/743/).

#### Impact

The PRD must cover direct public-user workflows in addition to system integration flows. Public API exposure is a dependency that must be accounted for rather than treating this solely as an internal capability.

#### Decision (D1)

Volume attach and detach are public user capabilities and are also available to authorized system components.

---

### R1.Q2: Service scope

Which workload flows must use this capability in milestone 0.3?

#### Answer

BMaaS and CSI flows.

#### Impact

Requirements and acceptance criteria must cover direct BMaaS volume attachment and migration of the existing OSAC CSI driver flow.

#### Decision (D2)

Milestone 0.3 covers BMaaS and OSAC CSI driver flows.

---

### R1.Q3: Concurrent attachments

What should happen when the same volume is requested for more than one workload target at once?

#### Answer

Honor the volume access capability and storage backend capability.

#### Impact

The PRD must require concurrent attachment requests to be accepted or rejected consistently with the volume's advertised access and backend capabilities.

#### Decision (D3)

Concurrent attachments are allowed only when supported by the volume access capability and storage backend.

---

### R1.Q4: Progress visibility

If backend attachment takes time, what observable behavior is required?

#### Answer

Callers must have observable progress.

#### Impact

Requirements must let callers distinguish pending, successful, and failed attach or detach outcomes without prescribing the underlying implementation.

#### Decision (D4)

Attach and detach expose pending, successful, and failed outcomes to callers.

---

### R1.Q5: Storage that does not require attachment

Some storage does not require a controller-side attach operation. How should attach and detach appear to callers for those volumes?

#### Answer

Succeed as a no-op.

#### Impact

Acceptance criteria must cover successful, idempotent attach and detach for storage whose capabilities require no backend attachment action.

#### Decision (D5)

Attach and detach succeed as no-ops for storage that does not require controller-side attachment.

---

## Round 2 - Interfaces, authorization, and lifecycle

### R2.Q1: Public interface coverage

With UI explicitly out of scope, which public interfaces must support attach and detach in milestone 0.3?

#### Answer

Public gRPC and REST interfaces.

#### Impact

The PRD must require equivalent user-observable attach and detach behavior through public gRPC and REST. Dedicated CLI and UI work are not required by this feature.

#### Decision (D6)

Milestone 0.3 exposes attach and detach through public gRPC and REST, without dedicated CLI or UI work.

---

### R2.Q2: Authorization boundary

What authorization boundary should users observe?

#### Answer

Tenant isolation with provider-level access.

#### Impact

Tenant users and tenant admins must be limited to authorized volumes and targets in their tenant, while authorized provider admins retain cross-tenant administrative authority. System components must use appropriately authorized identities.

#### Decision (D7)

Attach and detach enforce tenant isolation for tenant roles and permit cross-tenant operations only for authorized provider administrators.

---

### R2.Q3: Repeated requests

How should repeated requests for the same desired attachment state behave?

#### Answer

Return idempotent success.

#### Impact

Acceptance criteria must cover repeated attach to the same target and repeated detach when no attachment exists without producing duplicate work or user-visible conflicts.

#### Decision (D8)

Repeated requests for an already-satisfied attach or detach state succeed idempotently.

---

### R2.Q4: Backend failures

What should callers experience after a transient backend failure?

#### Answer

Automatic retry with observable progress; terminal failures remain visible.

#### Impact

The PRD must distinguish recoverable progress from terminal failure and require callers to observe the current outcome without repeatedly resubmitting transient failures.

#### Decision (D9)

Transient backend failures are retried automatically while progress remains observable; non-recoverable failures are reported as terminal outcomes.

---

### R2.Q5: Deletion behavior

What should happen when a workload target or volume is deleted while an attachment exists?

#### Answer

Deleting a workload target cleans up its attachment. Deleting a volume is blocked until the volume is detached.

#### Impact

Requirements must cover automatic attachment cleanup during target deletion and protect attached volumes from deletion until detach has completed.

#### Decision (D10)

Workload target deletion cleans up associated attachments, while volume deletion cannot complete until all attachments are removed.

---

## Round 3 - Dependencies, compatibility, and CSI alignment

### R3.Q1: Public Volume API dependency

How should this feature relate to `osac#743`, which exposes the Volume API publicly?

#### Answer

Treat `osac#743` as a required prerequisite.

#### Impact

The PRD must identify public Volume API availability as a dependency and must not duplicate the prerequisite's scope.

#### Decision (D11)

[osac#743](https://github.com/osac-project/osac/pull/743/) is a prerequisite for delivering public attach and detach operations.

---

### R3.Q2: Valid workload targets

Which workload targets are valid in milestone 0.3?

#### Answer

All OSAC compute services.

#### Impact

The attachment capability must be able to represent targets across BMaaS, VMaaS, and CaaS rather than accepting arbitrary backend host identifiers. The exact required service workflows still need reconciliation with D2, which named only BMaaS and CSI flows.

#### Decision (D12)

Valid attachment targets encompass OSAC-managed compute across BMaaS, VMaaS, and CaaS.

---

### R3.Q3: Forced detach

If normal detach cannot complete, should milestone 0.3 expose a force-detach capability?

#### Answer

No force-detach capability.

#### Impact

Terminal detach failures remain visible and require operator recovery; the PRD must not promise a user-facing bypass that could hide uncertain backend state.

#### Decision (D13)

Milestone 0.3 does not expose force detach.

---

### R3.Q4: Existing CSI-managed volumes

What compatibility is required when the CSI driver migrates to the Volume API path?

#### Answer

The migration must be transparent.

#### Impact

Existing CSI-managed volumes and attachments must continue to work without recreation or user action when future attachment operations move through the Volume API.

#### Decision (D14)

Existing CSI-managed volumes remain usable across migration with no recreation or user action.

---

### R3.Q5: Responsiveness and timeouts

What timing contract should users receive for potentially slow backend operations?

#### Answer

Use a CSI-aligned contract: no fixed final-completion SLA; requests honor caller deadlines, timed-out operations remain safely retriable, and pending, successful, and failed progress remains observable while completion time depends on the backend.

The decision is informed by the [CSI specification](https://github.com/container-storage-interface/spec/blob/master/spec.md), which permits RPC timeouts and retries and requires idempotency to make retries safe, and the [Kubernetes CSI external-attacher guidance](https://github.com/kubernetes-csi/external-attacher/blob/master/README.md#csi-error-and-timeout-handling), which uses configurable per-call timeouts and exponential-backoff retries because backend timing varies.

#### Impact

The PRD must define deadline, retry-safety, and progress-visibility outcomes without imposing a backend-independent completion duration.

#### Decision (D15)

Attach and detach honor caller deadlines, remain safely idempotent after timeout, and expose ongoing and final outcomes; final completion time has no fixed cross-backend SLA.

---

## Round 4 - Cross-service delivery and acceptance coverage

### R4.Q1: Service delivery scope

Does milestone 0.3 need complete user-visible attach and detach workflows for BMaaS, VMaaS, and CaaS, plus CSI-driver migration, or only a generic API that can represent all targets while BMaaS and CSI are the delivered integrations?

#### Answer

Deliver all OSAC compute services in milestone 0.3.

#### Impact

The PRD must include observable attachment outcomes for BMaaS, VMaaS, and CaaS and cannot limit delivery to BMaaS and CSI integration alone. This answer explicitly expands the earlier service boundary in D2.

#### Decision (D16)

Milestone 0.3 delivers volume attachment for BMaaS, VMaaS, and CaaS, superseding D2's narrower BMaaS-and-CSI service scope while retaining CSI-driver migration as required work.

---

### R4.Q2: CaaS attachment behavior

How is CaaS attachment exposed in milestone 0.3?

#### Answer

CaaS uses the regular CSI flow. The OSAC CSI driver calls the Volume API to attach a volume for the workload node.

#### Impact

CaaS does not need a separate public cluster-level attachment workflow. Its user-visible outcome is delivered through the standard Kubernetes storage flow, while the OSAC CSI driver uses the same Volume API attachment capability as other consumers.

#### Decision (D17)

CaaS volume attachment is exercised through the standard CSI flow, with the OSAC CSI driver requesting attachment through the Volume API.

---

### R4.Q3: End-to-end acceptance coverage

Which end-to-end service flows must acceptance testing demonstrate?

#### Answer

One representative flow.

#### Impact

The PRD must require one backend-neutral end-to-end attach and detach flow that demonstrates the public contract, while not requiring a separate full E2E scenario for each OSAC compute service.

#### Decision (D18)

End-to-end acceptance requires one representative attach and detach flow rather than separate E2E coverage for every service.

---

## Remaining Gaps

None.
