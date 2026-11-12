# Testplan — OSAC-4291

## Overview

- **Feature:** OSAC-4291 — CUDN EVPN K8s Manager Phase 1 Networking: Single-Cluster VM-to-Fabric Bridging
- **Total test cases:** 17
- **Requirements covered:** 9 of 9 (R1-R9)
- **Interface changes covered:** IC-1, IC-2, IC-3, IC-5, IC-6; no case has IC-4
- **Additional operational tests:** 2 deletion lifecycle tests
- **Lab suite:** `tests/e2e/networking/vmaas/test_vmaas_networking.py` is one ordered module; the job stops it at the first failed test (`pytest -x`), so later tests of the module do not run after a failure and fixture finalizers clean up. The job then runs the ExternalIP and NATGateway billing files as a second pytest run. It keeps `test_00` to `test_03` (connectivity and isolation), `test_04` to `test_08` (cluster DNS, SecurityGroup enforcement, cross-tenant isolation), `test_09` to `test_13` (NAT egress and ExternalIP ingress) and `test_14` (one teardown test). Every kept test decides the job; none is non-gating. The ExternalIP pool check is a fixture check, so it fails the first test that needs the pool. Removed E2E requirements, not covered by an equal E2E check: node service isolation from a tenant VM, the SecurityGroup ICMP capability gate (see TC-ICMP-01) and second-tenant automatic ExternalIP ingress and garbage collection. The `external_ip/` and `references/` directories were removed. The second run covers `test_external_ip_billing.py`, `test_external_ip_reattach_billing.py` and `test_nat_gateway_billing.py`.
- **Outside R1-R9:** TC-ICMP-01 (SecurityGroup ICMP capability gate) traces to contract FR-13 and IC-1, not to a requirement of this PRD; it is counted in the total
- **Added for policy ownership:** TC-R3-02 (VirtualNetwork baseline deny and SecurityGroup binding) is counted in the total

TC IDs use `TC-R<requirement>-<sequence>` for R1–R9. `TC-DELETE-*` and `TC-ICMP-*` are retained operational/contract IDs so existing references remain valid. Automation describes the intended execution method, not evidence that the complete case already passes.

## Planning evidence and execution

Source references below are relative to the `osac-project/osac` checkout, not this documentation repository. The runner commands and fixtures were inspected at `6e4300836789bb818f3fc4379d1206294eabdc11`; the CUDN ownership branches were also checked on main at `02d8d932a0a2a4f52d2778c167b6e98a2df29a2a`. **None of these runtime suites was executed for this documentation revision.** Commands are proposed acceptance invocations using existing runners; a runner's presence does not establish every new assertion. Preserve the real/faked boundary when recording results.

| Lane | Working directory and proposed command/procedure | Prerequisites and dependency boundary |
|---|---|---|
| H | `osac-installer/`: `python3 scripts/test-networking-values.py` | Python and Helm; chart render checks only, no cluster. Extend the registration assertions if needed. NetworkClass resolution is checked separately in O. |
| O | `osac-operator/`: `make test` | Go and downloadable Envtest assets. Real ephemeral API server/etcd; fake AAP and fulfillment clients. No Kind, manager role, OVN, or Netris data plane. |
| K | `osac-aap/tests/integration/`: `uv run ansible-playbook targets/cudn_evpn/tasks/baseline.yml -e '@common_vars.yml'` | Run `./setup_test_env.sh` first on disposable Kind and `./teardown_test_env.sh` afterward. Python/uv, Ansible collections, Kind and a container runtime. Real Kubernetes API and role subprocesses; fake CUDN/VTEP CRDs and injected readiness, no AAP/OVN/EVPN. The owner-lookup cases also install the OSAC Subnet CRD from `osac-operator/config/crd/bases/osac.openshift.io_subnets.yaml` and create labeled owner Subnet fixtures; the existing target must be extended for those reads. The target refuses pre-existing CUDN/VTEP CRDs. |
| N | `osac-aap/tests/integration/`: `uv run ansible-playbook targets/netris_fabric/tasks/baseline.yml -e '@common_vars.yml'` | Python/uv, Ansible collections and generated `common_vars.yml` (the setup script prepares it). Real generic playbook and Netris role; stateful `fixtures/netris/fake_netris.py`, unusable hub kubeconfig, no live Netris or switches. |
| F | `osac-installer/`: `make test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment` | Disposable Kind, container runtime and build dependencies. Real deployed fulfillment, PostgreSQL and Keycloak; the service-only phase injects status and disables provider networking. No physical fabric. `fulfillment-service/it/it_networking_design_test.go` contains the ICMP API gate. |
| L | OSAC root: `uv run pytest -n 0 -x tests/e2e/networking/vmaas/test_vmaas_networking.py` | Deployed Netris VMaaS profile, authenticated API client, hub kubeconfig, VM image/catalog item, SSH helper access and routed external pool. Real fulfillment, operator, AAP, KubeVirt, OVN and Netris. Provides related VM/DNS/policy/teardown evidence, not the manual bare-metal or cross-Subnet cases below. |
| M | Any directory with authenticated `osac`, `oc`, `virtctl` and SSH: follow [Manual lab procedure](#manual-lab-procedure) and the named case | Real OSAC with both VMaaS and BMaaS, two available physical hosts, approved catalog items, inventory NIC mappings, SSH access, Netris controller read access and EVPN-ready hub. No mocked completion. |
| D | Enhancement-proposals root: review the linked design/installation/support sections against the named case | Read-only documentation review. No deployed behavior is claimed; validate diagnostic commands in M when testing a lab. |

| Case | Tier / owner | Lane and concrete source/fixture | Coverage status for this revision |
|---|---|---|---|
| TC-R1-01 | Unit + Envtest / [DEV] | H registration templates; O `test/integration/networking_networkclass_test.go` is the related Kind suite, while `internal/controller/networkclass_controller_test.go` holds controller fixtures | Proposed render checks; O's unit/Envtest checks only, no claim to run the separate Kind suite. |
| TC-R2-01 | Envtest / [DEV] | O `internal/controller/networking_resources_test.go`, `networking_wire_golden_test.go`; fake AAP job results | Existing runner; verify ordered launch and eligibility/status assertions. |
| TC-R2-02 | Unit + Envtest / [DEV] | O `internal/networktask/result_test.go`, `vni_test.go`, controller networking fixtures | Existing runner; invalid output and deleting-holder cases require their listed assertions. |
| TC-R3-01 | Unit + component integration / [DEV] | K `targets/cudn_evpn/tasks/baseline.yml`, `cases_hub_states.yaml`; `osac-aap/tests/unit/test_cudn_evpn_role.py` for planner checks | Existing target; injected readiness proves role handling, not OVN provisioning. |
| TC-R3-02 | Component integration / [DEV] | K `baseline.yml` namespace, baseline and SecurityGroup fixtures | Existing rule-update/binding target; no VM traffic. |
| TC-R4-01 | E2E / [QE] | M; related automation: `tests/e2e/networking/stretched/test_shared_subnet_bmi_compute_instance.py` | Manual full case proposed; not covered by L. |
| TC-R4-02 | E2E / [QE] | M with both Subnets and both physical hosts | Manual case proposed; cross-Subnet traffic is not covered by L. |
| TC-R5-01 | Component integration + Envtest / [DEV] | K owner/sibling Subnet CR fixtures and `cases_hub_states.yaml`; O `internal/controller/computeinstance_networking_test.go` and feedback fixtures | Proposed assertions for the dedicated public failure reason, live/deleting/absent owner lookup, read errors, and post-delete claim; runtime execution remains required. |
| TC-R6-01 | E2E / [QE] | M; L gives related VM/DNS evidence only | Manual VM plus physical lease case proposed. |
| TC-R6-02 | Component integration / [DEV] | N `cases_vn_subnet.yaml`, `cases_attachment.yaml` | Existing create/repair scenarios; verify request ordering, no live lease proof. |
| TC-R6-03 | Component integration / [DEV] | N `cases_vn_subnet.yaml`, `cases_attachment.yaml`, `files/gateway_mode_none.yml` | Empty-pool assertions plus separate lab-only override regression; no claim that the override is supported. |
| TC-R7-01 | Documentation review / [DEV] | D [design prerequisites](design.md#test-plan); OSAC `osac-installer/README.md` EVPN overlays | Manual review proposed. |
| TC-R8-01 | Documentation review / [DEV] | D [Support Procedures](design.md#support-procedures); M for command execution | Manual review proposed. |
| TC-R9-01 | Documentation review / [DEV] | D [Gateway and DHCP](/enhancements/OSAC-2434-netris-fabric-manager-networking/design.md#gateway-and-dhcp) | Manual review proposed; does not establish gateway-MAC coordination. |
| TC-ICMP-01 | Component integration / [DEV] | F `it_networking_design_test.go` (`TC-SG-ICMP-01`), server fixtures in `internal/servers/security_groups_server_test.go` | Existing API gate runner; no VM ping or capable-manager READY-through-AAP coverage. |
| TC-DELETE-01 | E2E / [QE] | M; L teardown is related partial coverage only | Manual workload-blocked delete and sibling-preservation case proposed. |
| TC-DELETE-02 | E2E recovery / [QE] | M [Support Procedures](design.md#support-procedures), only on an isolated lab with an observed stale VRF | Conditional manual case; if no stale VRF occurs, record not exercised, not pass. |

### Manual lab procedure

Use this shared setup for TC-R4-01/02, TC-R6-01 and TC-DELETE-01. For TC-DELETE-01, stop setup after the VM in step 3 and leave the sibling empty; do not create the physical hosts in steps 4–5. Substitute deployment-approved IDs/CIDRs; commands are examples to run in the lab, not results of this PR.

1. The Cloud Infrastructure Admin installs Netris and `cudn_evpn` using the [Netris prerequisites](/enhancements/OSAC-2434-netris-fabric-manager-networking/design.md#installation-prerequisites) and OSAC installer's EVPN overlays. Verify `oc get vtep tenant-vtep -o yaml`, `oc get routeadvertisements osac-evpn`, `oc get networkclass -A`, and `oc -n openshift-frr-k8s get frrconfiguration`. The VTEP must be Accepted, the NetworkClass Ready, and underlay BGP established. Use the supported `gateway_ipv4` mode; no `none` or `physical_first` override. Both Subnets must have non-empty physical pools.
2. Authenticate `osac` as the fixture tenant. Reserve `<vn-cidr>` and two non-overlapping Subnet CIDRs within it, satisfying the address-plan prefix limit and excluded-range plan. Create a dedicated VirtualNetwork and Subnets, waiting for each parent and the owner Subnet to become READY before continuing:

   ```bash
   osac create virtualnetwork --name ep495-vn --ipv4-cidr <vn-cidr>
   osac create subnet --name ep495-owner --virtual-network ep495-vn --ipv4-cidr <subnet-cidr>
   osac create subnet --name ep495-sibling --virtual-network ep495-vn --ipv4-cidr <sibling-subnet-cidr>
   osac create securitygroup --name ep495-sg --virtual-network ep495-vn \
     --ingress protocol=all,ipv4-cidr=<vn-cidr> \
     --egress protocol=all,ipv4-cidr=0.0.0.0/0
   ```

   Wait for the SecurityGroup to be READY. Use `osac describe subnet <id>` to inspect VM eligibility. As administrator, obtain the corresponding Subnet CR by `osac.openshift.io/subnet-uuid=<id>` and record `status.ipam`, `status.networkSegment`, and `status.jobs` with `oc -n <osac-namespace> get subnet -l osac.openshift.io/subnet-uuid=<id> -o yaml`.
3. Create the VM first, before attaching physical hosts. Use a published VM catalog item and a registered SSH key supported by the test images:

   ```bash
   osac create computeinstance --name ep495-vm --catalog-item <vm-catalog-item> \
     --ssh-key <ssh-key-name> --network-attachment subnet=<owner-id>,security-groups=<sg-id>
   ```

   Wait for READY, find the VM and VMI with `oc -n osac-vn-<vn-id> get vm,vmi -o wide`, and open `virtctl console -n osac-vn-<vn-id> <vm-name>`. Record the address, `ip -4 route`, resolver configuration and the image's DHCP lease/client log. For TC-R6-01, run the [DHCP observation procedure](#dhcp-observation-procedure) before creating a physical host and repeat it after step 4. Verify the VM address is in the overlay, its router is `gateway_ipv4`, and its resolver matches cluster DNS; DNS need not be inside the overlay.
4. Create the physical host through BMaaS (not by moving a Netris port manually):

   ```bash
   osac create baremetalinstance --name ep495-host --catalog-item <bm-catalog-item> \
     --ssh-key <ssh-key-name> \
     --network-attachment subnet=<owner-id>,interface=<inventory-nic>,security-groups=<sg-id>
   ```

   Wait for READY. Inspect `osac describe baremetalinstance <id>` and the corresponding NetworkAttachment `status.jobs`. Follow its Fabric `query_dhcp_lease` job ID in AAP and record the `osac_result.dhcp_lease` for the host's inventory MAC. Using the provider's Netris controller UI, read V-Net `osac-sn-<subnet-id>`: its DHCP range must match the recorded physical pool, its gateway must be `gateway_ipv4`, and the mapped host port must belong to it. Match the active lease to the host MAC and its actual address via SSH or the serial console; a reservation alone does not pass. Record the lease as `<physical-dhcp-lease>`.
5. For TC-R4-02, repeat step 4 with a second host named `ep495-sibling-host` and `<sibling-id>`, recording `<sibling-physical-dhcp-lease>`. From the VM console run `ping -c 3 <physical-dhcp-lease>` and `ping -c 3 <sibling-physical-dhcp-lease>` for the respective cases. Record FRR `show bgp l2vpn evpn` / `show evpn vni` output and the Netris VPC routes using provider access. Do not attribute BMaaS traffic results to the VM-only suite.
6. Cleanup uses the workload APIs: `osac delete computeinstance <vm-id>` and `osac delete baremetalinstance <host-id>` for each fixture. Wait until their records, VM/VMI, NetworkAttachments and port moves are gone. Delete the sibling before the owner and verify the owner CUDN is unchanged; then delete the owner, SecurityGroup and VirtualNetwork with `osac delete subnet`, `osac delete securitygroup`, and `osac delete virtualnetwork`. In TC-DELETE-01, perform its initial rejected owner delete and empty-sibling delete while the VM still runs. Never bypass finalizers. TC-DELETE-02 uses the isolated stale-VRF recovery procedure only after the CUDN is confirmed absent; no bare-metal setup is required for that recovery case.

### DHCP observation procedure

Use this procedure for TC-R6-01 twice: before any physical attachment and after the physical host is attached and has obtained a lease. A guest lease identifies the selected server; it cannot alone show that the request stayed off the fabric.

1. Record the VM MAC, CUDN L2 VNI, guest interface, and the provider's observation point on the corresponding Netris V-Net/EVPN segment. Start simultaneous guest and fabric-side captures before triggering DHCP. For example, in the VM console run `sudo tcpdump -ni <guest-interface> -s 0 -w <guest-capture.pcap> 'udp port 67 or udp port 68'`. On the provider's decapsulated V-Net interface or a mirror of that segment, run the same DHCP filter to a separate capture. If the provider can capture only the underlay, capture VXLAN (`udp port 4789`) as well and decode the inner packets for this VNI; a DHCP-only filter on an encapsulated interface is insufficient.
2. Validate the fabric observation point with known control traffic on the same VNI in each run. After physical attachment, also capture the host's DHCP exchange as a positive control. If the required observation point cannot be validated, record the request-containment result as inconclusive, not passing.
3. From the VM serial console, force a DHCP exchange using the image's active network manager (for example, deactivate and reactivate its NetworkManager connection with `nmcli connection down <guest-connection>` then `nmcli connection up <guest-connection>`). Do not start a second DHCP client. Confirm the guest capture contains the new request and response; correlate them using the VM MAC/client identity and DHCP transaction ID. Retain the lease/client log, server identifier, address, router and DNS options.
4. Check the matching request is absent from the validated fabric capture while the guest capture shows OVN's reply. Retain both captures and control-traffic evidence. After the physical host is attached, repeat the captures and force another VM DHCP exchange; verify the same containment, overlay address, gateway and cluster DNS expectations. Also retain the physical host's distinct DHCP exchange and `query_dhcp_lease` result from the recorded physical pool.

## Test Cases

### R1: K8s manager registration for EVPN fabric bridging (IPv4 only)

#### TC-R1-01: Register cudn_evpn k8s manager via ConfigMap

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Preconditions

- **Tier / owner:** Unit + Envtest / [DEV], lanes H and O.
- Helm-render fixture selects Netris and `cudn_evpn`; no deployed installer is needed
- Controller fixtures provide the rendered registrations and a new NetworkClass

##### Steps

1. Render the osac-installer Helm chart with cudn_evpn manager enabled
2. Verify the rendered ConfigMap is named `osac-network-k8s-manager-cudn-evpn` in the OSAC namespace
3. Verify ConfigMap data.name = "cudn_evpn", data.ansible_role = "osac.templates.cudn_evpn", and data.network_type = "evpn"
4. Verify the ConfigMap has no `capabilities` key (cudn_evpn does not declare `security_group_icmp`)
5. Verify the rendered Netris registration has `capabilities: eastWestEthernet,security_group_icmp,security_group_physical_noop`

##### Expected Results

- ConfigMap created with label `osac.openshift.io/network-k8s-manager: "true"`
- `cudn_evpn` declares no capability, so a NetworkClass with it rejects ICMP rules (contract TC-CAP-03)
- NetworkClass controller loads cudn_evpn as available k8s manager
- A NetworkClass with Netris records `status.security_group_physical_noop` true, so CaaS surfaces that physical worker traffic is unfiltered

### R2: Fabric-to-k8s manager data dependency

#### TC-R2-01: Sequential provisioning fabric then k8s manager

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | critical | automated |

##### Preconditions

- **Tier / owner:** Envtest / [DEV], lane O.
- NetworkClass with fabric_manager="netris", k8s_manager="cudn_evpn"
- VirtualNetwork created with this NetworkClass
- Mocked Netris fabric returning `l3_vni` from `create_virtual_network` and `network_segment: {type: evpn, l2_vni}` from `create_subnet`

##### Steps

1. Observe the VirtualNetwork's Fabric `create_virtual_network` returns `l3_vni` and the VirtualNetwork CR records it in `status.l3Vni`
2. Create the Subnet CR through the Envtest client, using the controller networking fixtures
3. Observe Subnet controller creates fabric AAP Job first, with the `virtual_network` snapshot carrying `status.l3Vni`
4. Fabric job completes with `osac_result.network_segment`
5. Observe controller does not create k8s job until the Fabric `create_subnet` entry is `Succeeded` and `status.networkSegment` is recorded
6. Observe controller creates k8s AAP Job
7. Verify the k8s job's `osac_job_vars` contains `network_segment: {type: evpn, l2_vni}` and `virtual_network.status.l3Vni` (no route targets: both sides use `0:<VNI>`)

##### Expected Results

- Fabric job completes before k8s job starts (not concurrent)
- K8s job receives the L2 VNI from `Subnet.status.networkSegment` and the L3 VNI from `VirtualNetwork.status.l3Vni`
- `status.taskInput` stores the `virtual_network` snapshot with `status.l3Vni` and no `network_segment`
- The Fabric and Kubernetes entries in `status.jobs` are `Running` then `Succeeded`; the Subnet ends `Ready=True`, reason `Succeeded` (READY)

#### TC-R2-02: Invalid VNI result from the fabric job

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | automated |

##### Preconditions

- **Tier / owner:** Unit + Envtest / [DEV], lane O.
- Subnet provisioning in progress, fabric job completed
- Fabric job's `osac_result` is invalid: `network_segment` missing, `l2_vni` a string or out of 1..16777215, an extra `l3_vni`, or an `l2_vni` that a live VirtualNetwork or Subnet holds

##### Steps

1. Controller validates the fabric job's `osac_result`
2. Validation fails
3. Observe Subnet `Ready=False`, reason `Failed`, with a message naming the broken rule ("VNI already in use" for a held VNI)
4. Repeat with an `l2_vni` held only by a Subnet that has a deletionTimestamp: observe the Fabric `create_subnet` entry goes to `Retrying`, and the rerun is accepted once that Subnet is gone

##### Expected Results

- Subnet provisioning stops for an invalid result (k8s job never created); `status.networkSegment` stays unset
- The message names no VNI and no other resource's ID
- A VNI held only by deleting resources is retried, not rejected
- While retrying, the Fabric `create_subnet` entry is `Retrying` and the Subnet is `Ready=False`, reason `Progressing` (PENDING); after the accepted rerun it reaches `Ready=True`, reason `Succeeded`

### R3: Automatic overlay network provisioning on hosting clusters

#### TC-R3-01: CUDN provisioned with EVPN transport

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Preconditions

- **Tier / owner:** Unit + component integration / [DEV], lane K.
- Owner Subnet input and the target's fake CUDN/VTEP CRDs on disposable Kind
- Generic playbook runs the real manager role; the fixture supplies readiness

##### Steps

1. Observe the VirtualNetwork's namespace `osac-vn-<VirtualNetwork API ID>` (created by Kubernetes `create_virtual_network`) has the label `k8s.ovn.org/primary-user-defined-network`
2. Observe playbook creates ClusterUserDefinedNetwork CR with:
   - metadata.name = `osac-vn-<VirtualNetwork API ID>`
   - metadata.labels `evpn: "true"`
   - metadata.annotations `osac.openshift.io/owner-subnet: <subnet-id>` and `osac.openshift.io/owner-reference: Subnet/<subnet-name>`
   - spec.network.topology = "Layer2"
   - spec.network.transport = "EVPN"
   - spec.network.layer2.mtu = 1500, defaultGatewayIPs = [ipam.gateway_ipv4]
   - spec.network.evpn.vtep = "tenant-vtep"
   - spec.network.evpn.macVRF = {vni: network_segment.l2_vni, routeTarget: "0:<l2_vni>"}
   - spec.network.evpn.ipVRF = {vni: virtual_network.status.l3Vni, routeTarget: "0:<l3_vni>"}
3. Run three isolated negative cases: set `TransportAccepted=False` with the other two conditions True; set `NetworkCreated=False` with the other two True; then set `NetworkAllocationSucceeded=False` with the other two True. In each case, verify the task waits and ends with a retryable readiness timeout
4. In a fresh positive case set all three conditions True and verify success (OVN-Kubernetes 4.22 sets no `Ready` condition)

##### Expected Results

- CUDN CR exists with correct VNI values
- The CUDN records the owner Subnet's ID; the namespace is `osac-vn-<VirtualNetwork API ID>`, never a Subnet name
- Each of the three single-false cases independently waits and publishes `osac_error.retryable: true`; no one or two conditions suffice. Only the all-True case completes successfully
- This case does not run OVN-Kubernetes or prove VXLAN provisioning; deployed behavior belongs to the E2E cases

#### TC-R3-02: VirtualNetwork baseline deny and SecurityGroup policy binding

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- **Tier / owner:** Component integration / [DEV]. `osac-aap/tests/integration/targets/cudn_evpn`.
- NetworkClass with k8s_manager="cudn_evpn" and a VirtualNetwork
- One SecurityGroup in the VirtualNetwork
- One owner Subnet and one VM ComputeInstance ID

##### Steps

1. Run Kubernetes `create_virtual_network`; observe the namespace `osac-vn-<VN API ID>` and `osac-baseline-deny`
2. Verify `osac-baseline-deny` selects every pod, sets both `Ingress` and `Egress`, and allows only DHCP (egress UDP 67, ingress UDP 68); OVN-Kubernetes still allows ARP/ND implicitly
3. Run `create_security_group`; verify `osac-sg-<SG ID>` exists in the VirtualNetwork namespace and its podSelector matches no VM
4. Run `apply_network_attachment` for the VM with this SecurityGroup; verify the policy's podSelector includes `osac.openshift.io/compute-instance-id: <VM ID>`
5. Update the SecurityGroup's rules while the VM stays bound; verify `osac-sg-<SG ID>` replaces its rules and keeps the VM's `osac.openshift.io/compute-instance-id` membership
6. Run `delete_network_attachment`; verify the VM ID is removed and the policy remains
7. Run `delete_security_group`; verify the policy is removed and `osac-baseline-deny` remains

##### Expected Results

- The baseline deny and group policies are VirtualNetwork-scoped, not Subnet-scoped
- A VM with no binding gets only the baseline deny
- Binding and unbinding change members without changing rules; a rule update changes rules without changing members
- Deleting the SecurityGroup does not delete the namespace or the baseline deny

### R4: VM-to-fabric connectivity (L2 same-subnet and L3 cross-subnet scenarios)

#### TC-R4-01: L2 same-subnet VM to bare-metal connectivity

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5, IC-6 | critical | manual |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- CUDN provisioned with `<subnet-cidr>`; `Subnet.status.ipam` records `overlay_ipv4_cidrs`, `physical_ipv4_cidrs`, and `gateway_ipv4`
- VirtualMachine deployed in the VirtualNetwork namespace `osac-vn-<VN API ID>`; its address `<vm-overlay-ip>` is read from the VMI status and lies in `overlay_ipv4_cidrs`
- Bare-metal node provisioned on the Netris fabric in the same Subnet; its address `<physical-dhcp-lease>` comes from `query_dhcp_lease` and lies in `physical_ipv4_cidrs`
- FRR advertising EVPN routes to fabric

##### Steps

1. Verify VM running: `oc get vmi -n <namespace>`
2. Open the VM serial console (`osac` console command or `virtctl console <vm-name>`)
3. Ping bare-metal node: `ping <physical-dhcp-lease>`
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

- **Tier / owner:** E2E / [QE].
- CUDN provisioned with `<subnet-cidr>`; `Subnet.status.ipam` records the address plan
- VirtualMachine deployed in the VirtualNetwork namespace `osac-vn-<VN API ID>`; its address `<vm-overlay-ip>` is read from the VMI status and lies in `overlay_ipv4_cidrs`
- Bare-metal node provisioned on Netris fabric in a sibling Subnet `<sibling-subnet-cidr>`; its address `<sibling-physical-dhcp-lease>` comes from `query_dhcp_lease` and lies in that Subnet's `physical_ipv4_cidrs`
- Both subnets under same Netris VPC (shared ipVRF)

##### Steps

1. Console into VM
2. Ping bare-metal node in different subnet: `ping <sibling-physical-dhcp-lease>`
3. Verify FRR shows Type-5 route for the CUDN prefix: `vtysh -c "show bgp l2vpn evpn" | grep Type-5 | grep <subnet-network>`
4. Verify Netris VPC routing table includes both subnets

##### Expected Results

- Ping succeeds (routed via ipVRF)
- FRR advertises a Type-5 EVPN route for the `<subnet-network>` prefix
- Traffic encapsulated with L3 VNI (ipVRF), not L2 VNI (macVRF)

### R5: Owner-Subnet VM attachment limit

#### TC-R5-01: Second Subnet is accepted, a VM on it fails with the limit error

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Preconditions

- **Tier / owner:** Component integration + Envtest / [DEV], lanes K and O.
- NetworkClass with k8s_manager="cudn_evpn"
- VirtualNetwork created with this NetworkClass
- One Subnet already exists under this VirtualNetwork and owns the hub network
- Install the OSAC Subnet CRD and use owner CR fixtures with the API-ID label, tenant and VirtualNetwork identity; the role reads them through the real Kubernetes API

##### Steps

1. Run `create_subnet` for a second Subnet under the same VirtualNetwork
2. Run `apply_network_attachment` for a VM on the second Subnet
3. Check the real task's `osac_error` diagnostic and eligibility result. In lane O, inject a terminal failed Kubernetes apply and explicit false Subnet eligibility; assert `NetworkReady=False`, reason `SubnetDoesNotSupportVMs`, phase `Failed`, and the exact fixed public message below. Verify feedback preserves the public/private network condition and does not copy a deliberately different raw diagnostic
4. In separate lane O cases, use true and absent eligibility with a final Kubernetes failure: both retain `NetworkAttachmentFailed`. A retryable Kubernetes failure with false eligibility stays progressing, successful apply proceeds, and a final Fabric failure keeps `NetworkAttachmentFailed`. Verify eligibility never prevents the initial create or apply
5. In lane K, use the existing owner Subnet fixture with `osac.openshift.io/subnet-uuid=<owner-id>` in the fixture OSAC namespace. With no workload references, hold that CR in deletion using a test finalizer while its CUDN has no deletion timestamp. Rerun the sibling create: verify the role reads the owner from the API server, fails retryably, and leaves the CUDN unchanged; a stale live-owner observation from an earlier attempt must not be reused
6. Start deleting the CUDN and hold it with a test finalizer while the owner CR remains. Verify another sibling-create attempt still retries. Remove the CUDN finalizer, wait for it to disappear, complete owner-CR deletion, and rerun the sibling create. Verify it claims a new CUDN with its own ID, L2 VNI and original layout, reports support true with an empty reason, and supports VM apply
7. In an isolated orphan fixture, leave a CUDN with an owner ID but no matching Subnet CR. Rerun create: verify a final orphaned-hub-network diagnostic, no adoption and no CUDN change. Cover both non-terminating and terminating orphan CUDNs. In separate owner-read error cases, verify retry rather than treating an API error as owner absence; ambiguous or mismatched owners fail finally without adoption
8. In lane O, assert owner deletion does not automatically rerun an already successful sibling or retry a finally failed VM attachment

##### Expected Results

- `create_subnet` succeeds and creates no second hub network; OSAC does not reject the Subnet (contract §4.7)
- Before owner deletion, the attachment fails as final with `Subnet <X> does not support VMs (VM supported: false)`, the same tenant-readable explanation as `compute_instance_unsupported_reason`, and guidance to create the VM on a supported Subnet such as the current owner Y in the same tenant and VirtualNetwork. Do not require the manager name or claim that Y was the first Subnet ever created
- The ComputeInstance exposes `NetworkReady=False`, reason `SubnetDoesNotSupportVMs`, with fixed public message `The selected Subnet does not support VMs. Create the VM on a Subnet that supports VMs.` API, CLI and UI receive this same reason/message via feedback. Raw task diagnostics remain in administrator-visible hub `status.jobs`; no client inference or forwarding of `osac_error` is needed
- A deleting owner CR causes retry before CUDN termination; a missing owner with a surviving CUDN is a final orphan error. Neither case changes or adopts the existing CUDN
- The owner's hub network is unchanged by the sibling until the owner deletes it; the later claim creates a new network
- In the separate operator fixtures, OSAC records `Subnet.status.computeInstanceSupported: false` and the unsupported reason on the sibling before owner deletion; the owner records true. A successful later claim reports true for the former sibling and clears its unsupported reason without changing its recorded address layout

### R6: Non-conflicting IP address assignment

#### TC-R6-01: VM and physical DHCP addresses follow the recorded pools

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | manual |

##### Preconditions

- **Tier / owner:** E2E / [QE], lane M and the [manual lab procedure](#manual-lab-procedure).
- Netris with `cudn_evpn`, supported gateway mode `gateway_ipv4`, and a non-empty recorded physical pool.
- Create the VM before the first physical attachment; use the owner Subnet.

##### Steps

1. Verify CUDN `spec.network.layer2.reservedSubnets` covers exactly the Subnet outside `ipam.overlay_ipv4_cidrs`; no legacy first-half physical pool is reserved or handed out
2. Verify `infrastructureSubnets` alone contains `[<gateway_ipv4>/32, <network + 2>/32]`
3. Before any physical attachment, follow the [DHCP observation procedure](#dhcp-observation-procedure): force a VM DHCP exchange with simultaneous guest and validated fabric captures. Verify OVN supplies an address inside `overlay_ipv4_cidrs`, router `gateway_ipv4` and cluster DNS; the matching VM request is absent at the Netris segment. The resolver address need not be inside the overlay
4. Follow manual setup step 4: attach a physical host through BMaaS, capture its DHCP exchange, obtain its active `query_dhcp_lease` result, and match the MAC and address to the host and recorded physical pool
5. With the physical host attached, repeat the simultaneous captures and force another VM DHCP exchange. Correlate MAC/client identity and transaction ID to confirm its request still does not reach Netris, and recheck the selected server, overlay address, router and DNS. Retain positive-control traffic and captures from both attachment states

##### Expected Results

- In both pre-attachment and post-attachment captures, OVN-Kubernetes answers VM DHCP inside the logical switch and the matching VM request is absent from the validated fabric observation point. A lease alone, a capture without positive-control traffic, or no observed guest renewal is insufficient to pass
- The VM address excludes infrastructure, physical DHCP and LB VIP addresses; its router and DNS match their independent expectations
- The physical lease is inside `physical_ipv4_cidrs`, and Netris's scope contains only that recorded pool
- This is deployed lease evidence; Netris task creation/repair semantics are tested separately below

#### TC-R6-02: Fabric DHCP create, rerun repair and attachment ordering

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- **Tier / owner:** Component integration / [DEV], lane N (`cases_vn_subnet.yaml`, `cases_attachment.yaml`).
- Real generic playbook/role with the stateful Netris fake, a non-empty physical pool and supported `gateway_ipv4` mode.

##### Steps

1. Run `create_subnet` and read the fake controller state before any attachment: DHCP is enabled only over the recorded physical range
2. Disable or alter that scope in the fake, rerun `create_subnet`, and verify it restores the original recorded range without changing the VNI or gateway
3. Drift the scope again and run physical `apply_network_attachment`; inspect the fake's request history to verify DHCP repair completes before the first port move
4. Repeat the successful tasks and verify they keep the same range and allocation; delete the attachment and verify DHCP remains enabled

##### Expected Results

- Creation, rerun and attachment repair converge on the recorded pool
- Repair precedes port movement; no legacy first-half or overlay pool is used
- The fake controller verifies requests and ordering, not an actual DHCP exchange

#### TC-R6-03: Empty physical pool and lab-only gateway diagnostics

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

##### Preconditions

- **Tier / owner:** Component integration / [DEV], lane N; disposable fake-controller fixtures only.
- One valid address layout has `physical_ipv4_cidrs: []`.

##### Steps

1. Run `create_subnet` with that empty pool in supported `gateway_ipv4` mode; verify DHCP stays off on create and rerun
2. Attempt a physical attachment; verify it fails finally before any port or policy change because no physical address range exists
3. Run attachment delete for the failed apply; verify it does not enable DHCP
4. Separately run the existing `files/gateway_mode_none.yml` diagnostic fixture on a fresh Subnet with a non-empty pool. Verify the override creates no gateway or DHCP and physical apply fails without moving a port

##### Expected Results

- Empty pools never enable DHCP or allow a physical attachment
- The explicit `none` override is covered only as a developer diagnostic regression. Like `physical_first`, it is a lab-only mode in OSAC-2434, not a supported deployment or conformance option


### R7: Installation prerequisites documentation

#### TC-R7-01: Installation guide covers all manual prerequisites

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| — | high | manual |

##### Preconditions

- **Tier / owner:** Documentation review / [DEV], lane D.
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

- **Tier / owner:** Documentation review / [DEV], lane D.
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

- **Tier / owner:** Documentation review / [DEV], lane D.
- Access to installation guide

##### Steps

1. Read installation prerequisites
2. Verify guide documents gateway MAC coordination requirement
3. Verify guide explains consequences of mismatch (L3 traffic fails, ARP flapping)

##### Expected Results

- Gateway MAC coordination listed as prerequisite, or the two MACs documented as a known limitation for a fabric that serves the gateway too (contract §4.9)
- Guide explains the effect of two gateway MACs on routed traffic

### SecurityGroup ICMP: capability gate with cudn_evpn

#### TC-ICMP-01: ICMP capability gate rejects ICMP rules and accepts protocol all

Traces to contract FR-13 and [TC-CAP-03](/enhancements/OSAC-1433-network-manager-integration-contract-networking/testplan.md#tc-cap-03-reject-icmp-rules-at-the-securitygroup-api); it adds no PRD requirement. This is an executable lower-tier API case, not a removed E2E case counted as coverage.

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | medium | automated |

##### Preconditions

- **Tier / owner:** Component integration / [DEV], lane F; `fulfillment-service/it/it_networking_design_test.go` (`TC-SG-ICMP-01`).
- The fixture reports a READY NetworkClass with `security_group_icmp: false`, as Netris plus `cudn_evpn` derives. Fulfillment, PostgreSQL and Keycloak are real; readiness/capability is fixture-controlled, no AAP or VM runs.

##### Steps

1. Create a SecurityGroup with an ICMP ingress rule through the public API
2. Assert `INVALID_ARGUMENT`, guidance to use protocol `all`, and that no group was stored
3. Create a SecurityGroup with `all` rules and verify the stored rule fields; clean up the group

##### Expected Results

- The API rejects ICMP rules when the resolved capability is false and accepts `all`
- No manager task is needed to reject the invalid rule
- This proves API semantics only. ICMP packet delivery with `all` belongs to deployed connectivity tests; a capable NetworkClass reaching READY through real AAP is a separate coverage gap


### Subnet Deletion: Ordered cleanup prevents stale VRFs

#### TC-DELETE-01: Workloads block Subnet deletion; networking never deletes VMs

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | manual |

##### Preconditions

- **Tier / owner:** E2E / [QE].
- Owner Subnet with a READY CUDN and a VM running in `osac-vn-<VN API ID>`
- A sibling Subnet under the same VirtualNetwork
- A SecurityGroup whose policy is `osac-sg-<SG ID>` in the VirtualNetwork namespace
- The VM's stored network attachment references the owner Subnet

##### Steps

1. Delete the owner Subnet through the fulfillment-service API; verify `FAILED_PRECONDITION` gives the count and names the first blocking workload ID
2. Verify the VM and its VMI still exist and were not touched by networking
3. Delete the sibling Subnet while the owner CUDN and VM still exist; verify its VNet is removed, the owner CUDN is unchanged, and the VM and VMI are untouched
4. Delete the VM through ComputeInstance/VMaaS cleanup; verify the VMI and the NetworkAttachment are gone
5. Before deleting the owner Subnet, start observing its CUDN UID and both managers' `delete_subnet` jobs. Delete it, record the CUDN disappearing, and retain the Kubernetes job's successful wait for CUDN absence and terminal success. Record when the Fabric VNet delete job starts in AAP; verify it starts only after that Kubernetes success and CUDN removal, then verify the VNet disappears. Use the two AAP jobs' common timeline and the Kubernetes wait result for ordering evidence; merely finding both resources absent at the end does not pass
6. Verify the VirtualNetwork namespace, `osac-baseline-deny`, and `osac-sg-<SG ID>` still exist
7. Delete the SecurityGroup; verify `osac-sg-<SG ID>` is removed
8. Delete the VirtualNetwork; verify `osac-vn-<VN API ID>` and `osac-baseline-deny` are removed and Fabric removes the VPC
9. Check for stale VRF devices on worker nodes

##### Expected Results

- A workload reference blocks the Subnet delete; networking does not delete the VM, and the VM still exists after the rejection
- The owner Subnet removes only the CUDN; the VirtualNetwork namespace and baseline deny remain until the VirtualNetwork is deleted
- A sibling Subnet's delete changes no CUDN and leaves the owner's VM and VMI untouched, even while the owner CUDN and VM still exist
- No stuck Subnet delete; the CUDN is fully removed before the Fabric VNet, and the delete completes after workloads and NetworkAttachments are gone
- **Normal case:** no stale VRF devices persist after the CUDN is deleted
- **Rare failure case:** stale VRF requires manual recovery (see TC-DELETE-02 and Support Procedures)

#### TC-DELETE-02: Stale VRF manual recovery (troubleshooting)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| — | low | manual |

##### Preconditions

- **Tier / owner:** E2E / [QE].
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

## Summary and gaps

| Priority | Cases |
|---|---:|
| critical | 5 |
| high | 9 |
| medium | 2 |
| low | 1 |
| Total | 17 |

Planned automation: 9 automated cases and 8 manual cases. Runtime execution for this revision: not run. All R1–R9 requirements map to planned cases; this is not a passing coverage claim. No case exercises IC-4.

TC-R5-01 specifies the dedicated public failure reason and the required direct owner-Subnet lookup, including the deletion window and orphan refusal. Its extended fixtures and assertions must be implemented and executed; this document does not claim existing runtime coverage. Physical leases, cross-Subnet traffic, gateway-MAC behavior and full lifecycle acceptance require lane M. The VM-only lane L and fake-backed lane N are not substitutes. Deployed networking evidence is owned by [QE] under [OSAC-4291](https://redhat.atlassian.net/browse/OSAC-4291) and [OSAC-4843](https://redhat.atlassian.net/browse/OSAC-4843); new [DEV] assertions and implementation gaps remain under OSAC-4291 until assigned a dedicated task. A stale-VRF recovery check that cannot reproduce its precondition is recorded as not exercised.
