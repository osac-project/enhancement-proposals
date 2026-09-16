# Testplan — OSAC-1435 VMaaS Networking

## Overview

- **Feature:** OSAC-1435 — VMaaS Networking: Single Interface, Optional
  Attachments, and Auto External Access
- **Source design:** [design.md](design.md)
- **Shared contract:** [Unified Networking test plan](../OSAC-1433-unified-networking/testplan.md)
- **Deployment support boundary:** [Unified Networking deployment support
  boundary](../OSAC-1433-unified-networking/design.md#deployment-support-boundary);
  VMaaS is supported only in connected deployments, not air-gapped or
  disconnected deployments.
- **Inherited creation rule:** VM admission follows the [strict dependency-ready
  creation contract](../OSAC-1433-unified-networking/design.md#strict-dependency-ready-creation); a VM cannot be created to wait for a Pending network dependency. Only OSAC-owned automatic ExternalIP children may be Pending after pool readiness and capacity validation.
- **Current support boundary:** `network_attachments` remains a list
  but accepts zero or one entry. Multi-interface VM support is not supported.
- **API shape:** the resource-specific `ComputeNetworkAttachment` replaces the
  shared attachment format before release; no dual-field compatibility or
  conversion path is supported.

## Execution strategy

- **Unit:** fulfillment-service defaulting/reference validators,
  Compute controller helpers, template input validation, feedback/status
  parsing, and ExternalIP transaction logic.
- **Integration:** real PostgreSQL, public/private/Catalog handlers, Compute
  CRD/CEL validation, osac-operator, fake K8s manager/KubeVirt, and
  controllable VMI/manager status.
- **E2E:** connected VMaaS deployment with real KubeVirt/CUDN placement,
  DHCP/IP discovery, ExternalIP/DNAT, and cleanup.

## Test cases

### R1: Single-interface request contract

#### TC-R1-01: Zero or one canonical attachment is accepted

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Cases

- canonical field omitted;
- canonical field explicitly empty;
- one entry with omitted `primary`;
- one entry with `primary: true`.

##### Expected results

- The request is accepted according to defaulting semantics.
- The resolved resource contains exactly one attachment.
- The sole attachment is implicitly primary.

#### TC-R1-02: Any multi-entry list and any explicit false-primary input are rejected

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated |

##### Steps

1. Submit two canonical entries.
2. Submit one entry with explicit `primary: false`.
3. Repeat through public API, private API, Catalog, REST, and direct CR.

##### Expected results

- Each request is rejected before reference lookup, defaulting, capacity
  reservation, persistence, or template dispatch.
- Error identifies `spec.network_attachments` or the precise primary
  field.
- Unknown nested attachment fields, malformed typed Subnet
  references, and malformed `primary` presence/encoding are rejected by the
  request-shape layer with no normalization or persistence.

### R2: Attachment defaulting and readiness

#### TC-R2-01: VM attachment fields resolve independently

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Matrix

| Input | Expected result |
|---|---|
| Missing/empty list | Default Subnet and tenant default SecurityGroup; effective ACL is inherited from the Subnet |
| Only Subnet in the tenant default VirtualNetwork | Preserve Subnet; default only SecurityGroup when omitted; effective ACL is inherited from the Subnet |
| Subnet in a non-default VirtualNetwork with SecurityGroup omitted | Reject with `InvalidArgument`; do not apply the tenant default group from another VirtualNetwork |
| One entry with an explicitly empty `security_groups` list | Treat the empty list as missing; preserve a default-VN Subnet and resolve the tenant default SecurityGroup; reject with `InvalidArgument` for a non-default-VN Subnet without a compatible group |
| Only compatible SecurityGroup list, Subnet omitted | Preserve groups; default only the Subnet when the groups belong to the tenant default VirtualNetwork |
| SecurityGroup list from a non-default VirtualNetwork, Subnet omitted | `InvalidArgument`; the default Subnet and explicit groups would be in different VirtualNetworks; no VM is persisted |
| Subnet and SecurityGroup list | Preserve both; effective ACL is inherited from the Subnet |
| NetworkACL inside attachment | Reject; ACL association belongs to the NetworkACL resource |
| Complete entry | Preserve the supported Subnet and primary fields |
| Invalid explicit reference | Reject; do not repair with defaults |
| Selected Subnet has no effective NetworkACL | Reject with `FailedPrecondition`; do not use the deployment baseline or persist the VM |

##### Expected results

- Catalog/Template resolution occurs before tenant defaults.
- Subnet is Ready, same scope, same VN, and IPv4 before ComputeInstance
  persistence. Every explicit/default SecurityGroup is unique, Ready, same
  scope, and in the same VN. The effective NetworkACL must also be Ready.
- A missing/Pending/Failed required default blocks creation. Every workload
  uses the shared SecurityGroup and NetworkACL contract.
- After a Ready NetworkACL is associated with the previously unprotected
  Subnet, the same VM request succeeds and inherits that ACL.

#### TC-R2-02: Complete manager policy contract gates VM creation

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Cases

- Configure a complete K8s-only, Fabric-only, and combined manager profile.
- Configure a temporary successful no-op policy AAP role and exercise VM
  creation with the normal default and explicit policy references.

##### Expected results

- VM placement succeeds through the complete selected manager profile.
- Native Kubernetes NetworkPolicy alone is insufficient for either OSAC policy
  contract. Complete adapters pass the same dispatch and readiness checks as
  Fabric-manager adapters.
- One configured manager receives one policy target; two configured managers
  receive two targets and creation/readiness waits for both.
- A successful development no-op still follows the normal target/job path.
- EVPN or other prerequisite-gated manager accepts the VM only when Subnet,
  namespace/CUDN, and manager readiness checks pass.

#### TC-R2-03: SecurityGroup rule and attachment validation

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated |

##### Cases

- Create a tenant SecurityGroup with one valid allow rule and attach it to a
  VM.
- Create a tenant SecurityGroup with zero rules; attempt to create and verify
  rejection. Create the auto-created default SecurityGroup with zero rules and
  verify it is accepted and means deny.
- Attempt an action field, deny rule, invalid direction/protocol/port/CIDR,
  duplicate group reference, duplicate rule, cross-tenant group, wrong-VN
  group, and non-Ready group.
- Verify omitted groups receive the default group, while an
  explicit list is not replaced or augmented.

##### Expected results

- Invalid rules and references fail before persistence or VM provisioning.
- A VM request with both SG and ACL policy succeeds only when both policy
  layers are Ready; a deny at either layer blocks the flow.

#### TC-R2-04: VM networking uses the shared per-resource dispatch plan

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Cases

- K8s-only manager using the current profile and its entrypoint
  matrix from the [K8s-only manager test plan](../OSAC-1433-k8s-only-k8s-manager/testplan.md).
- Combined deployment with both complete managers.
- A manager registration with a partial resource, policy, scope, or service
  map, or without the complete manager entrypoints.

##### Expected results

- VMaaS can create a VM in K8s-only, Fabric-only, or combined mode through the
  complete manager profile; no Fabric fallback is required or called.
- Shared VirtualNetwork, Subnet, policy, and ExternalIP operations follow the
  unified target matrix. One configured manager creates one target; two
  configured managers create two targets and VM networking is usable only
  after both are Ready.
- The current K8s-only profile's ExternalIP and NATGateway boundary is covered
  by the [K8s-only manager test plan](../OSAC-1433-k8s-only-k8s-manager/testplan.md);
  MetalLB address allocation alone does not count as NAT support.
- Every admitted manager target receives the normal operation-specific job.
  An incomplete manager registration is rejected during provider
  configuration; an unfinished admitted operation may complete through the
  successful no-op AAP role. A tenant cannot provide a manager name or
  dispatch annotation to override the plan.
- ExternalIPAttachment waits for the ExternalIP and VM IP prerequisites, then
  dispatches to exactly the selected manager targets; it becomes Ready only
  after all selected DNAT implementations succeed.

#### TC-R2-05: Non-Ready dependencies reject VM admission

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection and retry | critical | automated |

##### Cases

- Hold the selected Subnet `Pending`, `Failed`, and `Deleting`; submit VM
  creates with omitted, partial, and complete `network_attachments`.
- Hold an explicit/default SecurityGroup or effective NetworkACL non-Ready.
- Make the complete manager registration or required placement prerequisite
  unavailable after request resolution but before the transaction commits.
- Repeat through direct, Catalog/Template, REST, and direct-CR paths; then
  advance each dependency to `Ready` and retry.

##### Expected results

- Every blocked create returns `FailedPrecondition` identifying the exact
  attachment/profile field, dependency identity, observed state, required
  state, and wait-and-retry remediation.
- No ComputeInstance, auto-child, capacity reservation, CR, KubeVirt object,
  or backend job is created for a rejected request.
- A VM may be `Pending` only after its own valid admission while its manager
  provisions it. Only the OSAC-owned automatic ExternalIP and attachment may
  be Pending as children; a VM never waits in the API for a Pending Subnet or
  policy dependency.
- After the dependency is Ready, retry succeeds exactly once and dispatches
  the VM operation once.

### R3: Single-interface provisioning and status

#### TC-R3-01: Template creates exactly one KubeVirt interface

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Steps

1. Create a valid ComputeInstance with one resolved attachment.
2. Inspect the private ComputeInstance CR and verify that public
   `spec.network_attachments` was converted to the CRD's
   `spec.networkAttachments` resource-specific message, with no legacy shared
   attachment field.
3. Observe the operator/template input and inspect the resulting
   VirtualMachine/VMI.

##### Expected results

- One `l2bridge` interface is created in the selected CUDN namespace.
- The CRD/template receives exactly the resolved typed Subnet reference from
  the API-to-CRD conversion and obtains the effective ACL from the Subnet.
- No `move_network_attachment` operation is invoked.
- A malformed CR with multiple entries fails closed rather than using the
  first entry.

#### TC-R3-02: IP feedback publishes only a valid sole status entry

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | high | automated |

##### Cases

- canonical IPv4 in the selected Subnet;
- missing status while VMI is starting;
- wrong NAD/subnet;
- IPv6 or malformed IP;
- duplicate or multiple VMI interfaces.

##### Expected results

- Only the valid sole interface produces a Ready network status.
- The status entry contains the resolved typed Subnet reference and
  `primary=true` for the sole attachment.
- Invalid or ambiguous status causes retry/failure and never mutates spec or
  reports a false Ready IP.

#### TC-R3-03: VM provisioning and template failures fail closed

| Test type | Priority | Automation |
|---|---|---|
| Integration, E2E recovery | high | automated |

##### Cases

- Subnet has no target namespace or its CUDN is not Ready;
- AAP/template execution failure;
- controller restart during namespace resolution or template dispatch.

##### Expected results

- The ComputeInstance remains Pending or enters Failed with the documented
  condition and job reference; it is never reported Ready without a valid
  resolved attachment and VM interface.
- Reconciliation retries after the dependency recovers without creating a
  second VM, interface, or backend operation.
- A controller restart resumes the existing operation idempotently.

### R4: Automatic ExternalIP

#### TC-R4-01: Automatic VM external access succeeds

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Steps

1. Create a VM with `auto_external_ip_attachment=true`.
2. Verify one IPv4 ExternalIP and Pending ExternalIPAttachment are created
   atomically.
3. Complete ExternalIP allocation and VM IP discovery independently.
4. Verify DNAT and inbound connectivity.

##### Expected results

- Attachment target is the VM and endpoint is `UNSPECIFIED`.
- Auto-created ExternalIP and ExternalIPAttachment resources carry the
  canonical `osac.openshift.io/auto-created: "true"` marker and an exact
  immutable ComputeInstance owner relationship. The owner relationship—not a
  label—is what authorizes cleanup.
- DNAT dispatch waits for both prerequisites.
- DNAT uses the discovered sole interface IP, not a tenant-supplied IP.

#### TC-R4-02: Automatic allocation failure rolls back

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated |

##### Steps

1. Exhaust every Ready IPv4 pool and submit an otherwise valid VM create with
   `auto_external_ip_attachment=true`.
2. Repeat with an invalid resolved attachment and with a failure injected after
   capacity reservation.
3. Inspect the VM, ExternalIP, ExternalIPAttachment, job, and pool capacity.

##### Expected results

- Pool selection uses greatest capacity and deterministic ties.
- Create-time exhaustion or validation failure leaves no VM, ExternalIP,
  ExternalIPAttachment, job, or capacity reservation.
- Cleanup retries attachment before ExternalIP.

#### TC-R4-03: Asynchronous ExternalIP and DNAT failures preserve VM state

| Test type | Priority | Automation |
|---|---|---|
| Integration, E2E recovery | critical | automated |

##### Cases

- ExternalIP allocation enters `Failed` after the VM and Pending children are
  persisted;
- ExternalIPAttachment/DNAT dispatch fails after the VM is provisioned;
- transient and permanent auto-created-resource cleanup failure.

##### Expected results

- ExternalIP failure leaves the VM Pending/functional without inbound
  external access; the VM is not falsely reported as having external access.
- Attachment failure does not activate DNAT, while the VM remains usable.
- Transient cleanup retries through the VM finalizer. Permanent cleanup keeps
  the VM `Deleting` and retains its finalizer; the controller does not remove
  the finalizer to create an orphan or authorize cleanup from a label alone.
- Cleanup requires the canonical auto-created marker and exact immutable VM
  owner, and deletes the owned attachment before the owned ExternalIP.

### R5: Immutability and cleanup

#### TC-R5-01: Network-owned changes are rejected after create

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated |

##### Cases

- attachment list/cardinality/order;
- Subnet;
- the effective NetworkACL inherited from the Subnet;
- primary;
- auto-external switch;
- nested field-mask and direct CR mutations.

##### Expected results

- All are rejected. Controller status, conditions, discovered IP, and
  finalizers remain writable by controllers.
- Delete/recreate is required for a network change.

#### TC-R5-02: Parent deletion follows ownership rules

| Test type | Priority | Automation |
|---|---|---|
| Integration, E2E | high | automated |

##### Expected results

- Auto-created attachment is deleted before auto-created ExternalIP and before
  the VM finalizer completes. Ownership requires the canonical marker and
  exact immutable VM owner; a label or target reference alone is insufficient.
- A tenant-created ExternalIPAttachment targeting the VM blocks VM deletion;
  it is never detached, retargeted, or deleted by the VM controller.
- Shared default VN/Subnet, tenant SecurityGroup and NetworkACL when present, and
  tenant-created networking resources are not deleted with the VM; the
  ExternalIPPool is never cascaded.
- Restart or transient cleanup failure does not leak duplicate children, and
  permanent cleanup failure retains the VM finalizer and leaves it `Deleting`.

#### TC-R5-03: VM dependency guards and NetworkACL associations

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated |

##### Cases

- Delete a Subnet referenced by the VM's sole attachment and by its effective
  NetworkACL. Verify the VM attachment and ACL are reported as direct blockers,
  including a child already `Deleting` but not archived; the SecurityGroup is
  validated as part of the VM attachment and is not a direct Subnet blocker.
- Delete the VirtualNetwork while its Subnet, SecurityGroup, NetworkACL, or supported
  NATGateway exists. Verify all direct blockers are returned and no resource is
  detached or deleted as a side effect.
- Attempt Subnet and VirtualNetwork deletion while a NetworkACL association
  exists. Verify the ACL is reported as a blocker with its identity and
  relationship. Delete the ACL, verify only the ACL/rules are removed and the
  Subnets and VirtualNetwork are unchanged, then retry the parent deletions
  and verify the ACL is no longer reported as a blocker.
- Run VM deletion concurrently with creation of a tenant attachment. Verify
  either the reference or the delete wins atomically, with no dangling
  attachment or deleted target.

##### Expected results

- Every rejected delete returns `FAILED_PRECONDITION` with blocker kind,
  ID/name, relationship field, and required remediation, and leaves the VM,
  networking resources, backend state, finalizers, and capacity unchanged.
- Deletion never mutates the immutable zero-or-one VM attachment list to
  bypass a dependency guard.

### R6: Unsupported VM networking

#### TC-R6-01: Future or invalid VM networking is rejected

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated where user-visible |

##### Cases

- multi-interface/multi-NIC VM;
- explicit false primary;
- cross-tenant, cross-VN, non-Ready, IPv6, or fabric-only Subnet;
- tenant-selected manager, dispatch annotation, CUDN namespace, MAC, or IPAM;
- arbitrary ExternalIP target IP;
- update/patch/replace;
- BM/CaaS port-move behavior for VM;
- static host-side networking.

##### Expected results

- Unsupported behavior is rejected or fails closed and no partial resource is
  persisted.

### R7: Catalog parity

#### TC-R7-01: Direct and Catalog creation produce the same contract

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | high | automated |

##### Expected results

- Execute the shared [TC-R4-04 precedence matrix](../OSAC-1433-unified-networking/testplan.md#tc-r4-04-catalog-template-private-and-direct-default-precedence-match)
  for VM direct API and Catalog materialization: a locked field rejects a
  conflicting tenant value; an editable Catalog default is overridden by an
  explicit valid tenant value; an omitted tenant value uses the Catalog
  default, then the Template default, then the tenant default; and an explicit
  invalid or non-Ready value is rejected rather than repaired.
- Both direct and Catalog creates enforce zero-or-one and primary rules.
- Shared Catalog Items cannot lock/default tenant-local references.
- Catalog updates do not mutate existing VM network specs or Catalog metadata.

### R8: VM CLI contract

#### TC-R8-01: CLI mapping, defaulting, and rejection

**Unit:** Verify one optional `--network-attachment` maps to repeated
`spec.network_attachments` containing `ComputeNetworkAttachment`. Verify
repeated attachment options, the deprecated plural `--network-attachments`
option, `interface=...`, explicit `primary=false`, unknown keys, invalid
CIDRs, and malformed typed references are rejected.
Verify omitted and explicit Subnet and SecurityGroup values preserve the shared
defaulting matrix, and that a NetworkACL key inside the attachment is rejected.

**Integration:** Run CLI-created VM requests through the same public and
private validation paths as direct API requests. Verify typed local-reference
serialization, readiness errors, field paths, rollback, and
`--external-ip-attachment` mapping. Run both flag states: when present it
sets the create-time switch to true and starts automatic external access; when
omitted it sets false, creates no automatic ExternalIP/attachment, and does
not consume pool capacity. Verify the switch cannot be updated.

**E2E:** Create a VM with one explicit attachment, with partial attachment
defaulting, and with no attachment, both with and without
`--external-ip-attachment`. Inspect the resolved plural field, create-time
switch, automatic ExternalIP state, and status. Attempt a second attachment,
the deprecated plural `--network-attachments` option, an update/patch, and an
unsupported multi-NIC value; verify rejection and no side effect.

## Graduation gate

- Every VMaaS validation rule has unit or integration coverage.
- One-interface success, defaults, SecurityGroup/NetworkACL policy behavior,
  auto ExternalIP, cleanup, no-op provider operations, and invalid-policy paths have
  E2E coverage.
- Every user-visible unsupported VM networking path has a negative E2E test.
