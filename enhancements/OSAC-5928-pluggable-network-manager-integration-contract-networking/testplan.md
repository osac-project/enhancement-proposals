# Testplan — OSAC-5928-pluggable-network-manager-integration-contract-networking

## Overview

- **Feature:** Pluggable Network Manager Integration Contract
- **Total test cases:** 8
- **Requirements covered:** 6 of 6 functional requirements
- **Interface changes covered:** 5 of 5

## Test Cases

### FR-1 and FR-6: Source-neutral manager conformance and AAP dependency boundary

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

1. Create registrations with an unsupported contractVersion, malformed implementationRef, missing required fields, unknown role labels, duplicate logical names, and malformed or duplicate peer names.
2. Reconcile a NetworkClass that selects each invalid manager.

##### Expected Results

- Each invalid registration reports its ConfigMap and invalid field.
- OSAC creates no AAP job for an invalid registration.

#### TC-FR2-02: Validate ExternalIP annotation handoff and DHCP lease results

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- A conforming Fabric Manager provides the contract-required ExternalIP allocation and DHCP lease query tasks for the tested target.
- The test backend retains reservations by ExternalIP UID and can write canonical, malformed, and out-of-pool annotation values.
- The manager result artifact contains the common operation/UID/generation envelope and no ExternalIP address payload.
- The test can exercise an allocation job with a stale UID or generation.

##### Steps

1. Reconcile an ExternalIP twice; inspect the provider reservation, ExternalIP annotation, common AAP result envelope, and ExternalIP status.
2. Configure a test manager to write a non-canonical or out-of-pool address annotation for another ExternalIP while returning a valid common result envelope; inspect its status and pool capacity.
3. Attempt to write an address annotation using a stale UID or generation for an ExternalIP with the same name; then run `dhcp_lease.query` for a network attachment.

##### Expected Results

- The manager writes the reserved address to `osac.openshift.io/allocated-address`; a retry for the same UID reuses the reservation and writes the same annotation value.
- The AAP artifact identifies the operation, resource UID, and generation but contains no ExternalIP address. OSAC validates that envelope and the annotation's canonical IPv4 form and pool membership before setting `ExternalIP.status.address` and Allocated readiness.
- OSAC leaves an ExternalIP non-ready and does not publish an accepted status address when the annotation is missing, non-canonical, or outside the selected pool; API-side capacity remains reserved for retry or cleanup.
- UID/generation preconditions prevent a stale task from writing the annotation to a replacement object or newer generation.
- The query job returns `osac_result.data.leases` with `subnetRef`, `interface`, `ipAddress`, and `macAddress` for the requested BaremetalInstance attachment.
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

#### TC-FR2-04: Verify SecurityGroup binding lifecycle and semantics

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- The candidate manager implements `security_group.apply` for every target assigned to its profile.
- At least two workload bindings can be placed on the same Subnet and attached to different SecurityGroups.

##### Steps

1. Create SecurityGroups with overlapping and distinct allow rules; attach two groups to one binding and a different group to another binding.
2. Verify each apply invocation receives the complete current `context.securityGroup.attachments` snapshot with stable binding UIDs.
3. Add and remove a binding, update rules, and delete a group while recording operation order, retry the same desired state, and inspect packet behavior.

##### Expected Results

- The effective allow set for a binding is the union of its attached groups; rules from another binding's groups do not leak across the shared Subnet.
- Attach applies policy before the workload attachment becomes Ready. Detach removes the workload from the network before the later snapshot removes its policy.
- Updates remove obsolete policy, established return traffic is allowed, unmatched traffic is denied when a group is attached, and retries converge without duplicate or stale policy.
- A binding absent from a later snapshot has no policy owned by that SecurityGroup.

### FR-3: Provider selection with one tenant networking API

#### TC-FR3-01: Combine conforming Fabric and K8s implementations from different sources

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-2, IC-5 | high | automated |

##### Preconditions

- A Fabric and K8s implementation with distinct logical names are installed in the AAP execution environment.
- Their role-labeled registrations declare the required capabilities and mutually name one another as compatible.
- The exact collection versions are recorded as a pair-test fixture.

##### Steps

1. Configure NetworkClass to select the mutually declared pair.
2. Create a Subnet using the existing tenant networking API.
3. Observe the Fabric job, contract ConfigMap, OSAC validation, and K8s job input.
4. Repeat the create at the same UID/generation, then delete the Subnet.

##### Expected Results

- OSAC dispatches each assigned operation to the selected implementation for its role.
- Fabric writes the standard handoff ConfigMap with VNI, route-target, reserved-CIDR, UID, and generation values; OSAC validates and pins its UID/resourceVersion; K8s reads that same ConfigMap and uses the values to provision the matching network.
- Retry is idempotent and deletion retains the ConfigMap until both manager cleanup stages succeed, then removes it.
- No tenant API or supplier-specific OSAC change is required to select implementations from different sources. The backend collection and any provider SDK/module dependencies are installed in AAP; this conformance case requires no supplier-specific code in the OSAC operator or UI.

### FR-3: Provider selection with one tenant networking API

#### TC-FR3-02: Reject a manager pair without mutual compatibility

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-3 | critical | automated |

##### Preconditions

- The test inventory contains Fabric and K8s registrations with the `evpn-vxlan` capability but no mutual peer declaration, a one-sided declaration, and an explicitly compatible pair.
- The inventory also contains Agentless VLAN and `cudn_evpn` registrations.

##### Steps

1. Attempt to select each non-mutual pair in NetworkClass and through Enclave installation.
2. Attempt to select the declared compatible pair.

##### Expected Results

- Shared capabilities alone and one-sided peer declarations do not make a pair eligible; Agentless VLAN plus `cudn_evpn` is rejected before AAP.
- The diagnostic identifies the incompatible Fabric/K8s pair and missing reciprocal declaration.
- OSAC makes the mutually declared pair eligible after capability and registration checks. The pair release gate independently runs the integration suite against the exact AAP collection versions before the publisher lists the pair; OSAC does not claim to run that suite at selection time.

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
| Total test cases | 8 |
| Critical | 6 |
| High | 2 |
| Medium | 0 |
| Low | 0 |
| Automated | 8 |
| Manual | 0 |
| Requirements with test cases | 6 / 6 |
| Interface changes with test cases | 5 / 5 |
