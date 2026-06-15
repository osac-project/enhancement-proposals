---
title: baremetal-instance-types
authors:
  - ajamias@redhat.com
creation-date: 2026-06-15
last-updated: 2026-06-15
tracking-link:
  - TBD
see-also:
  - "/enhancements/baremetal-instance-api"
  - "/enhancements/bare-metal-fulfillment"
  - "/enhancements/vm-instance-types"
replaces:
superseded-by:
---

# Bare Metal Instance Types

## Summary

This enhancement introduces `BareMetalInstanceType` as a cluster-scoped Kubernetes CRD that
represents a class of bare metal hardware available for tenant provisioning. Each
`BareMetalInstanceType` resource corresponds to a `hostType` value used by `BareMetalInstance` and
`BareMetalPool`, bridging the pluggable inventory interface with the OSAC BMaaS public API. Cloud
Provider Admins define and manage instance types via the `osac` CLI; the fulfillment service
creates and manages the corresponding CRDs in Kubernetes on their behalf. The fulfillment service
reads these CRDs to serve `ListBareMetalInstanceTypes` and `GetBareMetalInstanceType` API calls,
enabling Tenant Users to self-select hardware for provisioning without direct knowledge of the
underlying inventory. When the baremetal-fulfillment-operator reconciles a `BareMetalInstance`, it
reads the associated `BareMetalInstanceType` and uses its fields to filter available hosts from the
inventory backend in an inventory-client-specific manner.

Storage is explicitly excluded from instance type specifications: bare metal storage is offloaded to
NFS and is not a hardware differentiator at the instance type level.

## Motivation

Currently, `hostType` in `BareMetalInstance.spec.hostType` and
`BareMetalPool.spec.hostSets[].hostType` is an opaque string. There is no structured resource that:

- Documents what hardware a given type provides (CPUs, memory, accelerators, network ports)
- Manages the type's lifecycle (active, deprecated, obsolete)
- Exposes the type catalog to the BMaaS API layer for tenant self-service
- Provides structured fields the operator can use to filter available hosts from inventory

Without this, the BMaaS API cannot present meaningful instance type choices to Tenant Users, and
the inventory discovery interface has nowhere to publish availability data.

### User Stories

* As a **Cloud Provider Admin**, I want to define and expose available bare metal instance types
  so that the OSAC BMaaS API can present them to Tenant Users for self-service provisioning.
* As a **Cloud Provider Admin**, I want to annotate each instance type with CPU, memory, and
  network specifications so that Tenant Users can select the right hardware for their workloads
  without needing to contact the infrastructure team.
* As a **Cloud Provider Admin**, I want to manage instance type lifecycle states (Active /
  Deprecated / Obsolete) so that I can retire aging hardware classes gracefully without deleting the
  definitions or breaking existing `BareMetalInstance` records.
* As a **Cloud Provider Admin**, I want to provide a replacement suggestion and timeline when
  deprecating an instance type so that Tenant Users have clear guidance on how to migrate workloads.
* As a **Tenant User**, I want to list available bare metal instance types with hardware
  specifications so that I can choose the right type for my workload.
* As a **Tenant User**, I want to provision a `BareMetalInstance` by selecting an instance type
  name so that I do not need to know the underlying inventory structure.
* As a **Tenant User**, I want to be warned when I select a deprecated instance type so that I can
  plan a migration to the recommended replacement.

### Goals

* Provide a cluster-scoped `BareMetalInstanceType` CRD as the authoritative catalog of hardware
  types, with `metadata.name` as the canonical `hostType` key shared across `BareMetalInstance`,
  `BareMetalPool`, and the BMaaS API.
* Allow Cloud Provider Admins to manage instance types via the `osac` CLI; the fulfillment service
  creates and manages the corresponding CRDs in Kubernetes.
* Expose hardware specifications (CPU, memory, accelerators, network) and a freeform `capabilities`
  map for display to Tenant Users via the BMaaS API.
* Support instance type lifecycle states — `Active`, `Deprecated`, `Obsolete` — with bidirectional
  transitions and deprecation metadata (replacement suggestion, timeline timestamps).
* Enable the fulfillment service to serve `ListBareMetalInstanceTypes` and
  `GetBareMetalInstanceType` by reading CRDs directly, with state-based filtering (Active and
  Deprecated by default; Obsolete on request).
* Enable the baremetal-fulfillment-operator to read the `BareMetalInstanceType` associated with a
  `BareMetalInstance` during reconciliation and use its fields to filter available hosts from the
  inventory backend in an inventory-client-specific manner.
* Validate that `BareMetalInstance` creation via BMaaS API references an Active or Deprecated
  instance type, with a warning returned for Deprecated types.
* Reject `BareMetalInstance` creation for Obsolete instance types.

### Non-Goals

The following are explicitly out of scope:

* Storage specifications as part of instance types.
* Organization-scoped or tenant-scoped instance types — all types are globally defined by Cloud
  Provider Admins in Phase 1.
* Quota enforcement based on instance types — deferred to the OSAC quota system.
* Pricing or metering metadata associated with instance types.
* Automatic state transitions (e.g., scheduled DEPRECATED -> OBSOLETE at a specified timestamp) --
  Cloud Provider Admin must perform transitions manually in Phase 1.
* Per-organization instance type restrictions (hiding specific types from specific tenants).
* Network bandwidth constraints or network performance tiers beyond the existing network port spec.
* Validation that a `BareMetalInstance`'s `hostType` references an existing `BareMetalInstanceType`
  at the Kubernetes API layer -- enforcement is at the BMaaS API boundary only, consistent with the
  VM instance types pattern.

## Proposal

This proposal introduces the `BareMetalInstanceType` CRD as the bridge between the bare metal
inventory backend and the OSAC BMaaS public API. Cloud Provider Admins create and manage instance
types via the `osac` CLI; the fulfillment service translates those operations into CRD creates,
updates, and deletes in Kubernetes. The baremetal-fulfillment-operator reads the CRD during
`BareMetalInstance` reconciliation to obtain structured hardware criteria and applies them as
inventory filters when querying for available hosts. The fulfillment service also reads these CRDs
to expose instance types to Tenant Users.

### Key Resources

**BareMetalInstanceType** -- provider-defined hardware type catalog entry
* Cluster-scoped (no namespace); globally visible to all tenants via the BMaaS API
* `metadata.name` is the canonical `hostType` identifier used by `BareMetalInstance` and
  `BareMetalPool`
* Created and managed by the fulfillment service on behalf of Cloud Provider Admin CLI operations
* Mutable: `displayName`, `description`, `state`, `hardware`, `capabilities`
* Immutable: `metadata.name` (the hostType key must never change to avoid breaking existing
  resource references)
* State lifecycle: `Active` <-> `Deprecated` <-> `Obsolete` (bidirectional transitions supported)
* Deprecation metadata: replacement suggestion and timeline timestamps on `Deprecated` or `Obsolete`
  transitions

**BareMetalInstance (existing, no API change)** -- tenant-provisioned bare metal server
* `spec.hostType` references a `BareMetalInstanceType` name; this field is already immutable
* No changes to CR schema -- validation is enforced at the BMaaS API boundary

**BareMetalPool (existing, no API change)** -- pool of bare metal hosts
* `spec.hostSets[].hostType` references `BareMetalInstanceType` names
* No changes to CR schema

### Scoping and Visibility

All `BareMetalInstanceType` resources in Phase 1 are globally scoped:
* **Created and managed by:** Cloud Provider Admin only, via the `osac` CLI (which calls the
  private BMaaS admin API; the fulfillment service creates and manages the CRD in Kubernetes)
* **Lifecycle states:**
  - **Active**: Fully available for new `BareMetalInstance` provisioning, no warnings
  - **Deprecated**: Available for provisioning with a warning returned in the API response;
    migration to the suggested replacement is recommended
  - **Obsolete**: Not available for new provisioning (rejected at API boundary); still visible for
    `Get` and `List` (with explicit filter) for historical reference

**BMaaS API behavior by state:**
* `ListBareMetalInstanceTypes`: Returns Active and Deprecated types by default; supports filter
  parameter to include Obsolete (e.g., `filter: "state IN (ACTIVE, DEPRECATED, OBSOLETE)"`)
* `GetBareMetalInstanceType`: Returns any type regardless of state
* `CreateBareMetalInstance`: Active succeeds; Deprecated succeeds with warning in
  `CreateBareMetalInstanceResponse.warnings`; Obsolete is rejected with 409 Conflict

### Naming and Uniqueness

* `BareMetalInstanceType` names are globally unique (enforced by Kubernetes cluster-scoped
  resource semantics)
* The name is the primary identifier; it is immutable after creation to prevent reference breakage
  in existing `BareMetalInstance` and `BareMetalPool` resources
* Names should be meaningful and descriptive (e.g., `gpu-a100-2x`, `hpc-icelake-96c`,
  `edge-arm-32c`) rather than opaque IDs

### Workflow Description

#### Instance Type Management (Cloud Provider Admin)

**Creating an Instance Type**

1. Cloud Provider Admin creates an instance type via the `osac` CLI:
   ```bash
   osac-admin create baremetal-instance-type hpc-icelake-96c \
     --display-name "HPC - Intel Icelake 96-core" \
     --description "High-performance compute node with 96 physical cores and 100 GbE" \
     --cpu-count 2 --cpu-cores 48 --cpu-threads 96 \
     --cpu-arch x86_64 --cpu-model "Intel Xeon Platinum 8362" \
     --memory-gib 512 \
     --network-speed-gbps 100 --network-count 2 \
     --capability rdma=true --capability hpc=true
   ```
2. The fulfillment service validates the request and creates the `BareMetalInstanceType` CRD in
   Kubernetes with `spec.state: Active`.
3. The instance type is immediately visible in `ListBareMetalInstanceTypes`.

**Deprecating an Instance Type**

1. Cloud Provider Admin marks an instance type as deprecated:
   ```bash
   osac-admin update baremetal-instance-type hpc-icelake-96c \
     --state Deprecated \
     --replacement hpc-sapphirerapids-128c \
     --obsolete-at 2027-03-31T23:59:59Z
   ```
2. The fulfillment service updates `spec.state: Deprecated` and records deprecation metadata on
   the CRD.
3. The fulfillment service begins returning a warning on `CreateBareMetalInstance` requests
   referencing this type: "Instance type 'hpc-icelake-96c' is deprecated and will become obsolete
   on 2027-03-31. Consider migrating to 'hpc-sapphirerapids-128c'."
4. Existing `BareMetalInstance` and `BareMetalPool` resources continue to operate unchanged.

**Obsoleting an Instance Type**

1. Cloud Provider Admin sets the type to Obsolete:
   ```bash
   osac-admin update baremetal-instance-type hpc-icelake-96c --state Obsolete
   ```
2. The fulfillment service updates `spec.state: Obsolete` on the CRD.
3. The instance type disappears from the default `ListBareMetalInstanceTypes` response for Tenant
   Users.
4. New `BareMetalInstance` provisioning requests referencing this type are rejected with 409
   Conflict.
   allocated hosts unless they are the obsoleted instance type, then they will get deleted.
5. Existing `BareMetalInstance` resources whose `spec.hostType` matches this instance type will
   be deleted by the operator.

**Reactivating an Instance Type**

1. Cloud Provider Admin restores the type:
   ```bash
   osac-admin update baremetal-instance-type hpc-icelake-96c --state Active
   ```
2. The fulfillment service updates `spec.state: Active` on the CRD.
3. The instance type becomes fully available again without warnings.
4. Deprecation metadata is retained for historical reference.

#### Tenant User Workflow

**Listing Available Instance Types**

1. Tenant User calls `ListBareMetalInstanceTypes`:
   ```bash
   osac get baremetalinstancetypes
   ```
2. The fulfillment service reads `BareMetalInstanceType` CRDs from the management cluster and
   returns Active and Deprecated types:
   ```json
   {
     "items": [
       {
         "name": "hpc-icelake-96c",
         "display_name": "HPC - Intel Icelake 96-core",
         "description": "High-performance compute node with 96 physical cores and 100 GbE",
         "state": "ACTIVE",
         "hardware": {
           "cpu": {
             "count": 2, "cores": 48, "threads": 96,
             "architecture": "x86_64", "model": "Intel Xeon Platinum 8362", "speed_ghz": "2.8"
           },
           "memory": { "size_gib": 512 },
           "network": [{ "speed_gbps": 100, "count": 2 }]
         },
         "capabilities": { "rdma": "true", "hpc": "true" }
       },
       {
         "name": "hpc-skylake-48c",
         "display_name": "HPC - Intel Skylake 48-core (deprecated)",
         "state": "DEPRECATED",
         "hardware": { "cpu": { "cores": 48 }, "memory": { "size_gib": 256 } },
         "deprecation": {
           "replacement": "hpc-icelake-96c",
           "deprecated": "2026-06-01T00:00:00Z",
           "obsolete": "2027-03-31T23:59:59Z"
         }
       }
     ]
   }
   ```

**Error Cases**

**Obsolete instance type:**
```
Error: bare metal instance type "hpc-skylake-32c" is obsolete and cannot be used for new provisioning
```

**Non-existent instance type:**
```
Error: bare metal instance type "nonexistent" not found
```

### API Extensions

#### New Resources

**BareMetalInstanceType** (`proto/public/osac/public/v1/baremetal_instance_type_type.proto`)
- Public API: Read-only `List` and `Get` operations for Tenant Users
- Private API: Full CRUD operations for Cloud Provider Admins (via `osac` CLI)

**BareMetalInstanceTypes Service**
(`proto/public/osac/public/v1/baremetal_instance_types_service.proto`)
- Public API: `ListBareMetalInstanceTypes`, `GetBareMetalInstanceType`
- Private API: `ListBareMetalInstanceTypes`, `GetBareMetalInstanceType`,
  `CreateBareMetalInstanceType`, `UpdateBareMetalInstanceType`, `DeleteBareMetalInstanceType`

#### Validation

**Public API (Tenant Users):**
- `CreateBareMetalInstance`: Require `instance_type` field (string matching a
  `BareMetalInstanceType` name)
- `CreateBareMetalInstance`: Validate `spec.state` is `Active` or `Deprecated`; reject `Obsolete`
  with 409 Conflict
- `CreateBareMetalInstance`: If `Deprecated`, include deprecation warning in
  `CreateBareMetalInstanceResponse.warnings`
- `CreateBareMetalInstance`: If name not found, reject with 404 Not Found
- `UpdateBareMetalInstance`: Reject changes to `instance_type` field (immutable, consistent with
  `spec.hostType` immutability in the CR)

**Private API (Cloud Provider Admin):**
- `CreateBareMetalInstanceType`: Require `name` and `display_name`; default `state` to `Active`
- `UpdateBareMetalInstanceType`: Reject changes to `name` (immutable)
- `UpdateBareMetalInstanceType`: Allow changes to `display_name`, `description`, `state`,
  `hardware`, `capabilities`, and deprecation metadata
- `UpdateBareMetalInstanceType`: State transitions are bidirectional (e.g., `Obsolete` -> `Active`
  is permitted)
- `UpdateBareMetalInstanceType`: When transitioning to `Deprecated`, auto-populate
  `deprecation.deprecated` timestamp if not provided
- `UpdateBareMetalInstanceType`: When transitioning to `Obsolete`, auto-populate
  `deprecation.obsolete` timestamp if not provided
- `DeleteBareMetalInstanceType`: Reject if any `BareMetalInstance` or `BareMetalPool` resources
  reference this `hostType` value

#### Deletion Protection

`BareMetalInstanceType` deletion is blocked if any `BareMetalInstance` CRs have `spec.hostType`
matching the resource name. The fulfillment service checks for live references before deleting the
CRD from Kubernetes:
- Query `BareMetalInstance` and `BareMetalPool` resources in the management cluster by
  `spec.hostType`
- If any exist: reject with 409 Conflict -- "Cannot delete bare metal instance type
  'hpc-icelake-96c': referenced by N active BareMetalInstance(s)"
- If none exist: deletion proceeds; the fulfillment service deletes the `BareMetalInstanceType` CRD

#### Proto Definition Sketch

```proto
// proto/public/osac/public/v1/baremetal_instance_type_type.proto

enum BareMetalInstanceTypeState {
  INSTANCE_TYPE_STATE_UNSPECIFIED = 0;
  ACTIVE = 1;       // Fully available for new BareMetalInstance provisioning
  DEPRECATED = 2;   // Available with warnings, migration recommended
  OBSOLETE = 3;     // Not available for new provisioning, visible for lookups only
}

message BareMetalCPUSpec {
  int32 count = 1;            // Number of physical CPU sockets
  int32 cores = 2;            // Physical cores per socket
  int32 threads = 3;          // Total logical CPUs (hyperthreads) across all sockets
  string architecture = 4;    // CPU ISA (e.g. "x86_64", "aarch64")
  string model = 5;           // CPU model string (e.g. "Intel Xeon Platinum 8362")
  string speed_ghz = 6;       // Base clock speed in GHz
}

message BareMetalMemorySpec {
  int64 size_gib = 1;         // Total system RAM in gibibytes
}

message BareMetalAcceleratorSpec {
  enum Type {
    GPU = 0;
  }
  Type type = 1;              // Class of accelerator (currently GPU only)
  string model = 2;           // Model string (e.g. "NVIDIA A100 80GB")
  int32 count = 3;            // Number of devices of this model
  int32 memory_gib = 4;       // Optional: memory per device in gibibytes
  string interconnect = 5;    // Optional: interconnect fabric (e.g. "NVLink4", "PCIe")
}

message BareMetalNetworkPortSpec {
  int32 speed_gbps = 1;       // Port line speed in gigabits per second
  int32 count = 2;            // Number of ports at this speed
}

message BareMetalHardwareSpec {
  BareMetalCPUSpec cpu = 1;
  BareMetalMemorySpec memory = 2;
  repeated BareMetalAcceleratorSpec accelerators = 3;
  repeated BareMetalNetworkPortSpec network = 4;
}

message BareMetalInstanceTypeDeprecation {
  BareMetalInstanceTypeState state = 1;     // DEPRECATED or OBSOLETE (mirrors parent state)
  string replacement = 2;                   // Optional: suggested replacement instance type name
  google.protobuf.Timestamp deprecated = 3; // When deprecation was announced (auto-set on transition)
  google.protobuf.Timestamp obsolete = 4;   // When it becomes/became obsolete (auto-set on transition)
}

message BareMetalInstanceType {
  string name = 1;                          // Primary identifier (matches CRD metadata.name)
  Metadata metadata = 2;
  string display_name = 3;                  // Human-readable name for BMaaS API display
  string description = 4;                   // Optional description for users
  BareMetalInstanceTypeState state = 5;
  BareMetalHardwareSpec hardware = 6;
  map<string, string> capabilities = 7;     // Freeform hardware features (e.g. "rdma": "true")
  BareMetalInstanceTypeDeprecation deprecation = 8; // Only set when DEPRECATED or OBSOLETE
}

// proto/public/osac/public/v1/baremetal_instance_types_service.proto
service BareMetalInstanceTypes {
  rpc List(ListBareMetalInstanceTypesRequest) returns (ListBareMetalInstanceTypesResponse) {
    option (google.api.http) = {
      get: "/api/fulfillment/v1/baremetal_instance_types"
    };
  }
  rpc Get(GetBareMetalInstanceTypeRequest) returns (BareMetalInstanceType) {
    option (google.api.http) = {
      get: "/api/fulfillment/v1/baremetal_instance_types/{name}"
    };
  }
}

// proto/private/osac/private/v1/baremetal_instance_types_service.proto
service BareMetalInstanceTypes {
  rpc Create(CreateBareMetalInstanceTypeRequest) returns (BareMetalInstanceType);
  rpc Update(UpdateBareMetalInstanceTypeRequest) returns (BareMetalInstanceType);
  rpc Delete(DeleteBareMetalInstanceTypeRequest) returns (google.protobuf.Empty);
  rpc List(ListBareMetalInstanceTypesRequest) returns (ListBareMetalInstanceTypesResponse);
  rpc Get(GetBareMetalInstanceTypeRequest) returns (BareMetalInstanceType);
}

message GetBareMetalInstanceTypeRequest {
  string name = 1;
}

message DeleteBareMetalInstanceTypeRequest {
  string name = 1;
}

// CreateBareMetalInstanceResponse (modified)
message CreateBareMetalInstanceResponse {
  BareMetalInstance bare_metal_instance = 1;
  repeated string warnings = 2;  // Deprecation warnings for Deprecated instance types
}
```

### Implementation Details/Notes/Constraints

#### CRD as Source of Truth

Unlike VMaaS instance types (which are stored in the fulfillment service database),
`BareMetalInstanceType` resources live exclusively as Kubernetes CRDs in the management cluster.
The fulfillment service owns the full lifecycle of these CRDs -- creating them on admin `Create`
calls, patching them on `Update`, and deleting them on `Delete` -- rather than writing to a
separate database table. This design provides:

- **No database table required:** All state lives in the CRD; the fulfillment service uses its
  existing Kubernetes client for all CRUD operations.
- **Direct operator integration:** The baremetal-fulfillment-operator reads `BareMetalInstanceType`
  CRDs natively during `BareMetalInstance` reconciliation with no additional API calls to the
  fulfillment-service.
- **Auditability:** CRD creates, updates, and deletes are captured in the Kubernetes audit log.
- **GitOps-compatible:** The CRD state is inspectable and diffable via standard Kubernetes tooling.

#### Kubernetes CRD Schema

The `BareMetalInstanceType` CRD is defined in the baremetal-fulfillment-operator:

```yaml
# Example BareMetalInstanceType CR
apiVersion: osac.openshift.io/v1alpha1
kind: BareMetalInstanceType
metadata:
  name: gpu-a100-2x          # hostType key; immutable
spec:
  displayName: "GPU - NVIDIA A100 2x"
  description: "GPU-accelerated node with 2x NVIDIA A100 80GB"
  state: Active
  hardware:
    cpu:
      count: 2
      cores: 32
      threads: 128
      architecture: x86_64
      model: "AMD EPYC 7543"
      speedGHz: "2.8"
    memory:
      sizeGiB: 1024
    accelerators:
      - type: GPU
        model: "NVIDIA A100 80GB"
        count: 2
        memoryGiB: 80
        interconnect: "NVLink4"
    network:
      - speedGbps: 200
        count: 2
  capabilities:
    rdma: "true"
status:
  phase: Available
  availableCount: 4
  totalCount: 8
  conditions:
    - type: HostsAvailable
      status: "True"
      reason: HostsAvailable
      lastTransitionTime: "2026-06-15T12:00:00Z"
```

**`oc get bmit` output:**
```
NAME             PHASE       AVAILABLE   TOTAL   STATE      DISPLAYNAME              AGE
gpu-a100-2x      Available   4           8       Active     GPU - NVIDIA A100 2x     5d
hpc-icelake-96c  Available   12          20      Active     HPC - Intel Icelake 96c  12d
hpc-skylake-48c  Unavailable 0           8       Deprecated HPC - Intel Skylake 48c  45d
```

#### BareMetalInstance Reconciler Integration

The bare-metal-fulfillment-operator's existing `BareMetalInstance` reconciler is extended to read
the associated `BareMetalInstanceType` during host allocation. The flow is:

1. Reconciler receives a `BareMetalInstance` with `spec.hostType` set (e.g. `gpu-a100-2x`).
2. Reconciler fetches the `BareMetalInstanceType` CRD named `gpu-a100-2x` from the cluster. If
   the CRD does not exist, the reconciler sets an error condition on the `BareMetalInstance` and
   requeues.
3. Reconciler passes the `BareMetalInstanceType`'s `spec.hardware` and `spec.capabilities` fields
   to the inventory client as filter criteria when querying for available hosts. The exact mapping
   from hardware fields to inventory query parameters is inventory-client-specific and defined by
   the pluggable inventory interface implementation.
4. The inventory client returns a list of hosts matching the criteria; the reconciler selects and
   allocates one.

The `BareMetalInstanceType`'s status is written to by the reconciler to update the amount of hosts
the backend contains.

#### Fulfillment Service Integration

The fulfillment service manages `BareMetalInstanceType` CRDs via the same Kubernetes client it
uses for other cluster resources. No new database table is required.

**`ListBareMetalInstanceTypes` flow:**
1. fulfillment-service calls `List` on `BareMetalInstanceType` CRDs (cluster-scoped).
2. Filters by `spec.state` per the request filter (default: exclude Obsolete).
3. Maps each CRD to a `BareMetalInstanceType` proto message.
4. Returns the filtered list to the caller.

**`CreateBareMetalInstanceType` flow (admin):**
1. fulfillment-service validates the request (unique name, required fields).
2. fulfillment-service creates a `BareMetalInstanceType` CRD in Kubernetes.
3. Returns the created resource to the caller.

**`CreateBareMetalInstance` flow (instance type validation):**
1. Tenant User specifies `instance_type: "gpu-a100-2x"` in the request.
2. fulfillment-service reads the `BareMetalInstanceType` CRD named `gpu-a100-2x`.
3. If not found: return 404 Not Found.
4. If `spec.state == Obsolete`: return 409 Conflict.
5. If `spec.state == Deprecated`: add deprecation warning to response; proceed.
6. Creates `BareMetalInstance` CR with `spec.hostType: gpu-a100-2x`.
7. Returns `CreateBareMetalInstanceResponse` with optional `warnings`.

### Risks and Mitigations

**Risk: Fulfillment service requires write access to `BareMetalInstanceType` CRDs**
- Mitigation: The fulfillment service already uses the Kubernetes API client for other resources;
  adding write RBAC for `baremetalinstancetypes` is consistent with the existing pattern.
- Mitigation: Write access is scoped to the `baremetalinstancetypes` resource only; no broader
  cluster permissions are required.

**Risk: `BareMetalInstanceType` CRD not found during `BareMetalInstance` reconciliation**
- Mitigation: The reconciler sets an error condition on the `BareMetalInstance` and requeues. The
  condition message directs the operator to verify the `BareMetalInstanceType` exists.
- Mitigation: The fulfillment service validates `instance_type` at the API boundary, so a missing
  CRD indicates an out-of-band deletion -- the operator's error surface handles this case.

**Risk: Deleting a `BareMetalInstanceType` while `BareMetalPool` resources reference it**
- Mitigation: The deletion protection check scans both `BareMetalPool.spec.hostSets[].hostType`
  and `BareMetalInstance.spec.hostType` references.
- Mitigation: Cloud Provider Admin should set `state: Obsolete` and wait for all references to be
  removed before deleting.

**Risk: `BareMetalInstanceType` name reuse after deletion**
- Mitigation: Kubernetes does not prevent name reuse after deletion (unlike the DB soft-delete
  pattern used for VMaaS instance types). Cloud Provider Admins must treat deleted type names as
  permanently retired. Document this operational constraint.

### Drawbacks

**Inventory filter semantics are inventory-client-specific**
- The mapping from `BareMetalInstanceType` hardware fields to inventory query parameters is defined
  per inventory implementation, not enforced by the CRD schema.
- Trade-off: Flexibility to support heterogeneous inventory backends vs. less predictable filtering
  behavior across installations.

**Fulfillment service requires write access to `BareMetalInstanceType` CRDs**
- The fulfillment service's RBAC must grant `create`, `update`, `patch`, and `delete` on
  `baremetalinstancetypes`, not just `get` and `list`.
- Trade-off: Broader RBAC scope for the fulfillment service vs. avoiding a database table and a
  separate admin path.

## Alternatives (Not Implemented)

**Alternative 1: Store instance types in the fulfillment service database (VMaaS pattern)**
- Mirrors the VMaaS instance types design: DB table, no CRD.
- Rejected: The baremetal-fulfillment-operator reads the CRD directly during reconciliation;
  storing types in the DB would require the operator to call the fulfillment service API, adding a
  cross-service dependency to the hot reconciliation path.
- Rejected: CRD-native approach integrates directly with the operator's Kubernetes client.

**Alternative 2: Keep `hostType` as an opaque string with no structured resource**
- Simplest approach: no new CRD.
- Rejected: No mechanism to expose type metadata (hardware specs, capabilities) to Tenant Users
  via BMaaS API.
- Rejected: No lifecycle state management; retiring a type requires out-of-band coordination.
- Rejected: No structured fields for the operator to use as inventory filter criteria.

**Alternative 4: Source instance types from a ConfigMap or annotation convention**
- Cloud Provider Admins annotate or label hosts; a controller derives types from host metadata.
- Rejected: ConfigMaps are not strongly typed; no validation or lifecycle management.
- Rejected: Deriving types from host annotations is brittle and hard to manage at scale.

## Test Plan

**Unit Tests:**
- `BareMetalInstanceType` CRD validation (required fields, enum constraints, immutable name)
- `ListBareMetalInstanceTypes`: default filter excludes Obsolete; explicit filter includes it
- `GetBareMetalInstanceType`: returns type regardless of state
- `CreateBareMetalInstance` rejects Obsolete instance type with 409 Conflict
- `CreateBareMetalInstance` with Deprecated type succeeds and populates `warnings`
- `CreateBareMetalInstance` with non-existent type returns 404 Not Found
- `UpdateBareMetalInstanceType` rejects name changes
- `UpdateBareMetalInstanceType` allows `state`, `displayName`, `description`, `hardware`,
  `capabilities`, and deprecation metadata changes
- State transitions (Active <-> Deprecated <-> Obsolete, including reactivation)
- Deprecation timestamp auto-population on `Deprecated` transition
- Obsolete timestamp auto-population on `Obsolete` transition
- `DeleteBareMetalInstanceType` rejected when `BareMetalInstance` resources reference the type
- `DeleteBareMetalInstanceType` rejected when `BareMetalPool` resources reference the type
- `BareMetalInstance` reconciler: fetches `BareMetalInstanceType` and passes `spec.hardware` and
  `spec.capabilities` to the inventory client as filter criteria
- `BareMetalInstance` reconciler: sets error condition and requeues when `BareMetalInstanceType`
  CRD is not found

**Integration Tests:**
- Admin creates `BareMetalInstanceType` via CLI; verify CRD appears in cluster and in
  `ListBareMetalInstanceTypes` response
- `GetBareMetalInstanceType` returns hardware specs
- Provision `BareMetalInstance` referencing Active type: succeeds, no warnings
- Provision `BareMetalInstance` referencing Deprecated type: succeeds, warning in response
- Provision `BareMetalInstance` referencing Obsolete type: rejected with 409 Conflict
- Set type to Deprecated; verify it appears in list with deprecation metadata
- Set type to Obsolete; verify it disappears from default `ListBareMetalInstanceTypes` response
- Verify `GetBareMetalInstanceType` still returns Obsolete type for admin inspection
- Attempt to delete type with active `BareMetalInstance` references: rejected
- Deprovision all `BareMetalInstance` resources, then delete type: CRD removed from cluster
- Reactivate Deprecated type: returns to Active, no warnings on new provisioning
- `BareMetalInstance` reconciler fetches `BareMetalInstanceType` by `spec.hostType` and passes
  `spec.hardware` and `spec.capabilities` to the inventory client as filter criteria; verify
  via operator debug logs that filter parameters match the BMIT fields
- Hardware filter chain: provision `BareMetalInstance` with a GPU type; verify the allocated
  host has accelerators matching `spec.hardware.accelerators` from the `BareMetalInstanceType`
- Hardware filter chain: `BareMetalInstanceType` not found during reconcile sets an error
  condition on `BareMetalInstance` and requeues without allocating a host

**End-to-End Tests:**
- Cloud Provider Admin creates `BareMetalInstanceType` via `osac` CLI
- Tenant User lists instance types and sees the new type with hardware specs
- Tenant User provisions `BareMetalInstance` selecting the new type
- baremetal-fulfillment-operator reads BMIT, applies hardware filters to inventory query, allocates
  a matching host, and provisions it
- `BareMetalInstance` reaches Ready state
- Cloud Provider Admin sets type to Deprecated with replacement and future obsolete timestamp
- Tenant User lists instance types and sees Deprecated status with deprecation metadata
- Tenant User creates new `BareMetalInstance` with Deprecated type, receives warning with
  replacement suggestion
- Cloud Provider Admin sets type to Obsolete
- Tenant User no longer sees type in default list
- Attempt to create `BareMetalInstance` with Obsolete type fails with 409 Conflict
- Existing `BareMetalInstance` resources continue running unchanged

## Graduation Criteria

This enhancement is not targeting a specific OSAC release at this time. When targeting a release,
graduation criteria will be defined based on production deployment feedback and Cloud Provider Admin
validation.

Expected maturity progression:
- **Dev Preview:** `BareMetalInstanceType` CRD with basic BMaaS API (List/Get for Tenant Users,
  CRUD for admins) and operator integration for inventory filtering
- **Tech Preview:** State lifecycle management, deprecation metadata, warning propagation to tenants
- **GA:** Full production deployment with documented operational runbook for type lifecycle
  management

Success signals for graduation:
- Operator inventory filtering via BMIT hardware fields working correctly at 2+ pilot sites
- Cloud Provider Admins successfully manage type lifecycle via `osac` CLI without cluster access
- Tenant Users report clear hardware differentiation for workload selection
- Zero incidents from missing or stale `BareMetalInstanceType` references breaking provisioning

## Upgrade/Downgrade Strategy

Not applicable -- OSAC is pre-GA. Components should be upgraded together.

## Version Skew Strategy

Not applicable -- OSAC is pre-GA.

## Support Procedures

### Operational Impact of API Extensions

**New CRD:**
- `BareMetalInstanceType` (cluster-scoped, lifecycle managed by fulfillment service)
- Requires `ClusterRole` granting the fulfillment service `get`, `list`, `watch`, `create`,
  `update`, `patch`, and `delete` on `baremetalinstancetypes`
- Requires `ClusterRole` granting the baremetal-fulfillment-operator `get` and `list` on
  `baremetalinstancetypes` (read-only; the operator does not mutate these resources)

**New API resources:**
- `BareMetalInstanceTypes` service (public + private) in fulfillment-service

**Failure Modes and Troubleshooting:**

**`ListBareMetalInstanceTypes` returns empty list**
- **Detection:** API returns empty `items`; `oc get bmit` in management cluster shows resources
  exist
- **Diagnosis:** fulfillment-service RBAC may not permit reading `baremetalinstancetypes` resources
- **Resolution:** Verify fulfillment-service `ClusterRole` includes `baremetalinstancetypes` in
  `get`/`list` verbs

**`CreateBareMetalInstanceType` fails with permission error**
- **Detection:** Admin CLI returns a permission-denied error
- **Diagnosis:** fulfillment-service `ClusterRole` does not include write verbs on
  `baremetalinstancetypes`
- **Resolution:** Update the fulfillment-service `ClusterRole` to include `create`, `update`,
  `patch`, and `delete` on `baremetalinstancetypes`

**`BareMetalInstance` stuck with error condition: "BareMetalInstanceType not found"**
- **Detection:** `oc get bmi <name> -o yaml` shows an error condition referencing a missing BMIT
- **Diagnosis:** The `BareMetalInstanceType` CRD referenced by `spec.hostType` was deleted or
  never created in the cluster
- **Resolution:** Recreate the `BareMetalInstanceType` via the admin CLI, or delete the
  `BareMetalInstance` if the instance type is no longer available

**`CreateBareMetalInstance` returns 409 for a type that appears Active in list**
- **Detection:** List shows Active type; provisioning rejected with "is obsolete"
- **Diagnosis:** Stale cache in fulfillment service; CRD was updated to Obsolete between list and
  create
- **Resolution:** Re-list instance types; if type is genuinely Active, retry after cache TTL expires

**`BareMetalInstanceType` cannot be deleted: "referenced by active resources"**
- **Detection:** `osac-admin delete baremetal-instance-type` returns a 409 Conflict error
- **Diagnosis:** One or more `BareMetalInstance` or `BareMetalPool` resources reference this
  `hostType`
- **Resolution:** List referencing resources:
  `oc get bmi --all-namespaces -o jsonpath='{.items[?(@.spec.hostType=="<name>")].metadata.name}'`;
  deprovision or delete them before retrying

**`BareMetalInstance` allocated to host that does not match expected hardware**
- **Detection:** Provisioned host does not meet the CPU, memory, accelerator, or network specs
  defined in the `BareMetalInstanceType`
- **Diagnosis:** The inventory client's hardware filter mapping may not correctly translate
  `BareMetalInstanceType.spec.hardware` fields to backend query parameters; mapping is
  inventory-client-specific (see pluggable inventory interface implementation)
- **Resolution:** Enable debug logging on the baremetal-fulfillment-operator to inspect which
  filter parameters are passed to the inventory client; compare against the inventory client's
  filter documentation; verify that `spec.hardware` and `spec.capabilities` values in the
  `BareMetalInstanceType` CR use the field values and formats the inventory backend recognizes

### Disabling / Rollback

Not supported.

## Infrastructure Needed

No additional infrastructure is required.
