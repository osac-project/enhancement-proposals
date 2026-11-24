# Testplan — OSAC-8117

## Overview

- **Feature:** OSAC-8117 — Aviz ONES Fabric Manager
- **Total test cases:** 34: 31 for phase 1 (bare metal) and 3 deferred to
  phase 2 (VMs)
- **Requirements covered:** 8 of 8 phase 1 requirements (R1–R3, R5–R9);
  R4 is phase 2
- **Anchors:** the PRD has no numbered requirements, so R1–R9 name its In
  Scope items and user stories. External addresses and NAT are phase 2 and
  get their cases with the phase 2 design.
- **Status:**
  - **Covered:** a named test runs the case and passes: a pytest test of the
    ONES role, or a case of the ONES live suite (last run 2026-11-22, 18 of
    18 passed).
  - **Gap:** the behavior or its test is not written yet; the case says what
    lands it.
  - **Blocked:** the case cannot pass until a named dependency lands: an ONES
    capability ([design](design.md#ones-capabilities)) in the ONES
    development build, or an OSAC feature.
  - **Deferred:** the case belongs to phase 2 and is not counted for phase 1.
- **Owners:** Unit cases are [DEV]; Live and E2E cases are [QE], run on the
  ONES lab that Aviz provides.

### Tiers

| Tier | Boundary | Real / fake | Command (working directory) |
|---|---|---|---|
| Unit (osac-aap) | Filters and the `aviz.ones` client | No ONES, no Ansible run | `uv run --group development pytest tests/unit/test_ones_contract.py` (`osac-aap/`) |
| Unit (playbook) | The real `aviz.ones.fabric_manager` role through `playbook_osac_network_task.yml` in child Ansible processes | Stateful fake ONES `tests/unit/ones_fake.py`; no AAP, Kubernetes, switches or ONES | `uv run --group development pytest tests/unit/test_ones_playbook.py` (`osac-aap/`) |
| Live | The real role through the generic playbook, as AAP launches it, against a real ONES | Real ONES (API v4.0; v4.5.0 calls the same tenant APIs), virtual Cumulus fabric (spines, compute, border and storage leaves), real servers; no AAP or operator | ONES live suite on the ONES lab |
| E2E | Deployed OSAC on the ONES lab | Real ONES development build, fabric, OVN-Kubernetes, AAP | Lab workflow; working directory N/A |

### Follow-up owners

| Dependency | Owner |
|---|---|
| O3 tenant address plan, O5 same CIDR in two tenants (phase 1) | Aviz (ONES development build) |
| O1 hub nodes as EVPN VTEPs, O2 route targets `0:<VNI>`, O4 anycast gateway MAC (phase 2) | Aviz (ONES development build) |
| BMaaS runs the contract attachment tasks | [OSAC-1437](https://redhat.atlassian.net/browse/OSAC-1437) |
| `security_group_physical_noop` support and NetworkClass status | OSAC networking (contract OSAC-1433) |
| Role moved into `aviz.ones`, Subnet address plan, one-Subnet check, DHCP range plan | ONES Fabric Manager implementation (this feature) |

| ID | Scenario | Tier | Priority | Status |
|----|----------|------|----------|--------|
| TC-R1-01 | Documented registration and the role's task files | Unit (playbook) | high | Gap |
| TC-R1-02 | A bad setting is retryable and named | per row | high | Covered |
| TC-R1-03 | TLS settings | Unit (playbook) | medium | Gap |
| TC-R2-01 | VirtualNetwork becomes an ONES tenant and returns its L3 VNI | per row | critical | Covered |
| TC-R2-02 | Network type and VNI checks | Unit (osac-aap) | high | Covered |
| TC-R2-03 | Two tenants keep their servers apart | Live | critical | Covered |
| TC-R2-04 | Two VirtualNetworks with the same CIDR are isolated | Live | critical | Blocked |
| TC-R2-05 | VNIs stay fixed and are freed on delete | Live | high | Covered |
| TC-R3-01 | Subnet returns the tenant's L2 VNI | Unit (playbook) | critical | Covered |
| TC-R3-02 | Subnet sets the tenant address plan, and a rerun restores it | per row | critical | Blocked |
| TC-R3-03 | A second Subnet in one VirtualNetwork fails as final | Unit (playbook) | high | Gap |
| TC-R3-04 | Subnet waits for its tenant and refuses a foreign one | Unit (playbook) | high | Covered |
| TC-R3-05 | DHCP pool plan | Unit (osac-aap) | high | Gap |
| TC-R4-01 | VM and bare metal on one Subnet reach each other | E2E | critical | Deferred |
| TC-R4-02 | Stand-in hub node reaches a GPU server over EVPN | Live | critical | Deferred |
| TC-R4-03 | One gateway MAC for VMs and bare metal | Live | high | Deferred |
| TC-R5-01 | Physical apply moves the server from the provisioning tenant | per row | critical | Covered |
| TC-R5-02 | Physical apply rejections | per row | high | Covered |
| TC-R5-03 | Lease query returns the server's address | Unit (playbook) | critical | Covered |
| TC-R5-04 | The lease lies in the Subnet's physical range | Live | critical | Blocked |
| TC-R5-05 | Delete returns the server to the provisioning tenant | per row | critical | Covered |
| TC-R5-06 | Several servers in one tenant, and a move between tenants | Live | high | Covered |
| TC-R5-07 | BareMetalInstance on an ONES Subnet end to end | E2E | critical | Blocked |
| TC-R6-01 | Tenants and servers that are not OSAC's are refused | per row | critical | Covered |
| TC-R7-01 | VirtualNetwork delete with an attached server retries and completes | Unit (playbook) | high | Covered |
| TC-R7-02 | Error classification and sanitized messages | per row | high | Covered |
| TC-R7-03 | A job killed midway is completed by its rerun | Live | high | Covered |
| TC-R7-04 | A wait timeout is retryable and the rerun continues | Live | high | Covered |
| TC-R7-05 | Concurrent jobs on one tenant | Live | medium | Covered |
| TC-R8-01 | SecurityGroup, overlay and Subnet delete tasks send no write | per row | high | Covered |
| TC-R8-02 | Unsupported tasks fail as final | per row | high | Covered |
| TC-R8-03 | Physical apply ignores `security_group_ids` | Unit (playbook) | medium | Gap |
| TC-R9-01 | Timing baseline and many tenants | Live | medium | Covered |
| TC-R9-02 | Conformance profiles on the ONES lab | E2E | high | Blocked |

## Test Cases

### R1: Installation from OSAC's release

#### TC-R1-01: Documented registration and the role's task files

**Steps:** 1. Load the registration ConfigMap from the installation guide → 2. List the task files of `aviz.ones.fabric_manager` in the vendored collection.
**Expected:** Step 1: immutable, labelled `osac.openshift.io/network-fabric-manager: "true"`, with `name: ones`, `ansible_role: aviz.ones.fabric_manager`, `capabilities: security_group_icmp,security_group_physical_noop`, and no `network_types` (phase 1). Step 2: a task file for every Fabric task of the contract. Proposed: `test_ones_playbook.py` `test_registration_and_task_files`.

#### TC-R1-02: A bad setting is retryable and named (parameterized)

Every row: `osac_error.retryable: true`, a message starting "Missing or malformed setting in network-fulfillment-ig" that names the variable, no ONES request.

| Setting | Tier | Existing |
|---|---|---|
| `ONES_URL`, `ONES_FABRIC` or `ONES_PASSWORD` unset | Unit (playbook) | `test_missing_settings_are_retryable` |
| `ONES_URL` without an `http`/`https` scheme; `ONES_WAIT_TIMEOUT` `0`; `ONES_FABRIC` with a space | Unit (osac-aap) | `test_settings_error` |
| Settings missing on a real job | Live | RS-09 |

#### TC-R1-03: TLS settings (parameterized)

| Input | Expected Result |
|---|---|
| `ONES_VALIDATE_CERTS` unset or `"unexpected"` | TLS verification on |
| `ONES_VALIDATE_CERTS: "false"` | TLS verification off |
| `ONES_CA_PATH` to the fake ONES CA with verification on | the task succeeds over TLS |

### R2: VirtualNetwork isolation

#### TC-R2-01: VirtualNetwork becomes an ONES tenant and returns its L3 VNI (parameterized)

| Case | Expected Result | Tier |
|---|---|---|
| Without network type (phase 1) | tenant `osac<8 hex>` with marker `osac-vn:<id>`, no servers; result has `backend_id` (string) only | Unit (playbook) |
| Rerun | same result, no write | Unit (playbook) |
| With `network_type: evpn` (phase 2 path) | result also has `l3_vni` = the tenant's `nsVniId` (integer) | Unit (playbook) |
| On a real ONES | the tenant reaches `config_status` PASS | Live |

Existing: `test_create_virtual_network_creates_the_tenant_without_servers`, `test_create_virtual_network_rerun_writes_nothing`, `test_create_virtual_network_evpn_returns_the_vrf_vni`; live MT-01.

#### TC-R2-02: Network type and VNI checks (parameterized)

| Condition | Expected Result |
|---|---|
| `network_type: vlan` | final, "ONES supports network type evpn only" |
| `nsVniId` or `vlanVniId` missing | retryable |
| VNI 0, above 16777215, a bool, or not an integer | final |
| `l2_vni` equal to `l3_vni` | final |

Existing: `test_network_type_evpn_or_none`, `test_tenant_vnis`, `test_unknown_network_type_is_final`, `test_result_shape_and_unknown_keys`.

#### TC-R2-03: Two tenants keep their servers apart

**Steps:** 1. Create two VirtualNetworks, each with one server → 2. Attach the server of the first to the second.
**Expected:** Each tenant holds only its server; step 2 is final and leaves both tenants unchanged and PASS. Existing: live MT-02, MT-03.

#### TC-R2-04: Two VirtualNetworks with the same CIDR are isolated

**Steps:** 1. Create two VirtualNetworks with the same CIDR, each with a bare-metal server → 2. Ping and arping from each server to the other network's addresses.
**Expected:** No reply either way; each server gets its lease from its own tenant's pool. Blocked by O5.

#### TC-R2-05: VNIs stay fixed and are freed on delete

**Steps:** 1. Create a VirtualNetwork and read its VNIs → 2. Rerun the create → 3. Delete it and create new VirtualNetworks.
**Expected:** Step 2 returns the same VNIs; after step 3 ONES reuses the freed VLAN and VNIs, never two live tenants with one VNI. Existing: live SC-03.

### R3: Subnet on the tenant

#### TC-R3-01: Subnet returns the tenant's L2 VNI (phase 2 path)

**Steps:** 1. Run `create_virtual_network`, then `create_subnet` with `network_type: evpn` → 2. Rerun `create_subnet`.
**Expected:** Both runs return `network_segment: {type: evpn, l2_vni: <vlanVniId>}`, exactly those keys, `l2_vni` an integer. Without a network type (phase 1) the result has no segment. Existing: `test_create_subnet_evpn_returns_the_vlan_vni`.

#### TC-R3-02: Subnet sets the tenant address plan, and a rerun restores it (parameterized)

| Case | Expected Result | Tier |
|---|---|---|
| `create_subnet` for `10.0.1.0/24`, gateway `10.0.1.1`, physical range `10.0.1.192/26` | Get Tenant reports subnet `10.0.1.0/24`, gateway `10.0.1.1`, DHCP pool `10.0.1.192`–`10.0.1.254` | Unit (playbook), Live |
| Plan changed in ONES, then rerun | one update restores the plan | Unit (playbook) |
| Plan differs and ONES refuses the change (servers attached) | final, names the Subnet CIDR | Unit (playbook) |

Blocked by O3. The anycast gateway MAC (O4) is checked in phase 2 (TC-R4-03).

#### TC-R3-03: A second Subnet in one VirtualNetwork fails as final

**Steps:** 1. Run `create_subnet` for Subnet A of a VirtualNetwork → 2. Run it for Subnet B of the same VirtualNetwork → 3. Rerun it for A.
**Expected:** Step 2 is final, "ONES gives a VirtualNetwork one Subnet", no write; step 3 succeeds with the same segment.

#### TC-R3-04: Subnet waits for its tenant and refuses a foreign one

| Condition | Expected Result |
|---|---|
| Tenant not created yet | retryable, "the VirtualNetwork must be created first" |
| Tenant with the name but without the owner marker | final; no write |

Existing: `test_create_subnet_waits_for_the_tenant`, `test_create_subnet_refuses_a_foreign_tenant`.

#### TC-R3-05: DHCP pool plan (parameterized)

| Subnet | Expected plan |
|---|---|
| Gateway outside the physical range | pool over the physical range |
| Gateway inside the physical range | pool starts at the address after the gateway |
| Physical range ends the Subnet | pool ends one address before broadcast |
| Empty `physical_ipv4_cidrs` | no pool, no error |

### R4: VMs and bare metal on one Subnet (phase 2, deferred)

These cases run with the phase 2 design; they are kept here so the stand-in
hub node work already done is not lost.

#### TC-R4-01: VM and bare metal on one Subnet reach each other

**Steps:** 1. Create a VM and a BareMetalInstance on one ONES Subnet → 2. Ping and TCP connect each from the other → 3. Ping the gateway from both.
**Expected:** Replies and connections both ways; the gateway answers both. Needs O1, O2, O4 and OSAC-1437.

#### TC-R4-02: Stand-in hub node reaches a GPU server over EVPN

**Steps:** 1. Run the role's `create_virtual_network` and `create_subnet` with `network_type: evpn` against ONES and attach a GPU server → 2. Configure a Linux host on a compute leaf as the hub node: FRR BGP EVPN and the VRF, bridge and VXLAN devices built from `cudn_evpn`'s plan for the same task input, with a network namespace as the VM → 3. Ping the GPU server from the namespace.
**Expected:** The EVPN sessions to both leaves are up; the host imports the tenant's type-2 and type-5 routes with route targets `0:<l2_vni>` and `0:<l3_vni>`; the ping gets replies. Needs O1 and O2.

#### TC-R4-03: One gateway MAC for VMs and bare metal

**Steps:** 1. On the setup of TC-R4-02, read the gateway's ARP entry on the GPU server and in the namespace.
**Expected:** Both show `0a:58` followed by the gateway's four bytes. Needs O4.

### R5: Bare-metal addresses

#### TC-R5-01: Physical apply moves the server from the provisioning tenant (parameterized)

| Case | Expected Result | Tier |
|---|---|---|
| Server in the provisioning tenant | server leaves it and joins the VirtualNetwork's tenant; the tenant reaches PASS | Unit (playbook), Live |
| Rerun | no write | Unit (playbook) |

Existing: `test_physical_attachment_moves_the_host_from_provisioning`; live MT-07.

#### TC-R5-02: Physical apply rejections (parameterized)

| Condition | Expected Result | Existing |
|---|---|---|
| Tenant not created yet | retryable | `test_physical_attachment_waits_for_the_tenant`; live RS-12 |
| Server in another tenant | final; no write | `test_physical_attachment_refuses_a_host_of_another_tenant`; live MT-03 |
| Server not in the ONES topology | final | `test_physical_attachment_of_an_unknown_host_is_final`; live RS-12 |
| Invalid attachment input | final | `test_invalid_attachment_input_is_final` |
| Empty `physical_ipv4_cidrs` | final, "no fabric address range for bare-metal DHCP"; no write | Gap |

#### TC-R5-03: Lease query returns the server's address (parameterized)

| ONES IPAM state | Expected Result |
|---|---|
| Address for the server | `dhcp_lease: {ip_address: <address>, mac_address: <input MAC>}` |
| Address reported for another MAC | retryable |

Existing: `test_query_dhcp_lease_returns_the_ones_address`, `test_query_dhcp_lease_with_another_mac_is_retryable`.

#### TC-R5-04: The lease lies in the Subnet's physical range

**Steps:** 1. Create a Subnet with a physical range → 2. Attach a server and query its lease → 3. Read the address on the server.
**Expected:** The lease and the server's address are the same address, inside `physical_ipv4_cidrs`. Blocked by O3.

#### TC-R5-05: Delete returns the server to the provisioning tenant (parameterized)

| Case | Expected Result | Tier |
|---|---|---|
| Full lifecycle: create, attach, lease, detach, delete | server back in the provisioning tenant; tenant deleted | Unit (playbook) |
| Detach one of two servers; detach the last | the tenant keeps the other server, then none, and stays PASS | Live |
| Detach a server that is already gone | success, no write | Unit (playbook) |

Existing: `test_full_lifecycle_returns_the_host_to_provisioning`; live MT-05, MT-06, MT-07.

#### TC-R5-06: Several servers in one tenant, and a move between tenants

**Steps:** 1. Attach two servers to one VirtualNetwork → 2. Detach one and attach it to a second VirtualNetwork.
**Expected:** Step 1: both servers in the tenant, PASS. Step 2: the first tenant keeps one server, the second holds the moved one, both PASS. Existing: live MT-01, MT-04.

#### TC-R5-07: BareMetalInstance on an ONES Subnet end to end

**Steps:** 1. Order a BareMetalInstance on an ONES Subnet → 2. Release it.
**Expected:** The instance shows its address from the Subnet's physical range and answers on it; after release the server is in the provisioning tenant. Blocked by OSAC-1437 and O3.

### R6: Ownership

#### TC-R6-01: Tenants and servers that are not OSAC's are refused (parameterized)

| Object | Expected Result | Existing |
|---|---|---|
| Tenant with an OSAC name and no marker, on create | final; no write | `test_create_virtual_network_refuses_a_foreign_tenant_with_the_name`; live MT-08 |
| The same tenant, on delete | final; tenant kept | `test_delete_virtual_network_never_deletes_a_foreign_tenant`; live MT-08 |
| Two VirtualNetwork IDs with the same first 8 hex digits | the second create is final; the first tenant is unchanged | live SC-04 |

### R7: Failure visibility and recovery

#### TC-R7-01: VirtualNetwork delete with an attached server retries and completes

**Steps:** 1. Delete a VirtualNetwork whose tenant holds a server → 2. Detach the server and rerun → 3. Delete again.
**Expected:** Step 1 retryable, tenant kept; step 2 deletes the tenant; step 3 succeeds with no write. Existing: `test_delete_virtual_network_with_attached_host_is_retryable`, `test_delete_virtual_network_deletes_ours_and_tolerates_absent`.

#### TC-R7-02: Error classification and sanitized messages (parameterized)

| Fault | Expected Result | Existing |
|---|---|---|
| ONES unreachable | retryable | `test_unreachable_ones_is_retryable`; live RS-01 |
| Wrong password | retryable; the password is not in the message | `test_wrong_password_is_retryable_and_not_echoed` |
| Token invalidated mid-job | the client logs in once more and the task succeeds | `test_expired_token_is_refreshed_by_login`, `test_client_relogs_once_on_401`; live RS-02 |
| ONES operation fails | retryable | `test_failed_operation_is_retryable` |
| ONES validation error (400) | final | `test_ones_validation_error_is_final` |
| HTML from the gateway for a direct route | error naming `ONES_FM_DIRECT_URL` | `test_gateway_html_for_a_direct_route_is_an_error` |

Every message carries the step name and no response body, token or password (`test_client_error_message_has_no_secrets`).

#### TC-R7-03: A job killed midway is completed by its rerun

**Steps:** 1. Kill the job during `create_virtual_network` → 2. Rerun → 3. Kill the job during the physical apply → 4. Rerun.
**Expected:** Each rerun finds the tenant or the running ONES operation and ends with one tenant and the server attached, PASS. Existing: live RS-03, RS-04.

#### TC-R7-04: A wait timeout is retryable and the rerun continues

**Steps:** 1. Run the physical apply with a short `ONES_WAIT_TIMEOUT` → 2. Rerun with the default.
**Expected:** Step 1 retryable with a timeout message; step 2 completes the same attachment. Existing: live RS-07; `test_client_wait_config_times_out_as_retryable`.

#### TC-R7-05: Concurrent jobs on one tenant

**Steps:** 1. Start two physical applies for two servers on one tenant at once.
**Expected:** Both end with their server in the tenant; a 409 from ONES is retryable and its rerun succeeds. Existing: live RS-10.

### R8: Documented no-ops and unsupported tasks

#### TC-R8-01: SecurityGroup, overlay and Subnet delete tasks send no write (parameterized)

**Steps:** 1. Run `create_security_group`, `delete_security_group`, `delete_subnet`, and the overlay `apply_network_attachment` and `delete_network_attachment`.
**Expected:** Each succeeds with no ONES write. Existing: `test_no_op_tasks_touch_nothing`, `test_overlay_attachment_is_a_no_op`; live E2E-08.

#### TC-R8-02: Unsupported tasks fail as final (parameterized)

**Steps:** 1. Run `create_external_ip_pool`, `create_external_ip`, `attach_external_ip`, `create_nat_gateway` and `create_fabric_domain`.
**Expected:** Each fails `retryable: false`, "The ONES fabric manager does not support <task>", with no ONES request. In phase 2 the external address and NAT tasks move to the Aviz Gateway API and get their own cases. Existing: `test_unsupported_tasks_fail_as_final`; live E2E-08.

#### TC-R8-03: Physical apply ignores `security_group_ids`

**Steps:** 1. Run the physical apply with `security_group_ids: [<id>]` → 2. Compare with a run with `[]`.
**Expected:** Same requests and result.

### R9: Scale and conformance

#### TC-R9-01: Timing baseline and many tenants

**Steps:** 1. Time each task of one tenant lifecycle with one server → 2. Create and delete many tenants in sequence.
**Expected:** Every task ends within `ONES_WAIT_TIMEOUT`; on the virtual lab a tenant create takes about 10 seconds and a server move about 50 seconds; every tenant is deleted and no VLAN or VNI leaks. Existing: live SC-01, SC-02.

#### TC-R9-02: Conformance profiles on the ONES lab

**Steps:** 1. Run the contract conformance suite (§4.11) with ONES as the Fabric Manager and no Kubernetes Manager.
**Expected:** `baremetal` conformant, with the blocked-port check skipped as the documented SecurityGroup no-op and the external address checks skipped as unsupported in phase 1. Blocked by O3, O5, OSAC-1437 and OSAC support for `security_group_physical_noop`. The `vm` profile runs in phase 2.

## Summary

| Status | Cases |
|---|---|
| Covered | 21 |
| Gap | 5 |
| Blocked | 5 |
| Deferred (phase 2) | 3 |

| Priority (phase 1 cases) | Cases |
|---|---|
| critical | 11 |
| high | 16 |
| medium | 4 |
