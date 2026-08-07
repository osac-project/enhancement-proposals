# Structured GPU/Accelerator Support for CaaS

| Field       | Value   |
|-------------|---------|
| Author(s)   | Vladik Romanovsky |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1373 |
| Date        | 2026-06-26 |

## Problem Statement

There is no structured way to request GPU or accelerator resources across any of OSAC's service paths today:

- **CaaS (bare metal):** The catalog can present a GPU cluster as a fixed offering (e.g., "OpenShift on NICo with DGX nodes"), but the GPU capability is baked into the template name. Tenants cannot select GPU model, count, or sharing mode — each combination requires a separate catalog item.
- **VMaaS:** GPU passthrough is configured via PCI vendor:product IDs passed as opaque JSON in template parameters. Tenants need to know hardware-level identifiers, and the catalog cannot surface GPU options because there is no typed schema to build on.
- **BMaaS:** There is no GPU request mechanism at all.

This lack of structure means no validation at request time, no catalog-driven GPU selection, and no way to automatically coordinate GPU requests with fabric setup (e.g., triggering InfiniBand PKey or NVLink partition configuration when GPUs are requested on a high-performance subnet).

The current ad-hoc approach also makes it difficult to maintain a consistent experience as we add GPU support across service paths, and creates a hard coupling to the device-plugin model that will need to be replaced when KubeVirt adopts DRA (Dynamic Resource Allocation).

## Goals

We will not ship this feature unless we can deliver the following user-facing capabilities:

- Tenants can request GPUs through simple, high-level options in the catalog and receive a working, AI-ready cluster without manual post-install steps.
- Users get clear, actionable feedback when a GPU request cannot be fulfilled (including why it failed and what alternatives exist).
- Catalog authors can create reusable "AI-ready" cluster offerings with sensible defaults.
- A single structured accelerator request model works across CaaS, VMaaS, and BMaaS — avoiding three different ways of asking for GPUs as each path adds accelerator support.
- The accelerator request model is decoupled from the current device-plugin mechanism, so it can serve as the stable tenant API when the backend transitions to DRA.
- Accelerator requests can be correlated with networking fabric configuration (e.g., east-west IB/NVLink setup) because the system knows what GPUs are being requested in a structured way.

## User Stories

### Data Scientist / AI Engineer (Tenant User)

- As a data scientist, I want to request a GPU cluster by choosing a workload type (training, inference, or general development) and a size tier (small, medium, or large), so that I can get an AI-ready cluster without needing to know specific GPU models or infrastructure details.
- As a data scientist, I want my GPU cluster to be ready to use as soon as it reaches the "Ready" state, with GPU drivers and device plugins already installed, so that I can start running workloads immediately.
- As a data scientist, I want clear feedback when my GPU request cannot be fulfilled — including why it failed and what alternatives are available — so that I can adjust my request without opening a support ticket.

### Platform Engineer (Tenant Admin)

- As a platform engineer, I want to request specific GPU models and quantities when ordering a cluster, so that I can precisely match infrastructure to my team's workload needs.
- As a platform engineer, I want to choose the GPU sharing mode (dedicated, vGPU, or MIG) when ordering, so that I can balance performance and cost for my workloads.
- As a platform engineer, I want to see which GPU models are available in each resource class before ordering, so that I can choose compatible configurations without trial and error.
- As a platform engineer, I want to know when a chosen sharing mode requires additional configuration beyond what is automatically handled, so that I can plan the extra work.

### Cloud Provider Admin

- As a cloud provider admin, I want to control which GPU models and quantities each tenant can request, so that expensive GPU resources are shared fairly.
- As a cloud provider admin, I want GPU requests to be validated against available hardware at order time, so that incompatible requests are rejected with helpful guidance.
- As a cloud provider admin, I want visibility into GPU provisioning success rates, failure reasons, and times, so that I can identify and fix infrastructure issues.

### Catalog Author

- As a catalog author, I want to define high-level GPU offerings (for example "AI Training – Large") that map to concrete GPU configurations, so that non-expert tenants can easily order AI-ready clusters.
- As a catalog author, I want the catalog to also offer an advanced mode where power users can specify exact GPU parameters when needed.
- As a catalog author, I want GPU mappings to be stored as declarative configuration that I can update without changing code, so that I can add new GPU models or adjust offerings as hardware availability changes.

## In Scope (Phase 1)

- Structured GPU/accelerator requests when creating CaaS clusters
- Automatic installation of the NVIDIA GPU Operator so that clusters with dedicated GPUs are AI-ready out of the box
- High-level, guided GPU selection in the catalog for non-expert users
- Clear validation and error handling for GPU requests
- Ability for platform admins to control GPU access and quotas per tenant

## Out of Scope (Phase 1)

- VMaaS (`ComputeInstance`) GPU support — planned for Phase 2+
- Non-NVIDIA accelerators
- Full automation of vGPU and MIG modes
- **Dynamic Resource Allocation (DRA)** — KubeVirt DRA support is alpha today and not ready for production use. The `AcceleratorRequest` model is designed so that when DRA matures, the backend can switch from template parameters to DRA ResourceClaims without changing the tenant-facing API. Full DRA integration is Phase 2+.
- Mixing different GPU models or vendors on the same node

## Success Criteria

We will consider this feature complete when:

- A data scientist can select a GPU-enabled offering in the catalog and receive a provisioned cluster that is ready to run GPU workloads immediately.
- Users receive clear, actionable error messages (with suggestions where possible) when a GPU request cannot be fulfilled.
- Catalog authors can create and maintain GPU-enabled offerings using high-level mappings.
- Existing clusters that do not request GPUs continue to provision exactly as they do today.
- The accelerator request model works consistently across CaaS, VMaaS, and BMaaS — adding GPU support to a new service path reuses the same type, not a separate mechanism.
- The accelerator request model does not depend on the device-plugin framework, so adopting DRA later is a backend change, not an API change.

## Assumptions

- Phase 1 focuses on NVIDIA GPUs and uses the NVIDIA GPU Operator as the mechanism for GPU enablement.
- The accelerator request model (`AcceleratorRequest`) is designed to be extensible, so support for other GPU vendors (AMD, Intel, etc.) and other accelerator types can be added in future phases without major changes to the core request structure.
- Resource class definitions will eventually declare which GPU models and accelerator types they support.
- Users who request advanced sharing modes (vGPU or MIG) understand that Phase 1 does not fully automate these configurations.
- The catalog can maintain mappings from high-level offerings to specific accelerator configurations using declarative configuration.

## Dependencies

- Catalog UI and backend updates to present high-level GPU options and an advanced toggle.
- Post-install automation to detect GPU requests and install the NVIDIA GPU Operator for dedicated mode.
- Resource class metadata to declare supported GPU models (needed for validation and helpful errors).
