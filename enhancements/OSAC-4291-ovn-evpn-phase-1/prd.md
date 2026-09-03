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

- **K8s manager registration** via ConfigMap (identifier: `cudn_evpn`, capabilities: `addressFamily:ipv4`) [Clarify: R2.Q4]
- **Automatic VNI propagation** from Netris VPC/VNet creation to CUDN configuration (route targets are calculated automatically from VNI) [Clarify: R1.Q3, R2.Q5, D7] [User]
- **Automatic overlay network provisioning** on hosting clusters (via ClusterUserDefinedNetwork with EVPN transport) when a VirtualNetwork/Subnet is created [Clarify: R2.Q1]
- **Automatic BGP EVPN route advertisement** for VMs, using VNI mappings from Netris [Clarify: R2.Q1, D5]
- **VM-to-fabric connectivity** — VMs are discoverable and directly reachable from bare-metal servers on the physical fabric
- **Layer 2 and Layer 3 VPC support** — VMs can be bridged to Netris VPCs with flexible subnet configuration: same subnet uses Layer 2 bridging for direct connectivity; different subnets within the same VPC use Layer 3 routing [User]
- **Single-subnet-per-VirtualNetwork constraint** enforced at Subnet API creation time (OVN Connectors limitation) [Clarify: R1.Q4, D4]
- **Non-conflicting IP address assignment** — VMs receive IP addresses that do not conflict with Netris DHCP allocations [Clarify: R1.Q5]
- **Installation prerequisites documentation** for Cloud Infrastructure Admin (underlay link, VTEP setup, BGP peering with VTEP subnets/prefixes advertisement) [Clarify: R2.Q2, R2.Q3, D6] [User]
- **Diagnostic tooling documentation** for Cloud Infrastructure Admin (FRR commands: `show evpn vni`, `show bgp l2vpn evpn`, `show bgp vni <VNI>`, `show bgp l2vpn evpn summary`) [Clarify: R3.Q2]
- **Single hosting cluster** (no multi-cluster VM placement)
- **Release 0.3**

## Out of Scope

The following are explicitly deferred to Phase 2 (OSAC-3667, release 0.4):

- **Multi-cluster hosting** — subnet provisioned on multiple clusters with VMs on different clusters sharing the same subnet via fabric
- **Inter-subnet L3 routing between VMs** on the same cluster (requires OVN Connectors for inter-CUDN routing)
- **Multi-NIC VMs with all NICs fabric-reachable** (requires EVPN support for secondary UDN interface advertisement)
- **DPU-based bridging** — hardware offload of OVN-to-fabric bridging via SmartNICs

The following are out of scope for Phase 1:

- **`0:VNI_ID` route-target standardization** — deferred until Netris implements it. Phase 1 uses `(leaf ASN % 65536):VNI` formula, with route targets calculated automatically from VNI (no manual configuration required). [Clarify: R1.Q3, D3, D7] [User]
- **MetalLB IPAddressPool creation** — handled separately in OSAC-1436 (CaaS Networking) [Clarify: R3.Q3, D9]
- **BGP underlay automation** — physical link configuration, Netris port setup, and BGP session creation are manual prerequisites configured by Cloud Infrastructure Admin [Clarify: R2.Q1, R2.Q3, D5, D6]
- **Dual gateway MAC coordination** — automatic matching of OCP CUDN gateway and Netris VNet gateway MAC addresses (known limitation requiring manual coordination) [Clarify: R1.Q5]

## User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to register the `cudn_evpn` k8s manager via a ConfigMap (with `addressFamily:ipv4` capability) so that OSAC can provision EVPN-bridged subnets for VMs. [Clarify: R1.Q1, R2.Q4, D1]

- As a Cloud Infrastructure Admin, I want documented installation prerequisites (underlay link setup, VTEP configuration, BGP peering with Netris including VTEP subnets/prefixes advertisement) so that I can prepare the infrastructure before enabling EVPN for the first time. [Clarify: R2.Q2, R2.Q3, D6] [User]

- As a Cloud Infrastructure Admin, I want FRR diagnostic commands documented (show evpn vni, show bgp l2vpn evpn, show bgp vni <VNI>, show bgp l2vpn evpn summary) so that I can verify VNI creation and troubleshoot VNI/route-target mismatches. [Clarify: R3.Q2]

- As a Cloud Infrastructure Admin, I want VMs to automatically advertise their routes to the fabric via BGP EVPN when a subnet is provisioned, using VNI mappings from Netris, so that VMs are reachable from the fabric without manual BGP configuration. [Clarify: R2.Q1, D5, D7] [User]

- As a Cloud Infrastructure Admin, I want to identify which VirtualNetworks have reached the single-subnet limit (via monitoring or status queries) so that I can plan for Phase 2 deployment or guide tenants to create additional VirtualNetworks.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want to create VirtualNetworks and Subnets using the existing OSAC API without needing to configure EVPN details (VNIs, BGP peering) so that VMs I provision are automatically bridged to the physical fabric. [Clarify: R1.Q2, D2]

- As a Tenant Admin or Tenant User, I want VMs I provision on an EVPN-bridged subnet to receive IP addresses via OVN DHCP and be reachable from bare-metal servers in the same Netris VPC so that my workloads can span VMs and physical hosts — either via Layer 2 connectivity when using the same subnet, or via Layer 3 routing when using different subnets within the same VPC. [User]

- As a Tenant Admin or Tenant User, I want the system to reject my second Subnet creation attempt under the same VirtualNetwork with a clear error message referencing the OVN Connectors limitation so that I understand the constraint and can structure my networks accordingly. [Clarify: R1.Q4, D4]

## Assumptions

- The Cloud Infrastructure Admin has completed the documented prerequisites (underlay link configuration, VTEP setup, BGP session with Netris including VTEP subnets/prefixes advertisement) before creating the first VirtualNetwork. [Clarify: R2.Q3] [User]

- The Netris fabric manager returns VNI IDs when OSAC creates a VPC/VNet, enabling automatic propagation to CUDN. Route targets are calculated automatically from VNI (no manual configuration required). [Clarify: R1.Q3, R2.Q5, D7]

- OCP workers have network connectivity to the Netris fabric switches via the configured underlay link. [Clarify: R2.Q3]

- The FRR operator and NMState operator are installed on the OCP cluster before EVPN configuration. [Clarify: R2.Q2]

- A NetworkClass exists with `fabric_manager: "netris"` and `k8s_manager: "cudn_evpn"`, enabling dual-dispatch provisioning where fabric and k8s manager jobs run in parallel for each subnet.

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

- **Netris Fabric Manager:** Must support:
  - VPC/VNet creation with VNI ID allocation and return via API
  - Underlay port configuration (via Netris API or UI)
  - BGP session configuration with OCP workers
  
  Route targets are calculated automatically using `(leaf ASN % 65536):VNI` formula — no API return or manual configuration needed.

- **OVN-Kubernetes:** FRR routing capability with EVPN support, RouteAdvertisements for CUDN with EVPN transport topology. Constraint: does not currently route between separate CUDNs on the same cluster (Connectors feature pending). [Clarify: R1.Q4]

- **OSAC-3667 (Phase 2):** Blocked by this feature. Adds multi-cluster hosting, inter-subnet routing, and multi-NIC support.

- **OSAC-1435 (VMaaS Networking API Integration):** Blocked by this feature. Requires k8s manager (CUDN LocalNet or OVN EVPN) to be available before end-to-end VM networking works.

---

## Provenance

Authored: commit @ prd 0.8.0 - 837cf0d, workspace prd/OSAC-4291 @ e18362f (20 behind origin/main)
Final: revise @ prd 0.8.0 - 837cf0d, workspace prd/OSAC-4291 @ e69542d (20 behind origin/main)

> Context changed between commit and revise.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.8.0","ai_workflows":"837cf0d","source_repo":"e69542d","source_repo_branch":"prd/OSAC-4291","commits_behind_main":20,"commits_ahead_main":3,"main_ref":"main","phases":["commit","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":true} -->
