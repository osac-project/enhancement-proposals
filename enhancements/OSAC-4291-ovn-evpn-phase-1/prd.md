# K8s Manager — OVN EVPN Phase 1: Single-Cluster VM-to-Fabric Bridging

| Field       | Value   |
|-------------|---------|
| Author(s)   | Benny Kopilov |
| Jira        | https://redhat.atlassian.net/browse/OSAC-4291 |
| Date        | 2026-08-30 |

## Problem Statement

OSAC runs VMs on OpenShift using KubeVirt, which encapsulates each VM in a pod whose networking is managed by OVN-Kubernetes. By default, VM IP addresses exist only within the OVN overlay and are not visible on the physical fabric. This prevents VMs from being first-class fabric participants — they cannot share the same L2 subnet with bare-metal servers, cannot be reached directly from the fabric, and cannot leverage the fabric's multi-tenancy and routing capabilities.

Without a k8s manager that bridges VMs to the fabric, tenants cannot deploy workloads that span VMs and bare-metal hosts in the same subnet. The CUDN LocalNet approach (OSAC-1511) has been frozen in favor of OVN EVPN, which provides better scalability and multi-cluster support. [Clarify: R1.Q3]

The OVN EVPN spike (OSAC-1717) validated the technical approach: VMs can join the fabric via BGP EVPN route advertisements, enabling MAC/IP learning (Type-2 routes), VTEP discovery (Type-3 routes), and cross-subnet reachability (Type-5 routes). Phase 1 delivers single-cluster EVPN bridging with a constraint that OVN-Kubernetes does not currently route between separate CUDNs on the same cluster (the Connectors feature is pending). [Clarify: R1.Q4]

## In Scope

- **K8s manager registration** for EVPN fabric bridging (IPv4 address family only) [Clarify: R2.Q4]
- **Fabric-to-k8s manager data dependency** — subnet provisioning must ensure the fabric manager completes and provides network segment identifiers before the k8s manager begins, using a manager-agnostic interface [Clarify: R1.Q3, R2.Q5, D7] [User]
- **Automatic overlay network provisioning** on hosting clusters that bridges VMs to the physical fabric when a VirtualNetwork/Subnet is created [Clarify: R2.Q1]
- **VM-to-fabric connectivity** — VMs are discoverable and directly reachable from bare-metal servers on the physical fabric (both L2 same-subnet and L3 cross-subnet scenarios)
- **Single-subnet-per-VirtualNetwork constraint for this k8s manager** — when a VirtualNetwork uses a NetworkClass with this k8s manager, the system rejects additional subnet creation with a clear error [Clarify: R1.Q4, D4]
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
- **Multi-NIC VMs with all NICs fabric-reachable** (requires EVPN support for secondary UDN interface advertisement)
- **DPU-based bridging** — hardware offload of OVN-to-fabric bridging via SmartNICs

The following are out of scope for Phase 1:

- **IPv6 and dual-stack support** — Phase 1 supports IPv4 only. IPv6 route advertisement via EVPN is untested and deferred to Phase 2. [Clarify: R2.Q4]
- **Standardized route-target format** — deferred until fabric manager implements it [Clarify: R1.Q3, D3, D7] [User]
- **MetalLB IPAddressPool creation** — handled separately in OSAC-1436 (CaaS Networking) [Clarify: R3.Q3, D9]
- **Physical infrastructure automation** — manual prerequisites remain manual for Phase 1 [Clarify: R2.Q1, R2.Q3, D5, D6]
- **Automatic gateway MAC coordination** — Cloud Infrastructure Admin must manually coordinate gateway MAC addresses (moved to prerequisites above) [Clarify: R1.Q5]

## User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to register the EVPN k8s manager so that OSAC can provision fabric-bridged subnets for VMs. [Clarify: R1.Q1, R2.Q4, D1]

- As a Cloud Infrastructure Admin, I want documented installation prerequisites so that I can prepare the infrastructure before enabling EVPN for the first time. [Clarify: R2.Q2, R2.Q3, D6] [User]

- As a Cloud Infrastructure Admin, I want documented diagnostic tools so that I can verify network segment state and troubleshoot connectivity issues when VMs cannot reach the fabric. [Clarify: R3.Q2]

- As a Cloud Infrastructure Admin, I want to identify which VirtualNetworks have reached the single-subnet limit (via monitoring or status queries) so that I can plan for Phase 2 deployment or guide tenants to create additional VirtualNetworks.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want to create VirtualNetworks and Subnets using the existing OSAC API without needing to configure fabric bridging details, so that VMs I provision are automatically reachable from the physical fabric. [Clarify: R1.Q2, D2]

- As a Tenant Admin or Tenant User, I want VMs I provision on fabric-bridged subnets to be reachable from bare-metal servers, so that my workloads can span VMs and physical hosts. [User]

- As a Tenant Admin or Tenant User, I want the system to reject my second Subnet creation attempt under the same VirtualNetwork with a clear error message, so that I understand the constraint and can structure my networks accordingly. [Clarify: R1.Q4, D4]

## Assumptions

- The Cloud Infrastructure Admin has completed the documented infrastructure prerequisites before creating the first VirtualNetwork. [Clarify: R2.Q3] [User]

- The fabric manager provides network segment identifiers when OSAC creates a VPC/VNet, enabling automatic provisioning by the k8s manager without manual configuration. [Clarify: R1.Q3, R2.Q5, D7]

- OCP workers have network connectivity to the fabric. [Clarify: R2.Q3]

- A NetworkClass exists with both fabric and k8s managers configured, enabling dual-dispatch provisioning.

- Fabric-level SecurityGroups (ACL rules) apply to fabric-bridged VM traffic.

- Fabric-level NATGateways (SNAT via softgate) apply to fabric-bridged VM egress traffic.

## Acceptance Criteria

- [ ] A NetworkClass with `fabric_manager: "netris"` and `k8s_manager: "cudn_evpn"` can be created and transitions to READY state
- [ ] Creating a VirtualNetwork + Subnet with this NetworkClass provisions both Netris VNet (with L2/L3 VNI) and overlay network on OCP
- [ ] VMs deployed on the subnet receive IP addresses that do not conflict with Netris DHCP allocations
- [ ] VMs are discoverable and directly reachable from bare-metal servers on the physical fabric (both L2 same-subnet and L3 different-subnet scenarios)
- [ ] FRR diagnostic commands show correct VNI state on OCP workers
- [ ] Creating a second Subnet under the same VirtualNetwork returns a validation error message referencing OVN Connectors limitation

**Non-Functional:**
- [ ] Automated integration test in CI verifies end-to-end flow: subnet creation → dual-dispatch provisioning → VM placement → fabric reachability

## Dependencies

- **OSAC-1717 (K8s Manager — OVN-Kubernetes EVPN Spike):** Validates OVN EVPN technical approach. Status: Closed.

- **OSAC-1433 (Unified Networking Architecture):** Provides foundation for NetworkClass, dispatcher, k8s manager registration pattern. This design extends OSAC-1433 with the OVN EVPN k8s manager section. [Clarify: R3.Q4, D10]

- **OSAC-1440 (Dispatcher Core):** Provides dispatcher infrastructure for routing networking operations to fabric and k8s managers based on NetworkClass configuration.

- **Fabric Manager (Netris):** Must support VPC/VNet provisioning with network segment identifier allocation and API return. Physical infrastructure configuration (underlay ports, BGP sessions) is manual.

- **OVN-Kubernetes:** Must support overlay network provisioning with fabric bridging. Constraint: does not currently route between separate overlay networks on the same cluster (Connectors feature pending). [Clarify: R1.Q4]

- **FRR Operator (kubernetes-nmstate-operator):** Required for BGP EVPN route advertisement from OCP workers. Must be installed before EVPN configuration.

- **NMState Operator (openshift-nmstate):** Required for network interface configuration on OCP workers. Must be installed before EVPN configuration.

- **OSAC-3667 (Phase 2):** Blocked by this feature. Adds multi-cluster hosting, inter-subnet routing, and multi-NIC support.

- **OSAC-1435 (VMaaS Networking API Integration):** Blocked by this feature. Requires k8s manager (CUDN LocalNet or OVN EVPN) to be available before end-to-end VM networking works.

## Known Limitations

- **Silent connectivity failure on network segment mismatch** — If network segment identifiers are misconfigured between the fabric and overlay, VMs may boot successfully and receive IP addresses but cannot reach the fabric. The system does not surface warnings when segment state is inconsistent. Cloud Infrastructure Admins must use documented diagnostic tools to verify segment state. [Clarify: R3.Q2]

---

## Provenance

Authored: commit @ prd 0.8.0 - 837cf0d, workspace prd/OSAC-4291 @ e18362f (20 behind origin/main)
Final: revise @ prd 0.8.0 - 837cf0d, workspace prd/OSAC-4291 @ e69542d (20 behind origin/main)

> Context changed between commit and revise.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.8.0","ai_workflows":"837cf0d","source_repo":"e69542d","source_repo_branch":"prd/OSAC-4291","commits_behind_main":20,"commits_ahead_main":3,"main_ref":"main","phases":["commit","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":true} -->
