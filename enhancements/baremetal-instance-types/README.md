---
title: bare-metal-instance-types
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

This enhancement introduces `BareMetalInstanceType` as a discoverable list of bare metal hardware
types automatically derived from the inventory backend. Each `BareMetalInstanceType` corresponds
to a unique `hostType` value found in the inventory, providing structured hardware specifications
for the OSAC BMaaS public API. The bare-metal-fulfillment-operator automatically discovers distinct
host types from the inventory, samples representative hosts to extract hardware characteristics,
and creates/updates corresponding fulfillment service resources. Cloud Provider Admins can overlay
lifecycle states (ACTIVE/DEPRECATED/OBSOLETE), display names, and descriptions via configuration,
while hardware specifications and inventory count remain auto-synchronized on a recurring interval.
This approach eliminates manual catalog maintenance and ensures specifications always match actual
available hardware.

## Motivation

Currently, `hostType` in `BareMetalInstance.spec.hostType` and
`BareMetalPool.spec.hostSets[].hostType` is an opaque string corresponding to inventory backend
classifications. There is no structured resource that:

- Documents what hardware a given type provides (CPUs, memory, storage, accelerators,
  network ports)
- Automatically discovers available types from the inventory to ensure consistency
- Manages the type's lifecycle (ACTIVE, DEPRECATED, OBSOLETE) with administrative permissions
- Exposes the type list to the BMaaS API layer for tenant self-service
- Handles host subcategorization/filtering when the same host type has different availability
  characteristics

Without this, there is no way for Tenant Users to choose what hardware they want from the BMaaS
API, and there is no automated way to maintain consistent info presented as the inventory changes.

### User Stories

* As a **Cloud Provider Admin**, I want to define and expose available bare metal instance types
  so that the OSAC BMaaS API can present them to Tenant Users for self-service provisioning.
* As a **Cloud Provider Admin**, I don't want to have to annotate each instance type with CPU,
  memory, and network specifications. The list of `BareMetalInstanceTypes` should automatically
  update as new hardware gets installed or old hardware gets removed.
* As a **Cloud Provider Admin**, I want to manage instance type lifecycle states (ACTIVE /
  DEPRECATED / OBSOLETE) so that I can retire aging hardware classes gracefully without deleting the
  definitions or breaking existing `BareMetalInstance` records.
* As a **Cloud Provider Admin**, I want to provide a replacement suggestion and timeline when
  deprecating an instance type so that Tenant Users have clear guidance on how to migrate workloads.
* As a **Tenant User**, I want to list available bare metal instance types with hardware
  specifications so that I can choose the right type for my workload.
* As a **Tenant User**, I want to provision a `BareMetalInstance` by selecting an instance type
  name so that I do not need to know the underlying inventory implementation.
* As a **Tenant User**, I want to be warned when I select a deprecated instance type so that I can
  plan a migration to the recommended replacement.

### Goals

* Provide auto-discovered `BareMetalInstanceType` resources by querying inventory for distinct
  `hostType` values and extracting hardware specifications from representative hosts.
* Enable the bare-metal-fulfillment-operator to automatically maintain accurate hardware
  specifications by periodically sampling inventory hosts per type.
* Allow Cloud Provider Admins to overlay lifecycle states (`ACTIVE`, `DEPRECATED`, `OBSOLETE`),
  display names, and descriptions via configuration while hardware specs remain auto-synchronized.
* Separate instance types in the frontend for hosts with different `managed_by` fields
  while maintaining the core hostType-based identity model.
* Expose hardware specifications (CPU, memory, accelerators, network, local storage)
  and a freeform `capabilities` for display to Tenant Users via the BMaaS API.
* Enable the fulfillment service to serve `ListBareMetalInstanceTypes` and
  `GetBareMetalInstanceType` by reading CRDs directly, with state-based filtering.
* Validate that `BareMetalInstance` creation via BMaaS API references an ACTIVE or DEPRECATED
  instance type, with a warning returned for DEPRECATED types.
* Reject `BareMetalInstance` creation for OBSOLETE instance types.

### Non-Goals

The following are explicitly out of scope:

* Organization-scoped or tenant-scoped instance types — all types are globally defined by Cloud
  Provider Admins
* Quota enforcement based on instance types — deferred to the OSAC quota system.
* Pricing or metering metadata associated with instance types.
* Automatic state transitions (e.g., scheduled DEPRECATED -> OBSOLETE at a specified timestamp) --
  Cloud Provider Admin must perform transitions manually
* Per-organization instance type restrictions (hiding specific types from specific tenants).
* Manual catalog management -- instance types are auto-discovered from inventory, eliminating
  the need for manual hardware specification maintenance.

## Proposal

This proposal introduces the `BareMetalInstanceType` resource as an auto-discovered list of bare
metal hardware types derived directly from the inventory backend. The bare-metal-fulfillment-operator
periodically queries the inventory for distinct `hostType` values, obtains representative hosts
to extract hardware characteristics, and creates/updates corresponding fulfillment service
resources. Cloud Provider Admins can overlay administrative metadata (lifecycle states, descriptions)
via osac cli configuration, while hardware specifications remain automatically synchronized from
inventory. This approach ensures accuracy and eliminates manual synchronization overhead.

### Key Resources

**BareMetalInstanceType** -- auto-discovered hardware type catalog entry
* Globally scoped, visible to all organizations
* `metadata.name` is the canonical `hostType` identifier used by `BareMetalInstance` and `BareMetalPool`
* Auto-created and updated by the bare-metal-fulfillment-operator via inventory discovery
* Administrative overlay via osac cli for lifecycle states and descriptions
* Auto-synchronized: `hardware` specifications extracted from inventory host
* Mutable via admin config: `description`, `state`, deprecation metadata
* Immutable: `metadata.name`, `spec.hardware`
* State lifecycle: `ACTIVE` <-> `DEPRECATED` <-> `OBSOLETE` (bidirectional transitions supported)
* Frontend separation: hosts with different `managed_by` fields are presented as separate instance types

**BareMetalInstance (existing, no API change)** -- tenant-provisioned bare metal server
* `spec.hostType` references `BareMetalInstanceType` names
* No changes to CR schema

**BareMetalPool (existing, no API change)** -- pool of bare metal hosts
* `spec.hostSets[].hostType` references `BareMetalInstanceType` names
* No changes to CR schema

### Scoping and Visibility

All `BareMetalInstanceType` resources in Phase 1 are globally scoped:
* **Auto-discovered by:** bare-metal-fulfillment-operator via inventory queries
* **Administratively controlled by:** Cloud Provider Admin via osac cli configuration
* **Lifecycle states (detailed definitions):**
  - **ACTIVE**: Fully available for new `BareMetalInstance` provisioning
    - API behavior: Creation succeeds without warnings
    - Operator behavior: Normal host allocation and provisioning
    - Display: Shown in default `ListBareMetalInstanceTypes` results
  - **DEPRECATED**: Available for provisioning with migration recommendations
    - API behavior: Creation succeeds with warning in response (includes replacement suggestion and obsolete timeline)
    - Operator behavior: Normal host allocation and provisioning
    - Display: Shown in default lists with deprecation metadata
    - Purpose: Signal planned retirement while maintaining backwards compatibility
  - **OBSOLETE**: Not available for new provisioning, preserved for reference
    - API behavior: Creation rejected with 409 Conflict error
    - Operator behavior: Existing `BareMetalInstance` resources continue unchanged, no impact on running workloads
    - Display: Hidden from default lists, available via explicit filter (`state IN (ACTIVE, DEPRECATED, OBSOLETE)`)
    - Purpose: Block new usage while preserving historical records and existing deployments

**BMaaS API behavior by state:**
* `ListBareMetalInstanceTypes`: Returns ACTIVE and DEPRECATED types by default; supports filter
  parameter to include OBSOLETE (e.g., `filter: "state IN (ACTIVE, DEPRECATED, OBSOLETE)"`)
* `GetBareMetalInstanceType`: Returns any type regardless of state
* `CreateBareMetalInstance`: ACTIVE succeeds; DEPRECATED succeeds with warning in
  `CreateBareMetalInstanceResponse.warnings`; OBSOLETE is rejected with 409 Conflict

### Naming and Uniqueness

* `BareMetalInstanceType` names are globally unique
* The name is the primary identifier; it is immutable after creation to prevent reference breakage
  in existing `BareMetalInstance` and `BareMetalPool` resources
* Names should be meaningful and descriptive (e.g., `gpu-a100-2x`, `hpc-icelake-96c`,
  `edge-arm-32c`) rather than opaque IDs
* Database uses `name` as the primary key
* Hosts with same hostType but different `managed_by` fields are presented as separate instance types in the frontend

### Workflow Description

#### Instance Type Management (Cloud Provider Admin)

**Auto-Discovery Process**

1. The bare-metal-fulfillment-operator periodically queries the inventory backend for distinct `hostType` values.
2. For each `hostType`, the operator samples one representative host to extract hardware characteristics:
   - CPU specifications (count, cores, threads, architecture, model, speed)
   - Memory size
   - Accelerators (type, model, count, memory, interconnect)
   - Storage capacity
   - Network interfaces (speed, count, identifiers)
   - Capabilities derived from inventory metadata
3. The operator creates or updates the corresponding `BareMetalInstanceType` resource in the fulfillment database with auto-discovered hardware specifications.
4. Inventory count is automatically kept synchronized as inventory changes.

**Deprecating an Instance Type**

1. Cloud Provider Admin sets the type to deprecated:

   ```bash
   osac-admin update baremetalinstancetype fc430 --state deprecated
   ```

2. The fulfillment service updates `state: DEPRECATED` in the database.
3. The instance type still appears from the default `ListBareMetalInstanceTypes` response for Tenant
   Users.
4. The fulfillment service begins returning a warning on `CreateBareMetalInstance` requests.
5. Existing `BareMetalInstance` and `BareMetalPool` resources continue to operate unchanged.

**Obsoleting an Instance Type**

1. Cloud Provider Admin sets the type to Obsolete:

   ```bash
   osac-admin update baremetalinstancetype fc430 --state obsolete
   ```

2. The fulfillment service updates `state: OBSOLETE` in the database.
3. The instance type disappears from the default `ListBareMetalInstanceTypes` response for Tenant
   Users.
4. New `BareMetalInstance` provisioning requests referencing this type are rejected with 409
   Conflict.
5. **Existing `BareMetalInstance` resources whose `spec.hostType` matches this instance type continue
   to operate unchanged.** The OBSOLETE state only prevents new provisioning; it does not affect
   existing resources.

**Reactivating an Instance Type**

1. Cloud Provider Admin restores the type:

   ```bash
   osac-admin update baremetalinstancetype fc430 --state active
   ```

2. The fulfillment service updates `state: ACTIVE` in the database.
3. The instance type becomes fully available again without warnings.
4. Deprecation metadata is retained for historical reference.

#### Tenant User Workflow

**Listing Available Instance Types**

1. Tenant User calls `ListBareMetalInstanceTypes`:

   ```bash
   osac get baremetalinstancetypes
   ```

2. The fulfillment service queries `BareMetalInstanceType` records from the database and
   returns ACTIVE and DEPRECATED types:
   ```json
   {
     "items": [
       {
         "name": "fc430",
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
         "name": "fc830",
         "description": "High-performance compute node with 2x96 physical cores and 100 GbE",
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

```bash
$ osac create baremetal-instance my-bm --instance-type obsolete-instance
Error: bare metal instance type "obsolete-instance" is obsolete and cannot be used for new provisioning
```

**Non-existent instance type:**

```bash
$ osac create baremetal-instance my-bm --instance-type nonexistent
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
- `CreateBareMetalInstance`: Validate `spec.state` is `ACTIVE` or `DEPRECATED`; reject `OBSOLETE`
  with 409 Conflict
- `CreateBareMetalInstance`: If `DEPRECATED`, include deprecation warning in
  `CreateBareMetalInstanceResponse.warnings`
- `CreateBareMetalInstance`: If name not found, reject with 404 Not Found
- `UpdateBareMetalInstance`: Reject changes to `instance_type` field (immutable, consistent with
  `spec.hostType` immutability in the CR)

**Private API (Cloud Provider Admin):**
- `CreateBareMetalInstanceType`: Require `name` and `display_name`; default `state` to `ACTIVE`
- `UpdateBareMetalInstanceType`: Reject changes to `name` (immutable)
- `UpdateBareMetalInstanceType`: Allow changes to `description`, `state`,
  `hardware`, `capabilities`, and deprecation metadata
- `UpdateBareMetalInstanceType`: State transitions are bidirectional (e.g., `OBSOLETE` -> `ACTIVE`
  is permitted)
- `UpdateBareMetalInstanceType`: When transitioning to `DEPRECATED`, auto-populate
  `deprecation.deprecated` timestamp if not provided
- `UpdateBareMetalInstanceType`: When transitioning to `OBSOLETE`, auto-populate
  `deprecation.obsolete` timestamp if not provided
- `DeleteBareMetalInstanceType`: Reject if any `BareMetalInstance` or `BareMetalPool` resources
  reference this `hostType` value

#### Deletion Protection

`BareMetalInstanceType` deletion is blocked if any `BareMetalInstance` CRs have `spec.hostType`
matching the resource name. The fulfillment service checks for live references before deleting the
resource from the fulfillment database:
- Query `BareMetalInstance` and `BareMetalPool` resources in the management cluster by
  `spec.hostType`
- If any exist: reject with 409 Conflict -- "Cannot delete bare metal instance type
  'hpc-icelake-96c': referenced by N active BareMetalInstance(s)"
- If none exist: deletion proceeds; the fulfillment service deletes the `BareMetalInstanceType` CRD

#### Proto Definition Sketch

```proto
// proto/public/osac/public/v1/baremetal_instance_type_type.proto

enum BareMetalInstanceTypeState {
  BARE_METAL_INSTANCE_TYPE_STATE_UNSPECIFIED = 0;
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
  string identifier = 1;      // Unique identifier for this network interface group
  int32 speed_gbps = 2;       // Port line speed in gigabits per second
  int32 count = 3;            // Number of ports at this speed
}

message BareMetalStorageSpec {
  int64 size_gib = 1;         // Total local storage capacity in gibibytes
}

message BareMetalHardwareSpec {
  BareMetalCPUSpec cpu = 1;
  BareMetalMemorySpec memory = 2;
  repeated BareMetalAcceleratorSpec accelerators = 3;
  BareMetalStorageSpec storage = 4;
  repeated BareMetalNetworkPortSpec network = 5;
}

message BareMetalInstanceTypeDeprecation {
  BareMetalInstanceTypeState state = 1;     // DEPRECATED or OBSOLETE (mirrors parent state)
  string replacement = 2;                   // Optional: suggested replacement instance type name
  google.protobuf.Timestamp deprecated = 3; // When deprecation was announced (auto-set on transition)
  google.protobuf.Timestamp obsolete = 4;   // When it becomes/became obsolete (auto-set on transition)
}

message BareMetalInstanceType {
  string name = 1;                          // Primary identifier (globally unique, immutable)
  Metadata metadata = 2;                    // Standard metadata (name field matches top-level name)
  string description = 3;                   // Optional description for users
  BareMetalInstanceTypeState state = 4;
  BareMetalHardwareSpec hardware = 5;       // Auto-discovered hardware specifications
  map<string, string> capabilities = 6;     // Auto-discovered capabilities from inventory metadata
  BareMetalInstanceTypeDeprecation deprecation = 7; // Only set when DEPRECATED or OBSOLETE
  string managed_by = 8;                    // Inventory managed_by field value for frontend separation
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
  string name = 1;  // References metadata.name from BareMetalInstanceType
}

message DeleteBareMetalInstanceTypeRequest {
  string name = 1;  // References metadata.name from BareMetalInstanceType
}

// CreateBareMetalInstanceResponse (modified)
message CreateBareMetalInstanceResponse {
  BareMetalInstance bare_metal_instance = 1;
  repeated string warnings = 2;  // Deprecation warnings for Deprecated instance types
}
```

### Implementation Details/Notes/Constraints

#### Inventory Discovery as Source of Truth

`BareMetalInstanceType` resources are auto-discovered from the inventory backend and materialized
as fulfillment resource. The bare-metal-fulfillment-operator serves as the discovery engine, periodically
querying inventory for host types and extracting hardware specifications. This design provides:

- **Guaranteed accuracy:** Hardware specifications always match actual inventory state.
- **Zero maintenance overhead:** No manual catalog synchronization required.
- **Automatic updates:** New host types appear automatically as inventory changes.
- **Administrative overlay:** Cloud Provider Admins control presentation via osac cli without
  affecting hardware accuracy.

#### Discovery Process

The bare-metal-fulfillment-operator implements an inventory discovery controller that:

1. **Queries inventory backend** for all available hosts with their hostType classifications
2. **Groups hosts by hostType** and samples one representative host per type
3. **Extracts hardware characteristics** from the sampled host:
   - CPU specifications from inventory host properties
   - Memory size from inventory host properties
   - Accelerator devices and specifications
   - Storage capacity information
   - Network interface details with identifiers
   - Capabilities derived from inventory metadata/labels
4. **Creates/updates CRDs** with combined auto + admin data

#### BareMetalInstance Reconciler Integration

The bare-metal-fulfillment-operator implements two reconciliation loops:

**Discovery Controller:**
1. Periodically queries inventory backend for distinct hostTypes
2. Samples hosts per type to extract hardware specifications
4. Creates/updates `BareMetalInstanceType` in fulfillment service

**BareMetalInstance Controller (enhanced):**
1. Receives a `BareMetalInstance` with `spec.hostType` set (e.g. `gpu-a100-2x`)
2. Reads the corresponding `BareMetalInstanceType` to check lifecycle state
3. Sets appropriate conditions on `BareMetalInstance`:
   - `InstanceTypeDeprecated` if hostType is DEPRECATED
   - `InstanceTypeObsolete` if hostType becomes OBSOLETE (informational)
4. Passes the `hostType` value to inventory client for host filtering
5. Applies the managed_by field for inventory filtering as needed
6. Inventory client returns matching hosts; reconciler selects and allocates one

#### Fulfillment Service Integration

The fulfillment service reads auto-discovered `BareMetalInstanceType` directly from the
fulfillment database for API operations.

**`ListBareMetalInstanceTypes` flow:**
1. fulfillment-service queries `BareMetalInstanceType` from the fulfillment database.
2. Filters by `spec.state` per the request filter (default: exclude OBSOLETE).
3. Maps each row to a `BareMetalInstanceType` proto message.
4. Returns the filtered list to the caller.

### Risks and Mitigations

**Risk: Instance type reference becomes stale if type is deleted**
- Mitigation: Soft-delete pattern ensures `BareMetalInstanceType` records remain in the database
  even after deletion (archived table).
- Mitigation: Deletion protection check prevents deletion while `BareMetalInstance` or `BareMetalPool`
  resources reference the type.

**Risk: Inventory filtering no longer uses structured hardware specs**
- Mitigation: Inventory client configuration can be updated to map `hostType` values to appropriate
  filter criteria
- Mitigation: Hardware specifications remain available in instance types for display and planning
  purposes.

**Risk: Accidental workload impact when transitioning to OBSOLETE state**
- Mitigation: OBSOLETE state only prevents new provisioning; existing `BareMetalInstance` resources
  continue to operate unchanged.
- Mitigation: The CLI displays the count of affected references before state transitions.

**Risk: Name reuse concerns after soft deletion**
- Mitigation: Soft-delete pattern prevents name reuse; archived records maintain historical references.
- Mitigation: Primary key uniqueness constraint spans both active and archived tables.

### Drawbacks

**Hardware specifications become display-only metadata**
- Instance types provide hardware specifications for tenant selection and capacity planning, but
  do not directly drive inventory filtering logic.
- Trade-off: Consistent architecture with VM instance types vs. direct operator integration for
  hardware filtering.

**Inventory filtering remains implementation-specific**
- Each inventory backend (OpenStack Ironic, BCM) must implement its own `hostType` to filter
  mapping, which is configured separately from the instance type catalog.
- Trade-off: Flexibility to support diverse inventory systems vs. standardized hardware filtering.

## Alternatives (Not Implemented)

**Alternative 1: Keep `hostType` as an opaque string with no structured resource**
- Simplest approach: no new database tables or CRDs.
- Rejected: No mechanism to expose type metadata (hardware specs, capabilities) to Tenant Users
  via BMaaS API.
- Rejected: No lifecycle state management; retiring a type requires out-of-band coordination.
- Rejected: No structured catalog for capacity planning and tenant self-service.

**Alternative 2: Source instance types from a ConfigMap or annotation convention**
- Cloud Provider Admins annotate or label hosts; a controller derives types from host metadata.
- Rejected: ConfigMaps are not strongly typed; no validation or lifecycle management.
- Rejected: Deriving types from host annotations is brittle and hard to manage at scale.

**Alternative 3: Manual CLI-based catalog management**
- Cloud Provider Admin creates instance types via `osac-admin` CLI with manual hardware specifications.
- Rejected: Manual specification of hardware details is error-prone and requires constant synchronization
  with inventory changes.
- Rejected: Inventory discovery eliminates the need for manual catalog maintenance.

**Alternative 4: Unified instance types for VM and bare metal**
- Use the same `InstanceType` resource for both VM and bare metal provisioning.
- Rejected: VM and bare metal have fundamentally different hardware characteristics and provisioning
  patterns; separate catalogs provide better type safety and user experience.

## Test Plan

**Unit Tests:**
- `BareMetalInstanceType` fulfillment validation (required fields, enum constraints, immutable name)
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
- Database reconciliation: verify database changes sync to CRDs correctly
- `BareMetalInstance` reconciler: uses `hostType` as opaque identifier for inventory client filtering
  (hardware specs are metadata-only)

**Integration Tests:**
- Admin creates `BareMetalInstanceType` via CLI; verify database record and reconciled CRD appear;
  verify it appears in `ListBareMetalInstanceTypes` response
- `GetBareMetalInstanceType` returns hardware specs from database
- Provision `BareMetalInstance` referencing ACTIVE type: succeeds, no warnings
- Provision `BareMetalInstance` referencing DEPRECATED type: succeeds, warning in response
- Provision `BareMetalInstance` referencing OBSOLETE type: rejected with 409 Conflict
- Set type to DEPRECATED; verify it appears in list with deprecation metadata
- Set type to OBSOLETE; verify it disappears from default `ListBareMetalInstanceTypes` response
- Verify `GetBareMetalInstanceType` still returns OBSOLETE type for admin inspection
- Attempt to delete type with active `BareMetalInstance` references: rejected
- Deprovision all `BareMetalInstance` resources, then delete type: database record archived, CRD removed
- Reactivate DEPRECATED type: returns to ACTIVE, no warnings on new provisioning
- Database to CRD reconciliation: verify changes to database records sync to CRDs correctly
- `BareMetalInstance` reconciler uses `hostType` for inventory filtering (hardware specs are display-only)
- **Inventory integration validation:** Test that inventory clients correctly map `hostType` values
  to appropriate filter criteria; provision `BareMetalInstance` resources and verify allocated hosts
  match the expected characteristics for each `hostType`; hardware specifications in instance types
  should be for display/planning but not directly used for filtering

**End-to-End Tests:**
- Cloud Provider Admin creates `BareMetalInstanceType` via `osac` CLI
- Tenant User lists instance types and sees the new type with hardware specs
- Tenant User provisions `BareMetalInstance` selecting the new type
- bare-metal-fulfillment-operator uses `hostType` for inventory client filtering, allocates
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

**New API resources:**
- `BareMetalInstanceTypes` service (public) in fulfillment-service (read-only)
- Enhanced inventory discovery controller in bare-metal-fulfillment-operator

**Failure Modes and Troubleshooting:**

**`ListBareMetalInstanceTypes` returns empty list**
- **Detection:** API returns empty `items`; `oc get bmit` shows CRDs exist
- **Diagnosis:** fulfillment-service cannot read CRDs from management cluster
- **Resolution:** Check fulfillment-service RBAC for `baremetalinstancetypes` and cluster connectivity

**Instance types not auto-discovered**
- **Detection:** Expected `hostType` values from inventory don't appear as CRDs
- **Diagnosis:** Discovery controller may not be running or failing to query inventory
- **Resolution:** Check bare-metal-fulfillment-operator logs; verify inventory backend connectivity;
  ensure discovery controller is running

**`BareMetalInstance` creation rejected: "instance type not found"**
- **Detection:** API returns 404 Not Found for a valid `hostType` that exists in inventory
- **Diagnosis:** The `BareMetalInstanceType` CRD was not auto-discovered or was deleted
- **Resolution:** Check discovery controller logs; verify hostType exists in inventory; manually
  trigger discovery if needed

**`CreateBareMetalInstance` returns 409 for a type that appears Active in list**
- **Detection:** List shows Active type; provisioning rejected with "is obsolete"
- **Diagnosis:** Stale cache in fulfillment service; CRD was updated to Obsolete between list and
  create
- **Resolution:** Re-list instance types; if type is genuinely Active, retry after cache TTL expires

**Hardware specifications outdated**
- **Detection:** CRD shows hardware specs that don't match current inventory state
- **Diagnosis:** Discovery controller may not be running periodic inventory updates
- **Resolution:** Check discovery controller schedule and logs; manually trigger discovery;
  verify inventory backend connectivity

### Disabling / Rollback

Not supported.

## Infrastructure Needed

No additional infrastructure is required.
