# Testplan — OSAC-4277

## Overview

- **Feature:** OSAC-4277 — VM Resize via InstanceType Selection
- **Total test cases:** 15
- **Requirements covered:** 8 of 8 (FR-1 through FR-6, NFR-1, NFR-2)
- **Interface changes covered:** 4 of 4 (IC-1 through IC-4)

## Test Cases

### FR-1: API to change a ComputeInstance's InstanceType

#### TC-FR1-01: Resize ComputeInstance to a different InstanceType

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- A ComputeInstance exists in RUNNING state with instance_type "small"
  (e.g., 2 cores, 4 GiB)
- An InstanceType "medium" exists in ACTIVE state (e.g., 4 cores, 8 GiB)

##### Steps

1. Call `UpdateComputeInstance` with update mask `spec.instance_type` and
   target instance_type = "medium"
2. Wait for `ConfigurationApplied` condition to become True

##### Expected Results

- The Update RPC returns HTTP 200 / gRPC OK
- The ComputeInstance's `spec.instance_type` reference changes to "medium"
- The CRD's `spec.cores` updates to 4 and `spec.memoryGiB` updates to 8
- `ConfigurationApplied` transitions False → True after AAP re-provisioning

#### TC-FR1-02: Resize a stopped ComputeInstance

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- A ComputeInstance exists in STOPPED state with instance_type "small"
- An InstanceType "medium" exists in ACTIVE state

##### Steps

1. Call `UpdateComputeInstance` with update mask `spec.instance_type` and
   target instance_type = "medium"
2. Call `UpdateComputeInstance` with `spec.run_strategy = Always` to start
   the VM
3. Wait for the ComputeInstance to reach RUNNING state

##### Expected Results

- The Update RPC returns HTTP 200 / gRPC OK
- After starting, the KubeVirt VM runs with 4 cores and 8 GiB memory
  (matching InstanceType "medium")
- No `RestartRequired` condition is set (change applied during start)

### FR-2: Both increasing and decreasing InstanceType selections supported

#### TC-FR2-01: Resize to a smaller InstanceType (downsize)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- A ComputeInstance exists in RUNNING state with instance_type "medium"
  (4 cores, 8 GiB)
- An InstanceType "small" exists in ACTIVE state (2 cores, 4 GiB)

##### Steps

1. Call `UpdateComputeInstance` with update mask `spec.instance_type` and
   target instance_type = "small"
2. Wait for `ConfigurationApplied` condition to become True

##### Expected Results

- The Update RPC returns HTTP 200 / gRPC OK
- The CRD's `spec.cores` updates to 2 and `spec.memoryGiB` updates to 4
- `ConfigurationApplied` transitions False → True after AAP re-provisioning

#### TC-FR2-02: Resize with mixed direction (increase CPU, decrease memory)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | medium | automated |

##### Preconditions

- A ComputeInstance exists with instance_type "a" (2 cores, 8 GiB)
- An InstanceType "b" exists in ACTIVE state (4 cores, 4 GiB)

##### Steps

1. Call `UpdateComputeInstance` with update mask `spec.instance_type` and
   target instance_type = "b"
2. Wait for `ConfigurationApplied` condition to become True

##### Expected Results

- The Update RPC returns HTTP 200 / gRPC OK
- The CRD's `spec.cores` updates to 4 and `spec.memoryGiB` updates to 4
- The API does not reject the request based on direction of change

### FR-3: Resize target eligibility follows InstanceType lifecycle-state rules

#### TC-FR3-01: Resize to a DEPRECATED InstanceType succeeds with warning

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- A ComputeInstance exists with instance_type "current" (ACTIVE)
- An InstanceType "deprecated-type" exists in DEPRECATED state with
  replacement "replacement-type" and obsolescence date set

##### Steps

1. Call `UpdateComputeInstance` with update mask `spec.instance_type` and
   target instance_type = "deprecated-type"

##### Expected Results

- The Update RPC returns HTTP 200 / gRPC OK
- The response includes a deprecation warning containing the replacement
  InstanceType name and obsolescence date
- The ComputeInstance's `spec.instance_type` changes to "deprecated-type"

#### TC-FR3-02: Resize to an OBSOLETE InstanceType is rejected

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- A ComputeInstance exists with instance_type "current" (ACTIVE)
- An InstanceType "obsolete-type" exists in OBSOLETE state

##### Steps

1. Call `UpdateComputeInstance` with update mask `spec.instance_type` and
   target instance_type = "obsolete-type"

##### Expected Results

- The Update RPC returns gRPC `FailedPrecondition` (HTTP 400)
- The ComputeInstance's `spec.instance_type` remains "current" (unchanged)
- No reconciliation or re-provisioning is triggered

#### TC-FR3-03: Resize to a non-existent InstanceType is rejected

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | medium | automated |

##### Preconditions

- A ComputeInstance exists with instance_type "current"

##### Steps

1. Call `UpdateComputeInstance` with update mask `spec.instance_type` and
   target instance_type = "nonexistent"

##### Expected Results

- The Update RPC returns gRPC `NotFound` (HTTP 404)
- The ComputeInstance's `spec.instance_type` remains "current" (unchanged)

### FR-4: No-op detection for same InstanceType

#### TC-FR4-01: Resize to current InstanceType is a no-op

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | critical | automated |

##### Preconditions

- A ComputeInstance exists with instance_type "current" (ACTIVE)

##### Steps

1. Call `UpdateComputeInstance` with update mask `spec.instance_type` and
   target instance_type = "current"

##### Expected Results

- The Update RPC returns HTTP 200 / gRPC OK
- No change is persisted to the database (spec remains identical)
- No reconciliation or re-provisioning is triggered
- `ConfigurationApplied` remains True (no config version change)

#### TC-FR4-02: No-op takes precedence over lifecycle validation

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | automated |

##### Preconditions

- A ComputeInstance exists with instance_type "deprecated-type"
- "deprecated-type" is now in OBSOLETE state

##### Steps

1. Call `UpdateComputeInstance` with update mask `spec.instance_type` and
   target instance_type = "deprecated-type" (same as current)

##### Expected Results

- The Update RPC returns HTTP 200 / gRPC OK (not FailedPrecondition)
- No lifecycle validation error, despite the InstanceType being OBSOLETE
- No change is persisted; no reconciliation triggered

### FR-5: Hot-plug where possible; restart required otherwise

#### TC-FR5-01: RestartRequired condition set when hot-plug not supported

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

##### Preconditions

- A ComputeInstance exists in RUNNING state
- KubeVirt deployment does not support CPU/memory hot-plug for the
  requested change (or `VMLiveUpdateFeatures` is not enabled)
- A target InstanceType with different cores/memory exists in ACTIVE state

##### Steps

1. Call `UpdateComputeInstance` with the target instance_type
2. Wait for `ConfigurationApplied` condition to become True

##### Expected Results

- The ComputeInstance status shows `RestartRequired` condition = True
- The VM continues running with the previous CPU/memory values
- The ComputeInstance's `spec.instance_type` reflects the new target

### FR-6: User restarts manually after resize

#### TC-FR6-01: Manual restart clears RestartRequired after resize

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | critical | automated |

##### Preconditions

- A ComputeInstance has `RestartRequired` condition = True after a resize
- The ComputeInstance is in RUNNING state

##### Steps

1. Call `UpdateComputeInstance` with `spec.restart_requested_at` set to
   the current timestamp
2. Wait for the ComputeInstance to complete the restart cycle (RUNNING →
   restart → RUNNING)

##### Expected Results

- The `RestartRequired` condition transitions to False
- The VM now runs with the new CPU/memory values matching the target
  InstanceType
- `lastRestartedAt` is updated to reflect the restart

### NFR-1: E2E tests for InstanceType resize scenarios

#### TC-NFR1-01: End-to-end resize lifecycle

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| — | critical | automated |

##### Preconditions

- A fully provisioned ComputeInstance in RUNNING state
- Multiple InstanceTypes exist with different cores/memory configurations

##### Steps

1. Resize from InstanceType A to InstanceType B
2. Verify the VM reflects the new compute resources
3. If `RestartRequired` is True, restart the VM and verify resources again
4. Resize back from InstanceType B to InstanceType A
5. Verify the VM reflects the original compute resources

##### Expected Results

- Both resize operations complete with `ConfigurationApplied` = True
- The KubeVirt VM's CPU and memory match the selected InstanceType after
  each resize (and restart if required)
- The ComputeInstance transitions through expected states without errors

### NFR-2: Documentation for InstanceType resize operations

#### TC-NFR2-01: Resize documentation is complete and accurate

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| — | high | manual |

##### Preconditions

- Design is implemented and documentation deliverables are produced

##### Steps

1. Review API reference documentation for ComputeInstance Update RPC —
   verify it documents instance_type mutability, lifecycle-state
   validation, no-op behavior, and deprecation warnings
2. Review user guide for resize workflow — verify it covers how to change
   InstanceType, interpret RestartRequired, and restart the VM
3. Review deployment guide for hot-plug configuration — verify it covers
   KubeVirt feature gate requirements

##### Expected Results

- API reference documents the `spec.instance_type` field as mutable with
  lifecycle-state validation rules (ACTIVE, DEPRECATED with warning,
  OBSOLETE rejected)
- User guide includes a step-by-step resize workflow with expected
  outcomes for each state
- Deployment guide specifies which KubeVirt feature gates enable live
  resize vs. restart-required behavior

## Gaps

### Requirement Coverage Gaps

All PRD requirements have test cases.

### Interface Change Coverage Gaps

All interface changes are exercised by test cases.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 15 |
| Critical | 5 |
| High | 6 |
| Medium | 2 |
| Low | 0 |
| Automated | 14 |
| Manual | 1 |
| Requirements with test cases | 8 / 8 |
| Interface changes with test cases | 4 / 4 |
