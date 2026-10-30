---
title: cudn-evpn-k8s-manager-phase-1-networking
authors:
  - Benny Kopilov
creation-date: 2026-09-03
last-updated: 2026-10-28
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-4291
  - https://redhat.atlassian.net/browse/OSAC-6758
prd: prd.md
see-also:
  - /enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md
  - /enhancements/OSAC-1433-unified-networking/design.md
  - /enhancements/OSAC-1435-vmaas-networking/design.md
replaces:
  - N/A
superseded-by:
  - N/A
---

# CUDN EVPN Kubernetes Manager: VM-to-Fabric Networking

## Summary

The `cudn_evpn` manager connects VM primary networks to an EVPN Fabric using a VirtualNetwork-owned namespace and one ClusterUserDefinedNetwork per VirtualNetwork. It prepares SecurityGroup policies and VM bindings before boot, preserves recorded addresses and identifiers on retries, and removes only owned state.

## Motivation

Tenants need usable VM networks with isolation, DHCP, persistent addresses and connectivity to permitted Fabric destinations. The [manager integration contract](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md) defines the task interface; [Unified Networking](/enhancements/OSAC-1433-unified-networking/design.md) defines tenant resources; [VMaaS](/enhancements/OSAC-1435-vmaas-networking/design.md) owns VM creation and teardown. The [PRD](prd.md) defines the user outcomes.

### Goals

- Implement the eight Kubernetes Manager tasks with minimal saved snapshots and typed results.
- Prepare the namespace, primary network and selected policy before VM creation.
- Preserve VirtualNetwork/Subnet APIs, ownership, immutable specifications, recorded address pools and segment identifiers across supported retries.
- Support one VM-capable owner Subnet per VirtualNetwork, with explicit errors for unsupported attachments.

### Non-Goals

- Tenant Update/Patch operations on VirtualNetwork/Subnet, tenant-configured VNIs or route targets.
- Migration/adoption of live legacy networking, additional hubs, secondary tenant attachments, IPv6, dual-stack or disconnected deployments.
- Manager configuration of host uplinks, peering, FRR, VTEPs or MetalLB address pools.
- Changes to Fabric SecurityGroup no-op permissions or the shared SecurityGroup update-status protocol.

## Proposal

### Terminology

| Term | Meaning |
|---|---|
| VN | VirtualNetwork, the routing-domain parent of Subnets and SecurityGroups |
| CUDN | OVN-Kubernetes ClusterUserDefinedNetwork |
| VNI | 24-bit VXLAN network identifier; L2 belongs to a Subnet, L3 to a VN |
| RT | EVPN route target; `0:<l2_vni>` for MAC-VRF and `0:<l3_vni>` for IP-VRF |
| VRF | Virtual routing and forwarding domain; MAC-VRF bridges, IP-VRF routes |
| ASN | BGP autonomous-system number, independent of the explicit RT encoding |
| UID / RV | Kubernetes object UID and opaque resourceVersion, used as conditional-write preconditions |
| Owner Subnet | The Subnet API ID recorded by the VN's one CUDN; it owns the VM-capable realization until deletion |

The Fabric allocates VNIs, carries the MAC-VRF/IP-VRF and routes the IP-VRF. OVN-Kubernetes serves the VM gateway at `ipam.gateway_ipv4` through `defaultGatewayIPs`, routing symmetrically into the IP-VRF. A Fabric gateway for physical workloads is a BMaaS follow-up concern; it must not be assumed to serve the VM gateway or introduce a competing gateway. Physical enforcement remains governed by the existing shared contract.

### Workflow Description

#### Installation

1. The provider prepares Fabric peers, matching VRF imports/exports, VTEP underlay reachability and at least 1550-byte frame capacity for a 1500-byte workload MTU.
2. The administrator supplies `osac-infra` `evpn` values. The installer owns NMState, per-node uplink and VTEP addresses, hub network configuration, `tenant-vtep`, FRR, and `RouteAdvertisements` named `osac-evpn`; that advertisement selects CUDNs with `evpn: "true"`. It waits for BGP Established. Installer delivery is a dependency tracked in [osac #1993](https://github.com/osac-project/osac/pull/1993); its availability and real-cluster validation gate activation.
3. The installer registers the immutable `cudn_evpn` role with `network_type: evpn`, supplies the networking instance-group settings/Secret and validates the address plan, DNS delivery and installed API capabilities before admitting tenants.
4. Validate each selected Fabric/Kubernetes pair with actual routes and traffic. A merged host template or successful registration does not establish pair support.

#### Creation and attachment

1. Core creates the VN through Fabric first. Fabric returns integer `l3_vni`, with the existing optional `backend_id`. Core validates and records the L3 VNI in private `VirtualNetwork.status.l3Vni` before dependent Subnet tasks.
2. Kubernetes `create_virtual_network` prepares the VN namespace. SecurityGroups can then be created before any Subnet.
3. Fabric `create_subnet` receives that parent `l3_vni` and recorded IPAM and returns only `network_segment: {type: evpn, l2_vni: <integer>}`. Core accepts the segment into `Subnet.status.networkSegment` before Kubernetes work.
4. Kubernetes `create_subnet` atomically creates the VN-keyed CUDN to claim it for one Subnet API ID. It installs baseline protection and waits for readiness for the current CUDN generation. Sibling Subnet network creates succeed without changing the CUDN or owner.
5. Before a VM exists, Kubernetes `apply_network_attachment` validates the owner and all selected current group policies, binds the ComputeInstance API ID and returns exactly `vm_attachment: {namespace: <VN namespace>}`.
6. VMaaS creates the VM with an `l2bridge` primary interface, persistent-IP claim handling and the pod label `osac.openshift.io/compute-instance-id: <ComputeInstance API ID>`. It discovers the VM address before core runs the Fabric overlay apply.

A VM attachment to a non-owner Subnet fails permanently with `cudn_evpn supports VM attachments only on the owner Subnet of this VirtualNetwork`. That failure changes neither the existing owner nor physical siblings. The manager never reads or mutates a VM/VMI.

#### Deletion

VMaaS removes the VM before core runs Fabric attachment delete followed by Kubernetes attachment delete. Unbinding removes only the target ID; the shared namespace, baseline and other targets remain. Group deletion removes that group's policy after references are gone. Owner Subnet deletion removes its CUDN and baseline and releases the claim without handover; it retains the VN namespace and independent groups. VN deletion removes its namespace only after all children are gone and strict owned cleanup is complete. Core retains finalizers on failed or unproven cleanup.

### API Extensions

No tenant API extension is introduced. Existing VirtualNetwork/Subnet Create/Get/List/Delete contracts, IDs, parent references, immutable specifications and default selection remain. VN L3 and Subnet L2 identifiers are internal observed state; tenants do not supply them.

Core saves task input once and supplies explicit `tenant`, stable API-ID snapshots, recorded `ipam`, parent `l3_vni` and accepted `{type, l2_vni}` where required. It validates every typed result and preserves values for retry/delete. Source API/CRD projection and dispatch are shared-core work under [OSAC-6766](https://redhat.atlassian.net/browse/OSAC-6766); this manager does not write OSAC custom resources.

**Policy API restriction:** this manager rejects an explicit `icmp` SecurityGroup rule with `osac_error: {message: "cudn_evpn does not support explicit ICMP SecurityGroup rules", retryable: false}` before any policy mutation. The public SecurityGroup schema still accepts ICMP for other managers; selecting `cudn_evpn` makes that rule unsupported, not silently broadened. Installation validates default group rules before tenant onboarding, so an ICMP default fails installation with the same diagnostic rather than failing every tenant's default networking. TCP/UDP ranges and `all` retain exact shared-contract semantics.

### Implementation Details/Notes/Constraints

#### Task interface

Every task receives the shared `osac_job_vars` envelope and explicit tenant. A successful task has no `osac_result` unless the table lists one. Malformed/missing installation settings and API conflicts fail retryably; invalid inputs, unsupported policy or non-owner VM attachment fail permanently. Errors are sanitized and fail the Ansible play.

| Task pair | Inputs in addition to manager/task/tenant | Create/apply and delete behavior | Result |
|---|---|---|---|
| `create_virtual_network` / `delete_virtual_network` | VN snapshot | Create/reuse VN namespace; remove it only at final VN teardown | None |
| `create_subnet` / `delete_subnet` | Subnet and VN snapshots, `ipam`, parent `l3_vni`, `{type, l2_vni}` segment | Claim/reconcile VN-keyed CUDN and baseline; owner delete removes these without namespace/group removal or handover | None |
| `create_security_group` / `delete_security_group` | Group and VN snapshots, complete rules | Create/conditionally replace one policy per group; remove that policy on delete | None |
| `apply_network_attachment` / `delete_network_attachment` | Attachment/target/Subnet/VN snapshots, group IDs, segment, parent `l3_vni` | Bind/unbind target ID in current group selectors, preserving rules and other IDs | `vm_attachment: {namespace}` on apply only |

#### Namespace, CUDN and atomic owner claim

Names are keyed by the never-reused VN API ID: namespace and CUDN `ce-<VN UUID>`. Group names use `sg-<group UUID>`. These are creation rules for fresh activation; supported retries reuse recorded compatible names and UIDs. Missing/foreign identity never permits replacement.

The following complete examples use VN `11111111-1111-4111-8111-111111111111`, owner Subnet `22222222-2222-4222-8222-222222222222`, tenant `tenant-a`, L2 VNI 10100, parent L3 VNI 20001 and Subnet `192.0.2.0/24`. Its saved overlay pool is `.0/25`, physical pool `.128/26`, and ingress VIP pool `.192/26`.

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: ce-11111111-1111-4111-8111-111111111111
  labels:
    k8s.ovn.org/primary-user-defined-network: ""
    osac.openshift.io/tenant: tenant-a
    osac.openshift.io/virtualnetwork-id: 11111111-1111-4111-8111-111111111111
    osac.openshift.io/owner-kind: virtualnetwork
    osac.openshift.io/owner-id: 11111111-1111-4111-8111-111111111111
  annotations:
    osac.openshift.io/tenant: tenant-a
    osac.openshift.io/owner-reference: VirtualNetwork/vn-a
---
apiVersion: k8s.ovn.org/v1
kind: ClusterUserDefinedNetwork
metadata:
  name: ce-11111111-1111-4111-8111-111111111111
  labels:
    evpn: "true"
    osac.openshift.io/tenant: tenant-a
    osac.openshift.io/owner-kind: virtualnetwork
    osac.openshift.io/owner-id: 11111111-1111-4111-8111-111111111111
  annotations:
    osac.openshift.io/tenant: tenant-a
    osac.openshift.io/owner-reference: VirtualNetwork/vn-a
    osac.openshift.io/owner-subnet-id: 22222222-2222-4222-8222-222222222222
spec:
  namespaceSelector:
    matchLabels:
      osac.openshift.io/virtualnetwork-id: 11111111-1111-4111-8111-111111111111
      osac.openshift.io/tenant: tenant-a
  network:
    topology: Layer2
    transport: EVPN
    layer2:
      role: Primary
      mtu: 1500
      subnets: [192.0.2.0/24]
      defaultGatewayIPs: [192.0.2.1]
      infrastructureSubnets: [192.0.2.1/32, 192.0.2.2/32]
      reservedSubnets: [192.0.2.128/25]
      ipam:
        mode: Enabled
        lifecycle: Persistent
    evpn:
      vtep: tenant-vtep
      macVRF:
        vni: 10100
        routeTarget: "0:10100"
      ipVRF:
        vni: 20001
        routeTarget: "0:20001"
```

`POST` with that deterministic CUDN name is the atomic claim: only one request can create it. On AlreadyExists, read from the API server and verify tenant, VN identity, owner Subnet, saved pools and VNIs. The same live owner may reconcile; a different owner must not overwrite it. A terminating CUDN or owner Subnet holds the claim and causes a retryable conflict. Deletion uses UID/RV preconditions and waits for authoritative absence before releasing the claim. This prevents concurrent owner takeover; it does not prove safety against an already-issued create after deletion, which remains the explicit blocker below.

Compute the minimal reserved CIDR cover outside the overlay pool, subtracting infrastructure reservations so the lists are disjoint. The gateway is always reserved; another infrastructure address comes only from the saved overlay range. Exclude network/broadcast/gateway/infrastructure from workload allocation. If there are more than 25 `reservedSubnets` entries, fail permanently with `cudn_evpn reservedSubnets exceeds 25 entries`; do not merge across a permitted workload address or change saved IPAM. Set MTU 1500 explicitly. The [OVN API](https://ovn-kubernetes.io/1.4/api-reference/userdefinednetwork-api-spec/) defines these fields and limits; its schema support and deployed behavior must both be validated for the selected platform.

`ipam.lifecycle: Persistent` selects OVN IPAMClaims; VMaaS/KubeVirt owns claim association and retention across restart/live migration. The manager must not allocate another address on retry or remove VM-owned claims. See [OVN persistent IP lifecycle](https://ovn-kubernetes.io/master/features/multiple-networks/multi-homing/#persistent-ip-addresses-for-virtualization-workloads).

#### DHCP resolvers

OVN's Layer2 VM DHCP obtains resolver addresses from the DNS Service selected by its `dns-service-namespace` / `dns-service-name` configuration. There is no CUDN DNS field. Required manager settings `CUDN_EVPN_DNS_SERVICE_NAMESPACE` and `CUDN_EVPN_DNS_SERVICE_NAME` identify that existing Service; no namespace/name default is assumed. The job reads only that Service through the hub API. The installer must identify and validate that supported platform configuration and compare its IPv4 Service addresses with the ordered, canonical `CUDN_EVPN_DNS_RESOLVERS` list before activation. The manager checks the same installed Service/profile; a mismatch fails retryably before writes, never silently substitutes resolvers or patches OVN's database. The chosen pair must demonstrate guest DHCP delivering the agreed list and reaching it from the tenant routing domain. Arbitrary external resolver injection beyond this supported path requires a separately reviewed platform mechanism; it is not implemented by inventing a field. [OVN DHCP DNS configuration](https://ovn-kubernetes.io/master/features/multiple-networks/multi-homing/#configuring-dns-server), [DHCP Service lookup](https://github.com/ovn-kubernetes/ovn-kubernetes/blob/master/go-controller/pkg/kubevirt/dhcp.go).

#### Baseline and group manifests

The VN namespace is prepared before workloads. Once a Subnet owns the network, this baseline isolates all pods in both directions; selected group policies add permitted application traffic. DHCP exceptions permit the platform's DHCP exchange; OVN handles ARP outside these IPv4 NetworkPolicy rules. Actual primary-network enforcement and DHCP/ARP behavior require deployed checks.

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: baseline-22222222-2222-4222-8222-222222222222
  namespace: ce-11111111-1111-4111-8111-111111111111
  labels:
    osac.openshift.io/owner-kind: subnet
    osac.openshift.io/owner-id: 22222222-2222-4222-8222-222222222222
  annotations:
    osac.openshift.io/tenant: tenant-a
    osac.openshift.io/owner-reference: Subnet/subnet-a
spec:
  podSelector: {}
  policyTypes: [Ingress, Egress]
  ingress:
    - ports: [{protocol: UDP, port: 68}]
  egress:
    - ports: [{protocol: UDP, port: 67}]
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: sg-33333333-3333-4333-8333-333333333333
  namespace: ce-11111111-1111-4111-8111-111111111111
  labels:
    osac.openshift.io/owner-kind: securitygroup
    osac.openshift.io/owner-id: 33333333-3333-4333-8333-333333333333
  annotations:
    osac.openshift.io/tenant: tenant-a
    osac.openshift.io/owner-reference: SecurityGroup/web
    osac.openshift.io/rule-generation: "1"
    osac.openshift.io/rule-digest: "sha256:d4202eb8e1f5a8e9a0468962d2b3a33ada5c3fbac251615bf92fbb86691bfd85"
spec:
  podSelector:
    matchExpressions:
      - {key: osac.openshift.io/compute-instance-id, operator: Exists}
      - {key: osac.openshift.io/compute-instance-id, operator: DoesNotExist}
  policyTypes: [Ingress, Egress]
  ingress:
    - from: [{ipBlock: {cidr: 192.0.2.0/24}}]
      ports: [{protocol: TCP, port: 443}]
  egress: []
```

The rule digest is SHA-256 of canonical JSON for ingress, egress and policyTypes, with sorted object keys and compact separators after deterministic rule normalization; it excludes selector membership and metadata. The unbound selector is deliberately contradictory, never empty. Binding replaces it with a single `In` expression containing sorted unique ComputeInstance API IDs. One group object serves every bound target; namespace and group lifetime do not depend on an owner Subnet existing. TCP/UDP port ranges use `port`/`endPort`; `all` omits the port restriction while retaining its peer CIDR. An explicit ICMP rule fails as documented in API Extensions and the PRD. Reject unsupported/capacity-limited rules before mutating the policy.

#### Conditional rule replacement and membership

Use only non-creating `PATCH` with media type `application/json-patch+json` on an existing policy. Every fixed patch tests `/metadata/uid` and `/metadata/resourceVersion`. Rule updates replace ingress, egress, policyTypes and rule generation/digest together, preserving the selector. Bind/unbind changes only the selector, preserving current rules and other targets. Verify ownership and current source generation before constructing the patch. Reject an older generation or an equal generation with another digest. Conflict causes a fresh authorized reconciliation, never force apply or delete/recreate.

On 404, a stale bind/update fails retryably and cannot create its target. A legitimate group create is a separate authorized task; it is not a fallback for a failed patch. Never use Server-Side Apply for this operation. If the target ID was already absent, unbind is idempotent and performs no patch; an absent object has no RV to advance. When cleanup must invalidate a known pending fixed patch against an existing policy, write a changed membership revision even if membership was already absent. If the policy has disappeared, that fixed non-creating patch already fails. These arguments apply to patches only, not POSTs.

A definitively rejected patch keeps the previous rules. If a response is lost, its outcome is unknown: retain pending/retryable status and read/reconcile the desired generation and digest without claiming rollback. Do not report successful binding against stale rules or let an older fixed patch overwrite a newer generation. Prove the conflict, missing-target, response-loss and restart traces with real API requests before implementation acceptance. [Kubernetes conditional updates and PATCH types](https://kubernetes.io/docs/reference/using-api/api-concepts/#updates-to-existing-resources).

#### Interface Changes

The following identifiers are local design-to-test mappings, not API fields or Jira acceptance criteria.

| ID | Boundary |
|---|---|
| IC-1 | Registration and installer-owned prerequisites/settings |
| IC-2 | Eight saved task inputs/results and VN namespace lifetime |
| IC-3 | VN L3 / Subnet L2 handoff, CUDN, gateway, pools, DNS and MTU |
| IC-4 | Atomic owner claim, cancellation and strict owned cleanup |
| IC-5 | Baseline, exact group policy and conditional rule/membership updates |
| IC-6 | Pre-VM binding, namespace result and persistent-address workload integration |

Manager implementation belongs to [OSAC-6761](https://redhat.atlassian.net/browse/OSAC-6761), core/API consumers to [OSAC-6766](https://redhat.atlassian.net/browse/OSAC-6766) / [OSAC-6768](https://redhat.atlassian.net/browse/OSAC-6768), installation to [OSAC-6769](https://redhat.atlassian.net/browse/OSAC-6769). The installer schema must be consumed and validated through Enclave plugin and Wizard; tenant forms retain ordinary Subnet and SecurityGroup references. These are component dependencies, not assignment-status claims.

### Security Considerations

Validate tenant, API-ID ownership, parent VN, saved pools and VNIs before writes. Every created Namespace, CUDN and policy carries tenant/owner-reference annotations and owner-kind/owner-id labels as shown above. Foreign identity fails without mutation. Preserve tenant isolation even for overlapping VN CIDRs and sanitize logs/results. No task reads secrets from workload resources or accesses VM/VMI objects.

### Failure Handling and Recovery

Read authoritative API state for ownership/termination and use conditional patches/deletes. Missing prerequisites and conflicts are retryable. Unsupported policy/attachment and invalid input are final errors. Preserve previous allocations and UIDs on compatible retries. Core owns dispatch serialization, cancellation and finalizers; manager application locks/Leases are not introduced.

**Strict deletion blocker:** no native Kubernetes primitive has yet been demonstrated to prevent an already-issued Namespace/CUDN/policy POST from recreating an object after successful deletion. Deterministic names and UID/RV checks solve owner conflicts and stale patches, not new POSTs. A separate journal, preflight tombstone read, ended AAP job, absent GET or elapsed timeout does not establish settlement. Keep delete pending and retain the finalizer whenever that outcome is unknown. Do not replace the existing safeguards or activate this lifecycle until a backend ordering/fencing mechanism and restart recovery are reviewed and proven. Inert retained objects and eventual cleanup are not selected; the strict complete-removal guarantee remains.

### RBAC / Tenancy

The networking job service account requires the following exact resource classes. A ClusterRoleBinding grants the listed verbs to the trusted job service account. NetworkPolicy permissions are consequently effective across namespaces, including dynamically created VN namespaces; Kubernetes RBAC does not restrict them by tenant labels. Provider admission restrictions and manager ownership checks must reject writes outside managed VN namespaces. Namespace create/delete and CUDN permissions are cluster-scoped; this privilege must be reviewed explicitly.

| API group / resource | Scope | Verbs | Purpose |
|---|---|---|---|
| core / namespaces | Cluster | get, list, create, patch, delete | VN namespace lifetime and verified cleanup |
| k8s.ovn.org / clusteruserdefinednetworks | Cluster | get, list, watch, create, patch, delete | Atomic claim, realization, readiness, conditional cleanup |
| networking.k8s.io / networkpolicies | Namespaced, granted cluster-wide | get, list, create, patch, delete | Baseline/group lifetime and conditional updates |
| k8s.ovn.org / vteps, routeadvertisements | Cluster | get, list | Validate installed `tenant-vtep` and advertisement selection |
| frrk8s.metallb.io / frrconfigurations | Installed FRR namespace | get, list | Read prerequisite configuration; no peering mutation |
| core / services | Selected DNS namespace | get | Verify installed DHCP resolver source |
| osac.openshift.io / subnets, virtualnetworks | Networking namespace | get | Authoritative owner/termination checks only |

No permissions are granted for OSAC CR mutation/status, VM/VMI, pod or IPAMClaim mutation, Secrets, Leases, NMState or FRR writes. The installer owns prerequisite mutations. If installed API groups differ, fail preflight rather than widening permissions implicitly.

### Observability and Monitoring

Use existing task/job status and structured logs keyed by task, manager, resource API ID and attempt. Record prerequisite failures, rejected foreign ownership, owner conflicts, conditional-write conflicts and unresolved cleanup. Expose sanitized failure reasons and pending retry state; never present unknown cleanup as success. New metrics are not required by this change. Operational duration/retry trends can use existing job telemetry; packet and supported-pair results belong to the validation report.

### Risks and Mitigations

| Risk | Mitigation |
|---|---|
| An outstanding create resurrects deleted state | Block lifecycle activation on the missing enforced ordering/fence proof; retain finalizers on unknown outcomes |
| Policies appear present without primary-network enforcement | Require actual OVN traffic, DHCP/ARP, rule-update and pre-boot tests |
| Wrong advertisement selector or mismatched RTs silently drops routes | Require `evpn: "true"`, installer readiness and per-pair route/traffic evidence |
| Unsupported DNS configuration or fragmented exclusion cover | Validate installed DNS delivery and the 25-entry limit before activation/mutation |
| New lifecycle rewrites legacy state | Reject activation before any write; preserve records, UIDs, allocations, RTs and workloads |

### Drawbacks

One VM-capable Subnet limits placement within a VN. One policy object avoids duplicated rule copies but couples rule and membership writes through API conflicts. Cluster-scoped Namespace/CUDN privileges increase the impact of a manager bug. Platform-specific DNS and strict deletion recovery require more evidence than rendering alone; these costs remain prerequisites for supported activation.

## Alternatives (Not Implemented)

- Per-attachment namespaces and policy copies add duplicate updates and conflict with groups existing before any Subnet; use one VN namespace and one policy per group.
- Reuse of a sibling Subnet's owner network silently attaches VMs to the wrong CIDR; reject the unsupported attachment.
- Force apply or delete/recreate on policy conflict can lose membership or isolation; use non-creating conditional JSON Patch.
- A separate coordinator journal or manager Lease alone cannot fence an already-issued POST; neither is selected as the deletion solution.
- Direct OVN database writes for DNS/ICMP bypass the supported API contract; validate the supported DNS path and explicitly reject unsupported ICMP.

## Open Questions

**Backend deletion fence and recovery — implementation blocker.** Connectivity/Fabric and core lifecycle maintainers must select and demonstrate a backend primitive that prevents post-success recreation for Namespace, CUDN and policy creates, including crash-before-send and lost-response ambiguity. Closure requires reviewed state transitions and real-API race/restart evidence. It must preserve strict removal, stable API IDs and the no-manager-lock boundary. This decision must close before implementation acceptance and activation; no calendar date is invented.

**Installed platform qualification.** Connectivity/Fabric and platform maintainers must record the supported OVN/KubeVirt/FRR versions and the installed DNS-Service configuration, admission, persistent-IP and primary-policy results. The object model and conditional-write method above are selected; a version/profile or DNS configuration that cannot realize them fails readiness. No supported pair is claimed before the report exists.

## Test Plan

The [test plan](testplan.md) defines case metadata, source outcomes, IC-1–IC-6 coverage, numbered steps, fixtures, priorities and planned entry points. Cases blocked by the deletion mechanism remain explicit; required skips never count as a pass.

### Unit Tests

Extend `osac-aap/tests/unit/test_cudn_evpn_role.py` (`_render_cudn`, `_run_role_with_inputs`) and deletion-order regressions for exact input/result validation, integer VNI range without ASN coupling, RTs, selector/metadata rendering, IPAM exclusion count, policy compiler restrictions and owned cleanup.

### Integration Tests

Add `osac-aap/tests/integration/targets/cudn_evpn/tasks/baseline.yml` and independently executed race scenarios to the existing Kind harness; register them in `run_tests.sh`, making `make -C osac-aap test` the aggregate entry point. These planned targets must exercise real Namespace/CUDN/policy API operations, ownership conflicts, non-creating patches and restart traces. CRD/prerequisite fixtures must be identified as fakes; they do not prove OVN, KubeVirt, FRR or Fabric traffic. Shared core and installer suites validate typed dispatch, saved status and preflight separately.

### E2E Tests

Add `tests/e2e/vmaas/regression/test_cudn_evpn_networking.py` for the full deployed journey, using `grpc`/`k8s_hub_client` from tests/e2e/conftest.py and `k8s_virt_client`/`vm_template` from tests/e2e/vmaas/conftest.py and `wait_for_subnet_ready`, `wait_for_vmi_ip`, `poll_until` helpers. The planned invocation is `uv run pytest -n 0 tests/e2e/vmaas/regression/test_cudn_evpn_networking.py` from the OSAC root once implemented. Record exact versions, commands and real/faked dependencies. Prove DHCP gateway/DNS, denied/allowed traffic, restart/live-migration address stability and safe teardown with real Fabric, initially Netris; every additional pair requires its own report.

## Graduation Criteria

The prerequisite manager-contract amendment is approved; core, manager, installer and Fabric inputs/results agree; installed platform qualification and the strict deletion mechanism are complete; component tests and the real Netris VM-profile journey pass. Publish a report with versions, RT imports/exports, observed routes, commands and pass/fail/skip results. Documentation approval or a rendered manifest is insufficient runtime evidence. Update administrator installation/troubleshooting and tenant ICMP/owner-limit guidance before release.

## Upgrade / Downgrade Strategy

Fresh activation only. Existing live legacy VN/Subnet records, CRs, namespaces, CUDNs, selectors, RTs, address pools and workloads remain unchanged. Core/installer rejects activation before configuration changes, readiness resets, task dispatch or cleanup. No automatic migration, rename, ownership handover or network recreation is permitted.

On freshly activated compatible installations, retries/restarts preserve saved manager identities, namespace/CUDN UIDs, owner, IPAM, VNIs and guest addresses. New task files do not trigger provisioning replay or reallocation. In-place adoption or a different minor networking contract requires a separate reviewed transition; supported patch updates must retain these invariants.

## Version Skew Strategy

Activate only a compatible core/installer/manager/Fabric set. A legacy Subnet-only role cannot satisfy the namespace/policy gate. Reject a missing task, wrong output shape or unsupported prerequisite explicitly; never fall back to legacy variables or reset live state. Keep the current supported configuration active when the new preflight fails.

## Support Procedures

Inspect the recorded task input/job attempt, installed EVPN values, `tenant-vtep`, `osac-evpn`, CUDN conditions for the current generation, owner annotations and conditional-write errors. Compare matching RTs and actual BGP/routes before diagnosing application traffic. For unresolved cleanup, retain the finalizer and collect request/commit history; do not remove objects or retry with forced ownership to manufacture success. Correct prerequisites and allow normal reconciliation; unsupported activation leaves existing networks in place.

---

## Provenance

Authored: revise @ design 0.11.5 - 1c6e8de, workspace codex/cudn-evpn-route-targets @ 38d18d944 (7 behind origin/main)
Final: respond @ design 0.11.5 - 1c6e8de, workspace codex/osac-6761-cudn-evpn-contract @ a6aa33f0b (79 behind origin/main)

> Context changed between revise and respond.
>
> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"1c6e8de","source_repo":"a6aa33f0b","source_repo_branch":"codex/osac-6761-cudn-evpn-contract","commits_behind_main":79,"commits_ahead_main":2,"main_ref":"main","phases":["revise","revise","revise","revise","revise","revise","revise","revise","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":true} -->
