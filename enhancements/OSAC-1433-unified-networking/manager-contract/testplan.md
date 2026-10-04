# Testplan — OSAC-1433

## Overview

- **Feature:** OSAC-1433 — Network Manager Integration Contract
- **Total test cases:** 4
- **Requirements covered:** 1 of 1 functional requirements
- **Interface changes covered:** 4 of 4

## Test Cases

### FR-6: Pluggable networking backends with transparent selection

#### TC-FR6-01: Reject an invalid manager registration

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Preconditions

- The operator watches a test namespace containing manager registration ConfigMaps.
- The test AAP provider can report whether a job was created.

##### Steps

1. Create a role-labeled ConfigMap with an unsupported contractVersion, malformed implementationRef, or unknown operation identifier.
2. Reconcile a NetworkClass that selects that manager.

##### Expected Results

- The NetworkClass or affected resource reports the manager role, ConfigMap name, and invalid field.
- No AAP job is created.

#### TC-FR6-02: Dispatch an advertised operation to the selected collection task

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- A valid v1 manager registration advertises virtual_network.create and implementationRef acme.networking.fabric_manager.
- The AAP execution environment contains that test collection and its create_virtual_network task.

##### Steps

1. Create a VirtualNetwork using a NetworkClass that selects the registered manager.
2. Observe the AAP job and test backend state.

##### Expected Results

- AAP invokes acme.networking.fabric_manager and task create_virtual_network, even though the manager name is not the collection role suffix.
- The test backend contains one isolated routing-domain object associated with the VirtualNetwork UID.
- The operator reports the VirtualNetwork Ready after the AAP job succeeds.

#### TC-FR6-03: Fail an unadvertised operation-target pair without fallback

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | automated |

##### Preconditions

- A Fabric Manager is selected and does not advertise external_ip_attachment.create for cluster.
- A K8s Manager is present but the configured profile does not assign that operation to it.

##### Steps

1. Create an ExternalIPAttachment targeting a Cluster.
2. Observe the resource condition and AAP job count.

##### Expected Results

- The resource reports the selected Fabric Manager name, external_ip_attachment.create, and cluster as unsupported.
- No AAP job is created and no K8s Manager task runs.

#### TC-FR6-04: Validate ExternalIP and lease operation results

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

##### Preconditions

- A valid manager test collection advertises ExternalIP allocation and DHCP lease query for the tested target.
- The fake backend returns a stable allocated address and a matching lease.

##### Steps

1. Reconcile an ExternalIP twice, then run dhcp_lease.query for a network attachment.
2. Observe the resource annotation, AAP artifacts, and workload status.

##### Expected Results

- Both ExternalIP reconciliations retain the same osac.openshift.io/allocated-address value.
- The query_dhcp_lease job exposes a leases artifact with subnet_ref, interface, ip_address, and mac_address.
- OSAC reports the matching address for the requested attachment.

## Gaps

### Requirement Coverage Gaps

All PRD requirements have test cases.

### Interface Change Coverage Gaps

All interface changes are exercised by test cases.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 4 |
| Critical | 2 |
| High | 2 |
| Medium | 0 |
| Low | 0 |
| Automated | 4 |
| Manual | 0 |
| Requirements with test cases | 1 / 1 |
| Interface changes with test cases | 4 / 4 |
