---
title: multi-nic-role-based-network-types
authors:
  - Alona Kaplan
  - Vladik Romanovsky
creation-date: 2026-10-18
last-updated: 2026-10-19
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-6121
see-also:
  - "/enhancements/OSAC-1433-unified-networking-architecture"
  - "/enhancements/OSAC-4291-cudn-evpn-k8s-manager-phase-1-networking"
  - "/enhancements/OSAC-1435-vmaas-networking"
  - "/enhancements/OSAC-1437-bmaas-networking"
  - "https://github.com/osac-project/enhancement-proposals/pull/389"
replaces:
  - "N/A"
superseded-by:
  - "N/A"
---

# Multi-NIC with Role-Based Network Types

> **OSAC-6121 managed-VM follow-up:** This branch preserves the role-based
> network type design and its original commits. The provider-managed OOB path
> near the end of this document is authoritative where earlier generic or
> tenant-managed examples conflict with the first implementation scope. That
> path is VMaaS-only: the provider creates the VirtualNetworks and
> ComputeInstance, using one shared OOB VirtualNetwork. Tenants consume the
> resulting VM. CaaS, BMaaS, hot-plug, and tenant-created OOB networks are not
> included.

## Summary

This design extends OSAC-1433's single-NetworkClass architecture to support multiple network types
within one NetworkClass, enabling VMs (and bare-metal instances) to have multiple NICs where each NIC
connects to a network with a different role and different backend implementation. The NetworkClass
gains a `network_types` list that maps role names (e.g., "tenant", "secondary_vlan", "highspeed")
to specific manager pairings (fabric_manager + k8s_manager). Each VirtualNetwork selects a
`network_type`,
and the dispatcher routes provisioning to the matching managers. The k8s manager contract is extended
with primary/secondary role semantics and a `SubnetNetworkBinding` output contract that lets the VM
reconciler compose KubeVirt VM specs without k8s-manager-specific logic. New network roles can be
added by deploying a ConfigMap + Ansible role — no code changes to existing managers, the dispatcher,
or the VM reconciler.

For the first OSAC-6121 implementation, the role framework is used for a
provider-managed VM with a primary workload network and an optional OOB
secondary. One NetworkClass remains configured per deployment. A
provider-controlled `supports_multi_nic` capability keeps deployments on the
existing zero-or-one-attachment path until both manager paths and the guest
configuration/status path are ready. The detailed managed workflow below
supersedes the broader tenant-created OOB and SR-IOV examples for this
increment.

## Related Designs

- **OSAC-1433 Unified Networking Architecture** — Establishes the two-manager model
  (fabric_manager + k8s_manager), NetworkClass as a deployment-level resource, and pluggable
  managers via ConfigMap (decision #11). This design extends that architecture to support multiple
  manager pairings per NetworkClass.
- **OSAC-4291 CUDN EVPN K8s Manager Phase 1** — First k8s manager implementation (`cudn_evpn`).
  This design builds on it as the "tenant" network type with `supports_primary: true`. The Phase 1
  design is unchanged; this design adds the framework around it for multi-NIC.
- **OSAC-1435 VMaaS Networking** — Defines `ComputeNetworkAttachment` with `subnet`,
  `security_groups`, and `primary` fields. Already supports `repeated` attachments (multi-NIC at
  the API level). This design specifies how the VM reconciler uses `SubnetStatus.network_binding`
  to compose the KubeVirt VM.
- **OSAC-1437 BMaaS Networking** — Defines `BareMetalNetworkAttachment` with `interface` and
  `primary` fields. Already supports multi-NIC with different physical interfaces. This design
  extends the same pattern to VMs with different virtual network backends.

## Motivation

OSAC runs VMs on OpenShift using KubeVirt. The CUDN+EVPN design (OSAC-4291) enables VMs to join
the physical fabric via BGP EVPN. However, real-world deployments require VMs with multiple NICs
connected to networks with fundamentally different backend implementations:

- **Primary NIC**: Tenant traffic via CUDN+EVPN (fabric-bridged, L2/L3 reachable from bare-metal)
- **Secondary NIC**: Out-of-band management via secondary VLAN (`cudn_localnet` implementation —
  isolated, only management server can reach VMs, VMs cannot communicate with each other)
- **Secondary NIC**: High-speed data via SR-IOV (`sriov` implementation — hardware passthrough
  for performance-sensitive workloads)
- **Secondary NIC**: Storage network via dedicated VLAN (`cudn_localnet` implementation — for
  NFS/iSCSI access)

Each role maps to a fabric/k8s manager pair and may require a different
implementation. Multiple role names may reuse the same manager implementation.
The current model — one `fabric_manager` + one `k8s_manager` per NetworkClass —
cannot express this.

**Concrete customer scenario:** A customer wants VMaaS with CUDN+EVPN as the k8s manager and
their own fabric manager (not Netris). Additionally, some VMs need a secondary OOB network using
localnet, with MultiNetworkPolicy enforcing that VMs are isolated from each other — only the
management server outside the cluster can access VMs via this network. The customer may also
require SR-IOV interfaces for high-speed workloads in the future.

### Goals

- Support multiple network types within a single NetworkClass (preserving decision #6: one
  NetworkClass per deployment)
- Enable VMs with multiple NICs where each NIC connects to a different network type with
  a different backend implementation
- Define a generic k8s manager output contract (`SubnetNetworkBinding`) so the VM reconciler
  composes KubeVirt VM specs without k8s-manager-specific logic
- Allow providers to add new network roles by deploying a ConfigMap + Ansible role — no changes
  to existing managers, dispatcher, or VM reconciler (extending decision #11 to multi-NIC)
- Maintain backward compatibility — omitting `network_type` on a VirtualNetwork uses the
  top-level default managers

### Non-Goals

- Implementing specific k8s managers (`cudn_localnet`, `sriov`) — those are separate designs
  that conform to the contract defined here
- Multi-cluster VM placement with multi-NIC (deferred to Phase 2)
- Hot-plugging NICs after VM creation (attachment topology is create-time only)
- NetworkPolicy or MultiNetworkPolicy management beyond what individual k8s managers provide
- CaaS and BMaaS changes, tenant-created OOB networks, arbitrary cross-VirtualNetwork attachments, and hot-plug

## Proposal

### How Cloud Providers Model Multi-NIC

| Provider | Network container | NIC model | Multi-backend |
|----------|------------------|-----------|---------------|
| **GCP** | VPC Network | Each NIC in a **separate** VPC Network | Different VPCs = different backends |
| **AWS** | VPC | ENI per NIC, each ENI in a Subnet | Enhanced Networking (SR-IOV) is per-instance capability |
| **Azure** | VNet | NIC per network, each in a Subnet | Accelerated Networking per-NIC flag |
| **OCI** | VCN | Primary VNIC + secondary VNICs | Each VNIC can be in different VCN/Subnet |

**Common pattern**: different network purposes = different top-level network resources. The VM's
multi-NIC capability bridges across them. One NIC is "primary" (default gateway, DNAT target).

OSAC's existing `ComputeNetworkAttachment -> Subnet -> VirtualNetwork -> NetworkClass` chain
already follows this pattern. The GCP model is the closest match: each NIC is in a separate
VPC Network (= VirtualNetwork), and different VPCs can have different backends. What's missing
in OSAC is the ability to route different VirtualNetworks to different managers within the single
NetworkClass.

### Network Type vs K8s Manager: Role vs Implementation

A key distinction in this design:

- **Network type** (role) describes the **purpose** of the network — what it is used for.
  Examples: `"tenant"` (primary tenant L2/L3), `"secondary_vlan"` (secondary VLAN-attached
  network for OOB, storage, etc.), `"highspeed"` (SR-IOV/DPDK passthrough).
- **K8s manager** (implementation) describes **how** the network is provisioned on Kubernetes.
  Examples: `"cudn_evpn"` (OVN-K CUDN with EVPN transport), `"cudn_localnet"` (OVN-K CUDN
  with localnet bridge), `"sriov"` (SR-IOV Network Operator).

The same k8s manager can serve multiple roles. For example, `cudn_localnet` could back both
a `"secondary_vlan"` type (for OOB management) and a `"storage_vlan"` type (for NFS access) —
same implementation, different purpose, potentially different configuration. Conversely, the
same role could be served by different k8s managers in different deployments (e.g., `"highspeed"`
might use `"sriov"` in one deployment and `"dpdk"` in another).

The tenant never sees the k8s manager name. They create a VirtualNetwork with
`network_type: "secondary_vlan"` and the NetworkClass maps that role to the appropriate
implementation.

### Central Design Statement

The NetworkClass is extended with a `network_types` list. Each entry maps a role name to a
specific (fabric_manager, k8s_manager) pair with primary/secondary capabilities. VirtualNetworks
select a `network_type` and the dispatcher routes provisioning accordingly. The k8s manager
writes a `SubnetNetworkBinding` into Subnet status that tells the VM reconciler exactly how to
compose the KubeVirt VM — no manager-specific logic in the reconciler.

### NetworkClass Extension

The single NetworkClass describes **all** networking capabilities of the deployment:

```protobuf
message NetworkClass {
  // ... existing fields 1-12 unchanged ...

  // Supported network types with per-type manager dispatch.
  // When a VirtualNetwork specifies a network_type, the dispatcher
  // uses the managers from the matching entry instead of the
  // top-level fabric_manager / k8s_manager defaults.
  repeated NetworkType network_types = 13;
}

message NetworkType {
  // Tenant-facing role name describing the network's purpose.
  // Examples: "tenant", "secondary_vlan", "highspeed", "storage".
  // This is NOT a k8s manager name — it describes what the network is for,
  // not how it is implemented.
  string name = 1;

  // Human-friendly label, e.g. "Tenant Network", "Secondary VLAN", "High-Speed SR-IOV".
  string title = 2;

  // Fabric manager implementation for this role. Empty = no fabric manager (k8s-only).
  optional string fabric_manager = 3;

  // K8s manager implementation for this role, e.g. "cudn_evpn", "cudn_localnet", "sriov".
  // Must match a registered k8s manager ConfigMap.
  string k8s_manager = 4;

  // Whether this combination of managers can serve as a VM's primary NIC
  // (default gateway, DNAT target). This is a property of the combination —
  // e.g., cudn_evpn + a fabric manager that provides a gateway = primary-capable,
  // cudn_localnet alone = not primary-capable.
  bool supports_primary = 5;

  // Whether this combination can serve as a secondary NIC.
  bool supports_secondary = 6;
}
```

Concrete example — one NetworkClass describing the full deployment:

```yaml
NetworkClass "prod-region-1":
  fabric_manager: "customer-fabric"      # Default (backward compat)
  k8s_manager: "cudn_evpn"              # Default (backward compat)

  network_types:
    - name: "tenant"                           # Role: primary tenant L2/L3
      fabric_manager: "customer-fabric"        # Implementation: customer's fabric manager
      k8s_manager: "cudn_evpn"                # Implementation: OVN-K CUDN with EVPN
      supports_primary: true                   # This combination provides a fabric gateway
      supports_secondary: false

    - name: "secondary_vlan"                   # Role: secondary VLAN-attached network
      # no fabric_manager — k8s only           # (used for OOB, storage, monitoring, etc.)
      k8s_manager: "cudn_localnet"             # Implementation: OVN-K CUDN with localnet bridge
      supports_primary: false                  # No fabric gateway — secondary only
      supports_secondary: true

    - name: "highspeed"                        # Role: high-speed data plane
      # no fabric_manager — direct hardware
      k8s_manager: "sriov"                     # Implementation: SR-IOV Network Operator
      supports_primary: false                  # SR-IOV passthrough — secondary only
      supports_secondary: true
```

### VirtualNetwork Extension

Each VirtualNetwork selects which type it is:

```protobuf
message VirtualNetworkSpec {
  // ... existing fields ...

  // Selects which NetworkType from the NetworkClass handles this VN.
  // Immutable after creation. When omitted, the NetworkClass's
  // top-level fabric_manager / k8s_manager are used (backward compat).
  optional string network_type = 5 [
    (google.api.field_behavior) = OPTIONAL,
    (google.api.field_behavior) = IMMUTABLE
  ];
}
```

### Subnet Status: Network Binding Output Contract

The k8s manager writes its output via `set_stats`. The Subnet controller writes it into Subnet
status. The VM reconciler reads it when composing the KubeVirt VM. This is separate from the
fabric-to-k8s-manager handoff: the OOB localnet path consumes a versioned fabric-output contract
after physical network configuration, using the existing OSAC-4291 job/ConfigMap dependency
pattern or an equivalent contract. The handoff details are defined in the managed workflow below.

```protobuf
message SubnetStatus {
  SubnetState state = 1;
  optional string message = 2;
  string hub = 3;

  // K8s network resource provisioned for this subnet.
  // Populated by the Subnet controller from the k8s manager's set_stats output.
  optional SubnetNetworkBinding network_binding = 4;
}

message SubnetNetworkBinding {
  // KubeVirt interface binding method: "l2bridge" (primary UDN),
  // "bridge" (secondary bridge), "sriov" (SR-IOV passthrough).
  string kubevirt_binding = 1;

  // NAD reference for secondary networks (e.g., "oob-vlan100-nad").
  // Empty for primary (primary uses pod network, no NAD ref needed).
  // The VM reconciler determines whether to use pod: {} or multus: {} from
  // the ComputeNetworkAttachment.primary field, not from this binding.
  optional string nad_name = 2;

  // Namespace where VMs are placed (primary only — the k8s manager creates this).
  optional string namespace_name = 3;

  // Label key+value to add to the primary namespace so this
  // secondary network's CUDN/NAD namespace selector matches.
  optional string namespace_label_key = 4;
  optional string namespace_label_value = 5;
}
```

### ComputeNetworkAttachment for the Managed OOB Path

The repeated attachment shape remains the API surface. The managed OOB path
adds an optional primary marker and a provider-supplied static OOB address to
that attachment; it does not add a new resource type:

```protobuf
message ComputeNetworkAttachment {
  SubnetLocalReference subnet = 1;
  repeated SecurityGroupLocalReference security_groups = 2;
  optional bool primary = 3;
  // Provider-assigned static IPv4 address for a managed OOB attachment.
  optional string static_ipv4_address = 4;
}
```

And in `ComputeInstanceSpec`:

```protobuf
repeated ComputeNetworkAttachment network_attachments = 14;
```

For a single attachment, `primary` is optional and the attachment remains
implicitly primary. A multi-attachment VM requires exactly one
`primary: true`. The existing operator maximum of eight attachments is retained;
the first managed path supports the primary workload role and secondary OOB
attachment(s) on the one configured shared OOB VirtualNetwork. OOB static
addresses are immutable after creation. The provider-managed authorization
exception does not permit arbitrary cross-VirtualNetwork or cross-tenant
attachments.

### Workflow Description

The dispatcher and generic composition behavior below define the role-based
foundation from #393. The first managed OOB workflow changes the actor and
restricts the role combinations; see **OSAC-6121 Provider-Managed OOB Path** at
the end of this document for its authoritative provisioning sequence and
validation.

#### Dispatcher Behavior

When the Subnet controller dispatches provisioning, it traces:

```
Subnet "workload-sub"
  -> VN "my-workload-net" (network_type: "tenant")
    -> NetworkClass.network_types["tenant"]
      -> fabric_manager: "customer-fabric", k8s_manager: "cudn_evpn"

Subnet "oob-sub"
  -> VN "my-oob-net" (network_type: "secondary_vlan")
    -> NetworkClass.network_types["secondary_vlan"]
      -> k8s_manager: "cudn_localnet" (no fabric manager)
```

Same single NetworkClass, different managers per VN depending on the `network_type`.

#### K8s Manager Primary vs Secondary Role

A VM can only live in one namespace. The primary k8s manager owns the namespace; secondary
k8s managers provision resources into it.

**Primary k8s manager** (e.g., `cudn_evpn`):
- Creates namespace (name = subnet name)
- Creates CUDN with `role: Primary`
- VM lives in this namespace

**Secondary k8s manager** (e.g., `cudn_localnet`, `sriov`):
- Does NOT create a namespace
- Creates a CUDN with `role: Secondary` (generates NAD), or a SriovNetwork (generates NAD),
  or a direct NAD
- Uses `namespaceSelector` or targets specific namespaces via labels
- Optionally creates MultiNetworkPolicy for isolation

K8s manager ConfigMap capability declaration:

```yaml
# cudn_evpn
apiVersion: v1
kind: ConfigMap
metadata:
  name: k8s-manager-cudn-evpn
  namespace: osac
  labels:
    osac.openshift.io/network/k8s-manager: "true"
data:
  name: cudn_evpn
  description: "OVN-Kubernetes CUDN with EVPN transport"
  capabilities: "supports_ipv4:true,supports_ipv6:false"
  # supports_primary/secondary is NOT here — that depends on the
  # combination with a fabric manager, configured in NetworkType

---
# cudn_localnet
apiVersion: v1
kind: ConfigMap
metadata:
  name: k8s-manager-cudn-localnet
  namespace: osac
  labels:
    osac.openshift.io/network/k8s-manager: "true"
data:
  name: cudn_localnet
  description: "OVN-Kubernetes CUDN with localnet bridge to physical VLAN"
  capabilities: "supports_ipv4:true,supports_ipv6:false"

---
# sriov
apiVersion: v1
kind: ConfigMap
metadata:
  name: k8s-manager-sriov
  namespace: osac
  labels:
    osac.openshift.io/network/k8s-manager: "true"
data:
  name: sriov
  description: "SR-IOV passthrough for high-speed VM networking"
  capabilities: "supports_ipv4:true,supports_ipv6:false"
```

#### KubeVirt VM Composition

Given this ComputeInstance:

```yaml
ComputeInstance:
  spec:
    network_attachments:
      - subnet: "workload-sub"     # primary
        primary: true
      - subnet: "oob-sub-1"       # secondary — secondary_vlan, OOB VLAN 100
      - subnet: "oob-sub-2"       # secondary — secondary_vlan, OOB VLAN 200
      - subnet: "sriov-sub"       # secondary — SR-IOV high-speed
```

**Step 1: Resolve each attachment's binding from Subnet status and primary flag**

The VM reconciler reads `SubnetStatus.network_binding` for the binding method and NAD name,
and uses `ComputeNetworkAttachment.primary` to determine `pod: {}` vs `multus: {}`:

```
workload-sub  -> primary: true  + binding: l2bridge                       -> pod: {}
oob-sub-1     -> primary: false + binding: bridge, nad: "oob-vlan100-nad"  -> multus: { networkName: "oob-vlan100-nad" }
oob-sub-2     -> primary: false + binding: bridge, nad: "oob-vlan200-nad"  -> multus: { networkName: "oob-vlan200-nad" }
sriov-sub     -> primary: false + binding: sriov,  nad: "sriov-net-nad"    -> multus: { networkName: "sriov-net-nad" }
```

**Step 2: Label namespace for secondary networks**

The primary subnet's namespace (`workload-sub`) needs labels that match secondary CUDNs/NADs
namespace selectors. The VM reconciler adds labels from each secondary subnet's
`namespace_label_key` / `namespace_label_value`:

```yaml
Namespace "workload-sub":
  labels:
    virtual-network: "my-workload-net"  # existing — matches primary CUDN
    oob-vlan100: "true"                 # added — matches OOB VLAN 100 CUDN/NAD
    oob-vlan200: "true"                 # added — matches OOB VLAN 200 CUDN/NAD
    sriov-enabled: "true"               # added — matches SR-IOV NAD
```

**Step 3: Compose KubeVirt VM**

```yaml
apiVersion: kubevirt.io/v1
kind: VirtualMachine
metadata:
  name: my-vm
  namespace: workload-sub               # Primary subnet's namespace
spec:
  template:
    spec:
      domain:
        devices:
          interfaces:
            - name: tenant              # Primary — EVPN to fabric
              binding:
                name: l2bridge         # Primary UDN binding plugin
            - name: oob-1              # Secondary — OOB VLAN 100
              bridge: {}
            - name: oob-2              # Secondary — OOB VLAN 200
              bridge: {}
            - name: highspeed          # Secondary — SR-IOV
              sriov: {}
      networks:
        - name: tenant
          pod: {}                      # Primary UDN — pod network IS the CUDN
        - name: oob-1
          multus:
            networkName: oob-vlan100-nad   # NAD name from Subnet status
        - name: oob-2
          multus:
            networkName: oob-vlan200-nad
        - name: highspeed
          multus:
            networkName: sriov-net-nad
```

The asymmetry between primary and secondary:

| | Primary NIC | Secondary NIC(s) |
|---|---|---|
| **Determined by** | `ComputeNetworkAttachment.primary = true` | All other attachments |
| **KubeVirt network type** | `pod: {}` (derived from `primary` flag) | `multus: { networkName }` (derived from `primary` flag + `nad_name` from binding) |
| **How VM connects** | Pod network (which IS the primary CUDN) | Multus injects additional interface from NAD |
| **k8s manager creates** | CUDN with `role: Primary` -> namespace's pod network | CUDN with `role: Secondary` -> generates NAD, or direct NAD |
| **Namespace requirement** | k8s manager creates the namespace | Namespace must have matching label for NAD to be available |
| **KubeVirt binding** | `binding: { name: l2bridge }` (primary UDN plugin) | `bridge: {}` or `sriov: {}` (from `SubnetNetworkBinding.kubevirt_binding`) |

The reconciler does not hardcode any k8s-manager-specific logic. It reads the `primary` flag
from the attachment and `SubnetStatus.network_binding` from the subnet, then mechanically
composes the VM spec.

**Secondary CUDNs and NADs:** OVN-K secondary CUDNs (like those created by `cudn_localnet`) automatically generate a
`NetworkAttachmentDefinition` in each matching namespace. From KubeVirt's perspective, both
secondary CUDNs and direct NADs look the same — they are all referenced via
`multus: { networkName: "..." }`. The k8s manager's output binding tells the reconciler the
NAD name regardless of whether the underlying resource is a CUDN (which auto-generates NADs)
or a directly-created NAD.

### OOB Use Case: shared provider network with cudn_localnet

This role example is refined by the provider-managed workflow below. The
Provider Admin owns the single shared OOB VirtualNetwork. The fabric manager
configures its physical VLAN and publishes the handoff data; the localnet k8s
manager consumes that data to provision the Localnet CUDN. The VM reconciler
continues to consume only `SubnetNetworkBinding`.

For the customer's OOB management network — the `cudn_localnet` k8s manager (implementation)
serves the `secondary_vlan` network type (role), with MultiNetworkPolicy isolation:

```yaml
# cudn_localnet k8s manager creates at Subnet provisioning time:
ClusterUserDefinedNetwork:
  name: "oob-mgmt"
  spec:
    namespaceSelector:
      matchLabels:
        oob-enabled: "true"          # Namespaces opt-in via label
    network:
      topology: Localnet
      localnet:
        role: Secondary              # Not the primary network
        physicalNetworkName: "oob-physnet"
        ipam:
          mode: Disabled

---
# MultiNetworkPolicy for isolation (management server only)
MultiNetworkPolicy:
  name: "oob-isolate"
  metadata:
    annotations:
      k8s.v1.cni.cncf.io/policy-for: "oob-mgmt"
  spec:
    podSelector: {}
    policyTypes: [Ingress, Egress]
    ingress:
      - from:
          - ipBlock: { cidr: "172.16.0.1/32" }   # Management server only
    egress:
      - to:
          - ipBlock: { cidr: "172.16.0.1/32" }
```

When a VM is placed in the primary Subnet namespace, generic VM composition
applies the namespace label requirement from `SubnetNetworkBinding`. The
secondary CUDN's `namespaceSelector` matches only namespaces carrying that
provider-selected label, and the CUDN controller creates a local NAD in each
selected namespace. Multus therefore references a local NAD; it does not rely
on a cross-namespace NAD reference.

### How a Provider Implements a New Network Role

This is the key extensibility property. Adding a new role (e.g., "highspeed" using the `sriov`
k8s manager) is a **deploy-time operation** — no code changes to existing `cudn_evpn` or
`cudn_localnet` playbooks, no changes to the dispatcher, no changes to the VM reconciler.

#### What the Provider Delivers

**1. K8s manager ConfigMap (registration)**

```yaml
# osac-installer: charts/osac/templates/k8s-manager-sriov.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: k8s-manager-sriov
  namespace: osac
  labels:
    osac.openshift.io/network/k8s-manager: "true"
data:
  name: sriov
  description: "SR-IOV passthrough for high-speed VM networking"
  capabilities: "supports_ipv4:true,supports_primary:false,supports_secondary:true"
```

The dispatcher discovers k8s managers by label `osac.openshift.io/network/k8s-manager: "true"`.
Deploying this ConfigMap registers the new manager. No dispatcher code change.

**2. Ansible role (provisioning logic)**

```
collections/ansible_collections/osac/templates/roles/sriov/
+-- meta/
|   +-- osac.yaml              # Capability declaration
+-- tasks/
|   +-- create_subnet.yaml     # Creates SriovNetwork -> NAD
|   +-- delete_subnet.yaml     # Deletes SriovNetwork
+-- templates/
    +-- sriov_network.yaml.j2  # SriovNetwork CR template
```

**`meta/osac.yaml`:**

```yaml
---
k8s_manager: sriov
capabilities:
  supports_ipv4: true
  supports_ipv6: false
  # supports_primary/secondary not here — that's a property of the
  # NetworkType combination, configured by admin in NetworkClass
```

**`tasks/create_subnet.yaml`:**

```yaml
---
- name: Extract subnet details
  ansible.builtin.set_fact:
    subnet_name: "{{ osac_job_vars.resource.metadata.name }}"
    subnet_cidr: "{{ osac_job_vars.resource.spec.ipv4CIDR }}"
    tenant_id: "{{ osac_job_vars.resource.metadata.annotations['osac.openshift.io/tenant'] }}"

- name: Create SriovNetwork
  kubernetes.core.k8s:
    state: present
    definition:
      apiVersion: sriovnetwork.openshift.io/v1
      kind: SriovNetwork
      metadata:
        name: "{{ subnet_name }}-sriov"
        namespace: openshift-sriov-network-operator
        annotations:
          osac.openshift.io/tenant: "{{ tenant_id }}"
          osac.openshift.io/owner-reference: "Subnet/{{ subnet_name }}"
      spec:
        resourceName: "sriov_netdevice"        # Matches SriovNetworkNodePolicy
        networkNamespace: ""                    # NAD created cluster-wide
        ipam: |
          {
            "type": "whereabouts",
            "range": "{{ subnet_cidr }}"
          }

- name: Wait for NAD to be created
  kubernetes.core.k8s_info:
    api_version: k8s.cni.cncf.io/v1
    kind: NetworkAttachmentDefinition
    name: "{{ subnet_name }}-sriov"
  register: nad_check
  until: nad_check.resources | length > 0
  retries: 15
  delay: 5

# Output contract — tells the VM reconciler how to attach this network
- name: Report binding info
  ansible.builtin.set_stats:
    data:
      kubevirt_binding: "sriov"
      nad_name: "{{ subnet_name }}-sriov"
      namespace_label_key: "sriov-{{ subnet_name }}"
      namespace_label_value: "true"
```

**`tasks/delete_subnet.yaml`:**

```yaml
---
- name: Delete SriovNetwork
  kubernetes.core.k8s:
    api_version: sriovnetwork.openshift.io/v1
    kind: SriovNetwork
    name: "{{ osac_job_vars.resource.metadata.name }}-sriov"
    namespace: openshift-sriov-network-operator
    state: absent
```

**3. RBAC for the new role**

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: osac-aap-sriov
rules:
- apiGroups: ["sriovnetwork.openshift.io"]
  resources: ["sriovnetworks"]
  verbs: ["create", "get", "list", "watch", "update", "patch", "delete"]
- apiGroups: ["k8s.cni.cncf.io"]
  resources: ["network-attachment-definitions"]
  verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: osac-aap-sriov
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: osac-aap-sriov
subjects:
- kind: ServiceAccount
  name: osac-aap-runner
  namespace: osac
```

**4. Admin registers the type in the NetworkClass**

```yaml
NetworkClass "prod-region-1":
  network_types:
    - name: "tenant"
      fabric_manager: "customer-fabric"
      k8s_manager: "cudn_evpn"
      supports_primary: true
      supports_secondary: false
    - name: "secondary_vlan"
      k8s_manager: "cudn_localnet"
      supports_primary: false
      supports_secondary: true
    # NEW — added by provider, no existing code touched
    - name: "highspeed"
      k8s_manager: "sriov"
      supports_primary: false
      supports_secondary: true
```

#### What the Provider Does NOT Touch

| Artifact | Changed? | Why |
|----------|----------|-----|
| `cudn_evpn` Ansible role | No | Handles "tenant" role independently |
| `cudn_localnet` Ansible role | No | Handles "secondary_vlan" role independently |
| `netris` or other fabric manager role | No | Independent provisioning |
| Subnet controller / dispatcher code | No | Routes by `network_type` name generically |
| VM reconciler | No | Reads `SubnetStatus.network_binding` generically |
| Proto definitions | No manager-specific additions | The generic binding remains reusable; OSAC-6121 adds primary and static OOB fields to the existing ComputeNetworkAttachment |

The contract between the k8s manager and the rest of OSAC is the **output binding** written
to Subnet status:

```
{ kubevirt_binding, nad_name, namespace_name, namespace_label_* }
```

The VM reconciler determines `pod: {}` vs `multus: {}` from the `ComputeNetworkAttachment.primary`
field — this is not part of the k8s manager's output.

Any k8s manager that produces this output works with the existing VM reconciler. The dispatcher
routes to the manager by name (from the `network_types` entry), and the manager's Ansible role
does whatever it needs internally — create a CUDN, create an SriovNetwork, create a raw NAD,
create a Multus config — as long as its `set_stats` output conforms to the binding contract,
everything downstream works mechanically.

This is decision #11 ("Pluggable managers via ConfigMap: Adding a new manager = deploy ConfigMap
\+ Ansible role, no manager-specific API changes required") extended to the multi-NIC case.

### API Extensions

**NetworkClass proto (`network_class_type.proto`):**
- Add `repeated NetworkType network_types = 13` field
- Add `NetworkType` message with `name`, `title`, `fabric_manager`, `k8s_manager`,
  `supports_primary`, `supports_secondary`
- `supports_primary`/`supports_secondary` are on NetworkType (property of the manager
  combination), while intrinsic capabilities (IPv4/IPv6) stay on the k8s manager ConfigMap

**VirtualNetwork proto (`virtual_network_type.proto`):**
- Add `optional string network_type = 5` to `VirtualNetworkSpec` (OPTIONAL, IMMUTABLE)

**Subnet proto (`subnet_type.proto`):**
- Add `optional SubnetNetworkBinding network_binding = 4` to `SubnetStatus`
- Add `SubnetNetworkBinding` message

For this VMaaS follow-up, add optional `primary` and provider-supplied
`static_ipv4_address` fields to `ComputeNetworkAttachment`; preserve the existing
repeated field and legacy single-IP status. Add per-attachment status correlation
to the existing ComputeInstance status shape if the current implementation does
not already expose it. Do not change `BareMetalNetworkAttachment` or BMaaS.
Existing NetworkClass (`fabric_manager`, `k8s_manager`) fields remain for
backward compatibility. The capability controller publishes
`supports_multi_nic` only when every manager in the configured primary and OOB
paths advertises it; tenants cannot override it.

### Generic Role-Framework Example

The following tenant-created examples illustrate the extensible role framework
proposed in the original design. They are not the OSAC-6121 first-cut workflow:
the managed OOB flow below requires the Provider Admin to create the networks
and ComputeInstance, and tenants cannot request or manage OOB attachments.

```yaml
# 1. Tenant creates VirtualNetworks per role (all reference the single NetworkClass)
VirtualNetwork:
  name: "my-workload-net"
  spec:
    network_class: "prod-region-1"
    network_type: "tenant"
    ipv4_cidr: "10.0.0.0/16"

VirtualNetwork:
  name: "my-oob-net"
  spec:
    network_class: "prod-region-1"
    network_type: "secondary_vlan"      # Role — OOB is one use of secondary_vlan
    ipv4_cidr: "172.16.0.0/24"

VirtualNetwork:
  name: "my-sriov-net"
  spec:
    network_class: "prod-region-1"
    network_type: "highspeed"
    ipv4_cidr: "192.168.0.0/24"

# 2. Tenant creates Subnets
Subnet: { name: "work-sub",  spec: { virtual_network: "my-workload-net", ipv4_cidr: "10.0.1.0/24" } }
Subnet: { name: "oob-sub",   spec: { virtual_network: "my-oob-net",     ipv4_cidr: "172.16.0.0/24" } }
Subnet: { name: "sriov-sub", spec: { virtual_network: "my-sriov-net",   ipv4_cidr: "192.168.0.0/24" } }

# 3. Provisioning dispatches to different managers per network_type:
# work-sub  -> dispatcher -> customer-fabric + cudn_evpn (creates namespace + CUDN Primary)
# oob-sub   -> dispatcher -> cudn_localnet only (creates CUDN Secondary + MultiNetworkPolicy)
# sriov-sub -> dispatcher -> sriov only (creates SriovNetwork -> NAD)
# Note: "secondary_vlan" is the role, "cudn_localnet" is the k8s manager implementation

# 4. VM with multi-NIC
ComputeInstance:
  name: "my-vm"
  spec:
    network_attachments:
      - subnet: "work-sub"    # Primary — EVPN to fabric
        primary: true
      - subnet: "oob-sub"     # Secondary — secondary_vlan (OOB use case)
      - subnet: "sriov-sub"   # Secondary — highspeed (SR-IOV)
```

### Security Considerations

**Tenant Isolation:**
- All resources include standard tenant isolation metadata (`osac.openshift.io/tenant`,
  `osac.openshift.io/owner-reference`)
- OPA policies enforce read/write isolation at the fulfillment-service API layer
- The primary workload VirtualNetwork remains tenant-scoped. The one provider-owned
  OOB VirtualNetwork is the sole cross-tenant attachment exception, and fulfillment
  permits it only for provider-managed VM creation and only for the configured shared
  OOB network. Tenants cannot attach arbitrary provider networks.

**OOB Isolation:**
- MultiNetworkPolicy enforced by the `cudn_localnet` k8s manager restricts inter-VM traffic
  on the OOB network
- Only the designated management server IP can reach VMs through the OOB interface
- VMs cannot communicate with each other via the OOB network

**Secondary Network Namespace Access:**
- Secondary networks are attached to namespaces via label selectors
- The VM reconciler only adds labels for subnets explicitly referenced in the
  ComputeInstance's `network_attachments`
- Tenant-created secondary-network attachments remain subject to ownership validation.
  The managed OOB exception is provider-authorized and does not grant tenants rights
  to create the shared network, change its address allocation, or weaken its policy.

**No New Attack Surface:**
- Tenants interact only via the fulfillment-service API (existing auth/authz)
- K8s manager CRDs (CUDN, SriovNetwork, NAD) are cluster-scoped, managed by AAP
  service account, not directly accessible to tenants

### Validation Rules

The rules below describe the generic role framework. The capability gate, narrow
provider authorization, static address, and first-cut role restrictions in the
OSAC-6121 managed workflow at the end of this document are additionally required.

At ComputeInstance creation:

1. For multiple attachments, exactly one attachment has `primary: true`; with a
   single attachment, the primary is implicit and the marker is optional.
2. Primary attachment's VN must have a `network_type` where `supports_primary: true`
3. Secondary attachments' VNs must have a `network_type` where `supports_secondary: true`
4. All referenced subnets must be in READY state with `network_binding` populated
5. The generic role framework may allow multiple secondaries of the same
   `network_type`; the OSAC-6121 managed OOB path additionally restricts them
   to the configured shared OOB VirtualNetwork.
6. No two attachments may reference the same Subnet (prevents duplicate NICs)

At VirtualNetwork creation:

1. If `network_type` is specified, it must match an entry in the NetworkClass's
   `network_types` list
2. If `network_type` is omitted, the NetworkClass must have top-level
   `fabric_manager` and/or `k8s_manager` set (backward compat)

At Subnet creation:

1. Parent VirtualNetwork's `network_type` determines which managers handle provisioning
2. Existing type-specific validations still apply (e.g., single-subnet constraint for
   `cudn_evpn` from OSAC-4291)

### Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| **Namespace label race** — two VMs created simultaneously, both add secondary labels to same namespace | Labels are additive and idempotent. Concurrent label additions do not conflict. |
| **Secondary CUDN selector too broad** — matches unintended namespaces | K8s manager uses specific label key+value pairs (from `SubnetNetworkBinding`). VM reconciler only adds exact labels from the subnets referenced in the ComputeInstance. |
| **K8s manager output contract violation** — new manager missing required fields | Subnet controller validates all `SubnetNetworkBinding` fields before setting Subnet to READY. Missing fields -> Subnet stays in FAILED state. |
| **Backward compatibility** — existing VNs without `network_type` break | Top-level `fabric_manager`/`k8s_manager` on NetworkClass preserved. Omitting `network_type` uses those defaults. Zero behavioral change for existing resources. |
| **NetworkClass complexity** — admin must configure all network types upfront | NetworkClass is a deployment-level admin resource (decision #6). Complexity is at the admin level, not tenant-facing. Types can be added incrementally. |

### Drawbacks

**Increased NetworkClass complexity:** The NetworkClass now describes multiple manager
configurations instead of one. This is admin-facing complexity, not tenant-facing, but it
increases the configuration surface.

**Trade-off justification:** The alternative — multiple NetworkClasses — violates decision #6
and would require significant rework of the dispatcher, default networking provisioning, and
tenant onboarding. The `network_types` extension preserves the single-NetworkClass model
while enabling per-role manager dispatch.

**Namespace labeling coupling:** The VM reconciler must add labels to the primary namespace
for secondary networks. This creates a coupling between VM creation and namespace management.

**Trade-off justification:** This is the standard Kubernetes pattern for CUDN/NAD namespace
targeting. OVN-K CUDNs use `namespaceSelector` with labels; the VM reconciler simply manages
those labels declaratively based on `SubnetNetworkBinding` output.

### What Changes in Existing Designs

| Area | Change |
|------|--------|
| **NetworkClass proto** | Add `repeated NetworkType network_types` field |
| **VirtualNetwork proto** | Add `optional string network_type` to spec |
| **Subnet proto** | Add `optional SubnetNetworkBinding network_binding` to status |
| **ComputeInstance API** | Add optional `primary` and provider-supplied static OOB IPv4 address to the existing `ComputeNetworkAttachment`; expose per-attachment IP status |
| **Dispatcher** | Route based on `(NetworkClass, VN.network_type)` instead of just `(NetworkClass)` |
| **K8s manager capability declarations** | Keep role position support on `NetworkType`; advertise manager `supports_multi_nic` for capability intersection |
| **VM reconciler** | Read `SubnetStatus.network_binding` to compose VM `spec.template.spec.networks[]` + `spec.template.spec.domain.devices.interfaces[]` |
| **VM reconciler** | Label primary namespace for secondary network selectors |
| **Localnet manager and fabric handoff** | Consume versioned fabric output, provision Localnet CUDN/NAD, and publish binding data |
| **Networking decisions doc** | Decision #6 stays (one NC per deployment), but NC now declares multiple network types |

Existing `fabric_manager`/`k8s_manager` fields on NetworkClass are kept for backward
compatibility. The CUDN+EVPN Phase 1 design (OSAC-4291) is unchanged as the "tenant"
network type implementation.

## Alternatives (Not Implemented)

### Alternative 1: Multiple NetworkClasses Per Deployment

**Approach:** Remove decision #6 (one NetworkClass per deployment). Create separate
NetworkClasses per role: `nc-tenant-evpn`, `nc-oob-localnet`, `nc-sriov`.

**Pros:**
- Simpler NetworkClass structure (one manager pair each)
- Each NetworkClass is independent

**Cons:**
- Violates established architecture decision #6
- Breaks default networking auto-provisioning (which NetworkClass is the default?)
- Breaks tenant onboarding (tenants don't interact with NetworkClasses)
- Requires rework of dispatcher, which assumes one NC per deployment
- Proliferates admin objects

**Rejection reason:** The single-NetworkClass model is a load-bearing architectural decision.
Extending it with `network_types` achieves the same result without the blast radius.

### Alternative 2: Network Type on Subnet Instead of VirtualNetwork

**Approach:** Put `network_type` on SubnetSpec instead of VirtualNetworkSpec. Different
subnets within the same VN could use different managers.

**Pros:**
- More flexible (mixed types within one VN)
- Fewer VirtualNetworks

**Cons:**
- A VirtualNetwork with mixed subnet types has ambiguous manager semantics
- Breaks the conceptual model: a VN is a network of a specific type
- Complicates VN-level operations (SecurityGroup, NATGateway) — which manager handles them?
- Cloud providers (GCP, AWS, Azure) all model this at the VPC/VNet level, not the subnet level

**Rejection reason:** A VirtualNetwork conceptually IS a network of a specific type. Mixing
types within one VN creates ambiguity. The GCP model (each NIC in a separate VPC) validates
the VN-level approach.

### Alternative 3: Per-NIC Manager Override

**Approach:** Add `k8s_manager` override field directly on `ComputeNetworkAttachment`.
The VM specifies which manager handles each NIC.

**Pros:**
- Maximum flexibility per NIC
- No VirtualNetwork or NetworkClass changes

**Cons:**
- Tenants must know about k8s managers (violates abstraction)
- Bypasses the NetworkClass dispatch model entirely
- No Subnet-level provisioning — manager selection happens at VM creation time
- No way to pre-provision network infrastructure (CUDNs, NADs) at subnet time

**Rejection reason:** Breaks the fundamental abstraction that tenants don't interact with
manager details. Network infrastructure should be provisioned at Subnet time, not VM time.

## Open Questions

The original questions below concern the broader role framework. For the
managed OOB implementation, the questions under **Open questions for
implementation** below are the current decision points.

### 1. Default Networking with Network Types

**Owner:** Networking team

**Impact:** Tenant onboarding flow

When default networking auto-provisioning creates a VN + Subnet for a new tenant (decision #12),
which `network_type` does it use? The most likely answer is that the default VN uses the
top-level `fabric_manager`/`k8s_manager` (no `network_type` set), preserving backward
compatibility. But should the admin be able to configure default secondary networks (e.g.,
auto-provision an OOB network for every tenant)?

### 2. SecurityGroup and NATGateway Scope

**Owner:** Networking team

**Impact:** API validation

SecurityGroups and NATGateways are scoped to a VirtualNetwork. For future secondary network types
(e.g., SR-IOV), support remains to be decided. In the OSAC-6121 managed OOB path, isolation is
provider-controlled with MultiNetworkPolicy, and ExternalIP/NAT continue to target the primary
attachment only. Secondary-type-specific SG/NAT behavior outside this OOB path remains open.

### 3. BareMetalInstance Multi-NIC with Network Types

**Owner:** BMaaS team

**Impact:** `BareMetalNetworkAttachment` validation

`BareMetalNetworkAttachment` already has an `interface` field for physical NIC binding. With
network types, a bare-metal instance could have NICs on different network types (e.g., tenant
on `eno1`, OOB on `eno2`). The `interface` field maps to the physical NIC, but the
`network_type` determines the backend. How do these interact? Does the fabric manager handle
all BM NICs, or does the k8s manager for the network type get involved?

## Test Plan

### Unit Tests

**fulfillment-service:**
- VirtualNetwork creation with valid `network_type` succeeds
- VirtualNetwork creation with unknown `network_type` fails with 400
- VirtualNetwork creation without `network_type` uses defaults (backward compat)
- ComputeInstance with primary attachment on `supports_primary: false` type fails
- ComputeInstance with secondary attachment on `supports_secondary: false` type fails
- A single attachment without `primary: true` succeeds as implicitly primary
- A multi-attachment VM without exactly one primary fails

**osac-operator:**
- Dispatcher routes to correct managers based on VN `network_type`
- Dispatcher uses top-level defaults when `network_type` is not set
- Subnet controller writes `network_binding` from k8s manager `set_stats` output
- Subnet controller validates `network_binding` fields before setting READY
- VM reconciler composes VM with correct `networks[]` and `interfaces[]` from binding
- VM reconciler adds namespace labels for secondary network selectors
- VM reconciler removes namespace labels when VM is deleted (if no other VMs need them)

### Integration Tests

- Create NetworkClass with multiple `network_types`
- Create VNs with different `network_type` values, verify dispatcher routes correctly
- Create multi-NIC VM, verify KubeVirt VM has correct network/interface entries
- Verify secondary CUDN NAD is available in primary namespace after label addition
- Verify OOB MultiNetworkPolicy blocks inter-VM traffic

## Graduation Criteria

- **Role framework:** Ship the NetworkClass network type mapping and
  `SubnetNetworkBinding` contract with backward-compatible defaults.
- **OSAC-6121 managed OOB:** Enable only after the CUDN+EVPN primary path, the
  shared OOB Localnet path, manager capability intersection, static guest
  addressing, feedback, and isolation pass integration and E2E coverage.
- **Later extensions:** SR-IOV, BMaaS, multi-cluster, tenant-created OOB, and
  additional network roles require separate scope and design review.

### OSAC-6121 Provider-Managed OOB Path

This section defines the first managed-VM implementation built on the role
framework above. It replaces the earlier Phase 2 proposal that introduced a
`tenant_managed` NetworkType field. No such field or new resource type is
required: the Provider Admin owns the shared OOB VirtualNetwork, and
fulfillment authorizes its use based on the provider-managed ComputeInstance
request and the configured shared-network identity.

#### Scope and attachment model

- The feature applies to VMaaS managed ComputeInstances. The Provider Admin
  creates the primary and OOB VirtualNetworks, their Subnets and required
  SecurityGroups, reserves the OOB address, and creates the ComputeInstance.
  The Tenant User receives and uses the VM; tenant-created OOB selection is a
  later option.
- One NetworkClass remains configured per deployment. The primary workload
  VirtualNetwork uses a role mapped to the CUDN plus EVPN path. One shared OOB
  VirtualNetwork uses a role mapped to a localnet k8s manager such as
  `cudn_localnet`. Every managed VM needing OOB attaches to a Subnet in that
  same shared OOB VirtualNetwork.
- The provider-controlled `supports_multi_nic` capability is false unless all
  managers required by both role paths advertise support. When false or unset,
  fulfillment rejects requests with more than one attachment before
  persistence. When true, preserve the operator maximum of eight attachments.
  For a multi-attachment request, exactly one attachment has
  `primary: true`; a single attachment remains implicitly primary. The first
  managed role profile accepts the primary workload role and OOB secondary
  role(s) on the configured shared OOB VirtualNetwork only. It rejects
  arbitrary cross-VirtualNetwork combinations and unsupported roles.
- The VMaaS attachment set, Subnet references, primary designation, and OOB
  static address are immutable after creation. CaaS, BMaaS, cross-VN use beyond
  the shared OOB exception, and hot-plug are out of scope.

#### NetworkClass capability and role mapping

The existing NetworkClass `network_types` maps each unique role name to a
`(fabric_manager, k8s_manager)` pair and declares `supports_primary` and
`supports_secondary`. A role may use the same manager implementation as another
role; role names express purpose. Position validation occurs after resolving
the attachment's primary/secondary position. The primary role must resolve to
CUDN plus EVPN and support primary placement. The OOB role must resolve to the
fabric/localnet pair and support secondary placement. Multi-attachment
VirtualNetworks must explicitly set `network_type`; an omitted type continues
to use the legacy top-level manager defaults for the single-attachment path.

Each involved manager advertises `supports_multi_nic` in its existing manager
capability declaration. The capabilities controller publishes the computed
capability using its existing intersection behavior. The capability remains
false if any primary or OOB fabric/k8s manager is missing, does not advertise
support, or lacks a deployed localnet implementation, guest configuration,
feedback, or binding path. A provider may disable the computed capability;
tenants cannot set or override it.

Network type names are unique within a NetworkClass. VirtualNetwork
`network_type` is immutable, and unknown roles are rejected. Existing
NetworkClasses without role mappings retain their current single-NIC behavior.

#### Provider Admin workflow and fabric handoff

1. The Provider Admin configures the single NetworkClass with the primary
   CUDN+EVPN role and OOB localnet role, then creates the primary workload
   VirtualNetwork and Subnet.
2. The Provider Admin creates the one shared OOB VirtualNetwork and its Subnet
   with the OOB role. The same OOB VirtualNetwork is reused by multiple managed
   VMs; each VM receives an interface on its selected OOB Subnet.
3. Installer/AAP configures the worker OVS bridge and OVN bridge mapping for
   the declared physical network. The fabric manager configures the VLAN/network
   on the switches. After successful fabric configuration, it publishes
   validated output through the existing fabric-to-k8s-manager handoff pattern
   used for VNI data (the OSAC-4291 ConfigMap/job dependency pattern or an
   equivalent contract).
4. The handoff is a versioned, OSAC-managed contract. It carries the stable
   physical network name, VLAN/tag information when applicable, bridge mapping
   identity, and readiness needed by the localnet manager. It contains no
   credentials. The exact key names and schema version must be documented in
   the manager contract before capability advertisement.
5. The localnet k8s manager consumes the fabric output and creates a
   cluster-scoped Localnet CUDN with `role: Secondary`, the matching
   `physicalNetworkName`, and IPAM disabled when the provider supplies static
   guest IPs. Its `namespaceSelector` matches a generic OOB request label
   supplied through `SubnetNetworkBinding`. The CUDN controller creates the
   corresponding NAD in each selected VM namespace.
6. The Subnet becomes READY only after validated handoff data, the node bridge
   mapping, the CUDN, and the required binding fields are ready. When a VM
   namespace is selected later, its provisioning waits for the local NAD to be
   present there before creating the VM.
7. The Provider Admin reserves a static IPv4 address from the OOB allocation
   source and creates the ComputeInstance with its primary workload attachment
   and optional OOB attachment. The provider remains responsible for the
   address reservation and authorization to use the shared OOB VirtualNetwork.

Missing, malformed, stale, or mismatched handoff output leaves the Subnet
unready with an actionable condition. Missing per-VM NAD readiness blocks only
that VM and is reported on its ComputeInstance condition.

#### Binding contract and KubeVirt composition

The generic VM reconciler reads `SubnetNetworkBinding` from each attached
Subnet. It does not inspect `k8s_manager`, create CUDNs/NADs, or contain
manager-specific branches. Binding data must be validated before a Subnet is
marked READY: the primary binding has a supported nonempty KubeVirt binding;
a secondary has a supported binding, NAD name, and a paired namespace label
key/value; and optional namespace information is internally consistent.
Conflicting label requirements from attachments are rejected before namespace
mutation. Compatible labels are applied to the primary Subnet namespace and
removed only when no remaining VM attachment requires them.

The VM stays in the primary Subnet namespace. The AAP template loops over the
attachments and emits:

- **Primary:** one `pod: {}` network and an interface using the
  binding-provided primary KubeVirt binding, currently `l2bridge`.
- **Secondary:** a `multus` network referencing the binding-provided NAD name
  local to the VM namespace and a classic `bridge: {}` interface.

The OOB Localnet CUDN is secondary, so it coexists with the primary pod
network. No cross-namespace Multus reference is used. The namespace label is
manager-neutral; the same key/value from the binding is used by the VM
reconciler and the CUDN `namespaceSelector`.

#### Static OOB addressing, status, and routing

The provider supplies an OOB `static_ipv4_address` on the existing
`ComputeNetworkAttachment`. The VM template injects this address into the OOB
guest interface using the supported guest network-data path (cloud-init for
supported Linux templates; a Windows template is supported only after its
Sysprep/Unattend equivalent is implemented and tested). The address must be
inside the OOB Subnet CIDR and reserved uniquely before persistence. No new
resource type is introduced for the address.

Feedback correlates VMI interface identity with the configured attachment and
Subnet reference; it must not rely on interface list order. Existing
per-attachment status reports each Subnet and its discovered IP, while the
legacy single-IP view continues to expose the primary IP. The OOB status address
must agree with the injected static address before the managed VM is considered
network-ready. Delayed guest-agent reporting remains pending and retries rather
than assigning an address to the wrong attachment.

The primary attachment remains the guest default route. ExternalIP inbound
DNAT targets the primary attachment's discovered IP, and NATGateway egress
remains scoped to the primary VirtualNetwork and route. Do not install an OOB
default gateway. Directly connected OOB clients use the connected OOB route;
any remote OOB client prefixes require provider-supplied routes through the OOB
interface. The source and encoding for those routes remain an implementation
question and must not replace the primary default route.

#### Security, ownership, and validation

Fulfillment validates the request before persistence. The primary Subnet must
be READY and belong to the ComputeInstance tenant. The OOB Subnet must be READY
and belong to the configured shared OOB VirtualNetwork; only the provider
managed-VM identity may use this cross-tenant network exception. Validate role
support by attachment position, manager capability, unique Subnet references,
SecurityGroup readiness and VirtualNetwork alignment, OOB CIDR membership, and
address reservation. Invalid requests must not persist a ComputeInstance or an
auto-created dependent ExternalIP.

The shared OOB network uses provider-owned isolation rules. Any
MultiNetworkPolicy intended to isolate OOB traffic must include the
`k8s.v1.cni.cncf.io/policy-for` annotation naming the OOB NAD so the policy
applies to the secondary interface; verify this on the supported OpenShift
version. Tenant-supplied policy or SecurityGroup changes cannot weaken policy
for other users of the shared OOB network. OSAC-managed resources retain the
`osac.openshift.io/tenant` and `osac.openshift.io/owner-reference` metadata
where supported.

The CRD retains `MaxItems=8` and uniqueness by Subnet. Admission CEL may enforce
that multiple attachments have exactly one primary and that immutable
attachment fields do not change. Fulfillment remains authoritative for
capability, provider identity, role and ownership, readiness, SecurityGroup
alignment, and static-address reservation. A single attachment is valid
without a primary marker and remains implicitly primary. SecurityGroup update
behavior stays unchanged.

#### Open questions for implementation

1. Which provider IPAM or reservation system guarantees uniqueness for static
   OOB IPv4 addresses?
2. Which guest OS templates are supported in the first release, and what
   tested Sysprep/Unattend path is required for Windows?
3. Where will the provider-managed workflow configure the identity/reference of
   the one shared OOB VirtualNetwork?
4. Which remote OOB client prefixes must be reachable, and how will routes or
   policy-routing inputs be supplied without replacing the primary default
   route? Until answered and tested, directly connected OOB clients define the
   supported reachability boundary.
5. Where will the provider declare the physical network name and any VLAN/tag
   data consumed by the fabric manager and installer/AAP worker configuration?
   The versioned handoff contract must be documented before capability is
   advertised; the exact NetworkClass/configuration shape remains open.

#### Required changes to existing designs and context

- Update [OSAC-1435 VMaaS Networking](../OSAC-1435-vmaas-networking/design.md)
  to preserve the single-NIC baseline while documenting the capability-gated
  managed primary-plus-shared-OOB extension, primary-only ExternalIP/NAT, and
  create-time-only attachments.
- Update `osac/docs/agent-context/networking-decisions.md` to record the single
  shared OOB VirtualNetwork, provider-admin ownership, role-to-manager
  selection, and fabric-to-k8s-manager handoff. This workspace file is in the
  separate `osac` repository and will be published through its own change.
- Do not add a tenant `--enable-oob` flow in the first increment.

#### Test plan for the managed path

- Capability is false for missing/incomplete primary or OOB manager declarations
  and when provider-disabled; it becomes true only after both paths and all VM
  template/status dependencies are ready.
- With capability disabled, multi-attachment requests fail before persistence;
  default networking and one-attachment behavior remain unchanged.
- Validate unknown/duplicate roles, unsupported primary/secondary positions,
  arbitrary cross-VN attachments, unready or foreign Subnets, misaligned
  SecurityGroups, missing/multiple primary markers, duplicate Subnets,
  invalid/unreserved OOB addresses, more than eight attachments, and immutable
  updates.
- Create a managed VM with primary EVPN and secondary Localnet. Verify the
  primary `l2bridge`, local secondary NAD and `bridge: {}`, static OOB address,
  per-attachment status, and primary-only default route and ExternalIP target.
- Use the same shared OOB VirtualNetwork for multiple VMs; verify their primary
  namespaces receive the local NAD while an unrelated namespace does not.
- Verify the fabric handoff gates localnet provisioning and that missing or
  malformed output keeps the Subnet unready. Verify missing per-VM NAD blocks
  only the affected VM.
- Verify MultiNetworkPolicy targets the OOB NAD and OOB return traffic uses the
  OOB interface for directly connected clients and any configured remote
  prefixes.

The localnet k8s manager is a required implementation, whether OSAC-owned or
provider-owned. Keep `supports_multi_nic` disabled until the full handoff,
Localnet CUDN/NAD, static guest addressing, feedback, and isolation paths pass
integration and end-to-end tests.

## Upgrade / Downgrade Strategy

**Upgrade:**
- Add `network_types` to NetworkClass (additive, no migration)
- Existing VirtualNetworks without `network_type` continue using top-level defaults
- New VirtualNetworks can specify `network_type` to use new manager pairings
- `SubnetNetworkBinding` populated for newly provisioned subnets; existing subnets
  get binding populated on next reconcile

**Downgrade:**
- Remove `network_types` from NetworkClass
- VirtualNetworks with `network_type` set become invalid (field ignored, falls back to defaults)
- Secondary subnets provisioned by non-default managers may become orphaned (manual cleanup)
- Multi-NIC VMs continue running but cannot be recreated without `network_type` support

---

## Provenance

Authored: revise @ design 0.8.0 - 7efcedb, workspace design/OSAC-6121-vmaas-multi-nic @ 8a1340b (30 behind origin/main, dirty)
Phases: revise, revise

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.8.0","ai_workflows":"7efcedb","source_repo":"8a1340b (dirty)","source_repo_branch":"design/OSAC-6121-vmaas-multi-nic","commits_behind_main":30,"commits_ahead_main":0,"main_ref":"main","phases":["revise","revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":true} -->
