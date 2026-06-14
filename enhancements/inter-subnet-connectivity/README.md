---
title: inter-subnet-connectivity-within-virtualnetworks
authors:
  - oamizur@redhat.com
creation-date: 2026-06-09
last-updated: 2026-06-13
tracking-link:
  - TBD
see-also:
  - "/enhancements/networking"
replaces:
  - N/A
superseded-by:
  - N/A
---

# Inter-Subnet Connectivity within VirtualNetworks

## Summary

This enhancement replaces the `cudn_net` networking implementation to provide
connectivity between subnets within the same VirtualNetwork, analogous to how
AWS VPC subnets can route to each other by default. The current implementation
creates an isolated ClusterUserDefinedNetwork (CUDN) per subnet, preventing
communication between subnets in the same VirtualNetwork. The new implementation
creates a single shared CUDN per VirtualNetwork with IPAM enabled and
`ipam.lifecycle: Persistent`, using IPAMClaim CRDs for per-subnet IP address
allocation. This approach has been validated on a live OpenShift cluster with
OVN-Kubernetes and KubeVirt.

## Motivation

The current OSAC networking implementation creates one CUDN per subnet. While
this provides strong isolation, it prevents communication between subnets
within the same VirtualNetwork. In major cloud providers (AWS, Azure, GCP),
subnets within a VPC/VNet can communicate freely by default -- isolation is
enforced via security groups, not network topology. OSAC tenants familiar with
cloud networking expect the same behavior.

### Why subnets are isolated today

Each OSAC Subnet creates its own CUDN with a `namespaceSelector` matching only
its own namespace. OVN-Kubernetes enforces isolation between CUDNs at three
levels:

1. **Separate OVN logical topology**: Each CUDN gets its own logical switch,
   gateway router, join switch, and load balancers in the OVN northbound
   database. There is no logical path between them.
2. **Per-network gateway router**: Each CUDN gets a dedicated gateway router
   (`GR-<node>-<network>`) with its own patch port to `br-ex`. A shared GR was
   explicitly rejected to prevent cross-network routing.
3. **Conntrack-based traffic separation**: On the shared `br-ex` bridge, each
   CUDN gets unique masquerade IPs, conntrack zones, and CT marks to prevent
   cross-network traffic even at the data-plane level.

### User Stories

- As a tenant, I want VMs in different subnets of the same VirtualNetwork to
  communicate with each other, so that I can deploy multi-tier applications
  (e.g., web servers in one subnet, databases in another) within a single
  VirtualNetwork.

- As a tenant, I want each subnet to have its own IP address range and
  capacity, so that I can control how many resources can be deployed per
  subnet and organize my IP address space.

- As a tenant, I want subnets in different VirtualNetworks to remain isolated,
  so that I can maintain network boundaries between different environments
  (e.g., production vs. staging).

- As a service provider, I want to offer a NetworkClass that provides
  VPC-like networking, so that tenants migrating from AWS/Azure/GCP find a
  familiar networking model.

- As a service provider, I want to manage inter-subnet connectivity without
  requiring physical network infrastructure changes, so that I can deploy
  on any OpenShift cluster with OVN-Kubernetes.

### Goals

- Provide connectivity between all subnets within a VirtualNetwork
- Maintain per-subnet IP address allocation from each subnet's CIDR range
- Maintain per-subnet IP address capacity control
- Maintain isolation between different VirtualNetworks
- Work with current OVN-Kubernetes capabilities (no upstream changes required)
- Support SecurityGroups (via NetworkPolicy) for intra-VirtualNetwork traffic
  control
- Ensure CDI (Containerized Data Importer) can provision VM disk images in
  subnet namespaces
- Provide migration path from existing per-subnet CUDN deployments

### Non-Goals

- Connectivity between different VirtualNetworks (inter-VN peering)
- Integration with physical network infrastructure (localnet topology)
- IPv6 support in the initial implementation (can be added later)
- NAT Gateway or PublicIP changes (these work at the VirtualNetwork level and
  are unaffected by this change)

## Proposal

This proposal replaces the `cudn_net` implementation to create a single shared
CUDN per VirtualNetwork (instead of one CUDN per subnet) with IPAM enabled and
`ipam.lifecycle: Persistent`. Per-subnet IP allocation is achieved through
IPAMClaim CRDs: the OSAC operator allocates IPs from subnet CIDR ranges and
creates IPAMClaims before VMs are provisioned. The kubevirt-ipam-controller
webhook handles the default network annotation on VM pods, and OVN-K uses the
IPAMClaim IPs for allocation.

### PoC Validation Results

The core mechanisms of this proposal have been validated on a live OpenShift
cluster with OVN-Kubernetes (v4.19) and KubeVirt (v1.5.3):

| Test | Result |
|------|--------|
| Single CUDN spanning multiple namespaces — L2 connectivity | **Passed** |
| CUDN with `ipam.lifecycle: Persistent` — NAD gets `allowPersistentIPs: true` | **Passed** |
| IPAMClaim with pre-filled IP — VM gets exact requested IP | **Passed** |
| kubevirt-ipam-controller sets `v1.multus-cni.io/default-network` | **Passed** |
| Masquerade binding on `ovn-udn1` (not `eth0`) | **Passed** |
| Cross-subnet connectivity (pod in subnet-a reaches VM in subnet-b) | **Passed** |
| Per-subnet IPs (VM-A: `10.200.1.1`, VM-B: `10.200.2.1`) | **Passed** |
| Gateway router and external connectivity | **Passed** |
| VirtualNetwork isolation (different VNs cannot communicate) | **Passed** (earlier PoC) |
| IP conflict behavior — OVN-K silently accepts duplicates | **Confirmed** — OSAC must prevent conflicts |

### Key Technical Findings

During validation, several important behaviors were discovered:

1. **Pre-setting `k8s.ovn.org/pod-networks` annotation breaks the default
   network flag.** When a partial annotation (UDN entry only, no default entry)
   is set on a VM pod, Multus marks `eth0` as default instead of `ovn-udn1`.
   This causes KubeVirt's masquerade to bind to the wrong interface.
   **Solution**: Use IPAMClaim instead of pod annotation for IP allocation.

2. **CUDN `ipamLifecycle` vs `ipam.lifecycle`.** The old `ipamLifecycle` field
   at the `layer2` top level is silently ignored. The correct field is
   `ipam: {mode: Enabled, lifecycle: Persistent}` under `layer2`. Without this,
   the NAD does not get `allowPersistentIPs: true` and the kubevirt-ipam-controller
   does not handle the default network annotation.

3. **OVN-K does not detect IP conflicts.** When two logical switch ports on the
   same switch have identical IP and MAC addresses, OVN-K processes both without
   error. Traffic goes to the first port; the second is unreachable. OSAC must
   guarantee IP uniqueness.

4. **NAD configuration must match across namespaces.** OVN-K rejects NADs that
   reference the same logical network but have different configurations (e.g.,
   different `subnets` fields). Per-namespace subnet CIDRs via manual NADs are
   not supported.

5. **kubevirt-ipam-controller creates IPAMClaims with the naming convention
   `<vm-name>.default`.** If OSAC pre-creates an IPAMClaim with this name before
   the VM is created, the controller uses the existing claim (including its
   pre-filled IP) instead of creating a new one.

### Architecture Overview

**Current model (`cudn_net` — being replaced):**

```
VirtualNetwork (logical grouping only, no K8s resources)
  |
  +-- Subnet-A --> Namespace-A + CUDN-A (Layer2, 10.0.1.0/24) --> isolated
  +-- Subnet-B --> Namespace-B + CUDN-B (Layer2, 10.0.2.0/24) --> isolated
```

**New model (`cudn_net` — replacement):**

```
VirtualNetwork --> CUDN (Layer2, IPAM enabled, Persistent, 10.0.0.0/16)
  |
  +-- Subnet-A --> Namespace-A + IPAMClaim (10.0.1.x from subnet CIDR)
  +-- Subnet-B --> Namespace-B + IPAMClaim (10.0.2.x from subnet CIDR)
  |
  All namespaces within the VirtualNetwork share the same CUDN --> full L2 connectivity
  OSAC-managed IPAM tracks per-subnet allocations
  IPAMClaims ensure VMs get subnet-specific IPs
  kubevirt-ipam-controller handles default network annotation
```

### Key Design Decisions

1. **Single CUDN per VirtualNetwork with IPAM enabled and Persistent lifecycle**:
   All subnet namespaces share the same CUDN via a common label
   (`osac.openshift.io/virtual-network: <vn-uuid>`). The CUDN has
   `ipam: {mode: Enabled, lifecycle: Persistent}`, which causes the NAD to
   include `allowPersistentIPs: true`. This enables IPAMClaim-based allocation
   and triggers the kubevirt-ipam-controller to handle the default network
   annotation on VM pods.

2. **IPAMClaim for per-subnet IP allocation**: The OSAC operator maintains an
   in-memory IPAM bitmap per subnet. When creating a VM, the operator allocates
   the next available IP from the subnet's CIDR range and creates an IPAMClaim
   named `<vm-name>.default` in the subnet namespace with the allocated IP in
   `status.ips`. The kubevirt-ipam-controller finds this existing claim and
   references it when setting the `v1.multus-cni.io/default-network` annotation
   on the VM pod. OVN-K then uses the IPAMClaim IP for allocation.

3. **Three-layer conflict prevention**:
   - **Pre-allocation refresh**: Before allocating an IP, the operator refreshes
     its in-memory bitmap from the OVN NB database (time-cached, 60s interval)
     to learn about IPs allocated by OVN-K for CDI/system pods.
   - **Pre-launch check**: The bitmap check ensures the allocated IP is not
     already in use.
   - **Post-creation verification**: After the VM reaches Running state, the
     operator queries OVN NB for the allocated IP. If multiple ports share it,
     the operator releases the IP, removes the annotation, deletes the VMI,
     and the next reconcile allocates a new IP with a new IPAMClaim. Retry is
     limited to 3 attempts; if all attempts conflict, the ComputeInstance is
     marked as Failed with a conflict error condition.

4. **SecurityGroups enforce intra-VN isolation**: With all subnets sharing a
   single L2 domain, isolation between subnets is enforced via Kubernetes
   NetworkPolicies (translated from SecurityGroup CRs). This mirrors the AWS
   model where VPC subnets route freely and Security Groups control access.

5. **No VM template annotation changes**: The VM template uses `masquerade: {}`
   on `pod: {}` as before. No `k8s.ovn.org/pod-networks` annotation is injected.
   The kubevirt-ipam-controller handles the default network annotation via the
   IPAMClaim mechanism.

### Workflow Description

**service provider** is an administrator who defines NetworkClasses and manages
the OSAC platform.

**tenant** is an end-user who creates VirtualNetworks, Subnets, and resources.

#### VirtualNetwork Creation

1. The tenant creates a VirtualNetwork with `networkClass: cudn_net` and a
   CIDR (e.g., `10.0.0.0/16`).
2. The Fulfillment Service creates a VirtualNetwork CR.
3. The O-SAC Operator triggers AAP, which creates a shared CUDN:

```yaml
apiVersion: k8s.ovn.org/v1
kind: ClusterUserDefinedNetwork
metadata:
  name: <virtual-network-name>
  labels:
    osac.openshift.io/managed-by: osac-fulfillment
spec:
  namespaceSelector:
    matchLabels:
      osac.openshift.io/virtual-network: "<virtual-network-uuid>"
  network:
    topology: Layer2
    layer2:
      role: Primary
      subnets:
        - "<virtual-network-cidr>"
      ipam:
        mode: Enabled
        lifecycle: Persistent
```

4. OVN-K creates the logical switch and generates NADs with
   `allowPersistentIPs: true` in each matching namespace.
5. The VirtualNetwork transitions to Ready.

#### Subnet Creation

1. The tenant creates a Subnet within the VirtualNetwork (e.g.,
   `10.0.1.0/24`).
2. The Fulfillment Service validates the Subnet CIDR is within the
   VirtualNetwork's CIDR and creates a Subnet CR.
3. The O-SAC Operator triggers AAP, which creates a namespace with labels:

```yaml
labels:
  k8s.ovn.org/primary-user-defined-network: ""
  osac.openshift.io/virtual-network: "<virtual-network-uuid>"
  osac.openshift.io/subnet-id: "<subnet-id>"
  osac.openshift.io/managed-by: osac-fulfillment
```

4. The namespace is matched by the shared CUDN's `namespaceSelector`. OVN-K
   creates a NAD in the namespace. No per-subnet CUDN is created.
5. The operator registers the subnet's CIDR with the in-memory IPAM allocator.
6. The Subnet transitions to Ready.

#### VM Creation (Resource Attachment)

1. The tenant creates a ComputeInstance with a network attachment referencing
   the subnet.
2. The OSAC operator's `syncAllocatedIPAnnotation` runs:
   a. Refreshes the IPAM bitmap from OVN NB if needed (time-cached).
   b. Allocates the next available IP from the subnet's CIDR range.
   c. Creates an IPAMClaim named `<vm-name>.default` in the subnet namespace.
   d. Sets the IPAMClaim `status.ips` to the allocated IP.
   e. Stores the allocated IP as an annotation on the ComputeInstance for
      tracking.
3. AAP creates the VirtualMachine CR (no special annotations on the pod
   template).
4. KubeVirt creates the VirtualMachineInstance and virt-launcher pod.
5. The kubevirt-ipam-controller webhook finds the existing IPAMClaim, sets
   `v1.multus-cni.io/default-network` on the pod.
6. OVN-K cluster manager uses the IPAMClaim IP for allocation.
7. Multus correctly marks `ovn-udn1` as default; KubeVirt's masquerade binds
   to the UDN.
8. The VM gets the exact IP from the subnet's CIDR range.
9. The operator runs the post-creation conflict check. If a conflict is
   detected, the VM is restarted with a new IP.

#### Cross-Subnet Communication

1. VM-A in Subnet-A (10.0.1.10) sends a packet to VM-B in Subnet-B
   (10.0.2.20).
2. Since both are on the same Layer 2 logical switch (same CUDN), the packet
   is delivered directly through OVN's logical switch pipeline.
3. SecurityGroup rules (NetworkPolicies) are evaluated and the packet is
   allowed or dropped based on the configured rules.

### API Extensions

No changes to the VirtualNetwork, Subnet, or SecurityGroup CRDs. The behavior
change is internal to the `cudn_net` implementation strategy.

The operator now creates IPAMClaim CRDs (`k8s.cni.cncf.io/v1alpha1`) in subnet
namespaces. This requires RBAC for `ipamclaims` and `ipamclaims/status`.

A new annotation is used on ComputeInstance CRs:
- `osac.openshift.io/allocated-ip`: Tracks the IPAM-allocated IP for the VM.

### Implementation Details/Notes/Constraints

#### OSAC-Managed IPAM

The operator maintains an in-memory `SubnetAllocator` (bitmap-based) that
tracks IP allocations per subnet CIDR:

- **On startup** (after leader election): A startup runnable lists all Subnets
  and VirtualNetworks, registers CIDRs, then reads all port addresses from
  OVN NB to rebuild the bitmap.
- **Before each allocation**: If more than 60 seconds since the last refresh,
  reads all port addresses from OVN NB to sync the bitmap with any new
  allocations by OVN-K (CDI pods, system pods).
- **On subnet creation**: Registers the subnet CIDR.
- **On subnet deletion**: Removes the subnet from the allocator.
- **On VM deletion**: Releases the IP and deletes the IPAMClaim.

The allocator uses a `sync.Mutex` for thread safety within a single operator
process. Leader election ensures only one operator replica is active.

#### IPAMClaim Lifecycle

1. **Before VM creation**: Operator creates `IPAMClaim` named
   `<vm-name>.default` with `spec.interface: ovn-udn1` and
   `spec.network: cluster_udn_<vnet-name>`. Sets `status.ips` to the
   allocated IP via the status subresource.
2. **During VM creation**: kubevirt-ipam-controller finds the existing claim
   (matching `<vm-name>.default`), adds `ownerReferences` and labels, and
   references it in the pod's `v1.multus-cni.io/default-network` annotation.
3. **During VM operation**: OVN-K persists the IP in the claim for live
   migration and pod restarts.
4. **On VM deletion**: Operator releases the IP from IPAM and deletes the
   IPAMClaim.

#### OVN NB Access

The operator queries the OVN NB database for IPAM refresh and conflict
detection via `kubectl exec` into `ovnkube-node` pods. This requires a Role
in the `openshift-ovn-kubernetes` namespace:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: osac-ovn-nb-reader
  namespace: openshift-ovn-kubernetes
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["list"]
- apiGroups: [""]
  resources: ["pods/exec"]
  verbs: ["create"]
```

An alternative future approach is to embed `ovn-nbctl` in the operator image
and connect directly to the OVN NB database using TLS certificates from
cluster secrets (`ovn-cert`, `ovn-ca`).

**Error handling**: If OVN NB queries fail (ovnkube pod unavailable, network
issues), the operator logs a warning and proceeds with the cached bitmap.
This is conservative — the bitmap may be stale, but stale data only means
IPs that were recently freed appear as still allocated (false positive), which
prevents allocation but does not cause conflicts. The operator does not retry
failed queries within the same reconcile cycle; the next allocation attempt
(after the refresh interval) retries naturally. During cluster upgrades where
ovnkube pods are temporarily unavailable, IPAM allocation continues with cached
state and resumes full refresh when pods are back.

#### Conflict Detection Queries

- **Bulk refresh**: `ovn-nbctl lsp-list <switch>` + `lsp-get-addresses` per
  port. Used for IPAM bitmap rebuild.
- **Targeted check**: `ovn-nbctl --columns=name find logical_switch_port
  addresses="*<ip>*"`. Returns all ports with a specific IP. If count > 1,
  there is a conflict.

#### Components Modified

- **O-SAC AAP `cudn_net` role**:
  - `create_virtual_network.yaml`: Creates shared CUDN with VN CIDR and
    `ipam: {mode: Enabled, lifecycle: Persistent}`
  - `create_subnet.yaml`: Creates namespace only (no per-subnet CUDN)
  - `delete_virtual_network.yaml`: Deletes shared CUDN
  - `delete_subnet.yaml`: Deletes namespace only

- **O-SAC Operator**:
  - `internal/ipam/allocator.go`: Bitmap-based per-subnet IP allocator with
    OVN NB refresh capability
  - `internal/ovn/client.go`: OVN NB query client for port addresses and
    conflict detection
  - `internal/controller/computeinstance_controller.go`: IPAMClaim creation,
    pre-allocation refresh, post-creation conflict check with retry
  - `internal/controller/subnet_controller.go`: Subnet CIDR registration
  - `internal/controller/ipam_startup.go`: Startup IPAM rebuild from OVN NB
  - `cmd/main.go`: OVN client creation, IPAM wiring, startup runnable

### Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| IP collision between OSAC-assigned and OVN-K auto-allocated | VM unreachable | Three-layer conflict prevention: pre-refresh, pre-check, post-verify with retry |
| OVN NB access unavailable | Cannot refresh IPAM bitmap | Graceful degradation: operator continues with cached bitmap; logs warning |
| kubevirt-ipam-controller overwrites IPAMClaim status | VM gets wrong IP | Validated: controller uses existing claim status, does not overwrite |
| Single L2 domain broadcast storms | Network performance degradation | OVN logical switches don't flood unknown unicast; ARP is handled by OVN's ARP responder |
| CUDN immutability | Cannot change VN CIDR after creation | VirtualNetwork CIDR is immutable by design |
| IPAMClaim naming convention changes | Operator creates claims with wrong name | Pin to validated convention `<vm-name>.default`; monitor upstream changes |

### Drawbacks

- **Weaker isolation between subnets**: Subnets share an L2 domain; isolation
  depends entirely on NetworkPolicies (SecurityGroups). A misconfigured
  SecurityGroup could allow unintended cross-subnet traffic. However, this
  matches the AWS VPC model where Security Groups are the isolation mechanism.

- **OVN NB database dependency**: The operator queries the OVN NB database
  for IPAM refresh and conflict detection. This requires cross-namespace
  RBAC and adds a runtime dependency on OVN infrastructure availability.

- **IPAMClaim is v1alpha1**: The IPAMClaim CRD is at alpha maturity. API
  changes in future versions could require adaptation.

- **No strict network-level CIDR enforcement**: While OSAC assigns VMs IPs
  from the correct subnet range via IPAMClaim, OVN-K's IPAM is unaware of
  per-subnet partitioning. CDI and system pods may get IPs from any range.
  This is acceptable since only VMs need subnet-specific addresses.

## Migration Plan

Existing VirtualNetworks using the old per-subnet CUDN model can be migrated
to the new shared CUDN model. Migration requires downtime per VirtualNetwork
but preserves VM IP addresses.

### Migration Steps

1. **Gather state**: Record all VM names, namespaces, and current IP addresses.
2. **Stop all VMs**: Set `runStrategy: Halted` on all VMs in the VirtualNetwork.
3. **Delete old per-subnet CUDNs**: Remove all CUDNs named after subnets.
4. **Create shared CUDN**: Create a single CUDN with the VirtualNetwork CIDR,
   `namespaceSelector` matching the `virtual-network` label, and
   `ipam: {mode: Enabled, lifecycle: Persistent}`.
5. **Create IPAMClaims**: For each VM, create an IPAMClaim named
   `<vm-name>.default` in the subnet namespace with the VM's original IP
   in `status.ips`.
6. **Update annotations**: Set `osac.openshift.io/allocated-ip` on each
   ComputeInstance CR so the operator's IPAM tracks the allocation.
7. **Restart VMs**: Set `runStrategy: Always`. VMs boot and get their original
   IPs via IPAMClaim.
8. **Verify**: Check VMs got original IPs, masquerade binds to `ovn-udn1`,
   cross-subnet connectivity works.

An automated migration script is provided in the supplementary materials
(`migration-plan.md`).

### Rollback

If migration fails:
- **Before shared CUDN creation**: Recreate per-subnet CUDNs, restart VMs.
- **After shared CUDN creation**: Delete shared CUDN, recreate per-subnet
  CUDNs, restart VMs.
- **After VMs started with wrong IPs**: Delete IPAMClaims, delete VMIs,
  VMs restart with new pool-allocated IPs.

## Alternatives (Not Implemented)

### Alternative 1: Wait for OKEP-5224 (ClusterNetworkConnect)

OVN-Kubernetes proposal to connect UDNs via a dedicated transit router using
a `ClusterNetworkConnect` CRD.

**Why not selected**: Not yet shipped. Targets OVN-Kubernetes release 1.2.
Does not support overlapping subnets in first phase.


## Open Questions

1. **Refresh interval tuning**: The 60-second IPAM refresh interval is a
   starting point. May need tuning based on CDI pod frequency.

2. **IPAMClaim ownership**: kubevirt-ipam-controller adds `ownerReferences`
   and labels to existing claims. Need to verify it does not interfere with
   claim lifecycle on VM deletion.

3. **OVN NB access method**: Current implementation uses `kubectl exec` into
   ovnkube pods. Embedding `ovn-nbctl` with TLS certs is more secure but
   adds operational complexity.

4. **Multiple operator replicas**: Currently single replica with leader
   election. In-memory IPAM is safe. If scaling, need shared IPAM state.

## Test Plan

*Section to be completed when targeted at a release.*

- **Unit tests**: IPAM allocator (28 tests), OVN client (7 tests), MAC
  derivation, refresh logic, conflict detection
- **Controller tests**: 439 existing tests pass with new IPAM/OVN parameters
- **Integration tests**: Full lifecycle (VN → Subnet → VM) with IPAMClaim;
  cross-subnet connectivity; per-subnet IP allocation; conflict detection
  and retry
- **Migration tests**: Migrate from per-subnet to shared CUDN; verify IP
  preservation and connectivity
- **Conflict prevention stress tests** (future validation, required before GA):
  - Concurrent VM creation with simultaneous CDI pod creation to verify
    IPAM refresh prevents collisions under load
  - Conflict detection accuracy: verify no false negatives (missed conflicts)
    and that false positives (stale bitmap marking freed IPs as allocated)
    are harmless and self-resolving
  - Operator failover: verify IPAM bitmap is correctly rebuilt from OVN NB
    after leader election and that no duplicate IPs are assigned during
    the recovery window

## Graduation Criteria

*Section to be completed when targeted at a release.*

- **Dev Preview**: Core flow working (shared CUDN, IPAMClaim, per-subnet IPs,
  cross-subnet connectivity, conflict detection)
- **Tech Preview**: Migration tool validated; OVN NB IPAM refresh tested at
  scale; RBAC manifests in installer
- **GA**: Performance validated; migration documented; support procedures
  defined

## Upgrade / Downgrade Strategy

- The change replaces the `cudn_net` implementation. A migration procedure
  is provided for existing VirtualNetworks.
- Downgrade: Migrate back to per-subnet CUDNs using the reverse of the
  migration procedure (delete shared CUDN, recreate per-subnet CUDNs).
- The operator must be updated before the AAP playbooks to avoid the old
  operator recreating per-subnet CUDNs.

## Version Skew Strategy

- The operator must handle both old (per-subnet CUDN) and new (shared CUDN)
  VirtualNetworks during migration.
- The Fulfillment Service API is unchanged; the implementation strategy
  determines behavior.
- IPAMClaim CRD (`k8s.cni.cncf.io/v1alpha1`) must be available on the
  cluster (provided by OVN-Kubernetes).
- kubevirt-ipam-controller must be running (provided by OpenShift Virtualization).

## Support Procedures

- **VMs not getting the correct IP**: Verify IPAMClaim exists in the subnet
  namespace (`kubectl get ipamclaim -n <ns>`). Check its `status.ips` matches
  the expected IP. Verify the CUDN has `ipam.lifecycle: Persistent` and the
  NAD has `allowPersistentIPs: true`.

- **Masquerade binding to eth0 instead of ovn-udn1**: Verify NAD has
  `allowPersistentIPs: true`. Check that kubevirt-ipam-controller is running
  and processing pods. Verify no `k8s.ovn.org/pod-networks` annotation is
  set on the VM template.

- **Cross-subnet connectivity failing**: Verify both subnet namespaces have
  the `osac.openshift.io/virtual-network` label matching the CUDN's
  `namespaceSelector`. Check that no NetworkPolicy (SecurityGroup) is
  blocking the traffic. Verify both pods are on the same logical switch.

- **IP conflict detected**: Check operator logs for "IP conflict detected"
  messages. The operator will automatically retry with a different IP. If
  conflicts persist, check for pods with static IP configurations in the
  subnet namespaces.

- **CDI importer pod issues**: CDI pods get auto-allocated IPs from OVN's pool
  (not from IPAMClaim). Verify the CUDN has `ipam.mode: Enabled`.

## Infrastructure Needed

No additional infrastructure required. The implementation uses:
- OVN-Kubernetes (existing)
- IPAMClaim CRD (provided by OVN-Kubernetes)
- kubevirt-ipam-controller (provided by OpenShift Virtualization)
- OVN NB database access (via kubectl exec or embedded ovn-nbctl)
