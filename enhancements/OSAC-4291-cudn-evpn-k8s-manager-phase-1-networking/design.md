---
title: cudn-evpn-k8s-manager-phase-1-networking
authors:
  - Benny Kopilov
creation-date: 2026-09-03
last-updated: 2026-11-12
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

# CUDN EVPN K8s Manager Phase 1 Networking: Single-Cluster VM-to-Fabric Bridging

## Summary

This design extends OSAC-1433's NetworkClass two-manager architecture with a new k8s manager (`cudn_evpn`) that provisions OVN-Kubernetes ClusterUserDefinedNetwork (CUDN) with EVPN transport, enabling KubeVirt VMs to join the physical fabric via BGP EVPN route advertisement. The design covers sequential provisioning (fabric → k8s manager data flow), the owner-Subnet CUDN model, namespace and SecurityGroup policy ownership, lifecycle behavior, and integration test patterns. FRRConfiguration for BGP underlay peering is an installation prerequisite (not created by k8s manager); OVN-Kubernetes auto-updates it when CUDN appears. See [PRD](prd.md) for detailed requirements.

The design is normative for the owner-Subnet model in [contract §4.7–§4.10](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#47-ordering-concurrency-retries-and-ownership): every Subnet with a Kubernetes Manager runs Kubernetes `create_subnet`; the first Subnet whose task claims the VirtualNetwork's hub network owns it, and otherwise-valid sibling Subnets are accepted and become READY. A VM attachment on a non-owner Subnet fails at apply; the tenant sees the Subnet eligibility fields and the fixed message for ComputeInstance reason `SubnetDoesNotSupportVMs`. The [contract](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md) defines the target behavior; the [role README](https://github.com/osac-project/osac/blob/main/osac-aap/collections/ansible_collections/osac/templates/roles/cudn_evpn/README.md) describes the implementation and its remaining gaps. Superseded sketches are isolated in [Historical sketches (non-normative)](#historical-sketches-non-normative).

The data handoff from the Fabric Manager to `cudn_evpn` (the L3 and L2 VNIs, the address layout, the VM gateway, and the route targets) is the one [contract §4.8–§4.10](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#49-network-types-and-the-network-segment) defines; this design restates it where it uses it.

This manager inherits the [Unified Networking deployment support
boundary](/enhancements/OSAC-1433-unified-networking/design.md#deployment-support-boundary):
Phase 1 supports connected deployments only and does not add air-gapped or
disconnected networking support.
This manager also inherits the [Unified Networking hub support
boundary](/enhancements/OSAC-1433-unified-networking/design.md#networking-hub-support-boundary):
OSAC networking supports exactly one provider-owned hub per deployment.
Multi-hub networking placement, cross-hub resource coordination, and
cross-hub network connectivity are unsupported. This boundary applies only to
the networking area and does not define hub behavior for other OSAC areas.
Multiple hosting/workload clusters remain supported where a networking feature
explicitly specifies them.

## Related Designs

This design builds on and interacts with several networking designs:

- **OSAC-1435 VMaaS Networking** — VMaaS creates the NetworkAttachment, then creates the VM in the namespace returned by Kubernetes `apply_network_attachment` (`vm_attachment.namespace`). That namespace belongs to the VirtualNetwork (`osac-vn-<VirtualNetwork API ID>`), not to an individual Subnet. VMaaS neither derives a namespace from the Subnet name nor applies a subnet-count gate; a non-owner Subnet attachment fails at the Kubernetes apply as final.
- **OSAC-1436 CaaS Networking** — CaaS worker BareMetalInstances belong to the owning Cluster's tenant and reference that Cluster's Subnet and SecurityGroups. Physical worker attachments use the Fabric Manager path and do not need a VM namespace or CUDN; the VirtualNetwork's namespace, baseline deny, and SecurityGroup policies still exist for VM workloads.
- **OSAC-1437 BMaaS Networking** — Bare-metal servers provisioned via `BareMetalNetworkAttachment` are L2/L3 peers of EVPN-bridged VMs. This design validates same-subnet (L2) and cross-subnet (L3 via fabric ipVRF) connectivity in test cases.
- **OSAC-1433 Default Networking** — Tenant onboarding uses the deployment's single NetworkClass, created from `global.networking.networkClass`, `global.networking.fabricManager`, and `global.networking.k8sManager`. VMaaS requires a Kubernetes Manager, so a deployment with VMaaS must not default to no Kubernetes Manager. When the deployment selects `cudn_evpn`, the installation prerequisites are required and the default Subnet is the owner of the CUDN because the default Subnet must be READY before another Subnet of that VirtualNetwork can be created.
- **OSAC-2135 CaaS BM Worker Provisioning** — Worker BareMetalInstances use the owning Cluster's tenant and reference the Cluster's tenant Subnet and SecurityGroups. If the Subnet uses `cudn_evpn`, the worker uses the Fabric physical-attachment path; it does not join the VM CUDN or use the VM namespace. Worker lifecycle remains owned by OSAC-2135.
- **OSAC-1382 Multi-Fabric East-West** — Phase 1 east-west isolation domains will need to work across EVPN-bridged and non-EVPN subnets. Inter-domain routing with EVPN transport is TBD (out of scope for Phase 1).

## Motivation

OSAC runs VMs on OpenShift using KubeVirt. VM IP addresses exist only within the OVN overlay network and are not visible on the physical fabric. This prevents VMs from sharing L2 subnets with bare-metal servers or communicating across L3 subnets via shared ipVRF, blocking workloads that span VMs and bare-metal infrastructure.

The CUDN LocalNet approach (OSAC-1511) was frozen in favor of OVN EVPN, which provides better scalability and multi-cluster support (validated by OSAC-1717 spike). This design delivers single-cluster EVPN bridging as Phase 1, with a constraint that OVN-Kubernetes cannot currently route between separate CUDNs on the same cluster (Connectors feature pending).

**Implementation Context:**
OSAC's NetworkClass dispatcher supports dual-manager provisioning (fabric + k8s). This design defines the `cudn_evpn` manager and its fabric-to-k8s data dependency: the fabric manager allocates the VNIs, and the k8s manager consumes them to configure the CUDN. The Fabric target must complete and its output must be recorded before the Kubernetes target runs.

### Goals

- Reuse NetworkClass dispatcher pattern and two-manager architecture from OSAC-1433
- Sequential provisioning pattern reusable for future fabric-to-k8s dependencies
- **Owner-Subnet admission for one CUDN per VirtualNetwork:**
  - Every Subnet with `cudn_evpn` runs the Fabric and Kubernetes create tasks; sibling Subnets are otherwise valid and are not rejected
  - The first Subnet whose Kubernetes `create_subnet` claims the VirtualNetwork's hub network owns the CUDN; later Subnets succeed without changing it
  - VMs attach only to the owner Subnet; a non-owner VM attachment fails as final. Tenants see the Subnet eligibility fields and ComputeInstance reason `SubnetDoesNotSupportVMs` with fixed guidance to choose a supported Subnet
  - No fulfillment-service subnet-count gate, VM-count check, or VMaaS subnet-count gate is added
- VirtualNetwork-scoped namespace and baseline policy, plus SecurityGroup policy objects bound per VM
- K8s manager playbook creates CUDN as Kubernetes-native resource (no external API calls)
- FRRConfiguration for BGP underlay peering is installation prerequisite (auto-updated by OVN-Kubernetes, not by k8s manager)
- Installation prerequisites documented for Cloud Infrastructure Admin

### Non-Goals

- Multi-cluster VM placement (deferred to OSAC-3667 Phase 2)
- Inter-subnet L3 routing between VMs on same cluster (requires OVN Connectors)
- Multiple fabric-reachable VM networks per VirtualNetwork, or multi-NIC VMs with a NIC per Subnet (deferred to Phase 2 when OVN-K supports secondary CUDNs)
- IPv6 or dual-stack support (Phase 1 is IPv4-only)
- Automatic gateway MAC coordination (manual prerequisite) (physical hosts on an EVPN Subnet only; open, contract §4.9)
- Automatic VTEP provisioning (manual prerequisite)

## Proposal

**Central Design Statement:**

Phase 1 extends an existing Netris VPC and its VNets into OpenShift. **A VirtualNetwork has one hub CUDN, owned by the first Subnet whose Kubernetes create claims it.** Every Subnet with `cudn_evpn` is provisioned through both managers, and sibling Subnets are accepted. The owner Subnet keeps the CUDN and supports VMs; a VM attachment on a sibling Subnet fails at apply; the tenant sees its eligibility fields and `SubnetDoesNotSupportVMs` with fixed guidance to choose a supported Subnet. Bare-metal attachments on that sibling continue to work. Secondary CUDNs and multi-NIC VMs remain deferred.

This design introduces a new k8s manager (`cudn_evpn`) registered via osac-installer ConfigMap, used when a NetworkClass declares `k8s_manager: "cudn_evpn"`.

**Resource Mapping:**

| OSAC Resource | Netris Resource | OVN-K Resource | VM Support |
|---------------|-----------------|----------------|------------|
| VirtualNetwork | Netris VPC (L3 ipVRF) | — | — |
| Owner Subnet (first Kubernetes create to claim) | Netris VNet (L2 macVRF) | CUDN (primary) | ✅ VMs allowed |
| Sibling Subnet | Netris VNet (L2 macVRF) | — (owner's CUDN persists) | ❌ VM attachment fails as final; bare metal works |

- **One CUDN per VirtualNetwork** (Phase 1 limitation - OVN-K lacks secondary CUDN support)
- **Multiple VNets per VPC** (Netris fabric capability - all share same IP-VRF)
- **CUDN created on Subnet provisioning** (not on VM creation)
- **CUDN persists when sibling Subnets are added**; only the owner Subnet's Kubernetes delete removes it

**Provisioning Trigger:** The CUDN is created by the first Subnet Kubernetes `create_subnet` that claims it. Ownership is recorded on the CUDN (`osac.openshift.io/owner-subnet`). No task takes over a live owner's CUDN. A create retries while the previous network is being deleted; after it is gone, the next `create_subnet` that claims a new CUDN becomes its owner, including a rerun for an existing sibling. Successful sibling tasks are not automatically rerun when the owner is deleted. The recorded address layout never changes.

**Subnet provisioning sequence:**

0. **Fabric manager** (Netris) runs when the parent VirtualNetwork is created (`create_virtual_network`): creates the Netris VPC (IP-VRF) and returns its L3 VNI as `osac_result.l3_vni`. OSAC records it in the VirtualNetwork CR's `status.l3Vni` ([contract §4.9](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#49-network-types-and-the-network-segment)).
1. **Fabric manager** (Netris) runs when Subnet is created (`create_subnet`):
   - Uses the VPC of the parent VirtualNetwork, whose L3 VNI arrives in the stored parent snapshot as `virtual_network.status.l3Vni`
   - Creates Netris VNet for this Subnet (allocates L2 VNI)
   - Returns `osac_result.network_segment: {type: evpn, l2_vni}` (no `l3_vni`)
2. **Subnet controller** checks the segment and the VNI's uniqueness, records it in `Subnet.status.networkSegment` (`{type, l2Vni}`), and passes it to the Kubernetes tasks as the launch key `network_segment`
3. **K8s manager** (cudn_evpn) runs for every Subnet:
   - If this Subnet claims the VirtualNetwork's hub network, it creates the CUDN:
     - `spec.network.evpn.macVRF = {vni: l2_vni, routeTarget: "0:<l2_vni>"}` (from `network_segment`)
     - `spec.network.evpn.ipVRF = {vni: l3_vni, routeTarget: "0:<l3_vni>"}` (from `virtual_network.status.l3Vni`)
     - `spec.network.layer2.defaultGatewayIPs = [ipam.gateway_ipv4]`: OVN-Kubernetes serves the VM gateway and routes into the IP-VRF (symmetric IRB)
     - `spec.network.layer2.infrastructureSubnets = [<gateway_ipv4>/32, <network + 2>/32]` (the gateway and OVN-Kubernetes' management port) and `reservedSubnets` = the fewest CIDRs covering the Subnet outside `ipam.overlay_ipv4_cidrs`, so VMs get addresses only from the overlay range
     - `spec.network.layer2.mtu = 1500`
     - OVN-Kubernetes auto-updates FRRConfiguration when the CUDN appears
   - If another Subnet owns the network, Kubernetes `create_subnet` succeeds without changing it; the Subnet is READY

**Important:**
- VirtualNetwork creation creates the Netris VPC (and returns its L3 VNI) but no CUDN
- The owner Subnet triggers VNet + CUDN; sibling Subnets trigger VNet only and leave the CUDN to its owner
- **The CUDN persists when sibling Subnets are added**; VM attachments are supported only on the owner Subnet
- The VirtualNetwork namespace and baseline deny exist once Kubernetes `create_virtual_network` succeeds and are shared by all VMs of the VirtualNetwork

Key resources:
- **VirtualNetwork** (fulfillment-service + osac-operator CRD): Fabric `create_virtual_network` creates the Netris VPC; its L3 VNI is recorded in `status.l3Vni`
- **NetworkClass** (fulfillment-service): extended with `k8s_manager` field (already exists)
- **Subnet** (fulfillment-service + osac-operator CRD): triggers fabric (VNet) and Kubernetes (CUDN claim) provisioning; its L2 VNI is recorded in `status.networkSegment`
- **ClusterUserDefinedNetwork** (OVN-Kubernetes CRD): k8s manager creates with EVPN transport, macVRF/ipVRF VNI and explicit route targets `0:<VNI>`
- **VirtualNetwork namespace** (Kubernetes): `osac-vn-<VirtualNetwork API ID>`, owned by the VirtualNetwork; every VM and every SecurityGroup policy of the VirtualNetwork lives there
- **FRRConfiguration** (FRR operator CRD): installation prerequisite (not created by k8s manager), auto-updated by OVN-Kubernetes when CUDN appears

### Workflow Description

**Actor:** Cloud Infrastructure Admin (prerequisite setup) and Tenant Admin (runtime usage)

**Starting State:**
- OCP cluster installed with OVN-Kubernetes, FRR operator, NMState operator
- VTEP CR exists (defines VTEP IPs for each worker node)
- BGP underlay configured (workers peer with fabric switches)
- NetworkClass exists with `fabric_manager: "netris"`, `k8s_manager: "cudn_evpn"`

**Runtime Flow:**

```mermaid
sequenceDiagram
    participant Tenant
    participant API as fulfillment-service
    participant Controller as Subnet Controller
    participant AAP as AAP Fabric Job
    participant K8s as AAP K8s Job
    participant OVN as OVN-Kubernetes
    participant FRR as FRR Operator

    Tenant->>API: Create Subnet (IPv4 CIDR)
    API->>API: Validate ordinary Subnet fields and readiness gates
    Note over API: No subnet-count or VM-count gate
    API-->>Tenant: 201 Created

    Controller->>Controller: Dispatch to fabric + k8s managers
    Note over Controller: Sequential: fabric → k8s

    Controller->>AAP: Create fabric Job (netris role)
    AAP->>AAP: Use the VirtualNetwork's Netris VPC (L3 VNI)<br/>Create Netris VNet (L2 VNI)
    Note over AAP: VPC created by create_virtual_network,<br/>L3 VNI in virtual_network.status.l3Vni
    AAP-->>Controller: Job Complete (osac_result network_segment {type, l2_vni})

    Controller->>Controller: Check segment and VNI uniqueness,<br/>record status.networkSegment
    Controller->>K8s: Create k8s Job (cudn_evpn role)<br/>osac_job_vars: network_segment, virtual_network.status.l3Vni, ipam

    alt This Subnet claims the VirtualNetwork's hub network
        K8s->>OVN: Create CUDN (EVPN transport, VNI)
        OVN->>FRR: Auto-update FRRConfiguration (advertiseVNIs)
        OVN-->>K8s: CUDN conditions true
        FRR-->>K8s: Routes advertised
    else Another Subnet owns the hub network
        K8s->>K8s: Succeed without changing the CUDN
    end
    K8s-->>Controller: Job Complete

    Controller-->>Tenant: Subnet Ready=True
```

**Error Paths:**

- **Sibling Subnet:** Accepted and becomes READY; its Kubernetes `create_subnet` succeeds without changing the owner's CUDN. The Fabric VNet and physical attachments work. A VM attachment on it fails as final with a VM eligibility diagnostic identifying a supported Subnet when known.
- **Subnet deletion with a workload reference:** Fulfillment-service deletion guards reject the delete with `FAILED_PRECONDITION`, with the count and the first blocking workload ID. Workload deletion belongs to VMaaS/BMaaS/CaaS; networking never deletes a VM, BareMetalInstance, or Cluster. After the workload and its NetworkAttachment are gone, Subnet deletion proceeds.
- **Fabric job retryable failure:** The Subnet stays `Ready=False`, reason `Progressing`, with the manager message and next retry time; the Kubernetes job does not start until Fabric `create_subnet` is `Succeeded` and `status.networkSegment` is recorded.
- **Fabric job final failure:** The Subnet stays `Ready=False`, reason `Failed`; the tenant deletes the Subnet. No retry occurs without a new input.
- **Missing or malformed `network_segment`, or a VNI a live VirtualNetwork or Subnet holds:** OSAC rejects the result and marks Subnet as Failed ("VNI already in use" for a held VNI); a VNI held only by resources being deleted is retried with backoff ([contract §4.9](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#49-network-types-and-the-network-segment))
- **CUDN creation retryable failure:** The Kubernetes entry is `Retrying`; the Subnet stays `Ready=False`, reason `Progressing`, and OSAC retries with backoff. A final failure (`osac_error.retryable: false`, no `osac_error`, or a rejected result) sets `Ready=False`, reason `Failed`.

### API Extensions

**New:**
- osac-installer ConfigMap `osac-network-k8s-manager-cudn-evpn` (declares k8s manager capabilities)
- osac-aap fabric manager template role `netris` (creates Netris VPC/VNet, returns VNI)
- osac-aap k8s manager template role `cudn_evpn` (VirtualNetwork namespace, baseline deny, owner CUDN, SecurityGroup policies, and VM bindings)

**Modified:**
- osac-operator Subnet controller: runs Fabric `create_subnet` first and Kubernetes `create_subnet` after the Fabric result and `status.networkSegment` are recorded, for every Subnet with a Kubernetes Manager. Ownership is decided by the Kubernetes task, not by the controller.

**External CRDs Used (not created by OSAC):**
- `ClusterUserDefinedNetwork` (k8s.ovn.org/v1, OVN-Kubernetes) — created by k8s manager
- `FRRConfiguration` (frrk8s.metallb.io/v1beta1, FRR operator) — installation prerequisite, auto-updated by OVN-Kubernetes when CUDN appears
- `VTEP` (k8s.ovn.org/v1, OVN-Kubernetes) — prerequisite, not created by k8s manager
- `Namespace` and `NetworkPolicy` (core/v1 and networking.k8s.io/v1, Kubernetes) — the VirtualNetwork namespace, its baseline deny, and SecurityGroup policy objects

**No changes** to existing fulfillment-service proto schema. NetworkClass.k8s_manager field already exists.

**Topology admission and ownership:**

There is no skip annotation, subnet-count gate, or VM-count gate. The fulfillment service validates only the ordinary Subnet fields and the shared readiness gates. Every Subnet with `cudn_evpn` receives both manager tasks.

```yaml
# Owner Subnet - its Kubernetes create claims the VirtualNetwork's CUDN
apiVersion: osac.openshift.io/v1
kind: Subnet
metadata:
  name: vm-subnet
spec:
  virtualNetwork: vpc-1  # NetworkClass has k8s_manager: cudn_evpn
  ipv4CIDR: 10.0.1.0/24

---
# Sibling Subnet - accepted and READY; it does not take over the CUDN
apiVersion: osac.openshift.io/v1
kind: Subnet
metadata:
  name: baremetal-subnet
spec:
  virtualNetwork: vpc-1  # Same VPC
  ipv4CIDR: 10.0.2.0/24
# Result: vm-subnet keeps the CUDN and supports VMs. baremetal-subnet gets a
# Netris VNet and no CUDN; its VM attachment fails at apply, while bare-metal
# attachments work.
```

**Provisioning behavior:**
- **Owner Subnet:** provisions the Netris VNet and the VirtualNetwork's CUDN; VM attachments are allowed.
- **Sibling Subnet:** provisions the Netris VNet; Kubernetes `create_subnet` succeeds without changing the owner's CUDN; bare-metal attachments work and VM attachments fail as final.
- Netris creates the VNet in the VPC of the parent VirtualNetwork.
- The VirtualNetwork's namespace, baseline deny, and SecurityGroup policies are not recreated or owned by a Subnet.

**Deletion behavior:**
- Fulfillment-service deletion guards reject a Subnet delete while any workload's stored network attachment references it. Networking does not delete workloads.
- After dependent NetworkAttachments are gone, Kubernetes `delete_subnet` runs before Fabric `delete_subnet`.
- The **owner** Subnet removes the CUDN only. The VirtualNetwork namespace and baseline policy remain until Kubernetes `delete_virtual_network`.
- A **sibling** Subnet's Kubernetes `delete_subnet` changes no CUDN; Fabric `delete_subnet` removes its VNet.
- VirtualNetwork deletion is rejected while any child Subnet, SecurityGroup, NATGateway, or FabricDomain exists; after its children are gone, Kubernetes `delete_virtual_network` removes the namespace and baseline, then Fabric deletion removes the VPC.


## UX Alignment

*Skip this section — no `osac-ux` temp-api file exists for NetworkClass or Subnet (backend-only feature).*

### Implementation Details/Notes/Constraints

#### fulfillment-service: Subnet Validation

**No `cudn_evpn`-specific creation gate.**

The fulfillment service does not count Subnets, count VMs, inspect Kubernetes, or resolve the hub-network owner. A Subnet create is validated like any other Subnet ([Unified — Subnet](/enhancements/OSAC-1433-unified-networking/design.md#subnet)):

- the parent VirtualNetwork exists and is READY;
- in a tenant's default VirtualNetwork, the default Subnet is READY before another Subnet may be created, so the default Subnet becomes the `cudn_evpn` owner ([Unified — Creation readiness gates](/enhancements/OSAC-1433-unified-networking/design.md#creation-readiness-gates));
- the CIDR, address plan, and ordinary field checks pass.

Every Subnet whose NetworkClass has `cudn_evpn` is stored and provisioned by both managers. Otherwise-valid sibling Subnets are accepted and become READY; only Kubernetes `create_subnet` knows whether a Subnet may serve VMs. A non-owner Subnet's VM attachments fail at apply with `retryable: false` ([contract §4.7, Implementation limits](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#47-ordering-concurrency-retries-and-ownership)).

**Deletion guard, not workload deletion.** The fulfillment service rejects a Subnet delete with `FAILED_PRECONDITION` while any workload's stored network attachment references the Subnet, naming the first blocking workload ID ([Unified — Deletion dependency guards](/enhancements/OSAC-1433-unified-networking/design.md#deletion-dependency-guards)). Networking never deletes a ComputeInstance, BareMetalInstance, or Cluster; the owning workload service does. This guard is the only Subnet-level workload constraint this feature adds, and it applies to every Subnet, owner or sibling.

#### VMaaS: VM Placement Validation

VMaaS does not validate the Subnet count or the CUDN owner. It creates the NetworkAttachment first, then creates the VM in the namespace Kubernetes `apply_network_attachment` returns ([OSAC-1435 — Create](/enhancements/OSAC-1435-vmaas-networking/design.md#create)):

1. The ComputeInstance controller creates `NetworkAttachment computeinstance-<API ID>` with the selected Subnet and SecurityGroups.
2. The networking controller runs Kubernetes `apply_network_attachment`. On the owner Subnet it binds the VM to the SecurityGroup policies and returns `vm_attachment: {namespace: osac-vn-<VirtualNetwork API ID>}`.
3. VMaaS creates the VM in that namespace. The namespace belongs to the VirtualNetwork, not to the Subnet; VMaaS never derives it from a Subnet name.
4. A non-owner Subnet's apply fails with `retryable: false`. Its diagnostic uses VM eligibility terms: `Subnet <X> does not support VMs (VM supported: false): Only one Subnet in this VirtualNetwork supports VMs at a time. Create the VM on a Subnet that supports VMs, such as Subnet <Y>.` Here X is the selected Subnet and Y is the current owner in the same tenant and VirtualNetwork, identified from the current CUDN; Y is not necessarily the first Subnet created. Omit the example when a current supported Subnet cannot be identified. Once the Kubernetes apply has failed finally and the selected Subnet records `computeInstanceSupported: false`, VMaaS sets `NetworkReady=False`, reason `SubnetDoesNotSupportVMs`, and phase `Failed`; no VM is created. Feedback exposes that reason with the fixed public message `The selected Subnet does not support VMs. Create the VM on a Subnet that supports VMs.` in the existing ComputeInstance network condition, so API, CLI and UI show the same guidance. The detailed diagnostic stays in hub `status.jobs`. True or unknown eligibility keeps `NetworkAttachmentFailed`; retryable failures stay progressing. This classification runs after failure, never as a create/apply gate, and adds no manager result field ([VMaaS — Network status](/enhancements/OSAC-1435-vmaas-networking/design.md#network-status-and-address-discovery)). The tenant recreates the VM on a supported Subnet; no automatic retry or attachment update is introduced. VMaaS does not pre-check ownership, because only the Kubernetes Manager knows the owner ([contract §4.7, Implementation limits](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#47-ordering-concurrency-retries-and-ownership)).

| Subnet | Kubernetes `create_subnet` | VM attachment |
|---|---|---|
| Owner (first Subnet whose Kubernetes create claims the hub network) | Creates the CUDN | Succeeds; the VM runs in `osac-vn-<VN ID>` |
| Sibling under the same VirtualNetwork | Succeeds without changing the CUDN | Fails as final with the VM eligibility diagnostic above |
| Subnet of another VirtualNetwork with its own owner Subnet | Creates that VirtualNetwork's CUDN | Succeeds; the VM runs in that VirtualNetwork's namespace |

`cudn_evpn` reports compute eligibility from `create_subnet` (`compute_instance_supported`, `compute_instance_unsupported_reason`, the contract's optional result fields), and OSAC records it in `Subnet.status.computeInstanceSupported` and `computeInstanceUnsupportedReason` so the API and CLI can show it. The existing output-only API field mapping, unknown API presence, and compatible task-result defaults are defined in [Unified — Compute eligibility](/enhancements/OSAC-1433-unified-networking/design.md#compute-eligibility). It is informational: VMaaS does not gate VM creation on it.

#### osac-operator: Sequential Provisioning

The Subnet controller plans one target per manager in the Subnet's `status.networkManagers` and runs the contract's jobs in order ([contract §4.7](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#47-ordering-concurrency-retries-and-ownership)). It does not count Subnets, read the CUDN, or decide ownership.

**Create order:**

1. Run Fabric `create_subnet` with the Subnet snapshot and the VirtualNetwork snapshot carrying `status.l3Vni`.
2. When the Fabric entry in `status.jobs` is `Succeeded`, validate `osac_result.network_segment: {type: evpn, l2_vni}` and record it in `status.networkSegment` in the same status update. Only then run Kubernetes `create_subnet` with `network_segment`, `virtual_network`, and `ipam`.
3. The Kubernetes task decides ownership: it claims the VirtualNetwork's hub network when none exists, leaves another live Subnet's network unchanged, retries while the previous network is being deleted, a hub prerequisite is missing, or the network is not yet ready, and fails as final on a foreign CUDN with the same name or on immutable network drift in a CUDN it owns. A retry after deletion can claim a new CUDN for this Subnet. The Subnet is Ready when every recorded manager's create entry is `Succeeded`.
4. `cudn_evpn` publishes `compute_instance_supported` and `compute_instance_unsupported_reason` from its `create_subnet`; OSAC records them in the Subnet status.

**Delete order:** reverse. Kubernetes `delete_subnet` runs only after every overlay NetworkAttachment on the Subnet is gone, then Fabric `delete_subnet`. The owner's Kubernetes task removes the CUDN; a sibling's changes nothing; neither removes the VirtualNetwork namespace. OSAC keeps the Subnet finalizer until each manager whose create started has a successful delete ([contract §4.7, Finalizers and readiness](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#47-ordering-concurrency-retries-and-ownership)).

**Status and retries.** `status.jobs` is the source of truth: one entry `{task, manager, attempt, state, jobID, message}` per task and manager, with states `Running`, `Retrying`, `Succeeded`, `Failed`, and `Cancelled` ([contract §4.7, Job tracking](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#47-ordering-concurrency-retries-and-ownership)). There is no phase or job-history field.

- **Retryable failure:** the entry is `Retrying`; the Subnet is `Ready=False`, reason `Progressing` (API state PENDING), with the manager message and next retry time. There is no attempt limit; OSAC retries with backoff until a job succeeds or the Subnet is deleted.
- **Final failure:** the entry is `Failed`; the Subnet is `Ready=False`, reason `Failed` (API state FAILED). No retry starts without a new input; the tenant deletes and recreates the Subnet.
- **Ready:** `Ready=True`, reason `Succeeded`, after every recorded manager's create succeeded (API state READY).
- A controller restart re-reads `status.jobs`, resumes from the last succeeded entry, and never launches the Kubernetes task before the Fabric result is recorded. The task input is stored in `status.taskInput`; the `virtual_network` snapshot carries `status.l3Vni`, and the launch key carries `network_segment`.

The data path is the contract's: Fabric `create_virtual_network` publishes `l3_vni` and `create_subnet` publishes `network_segment`; OSAC validates both, checks VNI uniqueness, and records them. The controller writes no CUDN-specific condition, metric, or event; the hub CUDN's own conditions are read only by the role.

[PRD: In Scope — fabric-to-k8s data dependency] [Contract §4.7]

#### Fabric Manager handoff

`cudn_evpn` consumes only the [manager contract](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#49-network-types-and-the-network-segment):

| Input | Source and use |
|---|---|
| `virtual_network.status.l3Vni` | Fabric `create_virtual_network` returns `l3_vni`; OSAC validates and stores it. The CUDN uses it for `ipVRF.vni` and route target `0:<l3_vni>`. |
| `network_segment: {type: evpn, l2_vni}` | Fabric `create_subnet` returns the L2 segment; OSAC validates and stores it before launching the Kubernetes task. The CUDN uses it for `macVRF.vni` and route target `0:<l2_vni>`. |
| `ipam` | OSAC's recorded Subnet layout, sent to both managers. `cudn_evpn` derives `reservedSubnets`, `infrastructureSubnets`, and `defaultGatewayIPs` from it; the Fabric returns no address ranges. |
| `ipam.gateway_ipv4` | OVN-Kubernetes serves it to VMs. Netris also serves this address to physical hosts; its gateway MAC behavior is documented in OSAC-2434. |

The [Netris Fabric Manager design, OSAC-2434](/enhancements/OSAC-2434-netris-fabric-manager-networking/design.md) owns its task files, naming, registration, physical attachment behavior, SecurityGroup no-ops, ExternalIP/NAT, FabricDomain, lab evidence, and implementation gaps. In particular, see [Gateway and DHCP](/enhancements/OSAC-2434-netris-fabric-manager-networking/design.md#gateway-and-dhcp) for physical DHCP and [Cluster ingress addresses](/enhancements/OSAC-2434-netris-fabric-manager-networking/design.md#cluster-ingress-addresses) for fulfillment-owned LB VIP allocation and guest MetalLB announcements. None of those provider internals is an additional input to `cudn_evpn`.

#### osac-aap: cudn_evpn K8s Manager Role

**Role Structure:**

```
collections/ansible_collections/osac/templates/roles/cudn_evpn/
├── meta/
│   └── osac.yaml                    # Capability declaration
├── tasks/
│   ├── create_virtual_network.yaml  # Namespace
│   ├── delete_virtual_network.yaml
│   ├── create_subnet.yaml           # CUDN of the owner Subnet; no FRR object
│   ├── delete_subnet.yaml           # Delete the CUDN this Subnet owns
│   ├── create_security_group.yaml   # NetworkPolicy
│   ├── delete_security_group.yaml
│   ├── apply_network_attachment.yaml  # Bind the VM to its SecurityGroups
│   └── delete_network_attachment.yaml
```

**meta/osac.yaml:**

```yaml
---
name: cudn-evpn
title: CUDN EVPN Kubernetes Manager
description: >
  OSAC's Kubernetes Manager for network type evpn: one namespace and one
  EVPN ClusterUserDefinedNetwork per VirtualNetwork, and one NetworkPolicy
  per SecurityGroup, on the hub where VMs run.
template_type: network
k8s_manager: cudn_evpn
capabilities:
  supports_ipv4: true
  supports_ipv6: false
  supports_dual_stack: false
```

The role's `meta/osac.yaml` describes the role to the execution environment;
it is not the manager registration. The Kubernetes registration ConfigMap below carries
no `capabilities` key.

**`create_subnet` ownership and readiness:**

The role reads the CUDN before deciding what to write. The executable task and its filters are maintained with the [role README](https://github.com/osac-project/osac/blob/main/osac-aap/collections/ansible_collections/osac/templates/roles/cudn_evpn/README.md#tasks), rather than copied as a second implementation here.

| Observed CUDN | Action |
|---|---|
| Absent | Check the VTEP, then claim a new CUDN using server-side apply with field manager `cudn-evpn-<subnet-id>` and `force_conflicts: false`. If another Subnet wins between the read and apply, the conflict is retryable and the next attempt reassesses ownership. |
| Owned by this Subnet | Verify the immutable network and address layout, restore owned metadata and the namespace selector, and wait for readiness. Network drift is final; do not patch a network that workloads may use. |
| Owned by another Subnet | Read the owner Subnet CR directly from the hub API server as described below. If it exists and is not deleting, succeed without changing the CUDN and publish `compute_instance_supported: false` with tenant-readable reason `Only one Subnet in this VirtualNetwork supports VMs at a time.` If the owner is deleting, retry; if absent, fail finally as an orphan. |
| Being deleted, with its owner still present | Fail with `retryable: true`; after it is gone the next create can claim a new CUDN. This includes an existing sibling whose create task is rerun, not just a newly created Subnet. A missing owner takes the orphan failure path below. |
| Foreign ownership | Fail with `retryable: false`; never adopt or overwrite it. |

An owned CUDN carries `osac.openshift.io/owner-kind: Subnet`, `osac.openshift.io/owner-id: <Subnet API ID>`, `osac.openshift.io/k8s-manager: cudn_evpn`, tenant and VirtualNetwork labels, and the `owner-reference` and `owner-subnet` annotations. An owner succeeds and publishes `compute_instance_supported: true` with an empty reason only after `TransportAccepted`, `NetworkCreated`, and `NetworkAllocationSucceeded` are all True. Missing or unaccepted VTEP and CUDN readiness timeouts are retryable.

When the CUDN belongs to another Subnet, the role must read that owner's CR from the hub API server, not an informer cache, using `osac.openshift.io/subnet-uuid=<owner-subnet>` in the OSAC namespace. Verify a unique match in the same tenant and VirtualNetwork. A deletion timestamp makes the create retryable even while the CUDN has none; after deletion finishes, the next successful create can claim the network. If the owner CR is gone but the CUDN still exists, fail finally with an orphaned-hub-network diagnostic, change nothing, and adopt nothing, even if the CUDN is terminating. API read errors retry; an ambiguous or mismatched owner is a final ownership conflict. The role reads Subnet CRs only for this ownership check and never mutates them.

An already successful sibling is not automatically promoted. Its overlay range remains unused until a subsequent successful claim, and its original `ipam` layout is retained throughout. These are the required design and contract behaviors; the component tests must exercise the owner-CR deletion window as well as CUDN termination.

**Rationale:**
- **Namespace and CUDN name = `osac-vn-<VirtualNetwork API ID>`**: one namespace per VirtualNetwork (from Kubernetes `create_virtual_network`) and one CUDN per VirtualNetwork, owned by one Subnet (contract §4.10, `cudn_evpn` limit)
- CUDN namespaceSelector matches by `osac.openshift.io/virtualnetwork-id` and `osac.openshift.io/tenant`
- Namespace label `k8s.ovn.org/primary-user-defined-network` required for UDN as primary network (set at namespace creation)
- VTEP reference = `tenant-vtep` (cluster singleton, installation prerequisite)
- VNI values: L2 (macVRF) from the launch key `network_segment.l2_vni`, L3 (ipVRF) from the stored parent snapshot `virtual_network.status.l3Vni` (contract §4.9)
- Route targets explicit: `0:<l2_vni>` on macVRF, `0:<l3_vni>` on ipVRF, the same values the Fabric imports and exports; they do not depend on the node AS, so every 24-bit VNI is usable
- Wait for the CUDN's `TransportAccepted`, `NetworkCreated` and `NetworkAllocationSucceeded` conditions before completing (prevents race with VM provisioning)
- **Addressing from `ipam`** (contract §4.8): `infrastructureSubnets` = `[<gateway_ipv4>/32, <network + 2>/32]` and `reservedSubnets` = the rest of the Subnet outside the overlay range, so OVN IPAM never hands out a fabric, LB VIP, gateway or management-port address; a layout needing more than 25 `reservedSubnets` entries fails as final
- `defaultGatewayIPs: [gateway_ipv4]` — OVN-Kubernetes serves the VM gateway and routes into the IP-VRF; MTU 1500
- [Demo: Phase 5.2 CUDN structure] [Research: §Existing Solutions — OVN-K CUDN]

**Baseline deny and SecurityGroup binding:**

- Kubernetes `create_virtual_network` creates the namespace `osac-vn-<VirtualNetwork API ID>` and `osac-baseline-deny`. The baseline selects every pod, sets both `Ingress` and `Egress`, and allows only DHCP (egress UDP 67, ingress UDP 68); OVN-Kubernetes still allows ARP/ND implicitly.
- Kubernetes `create_security_group` creates `osac-sg-<SecurityGroup ID>` in that namespace. Its rules are the group's rules (`tcp`/`udp` with port/endPort, `all` without ports, the CIDR as `ipBlock`); its podSelector matches no pod until an attachment binds one, so the create needs no Subnet, CUDN, or VM.
- Kubernetes `apply_network_attachment` adds `osac.openshift.io/compute-instance-id: <VM ID>` to each selected group's podSelector and returns `vm_attachment: {namespace: osac-vn-<VN ID>}`. `delete_network_attachment` removes the VM ID. A rule update replaces the rules and keeps the members; a bind or unbind changes the members and keeps the rules.
- A VM with no SecurityGroup gets only the baseline deny. On a sibling Subnet, `apply_network_attachment` fails as final with the VM eligibility diagnostic; its delete succeeds because nothing was bound.

**`delete_subnet` ownership:**

The [role](https://github.com/osac-project/osac/blob/main/osac-aap/collections/ansible_collections/osac/templates/roles/cudn_evpn/README.md#tasks) reads the CUDN and removes it only if its tenant, VirtualNetwork, manager, and owner labels identify this Subnet. Deletion uses the observed UID as a precondition and waits until the CUDN is gone. An absent CUDN or a sibling's CUDN needs no change. This task never deletes the VirtualNetwork namespace, its baseline deny, or its SecurityGroup policies.

**Deletion order and ownership:**

1. The fulfillment service rejects the Subnet delete with `FAILED_PRECONDITION` while any workload's stored network attachment references the Subnet, naming the first blocking workload ID ([Unified — Deletion dependency guards](/enhancements/OSAC-1433-unified-networking/design.md#deletion-dependency-guards)). The workload service deletes the workload and its NetworkAttachment; networking does not.
2. OSAC then runs Kubernetes `delete_subnet` (only after every overlay attachment is gone), followed by Fabric `delete_subnet` ([contract §4.7](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#47-ordering-concurrency-retries-and-ownership)).
3. The owner Subnet's Kubernetes task deletes the CUDN and waits until it is gone, so OVN releases the VNIs before Fabric `delete_subnet` frees the L2 VNI. A sibling's Kubernetes task changes nothing; Fabric removes its VNet.
4. The VirtualNetwork namespace, the `osac-baseline-deny` policy, and the `osac-sg-<SecurityGroup ID>` policies remain. They are owned by the VirtualNetwork and its SecurityGroups, not by a Subnet. Kubernetes `delete_virtual_network` removes the namespace and, with it, the baseline deny, only after the VirtualNetwork's children are gone.
5. Networking never deletes VMs, BareMetalInstances, or Clusters. A rejected Subnet delete leaves every workload untouched.

The Fabric's backend cleanup and child-object checks are defined in [OSAC-2434](/enhancements/OSAC-2434-netris-fabric-manager-networking/design.md). They are a safety net after OSAC's dependency guards, not a workload-deletion mechanism.

**VirtualNetwork finalizer:** the VirtualNetwork keeps `osac.openshift.io/virtualnetwork-finalizer` while any child Subnet, SecurityGroup, NATGateway, or FabricDomain exists. After its children are gone, Kubernetes `delete_virtual_network` removes the namespace and baseline, and Fabric deletion removes the VPC ([Unified — Deletion dependency guards](/enhancements/OSAC-1433-unified-networking/design.md#deletion-dependency-guards)).

**FRRConfiguration Handling:**

FRRConfiguration for underlay BGP peering is created during installation (manual prerequisite). The k8s manager does **not** create or modify FRRConfiguration. OVN-Kubernetes auto-updates FRR config when CUDN with `evpn: "true"` label is created.

Per demo Phase 5.3:
> "On CUDN creation, BGP FRR configuration is updated... advertise-all-vni"

The RouteAdvertisements CR (installation prerequisite) defines `frrConfigurationSelector: {matchLabels: {evpn: "true"}}`, which tells OVN-K to update any FRRConfiguration with that label when a CUDN with matching label appears.

**Assumption:** Installation-time FRRConfiguration exists in `openshift-frr-k8s` namespace with label `evpn: "true"`. K8s manager only creates CUDN; FRR integration is declarative via label matching.

[Demo: Phase 2.6 FRRConfiguration, Phase 2.5 RouteAdvertisements] [Research: §FRR Operator — advertiseVNIs]

**DHCP Coexistence:**

OVN-Kubernetes answers a VM's DHCP request inside the CUDN logical switch, before the request leaves the node. VMs receive their addresses from OVN-Kubernetes and never reach Netris DHCP, as specified by [OSAC-2434 — Gateway and DHCP](/enhancements/OSAC-2434-netris-fabric-manager-networking/design.md#gateway-and-dhcp).

- `cudn_evpn` sets `reservedSubnets` to the Subnet outside `ipam.overlay_ipv4_cidrs`; only `infrastructureSubnets` holds `gateway_ipv4/32` and `<network + 2>/32`. VM addresses therefore exclude the physical pool, LB VIP pool, gateway, and management port.
- OVN-Kubernetes supplies `gateway_ipv4` as the VM router and cluster DNS as its resolver. The DNS address need not be in the tenant overlay pool.
- Netris DHCP serves physical interfaces from the recorded `physical_ipv4_cidrs`. Its creation, repair, empty-pool behavior, and per-MAC reservation limitation belong to OSAC-2434. The diagnostic overrides `none` and `physical_first` are lab-only; they are not supported deployment modes.

TC-R6-01 checks deployed VM and bare-metal leases. TC-R6-02 and TC-R6-03 exercise the Fabric role against its simulated controller; these do not establish live DHCP packet delivery.

**Gateway Ownership (Critical Architecture Decision):**

OVN-Kubernetes serves the VM gateway ([contract §4.9](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#49-network-types-and-the-network-segment)):

**What happens:**
1. `cudn_evpn` sets `layer2.defaultGatewayIPs: [ipam.gateway_ipv4]` (the Subnet's network address + 1, recorded in `Subnet.status.ipam`)
2. OVN DHCP gives VMs that address as router
3. OVN-Kubernetes serves the gateway address and routes the VM's L3 traffic into the IP-VRF (symmetric integrated routing and bridging, ipVRF VNI = `l3_vni`)
4. Traffic to other Subnets and outside the VirtualNetwork is encapsulated (VXLAN) with the L3 VNI toward the fabric, which routes the IP-VRF
5. Same-subnet traffic to bare-metal hosts is bridged over the macVRF (L2 VNI)

**Phase 1 behavior:**
- `defaultGatewayIPs: [gateway_ipv4]` and `infrastructureSubnets` include the gateway, so OVN IPAM never hands it to a VM
- The fabric (Netris) carries the macVRF and ipVRF and routes the ipVRF. It may also serve `gateway_ipv4` on its devices ([contract §4.9](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#49-network-types-and-the-network-segment)). The Netris manager does: its V-Net serves `gateway_ipv4` on its anycast gateway, as the working lab spike does, and OVN-Kubernetes serves the same address. OVN-Kubernetes assigns VM addresses; Netris DHCP serves only `physical_ipv4_cidrs`, enabled at creation and on rerun and used for physical attachments.
- Same-Subnet L2 traffic (VM to VM, VM to bare metal on one V-Net) is verified in the lab, as are NAT egress and ExternalIP ingress through the gateway; inter-Subnet routed traffic is not yet verified. Routed traffic can see two gateway MACs (the follow-up below addresses it), because the two sides do not share the gateway MAC. Follow-up: set the Netris V-Net `customAnycastMac` to OVN-Kubernetes' fixed gateway MAC, `0a:58` followed by the four bytes of `gateway_ipv4` (research evidence; not yet tested in the lab)
- Route targets `0:<l2_vni>` (macVRF) and `0:<l3_vni>` (ipVRF) on both sides
- How a physical host on the same Subnet reaches `gateway_ipv4` without a second gateway on the segment is open in the contract and belongs to the BMaaS design

**History:** an earlier demo omitted `defaultGatewayIPs` and let a Netris SVI own `.1` (no OVN logical router port). That gateway model is superseded by the contract.

Netris-specific lab observations and the remaining physical gateway and routing limitations are maintained in [OSAC-2434](/enhancements/OSAC-2434-netris-fabric-manager-networking/design.md#gateway-and-dhcp).

#### osac-installer: K8s Manager Registration

**New ConfigMap:**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: osac-network-k8s-manager-cudn-evpn
  namespace: osac
  labels:
    osac.openshift.io/network-k8s-manager: "true"  # Matches OSAC-1433 label path
immutable: true
data:
  name: cudn_evpn  # Field name 'name' per OSAC-1433 schema (not 'manager')
  ansible_role: osac.templates.cudn_evpn
  network_type: evpn
  # No `capabilities` key: IPv4 is mandatory and is not a capability, and
  # cudn_evpn does not declare security_group_icmp (a NetworkPolicy cannot
  # match ICMP).
```

**Capability Fields:**
- The registration declares no capability. In particular it does not declare
  `security_group_icmp`, so a NetworkClass with `cudn_evpn` always has
  `status.security_group_icmp` false and the API rejects ICMP rules.
- IPv6 and dual-stack are not supported; IPv4 is not a capability token.
- The owner-Subnet VM limit is a `cudn_evpn` implementation limit enforced by
  Kubernetes `create_subnet` and `apply_network_attachment`; it is not a
  manager capability token and not a fulfillment-service gate.

**RBAC:**

Networking jobs run as OSAC's job service account, which installation binds to `cluster-admin`, per [contract §4.12](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#412-security-rbac-and-tenancy). This design adds no separate service account or ClusterRole. The role needs:

- Namespaces: get, create, patch, delete.
- ClusterUserDefinedNetworks (`k8s.ovn.org`): get, create, patch, delete.
- NetworkPolicies (`networking.k8s.io`): get, list, create, patch, delete.
- VTEPs (`k8s.ovn.org`): get.
- Subnet CRs (`osac.openshift.io`): get and list, read-only; the API-ID label selector uses a list request to the API server.

The role does not modify FRRConfiguration. Registration follows the contract's manager ConfigMap format; the installer template is `osac-installer/charts/osac/templates/networking/cudn-evpn-registration.yaml`.

### Security Considerations

**Tenant Isolation:**

All OSAC resources include standard tenant isolation metadata:
- `osac.openshift.io/tenant` annotation on CUDN and namespace
- `osac.openshift.io/owner-reference` annotation linking CUDN to the Subnet that owns it
- OPA policies enforce read/write isolation at fulfillment-service API layer

**New Isolation Boundary:**

CUDN namespace selector uses `matchLabels: {osac.openshift.io/virtualnetwork-id: "<VN ID>", osac.openshift.io/tenant: "<tenant>"}`. Each VirtualNetwork has one VirtualNetwork-owned namespace, `osac-vn-<VirtualNetwork API ID>`, and one owner CUDN. VMs live in that namespace and on the owner Subnet's network; sibling Subnets have no CUDN and accept no VMs. VMs in different VirtualNetworks cannot communicate at L2 or L3 (separate macVRF + ipVRF).

**Node reachability:**

OVN-Kubernetes treats every EVPN network as advertised and SNATs traffic toward the cluster node IPs to the network's management-port masquerade IP, so it reaches the host through the management port, inside the network's VRF. A VM whose SecurityGroup allows all egress can therefore ping the node that hosts it. Measured on the single-node lab: TCP to listening ports got a reset from the node kernel, consistent with `net.ipv4.tcp_l3mdev_accept=0`, and traffic beyond the node stopped at the VRF's `unreachable` default. A listening UDP service got port-unreachable, consistent with `net.ipv4.udp_l3mdev_accept=0`. Isolation of node services rests on those kernel defaults. Another node's address has not been measured, and no E2E checks this.

**BGP Security:**

Underlay BGP session (OCP ↔ fabric switch) uses MD5 authentication (configured during installation, not managed by OSAC). FRRConfiguration credentials stored in Kubernetes Secret.

**No New Attack Surface:**

- CUDN and FRRConfiguration are cluster-scoped CRDs, not tenant-facing APIs
- Tenants interact only via fulfillment-service Subnet API (existing auth/authz)
- AAP jobs run with service account (RBAC-controlled), not tenant credentials

**Input Validation:**

VNI values from fabric manager are integers from 1 to 16777215, validated by OSAC before it records them (contract §4.9) and again by the CUDN CRD schema. Route targets are the strings `0:<VNI>` that `cudn_evpn` builds. Subnet CIDR validated by fulfillment-service (existing validation).

### Failure Handling and Recovery

Status is the contract's: the `Ready` condition and `status.jobs`. Retryable and final failures are distinct ([contract §4.6](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#46-task-result-and-errors) and [§4.7](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#47-ordering-concurrency-retries-and-ownership)).

**Fabric job failure — retryable:**

- **What happens:** Netris API error, backend timeout, quota exceeded, or a conflict on a shared backend object
- **Recovery:** the Fabric `create_subnet` entry is `Retrying`; OSAC retries with backoff (two minutes, doubling to thirty). The Kubernetes task does not start until the Fabric entry is `Succeeded` and `status.networkSegment` is recorded
- **User observes:** API state PENDING with its fixed progress message; administrator-visible hub status has `Ready=False`/`Progressing`, the manager diagnostic, and next retry time

**Fabric job failure — final:**

- **What happens:** missing or malformed `osac_result`, a VNI held by a live resource, or `osac_error.retryable: false`
- **Recovery:** OSAC records `Failed`; `status.networkSegment` stays unset and no Kubernetes job starts. No retry occurs without a new input
- **User observes:** API state FAILED with its fixed failure message; administrator-visible hub status has `Ready=False`/`Failed` and the manager or result-rejection diagnostic. The tenant deletes and recreates the Subnet

**Kubernetes job failure:**

- **Retryable:** VTEP missing or not Accepted, the namespace or CUDN not ready, the owner Subnet being deleted (even before CUDN termination), a previous CUDN still being deleted, an owner-CR read error, a Kubernetes API error, or a concurrent guarded-patch conflict. The entry is `Retrying`; `Ready=False`, reason `Progressing`. After deletion finishes, a retried create may claim a new CUDN
- **Final:** a CUDN with this name but foreign tenant or VirtualNetwork labels, an absent or conflicting owner Subnet while a CUDN remains, drift in an owned CUDN, more than 25 `reservedSubnets`, or a rejected result. The entry is `Failed`; `Ready=False`, reason `Failed`. The message names the limit or object; delete and recreate through the dependency-ordered flow

**CUDN VNI Collision:**

- **What happens:** The Fabric returns a VNI that another VirtualNetwork's `status.l3Vni` or another Subnet's `status.networkSegment.l2Vni` holds
- **Recovery:** OSAC accepts L3 and L2 VNIs one at a time under one operator-wide lock, reading VirtualNetwork and Subnet CRs from the API server ([contract §4.9](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#49-network-types-and-the-network-segment)). A VNI held by a live resource fails the create as final; a VNI held only by resources being deleted puts the create in `Retrying` with backoff, and the idempotent rerun is checked again
- **Mitigation:** Netris must still guarantee VNI uniqueness and reuse a VNI only after the Fabric delete that held it succeeded
- **User observes:** The resource fails with "VNI already in use" (no VNI or other resource ID in the message)

**Controller Restart Mid-Reconciliation:**

- **What happens:** Controller crashes after fabric job completes, before k8s job starts
- **Recovery:** Idempotent reconciliation — the controller re-reads `status.jobs` and `status.taskInput`, finds the Fabric entry `Succeeded` and `status.networkSegment` recorded, and proceeds to the Kubernetes job
- **User observes:** No impact, reconciliation resumes

**Partial Cleanup (Delete Subnet):**

- **What happens:** CUDN deleted but Netris VNet delete fails
- **Recovery:** the Subnet finalizer stays until each manager whose create started has a successful delete; delete tasks retry after every failure
- **User observes:** the Subnet stays DELETING with its fixed cleanup message; the administrator checks the Fabric `delete_subnet` entry in hub `status.jobs` for the diagnostic

**OVN-K CUDN Not Ready:**

- **What happens:** CUDN created but OVN-K cannot provision it
- **Recovery:** the role waits for `TransportAccepted`, `NetworkCreated`, and `NetworkAllocationSucceeded` (30 retries × 10s). On timeout it fails the job with `retryable: true`, so OSAC retries
- **User observes:** the Kubernetes `create_subnet` entry is `Retrying`; `Ready=False`, reason `Progressing`; check the OVN-K operator logs

### RBAC / Tenancy

**Tenant isolation:**

- The fulfillment-service API filters Subnet list/get by the `osac.openshift.io/tenant` annotation through OPA.
- The VirtualNetwork namespace, baseline deny, CUDN, and SecurityGroup policies carry tenant labels and annotations for traceability. They are hub objects, not tenant-facing APIs.
- VM traffic policy is enforced on the hub. `osac-baseline-deny` selects every pod in the VirtualNetwork namespace, sets both `Ingress` and `Egress`, and allows only the DHCP exchange; OVN-Kubernetes always allows ARP/ND past NetworkPolicy, but not DHCP. `osac-sg-<SecurityGroup ID>` objects carry the group's rules and select only the VMs bound to the group by `apply_network_attachment`, through `osac.openshift.io/compute-instance-id`. A VM with no SecurityGroup gets only the baseline deny.
- The CUDN namespace selector matches `osac.openshift.io/virtualnetwork-id` and `osac.openshift.io/tenant`. VMs of different VirtualNetworks cannot reach each other at L2 or L3.

**No tenant-facing RBAC:** tenants interact only through the fulfillment-service API. The AAP network jobs run as the OSAC job service account with the hub permissions in [contract §4.12](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#412-security-rbac-and-tenancy); a tenant has no direct access to namespaces, `NetworkPolicy`, or CUDNs.

**Ownership annotations:**

- CUDN: `osac.openshift.io/owner-reference: "Subnet/<subnet-name>"` and `osac.openshift.io/owner-subnet: <subnet-id>`. The owner Subnet's `delete_subnet` removes it.
- Namespace: `osac.openshift.io/owner-reference: "VirtualNetwork/<vn-name>"`. Kubernetes `delete_virtual_network` removes it.
- SecurityGroup policies: `osac.openshift.io/owner-reference: "SecurityGroup/<sg-name>"`. `delete_security_group` removes them.
- The namespace and the CUDN also carry the labels `osac.openshift.io/owner-kind`, `osac.openshift.io/owner-id`, and `osac.openshift.io/k8s-manager: cudn_evpn`; the role matches objects by their owner labels before it changes or deletes them.
- Cleanup is by the owning task, not by cross-API-group Kubernetes owner references. Deleting a VirtualNetwork is rejected while any child exists.

### Observability and Monitoring

This feature adds no metric, alert, or Kubernetes event of its own. Observe progress through:

- `Subnet.status.jobs`: the per-task `manager`, `attempt`, `state`, `jobID`, and `message` ([contract §4.7, Job tracking](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#47-ordering-concurrency-retries-and-ownership)).
- The Subnet `Ready` condition: `Ready=True`/`Succeeded` is READY; `Ready=False`/`Progressing` is PENDING; `Ready=False`/`Failed` is FAILED ([Unified — Status](/enhancements/OSAC-1433-unified-networking/design.md#status)).
- The AAP job record named by `jobID` and the launch label, for logs.
- The hub CUDN's `TransportAccepted`, `NetworkCreated`, and `NetworkAllocationSucceeded` conditions, read by the role (OVN-Kubernetes 4.22 sets no CUDN `Ready`).

There is no `status.phase`, no `jobHistory`, and no per-manager reconcile histogram, `K8sManagerWaitingForFabric`, or `CUDNProvisioningFailed` event in the contract or implementation; do not build alerts on them.

### Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| **VNI allocation race condition** — two Subnets created simultaneously get same VNI | Fabric manager (Netris) guarantees cluster-wide VNI uniqueness atomically. OSAC also checks every accepted VNI against all VirtualNetwork and Subnet CRs under one lock: a VNI a live resource holds is rejected, one held only by resources being deleted is retried. VNI reuse during delete+recreate: fabric deprovision only after CUDN fully deleted (not just deletionTimestamp set) |
| **Gateway MAC mismatch** — manual coordination step skipped, L3 traffic breaks (physical hosts on an EVPN Subnet only; open, contract §4.9) | Document prerequisite clearly in installation guide, add diagnostic command to compare MACs (kubectl + fabric API) |
| **VTEP not created** — k8s manager assumes VTEP exists, CUDN creation fails | Installation documents the VTEP prerequisite. A missing or unaccepted VTEP makes Kubernetes `create_subnet` retryable; adding or repairing it lets the task recover. It is not a NetworkClass admission gate |
| **Fabric output data loss** — fabric job completes but OSAC does not process its result | OSAC records the accepted VNIs in CR status (`VirtualNetwork.status.l3Vni`, `Subnet.status.networkSegment`) in the same status update that marks the Fabric task `Succeeded`; after a restart it resolves the job by its AAP label and processes the result (contract §4.7). |
| **IPv4-only regression** — future IPv6 support breaks existing CUDNs | CUDN VNI is immutable (delete+recreate required), no in-place upgrade |
| **FRRConfiguration conflict** — multiple OSAC installations on same cluster, label collision | Installation guide warns against multi-instance deployments, OR use namespace-scoped FRRConfiguration selector |
| **Incorrect DHCP pool configuration** — workload addresses could overlap infrastructure or another manager's pool | OVN-Kubernetes answers VM DHCP inside the logical switch; Netris serves physical hosts. Verify the recorded pool boundaries, infrastructure exclusions, router, and DNS in TC-R6-01. |
| **cudn_evpn coupled to Netris-specific outputs** — k8s manager expects Netris VPC/VNet concepts, won't work with other fabric managers | Generic contract ([contract §4.9](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#49-network-types-and-the-network-segment)): `l3_vni` from `create_virtual_network`, `network_segment: {type, l2_vni}` from `create_subnet`, and the `ipam` layout. Any fabric manager (OpenStack Neutron, Cisco ACI, Netris) can provide this contract without k8s manager changes. Netris role is first implementation of the contract. |

### Drawbacks

**Manual Prerequisites:**

Cloud Infrastructure Admin must configure VTEP, FRRConfiguration, BGP underlay, and gateway MAC coordination (physical hosts on an EVPN Subnet only; open, contract §4.9) before tenants can use this feature. High operational complexity compared to CUDN LocalNet (which required only nmstate, no BGP).

**Trade-off justification:** EVPN scalability (millions of VNIs vs 4096 VLANs) and multi-cluster support (Phase 2) outweigh the installation burden for large deployments.

**Owner-Subnet VM Limitation:**

Only the first Subnet whose Kubernetes `create_subnet` claims the VirtualNetwork's hub network can host VMs. Every Subnet with `cudn_evpn` is accepted and provisions its Fabric VNet; sibling Subnets carry bare-metal workloads, and a VM attachment on one fails finally. Tenants see Subnet eligibility and the ComputeInstance `SubnetDoesNotSupportVMs` reason with fixed guidance to choose a supported Subnet.

**Trade-off justification:** OVN Connectors (inter-subnet routing) and OVN-K secondary CUDN support (multi-NIC VMs) are pending. Phase 1 delivers single-cluster EVPN bridging with one CUDN per VirtualNetwork. Phase 2 will enable: (1) OVN Connectors for inter-subnet routing between VMs, (2) OVN-K secondary CUDN support for multi-NIC VMs (one NIC per subnet).

**Sequential Provisioning Latency:**

Subnet provisioning takes 2× the time of parallel provisioning (fabric job + k8s job serially instead of concurrently).

**Trade-off justification:** Data dependency requires sequencing. Measured overhead: ~30s fabric job + ~20s k8s job = ~50s total (vs ~30s parallel). Acceptable for infrequent Subnet creates.

## Alternatives (Not Implemented)

### Alternative 1: Unified AAP Workflow Template

**Approach:** Create single workflow template (`osac-create-subnet-fabric-k8s`) that calls Netris role, extracts VNI via set_stats, then calls cudn_evpn role within same AAP workflow.

**Pros:**
- set_stats data flow works natively (no controller VNI extraction)
- Simpler controller logic (single job instead of two)

**Cons:**
- Breaks dispatcher plugin architecture — NetworkClass can no longer route to arbitrary fabric/k8s manager combinations
- Hard-codes Netris + cudn_evpn coupling (not extensible to other fabric managers)
- AAP workflow template is more complex than individual role templates

**Rejection reason:** Preserving dispatcher extensibility is a design goal. Sequential provisioning at controller level keeps roles decoupled.

[Research: §Recommended Approach — why not unified workflow template]

### Alternative 2: API or admission gate for the owner Subnet

**Approach:** Reject a Subnet at the fulfillment-service API, or in an osac-operator admission webhook, unless it is the first Subnet of its VirtualNetwork; or reject a VM unless its Subnet owns the CUDN.

**Pros:**
- A tenant learns at create time that a sibling Subnet cannot host VMs.

**Cons:**
- Only the Kubernetes Manager knows the owner: ownership is claimed by Kubernetes `create_subnet`, and sibling Subnets are legitimate for bare-metal workloads.
- Counting Subnets or inspecting CUDNs in the API or webhook duplicates manager state and races the claim. A webhook rejection after `201 Created` leaves a stored Subnet that never provisions.
- It contradicts [contract §4.7](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#47-ordering-concurrency-retries-and-ownership): sibling Subnets are accepted, and the attachment apply fails as final; tenants see eligibility and the `SubnetDoesNotSupportVMs` failure reason.

**Rejection reason:** Keep admission uniform and let Kubernetes `create_subnet` decide ownership; expose the outcome through `Subnet.status.computeInstanceSupported` and the attachment failure.

### Alternative 3: k8s Manager Creates Per-Subnet FRRConfiguration

**Approach:** Each Subnet creates its own FRRConfiguration with VNI-specific route targets instead of relying on installation-time global FRRConfiguration.

**Pros:**
- Tenant-scoped FRRConfiguration lifecycle (delete Subnet → delete FRRConfiguration)
- No shared state between tenants in FRR config

**Cons:**
- FRRConfiguration merging is additive — multiple configs per node are allowed but increase reconciliation complexity
- Underlay BGP neighbor config must be duplicated in every FRRConfiguration (copy-paste from installation template)
- Research shows advertiseVNIs can reference multiple VNIs from one FRRConfiguration

**Rejection reason:** Installation-time FRRConfiguration with advertiseVNIs: All is simpler and follows demo pattern. OVN-K auto-updates FRR when CUDN appears.

[Demo: Phase 2.6 global FRRConfiguration, Phase 5.3 auto-update]

## Open Questions

### 1. Gateway MAC Coordination Mechanism

**Owner:** Cloud Infrastructure Admin (installation documentation owner)

**Impact:** Prerequisites documentation (§Test Plan)

Where is the authoritative MAC value? Does Netris VNet gateway MAC come from a pool (predictable), or is it random? Does CUDN gateway MAC come from a configurable field, or auto-generated? If both are random, manual coordination is impossible.

**Assumption:** Both sides support deterministic MAC generation or explicit MAC configuration. [Assumption]

**Status:** For VMs the coordination is a design choice of the Fabric Manager ([contract §4.9](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#49-network-types-and-the-network-segment)): OVN-Kubernetes serves the VM gateway (Gateway Ownership), and the Netris V-Net serves the same address with its own MAC until the shared-MAC follow-up. OVN-Kubernetes derives its gateway MAC from the gateway IP and has no field to set it; Netris accepts a per-V-Net `customAnycastMac`. Whether PRD R9 still applies to physical hosts on an EVPN Subnet is open with the physical-host gateway question in [contract §4.9](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#49-network-types-and-the-network-segment).

### 2. Validation still needed

The defined behavior is not evidence of a new deployed run. The test plan separates component checks for Netris DHCP creation and repair from live acceptance checks for VM and bare-metal leases, routing, DNS, gateway-MAC behavior, and isolation. VMs receiving DHCP from OVN-Kubernetes is established architecture, not an unresolved choice of responder. Cross-Subnet routing, physical gateway-MAC behavior, and node-service isolation still need their stated lab evidence.

## Test Plan

### Unit Tests

**fulfillment-service (Go + Ginkgo):**

- `internal/servers/subnets_server_test.go` and `networking_lifecycle_guards_test.go`:
  - Subnet creation succeeds for the owner Subnet and for an otherwise-valid sibling under the same VirtualNetwork; no Subnet-count, VM-count, or CUDN lookup runs
  - In a default VirtualNetwork, the default-Subnet readiness gate applies; no `cudn_evpn`-specific gate is added
  - Subnet delete is rejected with `FAILED_PRECONDITION` while a workload's stored network attachment references it, and the message names the first blocking workload ID
  - Subnet delete is accepted once the workload and its NetworkAttachment are gone
  - No code path deletes a ComputeInstance, BareMetalInstance, or Cluster

**osac-operator (Go + Ginkgo):**

- `internal/controller/networking_resources_test.go` (controller Envtest with fake AAP) and `internal/networktask/result_test.go` (unit):
  - Every Subnet with `cudn_evpn` plans both Fabric and Kubernetes create targets; the controller never counts Subnets and never reads a CUDN
  - Sequential provisioning: Fabric `create_subnet` runs first; Kubernetes `create_subnet` starts only after the Fabric entry is `Succeeded` and `status.networkSegment` is recorded
  - Sequential provisioning: the VirtualNetwork records `status.l3Vni` from the Fabric `l3_vni`; the Subnet stores no input and launches nothing until it is recorded
  - Sequential provisioning: a valid `network_segment {type, l2_vni}` is recorded in `status.networkSegment`; a malformed one, or one with `l3_vni`, fails the Subnet as final
  - Sequential provisioning: k8s job receives `network_segment` as a launch key and `virtual_network.status.l3Vni` in the stored snapshot
  - Parallel provisioning fallback when only fabric manager exists (no k8s manager in NetworkClass)
  - Controller restart mid-provisioning resumes from the Fabric `Succeeded` entry and recorded `networkSegment`
  - Retryable Fabric failure: entry `Retrying`, `Ready=False`/`Progressing`, Kubernetes job not started
  - Final Fabric or Kubernetes failure: entry `Failed`, `Ready=False`/`Failed`, no retry
  - Compute eligibility: consume mocked successful Kubernetes results (`true`, `false` with reason, or omitted), persist them with task completion, and verify feedback mapping; actual CUDN claims belong to the role tests
  - Deletion order: launch Kubernetes `delete_subnet` before Fabric `delete_subnet` and keep the finalizer until both succeed; CUDN and namespace side effects belong to the role tests
  - Networking never deletes a VM, BareMetalInstance, or Cluster CR

**VMaaS (Go + Ginkgo):**

- `internal/controller/computeinstance_controller_test.go`:
  - The ComputeInstance controller creates the NetworkAttachment before the VM and reads the namespace from `vm_attachment.namespace`
  - The VM is created in `osac-vn-<VirtualNetwork API ID>`, never in a namespace derived from the Subnet name
  - No Subnet-count or CUDN-owner pre-check runs in VMaaS
  - A final Kubernetes apply failure with explicit false Subnet eligibility sets ComputeInstance `NetworkReady=False`, reason `SubnetDoesNotSupportVMs`, with fixed public message `The selected Subnet does not support VMs. Create the VM on a Subnet that supports VMs.`; raw diagnostics stay in hub status. True/unknown eligibility retains the ordinary failure reason, retryable applies stay pending, and final Fabric failures do not select the new reason
  - A retryable apply failure keeps the ComputeInstance pending and retries

### Component Role Tests

**osac-aap (pytest unit tests and Ansible component integration):**

- `collections/ansible_collections/osac/templates/roles/netris/`:
  - `create_virtual_network.yaml` creates/fetches Netris VPC and returns `osac_result.l3_vni` (an integer) with `network_type`
  - `create_subnet.yaml` creates Netris VNet with correct CIDR in the VPC of `virtual_network.id`
  - `create_subnet.yaml` returns `osac_result.network_segment: {type: evpn, l2_vni}` (no `l3_vni`), the same value on every rerun
  - `delete_subnet.yaml` deletes Netris VNet, VPC remains
  - Netris DHCP: a non-empty `ipam.physical_ipv4_cidrs` enables DHCP over that recorded range at Subnet creation; a rerun repairs a missing or incorrect pool
  - Netris DHCP: a Subnet created with an empty physical pool leaves DHCP off, and a `delete_network_attachment` does not enable it
  - Netris DHCP: a physical `apply_network_attachment` repairs DHCP before moving the port
  - Lab-only diagnostic regression: `netris_evpn_vnet_gateway_mode: none` creates no Netris gateway and no Fabric DHCP; this is not supported-mode acceptance
  - The CUDN reservation is not expanded into a legacy first-half pool; only the region outside `ipam.overlay_ipv4_cidrs` is reserved

- `collections/ansible_collections/osac/templates/roles/cudn_evpn/`:
  - `create_virtual_network.yaml` creates the VirtualNetwork namespace `osac-vn-<VN API ID>` with the primary-UDN label and the `osac-baseline-deny` policy that allows only DHCP (plus OVN's implicit ARP/ND)
  - `create_security_group.yaml` creates `osac-sg-<SecurityGroup ID>` selecting no VM until an attachment binds one; a rule update replaces the rules and keeps the members
  - `apply_network_attachment.yaml` adds the VM's `osac.openshift.io/compute-instance-id` to each selected policy and returns `vm_attachment: {namespace: osac-vn-<VN ID>}`
  - `create_subnet.yaml` creates CUDN with macVRF/ipVRF VNIs from `network_segment.l2_vni` and `virtual_network.status.l3Vni`, route targets `0:<VNI>`, MTU 1500, `defaultGatewayIPs: [gateway_ipv4]`, `infrastructureSubnets: [gateway/32, network+2/32]`, and `reservedSubnets` outside the overlay range
  - `create_subnet.yaml` waits for the three CUDN conditions (`TransportAccepted`, `NetworkCreated`, `NetworkAllocationSucceeded`) before completing
  - `create_subnet.yaml` sets tenant, `osac.openshift.io/owner-reference: Subnet/<subnet-name>`, and `osac.openshift.io/owner-subnet: <subnet-id>` on the CUDN
  - A sibling's create reads the owner Subnet from the API server: a live owner permits the no-op, an owner with a deletion timestamp retries before CUDN termination, a missing owner with a surviving CUDN fails finally without adoption, and a read error retries. A create also retries while the CUDN terminates and can claim a new one after deletion, including on a sibling rerun; sibling delete leaves the owner CUDN unchanged
  - `delete_subnet.yaml` removes the CUDN only when this Subnet owns it, waits until it is gone, and never deletes the VirtualNetwork namespace or the baseline policy
  - A VM attachment on a non-owner Subnet fails as final with the eligibility diagnostic, selected Subnet ID, and current supported Subnet ID when known; its delete succeeds because nothing was bound
  - Stale VRF recovery (if needed) is manual — see Support Procedures (not automated due to ovnkube-node restart impact)

### Integration Tests

**osac-operator (Envtest, fake AAP):**

- Create NetworkClass with fabric_manager="netris", k8s_manager="cudn_evpn"
- Create Subnet, verify the dispatcher plan includes both Fabric and Kubernetes targets for every `cudn_evpn` Subnet
- Mock fabric job completion with `osac_result` `l3_vni` (VirtualNetwork) and `network_segment` (Subnet)
- Verify the k8s job gets `network_segment` and `virtual_network.status.l3Vni`
- Verify `Subnet.status.jobs` entries transition `Running` → `Succeeded` and the Subnet reaches `Ready=True`/`Succeeded`
- Delete Subnet, verify finalizer blocks until fabric and k8s jobs complete

**fulfillment-service + osac-operator (Kind cluster, mocked Netris):**

- Start with a fresh VirtualNetwork, a READY fixture SecurityGroup, and a first Subnet that owns its CUDN; the owner Subnet has no workloads in this scenario
- Create a sibling Subnet under the same VirtualNetwork → succeeds and becomes READY; Kubernetes `create_subnet` changes no CUDN
- While the owner CUDN still exists, create a ComputeInstance referencing the sibling Subnet and fixture SecurityGroup → its attachment fails finally with the VM eligibility diagnostic; no VM is provisioned and the owner CUDN stays unchanged
- Delete the failed ComputeInstance through its workload cleanup; wait until its record and NetworkAttachment are gone
- Delete the sibling Subnet and wait for its removal → its Fabric VNet is removed and the owner CUDN stays unchanged
- Delete the owner Subnet (with no workload references) → owner CUDN removed; the namespace and `osac-baseline-deny` remain
- Delete the fixture SecurityGroup and any other VirtualNetwork children created by the fixture; wait until every child, including both Subnets, is gone
- Delete the VirtualNetwork → namespace and baseline removed

### E2E Tests

**`tests/e2e/networking/vmaas/test_vmaas_networking.py` (pytest, real Netris fabric + OCP cluster):**

The bare-metal and cross-Subnet steps below are not in this module; run them by hand (TC-R4-01, TC-R4-02).

**Preconditions:**
- OCP cluster with OVN-Kubernetes, FRR operator, NMState operator installed
- VTEP CR exists (tenant-vtep)
- FRRConfiguration exists with underlay BGP peering (evpn: "true" label)
- RouteAdvertisements CR exists (frrConfigurationSelector matches FRRConfiguration)
- Netris fabric accessible, API credentials configured
- NetworkClass "netris-evpn" with fabric_manager="netris", k8s_manager="cudn_evpn"
- Supported Netris gateway mode `gateway_ipv4`; both Subnets have non-empty physical pools. The diagnostic `none` and `physical_first` modes are excluded
- Reserve two non-overlapping Subnet CIDRs within `<vn-cidr>`, each satisfying the address-plan prefix limit; use the deployment's excluded-range plan

**Test Flow:**

1. Create Tenant via fulfillment-service API
2. Create VirtualNetwork with IPv4 CIDR `<vn-cidr>` large enough for both planned non-overlapping Subnet CIDRs, from the deployment's excluded-range plan; it uses the deployment's single NetworkClass "netris-evpn". Create a SecurityGroup in it that allows the test traffic and wait until it is READY
3. Create Subnet with IPv4 CIDR `<subnet-cidr>`; record `Subnet.status.ipam` (`overlay_ipv4_cidrs`, `physical_ipv4_cidrs`, `gateway_ipv4`)
4. Wait for the Subnet's `Ready=True` condition, reason `Succeeded` (timeout 300s); do not read a phase
5. Verify the CUDN exists on OCP: `oc get clusteruserdefinednetwork osac-vn-<vn-id>`
6. Verify CUDN status.conditions TransportAccepted, NetworkCreated and NetworkAllocationSucceeded are True
7. Create the VM through the ComputeInstance API using the owner Subnet and fixture SecurityGroup; verify its VirtualMachine is in the VirtualNetwork's CUDN namespace
8. Wait for the VMI Running with an IP in `status.ipam.overlay_ipv4_cidrs`; record it as `<vm-overlay-ip>`
9. Verify FRR VNI status: `vtysh -c "show evpn vni"` includes L2 VNI and L3 VNI
10. Verify BGP EVPN routes: `vtysh -c "show bgp l2vpn evpn"` includes Type-2 (MAC), Type-3 (VTEP), Type-5 (prefix)
11. Provision an OSAC-managed BareMetalInstance on the Netris fabric in the same Subnet, with the fixture SecurityGroup; obtain its address from `query_dhcp_lease`, not a fixed host offset. Record it as `<physical-dhcp-lease>` and verify it is in `status.ipam.physical_ipv4_cidrs`
12. Verify L2 connectivity: VM pings `<physical-dhcp-lease>` (same subnet)
13. Create a sibling Subnet `<sibling-subnet-cidr>` under the same VirtualNetwork and wait until it is READY; provision a second OSAC-managed BareMetalInstance on it with the fixture SecurityGroup. Record its lease as `<sibling-physical-dhcp-lease>` and verify it lies in that Subnet's recorded physical pool
14. Verify L3 connectivity: VM pings bare-metal node (cross-subnet via ipVRF)
15. Attempt to delete the owner Subnet while the VM and first BareMetalInstance exist → `FAILED_PRECONDITION` reports the blocking workload count and first blocking ID; both workloads remain untouched
16. Delete the VM through ComputeInstance cleanup; wait until the VM, VMI, ComputeInstance record, and its NetworkAttachment are gone
17. Delete both BareMetalInstances through BMaaS cleanup; wait until their records and physical NetworkAttachments are gone and the fabric ports have been restored. Physical workload references must be removed before deleting either Subnet
18. Delete the sibling Subnet and wait until it and its Netris VNet are gone; verify the owner CUDN is unchanged
19. Delete the owner Subnet and wait until its CUDN is removed before its Netris VNet; the VirtualNetwork namespace, `osac-baseline-deny`, and fixture SecurityGroup policy remain
20. Delete the fixture SecurityGroup and wait until its record and policy are gone; verify both Subnet records are gone and the VirtualNetwork has no remaining child Subnets, SecurityGroups, NATGateways, or FabricDomains
21. Delete the VirtualNetwork → namespace and baseline removed; verify both Netris VNets and the VPC are gone (API query)
22. Delete the fixture Tenant through its API; tenant cleanup owns removal of its default networking

**Expected Results:**

- VM receives `<vm-overlay-ip>` from the recorded `overlay_ipv4_cidrs` (OVN-K IPAM), with `gateway_ipv4` as router
- Bare-metal addresses come from the recorded `physical_ipv4_cidrs` and match the actual DHCP leases
- VM MAC and IP advertised to fabric via BGP EVPN Type-2 route
- L2 ping succeeds (same-subnet VM ↔ bare-metal)
- L3 ping succeeds (cross-subnet VM ↔ bare-metal via VPC ipVRF routing)
- FRR shows the lab VTEP (from `oc get vtep tenant-vtep`) as remote VTEP for the VNI
- Networking never deletes the VM; ComputeInstance cleanup does
- Cleanup completes without orphaned CUDNs, namespaces, VNets, or VPCs

**Tricky Areas:**

- VNI acceptance: two creates returning one VNI at once (only one is accepted), and a VNI held by a resource being deleted (retried, then accepted)
- CUDN VNI collision: two Subnets created concurrently (stress test)
- Gateway MAC mismatch detection: compare CUDN gateway MAC with Netris VNet gateway MAC (physical hosts on an EVPN Subnet only; open, contract §4.9)
- `osac_result` VNIs must be JSON integers (`| int`), not strings; OSAC rejects a string VNI

## Graduation Criteria

Release labels are not assigned by this design. Phase 1 acceptance requires the contract task and component checks plus the deployed checks in [the test plan](testplan.md), with the single-hub, single-CUDN limit and remaining physical-gateway limitations documented. Multi-cluster placement, gateway-MAC automation, OVN Connectors, and secondary networks remain future work; they are not promises for specific release numbers.

## Upgrade / Downgrade Strategy

This design follows [contract §8](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#8-impact-and-compatibility): upgrading an existing installation is unsupported. Use a fresh, compatible OSAC installation with the manager registrations, execution environment, operator, fulfillment service, and EVPN hub prerequisites from the same tested release.

The operator records `Subnet.status.computeInstanceSupported` and `computeInstanceUnsupportedReason` after accepting the Kubernetes task result. Its feedback controller maps them to the API; fulfillment-service does not write those hub status fields.

A VirtualNetwork from before the EVPN handoff has no `status.l3Vni`; it cannot be repaired by assuming a VNI or an in-place upgrade. Recreate it through the dependency-ordered lifecycle. Before removing `cudn_evpn` or moving to an installation that lacks it, delete workloads and their NetworkAttachments, then Subnets, SecurityGroups and other children, VirtualNetworks, and finally the NetworkClass, as in [Disabling the Feature](#support-procedures). CUDN CRDs belong to OVN-Kubernetes.

**Backward Compatibility:**

- A NetworkClass with an empty `k8s_manager` follows the Fabric-only path.
- No subnet-count or VM-count API gate is added; the Kubernetes attachment task remains authoritative.
- Omitted successful manager eligibility results default to supported; absent API status stays unknown until reported, as defined in [Unified — Compute eligibility](/enhancements/OSAC-1433-unified-networking/design.md#compute-eligibility).

## Version Skew Strategy

No cross-release component skew is established by this design. Deploy the installer, execution environment, operator, and fulfillment service as a tested set; the required task inputs, results, and status mappings must agree. Do not infer compatibility from the historical 0.2/0.3 examples.

ClusterUserDefinedNetwork, VTEP, and FRRConfiguration are external CRDs. Their versions belong to OVN-Kubernetes and FRR; a changed CRD requires matching manager support and validation against that cluster version. OSAC provides no automatic CRD-version migration.

## Support Procedures

**Failure Detection:**

| Symptom | Likely Cause | Diagnostic Command |
|---------|-------------|-------------------|
| Subnet PENDING or `Ready=False`/`Progressing` >5min | Fabric job hanging or Kubernetes job waiting for the Fabric result | read `status.jobs`, then check the AAP job record named by `jobID` |
| Subnet `Ready=False Failed`, message 'OSAC rejected the create_subnet result: …' | Fabric `osac_result` broke a §4.9 rule | read the Subnet's `status.jobs` entry message and the operator log |
| CUDN exists but VMs have no network | VTEP down, FRR not advertising routes | `oc get vtep tenant-vtep`, `oc exec -n openshift-frr-k8s <frr-pod> -- vtysh -c "show evpn vni"` |
| VM pings same-subnet bare-metal fail (L2) | VNI mismatch, gateway MAC mismatch (physical hosts on an EVPN Subnet only; open, contract §4.9) | Compare CUDN macVRF.vni with Netris VNet vxlanID, compare gateway MACs |
| VM pings cross-subnet bare-metal fail (L3) | ipVRF route target mismatch, fabric routing issue | `vtysh -c "show bgp l2vpn evpn" \| grep Type-5`, check Netris VPC routing table |
| Subnet delete completes but VRF device persists on worker node | Stale VRF not cleaned up by OVN after CUDN delete (rare race condition) | `oc debug node/<node-name> -- chroot /host ip link show type vrf` |

**Manual Recovery Procedures:**

**Stale VRF Cleanup (observed during testing, rare):**

If a VRF device persists on a worker node after CUDN deletion:

1. Identify the stale VRF:
   ```bash
   oc debug node/<node-name> -- chroot /host ip link show type vrf
   # Look for VRF named after the deleted VirtualNetwork
   ```

2. Verify CUDN is actually deleted:
   ```bash
   oc get clusteruserdefinednetwork <vnet-name>
   # Should return "NotFound"
   ```

3. **Manual cleanup (if VRF persists after CUDN gone):**
   ```bash
   # Option 1: Restart ovnkube-node pod on affected node (impacts all VMs on node)
   oc delete pod -n openshift-ovn-kubernetes -l app=ovnkube-node --field-selector spec.nodeName=<node-name>

   # Option 2: Direct VRF deletion (less disruptive, requires node access)
   oc debug node/<node-name>
   chroot /host
   ip link delete <vrf-name> type vrf
   ```

**Impact:** Restarting ovnkube-node disrupts all VMs on the affected node (not just the deleted namespace). Only use when VRF persists after confirming CUDN is deleted.

**Prevention:** This is a timing race in OVN-Kubernetes. No known mitigation. If observed frequently, report to OVN-Kubernetes upstream.

**Disabling the Feature:**

Disabling is an ordered cleanup; the fulfillment-service dependency guards reject out-of-order deletes instead of leaving orphaned backend objects.

1. Delete every workload and its NetworkAttachment that references a Subnet of a VirtualNetwork using `cudn_evpn`.
2. Delete the Subnets. Each owner Subnet's Kubernetes `delete_subnet` removes the CUDN; a sibling's changes nothing; Fabric deletes each VNet.
3. Delete the SecurityGroups; `delete_security_group` removes each `osac-sg-<SecurityGroup ID>` policy.
4. Delete the VirtualNetworks; Kubernetes `delete_virtual_network` removes `osac-vn-<VN ID>` and `osac-baseline-deny`, then Fabric deletes the VPC.
5. Delete the NetworkClass.
6. Delete the ConfigMap `osac-network-k8s-manager-cudn-evpn` to prevent new registrations.

A VirtualNetwork delete is rejected with `FAILED_PRECONDITION` while any child Subnet, SecurityGroup, NATGateway, or FabricDomain exists; it never succeeds while children remain. A Subnet delete is rejected while any workload's stored network attachment references it. Networking never deletes a VM, BareMetalInstance, or Cluster.

**Consequences:**
- **Cluster health:** no impact.
- **Existing workloads:** they must be deleted before their Subnets; the guards block the Subnet delete otherwise.
- **New workloads:** tenants cannot create new `cudn_evpn` Subnets without the NetworkClass and registration.

**Re-Enabling:**

Recreate the ConfigMap and NetworkClass, then recreate the VirtualNetworks and Subnets from the desired configuration. Kubernetes `create_virtual_network` recreates the VirtualNetwork namespace and baseline deny, and the first Subnet's Kubernetes `create_subnet` claims a new CUDN.

There is no supported state where a supported cleanup leaves a CUDN orphaned: the owner Subnet's delete removes it, and the next Subnet claims a new one. If a CUDN is found without its `osac.openshift.io/owner-subnet` annotation, treat it as drift: confirm no Subnet owns it, remove it, and recreate the Subnet. Do not rely on the next create to adopt it.

## Historical sketches (non-normative)

These ideas appeared in earlier revisions of this design and are superseded by the contract and the `cudn_evpn` role. They are retained as a reference for identifying obsolete advice in older issues and reviews; they are not a roadmap and none is normative.

- **API rejection of a second Subnet.** Superseded by owner-Subnet admission: sibling Subnets are accepted and become READY.
- **VMaaS subnet-count gate.** Superseded: VMaaS creates the NetworkAttachment first and uses the returned VirtualNetwork namespace; a non-owner attachment fails at apply.
- **`osac.openshift.io/skip-k8s-manager` annotation and controller subnet-count auto-detection.** Removed. Every Subnet with `cudn_evpn` runs both managers.
- **Subnet-name namespace.** Superseded by the VirtualNetwork-owned `osac-vn-<VirtualNetwork API ID>` namespace, shared by the VirtualNetwork's VMs and SecurityGroup policies.
- **Provisioning-package `JobTarget.DependsOn` and a generic dependency graph.** The controller orders the contract tasks from `status.jobs`; no new dependency field exists.
- **Subnet deletion deletes the namespace and VMs.** Superseded: workloads block Subnet deletion; the owner Subnet removes only the CUDN; Kubernetes `delete_virtual_network` removes the namespace and baseline.
- **`Subnet.status.phase` and `status.jobHistory`.** Superseded by the `Ready` condition and `status.jobs` entries.
- **Old DHCP sketches:** a first-half physical pool, delayed DHCP enablement, and a CUDN preflight or mandatory delete-and-recreate migration. Superseded by the recorded `ipam.physical_ipv4_cidrs`, DHCP enabled at creation and repaired on rerun, and no first-half pool. Lab-only gateway overrides are documented in OSAC-2434 and do not define supported deployments.

## Infrastructure Needed

None. All infrastructure (OCP cluster, Netris fabric, FRR operator) is assumed to exist per PRD assumptions.

---

---

## Provenance

Authored: respond @ design 0.15.0 - 87d14ea, workspace main @ 74c7c4fb3
Phases: revise, revise, revise, revise, revise, revise, respond, respond, respond, respond, respond

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.15.0","ai_workflows":"87d14ea","source_repo":"74c7c4fb3","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["revise","revise","revise","revise","revise","revise","respond","respond","respond","respond","respond"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":true} -->

**End of Design Document**
