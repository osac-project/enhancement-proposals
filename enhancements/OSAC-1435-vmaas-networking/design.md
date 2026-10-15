---
title: vmaas-networking
authors:
  - dmanor@redhat.com
creation-date: 2026-07-08
last-updated: 2026-10-13
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1435
prd: "prd.md"
see-also:
  - "Unified Networking: /enhancements/OSAC-1433-unified-networking"
  - "Default Networking: /enhancements/OSAC-1433-default-networking"
  - "Network Manager Integration Contract: /enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md"
replaces:
  - N/A
superseded-by:
  - N/A
---

# VMaaS Networking — Optional Attachments and Auto External Access

## Contents

- [Summary](#summary)
- [Motivation](#motivation)
- [Proposal](#proposal)
  - [Working with provider-supplied managers](#working-with-provider-supplied-managers)
  - [VM placement and interface ownership](#vm-placement-and-interface-ownership)
  - [Workflow Description](#workflow-description)
  - [API contract](#api-contract)
  - [Component behavior and constraints](#component-behavior-and-constraints)
- [Security Considerations](#security-considerations)
- [Failure Handling and Recovery](#failure-handling-and-recovery)
- [RBAC and Tenancy](#rbac-and-tenancy)
- [Observability and Monitoring](#observability-and-monitoring)
- [Risks and Mitigations](#risks-and-mitigations)
- [Drawbacks](#drawbacks)
- [Provider Networking Disabled](#provider-networking-disabled)
- [Alternatives Considered](#alternatives-considered)
- [Open Questions](#open-questions)
- [Test Plan](#test-plan)
- [Graduation Criteria](#graduation-criteria)
- [Upgrade and Downgrade Strategy](#upgrade-and-downgrade-strategy)
- [Version Skew Strategy](#version-skew-strategy)
- [Support Procedures](#support-procedures)
- [Infrastructure Needed](#infrastructure-needed)

This enhancement extends the unified networking API to support VMaaS-specific requirements: a single ComputeInstance network attachment with an implicit primary/default route, optional network attachments with tenant defaults, and auto-provisioned external access (ExternalIP). The repeated attachment field is retained for API compatibility and is validated to contain at most one entry.

## Summary

This enhancement is a service-specific extension of the [Unified Networking EP](/enhancements/OSAC-1433-unified-networking/design.md), providing the detailed per-service flow for this service type. The Unified Networking EP defines NetworkClass and the shared networking resource semantics and hierarchy. The Network Manager Integration Contract defines manager registration and dispatch. This document defines how VMaaS consumes those shared contracts.

This integration targets VMaaS's existing KubeVirt runtime. VMaaS controllers
create and manage KubeVirt `VirtualMachine` resources and observe the VMI
created by KubeVirt: the VM is prepared while halted, its network interface
is applied before first start, and its assigned address is observed from VMI
status.
Provider-selected Kubernetes Managers vary how they realize networking on
that VM. Manager modularity applies to provider networking implementations;
VM lifecycle and IP observation remain KubeVirt-specific. Supporting another
VM runtime requires a separate VMaaS runtime integration and updates to this
service-specific flow.

VMaaS inherits the [Unified Networking deployment support
boundary](/enhancements/OSAC-1433-unified-networking/design.md#deployment-support-boundary):
VM networking supports connected deployments only and does not add air-gapped
or disconnected networking support.

VMaaS networking also inherits the [Unified Networking hub support
boundary](/enhancements/OSAC-1433-unified-networking/design.md#networking-hub-support-boundary):
OSAC networking supports exactly one provider-owned hub per deployment.
Multi-hub networking placement, cross-hub resource coordination, and
cross-hub network connectivity are unsupported. This boundary applies only to
the networking area and does not define hub behavior for other OSAC areas.
Multiple hosting/workload clusters remain supported where a networking feature
explicitly specifies them.

ComputeInstance currently uses a `ComputeNetworkAttachment` message. This enhancement keeps the existing repeated attachment field optional (populating it with tenant defaults when omitted), enforces a maximum of one entry, and adds `auto_external_ip_attachment` to enable fully connected VMs in a single API call. VMaaS has no primary field: the sole attachment is implicitly the default route. See [PRD](prd.md) for detailed requirements.

The manager-backed resource flows and provider IP-discovery/readiness behavior
in this document describe the enabled mode. The feature-gated disabled behavior
is specified at the end of the Proposal section. API-level SecurityGroup rule
validation and reference checks remain active in disabled mode. OSAC submits no
provider operation to apply or remove SecurityGroup rules; rules already
programmed in the backend may continue to affect traffic until provider-side
cleanup. [User]

The [Network Manager Integration Contract](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md)
owns registration, task/input/result schemas, no-op requirements, overlapping
address spaces, stable API ownership, NetworkData, retries and shared cleanup.
The [internal request protocol](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#workload-attachment-policy-lifecycle)
defines attachment status and projection recovery. This design specifies the
service's handoffs and readiness gates, not another copy of those rules.

## Motivation

Each VM receives its tenant network attachment before its first start. The
workload template creates the VM halted without tenant network/interface
fields; the selected Kubernetes Manager applies those fields and SecurityGroup
policy through the target-only `SubnetAttachment`. VMaaS starts the VM only
after the request confirms the configuration is ready. OSAC publishes the
discovered address through the workload API. Optional external access follows
the shared allocation and attachment lifecycle.

### Goals

- Single-NIC support with an implicit primary attachment for the default gateway
- Resource-specific attachment message (`ComputeNetworkAttachment`); the sole attachment is implicitly primary
- Optional `network_attachments` field — populate with tenant defaults when omitted
- Auto ExternalIP attachment (`auto_external_ip_attachment`) for single-call inbound connectivity
- BM-only deployment validation to reject VM provisioning when no k8s_manager is available

### Non-Goals

- CaaS or BMaaS networking (this EP covers VMaaS only)
- Implementation of the shared manager dispatch contract, which is defined by the Network Manager Integration Contract.
- Building or selecting a particular Kubernetes Manager implementation; VMaaS uses the deployment-selected manager that conforms to the shared contract.
- A VM runtime abstraction or support for VM runtimes other than KubeVirt.

## Proposal

### Working with provider-supplied managers

The deployment selects its Fabric and Kubernetes Managers through NetworkClass.
Neither the tenant nor the VM template chooses a binding plugin or provider.
The same workload template works with any conforming selected Kubernetes
Manager for VMaaS's KubeVirt VM target. The workload template creates each VM
halted and without its tenant network/interface fields. The manager applies
those fields and the requested policy through the target-only
`SubnetAttachment` before VMaaS allows the VM to start. The manager contract
varies provider networking behavior; VMaaS lifecycle and status observation
continue to use KubeVirt resources.

| Phase | VMaaS responsibility | Provider-manager responsibility |
|---|---|---|
| Subnet preparation | Supply the supported hosting-cluster set to the Subnet lifecycle extension and wait for Subnet Ready. | Fabric creates the shared network once; Kubernetes realizes each required placement using stored Fabric outputs. Subnet Ready waits for all required placement stages. |
| VM prepare | Create the VM halted without tenant network/interface fields; capture its backend UID and placement. | The Subnet is already prepared; workload attachment has not started. |
| Attach | Create the internal request with the exact placement and target identity; wait for `NetworkAttachmentsReady=True`. | Kubernetes Manager adds only the requested network/interface fields to the halted VM and applies policy. |
| Start and observe | Apply the requested final run strategy only after attachment readiness; mirror real VMI IP feedback. | Keep the first VM boot gated on attachment readiness and expose the address through VMI status. |
| Delete | Complete external cleanup, stop the VM, wait for request cleanup, then remove compute/disks. | Kubernetes Manager removes attachment-owned fields and policy; shared Subnet cleanup waits for all consumers. |

The Kubernetes Manager prepares the Subnet's overlay network when it creates
the Subnet. For an individual VM, its `apply_subnet_attachment` task updates
the exact stopped VM and applies policy. The manager owns the target's
network/interface fields; VMaaS owns compute fields and run control. The
manager must finish and the request must report `NetworkAttachmentsReady=True`
before VMaaS starts the VM. [User]

### VM placement and interface ownership

OSAC owns workload placement; the Kubernetes Manager owns backend network
realization. The VMaaS host-placement resolver supplies its supported hosting
cluster IDs to the Subnet lifecycle extension. When several clusters are
supported, the Kubernetes `create_subnet` stage runs once for each cluster and
OSAC sets `target_cluster.id` to that cluster's stable ID. Each call has its
own durable manager stage. The Fabric stage still realizes the shared Subnet
once, and the Subnet becomes Ready only after every required cluster stage
succeeds. VMaaS chooses a VM host from the configured placement set only after
the Subnet is Ready. The operation journal retains each placement stage; this
integration state adds no cluster field to the tenant networking API.

When the supported set changes, OSAC prepares added placements before they
can receive VMs. It cleans a removed placement only after its workloads have
detached and no consumer remains. Subnet deletion cleans every placement whose
create stage may have started, even if the current resolver no longer returns
it, before the single Fabric cleanup.

The manager preserves tenant ownership metadata, and a conflicting existing
placement is an error. It may use any backend object or attachment mechanism
that fulfills the shared Subnet and manager contracts; backend names and
configuration remain manager-owned. For example, a KubeVirt implementation
may expose the Subnet through a namespaced NetworkAttachmentDefinition. The
manager cannot move the workload to another placement or return a replacement
target.
Deletion removes only its owned realization/namespace after all consumers
are gone. Names do not replace the existing stable API ownership and concrete backend-object UID checks. [User]

After the Subnet is Ready, the workload controller chooses a hosting cluster
from the VMaaS placement set and records its stable ID as
`placement.hosting_cluster_id`. It also persists
`placement.workload_selector={kind: VirtualMachine, name:
osac-vm-<ComputeInstance API UUID>}` and the service-defined logical
`interface_selector`. The ordinary workload template creates the VM and disks
in that namespace with `spec.runStrategy: Halted` and no tenant
network/interface fields. It confirms no VMI is running and captures the
created VM UID as `placement.workload_selector.uid` before attachment
dispatch. When OSAC dispatches the Kubernetes Manager task, it copies
`hosting_cluster_id` to `osac_job_vars.target_cluster.id`; the matching
kubeconfig context is selected explicitly. The VM must remain halted and must
not acquire a tenant interface until the networking manager applies the
request. Preparation retries preserve that state.

When it creates the target-only `SubnetAttachment`, the workload controller
stores this immutable placement snapshot in `resource.spec.placement`:
`hosting_cluster_id`, target namespace, VM kind/name/UID, and
`interface_selector`.
Attachment jobs pass the request as `resource` and the ComputeInstance as the
separate `target`. The Kubernetes Manager uses the captured placement and
OSAC-supplied target-cluster access to read and update only the exact VM; it
does not search for a VM by tenant, Subnet, or name alone. Credential material
is supplied through the protected execution context and is never stored in the
request or serialized in `osac_job_vars`.

The following is an illustrative KubeVirt spec after
`apply_subnet_attachment` has added one manager-selected network reference and
its matching interface. The reference uses a NetworkAttachmentDefinition for
this example; the object name and binding details are provider implementation
choices, not fields in the tenant networking API or requirements for other
workload services.

```yaml
metadata:
  namespace: osac-subnet-<subnet-api-id>
spec:
  runStrategy: Halted
  template:
    spec:
      domain:
        devices:
          autoattachPodInterface: false
          interfaces:
            - name: primary
              bridge: {}
      networks:
        - name: primary
          multus:
            networkName: primary
```

KubeVirt requires a matching `spec.networks` entry and
`spec.domain.devices.interfaces` entry. The Multus entry refers to the
`NetworkAttachmentDefinition` in the VM's namespace. See the [KubeVirt network
interface contract](https://kubevirt.io/user-guide/network/interfaces_and_networks/)
and [run strategies](https://kubevirt.io/user-guide/compute/run_strategies/).
For this single-NIC flow, the completed VM configuration must expose only the
tenant-facing interface as an address-reporting VMI interface. The Kubernetes
Manager configures any default or autoattached interface behavior to meet that
constraint; this example disables `autoattachPodInterface`. This keeps the
existing first-non-empty VMI IP selection unambiguous.

Kubernetes `apply_subnet_attachment` verifies the exact VM UID, confirms the
VM is halted with no running VMI, adds only the manager-selected
network/interface fields for the requested Subnet, and installs the complete
effective policy. It must confirm both the VM update and policy before
reporting success. It must not change compute fields or run control, and it
must not start the VM. An identical replay after a lost result recognizes the
already-applied fields and policy without rewriting a running VM. A mismatch
or replacement VM UID fails rather than mutating another object. Live
attachment updates require a separately defined lifecycle. Provider-specific
labels/annotations used by networking must use a provider-owned prefix and
must not overwrite OSAC tenant/ownership metadata. The manager interprets its
Fabric-produced NetworkData inputs and its own configuration; it produces no
Kubernetes-owned NetworkData.

After the manager result is accepted and the SubnetAttachment reports
`NetworkAttachmentsReady=True`, the workload controller verifies the same VM
UID and applied interface, then applies the requested final run strategy. If
the requested strategy runs the VM, the first VMI starts only after the
network/interface fields and policy are present. If the requested strategy is
`Halted`, no VMI starts. Subsequent workload reconciliation must preserve the
manager-owned network/interface fields instead of applying a stale manifest
that removes them. IP discovery reads the VM's tenant interface status, not a
manager-specific backend identifier.
Deletion confirms no VMI remains, invokes attachment cleanup with the same
VM UID, and removes the stopped VM only after cleanup. A missing/replaced VM
is not permission to patch a same-name object; cleanup uses captured identity
and provider mappings. Backend object loss follows the existing failed-stage
recovery rules. These are fixed responsibilities of the existing apply/delete
tasks, not another output channel or lifecycle. [User]


### Workflow Description

The ComputeInstance's `network_attachments` field is the tenant's desired
Subnet and SecurityGroups. The internal `SubnetAttachment` is an OSAC request
for applying that attachment to one workload. It tracks the manager job,
attachment readiness, discovered address, and cleanup finalizer. It is not a
second tenant attachment. The networking controller resolves the request's
target and desired attachment from the ComputeInstance before dispatch; the
manager applies the selected network/interface fields to the stopped VM.

#### Networking prerequisites

Use the shared [creation readiness gates](/enhancements/OSAC-1433-unified-networking/design.md#creation-readiness-gates) and [deletion dependency guards](/enhancements/OSAC-1433-unified-networking/design.md#deletion-dependency-guards), together with [tenant defaults](/enhancements/OSAC-1433-default-networking/design.md).
Before VM creation, the selected Subnet, its SecurityGroups and required
hosting placement must be ready. Fabric values are committed before Kubernetes
realization; VMaaS does not allocate or reinterpret them.

#### VM Creation

1. **Tenant creates ComputeInstance:**
   ```bash
   # Explicit networking:
   osac create computeinstance --template ocp_virt_vm \
     --network-attachment subnet=my-subnet,security-groups=my-sg \
     --name my-vm

   # Or with defaults + auto external access:
   osac create computeinstance --template ocp_virt_vm \
     --external-ip-attachment --name my-vm
   ```
   - fulfillment-service:
     - If `network_attachments` is omitted or empty: populates the sole attachment with the tenant's default Subnet and default SecurityGroup (see Default Networking PRD)
     - If one attachment is supplied, defaults only missing fields: a missing Subnet receives the tenant default Subnet, and a missing or empty SecurityGroup list receives the tenant default SecurityGroup only when the resolved Subnet belongs to the tenant's default VirtualNetwork; otherwise the caller must provide SecurityGroups from the resolved Subnet's VirtualNetwork; supplied values are preserved
     - Validates: at most one attachment; the subnet is Ready and the security groups belong to the same VN
     - If `auto_external_ip_attachment == true`: auto-selects ExternalIPPool (READY, most available capacity), creates ExternalIP in the same DB transaction as the ComputeInstance — ExternalIP starts in **Pending** state. Pool capacity is decremented atomically; if the pool is exhausted, the API call fails and no resources are persisted. ExternalIPAttachment is **not** created at this point — it is deferred to the fulfillment-service internal reconciler, which creates it only after the ExternalIP is Allocated and the ComputeInstance is Ready. See [Unified Networking — Auto-provisioning lifecycle](/enhancements/OSAC-1433-unified-networking/design.md#auto-provisioned-external-access) for the full stepped flow.
   - Creates ComputeInstance CR with `network_attachments`

2. **Create the VM halted, then apply its Subnet attachment:**
   - The ComputeInstance lifecycle controller selects a cluster from the VMaaS placement set for the Ready Subnet and persists `hosting_cluster_id`, the deterministic VM name and interface selector. The ordinary workload template prepares the DataVolume and creates the VM with `runStrategy: Halted` and no tenant network/interface fields. It records the VM UID before creating the SubnetAttachment; the request's immutable `spec.placement` captures `hosting_cluster_id`, target namespace, VM name/UID and interface selector. No VMI runs and no tenant traffic is enabled. During attachment, VMaaS patches only its owned compute and run-control fields; it preserves manager-owned network/interface fields while the request is becoming Ready.
   - After registering its workload cleanup finalizer, the controller creates one target-only SubnetAttachment. The networking controller resolves the workload's immutable attachment, ready same-VirtualNetwork Subnet/SecurityGroup references, stateful rules, applicable NetworkData and the exact stopped-VM placement.
   - It dispatches Kubernetes `apply_subnet_attachment` with the SubnetAttachment request as `resource`, the ComputeInstance as `target`, normalized `network_attachment`, and `target_cluster.id=hosting_cluster_id`. Request UID/generation identify the result; the ComputeInstance API ID, logical interface and captured placement own backend state. The manager uses the exact kubeconfig context selected by `target_cluster.id` and the captured VM identity.
   - The manager confirms the VM UID and halted state, adds only its network/interface fields for the requested Subnet, and installs complete stateful policy. It must not change the VM's run control or start it. The request becomes `NetworkAttachmentsReady=True` only after the job result is accepted and the attachment is confirmed. Apply failure keeps the VM halted and non-ready. [User]

3. **Start only after attachment readiness (`osac.templates.ocp_virt_vm`):**
   - The lifecycle controller waits for `NetworkAttachmentsReady=True`, then applies the ComputeInstance's requested final run strategy. For a running VM, the first VMI boot therefore starts with the manager-applied network/interface fields and policy already in place; a requested `Halted` strategy leaves it stopped.
   - DHCP supplies the real address, gateway, prefix and DNS. Workload labels identify the selected interface; labels alone do not establish policy success.
   - Workload provisioning and networking jobs remain separately tracked. VM Ready requires successful attachment and real IP discovery. [User]

#### IP Discovery (feedback loop)

4. **SubnetAttachment controller discovers the VM IP:**
   - Reads the first non-empty `ipAddress` in KubeVirt VMI `status.interfaces`, matching the existing `ComputeInstance.status.ipAddress` observation behavior. The supported VM profile exposes only the tenant-facing interface, so this address belongs to the sole attachment.
   - DHCP assigns the address inside the guest; KubeVirt VMI status is OSAC's observation source. OSAC does not query a DHCP server for the VM address. A VM profile with another address-reporting interface is outside this flow; multi-interface support must match VMI interface identity to `interface_selector` before increasing the attachment limit.
   - Writes the assigned IPv4 address and `IPDiscoveryComplete` to request status.
   - The ComputeInstance lifecycle controller mirrors the request's readiness/IP to `computeNetworkAttachmentStatuses` on workload status.
   - The feedback controller transports that status through Signal RPC to fulfillment-service; fulfillment persists `compute_network_attachment_statuses` for tenant visibility and ExternalIPAttachment target resolution.
   - The request owns manager job history and discovery status; the workload API remains the sole source of desired attachment intent. [User]

#### External Access (optional, auto-provisioned when `auto_external_ip_attachment=true`)

5. **ExternalIP reconciliation:**
   - ExternalIP (created at step 1) is pushed to the hub cluster by the fulfillment-service reconciler
   - osac-operator dispatches `create_external_ip` to the manager selected by the NetworkClass profile. The Fabric Manager reserves the address under the ExternalIP API ID and returns it in `osac_result.data.external_ip.address`; OSAC validates the result identity and pool membership, writes status, and transitions the ExternalIP to Allocated. See [Unified Networking — ExternalIP Address Selection and Ownership](/enhancements/OSAC-1433-unified-networking/design.md#externalip-address-selection-and-ownership).
   - ExternalIP labeled `osac.openshift.io/auto-created: "true"` and `osac.openshift.io/auto-created-for: <compute-instance-id>`

6. **Deferred ExternalIPAttachment creation (fulfillment-service internal reconciler):**
   - Once ExternalIP is **Allocated** AND ComputeInstance is **Ready** (with `compute_network_attachment_statuses` populated): fulfillment-service internal reconciler creates ExternalIPAttachment, labeled `osac.openshift.io/auto-created: "true"`
   - This follows the standard creation readiness gate — no exceptions
   - osac-operator ExternalIPAttachment controller dispatches to AAP → fabric manager creates DNAT rule: external IP → VM's primary subnet IP (from `compute_network_attachment_statuses`)
   - ExternalIPAttachment transitions to **Ready**

#### Deletion (reverse order)

7. **Delete ComputeInstance:**
   - **Auto-provisioned cleanup:** If ExternalIP/ExternalIPAttachment were created by the system (`auto_external_ip_attachment=true`, labeled `osac.openshift.io/auto-created: "true"`): parent finalizer deletes ExternalIPAttachment first, then ExternalIP.
   - **Manually created ExternalIPAttachments block deletion** — if the tenant created ExternalIPAttachments explicitly (not labeled `osac.openshift.io/auto-created`), the delete request is rejected. The tenant must remove them first. See [Unified Networking — Deletion Dependency Guards](/enhancements/OSAC-1433-unified-networking/design.md#deletion-dependency-guards).
   - **Default networking resources (VN, Subnet, SG, NATGateway) are NOT cleaned up** — they are tenant-scoped and shared across resources.
   - The lifecycle controller stops the VM and waits until guest execution has ended, retaining the VM object and its immutable placement. It then deletes its SubnetAttachment and waits for its finalizer. The networking controller dispatches `delete_subnet_attachment` with `target_cluster.id` from that same placement. The Kubernetes Manager removes attachment-owned policy and network/interface fields from the exact stopped VM. The workload template deletes the VM only after request cleanup completes.
   - The ordinary `osac-delete-compute-instance` template deletes the stopped KubeVirt VM object and DataVolume only after request cleanup completes. VM teardown does not restore a physical provisioning port. [User]

8. **Delete networking resources:**
    - Shared-network deletion waits for all consumers. Subnet cleanup runs every possibly-started Kubernetes placement, using that placement's context, before Fabric cleanup. VirtualNetwork cleanup follows its children.
    - SecurityGroup and NetworkClass are OSAC objects with no standalone provider delete job; the fixed shared task table determines all dispatch.

<a id="api-extensions"></a>

### API contract

#### Proto (fulfillment-service)

Use the existing `ComputeNetworkAttachment` field with a single-entry limit:

```protobuf
message ComputeNetworkAttachment {
  SubnetLocalReference subnet = 1;                         // Optional on input; immutable after resolution
  repeated SecurityGroupLocalReference security_groups = 2; // Optional on input; immutable after resolution
}

message ComputeInstanceSpec {
  // ... existing fields ...
  repeated ComputeNetworkAttachment network_attachments = 14; // optional; max 1
  optional bool auto_external_ip_attachment = 18;  // auto-provision ExternalIP + ExternalIPAttachment
}

message ComputeNetworkAttachmentStatus {
  string subnet_ref = 1;               // Subnet ID (echoed from spec)
  string ip_address = 2;               // Sole attachment IP observed from the KubeVirt VMI after DHCP/overlay assignment
}

message ComputeInstanceStatus {
  // ... existing fields ...
  repeated ComputeNetworkAttachmentStatus compute_network_attachment_statuses = 7; // NEW
}
```

#### Operator CRD (osac-operator)

`ComputeInstanceSpec.NetworkAttachments` has the following behavior:
- Validation limits the repeated field to at most one attachment
- `PrimarySubnetRef()` returns the sole attachment (or no subnet when the list is empty)

CEL validation rule:
```yaml
- rule: "self.networkAttachments.size() <= 1"
  message: "at most one network attachment is supported"
```

`ComputeInstanceStatus` contains the discovered attachment status:

```go
type ComputeInstanceStatus struct {
    // ... existing fields ...
    ComputeNetworkAttachmentStatuses []ComputeNetworkAttachmentStatus `json:"computeNetworkAttachmentStatuses,omitempty"`
}

type ComputeNetworkAttachmentStatus struct {
    SubnetRef string `json:"subnetRef"`
    IPAddress string `json:"ipAddress,omitempty"` // Sole attachment IP observed from the KubeVirt VMI after DHCP/overlay assignment
}
```

The SubnetAttachment controller observes the first non-empty KubeVirt VMI
interface IP for the sole tenant attachment and writes request status. The
workload controller mirrors the discovered address to
`ComputeNetworkAttachmentStatuses`; the feedback controller synchronizes
workload status to fulfillment-service. The existing ComputeInstance
`status.ipAddress` path also reads the first non-empty VMI interface IP. This
behavior is specific to VMaaS's current KubeVirt single-interface flow.

#### Server Validation (fulfillment-service)

- Validate that `network_attachments` contains at most one entry.
- Primary/default-route resolution: the sole attachment is implicitly primary; VMaaS has no primary field
- BM-only deployment check: if the NetworkClass has no k8sManager, reject ComputeInstance creation

<a id="template-changes-osac-aap"></a>

#### Template responsibilities (osac-aap)

- The workload template prepares compute/disks and creates the VM halted without tenant network/interface fields. It captures the VM UID and deterministic placement before the request is dispatched.
- The Kubernetes Manager's `apply_subnet_attachment` task uses the explicit kubeconfig context selected by `target_cluster.id`, updates only the target VM's network/interface fields, and installs policy while the VM is stopped. It must use the exact target UID and may not change run control. Provider-specific network objects and their configuration remain manager-owned. Kubernetes Managers do not produce NetworkData unless a declared Fabric input is consumed.
- After `NetworkAttachmentsReady=True`, the workload lifecycle applies the requested run strategy and preserves manager-owned network/interface fields during later reconciliation; full stale-manifest replacement is forbidden. The [shared VM ownership contract](/enhancements/OSAC-1435-vmaas-networking/design.md#vm-placement-and-interface-ownership) defines field ownership, readiness and deletion behavior.
- Stop guest execution before `delete_subnet_attachment`, then remove the VM object only after request cleanup completes. [User]
- The sole attachment receives IP + default gateway + DNS via DHCP

<a id="implementation-detailsnotesconstraints"></a>

### Component behavior and constraints

#### Component Responsibility

| Component | Responsibility |
|-----------|---------------|
| fulfillment-service | Validate network_attachments, create CR, auto-provision ExternalIP, write `compute_network_attachment_statuses` from feedback |
| osac-operator ComputeInstance controller | Resolve workload placement, create/wait for target-only SubnetAttachment, mirror request status, trigger AAP, and gate teardown on request and external child cleanup |
| osac-operator ComputeInstance feedback controller | Signal fulfillment-service when mirrored workload status changes |
| osac-operator networking controllers | Own networking resources and SubnetAttachment status/jobs; resolve policy, dispatch apply/delete, discover VMI address |
| AAP template (ocp_virt_vm) | Prepare stopped single-NIC VM without tenant network/interface fields; start after attachment readiness; stop before cleanup and delete afterward |
| fabric_manager (Ansible role) | Shared VN/Subnet/address/NAT operations; VM interface policy belongs to the Kubernetes Manager |
| k8s_manager (Ansible role) | Create/delete the manager's Subnet overlay realization; apply/delete the target VM's network/interface fields and stateful SecurityGroup policy through `SubnetAttachment` |

#### Primary Attachment Resolution

- The sole attachment is implicitly primary/default route
- More than one attachment is rejected

#### Auto-Provisioned Resource Lifecycle

- ExternalIP created at workload creation time (pool is Ready, creation readiness gate satisfied). ExternalIPAttachment created later by fulfillment-service internal reconciler (after ExternalIP Allocated + ComputeInstance Ready)
- Labeled `osac.openshift.io/auto-created: "true"`
- Parent resource finalizer deletes in order: ExternalIPAttachment → ExternalIP
- **Cleanup failure:** the parent finalizer remains while auto-created ExternalIPAttachments or ExternalIPs remain. Reconciliation retries with backoff and reports the failed child operation; an administrator repairs the cause before cleanup resumes. Enabled-mode failure never silently orphans children. [User]

#### Backward Compatibility Strategy

The existing repeated `network_attachments` field is retained unchanged for API
compatibility. The server and operator validate that it contains at most one
entry; omitted and empty lists invoke default resolution, while a supplied
single entry receives defaults only for missing fields. No new singular field or
dual-field migration is required. The sole VM attachment is implicitly
primary/default, and changing any resolved attachment field requires deleting
and recreating the VM.

### Security Considerations

This feature inherits the existing security model:
- Tenant isolation via `osac.openshift.io/tenant` annotation enforced by OPA policies
- Auto-provisioned resources (ExternalIP, ExternalIPAttachment) inherit tenant annotation from parent ComputeInstance
- No new authentication or authorization changes
- SecurityGroup rules control VM inbound traffic (tenant-configurable via explicit SG or default SG)
- The sole VM attachment uses the same SecurityGroup enforcement as the rest of the fabric

### Failure Handling and Recovery

#### ComputeInstance Controller Reconciliation Failures

- Subnet resolution failure (subnet not found, not Ready): the API rejects the create request with a `FailedPrecondition` error; the ComputeInstance is never created. See [Unified Networking — Creation Readiness Gates](/enhancements/OSAC-1433-unified-networking/design.md#creation-readiness-gates)
- Namespace resolution failure (subnet has no target namespace): ComputeInstance enters Failed state, retries after manual correction
- AAP job failure (template execution error): ComputeInstance enters Failed state with AAP job ID in status, manual investigation required

#### Auto ExternalIP Allocation Failures

- Pool exhaustion: create API call returns error, no resources persisted (pool capacity checked synchronously during the API call — see [auto-provisioning lifecycle](/enhancements/OSAC-1433-unified-networking/design.md#auto-provisioned-external-access))
- ExternalIP provisioning failure: ExternalIP reports failure and optional public access remains unavailable. ComputeInstance readiness follows its ordinary provisioning, attachment and real-IP gates; it does not wait for the optional ExternalIP
- ExternalIPAttachment provisioning failure: DNAT rule not created, inbound traffic does not reach VM (VM functional, external access unavailable)

#### Cleanup Failures

- Auto-provisioned resource cleanup transient failure: finalizer retries
- **Cleanup failure:** the parent finalizer remains while auto-created ExternalIPAttachments or ExternalIPs remain. Reconciliation retries with backoff and reports the failed child operation; an administrator repairs the cause before cleanup resumes. Enabled-mode failure never silently orphans children. [User]

### RBAC and Tenancy

No RBAC or tenancy changes. All new resources (ComputeInstance with its existing fields, auto-provisioned ExternalIP/ExternalIPAttachment) inherit tenant isolation from parent:
- `osac.openshift.io/tenant` annotation propagated from ComputeInstance to auto-created resources
- OPA policies enforce tenant-scoped operations according to each resource API;
  networking resources use create/list/get/delete and do not expose
  update/patch, while supported non-network workload updates remain available
- Tenant User can view and manage auto-provisioned resources (labeled `osac.openshift.io/auto-created: "true"`) via standard API

### Observability and Monitoring

New structured log events:
- ComputeInstance controller: `ResolvedPrimarySubnet` (info), `SubnetResolutionFailed` (error), `AttachmentProvisioning` (info)
- fulfillment-service: `AutoProvisionedExternalIP` (info), `ExternalIPPoolExhausted` (error)

New Kubernetes events on ComputeInstance:
- `NetworkingResolved`: subnet → namespace resolution succeeded
- `NetworkingResolutionFailed`: subnet resolution failed (not found, not Ready, BM-only deployment)
- `AutoExternalIPCreated`: ExternalIP and ExternalIPAttachment auto-provisioned

No new metrics or alerts (existing provisioning duration and failure rate metrics apply).

### Risks and Mitigations

#### Risk: Qualified Kubernetes Manager is unavailable

**Impact:** OSAC-1511 (CUDN) and OSAC-1717 (EVPN) are closed evaluation spikes, not evidence that a Kubernetes Manager meeting the Network Manager Integration Contract is deployed and qualified. Without a compatible, qualified Kubernetes Manager, VM overlay networking cannot be provisioned.

**Mitigation:** Gate VM overlay networking on a deployment-selected Kubernetes Manager that passes NetworkClass compatibility validation and provider qualification for its assigned tasks. Do not treat completion of either evaluation spike as manager qualification.

**Reviewed by:** Engineering / Product

#### Risk: Shared manager contract support is delayed

**Impact:** The legacy two-job lifecycle tracking delivered by OSAC-1459 does not provide the manager registrations, generic task dispatch, validated results, and uncertain-job recovery specified by the Network Manager Integration Contract. VM networking cannot meet its readiness and cleanup requirements until that shared contract is implemented.

**Mitigation:** Deliver the shared contract implementation before enabling VMaaS networking. Require the selected Fabric and Kubernetes Manager stages and their documented readiness and cleanup behavior; do not treat legacy multi-job support alone as qualification.

**Reviewed by:** osac-operator team

#### Risk: ExternalIPPool exhaustion

**Impact:** Auto ExternalIP allocation fails, create API call returns error, tenant cannot create VM with `auto_external_ip_attachment=true`.

**Mitigation:** Pool capacity visible in status; clear error directs tenant to explicit allocation from another pool or contact admin.

**Reviewed by:** Cloud Provider Admin

### Drawbacks

#### Single-attachment compatibility constraint

The repeated `network_attachments` field remains in place to avoid an API
shape change. New requests containing more than one entry are rejected by
validation.

### Provider Networking Disabled

Apply the [unified disabled-mode contract](/enhancements/OSAC-1433-unified-networking/design.md#provider-networking-control)
for API validation, skipped jobs, external-address state and logical cleanup.
VMaaS-specific behavior: a valid VM provisions on the platform default network,
with its ordinary default interface instead of the enabled-mode stopped-empty
preparation/manager handoff. Tenant Subnet placement and SecurityGroup behavior
are not claimed. Real platform VMI feedback may be reported, but cannot be
relabeled as evidence of tenant attachment or public routing. VM provisioning
does not wait for an unallocated automatic ExternalIP. [PRD: FR-8] [User]

Re-enabling provider networking follows the [shared activation preflight](/enhancements/OSAC-1433-unified-networking/design.md#provider-networking-control). For this extension, drain and delete every ComputeInstance through the normal VM lifecycle; the extension does not migrate a running baseline VM to a tenant Subnet. The shared gate also waits for workloads owned by other extensions and blocks new workload Creates while activation is pending. Reads and deletes remain available. After the deployment profile and configured pools regain real provider readiness, ComputeInstances use their ordinary network-reference gates. A disabled-mode ProvisioningDisabled state does not satisfy enabled readiness. An ordinary restart of an already enabled deployment does not require a new drain. [User]

## Alternatives Considered

### Alternative 1: Single shared NetworkAttachment message with optional primary field

Instead of creating `ComputeNetworkAttachment`, extend the shared `NetworkAttachment` message with an optional `primary` field usable by all resource types.

**Rejected because:** Other resource types (Cluster, BaremetalInstance) have different attachment semantics. Resource-specific attachment messages provide cleaner API surface and type-specific validation; all current workload types enforce a single tenant attachment.

### Alternative 2: Capacity exhaustion creates Failed resource instead of returning error

Instead of returning an error when ExternalIPPool has no capacity, create a Failed ComputeInstance with a status condition.

**Rejected because:** Pool capacity is validated synchronously during the API call — if the pool is exhausted, the call fails atomically and no resources are persisted. Creating a Failed resource adds cleanup burden and audit trail complexity. Clear API error with no persisted state is simpler.

## Open Questions

### ~~1. Should capacity exhaustion return an API error or create a Failed resource?~~ — Resolved

Resolved: Return error, no resource persisted. Pool capacity checked synchronously. No Failed resource.

## Test Plan

- **[DEV/QE] Subnet placement lifecycle:** provide two hosting-cluster IDs and verify OSAC tracks one Kubernetes `create_subnet` stage per ID, reuses the single Fabric result, and withholds Subnet readiness until both stages succeed. Add a placement and verify it is prepared before VM placement; remove one while it still has a consumer and verify cleanup waits; then verify Subnet deletion cleans every possibly-started placement even when it is absent from the current resolver set, before Fabric deletion.
- **[DEV/QE] VM handoff:** exercise two provider implementations through the same workload template and two hosting-cluster kubeconfig contexts. Verify OSAC selects the context matching the captured `hosting_cluster_id`, and a same-named VM in another context is untouched. The VM is initially halted with no tenant network/interface fields; apply updates only the exact VM UID while no VMI exists, installs policy, and reports readiness only after both are confirmed; no start occurs before `NetworkAttachmentsReady=True`; the first VMI uses the applied interface; its first non-empty interface IP is mirrored to the sole attachment status; replay is idempotent; replacement VM UIDs or a missing context are rejected; and cleanup removes manager-owned fields/policy before VM deletion.

### Shared Attachment Contract Validation

- **[DEV] Contract:** assert the SubnetAttachment request as `resource`, the ComputeInstance as `target`, its immutable `spec.placement` snapshot, normalized attachment policy, request UID/generation results, and mandatory adapter entry points. A valid no-change result is accepted; missing required data is rejected.
- **[DEV] Contract:** prepare deterministic stopped-VM placement and selector before apply; managers add network/interface fields and apply policy without a running VMI; VM start cannot precede `NetworkAttachmentsReady=True`, and VM stop is confirmed before delete dispatch.
- **[DEV] Envtest:** install failure leaves request/VM non-ready; request owns discovered VMI IP and workload controller mirrors it; delete failure retains finalizers and blocks VM teardown.
- **[QE] E2E:** two VMs on one Subnet using different groups enforce their respective stateful policies before traffic; restart during apply/delete preserves stable API ownership and backend-VM UID fencing; external child cleanup completes before request/workload teardown. [User]


### Provider Networking Control (FR-8)

- **[DEV] Envtest / [QE] E2E:** request re-enablement with a baseline workload or a workload whose networking was suspended by disablement still present. Assert activation and new workload creates are blocked, existing Read/Delete remain available, and no apply/lease/reservation or tenant attachment mutation runs. Drain workloads and jobs, repair backend leftovers, then activate; stale skipped readiness cannot admit new workloads until genuine network prerequisites are ready. Repeated enabled restarts do not invoke a fresh drain.

- Verify normal VM provision/delete jobs still run with the shared setting
  disabled and sufficient baseline connectivity; no network provider job runs.
- Verify active network jobs are cancelled and awaited before skipped status
  or network-finalizer release, including deletion and retryable AAP failures.
- Verify non-allocating Networking API resources report `Ready=True`, reason
  `ProvisioningDisabled`, with a skipped-work message after logical
  preconditions pass; ExternalIP status distinguishes unconfirmed from
  confirmed real allocation and never exposes a placeholder. Enabled mode
  retains normal provider behavior.
- Verify invalid API/defaulting/dependency requests remain rejected,
  SecurityGroup defaulting/immutability remains unchanged, and automatic
  attachments still wait for Allocated + workload Ready.
- Verify omitted or empty API attachments retain existing defaulting and
  missing-default errors. A valid VM that has no tenant attachment provisions
  on the platform default network when disabled; supplied API references retain
  their existing validation, and enabled mode continues tenant placement.

### Unit Tests

- fulfillment-service: max-one validation (accept no attachment or one attachment)
- fulfillment-service: max-one `network_attachments` validation
- fulfillment-service: omitted and partial attachment defaulting (empty `security_groups` is missing; supplied values are preserved; a missing group list defaults only for the tenant default VirtualNetwork and is rejected for a non-default subnet without caller-supplied groups)
- fulfillment-service: BM-only deployment validation (reject VM when no k8s_manager)
- fulfillment-service: auto ExternalIP pool selection (pick READY pool with most capacity, respect IP family)
- osac-operator ComputeInstance controller: `PrimarySubnetRef()` resolution (implicit single attachment)

### Integration Tests

- **[DEV/QE] Optional external access:** fail asynchronous ExternalIP allocation after an admitted workload Create. Core workload readiness still follows its ordinary provision/attachment/IP gates; the ExternalIP reports failure and no ExternalIPAttachment is created until a real allocation and Ready target exist. Pool exhaustion at initial admission still fails atomically.

- E2E: create ComputeInstance with two attachments, verify the API rejects the request
- E2E: create ComputeInstance with `--external-ip-attachment`, verify auto ExternalIP + ExternalIPAttachment created, DNAT rule functional
- E2E: delete ComputeInstance with auto-provisioned resources, verify ExternalIPAttachment and ExternalIP cleaned up
- E2E: create ComputeInstance in BM-only deployment, verify error returned
- E2E: create ComputeInstance with one `network_attachments` entry, verify it is used as the default route

### Tricky Test Cases

- ComputeInstance with one attachment (verify implicit default-route behavior)
- ExternalIPPool exhaustion (verify error returned, no resource created)
- Auto-provisioned resource cleanup failure (verify retained finalizer/ownership on persistent failure, successful cleanup after repair)

## Graduation Criteria

**Note:** This section will be updated when the enhancement is targeted at a release.

Proposed maturity level: **Tech Preview** → **GA**

Tech Preview criteria:
- [ ] API fields (`network_attachments`, `auto_external_ip_attachment`) implemented in fulfillment-service
- [ ] Operator CRD updated with max-one CEL validation
- [ ] Single-NIC template support (`osac.templates.ocp_virt_vm`) implemented
- [ ] Auto ExternalIP attachment provisioning functional
- [ ] Integration tests pass (E2E coverage for max-one validation, auto ExternalIP)
- [ ] Documentation: API reference, user guide for simplified VM creation

GA criteria:
- [ ] Network Manager Integration Contract registration, dispatch, result validation, and recovery behavior delivered; the selected compatible Fabric/Kubernetes Manager pair passes provider qualification and is production-tested
- [ ] Production deployment verified (MOC or other OSAC deployment)
- [ ] User feedback incorporated (usability, error messages, edge cases)

## Upgrade and Downgrade Strategy

### Current implementation baseline

This subsection describes the existing code as a migration starting point; it
is not the proposed manager flow described above. The target design replaces
the legacy dispatch and template-built initial network fields with the
registered manager contract and request-gated attachment flow.

ComputeInstance already participates in the networking API. The current flow
is:

1. Tenant creates VirtualNetwork, Subnet, SecurityGroup via API
2. osac-operator's networking controllers reconcile each resource as a standalone AAP job, using `implementation_strategy` to select the Ansible role (e.g., `osac.templates.cudn_net.create_subnet`)
3. Tenant creates ComputeInstance with `network_attachments` (`ComputeNetworkAttachment`, no `primary` field, single-NIC only)
4. osac-operator's ComputeInstance controller resolves subnet → namespace, triggers AAP job
5. AAP template (`osac.templates.ocp_virt_vm`) creates KubeVirt VirtualMachine with one `l2bridge` interface in the subnet's CUDN namespace
6. The ComputeInstance controller observes the first non-empty IP in KubeVirt VMI interface status and publishes it as `ComputeInstance.status.ipAddress`; this is the existing KubeVirt-specific IP observation path.

### What Already Works

- `network_attachments` field exists on ComputeInstanceSpec (field 14)
- Operator CRD has `NetworkAttachments []ComputeNetworkAttachment` with CEL cardinality and immutability rules; the complete resolved attachment is immutable
- Subnet-to-namespace resolution is implemented
- The template creates VMs in the correct namespace
- ExternalIPAttachment with `compute_instance` target works end-to-end

### What's Missing

- Existing `ComputeNetworkAttachment` has no `primary` field; the compatibility field remains single-attachment only
- Service-level maximum-one validation and field-level defaulting are still required
- At most one attachment — template creates one `l2bridge` interface
- The current implementation still uses `implementation_strategy` annotations; migration to the generic dispatcher is defined by the Network Manager Integration Contract.
- BM-only deployment validation (reject VM when no k8sManager)
- Auto ExternalIP allocation (tenant must manually create ExternalIP + ExternalIPAttachment)

### Upgrade and downgrade gates

Follow the [shared coordinated rollout and rollback requirements](/enhancements/OSAC-1433-unified-networking/design.md#upgrade-and-downgrade-strategy).
Preserve existing resource/provider bindings, accepted results and cleanup
context. Wire compatibility does not establish backend migration safety.
Drain or verifiably adopt legacy state before using new ownership keys; finish
cleanup with compatible components before downgrading to a version that cannot
interpret the retained state. Disabled-mode provider leftovers still require
confirmed provider/manual cleanup before their addresses or hosts are reused.

### Service compatibility

The repeated `network_attachments` wire field and existing single
`--network-attachment` flag remain. New validation permits at most one entry.
Existing single-attachment requests remain compatible; preservation of running
VMs additionally requires verified manager ownership and backend VM UID checks.
The new network-status field is additive. Provider-specific stopped-VM
preparation, field ownership and attachment gates require the corresponding
workload template and controllers before new dispatch.

## Version Skew Strategy

### Control Plane Skew

Use the [shared version-skew rules](/enhancements/OSAC-1433-unified-networking/design.md#version-skew-strategy).
Fulfillment, the workload/networking controllers and AAP content must agree on
the handoff and cleanup protocol. A coordinated installer release still has a
rolling transition; incompatible components must not dispatch new work.

### Client Skew

osac-cli (n-1) with fulfillment-service (n):
- The CLI uses the existing single `--network-attachment` flag and sends the existing `network_attachments` field

osac-cli (n) with fulfillment-service (n-1):
- The CLI remains compatible with the existing `network_attachments` field; a second attachment is rejected client-side and server-side

Recommendation: keep osac-cli and fulfillment-service within one minor version.

## Support Procedures

### Symptom: ComputeInstance stuck in Pending, condition "NetworkingResolutionFailed"

**Detection:**
```bash
kubectl describe computeinstance <name> -n <namespace>
# Check status.conditions for NetworkingResolutionFailed
```

**Cause:** Subnet not found, not Ready, or BM-only deployment (no k8s_manager)

**Resolution:**
1. Check Subnet status: `kubectl get subnet <subnet-name> -n <namespace>`
2. If Subnet is not Ready, investigate Subnet provisioning failure (check AAP job logs)
3. If BM-only deployment, tenant must create VM in a deployment with k8s_manager configured

### Symptom: VM has no default gateway

**Detection:** VM cannot reach external networks, `ip route` shows no default route

**Cause:** The sole attachment was not resolved or the subnet did not provide DHCP gateway information

**Resolution:**
1. Check ComputeInstance spec: `kubectl get computeinstance <name> -n <namespace> -o yaml`
2. Verify the single `networkAttachments[]` entry resolves to the intended subnet
3. If missing or incorrect, delete and re-create ComputeInstance with the intended subnet

### Symptom: Deletion waits for automatic external cleanup

**Detection:** The parent remains Deleting with its finalizer and child references; an auto-created ExternalIPAttachment or ExternalIP reports a failed cleanup operation.

**Cause:** The provider has not confirmed DNAT removal or address release.

**Resolution:**
1. Inspect parent, child and AAP operation diagnostics to identify the failed task.
2. Repair provider connectivity/configuration or the backend operation; let reconciliation retry with the same durable operation identity.
3. Confirm attachment deletion before address release and parent deletion. Preserve finalizers and address ownership until successful cleanup; do not force-remove finalizers. [User]

### Disabling automatic ExternalIP requests

To disable auto ExternalIP attachment:
- Remove or redact ExternalIPPool CRs (capacity exhaustion prevents auto allocation)
- No API extension to disable (fields are part of CRD, cannot be removed at runtime)

Consequences:
- Auto ExternalIP allocation fails with error (resource not created)
- Manual ExternalIP workflows remain functional
- No impact on existing running VMs

### Provider networking intentionally skipped

Set `global.networking.provisioningEnabled=false` through the Helm setting or Enclave Wizard checkbox
installation/upgrade value map and complete both operator rollouts. Inspect
`Ready=True`/`ProvisioningDisabled` conditions on non-allocating Networking API
resources and tracked network job states. Ordinary workload provisioning
remains active with the baseline connectivity described
above. Networking APIs remain available; no provider allocation, routing,
port movement, DHCP discovery, or cleanup is supplied by the skipped path.
Existing provider resources may require manual/provider-side cleanup. [User]

## Infrastructure Needed

- AAP execution environment with `osac.templates.ocp_virt_vm` role updated for single-NIC support
- A deployment-selected Kubernetes Manager that implements the shared contract and passes provider qualification for VM overlay provisioning
- Integration test environment with a deployment-selected, compatible Fabric/Kubernetes Manager pair, including an overlay-capable Kubernetes Manager.

---

## Provenance

Authored: revise @ design 0.11.3 - cc0daa6, workspace main @ 06d340f90 (43 behind origin/main)
Final: manual-edit [manual] @ design 0.11.5 - 1c6e8de, workspace main @ 04cc50101

> Context changed between revise and manual-edit.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"1c6e8de","source_repo":"04cc50101","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["revise","revise","respond","manual-edit","revise","manual-edit","revise","manual-edit","revise","respond","respond","revise","revise","revise","revise","manual-edit","revise","revise","revise","revise","revise","manual-edit","manual-edit"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":true} -->
