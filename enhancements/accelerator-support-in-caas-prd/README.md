---
title: Accelerator / GPU Support in Cluster as a Service Requirements
authors:
  - vladikr@redhat.com
creation-date: 2026-06-08
last-updated: 2026-06-09
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1373
see-also:
  - Accelerator Support Design: /enhancements/accelerator-support-in-caas
replaces:
  - N/A
superseded-by:
  - N/A
---

# Accelerator / GPU Support in Cluster as a Service Requirements

## 1. Problem Statement

As it is today, there is no structured, first-class way for tenants to request GPU or accelerator resources when creating a cluster through OSAC's Cluster as a Service (CaaS).

Current mechanisms rely on `resourceClass` selection and free-form `templateParameters`. This leads to several issues:

- No typed and consistent model to express accelerator requirements (such as model, quantity, or sharing mode).  
- No automatic installation of the NVIDIA GPU Operator when GPUs are requested.  
- Tenants who want an "AI-ready" cluster still need to perform manual post-install configuration.  
- The current approach is not well positioned for future NVIDIA hardware or the shift toward Dynamic Resource Allocation (DRA).

Many target users (data scientists and AI engineers) do not have deep infrastructure knowledge. They often simply want a working AI-ready cluster without needing to understand the implications of requesting bare metal or virtual nodes, dedicated GPUs vs vGPUs, or specific device profiles.

## 2. Goals

- Enable tenants to request accelerator resources in a clear and structured way when ordering CaaS clusters.  
- Make it possible for clusters that request GPUs to be **AI-ready by default** (with appropriate hardware and operators pre-configured).  
- Introduce a **declarative and reusable backend model** for expressing accelerator requirements. This model should serve as a foundation that can be used across both CaaS and VMaaS, avoiding fragmented evolution of accelerator handling in the two paths.  
- Improve usability through the catalog layer while keeping the backend flexible and powerful for advanced use cases.

## 3. Success Criteria

- A tenant can order a GPU-enabled cluster through the catalog and receive a functional cluster with working accelerator resources and the NVIDIA GPU Operator pre-installed.  
- Catalog authors can create rich "AI-ready" offerings using structured accelerator configuration options.  
- The solution provides a foundation that can evolve toward DRA and newer NVIDIA hardware.  
- There is a clear separation between the simple tenant experience (catalog) and the more powerful declarative backend.  
- The accelerator model is designed with reuse in mind, so that `ClusterOrder` and `ComputeInstance` can converge on a consistent way of requesting accelerators instead of evolving separately.

## 4. Non-Goals (Initial Scope)

- Full implementation of Dynamic Resource Allocation (DRA).  
- Changes to the VM as a Service (`ComputeInstance`) path in Phase 1.  
- Support for non-NVIDIA accelerators in the first phase.

## 5. Proposed Direction

Introduce a declarative way to express accelerator requirements as part of cluster creation. This model should allow the system to understand what accelerators are needed on the nodes of the cluster.

The solution should follow a layered approach with three main layers:

- **Catalog layer**: Focuses on usability. Most tenants interact through curated catalog items and higher-level options rather than raw technical fields.  
- **Backend API layer**: Provides a declarative, typed, and **reusable** model for accelerator requirements (intended to be shared between `ClusterOrder` and `ComputeInstance` in the long term).  
- **Implementation layer**: Resolves declared requirements into hardware provisioning and post-install configuration, including automatic operator installation when appropriate.

**Long-term vision for API unification:** Even though full integration with VMaaS (`ComputeInstance`) is out of scope for the initial phase, the `AcceleratorRequest` type is intentionally designed to be reusable. The goal is to establish one coherent way of requesting accelerators across OSAC, so that CaaS and VMaaS do not evolve incompatible accelerator models over time.

## 6. User Experience

### Current Experience (Before)

Today, requesting GPUs requires understanding low-level details and using untyped parameters:

```yaml
apiVersion: osac.openshift.io/v1alpha1
kind: ClusterOrder
metadata:
  name: ai-cluster
spec:
  templateID: openshift-cluster
  # GPU config buried in opaque JSON string
  templateParameters: '{"gpu_model": "H100", "gpu_count": "2", "gpu_mode": "dedicated"}'
  nodeRequests:
    - resourceClass: metal-worker-gpu  # Must know which class has GPUs
      numberOfNodes: 3
```

Problems:
- No validation of GPU parameters
- Unclear which `resourceClass` values support GPUs
- No automatic operator installation
- Different templates may use different parameter names

### Proposed Experience (After)

With structured accelerator support:

```yaml
apiVersion: osac.openshift.io/v1alpha1
kind: ClusterOrder
metadata:
  name: ml-training-cluster
spec:
  templateID: ai-ready-cluster
  nodeRequests:
    - resourceClass: metal-worker-gpu
      numberOfNodes: 3
      accelerators:                     # NEW: Structured, typed GPU request
        - type: nvidia.com/gpu
          model: H100                    # Validated against known models
          count: 2                       # GPUs per node
          mode: dedicated                # Enum: dedicated, vgpu, mig
```

Benefits:
- **Type-safe**: Fields are validated at admission time
- **Self-documenting**: Clear what each field means
- **Discoverable**: API schema shows valid options
- **Consistent**: Same structure will work for ComputeInstance in the future
- **AI-ready**: Cluster is provisioned with NVIDIA GPU Operator pre-installed

## 7. Key Considerations

### Usability

Many users do not know (and probably should not need to know) low-level infrastructure details. The catalog experience must therefore guide users toward good defaults, while the backend model remains expressive enough for advanced scenarios.

### AI-Ready Expectation

When accelerators are requested, there is a strong expectation that the resulting cluster should be ready to use them with minimal additional work from the tenant. This includes proper hardware selection and installation of relevant operators.

### API Unification Across CaaS and VMaaS

We want to prevent accelerator handling from diverging between `ClusterOrder` and `ComputeInstance`. Introducing `AcceleratorRequest` as a shared building block now establishes a unified API direction, even though VMaaS integration is planned for a later phase.

## 8. High-Level Phasing

**Phase 1:**  
Introduce structured accelerator support in cluster requests (`ClusterOrder`) along with automatic installation of the NVIDIA GPU Operator. Define `AcceleratorRequest` as a reusable type.

**Phase 2:**  
Improve the catalog so tenants can more easily select appropriate accelerator configurations.

**Phase 3:**  
Evolve usage of `AcceleratorRequest` into the VMaaS path (`ComputeInstance`) and add support for Dynamic Resource Allocation (DRA) and future NVIDIA hardware.
