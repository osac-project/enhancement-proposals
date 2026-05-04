---
title: vm-image-management
authors:
  - avishayt
creation-date: 2026-04-16
last-updated: 2026-04-21
tracking-link:
  - https://redhat.atlassian.net/browse/MGMT-23984
see-also:
  - "/enhancements/vmaas"
replaces:
superseded-by:
---

# VM Image Management

## Summary

This proposal introduces a VM image management API that enables organization users to upload qcow2 virtual machine disk images without requiring direct registry access or OCI tooling knowledge. Uploaded images are wrapped in ContainerDisk format (tar with `/disk/disk.img` structure) and stored as OCI container images in a CSP-owned registry (source of truth, shareable across clusters). When a VM references an image, a local PVC cache is created on-demand for that (image, storageClass) combination. Subsequent VMs clone from the cache using CSI copy-on-write snapshots, eliminating repeated registry pulls.

Additionally, users can create images from running VMs, capturing the complete VM disk state. This enables backup workflows, golden image creation, and cross-cluster VM cloning by exporting the VM to the registry as a new image.

**MVP Scope:** Upload qcow2 images via API, create images from running VMs, store as ContainerDisk-format OCI container images in registry. On-demand PVC caching with garbage collection. Import from HTTP/S3 URLs and image cloning are deferred to future enhancements.

## Motivation

Currently, OSAC VM provisioning works as follows:
- **CSP uploads images**: Cloud Service Provider admins manually push VM images (RHEL, Windows, etc.) to the OCI registry using podman/skopeo
- **Ansible role per image**: Each image has a corresponding Ansible role that knows how to provision VMs from that image
- **Template per role**: ComputeInstance templates are created per Ansible role, exposing specific parameters (cores, memory, storage)
- **Org users consume templates**: Organization users create VMs by selecting a template and providing parameters

This approach has several limitations:

1. **No custom images for org users**: Users cannot upload their own qcow2 images (e.g., custom golden images, pre-configured environments). They must request CSP to upload images and create corresponding Ansible roles/templates.
2. **CSP bottleneck for new images**: Adding a new image requires CSP admin intervention (upload to registry, create Ansible role, create template). Cannot self-service.
3. **No image cloning from running VMs**: Users cannot capture a configured VM as a reusable image for backup or cloning purposes.
4. **Slow VM provisioning**: Each VM creation pulls the image from registry over the network (2-5 minutes per VM, no local caching).
5. **Registry bottleneck at scale**: Creating 100 VMs simultaneously means 100 concurrent registry pulls, even for the same image.
6. **No API discoverability**: Users cannot list available images or query metadata via the OSAC API, only templates.

This proposal introduces an image management API that enables organization users to upload custom qcow2 images and create images from running VMs. Images are stored in the CSP-owned registry (source of truth) and imported to local PVC caches on-demand for fast VM provisioning via CSI copy-on-write clones.

### User Stories

- As an authorized user, I want to upload a Windows Server qcow2 image via the OSAC API so that I can create Windows VMs without learning OCI tooling or managing registry credentials.
- As an authorized user, I want to upload a custom Linux qcow2 image so that I can deploy my pre-configured golden images.
- As an organization user, I want to create an image from a running VM so that I can capture my configured environment as a golden image for future deployments.
- As an organization user, I want to create an image from a VM to backup its current state before making risky changes.
- As an organization user, I want to create a new VM from a user-created image so that I can clone production environments for testing.
- As an organization user, I want to list uploaded images and their metadata via the API so that I can see what images are available.
- As an organization user, I want VM provisioning to be fast (< 30 seconds) so that I can scale my workloads quickly.
- As a Cloud Provider Admin, I want images stored in my registry so that they are shareable across multiple OpenShift clusters (e.g., across availability zones).
- As a Cloud Provider Admin, I want to leverage storage deduplication so that 100 VMs from the same image don't consume 100× storage on each cluster.

### Goals

- Enable organization users to upload qcow2 disk images via HTTP API without OCI tooling or registry access.
- Enable organization users to create images from running VMs (export VM disk state to registry).
- Store uploaded images in CSP-owned registry as OCI container images in ContainerDisk format (source of truth, cross-cluster sharing).
- Import registry images once per cluster to local PVC caches.
- Clone local PVC caches using CSI copy-on-write snapshots for fast VM provisioning.
- Provide metadata API (name, description, OS type, registry reference) for image discovery.
- Support organization-scoped images (private registry namespaces per organization).
- Distinguish between template images (provider-managed) and user-created images (from VMs or uploads).
- Reduce VM provisioning time from minutes (registry pull) to seconds (PVC clone).

### Non-Goals

- Importing images from HTTP/S3 URLs (deferred to future enhancement).
- Importing pre-existing images from external OCI registries (deferred to future enhancement).
- Cloning existing images within OSAC (deferred to future enhancement).
- Provider-managed shared image catalog (deferred to future enhancement).
- Supporting raw, vmdk, or other formats (MVP is qcow2 only).
- Image versioning or tagging (MVP uses auto-generated tags in registry).
- Image scanning or CVE detection (deferred to separate enhancement).
- Managing the OCI registry itself (OSAC uses existing CSP-provided registry, doesn't deploy one).
- Defining specific authorization policies for image uploads (cloud providers configure this via Authorino based on their requirements).
- Adaptive cache TTL based on usage patterns (deferred to future enhancement - MVP uses fixed 1-day TTL).

## Proposal

Introduce a `ComputeImage` custom resource that represents a qcow2 VM disk image uploaded by an authorized user. Images are uploaded via HTTP API, wrapped in ContainerDisk format (tar with `/disk/disk.img` structure), and stored as OCI container images in the CSP-owned registry. When a user creates a ComputeInstance referencing an image, the operator creates a local PVC cache on-demand (if it doesn't exist) by importing from the registry. Subsequent VMs clone from the cache using CSI copy-on-write snapshots, eliminating repeated registry pulls.

**Architecture:**
- **Source of truth:** OCI registry (CSP-owned, shareable across clusters)
- **Per-cluster caching:** PVC caches created on-demand when VMs reference images
  - Cache key: (image, storageClass) - separate cache per storage class
  - First VM: imports from registry to cache (~1-2 minutes)
  - Subsequent VMs: clone from cache (~5 seconds)
- **Garbage collection:** Unused cache PVCs deleted after TTL (default 1 day)

**MVP focuses on upload API with on-demand caching.** Import from HTTP/S3, external registry import, and image cloning are deferred to future enhancements.

### Workflow Description

#### Personas

| Persona | Role | Relevant actions |
|---|---|---|
| **Cloud Provider Admin** | Cloud provider administrator | Configures registry integration; may upload shared/curated images; sets upload authorization policies |
| **Organization Admin** | Organization administrator | May upload custom qcow2 images for the organization (if authorized) |
| **Organization User** | End user within an organization | May upload images or only consume existing ones (policy-dependent); creates VMs from images |

**Note:** Who can upload images is determined by cloud provider policy, not hard-coded in the system. Some clouds may restrict uploads to Cloud Provider Admins only, others may allow Organization Admins, and some may permit any Organization User to upload. This is enforced via Authorino authorization policies on the fulfillment-api Images service.

**Registry configuration:** The CSP configures a registry URL and credentials (pull/push secrets) that OSAC uses to store images. Organizations never access the registry directly.

#### Workflow 1: Authorized user uploads a custom image

**Actors:** Authorized user (could be Cloud Provider Admin, Organization Admin, or Organization User depending on Authorino authorization policy)

1. User has a Windows Server 2022 qcow2 image (15 GB) on their laptop.
2. User uploads via CLI:
   ```bash
   osac image upload windows-server-2022.qcow2 \
     --name windows-2022 \
     --description "Windows Server 2022 Datacenter"
   ```
3. CLI calls fulfillment-api `InitiateUpload` RPC.
4. Fulfillment-service creates Image record in database with `status.state = PENDING`, returns upload URL.
5. CLI streams qcow2 file to fulfillment-service upload endpoint.
6. Fulfillment-service:
   - Wraps uploaded qcow2 in ContainerDisk format (tar with `/disk/disk.img`) on-the-fly
   - Streams to CSP registry as OCI container image (no temporary storage)
   - Calculates SHA256 digest during streaming using io.TeeReader
   - Pushes to registry using OCI distribution spec (e.g., `registry.csp.internal/vm-images/org-acme/windows-2022:v1`)
   - Updates Image record: `status.state = AVAILABLE`, `status.size_bytes = <actual size>`
7. Image now discoverable via `ListImages` API with state=AVAILABLE
   - No ComputeImage CR created yet (lazy creation when first VM references the image)
   - No cache PVC created yet (on-demand import when operator reconciles)
8. Organization user creates VM (first VM using this image on this cluster):
   ```bash
   osac create compute-instance \
     --name web-server \
     --image windows-2022 \
     --cores 4 \
     --memory 8 \
     --storage-class ceph-fast
   ```
9. Operator reconciles ComputeInstance:
   - Queries fulfillment-service for image metadata (registry URL, digest)
   - Checks if ComputeImage CR exists for this image
   - **Not found (first VM on this cluster):** Creates ComputeImage CR with `spec.source` pointing to registry URL
   - Checks for cache PVC `vm-image-cache-windows-2022-ceph-fast`:
     - **Not found (first VM with this storageClass):** Creates DataVolume importing from registry to cache PVC with `storageClass: ceph-fast` (~1-2 minutes)
     - **Found (subsequent VMs):** Reuses existing cache PVC
   - **Note:** Cache PVC uses the same storage class (`ceph-fast`) as the VM to enable CSI smart clones
10. Operator creates VM's root disk DataVolume:
   - If cache just created: wait for it to be ready, then clone
   - If cache exists: clone immediately
11. Operator creates VirtualMachine referencing the root disk DataVolume (same pattern as current OSAC).
12. VM boots from cloned disk.

**Subsequent VMs:** Steps 9-12 but cache already exists → clone immediately (~5 seconds total).

**Expected result:** User uploads qcow2 without registry knowledge. Image stored in registry (shareable across clusters). VMs provision in seconds via PVC clones from local cache.

#### Workflow 2: Organization user creates image from running VM

**Actors:** Organization user

**Use case:** User has configured a production VM and wants to capture its current state as a golden image for cloning.

1. User has a running VM (`web-server`) that they've configured with applications and settings.
2. User creates an image from the VM via CLI:
   ```bash
   osac image create-from-vm web-server \
     --name web-server-golden \
     --description "Production web server configuration - April 2026"
   ```
3. CLI calls fulfillment-api `CreateImageFromVM` RPC.
4. Fulfillment-service:
   - Creates Image record in database with `status.state = PENDING`
   - Creates `ComputeImageExportJob` CR in the operator namespace:
   ```yaml
   apiVersion: osac.openshift.io/v1alpha1
   kind: ComputeImageExportJob
   metadata:
     name: export-web-server-golden
     namespace: org-acme
   spec:
     vmName: web-server
     imageName: web-server-golden
     description: "Production web server configuration - April 2026"
     ttlSecondsAfterFinished: 86400  # 24 hours
   ```
5. Operator watches `ComputeImageExportJob` and reconciles:
   - Creates `VirtualMachineExport` CR (KubeVirt resource) for the running VM
   - Waits for VirtualMachineExport to be Ready (polls status)
   - Downloads exported qcow2 from VirtualMachineExport endpoint
   - Wraps qcow2 in ContainerDisk format (tar with `/disk/disk.img`) on-the-fly
   - Streams to registry as OCI container image (e.g., `registry.csp.internal/vm-images/org-acme/web-server-golden:v1`)
   - Calculates SHA256 digest
   - Updates `ComputeImageExportJob.status`:
     ```yaml
     status:
       phase: Complete
       completionTime: "2026-04-26T12:00:00Z"
       registryURL: "registry.csp.internal/vm-images/org-acme/web-server-golden:v1"
       digest: "sha256:abc123..."
       virtualMachineExportName: "export-web-server-abc123"
     ```
6. Fulfillment-service watches `ComputeImageExportJob` status (via Signal RPC or polling).
7. When status.phase = Complete, fulfillment-service updates Image record: `status.state = AVAILABLE`, `status.size_bytes` from export, registry URL from status.
8. Image now available via `ListImages` API with state=AVAILABLE and metadata indicating it was created from a VM.
   - No ComputeImage CR created yet (lazy creation when first VM references the image)
   - No cache PVC created yet (on-demand import when operator reconciles)
9. After TTL expires (24 hours), operator garbage collects both `ComputeImageExportJob` and `VirtualMachineExport` CRs (via finalizer).
10. Organization user creates new VM from the image:
   ```bash
   osac create compute-instance \
     --name web-server-test \
     --image web-server-golden \
     --cores 4 \
     --memory 8
   ```
11. Operator follows standard image workflow:
    - Creates cache PVC if needed (on-demand import from registry)
    - Clones cache to create VM root disk
    - VM boots with identical disk state as source VM

**Expected result:** User captures configured VM as reusable image. Image stored in registry (cross-cluster sharing, survives cluster failure). New VMs can be created from the image following standard workflow.

**Benefits over VM snapshots:**
- Image survives cluster failure (stored in registry, not cluster-local VolumeSnapshot)
- Cross-cluster cloning (create VM from image on any cluster with access to registry)
- Aligns with cloud-native patterns (AWS AMI, Azure Managed Images, GCP Custom Images)

### API Extensions

#### ComputeImage CRD

New custom resource representing a VM disk image:

```yaml
apiVersion: osac.openshift.io/v1alpha1
kind: ComputeImage
metadata:
  name: windows-2022
  namespace: org-acme
spec:
  # Human-readable description
  description: "Windows Server 2022 Datacenter with security hardening"

  # Source reference (MVP: OCI registry URL, future: S3, HTTP)
  source: "registry.csp.internal/vm-images/org-acme/windows-2022:v1"

# Note: Human-friendly name is in metadata.name (Kubernetes standard), not spec

status:
  # Cache PVCs tracked by operator (one per storage class)
  # Used for reconciliation, GC decisions, and avoiding PVC list operations
  caches:
    - storageClass: ceph-fast
      pvcName: vm-image-cache-windows-2022-a1b2c3d4
      phase: Ready                    # Pending, Importing, Ready, Failed
      lastUsedTime: "2026-04-26T12:00:00Z"
      sizeGiB: 15
      message: ""                     # Error message if phase = Failed

    - storageClass: ceph-slow
      pvcName: vm-image-cache-windows-2022-e5f6g7h8
      phase: Ready
      lastUsedTime: "2026-04-25T10:00:00Z"
      sizeGiB: 15
      message: ""

  # Overall conditions
  conditions:
    - type: Available
      status: "True"
      lastTransitionTime: "2026-04-26T11:00:00Z"
      reason: RegistryImageReady
      message: "Image available in registry"
```

**Note:** ComputeImage CR is created lazily by the operator when the first VM on that cluster references the image. Cache PVCs are created on-demand per (image, storageClass) combination. Image metadata lives in the fulfillment-service database; the CR is purely an operator reconciliation artifact for cache management.

**Status usage (operator-internal):**
- `status.caches`: Tracks cache PVC state per storage class for reconciliation (avoid listing all PVCs to find caches)
- `lastUsedTime`: Updated when VMs reference the cache, used for TTL-based garbage collection
- `phase`: Import progress (Pending → Importing → Ready or Failed)
- End users don't see this status (they query fulfillment-service Image API, not CRDs)
- Future enhancement: Expose cache metrics to CSPs via Prometheus or admin API for observability

#### ComputeImageExportJob CRD

New custom resource for exporting a running VM to an image:

```yaml
apiVersion: osac.openshift.io/v1alpha1
kind: ComputeImageExportJob
metadata:
  name: export-web-server-golden
  namespace: org-acme
  finalizers:
    - osac.openshift.io/cleanup-export  # Ensures VirtualMachineExport is cleaned up
spec:
  # Source VM to export
  vmName: web-server

  # Name for the resulting image
  imageName: web-server-golden

  # Human-readable description for the image
  description: "Production web server configuration - April 2026"

  # TTL for garbage collection (both this CR and VirtualMachineExport)
  ttlSecondsAfterFinished: 86400  # 24 hours (default)

status:
  # Current phase of the export operation
  # Valid values: Pending, Exporting, Uploading, Complete, Failed
  phase: Complete

  # Time when the export completed (success or failure)
  completionTime: "2026-04-26T12:00:00Z"

  # Registry URL where the image was uploaded
  registryURL: "registry.csp.internal/vm-images/org-acme/web-server-golden:v1"

  # SHA256 digest of the uploaded image
  digest: "sha256:abc123..."

  # Name of the VirtualMachineExport CR created for this export
  virtualMachineExportName: "export-web-server-abc123"

  # Error message if phase = Failed
  error: ""

  # Optional: export progress percentage (0-100)
  exportProgress: 100
```

**Lifecycle:**
1. Created by fulfillment-service when user calls `CreateImageFromVM` (also creates Image DB record with status=PENDING)
2. Operator reconciles: creates VirtualMachineExport, exports VM disk, uploads to registry
3. Status updated to Complete (or Failed) with registry URL
4. Fulfillment-service watches status, updates Image DB record to status=AVAILABLE when Complete
5. After TTL expires, operator garbage collects both ComputeImageExportJob and VirtualMachineExport (via finalizer)

**Garbage collection:**
- TTL starts from `status.completionTime` (when phase becomes Complete or Failed)
- Finalizer ensures VirtualMachineExport is deleted when ComputeImageExportJob is deleted
- Both CRs cleaned up atomically after TTL expires
- Default TTL: 24 hours (configurable via spec.ttlSecondsAfterFinished)

#### fulfillment-api: Images Service

New gRPC service in `proto/fulfillment/v1/images_service.proto`:

```protobuf
service Images {
  // List images available to the organization
  rpc ListImages(ListImagesRequest) returns (ListImagesResponse);

  // Get details of a specific image
  rpc GetImage(GetImageRequest) returns (Image);

  // Initiate upload (creates Image DB record with status=PENDING, returns upload URL)
  // Upload completion updates status to AVAILABLE; failure updates to FAILED
  // Note: ComputeImage CR is created later by operator when first VM references the image (lazy creation)
  rpc InitiateUpload(InitiateUploadRequest) returns (UploadInfo);

  // Create image from running VM (async operation: creates ComputeImageExportJob, returns immediately)
  // Use GetImage to check when export completes and image becomes available
  rpc CreateImageFromVM(CreateImageFromVMRequest) returns (CreateImageFromVMResponse);

  // Update image metadata (name, description)
  rpc UpdateImage(UpdateImageRequest) returns (Image);

  // Delete image (deletes Image DB record, registry artifact, ComputeImage CR if it exists, and all cache PVCs)
  rpc DeleteImage(DeleteImageRequest) returns (google.protobuf.Empty);
}

message Image {
  string id = 1;
  shared.v1.Metadata metadata = 2;
  ImageSpec spec = 3;
  ImageStatus status = 4;
}

message ImageSpec {
  string description = 1;
}

message ImageStatus {
  // Current state of the image
  ImageState state = 1;

  // Size of the image in bytes (discovered during upload/export)
  int64 size_bytes = 2;

  // Human-readable status message
  string message = 3;
}

enum ImageState {
  IMAGE_STATE_UNSPECIFIED = 0;
  IMAGE_STATE_PENDING = 1;      // Upload/export in progress
  IMAGE_STATE_AVAILABLE = 2;    // Image ready to use
  IMAGE_STATE_FAILED = 3;       // Upload/export failed
}

// Note: Image uses metadata.name for the human-friendly name (from shared.v1.Metadata).
// No separate display_name field needed.

message CreateImageFromVMRequest {
  string vm_id = 1;                    // ID of the running VM to export
  string image_name = 2;               // Name for the new image (becomes metadata.name)
  string description = 3;              // Human-readable description
}

message CreateImageFromVMResponse {
  string export_job_id = 1;            // ID of the ComputeImageExportJob CR (for status tracking)
  string image_name = 2;               // Name of the image (will be available when export completes)
  string status = 3;                   // Current status: "Pending", "Exporting", "Uploading", "Complete", "Failed"
}

message InitiateUploadRequest {
  string image_name = 1;               // Name for the new image (becomes metadata.name)
  string description = 2;              // Human-readable description
  string organization_id = 3;          // Organization that owns the image
}

message UploadInfo {
  string upload_url = 1;               // URL where client should upload the qcow2 file
  string upload_token = 2;             // Token for authenticating the upload request
  string image_id = 3;                 // ID of the created Image record (status=PENDING)
}

message ListImagesRequest {
  string organization_id = 1;          // Filter images by organization
  string filter = 2;                   // Optional CEL filter expression
  int32 page_size = 3;                 // Maximum number of results per page
  string page_token = 4;               // Token for pagination
}

message ListImagesResponse {
  repeated Image images = 1;
  string next_page_token = 2;          // Token for retrieving next page
  int32 total_count = 3;               // Total number of images matching filter
}

message GetImageRequest {
  string image_id = 1;                 // ID of the image to retrieve
}

message UpdateImageRequest {
  string image_id = 1;                 // ID of the image to update
  shared.v1.Metadata metadata = 2;     // Updated metadata (name, labels, annotations)
  ImageSpec spec = 3;                  // Updated spec (description)
}

message DeleteImageRequest {
  string image_id = 1;                 // ID of the image to delete
}
```

#### ComputeInstance: Add imageRef field

Update `ComputeInstanceSpec` to reference images:

```protobuf
message ComputeInstanceSpec {
  string template = 1;
  map<string, google.protobuf.Any> template_parameters = 2;

  // Reference to ComputeImage by name
  // If set, creates VM by cloning the image PVC cache
  string image_ref = 3;
}
```

### Implementation Details/Notes/Constraints

#### Image Upload and Registry Storage

Images are uploaded to fulfillment-service, stored in the CSP registry as OCI artifacts, then imported to local PVC caches on each cluster via CDI:

**Upload and storage flow:**
1. User calls `osac image upload windows-2022.qcow2 --name windows-2022 --description "Windows Server 2022"`
2. CLI calls `InitiateUpload` RPC on fulfillment-api
3. Fulfillment-service creates Image record in database with `status.state = PENDING`, returns upload URL (fulfillment-service HTTP endpoint)
4. CLI streams qcow2 file to fulfillment-service upload endpoint (includes Content-Length header for file size)
5. Fulfillment-service:
   - Wraps uploaded qcow2 in ContainerDisk format on-the-fly (tar archive with `/disk/disk.img` structure)
   - Streams directly to CSP registry as OCI container image (no temporary storage)
   - Calculates SHA256 digest during streaming using io.TeeReader
   - Pushes to registry using OCI distribution spec (e.g., `registry.csp.internal/vm-images/org-acme/windows-2022:v1`)
   - Updates Image record in database: `status.state = AVAILABLE`, `status.size_bytes = <actual size>`
6. Image now discoverable via `ListImages` API with state=AVAILABLE
   - No ComputeImage CR created yet (operator creates it when first VM references the image)

**Upload service scalability (future enhancement):**
For MVP, image uploads go through fulfillment-service. The upload URL returned by `InitiateUpload` is opaque to clients, which allows future architecture changes without API impact:
- **Current (MVP)**: fulfillment-service handles both API requests and uploads
- **Future**: Dedicated image-upload-service that can scale independently
  - `InitiateUpload` returns URL pointing to upload service: `https://image-upload.osac.svc/upload/<token>`
  - Upload service handles high-bandwidth, long-running uploads
  - Fulfillment-service stays responsive during upload bursts
  - Upload service can have different resource limits and scaling policies

This separation allows CSPs to scale upload capacity independently from API capacity without changing client code.

**ContainerDisk format requirement:**
CDI's `DataVolume.source.registry` expects images in ContainerDisk format, which packages the qcow2 disk in a tar archive with specific directory structure:
- Directory: `/disk/` (mode 0755)
- File: `/disk/disk.img` containing the qcow2 (mode 0644)
- Packaged as OCI container image layer

**Streaming ContainerDisk creation (no temp storage):**
Fulfillment-service creates ContainerDisk format on-the-fly during upload:
1. Client provides file size via HTTP `Content-Length` header
2. Tar writer creates directory header for `/disk/` (~512 bytes)
3. Tar writer creates file header for `/disk/disk.img` with size from Content-Length (~512 bytes)
4. Stream qcow2 bytes directly into tar (no buffering)
5. Tar writer adds footer padding
6. Entire tar stream goes to OCI layer → registry push

**Go implementation example:**
```go
tarWriter := tar.NewWriter(ociLayerWriter)
tarWriter.WriteHeader(&tar.Header{Name: "/disk/", Typeflag: tar.TypeDir, Mode: 0755})
tarWriter.WriteHeader(&tar.Header{Name: "/disk/disk.img", Size: contentLength, Mode: 0644})
io.Copy(tarWriter, uploadStream) // Stream qcow2 directly, no temp storage
tarWriter.Close()
```

**Overhead:** Tar adds ~10KB headers/padding on a 5GB image (0.0002% overhead, negligible).

**Registry credentials and multi-tenancy:**
The registry is CSP-owned infrastructure. Fulfillment-service and operators use CSP-configured registry credentials (stored in Kubernetes Secret) for all registry operations (push during upload, pull during cache creation). Tenants never access the registry directly - they only interact via OSAC API.

**Why CSP credentials instead of per-tenant credentials:**
- **Shared images break per-tenant credentials**: CSP-provided shared images (e.g., `registry.csp.internal/vm-images/public/rhel9:latest`) need to be accessible to all tenants. If tenant A has credentials scoped to `org-acme/*` namespace, the operator cannot pull from `public/*` when creating VMs. Solutions like granting all tenants read access to `public/*` add ACL management complexity without security benefit.
- **Multi-tenancy enforced at API layer**: OSAC API/RBAC controls which tenants can upload images, list images, and create VMs. Registry namespaces (e.g., `org-acme/*`, `org-beta/*`) provide organization and naming structure, not the security boundary.
- **Simpler credential management**: Single CSP credential pair (push/pull) vs N tenant credentials + complex ACL policies.
- **Tenant isolation via API**: Fulfillment-service enforces tenant isolation - tenants can only list/use images in their organization namespace. This is enforced before any registry operation happens.

**Registry namespace structure:**
- Private images: `registry.csp.internal/vm-images/<org-name>/<image-name>:tag`
- Shared images (future): `registry.csp.internal/vm-images/public/<image-name>:tag`

CDI uses the same CSP credentials to pull from registry when creating cache PVCs.

**Cache PVC creation (on-demand):**
When a VM requests an image for the first time on a cluster with a specific storage class:
1. Operator checks for cache PVC: `vm-image-cache-<image-name>-<storageclass-hash>`
2. If not found, creates DataVolume importing from `ComputeImage.spec.source` (registry URL)
3. **Cache PVC MUST use the same storage class as the VM** (required for CSI smart clones)
4. Cache PVC persists after VM creation for reuse by subsequent VMs
5. Multiple cache PVCs can exist for same image with different storage classes (one per storage class)

**Why cache must match VM storage class:**
CSI smart clones (copy-on-write snapshots) only work when source and destination PVCs are on the same storage backend. Cross-storage-class cloning results in full copies instead of deduplicated snapshots:
- **Same storage class**: 10 GB cache + 10 VMs = 10 GB + deltas (CSI CoW snapshots)
- **Different storage class**: 10 GB cache + 10 VMs = 110 GB total storage consumed (10 full copies, no deduplication)

**User billing:**
Users are billed only for their VM's boot disk (e.g., 10 GB on `ceph-fast`). The cache PVC is infrastructure overhead, not billed to users. Users choose storage class based on performance needs and the per-GB cost of that tier.

**CSP infrastructure cost:**
Cache storage cost is amortized across VMs. Example: 10 GB cache on `ceph-fast` shared by 10 VMs consumes 10 GB (cache) + deltas (only changed blocks). For read-heavy workloads, total storage ≈ 10 GB vs 100 GB without caching (10× reduction). For write-heavy workloads, total = 10 GB + sum of deltas across all VMs.

**Cache PVC naming:**
- Format: `vm-image-cache-<image-name>-<storageclass-hash>`
- Example: `vm-image-cache-windows-2022-a1b2c3d4` (for `ceph-fast` storage class)
- Labels: `osac.openshift.io/image: <image-name>`, `osac.openshift.io/cache: "true"`

**Cache PVC lifecycle:**
- **Created:** On first VM creation for (image, storageClass) combination
- **Reused:** By all subsequent VMs using same image and storage class
- **Deleted:** When ComputeImage is deleted (operator cleans up all associated caches)
- **Garbage collected:** Cache PVCs not referenced by any VMs after 1 day (configurable TTL)

#### VM Export Workflow

Creating an image from a running VM uses an operator-driven workflow to keep heavy data operations out of the API server:

**Export and upload flow:**
1. User calls `osac image create-from-vm web-server --name web-server-golden`
2. CLI calls `CreateImageFromVM` RPC on fulfillment-api
3. Fulfillment-service:
   - Creates Image DB record with `status.state = PENDING`
   - Creates `ComputeImageExportJob` CR in the operator namespace
4. CreateImageFromVM RPC returns immediately with export job ID (async operation)
5. Operator watches `ComputeImageExportJob` CRs and reconciles:
   - Creates `VirtualMachineExport` CR (KubeVirt resource) for the source VM
   - Waits for VirtualMachineExport status to be Ready
   - Downloads exported qcow2 from VirtualMachineExport HTTP endpoint
   - Wraps qcow2 in ContainerDisk format (tar with `/disk/disk.img`) on-the-fly
   - Streams to CSP registry as OCI container image
   - Calculates SHA256 digest during upload
   - Updates `ComputeImageExportJob.status` with registry URL, digest, size, and phase=Complete
6. Fulfillment-service watches `ComputeImageExportJob` status (via polling or Signal RPC)
7. When status.phase = Complete, fulfillment-service updates Image DB record: `status.state = AVAILABLE`, `status.size_bytes` from export
8. Image now available via `ListImages` API with state=AVAILABLE
9. After TTL expires (default 24h), operator garbage collects both `ComputeImageExportJob` and `VirtualMachineExport` CRs

**Operator reconciliation logic:**
```go
func (r *ComputeImageExportJobReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    // Fetch ComputeImageExportJob
    job := &osacv1alpha1.ComputeImageExportJob{}
    if err := r.Get(ctx, req.NamespacedName, job); err != nil {
        return ctrl.Result{}, client.IgnoreNotFound(err)
    }

    // Handle deletion (finalizer cleanup)
    if !job.DeletionTimestamp.IsZero() {
        return r.handleDeletion(ctx, job)
    }

    // Garbage collection: delete if TTL expired
    if job.Status.Phase == osacv1alpha1.ExportPhaseComplete || job.Status.Phase == osacv1alpha1.ExportPhaseFailed {
        if job.Status.CompletionTime != nil && job.Spec.TTLSecondsAfterFinished != nil {
            ttl := time.Duration(*job.Spec.TTLSecondsAfterFinished) * time.Second
            if time.Since(job.Status.CompletionTime.Time) > ttl {
                return ctrl.Result{}, r.Delete(ctx, job)
            }
            // Requeue when TTL expires
            return ctrl.Result{RequeueAfter: ttl - time.Since(job.Status.CompletionTime.Time)}, nil
        }
    }

    // Skip if already complete or failed
    if job.Status.Phase == osacv1alpha1.ExportPhaseComplete || job.Status.Phase == osacv1alpha1.ExportPhaseFailed {
        return ctrl.Result{}, nil
    }

    // Phase: Pending → Exporting
    if job.Status.Phase == "" || job.Status.Phase == osacv1alpha1.ExportPhasePending {
        return r.createVMExport(ctx, job)
    }

    // Phase: Exporting → Uploading
    if job.Status.Phase == osacv1alpha1.ExportPhaseExporting {
        return r.checkExportReady(ctx, job)
    }

    // Phase: Uploading → Complete
    if job.Status.Phase == osacv1alpha1.ExportPhaseUploading {
        return r.uploadToRegistry(ctx, job)
    }

    return ctrl.Result{}, nil
}
```

**Finalizer cleanup:**
When `ComputeImageExportJob` is deleted, the finalizer ensures `VirtualMachineExport` is also deleted:
```go
func (r *ComputeImageExportJobReconciler) handleDeletion(ctx context.Context, job *osacv1alpha1.ComputeImageExportJob) (ctrl.Result, error) {
    if controllerutil.ContainsFinalizer(job, finalizerName) {
        // Delete VirtualMachineExport if it exists
        if job.Status.VirtualMachineExportName != "" {
            vmExport := &kubevirtv1.VirtualMachineExport{}
            vmExport.Name = job.Status.VirtualMachineExportName
            vmExport.Namespace = job.Namespace
            if err := r.Delete(ctx, vmExport); client.IgnoreNotFound(err) != nil {
                return ctrl.Result{}, err
            }
        }

        // Remove finalizer
        controllerutil.RemoveFinalizer(job, finalizerName)
        return ctrl.Result{}, r.Update(ctx, job)
    }
    return ctrl.Result{}, nil
}
```

**Benefits of operator-driven export:**
- ✅ Fulfillment-service stays stateless (no long-running uploads)
- ✅ Operator owns cluster resources (VirtualMachineExport, snapshots)
- ✅ Multi-cluster ready (each cluster's operator exports its VMs)
- ✅ Scalable (operator can handle concurrent exports, fulfillment-service doesn't)
- ✅ Follows existing OSAC pattern (like ComputeInstance provisioning)

#### Volume Clone Optimization

When creating a ComputeInstance with `imageRef`, the operator creates a DataVolume that clones the image PVC. This matches the existing OSAC pattern but uses PVC clone instead of registry pull.

**Current approach (registry-based):**
```yaml
apiVersion: cdi.kubevirt.io/v1beta1
kind: DataVolume
metadata:
  name: vm-root-disk
spec:
  source:
    registry:
      url: "docker://quay.io/containerdisks/fedora:40"  # Registry pull
  pvc:
    accessModes: [ReadWriteOnce]
    resources:
      requests:
        storage: 20Gi
```

**New approach (image clone):**
```yaml
apiVersion: cdi.kubevirt.io/v1beta1
kind: DataVolume
metadata:
  name: vm-root-disk
spec:
  source:
    pvc:
      name: rhel9-base-pvc          # Clone from golden image
      namespace: org-acme
  pvc:
    accessModes: [ReadWriteOnce]
    resources:
      requests:
        storage: 20Gi               # Can be larger than source
    # storageClassName inherited from source PVC for fast CSI clone
```

**Operator implementation:**
```go
// Operator logic for on-demand cache PVC creation
func (r *ComputeInstanceReconciler) createBootDisk(ctx context.Context, ci *ComputeInstance) error {
    image := &ComputeImage{}
    if err := r.Get(ctx, types.NamespacedName{
        Name: ci.Spec.ImageRef,
        Namespace: ci.Namespace,
    }, image); err != nil {
        return err
    }

    storageClass := ci.Spec.StorageClass  // VM's requested storage class
    cachePVCName := fmt.Sprintf("vm-image-cache-%s-%s",
        image.Name,
        hashStorageClass(storageClass))

    // Check if cache PVC exists for this (image, storageClass)
    cachePVC := &corev1.PersistentVolumeClaim{}
    err := r.Get(ctx, types.NamespacedName{
        Name:      cachePVCName,
        Namespace: ci.Namespace,
    }, cachePVC)

    if err != nil && !errors.IsNotFound(err) {
        return err
    }

    // Cache doesn't exist - create it
    if errors.IsNotFound(err) {
        cacheDV := &cdiv1beta1.DataVolume{
            ObjectMeta: metav1.ObjectMeta{
                Name:      cachePVCName,
                Namespace: ci.Namespace,
                Labels: map[string]string{
                    "osac.openshift.io/image": image.Name,
                    "osac.openshift.io/cache": "true",
                },
            },
            Spec: cdiv1beta1.DataVolumeSpec{
                Source: &cdiv1beta1.DataVolumeSource{
                    Registry: &cdiv1beta1.DataVolumeSourceRegistry{
                        URL: &image.Spec.Source,  // Import from registry
                    },
                },
                PVC: &corev1.PersistentVolumeClaimSpec{
                    AccessModes: []corev1.PersistentVolumeAccessMode{
                        corev1.ReadWriteOnce,
                    },
                    Resources: corev1.ResourceRequirements{
                        Requests: corev1.ResourceList{
                            corev1.ResourceStorage: estimateImageSize(image),
                        },
                    },
                    StorageClassName: storageClass,
                },
            },
        }
        if err := r.Create(ctx, cacheDV); err != nil {
            return err
        }
        // Cache creation in progress, requeue to wait for it
        return fmt.Errorf("cache PVC creation in progress, requeuing")
    }

    // Cache exists - clone from it for VM root disk
    vmRootDisk := &cdiv1beta1.DataVolume{
        ObjectMeta: metav1.ObjectMeta{
            Name:      fmt.Sprintf("%s-root-disk", ci.Name),
            Namespace: ci.Namespace,
        },
        Spec: cdiv1beta1.DataVolumeSpec{
            Source: &cdiv1beta1.DataVolumeSource{
                PVC: &cdiv1beta1.DataVolumeSourcePVC{
                    Name:      cachePVCName,
                    Namespace: ci.Namespace,
                },
            },
            PVC: &corev1.PersistentVolumeClaimSpec{
                AccessModes: []corev1.PersistentVolumeAccessMode{
                    corev1.ReadWriteOnce,
                },
                Resources: corev1.ResourceRequirements{
                    Requests: corev1.ResourceList{
                        corev1.ResourceStorage: ci.Spec.BootDisk.Size,
                    },
                },
                StorageClassName: storageClass,  // Same as cache for fast CSI clone
            },
        },
    }
    return r.Create(ctx, vmRootDisk)
}
```

The VirtualMachine creation remains identical to current OSAC implementation - it references the DataVolume in the same way.

**VirtualMachine creation (unchanged from current OSAC):**
```yaml
apiVersion: kubevirt.io/v1
kind: VirtualMachine
metadata:
  name: web-server-01
spec:
  runStrategy: Always
  template:
    spec:
      domain:
        devices:
          disks:
            - name: rootdisk
              disk:
                bus: virtio
      volumes:
        - name: rootdisk
          dataVolume:
            name: vm-root-disk  # References DataVolume (same as current)
```

**CSI smart clones (same storage class only):**
- Ceph: Instant copy-on-write snapshot (RBD layered image)
- Vast: Native snapshot/clone support
- Pure Storage: FlashArray snapshot clone
- Most CSI drivers: Native snapshot/clone support
- **Requires:** VM disk uses same storage class as image PVC cache

**Host-assisted copy (cross-storage-class):**
- CDI creates a pod to copy data from source PVC to target PVC
- Slower than smart clone (~1-2 minutes for typical images)
- Still faster than registry pull from remote registry
- Use when VM explicitly requests different storage class

**Performance benefit:**
- Current approach (registry pull per VM): 2-5 minutes per VM (network-bound download)
- New approach with same storage class (CSI smart clone): 5-30 seconds per VM
- New approach with different storage class (host-assisted): 1-2 minutes per VM
- **35x faster for same storage class, 2-3x faster for cross-storage-class**

#### Storage Considerations

**Multi-cluster architecture:**
- **Registry:** 1 copy of each image (source of truth, shareable across all clusters)
- **Each cluster:** N cache PVCs per image (where N = number of storage classes used)
  - Cache created on-demand when first VM requests (image, storageClass) combination
  - Example: `windows-2022` with `ceph-fast` and `ceph-standard` → 2 cache PVCs per cluster
- **VMs:** Clone from local PVC cache matching their storage class (no registry pulls)
- Example: 3 clusters, 1 image, 2 storage classes → 1 registry copy + 6 cache PVCs (2 per cluster)

**Storage savings via deduplication:**
CSI copy-on-write clones share base image blocks:
- Cache PVC: 2 GB (base image)
- 100 VM clones: ~100 MB avg delta each = 10 GB total deltas
- **Total: 12 GB** (cache + deltas)
- Without caching (current approach): 100 VMs × 2 GB registry pull = 200 GB
- **Savings: ~16x reduction** in storage consumption

**Storage class selection (simplified on-demand model):**
- Each VM specifies its desired storage class (from template or user request)
- Cache PVC is created with that storage class on first use
- Multiple cache PVCs can exist for same image with different storage classes
- Example: `windows-2022` might have caches for both `ceph-fast` and `ceph-standard`
- Subsequent VMs using same (image, storageClass) clone from existing cache → fast CSI clone (~5 seconds)
- VMs can use different storage class → new cache created on first use (~1-2 minutes), then cloned for subsequent VMs

**Cache PVC lifecycle:**
- **Creation:** On-demand when first VM needs (image, storageClass) combination
- **Protection:** Cannot be deleted while VMs reference them (finalizer)
- **Manual deletion:** When ComputeImage is deleted, operator deletes all associated cache PVCs
- **Garbage collection:** Operator periodically deletes cache PVCs not referenced by any VMs after TTL (default 1 day)
  - Configurable via operator environment variable: `VM_IMAGE_CACHE_TTL_DAYS=1`
  - Cache PVC tracks last-used timestamp via annotation
  - Next VM creation will re-import from registry if cache was GC'd
  - **Future enhancement:** Adaptive TTL based on usage patterns (e.g., frequently used images kept longer, rarely used images cleaned up sooner)

**Storage optimization:**
- Cache PVCs only created when needed (no preemptive imports)
- Multiple VMs share cache PVC blocks via CSI copy-on-write (minimal storage overhead)
- VM boot disks only store deltas from base image (workload changes)
- Unreferenced caches cleaned up after 1 day (minimal waste)
- Registry provides versioning and multi-cluster consistency

**Storage efficiency example:**
- 1 cache PVC (5 GB) + 100 VMs with 100 MB avg deltas = 15 GB total
- Traditional approach: 100 VMs × 5 GB full copies = 500 GB
- **Efficiency: 33x less storage per image**

#### Multi-tenancy and Sharing

**Private images (default):**
- Registry path scoped to organization (e.g., `registry.csp.internal/vm-images/org-acme/...`)
- ComputeImage CR created lazily in organization's namespace when first VM references the image
- PVC cache created in organization's namespace
- Only visible to that organization via RBAC

**Public/shared images (deferred to future enhancement):**
- Registry path in shared namespace (e.g., `registry.csp.internal/vm-images/public/rhel9`)
- ComputeImage CR created lazily in provider-managed namespace when first VM references the image
- Each cluster imports to local PVC cache in public namespace
- All organizations can list and clone via cross-namespace references
- Cross-namespace PVC clone supported by CDI

**Cross-cluster sharing:**
- Single registry image shared across all clusters (no replication needed)
- Each cluster independently imports to local PVC cache
- Updates to registry image trigger re-import on each cluster
- Consistent versioning via registry tags/digests

### Risks and Mitigations

**Risk: Large uploads (50+ GB) may timeout or fail.**

Mitigation: Use resumable upload protocol (TUS) in fulfillment-service upload endpoint. CLI implements retry logic with progress persistence. Upload endpoint supports chunked transfer encoding.

**Risk: Storage exhaustion from large/many images.**

Mitigation:
- Quota enforcement at registry level (registry storage limits per organization namespace)
- Quota enforcement at cluster level (Kubernetes PVC quotas per organization namespace)
- Operator rejects image import if PVC quota exceeded
- Metrics for both registry storage and PVC cache consumption
- Registry garbage collection for unused image versions

**Risk: Malicious images (malware, exploits).**

Mitigation:
- Image scanning deferred to separate enhancement
- Cloud provider can require approval workflow for public images
- Consider integration with image scanning tools (Clair, Trivy)

**Risk: CSI driver doesn't support volume clones.**

Mitigation:
- CDI falls back to host-assisted copy (slower but works)
- Document recommended storage solutions (Ceph, Vast Data, Pure Storage)
- Warn users if storage class doesn't support smart clones

**Risk: Registry unavailable during cache import.**

Mitigation:
- Retry logic in operator for failed cache PVC imports
- Cache DataVolume status indicates import failure with registry error message
- Existing VMs continue to work (cloning from already-cached PVCs)
- Manual retry: delete failed cache PVC, next VM creation will retry import

**Risk: Cross-namespace PVC clones may not work on all CSI drivers (deferred - applies to public images in future enhancement).**

Mitigation:
- CDI documentation lists supported drivers
- For unsupported drivers, public images use DV import (slower) instead of clone
- Alternative: replicate public images to each organization namespace

### Drawbacks

**Increased complexity:**
- New CRD and controller to maintain
- Registry integration (OCI artifact push/pull)
- Dual storage management (registry + PVC caches)
- Additional API surface (Images service)

**Storage costs:**
- Images stored in both registry (source of truth) and PVC caches (per-cluster)
- Multi-cluster deployment: N clusters = 1 registry copy + N PVC caches per image
- Must monitor and manage both registry and PVC storage usage
- Registry costs depend on CSP's registry solution

**Implementation effort:**
- New fulfillment-api service endpoints (InitiateUpload, List, Get, Update, Delete)
- Upload handling and OCI push logic in fulfillment-service
- Operator controller for ComputeImage (watch CR, import from registry, manage PVC cache)
- CLI commands (list, get, upload, delete)
- Registry credential management and configuration

## Alternatives (Not Implemented)

### Alternative 1: PVC-only storage (no registry)

Store uploaded images directly in PVCs without using registry as intermediary.

**Pros:**
- Simpler implementation (no registry integration)
- One storage layer to manage (PVCs only)
- No registry costs or configuration

**Cons:**
- No cross-cluster sharing (each cluster needs separate upload)
- No versioning or tagging (PVCs don't provide this natively)
- No standard tooling for backup/replication
- Difficult to implement organization-scoped access control across clusters
- Doesn't leverage existing CSP registry infrastructure

**Rejected because:** Multi-cluster OSAC deployments require shared image source of truth. Registry provides versioning, cross-cluster sharing, and standard backup/replication tooling.

### Alternative 2: Registry-only, no PVC caching

Store images in registry, pull directly at VM creation time (current OSAC behavior, with upload API added).

**Pros:**
- Simple architecture (registry-only storage)
- Standard OCI tooling for advanced users
- No PVC cache management needed

**Cons:**
- Slow VM provisioning (network-bound registry pulls, 2-5 minutes per VM)
- Registry bottleneck during scale-up (100 VMs = 100 concurrent pulls)
- Network dependency for every VM creation
- High registry bandwidth costs
- No storage deduplication benefits (each VM has full copy)

**Rejected because:** Performance penalty (35x slower provisioning) is unacceptable for production workloads. Registry pulls don't benefit from CSI copy-on-write snapshots.

### Alternative 3: Hybrid user choice (let users choose registry-pull or PVC-cache per image)

Let users decide per-image whether to use registry pulls or PVC caching.

**Pros:**
- Flexibility for different use cases (one-off VMs vs scale-out workloads)
- Advanced users can opt for registry-only to save PVC storage

**Cons:**
- Two code paths to maintain and test
- User confusion ("which mode should I use?")
- Inconsistent performance characteristics across VMs
- Increased complexity in operator logic

**Rejected because:** Complexity outweighs benefits. Default behavior (registry + PVC cache) provides best performance. Users can always delete PVC caches if storage is constrained, triggering re-import when needed.

## Open Questions

None. MVP scope is limited to qcow2 upload only.

## Test Plan

**Unit tests:**
- ComputeImage CRUD operations (create, list, get, delete)
- Registry push logic in fulfillment-service (OCI artifact creation, streaming upload)
- Cache PVC naming and hash generation (deterministic, collision-free)
- Cache PVC garbage collection logic (TTL-based cleanup)
- Error handling (upload failures, registry push failures, quota exceeded)

**Integration tests:**
- Upload to fulfillment-service → push to registry (verify OCI artifact created)
- First VM creation: cache PVC created on-demand from registry
- Second VM creation: clone from existing cache PVC (fast path)
- Multiple storage classes: separate cache PVCs for same image
- ComputeImage deletion: all cache PVCs cleaned up
- Cache garbage collection: unused caches deleted after TTL
- Storage quota enforcement (both registry and PVC quotas)
- Registry credential handling (pull secret configuration for cache imports)

**E2E tests:**
- Full workflow: upload qcow2 → stored in registry → create VM (cache created on-demand) → verify boot
- Multi-cluster: upload to registry → create VM on cluster A and cluster B (both create independent caches)
- Provisioning performance:
  - First VM: ~1-2 minutes (cache creation from registry)
  - Next 99 VMs: ~5 seconds each (clone from cache), measure time, verify storage dedup
- Multiple storage classes: create VMs with different storage classes, verify separate caches created
- Cache reuse: create VM, delete it, create another VM → cache reused (no re-import)
- Cache garbage collection: create VM, delete it, wait TTL+1 days, verify cache deleted
- Quota enforcement: exceed registry quota or PVC quota, verify rejection
- Registry failure handling: disconnect registry during cache creation, verify retry/error handling

**Scale tests:**
- 100 concurrent image uploads (registry ingress bandwidth)
- 10 clusters creating VMs from same image simultaneously (registry egress bandwidth for cache creation)
- 10,000 VMs created from 10 images on single cluster:
  - 10 images × 2 storage classes = 20 cache PVCs
  - 10,000 VM disk PVCs cloned from caches
  - Verify storage deduplication and performance
- Storage consumption: registry (source) + PVC caches (per cluster, per storageClass) + VM clones
- Garbage collection at scale: 1000 cache PVCs, 90% unused → verify efficient cleanup

## Graduation Criteria

N/A. OSAC is in active development and has not been released to customers.

**MVP implementation includes:**
- ComputeImage API with upload support
- On-demand PVC caching with garbage collection
- Integration with ComputeInstance via imageRef field
- Basic test coverage

**Future enhancements (not in MVP):**
- Import from HTTP/S3 URLs
- Import from external OCI registries
- Image cloning
- Public image sharing
- Adaptive cache TTL
- Image versioning/tagging

## Upgrade / Downgrade Strategy

**OSAC is pre-GA:** No backward compatibility guarantees. Breaking changes are acceptable.

**Deployment:**

1. CSP configures registry credentials and URL in OSAC configuration.
2. Deploy new operator version with ComputeImage controller.
3. Deploy new fulfillment-service version with upload endpoint and OCI push logic.
4. Deploy new fulfillment-api version with Images service.
5. Organizations can now upload images via new API (stored in CSP registry, imported to PVC caches).
6. VMs reference images via `imageRef` field in ComputeInstanceSpec.

**Downgrade:**

Not supported. If rollback is required:
- Delete all ComputeImage CRs
- Delete all image PVC caches
- Clean up registry namespace (manual or via registry GC)
- Downgrade operator/service/API components

## Version Skew Strategy

**Multi-cluster deployments:**
- Safe to upgrade operators independently across clusters
- Registry is source of truth: uploaded images automatically available to all clusters
- Each cluster creates cache PVCs on-demand when VMs reference images
- Unupgraded clusters without ComputeImage controller cannot provision VMs using `imageRef`
- Cache PVCs are per-cluster, not replicated (each cluster pulls from registry on first VM creation)

**Component version requirements:**
- All components (fulfillment-api, fulfillment-service, operator) must be updated together
- KubeVirt CDI v1.55+ required for smart clone support
- Operator validates CDI version on startup, fails if too old

## Support Procedures

**Symptom: First VM creation slow (cache PVC being created)**

Detection:
- ComputeInstance stuck in `Provisioning` state for > 2 minutes
- Operator logs: `Creating cache PVC for image windows-2022 with storage class ceph-fast`

Diagnosis:
```bash
# Check for cache PVC creation
oc get pvc -l osac.openshift.io/cache=true -n <namespace>

# Check cache DataVolume status
oc get datavolume vm-image-cache-<image>-<hash> -o yaml

# Check CDI importer pod logs
oc logs -l app=containerized-data-importer -n <namespace>
```

Common causes:
- First VM using this (image, storageClass) combination (expected behavior)
- Registry unreachable (network timeout, DNS failure)
- Registry authentication failure (invalid pull secret)
- Storage quota exceeded (PVC creation fails)

Resolution:
- Expected on first VM: wait for cache import to complete (~1-2 minutes)
- Subsequent VMs using same (image, storageClass) will be fast (~5 seconds)
- If import fails: verify registry URL and credentials, check network connectivity
- Increase storage quota if needed

**Symptom: VM creation fails with "image not found"**

Detection:
- ComputeInstance stuck in `Provisioning` state
- Operator logs: `ComputeImage "myimage" not found`

Diagnosis:
```bash
# Check if image exists
oc get computeimage myimage

# Check if cache PVC exists (may be creating on-demand)
oc get pvc -l osac.openshift.io/image=myimage,osac.openshift.io/cache=true
```

Resolution:
- If image doesn't exist: create it using `osac image upload`
- If image exists but cache PVC is being created: wait for cache import to complete (~1-2 minutes on first VM)
- Subsequent VMs will provision faster once cache exists

**Symptom: Slow VM provisioning despite using ComputeImage**

Detection:
- VM creation takes > 2 minutes (expected: < 30 seconds)
- Operator logs: `Cloning image PVC using host-assisted copy`

Diagnosis:
```bash
# Check if storage class supports volume clones
oc get storageclass <storage-class-name> -o yaml | grep volumeBindingMode

# Check CDI smart clone feature gate
oc get cdi cdi -o yaml | grep -A 5 featureGates
```

Common causes:
- Storage class doesn't support CSI volume snapshots/clones
- CDI smart clone feature disabled

Resolution:
- Migrate to storage class with CSI clone support (Ceph, Vast, Pure Storage)
- Enable CDI smart clone feature gate
- Document expected performance for non-clone-capable storage

**Symptom: Storage quota exceeded**

Detection:
- ComputeImage creation fails
- Error message: `exceeded quota: requests.storage=100Gi`

Diagnosis:
```bash
# Check namespace quota
oc get resourcequota -n <namespace>

# Check current PVC usage
oc get pvc -n <namespace> --no-headers | awk '{sum+=$4} END {print sum "Gi"}'
```

Resolution:
- Delete unused images: `osac image delete <name>`
- Request quota increase from CSP admin
- Use image cloning instead of re-uploading duplicates

## Infrastructure Needed

**OCI-compliant registry:**
- Required for storing VM images as OCI artifacts (source of truth)
- Must support OCI distribution spec v1.0+ and arbitrary media types
- Examples: Quay, Harbor, Azure Container Registry, AWS ECR, OpenShift integrated registry
- CSP configures registry URL and credentials (push/pull secrets)
- Recommend organization-scoped namespaces (e.g., `registry.csp.internal/vm-images/org-acme/`)
- Storage sizing: plan for total image library (e.g., 100 organizations × 10 images × 5 GB = 5 TB)

**KubeVirt CDI:**
- Required for importing images from registry to local PVC caches
- Already part of OpenShift Virtualization
- Minimum version: v1.55.0 (for smart clone support and registry import)
- Must be configured with registry pull secret

**CSI storage driver with snapshot/clone support:**
- Supported CSI drivers: Ceph, Vast Data, Pure Storage
- Volume clone capability required for optimal VM provisioning performance (35x faster)
- **Important:** Configure image PVC caches to use storage class with CSI clone support
- VM disks should use same storage class as cache for fast cloning
- Falls back to host-assisted copy for cross-storage-class cloning (slower but functional)

**Storage capacity per cluster:**
- Registry storage: centralized, shared across all clusters (e.g., 100 orgs × 10 images × 5 GB = 5 TB total)
- **PVC cache storage** (on-demand, small footprint):
  - Cache PVCs only store base images: 50 images × 5 GB = 250 GB
  - Unreferenced caches consume capacity until GC'd (1-day TTL minimizes waste)
  - Referenced caches (actively used by VMs) share storage via CSI deduplication
- **VM boot disk storage** (deltas only via CSI copy-on-write):
  - 10,000 VMs × ~100 MB avg delta = 1 TB (not 50 TB with full copies)
  - Actual delta depends on VM workload (OS updates, application data)
  - Example: 100 VMs from 1 cache = 5 GB cache + ~10 GB deltas = 15 GB total
- **Total cluster storage**: cache PVCs (small) + VM deltas (workload-dependent)
- Consider storage quotas per organization namespace
- Monitor cache hit rates to optimize garbage collection TTL

**Cache garbage collection configuration:**
- Default TTL: 1 day (configurable via `VM_IMAGE_CACHE_TTL_DAYS` environment variable)
- Periodic controller checks cache PVCs for last-used timestamp
- Caches not referenced by any VMs and older than TTL are deleted
- Minimal storage waste: unreferenced caches cleaned up quickly (1 day)
- Referenced caches (actively used) are never GC'd, no storage penalty

**Network bandwidth:**
- Upload path: fulfillment-service receives qcow2, pushes to registry (internet or internal network)
- Import path: each cluster pulls from registry to PVC cache once per image (cluster↔registry network)
- VM provisioning: no network usage (local PVC clone)
- Recommend dedicated network for fulfillment-service uploads
- Rate limiting on upload endpoint to prevent abuse
- Registry should have adequate bandwidth for multi-cluster imports
