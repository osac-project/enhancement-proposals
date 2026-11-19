# Tenant Networking on Per-Tenant VM Clusters

| Field       | Value                                                                    |
|-------------|--------------------------------------------------------------------------|
| Author(s)   | Yoni Bettan (yonibettan@gmail.com)                                       |
| Jira        | [OSAC-7305](https://redhat.atlassian.net/browse/OSAC-7305)               |
| Task        | [OSAC-7308](https://redhat.atlassian.net/browse/OSAC-7308)               |
| PRD         | [prd.md](prd.md)                                                         |
| Date        | 2026-11-16                                                               |

Requirement identifiers `R-1`–`R-12`, `US-1`–`US-8`, `DS-1`–`DS-3`, and
`NG-1`–`NG-8` are the traceability keys derived from the PRD in
[`prd.md`](prd.md); the PRD states requirements as prose.

# 1. Overview

OSAC runs on one management cluster and, today, all tenant VirtualNetworks and
the VMs that use them live on that same cluster, or on one configured remote
cluster that the operator carries as a process-wide setting. The accepted
networking contract binds every Kubernetes Manager task to "the cluster the job
runs in", so a deployment that hosts VMs on a workload cluster cannot give those
VMs tenant networking. This design lets tenant networking follow the cluster that
hosts the tenant's VMs while keeping OSAC on one management cluster.

Two records stay distinct:

- **`Hub` is the management cluster.** OSAC runs there, and every OSAC control
  object — `Tenant`, `VirtualNetwork`, `Subnet`, `SecurityGroup`,
  `NetworkAttachment`, `ComputeInstance`, `Volume` — is created there. A `Hub` is
  never a VM host in this design.
- **`WorkloadCluster` is a cluster that can host tenant VMs**, as defined by
  [OSAC-6488](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-6488-import-hub-registered-clusters-for-ai-workloads/design.md).
  It carries the registration, the credentials, the `supported_workloads`
  capability list, and the readiness conditions. The management cluster is a
  `WorkloadCluster` too when tenants are assigned to it [Locked: D16].

The VM cluster is a *provisioning target*, carried on each tenant-scoped CR as an
immutable `osac.openshift.io/vm-cluster` annotation and forwarded to the network
manager as `osac_job_vars.cluster`. Readiness for tenant networking becomes a
`TenantNetworkingReady` condition on the `WorkloadCluster`, enforced by
fulfillment when a tenant is assigned. Which cluster a tenant gets, how it is
registered, how OSAC reaches it, and how it is removed are the placement
foundation's decisions
([OSAC-977](https://redhat.atlassian.net/browse/OSAC-977)); this design consumes
them and owns only the networking behavior on that cluster.

The design reuses the existing per-cluster client, multicluster watch, AAP
instance-group credential channel, and network task engine: no new registry, no
new credential store, and no per-cluster manager copies. A single-cluster
deployment remains the degenerate case with byte-for-byte observable behavior.

# 2. Goals and Non-Goals

## 2.1 Goals

- Express a cluster's fitness for tenant networking as a condition on the
  `WorkloadCluster`, with a reason and message that name the unmet prerequisite.
- Resolve the target cluster per tenant from the first increment, so a
  single-cluster deployment is the degenerate case [Locked: D18].
- Reuse the existing `WorkloadCluster` registry, per-cluster clients,
  multicluster provider mechanism, AAP instance-group credential channel, and
  network task engine; add no new registry, no new credential store, and no
  per-cluster manager copies.
- Keep every OSAC CR on the management cluster so that adding a VM cluster does
  not change controller watch scope, finalizer behavior, or tenant isolation.
- Preserve byte-for-byte observable behavior for a fresh installation whose
  tenants are assigned to the management cluster [R-12, Locked: D19].

## 2.2 Non-Goals

- Registering clusters, storing credentials, recording the per-tenant
  assignment, deciding the default target, or guarding removal: consumed from the
  placement foundation, OSAC-977 [NG-1, NG-2].
- Moving tenant VirtualNetworks, Subnets, or SecurityGroups between clusters, or
  duplicating one tenant's networking on several clusters [NG-3, NG-4].
- Volume, DataVolume, snapshot, and disk-image placement, VM and storage
  credentials, and console routing. VMaaS and the storage designs own those; this
  design does not change them and does not make storage follow the VM.
- Automating BGP peering, VTEP range allocation, or cluster-AS assignment, which
  require the provider's network team [R-2].
- Any UI, console, or tenant-visible placement surface [NG-7, Locked: D17].
- Networking for hosted control plane clusters and MaaS gateways [NG-8].

# 3. Motivation / Background

Three current assumptions block the feature, and each one is a single-scope
assumption rather than a missing capability.

The operator binds all remote work to one cluster. `--remote-cluster-kubeconfig`
builds one cluster and wraps it in `single.New(remoteClusterName, remoteCluster)`;
`targetClusterFromManager` then returns that name for every reconcile, or the
local cluster when the flag is absent [Codebase: osac-operator/cmd/main.go]. The
process refuses to start when that flag is set and provider networking is
enabled [Codebase: osac-operator/cmd/main.go], which is why the split-cluster
shape cannot produce a usable networking capability today.

The Kubernetes Manager runs network tasks on the cluster the AAP job runs in.
`cudn_evpn` creates the tenant namespace, the EVPN `ClusterUserDefinedNetwork`,
and the SecurityGroup `NetworkPolicy` objects using the job pod's in-cluster
service account, and its README states that "the hub is the cluster the job runs
in; no remote cluster" [Codebase: osac-aap/collections/ansible_collections/osac/templates/roles/cudn_evpn/README.md].
The manager contract records that tasks "reach the hub with the job pod's
in-cluster service account" and that "task input has no cluster identifier"
[Codebase: OSAC-1433 network manager integration contract §4.3]. The contract on
`main` already amended both: Kubernetes Manager tasks receive `cluster: {id}`,
read a per-cluster kubeconfig, and keep the job pod's service account for hub
reads [Codebase: OSAC-1433 network manager integration contract §4.3, §4.5,
§4.12].

The cluster registry and the credential channel exist but are pinned to one
cluster. `WorkloadCluster` records already carry registration, capabilities, and
conditions, and the operator reaches remote clusters through one process-wide
kubeconfig [Codebase: enhancement-proposals OSAC-6488 design,
osac-operator/cmd/main.go]. What is pinned is the *choice*: the operator's single
remote cluster, and the network manager's implicit "the cluster the job runs in".

This design changes the *dispatch identity*, not the storage location. Each
tenant's networking gets a per-tenant execution target carried on its own CR, so
the Kubernetes Manager learns which cluster a task applies to from the object it
is already reconciling. OSAC's control objects keep living on the management
cluster, which stays the deployment's one `Hub` and needs no inference: there is
exactly one.

# 4. Design

## 4.1 Architecture

Five components change; none gains a new responsibility class.

- **fulfillment-service** reads the tenant's target cluster from the placement
  record, validates it against the `WorkloadCluster` readiness condition, stamps
  it on the tenant-scoped CRs it creates, and records the resolved value on the
  tenant.
- **osac-operator** watches every registered VM-hosting cluster, derives the
  target from the CR annotation, probes and reports `WorkloadCluster` readiness,
  and forwards `cluster` in `osac_job_vars`.
- **osac-aap** mounts one kubeconfig per registered cluster into the networking
  instance group, and `cudn_evpn` selects the one named by the task input while
  keeping hub reads on the job pod's service account.
- **osac-installer** prepares a cluster for tenant networking as an explicit
  idempotent step and stops staging a single deployment-wide remote kubeconfig.
- **The fabric manager and the fabric** are unchanged and stay registered once
  [Locked: D6].

The control-object topology is deliberate: CRs remain on the management cluster,
and only *effects* land on the VM cluster. This is what keeps the change to
controller watch scope at zero.

```mermaid
flowchart LR
    subgraph Main["Management cluster (single Hub, control objects)"]
        API[Fulfillment private API]
        VN[VirtualNetwork / Subnet / SecurityGroup]
        NA[NetworkAttachment]
        CI[ComputeInstance]
        OP[osac-operator]
        AAP[AAP network job]
    end
    subgraph VM["Tenant's VM cluster (WorkloadCluster)"]
        NS[Namespace osac-vn-ID]
        CUDN[ClusterUserDefinedNetwork]
        NP[SecurityGroup NetworkPolicies]
        KVV[KubeVirt VM]
    end
    API -->|creates, annotated vm-cluster| VN
    API -->|creates, annotated vm-cluster| CI
    OP --> VN
    OP -->|osac_job_vars.cluster.id| AAP
    AAP -->|kubeconfig for that cluster| NS
    AAP --> CUDN
    AAP --> NP
    AAP -->|ocp_virt_vm, cluster.id| KVV
    AAP -.->|Subnet CR read stays on the hub| VN
```

The diagram shows the split the design relies on. Fulfillment creates and the
operator reconciles every OSAC object on the management cluster. A network job is
launched from there but authenticates to the tenant's VM cluster with that
cluster's credentials, while the OSAC objects it reads stay on the management
cluster. The operator does not call the KubeVirt API itself: it launches the
provisioning job, and the AAP `ocp_virt_vm` role creates the `VirtualMachine` on
that cluster. The takeaway: nothing in the control plane moves; only the identity
a job applies objects with, and the cluster a VM is created on, become per-tenant.

### 4.1.1 Cluster identity

Two identities exist, and the design keeps them apart.

- **The management hub.** The deployment's single `Hub` record
  [Codebase: proto/private/osac/private/v1/hub_type.proto]. OSAC runs there and
  every OSAC CR is created there. It is not a VM-hosting registry: nothing in
  this design registers VM clusters as `Hub`s, and no Hub consumer (`selectHub`,
  onboarding, compute readiness) gains a new kind of member.
- **The VM-hosting cluster.** A `WorkloadCluster` record [OSAC-6488] whose
  `metadata.name` is the cluster identity used everywhere in this design. Its
  `spec.supported_workloads` must contain `vmaas` for the cluster to be eligible;
  its registration supplies the credentials the operator and AAP use (OSAC-977,
  OSAC-7828). This design assumes the existing allow-list gains `vmaas` — an
  amendment listed in §8 — rather than inventing a second registry.

`TenantNetworkingReady` is a new condition type on
`WorkloadCluster.status.conditions`; the readiness model is in §4.1.6.

### 4.1.2 Target resolution

Resolution has one owner per boundary.

**Placement (fulfillment, consumed).** The tenant-to-cluster assignment is the
placement foundation's [NG-2]. This design consumes it as a single read-only
value on the private tenant: the `WorkloadCluster` name of the tenant's assigned
cluster. The foundation also decides what happens when a tenant has none — this
design adds no fallback, no count of registered clusters, and no special-cased
management cluster. The first increment's "one VM cluster, all tenants" shape is
served by the foundation resolving the deployment's single VMaaS target [DS-1,
Locked: D18]; that is a dependency we state (§8), not a rule we define here.

**Resolution time.** Fulfillment resolves the target once, at tenant creation,
and records it on the tenant as a read-only private value. Creating a CR never
re-resolves: adding or removing a cluster later cannot move an existing tenant or
strand it, and every CR of a tenant targets the same cluster [DS-3].

Resolution fails deterministically:

| Condition | Result |
|---|---|
| No target recorded for the tenant | `InvalidArgument`, "no VM cluster assigned to tenant" |
| Target names a `WorkloadCluster` that does not exist or is being removed | `InvalidArgument`, naming the cluster [R-5] |
| Target names a cluster whose `TenantNetworkingReady` is not `True` | `InvalidArgument`, naming the cluster and the unmet prerequisite [R-5] |
| Target names a cluster without the `vmaas` capability | `InvalidArgument`, naming the cluster and the missing capability |

An unready target is rejected, never substituted: a tenant is never created on a
cluster other than the one the foundation recorded.

**Dispatch (fulfillment → CR).** Every tenant-scoped CR that fulfillment creates
for a tenant carries the resolved cluster name as the immutable annotation
`osac.openshift.io/vm-cluster`. The set is exactly the kinds that need a cluster:
`VirtualNetwork`, `Subnet`, `SecurityGroup`, `NetworkAttachment` and
`ComputeInstance`. Fabric-only kinds — `NATGateway`, `ExternalIP`,
`ExternalIPAttachment`, `ExternalIPPool` — do not carry it, because their tasks
talk to the fabric rather than to a cluster and adding the annotation would
suggest a targeting relationship that does not exist. The annotation is written
once at CR creation and never patched, which is how "changing a tenant's cluster
after creation is not supported" is enforced mechanically [R-4, Locked: D10]. Its
value is the `WorkloadCluster` name, not a UUID, so an operator log or an AAP job
label is diagnosable without a lookup.

Immutability rests on a single writer per kind. Fulfillment writes the annotation
on the CRs it creates and no API surface exposes it. One kind is created by the
operator instead: the `NetworkAttachment` for a `ComputeInstance`
[Codebase: osac-operator/internal/controller/computeinstance_controller.go]. The
operator copies the annotation from the `ComputeInstance` when it creates that
attachment and never invents a value. A cluster administrator editing a CR
directly is outside the threat model — that identity already has
`cluster-admin` on the cluster. The task engine therefore trusts the value it
reads and does not re-derive it from placement on every reconcile.

Kinds that must live on the VM cluster but are outside this design's annotation
set — `Volume`, `DataVolume`, snapshots, disk images — keep their current
behavior. VMaaS and the storage designs own their targeting; this design
explicitly does not claim that storage follows the VM.

**Execution (operator → AAP → cluster).** The operator reads the annotation from
the CR it is reconciling and (a) resolves the cluster client for VM work and
(b) sets `osac_job_vars.cluster.id` for Kubernetes Manager tasks. The task engine
never derives the cluster from configuration, and no task input carries
credentials.

### 4.1.3 Operator cluster engagement

Engagement is the placement foundation's: the operator reaches every registered
VM-hosting cluster through the connection mechanism OSAC-977 provides, one
client per registered cluster, and a cluster registered at installation or day 2
produces the same result without an operator restart [R-1]. This design does not
choose that mechanism, name its Secrets, or change `Hub` permissions; it states
only what it needs from it:

- an identity equal to the `WorkloadCluster` name, used unchanged for the
  annotation, the operator's client lookup, the AAP credential key, and the
  `cluster.id` task input;
- credentials scoped to the work OSAC does there: KubeVirt for VM provisioning,
  and namespaces, `ClusterUserDefinedNetwork`, `NetworkPolicy`, and `VTEP` reads
  for tenant networking. The management `Hub`'s `hub-access` credential is not
  reused for this;
- engagement limited to clusters whose `supported_workloads` contains `vmaas`,
  so a cluster that hosts no VMs adds no VM informers.

Which controllers engage which clusters follows from that: the VM and networking
controllers use the tenant's cluster; the management-hub controllers keep using
the single `Hub`.

### 4.1.4 Network task targeting

The network manager contract on `main` already states the targeting this design
needs [Codebase: OSAC-1433 network manager integration contract §4.3, §4.5,
§4.12]: a Kubernetes Manager task receives `cluster: {id: <VM-hosting cluster
name>}`, reads the kubeconfig mounted for it, and keeps the job pod's in-cluster
service account for hub reads. This design relies on that contract and adds no
new key.

`cudn_evpn` therefore uses two identities in every task:

- **On the VM cluster**, with the per-cluster kubeconfig: the tenant namespace,
  the EVPN `ClusterUserDefinedNetwork`, the SecurityGroup `NetworkPolicy`
  objects, and any `VTEP` read that concerns that cluster.
- **On the hub** (the management cluster), with the job pod's in-cluster service
  account: the OSAC `Subnet` CR read for owner and orphan detection. That read
  must never move to the VM cluster: the CR does not exist there, and a failed
  lookup would be misread as an orphaned hub network.

A Kubernetes Manager task whose `cluster` is absent or whose kubeconfig is
missing fails with `retryable: true` and a message naming the cluster. There is
no fallback to the management cluster: falling back would place tenant traffic on
the wrong network and silently violate isolation.

The namespace, CUDN, and NetworkPolicy logic is otherwise unchanged: the objects
are the same objects with the same names, labels, owner annotations, and
idempotency rules, created on a different cluster. VNI allocation is unaffected
because the fabric remains the single VNI authority and each tenant's networks
live on exactly one cluster [NG-4].

### 4.1.5 Cluster preparation

Preparation stays an administrator action, made idempotent and per-cluster, and
it is the same flow that prepares the management cluster today [R-1, R-2]:

- `osac-installer` gains `make prepare-vm-cluster`, which is
  `prepare-remote-cluster` generalized to take the cluster name and to run
  against any registered cluster. It installs LVMS and CNV and, when EVPN values
  are supplied, runs the existing `configure-evpn.sh` hook, which creates the
  VTEP, the `RouteAdvertisements` `osac-evpn`, the `FRRConfiguration`, and the
  NNCP/NMState objects [Codebase: osac-installer/scripts/setup-remote-cluster.sh].
- The hook keeps today's BGP behavior: with `evpn.bgp.waitForEstablished` set
  (the default), it waits for each node's BGP session to reach `Established` and
  fails the preparation otherwise [Codebase:
  osac-installer/charts/osac-infra/files/hooks/configure-evpn.sh]. BGP
  establishment is therefore verified when a cluster is prepared, by the same
  mechanism used for the management cluster, and no new runtime BGP monitor is
  introduced.
- Registration itself — `WorkloadCluster` creation, credentials, and removal —
  is the placement foundation's (OSAC-977, OSAC-7828), not this design's.
- The provider's network team owns the parts OSAC cannot do: a distinct VTEP
  CIDR and cluster AS per VM cluster, and BGP peering between each cluster's
  nodes and the fabric. These are prerequisites of the preparation step, not
  tasks.

An OSAC reconciler does not perform preparation. It would have to apply half of a
peering configuration that only the provider can complete, and it would then
report readiness for a cluster the fabric cannot reach. The readiness probe in
§4.1.6 is the OSAC-side proof that preparation happened, which is what R-2 needs.
Working fabric connectivity to a newly registered cluster is a prerequisite, not
a new fabric design: the fabric keeps allocating the segments and the Kubernetes
Manager keeps programming OVN through the CUDN, now on the tenant's cluster.

### 4.1.6 Readiness

The operator computes `TenantNetworkingReady` on each `WorkloadCluster` because
it is the component that will later fail the task; keeping the gate and the
failure in one place prevents the two from disagreeing. The probe runs on
`WorkloadCluster` create/update and every five minutes, and checks, in order:

| Prerequisite | Check | Reason when unmet |
|---|---|---|
| Credential usable | API discovery succeeds | `ClusterUnreachable`, `KubeconfigRejected` |
| Virtualization | KubeVirt API served; `HyperConverged` `Available=True` | `VirtualizationNotAvailable` |
| CUDN support | `clusteruserdefinednetworks.k8s.ovn.org` served | `CUDNNotAvailable` |
| VTEP | `VTEP` `tenant-vtep` `Accepted=True` | `VTEPNotAccepted` |
| Advertisement | `RouteAdvertisements` `osac-evpn` `Accepted=True` | `RouteAdvertisementsNotAccepted` |

The advertisement check accepts the state a freshly prepared cluster is in.
`configure-evpn.sh` documents that `RouteAdvertisements` may stay
`ConfigurationPending` until OSAC creates the first CUDN, and no CUDN exists
until a tenant is assigned. The probe therefore treats `ConfigurationPending`
with no CUDN on the cluster as ready: `TenantNetworkingReady=True`, reason
`AwaitingFirstNetwork`, message naming the state. Requiring `Accepted=True` there
would deadlock: no tenant can be assigned until a CUDN exists, and no CUDN is
created until a tenant is assigned. Once a CUDN exists, a fully prepared cluster
reports `TenantNetworkingReady=True` with reason `PrerequisitesMet`, and an
advertisement that is still not accepted reports
`RouteAdvertisementsNotAccepted`.

With `global.networking.provisioningEnabled=false` the probe stops after the
credential check and reports `True` with reason `ProvisioningDisabled`, because
the CI-only configuration has no provider networking [R-10]. Messages name the
cluster and the object, for example:
`cluster "vw1" is not prepared for tenant networking: RouteAdvertisements "osac-evpn" is not Accepted`.

**Task-time check.** Readiness is a five-minute observation, so it cannot be the
only gate. A task that targets a cluster rechecks the prerequisites it depends on
before it applies objects, and fails with the same reason and a message naming
the cluster when one is unmet [R-11]. This is what produces the "only the
affected task fails" behavior in §4.6 when a prerequisite drops between probes; a
task may rely on a `TenantNetworkingReady=True` observation only for the
preconditions it rechecks itself. The mechanism is left open: the role may check
inline, or the operator may pass the last observed reason.

### 4.1.7 The control-object hub

There is exactly one `Hub`: the management cluster where OSAC runs and where
every OSAC CR is created. The networking hub boundary is therefore unchanged from
the accepted contract [Codebase: OSAC-1433 unified networking design], and this
design makes no change to `NetworkClass`: it is not recreated, it gains no field,
and it keeps resolving to the single `Hub` exactly as today.

Registering a VM-hosting `WorkloadCluster` is invisible to that boundary. It
does not add a `Hub`, so `ResolveResourceNetworkingHub` still finds one active
hub, and adding a cluster at installation or on day 2 must not require updating
or replacing the `NetworkClass` [R-1].

### 4.1.8 External access

External access needs no new mechanism and inherits the design unchanged.
`ExternalIP`, `ExternalIPPool`, `ExternalIPAttachment`, and `NATGateway` are
Fabric Manager resources, so their tasks receive no `cluster` key and they carry
no `osac.openshift.io/vm-cluster` annotation. Address allocation, inbound DNAT,
and outbound SNAT stay fabric-global, so an `ExternalIP` allocated for a VM on one
VM cluster is the same kind of object and the same allocation as one allocated for
a VM on the management cluster [R-8]. The behavioral consequence is that attach
and detach reach the fabric through the single Fabric Manager registration, which
is why no per-cluster fabric registration is introduced [Locked: D6].

### 4.1.9 Networking-disabled configuration

`global.networking.provisioningEnabled=false` keeps its current meaning: no
Kubernetes or Fabric Manager task runs, no `NetworkAttachment` is created, the VM
is placed in the tenant namespace, and `NetworkReady` reports
`ReasonProvisioningDisabled` [Codebase: osac-operator/internal/controller/computeinstance_controller.go].
The `osac.openshift.io/vm-cluster` annotation is still written, because VM
placement is independent of provider networking; it is simply unused by any task.
When networking is disabled the operator reports the VM's pod-network address
rather than a tenant address, so readiness does not depend on a tenant address or
on provider connectivity [R-10]. This path remains CI-only and is the one blocked
in CI by OSAC-7297.

The standalone Kubernetes-only profile (OSAC-7436) is the degenerate remote
case: its only registered VM-hosting cluster is the management cluster, so every
`cluster.id` names that registration and the job pod's service account and the
per-cluster credential address the same cluster while remaining separate
identities.

## 4.2 Data Model / Schema Changes

**`WorkloadCluster` (private API).** `WorkloadClusterStatus` gains conditions,
following the per-resource condition pattern the private API already uses:

```proto
message WorkloadClusterStatus {
  repeated WorkloadClusterCondition conditions = 1;
  // ...existing fields, including managed_cluster_uid = 2...
}

message WorkloadClusterCondition {
  option (cleanapi.message).private = true;
  WorkloadClusterConditionType type = 1;
  ConditionStatus status = 2;
  google.protobuf.Timestamp last_transition_time = 3;
  optional string reason = 4;
  optional string message = 5;
}

enum WorkloadClusterConditionType {
  option (cleanapi.enum).private = true;
  WORKLOAD_CLUSTER_CONDITION_TYPE_UNSPECIFIED = 0;
  WORKLOAD_CLUSTER_CONDITION_TYPE_TENANT_NETWORKING_READY = 1;
}
```

`ConditionStatus` is the existing shared enum. The field number and message shape
follow the `WorkloadCluster` definition in OSAC-6488; adding the condition type
and the `vmaas` value to `spec.supported_workloads` are the two amendments this
design needs (§8).

**`Hub` (private API).** No change. `HubStatus` stays empty; this design adds no
condition to it.

**`Tenant` (private API).** The tenant carries the assigned cluster as a
read-only private value populated at tenant creation from the placement
foundation. Its name and placement in `TenantSpec` or `TenantStatus` are the
placement foundation's decision [NG-2]; this design reads it and treats it as
immutable.

**`NetworkClass` (private API).** No change. This design adds no field, and a
deployment that registers VM-hosting clusters still uses one `NetworkClass`
pointing at the single `Hub`.

**CR annotation.** `osac.openshift.io/vm-cluster` on the tenant-scoped CR kinds
listed in §4.1.2. It mirrors the existing `osac.openshift.io/tenant` annotation
[Codebase: osac-operator/internal/networktask/input.go] and is not indexed or
selectable.

**`osac_job_vars`.** No new key: `cluster.id` already exists in contract §4.5.

**No database migration for networking.** `WorkloadCluster.status`, the tenant's
target value, and the condition type are persisted by the existing sequential
schema; the annotation is created with the CR. No existing row is rewritten.

## 4.3 API Changes

**`WorkloadClusters.Get` / `WorkloadClusters.List`** return `status.conditions`.
Additive; existing clients ignore it. Private API only.

**`Tenants.Create`** validates the recorded target (table in §4.1.2). A cluster
that is unknown, removing, missing the `vmaas` capability, or unprepared yields
`InvalidArgument` whose message names the cluster and the unmet prerequisite:

```
cluster "vw1" is not prepared for tenant networking:
RouteAdvertisements "osac-evpn" is not Accepted
```

**`NetworkClasses`** unchanged. Adding a VM-hosting cluster must not require an
update or replacement.

**`Hubs`** unchanged. This design adds no delete guard to `Hub`, because a `Hub`
is not a VM host; removal of a VM-hosting cluster is guarded by the placement
foundation (OSAC-977), which must keep the cluster reachable until no tenant is
assigned to it and no cleanup task for it is outstanding.

**No public API change.** Placement stays internal administration, and no field,
error, or endpoint changes for tenants or the console [NG-7, Locked: D8, D17].

## 4.4 Scalability and Performance

Bounded by the number of registered clusters, `N`, which deployments size in
single digits.

- **Operator memory.** One client and cache per engaged VM-hosting cluster. The
  operator's watch set adds no kinds; the informer count grows as `N × kinds` for
  the clusters that carry `vmaas`, and a cluster without it adds nothing.
- **Readiness probes.** One probe per cluster per five minutes, one API discovery
  call and four object reads each. Negligible against the existing reconcile
  volume.
- **Network task latency.** Unchanged: the same job templates, the same AAP
  polling cadence, the same retry backoff. Only the kubeconfig the role uses
  differs.
- **Database.** No new queries on the hot path. The tenant-create validation adds
  one `WorkloadClusters.Get` per create; the per-hub client cache keeps
  Kubernetes clients warm, so validation constructs no client.
- **AAP.** One Secret holds one key per cluster instead of one key total. Job pods
  mount the same Secret, so pod startup cost does not grow with `N`.

## 4.5 Security Considerations

**Cluster credentials.** Each VM cluster's kubeconfig is available to the
networking instance group, which the contract already declares the trust
boundary: "Every role in the instance group can read all these values"
[Codebase: OSAC-1433 network manager integration contract §4.3]. One more key in
the same Secret does not widen that boundary. Credentials never appear in
`osac_job_vars`, `osac_result`, job labels, or task logs; the contract's existing
prohibition is extended to `cluster`.

**Operator privilege.** The operator can read every registered cluster's
kubeconfig and act as `cluster-admin` on each. The credential comes from the
cluster's registration (OSAC-977), not from the management `Hub`'s `hub-access`
service account, whose namespace RoleBinding and narrow ClusterRole grant no
KubeVirt, CUDN, NetworkPolicy, or VTEP rights. RBAC for the cluster credentials
stays in the operator namespace and is granted to the operator and the
credential provider only.

**Token lifetime.** A staged service-account token is valid for 365 days and is
not renewed [Codebase: osac-installer/scripts/stage-remote-cluster-secret.sh].
With `N` clusters this becomes `N` silent expiries instead of one. The readiness
probe turns an expired credential into `KubeconfigRejected` / `ClusterUnreachable`
on the `WorkloadCluster` before a tenant operation fails; rotation is the
foundation's (OSAC-7828 updates credentials for an existing registration without
re-registering).

**Validation and blast radius.** The target is validated at tenant create, so an
unprepared cluster cannot receive a tenant; and a resource's cluster is
immutable, so a task cannot be redirected after creation. A compromised or
misconfigured manager still cannot exceed `cluster-admin` on the cluster whose
kubeconfig it selected, and it selects only from the clusters the deployment
registered.

**Tenant isolation.** Unchanged and not weakened: isolation comes from
VirtualNetwork and Subnet identity plus the per-VirtualNetwork namespace on the
VM cluster, and `cluster.id` is informational like `tenant`
[Codebase: OSAC-1433 network manager integration contract §4.12].

## 4.6 Failure Handling and Recovery

| Failure | Behavior | Recovery |
|---|---|---|
| Cluster unreachable at task launch | Job fails; `osac_error.retryable=true`; entry `Retrying` with existing backoff | Probe sets `TenantNetworkingReady=False/ClusterUnreachable`; task succeeds on retry once reachable |
| Cluster becomes unprepared after assignment | The task rechecks its prerequisites and fails with a message naming the unmet prerequisite [R-11] | Fix the prerequisite; retry succeeds without tenant action |
| Kubeconfig rejected or expired | `KubeconfigRejected` on the `WorkloadCluster`; task fails with HTTP 401 named, no token in the message | Update the registration; no operator restart |
| Two tasks target the same cluster concurrently | Objects are per-VirtualNetwork and applied idempotently; the per-VirtualNetwork slot orders Subnet tasks of one VirtualNetwork and the VNI lock orders result acceptance and status writes. Neither limits concurrent jobs per cluster | — |
| Operator restart mid-job | Unchanged: `status.jobs` attempts, label lookup, `LostLaunchTimeout`, retry seeding from the attempt | — |
| Cluster removed while a tenant is assigned | The placement foundation rejects removal (OSAC-977); this design adds no `Hub` guard | Assigning the tenant elsewhere is unsupported; the admin must not remove the cluster |
| Cluster removed with no tenant assigned | Its client is disengaged, caches cancelled; in-flight reconciles for that cluster return `NotFound` | Re-registering the cluster resumes on the next probe |
| Annotation missing on a CR | Task is not launched; the CR reports `NetworkReady=False` with reason `VmClusterNotAssigned` | Fulfillment recreates the CR; the value is written at creation only |
| NetworkAttachment validation on the wrong cluster | `apply_network_attachment` returns a namespace that the operator must verify on the CR's target cluster; the local API reader would reject a valid remote namespace as "does not exist" | The operator resolves the target cluster for `ParseVMAttachment` and reads the namespace there |
| Delete while provisioning | Unchanged: `CancelForDelete`, cleanup tasks only, delete waits for the remote namespace to be gone | — |

**Idempotency.** Every Kubernetes Manager task is already a server-side apply or
an owner-labelled lookup keyed by API ID, so retrying against the same cluster
converges. Retrying against a *different* cluster cannot happen: the annotation
is immutable, and a CR whose cluster no longer exists fails as final rather than
falling back to the management cluster [R-11].

**No fallback.** A task never runs on the management cluster because its
annotated cluster is unavailable. Falling back would place tenant traffic on the
wrong network and silently violate isolation.

## 4.7 RBAC / Tenancy

No tenant-facing RBAC change. Tenants never observe the cluster identity: no
API field, error, event, or condition exposed to tenants names it [NG-7, Locked: D17].
Because the `ComputeInstance` `NetworkReady` condition is copied through feedback
to the public API, its tenant-facing reason and message stay generic (for example
`VmClusterNotReady`); the cluster name and the unmet prerequisite appear only on
provider-side surfaces: the `WorkloadCluster` condition, the job entry, the
`NetworkAttachment` status, and operator events. `VmClusterNotAssigned` follows the
same rule.

Provider-side:
- Cloud Provider Admin assigns the cluster at tenant creation — placement
  foundation; this design only rejects bad assignments [R-5].
- Cloud Infrastructure Admin registers, prepares, and removes VM-hosting
  clusters, which requires `cluster-admin` on the VM cluster, as today [R-2].
- The operator's Kubernetes RBAC keeps Secret access in its own namespace for the
  per-cluster credentials, and nothing cluster-scoped.

Tenant isolation edge case: two tenants assigned to the same VM cluster share the
cluster but not namespaces, VirtualNetworks, or SecurityGroups; the existing
`osac-vn-<id>` and `osac-sg-<id>` naming keeps them disjoint [R-9].

## 4.8 Extensibility / Future-Proofing

- **Adding a cluster** is register, prepare, wait for the condition. No per-tenant
  or per-VM step [R-2].
- **The second increment** changes only where the assignment comes from. The
  annotation, the task input key, the readiness condition, and the role are
  unchanged [DS-3].
- **Other managed services** (CaaS, BMaaS) can adopt `cluster.id` targeting
  without a new contract, because it is a contract-level key rather than a
  `cudn_evpn` detail.
- **Deliberately not built:** a second cluster registry, a per-cluster credential
  store, a per-cluster manager registration, a placement UI, and automated
  cluster preparation. Each would have to be undone if the placement foundation's
  model differs from `WorkloadCluster`.

# 5. Interface Changes

## IC-1: `WorkloadCluster.status.conditions` with `TenantNetworkingReady`

**Requirements:** R-2, R-5, R-10, R-11

`WorkloadClusters.Get` and `WorkloadClusters.List` return conditions. The operator
sets `TenantNetworkingReady` with the reasons in §4.1.6. This is the surface an
administrator inspects to learn why a cluster cannot be assigned. See §4.1.6.

## IC-2: Tenant-create target validation

**Requirements:** R-3, R-5, R-6

`Tenants.Create` rejects a missing, unknown, removing, unready, or
capability-less target with `InvalidArgument` naming the cluster and the unmet
prerequisite. Removal of a VM-hosting cluster is guarded by the placement
foundation. See §4.1.2 and §4.3.

## IC-3: `osac.openshift.io/vm-cluster` CR annotation

**Requirements:** R-4, R-7

Fulfillment writes the resolved cluster name on `VirtualNetwork`, `Subnet`,
`SecurityGroup`, `NetworkAttachment`, and `ComputeInstance` at creation and never
patches it. The operator copies it onto the `NetworkAttachment` it creates for a
`ComputeInstance`, reads it to select a cluster client, and uses it to populate
task input. See §4.1.2.

## IC-4: `osac_job_vars.cluster.id` task-input key

**Requirements:** R-7

Kubernetes Manager tasks receive `cluster: {id: <cluster name>}`; Fabric Manager
tasks do not. The key is already in contract §4.5; this design consumes it. See
§4.1.4.

## IC-5: `cudn_evpn` targets the task's cluster

**Requirements:** R-7, R-9

All Kubernetes Manager tasks accept `osac_job_vars.cluster.id`, read the
kubeconfig from `/var/run/secrets/osac/clusters/<id>`, and use it for the
namespace, CUDN, and NetworkPolicy objects on that cluster. OSAC `Subnet` reads
stay on the hub with the job pod's service account. A missing `cluster` or
kubeconfig fails the task; there is no fallback. Object names, labels, owner
annotations, and idempotency are unchanged. See §4.1.4.

## IC-6: Per-cluster clients and engagement in the operator

**Requirements:** R-1, R-7, R-11

The operator resolves the target per CR and reuses the placement foundation's
per-cluster connection mechanism; it removes `--remote-cluster-kubeconfig`, the
kubeconfig digest-restart loop, and the remote-plus-networking startup guard.
ComputeInstance provisioning and deletion, network attachment validation, and
network task launch resolve that target per CR instead of process-wide. Console
proxy routing, storage status keys, and Volume placement are unchanged here and
remain with their owning designs. See §4.1.3 and §4.6.

## IC-7: Per-cluster kubeconfig channel for networking jobs

**Requirements:** R-2, R-7

The networking instance group mounts one kubeconfig per registered cluster, keyed
by the cluster name, at `/var/run/secrets/osac/clusters/<id>`. The keys come from
the cluster registrations (OSAC-977); this design does not define a second
credential store. The single `aap.configAsCode.remoteClusterKubeconfigSecretName`
value stops being the source for networking tasks. Compute and storage instance
groups keep their own credential wiring, owned by VMaaS and the storage designs.
See §4.1.4 and §4.5.

## IC-8: `prepare-vm-cluster` installer target

**Requirements:** R-1, R-2, R-12

`make prepare-vm-cluster HUB_NAME=... VM_KUBECONFIG=... [EVPN_VALUES=...]`
generalizes `prepare-remote-cluster`: cluster prerequisites, EVPN host setup via
the existing `configure-evpn.sh` hook (including the BGP-established wait),
namespace, storage-class label, and the `osac-remote-access` service account.
Idempotent; safe to re-run. See §4.1.5.

## IC-9: VM network diagnostic

**Requirements:** R-11

When the annotated cluster is unavailable or unprepared, `ComputeInstance`
reaches `NetworkReady=False` with a generic tenant-facing reason and message.
The cluster name and the unmet prerequisite appear in the job entry and the
`WorkloadCluster` condition, not in the public API. Deletion still completes only
after remote cleanup. See §4.6 and §4.7.

**Requirements with no interface change.** R-8 (external access parity) and R-10
(networking-disabled configuration) add no field, value, endpoint, or task. R-8
keeps `ExternalIP`, `ExternalIPPool`, `ExternalIPAttachment`, and `NATGateway`
messages and pool-based allocation unchanged, with the same Fabric Manager
registration (§4.1.8). R-10 keeps today's skip behavior (§4.1.9). Both are
verified by behavior tests rather than by exercising a new surface.

# 6. Alternatives Considered

**Register VM clusters as `Hub`s.** Rejected. In code a `Hub` is where
fulfillment *places CRs*: `selectHub` picks a random active `Hub` for Volumes
always and for resources without a network attachment, and onboarding writes a
`Tenant` CR to every `Hub`. A VM cluster has no OSAC CRDs and no operator, so it
would receive CRs it cannot reconcile and break onboarding. The accepted
networking decision also supports one hub. `WorkloadCluster` already models "a
cluster that can host workloads", so the design uses it.

**One operator instance per VM cluster.** Highest failure isolation, since a
broken cluster cannot disturb others. Rejected: it multiplies deployments,
leases, and upgrade paths by `N`, gives each instance a single-cluster world view
that cannot observe a tenant's management-cluster state, and contradicts the
accepted architecture's one-operator-per-deployment shape. It also re-implements
multicluster engagement that the existing provider already gives OSAC.

**Move every tenant-scoped CR onto the tenant's VM cluster.** Conceptually
tidiest: the CR's location *is* the target, so no annotation and no task-input
key are needed. Rejected: it converts ten controllers, their feedback twins, two
field indexes, and `Tenant` lookups to multi-cluster semantics, changes watch
scope and finalizer behavior for every resource, and makes every OSAC CR depend on
every VM cluster. The security and tenancy review surface alone exceeds the
feature's scope.

**Pass a per-job kubeconfig inside `osac_job_vars`.** No new Secret, no mount.
Rejected: it puts cluster credentials into task input, which the contract forbids
outright, and it would leak into job artifacts and error payloads.

**Keep one canonical networking hub and select a deployment-wide placement mode.**
Rejected by the PRD: placement is per tenant, one cluster per tenant, and the
management cluster has no special status [Locked: D10, D13].

**Compute readiness in fulfillment-service.** Rejected: fulfillment already holds
a client per cluster, but the prerequisites are the Kubernetes Manager's (VTEP,
`RouteAdvertisements`, CUDN, KubeVirt). Duplicating that knowledge in fulfillment
puts the gate and the eventual task failure in different components, so a cluster
could pass the gate and still fail every task.

**An OSAC reconciler that prepares a cluster at registration.** Rejected: VTEP
range allocation, cluster AS, and BGP peering need the provider's network team, so
a reconciler would apply a partial configuration and could report readiness for a
cluster the fabric cannot reach. The idempotent installer step plus the readiness
probe gives the same operational outcome without a false success signal.

**Choose the target inside this design when the foundation has none.** Rejected:
the design would define placement, and any rule it invented — a fallback to the
management cluster, or a count of registered clusters — would be replaced when
OSAC-977 lands and could move an existing tenant's VMs. Placement stays with the
foundation; this design rejects a tenant with no target.

# 7. Observability and Monitoring

- **Metric** `osac_cluster_tenant_networking_ready{cluster,reason}` — gauge, 1
  when the condition is `True`. Alert on `0` for a cluster with assigned tenants.
- **Metric** `osac_network_task_target_total{cluster,task,result}` — counter,
  emitting the cluster a job targeted. Makes a systematic mis-targeting visible
  without reading job logs.
- **Event** on `WorkloadCluster` condition transitions, and on `ComputeInstance`
  when the cluster gate blocks provisioning.
- **Logs** — the network task launch line gains `cluster`; the readiness probe
  logs one line per unmet prerequisite at `Info`, not per poll.
- **Existing signals reused:** `status.jobs` entries and their `RetryMessage`
  text, which now carry the prerequisite message.

# 8. Impact and Compatibility

**Backward-compatible for a fresh single-cluster and single-workload-cluster
install** [R-12, Locked: D19]: one registered VM-hosting cluster resolves through
the foundation, the condition is `True`, and every task targets the same cluster
as today. The observable tenant behavior — attachment, address, readiness,
external access, cleanup — is unchanged. `WorkloadCluster.status.conditions` is
additive; `NetworkClass` is untouched.

**Relies on (already merged).** The unified hub boundary and the network manager
contract's `cluster: {id}`, per-cluster kubeconfig, and Kubernetes-Manager task
definition were merged with PR #514 (OSAC-7630) [Codebase: OSAC-1433 network
manager integration contract §4.3, §4.5, §4.10, §4.12; OSAC-1433 unified
networking design]. The CUDN prerequisites and the VMaaS non-goals are likewise
already recorded.

**Amendments this design needs:**
- OSAC-6488: allow `vmaas` in `WorkloadCluster.spec.supported_workloads`, and add
  the `TenantNetworkingReady` condition type.
- OSAC-977: supply the tenant's target and the per-cluster credentials; guard
  removal while a tenant is assigned or cleanup is outstanding; define the
  default target for the first increment.
- OSAC-7828: credential update for an existing registration (consumed, not
  changed).
- Network manager contract §4.11 (conformance against a non-hub VM cluster) and
  §4.14 (standalone `cluster.id` source).
- OSAC-2434 (Netris): per-cluster AS, VTEP, and peering values, and V-Net
  placement on the leaves that face each cluster.
- OSAC-1435 (VMaaS networking): its `cluster: {id: <hub name>}` wording becomes
  `{id: <VM-hosting cluster name>}`; the key, the annotation, and the credential
  channel are unchanged.
- The default-networking design: onboarding waits (`ResourcesPending`) while
  prerequisites are unready, whereas this design rejects at tenant creation.
  The two must agree; this design keeps rejection because the target is chosen by
  an administrator who can see the condition.
- [`docs/agent-context/networking-decisions.md`](https://github.com/osac-project/osac/blob/main/docs/agent-context/networking-decisions.md)
  must be updated in the OSAC repository in the same change.
- Coordination with open PRs #521 (runtime VMaaS registration), #518 and #513
  (Volume targeting), and #478 (AI Grid workload-cluster selection).

**Breaking, deployment-side:**
- `--remote-cluster-kubeconfig` and `operator.remoteClusterKubeconfig*` are
  removed; the operator resolves clusters per CR.
- `aap.configAsCode.remoteClusterKubeconfigSecretName` stops being the source for
  networking tasks; the networking instance group gets one key per cluster.
- The network manager contract's `cluster` key is required for Kubernetes
  Manager tasks; a role that receives none fails instead of using the job pod's
  cluster.
- An installation that today uses the remote-cluster shape must register that
  cluster as a `WorkloadCluster` and run `prepare-vm-cluster`. No data migration
  is involved because CRs stay where they are.

**Version skew.** The operator and AAP image must be upgraded together: an
operator that sends `cluster` to a role that ignores it silently targets the job
pod's cluster, which is the one failure mode this design must not allow. The
installer gates on both images matching; release-pinned images are what protect
the deployment, because an older `cudn_evpn` has no `cluster` in its
`argument_specs.yaml` and ignores the key silently. The role itself must fail when
a Kubernetes Manager task has no `cluster`, so a partial upgrade surfaces as a
failed task instead of a wrong placement. A provider-supplied Kubernetes Manager
is out of scope, as the contract already states.

# 9. Open Questions

## 9.1 What is the exact shape of the tenant's assigned-cluster field?

- **Owner:** OSAC-977 owners
- **Impact:** §4.1.2 and IC-2. This design consumes one read-only value naming a
  `WorkloadCluster`. If OSAC-977 records the assignment differently — for example
  by qualifying a cluster with a capability rather than naming it directly — the
  resolver and the error messages change, and IC-3's annotation value changes with
  them. The same question covers the first increment's default target.

## 9.2 How are VTEP CIDRs and cluster AS numbers allocated across VM clusters?

- **Owner:** Provider network team
- **Impact:** §4.1.5 and the readiness probe's VTEP advertisement check. The
  contract already requires non-overlapping VTEP CIDRs per cluster; OSAC keeps no
  copy, so it cannot validate uniqueness at registration. Two VM clusters with
  overlapping VTEP CIDRs or the same cluster AS will both report
  `TenantNetworkingReady=True` and then break at the fabric. The preparation step
  or the Fabric Manager settings must become the recorded value if OSAC is to
  detect it.

## 9.3 Does a registered cluster need an explicit "VM hosting" capability?

- **Resolved:** yes, and `WorkloadCluster.spec.supported_workloads` is it. This
  design requires `vmaas` and rejects a target without it (§4.1.2). The remaining
  work is the OSAC-6488 allow-list amendment in §8.

## 9.4 Should the readiness probe also verify the fabric path?

- **Owner:** Networking maintainers
- **Impact:** IC-1 reasons. The probe checks cluster-local prerequisites and
  preparation verifies each node's BGP session. A cluster whose session is
  established but whose fabric VRF is missing reports ready and fails at the
  first Subnet. Adding a fabric-side check requires the fabric manager to expose
  verification, which §4.10 of the contract does not define.

---

## Provenance

Authored: draft @ design 0.14.0 - 70405a6, workspace vmaas @ 126b81a70

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.14.0","ai_workflows":"70405a6","source_repo":"126b81a70","source_repo_branch":"vmaas","commits_behind_main":0,"commits_ahead_main":8,"main_ref":"main","phases":["draft"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
