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

This enhancement provides default networking resources at tenant onboarding, optional network_attachments with defaults, auto ExternalIP/NATGateway provisioning, and auto-cleanup on deletion.

## Summary

This enhancement is an expansion of the [Unified Networking EP](/enhancements/unified-networking/design.md), providing default networking automation and simplified resource creation. When a tenant is created, the system automatically provisions a default VirtualNetwork, Subnet, and SecurityGroup based on NetworkClass configuration. Resources (ComputeInstance, Cluster, BaremetalInstance) can omit network_attachments and use tenant defaults. Auto ExternalIP and NATGateway modes enable fully connected resources in a single API call. See [PRD](prd.md) for detailed requirements.

## Motivation

Creating a reachable resource in OSAC requires 6+ sequential API calls: VirtualNetwork, Subnet, SecurityGroup, the resource itself, ExternalIP, and ExternalIPAttachment. Every tenant must understand the full networking resource model before provisioning their first VM, cluster, or bare-metal server. This friction slows onboarding, increases the chance of misconfiguration, and makes OSAC harder to adopt compared to platforms where a single create command produces a reachable instance.

### What Already Works

- Tenant controller exists and reconciles Tenant resources
- VirtualNetwork, Subnet, SecurityGroup CRDs and controllers are implemented
- ExternalIP and ExternalIPAttachment provisioning works end-to-end
- NATGateway resource is implemented (OSAC-1676)
- NetworkClass resource exists with region-scoped configuration
- Resource creation with explicit network_attachments works for all three resource types

### What's Missing

- No default networking resources at tenant onboarding
- No default CIDR or SecurityGroup rules configuration on NetworkClass
- network_attachments field is required — no defaults applied when omitted
- No auto ExternalIP allocation mode
- No auto NATGateway provisioning mode
- No auto-cleanup of auto-provisioned resources on parent deletion
- No tenant READY condition gating on default networking readiness

### Goals

- Single-call resource creation with sensible networking defaults
- Default networking resources (VN, Subnet, SG) provisioned at tenant onboarding
- Optional network_attachments field on all resource types
- Auto ExternalIP and NATGateway modes for fully connected resources
- Auto-cleanup of auto-provisioned resources on deletion
- Tenant-scoped default resources (visible, editable, lifecycle-managed by tenant)

### Non-Goals

- Custom default configurations per tenant (all tenants receive the same defaults)
- Auto-provisioning of additional VirtualNetworks or Subnets beyond the initial default
- UI support for simplified creation (deferred — API and CLI only)
- Automatic migration of existing resources to use defaults

## Proposal

This enhancement adds three main capabilities: default networking at tenant onboarding, optional network_attachments with auto-population, and auto ExternalIP/NATGateway provisioning.

### Workflow Description

#### Default Networking at Tenant Onboarding

1. **Cloud Infrastructure Admin configures NetworkClass defaults:**
   ```bash
   # NetworkClass already exists, update with defaults
   kubectl patch networkclass moc-region-1 --type merge -p '{
     "spec": {
       "defaults": {
         "virtualNetworkCIDR": "10.0.0.0/16",
         "subnetCIDR": "10.0.1.0/24",
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
   - fulfillment-service creates Tenant CR
   - osac-operator Tenant controller:
     - Creates namespace (existing logic)
     - Reads NetworkClass defaults for the tenant's region
     - Creates default VirtualNetwork with label `osac.openshift.io/default: "true"`
     - Creates default Subnet with label `osac.openshift.io/default: "true"`
     - Creates default SecurityGroup with label `osac.openshift.io/default: "true"`
     - Watches for all three to reach READY state
     - Sets Tenant condition `DefaultNetworkingReady: true` only when all defaults are READY
     - Tenant overall status becomes READY only when DefaultNetworkingReady condition is true

3. **If default networking provisioning fails:**
   - Tenant remains in non-READY state
   - Tenant status condition shows: `DefaultNetworkingReady: false, reason: SubnetProvisioningFailed, message: "Subnet 'default' failed to provision: AAP job 12345 failed"`
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
     --external-ip=auto --name my-vm
   ```
   - fulfillment-service:
     - Populates network_attachments with defaults (if omitted)
     - Reads `external_ip_mode: AUTO`
     - Auto-selects ExternalIPPool (READY, most available capacity, IPv4 family)
     - Creates ExternalIP + ExternalIPAttachment in the same DB transaction — both start in **Pending** state. Pool capacity is decremented atomically.
     - Both labeled `osac.openshift.io/auto-provisioned: "true"`. ExternalIP also labeled `osac.openshift.io/auto-provisioned-for: <resource-id>` for orphan cleanup.
   - ComputeInstance CR created with `external_ip_mode: AUTO`
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
     --external-ip=auto-all --name my-cluster
   ```
   - fulfillment-service:
     - Populates network_attachments with defaults (if omitted)
     - Reads `external_ip_mode: AUTO_ALL`
     - Auto-selects ExternalIPPool (same algorithm)
     - Creates two ExternalIPs + two ExternalIPAttachments in the same DB transaction — all start in **Pending** state. Pool capacity decremented atomically.
     - All labeled `osac.openshift.io/auto-provisioned: "true"`
   - osac-operator ExternalIP controller dispatches to fabric manager → ExternalIPs transition to Allocated (external addresses assigned)
   - osac-operator ClusterOrder controller `reconcileNetworking` allocates internal VIPs from subnet CIDR via operator IPAM, writes to ClusterOrder status (`apiVIP`, `ingressVIP`). Template pins MetalLB to these VIPs.
   - ExternalIPAttachment controllers activate once ExternalIP is Allocated AND ClusterOrder `apiVIP`/`ingressVIP` are populated → creates DNAT: external IP → internal VIP
   - See [Unified Networking — Auto-provisioning lifecycle](/enhancements/unified-networking/design.md#external-access-same-for-all-resource-types) for the full two-phase flow
   - Result: Cluster is reachable via ExternalIPs for both API and ingress

9. **CLI flag mapping for clusters:**
   - `--external-ip=auto-all` → `external_ip_mode: AUTO_ALL` (both API and ingress)
   - `--external-ip=auto-api` → `external_ip_mode: AUTO_API` (API only)
   - `--external-ip=auto-ingress` → `external_ip_mode: AUTO_INGRESS` (ingress only)

#### Auto NATGateway for Outbound Connectivity

10. **Tenant User creates VM with auto NATGateway:**
    ```bash
    osac create computeinstance --template ocp_virt_vm \
      --nat-gateway=auto --name my-vm
    ```
    - fulfillment-service:
      - Populates network_attachments with defaults (if omitted)
      - Reads `nat_gateway_mode: AUTO`
      - Checks if NATGateway already exists on the VM's VirtualNetwork
      - If exists: reuse (regardless of state, whether manually or auto-created). No new resources created.
      - If not exists: creates a **separate** ExternalIP for the NATGateway's SNAT source (ExternalIP exclusivity means one consumer each — the inbound ExternalIP from `external_ip_mode=AUTO` cannot also be used as SNAT source). The NATGateway and its ExternalIP are created in a **separate DB transaction** after the parent resource is persisted, labeled `osac.openshift.io/auto-provisioned: "true"`. Pool capacity is decremented for this additional ExternalIP; if the pool is exhausted, the NATGateway is not created but the parent resource creation still succeeds (outbound NAT is best-effort, not a hard prerequisite).
    - osac-operator NATGateway controller reconciles SNAT rule provisioning
    - Result: VM has outbound connectivity via NATGateway

11. **Reusing existing NATGateway:**
    - If a NATGateway already exists on the VN (created manually or auto-provisioned by another resource), the system reuses it
    - No duplicate NATGateway is created
    - This avoids SNAT rule conflicts at the fabric level

#### Combined Auto External Access

12. **Tenant User creates VM with both inbound and outbound:**
    ```bash
    osac create computeinstance --template ocp_virt_vm \
      --external-ip=auto --nat-gateway=auto --name my-vm
    ```
    - fulfillment-service provisions: default network_attachments, auto ExternalIP + ExternalIPAttachment, auto NATGateway (or reuse existing)
    - Result: fully connected VM (inbound via ExternalIP, outbound via NATGateway) in a single API call

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
    - **Auto-provisioned NATGateway is NOT cleaned up** — NATGateway is a shared per-VN resource that may serve other resources on the same VirtualNetwork. Even if this resource auto-created it, deleting the resource does not delete the NATGateway. The tenant can delete the NATGateway manually if no longer needed.
    - **Manually created resources are NOT cleaned up** — if tenant created ExternalIP/ExternalIPAttachment explicitly (not labeled auto-provisioned), they persist after parent deletion
    - **Default networking resources (VN, Subnet, SG) are NOT cleaned up** — they are tenant-scoped and shared across resources

14. **Tenant Admin inspects and customizes default resources:**
    ```bash
    # List default resources
    osac get virtualnetworks --filter 'labels["osac.openshift.io/default"]="true"'
    osac get subnets --filter 'labels["osac.openshift.io/default"]="true"'
    osac get security-groups --filter 'labels["osac.openshift.io/default"]="true"'

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
  string subnet_cidr = 2;            // e.g., "10.0.1.0/24"
  repeated SecurityGroupRule security_group_rules = 3;
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
  ExternalIPMode external_ip_mode = 16;   // NONE (default) or AUTO
  NATGatewayMode nat_gateway_mode = 17;   // NONE (default) or AUTO
}

enum ExternalIPMode {
  EXTERNAL_IP_MODE_UNSPECIFIED = 0;
  EXTERNAL_IP_MODE_NONE = 1;   // default
  EXTERNAL_IP_MODE_AUTO = 2;
}

// Cluster
message ClusterSpec {
  // ... existing fields ...
  ClusterExternalIPMode external_ip_mode = 20;  // NONE, AUTO_API, AUTO_INGRESS, AUTO_ALL
  NATGatewayMode nat_gateway_mode = 21;         // NONE (default) or AUTO
}

enum ClusterExternalIPMode {
  CLUSTER_EXTERNAL_IP_MODE_UNSPECIFIED = 0;
  CLUSTER_EXTERNAL_IP_MODE_NONE = 1;        // default
  CLUSTER_EXTERNAL_IP_MODE_AUTO_API = 2;    // API server only
  CLUSTER_EXTERNAL_IP_MODE_AUTO_INGRESS = 3; // ingress only
  CLUSTER_EXTERNAL_IP_MODE_AUTO_ALL = 4;     // both API and ingress
}

enum NATGatewayMode {
  NAT_GATEWAY_MODE_UNSPECIFIED = 0;
  NAT_GATEWAY_MODE_NONE = 1;   // default
  NAT_GATEWAY_MODE_AUTO = 2;
}
```

**Default label on auto-created resources:**

All default resources (VirtualNetwork, Subnet, SecurityGroup created at tenant onboarding) receive label:
```yaml
metadata:
  labels:
    osac.openshift.io/default: "true"
```

All auto-provisioned resources (ExternalIP, ExternalIPAttachment, NATGateway created by external_ip_mode=AUTO or nat_gateway_mode=AUTO) receive label:
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
- `DefaultNetworkingReady: true` when default VN, Subnet, and SG are all READY
- `DefaultNetworkingReady: false, reason: <FailureReason>` when any default resource failed to provision

**NetworkClass defaults field:**

```go
type NetworkClassSpec struct {
    // ... existing fields ...
    Defaults *NetworkDefaults `json:"defaults,omitempty"`
}

type NetworkDefaults struct {
    VirtualNetworkCIDR    string              `json:"virtualNetworkCIDR,omitempty"`
    SubnetCIDR            string              `json:"subnetCIDR,omitempty"`
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
    ExternalIPMode   string `json:"externalIPMode,omitempty"`   // NONE or AUTO
    NATGatewayMode   string `json:"natGatewayMode,omitempty"`   // NONE or AUTO
}

type ClusterSpec struct {
    // ... existing fields ...
    ExternalIPMode   string `json:"externalIPMode,omitempty"`   // NONE, AUTO_API, AUTO_INGRESS, AUTO_ALL
    NATGatewayMode   string `json:"natGatewayMode,omitempty"`   // NONE or AUTO
}
```

#### Server Validation (fulfillment-service)

**NetworkClass defaults validation:**
- `virtual_network_cidr` must be valid CIDR notation
- `subnet_cidr` must be valid CIDR notation and within virtual_network_cidr range
- `security_group_rules[].direction` must be "ingress" or "egress"
- `security_group_rules[].protocol` must be valid (tcp, udp, icmp, etc.)

**Resource creation with optional network_attachments:**
- If network_attachments omitted: query tenant's default Subnet and SecurityGroup (labeled `osac.openshift.io/default: "true"`)
- If no defaults exist (NetworkClass has no defaults configured): return error `No default networking resources available. Please create VirtualNetwork, Subnet, and SecurityGroup explicitly or contact your administrator.`
- If network_attachments provided explicitly: no defaults applied

**Auto ExternalIP allocation:**
- Pool selection: pick READY ExternalIPPool with most available capacity matching IP family (defaults to IPv4)
- If multiple pools have equal capacity: selection is deterministic but implementation-defined (e.g., alphabetical by pool name)
- If no pool has capacity: return error `ExternalIPPool exhaustion: no available capacity in any READY pool for IPv4`
- Pool capacity is checked and decremented synchronously during the API call. If the pool is exhausted, the call fails and no resources are persisted (including the parent resource). "Synchronous" here means the API call validates and creates DB records atomically — actual IP address allocation from the fabric manager and DNAT rule creation happen asynchronously through the operator reconciliation loop. See [Unified Networking — Auto-provisioning lifecycle](/enhancements/unified-networking/design.md#external-access-same-for-all-resource-types) for the full two-phase flow.

**Auto NATGateway creation:**
- Check if NATGateway already exists on the VN (query by VirtualNetwork reference)
- If exists: reuse (regardless of state or whether manually or auto-created)
- If not exists: auto-select ExternalIPPool, create ExternalIP, create NATGateway

### Implementation Details/Notes/Constraints

#### Component Responsibility

| Component | Responsibility |
|-----------|---------------|
| fulfillment-service | Validate NetworkClass defaults, populate network_attachments defaults, auto-provision ExternalIP/NATGateway, return error on capacity exhaustion |
| osac-operator Tenant controller | Create default VN/Subnet/SG at tenant onboarding, watch for READY state, set DefaultNetworkingReady condition |
| osac-operator resource controllers | Clean up auto-provisioned ExternalIP and ExternalIPAttachment via finalizer (NATGateway is NOT cleaned up — shared per-VN) |
| osac-operator networking controllers | Reconcile default networking resources (same as manually created resources) |
| osac-installer | Configure NetworkClass defaults in setup.sh and installation overlays |

#### Default Resource Lifecycle

- **Creation:** Tenant controller creates default VN, Subnet, SG at tenant onboarding
- **Labeling:** All default resources labeled `osac.openshift.io/default: "true"`
- **Visibility:** Default resources appear in list/detail views like any other resource
- **Editability:** Tenant Admin can modify default resources (e.g., add SecurityGroup rules)
- **Deletion protection:** Default resources cannot be deleted while any resource depends on them (e.g., subnet deletion blocked if VMs reference it)
- **Tenant deletion:** Default resources are deleted when tenant is deleted (owner reference cleanup)

#### Auto-Provisioned Resource Lifecycle

- **Creation:** fulfillment-service creates ExternalIP, ExternalIPAttachment, or NATGateway when external_ip_mode=AUTO or nat_gateway_mode=AUTO
- **Labeling:** All auto-provisioned resources labeled `osac.openshift.io/auto-provisioned: "true"`
- **Cleanup:** Parent resource finalizer deletes auto-provisioned ExternalIP/ExternalIPAttachment on parent deletion
- **Cleanup order:** ExternalIPAttachment → ExternalIP → parent resource removal
- **NATGateway NOT cleaned up:** NATGateway is a shared per-VN resource — it persists after individual resource deletion even if auto-created, because other resources on the same VN may depend on it. Tenant deletes NATGateway manually when no longer needed.
- **Cleanup failure:** If cleanup fails permanently (after retries), finalizer is removed, parent deleted, orphaned resources left in cluster (manual cleanup required)
- **Manual resources NOT cleaned up:** If tenant created ExternalIP/ExternalIPAttachment explicitly (not labeled auto-provisioned), they persist after parent deletion

#### Prerequisite Ordering for Clusters

For clusters, two separate IP allocations happen from different sources:

- **External IPs** (from ExternalIPPool): allocated by ExternalIP controller via fabric manager (for DNAT front-end)
- **Internal VIPs** (from subnet CIDR): allocated by operator IPAM during `reconcileNetworking` (for MetalLB API/ingress endpoints)

The DNAT model maps external IPs to internal VIPs:

1. fulfillment-service creates ExternalIP resources (Pending state in DB) and ExternalIPAttachments (Pending, no target VIP yet)
2. osac-operator ExternalIP controller dispatches to fabric manager → ExternalIPs transition to Allocated (external addresses assigned, e.g., 203.0.113.10)
3. osac-operator ClusterOrder controller `reconcileNetworking` allocates internal VIPs from subnet CIDR via operator IPAM (e.g., 10.0.1.20 for API, 10.0.1.50 for ingress), writes to ClusterOrder status (`apiVIP`, `ingressVIP`)
4. Template creates MetalLB Services with pinned IPs using the pre-allocated VIPs — no dynamic MetalLB allocation needed
5. VIP feedback loop: template confirms VIPs in ClusterOrder status → feedback controller → fulfillment-service syncs to Cluster status
6. ExternalIPAttachment controller activates once ExternalIP is Allocated AND VIP is confirmed → creates DNAT: external IP → internal VIP

Note: the external IPs (from ExternalIPPool) and internal VIPs (from subnet CIDR via operator IPAM) are separate address spaces. The ExternalIPAttachment creates the DNAT mapping between them. Single IPAM (operator) for all subnet allocations eliminates conflicts between fabric manager and MetalLB.

#### NATGateway Reuse Logic

When `nat_gateway_mode=AUTO`:
1. Query NATGateway resources with VirtualNetwork reference matching the resource's VN
2. If one or more NATGateways exist: reuse the first one found (alphabetically by name, deterministic)
3. If no NATGateway exists: auto-select ExternalIPPool, create ExternalIP, create NATGateway

**Reuse regardless of state:** If existing NATGateway is Failed or Deleting, system reuses it (no new NATGateway created). Outbound connectivity will not work until tenant manually deletes failed NATGateway and retries.

#### Tenant Isolation

All default and auto-provisioned resources inherit tenant annotation from parent:
- `osac.openshift.io/tenant` annotation propagated from Tenant to default VN/Subnet/SG
- `osac.openshift.io/tenant` annotation propagated from ComputeInstance/Cluster/BaremetalInstance to auto-provisioned ExternalIP/ExternalIPAttachment/NATGateway
- OPA policies enforce tenant-scoped list/get/update/delete

#### CIDR Overlap Across Tenants

All tenants receive the same default CIDR range as configured on the NetworkClass. Tenants are isolated at the fabric level — the unified networking API provides VirtualNetworks with any IP subnet, and the fabric manager enforces isolation regardless of overlapping CIDRs between tenants. This is a fabric-level concern, not an API-level concern.

### Security Considerations

This feature inherits the existing security model:
- Tenant isolation via `osac.openshift.io/tenant` annotation enforced by OPA policies
- Auto-provisioned resources (ExternalIP, ExternalIPAttachment, NATGateway) inherit tenant annotation from parent resource
- Default resources (VN, Subnet, SG) inherit tenant annotation from Tenant resource
- No new authentication or authorization changes
- Default SecurityGroup rules configured by Cloud Infrastructure Admin (applies to all tenants)
- Tenant Admin can modify default SecurityGroup rules after creation (tenant-configurable)

**Risk: Default SecurityGroup too permissive**
- Mitigation: Cloud Infrastructure Admin configures default rules on NetworkClass with minimal access (e.g., SSH and HTTPS only). Tenant Admin tightens rules after creation if needed.

### Failure Handling and Recovery

#### Tenant Onboarding Failures

- **Default VirtualNetwork provisioning fails:** Tenant enters non-READY state with condition `DefaultNetworkingReady: false, reason: VirtualNetworkProvisioningFailed, message: "..."`
- **Default Subnet provisioning fails:** Tenant enters non-READY state with condition `DefaultNetworkingReady: false, reason: SubnetProvisioningFailed, message: "..."`
- **Default SecurityGroup provisioning fails:** Tenant enters non-READY state with condition `DefaultNetworkingReady: false, reason: SecurityGroupProvisioningFailed, message: "..."`
- **Recovery:** Cloud Provider Admin inspects failure (check networking controller logs, AAP job logs), fixes root cause, deletes tenant, re-creates tenant

#### Resource Creation Failures

- **No default networking resources:** If NetworkClass has no defaults configured, resource creation without explicit network_attachments returns error: `No default networking resources available. Please create VirtualNetwork, Subnet, and SecurityGroup explicitly or contact your administrator.`
- **ExternalIPPool capacity exhaustion:** create API call returns error: `ExternalIPPool exhaustion: no available capacity in any READY pool for IPv4`. Resource is NOT persisted.
- **Auto NATGateway provisioning fails:** NATGateway enters Failed state, outbound SNAT rule not created, VM has no outbound connectivity (VM functional, inbound access works if external_ip_mode=AUTO)

#### Auto-Provisioned Resource Cleanup Failures

- **Transient failure:** Parent finalizer retries cleanup (exponential backoff)
- **Permanent failure:** After N retries, finalizer is removed, parent resource deleted, orphaned ExternalIP/ExternalIPAttachment/NATGateway left in cluster
- **Manual cleanup required:** Tenant Admin or Cloud Provider Admin manually deletes orphaned resources (identified by label `osac.openshift.io/auto-provisioned: "true"` with no parent reference)

### RBAC / Tenancy

No RBAC or tenancy changes. All new resources (default networking, auto-provisioned ExternalIP/NATGateway) inherit tenant isolation:
- `osac.openshift.io/tenant` annotation propagated from parent to all child resources
- OPA policies enforce tenant-scoped list/get/update/delete
- Tenant User can view and manage default and auto-provisioned resources via standard API
- Cloud Infrastructure Admin configures NetworkClass defaults (global, applies to all tenants)

### Observability and Monitoring

New structured log events:
- Tenant controller: `CreatingDefaultNetworking` (info), `DefaultNetworkingReady` (info), `DefaultNetworkingFailed` (error)
- fulfillment-service: `PopulatedNetworkAttachmentsDefaults` (info), `AutoProvisionedExternalIP` (info), `AutoProvisionedNATGateway` (info), `ReusingExistingNATGateway` (info), `ExternalIPPoolExhausted` (error)

New Kubernetes events on Tenant:
- `DefaultNetworkingCreated`: default VN, Subnet, and SG creation started
- `DefaultNetworkingReady`: all default resources are READY
- `DefaultNetworkingFailed`: default resource provisioning failed (includes reason and failed resource name)

New Kubernetes events on ComputeInstance/Cluster/BaremetalInstance:
- `NetworkAttachmentsPopulated`: network_attachments field populated with tenant defaults
- `AutoExternalIPCreated`: ExternalIP and ExternalIPAttachment auto-provisioned
- `AutoNATGatewayCreated`: NATGateway auto-provisioned
- `AutoNATGatewayReused`: existing NATGateway reused

No new metrics or alerts (existing provisioning duration and failure rate metrics apply).

### Risks and Mitigations

#### Risk: ExternalIPPool exhaustion

**Impact:** Auto ExternalIP allocation fails, create API call returns error, tenant cannot create resource with external_ip_mode=AUTO.

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

#### Risk: Deployment misconfiguration (NetworkClass defaults not configured)

**Impact:** If NetworkClass defaults are not configured, tenant onboarding still succeeds (Tenant becomes READY) but resource creation without explicit network_attachments fails with error.

**Mitigation:** This is a deployment issue, not a runtime failure. Clear error message directs tenant to use explicit networking or contact admin. osac-installer setup.sh includes NetworkClass default configuration in installation overlays.

**Reviewed by:** osac-installer team

#### Risk: Auto NATGateway reuses failed or deleting NATGateway

**Impact:** If existing NATGateway on VN is Failed or Deleting, system reuses it (design choice), VM's outbound connectivity will not work.

**Mitigation:** Document expected behavior: tenants must manually delete failed NATGateway and retry resource creation. Alternative: change design to check NATGateway state before reusing (deferred to implementation phase).

**Reviewed by:** API design team

### Drawbacks

#### CIDR overlap across tenants

All tenants receive the same default CIDR range. While fabric-level isolation prevents actual IP conflicts, this may confuse tenants who expect unique CIDR ranges.

**Trade-off:** Simplicity (single default configuration) vs. per-tenant customization. Chosen approach: single default, document fabric-level isolation. Alternative: per-tenant CIDR allocation (more complex, requires IPAM).

#### Auto NATGateway reuse regardless of state

Reusing any existing NATGateway (regardless of state) simplifies conflict avoidance but means tenants can end up with resources referencing failed NATGateways.

**Trade-off:** Simplicity vs. robustness. Chosen approach: reuse any existing NATGateway, document workaround (delete and retry). Alternative: state-aware reuse (more complex, could create duplicate NATGateways during transient failures).

#### Capacity exhaustion returns API error, not Failed resource

When ExternalIPPool has no capacity, the create API call returns an error and the resource is NOT persisted. This provides no audit trail.

**Trade-off:** Simplicity vs. auditability. Chosen approach: return error (resource not persisted). Alternative: create Failed resource for audit trail (adds cleanup burden).

## Alternatives (Not Implemented)

### Alternative 1: Per-tenant default CIDR allocation

Instead of all tenants receiving the same default CIDR, allocate unique CIDR ranges per tenant from a global pool.

**Rejected because:** Adds complexity (requires IPAM, CIDR allocation tracking, exhaustion handling). The unified networking API allows overlapping CIDRs between tenants (fabric-level isolation), so unique CIDRs are not required. Single default CIDR is simpler.

### Alternative 2: Always create auto NATGateway, even if one exists

Instead of reusing existing NATGateway, always create a new one when nat_gateway_mode=AUTO.

**Rejected because:** Multiple NATGateways on the same VN would conflict at the fabric level (SNAT rules for the same CIDR would overlap). Reusing existing NATGateway avoids conflict.

### Alternative 3: Capacity exhaustion creates Failed resource instead of returning error

Instead of returning an error when ExternalIPPool has no capacity, create a Failed resource with a status condition.

**Rejected because:** Pool capacity is validated synchronously during the API call — if the pool is exhausted, the call fails atomically and no resources are persisted. Creating a Failed resource adds cleanup burden and audit trail complexity. Clear API error with no persisted state is simpler.

### Alternative 4: State-aware NATGateway reuse

Instead of reusing any existing NATGateway, only reuse if READY. If existing NATGateway is Failed or Deleting, create a new one.

**Rejected because:** Multiple NATGateways on the same VN would conflict at the fabric level (SNAT rules overlap). State-aware reuse adds complexity and could create duplicate NATGateways during transient failures. Chosen approach: reuse any existing NATGateway, document workaround (delete failed NATGateway and retry).

## Open Questions

### 1. Should auto NATGateway treat a Deleting NATGateway as "does not exist"?

Design decision: reuse existing NATGateway in Ready or Failed state (avoids duplicate SNAT conflicts). Open question: should a NATGateway in **Deleting** state be treated as "does not exist" (create a new one), since the SNAT rule is being removed and the NATGateway will soon be fully deleted? Current behavior would silently attach to a disappearing resource.

**Owner:** API design team

**Impact:** Affects NATGateway reuse logic and user experience when NATGateway is being deleted concurrently.

### 2. Should capacity exhaustion return an API error or create a Failed resource?

Current proposal: return error, resource not persisted. Alternative: create Failed resource for audit trail.

**Owner:** API design team

**Impact:** Affects auto ExternalIP allocation behavior and acceptance criteria.

## Test Plan

### Unit Tests

- fulfillment-service: NetworkClass defaults validation (valid CIDR, valid SecurityGroupRule fields)
- fulfillment-service: network_attachments population (populate with defaults when omitted, skip when provided)
- fulfillment-service: auto ExternalIP pool selection (pick READY pool with most capacity, respect IP family)
- fulfillment-service: auto NATGateway reuse (reuse existing, create new if none exists)
- fulfillment-service: capacity exhaustion error (return error, resource not persisted)
- osac-operator Tenant controller: default resource creation (VN, Subnet, SG with default label)
- osac-operator Tenant controller: DefaultNetworkingReady condition (true when all READY, false when any failed)
- osac-operator resource controllers: auto-provisioned resource cleanup (delete ExternalIPAttachment → ExternalIP on parent deletion)

### Integration Tests

- E2E: create Tenant, verify default VN/Subnet/SG created and labeled `osac.openshift.io/default: "true"`
- E2E: create Tenant, default Subnet provisioning fails, verify Tenant remains non-READY with condition
- E2E: create ComputeInstance without network_attachments, verify defaults populated in spec
- E2E: create ComputeInstance with `--external-ip=auto`, verify auto ExternalIP + ExternalIPAttachment created, DNAT rule functional
- E2E: create Cluster with `--external-ip=auto-all`, verify two ExternalIPs created BEFORE provisioning, cluster VIPs match
- E2E: create ComputeInstance with `--nat-gateway=auto`, verify auto NATGateway created or reused, SNAT rule functional
- E2E: create ComputeInstance with `--external-ip=auto --nat-gateway=auto`, verify full connectivity (inbound + outbound)
- E2E: delete ComputeInstance with auto-provisioned resources, verify ExternalIPAttachment and ExternalIP cleaned up
- E2E: create ComputeInstance with explicit network_attachments, verify defaults NOT applied
- E2E: create ComputeInstance with `--external-ip=auto` when pool exhausted, verify error returned, resource not persisted
- E2E: Tenant Admin modifies default SecurityGroup rules, verify changes take effect

### Tricky Test Cases

- Tenant onboarding failure: default Subnet provisioning fails, verify Tenant non-READY, manual retry works
- Auto NATGateway when existing NATGateway is Failed: verify reuse, document expected behavior
- ExternalIPPool exhaustion: verify error returned, no resource created
- Auto-provisioned resource cleanup failure: verify finalizer retry, eventual orphan cleanup
- Cluster ExternalIP prerequisite ordering: verify ExternalIPs allocated BEFORE provisioning, template receives correct VIPs

## Graduation Criteria

**Note:** This section will be updated when the enhancement is targeted at a release.

Proposed maturity level: **Tech Preview** → **GA**

Tech Preview criteria:
- [ ] NetworkClass defaults field implemented in fulfillment-service and osac-operator
- [ ] Tenant controller creates default VN/Subnet/SG at onboarding
- [ ] Tenant DefaultNetworkingReady condition functional
- [ ] network_attachments field optional on all three resource types (ComputeInstance, Cluster, BaremetalInstance)
- [ ] Auto ExternalIP mode (external_ip_mode: AUTO) functional for VM and BM
- [ ] Auto ExternalIP mode (external_ip_mode: AUTO_ALL/AUTO_API/AUTO_INGRESS) functional for Cluster
- [ ] Auto NATGateway mode (nat_gateway_mode: AUTO) functional
- [ ] Auto-provisioned resource cleanup via parent finalizer functional
- [ ] Integration tests pass (E2E coverage for default networking, optional attachments, auto ExternalIP, auto NATGateway, cleanup)
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
- New fields (NetworkClass.defaults, external_ip_mode, nat_gateway_mode) are additive — existing resources continue to work
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
- Existing resources with auto-provisioned ExternalIP/NATGateway: `N` server does not recognize external_ip_mode/nat_gateway_mode fields, auto-provisioned resources remain (manual cleanup required if not needed)
- New resource creation with external_ip_mode=AUTO will fail (field not recognized)

Acceptable downgrade steps:
- Existing resources continue to function (default networking and auto-provisioned resources persist)
- New resources must use explicit networking (external_ip_mode=AUTO not supported)
- Manually delete orphaned auto-provisioned resources if not needed (identified by label `osac.openshift.io/auto-provisioned: "true"`)

## Version Skew Strategy

### Control Plane Skew

fulfillment-service and osac-operator are deployed together in the same namespace and upgraded atomically (both controlled by osac-installer). No skew expected.

### Client Skew

osac-cli (n-1) with fulfillment-service (n):
- Old CLI does not support `--external-ip=auto` or `--nat-gateway=auto` flags
- Tenant must upgrade CLI to use simplified creation
- Existing explicit networking workflows remain functional

osac-cli (n) with fulfillment-service (n-1):
- New CLI uses `--external-ip=auto` flag → old server rejects unknown field
- Workaround: use explicit ExternalIP allocation until server is upgraded

Recommendation: keep osac-cli and fulfillment-service within one minor version.

## Support Procedures

### Symptom: Tenant stuck in non-READY state, condition "DefaultNetworkingReady: false"

**Detection:**
```bash
kubectl describe tenant acme-corp -n <namespace>
# Check status.conditions for DefaultNetworkingReady
```

**Cause:** Default VirtualNetwork, Subnet, or SecurityGroup provisioning failed

**Resolution:**
1. Check default networking resource status: `kubectl get virtualnetwork -n <namespace> -l osac.openshift.io/default=true`
2. If VirtualNetwork/Subnet/SecurityGroup is not READY, investigate provisioning failure (check networking controller logs, AAP job logs)
3. Fix root cause (e.g., AAP connectivity issue, fabric manager error)
4. Delete tenant: `osac delete tenant acme-corp`
5. Re-create tenant: `osac create tenant --name acme-corp`

### Symptom: Resource creation fails with "No default networking resources available"

**Detection:** API call returns error: `No default networking resources available. Please create VirtualNetwork, Subnet, and SecurityGroup explicitly or contact your administrator.`

**Cause:** NetworkClass has no defaults configured, or tenant has no default networking resources

**Resolution:**
1. Check NetworkClass configuration: `kubectl get networkclass <region> -o yaml`
2. If NetworkClass.spec.defaults is not set, Cloud Infrastructure Admin must configure defaults (see Workflow Description step 1)
3. If NetworkClass has defaults but tenant has no default resources, delete and re-create tenant

### Symptom: Auto-provisioned ExternalIP not cleaned up after resource deletion

**Detection:** `kubectl get externalip` shows orphaned ExternalIP labeled `osac.openshift.io/auto-provisioned: "true"` with no parent

**Cause:** Finalizer cleanup failed permanently

**Resolution:**
1. Check resource deletion logs (controller logs) for cleanup errors
2. Manually delete orphaned ExternalIPAttachment: `kubectl delete externalipattachment <name> -n <namespace>`
3. Manually delete orphaned ExternalIP: `kubectl delete externalip <name> -n <namespace>`

### Symptom: Resource with nat_gateway_mode=AUTO has no outbound connectivity

**Detection:** VM/cluster cannot reach external networks

**Cause:** NATGateway is Failed or Deleting (reused by auto NATGateway logic)

**Resolution:**
1. Check NATGateway status: `kubectl get natgateway -n <namespace>`
2. If NATGateway is Failed: check NATGateway controller logs and AAP job logs for provisioning failure
3. Delete failed NATGateway: `kubectl delete natgateway <name> -n <namespace>`
4. Delete and re-create resource with `--nat-gateway=auto` (new NATGateway will be created)

### Disabling the feature

To disable auto ExternalIP and auto NATGateway:
- Remove or redact ExternalIPPool CRs (capacity exhaustion prevents auto allocation)
- No API extension to disable NetworkClass defaults (fields are part of CRD, cannot be removed at runtime)

Consequences:
- Auto ExternalIP allocation fails with error (resource not created)
- Auto NATGateway creation fails (resource creation may succeed but outbound connectivity unavailable)
- Manual ExternalIP/NATGateway workflows remain functional
- Default networking at tenant onboarding remains functional (only auto external access is disabled)

## Infrastructure Needed

- osac-installer: NetworkClass default configuration in setup.sh and installation overlays
- osac-operator: Tenant controller extended to create default networking resources
- fulfillment-service: NetworkClass defaults validation, network_attachments population, auto ExternalIP/NATGateway provisioning
- Integration test environment: kind cluster with Tenant, NetworkClass, ExternalIPPool resources
