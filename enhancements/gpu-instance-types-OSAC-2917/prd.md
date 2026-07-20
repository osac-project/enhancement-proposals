# GPU-Enabled Compute Instances

| Field       | Value   |
|-------------|---------|
| Author(s)   | Tzif Morgenshtern |
| Jira        | https://redhat.atlassian.net/browse/OSAC-2917 |
| Service     | VMaaS |
| Date        | 2026-07-20 |

## Problem Statement

OSAC tenants cannot create GPU-accelerated virtual machines. The ComputeInstance resource only models CPU cores, memory, and disk — there is no way to request GPU hardware. As sovereign AI cloud adoption grows, tenants need self-service access to GPU-equipped VMs for AI/ML training, fine-tuning, and inference workloads. Without this capability, tenants must provision GPU workloads outside OSAC, bypassing its multitenant isolation and resource management.

## In Scope

- Cloud Provider Admins can define InstanceTypes that include GPU hardware specifications (GPU type and count alongside existing CPU and memory fields)
- Tenant Users can select a GPU-enabled InstanceType when creating a ComputeInstance and receive a VM with GPU hardware attached
- GPU VMs use the same networking, storage, and lifecycle model as existing ComputeInstances

## Out of Scope

- GPU discovery API — programmatic detection of available GPU hardware on cluster nodes is a separate future feature `[Clarify: R1.Q6]`
- Per-tenant GPU quotas — OSAC does not yet have a quota system; GPU quotas will be added when the general quota system is built `[Clarify: R1.Q1]`
- Preemptible VMs — preemptible scheduling and eviction policies are a separate feature `[Clarify: R1.Q2]`
- MIG (Multi-Instance GPU) partitioning and vGPU support `[Clarify: R1.Q8]`
- GPU clusters with InfiniBand interconnect for multi-node training `[Clarify: R1.Q8]`
- GPU VM live migration — not supported by current KubeVirt GPU passthrough
- GPU-compatible boot image filtering — tenant responsibility to select an appropriate image
- Multi-cluster GPU placement — this feature assumes a single VMaaS cluster `[Clarify: R1.Q7]`
- GPU type validation — the system does not validate that a GPU type specified in an InstanceType exists on the cluster; Cloud Provider Admin is responsible for correctness `[Clarify: R1.Q4]`
- Cost estimation and billing integration

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to define InstanceTypes that include GPU type and count so that tenants can select pre-validated GPU configurations when creating VMs.
- As a Cloud Provider Admin, I want to retire or update GPU-enabled InstanceTypes when the underlying GPU hardware changes so that tenants do not select configurations that cannot be fulfilled.

### Cloud Infrastructure Admin

- Not affected by this feature. GPU node installation and configuration is a prerequisite handled outside OSAC.

### Tenant Admin

- Not affected by this feature.

### Tenant User

- As a Tenant User, I want to see which InstanceTypes include GPU hardware so that I can choose the right configuration for my AI/ML workload.
- As a Tenant User, I want to create a ComputeInstance using a GPU-enabled InstanceType so that my VM is provisioned with GPU hardware attached.
- As a Tenant User, I want GPU VMs to behave the same as non-GPU VMs for lifecycle operations (start, stop, restart, delete) so that I do not need to learn a separate workflow.

## Assumptions

- The VMaaS cluster has GPU-equipped worker nodes with the appropriate device plugins installed and configured. Cloud Infrastructure Admin is responsible for this prerequisite.
- GPU passthrough infrastructure (KubeVirt HyperConverged CR configuration, permitted host devices) is already in place via the work delivered in OSAC-42.
- A single VMaaS cluster is used — no cross-cluster placement decisions are required. `[Clarify: R1.Q7]`

## Dependencies

- **OSAC-42 (VMs with GPU passthrough):** Delivered the Ansible-level GPU passthrough plumbing in `osac-aap`. The provisioning template already supports a GPU devices parameter for KubeVirt host device passthrough. This feature builds the user-facing layer on top of that foundation.
- **InstanceType / Catalog Items (OSAC-58):** GPU fields extend the existing InstanceType resource. Changes must align with the InstanceType model established by OSAC-1205 and any ongoing catalog work in OSAC-58.

## Acceptance Criteria

- [ ] A Cloud Provider Admin can create an InstanceType that specifies GPU type and GPU count in addition to CPU and memory
- [ ] A Tenant User can list InstanceTypes and identify which ones include GPU hardware
- [ ] A Tenant User can create a ComputeInstance using a GPU-enabled InstanceType and the resulting VM has GPU hardware attached
- [ ] A GPU-equipped ComputeInstance supports the same lifecycle operations as a non-GPU ComputeInstance (start, stop, restart, delete)
- [ ] GPU ComputeInstances carry the standard OSAC tenant isolation metadata
- [ ] A Cloud Provider Admin can update or delete GPU-enabled InstanceTypes

---

## Provenance

Authored: draft @ prd 0.5.0 - 92734a2, workspace main @ 2181523

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.5.0","ai_workflows":"92734a2","source_repo":"2181523","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft"],"authoring_modes":["skill"],"context_changed":false} -->
