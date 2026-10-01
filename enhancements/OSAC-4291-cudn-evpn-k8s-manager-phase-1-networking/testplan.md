# Testplan — OSAC-4291

## Overview

**Last updated:** 2026-09-26

- **Feature:** OSAC-4291 — CUDN EVPN K8s Manager Phase 1 Networking: Single-Cluster VM-to-Fabric Bridging
- **Total test cases:** 18
- **Requirements covered:** 9 of 9 (R1-R9)
- **Interface changes covered:** 6 of 6 (IC-1 through IC-6)
- **Additional operational tests:** 2 deletion lifecycle tests

**Subnet policy precondition:** The deployment has a required default ACL action (`PERMIT` or `DENY`). A Subnet may have no ACL association or one READY ACL from its VirtualNetwork. When `network_acl` is omitted, the association remains unset and the deployment default action decides unmatched traffic; the Subnet does not wait for ACL readiness. When an ACL is explicitly associated, that ACL's rules must be active before the Subnet becomes READY. No default ACL resource is expected.

## Test Cases

### R1: K8s manager registration for EVPN fabric bridging (IPv4 only)

#### TC-R1-01: Register cudn_evpn k8s manager via ConfigMap

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- osac-installer deployed to cluster
- No existing ConfigMap `k8s-manager-cudn-evpn` in osac namespace

##### Steps

1. Apply osac-installer Helm chart with cudn_evpn manager enabled
2. Verify ConfigMap `k8s-manager-cudn-evpn` exists in osac namespace
3. Verify ConfigMap data.manager = "cudn_evpn"
4. Verify ConfigMap data.capabilities includes "supports_ipv4: true"
5. Verify ConfigMap data.capabilities includes "supports_ipv6: false"

##### Expected Results

- ConfigMap created with label `osac.openshift.io/k8s-manager: "true"`
- Capabilities reflect IPv4-only support
- NetworkClass controller loads cudn_evpn as available k8s manager

### R2: Fabric-to-k8s manager data dependency

#### TC-R2-01: Sequential provisioning from fabric manager to k8s manager

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | critical | automated |

##### Preconditions

- A READY VirtualNetwork exists with a NetworkClass configured for the primary fabric manager and `cudn_evpn` k8s manager.
- A READY NetworkACL is scoped to that VirtualNetwork, and its policy is active.
- No Subnet exists under the VirtualNetwork.

##### Steps

1. Create a Subnet through the fulfillment-service API with an explicit `network_acl` reference to the READY same-VirtualNetwork ACL.
2. Observe the Subnet controller create the fabric AAP Job first.
3. Wait for the fabric job to complete, then inspect its output ConfigMap and verify `data.extra_vars` contains valid JSON with `l2_vni`, `l3_vni`, and `fabric_reserved_range`.
4. Verify the k8s job is not created until the fabric job succeeds and the associated ACL policy is active on the Subnet.
5. Verify the controller extracts `l2_vni` and `l3_vni` from the ConfigMap, not from the AAP Job CR.
6. Observe the controller create the k8s AAP Job with the VNI data in `extra_vars`.
7. Verify the k8s job `extra_vars` contains `l2_vni` and `l3_vni` (route targets are not passed; CUDN auto-generates them).
8. Verify the precreated `NetworkACL.status.phase` remains `Ready` and the Subnet's `NetworkACLAssociationReady=True` condition is set only after explicit manager activation acknowledgement; fabric job completion and ConfigMap data alone do not set the condition.
9. Verify the Subnet reaches READY only after both managers complete and the associated ACL is actively enforced.

##### Expected Results

- The Subnet references the READY ACL scoped to its VirtualNetwork.
- The fabric job completes before the k8s job starts; they do not run concurrently.
- The k8s job receives VNI values extracted from ConfigMap `data.extra_vars`.
- `NetworkACL.status.phase == "Ready"` reflects the ACL's active rules, and the Subnet's `NetworkACLAssociationReady=True` condition reflects explicit manager confirmation that those rules are enforced on this Subnet.
- Fabric job completion and VNI ConfigMap data are not treated as proof of ACL enforcement; because this case has an explicit association, the Subnet does not report READY before its association condition is true.
- Subnet.status.conditions shows a K8sManagerWaitingForFabric event between jobs.

#### TC-R2-02: VNI extraction failure when fabric job missing data

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | automated |

##### Preconditions

- The Subnet create request explicitly referenced a READY NetworkACL scoped to the same VirtualNetwork.
- The associated ACL policy is actively enforced; the Subnet remains non-READY while provisioning is incomplete.
- Fabric provisioning completed, but the output ConfigMap `data.extra_vars` is missing one or more required VNI fields

##### Steps

1. Controller reads the fabric output ConfigMap `data.extra_vars`
2. Extraction fails (missing `l2_vni` field)
3. Observe controller emits Kubernetes event "VNIExtractionFailed"
4. Observe Subnet.status.phase = "Failed"
5. Observe Subnet.status.conditions shows error message referencing fabric job

##### Expected Results

- Subnet provisioning stops (k8s job never created)
- Event message includes fabric job name for debugging
- User can inspect fabric AAP job logs to diagnose

#### TC-R2-03: Subnet without ACL uses deployment default policy

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | automated |

##### Preconditions

- The deployment NetworkClass has `spec.defaults.defaultAclAction: DENY`.
- A VirtualNetwork uses that NetworkClass and has no Subnet.
- No default NetworkACL resource exists.
- The test can pause the k8s-manager job after CUDN Ready and before its
  Namespace readiness check. An administrator can hold a deleted test
  Namespace in `Terminating` with a temporary finalizer, then remove the
  finalizer and recreate the Namespace with its normal manager labels.

##### Steps

1. Create a Subnet without `spec.network_acl`.
2. Verify the persisted Subnet has no ACL association.
3. Verify the Subnet controller provisions fabric and, for the first eligible Subnet, the CUDN without waiting for a NetworkACL resource or `NetworkACLAssociationReady` condition.
4. Confirm the target Namespace is named after the Subnet. After CUDN Ready,
   pause the job before the Namespace readiness check, add a temporary
   finalizer to the Namespace, and issue a Kubernetes DELETE. Verify the
   Namespace is `Terminating` with a `metadata.deletionTimestamp`.
5. Resume the job and verify it remains incomplete and the Subnet does not
   become READY while the Namespace is terminating.
6. Remove the temporary finalizer. After the deleting Namespace disappears,
   recreate it with its normal manager labels before the job's readiness
   retries expire. Verify it becomes Active and the k8s-manager job completes,
   then the Subnet becomes READY.
7. Send traffic that matches no tenant ACL rule and verify the deployment
   default action denies it.

##### Expected Results

- The Subnet remains unassociated and becomes READY only after fabric, CUDN,
  and Namespace readiness are independently confirmed.
- CUDN Ready alone is insufficient: a terminating Namespace keeps the
  k8s-manager job incomplete and the Subnet non-READY.
- A Namespace with a deletion timestamp is not ready for VM placement.
- No NetworkACL object or association-ready condition is required.
- Unmatched traffic follows the deployment-wide `DENY` default action.

### R3: Automatic overlay network provisioning on hosting clusters

#### TC-R3-01: CUDN provisioned with EVPN transport

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- A single-Subnet VirtualNetwork uses a NetworkClass with k8s_manager="cudn_evpn".
- The Subnet explicitly references a READY NetworkACL scoped to that VirtualNetwork.
- The ACL policy is actively enforced before the Subnet reaches READY.
- The k8s manager job is running.

##### Steps

1. Observe k8s manager playbook creates namespace with label `k8s.ovn.org/primary-user-defined-network`
2. Observe playbook creates ClusterUserDefinedNetwork CR with:
   - metadata.name = VirtualNetwork name
   - spec.network.topology = "Layer2"
   - spec.network.transport = "EVPN"
   - spec.network.evpn.vtep = "tenant-vtep"
   - spec.network.evpn.macVRF.vni = l2_vni from extra_vars
   - spec.network.evpn.ipVRF.vni = l3_vni from extra_vars
3. Wait for CUDN status.conditions Ready=True
4. Verify CUDN status.vrfName is set (Linux VRF device name)

##### Expected Results

- CUDN CR exists with correct VNI values
- CUDN status transitions to Ready within 60 seconds
- OVN-Kubernetes provisions VXLAN interfaces on worker nodes

### R4: VM-to-fabric L2 and fabric-only cross-Subnet L3 connectivity

#### TC-R4-01: L2 same-Subnet VM-to-bare-metal connectivity

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5, IC-6 | critical | manual |

##### Preconditions

- The VirtualNetwork has exactly one Subnet and uses the cudn_evpn k8s manager.
- The Subnet explicitly references a READY NetworkACL scoped to the same VirtualNetwork; policy enforcement completes before the Subnet becomes READY.
- The deployment default ACL action is `PERMIT`. The associated NetworkACL has more-specific `DENY ALL` rules in both directions: ingress from `200.200.1.0/24` and egress to `200.200.1.0/24`. Their selectors would match the endpoint addresses if evaluated, but both endpoints are in one Subnet, so the flow bypasses Subnet ACL evaluation.
- The CUDN is provisioned for the single Subnet.
- A VirtualMachine runs in the CUDN namespace with IP 200.200.1.3.
- A bare-metal endpoint is attached to the configured fabric in the same Subnet with IP 200.200.1.10.
- FRR advertises EVPN routes to the fabric.

##### Steps

1. Verify the VM is running: `oc get vmi -n <namespace>`.
2. Inspect the associated ACL and confirm it is Ready with the ingress and egress `DENY ALL` rules for `200.200.1.0/24`; these selectors would match the endpoints if evaluated, but same-Subnet traffic bypasses the ACL.
3. Connect to the VM console: `virtctl console <vm-name>`.
4. Ping the bare-metal endpoint: `ping 200.200.1.10`.
5. Verify FRR shows a Type-2 route for the VM MAC: `vtysh -c "show bgp l2vpn evpn" | grep <vm-mac>`.
6. Verify the configured fabric learns the VM MAC through EVPN.

##### Expected Results

- Ping succeeds (RTT <10ms).
- The same-Subnet ping succeeds because traffic between resources on the same Subnet bypasses the associated ACL, even though its rule selectors would otherwise match the endpoints.
- FRR advertises a Type-2 EVPN route with the VM MAC and IP.
- The configured fabric EVPN table shows the VM MAC through the OCP VTEP.
- The Subnet is in a one-Subnet VirtualNetwork; this test does not place VMs in a multi-Subnet VirtualNetwork.

#### TC-R4-02: Fabric-only cross-Subnet L3 connectivity between bare-metal endpoints

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5, IC-6 | critical | manual |

##### Preconditions

- A separate VirtualNetwork uses a fabric-only NetworkClass with no k8s manager and contains no VMs.
- The VirtualNetwork contains two Subnets with distinct CIDRs; each Subnet explicitly references a READY NetworkACL scoped to this same VirtualNetwork.
- Each associated ACL policy is actively enforced before its Subnet reaches READY. The ACL may be shared by both Subnets.
- The stateless policy explicitly permits both the test flow and its return traffic:
  - For A-to-B traffic, Subnet A egress permits destination Subnet B, and Subnet B ingress permits source Subnet A.
  - For the return B-to-A traffic, Subnet B egress permits destination Subnet A, and Subnet A ingress permits source Subnet B.
- One bare-metal endpoint is attached to each Subnet.
- No VM is present or created in this VirtualNetwork.

##### Steps

1. Verify the VirtualNetwork has multiple READY Subnets, active ACL enforcement on both, and no VMs.
2. Inspect the associated ACL rules and confirm the forward and reverse ingress/egress rules are active.
3. Ping from the endpoint in Subnet A to the endpoint in Subnet B, then verify the reply reaches Subnet A.
4. Verify the traffic is routed by the fabric between Subnets.

##### Expected Results

- Cross-Subnet L3 connectivity succeeds between the bare-metal endpoints.
- Return traffic succeeds only because the reverse-direction stateless ACL rules are present.
- No VM is used in the multi-Subnet VirtualNetwork.
- The test does not use the CUDN/VM path for cross-Subnet routing.

### R5: VM placement requires a single-Subnet VirtualNetwork

#### TC-R5-01: Reject a second Subnet while a VM exists

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- A VirtualNetwork uses a NetworkClass with k8s_manager="cudn_evpn".
- Exactly one Subnet exists, explicitly references a READY same-VirtualNetwork NetworkACL, and is READY only after active ACL enforcement.
- A VM is running on that Subnet.
- The second Subnet request will explicitly reference a READY NetworkACL scoped to the same VirtualNetwork; its policy is already active.

##### Steps

1. Attempt to create a second Subnet under the same VirtualNetwork without the skip-k8s-manager annotation and with the explicit ACL reference.
2. Observe the API response, Subnet list, and dispatch history.

##### Expected Results

- The API returns HTTP 400 Bad Request with code FailedPrecondition.
- The error explains that the first Subnet has running VMs and advises deleting the VMs or creating a new VirtualNetwork.
- The second Subnet is not created or dispatched.
- The existing one-Subnet VirtualNetwork and its CUDN remain unchanged.

#### TC-R5-02: Allow fabric-only multi-Subnet networking after VMs are removed

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- A cudn_evpn VirtualNetwork has one READY Subnet with an explicit READY same-VirtualNetwork NetworkACL association and active policy enforcement.
- The first Subnet's CUDN is provisioned.
- All VMs and VMIs have been deleted from the VirtualNetwork.
- A READY NetworkACL scoped to the same VirtualNetwork is available for the second Subnet, with policy active before the second Subnet can become READY.

##### Steps

1. Create a second Subnet without the skip-k8s-manager annotation and explicitly reference the READY same-VirtualNetwork NetworkACL.
2. Wait for active ACL enforcement and the second Subnet to reach READY.
3. Verify provisioning is fabric-only for the second Subnet and no second CUDN is created.
4. Verify the first Subnet's CUDN remains, the second Subnet is usable by fabric endpoints, and no VM is present.

##### Expected Results

- The API accepts the second Subnet after confirming no VMs remain.
- Both Subnets become READY only after their associated NetworkACL policies are actively enforced.
- The second Subnet receives fabric provisioning but no CUDN.
- The first Subnet's CUDN remains unchanged.
- The resulting multi-Subnet VirtualNetwork is fabric-only and rejects VM placement.

#### TC-R5-03: Create a fabric-only Subnet with the skip-k8s-manager annotation

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- A cudn_evpn VirtualNetwork has one READY Subnet with an explicit READY same-VirtualNetwork NetworkACL association and active policy enforcement; its CUDN is created.
- No VM or VMI exists in the VirtualNetwork.
- The second Subnet will explicitly reference a READY NetworkACL scoped to the same VirtualNetwork, with policy active before the Subnet can become READY.

##### Steps

1. Create a second Subnet with annotation `osac.openshift.io/skip-k8s-manager: "true"` and an explicit same-VirtualNetwork ACL reference.
2. Observe the API response.
3. Verify provisioning dispatches to the configured fabric manager only.
4. Verify no CUDN is created for the second Subnet.
5. Verify the configured fabric manager places both Subnets in the same VirtualNetwork routing domain.
6. Verify the first Subnet's CUDN remains unchanged.

##### Expected Results

- The API returns HTTP 201 Created.
- The second Subnet reaches READY only after its associated ACL is actively enforced.
- Subnet job history contains only the fabric-manager job for the second Subnet.
- The first Subnet's CUDN namespace and resources remain unaffected.
- The second Subnet has no CUDN or k8s namespace.
- The multi-Subnet VirtualNetwork has no VMs and remains ineligible for VM placement.

#### TC-R5-04: Reject VM placement in a multi-Subnet VirtualNetwork

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- A cudn_evpn VirtualNetwork has two READY Subnets, each explicitly associated with a READY NetworkACL scoped to the same VirtualNetwork.
- Both ACL policies are actively enforced before their Subnets became READY.
- No VM or VMI exists in the VirtualNetwork.
- The first Subnet's CUDN persists; the second Subnet is fabric-only.

##### Steps

1. Attempt VM placement targeting the first Subnet.
2. Attempt VM placement targeting the second Subnet.
3. Observe VMaaS validation results and confirm no VM or VMI is created.

##### Expected Results

- VM placement is rejected for both Subnets because the parent VirtualNetwork has multiple Subnets.
- The first Subnet's persistent CUDN does not make the multi-Subnet VirtualNetwork eligible for VM placement.
- The Subnets and their active NetworkACL associations remain unchanged.

#### TC-R5-05: Fence stale admissions and serialize Subnet create/delete admission

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- A `cudn_evpn` VirtualNetwork has one READY Subnet with active same-VirtualNetwork NetworkACL enforcement.
- A second VirtualNetwork is available on which VM placement is normally supported and whose k8s manager is not `cudn_evpn`.
- The test can pause admission persistence and control lease expiry and token issuance across two service replicas.
- Tenant RBAC denies direct Kubernetes DELETE requests for Subnets; tenants can
  initiate deletion only through the fulfillment-service Delete API.
- The Delete API and Subnet create path use the same VirtualNetwork admission
  lock and fenced reservation store. Test hooks can pause the Delete API after
  reservation persistence and before issuing Kubernetes DELETE.

##### Steps

1. Using tenant credentials, issue a direct Kubernetes API DELETE for an
   existing Subnet without calling the fulfillment-service Delete API. Read
   the Subnet and check `metadata.deletionTimestamp`.
2. For each path—Subnet creation, VM placement, and the `Requested` Subnet deletion reservation—have replica A acquire a fencing token and pause immediately before persisting its admission. For the deletion-promotion case, seed a `Requested` reservation after placements have drained and pause before the `Admitted` transition.
3. Expire A's lease and have replica B acquire a newer token for the same VirtualNetwork.
4. Resume A's write attempt.
5. Retry the operation with the current token and re-evaluate the VirtualNetwork state.
6. Start a Subnet create through replica A. Pause it after reading VirtualNetwork
   state while it holds the lock. Start a Delete API request for the existing
   Subnet through replica B; verify it waits and has not set
   `metadata.deletionTimestamp`. Resume the create, then allow the Delete API
   to acquire the lock, re-read state, and persist its `Requested` reservation
   before issuing Kubernetes DELETE.
7. In a separate ordering, let the Delete API persist the `Requested`
   reservation first and pause it before Kubernetes DELETE. Attempt a Subnet
   create through the other replica, then resume deletion.
8. On the second VirtualNetwork, persist a `Requested` Subnet deletion
   reservation and pause before Kubernetes DELETE. Attempt VM placement while
   the reservation is active, then resume deletion.
9. Separately, simulate a terminating Subnet with no reservation using an
   administrator fixture and reconcile it.

##### Expected Results

- Each expired or superseded write is rejected atomically; no stale Subnet, placement, deletion admission, or transition to `Admitted` is persisted.
- A retry is accepted only after acquiring the current lock token and repeating the state checks.
- Create and Delete API operations serialize on the shared VirtualNetwork lock:
  the delete timestamp is set only after its durable reservation exists, and a
  delete-first ordering blocks subsequent Subnet creation.
- A `Requested` deletion reservation blocks VM placement on both the
  `cudn_evpn` fixture and the fixture using a different k8s manager, before
  manager-specific placement validation runs; the Create request is rejected
  and no ComputeInstance or placement admission is persisted.
- The tenant's direct Kubernetes DELETE returns `403 Forbidden`; the Subnet
  remains and `metadata.deletionTimestamp` is unset. If a Subnet is observed
  terminating without a reservation, the controller emits `DeletionBlocked`
  and requeues without creating a late reservation or starting cleanup.
- Deletion reservations continue to block new Subnet creates and VM placements
  until cleanup completes and the finalizer is removed.

### R6: Non-conflicting IP address assignment

#### TC-R6-01: VM receives an OVN DHCP address without fabric DHCP overlap

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | manual |

##### Preconditions

- The VirtualNetwork has exactly one Subnet and a CUDN is provisioned for it.
- The Subnet explicitly references a READY NetworkACL scoped to the same VirtualNetwork; the ACL policy is actively enforced before the Subnet reaches READY.
- The configured fabric manager provides a DHCP range of 200.200.1.100-200.200.1.200 and a reserved range.

##### Steps

1. Verify CUDN `spec.network.layer2.reservedSubnets` includes the fabric reserved range.
2. Verify the k8s job extra_vars contains the fabric_reserved_range from fabric provisioning.
3. Deploy a VirtualMachine in the CUDN namespace.
4. Verify the VM receives an IP address via DHCP.
5. Check the DHCP server address in the VM lease file.
6. Verify the VM IP is not in the fabric DHCP range (200.200.1.100-200).
7. Verify the VM IP is not in the fabric reserved range.
8. Check the fabric DHCP service logs for requests from the VM MAC.
9. Verify the VM IP is inside the Subnet CIDR (200.200.1.0/24).

##### Expected Results

- CUDN reservedSubnets is populated; the k8s job fails if fabric_reserved_range is missing.
- OVN-Kubernetes assigns the VM address, not the fabric DHCP service.
- The VM lease identifies the OVN DHCP server, not the fabric gateway.
- The fabric DHCP service receives no request from the VM MAC.
- The VM IP does not collide with fabric-managed addresses (gateway, SVI, or DHCP pool).
- OVN IPAM respects the reserved range.
- The two DHCP services coexist without conflict.

### R7: Installation prerequisites documentation

#### TC-R7-01: Installation guide covers all manual prerequisites

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| — | high | manual |

##### Preconditions

- Access to osac-installer documentation

##### Steps

1. Read installation guide for cudn_evpn k8s manager
2. Verify guide documents:
   - VTEP CR creation
   - FRRConfiguration underlay BGP peering
   - RouteAdvertisements CR
   - BGP underlay connectivity (worker ↔ fabric switch)
   - Gateway MAC coordination requirement
3. Verify guide includes validation commands to check prerequisites complete

##### Expected Results

- All manual prerequisites documented with examples
- Validation commands provided (check VTEP exists, FRR BGP session up, etc.)
- Guide warns against skipping gateway MAC coordination

### R8: Diagnostic tooling documentation

#### TC-R8-01: Diagnostic commands documented for troubleshooting

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| — | medium | manual |

##### Preconditions

- Access to osac documentation

##### Steps

1. Read troubleshooting guide for cudn_evpn
2. Verify guide documents:
   - FRR VNI status check: `vtysh -c "show evpn vni"`
   - BGP EVPN routes check: `vtysh -c "show bgp l2vpn evpn"`
   - CUDN status check: `oc get clusteruserdefinednetwork`
   - Query the configured fabric manager's VirtualNetwork state or API
   - Packet capture for VXLAN traffic

##### Expected Results

- Diagnostic commands cover VNI mismatch detection
- Commands cover gateway MAC comparison
- Commands cover BGP session verification
- Known failure modes documented with symptoms and fixes

### R9: Gateway MAC coordination prerequisite

#### TC-R9-01: Gateway MAC documented as manual prerequisite

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| — | high | manual |

##### Preconditions

- Access to installation guide

##### Steps

1. Read installation prerequisites
2. Verify guide documents gateway MAC coordination requirement
3. Verify guide explains consequences of mismatch (L3 traffic fails, ARP flapping)
4. Verify guide provides commands to check gateway MAC on both sides

##### Expected Results

- Gateway MAC coordination listed as prerequisite
- Guide explains why MACs must match
- Guide provides diagnostic commands to compare the CUDN gateway MAC with the configured fabric gateway MAC

### Subnet Deletion: Ordered cleanup prevents stale VRFs

#### TC-DELETE-01: Subnet deletion waits for VM removal

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- A single-Subnet VirtualNetwork has a CUDN-backed Subnet explicitly associated with a READY same-VirtualNetwork NetworkACL.
- The ACL policy is actively enforced before the Subnet reaches READY.
- A VirtualMachine is running in the CUDN namespace.
- No Subnet deletion reservation or `metadata.deletionTimestamp` is present
  before the test's first Delete request.

##### Steps

1. Request Subnet deletion while the VM and its placement are active.
2. Verify deletion is rejected before a deletion reservation, deletion
   timestamp, or k8s-manager delete job is created.
3. Delete the VM through its supported API and wait until its placement and VMI
   are gone.
4. Retry Subnet deletion and observe the k8s-manager delete playbook run.
5. Verify CUDN deletion starts only after no VMIs remain.
6. Verify the namespace is deleted after the CUDN.
7. Check for stale VRFs on worker nodes (should not exist).

##### Expected Results

- While the VM or placement exists, Subnet deletion is rejected and cleanup
  does not start.
- After the VM and placement are gone, deletion order is enforced: CUDN →
  namespace.
- No stuck CUDN finalizer after deletion is admitted.
- **Normal case:** No stale VRF devices persist after CUDN deleted
- **Rare failure case:** Stale VRF requires manual recovery (see TC-DELETE-02 and Support Procedures)
- Subnet CR finalizer removed, CR deleted successfully

#### TC-DELETE-02: Stale VRF manual recovery (troubleshooting)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| — | low | manual |

##### Preconditions

- CUDN deleted successfully (confirmed via `oc get clusteruserdefinednetwork`)
- VRF device persists on worker node (observed rare race condition)
- Cloud Infrastructure Admin troubleshooting connectivity issue

##### Steps

1. Detect stale VRF:
   ```bash
   oc debug node/<node-name> -- chroot /host ip link show type vrf
   ```
2. Verify CUDN is deleted: `oc get clusteruserdefinednetwork <vnet-name>` returns NotFound
3. Follow manual recovery procedure from Support Procedures section
4. Option 1: Restart ovnkube-node pod (impacts all VMs on node)
5. Option 2: Direct VRF deletion via node debug (less disruptive)
6. Verify VRF cleaned up after recovery

##### Expected Results

- VRF cleanup procedure documented in Support Procedures
- **Automatic restart NOT performed by delete_subnet.yaml** (too disruptive for routine delete)
- Manual recovery successful (VRF removed after procedure)
- Documented impact: ovnkube-node restart affects all VMs on node (not just deleted namespace)

## Gaps

None identified. All requirements map to test cases, all interface changes exercised.

---

## Provenance

Authored: respond @ design 0.11.3 - 2bd6607, workspace main @ 2293f9140

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.3","ai_workflows":"2bd6607","source_repo":"2293f9140","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["respond"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":true} -->
