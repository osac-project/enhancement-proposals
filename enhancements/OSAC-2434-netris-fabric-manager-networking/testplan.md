# Testplan — OSAC-2434

## Overview

- **Feature:** OSAC-2434 — Netris Fabric Manager
- **Total test cases:** 38
- **Requirements covered:** 11 of 11 (R1–R11)
- **Anchors:** the PRD has no numbered requirements, so R1–R11 name its In
  Scope items and user stories.
- **Status** (true for osac `main` at `dbcde0d75`):
  - **Covered:** a named test on `main` runs the case and passes.
  - **Gap:** `main` lacks the behavior or its test; the case says what lands it.
  - **Blocked:** a test exists or is specified here but cannot pass until a
    named dependency lands.
- **Owners:** Unit, Integration and Envtest cases are [DEV]; E2E cases are [QE].

### Tiers

| Tier | Boundary | Real / fake | Command (working directory) |
|---|---|---|---|
| Unit (osac-aap) | Filters, the ExternalIP module, and role tasks through `playbook_osac_network_task.yml` in child Ansible processes | In-memory Netris double `tests/unit/netris_fake.py`; no AAP, Kubernetes, switches or Netris | `uv run --group development pytest tests/unit` (`osac-aap/`) |
| Unit (installer) | Rendered `osac` chart | Real `helm template`; no cluster | `uv run --project .. python scripts/test-networking-values.py` (`osac-installer/`) |
| Integration (osac-aap) | The real `osac.templates.netris` role through the generic playbook, as AAP launches it | Stateful fake Netris `tests/integration/fixtures/netris/fake_netris.py`, unusable kubeconfig; no AAP, operator, switches or Netris | `uv run ansible-playbook targets/netris_fabric/tasks/baseline.yml -e '@common_vars.yml'` and `targets/network_task_playbook/tasks/baseline.yml` (`osac-aap/tests/integration/`); also in `make test` |
| Envtest (osac-operator) | Real reconcilers and network task engine on envtest | In-memory AAP; no job runs a role | `make test` (`osac-operator/`) |
| E2E | Deployed OSAC on the osac-test-infra Netris lab | Real Netris controller, switches, SoftGates, OVN-Kubernetes, AAP | PR comment `/test vmaas-netris`, `/test bmaas-netris`, `/test stretched-netris`; working directory N/A (lab workflow) |

### Follow-up owners

| Dependency | Ticket |
|---|---|
| BMaaS runs the contract attachment tasks | [OSAC-1437](https://redhat.atlassian.net/browse/OSAC-1437) |
| CaaS assigns the ingress address and drops the ingress task calls | [OSAC-1436](https://redhat.atlassian.net/browse/OSAC-1436) |
| FabricDomain template in the task input | [OSAC-1382](https://redhat.atlassian.net/browse/OSAC-1382) |
| Live Netris beyond the lab suites | [OSAC-4843](https://redhat.atlassian.net/browse/OSAC-4843) |
| EVPN DHCP at create; ingress task files removed | osac#2286 (no Jira) |
| Serialization, capacity check, attachment delete, settings, site ownership, pool delete check, SG bind test, same-CIDR E2E, hairpin, conformance run | unresolved |

| ID | Scenario | Tier | Priority | Status |
|----|----------|------|----------|--------|
| TC-R1-01 | Installer renders the Netris registration | Unit (installer) | high | Covered |
| TC-R1-02 | A bad setting is retryable and named | per row | high | Covered |
| TC-R1-03 | Class map and CA bundle settings | Integration | high | Gap |
| TC-R2-01 | VirtualNetwork becomes a VPC and returns its L3 VNI | Integration | critical | Covered |
| TC-R2-02 | Two VirtualNetworks with the same CIDR are isolated | E2E | critical | Gap |
| TC-R2-03 | Network type and VNI checks | Integration | high | Covered |
| TC-R3-01 | Subnet becomes a V-Net and returns its L2 VNI | Integration | critical | Covered |
| TC-R3-02 | Replaced VPC fails the Subnet as final | Integration | high | Covered |
| TC-R3-03 | VM and bare metal on one Subnet reach each other | E2E | critical | Blocked |
| TC-R3-04 | EVPN V-Net DHCP is on from create, and a rerun restores it | Integration | critical | Gap |
| TC-R3-05 | V-Net gateway and DHCP range plan | Unit (osac-aap) | high | Covered |
| TC-R4-01 | Bare metal on two Subnets of one VirtualNetwork route | E2E | critical | Blocked |
| TC-R4-02 | VM routes to bare metal on another Subnet | E2E | critical | Blocked |
| TC-R5-01 | Physical apply moves the ports onto the DHCP V-Net | Integration | critical | Covered |
| TC-R5-02 | Physical apply rejections | Integration | high | Covered |
| TC-R5-03 | Lease query returns the host's address | per row | critical | Covered |
| TC-R5-04 | Full physical range fails before any write | Integration | high | Gap |
| TC-R5-05 | One physical attachment task at a time per Fabric Manager | Envtest | high | Gap |
| TC-R5-06 | Delete returns every fabric port and releases the address | Integration | critical | Gap |
| TC-R5-07 | Concurrent BareMetalInstances keep every port | E2E | high | Blocked |
| TC-R6-01 | Pool creates the allocation and its common subnet | Integration | critical | Covered |
| TC-R6-02 | ExternalIP allocation | per row | critical | Covered |
| TC-R6-03 | VMaaS NAT egress and ExternalIP ingress carry traffic | E2E | critical | Covered |
| TC-R6-04 | NAT rule placement and delete refusals | per row | high | Covered |
| TC-R6-05 | Pool delete refuses a changed CIDR | Integration | medium | Gap |
| TC-R6-06 | BMaaS NAT egress and ExternalIP ingress carry traffic | E2E | high | Blocked |
| TC-R6-07 | Hairpin through a NATGateway to an ExternalIP | E2E | high | Gap |
| TC-R7-01 | Cluster ingress address answers on a Netris Subnet | E2E | high | Gap |
| TC-R7-02 | No cluster ingress Fabric tasks | per row | high | Gap |
| TC-R8-01 | FabricDomain Server Cluster lifecycle | per row | medium | Covered |
| TC-R8-02 | Server Cluster template from the task input | Integration | medium | Gap |
| TC-R9-01 | Objects of another tenant or VPC are refused | Integration | critical | Covered |
| TC-R9-02 | Objects on another site are refused | Integration | high | Gap |
| TC-R10-01 | Delete with faults stays retryable and completes | Integration | high | Covered |
| TC-R10-02 | Error classification and sanitized messages | Integration | high | Covered |
| TC-R11-01 | SecurityGroup and overlay tasks send no request | Integration | high | Covered |
| TC-R11-02 | Physical apply ignores `security_group_ids` | Integration | medium | Gap |
| TC-R11-03 | Conformance profiles on the Netris lab | E2E | high | Gap |

## Test Cases

### R1: Installation from OSAC's release

#### TC-R1-01: Installer renders the Netris registration

**Steps:** 1. Render the `osac` chart with `global.networking.fabricManager: netris` → 2. Render it with another Fabric Manager.
**Expected:** With `netris`, one immutable ConfigMap `osac-network-fabric-manager-netris` labelled `osac.openshift.io/network-fabric-manager: "true"` with `name: netris`, `ansible_role: osac.templates.netris`, `network_types: evpn`, `capabilities: eastWestEthernet,security_group_icmp`; otherwise no such ConfigMap. Existing: `test-networking-values.py` `test_netris_registration_is_contract_format`, `test_no_netris_registration_for_another_fabric_manager`.

#### TC-R1-02: A bad setting is retryable and named (parameterized)

Every row: `osac_error.retryable: true`, a message starting "Missing or malformed setting in network-fulfillment-ig" that names the variable, no Netris request.

| Setting | Tier | Existing |
|---|---|---|
| `NETRIS_SITE_ID` unset | Integration | `cases_errors.yaml` |
| `NETRIS_TENANT_ID` `0` or not an integer | Unit (osac-aap) | `test_netris_role.py` `test_a_bad_setting_is_named` |
| `NETRIS_CONTROLLER_URL` without `http`/`https` scheme | Unit (osac-aap) | same |
| `NETRIS_VALIDATE_CERTS: "unexpected"` (not an error: TLS verification stays on) | Unit (osac-aap) | `test_netris_validate_certs.py` |

#### TC-R1-03: Class map and CA bundle settings (parameterized)

| Input | Expected Result |
|---|---|
| `create_fabric_domain` with no template in the input and `NETRIS_RESOURCE_CLASS_MAP` naming two templates, or not JSON | retryable, names `NETRIS_RESOURCE_CLASS_MAP`; no write (today final) |
| `NETRIS_CA_BUNDLE` with the fake controller's PEM CA and `NETRIS_VALIDATE_CERTS: "true"` | the task writes the bundle to a file in the job and succeeds over TLS |
| `NETRIS_CA_BUNDLE` that is not PEM | retryable, names `NETRIS_CA_BUNDLE`; no request |

### R2: VirtualNetwork isolation

#### TC-R2-01: VirtualNetwork becomes a VPC and returns its L3 VNI

**Steps:** 1. Run `create_virtual_network` with `network_type: evpn` → 2. Rerun it.
**Expected:** VPC `osac-vn-<id>` and allocation `osac-vn-<id>` over the VirtualNetwork CIDR exist once; both runs return the same `l3_vni` (integer) and `backend_id` (VPC ID as a string); the rerun sends no write. Existing: `cases_vn_subnet.yaml`.

#### TC-R2-02: Two VirtualNetworks with the same CIDR are isolated

**Steps:** 1. Create two VirtualNetworks with the same CIDR, each with a VM → 2. Ping and arping from each VM to the other's address.
**Expected:** No reply either way. Proposed: in `tests/e2e/networking/vmaas/test_vmaas_networking.py`, create network `b` with `vn_cidrs[0]` (today each network has its own /16, so `test_02`/`test_03` cross distinct CIDRs).

#### TC-R2-03: Network type and VNI checks (parameterized)

| Condition | Expected Result |
|---|---|
| `network_type: vlan` | final, "Netris supports network_type evpn only" |
| VPC or V-Net with no VNI right after create | retryable, "Netris has not assigned the VNI yet" |
| VNI above 16777215 | final, "Netris returned a VNI outside 1..16777215" |
| `create_virtual_network` without network type | result has `backend_id` only |

Existing: `cases_paths.yaml`, `cases_vn_subnet.yaml`.

### R3: VMs and bare metal on one Subnet

#### TC-R3-01: Subnet becomes a V-Net and returns its L2 VNI

**Steps:** 1. Run `create_subnet` with `network_type: evpn` and the VPC's VNI in `virtual_network.status.l3Vni` → 2. Rerun it → 3. Change the V-Net gateway in Netris and rerun.
**Expected:** V-Net `osac-sn-<id>` in the VPC with gateway `gateway_ipv4/<prefix>` and IPAM subnet `osac-sn-<id>`; every run returns `network_segment: {type: evpn, l2_vni: <V-Net VXLAN ID>}`; step 2 writes nothing; step 3 restores the gateway with one update. Existing: `cases_vn_subnet.yaml`.

#### TC-R3-02: Replaced VPC fails the Subnet as final

**Steps:** 1. Run `create_subnet` with a `virtual_network.status.l3Vni` that differs from the VPC's VNI.
**Expected:** `retryable: false`, "has L3 VNI <n>, but the VirtualNetwork recorded <m>. The VPC was replaced outside OSAC."; no IPAM subnet or V-Net. Existing: `cases_vn_subnet.yaml`.

#### TC-R3-03: VM and bare metal on one Subnet reach each other

**Steps:** 1. Create a VM and a BareMetalInstance on one Subnet → 2. Ping each from the other.
**Expected:** Replies both ways. Existing: `tests/e2e/networking/stretched/test_shared_subnet_bmi_compute_instance.py` (`/test stretched-netris`). Blocked by OSAC-1437.

#### TC-R3-04: EVPN V-Net DHCP is on from create, and a rerun restores it

**Steps:** 1. Run `create_subnet` with `network_type: evpn` → 2. Turn the V-Net's DHCP off in the fake and rerun → 3. Run it for a Subnet whose physical range ends at the Subnet's last address.
**Expected:** After step 1 and step 2, DHCP is on from the first to the last physical address; step 3 ends DHCP one address before broadcast. Today DHCP stays off until the first physical apply (`cases_vn_subnet.yaml` asserts no DHCP). Lands with osac#2286.

#### TC-R3-05: V-Net gateway and DHCP range plan (parameterized)

| Subnet | Expected plan |
|---|---|
| No network type, gateway outside the physical range | gateway `gateway_ipv4/<prefix>`, DHCP over the physical range only |
| Gateway inside the physical range | DHCP starts at the address after the gateway |
| Empty `physical_ipv4_cidrs` | no DHCP, no error |

Existing: `test_netris_vn_subnet.py`.

### R4: Routing between Subnets

#### TC-R4-01: Bare metal on two Subnets of one VirtualNetwork route

**Steps:** 1. Two BareMetalInstances on two Subnets of one VirtualNetwork → 2. Ping across; arping across.
**Expected:** Ping replies; arping gets no reply. Existing: `bmaas_networking` `test_08`, `test_09`. Blocked by OSAC-1437.

#### TC-R4-02: VM routes to bare metal on another Subnet

**Steps:** 1. A VM on the hub-network owner Subnet and a BareMetalInstance on a second Subnet of the same VirtualNetwork → 2. Ping and TCP connect both ways.
**Expected:** Replies and connections both ways through `gateway_ipv4`. No test yet; proposed in `tests/e2e/networking/stretched/`. Blocked by OSAC-1437 and the lab's leaves importing `0:<VNI>` (unresolved).

### R5: Bare-metal addresses

#### TC-R5-01: Physical apply moves the ports onto the DHCP V-Net

**Steps:** 1. Fake host with two ports on the provisioning V-Net; EVPN Subnet with physical ranges followed by an LB VIP range → 2. Run the physical `apply_network_attachment` → 3. Rerun it → 4. Rerun `create_subnet`.
**Expected:** Both ports leave the provisioning V-Net; only `interface.name` is on `osac-sn-<id>`; DHCP runs from the first to the last physical address, before the LB VIP range; steps 3 and 4 write nothing and DHCP stays on. Existing: `cases_attachment.yaml`.

#### TC-R5-02: Physical apply rejections (parameterized)

| Condition | Expected Result |
|---|---|
| Unknown port name on a known host | final, "has no port named"; no write |
| Empty `physical_ipv4_cidrs` | final, "no fabric address range for bare-metal DHCP"; no write |
| Host not in Netris | retryable, "the host must be registered in Netris" |
| Subnet V-Net missing | retryable, "the Subnet must be created first" |

Existing: `cases_attachment.yaml`, `cases_paths.yaml`.

#### TC-R5-03: Lease query returns the host's address (parameterized)

| IPAM hosts with the MAC | Expected Result | Tier |
|---|---|---|
| One | `dhcp_lease: {ip_address: <host IP>, mac_address: <input MAC>}` | Integration (`cases_attachment.yaml`) |
| None | retryable, "no DHCP lease for the interface MAC address yet" | Integration (`cases_paths.yaml`) |
| Two | retryable, "more than one IPAM host has the interface MAC address" | Unit (osac-aap) (`test_netris_attachment.py`) |

#### TC-R5-04: Full physical range fails before any write

**Steps:** 1. Fake Subnet whose DHCP range holds three addresses: server A has a port on the V-Net and an IPAM host, server B a port and no IPAM host, a provider device an IPAM host → 2. Apply for server C → 3. Apply for server D, whose MAC already has an IPAM host on the V-Net → 4. Apply for B again → 5. Remove the device's IPAM host and apply for C.
**Expected:** Step 2: final, the message names the full range, no write, C's ports stay on the provisioning V-Net. Steps 3 and 4: success (an address held for the MAC; a port already on the V-Net). Step 5: success, C's port moves.

#### TC-R5-05: One physical attachment task at a time per Fabric Manager

**Steps:** 1. In osac-operator envtest with the in-memory AAP, create three physical NetworkAttachments, two on one Subnet and one on another, at once → 2. Complete each running job in turn.
**Expected:** At most one physical `apply_network_attachment` job is running at any time; each next one starts only after the previous ended; all three end `Succeeded`. Proposed: `osac-operator/internal/controller/networking_attachments_test.go`.

#### TC-R5-06: Delete returns every fabric port and releases the address

**Steps:** 1. Host with three ports: two on the Subnet V-Net after an apply (one moved by an earlier attachment), one in a Server Cluster; an IPAM host for `interface.mac_address` on `osac-sn-<id>` → 2. Run the physical `delete_network_attachment` → 3. Rerun it.
**Expected:** Both non-cluster ports are on the provisioning V-Net, the Server Cluster port is unchanged, the MAC has no IPAM host on `osac-sn-<id>`; the rerun writes nothing. Today only `interface.name` returns and the IPAM host stays.

#### TC-R5-07: Concurrent BareMetalInstances keep every port

**Steps:** 1. Create two BareMetalInstances on one Subnet and one on another at once.
**Expected:** Each gets its lease and its port is on its Subnet's V-Net; no host port stays on the provisioning V-Net. Blocked by OSAC-1437 and TC-R5-05.

### R6: External addresses

#### TC-R6-01: Pool creates the allocation and its common subnet

**Steps:** 1. Run `create_external_ip_pool` with one CIDR → 2. Rerun → 3. Run it with two CIDRs.
**Expected:** Allocation `osac-pool-<id>` and subnet `osac-pool-<id>-common` (purpose `common`) over the CIDR; the rerun writes nothing; step 3 final, "resource.spec.cidrs must hold exactly one canonical IPv4 CIDR", nothing created. Existing: `cases_eip_nat_fd.yaml`, `cases_paths.yaml`.

#### TC-R6-02: ExternalIP allocation (parameterized)

| Case | Expected Result | Tier |
|---|---|---|
| Rerun of one ExternalIP | same `external_ip.address`, one `osac-eip-<id>` `/32` nat reservation | Integration |
| Two ExternalIPs in one pool | two different addresses | Integration |
| Full pool | final, "is full" | Integration |
| Reservation with the name of another tenant | final, "belongs to another tenant, site or pool" | Integration |
| A parallel allocation takes the address (409) | the task refreshes and retries; after the bounded retries, retryable | Unit (osac-aap) |
| Netris refuses the pool CIDR (409 on the allocation) | final, "Netris refused the ExternalIPPool CIDR" | Integration |

Existing: `cases_eip_nat_fd.yaml`, `cases_paths.yaml`, `test_netris_external_ip.py`.

#### TC-R6-03: VMaaS NAT egress and ExternalIP ingress carry traffic

**Steps:** 1. NATGateway on a VirtualNetwork with a VM → 2. Fetch the egress URL → 3. Attach an ExternalIP and connect to it from outside → 4. Delete the attachment and connect again.
**Expected:** The remote sees the NATGateway address; the inbound connection reaches the VM; after delete it is refused or times out. Existing: `vmaas_networking` `test_09`–`test_12`.

#### TC-R6-04: NAT rule placement and delete refusals (parameterized)

| Case | Expected Result | Tier |
|---|---|---|
| `attach_external_ip` to a tenant workload | DNAT `osac-eipa-<id>` in the destination VirtualNetwork's VPC | Integration |
| `attach_external_ip` to `provider_management` | DNAT in `NETRIS_MGMT_VPC_ID` | Integration |
| `create_nat_gateway` | SNAT `osac-natgw-<id>`, VirtualNetwork CIDR → `<external>/32`, in its VPC | Integration |
| Detach or NATGateway delete when the rule's addresses changed | final; rule kept, no write | Integration |
| ExternalIP delete when the `/32` is outside the pool, not purpose `nat`, or of another tenant or site | final; reservation kept | Unit (osac-aap) |

Existing: `cases_eip_nat_fd.yaml`; `test_netris_external_ip.py` `test_owned_address_fails_closed_on_mismatched_reservation`.

#### TC-R6-05: Pool delete refuses a changed CIDR

**Steps:** 1. Create a pool → 2. Change the allocation's prefix in the fake → 3. Run `delete_external_ip_pool`.
**Expected:** Final mismatch; allocation and common subnet kept. Today the delete does not compare the CIDR.

#### TC-R6-06: BMaaS NAT egress and ExternalIP ingress carry traffic

**Steps and Expected:** as TC-R6-03 with a BareMetalInstance. Existing: `bmaas_networking` `test_11`–`test_13`. Blocked by OSAC-1437.

#### TC-R6-07: Hairpin through a NATGateway to an ExternalIP

**Steps:** 1. VirtualNetwork with a NATGateway and two workloads; an ExternalIP attached to the second → 2. From the first, connect to the ExternalIP.
**Expected:** The connection reaches the second workload. No test yet; the contract's `cluster` conformance profile checks it (TC-R11-03).

### R7: Cluster ingress address

#### TC-R7-01: Cluster ingress address answers on a Netris Subnet

**Steps:** 1. Create the smallest Cluster on a Netris Subnet → 2. From the runner, request a route under `*.apps`.
**Expected:** The ingress address lies in the Subnet's LB VIP range and the route answers. Gap: OSAC-1436.

#### TC-R7-02: No cluster ingress Fabric tasks (parameterized)

| Check | Expected Result | Tier |
|---|---|---|
| The generic playbook's Fabric task set and the `netris_fabric` lifecycle | exactly 19 tasks, no `*_cluster_ingress_ip`; `roles/netris/tasks` has neither file | Integration |
| A ClusterOrder created and deleted | the controller launches no `reserve_cluster_ingress_ip` or `release_cluster_ingress_ip` job | Envtest |

Today both targets assert 21 tasks and the ClusterOrder controller calls both. Role: osac#2286; controller: OSAC-1436.

### R8: Ethernet east-west domains

#### TC-R8-01: FabricDomain Server Cluster lifecycle (parameterized)

| Case | Expected Result | Tier |
|---|---|---|
| `create_fabric_domain` with two servers | Server Cluster `osac-fd-<id>` in the VPC with exactly those servers; `backend_id` its ID | Integration |
| Rerun with one server replaced | exactly the new servers, no second Server Cluster | Unit (osac-aap) |
| Delete, then delete again | the Server Cluster is gone; the second delete writes nothing | Integration |

Existing: `cases_eip_nat_fd.yaml`; `test_netris_fabric_domain.py` `test_create_fabric_domain_resizes_to_the_new_servers`.

#### TC-R8-02: Server Cluster template from the task input

**Steps:** 1. Run `create_fabric_domain` with a template in the input while `NETRIS_RESOURCE_CLASS_MAP` holds two other templates.
**Expected:** The Server Cluster uses the input template. Gap: the input has no template field yet (OSAC-1382). The operator's template resolution belongs to the east-west test plan.

### R9: Ownership

#### TC-R9-01: Objects of another tenant or VPC are refused (parameterized)

| Object with an OSAC name | Expected Result |
|---|---|
| V-Net in another VPC | `create_subnet` final, "already exists in another tenant or VPC"; no IPAM subnet |
| V-Net whose owner Netris does not report | final, "its VPC or tenant is not reported"; no write |
| VPC of another Netris tenant, FabricDomain create | final, "belongs to another tenant"; no write |

Existing: `cases_isolation.yaml`, `cases_paths.yaml`.

#### TC-R9-02: Objects on another site are refused

**Steps:** 1. Fake a VPC and a V-Net with OSAC names, in the OSAC tenant and VPC but on a site other than `NETRIS_SITE_ID` → 2. Run `create_virtual_network`, `create_subnet` and their deletes.
**Expected:** Each run is final; nothing is written or deleted. Today the owner check compares only VPC and tenant.

### R10: Failure visibility and recovery

#### TC-R10-01: Delete with faults stays retryable and completes

**Steps:** 1. Make the IPAM subnet delete answer 500 during `delete_subnet` → 2. Remove the fault and rerun → 3. Delete an absent Subnet.
**Expected:** Step 1 retryable, V-Net gone, IPAM subnet kept; step 2 deletes the IPAM subnet; step 3 succeeds with no write. Existing: `cases_delete.yaml`.

#### TC-R10-02: Error classification and sanitized messages (parameterized)

| Fault | Expected Result |
|---|---|
| Netris answers 5xx | retryable |
| 400 on the VirtualNetwork allocation CIDR | final; the message names the CIDR |
| Login answers 500 | retryable |
| Controller unreachable | retryable |

Every message carries the step name and no response body, cookie or password. Existing: `cases_errors.yaml`.

### R11: SecurityGroups are a documented no-op

#### TC-R11-01: SecurityGroup and overlay tasks send no request

**Steps:** 1. Run `create_security_group`, `delete_security_group`, and the overlay `apply_network_attachment` and `delete_network_attachment`.
**Expected:** Each succeeds with no Netris request. Existing: `netris_fabric` `baseline.yml` lifecycle (`noreq`), `cases_attachment.yaml`.

#### TC-R11-02: Physical apply ignores `security_group_ids`

**Steps:** 1. Run the physical apply with `security_group_ids: [<id>]` → 2. Compare with a run with `[]`.
**Expected:** Same requests and result; no ACL request. Today every test passes `[]`.

#### TC-R11-03: Conformance profiles on the Netris lab

**Steps:** 1. Run the contract conformance suite (§4.11) with Netris as the Fabric Manager and `cudn_evpn`.
**Expected:** `vm` conformant; `baremetal` conformant with the blocked-port check skipped as the documented SecurityGroup no-op; `cluster` conformant, including hairpin. The suite is not on `main`; `baremetal` also needs OSAC-1437 and `cluster` OSAC-1436.

## Summary

| Status | Cases |
|---|---|
| Covered | 19 |
| Gap | 14 |
| Blocked | 5 |

| Priority | Cases |
|---|---|
| critical | 14 |
| high | 20 |
| medium | 4 |
