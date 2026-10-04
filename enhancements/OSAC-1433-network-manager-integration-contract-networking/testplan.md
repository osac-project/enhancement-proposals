# Testplan — OSAC-1433-network-manager-integration-contract-networking

## Overview

- **Feature:** Network Manager Integration Contract
- **Total test cases:** 6
- **Requirements covered:** 4 of 4 functional requirements
- **Interface changes covered:** 4 of 4

## Test Cases

### FR-1: Source-neutral manager conformance

#### TC-FR1-01: Dispatch to a role outside the OSAC collection

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- A valid Fabric Manager registration uses `implementationRef: acme.networking.fabric_manager`.
- The collection is installed in the AAP execution environment and provides every Fabric Manager task required by contract v1.

##### Steps

1. Select the manager by its logical registration name in NetworkClass.
2. Create a VirtualNetwork through the existing tenant API.
3. Observe the AAP job and backend state.

##### Expected Results

- AAP invokes the registered FQCN and fixed `create_virtual_network` task, independently of the manager's logical name.
- The selected implementation reconciles the resource and OSAC reports it Ready after AAP succeeds.
- No supplier-specific tenant API or OSAC dispatch code is required for this registered implementation.

### FR-2: Exact manager implementation requirements

#### TC-FR2-01: Reject an invalid manager registration

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- The operator watches a test namespace with manager registration ConfigMaps.
- The test AAP provider records whether an AAP job was created.

##### Steps

1. Create registrations with an unsupported contractVersion, malformed implementationRef, missing required fields, unknown role labels, or duplicate logical names.
2. Reconcile a NetworkClass that selects each invalid manager.

##### Expected Results

- Each invalid registration reports its ConfigMap and invalid field.
- OSAC creates no AAP job for an invalid registration.

#### TC-FR2-02: Validate ExternalIP and DHCP lease results

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- A conforming Fabric Manager provides the contract-required ExternalIP allocation and DHCP lease query tasks for the tested target.
- The test backend returns a stable allocated address and a matching lease.

##### Steps

1. Reconcile an ExternalIP twice, then run `dhcp_lease.query` for a network attachment.
2. Observe the resource annotation, AAP artifacts, and workload status.

##### Expected Results

- Both ExternalIP reconciliations retain the same `osac.openshift.io/allocated-address` value.
- The query job exposes a `leases` artifact with `subnet_ref`, `interface`, `ip_address`, and `mac_address`.
- OSAC reports the matching address for the requested attachment.

#### TC-FR2-03: Verify complete role operation and target coverage

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- A contract conformance harness can load the candidate Fabric or K8s Manager collection.
- The v1 role dispatch matrix and required target combinations are available to the harness.

##### Steps

1. Enumerate every operation and target combination assigned to the candidate manager role by contract v1.
2. Invoke each required `tasks_from` entry point with a valid resource fixture.
3. Check each task's required result, retry-safe behavior, and error contract.

##### Expected Results

- The collection provides a task entry point for every operation and target combination assigned to its role; registration has no mechanism to declare an operation subset.
- Every task meets the v1 input, desired-state, result, and failure requirements.

### FR-3: Provider selection with one tenant networking API

#### TC-FR3-01: Combine conforming Fabric and K8s implementations from different sources

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-2 | high | automated |

##### Preconditions

- A conforming Fabric implementation and a conforming K8s implementation are installed in the AAP execution environment.
- Each has a role-labeled registration with a distinct logical name and implementationRef.

##### Steps

1. Configure NetworkClass to select the two managers.
2. Create a Subnet using the existing tenant networking API.
3. Observe the jobs dispatched to both assigned roles.

##### Expected Results

- OSAC dispatches each assigned operation to the selected implementation for its role.
- Both implementations receive the resource shape defined by the contract.
- No tenant API change is required to select implementations from different sources.

### FR-4: Reject work unavailable in the selected profile without silent fallback

#### TC-FR4-01: Reject a profile-unavailable operation before AAP

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | critical | automated |

##### Preconditions

- The selected NetworkClass uses a K8s-only profile, which does not route `nat_gateway.create` to a K8s Manager.
- The test AAP provider records whether a job was created.

##### Steps

1. Request creation of a NATGateway.
2. Observe the resource condition and AAP job count.

##### Expected Results

- The resource receives a clear diagnostic that NATGateway requires a Fabric Manager.
- No AAP job is created and the K8s Manager does not receive the operation.

## Gaps

### Requirement Coverage Gaps

All PRD functional requirements have test cases.

### Interface Change Coverage Gaps

All interface changes are exercised by test cases.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 6 |
| Critical | 4 |
| High | 2 |
| Medium | 0 |
| Low | 0 |
| Automated | 6 |
| Manual | 0 |
| Requirements with test cases | 4 / 4 |
| Interface changes with test cases | 4 / 4 |
