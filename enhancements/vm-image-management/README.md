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

This proposal introduces a VM image management API that enables organization users to upload qcow2 virtual machine disk images without requiring direct registry access or OCI tooling knowledge. Uploaded images are stored as OCI artifacts in a CSP-owned registry (source of truth, shareable across clusters). When a VM references an image, a local PVC cache is created on-demand for that (image, storageClass) combination. Subsequent VMs clone from the cache using CSI copy-on-write snapshots, eliminating repeated registry pulls.

Additionally, users can create images from running VMs, capturing the complete VM disk state. This enables backup workflows, golden image creation, and cross-cluster VM cloning by exporting the VM to the registry as a new image.

**MVP Scope:** Upload qcow2 images via API, create images from running VMs, store as OCI artifacts in registry. On-demand PVC caching with garbage collection. Import from HTTP/S3 URLs and image cloning are deferred to future enhancements.

## Motivation

Currently, OSAC requires organization users to manually push VM images to an OCI registry using podman/skopeo, then reference them when creating VMs. Each VM creation pulls the image from the registry over the network. This approach has several limitations:

1. **Poor UX**: Requires understanding OCI tooling (podman, skopeo), managing registry credentials, and converting qcow2 to ContainerDisk format.
2. **No API discoverability**: Users cannot list available images or query metadata (OS type, size) via the OSAC API.
3. **Slow provisioning**: Each VM pulls a multi-gigabyte image from the registry over the network (2-5 minutes per VM).
4. **Registry bottleneck**: Creating 100 VMs simultaneously means 100 concurrent registry pulls.
5. **No multi-cluster optimization**: Each cluster re-pulls the same image from registry for every VM, even if the image was already pulled before.

This proposal introduces an upload API that hides registry complexity from users, stores images in the CSP-owned registry as the source of truth (enabling multi-cluster sharing and versioning), and creates local PVC caches on-demand when VMs reference images for fast VM cloning.

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
- Store uploaded images in CSP-owned registry as OCI artifacts (source of truth, cross-cluster sharing).
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

Introduce a `VirtualMachineImage` custom resource that represents a qcow2 VM disk image uploaded by an authorized user. Images are uploaded via HTTP API and stored as OCI artifacts in the CSP-owned registry. When a user creates a ComputeInstance referencing an image, the operator creates a local PVC cache on-demand (if it doesn't exist) by importing from the registry. Subsequent VMs clone from the cache using CSI copy-on-write snapshots, eliminating repeated registry pulls.

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
   fulfillment-cli image upload windows-server-2022.qcow2 \
     --name windows-2022 \
     --description "Windows Server 2022 Datacenter"
   ```
3. CLI calls fulfillment-api `InitiateUpload` RPC, receives upload URL.
4. CLI streams qcow2 file to fulfillment-service upload endpoint.
5. Fulfillment-service:
   - Streams uploaded qcow2 directly to CSP registry as OCI artifact (no temporary storage)
   - Calculates SHA256 digest on-the-fly using io.TeeReader while streaming
   - Pushes to registry using OCI distribution spec (e.g., `registry.csp.internal/vm-images/org-acme/windows-2022:v1`)
   - Creates VirtualMachineImage CR with `spec.source` pointing to the registry URL
6. VirtualMachineImage now exists in organization's namespace, ready to be referenced by VMs
   - No cache PVC is created yet (on-demand import happens when first VM references the image)
7. Organization user creates VM (first VM using this image on this cluster):
   ```bash
   fulfillment-cli create compute-instance \
     --name web-server \
     --image windows-2022 \
     --cores 4 \
     --memory 8 \
     --storage-class ceph-fast
   ```
8. Operator checks for cache PVC `vm-image-cache-windows-2022-ceph-fast`:
   - **Not found (first VM):** Create DataVolume importing from registry to cache PVC with storageClass `ceph-fast` (~1-2 minutes)
   - **Found (subsequent VMs):** Clone from existing cache PVC (~5 seconds)
9. Operator creates VM's root disk DataVolume:
   - If cache just created: wait for it to be ready, then clone
   - If cache exists: clone immediately
10. Operator creates VirtualMachine referencing the root disk DataVolume (same pattern as current OSAC).
11. VM boots from cloned disk.

**Subsequent VMs:** Steps 8-11 but cache already exists → clone immediately (~5 seconds total).

**Expected result:** User uploads qcow2 without registry knowledge. Image stored in registry (shareable across clusters). VMs provision in seconds via PVC clones from local cache.

#### Workflow 2: Organization user creates image from running VM

**Actors:** Organization user

**Use case:** User has configured a production VM and wants to capture its current state as a golden image for cloning.

1. User has a running VM (`web-server`) that they've configured with applications and settings.
2. User creates an image from the VM via CLI:
   ```bash
   fulfillment-cli image create-from-vm web-server \
     --name web-server-golden \
     --description "Production web server configuration - April 2026"
   ```
3. CLI calls fulfillment-api `CreateImageFromVM` RPC.
4. Fulfillment-service initiates VM export workflow:
   - Creates a temporary VirtualMachineExport CR (KubeVirt feature) for the running VM
   - VirtualMachineExport exports VM disk to downloadable qcow2 format
5. Fulfillment-service streams exported qcow2 to CSP registry:
   - Downloads from VirtualMachineExport endpoint
   - Streams to registry as OCI artifact (e.g., `registry.csp.internal/vm-images/org-acme/web-server-golden:v1`)
   - Calculates SHA256 digest
6. Fulfillment-service creates VirtualMachineImage CR with `spec.source` pointing to registry.
7. Fulfillment-service cleans up VirtualMachineExport CR.
8. VirtualMachineImage now exists with metadata indicating it was created from a VM.
   - No cache PVC is created yet (on-demand import happens when first VM references the image)
9. Organization user creates new VM from the image:
   ```bash
   fulfillment-cli create compute-instance \
     --name web-server-test \
     --image web-server-golden \
     --cores 4 \
     --memory 8
   ```
10. Operator follows standard image workflow:
    - Creates cache PVC if needed (on-demand import from registry)
    - Clones cache to create VM root disk
    - VM boots with identical disk state as source VM

**Expected result:** User captures configured VM as reusable image. Image stored in registry (cross-cluster sharing, survives cluster failure). New VMs can be created from the image following standard workflow.

**Benefits over VM snapshots:**
- Image survives cluster failure (stored in registry, not cluster-local VolumeSnapshot)
- Cross-cluster cloning (create VM from image on any cluster with access to registry)
- Aligns with cloud-native patterns (AWS AMI, Azure Managed Images, GCP Custom Images)

### API Extensions

#### VirtualMachineImage CRD

New custom resource representing a VM disk image:

```yaml
apiVersion: osac.openshift.io/v1alpha1
kind: VirtualMachineImage
metadata:
  name: windows-2022
  namespace: org-acme
spec:
  # Display name for UI/CLI
  displayName: "Windows Server 2022 Datacenter"

  # Human-readable description
  description: "Windows Server 2022 Datacenter with security hardening"

  # Source reference (MVP: OCI registry URL, future: S3, HTTP)
  source: "registry.csp.internal/vm-images/org-acme/windows-2022:v1"
```

**Note:** VirtualMachineImage is purely metadata. Cache PVCs are created on-demand per cluster when VMs reference the image, managed automatically by the operator.

#### fulfillment-api: Images Service

New gRPC service in `proto/fulfillment/v1/images_service.proto`:

```protobuf
service Images {
  // List images available to the organization
  rpc ListImages(ListImagesRequest) returns (ListImagesResponse);

  // Get details of a specific image
  rpc GetImage(GetImageRequest) returns (Image);

  // Initiate upload (returns upload token/URL; VirtualMachineImage created after upload completes)
  rpc InitiateUpload(InitiateUploadRequest) returns (UploadInfo);

  // Create image from running VM (exports VM disk to registry as new image)
  rpc CreateImageFromVM(CreateImageFromVMRequest) returns (Image);

  // Update image metadata (display name, description)
  rpc UpdateImage(UpdateImageRequest) returns (Image);

  // Delete image (deletes VirtualMachineImage CR, registry artifact, and all cache PVCs)
  rpc DeleteImage(DeleteImageRequest) returns (google.protobuf.Empty);
}

message Image {
  string id = 1;
  shared.v1.Metadata metadata = 2;
  ImageSpec spec = 3;
}

message ImageSpec {
  string display_name = 1;
  string description = 2;
  string source = 3;  // Source reference (OCI registry URL, future: S3, HTTP)
}

message CreateImageFromVMRequest {
  string vm_id = 1;                    // ID of the running VM to export
  string image_name = 2;               // Name for the new image
  string display_name = 3;             // Display name for UI/CLI
  string description = 4;              // Human-readable description
}
```

#### ComputeInstance: Add imageRef field

Update `ComputeInstanceSpec` to reference images:

```protobuf
message ComputeInstanceSpec {
  string template = 1;
  map<string, google.protobuf.Any> template_parameters = 2;

  // Reference to VirtualMachineImage by name
  // If set, creates VM by cloning the image PVC cache
  string image_ref = 3;
}
```

### Implementation Details/Notes/Constraints

#### Image Upload and Registry Storage

Images are uploaded to fulfillment-service, stored in the CSP registry as OCI artifacts, then imported to local PVC caches on each cluster via CDI:

**Upload and storage flow:**
1. User calls `fulfillment-cli image upload windows-2022.qcow2 --name windows-2022 --description "Windows Server 2022"`
2. CLI calls `InitiateUpload` RPC on fulfillment-api
3. Fulfillment-service returns upload URL (fulfillment-service HTTP endpoint)
4. CLI streams qcow2 file to fulfillment-service upload endpoint
5. Fulfillment-service:
   - Streams uploaded qcow2 directly to CSP registry as OCI artifact (no temporary storage)
   - Calculates SHA256 digest on-the-fly using io.TeeReader while streaming
   - Pushes to registry using OCI distribution spec (e.g., `registry.csp.internal/vm-images/org-acme/windows-2022:v1`)
   - Creates VirtualMachineImage CR with `spec.source`
6. VirtualMachineImage now exists in organization's namespace, ready to be referenced by VMs

**Registry credentials:** Fulfillment-service uses CSP-configured registry credentials (stored in Kubernetes Secret) to push images. CDI uses the same credentials to pull from registry when creating cache PVCs.

**Cache PVC creation (on-demand):**
When a VM requests an image for the first time on a cluster with a specific storage class:
1. Operator checks for cache PVC: `vm-image-cache-<image-name>-<storageclass-hash>`
2. If not found, creates DataVolume importing from `VirtualMachineImage.spec.source` (registry URL)
3. DataVolume PVC uses the storage class requested by the VM
4. Cache PVC persists after VM creation for reuse by subsequent VMs
5. Multiple cache PVCs can exist for same image with different storage classes

**Cache PVC naming:**
- Format: `vm-image-cache-<image-name>-<storageclass-hash>`
- Example: `vm-image-cache-windows-2022-a1b2c3d4` (for `ceph-fast` storage class)
- Labels: `osac.openshift.io/image: <image-name>`, `osac.openshift.io/cache: "true"`

**Cache PVC lifecycle:**
- **Created:** On first VM creation for (image, storageClass) combination
- **Reused:** By all subsequent VMs using same image and storage class
- **Deleted:** When VirtualMachineImage is deleted (operator cleans up all associated caches)
- **Garbage collected:** Cache PVCs not referenced by any VMs after 1 day (configurable TTL)

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
    image := &VirtualMachineImage{}
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
- **Manual deletion:** When VirtualMachineImage is deleted, operator deletes all associated cache PVCs
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
- VirtualMachineImage CR created in organization's namespace
- PVC cache created in organization's namespace
- Only visible to that organization via RBAC

**Public/shared images (deferred to future enhancement):**
- Registry path in shared namespace (e.g., `registry.csp.internal/vm-images/public/rhel9`)
- VirtualMachineImage CR created in provider-managed namespace
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
- Operator controller for VirtualMachineImage (watch CR, import from registry, manage PVC cache)
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
- VirtualMachineImage CRUD operations (create, list, get, delete)
- Registry push logic in fulfillment-service (OCI artifact creation, streaming upload)
- Cache PVC naming and hash generation (deterministic, collision-free)
- Cache PVC garbage collection logic (TTL-based cleanup)
- Error handling (upload failures, registry push failures, quota exceeded)

**Integration tests:**
- Upload to fulfillment-service → push to registry (verify OCI artifact created)
- First VM creation: cache PVC created on-demand from registry
- Second VM creation: clone from existing cache PVC (fast path)
- Multiple storage classes: separate cache PVCs for same image
- VirtualMachineImage deletion: all cache PVCs cleaned up
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
- VirtualMachineImage API with upload support
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
2. Deploy new operator version with VirtualMachineImage controller.
3. Deploy new fulfillment-service version with upload endpoint and OCI push logic.
4. Deploy new fulfillment-api version with Images service.
5. Organizations can now upload images via new API (stored in CSP registry, imported to PVC caches).
6. VMs reference images via `imageRef` field in ComputeInstanceSpec.

**Downgrade:**

Not supported. If rollback is required:
- Delete all VirtualMachineImage CRs
- Delete all image PVC caches
- Clean up registry namespace (manual or via registry GC)
- Downgrade operator/service/API components

## Version Skew Strategy

**Multi-cluster deployments:**
- Safe to upgrade operators independently across clusters
- Registry is source of truth: uploaded images automatically available to all clusters
- Each cluster creates cache PVCs on-demand when VMs reference images
- Unupgraded clusters without VirtualMachineImage controller cannot provision VMs using `imageRef`
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
- Operator logs: `VirtualMachineImage "myimage" not found`

Diagnosis:
```bash
# Check if image exists
oc get virtualmachineimage myimage

# Check if cache PVC exists (may be creating on-demand)
oc get pvc -l osac.openshift.io/image=myimage,osac.openshift.io/cache=true
```

Resolution:
- If image doesn't exist: create it using `fulfillment-cli image upload`
- If image exists but cache PVC is being created: wait for cache import to complete (~1-2 minutes on first VM)
- Subsequent VMs will provision faster once cache exists

**Symptom: Slow VM provisioning despite using VirtualMachineImage**

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
- VirtualMachineImage creation fails
- Error message: `exceeded quota: requests.storage=100Gi`

Diagnosis:
```bash
# Check namespace quota
oc get resourcequota -n <namespace>

# Check current PVC usage
oc get pvc -n <namespace> --no-headers | awk '{sum+=$4} END {print sum "Gi"}'
```

Resolution:
- Delete unused images: `fulfillment-cli image delete <name>`
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
