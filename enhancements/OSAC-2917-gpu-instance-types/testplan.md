# Test Plan — OSAC-2917 GPU instance types

## Overview

- **Public requirements:** [design.md](design.md), [prd.md](prd.md)
- **Total test cases:** 10

Execution identifies matching assertions on OSAC main. Gaps describe remaining coverage for
the named work owner. No individual assignee or follow-up ticket is recorded here.

## Test cases

#### TC-GPU-01: GpuSpec validation rejects zero, negative and empty required values

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 595-600](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-2917-gpu-instance-types/design.md#L595-L600)
- **Dependencies:** Local protobuf validation with synthetic GpuSpec.
- **Gap:** Server Create acceptance tests and the installed schema were found. A focused assertion for the four rejection rows was not verified.

**Preconditions.** Use baseline selector 10DE:20B0, resource nvidia.com/A100 and count 1.

1. Set count to 0 then -1 and separately clear selector and resource name.
2. Validate each mutation independently.

**Expected results.** Each mutation is rejected and identifies the changed field.

#### TC-GPU-02: The private server accepts an InstanceType without GPU

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 599-600](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-2917-gpu-instance-types/design.md#L599-L600)
- **Dependencies:** Real in-process fulfillment server and PostgreSQL testcontainer; attribution and tenancy fixtures; no provider.
- **Execution:** `fulfillment-service/internal/servers/private_instance_types_server_test.go`
- **Evidence:** `Creates object without GPU` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/servers/private_instance_types_server_test.go#L81)).
- **Selector:** `ginkgo run --timeout 10m --focus='Creates object without GPU' internal/servers` from `fulfillment-service`. Source reviewed, test not run.

**Preconditions.** Use fixture type standard-4-16 with 4 vCPUs and 16 GiB and omit GPU.

1. Create the InstanceType using the private server.
2. Read its returned identity, state, CPU and memory.

**Expected results.** The result is standard-4-16 in ACTIVE state with 4 vCPUs and 16 GiB.

#### TC-GPU-03: The private server preserves a valid GPU specification

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 600-601](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-2917-gpu-instance-types/design.md#L600-L601)
- **Dependencies:** Real in-process fulfillment server and PostgreSQL testcontainer; fixture attribution and tenancy; no GPU hardware.
- **Execution:** `fulfillment-service/internal/servers/private_instance_types_server_test.go`
- **Evidence:** `Creates object with GPU` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/servers/private_instance_types_server_test.go#L125)).
- **Selector:** `ginkgo run --timeout 10m --focus='Creates object with GPU' internal/servers` from `fulfillment-service`. Source reviewed, test not run.

**Preconditions.** Prepare a synthetic type with PCI selector 10DE:20B0, resource nvidia.com/A100 and count 1.

1. Create the GPU type using the private server.
2. Read the GPU fields from its Create response.

**Expected results.** Selector, resource name and count equal the supplied inputs.

#### TC-GPU-04: The deployed control plane places the selected GPU resource on the VM spec

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [design.md, lines 611-627](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-2917-gpu-instance-types/design.md#L611-L627)
- **Dependencies:** Real deployed fulfillment, hub, AAP and KubeVirt APIs; synthetic GPU InstanceType; no GPU hardware or guest readiness assertion.
- **Execution:** `tests/e2e/vmaas/sanity/test_compute_instance_gpu.py`
- **Evidence:** `test_gpu_compute_instance` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/tests/e2e/vmaas/sanity/test_compute_instance_gpu.py#L41)).
- **Selector:** `uv run pytest -n 0 tests/e2e/vmaas/sanity/test_compute_instance_gpu.py::test_gpu_compute_instance` from OSAC root. Source reviewed, test not run.

**Preconditions.** Use the deployed suite fixture and its synthetic GPU type.

1. Create a VM via the tenant CLI, then read its hub CR.
2. Observe the KubeVirt VM and inspect hostDevices.

**Expected results.** The hub CR contains the selected GPU fields and type label, and the KubeVirt VM requests the selected resource name.

#### TC-GPU-05: The mapper leaves GPU absent for a non-GPU InstanceType

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 611-612](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-2917-gpu-instance-types/design.md#L611-L612)
- **Dependencies:** In-process ComputeInstance spec builder, mock InstanceTypes client and fake Kubernetes client. No real API server or GPU hardware.
- **Execution:** `fulfillment-service/internal/controllers/computeinstance/computeinstance_reconciler_function_test.go`
- **Evidence:** `leaves gpu nil when InstanceType has no gpu` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/controllers/computeinstance/computeinstance_reconciler_function_test.go#L3220)).
- **Selector:** Ginkgo focus `leaves gpu nil when InstanceType has no gpu` in `fulfillment-service/internal/controllers/computeinstance`. Source reviewed, test not run.

**Preconditions.** Use the suite CPU-only standard-4-8 InstanceType and its fixture network reference.

1. Build the hub spec for a ComputeInstance using this type.
2. Compare projected CPU, memory and GPU presence.

**Expected results.** The spec has 4 vCPUs and 8 GiB memory, with no GPU struct.

#### TC-GPU-06: The private server rejects GPU edits

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 602-604](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-2917-gpu-instance-types/design.md#L602-L604)
- **Dependencies:** Real in-process fulfillment server and PostgreSQL testcontainer; fixture tenancy and attribution; no GPU provider.
- **Execution:** `fulfillment-service/internal/servers/private_instance_types_server_test.go`
- **Evidence:** `Rejects update of gpu` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/fulfillment-service/internal/servers/private_instance_types_server_test.go#L869)).
- **Selector:** `ginkgo run --timeout 10m --focus='Rejects update of gpu' internal/servers` from `fulfillment-service`. Source reviewed, test not run.

**Preconditions.** Create a GPU type with count 1 and the fixture selector and resource name.

1. Update the count to 2 while retaining CPU and memory.
2. Inspect gRPC status.

**Expected results.** The update returns InvalidArgument and identifies spec.gpu as immutable.

#### TC-GPU-07: GPU list filters distinguish GPU presence and resource name

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [design.md, lines 605-609](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-2917-gpu-instance-types/design.md#L605-L609)
- **Dependencies:** Real fulfillment server and PostgreSQL; synthetic GPU and CPU types; no GPU provider.
- **Gap:** No exact verified List assertions for GPU presence and specific resource filters in the InstanceType server and deployed suite inventory.

**Preconditions.** Create CPU-only, A100 and alternate GPU fixture types.

1. List unfiltered, filter for GPU presence, then filter for nvidia.com/A100.
2. Compare the selected names and GPU data.

**Expected results.** Unfiltered results preserve GPU fields, presence selects both GPU types, and the resource filter selects only A100.

#### TC-GPU-08: CLI table shows the GPU device, resource and count

| Priority | Automation |
|---|---|
| medium | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [design.md, lines 610-610](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-2917-gpu-instance-types/design.md#L610-L610)
- **Dependencies:** In-process table renderer and synthetic response rows; no service.
- **Gap:** No verified three-column assertion in the InstanceType CLI test inventory.

**Preconditions.** Prepare a CPU-only row and a GPU row with the synthetic selector, resource and count.

1. Render the instance type table.
2. Inspect the headers and both rows.

**Expected results.** GPU DEVICE, GPU RESOURCE and GPU COUNT are present and show the GPU row's values without fabricating values for the CPU-only row.

#### TC-GPU-09: The installed ComputeInstance CRD accepts a valid GPU configuration

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [design.md, lines 614-618](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-2917-gpu-instance-types/design.md#L614-L618)
- **Dependencies:** Real API server and etcd with installed CRD; no AAP, KubeVirt workload or GPU hardware.
- **Execution:** `osac-operator/internal/controller/computeinstance_validation_test.go`
- **Evidence:** `should allow creation with valid GPU spec` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/osac-operator/internal/controller/computeinstance_validation_test.go#L539)).
- **Selector:** Ginkgo focus `GPU validation should allow creation with valid GPU spec` in the operator controller envtest suite. Source reviewed, test not run.

**Preconditions.** Use the valid ComputeInstance fixture and set PCI selector 10DE:20B0, resource name nvidia.com/A100 and count 1.

1. Submit the valid fixture to the real envtest API server.
2. Check the Create result.

**Expected results.** CRD admission accepts the requested GPU configuration.

#### TC-GPU-10: The installed ComputeInstance CRD accepts an omitted GPU configuration

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Envtest
- **Owner:** [DEV]
- **References:** [design.md, lines 614-618](https://github.com/osac-project/enhancement-proposals/blob/71a6101a18a06a832695adefc5c505f20f5e24b4/enhancements/OSAC-2917-gpu-instance-types/design.md#L614-L618)
- **Dependencies:** Real API server and etcd with installed CRD; no AAP, KubeVirt workload or GPU hardware.
- **Execution:** `osac-operator/internal/controller/computeinstance_validation_test.go`
- **Evidence:** `should omit gpu from JSON when not set (omitempty)` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/osac-operator/internal/controller/computeinstance_validation_test.go#L556)).
- **Selector:** Ginkgo focus `GPU validation should omit gpu from JSON when not set` in the operator controller envtest suite. Source reviewed, test not run.

**Preconditions.** Use the valid ComputeInstance fixture without a GPU configuration.

1. Submit the fixture to the real envtest API server.
2. Get the created object and inspect its GPU field.

**Expected results.** Create succeeds and the persisted resource has no GPU struct.
