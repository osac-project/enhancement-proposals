---
title: default-networking
authors:
  - dmanor@redhat.com
creation-date: 2026-07-08
last-updated: 2026-10-12
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

## Contents

- [Summary](#summary)
- [Motivation](#motivation)
  - [Goals](#goals)
  - [Non-Goals](#non-goals)
- [Proposal](#proposal)
  - [Workflow Description](#workflow-description)
    - [Default Networking at Tenant Onboarding](#default-networking-at-tenant-onboarding)
    - [Shared Attachment Resolution](#shared-attachment-resolution)
    - [Auto ExternalIP for Single-Call Inbound Connectivity](#auto-externalip-for-single-call-inbound-connectivity)
    - [Auto-Cleanup on Deletion](#auto-cleanup-on-deletion)
    - [Inspecting Default Resources](#inspecting-default-resources)
  - [Provider Networking Disabled](#provider-networking-disabled)
  - [API Extensions](#api-extensions)
  - [Implementation Details](#implementation-details-notes-and-constraints)
  - [Security Considerations](#security-considerations)
  - [Failure Handling and Recovery](#failure-handling-and-recovery)
  - [RBAC and Tenancy](#rbac-and-tenancy)
  - [Observability and Monitoring](#observability-and-monitoring)
  - [Risks and Mitigations](#risks-and-mitigations)
  - [Drawbacks](#drawbacks)
  - [Alternatives Considered](#alternatives-considered)
- [Test Plan](#test-plan)
- [Graduation Criteria](#graduation-criteria)
- [Upgrade and Downgrade Strategy](#upgrade-and-downgrade-strategy)
- [Version Skew Strategy](#version-skew-strategy)
- [Support Procedures](#support-procedures)
- [Infrastructure Needed](#infrastructure-needed)

This design extends the shared resource model in the [Unified Networking
design](/enhancements/OSAC-1433-unified-networking/design.md). With provider
networking enabled, tenant onboarding creates a default VirtualNetwork, IPv4
Subnet, SecurityGroup, and NATGateway. With provider networking disabled, it
creates the logical defaults but omits provider-dependent ExternalIP and
NATGateway resources. This document defines shared defaulting, automatic
external-access admission, and cleanup; each workload extension defines its
request fields and service-specific endpoint flow. IPv6 and dual-stack
networking are not supported.

Each workload integration supports at most one tenant network attachment.
The service extension defines the request field, interface mapping, and how
that attachment participates in workload routing. See
the [VMaaS](/enhancements/OSAC-1435-vmaas-networking/design.md),
[CaaS](/enhancements/OSAC-1436-caas-networking/design.md), and
[BMaaS](/enhancements/OSAC-1437-bmaas-networking/design.md) designs.

## Summary

This design extends the [Unified Networking design](/enhancements/OSAC-1433-unified-networking/design.md) with tenant defaults and the shared admission, allocation, and cleanup behavior for simplified workload creation. It inherits the [Unified Networking deployment support boundary](/enhancements/OSAC-1433-unified-networking/design.md#deployment-support-boundary): default networking supports connected deployments only and does not support air-gapped or disconnected networking. With provider networking enabled, tenant onboarding creates a default VirtualNetwork, IPv4 Subnet, SecurityGroup, and NATGateway from NetworkClass configuration. With provider networking disabled, it creates the logical defaults but omits provider-dependent ExternalIP and NATGateway resources; this provides default attachment resolution without promising provider connectivity or outbound NAT. Workload-specific request fields and endpoint flows are defined by the corresponding service extension designs. See the [PRD](prd.md) for user-facing requirements.

Default networking also inherits the [Unified Networking hub support
boundary](/enhancements/OSAC-1433-unified-networking/design.md#networking-hub-support-boundary):
OSAC networking supports exactly one provider-owned hub per deployment.
Multi-hub networking placement, cross-hub resource coordination, and
cross-hub network connectivity are unsupported. This boundary applies only to
the networking area and does not define hub behavior for other OSAC areas.
Multiple hosting/workload clusters remain supported where a networking feature
explicitly specifies them.

Provider managers used by the shared resources follow the [Network Manager
Integration Contract](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md).

## Motivation

A provider-connected resource in OSAC requires networking resources: VirtualNetwork, Subnet, SecurityGroup, the resource itself, ExternalIP, and ExternalIPAttachment. With provider networking enabled, default networking reduces this setup to a single create command. With networking disabled, workloads still use logical tenant defaults, but provider connectivity and ExternalIP routing are not promised.

### Goals

- Single-call resource creation with sensible networking defaults
- Default networking resources (VN, IPv4 Subnet, SG, and, when provider networking is enabled, NATGateway) provisioned at tenant onboarding
- Optional resource-specific network attachment field on all resource types, with at most one tenant attachment per workload
- Auto ExternalIP mode for inbound connectivity
- Auto-cleanup of auto-created resources on deletion
- Tenant-scoped default resources (visible and managed through the unified
  create/read/delete lifecycle)

### Non-Goals

- Custom default configurations per tenant (all tenants receive the same defaults)
- Auto-provisioning of additional VirtualNetworks or Subnets beyond the initial default
- UI support for simplified creation (deferred — API and CLI only)
- Automatic migration of existing resources to use defaults

## Proposal

The design covers default tenant resources, optional resource-specific network attachment fields with auto-population, and auto ExternalIP provisioning. The provider-dependent NATGateway and ExternalIP are provisioned at onboarding only when provider networking is enabled.

### Workflow Description

#### Default Networking at Tenant Onboarding

1. **Cloud Infrastructure Admin creates the NetworkClass with defaults:**
   The NetworkClass is created with the deployment-wide IPv4 CIDRs and
   SecurityGroup rules before tenant onboarding. NetworkClass changes follow
   the unified create/read/delete contract and require replacement.

   **NetworkClass replacement lifecycle:** Follow the shared
   [profile lifetime and dependency guards](/enhancements/OSAC-1433-unified-networking/design.md#deletion-dependency-guards).
   Pause onboarding and all affected tenants' default-based creates. Drain
   workloads and replace their immutable attachments by recreating them; no
   existing workload is rebound. Drain the old class's VirtualNetworks and
   dependent resources, bound ExternalIPPools, ExternalIPs, endpoint
   reservations, and pending or unknown-outcome provider operations. A pool's
   immutable profile/manager binding is not transferred to the replacement.
   The old NetworkClass remains protected until all references and operations
   are resolved. Validate the replacement class and provision compatible ready
   external-pool capacity under its binding before creating replacement default
   NATGateways. Resume default-based creates only after all replacement defaults
   meet enabled readiness. Merely deleting the old VirtualNetworks is insufficient.

   Enabled onboarding also requires at least one Ready IPv4 ExternalIPPool
   bound to the active class, with available capacity for the default NATGateway's
   ExternalIP. Register and provision that capacity before tenant onboarding.

2. **Cloud Provider Admin creates Tenant with provider networking enabled:**
   ```bash
   osac create tenant --name acme-corp
   ```
   - **fulfillment-service** creates Tenant record, then creates default networking resources through its own API (same path as tenant-created resources — persisted in PostgreSQL, reconciled to K8s CRs):
     - Creates default VirtualNetwork with label `osac.openshift.io/default: "true"`, using CIDR from NetworkClass defaults
     - Creates default IPv4 Subnet with label `osac.openshift.io/default: "true"`, using `ipv4SubnetCIDR` from NetworkClass defaults
     - Creates default SecurityGroup with label `osac.openshift.io/default: "true"`, using rules from NetworkClass defaults
     - Creates default NATGateway with an auto-allocated ExternalIP on the default VirtualNetwork, labeled `osac.openshift.io/default: "true"`
   - Reads NetworkClass defaults configuration (single NetworkClass per deployment)
   - Default resources go through the normal reconciliation path: fulfillment-service reconciler pushes CRs → osac-operator networking controllers dispatch to fabric/k8s managers → resources transition to READY
   - fulfillment-service tracks default networking readiness on the Tenant: with provider networking enabled, `DefaultNetworkingReady` becomes true when default VN, IPv4 Subnet, SG, and NATGateway reach READY; with networking disabled, it becomes true with reason `ProvisioningDisabled` when the logical VN, Subnet, and SG are ready
   - Tenant overall status becomes READY when `DefaultNetworkingReady` is true; in disabled mode this allows workload defaulting and does not indicate outbound NAT

3. **If default networking provisioning fails:**
   - Tenant remains in non-READY state
   - Tenant status condition shows: `DefaultNetworkingReady: false, reason: SubnetProvisioningFailed, message: "Subnet 'default' failed to provision"`
   - Cloud Provider Admin inspects failure, fixes root cause, and retries by deleting and re-creating the tenant

#### Shared Attachment Resolution

Fulfillment-service applies the shared [workload attachment presence and
defaulting rules](/enhancements/OSAC-1433-unified-networking/design.md#workload-attachment-presence-and-defaulting)
when a workload request omits its network selection or leaves fields
unspecified. It stores the resolved Subnet and SecurityGroups with the
workload. Each service extension defines its request field, target mapping,
and any interface-selection default; see the [VMaaS](/enhancements/OSAC-1435-vmaas-networking/design.md),
[CaaS](/enhancements/OSAC-1436-caas-networking/design.md), and
[BMaaS](/enhancements/OSAC-1437-bmaas-networking/design.md) designs for those
service-specific flows.

#### Auto ExternalIP for Single-Call Inbound Connectivity

When provider networking is enabled and a workload requests automatic external
access, fulfillment-service checks and reserves enough ready ExternalIP
capacity for the endpoints defined by that workload's service extension. If
capacity is unavailable, the parent create request fails without creating a
partial workload or address request. With provider networking disabled, the
service extension's disabled-mode behavior applies; no address or route is
claimed as available, and an automatic request does not block ordinary
workload provisioning. Address assignment then proceeds asynchronously through the shared
[ExternalIP allocation contract](/enhancements/OSAC-1433-unified-networking/design.md#externalip-address-selection-and-ownership).
OSAC creates an inbound ExternalIPAttachment only after that address is real
and the corresponding service-defined endpoint is Ready. The extension owns
endpoint count, endpoint discovery, readiness, and routing-domain selection;
the auto-access request does not create a placeholder endpoint or substitute
an address.

| Workload service | Service-specific endpoint flow |
|---|---|
| VMaaS | [VMaaS networking design](/enhancements/OSAC-1435-vmaas-networking/design.md) |
| BMaaS | [BMaaS networking design](/enhancements/OSAC-1437-bmaas-networking/design.md) |
| CaaS | [CaaS networking design](/enhancements/OSAC-1436-caas-networking/design.md) |

#### Auto-Cleanup on Deletion

When a workload with automatically-created external access is deleted, OSAC
removes and confirms ExternalIPAttachment cleanup before releasing the
ExternalIP and completing workload deletion. If cleanup fails, deletion stays
pending with an actionable diagnostic and retains child ownership for retry.
Manually created attachments remain tenant-owned and must be removed before
the target workload can be deleted. Shared tenant defaults remain available
for other workloads.

If manually created ExternalIPAttachments target a workload, deletion of the
target workload is blocked until the tenant removes them. The
shared [deletion dependency contract](/enhancements/OSAC-1433-unified-networking/design.md#deletion-dependency-guards)
defines this rule and the common cleanup order. Each service extension defines
how its workload deletion waits for those shared children.

#### Inspecting default resources

```bash
# List default resources
osac get virtualnetworks --filter 'labels["osac.openshift.io/default"]="true"'
osac get subnets --filter 'labels["osac.openshift.io/default"]="true"'
osac get security-groups --filter 'labels["osac.openshift.io/default"]="true"'
osac get natgateways --filter 'labels["osac.openshift.io/default"]="true"'
```

- Default resources follow the unified create/read/delete contract; they
  cannot be edited in place.
- Default resources cannot be deleted while any resource depends on them
  (for example, a Subnet cannot be deleted while workloads use it).
- Replacing the default resource set (VirtualNetwork, Subnet,
  SecurityGroup, and NATGateway) is a coordinated transition: pause
  default-based creates for every affected existing tenant, drain or delete
  workloads attached to the old defaults, and run reverse-reference checks
  before deleting any old resource. The old VirtualNetwork must have no
  Subnet, SecurityGroup, NATGateway, or workload-attachment references.
  The old NATGateway must have no remaining dependents; deleting it releases
  its auto-allocated ExternalIP through the normal cleanup path. With
  networking enabled, provider release must be confirmed before OSAC returns
  capacity. With networking disabled, the logical object and capacity slot
  are removed without provider release, and prior provider state may require
  manual cleanup. A replacement NATGateway receives a newly
  allocated ExternalIP; the old address is not rebound. Create each
  replacement with the same tenant scope and
  `osac.openshift.io/default: "true"` label. Attachments are immutable, so
  existing workloads are not rebound and the replacement applies to later
  creates only.
- Defaults cannot be unlabeled in place because networking metadata is
  immutable. Default selection considers only active, READY resources and
  must find exactly one matching default; zero or multiple matches is a
  configuration error. Default-based creates remain paused until the
  replacement VirtualNetwork, Subnet, SecurityGroup, and NATGateway are
  READY.

### Provider Networking Disabled

When provider networking is disabled, tenant onboarding still creates the
logical default VirtualNetwork, IPv4 Subnet, and SecurityGroup through their
normal API paths. Those resources use the shared disabled-mode readiness
contract after their logical prerequisites pass. Onboarding does not create the
default ExternalIP or NATGateway: address allocation is skipped and NATGateway
creation retains its existing `ExternalIP state=Allocated` API prerequisite.
The API validation rule is unchanged; onboarding omits the dependent resources
instead of bypassing the gate.

When the default VirtualNetwork, Subnet, and SecurityGroup are logically ready,
`DefaultNetworkingReady` is true with reason `ProvisioningDisabled`, and the
Tenant can reach Ready. This means default attachment resolution is available;
it does not assert provider connectivity or outbound NAT. Integrating workload
services continue to resolve and validate default attachments while following
their documented disabled-mode behavior.

Re-enabling provider networking follows the shared [activation
preflight](/enhancements/OSAC-1433-unified-networking/design.md#provider-networking-control).
Default-based workload creates remain blocked until the shared activation
preflight completes and that tenant's provider-backed defaults are ready. The
preflight's workload drain, provider-operation checks, and activation state are
defined in Unified Networking; this design does not repeat them.

During `ReconcilingEnable` and after global activation, the tenant-default
reconciler clears skipped readiness, reconciles real VN/Subnet/SecurityGroup
state, and creates missing
ExternalIP/NATGateway defaults through normal allocation and API readiness
gates. `DefaultNetworkingReady` remains false until the enabled criteria hold;
that tenant's default-based creates remain blocked throughout this reconciliation. [User]

### API Extensions

#### Proto (fulfillment-service)

**NetworkClass defaults configuration:**

Use the shared `NetworkClassSpec` and `NetworkDefaults` messages from
[Unified Networking — Data Model and Schema Changes](/enhancements/OSAC-1433-unified-networking/design.md#42-data-model-and-schema-changes)
and the existing private proto source. `NetworkClassSpec.defaults` retains
field 1 and `vip_prefix_length` retains field 3. Defaults use the shared
immutable SecurityGroup rule schema with separate ingress/egress arrays,
protocol enum, optional TCP/UDP port range, and `ipv4_cidr`.
The VIP slice applies to Fabric-owned tenant ingress reservations and is
excluded from DHCP/overlay allocation at Subnet creation; it is not a shared
management-cluster tenant MetalLB pool. [User]

**Workload-specific external access fields:**

Each workload service owns the request field, API compatibility, and endpoint
status representation for automatic external access. See the [VMaaS](/enhancements/OSAC-1435-vmaas-networking/design.md),
[CaaS](/enhancements/OSAC-1436-caas-networking/design.md), and
[BMaaS](/enhancements/OSAC-1437-bmaas-networking/design.md) designs. The
shared ExternalIP and ExternalIPAttachment resources and their lifecycle are
defined by Unified Networking.

**Default label on auto-created resources:**

All default resources (VirtualNetwork, Subnet, SecurityGroup, NATGateway created at tenant onboarding) receive label:
```yaml
metadata:
  labels:
    osac.openshift.io/default: "true"
```

ExternalIP and ExternalIPAttachment resources created for automatic external
access receive the label:
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
- `DefaultNetworkingReady: true` when default VN, IPv4 Subnet, SG, and NATGateway are all READY with provider networking enabled
- `DefaultNetworkingReady: true, reason: ProvisioningDisabled` when the default VN, IPv4 Subnet, and SG are logically ready while provider networking is disabled; the default ExternalIP and NATGateway are intentionally absent
- `DefaultNetworkingReady: false, reason: <FailureReason>` when any default resource required in the current mode fails to provision

**NetworkClass defaults field:**

Use the existing operator NetworkClassSpec/default rule structures described
by Unified Networking; retain `defaults` and `vipPrefixLength` rather than
introducing `metallbVIPPrefixLength` or a second direction/single-port rule
schema. Default SecurityGroups are ordinary immutable OSAC rule resources;
provider policy is applied per resolved workload SubnetAttachment. [User]

Workload-specific attachment and automatic external-access fields remain in
the existing service APIs. Their field names, tags, target selectors, and
status mapping belong to the corresponding [VMaaS](/enhancements/OSAC-1435-vmaas-networking/design.md),
[CaaS](/enhancements/OSAC-1436-caas-networking/design.md), and
[BMaaS](/enhancements/OSAC-1437-bmaas-networking/design.md) extension designs;
this proposal does not duplicate those schemas.

#### Server Validation (fulfillment-service)

**NetworkClass defaults validation:**
- `virtual_network_cidr` must be valid CIDR notation
- `ipv4_subnet_cidr` must be valid IPv4 CIDR notation and within virtual_network_cidr range
- `virtual_network_cidr` and `ipv4_subnet_cidr` must use canonical IPv4 CIDR notation with host bits zero
- Default ingress/egress rules satisfy the shared IPv4 SecurityGroup schema: TCP/UDP require valid ordered port ranges; ICMP/ALL omit port fields; unsupported families/protocols are rejected

**Resource creation with optional network attachment fields:**
Fulfillment-service uses the shared
[attachment presence and defaulting contract](/enhancements/OSAC-1433-unified-networking/design.md#workload-attachment-presence-and-defaulting).
Each service extension defines its request field and interface selection; a
missing or non-Ready network dependency causes the create request to fail.

**Automatic external-access admission and allocation:**
- Pool selection: fulfillment-service picks a READY IPv4 ExternalIPPool with the most available capacity for each endpoint defined by the workload extension. This selects the pool only; the assigned manager selects the concrete address.
- If multiple pools have equal capacity: selection is deterministic but implementation-defined (e.g., alphabetical by pool name)
- If no pool has capacity, the create request fails and no parent or partial address resources are persisted.
- Capacity is reserved during the create request so that accepted requests do not overcommit a pool. Address assignment, validation, status publication, and inbound rule creation complete asynchronously. See [Unified Networking — ExternalIP Address Selection and Ownership](/enhancements/OSAC-1433-unified-networking/design.md#externalip-address-selection-and-ownership) and [Auto-provisioned External Access](/enhancements/OSAC-1433-unified-networking/design.md#auto-provisioned-external-access).

### Implementation Details, Notes, and Constraints

#### Component Responsibility

| Component | Responsibility |
|-----------|---------------|
| fulfillment-service | Validate NetworkClass defaults; create VN/IPv4 Subnet/SG/NATGateway defaults at onboarding when networking is enabled; while disabled create logical VN/Subnet/SG and omit provider-dependent ExternalIP/NATGateway; resolve attachment defaults and track DefaultNetworkingReady |
| osac-operator resource controllers | Clean up auto-created ExternalIP and ExternalIPAttachment via finalizer |
| osac-operator networking controllers | Reconcile default networking resources (same as manually created resources) |
| osac-installer | Configure NetworkClass defaults in setup.sh and installation overlays |

#### Default Resource Lifecycle

- **Creation:** With provider networking enabled, fulfillment-service creates
  default networking resources at tenant onboarding in dependency order, waiting for each to reach its ready
  state before creating the next. The sequence is:
  1. Create VirtualNetwork → wait for Ready
  2. Create Subnet and SecurityGroup → wait for Ready
  3. Create ExternalIP → wait for Allocated
  4. Create NATGateway → wait for Ready
  The fulfillment-service internal reconciler drives this progression,
  triggered by status updates via Signal RPC. The `DefaultNetworkingReady`
  tenant condition tracks the overall progress. This follows the same
  creation readiness rules as tenant-initiated operations — see
  [Unified Networking — Creation Readiness Gates](/enhancements/OSAC-1433-unified-networking/design.md#creation-readiness-gates).
  With provider networking disabled, the sequence stops after the logical
  VirtualNetwork, Subnet, and SecurityGroup are ready; no default ExternalIP or
  NATGateway is created. The shared `Provider Networking Disabled` contract
  defines the tenant readiness condition for this mode.
- **Labeling:** All default resources labeled `osac.openshift.io/default: "true"`
- **Visibility:** Default resources appear in list/detail views like any other resource
- **Mutability:** Default resources are immutable after creation; changes require
  delete and recreate under the unified networking contract
- **Deletion protection:** Default resources cannot be deleted while any workload or networking resource depends on them.
- **Tenant deletion:** Default resources are deleted when tenant is deleted (owner reference cleanup)

#### Auto-Provisioned Resource Lifecycle

- **Creation:** after accepting a workload extension's automatic external-
  access request, fulfillment-service creates the required ExternalIP
  requests (the selected ExternalIPPool is already Ready, so the readiness
  gate is satisfied). ExternalIPAttachment is created later by the
  fulfillment-service internal reconciler, only after the
  ExternalIP is Allocated and the target workload is Ready. This follows the
  same creation readiness rules as tenant-initiated operations — see
  [Unified Networking — Auto-provisioned External Access](/enhancements/OSAC-1433-unified-networking/design.md#auto-provisioned-external-access).
- **Labeling:** All auto-created resources labeled `osac.openshift.io/auto-created: "true"`
- **Cleanup:** Parent resource finalizer deletes auto-created ExternalIP/ExternalIPAttachment on parent deletion
- **Cleanup order:** ExternalIPAttachment → ExternalIP → parent resource removal
- **Cleanup failure:** the parent finalizer remains while auto-created ExternalIPAttachments or ExternalIPs remain. Reconciliation retries with backoff and reports the failed child operation; an administrator repairs the cause before cleanup resumes. Enabled-mode failure never silently orphans children. [User]
- **Manual resources block deletion:** If tenant created ExternalIP/ExternalIPAttachment explicitly (not labeled auto-created), they block the parent workload's deletion — the tenant must remove them first. See [Unified Networking — Deletion Dependency Guards](/enhancements/OSAC-1433-unified-networking/design.md#deletion-dependency-guards)

#### Service-specific endpoint flows

This design defines shared admission, capacity, allocation, attachment, and
cleanup rules. It does not define service-specific endpoint count, address
discovery, bootstrap dependencies, or routing domains. The [VMaaS](/enhancements/OSAC-1435-vmaas-networking/design.md),
[BMaaS](/enhancements/OSAC-1437-bmaas-networking/design.md), and
[CaaS](/enhancements/OSAC-1436-caas-networking/design.md) designs own those
flows, including cluster bootstrap and endpoint publication.

#### Tenant Isolation

All default and auto-created resources inherit tenant annotation from parent:
- `osac.openshift.io/tenant` annotation propagated from Tenant to default VN/Subnet/SG/NATGateway
- `osac.openshift.io/tenant` annotation propagated from the owning workload to auto-created ExternalIP/ExternalIPAttachment
- OPA policies enforce tenant-scoped create/list/get/delete; update/patch is
  not exposed for networking resources, and private controller status
  transitions remain internal

#### CIDR Overlap Across Tenants

All tenants receive the same default CIDR range as configured on the NetworkClass. Tenants are isolated at the fabric level — the unified networking API provides VirtualNetworks with any IP subnet, and the fabric manager enforces isolation regardless of overlapping CIDRs between tenants. This is a fabric-level concern, not an API-level concern.

### Security Considerations

This feature inherits the existing security model:
- Tenant isolation via `osac.openshift.io/tenant` annotation enforced by OPA policies
- Auto-provisioned resources (ExternalIP, ExternalIPAttachment) inherit tenant annotation from parent resource
- Default resources (VN, Subnet, SG, NATGateway) inherit tenant annotation from Tenant resource
- No new authentication or authorization changes
- Default SecurityGroup rules configured by Cloud Infrastructure Admin (applies to all tenants)
- Tenant Admin can create replacement SecurityGroup resources with customized
  rules after dependencies on the defaults have been removed

**Risk: Default SecurityGroup too permissive**
- Mitigation: Cloud Infrastructure Admin configures default rules on NetworkClass with minimal access (e.g., SSH and HTTPS only). Tenants that need different rules create replacement SecurityGroup resources and use them for subsequently created workloads.

### Failure Handling and Recovery

#### Tenant Onboarding Failures

- **Default VirtualNetwork provisioning fails:** Tenant enters non-READY state with condition `DefaultNetworkingReady: false, reason: VirtualNetworkProvisioningFailed, message: "..."`
- **Default IPv4 Subnet provisioning fails:** Tenant enters non-READY state with condition `DefaultNetworkingReady: false, reason: SubnetProvisioningFailed, message: "..."`
- **Default SecurityGroup provisioning fails:** Tenant enters non-READY state with condition `DefaultNetworkingReady: false, reason: SecurityGroupProvisioningFailed, message: "..."`
- **No ready compatible ExternalIPPool or exhausted capacity:** Tenant remains non-READY with `DefaultNetworkingReady=False`, reason `ExternalIPPoolUnavailable` or `ExternalIPPoolExhausted`. No default NATGateway is created until address capacity and allocation are ready.
- **Default ExternalIP allocation fails:** Tenant remains non-READY with `DefaultNetworkingReady=False`, reason `ExternalIPAllocationFailed`; retain the Pending address request/capacity and report the provider diagnostic. Retry the same request after repair; do not allocate a second default address.
- **Default NATGateway provisioning fails while provider networking is enabled:** Tenant enters non-READY state with condition `DefaultNetworkingReady: false, reason: NATGatewayProvisioningFailed, message: "..."`. Disabled-mode onboarding omits this provider-dependent resource and does not report this failure.
- **Recovery:** Cloud Provider Admin inspects failure (check networking controller logs, AAP job logs), fixes root cause, deletes tenant, re-creates tenant

#### Resource Creation Failures

- **No default networking resources:** Since defaults are mandatory on NetworkClass (rejected at creation time without them), this scenario should not occur. If it does due to data inconsistency, resource creation without an explicit network attachment returns error: `No default networking resources available. Please contact your administrator.`
- **ExternalIPPool capacity exhaustion:** create API call returns error: `ExternalIPPool exhaustion: no available capacity in any READY pool for IPv4`. Resource is NOT persisted.

#### Auto-Provisioned Resource Cleanup Failures

- **Transient failure:** Parent finalizer retries cleanup (exponential backoff)
- **Persistent failure:** retain the parent finalizer and child references, report the failed operation, and retry with backoff after provider repair
- **Repair required:** Tenant Admin or Cloud Provider Admin inspects the retained parent/child diagnostic and repairs the provider operation. Finalizers and reservations remain until cleanup succeeds; children do not lose their parent reference. [User]

### RBAC and Tenancy

No RBAC or tenancy changes. All new resources (default networking, auto-created ExternalIP) inherit tenant isolation:
- `osac.openshift.io/tenant` annotation propagated from parent to all child resources
- OPA policies enforce tenant-scoped create/list/get/delete; update/patch is
  not exposed for networking resources, and private controller status
  transitions remain internal
- Tenant User can view default and auto-created resources and use the supported
  create/list/get/delete operations subject to dependency protection
- Cloud Infrastructure Admin configures NetworkClass defaults (global, applies to all tenants)

### Observability and Monitoring

New structured log events:
- fulfillment-service: `CreatingDefaultNetworking` (info), `DefaultNetworkingReady` (info), `DefaultNetworkingFailed` (error), `PopulatedNetworkAttachmentsDefaults` (info), `AutoProvisionedExternalIP` (info), `ExternalIPPoolExhausted` (error)

New Kubernetes events on Tenant:
- `DefaultNetworkingCreated`: default VN, IPv4 Subnet, SG, and NATGateway creation started
- `DefaultNetworkingReady`: all defaults required by the active provider-networking mode are ready; the disabled-mode reason distinguishes logical defaults from provider-backed NAT readiness
- `DefaultNetworkingFailed`: default resource provisioning failed (includes reason and failed resource name)

New Kubernetes events on integrated workload resources:
- `NetworkAttachmentsPopulated`: resource-specific network attachment field populated with tenant defaults
- `AutoExternalIPCreated`: ExternalIP and ExternalIPAttachment auto-created

No new metrics or alerts (existing provisioning duration and failure rate metrics apply).

### Risks and Mitigations

#### Risk: ExternalIPPool exhaustion

**Impact:** Automatic external-address allocation fails, so the workload request is rejected without a partial workload or address request.

**Mitigation:** Pool capacity visible in status; clear error directs tenant to explicit allocation from another pool or contact admin.

**Reviewed by:** Cloud Provider Admin

#### Risk: Default SecurityGroup too permissive

**Impact:** All tenants receive the same default SecurityGroup rules configured by Cloud Infrastructure Admin. If misconfigured, all tenants' resources may be exposed.

**Mitigation:** Cloud Infrastructure Admin configures default rules on NetworkClass with minimal access (e.g., SSH and HTTPS only). Tenant Admin can create replacement immutable groups and select them for subsequently created workloads.

**Reviewed by:** Cloud Infrastructure Admin

#### Risk: Automatic external cleanup delays deletion

**Impact:** A persistent provider failure leaves parent deletion pending, holding child references and external pool capacity until cleanup is confirmed.

**Mitigation:** Retain parent/child finalizers, durable operation identities and address ownership; expose the failed task, retry with backoff, and resume after provider repair. Release capacity only after confirmed address release. Enabled-mode failures do not remove finalizers after a retry limit. [User]

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

## Alternatives Considered

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

### Shared Contract Scenarios

- **[DEV] Contract:** shared NetworkClass defaults and rule schema; pool
  capacity admission; immutable default resources; and attachment resolution
  that preserves supplied values and defaults only missing values.
- **[DEV] Envtest:** default resource readiness in enabled and disabled modes;
  workload admission waits for required defaults; and cleanup retains child
  ownership and address capacity until provider release is confirmed.
- **[QE] Service integration:** each workload service verifies its endpoint
  count, bootstrap, endpoint discovery, and cleanup in its own extension design:
  [VMaaS](/enhancements/OSAC-1435-vmaas-networking/design.md),
  [CaaS](/enhancements/OSAC-1436-caas-networking/design.md), and
  [BMaaS](/enhancements/OSAC-1437-bmaas-networking/design.md).


### Unit Tests

- fulfillment-service: NetworkClass defaults validation (valid CIDR, valid SecurityGroupRule fields)
- fulfillment-service: resource-specific attachment resolution (resolve omitted or empty fields, fill partial attachments, preserve complete explicit attachments)
- fulfillment-service: auto ExternalIP pool selection (pick READY pool with most capacity, respect IP family)
- fulfillment-service: capacity exhaustion error (return error, resource not persisted)
- fulfillment-service: enabled-mode default resource creation at tenant onboarding (VN, IPv4 Subnet, SG, NATGateway with default label)
- fulfillment-service: DefaultNetworkingReady condition tracking (enabled: true when VN, Subnet, SG, and NATGateway are READY; disabled: true/ProvisioningDisabled when VN, Subnet, and SG are logically ready; false when a required resource fails)
- fulfillment-service: disabled-mode tenant onboarding creates default VN/Subnet/SG, omits ExternalIP/NATGateway without weakening API gates, and sets `DefaultNetworkingReady=True`/`ProvisioningDisabled`; re-enabling is blocked until shared workload/job drain prerequisites pass, then clears skipped readiness and creates missing provider-dependent defaults through real allocation/readiness gates
- osac-operator resource controllers: auto-created resource cleanup (delete ExternalIPAttachment → ExternalIP on parent deletion)

### Integration Tests

- Verify onboarding creates the logical default resources and, when provider
  networking is enabled, the provider-backed defaults; each resource is
  visible through normal read operations.
- Verify disabled-mode onboarding omits provider-dependent defaults while
  keeping the logical defaults available for workloads.
- Verify failed default provisioning keeps tenant onboarding unready and
  exposes an actionable diagnostic.
- Verify omitted and partial attachment selections resolve according to the
  shared defaulting matrix, preserve supplied values, and reject incompatible
  Subnet/SecurityGroup combinations.
- Verify automatic external access rejects insufficient capacity before
  accepting a parent workload request, then creates inbound attachments only
  after a real address and a Ready target endpoint are available.
- Verify automatic cleanup preserves ownership and capacity through provider
  failure, then completes after repair.
- Verify defaults expose create/read/delete only and can be replaced after all
  dependents are removed. Service-specific endpoint and workload lifecycle
  tests remain in the relevant extension designs.

### Tricky Test Cases

- Tenant onboarding failure: default Subnet provisioning fails, verify Tenant non-READY, manual retry works
- ExternalIPPool exhaustion: verify error returned, no resource created
- Auto-provisioned resource cleanup failure: verify retained finalizer/ownership on persistent failure, successful cleanup after repair
- Service-specific bootstrap and endpoint independence are covered in the
  relevant extension designs, including the separation between required
  workload bootstrap access and optional tenant ExternalIP access.
- NetworkClass replacement: retain an old-bound pool with a default NAT address and a pending/unknown allocation operation. Old class deletion remains blocked until all resources/operations drain; replacement defaults use replacement-bound ready capacity, never a silently rebound pool.
- Re-enable with live baseline workloads: activation/new creates fail while Read/Delete remain available. After drain and backend repair, genuine network readiness replaces skipped readiness before default-based workload admission.

## Graduation Criteria

**Note:** This section will be updated when the enhancement is targeted at a release.

Proposed maturity level: **Tech Preview** → **GA**

Tech Preview criteria:
- [ ] NetworkClass defaults field implemented in fulfillment-service and osac-operator
- [ ] With provider networking enabled, fulfillment-service creates default VN/IPv4 Subnet/SG/NATGateway at tenant onboarding
- [ ] Tenant DefaultNetworkingReady condition functional
- [ ] Integrating workload services can omit tenant network selection and use the shared defaulting contract
- [ ] Automatic external access follows the shared capacity, allocation, endpoint-readiness, and cleanup contract; service endpoint behavior is verified in each extension design
- [ ] Auto-provisioned resource cleanup via parent finalizer functional
- [ ] Shared defaulting and external-access contract integration tests pass; service-specific lifecycle coverage is in the corresponding extension designs
- [ ] Documentation: API reference, user guide for simplified resource creation

GA criteria:
- [ ] Production deployment verified (MOC or other OSAC deployment)
- [ ] User feedback incorporated (usability, error messages, edge cases)
- [ ] osac-installer includes NetworkClass default configuration in setup.sh and overlays
- [ ] No major bugs reported in Tech Preview period
- [ ] Performance validated (tenant onboarding duration, resource creation latency)

## Upgrade and Downgrade Strategy

### Upgrade

Micro version upgrades (`x.y.N → x.y.N+2`):
- The shared `NetworkClass.defaults` field is additive. Workload request-field
  compatibility for automatic external access follows each service extension;
  existing resources continue to work.
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
- Existing automatically created external-access children remain owned by their
  workload; follow the applicable service extension's rollback and cleanup
  procedure before removing them.
- Workload requests that depend on an automatic external-access field added in
  `N+1` must follow that extension's version-compatibility guidance.

Acceptable downgrade steps:
- Existing resources continue to function (default networking and auto-created resources persist)
- New workloads must use the networking options supported by the rolled-back
  service version; automatic external access is unavailable if that version
  does not support its service-specific request field.
- After rollback, inspect any retained auto-created resources and complete cleanup through their finalizers; if provider networking is disabled, arrange provider/manual cleanup of skipped backend resources before reusing addresses.

## Version Skew Strategy

### Control Plane Skew

fulfillment-service and osac-operator are deployed together in the same namespace and upgraded atomically (both controlled by osac-installer). No skew expected.

### Client Skew

osac-cli (n-1) with fulfillment-service (n):
- Older CLI versions may not support the service's automatic external-access request.
- Tenants must use a supported CLI version to make that request.
- Existing explicit networking workflows remain functional

osac-cli (n) with fulfillment-service (n-1):
- A newer CLI's automatic external-access request may be rejected by an older server that does not recognize the service-specific field.
- Workaround: use explicit ExternalIP allocation until server is upgraded

Recommendation: keep osac-cli and fulfillment-service within one minor version.

## Support Procedures

### Symptom: Tenant stuck in non-READY state, condition "DefaultNetworkingReady: false" while provider networking is enabled

**Detection:**
```bash
kubectl describe tenant acme-corp -n <namespace>
# Check status.conditions for DefaultNetworkingReady
```

**Cause:** A required default VirtualNetwork, IPv4 Subnet, SecurityGroup, or (with provider networking enabled) NATGateway failed to provision

**Resolution:**
1. Check default networking resource status: `kubectl get virtualnetwork -n <namespace> -l osac.openshift.io/default=true`
2. If VirtualNetwork/IPv4 Subnet/SecurityGroup/NATGateway is not READY, investigate provisioning failure (check networking controller logs, AAP job logs)
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

### Symptom: Deletion waits for automatic external cleanup

**Detection:** The parent remains Deleting with its finalizer and child references; an auto-created ExternalIPAttachment or ExternalIP reports a failed cleanup operation.

**Cause:** The provider has not confirmed DNAT removal or address release.

**Resolution:**
1. Inspect parent, child and AAP operation diagnostics to identify the failed task.
2. Repair provider connectivity/configuration or the backend operation; let reconciliation retry with the same durable operation identity.
3. Confirm attachment deletion before address release and parent deletion. Preserve finalizers and address ownership until successful cleanup; do not force-remove finalizers. [User]

### Disabling automatic ExternalIP requests by exhausting pools

This is separate from disabling provider networking with
`global.networking.provisioningEnabled`; provider networking remains enabled
for the behavior in this subsection. To prevent automatic ExternalIP requests:

- Remove or redact ExternalIPPool CRs (capacity exhaustion prevents auto allocation)
- No API extension to disable NetworkClass defaults (fields are part of CRD, cannot be removed at runtime)

Consequences:
- Auto ExternalIP allocation fails with error (resource not created)
- Manual ExternalIP workflows remain functional
- Default networking at tenant onboarding is partially functional — VN, Subnets, and SG are created, but NATGateway creation also fails (requires ExternalIP from pool). Auto external access is disabled

### Provider networking disabled during installation or upgrade

Set `global.networking.provisioningEnabled=false` in Helm or the Enclave
Wizard and complete the coordinated rollout. Tenant onboarding creates the
logical default VN, Subnet, and SG, omits default ExternalIP/NATGateway, and
reports `DefaultNetworkingReady=True` with reason `ProvisioningDisabled` once
those defaults are ready. Tenant workload defaulting remains available;
outbound NAT is not provided. Re-enabling requires the shared workload/job
drain preflight and backend cleanup; after activation, real default networking
and the missing ExternalIP/NATGateway must pass normal readiness gates.
Existing provider routes are not withdrawn by disabling the setting; see the
shared [Unified Networking disabled-mode contract](/enhancements/OSAC-1433-unified-networking/design.md#provider-networking-control).

## Infrastructure Needed

- osac-installer: NetworkClass default configuration in setup.sh and installation overlays
- fulfillment-service: NetworkClass defaults validation, enabled-mode VN/IPv4 Subnet/SG/NATGateway creation and disabled-mode VN/Subnet/SG creation at tenant onboarding, resource-specific attachment resolution, auto ExternalIP provisioning, DefaultNetworkingReady condition tracking
- Integration test environment: kind cluster with Tenant, NetworkClass, ExternalIPPool resources

---

## Provenance

Authored: revise @ design 0.11.5 - 6d28c88, workspace docs/OSAC-1433-network-manager-provider-guide @ eabff3b59 (76 behind origin/main, dirty)
Final: revise @ design 0.11.5 - 1c6e8de, workspace docs/OSAC-1433-network-manager-provider-guide @ 639af2dba

> Context changed between revise and revise.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"1c6e8de","source_repo":"639af2dba","source_repo_branch":"docs/OSAC-1433-network-manager-provider-guide","commits_behind_main":0,"commits_ahead_main":5,"main_ref":"main","phases":["revise","revise","revise","revise","revise","manual-edit","revise","revise","revise"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":true} -->
