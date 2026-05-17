---
title: vm-instance-types
authors:
  - atraeger@redhat.com
creation-date: 2026-05-06
last-updated: 2026-05-06
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-46
see-also:
  - "/enhancements/vmaas"
replaces:
superseded-by:
---

# VM Instance Types

## Summary

This enhancement introduces VM instance types as pre-defined compute resource bundles (cores, memory) that can be referenced by name when creating virtual machines. Instance types simplify VM creation by providing a standardized set of compute configurations, following cloud-native patterns similar to AWS EC2 instance types, Azure VM sizes, and GCP machine types. All instance types are global. The instance type concept exists only at the gRPC API layer (fulfillment-service); at the Kubernetes CR level, instance types are expanded to cores/memory_gib fields. Users select an instance type by name rather than specifying individual cores and memory values. This proposal focuses on Virtual Machine-as-a-Service (VMaaS) compute instances only; Cluster-as-a-Service (CaaS) uses bare metal provisioning with a separate resource classification system (`HostType`) and is not covered by this enhancement.

## Motivation

The current ComputeInstance API allows users to specify compute resources (cores, memory) as individual numeric fields. While flexible, this approach creates several challenges: it complicates capacity planning and resource optimization, makes it harder to standardize VM offerings across tenants, and increases the cognitive load for users who must understand appropriate core-to-memory ratios. Instance types address these problems by providing a curated set of pre-validated compute configurations that align with infrastructure capabilities and organizational standards. This also lays the groundwork for future enhancements such as usage-based metering, capacity reservations, and custom instance type definitions (Phase 2).

### User Stories

* As a Organization User, I want to create a VM by selecting an instance type (e.g., 'standard-4-16') that defines the compute resources, so that I can quickly provision VMs without needing to understand appropriate core-to-memory ratios.
* As a Organization User, I want to list available instance types with their compute specifications, so that I can choose the right size for my workload.
* As a Cloud Provider Admin, I want to define global instance types including their compute specifications, so that I can standardize VM offerings and align them with available infrastructure capacity.
* As a Cloud Provider Admin, I want to enforce governance by requiring instance types for all VM creation, so that I can prevent resource fragmentation and ensure efficient capacity utilization.
* As a Cloud Provider Admin, I want to control instance type availability by managing lifecycle states (ACTIVE/DEPRECATED/OBSOLETE), so that I can manage which VM sizes are available to tenants without deleting instance type definitions.

### Goals

* Provide a self-service API for Organization Users to list available instance types and create VMs using instance type names
* Require all ComputeInstance creation to use instance types (strict mode), removing the ability to specify cores and memory individually
* Support globally-scoped instance types defined and managed by Cloud Provider Admins only
* Support instance type lifecycle states (ACTIVE → DEPRECATED → OBSOLETE) following GCP deprecation model, allowing graceful migration without deleting type definitions
* Provide deprecation metadata (timestamps, replacement suggestions) to communicate migration timelines to users
* Ensure instance type compute specifications (cores, memory, name) are immutable after creation to prevent inconsistencies

### Non-Goals

The following are explicitly out of scope for Phase 1:

* Organization-specific instance types (Organization Admin-defined types scoped to a single organization)
* Instance type "Series" with technical constraint ranges (min/max RAM-to-CPU ratios, supported architectures)
* Flexible mode allowing users to specify custom cores/memory values within series constraints
* GPU support (gpu_count, gpu_type fields) - deferred to Phase 2
* Storage specifications as part of instance types (boot disk size remains separate, following AWS/Azure/GCP pattern)
* Quota enforcement and capacity planning based on instance types (quota system not yet defined in OSAC)
* Pricing or metering metadata associated with instance types
* Network bandwidth constraints or network performance tiers
* Per-organization instance type restrictions
* Automatic state transitions based on deprecation timestamps (scheduled job to transition DEPRECATED → OBSOLETE)

## Proposal

This proposal introduces a new `InstanceType` resource that defines pre-configured compute bundles with immutable core and memory specifications. The Cloud Service Provider creates and manages all instance types, which are globally visible to all organizations. The `ComputeInstance` gRPC API is modified to require an `instance_type` field and remove the existing `cores` and `memory_gib` fields (the Kubernetes CR retains these fields, populated by fulfillment-service). Disk specifications remain separate from instance types, as storage and compute are decoupled following industry-standard cloud patterns. Instance types include a deprecation mechanism to manage lifecycle transitions.

### Key Resources

**InstanceType** - Provider-defined compute specification
* Globally scoped, visible to all organizations
* Identified by name (globally unique, user-specified, e.g., "standard-4-16")
* Immutable compute specs (cores, memory_gib, name)
* Mutable metadata (description, state, deprecation)
* State lifecycle: ACTIVE → DEPRECATED → OBSOLETE (following GCP deprecation model)
* Deprecation metadata includes timestamps and replacement suggestions for migration planning
* Cloud Provider Admin-only creation and management

**ComputeInstance (modified)** - Virtual machine resource
* Now requires `instance_type` field (string reference to InstanceType name)
* Removes `cores` and `memory_gib` fields from ComputeInstanceSpec (API layer only)
* Retains `boot_disk` and `storage_class` as separate specifications

### Scoping and Visibility

All instance types in Phase 1 are globally scoped:
* **Created by:** Cloud Provider Admin only
* **Lifecycle states:**
  - **ACTIVE**: Fully available for new VM creation, no warnings
  - **DEPRECATED**: Available with warnings on VM creation (e.g., "Instance type 'standard-2-4' is deprecated. Consider using 'standard-2-8' instead.")
  - **OBSOLETE**: Not available for new VM creation (rejected), still visible for lookups

**API behavior by state:**
* ListInstanceTypes: Returns ACTIVE and DEPRECATED by default; supports filter parameter to include OBSOLETE (e.g., `filter: "state IN (ACTIVE, DEPRECATED, OBSOLETE)"`)
* GetInstanceType: Returns any instance type regardless of state (for viewing details by name)
* CreateComputeInstance: ACTIVE succeeds, DEPRECATED succeeds with warning in `CreateComputeInstanceResponse.warnings` field, OBSOLETE is rejected with 409 Conflict

### Naming and Uniqueness

* Instance type names are globally unique across the entire platform
* Name is the primary identifier for referencing instance types (not an opaque ID)
* ComputeInstance.spec.instance_type holds the name as a string (e.g., "standard-4-16")
* Names are immutable after creation to prevent reference breakage
* Database uses `name` as the primary key

### Workflow Description

#### Instance Type Management (Cloud Provider Admin)

**Creating an Instance Type**

1. Cloud Provider Admin uses the OSAC CLI to create a new global instance type:
   ```bash
   osac-admin create instance-type standard-4-16 \
     --cores 4 \
     --memory-gib 16 \
     --description "Balanced compute: 4 cores, 16 GiB RAM"
   ```
2. The Fulfillment Service validates the request and creates the InstanceType resource
3. The instance type is immediately available (state=ACTIVE by default) to all Organization Users

**Deprecating an Instance Type**

1. Cloud Provider Admin marks an instance type as deprecated with optional transition timeline:
   ```bash
   osac-admin update instance-type standard-2-4 \
     --state DEPRECATED \
     --replacement standard-2-8 \
     --obsolete-at 2026-12-31T23:59:59Z
   ```
2. The Fulfillment Service updates the InstanceType state and records deprecation metadata (current timestamp as `deprecated`, future timestamp as `obsolete`)
3. The instance type remains visible in ListInstanceTypes for Organization Users
4. New VM creation requests succeed but return a warning: "Instance type 'standard-2-4' is deprecated and will become obsolete on 2026-12-31. Consider migrating to 'standard-2-8'."
5. Existing VMs continue to run unchanged
6. **Note:** Phase 1 does not include automatic state transitions - Cloud Provider Admin must manually transition to OBSOLETE on or after the obsolete date

**Obsoleting an Instance Type**

1. Cloud Provider Admin marks an instance type as obsolete to prevent new VM creation:
   ```bash
   osac-admin update instance-type standard-2-4 --state OBSOLETE
   ```
2. The Fulfillment Service updates the InstanceType state and records obsolete timestamp
3. The instance type is hidden from ListInstanceTypes for Organization Users (unless explicitly filtered)
4. Existing VMs using this instance type continue to run unchanged
5. New VM creation requests with this instance type are rejected with 409 Conflict

**Deleting an Instance Type**

1. Cloud Provider Admin attempts to delete an instance type:
   ```bash
   osac-admin delete instance-type standard-4-16
   ```
2. The Fulfillment Service checks if any VMs reference this instance type
3. If in use: deletion is rejected with error "instance type is in use by at least one VM"
4. If not in use: deletion succeeds

#### VM Creation (Organization User)

**Listing Available Instance Types**

1. Organization User lists available instance types:
   ```bash
   osac list instance-types
   ```
2. The Fulfillment Service returns ACTIVE and DEPRECATED instance types (OBSOLETE types can be included via filter parameter):
   ```json
   {
     "items": [
       {
         "name": "standard-2-4",
         "metadata": { "name": "standard-2-4" },
         "cores": 2,
         "memory_gib": 4,
         "description": "Small balanced compute",
         "state": "DEPRECATED",
         "deprecation": {
           "state": "DEPRECATED",
           "replacement": "standard-2-8",
           "deprecated": "2026-03-15T10:00:00Z",
           "obsolete": "2026-12-31T23:59:59Z"
         }
       },
       {
         "name": "standard-4-16",
         "metadata": { "name": "standard-4-16" },
         "cores": 4,
         "memory_gib": 16,
         "description": "Medium balanced compute",
         "state": "ACTIVE"
       }
     ]
   }
   ```

**Creating a VM with Instance Type**

1. Organization User creates a VM specifying an instance type:
   ```bash
   osac create compute-instance my-vm \
     --instance-type standard-4-16 \
     --boot-disk-gib 50 \
     --image quay.io/fedora/fedora:40
   ```
2. The Fulfillment Service validates and resolves:
   - Instance type "standard-4-16" exists and state is ACTIVE or DEPRECATED
   - User has appropriate permissions
   - Resolves instance type to cores=4, memory_gib=16
   - If state is DEPRECATED, includes warning in `CreateComputeInstanceResponse.warnings` field
3. The API returns `CreateComputeInstanceResponse`:
   ```json
   {
     "compute_instance": { /* ComputeInstance resource */ },
     "warnings": []  // Empty for ACTIVE instance types; contains deprecation message for DEPRECATED types
   }
   ```
4. The Fulfillment Service creates the ComputeInstance CR with expanded values:
   ```yaml
   apiVersion: osac.openshift.io/v1alpha1
   kind: ComputeInstance
   metadata:
     name: my-vm
     labels:
       osac.io/instance-type-name: "standard-4-16"  # Audit trail
   spec:
     cores: 4              # Expanded from instance type
     memory_gib: 16        # Expanded from instance type
     template: "default-vm-template"
     boot_disk:
       size_gib: 50
     image:
       source_type: "registry"
       source_ref: "quay.io/fedora/fedora:40"
   ```
5. The osac-operator reconciles the ComputeInstance, reading cores and memory_gib from spec
6. The VM is provisioned via KubeVirt with 4 cores and 16 GiB RAM

**Error Cases**

**Non-existent instance type:**
```bash
$ osac create compute-instance my-vm --instance-type nonexistent
Error: instance type "nonexistent" not found
```

**OBSOLETE instance type:**
```bash
$ osac create compute-instance my-vm --instance-type old-type
Error: instance type "old-type" is obsolete and cannot be used for new VMs
```

**Missing instance type:**
```bash
$ osac create compute-instance my-vm --boot-disk-gib 50
Error: instance_type field is required
```

### API Extensions

This enhancement modifies existing OSAC APIs and introduces new resources:

#### New Resources

**InstanceType** (proto/public/osac/public/v1/instance_type_type.proto)
- Public API: Read-only List and Get operations for Organization Users
- Private API: Full CRUD operations for Cloud Provider Admins

**InstanceTypes Service** (proto/public/osac/public/v1/instance_types_service.proto)
- Public API: ListInstanceTypes, GetInstanceType
- Private API: CreateInstanceType, UpdateInstanceType, DeleteInstanceType

#### Modified Resources

**ComputeInstanceSpec** (proto/public/osac/public/v1/compute_instance_type.proto - API layer only)
- Add: `instance_type` field (string, required) - reference to InstanceType name
- Remove: `cores` field (optional int32) - replaced by instance_type in API
- Remove: `memory_gib` field (optional int32) - replaced by instance_type in API
- Note: fulfillment-service resolves instance_type name to cores/memory_gib when creating the CR
- Retain: `boot_disk`, `storage_class`, `template`, `image`, `user_data`, `ssh_key`, etc.

Note: The Kubernetes CR schema retains cores/memory_gib fields. The fulfillment-service expands instance_type to these fields when creating the CR. See "Instance Type Resolution Strategy" for details.

#### Validation

**Public API (Organization Users):**
- CreateComputeInstance: Require instance_type field (string name), reject if missing
- CreateComputeInstance: Validate instance_type name exists and state is ACTIVE or DEPRECATED
- CreateComputeInstance: If state is DEPRECATED, include warning in `CreateComputeInstanceResponse.warnings` field with replacement suggestion (if set) and obsolete timestamp (if set)
- CreateComputeInstance: If state is OBSOLETE, reject with HTTP 409 Conflict ("instance type is obsolete")
- CreateComputeInstance: If instance_type name not found, reject with HTTP 404 Not Found
- CreateComputeInstance: Expand instance_type name to cores/memory_gib before creating CR
- CreateComputeInstance: Add osac.io/instance-type-name label to CR
- UpdateComputeInstance: Reject changes to instance_type field (immutable in Phase 1)

**Private API (Cloud Provider Admin):**
- CreateInstanceType: Require name, cores, and memory_gib fields
- CreateInstanceType: Validate name uniqueness (globally unique across all instance types)
- CreateInstanceType: Validate cores > 0 and memory_gib > 0
- CreateInstanceType: Default state to ACTIVE if not specified
- UpdateInstanceType: Reject changes to name, cores, or memory_gib (immutable)
- UpdateInstanceType: Allow changes to description, state, and deprecation fields
- UpdateInstanceType: When transitioning to DEPRECATED, auto-populate deprecation.deprecated timestamp (set to current time) if not provided
- UpdateInstanceType: When transitioning to OBSOLETE, auto-populate deprecation.obsolete timestamp (set to current time) if not provided
- UpdateInstanceType: If deprecation.deprecated is provided explicitly, allow any timestamp (past or future) - represents when deprecation was/will be announced
- UpdateInstanceType: If deprecation.obsolete is provided explicitly when transitioning to DEPRECATED, validate it is in the future (cannot set future DEPRECATED type to already-obsolete)
- UpdateInstanceType: If deprecation.obsolete is provided explicitly when transitioning to OBSOLETE, allow any timestamp (past or future) - represents when it became/will become obsolete
- UpdateInstanceType: API behavior is based on state field, not timestamps (future deprecation timestamps do not affect current behavior)
- DeleteInstanceType: Reject if any ComputeInstances reference this instance type by name

#### Deletion Protection

**InstanceType deletion checks:**
- fulfillment-service queries database for ComputeInstances using this instance type name (via osac.io/instance-type-name label)
- If any references exist, deletion is rejected with 409 Conflict
- Returns list of affected ComputeInstance names in error message
- Deletion succeeds only when no ComputeInstances reference the instance type name

### Implementation Details/Notes/Constraints

#### Database Schema

**instance_types table:**
```sql
CREATE TABLE instance_types (
    name TEXT PRIMARY KEY,                  -- User-specified name (globally unique, immutable, never reusable, e.g., "standard-4-16")
    creation_timestamp TIMESTAMPTZ NOT NULL,
    deletion_timestamp TIMESTAMPTZ,
    finalizers TEXT[],
    creators TEXT[],
    tenants TEXT[],                         -- Empty for global instance types in Phase 1
    labels JSONB,
    annotations JSONB,
    data JSONB NOT NULL                     -- Serialized InstanceType protobuf
);

-- No additional unique index needed: PRIMARY KEY on name enforces uniqueness for all rows (active and soft-deleted)
-- Instance type names are never reusable, even after soft deletion
```

The `data` JSONB column contains the serialized InstanceType protobuf.

Example of an ACTIVE instance type:
```json
{
  "name": "standard-4-16",
  "metadata": {
    "name": "standard-4-16"
  },
  "cores": 4,
  "memory_gib": 16,
  "description": "Balanced compute: 4 cores, 16 GiB RAM",
  "state": "ACTIVE"
}
```

Example of a DEPRECATED instance type with deprecation metadata:
```json
{
  "name": "standard-2-4",
  "metadata": {
    "name": "standard-2-4"
  },
  "cores": 2,
  "memory_gib": 4,
  "description": "Small balanced compute",
  "state": "DEPRECATED",
  "deprecation": {
    "state": "DEPRECATED",
    "replacement": "standard-2-8",
    "deprecated": "2026-03-15T10:00:00Z",
    "obsolete": "2026-12-31T23:59:59Z"
  }
}
```

**Note:** The top-level database `name` column (PRIMARY KEY) mirrors `data.name` and `data.metadata.name` for efficient querying and indexing. All three values must be identical for a given InstanceType record.

#### Instance Type Resolution Strategy

**Expansion at API boundary:**

Instance types are resolved and expanded by fulfillment-service when creating the ComputeInstance CR. The CR spec contains the expanded compute resources (cores, memory_gib), not the instance type reference. This design choice provides:

- **Zero changes to osac-operator:** Controller reads cores/memory_gib as it does today
- **No runtime dependencies:** osac-operator doesn't need to call fulfillment-service API
- **Enforcement at boundary:** Organization Users access only the fulfillment-service API (not k8s APIs), so instance type validation cannot be bypassed
- **Audit trail:** Original instance_type name stored in CR label

**fulfillment-service flow:**
1. User creates ComputeInstance via API with `instance_type: "standard-4-16"` (name reference)
2. fulfillment-service queries database for InstanceType with `name = "standard-4-16"`
3. fulfillment-service validates instance type exists and state is ACTIVE or DEPRECATED
4. If state is DEPRECATED, add warning to response
5. fulfillment-service resolves cores=4, memory_gib=16 from InstanceType record
6. fulfillment-service creates ComputeInstance CR with:
   - `spec.cores: 4`
   - `spec.memory_gib: 16`
   - `metadata.labels["osac.io/instance-type-name"]: "standard-4-16"` (audit trail and deletion protection lookup)

**osac-operator reconciliation (unchanged):**
1. Read ComputeInstance.spec.cores and spec.memory_gib
2. Pass values to KubeVirt VM spec
3. Update ComputeInstance.status

**Future extensibility:**

Changing instance types is blocked in Phase 1 (spec.cores and spec.memory_gib are immutable). In the future, we could support instance type updates by:
1. Allowing updates to cores/memory_gib fields
2. Updating the `osac.io/instance-type-name` label
3. Triggering VM resize (if supported by underlying platform)

Advanced OpenShift Virtualization features (NUMA topology, hugepages, CPU pinning) remain internal implementation details and are not exposed to Organization Users through the instance type API.

#### Fulfillment Service Implementation

**Server structure:**
- `InstanceTypesServer` (public) - wraps `PrivateInstanceTypesServer` with tenant filtering
- `PrivateInstanceTypesServer` (private) - full CRUD using GenericServer pattern
- Both servers in `internal/servers/instance_types_server.go` and `private_instance_types_server.go`

**Authorization and scoping:**

Instance type APIs follow the standard fulfillment-service authentication, authorization, and tenant-scoping policy. Instance-type-specific deltas:

- **Global scope:** All instance types are globally scoped (no tenant filtering)
- **Admin-only write:** CreateInstanceType, UpdateInstanceType, DeleteInstanceType require Cloud Provider Admin role
- **State-based filtering:** ListInstanceTypes returns ACTIVE and DEPRECATED by default (use filter parameter for OBSOLETE)
- **Deletion protection:** DeleteInstanceType rejects if any ComputeInstances reference the type (API-layer query check)

#### Proto Definition Sketch

```proto
// proto/public/osac/public/v1/instance_type_type.proto
enum InstanceTypeState {
  INSTANCE_TYPE_STATE_UNSPECIFIED = 0;
  ACTIVE = 1;       // Fully available for new VM creation
  DEPRECATED = 2;   // Available with warnings, migration recommended
  OBSOLETE = 3;     // Not available for new VMs, visible for lookups only
}

message InstanceTypeDeprecation {
  InstanceTypeState state = 1;                   // DEPRECATED or OBSOLETE (matches parent InstanceType.state)
  string replacement = 2;                        // Optional: suggested replacement instance type name
  google.protobuf.Timestamp deprecated = 3;      // Optional: when deprecation was announced (auto-set on DEPRECATED transition)
  google.protobuf.Timestamp obsolete = 4;        // Optional: when it becomes/became obsolete (admin-specified or auto-set)
}

message InstanceType {
  string name = 1;                               // Primary identifier (globally unique, immutable, e.g., "standard-4-16")
  Metadata metadata = 2;                         // Standard metadata (name field matches top-level name)
  int32 cores = 3;                               // Immutable compute specification
  int32 memory_gib = 4;                          // Immutable compute specification
  string description = 5;                        // Mutable descriptive text
  InstanceTypeState state = 6;                   // Mutable lifecycle state
  InstanceTypeDeprecation deprecation = 7;       // Optional: only set when state is DEPRECATED or OBSOLETE
}

// proto/public/osac/public/v1/instance_types_service.proto
service InstanceTypes {
  rpc List(ListInstanceTypesRequest) returns (ListInstanceTypesResponse) {
    option (google.api.http) = {
      get: "/api/fulfillment/v1/instance_types"
    };
  }
  rpc Get(GetInstanceTypeRequest) returns (InstanceType) {
    option (google.api.http) = {
      get: "/api/fulfillment/v1/instance_types/{name}"
    };
  }
}

// proto/private/osac/private/v1/instance_types_service.proto
service InstanceTypes {
  rpc Create(CreateInstanceTypeRequest) returns (InstanceType);
  rpc Update(UpdateInstanceTypeRequest) returns (InstanceType);
  rpc Delete(DeleteInstanceTypeRequest) returns (google.protobuf.Empty);
  rpc List(ListInstanceTypesRequest) returns (ListInstanceTypesResponse);
  rpc Get(GetInstanceTypeRequest) returns (InstanceType);
}

// GetInstanceTypeRequest references by name
message GetInstanceTypeRequest {
  string name = 1;  // Instance type name (e.g., "standard-4-16")
}

// DeleteInstanceTypeRequest references by name
message DeleteInstanceTypeRequest {
  string name = 1;  // Instance type name (e.g., "standard-4-16")
}
```

**API vs CR Schema:**

The fulfillment-service API and the Kubernetes CR have different schemas to support instance type expansion at the API boundary.

**Public API Schema (proto/public/osac/public/v1/):**
```proto
message ComputeInstanceSpec {
  string template = 1;
  map<string, google.protobuf.Any> template_parameters = 2;
  optional google.protobuf.Timestamp restart_requested_at = 3;
  optional ComputeInstanceImage image = 4;

  // NEW: Required instance type reference (API only)
  string instance_type = 5;

  // REMOVED from API: cores and memory_gib (replaced by instance_type)

  optional string ssh_key = 7;
  optional ComputeInstanceDisk boot_disk = 8;
  repeated ComputeInstanceDisk additional_disks = 9;
  optional string run_strategy = 10;
  optional string user_data = 11;
  optional string subnet = 12;
  repeated string security_groups = 13;
}

// CreateComputeInstanceResponse includes warnings for DEPRECATED instance types
message CreateComputeInstanceResponse {
  ComputeInstance compute_instance = 1;
  repeated string warnings = 2;  // Warning messages (e.g., "Instance type 'standard-2-4' is deprecated and will become obsolete on 2026-12-31. Consider migrating to 'standard-2-8'.")
}
```

**Kubernetes CR Schema (osac-operator CRD):**
```yaml
# ComputeInstance CR (created by fulfillment-service)
apiVersion: osac.openshift.io/v1alpha1
kind: ComputeInstance
metadata:
  labels:
    osac.io/instance-type-name: "standard-4-16"  # Audit trail
spec:
  template: "..."
  cores: 4              # Expanded from instance type
  memory_gib: 16        # Expanded from instance type
  boot_disk:
    size_gib: 50
  # ... other fields unchanged
```

The CR retains cores/memory_gib fields in spec (unchanged from today) so osac-operator requires no modifications. The instance_type field exists only in the API layer and is stored as a label in the CR.

### Risks and Mitigations

**Risk: Breaking change for existing API consumers**
- Mitigation: Since OSAC is pre-GA, breaking changes are acceptable

**Risk: Instance type reference becomes stale if type is deleted**
- Mitigation: fulfillment-service API checks prevent deletion of InstanceTypes referenced by active VMs
- Mitigation: Admin must set type to OBSOLETE, wait for VMs to be deleted, then delete type

**Risk: Users need a specific core/memory combination not offered**
- Mitigation: Document process for requesting new instance types from Cloud Provider Admin
- Mitigation: Phase 2 will introduce flexible mode with custom configurations within series bounds
- Mitigation: Admins can create arbitrary instance types to meet tenant needs

**Risk: Capacity planning becomes harder without understanding actual resource allocation**
- Mitigation: ListInstanceTypes provides full spec visibility
- Mitigation: Future quota system will track instance type usage
- Mitigation: Admin APIs expose compute resource consumption per tenant

### Drawbacks

**Reduced flexibility for Organization Users**
- Users can no longer specify arbitrary core/memory combinations
- Trade-off: Simplicity and standardization vs. maximum flexibility
- Justification: Cloud providers typically constrain VM sizes for operational reasons (capacity planning, SLA guarantees, cost optimization)

**Additional API resource and complexity**
- Introduces new InstanceType resource with CRUD operations
- Trade-off: More API surface area vs. simplified VM creation UX
- Justification: The pattern is well-established (AWS, Azure, GCP) and familiar to users

## Alternatives (Not Implemented)

**Alternative 1: Keep cores/memory_gib fields alongside instance_type**
- Allow users to either specify instance_type OR cores/memory_gib
- Rejected: Creates API ambiguity (what if both are specified?)
- Rejected: Doesn't achieve goal of standardization and governance
- Rejected: Complicates capacity planning and quota enforcement

**Alternative 2: Make instance types optional (flexible mode from start)**
- Allow instance_type as a convenience but keep cores/memory_gib as primary fields
- Rejected: Doesn't enforce standardization
- Rejected: Deferred to Phase 2 with proper series-based constraints

**Alternative 3: Use HostType instead of creating new InstanceType resource**
- Reuse existing HostType resource for VMs
- Rejected: HostType is intentionally opaque (only id/title/description)
- Rejected: HostType serves bare metal inventory labeling, not VM compute specs
- Rejected: Need structured cores/memory_gib for capacity planning and quotas

**Alternative 4: Store instance type inline in ComputeInstanceSpec**
- Embed full instance type spec (cores, memory) directly in each ComputeInstance
- Rejected: Updates to instance type definitions wouldn't propagate to existing VMs
- Rejected: Breaks immutability guarantees (users could modify embedded spec)
- Rejected: Increases storage overhead and denormalization

**Alternative 5: Dynamic instance type generation based on requested resources**
- Auto-create instance types on-demand when users specify custom cores/memory
- Rejected: Defeats purpose of governance and standardization
- Rejected: Infinite instance type growth makes management infeasible
- Rejected: Deferred to Phase 2 as explicit "custom instance types within series"

## Test Plan

**Unit Tests:**
- InstanceType CRUD operations via GenericServer
- ComputeInstance validation rejects missing instance_type
- ComputeInstance validation rejects OBSOLETE instance_type
- ComputeInstance validation rejects non-existent instance_type
- ComputeInstance with DEPRECATED instance_type succeeds with warning (includes obsolete timestamp in warning)
- InstanceType state transitions (ACTIVE → DEPRECATED → OBSOLETE)
- InstanceType deprecation metadata auto-population (deprecated timestamp on DEPRECATED transition, obsolete timestamp on OBSOLETE transition)
- InstanceType validation rejects obsolete timestamp in the past when transitioning to DEPRECATED
- InstanceType deletion rejected when VMs reference it
- InstanceType cores/memory_gib/name immutability enforcement
- InstanceType deprecation field mutability (replacement, timestamps)
- ListInstanceTypes filter behavior (default excludes OBSOLETE, filter includes it)
- ListInstanceTypes returns deprecation metadata for DEPRECATED/OBSOLETE types

**Integration Tests (fulfillment-service/it/):**
- Create InstanceType, verify it appears in ListInstanceTypes
- Create ComputeInstance with valid instance_type, verify VM provisions with correct resources
- Attempt to create ComputeInstance with OBSOLETE instance_type, verify 409 Conflict
- Set InstanceType to DEPRECATED with future obsolete timestamp, verify warning includes obsolete date
- Create VM with DEPRECATED instance_type, verify warning message includes deprecation timeline
- Set InstanceType to OBSOLETE, verify it disappears from org user ListInstanceTypes
- Verify GetInstanceType returns deprecation metadata for DEPRECATED and OBSOLETE types
- Attempt to delete InstanceType with active VMs, verify rejection
- Delete all VMs, then delete InstanceType, verify success
- Create VM, update instance_type, verify rejection (immutability)

**End-to-End Tests:**
- Cloud Provider Admin creates instance type via CLI
- Organization User lists instance types and sees new type
- Organization User creates VM using instance type
- osac-operator provisions KubeVirt VM with correct cores/memory
- VM reaches Running state
- Cloud Provider Admin sets instance type to DEPRECATED with replacement and future obsolete timestamp
- Organization User lists instance types and sees DEPRECATED status with deprecation metadata
- Organization User creates new VM with DEPRECATED type, receives warning with obsolete date
- Cloud Provider Admin sets instance type to OBSOLETE
- Organization User no longer sees type in list (unless filtered)
- Attempt to create new VM with OBSOLETE type fails with 409 Conflict
- Existing VM continues running

**Migration Testing:**
- Run migration on test database with existing ComputeInstances
- Verify all VMs get assigned instance_type
- Verify compute resources match pre-migration values
- Verify new VM creation works post-migration

## Graduation Criteria

This enhancement is not targeting a specific OSAC release at this time. When targeting a release, graduation criteria will be defined based on production deployment feedback and user validation.

Expected maturity progression:
- **Dev Preview:** Initial implementation with basic instance type CRUD and VM creation
- **Tech Preview:** Production deployment at pilot sites with migration tooling
- **GA:** Full production deployment with documented migration path and operational runbooks

Success signals for graduation:
- Zero incidents related to instance type reference resolution
- Migration tooling successfully used at 2+ pilot sites
- Positive feedback from Cloud Provider Admins on manageability
- Positive feedback from Organization Users on simplified VM creation UX
- Documentation complete and validated by users

## Upgrade/Downgrade Strategy

Not applicable - OSAC is pre-GA. This is a breaking API change.

## Version Skew Strategy

Not applicable - OSAC is pre-GA. Components should be upgraded together.

## Support Procedures

### Operational Impact of API Extensions

**New API resources:**
- InstanceType (CRD-like resource in fulfillment-service, not a Kubernetes CRD)
- Creates additional database table and API endpoints
- Increases fulfillment-service memory footprint (caching layer for instance type lookups)

**Modified API resources:**
- ComputeInstance.spec.instance_type (new required field)
- Breaking change: cores/memory_gib fields removed

**Failure Modes and Troubleshooting:**

**ComputeInstance stuck in Pending with invalid resource values**
- **Detection:** `kubectl get computeinstance <name> -o yaml` shows invalid cores/memory_gib values
- **Diagnosis:** Instance type definition was corrupted or manually modified in database
- **Resolution:** Delete and recreate VM via API with valid instance type, or fix database corruption
- **Prevention:** Only modify instance types via fulfillment-service API, never directly in database

**ComputeInstance creation rejected: "instance type is obsolete"**
- **Detection:** API returns 409 Conflict with message indicating instance type is OBSOLETE
- **Diagnosis:** Cloud Provider Admin marked the instance type as OBSOLETE
- **Resolution:** Choose a different instance type (check replacement suggestion if available) or ask admin to change state back to ACTIVE/DEPRECATED
- **Prevention:** Communicate instance type lifecycle changes (OBSOLETE transitions) to users before making the change

**osac-operator reconciliation failures**
- **Detection:** Controller logs show errors provisioning VM or invalid spec values
- **Diagnosis:** ComputeInstance CR has invalid cores/memory_gib values (data corruption or manual edit)
- **Resolution:** Check CR spec.cores and spec.memory_gib; if invalid, delete CR and recreate VM via API
- **Prevention:** Never manually edit ComputeInstance CRs; always use fulfillment-service API

**InstanceType cannot be deleted: "referenced by active VMs"**
- **Detection:** DELETE API call returns 409 Conflict
- **Diagnosis:** fulfillment-service database query found ComputeInstances using this instance type name
- **Resolution:** Delete all referencing VMs first, then delete instance type. Or set instance type to OBSOLETE and delete later.
- **Prevention:** Use List API or query database to find referencing VMs before attempting deletion

### Disabling / Rollback

Not supported.

## Infrastructure Needed

No additional infrastructure is required for this enhancement.
