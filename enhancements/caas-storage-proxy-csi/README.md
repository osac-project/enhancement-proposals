---
title: caas-storage-proxy-csi
authors:
  - avishayt
creation-date: 2026-05-17
last-updated: 2026-05-17
tracking-link:
  - TBD
see-also:
replaces:
superseded-by:
---

# CaaS Storage Integration via Proxy CSI Driver

## Summary

This enhancement establishes a centralized storage control plane for Cluster-as-a-Service (CaaS) by introducing an OSAC CSI driver that proxies storage requests from tenant Kubernetes clusters through the OSAC Volume API. Instead of allowing tenant clusters to communicate directly with storage backends, the OSAC CSI driver intercepts CSI operations (CreateVolume, DeleteVolume, ControllerPublishVolume) and forwards them via gRPC to the OSAC control plane, which enforces policy, quotas, and auditing before delegating to vendor-specific CSI drivers running in the management cluster. This architecture preserves strict data sovereignty claims and centralized governance while providing tenant workloads with transparent access to block storage.

## Motivation

OSAC's product positioning requires demonstrable data sovereignty and centralized governance over all infrastructure resources. For CaaS tenant clusters running on bare-metal worker nodes, storage access presents a critical architectural decision: should tenant clusters communicate directly with storage backends, or should all storage requests flow through the OSAC control plane?

### The Problem

If tenant clusters deploy vendor CSI drivers (e.g., VAST, Ceph) directly and communicate with storage arrays over an out-of-band network for control plane operations (CreateVolume, DeleteVolume, ControllerPublishVolume), OSAC faces several showstopping issues:

1. **Evidence Locker Compliance Violation**: OSAC's sovereign cloud architecture requires an evidence locker—a cryptographically signed, immutable audit repository proving compliance with data residency laws and operational boundaries. Storage backends can isolate tenants via dedicated pools (separate namespaces with QoS, quotas, redundancy controls), but the core question is: Does OSAC need control-plane visibility into what happens in those pools? For evidence locker compliance, the answer is yes:

   - **Tenant clusters are untrusted**: A compromised cluster could suppress audit logs, forge timestamps, or modify webhook configurations. The evidence locker cannot accept events from sources outside the trust boundary.
   
   - **Backend logs lack identity context**: Storage arrays log pool-level operations (e.g., "Namespace pool-12345 created volume vol-abc-123") but are missing who (user identity), why (organization/project context), and policy approval (was this authorized?).
   
   - **Multi-source correlation is unverifiable**: Reconstructing compliance events from tenant K8s audit logs + backend storage logs + OSAC tenant mappings produces a composite event that cannot be cryptographically signed by a single authority.

   Without OSAC in the control path, storage lifecycle events cannot be attested by the OSAC control plane, breaking the evidence locker's trust model.

2. **Fragmented Volume Inventory and Governance**: Without OSAC control plane visibility, CaaS volumes exist only as Kubernetes PVCs in tenant cluster etcd, invisible to OSAC's unified resource inventory. This prevents:

   - **Cross-workload governance**: Cannot apply policies like "snapshot all production volumes daily" uniformly across VMs, clusters, and bare-metal hosts.
   - **Unified inventory**: `osac volumes list --organization acme-corp` returns VMaaS and BMaaS volumes but omits CaaS PVCs.
   - **Consistent quota enforcement**: Different backends enforce quotas differently (VAST: hard limit at provision, Ceph: soft limit with grace, Pure: configurable burst). OSAC cannot provide consistent API-level quota enforcement across storage tiers.
   - **Account lifecycle control**: Suspending an organization requires revoking credentials in every tenant cluster instead of a single control-plane operation.
   - **Encryption key management**: Storage backends like NetApp ONTAP that support per-volume encryption with external KMIP servers (NetApp Volume Encryption with unique keys per volume) require OSAC to broker key requests from the central KMS (e.g., Vault). Without OSAC in the path, either volumes remain unencrypted (compliance violation), tenant clusters need direct KMIP access (security risk, credential distribution), or encryption keys are managed per-cluster (fragmented, no central audit trail of which volumes are encrypted with which keys).
   
   Operational scenarios become fragmented: troubleshooting "We're billed for 8TB but only see 6TB" requires querying vendor-specific backend APIs, manually mapping hardware volume IDs back to PVCs across isolated clusters, and reconstructing inventory by hand.

3. **Network Trust Boundary Violation**: Direct backend access requires tenant cluster worker nodes (low-trust zone) to access storage backend control APIs on the storage management network (high-trust zone). This violates network segmentation principles for sovereign environments where low-trust tenant infrastructure must remain isolated from high-trust storage control infrastructure. With the OSAC CSI driver proxy, tenant clusters communicate only with the OSAC control plane via the existing tenant-to-control-plane network path, while only the management cluster (high-trust) accesses the storage control network. The data path remains direct (iSCSI/NVMe-TCP from worker nodes to storage data network), but the **control path** (CreateVolume, DeleteVolume, ControllerPublishVolume) is proxied through the high-trust zone, maintaining clear network trust boundaries.

4. **Operational Complexity**: Each storage vendor has different API patterns, authentication mechanisms, and multi-tenancy models. OSAC would need to query each backend separately to load usage data, breaking the single-source-of-truth control plane pattern. Usage data will lag behind actual values (polling/caching), causing confusing UX where quota appears available but requests are rejected by the backend.

### User Stories

**As a Cloud Service Provider (CSP)**, I want tenant storage requests to flow through the OSAC control plane so that I can enforce organization quotas, audit all operations, and maintain sovereignty claims over customer data.

**As a CSP Security Officer**, I want storage backend credentials isolated in the management cluster so that compromised tenant clusters cannot escalate privileges to the shared storage infrastructure.

**As a CSP Operations Engineer**, I want a centralized audit log of all storage lifecycle events (create, attach, detach, delete, snapshot) so that I can troubleshoot issues and demonstrate compliance without correlating logs across multiple vendor backends.

**As an Organization User**, I want to provision PersistentVolumeClaims in my tenant cluster using standard Kubernetes workflows so that my applications can consume block storage without understanding OSAC-specific APIs.

**As a CSP Architect**, I want OSAC to abstract storage backend differences (VAST vs Ceph vs NetApp) so that I can offer a uniform storage tier API without exposing tenant cluster-admins to vendor-specific configuration details.

### Goals

* Design and implement an OSAC CSI driver that runs in tenant Kubernetes clusters and proxies CSI operations to the OSAC Volume API
* Ensure all storage lifecycle operations (CreateVolume, DeleteVolume, ControllerPublishVolume, CreateSnapshot) flow through the OSAC control plane for policy enforcement and auditing
* Integrate with the OSAC Volume API (OSAC-48) for quota enforcement, metering, and authorization
* Keep storage backend credentials and management network access isolated in the management cluster only
* Provide tenant users with a transparent Kubernetes storage experience using standard PersistentVolumeClaim workflows
* Centralize audit logging for all storage operations in the OSAC control plane
* Support multiple storage tiers (fast, standard, archival) via StorageClass abstraction

### Non-Goals

* Storage for hosted control plane infrastructure components (etcd, API server) — these use management cluster storage directly
* File storage (NFS, SMB) or object storage (S3) — deferred to future enhancements
* VMaaS storage integration — this EP focuses solely on the CaaS CSI driver for Kubernetes workloads. VMaaS (VMs) do not use CSI drivers. Both VMaaS and CaaS may share the OSAC Volume API backend (OSAC-48), but the CSI driver component is CaaS-specific.
* Custom volume lifecycle policies beyond standard CSI operations (e.g., auto-tiering, data migration) — deferred to future enhancements
* Support for tenant clusters not hosted by OSAC (e.g., self-managed OpenShift) — out of scope

## Proposal

### High-Level Architecture

The proposed architecture establishes a three-tier control plane for CaaS storage:

```
┌─────────────────────────────────────────────────────────────┐
│ Tenant Kubernetes Cluster (Hosted by OSAC)                 │
│                                                             │
│  ┌─────────────┐          ┌──────────────────────┐         │
│  │  Workload   │──────────│ PersistentVolumeClaim│         │
│  │    Pod      │  mount   └──────────┬───────────┘         │
│  └─────────────┘                     │                     │
│                                      │                     │
│  ┌───────────────────────────────────▼──────────────────┐  │
│  │ Vendor CSI Node Plugin (VAST, Ceph, etc.)            │  │
│  │ - Handles NodeStageVolume, NodePublishVolume         │  │
│  │ - Mounts volumes using connection info              │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ OSAC CSI Controller Plugin                           │  │
│  │ - Intercepts CreateVolume, DeleteVolume, etc.        │  │
│  │ - Forwards requests to OSAC Volume API via gRPC      │  │
│  └──────────────────┬───────────────────────────────────┘  │
└────────────────────┼────────────────────────────────────────┘
                     │ gRPC over mTLS
                     │ (tenant→control plane)
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ OSAC Control Plane (Management Cluster)                    │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ OSAC Volume API (OSAC-48)                            │  │
│  │ - Authenticates tenant requests                      │  │
│  │ - Enforces quota and RBAC policies                   │  │
│  │ - Writes audit log entries                           │  │
│  │ - Calls vendor CSI driver in management cluster      │  │
│  └──────────────────┬───────────────────────────────────┘  │
│                     │                                       │
│                     ▼                                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Vendor CSI Driver (VAST, Ceph, etc.)                 │  │
│  │ - Runs in management cluster with admin credentials  │  │
│  │ - Communicates with storage backend over isolated    │  │
│  │   provider network                                   │  │
│  └──────────────────┬───────────────────────────────────┘  │
└────────────────────┼────────────────────────────────────────┘
                     │ Storage provider network
                     │ (isolated from tenant clusters)
                     ▼
         ┌────────────────────────────┐
         │  Storage Backend           │
         │  (VAST, Ceph, NetApp, etc.)│
         └────────────────────────────┘
```

### Workflow Description

#### Volume Provisioning (CreateVolume)

**Actors**: Tenant User, Kubernetes Scheduler, OSAC CSI Driver, OSAC Volume API, Vendor CSI Driver, Storage Backend

1. **Tenant User** creates a PersistentVolumeClaim in their tenant cluster:
   ```yaml
   apiVersion: v1
   kind: PersistentVolumeClaim
   metadata:
     name: my-data-volume
   spec:
     storageClassName: fast  # maps to OSAC storage tier
     accessModes: [ReadWriteOnce]
     resources:
       requests:
         storage: 100Gi
   ```

2. **Kubernetes** detects the unbound PVC and triggers the CSI external-provisioner sidecar, which calls `CreateVolume` on the OSAC CSI driver controller plugin.

3. **OSAC CSI Driver (Controller)** extracts the request parameters (size, storage tier, access mode) and forwards a `CreateVolume` gRPC request to the OSAC Volume API, including:
   - Tenant identity (extracted from ServiceAccount token)
   - Organization ID (from tenant cluster metadata)
   - Storage tier (from StorageClass parameter)
   - Volume size and access mode

4. **OSAC Volume API** (fulfillment-service):
   - Authenticates the tenant cluster's request using mTLS and RBAC
   - Enforces organization quotas and writes an immutable audit log entry
   - Creates a `Volume` resource in the database
   - Calls the appropriate vendor CSI driver in the management cluster (e.g., VAST CSI driver) via the Kubernetes CSI interface
   - Returns volume metadata (volumeID, connection parameters) to the OSAC CSI driver

5. **Vendor CSI Driver** (in management cluster):
   - Communicates with the storage backend over the isolated provider network
   - Provisions the volume on the storage array
   - Returns volume details to OSAC Volume API

6. **OSAC Volume API**:
   - Updates `Volume` resource state
   - Writes audit log entry
   - Returns success to OSAC CSI driver in tenant cluster

7. **OSAC CSI Driver** returns the volume metadata to Kubernetes, which binds the PVC and creates a PersistentVolume.

#### Volume Attachment (ControllerPublishVolume)

**Actors**: Kubernetes Scheduler, OSAC CSI Driver, OSAC Volume API, Vendor CSI Driver

1. **Kubernetes Scheduler** assigns a pod using the PVC to a node and creates a `VolumeAttachment` resource.

2. **CSI external-attacher** sidecar calls `ControllerPublishVolume` on the OSAC CSI driver with the volume ID and target node ID.

3. **OSAC CSI Driver (Controller)** forwards the request to OSAC Volume API.

4. **OSAC Volume API**:
   - Validates the attachment request and writes audit log entry
   - Calls vendor CSI driver's `ControllerPublishVolume` to prepare the volume for the specific node

5. **Vendor CSI Driver** performs backend-specific attachment operations (e.g., for iSCSI: map LUN to initiator, for NFS: configure export with node IP) and returns connection info (iSCSI target IQN, NFS mount path, etc.).

6. **OSAC Volume API**:
   - Updates `Volume` resource with attachment metadata and writes audit log entry
   - Returns connection info to OSAC CSI driver

7. **OSAC CSI Driver** returns publish context (connection info) to Kubernetes.

#### Volume Mounting (NodeStageVolume, NodePublishVolume)

**Actors**: Kubelet, Vendor CSI Node Plugin (VAST, Ceph, etc.)

1. **Kubelet** on the target node calls `NodeStageVolume` on the vendor CSI node plugin, passing the volume ID and staging path.

2. **Vendor CSI Node Plugin**:
   - Retrieves connection info from the publish context (returned by ControllerPublishVolume via OSAC controller)
   - Performs protocol-specific mount operations (iSCSI login, NFS mount, RBD map) using the connection info
   - Stages the volume to the staging path

3. **Kubelet** calls `NodePublishVolume` to bind-mount the staged volume into the pod's namespace.

**Note**: The vendor node plugin does NOT communicate with the OSAC Volume API or storage backend control plane directly. It only uses the connection info (mount paths, target IQNs, etc.) provided by the OSAC controller plugin via the publish context. This is the same vendor node plugin used in the management cluster, reused in tenant clusters for reduced complexity and increased supportability.

#### Volume Deletion (DeleteVolume)

**Actors**: Tenant User, Kubernetes, OSAC CSI Driver, OSAC Volume API, Vendor CSI Driver

1. **Tenant User** deletes the PersistentVolumeClaim.

2. **Kubernetes** (via external-provisioner) calls `DeleteVolume` on the OSAC CSI driver.

3. **OSAC CSI Driver (Controller)** forwards the delete request to OSAC Volume API.

4. **OSAC Volume API**:
   - Validates deletion and writes audit log entry
   - Calls vendor CSI driver's `DeleteVolume`

5. **Vendor CSI Driver** deletes the volume from the storage backend.

6. **OSAC Volume API**:
   - Marks `Volume` resource as deleted
   - Updates organization quota and writes audit log entry

### API Extensions

#### New Component: OSAC CSI Controller Plugin

A new repository (`osac-csi-driver`) will be created with the following components:

- **Controller Plugin**: Implements CSI Controller Service (CreateVolume, DeleteVolume, ControllerPublishVolume, ControllerUnpublishVolume, CreateSnapshot, DeleteSnapshot). This is the OSAC-specific component that proxies to the OSAC Volume API.
- **gRPC Client**: Communicates with OSAC Volume API (fulfillment-service private API)
- **Deployment Manifests**: Deployment (controller plugin) + RBAC + ServiceAccount
- **CSI Sidecars**: Uses Kubernetes CSI sidecar containers (external-provisioner, external-attacher, external-snapshotter)

**Note**: The CSI Node Service (NodeStageVolume, NodePublishVolume, etc.) is provided by the **vendor's existing node plugin** (VAST, Ceph, NetApp). OSAC reuses these vendor-provided DaemonSets in tenant clusters to reduce implementation complexity, improve supportability, and leverage vendor-tested code for protocol-specific operations (iSCSI, NFS, RBD).

#### StorageClass Definition

Tenant clusters will be provisioned with StorageClasses that reference the OSAC CSI driver:

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast
provisioner: csi.osac.io
parameters:
  tier: fast  # maps to OSAC storage tier
  type: block
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true
```

The `tier` parameter maps to the storage tier defined in the OSAC control plane (see [tenant-storage-tiers](/enhancements/tenant-storage-tiers)).

#### OSAC Volume API Integration

The OSAC CSI driver consumes the private Volume API defined in OSAC-48. Key RPCs:

- `CreateVolume(CreateVolumeRequest) → Volume`
- `DeleteVolume(DeleteVolumeRequest) → Empty`
- `AttachVolume(AttachVolumeRequest) → AttachVolumeResponse` (returns connection info)
- `DetachVolume(DetachVolumeRequest) → Empty`
- `CreateSnapshot(CreateSnapshotRequest) → Snapshot`
- `DeleteSnapshot(DeleteSnapshotRequest) → Empty`

These API calls enforce quota, RBAC, and audit logging before delegating to vendor CSI drivers in the management cluster.

### Implementation Details

#### CSI Driver Implementation

**Language**: Go (standard for Kubernetes CSI drivers)

**Dependencies**:
- `kubernetes-csi/csi-lib-utils`: CSI helper libraries
- `container-storage-interface/spec`: CSI protobuf definitions
- OSAC Volume API client (generated from fulfillment-service protos)
- `google.golang.org/grpc`: gRPC client for OSAC API communication

**OSAC Controller Plugin Responsibilities**:
- Accept CSI Controller RPC calls from CSI sidecars
- Translate CSI requests to OSAC Volume API calls
- Handle authentication (mTLS, ServiceAccount tokens)
- Return CSI-compliant responses based on OSAC API responses, including publish context with connection info for the vendor node plugin

**Vendor Node Plugin Responsibilities** (reused from vendor's existing implementation):
- Accept CSI Node RPC calls from kubelet
- Parse connection info from publish context (e.g., iSCSI target, NFS path, RBD monitor addresses)
- Perform protocol-specific mount operations (iscsiadm, mount.nfs, rbd map)
- Handle volume cleanup on unmount

**Rationale for Reusing Vendor Node Plugins**: Vendor CSI node plugins are complex, protocol-specific, and well-tested. Reusing them reduces OSAC's implementation burden, improves supportability (CSPs can leverage vendor support channels), and ensures compatibility with vendor storage features (multipath, CHAP auth, etc.).

**Authentication**:
- Tenant cluster → OSAC API: mTLS with cluster-specific client certificates
- OSAC API identifies the tenant cluster and organization from the client certificate
- OSAC API enforces RBAC policies (organization quota, storage tier access)

#### OSAC Volume API Changes (OSAC-48 Dependency)

The Volume API must support CSI-originated requests:

**New RPC**:
```protobuf
service Volumes {
  rpc AttachVolume(AttachVolumeRequest) returns (AttachVolumeResponse);
}

message AttachVolumeRequest {
  string volume_id = 1;
  string node_id = 2;  // Kubernetes node ID from tenant cluster
  map<string, string> volume_context = 3;
}

message AttachVolumeResponse {
  map<string, string> publish_context = 1;  // connection info (IQN, NFS path, etc.)
}
```

**Audit Logging**:
All volume lifecycle operations are logged to the centralized audit system for compliance and troubleshooting. Specific audit log schema and event types will be defined as part of the OSAC Volume API implementation (OSAC-48).

#### Vendor CSI Driver Integration

OSAC Volume API delegates to vendor CSI drivers running in the management cluster:

**VAST Example**:
1. OSAC Volume API receives `CreateVolume(tier=fast, size=100Gi)` from tenant cluster
2. Looks up `fast` tier → resolves to VAST-backed StorageClass in management cluster
3. Creates a PVC in a dedicated namespace (e.g., `osac-storage-backend`) using the VAST CSI driver
4. VAST CSI driver provisions volume on VAST array
5. OSAC API extracts volume metadata (NFS export path) from the resulting PV
6. Returns metadata to OSAC CSI driver in tenant cluster

**Ceph RBD Example**:
1. OSAC Volume API creates PVC using Ceph RBD StorageClass in management cluster
2. Ceph CSI driver provisions RBD image
3. On attach, Ceph CSI driver maps the RBD image and returns device path
4. OSAC API returns connection info (monitor addresses, pool, image name, authentication secret)
5. Vendor Ceph CSI node plugin in tenant cluster uses this info to map the RBD image locally

**Isolation**: Vendor CSI drivers run in the management cluster with full backend credentials. Tenant clusters never receive these credentials — they only receive connection info (mount paths, target IQNs) needed by the node plugin to perform data-plane operations.

#### Deployment

**Management Cluster**:
- OSAC Volume API (fulfillment-service) updated with Volume resource support
- Vendor CSI drivers deployed (VAST, Ceph, NetApp) with admin credentials
- Storage backend network access (isolated VLAN, no tenant cluster access)

**Tenant Cluster** (provisioned by OSAC):
- OSAC CSI controller plugin deployed as Deployment
- Vendor CSI node plugins deployed as DaemonSets (VAST, Ceph, etc.)
- StorageClasses created with `provisioner: csi.osac.io` and tier parameters
- Client certificate for mTLS to OSAC Volume API
- No storage backend credentials

### Risks and Mitigations

#### Risk: CSI Controller Plugin Complexity

**Description**: Implementing a CSI controller plugin requires careful integration with Kubernetes CSI sidecars, correct error handling, and proper translation between CSI semantics and OSAC Volume API semantics.

**Mitigation**:
- OSAC controller plugin is protocol-agnostic — it only handles control plane operations (CreateVolume, Attach) and delegates protocol-specific logic to vendor node plugins
- Reuse Kubernetes CSI libraries (`csi-lib-utils`, reference implementations) for standard CSI patterns
- Reuse vendor-provided node plugins (VAST, Ceph, NetApp) which already support all protocols (NFS, iSCSI, RBD, FC, NVMe-oF) — no need for OSAC to implement or support protocol-specific mount logic
- Comprehensive testing with CSI sanity tests and e2e scenarios

#### Risk: Network Latency Impact

**Description**: Proxying storage requests through the OSAC control plane adds network hops (tenant cluster → control plane → management cluster → storage backend), which could impact volume provisioning latency.

**Mitigation**:
- Control plane operations (CreateVolume, Attach) are infrequent compared to I/O operations
- Data plane (actual reads/writes) is direct: tenant node → storage backend (no proxy)
- Benchmark provisioning latency in test environments and document acceptable thresholds
- Consider caching resolved connection info in the CSI driver to reduce API calls for repeated attach/detach operations

#### Risk: Single Point of Failure

**Description**: If the OSAC Volume API is unavailable, tenant clusters cannot provision or attach new volumes.

**Mitigation**:
- OSAC Volume API deployed with high availability (multi-replica)
- CSI driver implements retry logic with exponential backoff
- Existing attached volumes continue to function (data plane is independent)
- Monitor control plane availability and alert on degradation

#### Risk: Credential Leakage via Connection Info

**Description**: The vendor CSI node plugin receives connection info (NFS mount paths, iSCSI target IQNs) to mount volumes. A compromised node could observe this data.

**Mitigation**:
- Connection info is data-plane only (mount paths, targets) — no admin credentials
- Even with connection info, the tenant cannot create new volumes or access other organizations' data (enforced by storage backend ACLs)
- This is acceptable risk: tenant nodes MUST have data-plane access to read/write their volumes
- Compared to Option B (vendor CSI in tenant cluster), this is strictly more secure: no control-plane credentials in tenant cluster

#### Risk: Storage Backend Multi-Tenancy Gaps

**Description**: If a storage backend does not support strong multi-tenancy isolation, one organization could access another's volumes by guessing volume IDs or export paths.

**Mitigation**:
- Require storage backends to implement namespace isolation (e.g., VAST views, Ceph pools per organization)
- OSAC Volume API enforces organization-scoped volume access (cannot attach another organization's volume)
- Document minimum multi-tenancy requirements for supported storage backends
- Audit storage backend configurations during CSP onboarding

### Drawbacks

**Increased Complexity**: OSAC must maintain a CSI driver and proxy layer, adding operational burden compared to letting tenant clusters use vendor CSI drivers directly.

**Latency Overhead**: Proxying control plane requests adds milliseconds to volume provisioning, though this is negligible compared to backend provisioning time (seconds to minutes).

**Vendor CSI Driver Dependency**: OSAC Volume API depends on vendor CSI drivers in the management cluster. If a vendor driver has a bug or compatibility issue, it impacts all tenant clusters using that storage tier.

Despite these drawbacks, the centralized control plane architecture is the ONLY viable approach to meet OSAC's sovereignty and audit requirements.

## Alternatives

### Option B: Direct Storage Backend Access (Rejected)

**Description**: Deploy vendor CSI drivers (VAST, Ceph, NetApp) directly in tenant clusters. Tenant clusters communicate with storage backends over a dedicated storage network.

**Architecture**:
```
Tenant Cluster
  └─ Vendor CSI Driver (VAST, Ceph)
       └─ Storage Backend (direct communication)
```

**Why Rejected**:

1. **Violates Sovereignty Claims**: OSAC cannot claim strict governance over tenant data when tenants can provision volumes directly on shared storage infrastructure. The control plane is bypassed, invalidating sovereignty guarantees.

2. **Fragmented Audit Trail**: Storage lifecycle events are logged only in vendor backend systems, not in OSAC's centralized audit log. Compliance audits require correlating logs across multiple storage arrays, breaking the single-source-of-truth requirement.

3. **Information Leakage and Operational Burden**:
   - While storage backends can provide tenant-scoped credentials (separate management endpoints or API keys per organization), distributing these into tenant clusters leaks infrastructure details that OSAC otherwise abstracts (management IPs, backend hardware topology, storage vendor specifics beyond what the node plugin already reveals)
   - This is analogous to leaking which physical host a VM runs on — information OSAC intentionally hides
   - Credential rotation requires updating secrets in every tenant cluster instead of only in the management cluster, increasing operational complexity and surface area for misconfigurations
   - Tenant cluster-admins gain visibility into backend infrastructure that undermines OSAC's abstraction layer

4. **Vendor-Specific Quota Enforcement**: OSAC must rely on each storage backend's native quota implementation, which means:
   - Different quota models per vendor (VAST quotas work differently than Ceph quotas)
   - Different enforcement granularity (some backends support per-organization quotas, others only per-pool or per-project)
   - No single enforcement point or uniform policy across all storage tiers
   - OSAC cannot guarantee consistent quota behavior or reporting across different backends
   - CSPs must configure quotas separately in each backend system, increasing operational complexity
   - Quota violations may behave differently (some backends hard-fail, others soft-warn, others allow overruns)

5. **Operational Complexity**: Each storage vendor has different APIs, authentication models, and multi-tenancy patterns. OSAC must implement vendor-specific clients to query usage, bill organizations, and detect anomalies. This breaks the vendor-agnostic abstraction layer. Additionally, usage data must be polled from backends and will lag behind actual values, causing confusing UX where quota appears available in OSAC but requests are rejected by the backend.

6. **Volume Import Requirement**: To allow users to manage volumes via the OSAC API (resize, snapshot, backup, cross-cluster portability), OSAC must import volume metadata from storage backends. This creates a synchronization problem: volumes created directly via tenant CSI drivers must be discovered and imported, leading to eventual consistency issues and potential conflicts between backend state and OSAC's view.

7. **Breaks API Gateway Boundary**: OSAC's architectural requirement is that all infrastructure mutations flow through the OSAC API for authorization and audit. Option B allows tenants to mutate shared infrastructure out-of-band, violating this guardrail.

**Conclusion**: Option B appears simpler initially (reuse vendor drivers as-is), but long-term complexity is higher: developing and testing per-backend plugins for quota queries, volume import/sync logic, and handling consistency between backend state and OSAC's database. Additionally, it is architecturally incompatible with OSAC's product requirements. The centralized control plane (Option A) is the only viable approach.

## Infrastructure Needed

### Development

- **Test Kubernetes cluster**: kind or OpenShift Local for CSI driver development and unit testing
- **Mock storage backend**: Simple NFS server or MinIO for integration tests
- **gRPC test server**: Mock OSAC Volume API for CSI driver testing

### CI/CD

- **E2E test cluster**: Hosted control planes environment (real OpenShift on bare metal) with VAST or Ceph backend
- **Automated testing**: GitHub Actions workflow to run CSI sanity tests and Kubernetes storage conformance tests
- **Image registry**: Quay.io repository for OSAC CSI driver container images

### Production

- **Management cluster storage**: Existing storage for fulfillment-service database (no new infrastructure)
- **Vendor CSI drivers**: Deployed in management cluster (VAST, Ceph, NetApp drivers are open source or vendor-provided)
- **Storage backend**: CSP-provided VAST, Ceph, or NetApp arrays (OSAC does not provide storage hardware)

**Note**: No additional infrastructure is required beyond what OSAC already deploys for CaaS. The OSAC CSI driver runs in tenant clusters (already provisioned) and the OSAC Volume API is part of fulfillment-service (already deployed).
