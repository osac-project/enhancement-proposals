# Test Plan — BMaaS Networking

## Overview

- **Feature:** OSAC-1437 — BMaaS Networking.
- **Total test cases:** 13
- **Requirements covered:** 7 of 15 OSAC-1437 FR/NFRs. This plan covers attachment validation, selected-port identity, network handoff, address discovery, cleanup, disabled networking, and connectivity timing.
- **Interface changes covered:** 4 of 4

## Test Case Index

| ID | Scenario | IC | Priority |
|---|---|---|---|
| TC-FR1-01 | Reject more than one attachment | IC-1 | high |
| TC-FR3-01 | Reject invalid or non-tenant interface | IC-1 | high |
| TC-FR7-01 | Move selected port, power-cycle, then discover lease | IC-2, IC-3 | high |
| TC-FR7-02 | Wait for provider move readiness before handoff | IC-3 | medium |
| TC-FR7-03 | Verify tenant handoff in deployed BMaaS | IC-3 | high |
| TC-FR8-01 | Report lease for selected MAC and saved network | IC-3 | high |
| TC-FR8-02 | Ignore leases for a different MAC | IC-3 | high |
| TC-FR12-01 | Delete owned attachment and release tenant connectivity | IC-4 | critical |
| TC-FR12-02 | Retain repair mark and allocation hold on uncertain cleanup | IC-4 | critical |
| TC-FR12-03 | Preserve unrelated attachments and retry cleanup | IC-4 | critical |
| TC-FR12-04 | Verify tenant port cleanup in deployed BMaaS | IC-4 | critical |
| TC-FR13-01 | Preserve disabled-networking provisioning behavior | IC-3 | high |
| TC-NFR2-01 | Meet the two-minute connectivity target | IC-3 | high |

## Test Cases

### FR-1: At most one attachment

#### TC-FR1-01: Reject more than one attachment

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1 | high | automated |

**Preconditions:** The request otherwise has a valid BMI type and network attachment.

**Steps:**

1. Submit a BMI create request with two network attachments.
2. Read the BMI list for the tenant.

**Expected Results:** Fulfillment returns `INVALID_ARGUMENT` with the at-most-one validation message and stores no BMI.
**Evidence:** DEV unit; run `ginkgo run --timeout 10m internal/servers` from `fulfillment-service/`; API validation is real and persistence is stubbed. Evidence lane E1.

### FR-3: Validate the selected interface

#### TC-FR3-01: Reject invalid or non-tenant interface

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1 | high | automated |

**Preconditions:** The catalog type has at least one fabric port.

**Steps:**

1. Submit a BMI request with an interface absent from the type's port catalog.
2. Submit a BMI request with a system-only/non-fabric interface.
3. Check the API response and verify no BMI CR was created for either request.

**Expected Results:** Both requests fail with `INVALID_ARGUMENT` before a BMI CR or provider operation is created.
**Evidence:** DEV unit; run `ginkgo run --timeout 10m internal/servers` from `fulfillment-service/` and `make test` from `bare-metal-fulfillment-operator/`; production validation/selection code is real and catalogs/inventory are fixtures. Evidence lanes E1 and E2.

### FR-7: Configure connectivity after provisioning

#### TC-FR7-01: Move selected port, power-cycle, then discover lease

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2, IC-3 | high | automated |

##### Preconditions

- The selected interface resolves to a valid MAC.
- OS provisioning has completed and the deployment-provided provisioning network is available.

##### Steps

1. Reconcile the BMI through network setup and handoff.
2. Observe the shared networking request, management power API calls, and final BMI status.

##### Expected Results

- The shared networking controller receives one move for the selected logical port from provisioning to tenant network.
- BMF calls `SetPowerState(OFF)`, observes `OFF`, calls `SetPowerState(ON)`, and observes `ON` before lease discovery starts.
- The tenant status reaches `NETWORK_READY` only after a selected-MAC lease is reported.

**Evidence:** BM-DEV-01 unit and BM-DEV-02 Envtest; `make test` in `bare-metal-fulfillment-operator/`; real reconciliation and Kubernetes persistence with inventory, management, and provider transitions faked. Evidence lane E2.

#### TC-FR7-02: Wait for provider move readiness before handoff

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3 | medium | automated |

**Preconditions:** A BMI has completed OS provisioning and has a NetworkAttachment with an `apply_network_attachment` job in progress.

**Steps:**

1. Reconcile the BMI repeatedly while the NetworkAttachment remains not Ready.
2. Mark the NetworkAttachment Ready and reconcile the BMI again.

**Expected Results:** While the attachment is pending, BMF does not start the handoff or lease discovery. After Ready, BMF starts exactly one OFF/ON handoff sequence.
**Evidence:** BM-DEV-01 unit and BM-DEV-02 Envtest; `make test` in `bare-metal-fulfillment-operator/`; provider response is faked. Confirm real AAP/provider retry semantics under OSAC-4843 where needed. Evidence lanes E2 and E4.

#### TC-FR7-03: Verify tenant handoff in deployed BMaaS

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3 | high | automated |

**Preconditions:** The deployed BMaaS test environment has an available BMH, Netris fabric, tenant subnet, and tenant DHCP.

**Steps:**

1. Create a BMI with one selected interface.
2. Wait for the BMI to reach network readiness and read its tenant IP from Fulfillment.
3. Inspect the selected port's fabric placement and lease.

**Expected Results:** The selected fabric port is on the tenant network after the handoff power cycle, and the address visible in Fulfillment matches the lease for that port on the tenant network.
**Evidence:** Proposed QE extension to `tests/e2e/networking/bmaas/test_bmaas_networking.py`; run `uv run pytest -n 0 -m 'requires_netris and requires_netris_bmaas' tests/e2e/networking/bmaas`. Requires Netris BMaaS services, BMH SSH endpoints, `OSAC_BMI_NETWORK_INTERFACE`, fabric, and tenant DHCP. OSAC, BMC, fabric, DHCP, and status feedback run for real; no provider fakes. Evidence lane E5.

### FR-8: Expose the selected attachment address

#### TC-FR8-01: Report lease for selected MAC and saved network

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3 | high | automated |

**Preconditions:** The BMI handoff is complete, and the selected interface's MAC and tenant network are stored in the NetworkAttachment.

**Steps:**

1. Return a DHCP lease for the selected MAC in the saved tenant network context.
2. Reconcile the NetworkAttachment and BMI feedback.

**Expected Results:** The BMI attachment status contains that lease address and Fulfillment exposes the same address to the tenant.
**Evidence:** BM-DEV-01 unit and BM-DEV-02 Envtest; run `ginkgo run --timeout 20m internal/controllers/baremetalinstance` from `fulfillment-service/` and `make test` from BMF; provider response is a fixture, while the Kubernetes status and service mapping code are real. Evidence lanes E1 and E2.

#### TC-FR8-02: Ignore leases for a different MAC

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3 | high | automated |

**Preconditions:** The BMI handoff is complete, and the selected interface's MAC is recorded.

**Steps:**

1. Return a DHCP lease whose MAC belongs to a different port.
2. Reconcile the NetworkAttachment and BMI feedback.

**Expected Results:** The Networking controller rejects the lease because its MAC differs from the selected interface; BMI status contains no tenant address, IP discovery fails, and Fulfillment reports `IP address discovery did not complete.`
**Evidence:** BM-DEV-01 unit and BM-DEV-02 Envtest; run `ginkgo run --timeout 20m internal/controllers/baremetalinstance` from `fulfillment-service/` and `make test` from BMF; lease records are fixtures. Evidence lanes E1 and E2.

### FR-12: Delete the attachment and release its address

#### TC-FR12-01: Delete owned attachment and release tenant connectivity

| Interface Change | Priority | Automation |
|---|---|---|
| IC-4 | critical | automated |

**Preconditions:** A Ready BMI has an attachment at its deterministic BMI-derived key and a known tenant lease.

**Steps:**

1. Delete the BMI through Fulfillment.
2. Observe BMF's power state calls, NetworkAttachment deletion, and finalizer state.
3. Observe the shared networking controller complete tenant-to-provisioning cleanup.

**Expected Results:** BMF powers off the host, and the shared networking controller cleans up the selected port. The BMI finalizer remains until cleanup succeeds or a durable repair hold is recorded before inventory release. Confirmed cleanup releases the tenant attachment/address.
**Evidence:** BM-DEV-02 Envtest, BM-DEV-03 osac-operator unit/Envtest, and BM-DEV-04 Kind; `make test` in BMF and osac-operator, then `make integration-tests` in BMF. Kubernetes lifecycle is real in Envtest/Kind; provider release is simulated. Use OSAC-4843 for provider contract evidence. Evidence lanes E2–E4.

#### TC-FR12-02: Retain repair mark and allocation hold on uncertain cleanup

| Interface Change | Priority | Automation |
|---|---|---|
| IC-4 | critical | automated |

**Preconditions:** A Ready BMI owns a host with a NetworkAttachment and inventory entry.

**Steps:**

1. Make tenant-to-provisioning cleanup return an uncertain outcome.
2. Reconcile the BMI through the repair-hold decision.
3. Attempt to allocate another BMI from the same inventory.

**Expected Results:** The repair mark is persisted before inventory release and the host is not selected for the second BMI. If the marker is unsupported or cannot be written, BMF retains inventory ownership and the BMI finalizer. The mark is cleared only after confirmed provider cleanup or the authorized repair workflow resolves the host.
**Evidence:** BM-DEV-02 Envtest persists the marker across reconciles; `make test` in BMF. Inventory/provider responses are faked. Verify the marker's real inventory contract under OSAC-4843. Evidence lanes E2 and E4.

#### TC-FR12-03: Preserve unrelated attachments and retry cleanup

| Interface Change | Priority | Automation |
|---|---|---|
| IC-4 | critical | automated |

**Preconditions:** The namespace contains the BMI attachment at its deterministic key and an unrelated/manual attachment at a different key.

**Steps:**

1. Make cleanup of the BMI attachment fail once.
2. Reconcile the delete again and allow cleanup to succeed.
3. Read both NetworkAttachments and the BMI finalizer state.

**Expected Results:** The shared cleanup helper deletes the object at the BMI-derived key; the unrelated attachment remains. The BMI finalizer remains after the first failure and is removed only after cleanup succeeds. Existing ComputeInstance cleanup results remain unchanged.
**Evidence:** BM-DEV-03 unit/Envtest and BM-DEV-04 Kind; extend `osac-operator/internal/controller/networking_contract_test.go`, `osac-operator/internal/controller/baremetalinstance_cleanup_controller_test.go`, and `osac-operator/internal/controller/computeinstance_cleanup_test.go`, plus `bare-metal-fulfillment-operator/test/integration/networking_cleanup_test.go`; run `make test` in osac-operator and `make integration-tests` in BMF. Kubernetes objects are real in Envtest/Kind; provider transitions are faked. Evidence lanes E3 and E4.

#### TC-FR12-04: Verify tenant port cleanup in deployed BMaaS

| Interface Change | Priority | Automation |
|---|---|---|
| IC-4 | critical | automated |

**Preconditions:** The deployed BMaaS test environment has a Ready BMI with a selected-MAC tenant lease.

**Steps:**

1. Delete the BMI through Fulfillment.
2. Wait for the BMI and its NetworkAttachment to disappear.
3. Inspect the selected port's network and lease state.

**Expected Results:** The tenant-to-provisioning port move is confirmed before the host is released, and the deleted BMI's NetworkAttachment no longer appears in the API; unrelated tenant resources remain.
**Evidence:** Proposed QE extension to `tests/e2e/networking/bmaas/test_bmaas_networking.py`; run `uv run pytest -n 0 -m 'requires_netris and requires_netris_bmaas' tests/e2e/networking/bmaas`. Requires Netris BMaaS services, BMH SSH endpoints, fabric, tenant DHCP, and API access. Provider movement and Kubernetes/API state are real. Evidence lane E5.

### FR-13: Provider networking disabled

#### TC-FR13-01: Preserve disabled-networking provisioning behavior

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3 | high | automated |

**Preconditions:** The OSAC deployment has provider networking disabled before installation.

**Steps:**

1. Create and reconcile a BMI with a network attachment request.
2. Wait for OS provisioning and inspect NetworkAttachment, power, and lease activity.
3. Delete the BMI and observe deprovisioning.

**Expected Results:** OS provisioning remains available; BMF submits no tenant port move, handoff power cycle, or lease query; skipped phases do not claim tenant connectivity or an IP address. Delete deprovisions without power-off or NetworkAttachment cleanup.
**Evidence:** BM-DEV-02 Envtest and BM-DEV-04 Kind; `make test` and `make integration-tests` in `bare-metal-fulfillment-operator/`; API server/operator wiring is real in Kind and provider calls are observed through fakes. Evidence lanes E2 and E3.

### NFR-2: Connectivity completes within two minutes

#### TC-NFR2-01: Meet the two-minute connectivity target

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3 | high | automated |

##### Preconditions

- Run against the Netris BMaaS profile with live BMH, fabric, and tenant DHCP; provider outcomes are not faked.

##### Steps

1. Start a monotonic timer when the BMI reports `ProvisionTemplateComplete=True`.
2. Wait for the deployed Fulfillment API to expose the selected attachment IP and `NETWORK_READY` status.
3. Stop the timer and compare the elapsed time with the 120-second bound.

##### Expected Results

- The selected attachment address is visible to the tenant no later than 120 seconds after `ProvisionTemplateComplete=True`.

**Evidence:** QE deployed E2E; collect with `uv run pytest --collect-only -m 'requires_netris and requires_netris_bmaas' tests/e2e/networking/bmaas`, then run `uv run pytest -n 0 -m 'requires_netris and requires_netris_bmaas' tests/e2e/networking/bmaas`. Requires the Netris BMaaS services, BMH SSH endpoints, `OSAC_BMI_NETWORK_INTERFACE`, and fabric/DHCP integration. Fabric and DHCP are real; test fixtures are not used for provider outcomes. Current PR checks that disable shared networking do not satisfy this case.

## Evidence Lanes

| Lane | Owner | Tier / boundary | Suite and command | Prerequisites | Real vs. simulated |
|---|---|---|---|---|---|
| E1 | DEV — Fulfillment | Unit / service validation and status mapping | From `fulfillment-service/`: `ginkgo run --timeout 10m internal/servers` for validation and `ginkgo run --timeout 20m internal/controllers/baremetalinstance` for status mapping. If proto sources change, from repo root run `make -C proto generate` then `make -C proto lint`. | Repository dependencies and pinned proto toolchain | Fulfillment validation/mapping code real; persistence and downstream CR state use test doubles where applicable |
| E2 | DEV — BMF | Unit + Envtest / controller and Kubernetes persistence | `make test` from `bare-metal-fulfillment-operator/`; extend `internal/controller/baremetalinstance_networking_test.go`, `baremetalinstance_ip_discovery_test.go`, and `baremetalinstance_metal3_envtest_test.go` | Envtest assets required by the component | Reconciler and API server/etcd real; inventory, BMC, Metal3, AAP, and fabric transitions controlled by fixtures |
| E3 | DEV — osac-operator + BMF | Unit/Envtest and Kind component integration / helper ownership and deployed wiring | Extend `osac-operator/internal/controller/networking_contract_test.go`, `osac-operator/internal/controller/baremetalinstance_cleanup_controller_test.go`, and `osac-operator/internal/controller/computeinstance_cleanup_test.go`, plus `bare-metal-fulfillment-operator/test/integration/networking_cleanup_test.go`; run `make test` from `osac-operator/` and `make integration-tests` from `bare-metal-fulfillment-operator/` | A pre-existing Kind cluster for the BMF integration command | Kubernetes API/operator wiring real in Envtest/Kind; provider operations simulated |
| E4 | DEV/provider-contract owner | Contract / AAP or hardware semantics | [OSAC-4843](https://redhat.atlassian.net/browse/OSAC-4843) owns the real boundary; use its documented command and prerequisites | Contract environment and provider access are defined by OSAC-4843; confirm details with the contract owner before implementation | Real provider/AAP boundary; Envtest/Kind fixtures do not substitute |
| E5 | Proposed QE owner — BMaaS | E2E / deployed tenant workflow | Extend `tests/e2e/networking/bmaas/test_bmaas_networking.py`; collect with `uv run pytest --collect-only -m 'requires_netris and requires_netris_bmaas' tests/e2e/networking/bmaas`, then run `uv run pytest -n 0 -m 'requires_netris and requires_netris_bmaas' tests/e2e/networking/bmaas` | Netris BMaaS services, BMH SSH endpoints, `OSAC_BMI_NETWORK_INTERFACE`, fabric and tenant DHCP | Real deployed OSAC, fabric, and DHCP; no provider fakes |

Every test case maps to an evidence lane above. Before implementation work
merges, record the exact changed test files, commands, prerequisites, and
observed real/simulated boundary in the PR evidence. Assign the deployed
handoff/lease/delete journey to QE; assign the QE owner and tracking issue during
work decomposition. The test command and
prerequisites for the provider contract are owned by
[OSAC-4843](https://redhat.atlassian.net/browse/OSAC-4843); this plan does not
claim Envtest or Kind proves that boundary. Follow the component integration
testing guidance in `docs/INTEGRATION-TESTING.md`.

## Gaps

### Requirement Coverage Gaps

The following parent PRD requirements are not exercised by these lifecycle
scenarios: FR-2 (port catalog API), FR-4 (primary gateway
designation), FR-5 (attachment defaults), FR-6 (ExternalIP allocation), FR-9
(ExternalIP routing), FR-10 (provider backend selection), FR-11 (auto-created
ExternalIP cleanup), and NFR-1 (ExternalIP pool reservation timing). Existing
coverage remains with their owning implementation work.

All seven in-scope requirements have cases: FR-1, FR-3, FR-7, FR-8, FR-12,
FR-13, and NFR-2.

### Interface Change Coverage Gaps

All interface changes are exercised by at least one case.

## Summary

| Metric | Count |
|---|---:|
| Total test cases | 13 |
| Critical | 4 |
| High | 8 |
| Medium | 1 |
| Low | 0 |
| Automated | 13 |
| Manual | 0 |
| Requirements with test cases | 7 / 15 |
| Interface changes with test cases | 4 / 4 |
