---
title: caas-bare-metal-worker-provisioning
authors:
  - rpiccoli@redhat.com
creation-date: 2026-08-06
last-updated: 2026-11-11
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-2135
prd:
  - "prd.md"
see-also:
  - "/enhancements/OSAC-2540-disk-image"
  - "/enhancements/OSAC-1201-baremetal-instance-types"
  - "/enhancements/OSAC-1330-type-safe-resource-references"
  - "/enhancements/OSAC-1436-caas-networking"
  - "/enhancements/OSAC-1589-vm-worker-caas"
replaces:
  - N/A
superseded-by:
  - N/A
---

# CaaS Bare-Metal Worker Node Provisioning

## Summary

This design adds on-demand bare-metal worker node provisioning to CaaS via a dedicated `BareMetalWorkerReconciler` in osac-operator that creates BareMetalInstances via the fulfillment-service private gRPC API. Each instance references a pre-registered RHCOS DiskImage and carries discovery ignition inline from a cluster-specific InfraEnv, causing the host to register as an assisted-service Agent and join the HyperShift-managed cluster as a worker node. The existing BareMetalPool-based static pre-boot pool is removed. See [PRD](prd.md) for detailed requirements.

## Motivation

CaaS currently provisions bare-metal worker nodes through a static pre-boot pool: a cron job maintains hosts running the Assisted Installer ISO via BareMetalPool resources. This wastes capacity on idle hosts, is difficult to right-size, and couples cluster provisioning to a fragile pool management process. When the pool is exhausted, cluster scale-up fails silently until an administrator intervenes.

The new approach eliminates the pool by provisioning workers on-demand. When a ClusterOrder specifies bare-metal node sets, the controller creates individual BareMetalInstances through the BMaaS private API, each configured with discovery ignition and a version-matched RHCOS DiskImage. This gives CaaS per-instance control over image and boot configuration while keeping cluster lifecycle (templates, catalogs, ordering) free of infrastructure details. The PoC (OSAC-2817) validated this flow end-to-end: BMI provisioning took approximately 6 minutes, the agent registered successfully, and the worker joined the HyperShift cluster.

### Goals

- Implement bare-metal worker management as a dedicated controller (`BareMetalWorkerReconciler`) within osac-operator, keeping the ClusterOrder controller generic and extensible for future VM worker support.
- Keep InfraEnvs and Agents private, while exposing worker BMIs in the owning tenant's scope with provenance to the Cluster; cluster capacity remains managed through the Cluster API.
- Support both initial provisioning and manual scale-up/scale-down through the same controller logic.
- Ensure host cleanup on scale-down and cluster deletion flows through BMaaS's existing deprovision pipeline via `BareMetalInstances.Delete`.
- Remove the BareMetalPool-based static pre-boot pool workflow entirely — no coexistence period.
- Require no changes to the tenant-facing Cluster API or CLI experience.

### Non-Goals

- Autoscaling based on workload utilization (deferred to a future CaaS autoscaling feature).
- VM-based worker nodes (deferred to VMaaS integration).
- Static IP or NMStateConfig support for worker nodes (deferred; not validated by the PoC).
- Network boot acceleration or caching strategies `[Jira: OSAC-2134]`.

## Proposal

A new `BareMetalWorkerReconciler` in osac-operator watches `ClusterOrder` CRs for bare-metal worker management. When a ClusterOrder's `nodeRequests` reference bare-metal node sets, the controller:

> **Terminology note:** `node_sets` (proto, on `ClusterSpec`) maps to `nodeRequests` (CRD, on `ClusterOrderSpec`) via the fulfillment-service Cluster controller. The proto map key becomes `NodeRequest.nodeSet`. The `BareMetalWorkerReconciler` reads `nodeRequests` from the ClusterOrder CRD.

1. Creates a cluster-specific `InfraEnv` CR on the hub cluster to generate discovery ignition.
2. Fetches discovery ignition from the InfraEnv and creates `BareMetalInstance` objects with the ignition passed inline as `user_data`, referencing the RHCOS DiskImage.
3. Correlates registered Agents to BMIs and applies the networking-aware binding gate before approving, binding, or labeling them for NodePool selection.

No new CRDs are introduced. The design extends the ClusterOrder CRD status with a `workers` field to track CaaS-managed worker resources. BareMetalInstances created by CaaS belong to the cluster's tenant (see Worker Tenancy and Ownership) — the controller resolves the authoritative tenant from the fulfillment-service Cluster on every reconciliation and fails closed on any mismatch.

**Dependencies:**

| Dependency | Jira | Provides |
|-----------|------|----------|
| MAC addresses in BareMetalInstance status | [OSAC-4203](https://redhat.atlassian.net/browse/OSAC-4203) | `status.hardware.nics[].mac` — host NIC MACs (multiple per host) for Agent correlation |
| DiskImage resource + BMI DiskImage integration | [OSAC-2540](https://redhat.atlassian.net/browse/OSAC-2540), [OSAC-1270](https://redhat.atlassian.net/browse/OSAC-1270) | The DiskImage resource and the `DiskImageReference disk_image` field on `BareMetalInstanceSpec` |
| Type-safe resource references | [OSAC-1330](https://redhat.atlassian.net/browse/OSAC-1330) | `DiskImageReference` typed references on `ClusterVersionSpec` (field 7) and on `BareMetalInstanceSpec` |
| BMaaS networking for subnet attachment | [OSAC-1437](https://redhat.atlassian.net/browse/OSAC-1437) | BMI `network_attachments` accepting at most one entry |

The existing BareMetalPool-based static pre-boot pool is removed as part of this work. The `cluster_infra` AAP step that creates BareMetalPool CRs and the scheduled `osac-import-agents` AAP job that discovers and imports hosts are no longer used by CaaS. Any remaining BareMetalPool resources are drained and cleaned up during rollout. The BareMetalPool CRD itself is retained (it serves BMaaS standalone use cases) but CaaS no longer creates or references BareMetalPool resources.

### Workflow Description

#### Changes Overview

This design replaces `HostType` with `BareMetalInstanceType` and the static agent pool with on-demand BMI provisioning. The key changes per component:

| Component | Before | After |
|---|---|---|
| **ClusterNodeSet (proto)** | `host_type: HostTypeReference` | `baremetal_instance_type: BareMetalInstanceTypeReference` (field 4, immutable); system-populated `fabric_interface` (field 3, private) |
| **NodeRequest (CRD)** | `ResourceClass string` (opaque) | `nodeSet` (logical group key) + `numberOfNodes` + `bareMetal.instanceType` (+ system-populated `fabricInterface`) |
| **ClusterCatalogItem** | `host_type: "acme_1tb"` in template YAML | `fields.node_sets` policy: locked map or editable map with defaults, entries carry `size` + `baremetal_instance_type` |
| **ClusterVersionSpec (proto)** | No DiskImage reference | `disk_image: DiskImageReference` (owned by this design) |
| **BMI Create call** | No `instance_type` field | `spec.template` = shared `osac.templates.bm_host_provisioning`; `spec.instance_type` = `BareMetalInstanceTypeReference`; `spec.disk_image` = `DiskImageReference` |
| **Interface resolution** | HostType.interfaces[].role=fabric | BareMetalInstanceType network_ports[].role=fabric |
| **Network attachment source** | Cluster proto via private API callback | ClusterOrder CRD singular `networkAttachment` (ClusterNetworkAttachment) |
| **Host selection** | HostType → Template → CatalogItem reverse lookup | BareMetalInstanceType host label selector (direct, OSAC-1201) |
| **Worker provisioning** | Static pre-boot pool + cron job + parking network | On-demand BMI creation via private API |
| **Boot image** | Assisted image service ISO | RHCOS DiskImage (OCI artifact) linked to ClusterVersion |
| **HostType resource** | Shared BM/VM concept, no hardware specs | Deprecated and decommissioned |

#### Setup Flow (by persona)

**Cloud Infrastructure Admin** — one-time platform setup:

1. **Register RHCOS DiskImages** for each supported OCP version. CaaS boots bare-metal hosts with a RHCOS qcow2 image containing discovery ignition — unlike the old pool model which used ISOs from the assisted image service. Each DiskImage is an OCI artifact registered in the fulfillment-service (dependency: OSAC-2540, OSAC-1270).

   ```bash
   osac create diskimage rhcos-4.18 \
     --source-ref quay.io/osac/rhcos:4.18.0 \
     --guest-os-family linux --architecture x86_64
   ```

2. **Link each DiskImage to its ClusterVersion** via the `disk_image` reference (this design adds `DiskImageReference` to `ClusterVersionSpec`). This is how the controller resolves which boot image to use — it reads the Cluster's ClusterVersion, follows the reference, and passes the DiskImage reference to the BMI Create call. Without this link, the controller sets `RHCOSImageNotFound` and does not create BMIs.

   ```bash
   osac create clusterversion 4.18.0 --image <release-image> --disk-image rhcos-4.18
   ```

   The private `ClusterVersions.Update` RPC accepts `spec.disk_image` (the CLI exposes it at create time via `--disk-image`; later changes go through `osac edit clusterversion` or the API).

3. **Register BareMetalInstanceTypes** defining available hardware profiles. This replaces `HostType`, which was opaque (no CPU/memory specs, no inventory matching). `BareMetalInstanceType` (OSAC-1201) carries full hardware specs AND `host_label` selectors for direct inventory matching — no reverse lookup needed. The `network-port` fields are critical for CaaS: the controller reads them to resolve the fabric interface for each BMI's network attachment. CaaS resolves BareMetalInstanceType references in the **shared** tenant (see [BareMetalWorkerReconcilerS.md](https://github.com/osac-project/osac/blob/main/fulfillment-service/docs/BareMetalWorkerReconcilerS.md)); tenant-scoped CaaS type selection is not yet defined.

   ```bash
   # BEFORE — HostType (opaque, no hardware specs, no inventory matching)
   osac create hosttype acme_1tb \
     --title "Acme 1TB Server" \
     --interface name=data-0,role=fabric \
     --interface name=mgmt-0,role=management

   # AFTER — BareMetalInstanceType (rich hardware specs + inventory matching)
   osac create baremetalinstancetype bm-standard \
     --cpu-cores 64 --cpu-architecture x86_64 \
     --memory-total-gb 512 \
     --network-port name=data-0,role=fabric,type=Ethernet,speed=100Gbps \
     --network-port name=mgmt-0,role=management,type=Ethernet,speed=1Gbps \
     --host-label profile=bm-standard \
     --description "Standard bare-metal node: 64-core x86_64, 512 GiB RAM, 100GbE fabric"
   ```

   Cloud Infrastructure Admins must also label inventory hosts to match — via whatever host-labeling mechanism the BMaaS backend exposes. This is a BMaaS/backend concern; CaaS does not assume a specific backend and OSAC does not validate label consistency at type-creation time.

4. **Ensure the assisted image service is disabled** (deployment prerequisite — see Assisted Image Service section).

**Cloud Provider Admin** — catalog and template configuration:

1. Creates `ClusterVersion` entries (OCP version + release image pullspec), or they are seeded during installation.

2. Creates a `ClusterCatalogItem` (cluster offering) whose `fields.node_sets` policy supplies the worker map. Cluster templates describe provisioning behavior and parameters; they no longer carry node sets or hardware (the template `node_sets` field is reserved). A policy is either **locked** (fixed map) or **editable** (defaults the tenant may override):

   ```yaml
   # ClusterCatalogItem policy (private API / CLI)
   fields:
     node_sets:
       editable:
         default_value:
           items:
             workers:
               size: 2
               baremetal_instance_type:
                 name: bm-standard
   ```

   Tenants can override an editable policy at cluster creation:

   ```bash
   osac create cluster --catalog-item hosted_cluster_offering \
     --node-set name=workers,size=2,baremetal-instance-type=bm-standard
   ```

   This flows through to the proto as `ClusterNodeSet.baremetal_instance_type` (replacing `ClusterNodeSet.host_type`) and to the CRD as `NodeRequest.bareMetal.instanceType` (replacing `NodeRequest.ResourceClass`). The fulfillment-service resolves the effective BareMetalInstanceType references in the shared tenant and writes each selected type and size to `ClusterOrder.spec.nodeRequests[].bareMetal.instanceType` and `numberOfNodes`.

3. No per-offering BMI catalog item or template is needed: worker BMIs are created through the fixed shared `osac.templates.bm_host_provisioning` BareMetalInstanceTemplate (see BMI Creation via Private API). The Cloud Provider Admin does not create or configure it — it ships with the OSAC AAP template collection.

4. Publishes catalog items to make them available to tenants.

**Tenant User** — cluster lifecycle (unchanged before and after):

```bash
# Same CLI, same UX — before and after
osac create cluster my-cluster --template ocp-small
```

The tenant never directly manages BareMetalInstanceTypes, DiskImages, InfraEnvs, or Agents. The catalog item's node-set policy (or the `--node-set` flag) populates `node_sets` with the `BareMetalInstanceType` reference and size. Tenant-visible infrastructure (worker BMIs, the backing DiskImage) is created in the tenant's own scope; see Worker Tenancy and Ownership for the visibility consequences.

#### Provisioning Flow

Starting state: a Tenant User creates a Cluster from a catalog item (e.g., `hosted_cluster_offering`). The catalog item's node-set policy populates `node_sets` with `baremetal_instance_type` references. The fulfillment-service Cluster controller creates a ClusterOrder CR on the hub cluster.

```mermaid
sequenceDiagram
    participant T as Tenant User
    participant FS as fulfillment-service
    participant CO as ClusterOrder Controller
    participant BMW as BareMetalWorkerReconciler
    participant AAP as AAP Provisioning
    participant BMaaS as BMaaS (Private API)
    participant AS as assisted-service
    participant HCP as HyperShift

    T->>FS: Create Cluster (node_sets with BM instance types)
    FS->>CO: Create ClusterOrder CR

    CO->>AAP: Trigger cluster provisioning job
    AAP->>HCP: Create HostedCluster + NodePool
    HCP-->>BMW: ClusterDeployment exists

    BMW->>BMW: Create InfraEnv CR (late binding, no clusterRef)
    AS-->>BMW: InfraEnv ready (discovery ignition available)
    BMW->>BMW: Wait for HostedCluster and ManagementPublicationReady=True before worker Create

    loop For each requested bare-metal worker
        BMW->>BMaaS: Create BareMetalInstance (qcow2 + ignition)
        BMaaS-->>BMW: BMI network-ready evidence and selected-port lease in status
    end

    loop Agent registration
        AS-->>BMW: Agent registered (MAC in inventory)
        BMW->>BMW: Unique correlation plus BMI Ready and management; DNS/selected-port lease only when networking enabled
        BMW->>AS: Only after gate passes: approve, bind and label for NodePool
    end

    HCP-->>BMW: Workers joined, NodePool scaled
    CO->>FS: Signal Cluster (state=Ready)
```

The diagram shows the end-to-end provisioning flow. The controller waits for each phase to complete before proceeding: AAP provisions the HostedCluster, the InfraEnv generates ignition, BMIs provision hosts, and agents register and join the cluster. The controller updates ClusterOrder status conditions at each phase transition.

**Step-by-step:**

1. The `BareMetalWorkerReconciler` identifies bare-metal node sets from the ClusterOrder's `nodeRequests` — any node request whose `bareMetal` block carries an `instanceType` reference (see ClusterNodeSet Redesign).
2. After AAP creates the HostedCluster and the ClusterDeployment CR exists, the controller creates a cluster-specific `InfraEnv` CR (see InfraEnv Creation). The InfraEnv uses late binding (no `clusterRef`) — agents register as unbound and the controller explicitly binds them in step 8.
3. The controller polls the InfraEnv status until `status.bootArtifacts.discoveryIgnitionURL` is populated, then fetches the discovery ignition content. The ignition is architecture-neutral (the `assisted-installer-agent` image is a multi-arch manifest).
4. For each bare-metal worker requested, the controller assembles a `BareMetalInstances.Create` call on the private API from multiple sources:

   | Field | Source | Purpose |
   |---|---|---|
   | `instance_type` | `nodeRequests[i].bareMetal.instanceType` (shared scope) | Hardware profile → host labels → inventory match |
   | `template` | Fixed shared `osac.templates.bm_host_provisioning` | Required by private API; ships with the OSAC AAP template collection |
   | `disk_image` | `ClusterVersion.disk_image` → resolved `DiskImageReference` (id + name) | RHCOS boot image for discovery agent |
   | `user_data` | InfraEnv ignition (inline, ~15KB, max 64KB) | Discovery ignition to register with assisted-service |
   | `ssh_public_key` | `ClusterOrder.spec.sshPublicKey` (or template parameter fallback) | SSH access to worker hosts |
   | `network_attachments` | `networkAttachment` + stored node-request `fabricInterface` | The sole attachment from `ClusterNetworkAttachment`; the stored interface was selected from the first `fabric` port during cluster creation, with `primary: true` (see Network Attachment Enrichment); BMaaS rejects additional entries |
   | `tenant` | The cluster's tenant, resolved authoritatively from the fulfillment-service Cluster | Ownership and audit; the controller fails closed on any ClusterOrder/Cluster tenant mismatch (see Worker Tenancy and Ownership) |

   BMaaS owns the physical attachment, handoff power cycle, and lease discovery (dependency: OSAC-1437). Before handoff CaaS waits; after handoff, the registration deadline detects an Agent that never proves the worker network (see MAC Address Correlation). OSAC-1436 owns endpoint publication: provider management MetalLB supplies the hosted API VIP, OSAC allocates the guest ingress address, and a separate guest endpoint job configures guest MetalLB. The core install job creates the HostedCluster and NodePools, not guest MetalLB. This worker controller manages none of those endpoint allocations or public DNS records.
5. The controller updates ClusterOrder status with the BMI references in `workers[]`. Each worker slot is first **reserved** in `status.workers[]` with an opaque generated name (see ClusterOrder CRD Status Extensions), and the BMI identity is persisted as part of the slot's record — the status journal is the durable source of truth for worker identity, so a crash or lost response can never produce an untracked BMI.
6. BMaaS allocates a host, provisions it with the DiskImage and discovery ignition, and boots it. The host registers as an Agent with assisted-service.
7. The controller watches Agent CRs in the cluster namespace. Initial correlation is unique in both directions. With provider networking enabled it uses the selected NetworkAttachment port's MAC and accepted BMI IPv4 lease, not any NIC's MAC or the provisioning-network address; with networking disabled it uses the scoped host-NIC MAC fallback (see MAC Address Correlation).
8. Only after correlation and the binding gate pass (BMI phase `Ready`, `ManagementPublicationReady=True`, and, with provider networking enabled, published API records and selected-MAC/lease proof), the controller sets the Agent's `clusterDeploymentName`, marks it `approved: true`, and applies the `agentBareMetal` role label plus `osac.openshift.io/worker-name`, `osac.openshift.io/node-set`, `osac.openshift.io/instance-type`, and cluster-order labels for NodePool selection. On scale-down CAPA clears `clusterDeploymentName`, triggering cleanup. A binding already rewritten by HyperShift's CAP-Agent handoff for the same worker is left untouched. The osac-operator's RBAC includes `get`, `list`, `watch`, `patch`, and `delete` on `agents` in the `agent-install.openshift.io` API group (see RBAC / Tenancy).
9. HyperShift installs the Agent as a worker node. The controller converges NodePool `.spec.replicas` to the requested per-node-set capacity so provisioning Agents are not orphaned by premature scale-down.

#### Scale-Up

A Tenant User increases `node_sets[].size` for a bare-metal node set. The fulfillment-service updates the Cluster object, the Cluster controller updates the ClusterOrder's `nodeRequests`, and the controller detects the delta between desired and current worker count.

**Step-by-step:**

1. The controller compares requested capacity with the persisted worker slots and creates BMIs for missing workers. It keeps healthy BMIs if a retry temporarily exceeds the requested NodePool size; CAPI drains its normally selected surplus Machine to converge.
2. The controller reads the cluster InfraEnv's `status.bootArtifacts.discoveryIgnitionURL` and uses it as the discovery ignition for each new worker.
3. The controller resolves the RHCOS DiskImage from the cluster's current ClusterVersion's `disk_image` reference (see RHCOS DiskImage Resolution).
4. For each new worker, the controller follows provisioning steps 4-9 from the initial flow (the ignition content is re-fetched in step 2 above).
5. Partial success is reported: if 3 of 5 new workers succeed and 2 fail, the ClusterOrder status shows 3 additional `Ready` workers and 2 `Failed`. The tenant sees the cluster with the successfully added workers; the failed slots are visible via ClusterOrder conditions and events.

#### Scale-Down

```mermaid
sequenceDiagram
    participant T as Tenant User
    participant BMW as BareMetalWorkerReconciler
    participant HCP as HyperShift / CAPI
    participant AS as assisted-service
    participant BMaaS as BMaaS (Private API)

    T->>BMW: Decrease node count
    BMW->>HCP: Decrease NodePool replicas

    HCP->>HCP: CAPI selects Machine, drains node
    HCP->>AS: AgentMachine unbinds Agent
    AS-->>BMW: Agent enters unbinding-pending-user-action

    BMW->>BMW: Resolve the worker from the unbound Agent
    BMW->>AS: Delete Agent CR
    BMW->>BMW: Confirm old Agent absent
    BMW->>BMW: Remove CaaS cleanup finalizer
    BMW->>BMaaS: Delete BareMetalInstance
    BMaaS->>BMaaS: Ordinary offboarding, network cleanup and host release
    BMW->>BMW: Retain identity; remove slot only after authoritative BMI Get NotFound
```

This diagram shows the scale-down flow. CAPI handles node drain and agent unbinding automatically. The controller reacts to the agent reaching an unbound state and then cleans up the BMI.

**Step-by-step:**

1. The controller reads the durable requested `numberOfNodes` for each node set and computes the NodePool replica target. On Cluster scale-down it updates the NodePool target before waiting for worker cleanup; CAPI owns Machine selection and node drain. The requested count in `ClusterOrder.spec.nodeRequests[]` is the durable intent across restarts.
2. CAPI's MachineDeployment controller selects and drains a Machine. CaaS does not preselect a different worker slot or mark an arbitrary slot for deletion. When the corresponding Agent enters `unbinding-pending-user-action` (or `known-unbound`), the controller uses the established worker association to persist that worker as `Unbinding`. CAPA has cleared `ClusterDeploymentName` and removed its pre-terminate hook/finalizer. With the assisted image service disabled (see Assisted Image Service), reclaim is not attempted. Restart recovery of the Agent association is an edge case below.
4. After CAPI has unbound the Agent, CaaS deletes the Agent CR and confirms its absence before clearing the worker cleanup finalizer. CAPA clears `ClusterDeploymentName` and removes its own hook/finalizer but does not delete the Agent.
5. The controller removes the CaaS worker-cleanup finalizer after confirming the old Agent is absent, then calls `BareMetalInstances.Delete`. A valid CaaS worker Delete is accepted with an empty response; that acknowledges the request, not physical cleanup. BMF owns NetworkAttachment offboarding, backend cleaning, and host release. A successful Delete, DELETING state, cache miss, List omission, or failed lookup is not absence: only an authoritative BMI `Get` returning `NotFound` releases the recorded BMI identity. Direct tenant Delete, which reaches BMaaS before CaaS can remove the finalizer, follows the separate edge-case cleanup handshake.
6. The controller retains the worker entry in `status.workers[]` in `Deleting` phase until BMI deletion is confirmed. A scale-down never creates a replacement for the removed slot; NodePool replicas already match the reduced request. Direct tenant Delete is a separate operation, not a scale-down; see [Edge cases](#edge-cases-that-need-handling).

#### Cluster Deletion

On ClusterOrder deletion, the BareMetalWorkerReconciler waits for `ClusterTeardownReady=True`, which the ClusterOrder controller writes only after automatic ExternalIPAttachments and ExternalIPs are gone and all cancelled AAP jobs are terminal (CaaS [Delete](/enhancements/OSAC-1436-caas-networking/design.md#delete)). A missing or False condition holds the worker finalizer and starts no Agent or BMI cleanup. After the gate, deleting the HostedCluster cascades through HyperShift (deletes all NodePools) → CAPI (drains nodes, deletes Machines) → CAPA (unbinds Agents). CaaS deletes the old Agent CRs; CAPA unbinding does not itself delete them. The cascade does **not** delete the BMIs — the fulfillment-service BareMetalInstances are unknown to HyperShift. The `BareMetalWorkerReconciler`'s finalizer (`osac.openshift.io/baremetalworker-finalizer`) cleans each Agent and worker BMI in its recorded slot. After an Agent is authoritatively absent, CaaS removes the worker cleanup finalizer before requesting BMaaS Delete; BMF follows its ordinary offboarding flow. Uncertain cleanup retains the slot, identity and finalizers; no replacement is created during Cluster teardown. The finalizer holds until all Agents and BMIs are authoritatively gone. The InfraEnv CR and pull-secret Secret are garbage collected via their ownerReferences to the ClusterOrder.

### API Extensions

**Modified CRDs:**

- `ClusterOrder` (osac-operator): new `workers` status field and aggregate counts (`desiredWorkers`, `currentWorkers`, `readyWorkers`) for tracking CaaS-managed worker resources; `ClusterTeardownReady` gates teardown on endpoint and AAP-job cleanup; each worker stores its registration deadline and Agent identity. The `nodeRequests` element type (`NodeRequest`) is redesigned to carry the `BareMetalInstanceType` reference (see ClusterNodeSet Redesign). The singular `networkAttachment` field (defined by OSAC-1436) carries the tenant subnet reference — the `BareMetalWorkerReconciler` reads it from the ClusterOrder spec and builds one-entry per-BMI `BareMetalNetworkAttachment` lists (see Network Attachment Enrichment below).

**New CRs created at runtime (not new CRD definitions):**

- `InfraEnv` (agent-install.openshift.io/v1beta1): one per cluster, created by the controller in the cluster's namespace. Owned by the ClusterOrder via an owner reference for garbage collection.

**Modified behavior of existing resources:**

- `BareMetalInstances` private API (fulfillment-service): `SetCaaSAgentCleanupReady` is used only by the direct-delete edge case. It accepts a BMI API ID plus expected Cluster API ID, validates CaaS ownership, the deletionTimestamp, and the cleanup finalizer, then sets the server-owned cleanup-ready annotation on the hub BMI CR. The registration deadline uses existing network/publication status; no run-strategy history API or table is added.
- `BareMetalInstance` (fulfillment-service / BMF): CaaS-created BMIs belong to the cluster's tenant (see Worker Tenancy and Ownership). Fulfillment installs the CaaS-owned `osac.openshift.io/caas-agent-cleanup` finalizer on private worker Create; BMF does not detach, deprovision, or return the host while it remains. Normal CaaS scale-down and Cluster deletion remove this finalizer after Agent absence and before BMaaS Delete. A direct public Delete arrives earlier; its cleanup-ready annotation and power-off handshake are described in the direct-delete edge case. No changes to the public Create request are required; the worker controller validates ownership on every read-back.

**Tenant-visible status:** The PRD requires tenant-visible failure conditions. ClusterOrder conditions (`WorkersFailed`, `InfraEnvReady`, `RHCOSImageNotFound`) live on the hub cluster, which tenants cannot access. The existing feedback controller syncs ClusterOrder status to the public Cluster API via the `Signal` RPC. This design extends the feedback controller to translate worker conditions into the tenant-visible Cluster status:

- `WorkersFailed=True` on ClusterOrder → `WORKER_PROVISIONING_FAILED` condition on the public Cluster, with a tenant-safe message (e.g., "2 of 5 worker nodes failed to provision") that omits infrastructure details (no BMI names, MACs, or backend errors)
- Networking failures (`NetworkAttachmentFailed`, `NetworkHandoffFailed`, `IPDiscoveryFailed`) → the worker failure condition uses the fixed tenant message `worker network attachment failed`; attempt counts, retry times, identities, and backend diagnostics remain on the hub for these failures
- Other workers in `Failed` with high attempt count → Cluster condition message includes the attempt count and next retry time, so tenants know retries are ongoing
- All other conditions (`InfraEnvReady=False`, `RHCOSImageNotFound`) → mapped to a generic `WORKER_PROVISIONING_BLOCKED` condition on the Cluster, indicating the cluster cannot provision workers due to an infrastructure issue requiring Cloud Infrastructure Admin intervention

This ensures tenants see provisioning progress and actionable failure messages without exposure to CaaS internals. The condition names and feedback controller extension must align with [OSAC-1604](https://redhat.atlassian.net/browse/OSAC-1604) (status reporting improvements) to avoid overlap — this design defines CaaS-specific worker conditions, while OSAC-1604 defines the general status reporting framework. Coordination tracked via Jira link.

**Operational impact:** If the osac-operator is down, no new bare-metal workers are provisioned and scale-up/scale-down operations stall. Existing workers continue running — HyperShift manages the cluster independently. On restart, the controller resumes pending work from the persisted worker identity and lifecycle state.

## UX Alignment

CaaS-managed workers require no tenant UI workflow changes. However, the BareMetalPool removal and assisted image service disablement affect the **Cloud Infrastructure Admin** installation and configuration flow, which surfaces through Enclave.

### Installer / Enclave Impact

The following `osac-installer`/AAP config-as-code values are affected:

| Value | Current purpose | Status |
|---|---|---|
| `aap.configAsCode.importAgentsEnabled` (`OSAC_IMPORT_AGENTS_ENABLED`) | Previously enabled the `osac-import-agents` scheduled AAP job for the pre-boot pool | **Inert** — the import-agents job template is no longer part of the AAP configuration; the variable remains defined in `config_as_code/playbooks/vars/config.yml` but is not consumed. Safe to remove from the chart. |
| `aap.configAsCode.importBcmAgentsEnabled` (`OSAC_IMPORT_BCM_AGENTS_ENABLED`) | Enabled the BCM inventory backend for agent import | Same as above — orphaned variable. |
| `aap.importAgents` | Server inventory list for BareMetalHost CR provisioning (BMC addresses, credentials) | **Retained for BMaaS** — bare-metal host inventory registration is still needed for standalone BareMetalInstance provisioning. |
| `aap.configAsCode.env.IMPORT_AGENTS_NAMESPACE` | Namespace for inventory CRs (default: `hardware-inventory`) | **Still needed** — the `hardware-inventory` namespace hosts inventory resources. CaaS creates per-cluster InfraEnvs in cluster namespaces, not here. |
| `aap.configAsCode.env.IMPORT_AGENTS_INFRAENV_NAME` | Shared InfraEnv CR name for agent discovery | **No longer consumed by CaaS** — CaaS creates per-cluster InfraEnvs. BMaaS standalone may still use a shared InfraEnv for its own inventory. |

**Enclave Wizard changes:**
- The Wizard's CaaS configuration panel (if it exposes `importAgentsEnabled` or pool-related settings) must drop pool configuration for CaaS deployments.
- New prerequisite: the assisted image service must be disabled. If Enclave controls this setting, it must default to disabled for CaaS deployments.
- New prerequisite: DiskImage registration and ClusterVersion linking. The Wizard should guide the Cloud Infrastructure Admin through registering RHCOS DiskImages and linking them to ClusterVersions (see Setup Flow, Cloud Infrastructure Admin steps 1-2).

**AAP template changes:**
- `playbook_osac_create_bare_metal_pool.yml` and `playbook_osac_delete_bare_metal_pool.yml` are no longer invoked by CaaS. They may be retained for BMaaS standalone use or removed if BareMetalPool is fully deprecated.
- The `cluster_infra` step collections (`agentless_net.steps`, `ci.steps`, `nico.steps`) no longer provision BareMetalPool CRs for CaaS — the BareMetalWorkerReconciler replaces that functionality.

### Implementation Details/Notes/Constraints

#### ClusterOrder CRD Status Extensions

The desired worker journal records the associated Agent name and UID as `agent`, scoped to the cluster namespace, and the persisted networking-aware `registrationDeadline`. Persist and confirm the Agent association before approval, binding, or NodePool-label side effects; retain it through cleanup. A pruned or conflicting status write authorizes no action.

```go
type ClusterOrderStatus struct {
    // ... existing fields ...

    // Aggregate worker counts (aligned with the CAPI MachineDeployment convention).
    // Populated by and owned by the BareMetalWorkerReconciler.
    // +kubebuilder:validation:Optional
    DesiredWorkers *int32 `json:"desiredWorkers,omitempty"`
    // +kubebuilder:validation:Optional
    CurrentWorkers *int32 `json:"currentWorkers,omitempty"`
    // +kubebuilder:validation:Optional
    ReadyWorkers *int32 `json:"readyWorkers,omitempty"`

    // Per-worker lifecycle state.
    // +kubebuilder:validation:Optional
    // +listType=map
    // +listMapKey=name
    Workers []WorkerStatus `json:"workers,omitempty"`
}

// BareMetalInstanceReference identifies the fulfillment resource backing a worker.
// Name is reserved before creation; ID is populated after creation succeeds.
type BareMetalInstanceReference struct {
    // +kubebuilder:validation:Optional
    // +kubebuilder:validation:MinLength=1
    Name string `json:"name,omitempty"`
    // +kubebuilder:validation:Optional
    ID string `json:"id,omitempty"`
}

type WorkerAgentReference struct {
    Name string `json:"name"`
    UID string `json:"uid"`
}

const (
    WorkerBMICreateStateReserved  = "Reserved"
    WorkerBMICreateStateAttempted = "Attempted"
)

type WorkerStatus struct {
    // NodeSet is the Fulfillment spec.node_sets map key identifying this worker's
    // logical group (e.g., "compute", "gpu"), not its hardware-profile name.
    // +kubebuilder:validation:Required
    NodeSet string `json:"nodeSet"`
    // InstanceType is the BareMetalInstanceType this worker was provisioned from.
    // Exposed as the instance_type metric label; sourced from
    // spec.nodeRequests[].bareMetal.instanceType.
    // +kubebuilder:validation:Optional
    InstanceType string `json:"instanceType,omitempty"`
    // Name is the stable worker slot identity, unique within the cluster.
    // New slots use opaque generated names, independent of the ClusterOrder name.
    // +kubebuilder:validation:Required
    Name string `json:"name"`
    // Kind of the backing resource (BareMetalInstance).
    // +kubebuilder:validation:Required
    Kind string `json:"kind"`
    // BareMetalInstance records the reserved name and fulfillment ID of the backing BMI.
    // +kubebuilder:validation:Optional
    BareMetalInstance BareMetalInstanceReference `json:"bareMetalInstance,omitempty"`
    Agent *WorkerAgentReference `json:"agent,omitempty"`
    // CleanupOnly records an unbound discovery Agent found before it passed
    // the binding gate; it authorizes cleanup but never binding side effects.
    // +kubebuilder:validation:Optional
    CleanupOnly bool `json:"cleanupOnly,omitempty"`
    // BMICreateState distinguishes a never-attempted reservation (Reserved) from a
    // BMI Create that may have reached fulfillment (Attempted, persisted with
    // optimistic locking before calling Create and retained on unknown outcomes).
    // +kubebuilder:validation:Optional
    // +kubebuilder:validation:Enum=Reserved;Attempted
    BMICreateState string `json:"bmiCreateState,omitempty"`
    // Phase of the worker lifecycle.
    // +kubebuilder:validation:Required
    // +kubebuilder:validation:Enum=Provisioning;WaitingForAgent;Binding;Ready;Failed;Unbinding;Deleting
    Phase string `json:"phase"`
    // CreationTimestamp is when this worker entry was first created.
    // +kubebuilder:validation:Required
    CreationTimestamp metav1.Time `json:"creationTimestamp"`
    // AttemptCount tracks how many times this worker slot has been provisioned.
    AttemptCount int32 `json:"attemptCount"`
    // AttemptStartedAt is the durable start of the current provisioning attempt
    // for accounting only; it never starts the registration timeout.
    // +kubebuilder:validation:Optional
    AttemptStartedAt *metav1.Time `json:"attemptStartedAt,omitempty"`
    // RegistrationDeadline is the persisted networking-aware deadline.
    // +kubebuilder:validation:Optional
    RegistrationDeadline *metav1.Time `json:"registrationDeadline,omitempty"`
    // LastFailureReason is a machine-readable reason for the last failure
    // (e.g., AgentRegistrationTimeout).
    // +kubebuilder:validation:Optional
    LastFailureReason string `json:"lastFailureReason,omitempty"`
    // LastFailureMessage is a human-readable description of the last failure.
    // +kubebuilder:validation:Optional
    LastFailureMessage string `json:"lastFailureMessage,omitempty"`
    // LastFailureTime is when the last failure occurred.
    // +kubebuilder:validation:Optional
    LastFailureTime *metav1.Time `json:"lastFailureTime,omitempty"`
    // NextRetryTime is when the controller will attempt the next retry.
    // +kubebuilder:validation:Optional
    NextRetryTime *metav1.Time `json:"nextRetryTime,omitempty"`
    // ReadySince is when the worker first transitioned to Ready after the most
    // recent retry; used to reset attemptCount after MinHealthyDuration.
    // +kubebuilder:validation:Optional
    ReadySince *metav1.Time `json:"readySince,omitempty"`
}
```

**Aggregate counts** align with the CAPI MachineDeployment convention: `desiredWorkers` (sum of positive bare-metal `nodeRequests` counts — visible before any reservation exists), `currentWorkers` (retained slots holding a verified BMI identity in an active phase: Provisioning + WaitingForAgent + Binding + Ready), `readyWorkers` (Ready subset, partitioned per node set). Identity-less reservations, `Failed`, retiring, surplus, and non-bare-metal entries never count. The three fields are written only by the `BareMetalWorkerReconciler`, together with the worker list and the `WorkersFailed` condition, so they never lag a reconcile behind the journal.

**Per-worker state** is persisted in `workers[]` (a map keyed by slot name), not tracked in-memory. Each `WorkerStatus` entry carries the lifecycle phase, retry state, and failure details. On restart, the controller rebuilds phases from live BMI and Agent state but preserves `attemptCount` and failure history from the persisted status — no dependency on Kubernetes events for retry tracking.

Example: a 5-worker cluster where 3 workers are ready and 2 are retrying:

```yaml
status:
  phase: Progressing
  desiredWorkers: 5
  currentWorkers: 3
  readyWorkers: 3
  conditions:
    - type: WorkersFailed
      status: "True"
      reason: WorkersRetrying
      message: "retry 1: attempt 2, next retry 2026-08-10T15:00:00Z; retry 2: attempt 3, next retry 2026-08-10T14:55:00Z"
    - type: InfraEnvReady
      status: "True"
  workers:
    - nodeSet: compute
      instanceType: bm-standard
      name: 4f9d2b1e-3c7a-4a55-9d0e-8b1f2a3c4d5e
      kind: BareMetalInstance
      bareMetalInstance:
        name: 4f9d2b1e-3c7a-4a55-9d0e-8b1f2a3c4d5e
        id: "uuid-0"
      agent:
        name: agent-0
        uid: "agent-uid-0"
      bmiCreateState: Attempted
      phase: Ready
      creationTimestamp: "2026-08-10T13:00:00Z"
      attemptCount: 1
      readySince: "2026-08-10T13:40:00Z"
    - nodeSet: compute
      instanceType: bm-standard
      name: 7c2e9f4a-1b3d-4e88-9a6f-0d5c7b8e2a1f
      kind: BareMetalInstance
      bareMetalInstance:
        name: 7c2e9f4a-1b3d-4e88-9a6f-0d5c7b8e2a1f
        id: "uuid-1"
      agent:
        name: agent-1
        uid: "agent-uid-1"
      bmiCreateState: Attempted
      phase: Ready
      creationTimestamp: "2026-08-10T13:00:00Z"
      attemptCount: 1
      readySince: "2026-08-10T13:42:00Z"
    - nodeSet: compute
      instanceType: bm-standard
      name: a1b2c3d4-e5f6-4789-9a0b-1c2d3e4f5a6b
      kind: BareMetalInstance
      bareMetalInstance:
        name: a1b2c3d4-e5f6-4789-9a0b-1c2d3e4f5a6b
      bmiCreateState: Reserved
      phase: Failed
      creationTimestamp: "2026-08-10T13:00:00Z"
      attemptCount: 2
      lastFailureReason: AgentRegistrationTimeout
      lastFailureMessage: "no Agent passed the binding gate by the reconstructed registration deadline"
      lastFailureTime: "2026-08-10T14:30:00Z"
      nextRetryTime: "2026-08-10T15:00:00Z"
    - nodeSet: gpu
      instanceType: bm-gpu
      name: d4e5f6a7-b8c9-4d0e-8f1a-2b3c4d5e6f7a
      kind: BareMetalInstance
      bareMetalInstance:
        name: d4e5f6a7-b8c9-4d0e-8f1a-2b3c4d5e6f7a
        id: "uuid-3"
      agent:
        name: agent-3
        uid: "agent-uid-3"
      bmiCreateState: Attempted
      phase: Ready
      creationTimestamp: "2026-08-10T13:05:00Z"
      attemptCount: 1
      readySince: "2026-08-10T13:50:00Z"
    - nodeSet: gpu
      instanceType: bm-gpu
      name: f7a8b9c0-1d2e-4f3a-9b4c-5d6e7f8a9b0c
      kind: BareMetalInstance
      bareMetalInstance:
        name: f7a8b9c0-1d2e-4f3a-9b4c-5d6e7f8a9b0c
      bmiCreateState: Reserved
      phase: Failed
      creationTimestamp: "2026-08-10T13:05:00Z"
      attemptCount: 3
      lastFailureReason: ResourceExhausted
      lastFailureMessage: "Host allocation failed: no available hosts"
      lastFailureTime: "2026-08-10T14:25:00Z"
      nextRetryTime: "2026-08-10T14:55:00Z"
```

The `workers[]` list always contains all worker references regardless of their individual state. The `WorkersFailed` condition provides the aggregate summary. The ClusterOrder remains in `Progressing` phase (not `Failed`) because 3 workers are operational. Per-worker detail (which slot failed, why, when the next retry is) is visible directly in the status.

The controller tracks worker lifecycle through phases: `Provisioning` → `WaitingForAgent` → `Binding` → `Ready` (and `Unbinding` → `Deleting` for teardown). `Provisioning` is the reservation period before the BMI exists; the phase moves to `WaitingForAgent` once the BMI identity is recorded. `Failed` is reachable only from provisioning phases (`Provisioning`, `WaitingForAgent`, `Binding`) and triggers automatic retry. Teardown issues (e.g., agent unbinding timeout, BMI deletion failure) keep the worker in `Unbinding` or `Deleting` with error details in `lastFailureReason`; they do not transition to `Failed` or authorize replacement before cleanup. After confirmed cleanup, scale-down or Cluster deletion removes the slot; a tenant-deleted Ready BMI instead follows the replacement rule below if Cluster capacity is still requested.

**Retry behavior:** The API is declarative — the controller retries indefinitely until the desired state is reached. There is no `PermanentlyFailed` state. When a worker enters `Failed`, the controller first cleans the failed incarnation (the old Agent must be gone and the BMI must be authoritatively absent — a successful `Delete` alone is pending, not completion), then initializes a single retry checkpoint (`nextRetryTime`, `bmiCreateState: Reserved`, cleared `attemptStartedAt`) and creates a replacement when the retry is due, with escalating backoff classified by `lastFailureReason`:

| Failure type | Examples (`lastFailureReason`) | Backoff | Rationale |
|---|---|---|---|
| Transient infrastructure | Definite backend provisioning error (default category); unknown Create outcomes use identity recovery, not failure classification | Short exponential: 30s, 60s, 120s, capped at 5m | Likely to resolve quickly; fresh host allocation may succeed after confirmed cleanup |
| Resource availability | `NoHostAvailable`, `ResourceExhausted` | Long exponential: 5m, 15m, 30m, capped at 30m | Inventory needs time to free up; aggressive retry wastes API calls |
| Agent registration timeout | `AgentRegistrationTimeout` | Long exponential: 5m, 15m, 30m, capped at 30m | Root cause (bad image URL, broken InfraEnv, network) is unlikely to self-resolve; gives operator time to investigate before next attempt burns another host |
| Worker networking | `NetworkAttachmentFailed`, `NetworkHandoffFailed`, `IPDiscoveryFailed` | Long exponential: 5m, 15m, 30m, capped at 30m | Preserve the BMI's stable reason; repair the network before consuming another host |

The `attemptCount` is persisted in `WorkerStatus` and survives controller restarts. After the initial escalation period (first 3 attempts), the backoff caps at the maximum for that failure type and the controller continues retrying at that interval. If a replacement succeeds and stays `Ready` for 1 hour (`MinHealthyDuration`), the `attemptCount` resets to 0 — distinguishing a resolved transient issue from a recurring problem.

The `WorkersFailed` condition reports which slots are retrying (with attempt number and next retry time), so operators are alerted and can investigate. For persistent misconfigurations (wrong DiskImage, broken network), the capped backoff ensures the controller does not burn hosts aggressively while still converging once the root cause is fixed.

The ClusterOrder controller separately derives `WorkerNetworkingReady` from the hub BMI CRs and Cluster SecurityGroups as [OSAC-1436 defines](/enhancements/OSAC-1436-caas-networking/design.md#worker-bmis). A networking-failed worker preserves its stable reason through cleanup/backoff until a replacement BMI is Ready; a failed automatic or selected SecurityGroup also yields `WorkerNetworkingFailed`. With provider networking enabled, failure takes precedence: only without either failure does pending BMI evidence yield `WorkersProgressing` or every requested worker BMI Ready yield `WorkersReady` (including zero workers). Provider-disabled networking yields True with `ProvisioningDisabled`. Tenant networking messages are fixed: `Worker networking is in progress.` or `Worker networking did not complete.`; the worker failure condition uses `worker network attachment failed`. BMI identities, backend diagnostics, and retry history remain on the hub, with Warning event `WorkerNetworkingFailed`.

**Scale-down selection:** When the tenant scales down, the worker reconciler updates the NodePool target first and lets CAPI select the Machine to drain. The Agent unbind event and established Agent name/UID journal identify the worker slot CAPI actually selected; the reconciler does not mark a different slot for cleanup. Which Ready Machine CAPI removes follows its MachineDeployment policy, not a CaaS age/health priority.

This satisfies the PRD requirement: "CaaS automatically handles provisioning retries and release of failed bare-metal resources, so that transient BMaaS failures do not leave orphaned infrastructure."

#### InfraEnv Creation

The controller creates one InfraEnv per ClusterOrder, named `<cluster-order-name>-infraenv` in the cluster's namespace and controller-owned by the ClusterOrder (garbage-collected with it). Before creating the InfraEnv the controller ensures a pull-secret Secret named `<cluster-order-name>-pull-secret`, taking the credential from `spec.pullSecret` or falling back to the `pull_secret` template parameter; the Secret is likewise controller-owned. The InfraEnv spec:

```yaml
apiVersion: agent-install.openshift.io/v1beta1
kind: InfraEnv
metadata:
  name: <cluster-order-name>-infraenv
  namespace: <cluster-namespace>
  ownerReferences:
    - apiVersion: osac.openshift.io/v1alpha1
      kind: ClusterOrder
      name: <cluster-order-name>
spec:
  pullSecretRef:
    name: <cluster-order-name>-pull-secret
  sshAuthorizedKey: <from spec.sshPublicKey, falling back to the ssh_public_key template parameter>
```

The InfraEnv uses **late binding** — no `clusterRef`. Agents register as unbound and the controller explicitly binds them by setting `clusterDeploymentName` only after unique correlation and the networking-aware gate. This gives the controller full control over the Agent binding lifecycle: on scale-down, CAPA clears `clusterDeploymentName`, the Agent enters `unbinding-pending-user-action`, and the controller reacts by deleting the Agent CR and then the BMI. CAPI handles node drain and Node object deletion independently — the pre-terminate hook clears as soon as the Agent reaches `unbinding-pending-user-action`, so node removal does not depend on the host rebooting into discovery.

One InfraEnv per cluster provides pull secret isolation (each cluster's InfraEnv carries the cluster-specific pull secret) and supports future static networking (per-host NMStateConfig is InfraEnv-scoped). Agent-to-cluster isolation is enforced by the MAC correlation algorithm (see MAC Address Correlation), which scopes matching to BMIs owned by the current ClusterOrder.

The discovery ignition is architecture-neutral (the `assisted-installer-agent` image is a multi-arch manifest) — the `cpuArchitecture` field on InfraEnv only affects ISO/kernel/rootfs URLs in `status.bootArtifacts`, not the ignition content, and this design uses the ignition-only flow. The controller uses unstructured objects with the agent-install GVKs rather than importing the `openshift/assisted-service` Go types, and registers Agent/NodePool watches only when their CRDs exist on the hub (see RBAC / Tenancy).

**Future optimization — shared InfraEnv for agent pooling:** A single platform-level InfraEnv could enable pre-booting hosts ahead of cluster requests, reducing provisioning latency. This design uses per-cluster InfraEnvs to keep the flow simple and maintain pull secret isolation. Agent pooling can be revisited as a future CaaS optimization.

#### RHCOS DiskImage Resolution

The controller resolves the RHCOS boot image via a `DiskImageReference` on the `ClusterVersion` resource. **This design owns the `disk_image` field on `ClusterVersionSpec`** — it is not covered by OSAC-2540 (which adds DiskImage to ComputeInstance only) or OSAC-1270 (which adds DiskImage to BareMetalInstance).

The private `ClusterVersionSpec` gains a new field:

```protobuf
message ClusterVersionSpec {
    // ... existing fields (image, version, enabled, is_default, state, deprecation) ...
    DiskImageReference disk_image = 7;
}
```

The controller reads the cluster's current ClusterVersion, follows the `disk_image` reference (preferring the id, falling back to the name), validates it with a `GetDiskImage`, and passes the resolved reference (id + name) as `spec.disk_image` on the BMI. No label-based lookup, no ambiguity — each ClusterVersion references exactly one DiskImage. The typed reference (per OSAC-1330) provides reference validation at ClusterVersion creation time and deletion protection (the DiskImage cannot be deleted while referenced by an active ClusterVersion).

**Cross-component changes introduced by this field:**
- `ClusterVersionSpec` proto: `DiskImageReference disk_image = 7` (private API only — tenants don't set this)
- `ClusterVersionsServer`: `Update` accepts `spec.disk_image` via the update mask
- CLI: `osac create clusterversion --disk-image <id>`; later changes go through `osac edit clusterversion` or the API
- DiskImage deletion protection: a DB trigger checks `cluster_versions` in addition to catalog references — a DiskImage referenced by an active ClusterVersion is not deletable (migration 120)

The controller re-resolves the disk image on every reconcile (not only at creation), so a ClusterVersion change takes effect without a controller restart. It reads the cluster's **current** ClusterVersion reference, not the creation-time version. Note: until cluster upgrades are implemented, this is always the creation-time version. Once upgrades land, the Cluster's ClusterVersion reference will be updated by the upgrade flow — this is the most reasonable assumption but should be treated as a dependency since cluster upgrades are still at the PRD stage.

The boot image is ephemeral — it exists only to run the discovery agent. The assisted-installer writes the correct RHCOS version (pinned to the release image) to disk during installation. Any Z stream within the same minor version is acceptable for the boot image.

If the `disk_image` reference is not set on the ClusterVersion, the controller sets the ClusterOrder condition `RHCOSImageNotFound` and does not proceed with BMI creation. If the underlying image is unreachable or the download fails during provisioning, the BMI enters `Failed` phase. The failure is reported via ClusterOrder conditions.

**Current limitation — manual DiskImage registration and linking:** In this version, the Cloud Infrastructure Admin must manually register RHCOS images and link them to ClusterVersions. For each supported OCP version:

1. Download the RHCOS qcow2 image for the target OCP version and architecture
2. Repackage the qcow2 as an OCI artifact
3. Push the OCI artifact to a container registry accessible to BMaaS
4. Register a DiskImage via the fulfillment-service API with `source_ref` pointing to the pushed OCI artifact
5. Set the ClusterVersion's `disk_image` reference to the registered DiskImage (e.g., `osac create clusterversion 4.22.0 --image <release-image> --disk-image <disk-image-id>`)

**Future automation path:** The OCP release image (`ClusterVersion.spec.image`) contains the RHCOS image reference as a component (`rhel-coreos`). A future utility could introspect registered ClusterVersions, extract the RHCOS image reference from each release payload, and automatically create the DiskImage and set the `disk_image` reference on the ClusterVersion. This removes the manual coupling — adding a new ClusterVersion would automatically produce and link the matching DiskImage. Note: directly using the RHCOS OCI image from the release payload as the DiskImage `source_ref` is not possible today because OCP BMO does not support this image format (planned for OCP 5.1). Until then, the qcow2 repackaging step remains necessary.

**Cluster upgrade path:** The `ClusterVersion → DiskImage` link is designed with upgrades in mind. When the cluster upgrade flow lands, the upgrade updates the Cluster's ClusterVersion reference (e.g., `4.18.0` → `4.19.0`). The controller detects the change, resolves the new ClusterVersion's `disk_image` reference (e.g., `rhcos-4.19`), and new workers provisioned during or after the upgrade boot with the updated image. Existing workers upgrade through the normal OCP upgrade path — they are not reprovisioned. This is why `disk_image` lives on `ClusterVersion` rather than on the Cluster or ClusterOrder: it naturally follows the version, so upgrading automatically selects the matching boot image.

#### BMI Creation via Private API

For each worker, the controller calls `BareMetalInstances.Create` on the private API. A BMI requires either `spec.catalog_item` or `spec.template`; CaaS uses the fixed **shared `BareMetalInstanceTemplate` `osac.templates.bm_host_provisioning`** (referenced with shared scope). It ships with the OSAC AAP template collection (`osac.templates.bm_host_provisioning`, the `bm_host_provisioning` role) and is not created or configured by any admin. The `BareMetalInstanceType` from the node request — not the template — determines which host hardware profile BMaaS allocates. The fields consumed by CaaS on `BareMetalInstanceSpec`:

```protobuf
// Fields in osac.private.v1.BareMetalInstanceSpec used by CaaS
// (see baremetal_instance_type.proto for canonical numbering):
message BareMetalInstanceSpec {
  BareMetalInstanceTemplateReference template = 10;   // shared osac.templates.bm_host_provisioning
  optional string user_data = 3;                      // inline discovery ignition content (max 64KB)
  repeated BareMetalNetworkAttachment network_attachments = 8; // max 1; plural for API compatibility
  BareMetalInstanceTypeReference instance_type = 11;  // from NodeRequest.bareMetal.instanceType (OSAC-1201)
  DiskImageReference disk_image = 12;                 // RHCOS DiskImage reference (see RHCOS DiskImage Resolution)
  optional string ssh_public_key = 2;                 // from ClusterOrder spec / template parameter
  // ... other existing fields (run_strategy, template_parameters, user_data_secret, ...) not set by CaaS
}
```

The fixed shared template satisfies the private API's catalog-or-template requirement without any deployment-time seeding: nothing to create or order at install time, and all CaaS-specific configuration (`instance_type`, `disk_image`, `user_data`, the network attachment) is carried by the BMI spec itself rather than by the template.

**gRPC call behavior:** This controller is the first in osac-operator to call `Create` and `Delete` on the fulfillment-service private API (existing controllers only call `Signal`). All gRPC calls use a context deadline of 30 seconds. Transport unavailability is classified per call (`codes.Unavailable`, and `codes.DeadlineExceeded` while the caller's context is still active, are transport outages; semantic codes keep their own meaning, and there is deliberately no shared failure counter — one order's or operation's outcome never changes another's). A transport outage is reported as an order-scoped `FulfillmentServiceUnavailable` condition on the ClusterOrder with a bounded 5-minute requeue, and the condition clears on the next successful reconcile. The controller-runtime requeue provides the retry loop; the deadline prevents a hung fulfillment-service from blocking the controller goroutine.

The controller sets the following metadata fields on the created BMI:

- `name`: the worker slot's opaque reserved name (see ClusterOrder CRD Status Extensions — names are generated UUIDs, independent of the ClusterOrder name)
- `tenant`: the cluster's tenant (see Worker Tenancy and Ownership)
- `labels["osac.openshift.io/cluster-order"]`: `"<cluster-order-name>"` — links BMI to parent ClusterOrder
- `annotations["osac.openshift.io/owner-reference"]`: new BMIs use the owning Cluster API ID, matching the shared owner-reference contract; the `osac.openshift.io/cluster-order` label separately identifies the ClusterOrder.
- `annotations["osac.openshift.io/cluster-api-id"]`: the authoritative Cluster API ID, a server-owned marker permitted only on the private worker Create path; public BMI Create requests supplying it are rejected with `INVALID_ARGUMENT`
- `finalizers[]`: fulfillment adds `osac.openshift.io/caas-agent-cleanup` for a marked CaaS worker before its BMI CR is created. In normal scale-down and Cluster deletion, CaaS removes this finalizer after Agent absence and before requesting BMaaS Delete. The direct-delete edge case, where the deletionTimestamp arrives first, uses the cleanup-ready handshake described below.

Before Create, fulfillment resolves the marked Cluster and verifies that the BMI tenant is exactly the Cluster tenant; the attachment uses the Cluster's stored Subnet API ID, exactly its stored SecurityGroup API IDs plus the automatic Cluster SecurityGroup, `primary: true`, and the stored `fabric_interface` of a matching instance-type node set. Caller overrides, missing or mismatched identity, tenant, networks, groups, or interface fail closed as defined by [CaaS worker authorization](/enhancements/OSAC-1436-caas-networking/design.md#caas-worker-network-authorization). The authoritative Cluster must not be deleting and the applicable network creation gates must pass. A transient dependency rejection (`FAILED_PRECONDITION`, for example the automatic SecurityGroup not READY) leaves the reserved slot without a BMI: retry with transient backoff, without entering `Failed`, consuming a failed attempt, or incrementing failure metrics. An uncertain Create outcome still follows identity recovery below, never this definite-rejection path. New creates also wait for the HostedCluster and `ManagementPublicationReady=True`; cleanup is never gated by creation prerequisites.

The attachment checks and networking-resource readiness gates above apply only with provider networking enabled. With networking disabled, worker Create sends no tenant attachment; fulfillment still verifies the private Cluster marker, authoritative Cluster tenant, live Cluster and matching instance-type node set. It does not require a Subnet lease, selected fabric interface or automatic SecurityGroup readiness for that attachment-free fallback.

**Idempotency on lost responses:** Persist a worker slot and reserved BMI name before calling Create. An uncertain response is not absence and never authorizes a second BMI; owned-name recovery and database uniqueness are covered under [Edge cases and recovery](#edge-cases-and-recovery).

#### ClusterNodeSet Redesign

The `ClusterNodeSet` proto currently references a `HostType`, which does not map directly to a provisioning resource for BMI creation. This design replaces `host_type` with a direct `BareMetalInstanceTypeReference` field (the old field 1 is reserved):

```protobuf
// Defines a set of cluster nodes sharing the same bare metal instance type.
message ClusterNodeSet {
  reserved 1;
  reserved "host_type";

  // Number of nodes of the set.
  optional int32 size = 2 [(buf.validate.field).int32.gt = 0];

  // Name of the network port on the BareMetalInstanceType used for tenant fabric traffic.
  // System-populated during cluster creation by selecting the first network port with
  // role "fabric" from the BareMetalInstanceType's network ports. Not user-settable.
  // Empty when the cluster has no network_attachment.
  string fabric_interface = 3 [(cleanapi.field).private = true];

  // BareMetalInstanceType (hardware profile) for the nodes in this set.
  // Immutable after creation.
  BareMetalInstanceTypeReference baremetal_instance_type = 4 [(google.api.field_behavior) = IMMUTABLE];
}
```

`node_sets` is a map on `ClusterSpec` keyed by node-set name (e.g., `compute`, `gpu`). The `BareMetalInstanceType` is an admin-managed resource defining hardware specifications (CPU architecture, cores, memory, network ports, host labels). The Cloud Infrastructure Admin creates `BareMetalInstanceType` entries for each available hardware profile. Hardware details (specific host, MAC address, network configuration) are not known until runtime — the `BareMetalInstanceType` defines *what kind* of host is needed, and BMaaS resolves *which specific host* at provisioning time via the host labels. The `ClusterCatalogItem` restricts or defaults the node-set map through its `fields.node_sets` policy (locked map or editable map with defaults; entries carry `size` + `baremetal_instance_type`). Cluster templates no longer carry node sets at all — the `ClusterTemplate.node_sets` field is reserved and templates only describe provisioning behavior and parameters.

This change:
- Eliminates the ambiguous HostType → Template → CatalogItem reverse lookup — the controller reads the instance type reference directly from the node request and passes it to the private API.
- The `BareMetalInstanceType` carries hardware metadata (CPU architecture, network ports) needed for DiskImage architecture resolution and fabric interface selection.
- The private `BareMetalInstances.Create` API is unchanged — CaaS references the shared `osac.templates.bm_host_provisioning` template, while `spec.instance_type` determines the hardware profile.
- VM worker node sets (OSAC-1589) use a separate provisioning path (AAP template hooks, not a controller) and are out of scope for this `ClusterNodeSet` redesign.

On the ClusterOrder CRD, the fulfillment-service writes each node set as a `NodeRequest` (`nodeSet` = the map key, `numberOfNodes`, `bareMetal.instanceType`, plus the stored `fabricInterface`). A node request without a `bareMetal` block is not bare-metal, which is how the reconciler filters node sets without a separate kind field.

This is a cross-component change affecting the fulfillment-service proto (ClusterNodeSet + BareMetalInstanceSpec), ClusterCatalogItem policies, and the osac-operator's `NodeRequest` type. It replaces the existing `host_type`-based model.

#### Worker Tenancy and Ownership

CaaS-managed BMIs are created under the **cluster's tenant**, resolved authoritatively by the controller. The controller never trusts the ClusterOrder's own annotations as an ownership source: it reads the fulfillment-service Cluster UUID from the `osac.openshift.io/clusterorder-uuid` label, fetches the authoritative Cluster via the private API, and requires that the Cluster's tenant matches the ClusterOrder's `osac.openshift.io/tenant` annotation. Any mismatch, missing label, or missing Cluster fails closed with a `WorkerOwnershipMismatch` event and no BMI mutation. The same checks are applied on every BMI read-back: tenant, reserved name, `osac.openshift.io/cluster-order` label, server-owned `osac.openshift.io/cluster-api-id` marker, and — where recorded — the BMI ID must all match. New BMIs use `osac.openshift.io/owner-reference: <Cluster API ID>`. For migration, an existing BMI may be read with the legacy value `ClusterOrder/<name>` only when every other authoritative ownership field matches; the controller does not rewrite that legacy annotation and deletes the BMI normally during cleanup. A legacy value alone never authorizes adoption.

This is semantically correct: the tenant ordered a cluster with N workers backed by bare metal, and the worker BMIs are the physical realization of that order in the tenant's scope. New BMIs use the owning Cluster API ID in `osac.openshift.io/owner-reference`; existing BMIs may retain the legacy `ClusterOrder/<name>` value until deleted after all other ownership checks pass. The `osac.openshift.io/cluster-order` label links either form to the ClusterOrder that manages the worker slot.

**Visibility (requirement, revised 2026-10-14):** worker BMIs live in the tenant's scope, so a tenant listing their bare-metal instances sees the CaaS worker BMIs alongside tenant-created ones. The `osac.openshift.io/owner-reference` annotation identifies the parent Cluster API ID, while the `osac.openshift.io/cluster-order` label identifies the managing ClusterOrder. This is intentional per the revised PRD: worker instances are visible for transparency and accounting, while Cluster lifecycle operations remain the management path. The controller itself never relies on visibility for safety — its ownership checks are authoritative, not cosmetic — and permitted mutable operations are not reverted. Ownership tampering is rejected; direct deletion triggers old-Agent cleanup and replacement only if Cluster capacity is still requested.

**Permitted operations:** tenants can Update fields that the public BMI API permits as mutable (for example `spec.run_strategy`); accepted updates are returned by that API and CaaS does not revert them. Immutable provisioning-field or status updates are rejected with `INVALID_ARGUMENT`. A permitted stop or restart is not a scale-down request. A valid CaaS worker Delete is accepted with an empty response; CaaS then drains the associated Machine and cleans up the old Agent before BMaaS releases the host, as described under Edge cases. ExternalIPAttachment cannot target a worker BMI. Generic BMaaS dependency guards remain in force for other BMIs. Tenant operations never change the Cluster's requested worker count.

**Metering:** the public [event-log-driven metering design](/enhancements/OSAC-5753-event-log-driven-metering/design.md#default-meters) supersedes Cluster worker-count billing. Fulfillment captures each worker BMI's own resource events and bills through `allocation` and `consumption`, with immutable owning Cluster and node-set attribution recorded at creation; worker heartbeats carry `cluster` and `node_set` dimensions. The Cluster bills only `control_plane`, not a second copy of worker usage. By default the Cluster's READY gate defers all owned worker billing during install; once it opens, eligible spans bill retroactively from each worker's own start. A Cluster that fails or is deleted before READY bills no workers, and a worker span closed before that gate opened remains unbilled. Later READY-to-PROGRESSING transitions do not close the gate. Allocation can include DELETING until physical deletion, as the successor's rules specify. These are CaaS attribution requirements, not changes to standalone BMaaS meters or metering rule policy.

**Cloud Provider Admin access:** Admins debug CaaS-managed workers via the private API. Per-cluster lookups use the `osac.openshift.io/cluster-order` label; per-worker lookups use the `status.workers[].bareMetalInstance.id` references recorded on the ClusterOrder.

#### MAC Address Correlation

Agent-to-BMI matching uses MAC addresses scoped to the cluster's namespace and ClusterOrder. When a BMI is allocated, its status reports the allocated host's NIC MAC addresses at `status.hardware.nics[].mac` (OSAC-4203; multiple NICs support the provider-disabled fallback, not arbitrary-NIC matching when networking is enabled). When an Agent registers, its inventory includes NIC MAC addresses at `status.inventory.interfaces[].macAddress`.

The correlation algorithm requires a unique match in **both directions** before binding:
1. **Namespace:** the Agent must be in the same namespace as the ClusterOrder's cluster
2. **Ownership:** the candidate worker must belong to the current ClusterOrder; an already-labelled or already-bound Agent is never a MAC fallback candidate
3. **Network proof:** with provider networking enabled, the inventory entry matching the selected NetworkAttachment `spec.interface.macAddress` (case-insensitive) must contain an `ipV4Addresses` CIDR whose parsed IPv4 address equals the accepted BMI attachment-status lease for the requested `subnetRef`. An address on a different NIC or the provisioning network is insufficient. With provider networking disabled, at least one inventory MAC must match a BMI host NIC MAC case-insensitively; no selected-port lease or OSAC DNS proof is required.
4. **Uniqueness:** exactly one unbound Agent may match a waiting worker, and that Agent may be the unique candidate for exactly one worker — one Agent matching several workers and several Agents matching one worker are both ambiguous and bind nothing

**Binding prerequisites:** approval, `clusterDeploymentName`, and NodePool-selection labels wait for BMI phase `Ready` and `ManagementPublicationReady=True`. With provider networking enabled, the `publish_public_dns_api` entry must also be `Succeeded` (both `api` and `api-int` published). A provisioning-network Agent waits, without approval or labels, while the gate is rechecked on Agent, BMI, NetworkAttachment, and ClusterOrder changes. The hub BMI CR is located by `osac.openshift.io/baremetalinstance-uuid: <status.workers[].bareMetalInstance.id>`.

**Registration clock:** `AgentRegistrationTimeout` defaults to 30 minutes after the latest of the BMI `NetworkHandoffComplete=True` transition, the latest `ManagementPublicationReady=True` transition, and, with provider networking enabled, `status.apiRecordsPublishedTime`. With provider networking disabled, use `ProvisionTemplateComplete=True` instead of handoff and omit the API-record timestamp. Once these prerequisites occur, a missing lease or an Agent that never passes the binding gate can time out.

If zero candidates match, the controller continues watching until the active deadline; multiple candidates remain unbound with an ambiguity diagnostic. At expiry the worker becomes `Failed`, reason `AgentRegistrationTimeout`. Incompatible candidates already claimed by another cluster or worker are observable errors, not silently adopted.

After a unique Agent match passes the binding gate, persist its name and UID before approval, binding, or NodePool-label side effects. Subsequent reconciles use that recorded association; restart and cleanup recovery are edge cases.



#### Network Attachment Enrichment

The BM controller reads the singular cluster-level network attachment from
`ClusterOrder.spec.networkAttachment` (a `ClusterNetworkAttachment` carrying
typed subnet and security-group references, defined by OSAC-1436). CaaS
fulfillment resolves omitted, empty, and partial attachment input before the
ClusterOrder is created; the worker controller does not apply a second set of
defaults. It enriches the resolved attachment into a one-entry per-BMI
`network_attachments` list for the private API call. The per-BMI list is an
internal compatibility shape; CaaS does not provide multi-NIC worker
networking:

| ClusterNetworkAttachment (input) | BareMetalNetworkAttachment (output) | Source |
|---|---|---|
| `subnetRef` | `subnet` | Pass-through |
| `securityGroupRefs[]` | `security_groups[]` | Pass-through |
| — | `interface` | The node set's stored `fabric_interface`, resolved from `BareMetalInstanceType.network_ports[]` during cluster creation (first port with role `fabric`) |
| — | `primary: true` | Always set — CaaS BM workers have a single network attachment |

This enrichment is a read-only consumer of the ClusterOrder's singular
`networkAttachment` field — the BM controller does not define or modify the
field shape. The field uses the cluster-specific `ClusterNetworkAttachment`
type, not ComputeInstance's `ComputeNetworkAttachment`. This design requires
the field to be present on the ClusterOrder CRD before the BM controller can
read it when provider networking is enabled. With networking disabled it sends
no tenant network attachment and uses the MAC-only fallback; private Cluster
identity and tenant checks still apply.

The `interface` field is resolved once during cluster fulfillment from `BareMetalInstanceType.network_ports[]`, stored as the node set's immutable `fabric_interface` — on the proto `ClusterNodeSet` and mirrored to the ClusterOrder's `nodeRequests[].fabricInterface` — and consumed by the worker controller when building the BMI request. Different node sets may carry different stored values; later profile changes do not alter an in-flight ClusterOrder. For Agent proof, use the selected NetworkAttachment port's MAC and accepted BMI IPv4 lease, not equality between an instance-type port name and a guest NIC name.

#### Minimum MCE Version

The MGMT-24903 fix (persistent-boot day-2 installs) is merged to assisted-service master ([PR #10717](https://github.com/openshift/assisted-service/pull/10717), 2026-07-29) and assisted-installer-agent master ([PR #1568](https://github.com/openshift/assisted-installer-agent/pull/1568), 2026-07-30). The fix ships in MCE 5.0. Without it, workers fail to install because `osImageURL` is stripped from the ignition config. The controller does not implement a workaround — MCE >= 5.0 is a deployment prerequisite.

#### Assisted Image Service

The assisted image service must be **disabled** for CaaS deployments. CaaS does not use ISO-based discovery — hosts boot from a RHCOS DiskImage with inline ignition, not from an assisted-service ISO. If the image service is deployed, assisted-service will attempt to reclaim Agents during scale-down (rebooting the host back into the discovery ISO), which conflicts with CaaS's flow where BMaaS owns host lifecycle and the controller deletes the BMI directly. Disabling the image service ensures Agents transition directly to `unbinding-pending-user-action` on unbind, allowing CaaS to clean up the Agent CR and the BMI without interference.

#### Controller Reconciliation Structure

The bare-metal worker management is implemented as a **separate controller** (`BareMetalWorkerReconciler`, the `baremetalworker` package in osac-operator), not folded into the ClusterOrder controller. Both controllers watch the same `ClusterOrder` CR (the worker reconciler additionally watches Agent CRs — mapped via the worker-name and InfraEnv labels — and NodePools, both watches gated on CRD presence so startup does not depend on the agent-install CRDs being installed):

- **ClusterOrder controller** — orchestrates the generic cluster lifecycle: AAP provisioning, NodePool creation (via AAP), and tenant-visible condition translation.
- **BareMetalWorkerReconciler** — handles all BM-specific phases, and **owns** the worker status: `status.workers[]`, the aggregate counts (`desiredWorkers`, `currentWorkers`, `readyWorkers`), and the `WorkersFailed` / `FulfillmentServiceUnavailable` worker conditions are all populated by and owned by the worker reconciler. A reconcile pass runs, in order:

1. **observe** — read scoped BMIs, Agents, and the ClusterOrder, then project worker identities and phases.
2. **creation prerequisites** — confirm the cluster InfraEnv is available before creating workers.
3. **existing-worker lifecycle** — retirement intent for scale-down and failed-incarnation cleanup; needs no creation inputs, so a missing pull secret, ignition or disk image cannot starve it.
4. **creation** — reservation of missing slots and creation/retry of BMIs for due slots, with image, ignition and instance type resolved only when a create is actually due (a stable order never fetches discovery ignition or resolves disk images on an unrelated event).
5. **convergence** — teardown, Agent binding, NodePool replica convergence and the worker summary; a prerequisite wait or error from the create stage is merged into the final scheduling decision instead of gating these.

NodePool replicas converge to the requested per-node-set capacity (preserving capacity while Agents are still provisioning), not to the number of correlated agents.

This separation keeps the ClusterOrder controller generic — it does not contain BM-specific logic (InfraEnv, ignition, MAC correlation, Agent handling). VM worker support (OSAC-1589) uses AAP template hooks rather than a controller, so no `VMWorkerReconciler` is planned.

**Status writes:** the worker reconciler owns its worker status writes (the `BareMetalWorkerReconciler` populates `status.workers[]`, the aggregate counts and the worker conditions; the ClusterOrder controller never writes them). Each status patch is built from an authoritative read, and a `resourceVersion` conflict aborts the reconcile so a fresh one re-observes, rather than merging stale evidence into newer worker state. If the worker and ClusterOrder controllers update status in the same cycle, one wins and the other retries on its next requeue — standard controller-runtime behavior, no data loss.

Each stage is idempotent. The controller re-enters from the top on each reconciliation cycle and progresses through completed stages without repeating side effects; durable status writes precede the external actions they authorize (see Idempotency on lost responses).

The reconciler adds its own finalizer (`osac.openshift.io/baremetalworker-finalizer`) and, on ClusterOrder deletion, actively deletes every recorded worker BMI via `BareMetalInstances.Delete` before releasing it (see Cluster Deletion).

**State rebuild on restart:** Worker lifecycle phase, retry state, failure details, BMI identity, and Agent identity persist in `ClusterOrder.status.workers[]`. The controller reconstructs routine progress from that persisted status and current BMI/Agent objects. Recovery after uncertain writes, a missed Agent association, or direct Delete is covered under [Edge cases and recovery](#edge-cases-and-recovery).

### Edge cases and recovery

These non-normative cases cover rare restarts, races, and partial failures. The main lifecycle above describes routine provisioning, CAPI scale-down, and Cluster deletion. Direct public BMI Delete remains accepted; its safety behavior is described here.

- **Uncertain BMI Create:** a lost response remains an unknown outcome. Recover by the reserved name and cluster-order label, validate tenant, name, owner reference, Cluster API marker, and recorded ID, and use the database uniqueness constraint as a backstop. List omission or transport failure is not proof of absence and must not authorize a second BMI.
- **Agent identity journal/label crash window:** if the controller restarts after recording the Agent name/UID but before binding labels, fetch the recorded name and verify the UID before repairing the label or resuming binding. Never adopt a same-name Agent with a different UID.
- **Cleanup-only discovery before Agent identity is recorded:** use an uncached list scoped to ClusterOrder namespace, InfraEnv UID, and BMI host NIC MAC. Only a single unbound, unlabelled Agent with no AgentMachine association can be recorded as cleanup-only and deleted with UID/resourceVersion preconditions. Ambiguous or bound candidates and lookup failures retain the finalizer and host.
- **Direct tenant Delete while the Agent remains bound:** the API accepts the Delete with an empty response. CaaS resolves the exact CAPI Machine from `agentMachineRef`, requests normal drain/unbind, deletes the old Agent, then calls `SetCaaSAgentCleanupReady`. BMF powers off while retaining attachment and host; CaaS confirms power-off and performs a fresh Agent absence check before removing the finalizer. If the Machine/Agent association is missing or ambiguous, keep the finalizer and host and do not replace the worker. Replace only after BMI NotFound and old-Agent absence if Cluster capacity remains requested.
- **A worker is Halted through the registration window:** the timeout is not paused; it may expire and the worker may be replaced.
- **The InfraEnv is deleted and recreated while workers wait for Agents:** the new ignition differs from what those hosts booted. Record the InfraEnv UID; mark affected `WaitingForAgent` workers failed and reprovision them with fresh ignition rather than waiting for Agents that cannot register.

### Security Considerations

CaaS-managed BMIs are created under the cluster's tenant via the private API, and the controller verifies ownership authoritatively on every reconciliation (see Worker Tenancy and Ownership): the fulfillment-service Cluster must exist, its tenant must match the ClusterOrder's tenant annotation, and every BMI read-back must match the recorded tenant, name, `osac.openshift.io/cluster-order` label and server-owned Cluster API ID marker. New BMIs use `osac.openshift.io/owner-reference: <Cluster API ID>`; an existing BMI may retain `ClusterOrder/<name>` during migration only when all other authoritative fields match. The private API bypasses tenant-scoped OPA policies because it operates with system-level credentials. The owner-reference annotation identifies the owning Cluster; the cluster-order label links the BMI to the managing ClusterOrder.

The discovery ignition contains the InfraEnv's pull secret and the assisted-service endpoint URL. It is passed inline as `user_data` on each BMI (max 64KB; PoC measured 15KB). The `user_data` field is immutable (enforced by the proto `IMMUTABLE` field behavior annotation). The InfraEnv uses late binding (no `clusterRef`) — agents register as unbound and bind only after unique correlation and the networking-aware gate. Agent-to-cluster isolation is enforced by the MAC correlation scoping, not by the ignition content.

Authentication credentials and the public OPA tenancy policy are unchanged; the private worker Create path adds the Cluster-specific authorization checks above and rejects the server-owned marker on public Create. The osac-operator authenticates to the private API using a token file mounted from a Kubernetes Secret (`OSAC_FULFILLMENT_TOKEN_FILE`), following the same pattern used by the existing feedback controllers for Signal RPCs.

Tenants interact only through the fulfillment-service API. They do not have K8s API access to the hub cluster — ClusterOrder, InfraEnv, and Agent CRs are not tenant-readable. The `Workers` references in ClusterOrder status are visible only to platform operators with hub cluster access.

The private API token (`OSAC_FULFILLMENT_TOKEN_FILE`) authenticates as `service-account-osac-controller`, an admin service account with unrestricted access to all API methods across all tenants. This is an existing platform-wide credential used by all osac-operator controllers (feedback, compute instance, networking). This design does not widen its scope — it adds BMI Create/Delete to a token that already has full admin access.

**Tenant visibility (requirement):** worker BMIs live in the tenant's scope and are deliberately visible to the tenant through the public BareMetalInstances API, per the revised PRD — see Worker Tenancy and Ownership for the provenance contract and the tamper-recovery guarantees.

### Failure Handling and Recovery

| Failure Mode | What Happens | Recovery | Tenant Observes |
|---|---|---|---|
| InfraEnv creation fails | Controller retries on next reconciliation cycle (controller-runtime requeue) | Automatic retry with exponential backoff | Cluster stuck in `PROGRESSING` with `WORKER_PROVISIONING_BLOCKED` condition |
| InfraEnv ignition not generated | Controller polls InfraEnv status with 30s requeue | Automatic; investigate assisted-service if persistent | Same as above |
| BMI creation fails definitively (excluding transient dependency rejection) | Worker phase set to `Failed`; account for the failed attempt once | Recover any recorded identity and clean it up before retrying with reason-classified backoff. An uncertain outcome uses identity recovery, not this failure path | Cluster shows `WORKER_PROVISIONING_FAILED` with tenant-safe feedback |
| BMI provisioning fails (host allocation or backend error) | BMI enters `Failed` phase, worker phase set to `Failed` | Controller deletes the failed BMI and retries with escalating backoff. Each attempt allocates a fresh host | Cluster shows degraded worker count during retries |
| No Agent passes the binding gate by the registration deadline | Worker phase set to `Failed`, reason `AgentRegistrationTimeout` | Controller deletes the timed-out BMI and retries with escalating backoff (capped at 30m) | Cluster shows `WORKER_PROVISIONING_FAILED` |
| BMI network attachment, handoff or IP discovery fails | Preserve `NetworkAttachmentFailed`, `NetworkHandoffFailed` or `IPDiscoveryFailed`; worker Failed | Clean the old Agent/BMI before replacement with long backoff | Fixed networking messages; administrator details stay on the hub |
| Worker Create dependency is not READY | Reserved slot has no BMI; no failed attempt | Retry transiently, retain unknown-outcome recovery for uncertain Create | Worker provisioning waits |
| MAC correlation finds no match | Agent remains uncorrelated | Controller logs a warning and continues watching. If all BMIs are correlated and extra agents exist, they are ignored | No direct tenant impact |
| Agent binding to NodePool fails | Agent not installed as worker | assisted-service reports failure in Agent conditions; controller reflects in worker phase | Cluster shows degraded worker count |
| Scale-down: Agent unbinding times out | Agent stuck in unbound state longer than 30 minutes | Worker remains in `Unbinding` phase with `lastFailureReason: AgentUnbindingTimeout`. Controller retries periodically. Manual intervention required. No replacement is triggered | Node count mismatch visible in Cluster status |
| BMI deletion fails | BMI stuck in `Deleting` (e.g., AAP deprovision job fails with `blockDeletionOnFailure: true`) | Controller retries delete periodically. Alerting notifies operators | Scale-down appears incomplete in Cluster status |
| Controller restart mid-reconciliation | Controller resumes from current state on restart | Idempotent reconciliation logic rebuilds in-memory state from CRD status and re-queries BMI/Agent state | Temporary stall, no data loss |

### RBAC / Tenancy

The controller intentionally does **not** depend on the `openshift/assisted-service` Go module: InfraEnv, Agent, and NodePool objects are handled as unstructured types with their GVKs, and the Agent and NodePool watches are registered only when their CRDs exist on the hub (checked via the REST mapper at startup). This avoids a hard module/startup dependency on the agent-install CRDs.

The osac-operator's ClusterRole is extended with:
- `get`, `list`, `watch`, `create`, `update`, `patch`, `delete` on `infraenvs` in the `agent-install.openshift.io` API group (InfraEnv creation, UID tracking, ignition readiness polling, and deletion)
- `get`, `list`, `watch`, `patch`, `delete` on `agents` in the `agent-install.openshift.io` API group (MAC correlation, cluster binding via `clusterDeploymentName` patch, NodePool label application, Agent CR cleanup on scale-down)
- `get`, `list`, `watch`, `delete` on `machines` in the `cluster.x-k8s.io` API group, to request the normal CAPI drain/unbind path for the exact Machine referenced by a CaaS worker Agent's `agentMachineRef` during direct BMI Delete
- `patch` on `baremetalinstances/finalizers` in the `osac.openshift.io` API group, restricted by controller logic to remove `osac.openshift.io/caas-agent-cleanup` after the recorded Agent is unbound and authoritatively absent
- `get`, `list`, `watch`, `patch`, `update` on `nodepools` in the `hypershift.openshift.io` API group (replica convergence)
- `get`, `create` on `secrets` (the per-cluster pull-secret Secret)
- `get`, `list`, `watch` on `clusterorders` and `get`, `update`, `patch` on `clusterorders/status`

The existing service account permissions for creating CRs in cluster namespaces and calling the private API are unchanged.

CaaS-managed BMIs carry the cluster's tenant and the `osac.openshift.io/cluster-order` label linking them to their parent ClusterOrder, enabling Cloud Provider Admin queries via the private API (see Worker Tenancy and Ownership for the tenant-visibility consequence).

Tenant-owned BMaaS workflows are unaffected. A tenant creating their own BareMetalInstance through the public API sees only their own instances, as before.

### Observability and Monitoring

| Metric | Type | Labels | Description |
|---|---|---|---|
| `osac_caas_worker_desired` | Gauge | `tenant`, `worker_type`, `instance_type` | Desired workers, derived from the requested bare-metal NodeSets (visible before any reservation exists) |
| `osac_caas_worker_ready` | Gauge | `tenant`, `worker_type`, `instance_type` | Ready workers, from the same retained identity-backed eligibility the status summary uses |
| `osac_caas_worker_provisioning_failures_total` | Counter | `tenant`, `worker_type`, `instance_type` | Worker provisioning failures (each transition into `Failed` counts once; retries that fail again count again) — the rate-alertable failure signal |
| `osac_caas_worker_provisioning_duration_seconds` | Histogram | `tenant`, `worker_type`, `instance_type` | Time from worker creation to Ready, including retries (anchored on `creationTimestamp`, which survives retries) |
| `osac_caas_worker_correlation_duration_seconds` | Histogram | `tenant`, `worker_type`, `instance_type` | Time from worker creation to Agent correlation (Binding) |

`worker_type` label values: `bare_metal` (BareMetalInstance workers). The metric names are shared with future compute (VM) worker flows; `worker_type` disambiguates them. Per-ClusterOrder metrics would create unbounded label cardinality at scale. Metrics are aggregated by `tenant` and `instance_type` (bounded), recomputed from the full ClusterOrder set on each reconcile (gauge Reset + Set, so series for deleted clusters drop). Per-ClusterOrder detail is available via the ClusterOrder status fields and Kubernetes events, which are the appropriate layer for per-instance diagnostics.

**Kubernetes Events:**

| Event | Type | Reason | When |
|---|---|---|---|
| Worker created | Normal | `WorkerCreated` | Controller creates a worker resource via private API |
| Agent correlated | Normal | `AgentCorrelated` | MAC match found between Agent and worker resource |
| Worker joined | Normal | `WorkerReady` | Worker installed as cluster node |
| Agent registration timeout | Warning | `AgentRegistrationTimeout` | No Agent passed the networking-aware binding gate before its reconstructed deadline |
| Worker provisioning failed | Warning | `WorkerFailed` | Worker resource entered `Failed` phase (with attempt number and retry interval) |
| Worker retry | Normal | `WorkerRetry` | Replacement BMI created for a failed worker |
| Worker deleted / scale-down | Normal | `WorkerDeleted` | Worker slot marked for unbinding during scale-down |
| Stale ignition | Warning | `StaleIgnition` | InfraEnv was recreated; waiting workers marked failed |
| Ignition size warning | Warning | `DiscoveryIgnitionSizeWarning` | Fetched ignition exceeds 48KB (75% of 64KB limit) |
| Ownership mismatch | Warning | `WorkerOwnershipMismatch` | Authoritative tenant/ownership check failed |
| Cleanup blocked | Normal | `WorkerCleanupBlocked` | Worker teardown waits for owner-driven Agent detach |

### Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| RHCOS DiskImage not linked to ClusterVersion | Controller cannot resolve boot image; BMI creation blocked with `RHCOSImageNotFound` condition | Cloud Infrastructure Admin must register DiskImages and link them to ClusterVersions via `--disk-image` before enabling CaaS provisioning. Reference validation catches this at ClusterVersion creation time. |
| Tenant mutation/deletion of cluster-managed worker BMIs (visible in the tenant's scope per the revised PRD) | Tenants can see and modify worker BMIs in `osac get/list baremetalinstances` | Accepted mutable updates are not reverted or inferred as scale-down. Ownership tampering fails closed; direct deletion requires authoritative BMI absence and old-Agent cleanup before replacement. Cluster capacity changes remain the supported scale-down path. |
| BMaaS deprovision failure leaves hosts in limbo during scale-down | Hosts are not cleaned up; potential data leakage if reassigned | Worker remains in `Unbinding`/`Deleting` phase with error details in `lastFailureReason`. Operators alerted via the `osac_caas_worker_provisioning_failures_total` rate and desired-ready gap. Manual intervention documented in support procedures. |
| Discovery ignition exceeds `user_data` limit (64KB) | BMI creation rejected | PoC measured 15KB. The controller emits a `DiscoveryIgnitionSizeWarning` event when the fetched ignition exceeds 48KB (75% of the 64KB limit), giving operators advance notice before BMI creation starts failing. |
| Concurrent scale operations on multiple clusters exhaust host inventory | Multiple ClusterOrders compete for limited hosts; some fail | BMI creation fails, worker enters `Failed` phase with `ResourceExhausted`-class backoff. ClusterOrder status reflects partial provisioning. Inventory sizing is the admin's responsibility. |

### Drawbacks

This design tightly couples the osac-operator to the fulfillment-service private API for BMI lifecycle management. The controller becomes a gRPC client of the fulfillment-service, adding a synchronous dependency in the reconciliation path. If the fulfillment-service is unavailable, worker provisioning and deprovisioning stall. The alternative — creating BMI CRs directly on the hub cluster — would avoid this dependency but lose the audit trail and tenant-scoped ownership records that the fulfillment-service provides. The coupling is justified because the private API is the canonical path for all BMI operations, and the fulfillment-service is a core dependency that the osac-operator already communicates with for Signal RPCs and other operations.

The per-cluster InfraEnv provides pull secret isolation. Late binding (no `clusterRef`) means agents register as unbound and the controller binds them only after unique correlation and the networking-aware gate. Established worker-name/UID associations drive subsequent cleanup; MAC fallback does not replace the selected-port lease proof for initial binding.

## Alternatives (Not Implemented)

### BareMetalPool-Based Provisioning (Current Approach)

Create a BareMetalPool per ClusterOrder and let the bare-metal-fulfillment-operator manage BMI creation. **Rejected** because BareMetalPool groups BMIs with a shared profile — CaaS needs per-instance configuration (different DiskImage, network attachments, user_data per cluster). The Pool abstraction does not support per-BMI `image` and `user_data` configuration. The PoC validated direct BMI creation; adding a pooling abstraction that does not fit the use case adds complexity without benefit.

### Direct CR Creation on Hub Cluster

Have the controller (or AAP role) create BareMetalInstance CRs directly on the hub cluster, bypassing the fulfillment-service. This is what the current `cluster_infra` AAP step does with BareMetalPool CRs. **Rejected** because: (a) BMIs would not appear in the fulfillment-service database, breaking audit and observability; (b) tenant-scoped ownership requires BMIs to be fulfillment-service records; (c) the private API is the canonical path for BMI lifecycle, and the PRD explicitly requires it.

### AAP-Orchestrated BMI Creation

Replace the controller-based flow with a new AAP role that calls the private API and manages the agent correlation loop. **Rejected** because AAP jobs are one-shot — they do not naturally handle the asynchronous agent registration and correlation flow. The controller's watch-based reconciliation model is the correct abstraction for reacting to Agent CR state changes over time. Scale-up and scale-down events also need reactive handling that controllers provide.


## Test Plan

> Coverage note: unit and envtest coverage lives in `osac-operator/internal/controller/baremetalworker/` (unit suites per behavior area, plus real-API-server acceptance suites: `baremetalworker_convergence_test.go`, `baremetalworker_lifecycle_test.go`, `baremetalworker_tenant_safety_test.go`, etc.). Deployed cross-component journeys are owned by the [QE] follow-up (OSAC-4843) and the `tests/e2e/caas/` suites.

### Unit Tests

- BareMetalWorkerReconciler: worker capacity planning reserves the correct number of slots when desired count exceeds current count, and re-reconciles after a lost Create acknowledgement without creating duplicates (recovery by owned name / `AlreadyExists`). Identity-less, failed/retrying and teardown slots retain their obligations even when excluded from `currentWorkers`; no fresh slot bypasses pending cleanup.
- BareMetalWorkerReconciler: scale-down updates the NodePool target before cleanup and resolves the actual CAPI-selected Machine back to its worker from the Agent journal; the Agent is deleted before the CaaS BMI finalizer is removed and BMaaS Delete begins.
- BareMetalWorkerReconciler: initial correlation requires a unique bidirectional match and BMI Ready/management gates. Test selected-port MAC plus parsed accepted IPv4 lease with networking enabled, reject another NIC/provisioning address, wait for both API records, and use scoped host-MAC fallback without networking. Wrong namespaces, already-claimed Agents and ambiguous matches never bind.
- BareMetalWorkerReconciler: InfraEnv creation uses late binding (no `clusterRef`), correct owner reference, and a controller-owned pull-secret Secret.
- BareMetalWorkerReconciler: worker phase transitions correctly through `Provisioning` → `WaitingForAgent` → `Binding` → `Ready`.
- BareMetalWorkerReconciler: reconciliation is idempotent — re-running with the same state produces no new API calls; a lost Create acknowledgement keeps the reservation and recovers by owned name / `AlreadyExists`.
- Tenant safety: the controller fails closed when the authoritative Cluster tenant does not match the ClusterOrder tenant annotation, and when a BMI read-back violates the ownership contract (tenant, name, owner-reference, cluster-order label, server-owned Cluster API ID marker, recorded ID); accept the legacy `ClusterOrder/<name>` owner-reference only for an existing BMI whose other fields match, and verify new creates use the Cluster API ID.
- Private authorization: reject a public Create carrying `cluster-api-id`; verify authoritative Cluster tenant, Subnet, exact tenant plus automatic SecurityGroups, stored node-set interface and instance type. Dependency `FAILED_PRECONDITION` creates no Failed phase, failed attempt or failure metric; unknown outcomes recover the original identity.
- Networking failures: each stable reason selects long backoff and the fixed tenant feedback; verify `WorkerNetworkingReady` for missing/Ready/failed BMIs, failed SecurityGroups, zero workers and provider-disabled mode.
- RBAC: osac-operator's ClusterRole includes Agent get/list/watch/patch/delete; exact CAPI Machine get/list/watch/delete for direct worker Delete; `baremetalinstances/finalizers` patch limited to removing the CaaS Agent-cleanup finalizer after Agent absence; and the existing NodePool replica permissions (kubebuilder markers).

### Integration Tests (envtest)

- Create a ClusterOrder with bare-metal node requests against a real API server. Verify InfraEnv CR is created with correct spec. Verify BMI creation calls reach the (faked) private API. Verify ClusterOrder status reflects `workers` entries, aggregates and conditions.
- Simulate provisioning-network Agent arrival, BMI handoff/Ready, selected-MAC lease and API publication independently. Verify no approval, binding or NodePool labels before all gates pass, then verify correlation and selection; repeat with provider networking disabled and management publication still required.
- Simulate scale-down by decreasing `nodeRequests`. Verify the NodePool replica target changes before cleanup, CAPI drains and unbinds the Machine it selects, the matching worker is resolved from its journal, the Agent is deleted with UID preconditions, and BMI Delete follows.
- Verify ClusterOrder deletion waits for `ClusterTeardownReady=True` before Agent/BMI cleanup; it stays pending while automatic endpoints or cancelled jobs remain. After the gate, verify Agents and BMIs are cleaned before removing the `baremetalworker` finalizer, including recovery of ID-less reservations.
- Verify worker event attribution is immutable and tenant-scoped. Under the public metering successor, the Cluster gate defers worker allocation/consumption until READY; pre-READY Cluster failure/deletion and closed worker spans bill nothing, while eligible active spans bill retroactively without duplicate Cluster worker-count charges.

### E2E Tests

- Full provisioning flow: create a Cluster with a bare-metal node set via the fulfillment-service public API. Verify workers join and ClusterOrder reaches `Ready`. (Requires a test environment with BMaaS hosts and assisted-service.)
- Scale-up: increase node count on an existing cluster. Verify new workers are provisioned and join.
- Scale-down: decrease node count. Verify the NodePool target changes first, CAPI drains/unbinds the selected worker, the Agent CR is deleted, and BMaaS cleans the BMI without replacement.
- Cluster deletion: delete a cluster with bare-metal workers while endpoint cleanup is pending. Verify worker cleanup waits for `ClusterTeardownReady`, then Agents are removed before BMaaS releases hosts.
- Tenancy: verify worker BMIs are created in the cluster's tenant and remain correlated to the ClusterOrder; verify tenants can list their cluster's worker BMIs with the cluster-order provenance labels, that permitted mutable updates remain accepted without reverting or replacing the BMI, and that Cluster API scale-down is the supported capacity-change path; direct Delete follows the documented edge case.
- Pool removal: verify no BareMetalPool CRs are created during CaaS cluster provisioning. Verify the `cluster_infra` AAP step no longer references BareMetalPool.

Note: full E2E tests require a BMaaS-capable test environment with physical or simulated bare-metal hosts. Initial E2E coverage may be limited to API-level verification with mocked BMaaS responses.

### Edge-case tests (later)

- Lose the BMI Create response after fulfillment commits; restart and verify the reserved worker name recovers the original BMI without a duplicate.
- Crash after Agent name/UID persistence but before binding labels; verify UID-checked label repair and reject a same-name/different-UID Agent.
- Exercise cleanup-only discovery for one valid unbound Agent, zero candidates, ambiguous candidates, a bound candidate, and an uncached list failure. Only the valid unique candidate is deleted; every ambiguous case retains the host and finalizer.
- Direct Delete of a Ready worker with a bound Agent: drain/unbind its exact CAPI Machine, delete the Agent, run the cleanup-ready/power-off handshake, and replace only after BMI NotFound if capacity remains. Also test missing or ambiguous Machine association.
- Keep a worker Halted through the registration window and verify AgentRegistrationTimeout and the documented replacement behavior.
- Delete and recreate the InfraEnv while workers wait for Agents; verify stale ignition classification and reprovisioning with the new discovery ignition.
- Delete and recreate the InfraEnv while workers wait for Agents; verify the stale ignition is detected and those workers are reprovisioned with the new discovery ignition.

## Graduation Criteria

N/A. OSAC is in active development and has not been released to customers.

## Upgrade / Downgrade Strategy

The BareMetalPool-based pre-boot pool is removed immediately — there is no coexistence period. On upgrade:

1. The `cluster_infra` AAP step that creates BareMetalPool CRs is removed from the CaaS provisioning workflow.
2. The scheduled `osac-import-agents` AAP job is no longer needed for CaaS (it may be retained for standalone BMaaS use cases).
3. Existing BareMetalPool resources created by CaaS are drained: idle hosts are released back to inventory, and the BareMetalPool CRs are deleted.
4. Existing clusters with workers provisioned via the old pool flow continue running — their workers are already installed and do not depend on the pool. However, scale-up on these clusters uses the new on-demand BMI flow going forward.
5. Clusters mid-provisioning during the upgrade (AAP job in progress using the old `cluster_infra` step) must complete or fail before the upgrade. The upgrade procedure must drain the AAP job queue — no new CaaS provisioning jobs are accepted while the old step is being removed. Any in-flight job that references the deleted `cluster_infra` step will fail; the operator must re-trigger provisioning using the new flow after the upgrade completes.

Downgrade requires:
1. Scale down all bare-metal workers on affected clusters (the controller manages cleanup).
2. Delete any InfraEnv CRs created by the controller.
3. Re-deploy the `cluster_infra` AAP step and scheduled `osac-import-agents` job for BareMetalPool management.
4. Revert the osac-operator to the previous version.

The ClusterOrder CRD gains a durable status journal (`workers`). Preserve its recorded BMI and Agent identities and cleanup intent until teardown is confirmed; live-state reconstruction is not a substitute for a lost journal. Downgrade only after worker cleanup completes, and do not install a CRD that prunes the journal while it still authorizes pending actions.

## Version Skew Strategy

The osac-operator (controller) and fulfillment-service (private API) must be upgraded together or the operator first. The controller calls `BareMetalInstances.Create` with fields introduced by the DiskImage integration (OSAC-1270 — `spec.disk_image`) and the instance type reference (OSAC-1201 — `spec.instance_type`), both listed dependencies — the fulfillment-service must have them implemented before CaaS bare-metal provisioning is enabled, so there is no version skew scenario for these fields. The optional `WorkerStatus` fields (`attemptStartedAt`, `bmiCreateState`, `readySince`, `agent`) are unknown to older CRDs; the controller verifies that required journal writes survived (an older CRD may prune fields) before treating them as authorization for external Create or Agent binding/cleanup.

CaaS-managed BMIs belong to the cluster's tenant, so no fulfillment-service tenancy change is involved. Worker CRs use the configured Hub namespace, not a per-tenant namespace; enforcing same-Hub placement across multiple Hubs remains a separate rollout gate.

## Support Procedures

**Detecting failures:**
- ClusterOrder stuck in `Progressing` with condition `WorkersFailed`: check `status.workers[]` for the referenced BMI IDs, then inspect each via the private API (`osac get baremetalinstances <id> --private`) for provisioning job errors and state.
- Alert: `rate(osac_caas_worker_provisioning_failures_total[15m]) > 0`, or `osac_caas_worker_desired - osac_caas_worker_ready > 0` sustained for 15 minutes.
- Agent registration timeout: check InfraEnv status for ignition generation errors. Verify DiskImage is reachable. Check BMI status for host allocation failures.
- Scale-down stall: Agent stuck in `unbinding-pending-user-action` — verify osac-operator has `delete` permission on `agents` in `agent-install.openshift.io`. Check BMI status via the private API for deprovision errors. Investigate the BMaaS backend if the BMI remains in `Deleting`.

**Disabling the feature:**
- Remove bare-metal node sets from the cluster catalog items. Existing clusters with bare-metal workers continue running — the controller does not deprovision workers unless instructed (scale-down or delete).
- To remove CaaS BMIs through normal scale-down or Cluster deletion, CaaS confirms Agent absence, removes the worker cleanup finalizer, and then requests BMaaS Delete. Direct public Delete is accepted but uses the separate [edge-case cleanup sequence](#edge-cases-and-recovery); do not remove its finalizer manually. Generic BMaaS dependency guards remain in force for non-CaaS BMIs.

**Recovery:**
- The controller is designed for idempotent reconciliation. Restarting the osac-operator pod causes the controller to rebuild state from the ClusterOrder status, re-query BMI and Agent CRs, and resume any pending operations. No manual consistency repair is needed.

## Infrastructure Needed

No new infrastructure. The feature uses existing components: osac-operator deployment, fulfillment-service private API, assisted-service, HyperShift, and BMaaS hosts.

Documentation updates required:
- Cloud Infrastructure Admin guide: DiskImage registration procedure and ClusterVersion linking.
- Installation prerequisites: minimum MCE version requirement (assisted-service 5.0.0+ for MGMT-24903 fix), assisted image service must be disabled.
- Migration guide: BareMetalPool removal procedure, AAP job queue drain during upgrade, post-upgrade re-trigger of mid-provisioning clusters.

---

## Provenance

Authored: respond @ design 0.15.0 - 87d14ea, workspace main @ 74c7c4fb3
Phases: revise, revise, revise, revise, revise, revise, revise, respond, respond, respond, respond, respond, respond

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.15.0","ai_workflows":"87d14ea","source_repo":"74c7c4fb3","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["revise","revise","revise","revise","revise","revise","revise","respond","respond","respond","respond","respond","respond"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":true} -->
