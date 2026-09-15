# Testplan — OSAC-1435 VMaaS Networking

## Overview

- **Feature:** OSAC-1435 — VMaaS Networking: Single Interface, Optional
  Attachments, and Auto External Access
- **Source design:** [design.md](design.md)
- **Shared contract:** [Unified Networking test plan](../OSAC-1433-unified-networking/testplan.md)
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
| Missing/empty list | Default Subnet; effective ACL is inherited from the Subnet |
| Only Subnet | Preserve Subnet; effective ACL is inherited from the Subnet |
| NetworkACL inside attachment | Reject; ACL association belongs to the NetworkACL resource |
| Complete entry | Preserve the supported Subnet and primary fields |
| Invalid explicit reference | Reject; do not repair with defaults |

##### Expected results

- Catalog/Template resolution occurs before tenant defaults.
- Subnet is Ready, same scope, same VN, and IPv4 before ComputeInstance
  persistence; its effective NetworkACL must also be Ready.
- A missing/Pending/Failed default blocks creation.

#### TC-R2-02: K8s-manager capability gates VM creation

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Expected results

- K8s-only VM placement succeeds when the manager advertises VM support.
- Fabric-only/BM-only deployment rejects VM creation before persistence.
- EVPN or other prerequisite-gated manager accepts the VM only when Subnet,
  namespace/CUDN, and manager readiness checks pass.
- VMaaS does not require a Fabric Manager when the K8s-only capability is
  complete.

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
- Auto-created ExternalIP and ExternalIPAttachment resources carry
  `osac.openshift.io/auto-created: "true"`; the ExternalIP also carries
  `osac.openshift.io/auto-created-for: <compute-instance-id>` for orphan
  cleanup.
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
- Transient cleanup retries through the VM finalizer. Permanent cleanup
  follows the documented orphan/manual-cleanup path without duplicate IPs or
  attachments.

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

- Auto-created attachment is deleted before auto-created ExternalIP.
- Manually created ExternalIP resources remain tenant-managed.
- Shared default VN/Subnet/NetworkACL are not deleted with the VM.
- Restart or transient cleanup failure does not leak duplicate children.

### R6: Unsupported VM networking

#### TC-R6-01: Future or invalid VM networking is rejected

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated where user-visible |

##### Cases

- multi-interface/multi-NIC VM;
- explicit false primary;
- cross-tenant, cross-VN, non-Ready, IPv6, or fabric-only Subnet;
- tenant-selected implementation strategy, CUDN namespace, MAC, or IPAM;
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

- Locked, editable, empty, and default policies resolve before tenant default
  networking.
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
Verify omitted and explicit Subnet values preserve the shared defaulting
matrix, and that a NetworkACL key inside the attachment is rejected.

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
- One-interface success, defaults, auto ExternalIP, cleanup, and
  K8s-only capability have E2E coverage.
- Every user-visible unsupported VM networking path has a negative E2E test.
