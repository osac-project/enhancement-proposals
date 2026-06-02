---
title: storage-backend-import
authors:
  - avishayt
creation-date: 2026-05-20
last-updated: 2026-06-02
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-917
see-also:
  - https://redhat.atlassian.net/browse/OSAC-882
  - /enhancements/tenant-storage-tiers
  - /enhancements/tenant-specific-storageclasses
replaces:
superseded-by:
---

# Storage Backend Import and Observability

## Summary

Enable Cloud Provider Admins to discover, track, and monitor storage backends across spoke hubs through auto-discovered StorageBackend resources. When Cloud Infrastructure Admins install CSI drivers and create labeled StorageClasses for capacity pools on hub clusters, OSAC automatically creates corresponding StorageBackend resources that expose available capacity via a private admin API. Each StorageBackend is tied to a specific hub cluster, providing a unified inventory of storage infrastructure across all hubs and enabling integration with storage tier management.

## Motivation

Cloud Infrastructure Admins install CSI drivers (VAST, Ceph, Pure Storage, NetApp) and create StorageClasses for each capacity pool on spoke hub clusters where tenant workloads run. However, OSAC currently has no unified view of these storage resources across hubs. Cloud Provider Admins cannot see available capacity per hub, cannot track which pools exist across different storage arrays and hub clusters, and have no API-level visibility into the storage infrastructure that backs tenant workloads.

This creates operational blindness: admins must manually query each hub cluster and each storage backend's vendor-specific API to understand capacity, and there is no centralized inventory of storage pools available across all hubs for tenant provisioning.

### User Stories

**As a Cloud Infrastructure Admin**, I want to install a CSI driver and label my StorageClasses so that OSAC automatically discovers and tracks the storage pools without requiring manual API calls or additional configuration.

**As a Cloud Infrastructure Admin**, I want to optionally group multiple pools that belong to the same physical storage array so that Cloud Provider Admins can understand the relationship between pools (e.g., SSD and HDD pools on the same VAST array).

**As a Cloud Provider Admin**, I want to view a list of all discovered storage backends via the OSAC private API so that I have a unified inventory of storage infrastructure across different vendors and arrays.

**As a Cloud Provider Admin**, I want to see the available capacity for each storage pool so that I can understand how much storage can be provisioned for tenants without querying vendor-specific backend APIs.

**As a Cloud Provider Admin**, I want to query all pools on a specific storage array (e.g., "all pools on vast-dc1") so that I can plan capacity allocation and understand the total storage resources on each physical array.

**As a Cloud Provider Admin**, I want to filter storage backends by CSI driver type so that I can see all Ceph pools or all VAST pools independently when planning infrastructure changes.

**As a Cloud Provider Admin**, I want to reference specific storage backends when creating storage tiers so that I can map tenant-facing storage offerings to specific infrastructure pools.

**As a Cloud Provider Admin**, I want to filter storage backends by hub so that I can see all storage pools available on a specific hub cluster when planning tenant placement or troubleshooting capacity issues.

### Goals

* Auto-discover storage backends from labeled Kubernetes StorageClasses without requiring manual API import
* Create one StorageBackend resource per capacity pool per hub (no aggregation)
* Track which hub cluster each storage backend resides on
* Track which pools belong to the same physical storage array via optional labeling
* Expose available capacity per pool via CSIStorageCapacity objects
* Provide admin-only private API for querying and filtering StorageBackend resources by hub, array, and CSI driver
* Enable integration with storage tier management (StorageTiers map to StorageBackends in a many-to-many relationship)

### Non-Goals

* Creating or managing StorageClasses (Cloud Infrastructure Admin responsibility)
* Total physical capacity tracking (requires vendor API integration or tenant volume tracking)
* Allocated capacity and overprovisioning monitoring (requires tenant volume tracking)
* Automatic backend discovery without explicit labels (all StorageClasses would be imported)
* Multi-backend aggregation (single tier spanning multiple pools)
* Backend health monitoring beyond capacity (latency, IOPS, error rates)
* Tenant-facing API access to StorageBackend resources (admin-only)

## Proposal

### High-Level Design

The proposal introduces a new `StorageBackend` resource in the fulfillment-service database and private API. An OSAC controller instance runs on each spoke hub cluster and watches Kubernetes StorageClasses with a discovery label, automatically creating corresponding StorageBackend resources. The controller also watches CSIStorageCapacity objects to populate available capacity data. Each StorageBackend is tagged with the hub ID where it was discovered, enabling cross-hub inventory management.

**Multi-hub architecture context:**
- OSAC has a main hub where fulfillment-service runs
- Multiple spoke hubs exist where tenant VMs and clusters are provisioned
- Storage backends (StorageClasses + CSI drivers) are deployed on spoke hubs
- Each spoke hub has an osac-operator instance that discovers local StorageClasses
- All StorageBackend resources are centralized in the fulfillment-service database

**Discovery flow:**

1. Cloud Infrastructure Admin installs CSI driver on a spoke hub (e.g., VAST, Ceph, Pure)
2. Cloud Infrastructure Admin creates StorageClass for each pool with discovery label:
   - `osac.openshift.io/storage-backend: "vast-dc1-ssd"` (triggers discovery)
   - `osac.openshift.io/storage-array: "vast-dc1"` (optional: groups pools)
3. OSAC controller on that spoke hub detects the labeled StorageClass
4. Controller creates StorageBackend resource in fulfillment-service database with hub_id set to the current hub
5. Controller watches CSIStorageCapacity for that StorageClass
6. Controller updates StorageBackend with available capacity
7. Cloud Provider Admin queries StorageBackends via private API (can filter by hub_id)

**No aggregation:** Each StorageClass maps to exactly one StorageBackend resource. If a physical array has multiple pools (e.g., SSD and HDD), the admin creates separate StorageClasses for each pool, and OSAC creates separate StorageBackend resources. The optional `storage-array` label allows grouping related pools for query purposes.

**Relationship to StorageTier (OSAC-882):**
- StorageBackend is infrastructure-level (discovered from StorageClasses on hubs)
- StorageTier is tenant-facing abstraction (e.g., "fast", "standard", "archive") managed via OSAC API
- A StorageTier can reference multiple StorageBackends (e.g., "fast" tier backed by SSD pools on multiple hubs)
- A StorageBackend can support multiple StorageTiers (e.g., same pool used for "standard" and "archive")
- If a StorageTier has no StorageBackends on a given hub, resources requesting that tier cannot be scheduled there
- StorageTier controller (out of scope) validates StorageBackend references and handles tier-to-StorageClass resolution

### Workflow Description

#### Personas

| Persona | Role | Relevant Actions |
|---------|------|------------------|
| **Cloud Infrastructure Admin** | Manages physical infrastructure and Kubernetes clusters | Installs CSI drivers, creates labeled StorageClasses for capacity pools |
| **Cloud Provider Admin** | Manages OSAC platform and tenant provisioning | Queries storage backends, plans capacity allocation, creates storage tiers |

#### Workflow 1: Cloud Infrastructure Admin discovers a new storage backend on a spoke hub

**Actors:** Cloud Infrastructure Admin

**Prerequisites:** CSI driver installed on spoke hub cluster with `external-provisioner` sidecar configured with `--enable-capacity=true`

**Steps:**

1. Cloud Infrastructure Admin creates a StorageClass for the SSD pool on a VAST array on spoke hub `hub-east-1`:

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: osac-vast-dc1-ssd
  labels:
    osac.openshift.io/storage-backend: "vast-dc1-ssd"
    osac.openshift.io/storage-array: "vast-dc1"
provisioner: csi.vastdata.com
parameters:
  vastNamespace: "/ssd-pool"
allowVolumeExpansion: true
```

2. OSAC StorageBackend controller running on `hub-east-1` detects the new StorageClass (via watch on StorageClasses with the discovery label)

3. Controller extracts:
   - Backend name: `"vast-dc1-ssd"` (from `storage-backend` label)
   - Array name: `"vast-dc1"` (from `storage-array` label)
   - CSI driver: `"csi.vastdata.com"` (from `provisioner` field)
   - StorageClass name: `"osac-vast-dc1-ssd"`
   - Hub ID: `"hub-east-1"` (from controller's hub configuration)

4. Controller creates StorageBackend resource in fulfillment-service database with `hub_id = "hub-east-1"`

5. Controller watches CSIStorageCapacity objects filtered by StorageClass name

6. When CSIStorageCapacity is published by the CSI driver, controller updates StorageBackend with available capacity

**Expected result:** StorageBackend `"vast-dc1-ssd"` is visible via private API with `hub_id = "hub-east-1"` and available capacity populated.

#### Workflow 2: Cloud Infrastructure Admin groups multiple pools on the same array

**Actors:** Cloud Infrastructure Admin

**Prerequisites:** CSI driver installed, SSD pool already discovered (from Workflow 1)

**Steps:**

1. Cloud Infrastructure Admin creates a second StorageClass for the HDD pool on the same VAST array:

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: osac-vast-dc1-hdd
  labels:
    osac.openshift.io/storage-backend: "vast-dc1-hdd"
    osac.openshift.io/storage-array: "vast-dc1"  # Same array as SSD pool
provisioner: csi.vastdata.com
parameters:
  vastNamespace: "/hdd-pool"
allowVolumeExpansion: true
```

2. OSAC controller creates a second StorageBackend resource: `"vast-dc1-hdd"`

**Expected result:**
- Two separate StorageBackend resources exist: `"vast-dc1-ssd"` and `"vast-dc1-hdd"`
- Both have `array_name: "vast-dc1"`
- Cloud Provider Admin can query: `GET /api/private/v1/storage-backends?array_name=vast-dc1` to see all pools on that array

#### Workflow 3: Cloud Provider Admin queries storage backends

**Actors:** Cloud Provider Admin

**Prerequisites:** At least one StorageBackend discovered

**Steps:**

1. Cloud Provider Admin lists all storage backends:
   ```
   GET /api/private/v1/storage-backends
   ```

   Response:
   ```json
   {
     "storage_backends": [
       {
         "id": "uuid-1",
         "name": "vast-dc1-ssd",
         "csi_driver": "csi.vastdata.com",
         "array_name": "vast-dc1",
         "storage_class_name": "osac-vast-dc1-ssd",
         "available_capacity_bytes": "483183820800",
         "hub_id": "hub-east-1"
       },
       {
         "id": "uuid-2",
         "name": "vast-dc1-hdd",
         "csi_driver": "csi.vastdata.com",
         "array_name": "vast-dc1",
         "storage_class_name": "osac-vast-dc1-hdd",
         "available_capacity_bytes": "1978419814400",
         "hub_id": "hub-east-1"
       },
       {
         "id": "uuid-3",
         "name": "ceph-fast",
         "csi_driver": "rook-ceph.rbd.csi.ceph.com",
         "array_name": "ceph-cluster-west",
         "storage_class_name": "osac-ceph-fast",
         "available_capacity_bytes": "2199023255552",
         "hub_id": "hub-west-1"
       }
     ]
   }
   ```

2. Cloud Provider Admin filters by hub to see all storage on `hub-east-1`:
   ```
   GET /api/private/v1/storage-backends?hub_id=hub-east-1
   ```

3. Cloud Provider Admin filters by array:
   ```
   GET /api/private/v1/storage-backends?array_name=vast-dc1
   ```

4. Cloud Provider Admin filters by CSI driver:
   ```
   GET /api/private/v1/storage-backends?csi_driver=csi.vastdata.com
   ```

**Expected result:** Cloud Provider Admin has a unified view of storage infrastructure across all hubs with queryable capacity data.

#### Workflow 4: StorageClass deleted, StorageBackend cleaned up

**Actors:** Cloud Infrastructure Admin

**Steps:**

1. Cloud Infrastructure Admin deletes a StorageClass:
   ```bash
   kubectl delete storageclass osac-vast-dc1-ssd
   ```

2. OSAC controller detects deletion event

3. Controller deletes corresponding StorageBackend resource from database

**Expected result:** StorageBackend `"vast-dc1-ssd"` is removed from the private API. Any storage tiers referencing this backend become invalid (handled by tier controller, out of scope for this EP).

### API Extensions

#### New Message: StorageBackend (fulfillment-service proto)

**File:** `fulfillment-service/proto/private/osac/private/v1/storage_backend_type.proto`

```protobuf
syntax = "proto3";

package osac.private.v1;

// StorageBackend represents a discovered storage capacity pool from a
// labeled Kubernetes StorageClass on a specific hub. One StorageBackend per pool; multiple
// pools on the same physical array are grouped via array_name.
message StorageBackend {
  // Unique identifier for this StorageBackend resource
  string id = 1;

  // Name of the storage backend (from osac.openshift.io/storage-backend label)
  // Must be globally unique across all hubs (like Kubernetes resource names).
  // Recommended naming: include hub identifier for clarity (e.g., "us-east-vast1-ssd")
  // Example: "us-east-vast1-ssd", "eu-west-ceph-fast"
  string name = 2;

  // CSI driver provisioner (from StorageClass provisioner field)
  // Example: "csi.vastdata.com"
  string csi_driver = 3;

  // Optional: physical storage array grouping (from osac.openshift.io/storage-array label)
  // Example: "vast-dc1"
  // Multiple pools on the same array share this value.
  string array_name = 4;

  // Name of the Kubernetes StorageClass that created this backend
  string storage_class_name = 5;

  // Available capacity in bytes (from CSIStorageCapacity.capacity field)
  // This is how much storage can be provisioned now.
  int64 available_capacity_bytes = 6;

  // Timestamp of last capacity update
  google.protobuf.Timestamp last_updated = 7;

  // Hub identifier - the spoke hub cluster where this storage backend exists.
  // This is immutable infrastructure metadata that identifies which hub cluster
  // the StorageClass and CSI driver are deployed on.
  // Example: hub ID from /api/private/v1/hubs
  string hub_id = 8;

  // Storage protocol provided by this backend (block or file/NFS)
  // Auto-detected from the CSI driver provisioner.
  // Example: "block", "nfs"
  string protocol = 9;
}
```

#### New Service: StorageBackends (fulfillment-service proto)

**File:** `fulfillment-service/proto/private/osac/private/v1/storage_backends_service.proto`

```protobuf
syntax = "proto3";

package osac.private.v1;

import "google/api/annotations.proto";
import "osac/private/v1/storage_backend_type.proto";

service StorageBackends {
  // List all storage backends with optional filtering
  rpc List(ListStorageBackendsRequest) returns (ListStorageBackendsResponse) {
    option (google.api.http) = {
      get: "/api/private/v1/storage-backends"
    };
  }

  // Get a specific storage backend by ID
  rpc Get(GetStorageBackendRequest) returns (StorageBackend) {
    option (google.api.http) = {
      get: "/api/private/v1/storage-backends/{id}"
    };
  }
}

message ListStorageBackendsRequest {
  // Optional: filter by array name
  string array_name = 1;

  // Optional: filter by CSI driver
  string csi_driver = 2;

  // Pagination (standard OSAC pattern)
  int32 page = 3;
  int32 size = 4;

  // Optional: filter by hub ID
  string hub_id = 5;
}

message ListStorageBackendsResponse {
  repeated StorageBackend storage_backends = 1;
  int32 total = 2;
}

message GetStorageBackendRequest {
  string id = 1;
}
```

**Note:** This is a **private API only**. No public API exposure. Tenants cannot see StorageBackend resources.

#### Database Schema (fulfillment-service)

**Table:** `storage_backends`

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `name` | VARCHAR(253) | Backend name (from label) |
| `csi_driver` | VARCHAR(253) | CSI driver provisioner |
| `array_name` | VARCHAR(253) | Optional array grouping |
| `storage_class_name` | VARCHAR(253) | Source StorageClass name |
| `available_capacity_bytes` | BIGINT | Available capacity |
| `last_updated` | TIMESTAMP | Last capacity update |
| `hub_id` | UUID | Hub where this backend exists |
| `created_at` | TIMESTAMP | Discovery time |
| `updated_at` | TIMESTAMP | Last modified |

**Indexes:**
- Unique index on `(name, hub_id)` — backend names are unique per hub
- Index on `hub_id` for filtering by hub
- Index on `array_name` for filtering
- Index on `csi_driver` for filtering
- Index on `storage_class_name` for fast lookup during reconciliation

### Implementation Details

#### Component: StorageBackend Controller (osac-operator)

**File:** `osac-operator/internal/controller/storagebackend_controller.go`

**Deployment:** One controller instance per spoke hub. Each controller watches StorageClasses and CSIStorageCapacity objects on its local hub cluster and reports to the centralized fulfillment-service.

**Configuration:** Controller is configured with the hub ID of the hub it's running on (via environment variable or hub metadata). This hub ID is included in all StorageBackend resources created by this controller.

**Responsibilities:**
1. Watch Kubernetes StorageClasses with label `osac.openshift.io/storage-backend` on the local hub
2. Create/update/delete StorageBackend resources in fulfillment-service database via gRPC, tagged with this hub's ID
3. Watch CSIStorageCapacity objects and update corresponding StorageBackend capacity
4. Handle label changes (if `storage-backend` label is removed, delete StorageBackend)

**Reconciliation logic:**

```go
func (r *StorageBackendReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    // 1. Fetch StorageClass
    sc := &storagev1.StorageClass{}
    if err := r.Get(ctx, req.NamespacedName, sc); err != nil {
        if apierrors.IsNotFound(err) {
            // StorageClass deleted - delete StorageBackend via API
            return r.deleteStorageBackend(ctx, req.Name)
        }
        return ctrl.Result{}, err
    }

    // 2. Check for discovery label
    backendName, ok := sc.Labels["osac.openshift.io/storage-backend"]
    if !ok {
        // Label removed - delete StorageBackend if it exists
        return r.deleteStorageBackend(ctx, req.Name)
    }

    // 3. Extract fields
    arrayName := sc.Labels["osac.openshift.io/storage-array"]
    csiDriver := sc.Provisioner
    hubID := r.HubID // Controller knows its hub ID from configuration

    // 4. Query CSIStorageCapacity for this StorageClass
    capacity, err := r.getAvailableCapacity(ctx, sc.Name)
    if err != nil {
        log.Error(err, "failed to query CSIStorageCapacity")
        capacity = 0 // Will be updated when CSIStorageCapacity becomes available
    }

    // 5. Create or update StorageBackend via fulfillment-service API
    return r.upsertStorageBackend(ctx, backendName, arrayName, csiDriver, sc.Name, capacity, hubID)
}
```

**Watch predicates:**
- Watch StorageClasses with label `osac.openshift.io/storage-backend`
- Watch CSIStorageCapacity objects (trigger update to associated StorageBackend)

**CSIStorageCapacity integration:**

CSIStorageCapacity objects are created by the CSI driver's `external-provisioner` sidecar when configured with `--enable-capacity=true`. The controller queries CSIStorageCapacity filtered by `storageClassName` to find capacity for a given StorageClass.

```go
func (r *StorageBackendReconciler) getAvailableCapacity(ctx context.Context, storageClassName string) (int64, error) {
    capacityList := &storagev1.CSIStorageCapacityList{}
    if err := r.List(ctx, capacityList); err != nil {
        return 0, err
    }

    // Find CSIStorageCapacity matching the StorageClass
    for _, cap := range capacityList.Items {
        if cap.StorageClassName == storageClassName {
            if cap.Capacity != nil {
                return cap.Capacity.Value(), nil
            }
        }
    }

    return 0, fmt.Errorf("no CSIStorageCapacity found for StorageClass %s", storageClassName)
}
```

**Note:** CSIStorageCapacity may be topology-aware (capacity varies by zone/node). If multiple CSIStorageCapacity objects exist for one StorageClass, the controller aggregates the minimum capacity (most conservative) or sums capacity across topology segments (implementation decision deferred to development).

#### Fulfillment-Service Changes

**New gRPC service:** `StorageBackends` (private API)

**Database operations:**
- `CreateStorageBackend(name, csi_driver, array_name, storage_class_name, available_capacity_bytes, hub_id)`
- `UpdateStorageBackend(name, hub_id, available_capacity_bytes, last_updated)`
- `DeleteStorageBackend(name, hub_id)`
- `ListStorageBackends(array_name, csi_driver, hub_id, page, size)`
- `GetStorageBackend(id)`

**Controller calls fulfillment-service via gRPC** to persist StorageBackend state. The controller does not store state locally; fulfillment-service database is the source of truth.

#### Label Conventions

| Label Key | Required | Values | Purpose |
|-----------|----------|--------|---------|
| `osac.openshift.io/storage-backend` | Yes | Unique backend name (e.g., `"vast-dc1-ssd"`) | Triggers discovery and uniquely identifies the backend |
| `osac.openshift.io/storage-array` | No | Array identifier (e.g., `"vast-dc1"`) | Groups pools on the same physical array for query filtering |

**Label validation:**
- `storage-backend` value must be unique per hub (enforced by database unique constraint on `(name, hub_id)`)
- Same backend name can exist on different hubs (e.g., "fast-ssd" on both hub-east-1 and hub-west-1)
- Label values must follow Kubernetes label syntax (DNS subdomain format, max 63 characters)

#### Error Handling

**Scenario: Duplicate backend name on same hub**
- Two StorageClasses on the same hub labeled with the same `storage-backend` value
- Controller detects conflict when calling `CreateStorageBackend` (database unique constraint violation on `(name, hub_id)`)
- Controller emits Kubernetes Event: `Warning DuplicateStorageBackend "Multiple StorageClasses with backend name 'vast-dc1-ssd' on hub hub-east-1"`
- Second StorageClass is skipped (not imported)
- Note: Same backend name is allowed on different hubs (e.g., "fast-ssd" on hub-east-1 and hub-west-1 are distinct StorageBackends)

**Scenario: CSIStorageCapacity not available**
- StorageClass exists but CSI driver has not published capacity yet
- Controller creates StorageBackend with `available_capacity_bytes = 0`
- Controller continues to watch CSIStorageCapacity; capacity is updated when published

**Scenario: StorageClass deleted while storage tier references it**
- StorageBackend is deleted from database
- Storage tier controller (OSAC-882, out of scope) detects invalid backend reference
- Tier provisioning fails with clear error message referencing missing backend

### Risks and Mitigations

#### Risk: CSIStorageCapacity topology fragmentation

**Description:** CSI drivers may publish multiple CSIStorageCapacity objects per StorageClass when storage is topology-aware (e.g., capacity varies by availability zone or node). The controller must decide how to aggregate capacity: sum across topologies, or report the minimum?

**Mitigation:**
- For initial implementation, report the **minimum capacity** across all topology segments (most conservative)
- Document the aggregation strategy in API documentation
- Future enhancement: expose topology-specific capacity via additional API fields

#### Risk: Stale capacity data

**Description:** CSIStorageCapacity objects are periodically updated by the CSI driver (default poll interval: 1 minute). Available capacity in OSAC may lag behind actual backend state.

**Mitigation:**
- Accept eventual consistency (capacity data is informational, not transactional)
- Expose `last_updated` timestamp in StorageBackend API so admins can see data freshness
- Recommend CSI drivers configure short poll intervals (`--capacity-poll-interval=1m`)

#### Risk: Label removal or misconfiguration

**Description:** Cloud Infrastructure Admin removes the `storage-backend` label from a StorageClass that is referenced by storage tiers, breaking tier provisioning.

**Mitigation:**
- StorageBackend controller emits Event when deleting a backend due to label removal
- Storage tier controller (OSAC-882) validates backend references and reports errors
- Operational guidance: do not remove labels from production StorageClasses

#### Risk: CSI driver does not support capacity reporting

**Description:** Older or minimal CSI drivers may not implement the `GetCapacity` RPC or deploy the `external-provisioner` sidecar with capacity enabled.

**Mitigation:**
- Document CSI driver requirements in Prerequisites section
- Controller creates StorageBackend with `available_capacity_bytes = 0` if CSIStorageCapacity is unavailable
- Admin can still use the backend for tier provisioning; capacity is simply unknown
- Recommend CSI drivers that support capacity reporting (VAST, Ceph RBD, NetApp Trident, Pure, etc.)

### Drawbacks

**Operational overhead:** Cloud Infrastructure Admins must manually label StorageClasses for discovery. If labels are misconfigured or omitted, backends will not appear in OSAC inventory.

**Limited capacity observability:** Only **available capacity** is exposed (from CSIStorageCapacity). Total physical capacity and allocated capacity require additional integration (vendor APIs or tenant volume tracking). Admins may expect more detailed capacity metrics than this proposal provides.

**No validation of storage parameters:** OSAC trusts that the StorageClass parameters are correct (e.g., `vastNamespace` points to a real pool). If misconfigured, provisioning will fail at the CSI driver level, not at OSAC discovery time.

**Label sprawl:** Each pool requires a separate StorageClass and unique label. Large deployments with many pools may have dozens of labeled StorageClasses, increasing configuration complexity.

## Alternatives

### Alternative 1: Manual API import instead of auto-discovery

**Description:** Require Cloud Provider Admins to manually import storage backends via a `CreateStorageBackend` API call with explicit parameters (backend name, CSI driver, StorageClass reference).

**Advantages:**
- Admin has full control over which backends are imported
- Supports importing backends that don't correspond to Kubernetes StorageClasses (e.g., external storage arrays)

**Disadvantages:**
- Extra operational step (install CSI driver → create StorageClass → manually import backend)
- Risk of configuration drift (StorageClass exists but not imported, or vice versa)
- Requires admin to provide metadata that is already available on the StorageClass (CSI driver, array name)

**Why rejected:** Auto-discovery from labels is more Kubernetes-native and reduces operational toil. The label opt-in still provides control over which backends are imported.

### Alternative 2: Aggregate pools per array instead of one backend per pool

**Description:** Group all pools on the same array into one StorageBackend resource with aggregated capacity.

**Advantages:**
- Simpler model: one StorageBackend per physical array
- Matches admin mental model ("I have one VAST array")

**Disadvantages:**
- Loses granularity: cannot see capacity per pool (SSD vs HDD)
- Storage tiers need to reference specific pools, not the aggregate array
- Different pools have different performance characteristics (SSD fast, HDD slow) and should not be conflated

**Why rejected:** One StorageBackend per pool is more precise and maps cleanly to storage tier provisioning. The optional `array_name` field provides grouping without losing pool-level detail.

### Alternative 3: Discover all StorageClasses automatically (no labels required)

**Description:** Import every StorageClass in the cluster as a StorageBackend.

**Advantages:**
- No manual labeling required
- Captures all storage infrastructure automatically

**Disadvantages:**
- Imports unintended StorageClasses (local-path, hostPath, testing classes)
- No way to exclude irrelevant storage from OSAC inventory
- Creates noise in admin API (dozens of backends, many not relevant to tenant provisioning)

**Why rejected:** Explicit labeling provides clear opt-in semantics and prevents pollution of the StorageBackend inventory with irrelevant storage.

### Alternative 4: Use CRDs instead of database-backed resources

**Description:** Define StorageBackend as a Kubernetes CRD instead of a fulfillment-service database resource.

**Advantages:**
- Kubernetes-native (kubectl-friendly)
- Controller can use Kubernetes watch/informer patterns

**Disadvantages:**
- Requires cross-cluster CRD distribution (management cluster has CRDs, but fulfillment-service runs elsewhere)
- Breaks OSAC's pattern of using fulfillment-service as the source of truth for resources
- Harder to integrate with storage tier API (which is also in fulfillment-service)

**Why rejected:** Consistency with existing OSAC resource model (database-backed, gRPC API).

## Open Questions

None at this time.

## Test Plan

Test plan will be developed during implementation. Expected coverage includes:

**Unit tests:**
- StorageBackend controller: label-based filtering, CSIStorageCapacity aggregation, gRPC API calls
- Fulfillment-service: StorageBackend CRUD operations, filtering by array/driver, pagination

**Integration tests:**
- Create labeled StorageClass → verify StorageBackend created in database with correct hub_id
- CSI driver publishes CSIStorageCapacity → verify StorageBackend capacity updated
- Delete StorageClass → verify StorageBackend deleted
- Change `storage-backend` label value → verify old backend deleted, new backend created
- Duplicate `storage-backend` label on same hub → verify conflict handling (Event emitted, one backend created)
- Same backend name on different hubs → verify both StorageBackends created successfully (no conflict)
- Filter by hub_id → verify only backends from that hub returned

**E2E tests:**
- Install VAST CSI driver on test cluster
- Create labeled StorageClasses for SSD and HDD pools
- Query private API: verify both backends appear with correct capacity and array grouping
- Filter by array name → verify both pools returned
- Filter by CSI driver → verify only VAST backends returned
- Delete one StorageClass → verify corresponding backend removed from API

**Focus areas for testing:**
- CSIStorageCapacity topology handling (single vs. multiple topology segments)
- Eventual consistency of capacity updates (CSI driver poll interval vs. controller watch latency)
- Label edge cases (label removed, label value changed, duplicate labels)
- Database constraint enforcement (unique backend names)

## Graduation Criteria

This feature targets Dev Preview. No GA timeline is defined at this time.

## Upgrade / Downgrade Strategy

**Upgrade:**
- OSAC controller and fulfillment-service must be upgraded together (controller depends on StorageBackends gRPC service)
- On first deployment, controller scans all existing StorageClasses for discovery labels and imports any previously unlabeled backends
- No migration required (StorageBackend is a new resource)

**Downgrade:**
- StorageBackend resources remain in database but are not updated
- Controller stops reconciling StorageClasses
- Private API continues to serve stale data until StorageBackend table is manually purged

**Version skew:**
- Controller (osac-operator) and fulfillment-service must be at the same version
- Hub cluster Kubernetes version is independent (controller uses standard storagev1 API)

## Version Skew Strategy

No special version skew considerations. This feature is isolated to osac-operator and fulfillment-service with no cross-cluster dependencies.

## Support Procedures

**Symptom:** StorageBackend not appearing in private API after labeling StorageClass

**Diagnosis:**
- Check controller logs: `kubectl logs -n osac-system deployment/osac-operator-controller-manager`
- Verify label syntax: `kubectl get storageclass <name> -o yaml | grep osac.openshift.io/storage-backend`
- Check for duplicate label conflict: query database for duplicate backend names

**Resolution:**
- Fix label syntax if invalid
- If duplicate detected, rename one of the StorageClasses' labels to a unique value
- Restart controller if reconciliation is stuck: `kubectl rollout restart -n osac-system deployment/osac-operator-controller-manager`

**Symptom:** Available capacity is zero or stale

**Diagnosis:**
- Check if CSI driver publishes CSIStorageCapacity: `kubectl get csistoragecapacity`
- Verify `external-provisioner` sidecar is configured with `--enable-capacity=true`
- Check `last_updated` timestamp in StorageBackend API response

**Resolution:**
- If no CSIStorageCapacity found: reconfigure CSI driver deployment to enable capacity reporting
- If CSIStorageCapacity exists but capacity is stale: check CSI driver logs for errors, verify storage backend is reachable

**Symptom:** StorageBackend not deleted after StorageClass removal

**Diagnosis:**
- Check controller logs for deletion errors
- Verify fulfillment-service API is reachable from controller

**Resolution:**
- Manually delete StorageBackend via private API if necessary: `DELETE /api/private/v1/storage-backends/{id}`

## Infrastructure Needed

No additional infrastructure required. This feature uses existing OSAC components:
- osac-operator (new controller added)
- fulfillment-service (new proto/service/database table)
- Hub cluster (watches existing Kubernetes resources: StorageClass, CSIStorageCapacity)
