---
title: default-networking
authors:
  - dmanor@redhat.com
creation-date: 2026-07-08
last-updated: 2026-07-08
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1029
prd: "prd.md"
see-also:
  - "/enhancements/unified-networking"
  - "/enhancements/vmaas-networking"
  - "/enhancements/caas-networking"
  - "/enhancements/bmaas-networking"
replaces:
  - N/A
superseded-by:
  - N/A
---

# Default Networking — Simplified Resource Creation

This enhancement provides default networking resources (including dual-stack subnets and NATGateway) at tenant onboarding, optional network_attachments with defaults, auto ExternalIP provisioning, and auto-cleanup on deletion.

## Summary

This enhancement is an expansion of the [Unified Networking EP](/enhancements/unified-networking/design.md), providing default networking automation and simplified resource creation. When a tenant is created, the system automatically provisions a default VirtualNetwork, IPv4 Subnet, IPv6 Subnet, SecurityGroup, and NATGateway based on NetworkClass configuration (dual-stack). Resources (ComputeInstance, Cluster, BaremetalInstance) can omit network_attachments and use tenant defaults. Auto ExternalIP modes enable fully connected resources in a single API call. See [PRD](prd.md) for detailed requirements.

## Motivation

Creating a reachable resource in OSAC requires 6+ sequential API calls: VirtualNetwork, Subnet, SecurityGroup, the resource itself, ExternalIP, and ExternalIPAttachment. Every tenant must understand the full networking resource model before provisioning their first VM, cluster, or bare-metal server. This friction slows onboarding, increases the chance of misconfiguration, and makes OSAC harder to adopt compared to platforms where a single create command produces a reachable instance.

### What Already Works

- Tenant controller exists and reconciles Tenant resources
- VirtualNetwork, Subnet, SecurityGroup CRDs and controllers are implemented
- ExternalIP and ExternalIPAttachment provisioning works end-to-end
- NATGateway resource is implemented (OSAC-1676)
- NetworkClass resource exists with defaults configuration
- Resource creation with explicit network_attachments works for all three resource types

### What's Missing

- No default networking resources at tenant onboarding
- No default CIDR or SecurityGroup rules configuration on NetworkClass
- network_attachments field is required — no defaults applied when omitted
- No auto ExternalIP allocation mode
- No auto-cleanup of auto-provisioned resources on parent deletion
- No tenant READY condition gating on default networking readiness

### Goals

- Single-call resource creation with sensible networking defaults
- Default networking resources (VN, IPv4 Subnet, IPv6 Subnet, SG, NATGateway) provisioned at tenant onboarding (dual-stack)
- Optional network_attachments field on all resource types
- Auto ExternalIP mode for inbound connectivity
- Auto-cleanup of auto-provisioned resources on deletion
- Tenant-scoped default resources (visible, editable, lifecycle-managed by tenant)

### Non-Goals

- Custom default configurations per tenant (all tenants receive the same defaults)
- Auto-provisioning of additional VirtualNetworks or Subnets beyond the initial default
- UI support for simplified creation (deferred — API and CLI only)
- Automatic migration of existing resources to use defaults

## Proposal

This enhancement adds three main capabilities: default networking (including NATGateway) at tenant onboarding, optional network_attachments with auto-population, and auto ExternalIP provisioning.

### Workflow Description

#### Default Networking at Tenant Onboarding

1. **Cloud Infrastructure Admin configures NetworkClass defaults:**
   ```bash
   # NetworkClass already exists, update with defaults
   kubectl patch networkclass moc-region-1 --type merge -p '{
     "spec": {
       "defaults": {
         "virtualNetworkCIDR": "10.0.0.0/16",
         "ipv4SubnetCIDR": "10.0.1.0/24",
         "ipv6SubnetCIDR": "fd00:osac:1::/64",
         "securityGroupRules": [
           {"direction": "ingress", "protocol": "tcp", "port": 22, "source": "0.0.0.0/0"},
           {"direction": "ingress", "protocol": "tcp", "port": 443, "source": "0.0.0.0/0"}
         ]
       }
     }
   }'
   ```

2. **Cloud Provider Admin creates Tenant:**
   ```bash
   osac create tenant --name acme-corp
   ```
   - **fulfillment-service** creates Tenant record, then creates default networking resources through its own API (same path as tenant-created resources — persisted in PostgreSQL, reconciled to K8s CRs):
     - Creates default VirtualNetwork with label `osac.openshift.io/default: "true"`, using CIDR from NetworkClass defaults
     - Creates default IPv4 Subnet with label `osac.openshift.io/default: "true"`, using `ipv4SubnetCIDR` from NetworkClass defaults
     - Creates default IPv6 Subnet with label `osac.openshift.io/default: "true"`, using `ipv6SubnetCIDR` from NetworkClass defaults
     - Creates default SecurityGroup with label `osac.openshift.io/default: "true"`, using rules from NetworkClass defaults
     - Creates default NATGateway with an auto-allocated ExternalIP on the default VirtualNetwork, labeled `osac.openshift.io/default: "true"`
   - Reads NetworkClass defaults configuration (single NetworkClass per deployment)
   - Default resources go through the normal reconciliation path: fulfillment-service reconciler pushes CRs → osac-operator networking controllers dispatch to fabric/k8s managers → resources transition to READY
   - fulfillment-service tracks default networking readiness on the Tenant: sets `DefaultNetworkingReady` condition once all default resources (VN, IPv4 Subnet, IPv6 Subnet, SG, NATGateway) reach READY state (via feedback)
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
     - Detects `compute_network_attachments` field is omitted
     - Queries tenant's default Subnet and default SecurityGroup (labeled `osac.openshift.io/default: "true"`)
     - Populates `compute_network_attachments` with default Subnet + default SecurityGroup
     - Stores resolved attachments in spec
   - Creates ComputeInstance CR with resolved network_attachments
   - osac-operator reconciles normally (VM provisioned on default subnet)

5. **Tenant User retrieves resource and sees resolved defaults:**
   ```bash
   osac get computeinstance my-vm -o yaml
   ```
   Output shows:
   ```yaml
   spec:
     compute_network_attachments:
       - subnet: "default-subnet-id"
         security_groups: ["default-sg-id"]
         primary: true
   ```

#### Auto ExternalIP for Single-Call Inbound Connectivity

6. **Tenant User creates VM with auto ExternalIP:**
   ```bash
   osac create computeinstance --template ocp_virt_vm \
     --external-ip-attachment --name my-vm
   ```
   - fulfillment-service:
     - Populates network_attachments with defaults (if omitted)
     - Reads `auto_external_ip_attachment: true`
     - Auto-selects ExternalIPPool (READY, most available capacity, IPv4 family)
     - Creates ExternalIP + ExternalIPAttachment in the same DB transaction — both start in **Pending** state. Pool capacity is decremented atomically.
     - Both labeled `osac.openshift.io/auto-provisioned: "true"`. ExternalIP also labeled `osac.openshift.io/auto-provisioned-for: <resource-id>` for orphan cleanup.
   - ComputeInstance CR created with `auto_external_ip_attachment: true`
   - osac-operator reconciles ExternalIP (fabric manager allocates address → Allocated), then VM provisioning, then ExternalIPAttachment controller activates once ExternalIP is Allocated AND VM's `VirtualMachineReference` is set
   - See [Unified Networking — Auto-provisioning lifecycle](/enhancements/unified-networking/design.md#external-access-same-for-all-resource-types) for the full two-phase flow
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
     - Populates network_attachments with defaults (if omitted)
     - Reads `auto_external_ip_attachment: true`
     - Auto-selects ExternalIPPool (same algorithm)
     - Creates two ExternalIPs + two ExternalIPAttachments in the same DB transaction — all start in **Pending** state. Pool capacity decremented atomically.
     - All labeled `osac.openshift.io/auto-provisioned: "true"`
   - osac-operator ExternalIP controller dispatches to fabric manager → ExternalIPs transition to Allocated (external addresses assigned)
   - Cluster provisioning proceeds — MetalLB allocates internal VIPs from its IPAddressPool. Template discovers VIPs and writes to ClusterOrder status (`apiEndpoint`, `ingressEndpoint`).
   - ExternalIPAttachment controllers activate once ExternalIP is Allocated AND ClusterOrder `apiEndpoint`/`ingressEndpoint` are populated → creates DNAT: external IP → internal VIP
   - See [Unified Networking — Auto-provisioning lifecycle](/enhancements/unified-networking/design.md#external-access-same-for-all-resource-types) for the full two-phase flow
   - Result: Cluster is reachable via ExternalIPs for both API and ingress

9. **CLI flag mapping for clusters:**
   - `--external-ip-attachment` → `auto_external_ip_attachment: true` (auto-provision ExternalIP + ExternalIPAttachment for both API and ingress)

#### Auto-Cleanup on Deletion

13. **Tenant User deletes resource with auto-provisioned ExternalIP:**
    ```bash
    osac delete computeinstance my-vm
    ```
    - osac-operator ComputeInstance controller finalizer:
      - Queries ExternalIPAttachment and ExternalIP labeled `osac.openshift.io/auto-provisioned: "true"` referencing this ComputeInstance
      - Deletes ExternalIPAttachment first (DNAT rule removed)
      - Deletes ExternalIP second (IP returned to pool)
      - If cleanup fails permanently (after retries): finalizer is removed, parent resource deleted, orphaned resources left in cluster
    - **Manually created resources are NOT cleaned up** — if tenant created ExternalIP/ExternalIPAttachment explicitly (not labeled auto-provisioned), they persist after parent deletion
    - **Default networking resources (VN, Subnet, SG, NATGateway) are NOT cleaned up** — they are tenant-scoped and shared across resources

14. **Tenant Admin inspects and customizes default resources:**
    ```bash
    # List default resources
    osac get virtualnetworks --filter 'labels["osac.openshift.io/default"]="true"'
    osac get subnets --filter 'labels["osac.openshift.io/default"]="true"'
    osac get security-groups --filter 'labels["osac.openshift.io/default"]="true"'
    osac get natgateways --filter 'labels["osac.openshift.io/default"]="true"'

    # Modify default SecurityGroup rules
    osac update security-group default-sg \
      --add-ingress "protocol:tcp,port:8080,source:0.0.0.0/0"
    ```
    - Default resources are editable like any other resource
    - Default resources cannot be deleted while any resource depends on them (subnet deletion blocked if VMs reference it)

### API Extensions

#### Proto (fulfillment-service)

**NetworkClass defaults configuration:**

```protobuf
message NetworkClassSpec {
  // ... existing fields ...
  NetworkDefaults defaults = 10; // new field
}

message NetworkDefaults {
  string virtual_network_cidr = 1;  // e.g., "10.0.0.0/16"
  string ipv4_subnet_cidr = 2;      // e.g., "10.0.1.0/24"
  repeated SecurityGroupRule security_group_rules = 3;
  string ipv6_subnet_cidr = 4;      // e.g., "fd00:osac:1::/64"
}

message SecurityGroupRule {
  string direction = 1;   // "ingress" or "egress"
  string protocol = 2;    // "tcp", "udp", "icmp", etc.
  int32 port = 3;         // port number (0 for ICMP)
  string source = 4;      // CIDR (for ingress) or destination (for egress)
}
```

**Resource-level auto external access fields:**

```protobuf
// ComputeInstance and BaremetalInstance
message ComputeInstanceSpec {
  // ... existing fields ...
  bool auto_external_ip_attachment = 19;  // auto-provision ExternalIP + ExternalIPAttachment
}

// Cluster
message ClusterSpec {
  // ... existing fields ...
  bool auto_external_ip_attachment = 10;  // auto-provision ExternalIP + ExternalIPAttachment for API and ingress
}
```

**Default label on auto-created resources:**

All default resources (VirtualNetwork, Subnet, SecurityGroup, NATGateway created at tenant onboarding) receive label:
```yaml
metadata:
  labels:
    osac.openshift.io/default: "true"
```

All auto-provisioned resources (ExternalIP, ExternalIPAttachment created by auto_external_ip_attachment=true) receive label:
```yaml
metadata:
  labels:
    osac.openshift.io/auto-provisioned: "true"
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
- `DefaultNetworkingReady: true` when default VN, IPv4 Subnet, IPv6 Subnet, SG, and NATGateway are all READY
- `DefaultNetworkingReady: false, reason: <FailureReason>` when any default resource failed to provision

**NetworkClass defaults field:**

```go
type NetworkClassSpec struct {
    // ... existing fields ...
    Defaults *NetworkDefaults `json:"defaults,omitempty"`
}

type NetworkDefaults struct {
    VirtualNetworkCIDR    string              `json:"virtualNetworkCIDR,omitempty"`
    IPv4SubnetCIDR        string              `json:"ipv4SubnetCIDR,omitempty"`
    IPv6SubnetCIDR        string              `json:"ipv6SubnetCIDR,omitempty"`
    SecurityGroupRules    []SecurityGroupRule `json:"securityGroupRules,omitempty"`
}

type SecurityGroupRule struct {
    Direction string `json:"direction"` // ingress or egress
    Protocol  string `json:"protocol"`  // tcp, udp, icmp, etc.
    Port      int32  `json:"port"`      // port number
    Source    string `json:"source"`    // CIDR
}
```

**Resource spec fields (ComputeInstance, Cluster, BaremetalInstance):**

```go
type ComputeInstanceSpec struct {
    // ... existing fields ...
    AutoExternalIPAttachment bool `json:"autoExternalIPAttachment,omitempty"`
}

type ClusterSpec struct {
    // ... existing fields ...
    AutoExternalIPAttachment bool `json:"autoExternalIPAttachment,omitempty"`
}
```

#### Server Validation (fulfillment-service)

**NetworkClass defaults validation:**
- `virtual_network_cidr` must be valid CIDR notation
- `ipv4_subnet_cidr` must be valid IPv4 CIDR notation and within virtual_network_cidr range
- `ipv6_subnet_cidr` must be valid IPv6 CIDR notation
- `security_group_rules[].direction` must be "ingress" or "egress"
- `security_group_rules[].protocol` must be valid (tcp, udp, icmp, etc.)

**Resource creation with optional network_attachments:**
- If network_attachments omitted: query tenant's default Subnet and SecurityGroup (labeled `osac.openshift.io/default: "true"`)
- If no defaults exist (should not occur — defaults are mandatory on NetworkClass): return error `No default networking resources available. Please contact your administrator.`
- If network_attachments provided explicitly: no defaults applied

**Auto ExternalIP allocation (when auto_external_ip_attachment: true):**
- Pool selection: pick READY ExternalIPPool with most available capacity matching IP family (defaults to IPv4)
- If multiple pools have equal capacity: selection is deterministic but implementation-defined (e.g., alphabetical by pool name)
- If no pool has capacity: return error `ExternalIPPool exhaustion: no available capacity in any READY pool for IPv4`
- Pool capacity is checked and decremented synchronously during the API call. If the pool is exhausted, the call fails and no resources are persisted (including the parent resource). "Synchronous" here means the API call validates and creates DB records atomically — actual IP address allocation from the fabric manager and DNAT rule creation happen asynchronously through the operator reconciliation loop. See [Unified Networking — Auto-provisioning lifecycle](/enhancements/unified-networking/design.md#external-access-same-for-all-resource-types) for the full two-phase flow.

### Implementation Details/Notes/Constraints

#### Component Responsibility

| Component | Responsibility |
|-----------|---------------|
| fulfillment-service | Validate NetworkClass defaults, **create default VN/IPv4 Subnet/IPv6 Subnet/SG/NATGateway at tenant onboarding** (via its own API), populate network_attachments defaults, auto-provision ExternalIP, track DefaultNetworkingReady condition, return error on capacity exhaustion |
| osac-operator resource controllers | Clean up auto-provisioned ExternalIP and ExternalIPAttachment via finalizer |
| osac-operator networking controllers | Reconcile default networking resources (same as manually created resources) |
| osac-installer | Configure NetworkClass defaults in setup.sh and installation overlays |

#### Default Resource Lifecycle

- **Creation:** fulfillment-service creates default VN, IPv4 Subnet, IPv6 Subnet, SG, and NATGateway at tenant onboarding (via its own API — resources are persisted in PostgreSQL and reconciled to K8s CRs like any other resource)
- **Labeling:** All default resources labeled `osac.openshift.io/default: "true"`
- **Visibility:** Default resources appear in list/detail views like any other resource
- **Editability:** Tenant Admin can modify default resources (e.g., add SecurityGroup rules)
- **Deletion protection:** Default resources cannot be deleted while any resource depends on them (e.g., subnet deletion blocked if VMs reference it)
- **Tenant deletion:** Default resources are deleted when tenant is deleted (owner reference cleanup)

#### Auto-Provisioned Resource Lifecycle

- **Creation:** fulfillment-service creates ExternalIP or ExternalIPAttachment when auto_external_ip_attachment=true
- **Labeling:** All auto-provisioned resources labeled `osac.openshift.io/auto-provisioned: "true"`
- **Cleanup:** Parent resource finalizer deletes auto-provisioned ExternalIP/ExternalIPAttachment on parent deletion
- **Cleanup order:** ExternalIPAttachment → ExternalIP → parent resource removal
- **Cleanup failure:** If cleanup fails permanently (after retries), finalizer is removed, parent deleted, orphaned ExternalIP/ExternalIPAttachment left in cluster (manual cleanup required)
- **Manual resources NOT cleaned up:** If tenant created ExternalIP/ExternalIPAttachment explicitly (not labeled auto-provisioned), they persist after parent deletion

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

All default and auto-provisioned resources inherit tenant annotation from parent:
- `osac.openshift.io/tenant` annotation propagated from Tenant to default VN/Subnet/SG/NATGateway
- `osac.openshift.io/tenant` annotation propagated from ComputeInstance/Cluster/BaremetalInstance to auto-provisioned ExternalIP/ExternalIPAttachment
- OPA policies enforce tenant-scoped list/get/update/delete

#### CIDR Overlap Across Tenants

All tenants receive the same default CIDR range as configured on the NetworkClass. Tenants are isolated at the fabric level — the unified networking API provides VirtualNetworks with any IP subnet, and the fabric manager enforces isolation regardless of overlapping CIDRs between tenants. This is a fabric-level concern, not an API-level concern.

### Security Considerations

This feature inherits the existing security model:
- Tenant isolation via `osac.openshift.io/tenant` annotation enforced by OPA policies
- Auto-provisioned resources (ExternalIP, ExternalIPAttachment) inherit tenant annotation from parent resource
- Default resources (VN, Subnet, SG, NATGateway) inherit tenant annotation from Tenant resource
- No new authentication or authorization changes
- Default SecurityGroup rules configured by Cloud Infrastructure Admin (applies to all tenants)
- Tenant Admin can modify default SecurityGroup rules after creation (tenant-configurable)

**Risk: Default SecurityGroup too permissive**
- Mitigation: Cloud Infrastructure Admin configures default rules on NetworkClass with minimal access (e.g., SSH and HTTPS only). Tenant Admin tightens rules after creation if needed.

### Failure Handling and Recovery

#### Tenant Onboarding Failures

- **Default VirtualNetwork provisioning fails:** Tenant enters non-READY state with condition `DefaultNetworkingReady: false, reason: VirtualNetworkProvisioningFailed, message: "..."`
- **Default IPv4 Subnet provisioning fails:** Tenant enters non-READY state with condition `DefaultNetworkingReady: false, reason: SubnetProvisioningFailed, message: "..."`
- **Default IPv6 Subnet provisioning fails:** Tenant enters non-READY state with condition `DefaultNetworkingReady: false, reason: SubnetProvisioningFailed, message: "..."`
- **Default SecurityGroup provisioning fails:** Tenant enters non-READY state with condition `DefaultNetworkingReady: false, reason: SecurityGroupProvisioningFailed, message: "..."`
- **Default NATGateway provisioning fails:** Tenant enters non-READY state with condition `DefaultNetworkingReady: false, reason: NATGatewayProvisioningFailed, message: "..."`
- **Recovery:** Cloud Provider Admin inspects failure (check networking controller logs, AAP job logs), fixes root cause, deletes tenant, re-creates tenant

#### Resource Creation Failures

- **No default networking resources:** Since defaults are mandatory on NetworkClass (rejected at creation time without them), this scenario should not occur. If it does due to data inconsistency, resource creation without explicit network_attachments returns error: `No default networking resources available. Please contact your administrator.`
- **ExternalIPPool capacity exhaustion:** create API call returns error: `ExternalIPPool exhaustion: no available capacity in any READY pool for IPv4`. Resource is NOT persisted.

#### Auto-Provisioned Resource Cleanup Failures

- **Transient failure:** Parent finalizer retries cleanup (exponential backoff)
- **Permanent failure:** After N retries, finalizer is removed, parent resource deleted, orphaned ExternalIP/ExternalIPAttachment left in cluster
- **Manual cleanup required:** Tenant Admin or Cloud Provider Admin manually deletes orphaned resources (identified by label `osac.openshift.io/auto-provisioned: "true"` with no parent reference)

### RBAC / Tenancy

No RBAC or tenancy changes. All new resources (default networking, auto-provisioned ExternalIP) inherit tenant isolation:
- `osac.openshift.io/tenant` annotation propagated from parent to all child resources
- OPA policies enforce tenant-scoped list/get/update/delete
- Tenant User can view and manage default and auto-provisioned resources via standard API
- Cloud Infrastructure Admin configures NetworkClass defaults (global, applies to all tenants)

### Observability and Monitoring

New structured log events:
- fulfillment-service: `CreatingDefaultNetworking` (info), `DefaultNetworkingReady` (info), `DefaultNetworkingFailed` (error), `PopulatedNetworkAttachmentsDefaults` (info), `AutoProvisionedExternalIP` (info), `ExternalIPPoolExhausted` (error)

New Kubernetes events on Tenant:
- `DefaultNetworkingCreated`: default VN, IPv4 Subnet, IPv6 Subnet, SG, and NATGateway creation started
- `DefaultNetworkingReady`: all default resources are READY
- `DefaultNetworkingFailed`: default resource provisioning failed (includes reason and failed resource name)

New Kubernetes events on ComputeInstance/Cluster/BaremetalInstance:
- `NetworkAttachmentsPopulated`: network_attachments field populated with tenant defaults
- `AutoExternalIPCreated`: ExternalIP and ExternalIPAttachment auto-provisioned

No new metrics or alerts (existing provisioning duration and failure rate metrics apply).

### Risks and Mitigations

#### Risk: ExternalIPPool exhaustion

**Impact:** Auto ExternalIP allocation fails, create API call returns error, tenant cannot create resource with auto_external_ip_attachment=true.

**Mitigation:** Pool capacity visible in status; clear error directs tenant to explicit allocation from another pool or contact admin.

**Reviewed by:** Cloud Provider Admin

#### Risk: Default SecurityGroup too permissive

**Impact:** All tenants receive the same default SecurityGroup rules configured by Cloud Infrastructure Admin. If misconfigured, all tenants' resources may be exposed.

**Mitigation:** Cloud Infrastructure Admin configures default rules on NetworkClass with minimal access (e.g., SSH and HTTPS only). Tenant Admin can tighten rules after creation.

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

### Unit Tests

- fulfillment-service: NetworkClass defaults validation (valid CIDR, valid SecurityGroupRule fields)
- fulfillment-service: network_attachments population (populate with defaults when omitted, skip when provided)
- fulfillment-service: auto ExternalIP pool selection (pick READY pool with most capacity, respect IP family)
- fulfillment-service: capacity exhaustion error (return error, resource not persisted)
- fulfillment-service: default resource creation at tenant onboarding (VN, IPv4 Subnet, IPv6 Subnet, SG, NATGateway with default label)
- fulfillment-service: DefaultNetworkingReady condition tracking (true when all defaults including both Subnets and NATGateway READY via feedback, false when any failed)
- osac-operator resource controllers: auto-provisioned resource cleanup (delete ExternalIPAttachment → ExternalIP on parent deletion)

### Integration Tests

- E2E: create Tenant, verify default VN/IPv4 Subnet/IPv6 Subnet/SG/NATGateway created and labeled `osac.openshift.io/default: "true"`
- E2E: create Tenant, default Subnet provisioning fails, verify Tenant remains non-READY with condition
- E2E: create ComputeInstance without network_attachments, verify defaults populated in spec
- E2E: create ComputeInstance with `--external-ip-attachment`, verify auto ExternalIP + ExternalIPAttachment created, DNAT rule functional
- E2E: create Cluster with `--external-ip-attachment`, verify two ExternalIPs created BEFORE provisioning, cluster VIPs match
- E2E: delete ComputeInstance with auto-provisioned resources, verify ExternalIPAttachment and ExternalIP cleaned up
- E2E: create ComputeInstance with explicit network_attachments, verify defaults NOT applied
- E2E: create ComputeInstance with `--external-ip-attachment` when pool exhausted, verify error returned, resource not persisted
- E2E: Tenant Admin modifies default SecurityGroup rules, verify changes take effect

### Tricky Test Cases

- Tenant onboarding failure: default Subnet provisioning fails, verify Tenant non-READY, manual retry works
- ExternalIPPool exhaustion: verify error returned, no resource created
- Auto-provisioned resource cleanup failure: verify finalizer retry, eventual orphan cleanup
- Cluster ExternalIP prerequisite ordering: verify ExternalIPs allocated BEFORE provisioning, template receives correct VIPs

## Graduation Criteria

**Note:** This section will be updated when the enhancement is targeted at a release.

Proposed maturity level: **Tech Preview** → **GA**

Tech Preview criteria:
- [ ] NetworkClass defaults field implemented in fulfillment-service and osac-operator
- [ ] fulfillment-service creates default VN/IPv4 Subnet/IPv6 Subnet/SG/NATGateway at tenant onboarding
- [ ] Tenant DefaultNetworkingReady condition functional
- [ ] network_attachments field optional on all three resource types (ComputeInstance, Cluster, BaremetalInstance)
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
- Existing resources with auto-provisioned ExternalIP: `N` server does not recognize auto_external_ip_attachment field, auto-provisioned resources remain (manual cleanup required if not needed)
- New resource creation with auto_external_ip_attachment=true will fail (field not recognized)

Acceptable downgrade steps:
- Existing resources continue to function (default networking and auto-provisioned resources persist)
- New resources must use explicit networking (auto_external_ip_attachment=true not supported)
- Manually delete orphaned auto-provisioned resources if not needed (identified by label `osac.openshift.io/auto-provisioned: "true"`)

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

**Cause:** Default VirtualNetwork, IPv4 Subnet, IPv6 Subnet, SecurityGroup, or NATGateway provisioning failed

**Resolution:**
1. Check default networking resource status: `kubectl get virtualnetwork -n <namespace> -l osac.openshift.io/default=true`
2. If VirtualNetwork/IPv4 Subnet/IPv6 Subnet/SecurityGroup/NATGateway is not READY, investigate provisioning failure (check networking controller logs, AAP job logs)
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

**Detection:** `kubectl get externalip` shows orphaned ExternalIP labeled `osac.openshift.io/auto-provisioned: "true"` with no parent

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
- Default networking at tenant onboarding remains functional (only auto external access is disabled)

## Infrastructure Needed

- osac-installer: NetworkClass default configuration in setup.sh and installation overlays
- fulfillment-service: NetworkClass defaults validation, default VN/IPv4 Subnet/IPv6 Subnet/SG/NATGateway creation at tenant onboarding, network_attachments population, auto ExternalIP provisioning, DefaultNetworkingReady condition tracking
- Integration test environment: kind cluster with Tenant, NetworkClass, ExternalIPPool resources
