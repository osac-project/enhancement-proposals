---
title: cudn-evpn-k8s-manager-networking
authors:
  - Benny Kopilov
creation-date: 2026-09-03
last-updated: 2026-10-05
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-4291
prd:
  - prd.md
see-also:
  - "/enhancements/OSAC-1433-unified-networking"
  - "/enhancements/OSAC-1717-ovn-kubernetes-evpn-spike"
  - "/enhancements/OSAC-1435-vmaas-networking"
  - "/enhancements/OSAC-1436-caas-networking"
  - "/enhancements/OSAC-1437-bmaas-networking"
  - "/enhancements/OSAC-1433-default-networking"
  - "/enhancements/OSAC-2135-caas-bare-metal-worker-provisioning"
  - "/enhancements/OSAC-1382-multi-fabric-east-west-networking"
replaces:
  - "N/A"
superseded-by:
  - "N/A"
---

# CUDN EVPN K8s Manager: Single-Cluster VM-to-Fabric Bridging

## Summary

This design implements `cudn_evpn` as a K8s Manager for the contract's
fabric-backed `evpn-vxlan` profile. It provisions one OVN-Kubernetes secondary
CUDN and NAD for each OSAC Subnet, so Subnet creation order does not affect VM
placement. The selected Fabric Manager creates the physical segment first and writes the
contract-defined, Subnet-UID-owned handoff ConfigMap with its VNIs, route
targets, and reserved IPv4 ranges. OSAC validates and version-pins that object;
`cudn_evpn` reads the same ConfigMap through its AAP Kubernetes credential.
This is a shared contract interaction, not a supplier-specific callback or
private ConfigMap schema.

The target manager registration uses `implementationRef:
osac.templates.cudn_evpn`, `contractVersion: v1`, and capabilities `ipv4` and
`evpn-vxlan`. Netris plus `cudn_evpn` is the first pair targeted for
certification, not a claim that the current Netris implementation is already
contract-conformant. The registration example below omits a peer declaration
while that certification is incomplete. After the full role conformance suite
and pair integration test pass for the supported versions, the K8s Manager may
declare that Fabric Manager in `compatibleFabricManagers`.
A new Fabric Manager requires its own tested peer declaration. It implements every K8s operation assigned by the fixed
fabric-backed EVPN dispatch profile: `subnet.create` and `subnet.delete`.
SecurityGroup and ExternalIPAttachment operations remain assigned to the
selected Fabric Manager, which enforces their shared contract for VM targets.
The `evpn-vxlan` capability prevents this implementation from being selected for
the K8s-only profile, whose K8s Manager must provide the complete
`primarySubnet` fallback operation set. No registration advertises an
operation subset.

See the [Network Manager Integration Contract](/enhancements/OSAC-5928-pluggable-network-manager-integration-contract-networking/design.md)
for the normative manager interface, fixed profile dispatch, `osac_result`
schema, and conformance rules. This design owns only the CUDN-specific
realization and its OpenShift prerequisites.

## Related Designs

This design builds on and interacts with several networking designs:

- **OSAC-1435 VMaaS Networking** — VMs provisioned via ComputeNetworkAttachment resolve the requested Subnet to the UID-owned namespace and NAD created by this design. Every Subnet has its own CUDN/NAD; VM placement does not depend on Subnet creation order.
- **OSAC-1436 CaaS Networking** — CaaS clusters may run on EVPN-bridged subnets. Port-move primitive compatibility with EVPN transport (VXLAN encap vs VLAN trunking) is TBD (out of scope for Phase 1).
- **OSAC-1437 BMaaS Networking** — Bare-metal servers provisioned via `BareMetalNetworkAttachment` are L2/L3 peers of EVPN-bridged VMs. This design validates same-subnet (L2) and cross-subnet (L3 via fabric ipVRF) connectivity in test cases.
- **OSAC-1433 Default Networking** — Auto-provisioning of VN/Subnet/SG/NAT at tenant onboarding uses a default NetworkClass. `cudn_evpn` is **not suitable** as the default NetworkClass due to manual prerequisites (VTEP, FRR, BGP underlay). Default networking should use a simpler k8s manager (e.g., k8s-only or none).
- **OSAC-2135 CaaS BM Worker Provisioning** — System-tenant bare-metal instances reference tenant Subnets. If those Subnets use `cudn_evpn`, the BMI provisioning flow interacts with the EVPN namespace/CUDN. Interaction is TBD (out of scope for Phase 1).
- **OSAC-1382 Multi-Fabric East-West** — Phase 1 east-west isolation domains will need to work across EVPN-bridged and non-EVPN subnets. Inter-domain routing with EVPN transport is TBD (out of scope for Phase 1).

## Motivation

OSAC runs VMs on OpenShift using KubeVirt. OVN EVPN makes VM addresses
reachable from a physical fabric, but an implementation must create a
corresponding K8s network for every OSAC Subnet and must consume the Fabric
Manager's network identifiers through the shared contract. A first-Subnet-only rule or a provider-specific handoff format violates the
shared resource model and prevents independent manager implementations from
interoperating. Contract v1 instead defines one standard ConfigMap name and
schema per Subnet UID; each Subnet remains independent of creation order.

The CUDN LocalNet approach (OSAC-1511) was frozen in favor of OVN EVPN, which
was validated by OSAC-1717. The deployment remains single-cluster and requires
the documented VTEP, FRR, and BGP underlay prerequisites. [Clarify: R1.Q3,
R1.Q4, R2.Q1]

## Proposal

### Profile and registration

`cudn_evpn` is selected only with a Fabric Manager that declares the
`evpn-vxlan` capability and whose registration mutually names `cudn_evpn` as
a tested peer. `cudn_evpn` declares the Fabric Manager logical name in
`compatibleFabricManagers` only after the full manager conformance and pair
integration gates pass. The first targeted pair is Netris plus `cudn_evpn`;
current Netris conformance gaps mean it is not certified yet. Both managers use contract v1 registrations with a
logical name, fully qualified `implementationRef`, `contractVersion: v1`, and
technical capabilities. Registration does not list operations. The fixed
fabric-backed EVPN profile assigns the Fabric Manager's physical operations
and assigns `subnet.create` / `subnet.delete` to the K8s Manager.

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: osac-network-k8s-manager-cudn-evpn
  namespace: osac
  labels:
    osac.openshift.io/network-k8s-manager: "true"
data:
  name: cudn_evpn
  implementationRef: osac.templates.cudn_evpn
  contractVersion: "v1"
  capabilities: "ipv4,evpn-vxlan"
```

The `primarySubnet` capability is absent, so OSAC rejects selecting this
implementation in a K8s-only profile before creating an AAP job. The K8s-only
profile requires a manager that implements its full fixed fallback matrix.

### Fabric-to-K8s Subnet handoff

For each Subnet, OSAC first invokes the Fabric Manager's `subnet.create` task
with the deterministic handoff reference
`<operator-namespace>/osac-fabric-handoff-<subnet-uid>`. The Fabric role
creates or updates that contract-defined ConfigMap with `contractVersion`,
`profile`, Subnet UID, observed generation, L2/L3 VNIs, import/export route
targets for each VNI, and all reserved IPv4 CIDRs. The VNI and route-target
values are allocated or selected by the Fabric implementation; the K8s
implementation never derives them.

The Fabric task returns the common `osac_result` envelope with `data: {}`.
OSAC validates that result and the ConfigMap schema and identity, stores its
ConfigMap UID and resourceVersion, then invokes `cudn_evpn.subnet.create`
with the complete Subnet resource and the version-pinned ConfigMap reference
in `osac_job_vars.context.fabricHandoffConfigMap`. The K8s task reads the
referenced object, checks its UID, resourceVersion, Subnet UID, and observed
generation, and uses the contract fields to configure CUDN and FRR. It returns
its own `osac_result` with the operation, Subnet UID, and observed generation.
The K8s role does not call Fabric or read a Netris-specific object.

### One secondary CUDN per Subnet

The K8s task creates one namespace and one `ClusterUserDefinedNetwork` with
`role: Secondary` for each Subnet. It uses the Subnet UID for stable ownership
and derives the CUDN/NAD name from that UID. The CUDN and FRR configuration use the Subnet CIDR, `l2Vni`, `l3Vni`,
`l2RouteTargets`, `l3RouteTargets`, and `reservedIPv4CIDRs` read from the
validated contract ConfigMap. The Namespace selector and tenant/owner
metadata identify only that Subnet's workload namespace.

VMaaS resolves the VM's selected Subnet to its generated NAD and attaches that
secondary network to the VM pod. Each ComputeInstance continues to have at
most one tenant network attachment. VMs in different Subnets use distinct
CUDNs/NADs; the fabric's shared L3 routing domain provides cross-Subnet
reachability. OVN Connectors are not required for traffic routed by the
physical fabric. Multi-cluster VM placement, multiple tenant NICs, and direct
OVN routing between separate CUDNs remain out of scope.

Subnet deletion runs the K8s Manager's `subnet.delete` task before the Fabric
Manager deletes the physical segment. OSAC retains the handoff ConfigMap
through both cleanup stages so either manager can use the same data on retry.
The K8s role removes its CUDN and namespace only after VM attachments are
gone; OSAC deletes the ConfigMap after both managers confirm cleanup. All
steps retry by Subnet UID until observed complete. There is no subnet-count test, first-Subnet special case, or
`skip-k8s-manager` annotation.

### Installation prerequisites

The Cloud Infrastructure Admin installs OVN-Kubernetes, the FRR and NMState
operators, configures the VTEP and BGP underlay, and coordinates the gateway
MAC behavior required by the chosen Fabric Manager. OVN-Kubernetes updates
FRRConfiguration when the EVPN CUDN is created. These prerequisites are
installation configuration, not additional manager operations.

## UX Alignment

*Skip this section — no `osac-ux` temp-api file exists for NetworkClass or Subnet (backend-only feature).*

### Implementation Details/Notes/Constraints

#### Contract task crosswalk

| Contract operation | `implementationRef` | `tasks_from` | Input and result |
|---|---|---|---|
| `subnet.create` | `osac.templates.cudn_evpn` | `create_subnet` | Full Subnet resource plus the version-pinned `context.fabricHandoffConfigMap` reference; task reads and validates the shared ConfigMap and returns the common `osac_result` |
| `subnet.delete` | `osac.templates.cudn_evpn` | `delete_subnet` | Full Subnet resource, version-pinned `context.fabricHandoffConfigMap` reference, and UID-owned CUDN/NAD; successful task confirms deletion before returning `osac_result` |

These are the complete K8s Manager operations assigned by the
fabric-backed EVPN profile. A different profile has a different fixed
dispatch set and requires a compatible registration capability; the manager
does not use an operation list to opt out of tasks.

#### CUDN resource ownership and names

The Subnet UID is the owner key for the namespace, secondary CUDN, and NAD.
Names are deterministic, DNS-compatible encodings of that UID. Each generated
resource carries the OSAC Subnet UID, tenant, and owner-reference metadata.
The K8s role reconciles desired state on create and treats already-absent
objects as successful deletion. It removes only resources it owns.

#### Address exclusions and VM attachment

The task reads `reservedIPv4CIDRs`, `l2Vni`, `l3Vni`, `l2RouteTargets`, and
`l3RouteTargets` from the standard handoff ConfigMap and applies them to CUDN
and FRRConfiguration. It fails closed if the ConfigMap is missing, malformed,
stale, or contains reserved CIDRs outside the Subnet CIDR. OSAC validates the
Fabric result envelope and ConfigMap's Subnet UID/generation before passing
the version-pinned reference; the ConfigMap identity fields are separate from
its EVPN data. VMaaS selects the NAD associated with the resolved `subnetRef`;
the K8s Manager does not infer the selection from Subnet names or creation
order.

#### Deletion and retry

On delete, the Subnet controller waits for workloads using the Subnet to be
removed, then dispatches `subnet.delete`. The task deletes the CUDN, waits for
the CUDN to disappear, deletes its namespace and NAD, and returns success only
after all UID-owned objects are absent. OSAC then dispatches Fabric cleanup.
Retries use the same Subnet UID and safely continue from any partially
completed cleanup phase.

#### Current versus target behavior

The legacy implementation used one primary CUDN per VirtualNetwork, passed
Fabric Manager output through a private ConfigMap and private job variables,
and skipped K8s dispatch for later Subnets. Those behaviors are
superseded by this contract-aligned design and must not be carried into the
implementation.

### Security Considerations

The manager receives only the authorized Subnet object, the validated contract ConfigMap reference, and AAP credentials. The Fabric and K8s manager jobs receive only the Kubernetes access needed to write or read the named handoff in the configured OSAC namespace. Credentials are not stored in manager registration ConfigMaps or resource payloads. The K8s role creates resources only for the supplied Subnet UID and tenant, and deletion removes only objects carrying that UID ownership metadata. SecurityGroup policy remains the Fabric Manager's responsibility in this profile.

CUDN and FRRConfiguration are cluster-scoped implementation resources. Tenants interact through the existing OSAC APIs; only the provider-scoped AAP identity can create or remove these resources. Installation credentials for the underlay remain in provider-managed Secrets.

### Failure Handling and Recovery

- Invalid or missing handoff: OSAC rejects a missing/malformed/stale ConfigMap or a Fabric result whose operation, resource UID, or generation does not match the current Subnet. It does not start the K8s task until both the result envelope and ConfigMap identity/schema validate.
- K8s-side handoff mismatch: `cudn_evpn` reads the named ConfigMap and verifies its UID, resourceVersion, profile, Subnet UID, generation, VNIs, route-target sets, and reserved CIDRs against the request. A replaced or changed ConfigMap causes a retry after OSAC revalidates it. The manager must not infer missing fields from a manager-specific source.
- CUDN API or readiness failure: return a failed AAP task with a sanitized diagnostic. OSAC keeps the Subnet non-ready and retries through its provisioning lifecycle.
- Retry after partial create: reconcile the same UID-owned namespace, CUDN, and NAD to desired state without creating duplicates.
- Delete failure: return failure until all UID-owned CUDN/NAD/namespace resources are absent. OSAC retains the Subnet finalizer and retries before invoking Fabric cleanup.
- Missing or stale result: OSAC rejects an absent, malformed, stale, or mismatched osac_result; job success alone is not accepted as proof of convergence.

### RBAC / Tenancy

The AAP execution identity receives only the cluster permissions needed to manage the CUDN, Namespace, and NAD resources for this feature. CUDN labels and annotations retain the Subnet UID, tenant, and parent VirtualNetwork identity for audit and ownership. The K8s task validates the supplied tenant and owner identity and does not enumerate or modify unrelated tenant resources.

### Observability and Monitoring

Operators diagnose this manager through OSAC Subnet conditions and job history, the standard handoff ConfigMap and its validated UID/resourceVersion, `osac_result`, CUDN status, and OVN-Kubernetes/FRR events and logs. Failures identify the operation and missing or invalid contract field. No CUDN-specific callback, result annotation, or provider-specific ConfigMap is used for manager-to-manager transfer.

### Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Fabric Manager returns duplicate or invalid VNIs/route targets | The Fabric Manager must allocate values valid for the selected pair; OSAC validates the common schema and pair tests verify interoperability. |
| Handoff is lost or changes between manager stages | OSAC persists the validated ConfigMap UID/resourceVersion by Subnet UID and generation; K8s fails closed if that identity changes. |
| VTEP, FRR, or underlay is not ready | Installation validation and the documented prerequisites run before selecting this profile; CUDN readiness and route advertisement failures remain visible on the Subnet. |
| Concurrent Subnet creation | Every Subnet has a separate UID-owned CUDN/NAD; Fabric Manager allocation must be atomic and unique. |
| Partial deletion leaves overlay objects | K8s deletion is retry-safe and reports success only when all resources owned by the Subnet UID are absent. |

### Drawbacks

The deployment requires manual VTEP, FRR, NMState, BGP underlay, and gateway-MAC prerequisites. Subnet provisioning is sequential because the K8s Manager consumes the shared handoff written by the Fabric Manager, so it takes longer than independent parallel provisioning. The scope is single-cluster and each VM supports at most one tenant attachment; direct OVN routing between separate CUDNs is out of scope, while fabric-routed cross-Subnet traffic is supported.

## Alternatives (Not Implemented)

### One CUDN per VirtualNetwork

Rejected because it loses the one-to-one mapping between OSAC Subnets and workload networks, prevents distinct Subnet CIDRs and attachment selection, and makes resource readiness depend on creation order. Contract v1 requires the manager to reconcile every Subnet assigned by the selected profile.

### Supplier-specific ConfigMap or callback handoff

Rejected because it couples `cudn_evpn` to a particular Fabric Manager. Contract v1 instead defines one shared ConfigMap schema, deterministic name, validation boundary, and lifecycle. Fabric writes that standard object; K8s consumes it; OSAC validates and coordinates it.

### Single AAP workflow containing both managers

Rejected because it couples the generic dispatcher to one manager pair. Separate role invocations allow independently supplied implementations to use the same contract and preserve OSAC's validation and retry boundary between stages.

## Open Questions

### Gateway MAC coordination

The installer documentation must identify the authoritative gateway MAC and how the provider configures matching behavior in the selected Fabric Manager and OVN EVPN environment. A deployment cannot enable this profile until the chosen pair supports a deterministic match. This is an installation prerequisite, not an extra manager operation.

## Test Plan

The design's conformance tests validate the shared interface as well as CUDN behavior. They do not treat successful AAP job completion alone as a valid result.

### Unit and integration tests

- Validate cudn_evpn registration fields, role label, implementationRef, contractVersion v1, ipv4,evpn-vxlan capabilities, and compatibleFabricManagers. Reject missing capabilities, missing reciprocal pair declaration, Agentless VLAN pairing, and K8s-only profile selection before AAP.
- Validate the complete osac_job_vars envelope, subnet.create / subnet.delete task names, and Fabric-before-K8s sequencing.
- Accept a Fabric `osac_result` only when its operation, Subnet UID, and
  generation match the request and the referenced contract ConfigMap passes
  the v1 schema, profile, VNI, route-target, and CIDR checks. Reject invalid
  results or handoff data before creating a CUDN.
- Create two Subnets in either order. Verify each receives one secondary CUDN/NAD and that its VNIs, L2/L3 import/export route targets, and reserved CIDRs match its UID-owned handoff ConfigMap.
- Retry create after partial progress and verify no duplicate namespace, CUDN, or NAD is created.
- Delete one of two Subnets; verify only that Subnet's UID-owned resources are removed and Fabric deletion starts only after K8s cleanup result validation.
- Reject absent, stale, or malformed K8s osac_result; retain non-ready status and retry.

### End-to-end tests

- Attach VMs and fabric-connected bare-metal endpoints to the same Subnet and verify L2 reachability.
- Attach endpoints to different Subnets of one VirtualNetwork and verify fabric-routed L3 reachability, regardless of Subnet creation order.
- Verify OVN DHCP addresses do not overlap reservedIPv4CIDRs supplied by the Fabric Manager.
- Verify an incompatible profile or unavailable prerequisite produces an actionable diagnostic before a workload is reported Ready.

## Graduation Criteria

- Every assigned K8s operation conforms to the Network Manager Integration Contract v1 and passes contract-result replay, retry, and deletion tests. The declared Netris pair passes the pinned-version handoff and end-to-end connectivity suite; other Fabric peers are not advertised until their pair suite passes.
- Every Subnet gets its own ready secondary CUDN/NAD and VMs reach same-Subnet and fabric-routed cross-Subnet peers.
- Installation prerequisites and troubleshooting steps are documented and validated in the deployment environment.

## Upgrade / Downgrade Strategy

This feature adds a K8s Manager registration and operation behavior; it does not change tenant-facing networking APIs. The operator, installer, and AAP execution environment must all support contract v1 registration and result validation before cudn_evpn can be selected. Existing Subnets created by the legacy single-CUDN implementation require an explicit migration that maps each Subnet UID to its own CUDN/NAD; the upgrade must not silently claim those objects are contract-conformant. Drain or migrate legacy resources before enabling the new profile. Downgrade requires deleting or explicitly retaining the CUDN/NAD objects before removing the manager registration.

## Version Skew Strategy

OSAC must validate registration contractVersion, capabilities, and mutual peer compatibility before dispatch. A controller that does not understand contract v1 or cannot validate osac_result and the standard handoff ConfigMap must reject cudn_evpn as unavailable; it must not invoke a default role or read a supplier-specific handoff object. Roll out the contract-aware operator, the cudn_evpn collection, and registration together. During skew, Subnets remain non-ready with a diagnostic rather than being reported successful without a validated handoff/result.

## Support Procedures

1. Inspect the Subnet condition and provisioning job history to identify the failed operation and manager.
2. Inspect the Fabric osac_result envelope and the standard handoff ConfigMap for matching operation, Subnet UID, generation, VNIs, route targets, and reserved CIDRs.
3. Inspect the K8s job's version-pinned context.fabricHandoffConfigMap reference, the K8s osac_result, and the UID-owned Namespace/CUDN/NAD.
4. Check CUDN readiness, VTEP and FRR status, BGP EVPN routes, and the relevant OVN-Kubernetes events.
5. For deletion, confirm that VM attachments are gone and that every resource with the Subnet UID has been removed before diagnosing Fabric cleanup.

Do not repair the Subnet by editing the contract handoff ConfigMap or calling an OSAC callback. Correct the selected manager or infrastructure prerequisite, then allow OSAC to retry the contract operation.

## Infrastructure Needed

None. The OpenShift cluster, an evpn-vxlan-capable physical fabric, and FRR operator are assumed to exist per PRD assumptions.

---

**End of Design Document**

---

## Provenance

Authored: revise @ design 0.11.3 - cc0daa6, workspace main @ 06d340f90 (67 behind origin/main)
Final: revise @ design 0.11.3 - 2bd6607, workspace main @ e97b06357

> Context changed between revise and revise.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.3","ai_workflows":"2bd6607","source_repo":"e97b06357","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["revise","revise","revise","revise","revise","respond","respond","revise","revise","revise","revise","manual-edit","revise","manual-edit","revise","manual-edit","revise","respond","respond","revise","revise","revise"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":true} -->
