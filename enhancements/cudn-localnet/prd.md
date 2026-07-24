# CUDN Localnet — K8s Manager for Fabric-Bridged VMs

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1830 |
| Date        | 2026-06-28 |

## Problem Statement

OSAC VMs run inside KubeVirt pods on OVN-Kubernetes. By default, VM IP addresses exist only within the OVN overlay and are not visible on the physical fabric. For VMs to participate in infrastructure-agnostic subnets alongside bare-metal servers and cluster nodes, the OVN overlay must be bridged to the physical fabric.

The Unified Networking Architecture (OSAC-1433) defines a `k8sManager` role in NetworkClass — a pluggable backend responsible for bridging the OVN overlay to the fabric. No k8sManager implementation exists yet. Without one, the networking architecture cannot provision fabric-connected VMs.

## User Stories

### Cloud Infrastructure Admin

* As a Cloud Infrastructure Admin, I want to register CUDN LocalNet as a k8s manager so that regions with KubeVirt can bridge VMs to the physical fabric via VLAN tagging.
* As a Cloud Infrastructure Admin, I want the k8s manager to automatically configure NMState bridge-mappings on hosting clusters so that I don't need to manually set up OVN-to-fabric connectivity.
* As a Cloud Infrastructure Admin, I want bridge connectivity validation after subnet creation so that networking issues are caught at provisioning time rather than at VM creation.
* As a Cloud Infrastructure Admin, I want the system to reject subnets using the 10.0.2.0/24 CIDR so that KubeVirt masquerade collisions are prevented.

### Tenant User

* As a Tenant User, I want VMs on a CUDN LocalNet subnet to be reachable from bare-metal servers on the same fabric segment with L2 adjacency.

## Goals and Non-Goals

### Goals

- Implement the first k8sManager backend using CUDN Localnet topology with 802.1Q VLAN tagging, the simplest approach requiring no control-plane integration on the OCP side.
- Validate bridge connectivity after subnet provisioning to catch networking issues before VM creation.
- Prevent the KubeVirt masquerade subnet collision (10.0.2.0/24) at provisioning time.
- Provide L2 adjacency for VMs on the same virtual network within a hosting cluster, matching bare-metal server behavior on the fabric.

### Non-Goals

- OVN EVPN, VRF-lite, or DPU-based bridging (future k8sManager implementations).
- Primary network CUDNs (Localnet is secondary only — VMs retain the pod network for Kubernetes health probes).
- NMState Operator installation or lifecycle management (prerequisite, not managed by OSAC).
- Automated cross-subnet L3 routing between virtual networks (requires manual routes on VMs when virtual networks share a VPC/VRF).
- Multi-cluster subnet sharing and cross-cluster IPAM (single hosting cluster per subnet in the initial implementation; multi-cluster IP partitioning via `excludeSubnets` is planned as a future extension).

## Requirements

### Functional Requirements

- **FR-1:** The k8s manager creates an NMState NNCP that adds a `localnet-physnet:br-ex` bridge-mapping on all worker nodes of the hosting cluster. [OSAC-1511]
- **FR-2:** The k8s manager creates a CUDN with Localnet topology, matching the fabric virtual network's VLAN ID and subnet CIDR. [OSAC-1511]
- **FR-3:** The k8s manager validates that the NNCP is applied and the CUDN reports `NetworkCreated: True` before reporting subnet readiness. [OSAC-1511]
- **FR-4:** The k8s manager rejects subnets whose CIDR overlaps with 10.0.2.0/24 (KubeVirt masquerade collision). [OSAC-1511]
- **FR-5:** VMs created on a CUDN Localnet subnet receive two interfaces: the pod network (masquerade) and the fabric network (localnet CUDN). [OSAC-1511]
- **FR-6:** The k8s manager cleans up CUDN and NNCP resources when a subnet is deleted. [OSAC-1511]
- **FR-7:** The k8s manager is registered via a ConfigMap referenced by the NetworkClass `k8sManager` field. [OSAC-1511]

### Non-Functional Requirements

- **NFR-1:** The k8s manager must work on OpenShift 4.19+ (CUDN Localnet GA). [OCP dependency]
- **NFR-2:** Bridge-mapping application (NNCP) must be additive — it must not modify or remove existing OVS bridge-mappings. [NMState constraint]
- **NFR-3:** The k8s manager must handle CUDN immutability — configuration changes require delete and recreate. [OVN-K8s constraint]

## Acceptance Criteria

- [ ] CUDN LocalNet Ansible role creates namespace + CUDN with correct VLAN ID
- [ ] NMState NNCP bridge-mapping configured per hosting cluster
- [ ] Bridge connectivity validated after NNCP and CUDN creation
- [ ] Subnet deletion cleans up CUDN and NNCP resources
- [ ] Manager ConfigMap registered and referenced by NetworkClass
- [ ] Masquerade subnet collision guard rejects 10.0.2.0/24 overlap
- [ ] L2 connectivity verified: same virtual network, same cluster (TTL=64)
- [ ] VRF isolation verified: different VPCs/VRFs have no connectivity

## Assumptions

- The fabric manager has already created the virtual network with the VLAN ID, switch port trunk membership, anycast gateway, and DHCP disabled before the k8s manager runs.
- NMState Operator is installed on all hosting clusters.
- OCP nodes' physical NICs are connected to leaf switch ports configured as trunks.
- A single physical NIC on br-ex carries both node management (untagged) and VM tenant (tagged) traffic.

## Dependencies

- **OSAC-1433 (Unified Networking Architecture):** The dispatcher that calls this k8s manager must exist first. This feature is blocked by the NetworkClass and k8sManager dispatch mechanism.
- **Fabric manager:** Must create virtual networks with VLAN IDs, switch port trunk membership, and anycast gateways before the k8s manager provisions the OCP side.
- **NMState Operator:** Must be installed on hosting clusters (prerequisite, not managed by OSAC).

## Risks

### CUDN immutability forces disruptive changes

CUDNs cannot be modified after creation. Any change to VLAN ID or subnet requires deleting VMs, deleting the CUDN, and recreating both.

- **Owner:** OSAC networking team
- **Mitigation:** Document the workflow; k8s manager handles teardown and recreation. Design the provisioning flow to get it right the first time.

### Same-node traffic bypasses fabric ACLs

VM-to-VM traffic on the same node stays within OVN and never hits the physical fabric, so fabric-level ACLs don't apply to same-node communication.

- **Owner:** OSAC networking team
- **Mitigation:** Document as a known limitation. OVN NetworkPolicy can supplement fabric ACLs for same-node traffic if needed.

### OCP upgrade connectivity loss (OCPBUGS-66994)

During cluster upgrades, VMs on localnet can lose connectivity temporarily.

- **Owner:** OCP networking team (upstream)
- **Mitigation:** Workaround: restart ovnkube-node pod or live-migrate affected VM. Fixed in future OCP versions.
