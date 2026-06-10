---
title: Accelerator Support in Cluster as a Service
authors:
  - vladikr@redhat.com
creation-date: 2026-06-08
last-updated: 2026-06-09
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1373
see-also:
  - Accelerator Support PRD: /enhancements/accelerator-support-in-caas-prd
replaces:
  - N/A
superseded-by:
  - N/A
---

# Accelerator Support in Cluster as a Service

## Summary

This proposal introduces structured accelerator (primarily GPU) support for Cluster as a Service (CaaS) in OSAC.

It defines a new declarative type `AcceleratorRequest` that can be embedded in `NodeRequest` within `ClusterOrder`. This allows tenants (via the catalog) or catalog authors to express accelerator requirements in a typed, future-proof way.

The proposal also covers automatic installation of the NVIDIA GPU Operator during cluster post-install when accelerators are requested, and defines how the system should resolve declarative accelerator intent into actual infrastructure provisioning.

A key goal of this proposal is to establish `AcceleratorRequest` as a **reusable building block** that can serve both CaaS and VMaaS in the long term, instead of allowing the two paths to evolve incompatible accelerator models.

## Motivation

Currently, requesting GPUs in CaaS is ad-hoc and relies on `resourceClass` + free-form `templateParameters`. This approach lacks:

- Type safety and validation  
- Clear semantics for GPU model, count, and sharing mode (dedicated / vGPU / MIG)  
- Automatic operator installation for "AI-ready" clusters  
- Forward compatibility with DRA and newer NVIDIA hardware (GB200, Blackwell, etc.)

As OSAC targets sovereign AI workloads, structured accelerator support is essential for both usability and technical correctness. Importantly, we want to avoid creating two separate accelerator request mechanisms — one for `ClusterOrder` and another for `ComputeInstance` — which would lead to fragmentation and higher long-term maintenance cost.

### User Stories

* As a data scientist, I want to order a GPU-enabled OpenShift cluster through the catalog, so that I can run ML training workloads without needing to understand bare metal provisioning or GPU operator installation.

* As a catalog author, I want to create an "AI-ready cluster" offering that declaratively specifies GPU requirements, so that tenants can select it and get a working cluster with GPUs and operators pre-configured.

* As a platform engineer, I want accelerator configuration to be consistent between CaaS and VMaaS, so that I don't have to maintain two different accelerator provisioning code paths.

* As a tenant, I want to request vGPU or MIG profiles for cost optimization, so that I can share GPUs across multiple workloads instead of dedicating entire GPUs per node.

## Goals

- Introduce a reusable, declarative `AcceleratorRequest` type that can serve as a shared model across both CaaS and VMaaS.  
- Enable automatic NVIDIA GPU Operator installation when GPUs are requested in CaaS.  
- Provide a clean mapping from catalog UI parameters to backend intent.  
- Design for future evolution toward Dynamic Resource Allocation (DRA).  
- Maintain clear separation between catalog usability and backend declarative power.  
- Establish a foundation for API unification so that accelerator handling in `ClusterOrder` and `ComputeInstance` converges over time rather than diverging.

## Non-Goals (But the logical next step)

- Full implementation of DRA-based device claims in Phase 1  
- Changes to the `ComputeInstance` / VMaaS path in this proposal   
- Support for non-NVIDIA accelerators in the initial implementation

## Proposal

### 1. New `AcceleratorRequest` Type

We propose adding the following type in `osac-operator/api/v1alpha1`:

```go
type AcceleratorRequest struct {
    // Type is the resource type (e.g., "nvidia.com/gpu")
    // +kubebuilder:validation:Required
    // +kubebuilder:validation:MinLength=1
    Type string `json:"type"`

    // Vendor is the accelerator vendor (e.g., "nvidia")
    // +kubebuilder:validation:Optional
    // +kubebuilder:validation:Enum=nvidia
    Vendor string `json:"vendor,omitempty"`

    // Model is the specific GPU model (e.g., "H100", "H200", "GB200")
    // +kubebuilder:validation:Optional
    Model string `json:"model,omitempty"`

    // Count is the number of GPUs per node
    // +kubebuilder:validation:Optional
    // +kubebuilder:validation:Minimum=1
    Count int `json:"count,omitempty"`

    // Mode specifies how GPUs are allocated (dedicated, vgpu, mig)
    // +kubebuilder:validation:Optional
    // +kubebuilder:validation:Enum=dedicated;vgpu;mig
    Mode string `json:"mode,omitempty"`

    // Profile is the vGPU or MIG profile name (e.g., "GRID-A100-4C", "1g.5gb")
    // +kubebuilder:validation:Optional
    Profile string `json:"profile,omitempty"`

    // UseDRA enables Dynamic Resource Allocation for this accelerator
    // +kubebuilder:validation:Optional
    UseDRA bool `json:"useDRA,omitempty"`

    // ResourceClaimTemplate is the name of a ResourceClaimTemplate for DRA
    // +kubebuilder:validation:Optional
    ResourceClaimTemplate string `json:"resourceClaimTemplate,omitempty"`
}
```

This struct will be added to `NodeRequest`:

```go
type NodeRequest struct {
    // ResourceClass describes the type of node you are requesting
    // +kubebuilder:validation:Required
    ResourceClass string `json:"resourceClass"`

    // NumberOfNodes describes the number of nodes you want of the given resource class
    // +kubebuilder:validation:Required
    NumberOfNodes int `json:"numberOfNodes"`

    // Accelerators describes accelerator (GPU) requirements for these nodes
    // +kubebuilder:validation:Optional
    Accelerators []AcceleratorRequest `json:"accelerators,omitempty"`
}
```

### 2. Unified Accelerator Model Across CaaS and VMaaS (Long-term Vision)

While this proposal focuses on CaaS, `AcceleratorRequest` is intentionally designed to be a **shared, reusable type** across the entire OSAC platform.

**Long-term goal:** We want one coherent way of requesting accelerators in OSAC, whether the target is:

- Worker nodes of a tenant-managed cluster (`ClusterOrder` / CaaS), or  
- Individual virtual machines (`ComputeInstance` / VMaaS).

**Why unification matters:** If `ClusterOrder` and `ComputeInstance` evolve their accelerator handling independently, we will end up with duplicated logic, inconsistent semantics, and a fragmented user experience. By introducing `AcceleratorRequest` now as a common building block, we set the direction toward convergence.

**Future usage in VMaaS (illustrative, not in scope for Phase 1):** In `ComputeInstance`, entries from `AcceleratorRequest` could be translated into the corresponding KubeVirt configuration under `spec.domain.devices.gpus`, using the appropriate `deviceName` derived from the accelerator type, model, and profile. The same type would allow catalog items to offer GPU-enabled VMs in a consistent manner with GPU-enabled clusters.

This approach ensures that improvements to accelerator handling (for example, better DRA support or new NVIDIA hardware profiles) can benefit both CaaS and VMaaS without duplicating effort.

### 3. Resolution and Validation Logic (CaaS)

When one or more `AcceleratorRequest` entries exist in a `ClusterOrder`, the cluster is considered to require accelerator support. The `osac-operator` (or Fulfillment Service) should validate that the chosen `resourceClass` is compatible with the requested accelerators. In later phases, we may allow the system to derive a suitable `resourceClass` from accelerator requirements.

### 4. GPU Operator Installation

The post-install playbook (`playbook_osac_create_hosted_cluster_post_install.yml`) will be updated to:

- Detect the presence of NVIDIA GPU requests in `AcceleratorRequest`.  
- Install the NVIDIA GPU Operator (via Subscription or manifests) if not explicitly disabled.  
- Configure the operator based on requested `mode` (for example using `vm-passthrough` or `vm-vgpu` labels when relevant).

An explicit override flag in `templateParameters` or `ClusterOrderSpec` will be supported for cases where the tenant wants to manage operator installation themselves.

### 5. Catalog Integration

The catalog layer (UI + Fulfillment Service request translation) is responsible for:

- Presenting curated "AI-ready" cluster offerings.  
- Mapping high-level user choices (GPU size, workload type, sharing preference) into `AcceleratorRequest` fields.  
- Hiding low-level complexity from most tenants while still allowing advanced configuration.

### 6. Forward Compatibility

The `AcceleratorRequest` struct includes `UseDRA` and `ResourceClaimTemplate` fields to support future migration toward Dynamic Resource Allocation without requiring API changes. These fields are also relevant for future unified usage in both CaaS and VMaaS.

## Risks and Mitigations

**Complexity of resolution between `AcceleratorRequest` and `resourceClass`**  
Mitigation: Start with validation only in Phase 1. Add more intelligent derivation in Phase 2 if needed.

**Overwhelming tenants with too many options**  
Mitigation: Rely on strong catalog curation and progressive disclosure in the UI. Most tenants should use pre-defined catalog items.

**Future NVIDIA hardware changes**  
Mitigation: Keep the `AcceleratorRequest` model generic. Monitor KubeVirt and NVIDIA work on DRA and new device types.

## Alternatives Considered

1. **Keep everything in `templateParameters` (as JSON)**  
   Rejected because it loses type safety, validation, and discoverability.  
     
2. **Make `resourceClass` fully derived from accelerators**  
   This approach could be too risky for Phase 1. It's better to start with compatibility validation instead. May be explored in Phase 2.
     
3. **Scope only to Instance Type changes (no new type)**  
   This is too risky going forward, because it does not provide the declarative foundation needed for long-term evolution and unification across CaaS and VMaaS. The number of permutations can be too large.

## Implementation Plan

We expect the work to be delivered across the following areas:

1. **`osac-operator`**  
   Add the `AcceleratorRequest` type and embed it in `NodeRequest`. Add basic validation logic. Design the type with future reuse in `ComputeInstance` in mind.  
     
2. **`osac-aap`**  
   Update the post-install playbook to detect accelerator requests and install the NVIDIA GPU Operator when appropriate.  
     
3. **Catalog UI**  
   Add an "Accelerators" section in the Compute step of the cluster creation flow.  
     
4. **Documentation**  
   Update the catalog authoring guide with examples of how to use accelerator configuration in catalog items.

## Upgrade / Downgrade Strategy

N/A for Phase 1 - this is a new field that defaults to empty. Existing clusters without `accelerators` continue to work as before.

## Version Skew Strategy

N/A - the `AcceleratorRequest` field is optional and backward compatible.

## Operational Aspects of API Extensions

### Failure Modes

- **Invalid resourceClass**: If the selected `resourceClass` doesn't support the requested accelerators, the ClusterOrder will transition to `Failed` phase with a clear condition message.
- **GPU Operator installation failure**: If the NVIDIA GPU Operator fails to install, this will be captured in the post-install job status and surfaced in ClusterOrder conditions.

### Support Procedures

Operators supporting clusters with accelerators should:
- Verify GPU nodes are properly labeled (e.g., `nvidia.com/gpu.present=true`)
- Check NVIDIA GPU Operator status: `oc get pods -n nvidia-gpu-operator`
- Validate GPU device plugins are running on worker nodes
- Review ClusterOrder conditions for accelerator-related failures
