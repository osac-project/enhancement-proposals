# CUDN EVPN K8s Manager: Single-Cluster VM-to-Fabric Bridging

| Field       | Value   |
|-------------|---------|
| Author(s)   | Benny Kopilov |
| Jira        | https://redhat.atlassian.net/browse/OSAC-4291 |
| Date        | 2026-08-30 |

This PRD implements the K8s Manager role for the fabric-backed EVPN profile in the [Network Manager Integration Contract](/enhancements/OSAC-5928-pluggable-network-manager-integration-contract-networking/prd.md). Its registration declares the `evpn-vxlan` integration capability; it does not declare an operation subset. In this profile, the fixed dispatcher assigns Subnet create/delete to the K8s Manager. The K8s-only fallback profile requires a different K8s Manager that declares `primarySubnet` and implements that profile's full fallback operation set.

This PRD inherits the [Unified Networking deployment support
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

The OVN EVPN spike (OSAC-1717) validated the technical approach: VMs can join an EVPN fabric via BGP route advertisements, enabling L2 same-Subnet and L3 cross-Subnet reachability. Phase 1 delivers single-cluster bridging. Separate CUDNs do not route directly through OVN; cross-Subnet traffic uses the selected Fabric Manager path. [Clarify: R1.Q4]

## In Scope

- **K8s manager registration** for EVPN fabric bridging (IPv4 address family only) [Clarify: R2.Q4]
- **Fabric-to-K8s manager data dependency** — Subnet provisioning waits for the Fabric Manager and passes its versioned `evpn-vxlan` `osac_result.data.fabricHandoff` to the K8s Manager as `context.fabricHandoff`, exactly as defined by the Network Manager Integration Contract [Clarify: R1.Q3, R2.Q5, D7] [User]
- **Automatic overlay network provisioning** on hosting clusters that bridges VMs to the physical fabric when a VirtualNetwork/Subnet is created [Clarify: R2.Q1]
- **VM-to-fabric connectivity** — VMs are discoverable and directly reachable from bare-metal servers on the physical fabric (both L2 same-subnet and L3 cross-subnet scenarios)
- **Multiple Subnets per VirtualNetwork** — every Subnet receives its own EVPN CUDN and NAD; VMaaS selects the NAD for the VM's requested Subnet. Subnet creation order does not change behavior [Contract]
- **Non-conflicting IP address assignment** — the CUDN excludes every reservedIPv4CIDRs range returned by the selected Fabric Manager in the shared handoff [Contract]
- **Installation prerequisites documentation** — Cloud Infrastructure Admin must complete documented infrastructure prerequisites to enable physical fabric connectivity before creating the first VirtualNetwork [Clarify: R2.Q2, R2.Q3, D6] [User]
- **Diagnostic tooling documentation** — documented tools for Cloud Infrastructure Admins to verify network segment state and troubleshoot connectivity issues [Clarify: R3.Q2]
- **Gateway MAC coordination prerequisite** — Cloud Infrastructure Admin must ensure gateway MAC addresses match between overlay and fabric before enabling EVPN to prevent L3 traffic failures [Clarify: R1.Q5]
- **Single hosting cluster** (no multi-cluster VM placement)
- **Release 0.3**

## Out of Scope

The following are explicitly deferred to Phase 2 (OSAC-3667, release 0.4):

- **Multi-cluster hosting** — subnet provisioned on multiple clusters with VMs on different clusters sharing the same subnet via fabric
- **Direct OVN routing between separate CUDNs without traversing the Fabric Manager** (requires OVN Connectors; Subnet-to-Subnet reachability through the configured fabric remains in scope)
- **Multi-NIC VMs with all NICs fabric-reachable** (future scope; current VMaaS accepts at most one tenant attachment; requires EVPN support for secondary UDN interface advertisement)
- **DPU-based bridging** — hardware offload of OVN-to-fabric bridging via SmartNICs

The following are out of scope for Phase 1:

- **IPv6 and dual-stack support** — not supported by the shared Unified Networking contract. [Clarify: R2.Q4]
- **Manager-specific EVPN route-target negotiation** — outside this K8s Manager contract; interoperability is a prerequisite of the selected evpn-vxlan Fabric Manager and K8s Manager pair. The shared handoff contains only the fields defined by contract v1.
- **MetalLB IPAddressPool creation** — handled separately in OSAC-1436 (CaaS Networking) [Clarify: R3.Q3, D9]
- **Physical infrastructure automation** — manual prerequisites remain manual for Phase 1 [Clarify: R2.Q1, R2.Q3, D5, D6]
- **Automatic gateway MAC coordination** — Cloud Infrastructure Admin must manually coordinate gateway MAC addresses (moved to prerequisites above) [Clarify: R1.Q5]

## User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to register the EVPN k8s manager so that OSAC can provision fabric-bridged subnets for VMs. [Clarify: R1.Q1, R2.Q4, D1]

- As a Cloud Infrastructure Admin, I want documented installation prerequisites so that I can prepare the infrastructure before enabling EVPN for the first time. [Clarify: R2.Q2, R2.Q3, D6] [User]

- As a Cloud Infrastructure Admin, I want documented diagnostic tools so that I can verify network segment state and troubleshoot connectivity issues when VMs cannot reach the fabric. [Clarify: R3.Q2]

- As a Cloud Infrastructure Admin, I want each registered EVPN-compatible Fabric/K8s Manager pair to exchange the standard Subnet handoff so that I can select implementations from different sources without supplier-specific OSAC changes.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want to create VirtualNetworks and Subnets using the existing OSAC API without needing to configure fabric bridging details, so that VMs I provision are automatically reachable from the physical fabric. [Clarify: R1.Q2, D2]

- As a Tenant Admin or Tenant User, I want VMs I provision on fabric-bridged subnets to be reachable from bare-metal servers, so that my workloads can span VMs and physical hosts. [User]

- As a Tenant Admin or Tenant User, I want VMs to attach to any Subnet in my VirtualNetwork and reach fabric-connected workloads there, regardless of Subnet creation order. [Contract]

## Assumptions

- The Cloud Infrastructure Admin has completed the documented infrastructure prerequisites before creating the first VirtualNetwork. [Clarify: R2.Q3] [User]

- The selected Fabric Manager and `cudn_evpn` both declare `evpn-vxlan`; the Fabric Manager returns the exact handoff schema defined by the contract. [Contract]

- OCP workers have network connectivity to the fabric. [Clarify: R2.Q3]

- The NetworkClass selects an `evpn-vxlan`-capable Fabric Manager and this K8s Manager; the K8s-only profile is not supported by this implementation.

- The selected Fabric Manager enforces the shared SecurityGroup contract for
  bridged ComputeInstance traffic, including same-Subnet, routed, and external
  paths. cudn_evpn is responsible only for its assigned subnet.create and
  subnet.delete operations; SecurityGroup operations remain assigned to Fabric.

- Fabric-level NATGateways apply through the selected Fabric Manager’s outbound path to fabric-bridged VM egress traffic.

## Acceptance Criteria

- [ ] A NetworkClass selecting any contract-v1 Fabric Manager and cudn_evpn, with both registrations declaring evpn-vxlan, can be created and transitions to READY state
- [ ] Creating any number of Subnets with this NetworkClass provisions each Fabric segment and its matching secondary EVPN CUDN/NAD, using the shared result handoff
- [ ] VMs deployed on each Subnet receive IP addresses outside every reservedIPv4CIDRs range returned by the selected Fabric Manager
- [ ] VMs are discoverable and directly reachable from bare-metal servers on the physical fabric (both L2 same-subnet and L3 different-subnet scenarios)
- [ ] FRR diagnostic commands show correct VNI state on OCP workers
- [ ] VMs attached to different Subnets can reach one another through the Fabric Manager's routed path; the test does not depend on Subnet creation order

**Non-Functional:**
- [ ] Automated integration test in CI verifies end-to-end flow: subnet creation → dual-dispatch provisioning → VM placement → fabric reachability

## Dependencies

- **OSAC-1717 (K8s Manager — OVN-Kubernetes EVPN Spike):** Validates OVN EVPN technical approach. Status: Closed.

- **OSAC-1433 (Unified Networking Architecture):** Provides the shared resource model, profiles, and dispatcher. Exact manager registration, task, result, and conformance requirements are defined by [OSAC-5928 Network Manager Integration Contract](/enhancements/OSAC-5928-pluggable-network-manager-integration-contract-networking/design.md).

- **OSAC-1440 (Dispatcher Core):** Provides dispatcher infrastructure for routing networking operations to fabric and k8s managers based on NetworkClass configuration.

- **Fabric Manager:** The selected contract-v1 Fabric Manager must declare evpn-vxlan and return the contract-defined fabricHandoff for each Subnet. Physical infrastructure configuration is manual.

- **OVN-Kubernetes:** Must support overlay network provisioning with fabric bridging. Constraint: does not currently route between separate overlay networks on the same cluster (Connectors feature pending). [Clarify: R1.Q4]

- **FRR Operator (kubernetes-nmstate-operator):** Required for BGP EVPN route advertisement from OCP workers. Must be installed before EVPN configuration.

- **NMState Operator (openshift-nmstate):** Required for network interface configuration on OCP workers. Must be installed before EVPN configuration.

- **OSAC-3667 (Phase 2):** Blocked by this feature. Adds multi-cluster hosting, inter-subnet routing, and future multi-NIC support.

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
