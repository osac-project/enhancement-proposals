---
title: multi-nic-role-based-network-types
authors:
  - Alona Kaplan
creation-date: 2026-10-18
last-updated: 2026-10-18
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-6121
see-also:
  - "/enhancements/OSAC-1433-unified-networking-architecture"
  - "/enhancements/OSAC-4291-cudn-evpn-k8s-manager-phase-1-networking"
  - "/enhancements/OSAC-1435-vmaas-networking"
  - "/enhancements/OSAC-1437-bmaas-networking"
replaces:
  - "N/A"
superseded-by:
  - "N/A"
---

# Multi-NIC with Role-Based Network Types

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

Each role requires a different k8s manager implementation (`cudn_evpn`, `cudn_localnet`, `sriov`,
etc.) and potentially a different or no fabric manager. The current model — one
`fabric_manager` + one `k8s_manager` per NetworkClass — cannot express this.

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
status. The VM reconciler reads it when composing the KubeVirt VM. No extra ConfigMap needed
for k8s manager output — the only ConfigMap in the chain is the existing fabric-to-k8s inter-job
one for VNI data (from OSAC-4291).

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
  // KubeVirt interface binding method: "l2-bridge" (primary UDN),
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

### No Changes to ComputeNetworkAttachment

The existing proto already supports multi-NIC:

```protobuf
// Already exists — no changes
message ComputeNetworkAttachment {
  SubnetLocalReference subnet = 1;
  repeated SecurityGroupLocalReference security_groups = 2;
}
```

And in `ComputeInstanceSpec`:

```protobuf
// Already exists — no changes
repeated ComputeNetworkAttachment network_attachments = 14;
```

Different attachments can reference subnets from different VirtualNetworks (which have
different `network_type` values and thus route to different managers). The `primary` field
on the attachment (from decision #9) designates the default gateway NIC.

Multiple secondary attachments of the same `network_type` are allowed (e.g., two
`secondary_vlan` NICs on different VLANs in different VirtualNetworks — one for OOB, one for
storage). There is no "one NIC per type" constraint.

### Workflow Description

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
workload-sub  -> primary: true  + binding: l2-bridge                       -> pod: {}
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
                name: l2-bridge         # Primary UDN binding plugin
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
| **KubeVirt binding** | `binding: { name: l2-bridge }` (primary UDN plugin) | `bridge: {}` or `sriov: {}` (from `SubnetNetworkBinding.kubevirt_binding`) |

The reconciler does not hardcode any k8s-manager-specific logic. It reads the `primary` flag
from the attachment and `SubnetStatus.network_binding` from the subnet, then mechanically
composes the VM spec.

**Secondary CUDNs and NADs:** OVN-K secondary CUDNs (like those created by `cudn_localnet`) automatically generate a
`NetworkAttachmentDefinition` in each matching namespace. From KubeVirt's perspective, both
secondary CUDNs and direct NADs look the same — they are all referenced via
`multus: { networkName: "..." }`. The k8s manager's output binding tells the reconciler the
NAD name regardless of whether the underlying resource is a CUDN (which auto-generates NADs)
or a directly-created NAD.

### OOB Use Case: secondary_vlan with cudn_localnet

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
      topology: Layer2
      layer2:
        role: Secondary              # Not the primary network
        subnets: ["172.16.0.0/24"]
        localnet: "oob-bridge"       # Bridge to physical OOB VLAN

---
# MultiNetworkPolicy for isolation (management server only)
MultiNetworkPolicy:
  name: "oob-isolate"
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

When a VM is placed in namespace `workload-sub`, the VM reconciler adds label
`oob-enabled: "true"` (from `SubnetNetworkBinding.namespace_label_key/value`).
The secondary CUDN's `namespaceSelector` matches, and the OOB network becomes available
as a secondary interface in that namespace.

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
| Proto definitions | No | `SubnetNetworkBinding` contract is generic for any k8s manager |

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
\+ Ansible role, no API changes required") extended to the multi-NIC case.

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

**No changes** to `ComputeNetworkAttachment`, `BareMetalNetworkAttachment`, `ComputeInstanceSpec`,
or any existing k8s manager ConfigMap schema. Existing fields on NetworkClass (`fabric_manager`,
`k8s_manager`) are kept for backward compatibility.

### Concrete Tenant Flow

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
- Each VirtualNetwork is tenant-scoped; cross-tenant network attachment is not possible

**OOB Isolation:**
- MultiNetworkPolicy enforced by the `cudn_localnet` k8s manager restricts inter-VM traffic
  on the OOB network
- Only the designated management server IP can reach VMs through the OOB interface
- VMs cannot communicate with each other via the OOB network

**Secondary Network Namespace Access:**
- Secondary networks are attached to namespaces via label selectors
- The VM reconciler only adds labels for subnets explicitly referenced in the
  ComputeInstance's `network_attachments`
- A tenant cannot attach to a secondary network they do not own (subnet ownership
  validated by OPA)

**No New Attack Surface:**
- Tenants interact only via the fulfillment-service API (existing auth/authz)
- K8s manager CRDs (CUDN, SriovNetwork, NAD) are cluster-scoped, managed by AAP
  service account, not directly accessible to tenants

### Validation Rules

At ComputeInstance creation:

1. Exactly one attachment has `primary: true` (decision #9, already enforced)
2. Primary attachment's VN must have a `network_type` where `supports_primary: true`
3. Secondary attachments' VNs must have a `network_type` where `supports_secondary: true`
4. All referenced subnets must be in READY state with `network_binding` populated
5. Multiple secondaries of the same `network_type` are allowed (e.g., two
   `secondary_vlan` NICs on different VLANs in different VirtualNetworks)
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
| **Dispatcher** | Route based on `(NetworkClass, VN.network_type)` instead of just `(NetworkClass)` |
| **K8s manager ConfigMap** | Add `supports_primary` / `supports_secondary` to capabilities |
| **VM reconciler** | Read `SubnetStatus.network_binding` to compose VM `spec.template.spec.networks[]` + `spec.template.spec.domain.devices.interfaces[]` |
| **VM reconciler** | Label primary namespace for secondary network selectors |
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

SecurityGroups and NATGateways are scoped to a VirtualNetwork. For secondary network types
(OOB, SR-IOV), should SecurityGroups and NATGateways be supported? OOB networks use
MultiNetworkPolicy for isolation (k8s-native, not fabric SecurityGroups). SR-IOV networks
typically have no security group support. The validation may need to reject SG/NAT creation
on VNs with secondary-only network types.

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
- ComputeInstance with multiple secondaries of same type succeeds
- ComputeInstance with no primary attachment fails

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

- **Phase 1:** Ship CUDN+EVPN as "tenant" type with the `network_types` framework.
  Single-NIC only (no secondary types implemented yet). Backward compatible.
- **Phase 1.5:** Add `cudn_localnet` k8s manager for "secondary_vlan" role. Multi-NIC with
  primary (EVPN) + secondary (OOB via secondary_vlan) validated end-to-end.
- **Phase 2:** `sriov` k8s manager for "highspeed" role. Multi-cluster. Additional roles
  as needed.

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
