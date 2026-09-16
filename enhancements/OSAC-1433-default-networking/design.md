---
title: default-networking
authors:
  - dmanor@redhat.com
creation-date: 2026-07-08
last-updated: 2026-09-10
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1433
prd: "prd.md"
see-also:
  - "/enhancements/OSAC-1433-unified-networking"
  - "/enhancements/OSAC-1435-vmaas-networking"
  - "/enhancements/OSAC-1436-caas-networking"
  - "/enhancements/OSAC-1437-bmaas-networking"
  - "/enhancements/OSAC-1433-k8s-only-k8s-manager"
replaces:
  - N/A
superseded-by:
  - N/A
---

# Default Networking — Simplified Resource Creation

Default networking provides automatic resource provisioning at tenant onboarding (including a default VirtualNetwork, Subnet, tenant default SecurityGroup, tenant default NetworkACL, and NATGateway), optional resource-specific network attachments with defaults, auto ExternalIP provisioning, and auto-cleanup on deletion.

## Summary

This document is a per-service expansion of the [Unified Networking EP](/enhancements/OSAC-1433-unified-networking/design.md), providing default networking automation and simplified resource creation. When a tenant is created, the system provisions a default VirtualNetwork, IPv4 Subnet, tenant default SecurityGroup, tenant default NetworkACL associated with the default Subnet, and NATGateway through every selected manager. Workloads carry SecurityGroup membership in their attachments and inherit NetworkACL policy from the selected Subnet. Resources (ComputeInstance, Cluster, BaremetalInstance) can omit their resource-specific network attachment field and use tenant defaults. For BMaaS, default resolution produces one tenant network attachment on one physical NIC; BMaaS does not support multi-NIC or multi-homed attachments. Auto ExternalIP modes create Pending records synchronously and complete allocation and activation asynchronously. See [PRD](prd.md) for detailed requirements.
Shared field types, formats, presence rules, allowed values, and validation
are defined by the [Unified Networking field contract](/enhancements/OSAC-1433-unified-networking/design.md#field-types-formats-and-validation).

The shared networking resource model and IPv4-only scope are defined by the
[Unified Networking design](/enhancements/OSAC-1433-unified-networking/design.md#deployment-topology).
Its connected-only deployment boundary, including the exclusion of air-gapped
deployments, is defined by the [Unified Networking deployment support
boundary](/enhancements/OSAC-1433-unified-networking/design.md#deployment-support-boundary).

## Motivation

A reachable resource in OSAC requires a VirtualNetwork and Subnet, plus a
tenant NetworkACL,
the resource itself, and optionally ExternalIP and ExternalIPAttachment.
Default networking eliminates this friction — a single create command produces
a reachable instance by leveraging tenant defaults provisioned at onboarding.

### Goals

- Single-call resource creation with sensible networking defaults
- Default networking resources (VN, IPv4 Subnet, SecurityGroup, NetworkACL, and NATGateway at tenant onboarding)
- Optional resource-specific network attachment field on all resource types
- Auto ExternalIP mode for inbound connectivity
- Auto-cleanup of auto-created resources on deletion
- Tenant-scoped default resources (visible, read-only after creation, and lifecycle-managed by tenant)

### Non-Goals

- Custom default configurations per tenant (all tenants receive the same defaults)
- Auto-provisioning of additional VirtualNetworks or Subnets beyond the initial default
- UI support for simplified creation (deferred — API and CLI only)
- Automatic migration of existing resources to use defaults

SecurityGroup and NetworkACL rule evaluation is defined by the [Unified
Networking policy semantics](/enhancements/OSAC-1433-unified-networking/design.md#securitygroup-rule-semantics).
Default networking creates the tenant default SecurityGroup. Its empty rule
set means default deny. It also creates the tenant default NetworkACL and
associates it with the tenant's default Subnet. Its explicit policy is
deny-all ingress and allow-all egress. The provider-owned deployment default
ACL policy is hard-coded to `permit` all traffic and is used only as the
least-specific fallback when no tenant ACL rule matches.

### Catalog Item interaction

Catalog Items are an optional create-time governance layer over these defaults.
The resolution order is:

```text
tenant input
  → Catalog locked value or Catalog default
  → Template default
  → tenant default networking
```

More precisely, a locked Catalog value rejects conflicting tenant input;
editable input accepts the tenant value and otherwise uses its Catalog default
when present. If the field is still unset after Catalog and Template
resolution, the tenant's default Subnet is selected and the tenant default
SecurityGroup is selected. Its effective ACL is inherited from the resolved
Subnet.

Here, "editable" describes a Catalog Item's create-time input policy only. It
does not permit updating the resolved network attachment or any other
network-owned field after the workload is created.

The field is resource-specific: Compute uses
`network_attachments` with at most one entry, Cluster uses the singular
`network_attachment`, and BaremetalInstance uses `network_attachments` with
at most one attachment. Catalog validation uses the same readiness, VirtualNetwork,
cardinality, primary, and physical-interface rules as direct resource creation.

NetworkClass defaults and tenant default resources remain networking defaults,
not Catalog Item policy. A shared Catalog Item cannot lock or default a
tenant-local Subnet; it must leave that choice editable or ungoverned so
tenant defaults can apply. NetworkACL association is managed by the
NetworkACL resource.

Default networking follows the [unified networking operation
contract](/enhancements/OSAC-1433-unified-networking/design.md#supported-operations-and-immutability).
This document defines only the default-resource lifecycle and
auto-provisioned-resource behavior that is specific to this enhancement.

## Proposal

The design covers three areas: default networking at tenant onboarding
(including NATGateway), optional
resource-specific network attachments with auto-population, and auto
ExternalIP provisioning.

### Workflow Description

#### Default Networking at Tenant Onboarding

1. **Cloud Infrastructure Admin creates NetworkClass with its defaults:**
   ```yaml
   # NetworkClass defaults are supplied at creation time; its network spec is immutable
   apiVersion: osac.openshift.io/v1alpha1
   kind: NetworkClass
   metadata:
     name: moc-site-1
   spec:
     fabricManager: <configured-fabric-manager>
     defaults:
       virtualNetworkCIDR: 10.0.0.0/16
       ipv4SubnetCIDR: 10.0.1.0/24
   ```

2. **Cloud Provider Admin creates Tenant:**
   ```bash
   osac create tenant --name acme-corp
   ```
   - **fulfillment-service** creates the Tenant record, then creates default networking resources through its own API (same path as tenant-created resources — persisted in PostgreSQL, reconciled to K8s CRs). It obeys the strict dependency-ready creation rule:
     - Creates the default VirtualNetwork with label `osac.openshift.io/default: "true"`, using the CIDR from NetworkClass defaults. It does not create the Subnet, policies, or NATGateway until the default VirtualNetwork is `Ready`.
     - After the default VirtualNetwork is `Ready`, creates the default IPv4 Subnet with label `osac.openshift.io/default: "true"`, using `ipv4SubnetCIDR` from NetworkClass defaults. The Subnet may then become `Pending` while its own managers provision it.
     - After the default VirtualNetwork is `Ready`, creates the tenant default SecurityGroup with label `osac.openshift.io/default: "true"` and an empty rule set, which means default deny.
     - After the default Subnet is `Ready`, creates the tenant default NetworkACL with label `osac.openshift.io/default: "true"`, associates it with the tenant's default Subnet, and installs the default ACL policy: deny-all ingress and allow-all egress.
     - First creates the allowlisted OSAC-owned automatic ExternalIP after a Ready pool and capacity check. That ExternalIP may be `Pending`; the default NATGateway is created only after the default VirtualNetwork is `Ready` and the ExternalIP is `Allocated`. The NATGateway is labeled `osac.openshift.io/default: "true"`.
   - Reads NetworkClass defaults configuration (single NetworkClass per deployment)
   - Default resources go through the normal reconciliation path: fulfillment-service reconciler pushes each admitted CR → osac-operator networking controllers dispatch to fabric/k8s managers → each resource transitions to `READY`. A default resource is never persisted merely to wait for a non-Ready dependency; onboarding remains non-Ready and retries the next create only after its prerequisite is usable.
   - fulfillment-service tracks default networking readiness on the Tenant: sets `DefaultNetworkingReady` condition once all default resources (VN, IPv4 Subnet, SecurityGroup, NetworkACL, and NATGateway) reach READY state (via feedback)
   - Tenant overall status becomes READY only when DefaultNetworkingReady condition is true

3. **If default networking provisioning fails:**
   - Tenant remains in non-READY state
   - Tenant status condition shows: `DefaultNetworkingReady: false, reason: SubnetProvisioningFailed, message: "Subnet 'default' failed to provision"`
   - Cloud Provider Admin inspects failure, fixes root cause, and retries by deleting and re-creating the tenant

#### Simplified Resource Creation with Defaults

4. **Tenant User creates VM without networking parameters:**
   ```bash
   # No network_attachments specified
   osac create computeinstance --template ocp_virt_vm --name my-vm
   ```
   - fulfillment-service:
     - Detects `network_attachments` field is omitted or empty
     - Queries the tenant's default Subnet (labeled `osac.openshift.io/default: "true"`)
     - Populates `network_attachments` with the default Subnet and tenant default SecurityGroup when it exists
     - The effective NetworkACL is resolved from the Subnet association and is not copied into the workload attachment
   - Creates ComputeInstance CR with resolved `network_attachments`
   - osac-operator reconciles normally (VM provisioned on default subnet)

5. **Tenant User retrieves resource and sees resolved defaults:**
   ```bash
   osac get computeinstance my-vm -o yaml
   ```
   Output shows:
   ```yaml
   spec:
     network_attachments:
       - subnet: { name: "default-subnet" }
         primary: true
   ```

#### Auto ExternalIP for Single-Call Inbound Connectivity

6. **Tenant User creates VM with auto ExternalIP:**
   ```bash
   osac create computeinstance --template ocp_virt_vm \
     --external-ip-attachment --name my-vm
   ```
   - fulfillment-service:
     - Resolves `network_attachments` using the shared omitted/empty/partial field-level defaulting rules
     - Reads `auto_external_ip_attachment: true`
     - Auto-selects an IPv4 ExternalIPPool (READY, most available capacity)
     - Creates ExternalIP + ExternalIPAttachment in the same DB transaction — both start in **Pending** state. Pool capacity is decremented atomically.
     - Both carry the canonical `osac.openshift.io/auto-created: "true"` marker and an exact immutable owner relationship to the workload. A label alone is not sufficient ownership proof.
   - ComputeInstance CR created with `auto_external_ip_attachment: true`
   - osac-operator reconciles ExternalIP (every selected manager allocates or confirms the address → Allocated), then VM provisioning, then ExternalIPAttachment controller activates once ExternalIP is Allocated AND `compute_network_attachment_statuses` is populated with the primary attachment's `ip_address`
   - See [Unified Networking — Auto-provisioning lifecycle](/enhancements/OSAC-1433-unified-networking/design.md#external-access-same-for-all-resource-types) for the full two-phase flow
   - Result: VM is reachable via ExternalIP

7. **If ExternalIPPool has no capacity:**
   - fulfillment-service returns error: `ExternalIPPool exhaustion: no available capacity in any READY pool for IPv4`
   - Resource is NOT persisted
   - Tenant User must use explicit ExternalIP allocation from another pool or contact admin

#### Auto ExternalIP for Clusters (Prerequisite Ordering)

8. **Tenant User creates Cluster with auto ExternalIP for API and ingress:**
   ```bash
   osac create cluster --template ocp_4_17_small \
     --external-ip-attachment --name my-cluster
   ```
   - fulfillment-service:
     - Resolves the singular `network_attachment` using the shared omitted/empty/partial field-level defaulting rules
     - Reads `auto_external_ip_attachment: true`
     - Auto-selects ExternalIPPool (same algorithm)
     - Creates two ExternalIPs + two ExternalIPAttachments in the same DB transaction — all start in **Pending** state. Pool capacity decremented atomically.
     - All carry the canonical `osac.openshift.io/auto-created: "true"`
       marker and an exact immutable owner relationship to the Cluster; the
       marker alone is not ownership proof.
   - osac-operator ExternalIP controller dispatches to every selected
     manager → ExternalIPs transition to Allocated only after all selected
     implementations assign/confirm the address
   - Cluster provisioning proceeds — MetalLB allocates internal VIPs from its IPAddressPool. Template discovers VIPs and writes to ClusterOrder status (`apiEndpoint`, `ingressEndpoint`).
   - ExternalIPAttachment controllers activate once ExternalIP is Allocated AND ClusterOrder `apiEndpoint`/`ingressEndpoint` are populated → creates DNAT: external IP → internal VIP
   - See [Unified Networking — Auto-provisioning lifecycle](/enhancements/OSAC-1433-unified-networking/design.md#external-access-same-for-all-resource-types) for the full two-phase flow
   - Result: Cluster is reachable via ExternalIPs for both API and ingress

9. **CLI flag mapping for all workload types:**
   - `--external-ip-attachment` → `auto_external_ip_attachment: true` for VM and BM (one automatic ExternalIP + ExternalIPAttachment) and Cluster (one API and one ingress ExternalIP + ExternalIPAttachment)
   - Omitting the flag → `auto_external_ip_attachment: false`
   - The flag is create-time-only; changing it requires deleting and recreating the workload
   - `--network-attachment` follows the shared CLI contract: zero or one structured value; omitting the option resolves the default Subnet, an API empty attachment message/list follows the same rule, an empty CLI key/value is rejected, and a partial value defaults only its missing Subnet

#### Auto-Cleanup on Deletion

10. **Tenant User deletes resource with auto-created ExternalIP:**
    ```bash
    osac delete computeinstance my-vm
    ```
    - osac-operator ComputeInstance controller finalizer:
      - Queries only ExternalIPAttachment and ExternalIP resources with the canonical auto-created marker and an exact immutable owner relationship to this ComputeInstance
      - Deletes ExternalIPAttachment first (DNAT rule removed), waits for full removal, then deletes ExternalIP (IP returned to pool)
      - If cleanup fails, the finalizer remains and the parent stays `Deleting`; the parent is not removed to leave an orphan
    - **Manually created resources are NOT cleaned up** — a manually created
      ExternalIP persists until the tenant deletes it. A manually created
      ExternalIPAttachment targeting the parent remains a reverse reference and
      blocks parent deletion until the tenant deletes the attachment; it is not
      detached or changed to Pending implicitly.
- **Default networking resources (VN, Subnet, SecurityGroup, NetworkACL, and NATGateway) are NOT part of workload auto-cleanup** — they are tenant-scoped and shared across resources. Their deletion uses the shared leaf-first dependency guards.

11. **Tenant Admin inspects and replaces default resources when needed:**
    ```bash
    # List default resources
    osac get virtualnetworks --filter 'labels["osac.openshift.io/default"]="true"'
    osac get subnets --filter 'labels["osac.openshift.io/default"]="true"'
    osac get network-acls --filter 'labels["osac.openshift.io/default"]="true"'
    osac get natgateways --filter 'labels["osac.openshift.io/default"]="true"'

    ```
    - Default resources and all network-owned fields are read-only after creation; update and patch requests are rejected
    - To change a default network, remove dependencies, delete it, and create a replacement
    - Default resources cannot be deleted while any resource depends on them. The API reports direct blocker kind, ID/name, relationship, and remediation; deletion-in-progress children remain blockers until archived.

### API Extensions

#### Proto (fulfillment-service)

**NetworkClass defaults configuration:**

```protobuf
message NetworkClassSpec {
  // ... existing fields ...
  NetworkDefaults defaults = 10; // required provider configuration
  int32 metallb_vip_prefix_length = 11; // required for the CaaS/MetalLB VIP path; no universal default
}

message NetworkDefaults {
  string virtual_network_cidr = 1;  // e.g., "10.0.0.0/16"
  string ipv4_subnet_cidr = 2;      // e.g., "10.0.1.0/24"
}
```

**Resource-level auto external access fields:**

```protobuf
// ComputeInstance
message ComputeInstanceSpec {
  // ... existing fields ...
  optional bool auto_external_ip_attachment = 19;  // omitted/false disables auto-provisioning; true creates ExternalIP + ExternalIPAttachment
}

// BaremetalInstance
message BareMetalInstanceSpec {
  // ... existing fields ...
  optional bool auto_external_ip_attachment = 9;  // omitted/false disables auto-provisioning; true creates ExternalIP + ExternalIPAttachment
}

// Cluster
message ClusterSpec {
  // ... existing fields ...
  optional bool auto_external_ip_attachment = 10;  // omitted/false disables auto-provisioning; true creates ExternalIP + ExternalIPAttachment for API and ingress
}
```

**Default label on auto-created resources:**

All default resources created at tenant onboarding (VirtualNetwork, Subnet,
SecurityGroup, NetworkACL, and NATGateway) receive label:
```yaml
metadata:
  labels:
    osac.openshift.io/default: "true"
```

All auto-created workload resources (ExternalIP and ExternalIPAttachment created by `auto_external_ip_attachment=true`) receive label:
```yaml
metadata:
  labels:
    osac.openshift.io/auto-created: "true"
```

The ExternalIP created for an onboarding default NATGateway receives the same
label and the exact immutable NATGateway owner reference described in the
default NATGateway lifecycle. The owner reference, not the label alone,
authorizes its cleanup.

#### Operator CRD (osac-operator)

**Tenant status condition:**

```go
type TenantStatus struct {
    // ... existing fields ...
    Conditions []metav1.Condition `json:"conditions,omitempty"`
}

// New condition type
const (
    TenantConditionDefaultNetworkingReady = "DefaultNetworkingReady"
)
```

Condition values:
- `DefaultNetworkingReady: true` when all defaults (VN, IPv4 Subnet,
  SecurityGroup, NetworkACL, and NATGateway) are READY
- `DefaultNetworkingReady: false, reason: <FailureReason>` when any default resource failed to provision

**NetworkClass defaults field:**

```go
type NetworkClassSpec struct {
    // ... existing fields ...
    Defaults               *NetworkDefaults `json:"defaults"` // required provider configuration
    MetalLBVIPPrefixLength int32            `json:"metallbVIPPrefixLength,omitempty"` // required only with CaaS/MetalLB support
}

type NetworkDefaults struct {
    VirtualNetworkCIDR string              `json:"virtualNetworkCIDR"` // required canonical IPv4 CIDR
    IPv4SubnetCIDR     string              `json:"ipv4SubnetCIDR"`     // required canonical IPv4 CIDR contained by the VN
}
```

**Resource spec fields (ComputeInstance, Cluster, BaremetalInstance):**

```go
type ComputeInstanceSpec struct {
    // ... existing fields ...
    AutoExternalIPAttachment bool `json:"autoExternalIPAttachment,omitempty"`
}

type BareMetalInstanceSpec struct {
    // ... existing fields ...
    AutoExternalIPAttachment bool `json:"autoExternalIPAttachment,omitempty"`
}

type ClusterSpec struct {
    // ... existing fields ...
    AutoExternalIPAttachment bool `json:"autoExternalIPAttachment,omitempty"`
}
```

#### Server Validation (fulfillment-service)

Default Networking applies the shared [Unified Networking validation
pipeline](/enhancements/OSAC-1433-unified-networking/design.md#validation-and-enforcement-pipeline)
and adds the onboarding and field-defaulting checks below. It does not define
an alternative resource or attachment contract.

**NetworkClass defaults validation:**
- `defaults` is required on the single deployment NetworkClass; there is no enable/disable knob
- `virtual_network_cidr` must be canonical IPv4 CIDR notation
- `ipv4_subnet_cidr` must be canonical IPv4 CIDR notation and within `virtual_network_cidr`
- `metallb_vip_prefix_length` has no universal default and is required for the
  CaaS/MetalLB VIP path
- The tenant default SecurityGroup exists and may have an empty rule set,
  which means default deny. The tenant default NetworkACL is associated with
  the tenant's default Subnet and contains explicit deny-all ingress and
  allow-all egress rules. Separately, the provider-owned ACL deployment
  baseline is hard-coded to `permit` all traffic and is not tenant-configurable.

**Resource creation with optional network attachments:**
- For ComputeInstance, if `network_attachments` is omitted or empty, resolve the tenant's default Subnet and default SecurityGroup. A supplied list may contain at most one entry; default only that entry's missing subnet or SecurityGroup list, and reject a second entry. Its effective NetworkACL policy is inherited from the resolved Subnet.
- For Cluster, if `network_attachment` is omitted or an empty message, resolve the default Subnet and default SecurityGroup when it exists. If the message omits either field, default only that field.
- For BaremetalInstance, if `network_attachments` is omitted or empty, resolve the default Subnet, default SecurityGroup, and the first default fabric interface from the BareMetalInstanceType. For a supplied single entry, default only missing subnet, SecurityGroup list, or interface.
- If the mandatory default VirtualNetwork/Subnet does not exist or is not
  Ready, return `FailedPrecondition` with the attachment field, the default
  resource identity, observed state, required `Ready` state, and remediation
  to wait and retry. The human-readable message may retain the concise text
  `No default networking resources available. Please contact your
  administrator.`, but machine-readable details must identify the blocker.
  Default SecurityGroup and NetworkACL resources are required by the complete
  manager contract; an unfinished backend may use a successful no-op AAP role.
- A supplied subnet is used unchanged; defaults do not replace fields that the tenant supplied.
- The tenant default SecurityGroup belongs to the tenant default
  VirtualNetwork. If a supplied Subnet belongs to another VirtualNetwork and
  the attachment omits its SecurityGroup, defaulting fails with
  `InvalidArgument`; the service does not attach the default group from the
  default VN or create a new per-VN default group. An explicitly supplied
  SecurityGroup must likewise belong to the resolved Subnet's VirtualNetwork.
- For BaremetalInstance, the resolved list contains exactly one attachment; an explicit BMaaS list with more than one attachment is rejected.
- All resolved references must be `Ready` before the workload create is accepted.
  The resolved Subnet's effective ACL must also be `Ready`, and the resolved
  default or explicit groups must be `Ready`. Onboarding creates
  default resources in dependency order and does not create a resource merely
  to wait for a non-Ready dependency. Only the allowlisted auto-created
  ExternalIP and ExternalIPAttachment may be persisted Pending.
- A custom Subnet may exist without an ACL association, but it is not usable
  for workload placement.
  Workload creation then returns `FailedPrecondition` identifying the Subnet
  and the missing Ready effective NetworkACL. The deployment permit baseline
  The deployment permit baseline does not replace the tenant ACL.

**Auto ExternalIP allocation (when auto_external_ip_attachment: true):**
- Pool selection: pick a READY IPv4 ExternalIPPool with the most available capacity
- If multiple pools have equal capacity: selection is deterministic but implementation-defined (e.g., alphabetical by pool name)
- If no pool has capacity: return error `ExternalIPPool exhaustion: no available capacity in any READY pool for IPv4`
- Pool capacity is checked and decremented synchronously during the API call. If the pool is exhausted, the call fails and no resources are persisted (including the parent resource). "Synchronous" here means the API call validates and creates DB records atomically — actual IP address allocation by every selected manager and DNAT rule creation happen asynchronously through the operator reconciliation loop. See [Unified Networking — Auto-provisioning lifecycle](/enhancements/OSAC-1433-unified-networking/design.md#external-access-same-for-all-resource-types) for the full two-phase flow.

**Tenant-onboarding validation:**

- A Tenant cannot become `DefaultNetworkingReady` until the provider has
  created exactly one default VirtualNetwork, default IPv4 Subnet, default
  SecurityGroup, default NetworkACL associated with the default Subnet, and
  default NATGateway in the tenant scope.
- Every default resource carries the default label and the tenant ownership
  annotation. A resource with the default label but the wrong tenant, wrong
  VirtualNetwork parent, wrong address family, or non-canonical CIDR is not
  accepted as a default and cannot satisfy readiness.
- The default VN CIDR and default Subnet CIDR must pass all shared CIDR
  validation. The Subnet must be contained by the VN. The default SecurityGroup
  must reference that VN. The default NetworkACL must reference that VN and
  Subnet. The default NATGateway must reference that VN and a
  Ready/Allocated unconsumed ExternalIP.
- Onboarding selects a Ready IPv4 ExternalIPPool using the shared
  most-available-capacity rule and reserves
  one address atomically with creation of the auto-created ExternalIP. The
  ExternalIP may be Pending under the shared automatic-external-access
  exception, but the default NATGateway is not created until that ExternalIP
  is Allocated and the default VirtualNetwork is Ready. The ExternalIP carries
  `osac.openshift.io/auto-created: "true"` and an exact immutable
  `osac.openshift.io/owner-reference: "NATGateway/<id>"`; the owner reference,
  not the label alone, authorizes cleanup. Onboarding may reserve the future
  NATGateway ID/owner token before creating the auto ExternalIP; this internal
  token is not a persisted NATGateway and cannot be referenced by a tenant.
  If no Ready pool has capacity, onboarding
  creates neither the ExternalIP nor the NATGateway and reports
  `DefaultNetworkingReady: false` with an explicit ExternalIPPool exhaustion
  condition. The NATGateway is not dispatched until the ExternalIP becomes
  `Allocated`; readiness requires both resources to be Ready/Allocated.
- The tenant default SecurityGroup exists with an empty allow-rule list, which
  means default deny. A user-created
  SecurityGroup must contain at least one valid allow rule.
- The tenant default NetworkACL contains the explicit default ACL policy and is
  associated with the default Subnet. A user-created NetworkACL must contain
  at least one valid rule and one or more explicit Subnet associations.
- Onboarding creates every policy resource in the complete manager contract.
  An unfinished manager operation may use a successful no-op AAP role; it is
  not omitted from onboarding and the tenant default ACL is still created.
- Duplicate onboarding requests are idempotent only when the existing
  resources match the expected tenant, label, parent, CIDR, address family,
  and complete-manager profile. A mismatched existing default is a terminal
  configuration error requiring provider repair; it must not be silently
  adopted.

**Manual default replacement validation:**

- A Tenant Admin may create a replacement default only in that tenant's
  effective scope and only after the existing default of the same resource
  kind has been deleted after its dependencies are removed. The server
  rejects a second active default of the same kind; list order never selects
  between competing defaults.
- The `osac.openshift.io/default: "true"` label is reserved. Only the
  system onboarding path or the authorized Tenant Admin replacement path may
  set it, and the service writes and
  verifies the tenant ownership annotation rather than trusting a caller's
  cross-tenant value. A default label with the wrong tenant, parent, family,
  or canonical CIDR is rejected and cannot satisfy default readiness.
- A manually replaced tenant default SecurityGroup must reference the default
  VN and may have an empty rule list; every other user-created SecurityGroup
  requires at least one valid allow rule. A manually replaced tenant default
  NetworkACL must contain the explicit default ACL policy and remain associated
  with the default Subnet. Every other user-created NetworkACL requires at
  least one valid rule and one or more explicit Subnet associations. A manually
  replaced default still passes all ordinary readiness, same-VN, immutable
  field, and manager validation.
- The default ACL counts as the one effective ACL association on the default
  Subnet. An ordinary custom ACL cannot be associated with that Subnet while
  the default ACL exists; replacing the default ACL uses this replacement
  workflow rather than creating a second effective association.
- Manual replacement does not make the resource mutable: changing the
  default requires deleting it and creating a validated replacement, and the
  tenant remains unable to use omitted/empty attachment defaulting until the
  replacement graph is Ready.

**Default readiness validation:**

- `DefaultNetworkingReady == true` only when every default resource is Ready:
  VN and Subnet, plus tenant default SecurityGroup, NetworkACL, and NAT
  Gateway.
- A Pending or Failed default keeps the Tenant non-Ready and prevents a
  workload create that relies on that default from succeeding. The workload
  API returns a clear readiness/precondition error rather than persisting an
  unresolved attachment.
- Feedback must verify the expected resource identity and parent before
  setting a default Ready. A Ready resource from another tenant or another VN
  cannot satisfy this tenant's condition.
- If default provisioning later loses readiness, existing workloads and
  immutable resolved attachments are not rewritten. New omitted/empty
  attachment requests fail immediately with `FailedPrecondition` and identify
  the non-Ready default; they are retried only by the caller after the default
  graph recovers.

**Field-level defaulting validation:**

- ComputeInstance omitted/empty input resolves to one default Subnet, subject
  to VMaaS's zero-or-one list contract. Its effective NetworkACL policy is
  inherited from that Subnet.
- Cluster omitted/empty input resolves to one singular Cluster attachment
  containing the default Subnet.
- BaremetalInstance omitted/empty input resolves to one attachment containing
  the default Subnet and the first eligible fabric interface.
- A supplied single BM or VM attachment, or supplied singular Cluster
  attachment, receives defaults only for missing Subnet or SecurityGroup
  fields. Supplied Subnet or SecurityGroup references are never replaced;
  NetworkACL membership is inherited from the resolved Subnet and is not a
  workload attachment field.
- Defaulting occurs only after Catalog/Template precedence is resolved and
  before final shared readiness and service-specific validation. A Catalog or
  Template value that is invalid is rejected; defaulting must not repair an
  invalid explicit value.
- All resolved references are rechecked for Ready state in the same create
  transaction. Onboarding may have an incomplete graph while it waits between
  strict, ordered create calls, but it never persists a dependent default
  resource before its dependency is Ready. A direct tenant request cannot
  create a workload that points to a Pending default. The only Pending
  dependency exception is the allowlisted automatic ExternalIP and
  ExternalIPAttachment pair.

### Implementation Details/Notes/Constraints

#### Component Responsibility

| Component | Responsibility |
|-----------|---------------|
| fulfillment-service | Validate NetworkClass defaults, **create default VN/IPv4 Subnet plus SecurityGroup, NetworkACL, and NATGateway through the complete manager profile** (via its own API), associate a tenant default NetworkACL with the default Subnet, populate each resource-specific network field with the default Subnet and default SecurityGroup, auto-provision ExternalIP, track DefaultNetworkingReady condition, return error on capacity exhaustion |
| osac-operator resource controllers | Clean up workload-owned auto-created ExternalIP/ExternalIPAttachment and default-NAT-owned automatic ExternalIP via finalizers |
| osac-operator networking controllers | Reconcile default networking resources (same as manually created resources) |
| osac-installer | Configure NetworkClass defaults in setup.sh and installation overlays |

#### Default Resource Lifecycle

- **Creation:** fulfillment-service creates the default VN first and waits for `Ready` before creating the dependent Subnet or policy resources. The default SecurityGroup is created after the VN is `Ready`; the default NetworkACL is created only after both the VN and default Subnet are `Ready`. It creates NATGateway after its default VN is `Ready` and its auto-created ExternalIP is `Allocated`. The auto-created ExternalIP may be Pending under the shared automatic-external-access exception; the NATGateway may not be created Pending on that dependency. All resources are persisted in PostgreSQL and reconciled to K8s CRs like any other resource.
- **Labeling:** All default resources labeled `osac.openshift.io/default: "true"`
- **Visibility:** Default resources appear in list/detail views like any other resource
- **Mutability:** Default resources and all network-owned fields are immutable after creation; changes require delete and recreate after dependencies are removed
- **Deletion protection:** Default resources cannot be deleted while any resource depends on them (e.g., subnet deletion blocked if VMs reference it)
- **Tenant deletion:** Tenant deletion uses the shared leaf-first dependency contract. Owner references do not bypass reverse-reference validation or implicitly delete default VirtualNetworks, Subnets, SecurityGroups, NetworkACLs, or NATGateways; each resource is deleted only after its blockers have been removed. When an admitted default NATGateway delete reaches its own finalizer, only its exact OSAC-owned automatic ExternalIP may be cleaned up, after NATGateway backend cleanup and before the NATGateway finalizer is removed. The ExternalIPPool is never cascaded.

#### Auto-Provisioned Resource Lifecycle

- **Creation:** fulfillment-service creates ExternalIP or ExternalIPAttachment when auto_external_ip_attachment=true. Tenant onboarding creates the default NATGateway ExternalIP as a separate allowlisted OSAC-owned automatic resource. The pool must already be `Ready` and have capacity; only the ExternalIP and its workload attachment may be admitted Pending. The dependent default NATGateway waits for the ExternalIP to become `Allocated`.
- **Labeling:** Auto-created workload resources carry `osac.openshift.io/auto-created: "true"` and an exact immutable owner relationship.
- **Cleanup:** Parent resource finalizer deletes only its owned auto-created ExternalIP/ExternalIPAttachment resources on parent deletion. The default NATGateway finalizer may delete only its owned automatic ExternalIP after the NAT backend binding is gone. A tenant-created ExternalIP is never treated as owned.
- **Cleanup order:** Workload: ExternalIPAttachment → ExternalIP → parent resource removal. Default NAT: NATGateway backend cleanup → owned ExternalIP → NATGateway removal. The ExternalIPPool is never cascaded.
- **Cleanup failure:** The finalizer is retained, the parent remains `Deleting`, and cleanup retries. No tenant-created resource is touched and no orphan is intentionally created.
- **Manual resources NOT cleaned up:** A manually created ExternalIP persists
  until the tenant deletes it. A manually created ExternalIPAttachment targeting
  the parent blocks parent deletion until the tenant deletes the attachment; it
  is not detached or changed to Pending implicitly.

#### Prerequisite Ordering for Clusters

For clusters, two separate IP allocations happen from different sources:

- **External IPs** (from ExternalIPPool): allocated by ExternalIP controller
  via every selected manager (for the DNAT front-end)
- **Internal VIPs** (from subnet CIDR): allocated by MetalLB from its IPAddressPool (for API/ingress endpoints)

The DNAT model maps external IPs to internal VIPs:

1. fulfillment-service creates ExternalIP resources (Pending state in DB) and ExternalIPAttachments (Pending, no target VIP yet)
2. osac-operator ExternalIP controller dispatches to every selected
   manager → ExternalIPs transition to Allocated only after all selected
   implementations assign/confirm the address (e.g., 203.0.113.10)
3. Cluster provisioning proceeds — MetalLB allocates internal VIPs from its IPAddressPool on the hosting cluster (e.g., 10.0.1.200 for API, 10.0.1.201 for ingress)
4. Template discovers VIPs after MetalLB allocation, writes to ClusterOrder status (`apiEndpoint`, `ingressEndpoint`)
5. VIP feedback loop: ClusterOrder status → feedback controller → fulfillment-service syncs to Cluster status
6. ExternalIPAttachment controller activates once ExternalIP is Allocated AND the relevant endpoint is populated → creates DNAT: external IP → internal VIP

Note: the external IPs (from ExternalIPPool) and internal VIPs (from MetalLB IPAddressPool) are separate address spaces managed by separate systems. No IPAM coordination needed between them.

#### Tenant Isolation

All default and auto-created resources inherit tenant annotation from parent:
- `osac.openshift.io/tenant` annotation propagated from Tenant to default VN/Subnet/SecurityGroup/NetworkACL/NATGateway
- `osac.openshift.io/tenant` annotation propagated from ComputeInstance/Cluster/BaremetalInstance to auto-created ExternalIP/ExternalIPAttachment
- OPA policies enforce tenant-scoped list/get/create/delete; update and patch of network-owned fields are rejected

#### CIDR Overlap Across Tenants

All tenants receive the same default CIDR range as configured on the NetworkClass. Tenants are isolated at the fabric level — the unified networking API provides VirtualNetworks with any IP subnet, and the fabric manager enforces isolation regardless of overlapping CIDRs between tenants. This is a fabric-level concern, not an API-level concern.

### Security Considerations

This feature inherits the existing security model:
- Tenant isolation via `osac.openshift.io/tenant` annotation enforced by OPA policies
- Auto-provisioned resources (ExternalIP, ExternalIPAttachment) inherit tenant annotation from parent resource
- Default resources (VN, Subnet, SecurityGroup, NetworkACL, and NATGateway)
  inherit tenant annotation from Tenant resource
- No new authentication or authorization changes
- The tenant default SecurityGroup is attached by default and its empty
  allow-rule list means deny all. Replacing it requires delete and recreate
  after dependencies are removed. The tenant default NetworkACL is the default
  ACL policy for the tenant's default Subnet: deny-all ingress and allow-all
  egress. Replacing it requires delete and recreate after dependencies are
  removed.
- The provider-owned deployment baseline is separate from the tenant default
  ACL, applies only when no tenant rule matches, and is currently hard-coded to
  `permit` all traffic. It is not serialized in tenant resources or exposed as
  a tenant setting.

**Risk: Default policy is misconfigured**
- Mitigation: The default SecurityGroup and NetworkACL policies are explicit
  and visible: the default SecurityGroup has no allow rules, while the default
  NetworkACL denies ingress and allows egress. Overlapping ACL rules are
  evaluated by specificity, and equal-specificity contradictory rules are
  rejected. The separate deployment baseline is fixed to permit all and cannot
  be changed by tenant input.

### Failure Handling and Recovery

#### Tenant Onboarding Failures

- **Default VirtualNetwork provisioning fails:** Tenant enters non-READY state with condition `DefaultNetworkingReady: false, reason: VirtualNetworkProvisioningFailed, message: "..."`
- **Default IPv4 Subnet provisioning fails:** Tenant enters non-READY state with condition `DefaultNetworkingReady: false, reason: SubnetProvisioningFailed, message: "..."`
- **Default SecurityGroup provisioning fails:** Tenant enters non-READY state with condition `DefaultNetworkingReady: false, reason: SecurityGroupProvisioningFailed, message: "..."`.
- **Default NetworkACL provisioning fails:** Tenant enters non-READY state with condition `DefaultNetworkingReady: false, reason: NetworkACLProvisioningFailed, message: "..."`.
- **Default NATGateway provisioning fails:** Tenant enters non-READY state with condition `DefaultNetworkingReady: false, reason: NATGatewayProvisioningFailed, message: "..."`
- **Recovery:** Cloud Provider Admin inspects failure (check networking controller logs, AAP job logs), fixes root cause, deletes tenant, re-creates tenant

#### Resource Creation Failures

- **No default networking resources:** Since defaults are mandatory on NetworkClass (rejected at creation time without them), this scenario should not occur. If it does due to data inconsistency, resource creation without an explicit resource-specific network field returns `FailedPrecondition` with the missing default resource and field details. The human-readable message is `No default networking resources available. Please contact your administrator.`
- **ExternalIPPool capacity exhaustion:** create API call returns error: `ExternalIPPool exhaustion: no available capacity in any READY pool for IPv4`. Resource is NOT persisted.

#### Auto-Provisioned Resource Cleanup Failures

- **Transient or permanent failure:** Parent finalizer retries cleanup with
  backoff and retains the parent in `Deleting`. The finalizer is not removed
  merely to unblock deletion, and no orphan is intentionally created.

### RBAC / Tenancy

No RBAC or tenancy changes. All new resources (default networking, auto-created ExternalIP) inherit tenant isolation:
- `osac.openshift.io/tenant` annotation propagated from parent to all child resources
- OPA policies enforce tenant-scoped list/get/create/delete; update and patch of network-owned fields are rejected
- Tenant User can view, create, and delete permitted network resources via the standard API; network-owned updates are rejected
- Cloud Infrastructure Admin configures NetworkClass defaults (global, applies to all tenants)

### Observability and Monitoring

New structured log events:
- fulfillment-service: `CreatingDefaultNetworking` (info), `DefaultNetworkingReady` (info), `DefaultNetworkingFailed` (error), `PopulatedNetworkAttachmentsDefaults` (info), `AutoProvisionedExternalIP` (info), `ExternalIPPoolExhausted` (error)

New Kubernetes events on Tenant:
- `DefaultNetworkingCreated`: default VN and IPv4 Subnet creation started, plus SecurityGroup, NetworkACL, and NATGateway
- `DefaultNetworkingReady`: all supported default resources are READY
- `DefaultNetworkingFailed`: default resource provisioning failed (includes reason and failed resource name)

New Kubernetes events on ComputeInstance/Cluster/BaremetalInstance:
- `NetworkAttachmentsPopulated`: the resource-specific network field populated with tenant defaults
- `AutoExternalIPCreated`: ExternalIP and ExternalIPAttachment auto-created

No new metrics or alerts (existing provisioning duration and failure rate metrics apply).

### Risks and Mitigations

#### Risk: ExternalIPPool exhaustion

**Impact:** Auto ExternalIP allocation fails, create API call returns error, tenant cannot create resource with auto_external_ip_attachment=true.

**Mitigation:** Pool capacity visible in status; clear error directs tenant to explicit allocation from another pool or contact admin.

**Reviewed by:** Cloud Provider Admin

#### Risk: Default ACL policy is misconfigured

**Impact:** A tenant's default ACL could permit or deny more traffic than
intended for that tenant's default Subnet.

**Mitigation:** The default policy is explicit and tested as deny-all ingress
and allow-all egress. User rules are evaluated by specificity and equal-
specificity contradictory rules are rejected.

**Reviewed by:** Cloud Infrastructure Admin

#### Risk: Auto ExternalIP cleanup remains pending after partial failure

**Impact:** If parent resource finalizer cleanup fails, the parent remains in `Deleting` until the auto-created resources are cleaned up.

**Mitigation:** Parent resource finalizer handles cleanup; controller retries with backoff and retains the finalizer on failure. Ownership is checked before cleanup, and the ExternalIPPool and tenant-created resources are never cascaded.

**Reviewed by:** Platform

#### ~~Risk: Deployment misconfiguration (NetworkClass defaults not configured)~~ — Eliminated

Since defaults are mandatory (a NetworkClass without defaults is rejected at creation time), this scenario cannot occur. The osac-installer setup.sh includes NetworkClass default configuration in installation overlays, and the API validation ensures defaults are always present.

### Drawbacks

#### CIDR overlap across tenants

All tenants receive the same default CIDR range. While fabric-level isolation prevents actual IP conflicts, this may confuse tenants who expect unique CIDR ranges.

**Trade-off:** Simplicity (single default configuration) vs. per-tenant customization. Chosen approach: single default, document fabric-level isolation. Alternative: per-tenant CIDR allocation (more complex, requires IPAM).

#### Capacity exhaustion returns API error, not Failed resource

When ExternalIPPool has no capacity, the create API call returns an error and the resource is NOT persisted. This provides no audit trail.

**Trade-off:** Simplicity vs. auditability. Chosen approach: return error (resource not persisted). Alternative: create Failed resource for audit trail (adds cleanup burden).

## Alternatives (Not Implemented)

### Alternative 1: Per-tenant default CIDR allocation

Instead of all tenants receiving the same default CIDR, allocate unique CIDR ranges per tenant from a global pool.

**Rejected because:** Adds complexity (requires IPAM, CIDR allocation tracking, exhaustion handling). The unified networking API allows overlapping CIDRs between tenants (fabric-level isolation), so unique CIDRs are not required. Single default CIDR is simpler.

### Alternative 2: Capacity exhaustion creates Failed resource instead of returning error

Instead of returning an error when ExternalIPPool has no capacity, create a Failed resource with a status condition.

**Rejected because:** Pool capacity is validated synchronously during the API call — if the pool is exhausted, the call fails atomically and no resources are persisted. Creating a Failed resource adds cleanup burden and audit trail complexity. Clear API error with no persisted state is simpler.


## Open Questions

### ~~1. Should capacity exhaustion return an API error or create a Failed resource?~~ — Resolved

Resolved: Return error, no resource persisted.

## Test Plan

The executable, reviewable plan for Default Networking is maintained in
[testplan.md](testplan.md). It covers default NetworkClass configuration,
tenant onboarding, readiness and failure recovery, workload default
resolution, automatic ExternalIP behavior, and unsupported behavior. Shared
networking contracts are covered by the [Unified Networking test
plan](../OSAC-1433-unified-networking/testplan.md).
## Graduation Criteria

**Note:** This section will be updated when the enhancement is targeted at a release.

Proposed maturity level: **Tech Preview** → **GA**

Tech Preview criteria:
- [ ] NetworkClass defaults field implemented in fulfillment-service and osac-operator
- [ ] fulfillment-service creates default VN/IPv4 Subnet, SecurityGroup, NetworkACL, and NATGateway through every selected complete manager
- [ ] Tenant DefaultNetworkingReady condition functional
- [ ] Resource-specific network attachment fields are optional on all three resource types (`network_attachments` for ComputeInstance, `network_attachment` for Cluster, and `network_attachments` for BaremetalInstance)
- [ ] BMaaS default networking resolves exactly one tenant network attachment
- [ ] Auto ExternalIP attachment (auto_external_ip_attachment) functional for VM and BM
- [ ] Auto ExternalIP attachment for Cluster functional
- [ ] Auto-provisioned resource cleanup via parent finalizer functional
- [ ] Integration tests pass (E2E coverage for default networking, optional attachments, auto ExternalIP, cleanup)
- [ ] Documentation: API reference, user guide for simplified resource creation

GA criteria:
- [ ] Production deployment verified (MOC or other OSAC deployment)
- [ ] User feedback incorporated (usability, error messages, edge cases)
- [ ] osac-installer includes NetworkClass default configuration in setup.sh and overlays
- [ ] No major bugs reported in Tech Preview period
- [ ] Performance validated (tenant onboarding duration, resource creation latency)

## Upgrade / Downgrade Strategy

### Upgrade

Micro version upgrades (`x.y.N → x.y.N+2`):
- New fields (NetworkClass.defaults, auto_external_ip_attachment) are additive — existing resources continue to work
- Existing Tenants do NOT receive default networking resources retroactively (only new Tenants get defaults)
- No user action required

Minor version upgrades (`x.N → x.N+1`):
- Existing Tenants remain without default networking resources
- Tenant Admin can manually create default resources and label them `osac.openshift.io/default: "true"` to enable simplified creation for their tenant
- No breaking changes

### Downgrade

If `N+1` upgrade fails or cluster is misbehaving:
- Manual rollback: update fulfillment-service and osac-operator images to `N`
- Existing Tenants with default networking resources: default resources remain (no impact)
- Existing resources with auto-created ExternalIP: `N` server does not recognize auto_external_ip_attachment field; compatible ownership/finalizer handling must be restored before cleanup continues.
- New resource creation with auto_external_ip_attachment=true will fail (field not recognized)

Acceptable downgrade steps:
- Existing resources continue to function (default networking and auto-created resources persist)
- New resources must use explicit networking (auto_external_ip_attachment=true not supported)
- If an auto-created workload resource is still in cleanup during downgrade, keep the parent finalizer and retry the documented `ExternalIPAttachment -> ExternalIP` cleanup after the compatible control plane is restored. Do not remove the finalizer or manually delete a resource based on its label alone; ownership must be verified from the immutable owner relationship.

## Version Skew Strategy

### Control Plane Skew

fulfillment-service and osac-operator are deployed together in the same namespace and upgraded atomically (both controlled by osac-installer). No skew expected.

### Client Skew

osac-cli (n-1) with fulfillment-service (n):
- Old CLI does not support `--external-ip-attachment` flag
- Tenant must upgrade CLI to use simplified creation
- Existing explicit networking workflows remain functional

osac-cli (n) with fulfillment-service (n-1):
- New CLI uses `--external-ip-attachment` flag → old server rejects unknown field
- Workaround: use explicit ExternalIP allocation until server is upgraded

Recommendation: keep osac-cli and fulfillment-service within one minor version.

## Support Procedures

### Symptom: Tenant stuck in non-READY state, condition "DefaultNetworkingReady: false"

**Detection:**
```bash
kubectl describe tenant acme-corp -n <namespace>
# Check status.conditions for DefaultNetworkingReady
```

**Cause:** A default VirtualNetwork, IPv4 Subnet, SecurityGroup, NetworkACL, or NATGateway provisioning failed.

**Resolution:**
1. Check default networking resource status: `kubectl get virtualnetwork -n <namespace> -l osac.openshift.io/default=true`
2. If a VirtualNetwork/IPv4 Subnet/SecurityGroup/NetworkACL/NATGateway is not READY, investigate provisioning failure (check networking controller logs, AAP job logs).
3. Fix root cause (e.g., AAP connectivity issue, fabric manager error)
4. Delete tenant: `osac delete tenant acme-corp`
5. Re-create tenant: `osac create tenant --name acme-corp`

### Symptom: Resource creation fails with "No default networking resources available"

**Detection:** API call returns error: `No default networking resources available. Please contact your administrator.`

**Cause:** Tenant has no default networking resources (data inconsistency — defaults are mandatory on NetworkClass, so this should not occur under normal operation)

**Resolution:**
1. Check NetworkClass configuration: `osac get networkclass -o yaml`
2. Verify NetworkClass.spec.defaults is set (required — NetworkClass creation is rejected without defaults)
3. If tenant has no default resources despite NetworkClass having defaults, delete and re-create tenant

### Symptom: Auto-provisioned ExternalIP remains while the parent is deleting

**Detection:** The parent remains in `Deleting` and its owned ExternalIP or ExternalIPAttachment is still present.

**Cause:** Finalizer cleanup is retrying or ownership validation found an inconsistent resource.

**Resolution:**
1. Check resource deletion logs (controller logs) for cleanup errors
2. Inspect the blocker details and controller status.
3. Correct the backend or ownership condition and allow the finalizer to retry.

### Disabling the feature

To disable auto ExternalIP attachment:
- Remove or redact ExternalIPPool CRs (capacity exhaustion prevents auto allocation)
- No API extension to disable NetworkClass defaults (fields are part of CRD, cannot be removed at runtime)

Consequences:
- Auto ExternalIP allocation fails with error (resource not created)
- Manual ExternalIP workflows remain functional
- Default networking at tenant onboarding is partially functional — VN,
  Subnet, SecurityGroup, NetworkACL, and NATGateway are created, but an
  enabled NATGateway may fail
  when it requires an unavailable ExternalIP pool. Auto external access is
  disabled

## Infrastructure Needed

- osac-installer: NetworkClass default configuration in setup.sh and installation overlays
- fulfillment-service: NetworkClass defaults validation, default VN/IPv4
  Subnet plus conditional SecurityGroup, NetworkACL, and NATGateway creation at tenant
  onboarding, network_attachments population, auto ExternalIP provisioning,
  DefaultNetworkingReady condition tracking
- Integration test environment: kind cluster with Tenant, NetworkClass, ExternalIPPool resources
