---
title: netris-fabric-manager
authors:
  - Dan Manor
creation-date: 2026-09-28
last-updated: 2026-09-28
tracking-link:
  - "https://redhat.atlassian.net/browse/OSAC-2434"
prd:
  - "prd.md"
see-also:
  - Unified Networking: /enhancements/OSAC-1433-unified-networking
  - CaaS Networking: /enhancements/OSAC-1436-caas-networking
  - Agentless VLAN Fabric Manager: /enhancements/OSAC-3664-agentless-vlan-fabric-manager-networking
  - K8s-Only K8s Manager: /enhancements/OSAC-2069-k8s-only-k8s-manager-networking
---

# Fabric Manager — Netris

## Summary

This document describes the technical design for the Netris fabric manager,
OSAC's production networking backend that translates tenant networking
resources into Netris controller configuration. The Netris backend fulfills
the fabric manager contract defined by the
[Unified Networking design](/enhancements/OSAC-1433-unified-networking/design.md):
it manages VPCs, VNets, IPAM allocations, NAT rules, and ACLs through the
Netris controller REST API.

See [PRD](prd.md) for the problem statement, user stories, and requirements.

## Motivation

OSAC networking relies on a pluggable fabric manager to translate
infrastructure-agnostic networking resources (VirtualNetwork, Subnet,
SecurityGroup, ExternalIP, ExternalIPAttachment, NATGateway) into physical
network configuration. The Netris fabric manager is the first production
backend and serves as the reference backend. Its behavior is scattered
across Ansible roles, operator
controllers, and feature-level docs, making it difficult to reason about
correctness, validate new backends against a baseline, or identify enforcement
gaps.

This design documents the Netris-specific resource mapping, Ansible role
behavior, and failure recovery.

### Goals

- Map each OSAC networking resource to the specific Netris resources the
  backend creates, updates, and deletes.
- Describe how Netris Ansible tasks call the Netris controller API.
- Define failure modes, error surfaces, and recovery behavior.

### Non-Goals

- Changes to the Netris backend implementation — this document describes
  the existing design.
- K8s-only implementation details — see the
  [K8s-only manager design](../OSAC-2069-k8s-only-k8s-manager-networking/design.md).
- SecurityGroup policy semantics (allow/deny evaluation, rule ordering,
  stateful tracking) — that is a cross-backend concern.
- Multiple Netris controllers, split-controller topologies, or Netris
  controller HA. One controller may manage multiple sites mapped to OSAC
  regions.

## Proposal

### Netris Implementation

The Netris backend implements the fabric-manager role through Ansible roles
in the `osac.templates.netris` collection, invoked by AAP.

#### Manager Registration

The OSAC chart renders the Netris registration ConfigMap as
- `metadata.name`: `osac-network-fabric-manager-netris`
- `data.name`: `netris`, matching `NetworkClass.spec.fabricManager`
- `data.capabilities`: `ipv4`

The ConfigMap contains registration metadata; Netris credentials are supplied
separately through a Kubernetes Secret.

#### Netris Role Operations

The role tasks in `osac.templates.netris` call the Netris controller REST API
using its authentication configuration. Resource-specific task and API
mappings are listed below.

The Netris role implements workload-network operations as follows:

- `move_network_attachment` moves the workload port from the configured
  provisioning segment to the tenant segment on attach and restores it on
  detach; retries are safe.
- `query_dhcp_lease` resolves the address from Netris IPAM host entries by
  port MAC. Server-name lookup is used only for service flows that permit it;
  the current bare-metal IP-discovery flow uses this task.

#### Resource Mapping

The following table describes the Netris-specific mapping.

| OSAC Resource | Netris Resources | Ansible Role / Task | Details |
|---------------|-----------------|---------------------|---------|
| VirtualNetwork | VPC (ipVRF) + IPAM allocation | `netris.controller.vpc` → `create`, `netris.controller.ipam` → `create_allocation` | VPC provides isolated routing domain. IPAM allocation with `purpose=common` reserves the VN CIDR. Region is mapped to Netris site ID via `netris_region_site_map`. |
| Subnet | IPAM subnet + VNet (macVRF) | `netris.controller.ipam` → `create_subnet`, `netris.controller.vnet` → `create` | IPAM subnet under parent VPC. VNet with gateway (first usable IP), DHCP enabled, range = second usable to last usable. VXLAN VNI auto-assigned by Netris. Both use the site resolved for the parent VirtualNetwork. |
| SecurityGroup | ACL permit rules | `netris.controller.acl` → `create` | Resolve the parent VPC and subnet CIDRs before creating the Cartesian product of ingress/egress rules × subnet CIDRs. Missing values fail closed; updates remove obsolete ACLs. |
| ExternalIPPool | Provider-owned NAT IPAM allocation + common subnet | `netris.controller.ipam` → `create_allocation`, `create_subnet` | The current API permits one CIDR. The allocation has no Netris `purpose` field; its common subnet uses `purpose=common`. A stable pool owner key identifies the allocation. |
| ExternalIP | IPAM /32 subnet (`purpose=nat`) | `netris.controller.ipam` → `create_subnet` | Reuse a reservation found by stable ExternalIP UID owner key, repair the allocated-address annotation if needed, and allocate only when no reservation exists. The /32 subnet uses `purpose=nat`. |
| ExternalIPAttachment | DNAT rule | `netris.controller.nat` → `create` | `nat_action: dnat`, destination = ExternalIP allocated address, DNAT-to = target internal IP. Workload targets use the resolved tenant VPC. The management VPC is used only for an explicitly requested, supported cluster endpoint. |
| NATGateway | SNAT rule (NAT) | `netris.controller.nat` → `create` | `nat_action: snat`, source = VN CIDR, SNAT-to = ExternalIP allocated address. Rule lives in the resolved tenant VPC. If the VirtualNetwork or tenant VPC cannot be resolved, provisioning fails; the management VPC is never used as a fallback. |

#### Deletion Mapping

Each create operation has a corresponding delete task that reverses it:

| OSAC Resource | Delete Task | Netris Resources Removed |
|---------------|-------------|--------------------------|
| VirtualNetwork | `delete_virtual_network.yaml` | IPAM allocation + VPC |
| Subnet | `delete_subnet.yaml` | VNet + IPAM subnet |
| SecurityGroup | `delete_security_group.yaml` | All ACL rules owned by the SecurityGroup, including obsolete rules |
| ExternalIPPool | `delete_external_ip_pool.yaml` | Common subnets + IPAM allocations |
| ExternalIP | `delete_external_ip.yaml` | /32 IPAM subnet |
| ExternalIPAttachment | `detach_external_ip.yaml` | DNAT rule |
| NATGateway | `delete_nat_gateway.yaml` | SNAT rule |

### API Extensions

No new API extensions. The Netris backend implements the existing
networking API defined by the unified networking design (OSAC-1433). The
backend is selected through provider-level configuration (NetworkClass
`fabricManager` field), not through API changes visible to tenants.

The only annotation the backend writes is `osac.openshift.io/allocated-address`
on ExternalIP CRs to record the allocated address. Backend ownership is
recovered from a stable key
derived from the immutable OSAC object UID and stored in Netris; it does not
require extra CRD fields or infer ownership from a human-readable name.

### Implementation Details/Notes/Constraints

#### Configuration

The Netris backend requires the following configuration, deployed as part
of the OSAC installation:

| Variable | Source | Description |
|----------|--------|-------------|
| `netris_controller_url` | Kubernetes Secret (required target; currently installer AAP ConfigMap) | Netris controller REST API base URL |
| `netris_username` | Kubernetes Secret (required target; currently installer AAP ConfigMap) | Netris controller username |
| `netris_password` | Kubernetes Secret / AAP credential | Netris controller password |
| `netris_site_id` | `global.networking.netris.siteId` → AAP environment ConfigMap | Default Netris site ID used only when a VirtualNetwork omits its region, and for provider-scoped resources without a VirtualNetwork region. |
| `netris_tenant_id` | `global.networking.netris.tenantId` → AAP environment ConfigMap | Netris tenant ID for OSAC resources |
| `netris_region_site_map` | Not currently exposed by the installer or passed to AAP | Required mapping from supported OSAC VirtualNetwork regions to Netris site IDs. An explicitly configured but unmapped region is an error; use `netris_site_id` only when region is omitted. Subnets inherit their parent VirtualNetwork's resolved site. |
| `netris_mgmt_vpc_id` | `global.networking.netris.mgmtVpcId` → AAP environment ConfigMap | Management VPC ID for explicitly supported cluster-endpoint DNAT rules; never a fallback for tenant NATGateway rules. |
| `netris_mgmt_vpc_name` | `global.networking.netris.mgmtVpcName` → AAP environment ConfigMap | Management VPC name for explicitly supported cluster-endpoint DNAT rules. |

#### Idempotency

Every Ansible task checks for existing resources before creating:

- VPC: checks `vpc_already_existed` from `netris.controller.vpc.create`
- IPAM: checks `ipam_already_existed` from `netris.controller.ipam.create_*`
- VNet: checks `vnet_already_existed` from `netris.controller.vnet.create`
- NAT: checks `nat_already_existed` from `netris.controller.nat.create`
- ACL: checks existing ACL by name before creating

Idempotent reconciliation is also required for update requests: when a mutable
spec changes, provisioning must update the existing Netris objects until they
match the new desired state. Merely finding an existing object and returning
success would leave stale configuration; retrying the update must not create
duplicates. This desired-state convergence is essential for update requests,
not just duplicate prevention. Delete tasks treat an already absent Netris
resource as successfully deleted. Resource lookups and deletes use exact
Netris IDs or stable UID-derived owner keys; they do not infer ownership from a
human-readable name pattern alone.

#### ExternalIP Allocation Algorithm

ExternalIP allocation must be serialized per pool, either by using an atomic
Netris allocation operation or by holding a pool-scoped lock across selection
and reservation. The current scan-then-reserve implementation is not atomic
and can assign the same address to concurrent requests; it must not be treated
as concurrency-safe until an atomic allocation operation or pool-scoped
lock is implemented. The current lookup
also matches pool allocations by name and optional numeric suffix and matches
an existing reservation by ExternalIP name; neither lookup proves ownership.

1. Resolve the provider pool's single Netris allocation by a stable owner key
   derived from the ExternalIPPool UID, not by a name or suffix pattern.
2. Before selecting an address, look up a reservation owned by the
   ExternalIP UID. If found, reuse it and restore the address annotation if
   necessary.
3. If no reservation exists, read current reservations while holding the
   pool allocator lock and select a free host address, skipping network and
   broadcast addresses.
4. Reserve the address as a /32 IPAM subnet with `purpose=nat` and bind it to
   the ExternalIP UID. If reservation conflicts, refresh the full pool state
   and retry a bounded number of times.
5. Publish the allocated-address annotation only after reservation and owner
   binding are confirmed. Reconciliation must recover the same reservation
   if annotation writing fails.
6. Release the exact owned reservation on deletion; an already-absent
   reservation is successful.

Pool CIDRs must be /30 or wider — /31 (RFC 3021) produces an empty
candidate range and is not supported.

#### SecurityGroup ACL Rule Expansion

ACL rules are created as the Cartesian product of user-defined rules and
resolved subnet CIDRs. For a SecurityGroup with 3 ingress rules on a
VirtualNetwork with 2 subnets, the backend creates 6 ACL rules (3 × 2). Each
ACL must carry a stable SecurityGroup owner identity so updates and deletion
can find all currently owned rules, including rules for removed subnets or
removed entries. A missing VPC or subnet CIDR is an error; it must never
default to VPC ID 1 or `0.0.0.0/0`.

This expansion is necessary because Netris ACL rules operate on specific
CIDR prefixes, not on VPC-level abstractions.

### Security Considerations

#### Credential Handling

Netris controller credentials (`netris_controller_url`, `netris_username`,
`netris_password`) are stored in Kubernetes Secrets and injected into AAP
as credential types. They are never written to the manager registration
ConfigMap, resource status, events, or tenant-visible output. AAP task output,
job status, resource
conditions, and events may expose only allowlisted diagnostic fields such as
operation, resource kind, sanitized Netris error code, request ID, and AAP job
ID. Redact credentials, authorization data, secret-bearing response fields,
raw response bodies, and tenant or network identifiers before surfacing
diagnostics.

#### Tenant Isolation

Different VirtualNetworks map to separate Netris VPCs (VRFs). Traffic
isolation between VPCs is enforced by the Netris controller at the fabric
level. A workload in one VPC cannot reach another VPC's private addresses,
even when CIDRs overlap. Cross-VN traffic is only possible via ExternalIPs,
which traverse the external path through DNAT/SNAT rules.

#### Input Validation

- CIDR fields are validated at the CRD level (CEL validation for canonical
  IPv4 format, no IPv6).
- The Netris Ansible roles validate required annotations before proceeding
  (e.g., `osac.openshift.io/externalip-name` on NATGateway).
- An explicitly configured VirtualNetwork region must resolve to one Netris
  site before provisioning; only an omitted region may use `netris_site_id`.
  Subnets inherit the resolved site from their parent VirtualNetwork.
- NATGateway and tenant-workload DNAT provisioning must resolve the referenced
  tenant VirtualNetwork and Netris VPC. The management VPC is reserved for an
  explicitly supported cluster-endpoint DNAT request.

### Failure Handling and Recovery

| Failure Mode | Behavior | User Observation | Recovery |
|-------------|----------|-----------------|----------|
| Netris controller unreachable | AAP job fails with a connection error | Resource transitions to `Failed` with a sanitized diagnostic | Retry with bounded exponential backoff; it recovers when the controller is reachable |
| Netris API returns error (e.g., VPC name conflict) | AAP job fails; sanitized error code and request ID are captured | Resource transitions to `Failed`; status condition gives an actionable sanitized diagnostic without credentials or an unfiltered response body | Operator retries with exponential backoff; user may need to resolve the conflict in Netris |
| Parent VPC not found when creating Subnet | Ansible task fails with explicit error message | Subnet transitions to `Failed`: "Parent VPC not found in Netris controller" | Re-reconcile after parent VirtualNetwork is provisioned |
| VirtualNetwork region has no Netris site mapping | Validation fails before creating a VPC or IPAM resource | VirtualNetwork transitions to `Failed` with an unmapped-region diagnostic | Cloud Infrastructure Admin adds the region-to-site mapping and retries |
| Tenant VPC cannot be resolved for NATGateway | Provisioning fails before creating a NAT rule | NATGateway transitions to `Failed`; no rule is created in the management VPC | Reconcile after the referenced VirtualNetwork and tenant VPC are Ready |
| ExternalIP pool exhausted | Ansible task fails: "No available IPs in ExternalIPPool" | ExternalIP transitions to `Failed` with pool exhaustion message | Cloud Infrastructure Admin provisions additional IPAM capacity in Netris |
| Concurrent ExternalIP allocation reserves the same candidate | Reservation conflict triggers a pool refresh and bounded retry under the pool allocator lock | Only one ExternalIP is bound to the address; other requests select a different free address or fail clearly when exhausted | Reconcile after the competing reservation is visible |
| AAP job times out | Job transitions to `Failed` after AAP timeout | Resource shows `Failed` with timeout message | Automatic retry on next reconciliation |
| Partial provisioning (e.g., VPC created but IPAM allocation fails) | AAP job fails; VPC remains in Netris | Resource shows `Failed`; re-reconciliation will find existing VPC and retry IPAM allocation (idempotent) | Automatic convergence on retry |

The provisioning lifecycle uses `DesiredConfigVersion` hashing to avoid
redundant reprovisioning. When a resource's spec changes, the version hash
changes and triggers a new provisioning cycle. A successful job for the same
version may be skipped only while its managed Netris state is known to match
desired state. A failed or incomplete job for the same version is retried after
exponential backoff (2 to 30 minutes), and detected missing Netris resources
must trigger repair even when the version is unchanged.

### RBAC / Tenancy

No RBAC changes are introduced by the Netris backend. Tenant isolation is
inherited from the unified networking model:

- VirtualNetworks are namespaced resources scoped to tenants via
  `osac.openshift.io/tenant` annotations.
- Tenants can only see and manage their own networking resources.
- Provider-level resources (NetworkClass, ExternalIPPool) are cluster-scoped
  and managed by Cloud Infrastructure Admins.
- The Netris backend enforces fabric-level isolation through VPC separation —
  each VirtualNetwork maps to a dedicated VPC.

### Observability and Monitoring

- **AAP job status**: Each provisioning and deprovisioning operation is
  tracked as a job in `status.provisioningJobs[]`, with state, message,
  start time, end time, and sanitized error details only.
- **Kubernetes conditions**: Standard conditions report detailed status
  (e.g., `Ready`, `Progressing`, `Degraded`).
- **Ansible task output**: AAP job output includes operation summaries and
  sanitized diagnostics. Raw Netris response bodies, credentials, and
  authorization data are not copied into tenant-visible status or unfiltered
  logs.
- **Existing monitoring**: The Netris controller has its own monitoring
  and alerting for fabric health. OSAC does not duplicate this.

### Risks and Mitigations

#### Netris controller availability

If the Netris controller is unavailable, all provisioning and
deprovisioning operations fail. Resources transition to `Failed` with a
connection error message. Recovery is automatic through reconciliation
when the controller becomes reachable. Mitigation: the Netris controller
should be deployed with appropriate availability guarantees by the Cloud
Infrastructure Admin.

#### Drift between OSAC state and Netris state

Manual changes in the Netris controller (e.g., deleting a VPC that OSAC
manages) create drift from OSAC's desired state. The target behavior is to
detect and repair missing managed resources; the current hash-based lifecycle
does not reliably trigger that repair after a successful job. Manual changes
that create conflicting state (e.g., a VPC name collision) require operator
intervention. Mitigation: document that OSAC-managed Netris resources should
not be modified manually and implement the recovery trigger above.

#### Netris API breaking changes

The backend depends on the Netris controller REST API. Breaking changes
to the API require updating the Ansible roles. Mitigation: pin the
supported Netris controller version range and validate compatibility
before upgrades.

#### SecurityGroup rule explosion

The Cartesian product expansion (rules × subnets) can produce a large
number of ACL rules. For a SecurityGroup with 10 rules on a VirtualNetwork
with 5 subnets, the backend creates 50 ACL rules per direction (100 total).
Mitigation: document the expansion behavior and recommend keeping
SecurityGroup rules focused. Future work may introduce a VPC-level ACL
abstraction in Netris to avoid per-subnet expansion.

### Drawbacks

- **AAP dependency**: The Netris backend requires AAP for provisioning,
  adding operational complexity. A direct Netris API client in the
  operator would reduce this dependency but would require maintaining
  a Go SDK for the Netris controller API.
- **Eventual consistency**: The provisioning model is asynchronous (operator
  → AAP → Netris). Resource status reflects the last known state from AAP
  job polling, not real-time Netris state. A resource may show `Ready`
  while the underlying Netris configuration has been manually modified.

## Alternatives (Not Implemented)

### Direct Netris API integration in the operator

Instead of dispatching through AAP, the operator could call the Netris
controller REST API directly from Go code. This would eliminate AAP as a
dependency and provide synchronous provisioning. Rejected because:
- The AAP-based model is the established pattern for all OSAC provisioning.
- Ansible roles are easier to test and iterate on than compiled Go code.
- AAP provides job tracking, retry logic, and audit logging.

### Per-VPC ACL rules instead of per-subnet expansion

SecurityGroup rules could be applied at the VPC level instead of expanding
per subnet. Rejected because the Netris ACL API operates on specific CIDR
prefixes and does not support VPC-level wildcard rules.

## Test Plan

### Unit and Envtest

Run from `osac-operator/` with `make test`. Existing package and envtest suites
cover manager registration, dispatch, controller state, and Kubernetes API
behavior. Extend these suites to assert:

- **UT-1 — Netris registration and selection:** the installer renders the
  expected Netris registration name and `data.name`, and a
  NetworkClass naming `netris` selects the Netris role.
- **UT-2 — Desired state updates:** the same successfully applied spec does
  not launch duplicate work; a mutable spec change after success launches a
  new job; changed SecurityGroup rules are part of the new desired version.
  This verifies update dispatch, while role-level tests verify Netris objects
  actually converge.
- **UT-3 — Retry state:** failed or incomplete provisioning can be retried
  with the same spec hash after backoff.
- **UT-4 — Deletion guards:** VirtualNetwork deletion waits for Subnets,
  SecurityGroups, and NATGateways; Subnet deletion waits for ComputeInstances
  and BareMetalInstances; ExternalIPPool deletion waits for ExternalIPs. These
  are operator/controller behaviors, not Netris Ansible role tests.

### Component Integration

The existing `osac-operator/test/integration/networking_test.go` Kind suite
does not exercise Netris provisioning: it removes resource finalizers to
bypass AAP. The current `osac-aap/tests/integration/run_tests.sh` has no Netris
role target. Neither suite currently proves that a Netris controller object
was created or updated.

Add a Netris role integration target under
`osac-aap/tests/integration/` and register it in `run_tests.sh`. Run the actual
Ansible tasks against a stateful mock Netris REST API server; CI does not need
access to a live Netris controller. The mock records requests and models
allocations, subnets, VPCs, VNets, ACLs, and NAT rules. Once that target is
added, `make test` from `osac-aap/` is the execution command. This suite
validates role behavior against the API model, not Netris server-side
persistence or concurrency semantics. Cover:

| Case | Scenario | Required assertions |
|------|----------|--------------------|
| IT-1 | VirtualNetwork region and Subnet site selection | An explicitly unmapped region fails before any create request; an omitted region uses the configured default; a Subnet uses the parent VirtualNetwork's resolved site. |
| IT-2 | NATGateway and ExternalIPAttachment VPC selection | SNAT and workload DNAT use the resolved tenant VPC; failed lookup creates no rule in the management VPC; only an explicit supported cluster-endpoint DNAT uses the management VPC. |
| IT-3 | SecurityGroup create and update | Missing VPC or Subnet CIDR fails with no API create; no default VPC or `0.0.0.0/0` is sent; a rule update changes the owned ACL set and removes obsolete rules; retry creates no duplicates. |
| IT-4 | ExternalIP allocation lifecycle | One pool CIDR maps to its provider-owned allocation; a reservation is looked up by owner identity before allocating; retries reuse the same /32 and repair a missing annotation; two concurrent allocations receive distinct addresses; a simulated reservation conflict refreshes the full pool and retries within a bound; delete of an absent reservation succeeds. |
| IT-5 | Workload network operations | `move_network_attachment` is exercised independently of per-resource dispatch: attach moves the port to the tenant Subnet, detach returns it to the configured provisioning segment, and retries are safe. `query_dhcp_lease` resolves by MAC from Netris IPAM host entries and returns the matching address. |
| IT-6 | Error redaction | A synthetic Netris failure containing credentials, response body, hostnames, tenant data, and network addresses does not expose those values in Ansible output, AAP job details, resource status, conditions, or events. |
| IT-7 | Deprovisioning | Delete removes all Netris objects owned by the resource and is safe to repeat, including when an object is already absent. |

Plan a separate AAP-boundary integration test in
`osac-operator/test/integration/networking_test.go`. Keep the resource
finalizer and configure the Kind test deployment to use a controllable mock
AAP HTTP server that the operator pod can reach, for example, a test Service
deployed inside the cluster. Adding the server fixture and wiring its endpoint
into the test deployment are part of implementing this target. Assert the
selected template, job variables, status transition, retry, and sanitized
failure projection. For workload operations, assert
`move_network_attachment` dispatches only to a fabric manager and
`query_dhcp_lease` dispatches to the selected manager when lease discovery is
requested. Run it with `make integration-tests` from `osac-operator/`. The
existing Kind test that strips finalizers cannot cover this boundary. This
test exercises the controller-to-AAP HTTP boundary using mocked AAP responses;
it does not contact Netris. A separate test environment with a live Netris
controller would be needed to validate server-side allocation atomicity and
persistence, outside the CI integration target.

Until these targets are implemented, these are planned cases rather than
available or passing integration tests. The documented existing commands do
not currently run a Netris-backed integration scenario.

### As-a-Service E2E

End-to-end journeys belong to the owning as-a-service flows under
`tests/e2e/`, not to a duplicate Netris-specific E2E suite. The existing BMaaS
networking flow at
`tests/e2e/bmaas/regression/networking/test_bmaas_networking.py` is the current
Netris-backed example. Service flows should provision the provider-owned NAT
pool as setup, then test the tenant journey: create networking resources,
verify DHCP and connectivity or external NAT behavior, and clean up. Add
equivalent coverage to VMaaS or CaaS flows only where those services expose the
corresponding feature. These E2E checks verify the user-visible service path;
they do not replace the focused role assertions above. The current BMaaS flow
can be run from the OSAC repository root with
`uv run pytest tests/e2e/bmaas/regression/networking/test_bmaas_networking.py`.
