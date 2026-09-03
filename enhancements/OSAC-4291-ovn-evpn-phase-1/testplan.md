# Testplan — OSAC-4291

## Overview

- **Feature:** OSAC-4291 — K8s Manager — OVN EVPN Phase 1: Single-Cluster VM-to-Fabric Bridging
- **Total test cases:** 16
- **Requirements covered:** 9 of 9 (R1-R9)
- **Interface changes covered:** 6 of 6 (IC-1 through IC-6)
- **Additional operational tests:** 2 deletion lifecycle tests

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

#### TC-R2-01: Sequential provisioning fabric then k8s manager

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | critical | automated |

##### Preconditions

- NetworkClass with fabric_manager="netris", k8s_manager="cudn_evpn"
- VirtualNetwork created with this NetworkClass
- Mocked Netris fabric returning VNI values

##### Steps

1. Create Subnet via fulfillment-service API
2. Observe Subnet controller creates fabric AAP Job first
3. Fabric job completes with VNI data in status.extraVars
4. Observe controller does not create k8s job until fabric job status shows Successful
5. Controller extracts l2_vni, l3_vni from fabric job
6. Observe controller creates k8s AAP Job with VNI data in extra_vars
7. Verify k8s job extra_vars contains: l2_vni, l3_vni (route targets not passed - CUDN auto-generates)

##### Expected Results

- Fabric job completes before k8s job starts (not concurrent)
- K8s job receives VNI values extracted from fabric job status
- Subnet.status.conditions shows "K8sManagerWaitingForFabric" event between jobs

#### TC-R2-02: VNI extraction failure when fabric job missing data

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | automated |

##### Preconditions

- Subnet provisioning in progress, fabric job completed
- Fabric AAP Job CR exists but status.extraVars missing VNI fields

##### Steps

1. Controller attempts to extract VNI from fabric job status
2. Extraction fails (missing l2_vni field)
3. Observe controller emits Kubernetes event "VNIExtractionFailed"
4. Observe Subnet.status.phase = "Failed"
5. Observe Subnet.status.conditions shows error message referencing fabric job

##### Expected Results

- Subnet provisioning stops (k8s job never created)
- Event message includes fabric job name for debugging
- User can inspect fabric AAP job logs to diagnose

### R3: Automatic overlay network provisioning on hosting clusters

#### TC-R3-01: CUDN provisioned with EVPN transport

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- Subnet created with NetworkClass k8s_manager="cudn_evpn"
- K8s manager job running

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

### R4: VM-to-fabric connectivity (L2 same-subnet and L3 cross-subnet scenarios)

#### TC-R4-01: L2 same-subnet VM to bare-metal connectivity

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5, IC-6 | critical | manual |

##### Preconditions

- CUDN provisioned with subnet 200.200.1.0/24
- VirtualMachine deployed in CUDN namespace, IP 200.200.1.3
- Bare-metal node provisioned on Netris fabric in same subnet, IP 200.200.1.10
- FRR advertising EVPN routes to fabric

##### Steps

1. Verify VM running: `oc get vmi -n <namespace>`
2. Console into VM: `virtctl console <vm-name>`
3. Ping bare-metal node: `ping 200.200.1.10`
4. Verify FRR shows Type-2 route for VM MAC: `vtysh -c "show bgp l2vpn evpn" | grep <vm-mac>`
5. Verify Netris fabric learned VM MAC via EVPN

##### Expected Results

- Ping succeeds (RTT <10ms)
- FRR advertises Type-2 EVPN route with VM MAC and IP
- Netris leaf switch has VM MAC in EVPN table pointing to OCP VTEP

#### TC-R4-02: L3 cross-subnet VM to bare-metal connectivity

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5, IC-6 | critical | manual |

##### Preconditions

- CUDN provisioned with subnet 200.200.1.0/24
- VirtualMachine deployed in CUDN namespace, IP 200.200.1.3
- Bare-metal node provisioned on Netris fabric in different subnet 200.200.2.0/24, IP 200.200.2.10
- Both subnets under same Netris VPC (shared ipVRF)

##### Steps

1. Console into VM
2. Ping bare-metal node in different subnet: `ping 200.200.2.10`
3. Verify FRR shows Type-5 route for CUDN prefix: `vtysh -c "show bgp l2vpn evpn" | grep Type-5 | grep 200.200.1.0`
4. Verify Netris VPC routing table includes both subnets

##### Expected Results

- Ping succeeds (routed via ipVRF)
- FRR advertises Type-5 EVPN route for 200.200.1.0/24 prefix
- Traffic encapsulated with L3 VNI (ipVRF), not L2 VNI (macVRF)

### R5: Single-subnet-per-VirtualNetwork constraint for this k8s manager

#### TC-R5-01: Second subnet creation rejected for cudn_evpn NetworkClass

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- NetworkClass with k8s_manager="cudn_evpn"
- VirtualNetwork created with this NetworkClass
- One Subnet already exists under this VirtualNetwork

##### Steps

1. Attempt to create second Subnet under same VirtualNetwork via fulfillment-service API
2. Observe API response

##### Expected Results

- API returns HTTP 400 Bad Request
- Response code = `FailedPrecondition`
- Error message includes: "NetworkClass with k8s_manager 'cudn_evpn' supports only one subnet per VirtualNetwork"
- Error message includes: "OVN Connectors limitation"
- Error message includes name of existing subnet

#### TC-R5-02: Multiple subnets allowed for different k8s manager

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- NetworkClass with k8s_manager="cudn_localnet" (not cudn_evpn)
- VirtualNetwork created with this NetworkClass
- One Subnet already exists under this VirtualNetwork

##### Steps

1. Attempt to create second Subnet under same VirtualNetwork
2. Observe API response

##### Expected Results

- API returns HTTP 201 Created
- Second Subnet provisioned successfully
- Single-subnet validation skipped (conditional on k8s_manager)

### R6: Non-conflicting IP address assignment

#### TC-R6-01: VM receives IP from OVN DHCP, Netris DHCP coexists safely

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | manual |

##### Preconditions

- CUDN provisioned with subnet 200.200.1.0/24
- Netris VNet configured with DHCP enabled (default), DHCP range 200.200.1.100-200.200.1.200

##### Steps

1. Verify CUDN `spec.network.layer2.excludeSubnets` includes Netris reserved range (REQUIRED)
2. Verify k8s job extra_vars contains netris_reserved_range from fabric job
3. Deploy VirtualMachine in CUDN namespace
4. Verify VM receives IP address via DHCP
5. Check VM received IP from OVN DHCP (inside VM: check DHCP server IP in lease file)
6. Verify VM IP is not in Netris DHCP range (not 200.200.1.100-200)
7. Verify VM IP is not in Netris reserved range (excludeSubnets)
8. Check Netris DHCP logs — verify no DHCP requests from VM MAC address
9. Verify VM IP is in subnet CIDR (200.200.1.0/24)

##### Expected Results

- CUDN `excludeSubnets` field is populated (k8s job fails if netris_reserved_range missing from fabric job)
- VM IP assigned by OVN-Kubernetes DHCP (not Netris DHCP)
- VM DHCP lease shows OVN DHCP server IP (logical switch IP, not Netris SVI)
- Netris DHCP logs show no requests from VM MAC (OVN intercepts DHCP inside logical switch)
- **VM IP does not collide with Netris-managed IPs (gateway .1, SVIs, DHCP pool)**
- OVN IPAM respects the excluded range (correctness requirement, not optional)
- Both DHCP servers coexist without conflict (validated behavior)

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
   - Netris VNet query via API
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
- Guide provides diagnostic commands to compare CUDN gateway MAC with Netris VNet gateway MAC

### Subnet Deletion: Ordered cleanup prevents stale VRFs

#### TC-DELETE-01: Subnet deletion with running VMs

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- CUDN provisioned with subnet
- VirtualMachine running in CUDN namespace
- Subnet marked for deletion (finalizer present)

##### Steps

1. Delete Subnet CR
2. Observe k8s manager delete playbook runs
3. Verify VMs deleted before CUDN deletion attempted
4. Verify playbook waits for all VMIs terminated (retries with timeout)
5. Verify CUDN deleted after VMIs gone
6. Verify namespace deleted after CUDN deleted
7. Check for stale VRF on worker nodes (should not exist)

##### Expected Results

- Deletion order enforced: VMs → wait VMIs → CUDN → namespace
- No stuck CUDN finalizer (deletion completes within timeout)
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

