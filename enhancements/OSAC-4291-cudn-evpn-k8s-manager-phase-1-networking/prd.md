# CUDN EVPN K8s Manager Phase 1 Networking: Single-Cluster VM-to-Fabric Bridging

| Field       | Value   |
|-------------|---------|
| Author(s)   | Benny Kopilov |
| Jira        | https://redhat.atlassian.net/browse/OSAC-4291 |
| Date        | 2026-09-24 |

This Phase 1 PRD inherits the [Unified Networking deployment support
boundary](/enhancements/OSAC-1433-unified-networking/prd.md#deployment-support-boundary):
the deployment must be connected, and air-gapped or disconnected networking
deployments are not supported.

This Phase 1 PRD also inherits the [Unified Networking hub support
boundary](/enhancements/OSAC-1433-unified-networking/prd.md#networking-hub-support-boundary):
OSAC networking supports exactly one provider-owned hub per deployment.
Multi-hub networking placement, cross-hub resource coordination, and
cross-hub network connectivity are unsupported. This boundary applies only to
the networking area and does not define hub behavior for other OSAC areas.
Multiple hosting/workload clusters remain supported where a networking feature
explicitly specifies them.

## Problem Statement

OSAC runs VMs on OpenShift using KubeVirt, which encapsulates each VM in a pod whose networking is managed by OVN-Kubernetes. By default, VM IP addresses exist only within the OVN overlay and are not visible on the physical fabric. This prevents VMs from being first-class fabric participants — they cannot share the same L2 subnet with bare-metal servers, cannot be reached directly from the fabric, and cannot leverage the fabric's multi-tenancy and routing capabilities.

Without a k8s manager that bridges VMs to the fabric, tenants cannot deploy workloads that span VMs and bare-metal hosts in the same subnet. The CUDN LocalNet approach (OSAC-1511) has been frozen in favor of OVN EVPN, which provides better scalability and multi-cluster support. [Clarify: R1.Q3]

The OVN EVPN spike (OSAC-1717) validated the technical approach: VMs can join the fabric via BGP EVPN route advertisements and communicate with fabric endpoints on the same Subnet at L2. Phase 1 supports VM placement only while a VirtualNetwork has exactly one Subnet. A second Subnet is allowed after VMs are removed; a VirtualNetwork with multiple Subnets is fabric-only and rejects VM placement. Cross-Subnet L3 validation, if performed, uses fabric and bare-metal endpoints in a multi-Subnet VirtualNetwork with no VMs. OVN-Kubernetes does not currently route between separate CUDNs on the same cluster (the Connectors feature is pending). [Clarify: R1.Q4]

## In Scope

- **K8s manager registration** for EVPN fabric bridging (IPv4 address family only) [Clarify: R2.Q4]
- **Fabric-to-k8s manager data dependency** — subnet provisioning must ensure the fabric manager completes and provides network segment identifiers before the k8s manager begins, using a manager-agnostic interface [Clarify: R1.Q3, R2.Q5, D7] [User]
- **Automatic overlay network provisioning** on hosting clusters that bridges VMs to the physical fabric when a VirtualNetwork/Subnet is created [Clarify: R2.Q1]
- **Same-Subnet VM-to-fabric connectivity** — VMs are discoverable and directly reachable from bare-metal servers on the same Subnet at L2
- **Subnet and VM placement constraints** — VMs are supported only while their VirtualNetwork has one Subnet; a second Subnet is rejected while VMs exist, and VM placement is rejected whenever the VirtualNetwork has multiple Subnets [Clarify: R1.Q4, D4]
- **Fabric-only multi-Subnet validation** — where tested, cross-Subnet L3 connectivity uses bare-metal endpoints on a multi-Subnet VirtualNetwork with no VMs
- **Non-conflicting IP address assignment** — VMs receive IP addresses that do not conflict with fabric DHCP allocations [Clarify: R1.Q5]
- **Installation prerequisites documentation** — Cloud Infrastructure Admin must complete documented infrastructure prerequisites to enable physical fabric connectivity before creating the first VirtualNetwork [Clarify: R2.Q2, R2.Q3, D6] [User]
- **Diagnostic tooling documentation** — documented tools for Cloud Infrastructure Admins to verify network segment state and troubleshoot connectivity issues [Clarify: R3.Q2]
- **Gateway MAC coordination prerequisite** — Cloud Infrastructure Admin must ensure gateway MAC addresses match between overlay and fabric before enabling EVPN to prevent L3 traffic failures [Clarify: R1.Q5]
- **Single hosting cluster** (no multi-cluster VM placement)
- **Release 0.3**

## Out of Scope

The following are explicitly deferred to Phase 2 (OSAC-3667, release 0.4):

- **Multi-cluster hosting** — subnet provisioned on multiple clusters with VMs on different clusters sharing the same subnet via fabric
- **Inter-subnet L3 routing between VMs** on the same cluster (requires OVN Connectors for inter-CUDN routing)
- **Multi-NIC VMs with all NICs fabric-reachable** (future scope; current VMaaS accepts at most one tenant attachment; requires EVPN support for secondary UDN interface advertisement)
- **DPU-based bridging** — hardware offload of OVN-to-fabric bridging via SmartNICs

The following are out of scope for Phase 1:

- **IPv6 and dual-stack support** — not supported by the shared Unified Networking contract. [Clarify: R2.Q4]
- **Standardized route-target format** — deferred until fabric manager implements it [Clarify: R1.Q3, D3, D7] [User]
- **MetalLB IPAddressPool creation** — handled separately in OSAC-1436 (CaaS Networking) [Clarify: R3.Q3, D9]
- **Physical infrastructure automation** — manual prerequisites remain manual for Phase 1 [Clarify: R2.Q1, R2.Q3, D5, D6]
- **Automatic gateway MAC coordination** — Cloud Infrastructure Admin must manually coordinate gateway MAC addresses (moved to prerequisites above) [Clarify: R1.Q5]

## User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to register the EVPN k8s manager so that OSAC can provision fabric-bridged subnets for VMs. [Clarify: R1.Q1, R2.Q4, D1]

- As a Cloud Infrastructure Admin, I want documented installation prerequisites so that I can prepare the infrastructure before enabling EVPN for the first time. [Clarify: R2.Q2, R2.Q3, D6] [User]

- As a Cloud Infrastructure Admin, I want documented diagnostic tools so that I can verify network segment state and troubleshoot connectivity issues when VMs cannot reach the fabric. [Clarify: R3.Q2]

- As a Cloud Infrastructure Admin, I want to identify which VirtualNetworks are eligible for VM placement based on their Subnet count, so that I can guide tenants to keep VM networks single-Subnet or use multi-Subnet VirtualNetworks for fabric-only workloads.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want to create VirtualNetworks and Subnets with explicit same-VirtualNetwork NetworkACL associations using the existing OSAC API, without needing to configure fabric bridging details, so that VMs on a supported single-Subnet VirtualNetwork are automatically reachable from the physical fabric. [Clarify: R1.Q2, D2]

- As a Tenant Admin or Tenant User, I want VMs on a single-Subnet VirtualNetwork to be reachable from bare-metal servers on the same Subnet at L2, so that my workloads can span VM and physical hosts within that Subnet. [User]

- As a Tenant Admin or Tenant User, I want the system to reject adding a second Subnet while VMs exist and to reject VM placement when a VirtualNetwork has multiple Subnets, so that VM networks retain the supported topology while fabric-only networks can use multiple Subnets. [Clarify: R1.Q4, D4]

## Assumptions

- The Cloud Infrastructure Admin has completed the documented infrastructure prerequisites before creating the first VirtualNetwork. [Clarify: R2.Q3] [User]

- The fabric manager provides network segment identifiers when OSAC creates a VPC/VNet, enabling automatic provisioning by the k8s manager without manual configuration. [Clarify: R1.Q3, R2.Q5, D7]

- OCP workers have network connectivity to the fabric. [Clarify: R2.Q3]

- A NetworkClass exists with both fabric and k8s managers configured, enabling dual-dispatch provisioning.

- Each Subnet has an explicit association to an independent NetworkACL scoped to its VirtualNetwork. The configured fabric manager owns NetworkACL provisioning and enforcement, and the Subnet becomes READY only after its associated policy is active. This CUDN/K8s integration consumes the Subnet's network-segment data and does not create an ACL per Subnet or implement ACL behavior in the K8s manager.

- A VirtualNetwork with a single Subnet may host VMs. Once VMs exist, adding a second Subnet is rejected. If a second Subnet is added while no VMs exist, the VirtualNetwork becomes fabric-only and VM placement is rejected in all its Subnets.

- Fabric-level NATGateways (SNAT via softgate) apply to fabric-bridged VM egress traffic.

## Acceptance Criteria

- [ ] A NetworkClass with `fabric_manager: "primary"` and `k8s_manager: "cudn_evpn"` can be created and transitions to READY state
- [ ] Each Subnet has an explicit NetworkACL association to a READY ACL scoped to the same VirtualNetwork, and the Subnet becomes READY only after the associated ACL policy is active
- [ ] Creating a VirtualNetwork, a READY same-VirtualNetwork NetworkACL, and a single Subnet explicitly associated with that ACL provisions both fabric manager VNet and overlay network on OCP
- [ ] VMs deployed on the subnet receive IP addresses that do not conflict with fabric manager DHCP allocations
- [ ] VMs are discoverable and directly reachable from bare-metal servers on the same Subnet at L2
- [ ] Adding a second Subnet while VMs exist is rejected; after VMs are removed, a second Subnet may be added as fabric-only, and VM placement is rejected while the VirtualNetwork has multiple Subnets
- [ ] Any cross-Subnet L3 connectivity validation uses only fabric and bare-metal endpoints in a multi-Subnet VirtualNetwork with no VMs
- [ ] FRR diagnostic commands show correct VNI state on OCP workers

**Non-Functional:**
- [ ] Automated integration test in CI verifies end-to-end flow: subnet creation → dual-dispatch provisioning → VM placement → fabric reachability

## Dependencies

- **OSAC-1717 (K8s Manager — OVN-Kubernetes EVPN Spike):** Validates OVN EVPN technical approach. Status: Closed.

- **OSAC-1433 (Unified Networking Architecture):** Provides foundation for NetworkClass, dispatcher, k8s manager registration pattern. This design extends OSAC-1433 with the OVN EVPN k8s manager section. [Clarify: R3.Q4, D10]

- **OSAC-1440 (Dispatcher Core):** Provides dispatcher infrastructure for routing networking operations to fabric and k8s managers based on NetworkClass configuration.

- **Fabric manager:** Must support VirtualNetwork and Subnet provisioning with network segment identifiers, and must satisfy the shared NetworkACL provisioning and readiness contract. Physical infrastructure configuration is manual.

- **OVN-Kubernetes:** Must support overlay network provisioning with fabric bridging. Constraint: does not currently route between separate overlay networks on the same cluster (Connectors feature pending). [Clarify: R1.Q4]

- **FRR Operator (kubernetes-nmstate-operator):** Required for BGP EVPN route advertisement from OCP workers. Must be installed before EVPN configuration.

- **NMState Operator (openshift-nmstate):** Required for network interface configuration on OCP workers. Must be installed before EVPN configuration.

- **OSAC-3667 (Phase 2):** Blocked by this feature. Adds multi-cluster hosting, inter-subnet routing, and future multi-NIC support.

- **OSAC-1435 (VMaaS Networking API Integration):** Blocked by this feature. Requires k8s manager (CUDN LocalNet or OVN EVPN) to be available before end-to-end VM networking works.

## Known Limitations

- **Silent connectivity failure on network segment mismatch** — If network segment identifiers are misconfigured between the fabric and overlay, VMs may boot successfully and receive IP addresses but cannot reach the fabric. The system does not surface warnings when segment state is inconsistent. Cloud Infrastructure Admins must use documented diagnostic tools to verify segment state. [Clarify: R3.Q2]

---

## Provenance

Authored: revise @ prd 0.11.3 - cc0daa6, workspace HEAD @ 43141585d
Phases: revise, revise

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"cc0daa6","source_repo":"43141585d","source_repo_branch":"HEAD","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["revise","revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":true} -->
