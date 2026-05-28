---
title: image-management
authors:
  - yblum@redhat.com
creation-date: 2026-05-26
last-updated: 2026-05-26
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-979
see-also:
  - "/enhancements/vmaas"
  - "/enhancements/catalog-items"
replaces:
  - N/A
superseded-by:
  - N/A
---

# OSAC Image Management

## Summary

This enhancement introduces a **ComputeImage** API resource for managing virtual machine images as first-class entities in OSAC. Instead of users specifying arbitrary image URLs when creating a ComputeInstance, administrators register images that point to OCI-compatible artifacts in a registry, and users select from this curated list of images. This first milestone focuses on metadata-level image management with out-of-band image upload — OSAC tracks and serves the list of images but does not handle the binary upload itself. The design supports both provider-global images (available to all tenants) and tenant-scoped images (visible only within a single tenant).

## Terminology

- **ComputeImage**: An OSAC API resource representing a registered VM image. It contains metadata (name, description, OS info) and a reference to an OCI artifact in a registry. ComputeImages are the unit of selection when creating a ComputeInstance.
- **OCI artifact**: An Open Container Initiative-compatible image stored in a container registry. VM disk images can be packaged as OCI artifacts and imported by KubeVirt into DataVolumes for use as root disks.
- **Global image**: A ComputeImage created by a provider administrator with no tenant set (`metadata.tenant` is empty). Visible to all tenants.
- **Tenant image**: A ComputeImage created by a tenant administrator. The server automatically sets `metadata.tenant` to the caller's tenant, scoping visibility to that tenant only.
- **Out-of-band upload**: The process of pushing an OCI artifact to a registry outside of OSAC (e.g., using `podman push`, `skopeo copy`, or Quay UI). OSAC does not mediate the upload in this milestone.
- **Image reference**: The OCI image reference string (e.g., `registry.example.com/images/rhel9:latest`) that points to the actual artifact in a registry.

## Motivation

Today, ComputeInstance creation accepts an arbitrary image URL via the `source_ref` field. This has several problems:

1. **No access control**: Any user can point to any image, including untrusted or unauthorized sources.
2. **No discoverability**: Users must know the exact OCI reference — there is no way to list available images.
3. **No governance**: Administrators cannot restrict which images are available to tenants.
4. **No metadata**: Users see raw OCI references with no human-readable context (OS type, version, description).
5. **No consistency**: Different users may use different URLs for the same logical image, making auditing difficult.

Every major cloud provider (AWS AMI, GCP Images, Azure VM Images) treats VM images as managed resources with dedicated APIs. OSAC needs the same to be a credible VM-as-a-Service platform.

### User Stories

**Provider Administrator:**

* As a provider administrator, I want to register base OS images (RHEL, CentOS, Ubuntu) as global ComputeImages so that all tenants can discover and use them without needing to know the underlying OCI reference.

* As a provider administrator, I want to set a human-readable display name and description on each ComputeImage so that users can make informed selections without understanding OCI artifact conventions.

* As a provider administrator, I want to list all registered images (global and tenant-scoped) so that I can audit the list across the platform.

* As a provider administrator, I want to update the metadata of a global image (e.g., change description, fix a typo in the display name) so that I can maintain the platform's list of base images.

* As a provider administrator, I want to delete a global image that is no longer supported so that tenants are not using outdated or insecure base images.

* As a provider administrator, I want to deprecate a global image and specify a replacement so that tenants are warned to migrate before the image becomes obsolete.

* As a provider administrator, I want to mark an obsolete global image so that new VM creation with that image is blocked while existing VMs remain unaffected.

**Tenant Administrator:**

* As a tenant administrator, I want to register custom images for my organization so that my users can create VMs from our internally approved golden images.

* As a tenant administrator, I want to list all images available to my tenant (both global and tenant-scoped) so that I can verify which images my users will see.

* As a tenant administrator, I want to update the metadata of a tenant-scoped image (e.g., change description, deprecate it) so that I can manage my organization's image lifecycle.

* As a tenant administrator, I want to delete a tenant-scoped image that is no longer needed so that my users are not confused by stale entries.

* As a tenant administrator, I want to deprecate a tenant-scoped image and point users to a replacement so that my team migrates to newer images on a clear timeline.

* As a tenant administrator, I want to mark a tenant-scoped image as obsolete so that my users cannot create new VMs with an unsupported image.

**Tenant User:**

* As a tenant user, I want to list all images available to me so that I can choose the right base image for my VM.

* As a tenant user, I want to see the display name, description, OS type, and architecture of each image so that I can make an informed choice without consulting documentation or administrators.

* As a tenant user, I want to create a ComputeInstance that references a ComputeImage by ID so that I use only approved, registered images.

### Goals

1. Provide a dedicated ComputeImage API for registering, listing, and managing VM image metadata.
2. Support two-tier visibility: provider-global images (visible to all tenants) and tenant-scoped images (visible only within a tenant).
3. Allow provider and tenant administrators to register images that reference OCI artifacts in a registry.
4. Expose human-readable metadata (display name, description, OS type, architecture) alongside the technical OCI reference.
5. Update ComputeInstance to reference a registered ComputeImage instead of accepting arbitrary image URLs.
6. Enforce that only registered images can be used for VM creation, preventing use of unvetted sources.

### Non-Goals

1. **Image upload/push**: This milestone does not provide an API for uploading image binaries to a registry. Upload is performed out-of-band.
2. **VM snapshot/export**: Creating images from running VMs (snapshot-to-image workflow) is a future capability.
3. **Image scanning or vulnerability analysis**: Integration with security scanning tools is deferred.
4. **Registry management**: OSAC does not deploy, configure, or manage the underlying container registry in this milestone.
5. **Container image management**: This proposal covers VM disk images only, not general container images or AI model artifacts.
6. **Quota or rate limiting**: Resource quotas on the number of images per tenant are deferred to the quota system proposal.
7. **Image versioning or tagging**: Tracking multiple versions of the same logical image (e.g., RHEL 9.1, 9.2, 9.3) is left to the administrator's naming conventions for now.
8. **Image caching on workload clusters**: This milestone does not change the osac-operator's image handling. Pre-pulling or caching images on target clusters for faster VM startup is out of scope.
9. **Private registry authentication**: This milestone assumes the OCI registry referenced by `source_ref` is accessible without additional credentials from the workload cluster. Authentication to private registries (e.g., pull secrets, registry credentials management) is not addressed. A future milestone will either add private registry support with credential management, or make it unnecessary by requiring all images to be uploaded to an OSAC-managed registry via the planned upload API.

## Proposal

### Overview

A new **ComputeImage** resource is added to the OSAC fulfillment-service API. ComputeImages are registered by administrators (provider or tenant level) and represent VM images stored as OCI artifacts in a container registry. Each ComputeImage record holds:

- A human-readable display name and description
- The OCI image reference pointing to the actual artifact
- OS metadata (type, version, architecture)
- Tenant scoping via `metadata.tenant` (empty = global, set = tenant-scoped)

Users interact with ComputeImages through List and Get operations. When creating a ComputeInstance, the user specifies a ComputeImage ID instead of a raw image URL.

### Workflow Description

**Actors:**

- **Provider administrator**: Manages the OSAC platform. Can create global ComputeImages visible to all tenants.
- **Tenant administrator**: Manages resources within a tenant. Can create tenant-scoped ComputeImages.
- **Tenant user**: Consumes resources within a tenant. Can list/get ComputeImages and reference them in ComputeInstances.

#### Image Management (Provider Administrator)

**Creating a Global ComputeImage**

1. Provider administrator uploads a VM disk image to the platform's OCI registry out-of-band (e.g., using `skopeo copy` or the Quay UI).
2. Provider administrator uses the OSAC CLI to register the image:
   ```bash
   osac create compute-image \
     --display-name "Red Hat Enterprise Linux 9.4" \
     --description "RHEL 9.4 base image with cloud-init support" \
     --source-ref "registry.internal.example.com/osac-images/rhel9:9.4" \
     --os-type linux \
     --os-version "RHEL 9.4" \
     --architecture amd64 \
     --min-cpus 2 \
     --min-memory-mib 2048 \
     --min-disk-gib 20
   ```
3. The Fulfillment Service validates the request and creates the ComputeImage resource with `metadata.tenant` empty (global).
4. The image is immediately available (state=AVAILABLE by default) to all tenants.

**Deprecating a ComputeImage**

1. Provider administrator marks a ComputeImage as deprecated with optional transition timeline:
   ```bash
   osac update compute-image <image-id> \
     --state DEPRECATED \
     --replacement <replacement-image-id> \
     --obsolete-at 2026-12-31T23:59:59Z
   ```
2. The Fulfillment Service updates the ComputeImage state and records deprecation metadata (current timestamp as `deprecated`, future timestamp as `obsolete`).
3. The image remains visible in `ListComputeImages` for all users.
4. New VM creation requests succeed but return a warning: *"ComputeImage 'rhel9-9.3' is deprecated and will become obsolete on 2026-12-31. Consider migrating to 'rhel9-9.4'."*
5. Existing ComputeInstances are unaffected — they retain their resolved OCI reference.
6. **Note:** Phase 1 does not include automatic state transitions — the administrator must manually transition to OBSOLETE on or after the obsolete date.

**Obsoleting a ComputeImage**

1. Provider administrator marks a ComputeImage as obsolete to prevent new VM creation:
   ```bash
   osac update compute-image <image-id> --state OBSOLETE
   ```
2. The Fulfillment Service updates the ComputeImage state and records the obsolete timestamp.
3. The image is hidden from `ListComputeImages` by default (unless explicitly filtered by state).
4. `GetComputeImage` returns any image regardless of state, so direct lookups still work.
5. Existing ComputeInstances using this image continue to run unchanged.
6. New VM creation requests with this image are rejected with 409 Conflict.

**Updating a ComputeImage**

1. Provider administrator updates mutable fields on a ComputeImage:
   ```bash
   osac update compute-image <image-id> \
     --display-name "Red Hat Enterprise Linux 9.4 (Updated)" \
     --description "RHEL 9.4 base image with cloud-init and security patches"
   ```
2. The Fulfillment Service validates and applies the update. Mutable fields: `display_name`, `description`, `os_version`, `architecture`, `min_requirements`.
3. The `source_ref` is immutable — to point to a new artifact version, create a new ComputeImage and delete the old one.

**Deleting a ComputeImage**

1. Provider administrator attempts to delete a ComputeImage:
   ```bash
   osac delete compute-image <image-id>
   ```
2. The Fulfillment Service checks if any active ComputeInstances reference this image.
3. If in use: deletion is rejected with 409 Conflict: *"ComputeImage is in use by at least one ComputeInstance"*.
4. If not in use: soft-delete succeeds (sets `deleted_at`, record is excluded from list/get queries but retained in the database).

#### Image Management (Tenant Administrator)

**Creating a Tenant-Scoped ComputeImage**

1. Tenant administrator uploads a custom image to the registry out-of-band.
2. Tenant administrator uses the OSAC CLI to register the image:
   ```bash
   osac create compute-image \
     --display-name "Custom RHEL 9 with GPU Drivers" \
     --description "RHEL 9.4 with NVIDIA GPU drivers pre-installed" \
     --source-ref "registry.internal.example.com/tenant-acme/rhel9-gpu:v2" \
     --os-type linux \
     --os-version "RHEL 9.4" \
     --architecture amd64
   ```
3. The Fulfillment Service validates the request and automatically sets `metadata.tenant` to the caller's tenant.
4. The image is visible only to users within that tenant.

Tenant administrators can also deprecate, obsolete, update, and delete their own tenant-scoped images using the same commands shown above for provider administrators. Tenant administrators cannot modify or delete global images or other tenants' images.

#### VM Creation Using a ComputeImage (Tenant User)

**Listing Available ComputeImages**

1. Tenant user lists available images:
   ```bash
   osac list compute-images
   ```
2. The Fulfillment Service returns AVAILABLE and DEPRECATED images (OBSOLETE images can be included via filter parameter). Results include both global images and the user's tenant-scoped images:
   ```json
   {
     "items": [
       {
          "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
          "metadata": {
            "tenant": ""
          },
          "display_name": "Red Hat Enterprise Linux 9.4",
          "description": "RHEL 9.4 base image with cloud-init support",
          "source_ref": "registry.internal.example.com/osac-images/rhel9:9.4",
          "os_type": "linux",
          "os_version": "RHEL 9.4",
          "architecture": "amd64",
          "min_requirements": {
            "min_cpus": 2,
            "min_memory_mib": 2048,
            "min_disk_gib": 20
          },
          "state": "AVAILABLE"
       },
       {
          "id": "948c850b-5670-478d-b4be-e16642f88b9b",
          "metadata": {
            "tenant": ""
          },
          "display_name": "Red Hat Enterprise Linux 9.3",
          "description": "RHEL 9.3 base image (deprecated)",
          "source_ref": "registry.internal.example.com/osac-images/rhel9:9.3",
          "os_type": "linux",
          "os_version": "RHEL 9.3",
          "architecture": "amd64",
          "state": "DEPRECATED",
          "deprecation": {
            "replacement": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "deprecated": "2026-06-01T00:00:00Z",
            "obsolete": "2026-12-31T23:59:59Z"
          }
       },
       {
          "id": "6997aa1a-7bcc-4b14-bf1e-18d91fb64e33",
          "metadata": {
            "tenant": "0c9e7c27-8558-4641-84cb-c72daf811de7"
          },
          "display_name": "Custom RHEL 9 with GPU Drivers",
          "description": "RHEL 9.4 with NVIDIA GPU drivers pre-installed",
          "source_ref": "registry.internal.example.com/tenant-acme/rhel9-gpu:v2",
          "os_type": "linux",
          "os_version": "RHEL 9.4",
          "architecture": "amd64",
          "state": "AVAILABLE"
       }
     ]
   }
   ```

**Creating a VM with a ComputeImage**

1. Tenant user creates a VM specifying a ComputeImage:
   ```bash
   osac create compute-instance my-vm \
     --compute-image a1b2c3d4-e5f6-7890-abcd-ef1234567890 \
     --instance-type standard-4-16 \
     --boot-disk-gib 50
   ```
2. The Fulfillment Service validates and resolves:
   - ComputeImage `a1b2c3d4-...` exists and is visible to the user's tenant
   - Image state is AVAILABLE or DEPRECATED
   - Retrieves the `source_ref` from the ComputeImage
   - If state is DEPRECATED, includes warning in `CreateComputeInstanceResponse.warnings` field
3. The API returns `CreateComputeInstanceResponse`:
   ```json
   {
     "compute_instance": { /* ComputeInstance resource */ },
     "warnings": []
   }
   ```
4. The Fulfillment Service creates the ComputeInstance CR with the resolved OCI reference:
   ```yaml
   apiVersion: osac.openshift.io/v1alpha1
   kind: ComputeInstance
   metadata:
     name: my-vm
   spec:
     compute_image: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
     instance_type: "standard-4-16"
     boot_disk:
       size_gib: 50
     image:
       source_type: "registry"
       source_ref: "registry.internal.example.com/osac-images/rhel9:9.4"
   ```
5. The osac-operator reconciles the ComputeInstance, reading the resolved `source_ref` from the image spec.
6. The VM is provisioned via KubeVirt using the OCI artifact from the registry.

**Error Cases**

**Non-existent ComputeImage:**
```bash
$ osac create compute-instance my-vm --compute-image nonexistent-id
Error: compute image "nonexistent-id" not found
```

**ComputeImage not visible to tenant:**
```bash
$ osac create compute-instance my-vm --compute-image <other-tenants-image-id>
Error: compute image "<other-tenants-image-id>" not found
```

**OBSOLETE ComputeImage:**
```bash
$ osac create compute-instance my-vm --compute-image <obsolete-image-id>
Error: ComputeImage 'rhel9-9.3' is obsolete and cannot be used for new VMs
```

**Missing ComputeImage:**
```bash
$ osac create compute-instance my-vm --instance-type standard-4-16
Error: compute_image field is required
```

#### Image Lifecycle Summary

**API behavior by state:**

| State | VM creation | List visibility | Get visibility |
|-------|-------------|-----------------|----------------|
| AVAILABLE | Succeeds | Shown by default | Always returned |
| DEPRECATED | Succeeds with warning | Shown by default | Always returned |
| OBSOLETE | Rejected (409 Conflict) | Hidden by default (requires explicit filter) | Always returned |

**Validation rules:**

- When transitioning to DEPRECATED: if an `obsolete` timestamp is provided, it must be in the future.
- When transitioning to OBSOLETE: the `obsolete` timestamp can be in the past or future (it represents when the image became or becomes obsolete).
- The `deprecated` timestamp is auto-populated with the current time on the DEPRECATED transition if not explicitly set.
- Phase 1 does not include automatic state transitions — the administrator must manually transition an image to OBSOLETE on or after the planned obsolete date.

### API Extensions

This enhancement introduces a new ComputeImage resource and modifies existing OSAC APIs:

#### New Resources

**ComputeImage** (`proto/public/osac/public/v1/compute_image_type.proto`)
- Represents a registered VM image stored as an OCI artifact in a container registry
- Contains metadata (display name, description, OS info) and a reference to an OCI artifact
- Supports two-tier visibility: global (visible to all tenants) and tenant-scoped

**ComputeImages Service** (`proto/public/osac/public/v1/compute_images_service.proto`)
- Public API: ListComputeImages, GetComputeImage, CreateComputeImage, UpdateComputeImage, DeleteComputeImage
- Private API: Same as public, plus SignalComputeImage (included for consistency with the established private API pattern; no active consumers in this milestone)

#### Modified Resources

**ComputeInstanceSpec** (`proto/public/osac/public/v1/compute_instance_type.proto`)
- Replace: `image` field (ComputeInstanceImage with `source_type`/`source_ref`) with `compute_image` field (string, required) — reference to ComputeImage by ID
- Note: The fulfillment-service resolves the `compute_image` ID to the OCI `source_ref` when creating the CR. The osac-operator continues to receive the resolved OCI reference, unchanged from today.

**CreateComputeInstanceResponse** (`proto/public/osac/public/v1/compute_instances_service.proto`)
- Add: `warnings` field (`repeated string`) — surfaces deprecation notices when creating a VM with a DEPRECATED image

**ComputeInstanceTemplate** (`proto/public/osac/public/v1/compute_instance_template_type.proto`)
- Add: `compute_image` field (string) — reference to ComputeImage by ID, replacing inline image specification

#### Proto Definition Sketch

```proto
// proto/public/osac/public/v1/compute_image_type.proto
enum ComputeImageState {
  COMPUTE_IMAGE_STATE_UNSPECIFIED = 0;
  AVAILABLE = 1;     // Fully available for new VM creation
  DEPRECATED = 2;    // Available with warnings, migration recommended
  OBSOLETE = 3;      // Not available for new VMs, visible for direct lookups only
}

message ComputeImageDeprecation {
  string replacement = 1;                        // Optional: suggested replacement ComputeImage ID
  optional google.protobuf.Timestamp deprecated = 2;  // When deprecation was announced (auto-set on DEPRECATED transition)
  optional google.protobuf.Timestamp obsolete = 3;    // When it becomes/became obsolete (admin-specified or auto-set)
}

message ComputeImageRequirements {
  optional int32 min_cpus = 1;                   // Minimum CPU cores required
  optional int32 min_memory_mib = 2;             // Minimum memory in MiB
  optional int32 min_disk_gib = 3;               // Minimum disk size in GiB
}

message ComputeImageSpec {
  string display_name = 1;                       // Human-readable name (e.g., "Red Hat Enterprise Linux 9.4")
  string description = 2;                        // Detailed description of the image
  string source_ref = 3 [(google.api.field_behavior) = IMMUTABLE];  // OCI image reference (immutable)
  string os_type = 4 [(buf.validate.field).string.min_len = 1];     // "linux", "windows"
  optional string os_version = 5;                // e.g., "RHEL 9.4", "Windows Server 2022"
  string architecture = 6 [(buf.validate.field).string.min_len = 1]; // "amd64", "arm64"
  optional ComputeImageRequirements min_requirements = 7;
}

message ComputeImageStatus {
  ComputeImageState state = 1;                   // Lifecycle state
  optional ComputeImageDeprecation deprecation = 2;  // Present when state is DEPRECATED or OBSOLETE
}

message ComputeImage {
  string id = 1;                                 // System-generated UUID (primary identifier)
  Metadata metadata = 2;                         // Standard metadata (tenant, labels, annotations, timestamps)
  ComputeImageSpec spec = 3;                     // Image specification
  ComputeImageStatus status = 4;                 // Current status
}

// proto/public/osac/public/v1/compute_images_service.proto
service ComputeImages {
  rpc List(ListComputeImagesRequest) returns (ListComputeImagesResponse) {
    option (google.api.http) = {
      get: "/api/fulfillment/v1/compute_images"
    };
  };
  rpc Get(GetComputeImageRequest) returns (ComputeImage) {
    option (google.api.http) = {
      get: "/api/fulfillment/v1/compute_images/{id}"
    };
  };
  rpc Create(CreateComputeImageRequest) returns (ComputeImage) {
    option (google.api.http) = {
      post: "/api/fulfillment/v1/compute_images"
      body: "*"
    };
  };
  rpc Update(UpdateComputeImageRequest) returns (ComputeImage) {
    option (google.api.http) = {
      patch: "/api/fulfillment/v1/compute_images/{id}"
      body: "*"
    };
  };
  rpc Delete(DeleteComputeImageRequest) returns (google.protobuf.Empty) {
    option (google.api.http) = {
      delete: "/api/fulfillment/v1/compute_images/{id}"
    };
  };
}

// proto/private/osac/private/v1/compute_images_service.proto
service ComputeImages {
  rpc Create(CreateComputeImageRequest) returns (ComputeImage);
  rpc Update(UpdateComputeImageRequest) returns (ComputeImage);
  rpc Delete(DeleteComputeImageRequest) returns (google.protobuf.Empty);
  rpc List(ListComputeImagesRequest) returns (ListComputeImagesResponse);
  rpc Get(GetComputeImageRequest) returns (ComputeImage);
  rpc Signal(SignalComputeImageRequest) returns (SignalComputeImageResponse);
}
```

**API vs CR Schema:**

The fulfillment-service API and the Kubernetes CR have different schemas. The API introduces `compute_image` as the image selection field, while the CR retains the existing `image` block with the resolved OCI reference.

**Public API Schema (proto/public/osac/public/v1/):**
```proto
message ComputeInstanceSpec {
  string template = 1;
  map<string, google.protobuf.Any> template_parameters = 2;
  optional google.protobuf.Timestamp restart_requested_at = 3;
  string compute_image = 4 [(buf.validate.field).string.min_len = 1];
  string instance_type = 5;
  optional string ssh_key = 7;
  optional ComputeInstanceDisk boot_disk = 8;
  repeated ComputeInstanceDisk additional_disks = 9;
  optional string run_strategy = 10;
  optional string user_data = 11;
  optional string subnet = 12;
  repeated string security_groups = 13;
}

// CreateComputeInstanceResponse includes warnings for DEPRECATED images
message CreateComputeInstanceResponse {
  ComputeInstance compute_instance = 1;
  repeated string warnings = 2;  // e.g., "ComputeImage 'rhel9-9.3' is deprecated and will become obsolete on 2026-12-31. Consider migrating to 'rhel9-9.4'."
}
```

**Kubernetes CR Schema (osac-operator CRD):**
```yaml
# ComputeInstance CR (created by fulfillment-service)
apiVersion: osac.openshift.io/v1alpha1
kind: ComputeInstance
metadata:
  name: my-vm
spec:
  template: "..."
  compute_image: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"  # ComputeImage ID for audit trail
  image:
    source_type: "registry"
    source_ref: "registry.internal.example.com/osac-images/rhel9:9.4"  # Resolved from ComputeImage
  boot_disk:
    size_gib: 50
  # ... other fields unchanged
```

The CR retains the `image` block with the resolved `source_ref` (unchanged from today) so osac-operator requires no modifications. The `compute_image` field is stored in the CR for audit purposes. The indirection from ComputeImage ID to OCI reference is handled entirely in the fulfillment-service.

#### Validation

**Public API (Tenant Users — ComputeInstance creation):**
- CreateComputeInstance: Require `compute_image` field (ComputeImage ID), reject if missing
- CreateComputeInstance: Validate ComputeImage exists and is visible to the caller's tenant (global or same tenant)
- CreateComputeInstance: If state is AVAILABLE, proceed normally
- CreateComputeInstance: If state is DEPRECATED, succeed but include warning in `CreateComputeInstanceResponse.warnings` with replacement suggestion (if set) and obsolete timestamp (if set)
- CreateComputeInstance: If state is OBSOLETE, reject with HTTP 409 Conflict ("ComputeImage is obsolete and cannot be used for new VMs")
- CreateComputeInstance: If ComputeImage ID not found or not visible to tenant, reject with HTTP 404 Not Found
- CreateComputeInstance: Resolve ComputeImage `source_ref` and pass to underlying provisioning system
- UpdateComputeInstance: Reject changes to `compute_image` field (immutable)

**Public API (Administrators — ComputeImage management):**
- CreateComputeImage: Require `source_ref`, `os_type`, and `architecture` fields
- CreateComputeImage: Validate `source_ref` is a valid OCI image reference format
- CreateComputeImage: Default state to AVAILABLE if not specified
- CreateComputeImage: Provider admin creates global images (`metadata.tenant` empty); tenant admin creates tenant-scoped images (`metadata.tenant` auto-set to caller's tenant)
- CreateComputeImage: Tenant users cannot create images (authorization rejection)
- UpdateComputeImage: Reject changes to `source_ref` (immutable after creation)
- UpdateComputeImage: Allow changes to `display_name`, `description`, `os_version`, `architecture`, `min_requirements`, `state`, and `deprecation` fields
- UpdateComputeImage: When transitioning to DEPRECATED, auto-populate `deprecation.deprecated` timestamp (set to current time) if not provided
- UpdateComputeImage: When transitioning to OBSOLETE, auto-populate `deprecation.obsolete` timestamp (set to current time) if not provided
- UpdateComputeImage: If `deprecation.obsolete` is provided when transitioning to DEPRECATED, validate it is in the future
- UpdateComputeImage: If `deprecation.obsolete` is provided when transitioning to OBSOLETE, allow any timestamp (past or future)
- UpdateComputeImage: API behavior is based on state field, not timestamps
- UpdateComputeImage: Tenant admin can only update own tenant's images; provider admin can update any
- DeleteComputeImage: Reject if any active ComputeInstances reference this image (409 Conflict)
- DeleteComputeImage: Tenant admin can only delete own tenant's images; provider admin can delete any

#### Deletion Protection

**ComputeImage deletion checks:**
- fulfillment-service queries database for active ComputeInstances referencing this ComputeImage ID
- If any references exist, deletion is rejected with 409 Conflict
- Returns descriptive error message: *"ComputeImage is in use by at least one ComputeInstance"*
- Deletion succeeds only when no active ComputeInstances reference the image
- Alternative to deletion: transition image to OBSOLETE to prevent new usage while existing VMs wind down

#### Authorization Model

| Operation | Provider Admin | Tenant Admin | Tenant User |
|-----------|---------------|--------------|-------------|
| CreateComputeImage (global) | Yes | No | No |
| CreateComputeImage (tenant-scoped) | Yes | Yes (own tenant) | No |
| ListComputeImages | All | Global + own tenant | Global + own tenant |
| GetComputeImage | All | Global + own tenant | Global + own tenant |
| UpdateComputeImage | All | Own tenant only | No |
| DeleteComputeImage | All | Own tenant only | No |

### Implementation Details/Notes/Constraints

#### Database Schema

A new `compute_images` table in the fulfillment-service PostgreSQL database:

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key |
| creation_timestamp | TIMESTAMPTZ | Creation time |
| deletion_timestamp | TIMESTAMPTZ | Soft delete |
| finalizers | TEXT[] | Finalizer list |
| creators | TEXT[] | Who created the record |
| tenants | TEXT[] | Tenant scoping; empty array = global (visible to all tenants) |
| labels | JSONB | Indexed labels |
| annotations | JSONB | Annotations |
| data | JSONB | Serialized ComputeImage protobuf (display_name, description, source_ref, os_type, os_version, architecture, min_requirements) |

The `data` JSONB column contains the serialized ComputeImage protobuf. Resource-specific fields are stored inside `data` rather than as individual columns, following the fulfillment-service convention.

Example of a global ComputeImage `data` value:
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "display_name": "Red Hat Enterprise Linux 9.4",
  "description": "RHEL 9.4 base image for general-purpose workloads",
  "source_ref": "registry.example.com/osac-images/rhel9:9.4",
  "os_type": "linux",
  "os_version": "RHEL 9.4",
  "architecture": "amd64",
  "min_requirements": {
    "min_cpus": 2,
    "min_memory_mib": 2048,
    "min_disk_gib": 20
  },
  "state": "COMPUTE_IMAGE_STATE_AVAILABLE",
}
```

Example of a tenant ComputeImage `data` value:
```json
{
  "id": "6997aa1a-7bcc-4b14-bf1e-18d91fb64e33",
  "metadata": {
    "tenant": "0c9e7c27-8558-4641-84cb-c72daf811de7"
  },
  "display_name": "Red Hat Enterprise Linux 9.4",
  "description": "RHEL 9.4 base image for general-purpose workloads",
  "source_ref": "registry.example.com/osac-images/rhel9:9.4",
  "os_type": "linux",
  "os_version": "RHEL 9.4",
  "architecture": "amd64",
  "min_requirements": {
    "min_cpus": 2,
    "min_memory_mib": 2048,
    "min_disk_gib": 20
  },
  "state": "COMPUTE_IMAGE_STATE_AVAILABLE",
}
```

Example of a global ComputeImage `data` value with deprecation metadata:
```json
{
  "id": "948c850b-5670-478d-b4be-e16642f88b9b",
  "display_name": "Red Hat Enterprise Linux 9.4",
  "description": "RHEL 9.4 base image for general-purpose workloads",
  "source_ref": "registry.example.com/osac-images/rhel9:9.4",
  "os_type": "linux",
  "os_version": "RHEL 9.4",
  "architecture": "amd64",
  "min_requirements": {
    "min_cpus": 2,
    "min_memory_mib": 2048,
    "min_disk_gib": 20
  },
  "state": "COMPUTE_IMAGE_STATE_DEPRECATED",
  "deprecation": {
    "replacement": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "deprecated": "2026-06-01T00:00:00Z",
    "obsolete": "2026-12-31T23:59:59Z"
  }
}
```

#### List Filtering

The `ListComputeImages` RPC supports filtering via the standard OSAC SQL-like filter syntax:

- `os_type = 'linux'` — only Linux images
- `architecture = 'amd64'` — only amd64 images
- `display_name LIKE '%RHEL%'` — search by name
- `state IN (AVAILABLE, DEPRECATED, OBSOLETE)` — include obsolete images in results

By default, `ListComputeImages` returns images in AVAILABLE and DEPRECATED states. OBSOLETE images are hidden from default results and require an explicit state filter. `GetComputeImage` returns any image regardless of state.

The List operation automatically scopes results: tenant users see global images plus their own tenant's images. Provider administrators see all images.

#### ComputeInstance Creation Flow

When a user creates a ComputeInstance referencing a ComputeImage:

1. The fulfillment-service resolves the `compute_image` ID.
2. It verifies the ComputeImage exists and is visible to the user's tenant.
3. It checks the image's state:
   - **AVAILABLE**: Proceeds normally.
   - **DEPRECATED**: Proceeds, but includes a warning in the `CreateComputeInstanceResponse.warnings` field with the deprecation details (obsolete date and replacement suggestion, if set).
   - **OBSOLETE**: Rejects the request with 409 Conflict.
4. It retrieves the `source_ref` from the ComputeImage and passes it to the underlying provisioning system (osac-operator/KubeVirt).
5. If the ComputeImage is not found or not visible to the tenant, the request is rejected with a descriptive error. If the OCI artifact is unreachable or invalid, the error surfaces at VM provisioning time (from KubeVirt).

#### osac-operator Integration

The osac-operator does not need a new CRD for ComputeImage — image management is purely a fulfillment-service concern for this milestone. The operator continues to receive the resolved OCI reference in the ComputeInstance CR's spec, just as it does today. The indirection from ComputeImage ID to OCI reference is handled entirely in the fulfillment-service.

#### Impact on ComputeInstanceTemplate

The `ComputeInstanceTemplate` resource also uses `ComputeInstanceImage`. It will be updated to reference a `compute_image` (ComputeImage ID) instead. Templates that specify an image will point to a registered ComputeImage, ensuring that images are chosen from the list.

### Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Global images visible across all tenants | Potential information leakage if image names/descriptions contain sensitive info | Provider admin is trusted; document that global image metadata is visible to all tenants. |
| Orphaned ComputeImages | Deleted images still referenced by running VMs | Running VMs retain the resolved OCI reference. Only new VM creation is blocked. Document this behavior. |
| Performance of List with many images | A large image list could slow listing | Standard pagination support via `page` and `size` parameters. Index on tenants array. |

### Drawbacks

- **Additional indirection**: Users must now discover and select a ComputeImage before creating a VM, adding a step to the workflow. This is intentional — it trades convenience for governance — but may feel heavy for simple deployments with few images.
- **No upload API**: Requiring out-of-band upload for this milestone means administrators must use separate tooling (skopeo, Quay UI) to push images. This is a deliberate scope limitation but may frustrate administrators who expect a unified experience.

## Alternatives (Not Implemented)

### Alternative 1: Extend ComputeInstance with Image Validation Only

Instead of a new resource, add validation rules to the existing `source_ref` field — for example, an allowlist of permitted registries or image patterns.

**Rejected because**: This provides no discoverability (users can't list available images), no human-readable metadata, and no centralized governance. It addresses only the "prevent arbitrary URLs" goal without solving the list of offering problem.

### Alternative 2: Use CatalogItems for Image Selection

Leverage the proposed CatalogItems system to present images as catalog entries rather than a dedicated ComputeImage resource.

**Rejected because**: CatalogItems are broader (they wrap entire templates with parameter variations) and serve a different purpose. Images are a fundamental building block that should exist as a standalone resource. CatalogItems may reference ComputeImages in the future, but images need their own API for registration and management.

### Alternative 3: ImageClass + ComputeImage (Two-Resource Model)

Introduce an `ImageClass` resource (like NetworkClass) representing different image backends or registries, with ComputeImage referencing an ImageClass.

**Deferred**: For the first milestone with a single registry and metadata-only management, ImageClass adds complexity without clear benefit. If OSAC later supports multiple registries with different capabilities (e.g., scanning-enabled vs. basic), ImageClass can be introduced as a backward-compatible addition.

### Alternative 4: Full Upload API from Day One

Build the ComputeImage API with integrated binary upload (similar to AWS EC2 `ImportImage`).

**Deferred**: Building a reliable image upload pipeline (chunked upload, resumption, progress tracking, virus scanning) is a significant effort that would delay the core image list functionality. The out-of-band upload approach unblocks VM governance immediately while the upload API is designed separately.

## Open Questions

### Should ComputeImage have a structured `name` field (DNS-1035)?

ComputeImage currently has a system-generated `id` (UUID) and a free-text `display_name`. Should it also have a `name` field with DNS-1035 constraints (lowercase alphanumeric and hyphens, max 63 characters, e.g., `rhel9-9-4-base`)?

If so, should `name` replace `id` as the primary reference in `ComputeInstanceSpec.compute_image`? This would allow users to write `compute_image: "rhel9-9-4-base"` instead of `compute_image: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"`, making templates and CLI usage significantly more readable.

**Considerations:**

- **Usability**: Meaningful names are easier to type, remember, and use in automation scripts and templates than UUIDs.
- **Uniqueness scope**: Names would need to be unique within a scope — globally for global images, per-tenant for tenant-scoped images. This mirrors how Kubernetes resources use names within namespaces.
- **Immutability**: If `name` is used as a reference key, it should be immutable after creation (same as `source_ref`), since renaming would break existing ComputeInstance references.
- **Consistency**: Other OSAC resources (VirtualNetwork, Subnet, ComputeInstance) use UUIDs as their primary identifier. Introducing name-based references for ComputeImage alone may be inconsistent — or it may set a precedent for improving usability across the API.

## Future Work

This enhancement establishes the foundation for a complete image management lifecycle. Planned future capabilities include:

- **Image upload API**: A dedicated API for uploading image binaries through OSAC, eliminating the need for out-of-band registry access.
- **VM snapshot/export**: Creating a new ComputeImage from a running ComputeInstance's disk state.
- **Image scanning integration**: Connecting with vulnerability scanning tools and exposing scan results as image metadata.
- **Cross-region image replication**: Automatically replicating images across multiple registries for multi-region deployments.
- **Image policies**: Tenant-level policies restricting which global images are available or requiring approval for new tenant images.
- **User-created images**: Allowing tenant users (not just admins) to register images, with optional admin approval workflows.
- **CatalogItems integration**: CatalogItems (see `/enhancements/catalog-items`) may reference ComputeImages as building blocks — e.g., a catalog entry could combine a ComputeImage with a predefined instance size and network configuration into a one-click deployment template.

## Test Plan

**Unit Tests:**

- ComputeImage CRUD operations via GenericServer
- ComputeImage proto validation rejects missing required fields (source_ref, os_type, architecture)
- ComputeImage source_ref immutability enforcement on update
- ComputeImage mutable field updates (display_name, description, os_version, architecture, min_requirements)
- ComputeInstance validation rejects missing compute_image
- ComputeInstance validation rejects non-existent compute_image
- ComputeInstance validation rejects compute_image not visible to caller's tenant
- ComputeInstance validation rejects OBSOLETE compute_image
- ComputeInstance with DEPRECATED compute_image succeeds with warning (includes obsolete timestamp and replacement in warning)
- ComputeImage state transitions (AVAILABLE → DEPRECATED → OBSOLETE)
- ComputeImage deprecation metadata auto-population (deprecated timestamp on DEPRECATED transition, obsolete timestamp on OBSOLETE transition)
- ComputeImage validation rejects obsolete timestamp in the past when transitioning to DEPRECATED
- ComputeImage deletion rejected when active ComputeInstances reference it
- ListComputeImages default filter excludes OBSOLETE, explicit filter includes it
- ListComputeImages returns deprecation metadata for DEPRECATED/OBSOLETE images
- ListComputeImages tenant scoping: tenant user sees global + own tenant images only
- Provider admin CreateComputeImage with no tenant creates global image
- Tenant admin CreateComputeImage auto-sets metadata.tenant to caller's tenant
- Tenant user CreateComputeImage rejected (authorization)
- Tenant admin cannot update or delete global images
- Tenant admin cannot update or delete another tenant's images

**Integration Tests (fulfillment-service/it/):**

- Create global ComputeImage as provider admin, verify it appears in ListComputeImages for all tenants
- Create tenant-scoped ComputeImage as tenant admin, verify it appears only for that tenant
- Verify tenant A cannot see tenant B's tenant-scoped images
- Create ComputeInstance with valid compute_image, verify VM provisions with correct OCI reference
- Attempt to create ComputeInstance with OBSOLETE compute_image, verify 409 Conflict
- Create ComputeInstance with DEPRECATED compute_image, verify warning message includes deprecation timeline and replacement
- Set ComputeImage to DEPRECATED with future obsolete timestamp and replacement, verify deprecation metadata persisted
- Set ComputeImage to OBSOLETE, verify it disappears from default ListComputeImages results
- Verify GetComputeImage returns any image regardless of state (AVAILABLE, DEPRECATED, OBSOLETE)
- Attempt to delete ComputeImage with active ComputeInstances, verify 409 Conflict rejection
- Delete all referencing ComputeInstances, then delete ComputeImage, verify success
- Attempt to update source_ref on existing ComputeImage, verify rejection (immutability)
- ListComputeImages filtering by os_type, architecture, display_name LIKE, and state
- ListComputeImages pagination with page and size parameters

**End-to-End Tests:**

- Provider admin registers a global ComputeImage via API
- Tenant user lists images and sees the global image
- Tenant admin registers a tenant-scoped ComputeImage
- Tenant user lists images and sees both global and tenant-scoped images
- Tenant user creates ComputeInstance using a ComputeImage reference
- osac-operator provisions KubeVirt VM with the resolved OCI reference from the ComputeImage
- VM reaches Running state
- Provider admin sets global ComputeImage to DEPRECATED with replacement and future obsolete timestamp
- Tenant user lists images and sees DEPRECATED status with deprecation metadata
- Tenant user creates new VM with DEPRECATED image, receives warning with obsolete date and replacement suggestion
- Provider admin sets global ComputeImage to OBSOLETE
- Tenant user no longer sees image in default list (unless explicitly filtered by state)
- Attempt to create new VM with OBSOLETE image fails with 409 Conflict
- Existing VM continues running unaffected
- Multi-tenant isolation: tenant B cannot see tenant A's tenant-scoped images

## Graduation Criteria

Graduation criteria will be defined when targeting a release. Expected stages:

- **Dev Preview**: ComputeImage CRUD API available. ComputeInstance accepts `compute_image` reference.
- **Tech Preview**: Multi-tenant visibility enforced.
- **GA**: Production-hardened. Performance validated at scale. Upgrade/downgrade tested. Documentation complete.

## Upgrade / Downgrade Strategy

Not applicable - OSAC is pre-GA. This is a breaking API change.

## Version Skew Strategy

Not applicable - OSAC is pre-GA. This is a breaking API change.

## Support Procedures

- **User cannot see expected images**: Verify the image's `metadata.tenant` field. Global images have an empty tenant and should be visible to all tenants. Tenant-scoped images should have `metadata.tenant` matching the user's tenant. Use `ListComputeImages` as a provider admin to see all images.
- **ComputeInstance creation fails with "image not found"**: Verify the referenced ComputeImage exists and is visible to the user's tenant.
- **VM fails to start after ComputeInstance creation**: The ComputeImage's `source_ref` may point to an unreachable or invalid OCI artifact. Check KubeVirt/osac-operator logs for image pull errors. Verify the OCI reference is correct and the registry is accessible from the workload cluster.
- **Deleting a ComputeImage**: `DeleteComputeImage` is rejected with 409 Conflict when any active ComputeInstances reference the ComputeImage ID, returning the error *"ComputeImage is in use by at least one ComputeInstance"*. Once all referencing ComputeInstances are removed, deletion proceeds as a soft-delete — the record is marked with `deletion_timestamp` and excluded from queries, but retained in the database. As an alternative to deletion, transition the image to OBSOLETE to prevent new usage while existing VMs wind down.
- **ComputeInstance creation rejected: "ComputeImage is obsolete"**: The API returns 409 Conflict when attempting to create a VM with an OBSOLETE image. Resolution: choose a different image, or ask the administrator to change the image state back to AVAILABLE or DEPRECATED. Prevention: communicate image lifecycle changes (OBSOLETE transitions) to users before making the change.
- **User sees deprecation warning on VM creation**: This is expected behavior when the referenced ComputeImage is in DEPRECATED state. The warning includes the planned obsolete date and suggested replacement (if set). Users should plan to migrate to the replacement image before the obsolete date.
- **User cannot find an image they previously used**: The image may have been transitioned to OBSOLETE state, which hides it from default `ListComputeImages` results. Use `GetComputeImage` with the image ID for a direct lookup (returns any state), or filter the list explicitly with `state IN (AVAILABLE, DEPRECATED, OBSOLETE)` to include obsolete images.

## Infrastructure Needed

No additional infrastructure is required for this enhancement. All work will be done in the existing `fulfillment-service` repository. The container registry is assumed to be pre-deployed as part of the OSAC landing zone installation.
