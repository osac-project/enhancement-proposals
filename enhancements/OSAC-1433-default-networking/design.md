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
replaces:
  - N/A
superseded-by:
  - N/A
---

# Default Networking — Simplified Resource Creation

Default networking provides automatic resource provisioning at tenant onboarding (including a default Subnet and a tenant default NetworkACL, plus an optional NATGateway when the deployment supports it), optional resource-specific network attachments with defaults, auto ExternalIP provisioning, and auto-cleanup on deletion.

## Summary

This document is a per-service expansion of the [Unified Networking EP](/enhancements/OSAC-1433-unified-networking/design.md), providing default networking automation and simplified resource creation. When a tenant is created, the system provisions a default VirtualNetwork, IPv4 Subnet, and tenant default NetworkACL, plus a NATGateway only when the NetworkClass supports it. The tenant default NetworkACL is associated with the tenant's default Subnet and contains the explicit default ACL policy: deny all ingress and allow all egress. Workloads omit ACL membership from their attachments; their effective ACL is inherited from the selected Subnet. Resources (ComputeInstance, Cluster, BaremetalInstance) can omit their resource-specific network attachment field and use the tenant default Subnet. For BMaaS, default resolution produces one tenant network attachment on one physical NIC; BMaaS does not support multi-NIC or multi-homed attachments. Auto ExternalIP modes create Pending records synchronously and complete allocation and activation asynchronously. See [PRD](prd.md) for detailed requirements.
Shared field types, formats, presence rules, allowed values, and validation
are defined by the [Unified Networking field contract](/enhancements/OSAC-1433-unified-networking/design.md#field-types-formats-and-validation).

The shared networking resource model, IPv4-only scope, and connected
single-hub deployment boundary are defined by the [Unified Networking
design](/enhancements/OSAC-1433-unified-networking/design.md#deployment-topology).

## Motivation

A reachable resource in OSAC requires networking resources: VirtualNetwork, Subnet, NetworkACL, the resource itself, ExternalIP, and ExternalIPAttachment. Default networking eliminates this friction — a single create command produces a reachable instance by leveraging tenant defaults provisioned at onboarding.

### Goals

- Single-call resource creation with sensible networking defaults
- Default networking resources (VN, IPv4 Subnet, NetworkACL, and NATGateway when supported) provisioned at tenant onboarding
- Optional resource-specific network attachment field on all resource types
- Auto ExternalIP mode for inbound connectivity
- Auto-cleanup of auto-created resources on deletion
- Tenant-scoped default resources (visible, read-only after creation, and lifecycle-managed by tenant)

### Non-Goals

- Custom default configurations per tenant (all tenants receive the same defaults)
- Auto-provisioning of additional VirtualNetworks or Subnets beyond the initial default
- UI support for simplified creation (deferred — API and CLI only)
- Automatic migration of existing resources to use defaults

NetworkACL rule evaluation is defined by the [Unified Networking
NetworkACL rule semantics](/enhancements/OSAC-1433-unified-networking/design.md#networkacl-rule-semantics).
Default networking creates each tenant's default NetworkACL and associates it
with that tenant's default Subnet. Its explicit policy is deny-all ingress and allow-all
egress. It is distinct from the provider-owned deployment default ACL policy
(the deployment baseline), which is hard-coded to `permit` all traffic and is
used as the least-specific fallback when no tenant rule matches.

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
resolution, the tenant's default Subnet is selected. The effective NetworkACL
is inherited from that Subnet.

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

The design covers three capabilities: default networking at tenant onboarding
(including NATGateway only when the manager capability is available), optional
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
   - **fulfillment-service** creates Tenant record, then creates default networking resources through its own API (same path as tenant-created resources — persisted in PostgreSQL, reconciled to K8s CRs):
     - Creates default VirtualNetwork with label `osac.openshift.io/default: "true"`, using CIDR from NetworkClass defaults
     - Creates default IPv4 Subnet with label `osac.openshift.io/default: "true"`, using `ipv4SubnetCIDR` from NetworkClass defaults
     - Creates the tenant default NetworkACL with label `osac.openshift.io/default: "true"`, associates it with the tenant's default Subnet, and installs the default ACL policy: deny-all ingress and allow-all egress
     - If the NetworkClass advertises `natGateway: true`, creates a default NATGateway with an auto-allocated ExternalIP on the default VirtualNetwork, labeled `osac.openshift.io/default: "true"`; in K8s-only OVN mode, NATGateway is unsupported and is not created
   - Reads NetworkClass defaults configuration (single NetworkClass per deployment)
   - Default resources go through the normal reconciliation path: fulfillment-service reconciler pushes CRs → osac-operator networking controllers dispatch to fabric/k8s managers → resources transition to READY
   - fulfillment-service tracks default networking readiness on the Tenant: sets `DefaultNetworkingReady` condition once all supported default resources (VN, IPv4 Subnet, NetworkACL, and NATGateway when enabled) reach READY state (via feedback)
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
     - Populates `network_attachments` with the default Subnet only
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
     - Both labeled `osac.openshift.io/auto-created: "true"`. ExternalIP also labeled `osac.openshift.io/auto-created-for: <resource-id>` for orphan cleanup.
   - ComputeInstance CR created with `auto_external_ip_attachment: true`
   - osac-operator reconciles ExternalIP (the configured network manager allocates the address → Allocated), then VM provisioning, then ExternalIPAttachment controller activates once ExternalIP is Allocated AND `compute_network_attachment_statuses` is populated with the primary attachment's `ip_address`
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
     - All labeled `osac.openshift.io/auto-created: "true"`
   - osac-operator ExternalIP controller dispatches to fabric manager → ExternalIPs transition to Allocated (external addresses assigned)
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
      - Queries ExternalIPAttachment and ExternalIP labeled `osac.openshift.io/auto-created: "true"` referencing this ComputeInstance
      - Deletes ExternalIPAttachment first (DNAT rule removed)
      - Deletes ExternalIP second (IP returned to pool)
      - If cleanup fails permanently (after retries): finalizer is removed, parent resource deleted, orphaned resources left in cluster
    - **Manually created resources are NOT cleaned up** — a manually created
      ExternalIP persists until the tenant deletes it. A manually created
      ExternalIPAttachment targeting the parent remains a reverse reference and
      blocks parent deletion until the tenant deletes the attachment; it is not
      detached or changed to Pending implicitly.
    - **Default networking resources (VN, Subnet, NetworkACL, and NATGateway when supported) are NOT cleaned up** — they are tenant-scoped and shared across resources

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
    - Default resources cannot be deleted while any resource depends on them (subnet deletion blocked if VMs reference it)

### API Extensions

#### Proto (fulfillment-service)

**NetworkClass defaults configuration:**

```protobuf
message NetworkClassSpec {
  // ... existing fields ...
  NetworkDefaults defaults = 10; // required provider configuration
  int32 metallb_vip_prefix_length = 11; // required when CaaS/MetalLB support is advertised; no universal default
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
NetworkACL, and NATGateway when supported) receive label:
```yaml
metadata:
  labels:
    osac.openshift.io/default: "true"
```

All auto-created resources (ExternalIP, ExternalIPAttachment created by auto_external_ip_attachment=true) receive label:
```yaml
metadata:
  labels:
    osac.openshift.io/auto-created: "true"
```

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
- `DefaultNetworkingReady: true` when all supported defaults (VN, IPv4 Subnet,
  NetworkACL, and NATGateway when enabled) are READY
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
- `metallb_vip_prefix_length` has no universal default and is required only when CaaS/MetalLB VIP support is advertised
- The tenant default NetworkACL is associated with the tenant's default Subnet
  and contains explicit deny-all ingress and allow-all egress rules. It is the
  default ACL policy. Separately, the provider-owned deployment baseline is
  hard-coded to `permit` all traffic and is not tenant-configurable.

**Resource creation with optional network attachments:**
- For ComputeInstance, if `network_attachments` is omitted or empty, resolve the tenant's default Subnet. A supplied list may contain at most one entry; default only that entry's missing subnet, and reject a second entry. The effective NetworkACL is inherited from the resolved Subnet.
- For Cluster, if `network_attachment` is omitted or an empty message, resolve the default Subnet. If the message omits the subnet, default that field.
- For BaremetalInstance, if `network_attachments` is omitted or empty, resolve the default Subnet and the first default fabric interface from the BareMetalInstanceType. For a supplied single entry, default only missing subnet or interface.
- If no defaults exist (should not occur — defaults are mandatory on NetworkClass): return error `No default networking resources available. Please contact your administrator.`
- A supplied subnet is used unchanged; defaults do not replace fields that the tenant supplied.
- For BaremetalInstance, the resolved list contains exactly one attachment; an explicit BMaaS list with more than one attachment is rejected.
- All resolved references must be `Ready` before the workload create is accepted. Internal onboarding/default transactions may create resources in Pending state and must requeue until they become Ready.

**Auto ExternalIP allocation (when auto_external_ip_attachment: true):**
- Pool selection: pick a READY IPv4 ExternalIPPool with the most available capacity
- If multiple pools have equal capacity: selection is deterministic but implementation-defined (e.g., alphabetical by pool name)
- If no pool has capacity: return error `ExternalIPPool exhaustion: no available capacity in any READY pool for IPv4`
- Pool capacity is checked and decremented synchronously during the API call. If the pool is exhausted, the call fails and no resources are persisted (including the parent resource). "Synchronous" here means the API call validates and creates DB records atomically — actual IP address allocation from the fabric manager and DNAT rule creation happen asynchronously through the operator reconciliation loop. See [Unified Networking — Auto-provisioning lifecycle](/enhancements/OSAC-1433-unified-networking/design.md#external-access-same-for-all-resource-types) for the full two-phase flow.

**Tenant-onboarding validation:**

- A Tenant cannot become `DefaultNetworkingReady` until the provider has
  created exactly one default VirtualNetwork, one default IPv4 Subnet, and
  one tenant default NetworkACL in the tenant scope, associated with
  the default Subnet. A default NATGateway
  is required only when the resolved NetworkClass advertises NATGateway
  support.
- Every default resource carries the default label and the tenant ownership
  annotation. A resource with the default label but the wrong tenant, wrong
  VirtualNetwork parent, wrong address family, or non-canonical CIDR is not
  accepted as a default and cannot satisfy readiness.
- The default VN CIDR and default Subnet CIDR must pass all shared CIDR
  validation. The Subnet must be contained by the VN and the default
  NetworkACL must reference that VN. The default NATGateway, when
  supported, must reference that VN and a Ready/Allocated unconsumed
  ExternalIP.
- When NATGateway is supported, onboarding selects a Ready IPv4
  ExternalIPPool using the shared most-available-capacity rule and reserves
  one address atomically with creation of the auto-created ExternalIP and
  Pending default NATGateway under the shared internal default-resource
  transaction exception. If no Ready pool has capacity, onboarding
  creates neither the ExternalIP nor the NATGateway and reports
  `DefaultNetworkingReady: false` with an explicit ExternalIPPool exhaustion
  condition. The NATGateway is not dispatched until the ExternalIP becomes
  `Allocated`; readiness requires both resources to be Ready/Allocated.
- The tenant default NetworkACL contains the explicit default ACL
  policy and is associated with the default Subnet. A user-created NetworkACL
  must contain at least one valid rule and one or more explicit Subnet
  associations.
- In K8s-only mode, onboarding must not attempt to create a NATGateway. The
  absence of NAT capability is a successful expected configuration, not a
  failed default resource and not an indefinitely Pending condition.
- Duplicate onboarding requests are idempotent only when the existing
  resources match the expected tenant, label, parent, CIDR, address family,
  and manager-derived capability. A mismatched existing default is a terminal
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
- A manually replaced tenant default NetworkACL must contain the explicit default ACL
  policy and remain associated with the default Subnet. Every other
  user-created NetworkACL requires at least one valid rule and one or more
  explicit Subnet associations. A manually replaced default still passes all
  ordinary readiness, same-VN, immutable field, and manager validation.
- Manual replacement does not make the resource mutable: changing the
  default requires deleting it and creating a validated replacement, and the
  tenant remains unable to use omitted/empty attachment defaulting until the
  replacement graph is Ready.

**Default readiness validation:**

- `DefaultNetworkingReady == true` only when every default resource required by
  the NetworkClass capability set is Ready: VN, Subnet, tenant default NetworkACL,
  and NAT Gateway when supported. Unsupported resources are excluded from the
  readiness set.
- A Pending or Failed default keeps the Tenant non-Ready and prevents a
  workload create that relies on that default from succeeding. The workload
  API returns a clear readiness/precondition error rather than persisting an
  unresolved attachment.
- Feedback must verify the expected resource identity and parent before
  setting a default Ready. A Ready resource from another tenant or another VN
  cannot satisfy this tenant's condition.
- If default provisioning later loses readiness, existing workloads and
  immutable resolved attachments are not rewritten. New omitted/empty
  attachment requests are blocked or remain Pending according to the shared
  API contract until the defaults recover.

**Field-level defaulting validation:**

- ComputeInstance omitted/empty input resolves to one default Subnet, subject
  to VMaaS's zero-or-one list contract. The effective NetworkACL is inherited
  from that Subnet.
- Cluster omitted/empty input resolves to one singular Cluster attachment
  containing the default Subnet.
- BaremetalInstance omitted/empty input resolves to one attachment containing
  the default Subnet and the first eligible fabric interface.
- A supplied single BM or VM attachment, or supplied singular Cluster
  attachment, receives defaults only for a missing Subnet. Supplied Subnet
  references are never replaced; NetworkACL membership is not a workload
  attachment field.
- Defaulting occurs only after Catalog/Template precedence is resolved and
  before final shared readiness and service-specific validation. A Catalog or
  Template value that is invalid is rejected; defaulting must not repair an
  invalid explicit value.
- All resolved references are rechecked for Ready state in the same create
  transaction. The only Pending default graph permitted is the internal
  tenant-onboarding/auto-provisioning graph; a direct tenant request cannot
  create a workload that points to a Pending default.

### Implementation Details/Notes/Constraints

#### Component Responsibility

| Component | Responsibility |
|-----------|---------------|
| fulfillment-service | Validate NetworkClass defaults, **create default VN/IPv4 Subnet/NetworkACL and NATGateway when supported at tenant onboarding** (via its own API), associate each tenant default NetworkACL with that tenant's default Subnet, populate each resource-specific network field with the default Subnet, auto-provision ExternalIP, track DefaultNetworkingReady condition, return error on capacity exhaustion |
| osac-operator resource controllers | Clean up auto-created ExternalIP and ExternalIPAttachment via finalizer |
| osac-operator networking controllers | Reconcile default networking resources (same as manually created resources) |
| osac-installer | Configure NetworkClass defaults in setup.sh and installation overlays |

#### Default Resource Lifecycle

- **Creation:** fulfillment-service creates default VN, IPv4 Subnet, and one tenant default NetworkACL at tenant onboarding, associates the ACL with that tenant's default Subnet, installs deny-all ingress and allow-all egress, and creates NATGateway only when the NetworkClass advertises support (via its own API — resources are persisted in PostgreSQL and reconciled to K8s CRs like any other resource)
- **Labeling:** All default resources labeled `osac.openshift.io/default: "true"`
- **Visibility:** Default resources appear in list/detail views like any other resource
- **Mutability:** Default resources and all network-owned fields are immutable after creation; changes require delete and recreate after dependencies are removed
- **Deletion protection:** Default resources cannot be deleted while any resource depends on them (e.g., subnet deletion blocked if VMs reference it)
- **Tenant deletion:** Default resources are deleted when tenant is deleted (owner reference cleanup)

#### Auto-Provisioned Resource Lifecycle

- **Creation:** fulfillment-service creates ExternalIP or ExternalIPAttachment when auto_external_ip_attachment=true
- **Labeling:** All auto-created resources labeled `osac.openshift.io/auto-created: "true"`
- **Cleanup:** Parent resource finalizer deletes auto-created ExternalIP/ExternalIPAttachment on parent deletion
- **Cleanup order:** ExternalIPAttachment → ExternalIP → parent resource removal
- **Cleanup failure:** If cleanup fails permanently (after retries), finalizer is removed, parent deleted, orphaned ExternalIP/ExternalIPAttachment left in cluster (manual cleanup required)
- **Manual resources NOT cleaned up:** A manually created ExternalIP persists
  until the tenant deletes it. A manually created ExternalIPAttachment targeting
  the parent blocks parent deletion until the tenant deletes the attachment; it
  is not detached or changed to Pending implicitly.

#### Prerequisite Ordering for Clusters

For clusters, two separate IP allocations happen from different sources:

- **External IPs** (from ExternalIPPool): allocated by ExternalIP controller via fabric manager (for DNAT front-end)
- **Internal VIPs** (from subnet CIDR): allocated by MetalLB from its IPAddressPool (for API/ingress endpoints)

The DNAT model maps external IPs to internal VIPs:

1. fulfillment-service creates ExternalIP resources (Pending state in DB) and ExternalIPAttachments (Pending, no target VIP yet)
2. osac-operator ExternalIP controller dispatches to fabric manager → ExternalIPs transition to Allocated (external addresses assigned, e.g., 203.0.113.10)
3. Cluster provisioning proceeds — MetalLB allocates internal VIPs from its IPAddressPool on the hosting cluster (e.g., 10.0.1.200 for API, 10.0.1.201 for ingress)
4. Template discovers VIPs after MetalLB allocation, writes to ClusterOrder status (`apiEndpoint`, `ingressEndpoint`)
5. VIP feedback loop: ClusterOrder status → feedback controller → fulfillment-service syncs to Cluster status
6. ExternalIPAttachment controller activates once ExternalIP is Allocated AND the relevant endpoint is populated → creates DNAT: external IP → internal VIP

Note: the external IPs (from ExternalIPPool) and internal VIPs (from MetalLB IPAddressPool) are separate address spaces managed by separate systems. No IPAM coordination needed between them.

#### Tenant Isolation

All default and auto-created resources inherit tenant annotation from parent:
- `osac.openshift.io/tenant` annotation propagated from Tenant to default VN/Subnet/NetworkACL/NATGateway
- `osac.openshift.io/tenant` annotation propagated from ComputeInstance/Cluster/BaremetalInstance to auto-created ExternalIP/ExternalIPAttachment
- OPA policies enforce tenant-scoped list/get/create/delete; update and patch of network-owned fields are rejected

#### CIDR Overlap Across Tenants

All tenants receive the same default CIDR range as configured on the NetworkClass. Tenants are isolated at the fabric level — the unified networking API provides VirtualNetworks with any IP subnet, and the fabric manager enforces isolation regardless of overlapping CIDRs between tenants. This is a fabric-level concern, not an API-level concern.

### Security Considerations

This feature inherits the existing security model:
- Tenant isolation via `osac.openshift.io/tenant` annotation enforced by OPA policies
- Auto-provisioned resources (ExternalIP, ExternalIPAttachment) inherit tenant annotation from parent resource
- Default resources (VN, Subnet, NetworkACL, NATGateway) inherit tenant annotation from Tenant resource
- No new authentication or authorization changes
- The tenant default NetworkACL is the default ACL policy for the tenant's
  default Subnet: deny-all ingress and allow-all egress. Replacing it requires delete
  and recreate after dependencies are removed.
- The provider-owned deployment baseline is separate from the tenant default
  ACL, applies only when no tenant rule matches, and is currently hard-coded to
  `permit` all traffic. It is not serialized in tenant resources or exposed as
  a tenant setting.

**Risk: Default ACL policy is misconfigured**
- Mitigation: The default NetworkACL policy is explicit and visible: deny-all
  ingress and allow-all egress. Overlapping user rules are evaluated by
  specificity, and equal-specificity contradictory rules are rejected. The
  separate deployment baseline is fixed to permit all and cannot be changed by
  tenant input.

### Failure Handling and Recovery

#### Tenant Onboarding Failures

- **Default VirtualNetwork provisioning fails:** Tenant enters non-READY state with condition `DefaultNetworkingReady: false, reason: VirtualNetworkProvisioningFailed, message: "..."`
- **Default IPv4 Subnet provisioning fails:** Tenant enters non-READY state with condition `DefaultNetworkingReady: false, reason: SubnetProvisioningFailed, message: "..."`
- **Default NetworkACL provisioning fails:** Tenant enters non-READY state with condition `DefaultNetworkingReady: false, reason: NetworkACLProvisioningFailed, message: "..."`
- **Default NATGateway provisioning fails when enabled:** Tenant enters non-READY state with condition `DefaultNetworkingReady: false, reason: NATGatewayProvisioningFailed, message: "..."`
- **Recovery:** Cloud Provider Admin inspects failure (check networking controller logs, AAP job logs), fixes root cause, deletes tenant, re-creates tenant

#### Resource Creation Failures

- **No default networking resources:** Since defaults are mandatory on NetworkClass (rejected at creation time without them), this scenario should not occur. If it does due to data inconsistency, resource creation without an explicit resource-specific network field returns error: `No default networking resources available. Please contact your administrator.`
- **ExternalIPPool capacity exhaustion:** create API call returns error: `ExternalIPPool exhaustion: no available capacity in any READY pool for IPv4`. Resource is NOT persisted.

#### Auto-Provisioned Resource Cleanup Failures

- **Transient failure:** Parent finalizer retries cleanup (exponential backoff)
- **Permanent failure:** After N retries, finalizer is removed, parent resource deleted, orphaned ExternalIP/ExternalIPAttachment left in cluster
- **Manual cleanup required:** Tenant Admin or Cloud Provider Admin manually deletes orphaned resources (identified by label `osac.openshift.io/auto-created: "true"` with no parent reference)

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
- `DefaultNetworkingCreated`: supported default VN, IPv4 Subnet, NetworkACL, and NATGateway creation started
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

#### Risk: Auto ExternalIP orphans on partial failure

**Impact:** If parent resource finalizer cleanup fails permanently, orphaned ExternalIP/ExternalIPAttachment resources remain in cluster.

**Mitigation:** Parent resource finalizer handles cleanup; controller retries on transient failures. If cleanup permanently fails, finalizer is removed and parent deleted — orphaned ExternalIPs must be cleaned up manually by Tenant Admin or Cloud Provider Admin.

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
- [ ] fulfillment-service creates default VN/IPv4 Subnet/NetworkACL and NATGateway only when the manager capability supports it
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
- Existing resources with auto-created ExternalIP: `N` server does not recognize auto_external_ip_attachment field, auto-created resources remain (manual cleanup required if not needed)
- New resource creation with auto_external_ip_attachment=true will fail (field not recognized)

Acceptable downgrade steps:
- Existing resources continue to function (default networking and auto-created resources persist)
- New resources must use explicit networking (auto_external_ip_attachment=true not supported)
- Manually delete orphaned auto-created resources if not needed (identified by label `osac.openshift.io/auto-created: "true"`)

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

**Cause:** A supported default VirtualNetwork, IPv4 Subnet, NetworkACL, or NATGateway provisioning failed

**Resolution:**
1. Check default networking resource status: `kubectl get virtualnetwork -n <namespace> -l osac.openshift.io/default=true`
2. If a supported VirtualNetwork/IPv4 Subnet/NetworkACL/NATGateway is not READY, investigate provisioning failure (check networking controller logs, AAP job logs)
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

### Symptom: Auto-provisioned ExternalIP not cleaned up after resource deletion

**Detection:** `kubectl get externalip` shows orphaned ExternalIP labeled `osac.openshift.io/auto-created: "true"` with no parent

**Cause:** Finalizer cleanup failed permanently

**Resolution:**
1. Check resource deletion logs (controller logs) for cleanup errors
2. Manually delete orphaned ExternalIPAttachment: `kubectl delete externalipattachment <name> -n <namespace>`
3. Manually delete orphaned ExternalIP: `kubectl delete externalip <name> -n <namespace>`

### Disabling the feature

To disable auto ExternalIP attachment:
- Remove or redact ExternalIPPool CRs (capacity exhaustion prevents auto allocation)
- No API extension to disable NetworkClass defaults (fields are part of CRD, cannot be removed at runtime)

Consequences:
- Auto ExternalIP allocation fails with error (resource not created)
- Manual ExternalIP workflows remain functional
- Default networking at tenant onboarding is partially functional — VN, Subnets, and NetworkACL are created, but an enabled NATGateway may fail when it requires an unavailable ExternalIP pool. Auto external access is disabled

## Infrastructure Needed

- osac-installer: NetworkClass default configuration in setup.sh and installation overlays
- fulfillment-service: NetworkClass defaults validation, default VN/IPv4 Subnet/NetworkACL and conditional NATGateway creation at tenant onboarding, network_attachments population, auto ExternalIP provisioning, DefaultNetworkingReady condition tracking
- Integration test environment: kind cluster with Tenant, NetworkClass, ExternalIPPool resources
