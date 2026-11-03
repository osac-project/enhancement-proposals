---
title: OSAC-1437 BMaaS Networking Test Plan
last-updated: 2026-11-03
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1437
  - https://redhat.atlassian.net/browse/OSAC-6817
---

# Test Plan — OSAC-1437 BMaaS Networking

## Overview

- **Feature:** OSAC-1437 BMaaS Networking (accepted under [PR #357](https://github.com/osac-project/enhancement-proposals/pull/357))
- **Design:** [design.md](design.md)
- **PRD:** [prd.md](prd.md)
- **Shared contract tests:** [OSAC-1433 contract testplan](/enhancements/OSAC-1433-network-manager-integration-contract-networking/testplan.md) (includes TC-BM-01, TC-WORKLOAD-01)

This plan classifies BMaaS networking verification by **tier** and **owner**. It names existing suites and commands where they exist. The remaining PR #357 code is under review in [OSAC PR #2149](https://github.com/osac-project/osac/pull/2149) for [OSAC-6818](https://redhat.atlassian.net/browse/OSAC-6818); the open implementation PR is not a shipping-support claim. Real Fabric Manager + Metal3/Ironic hardware evidence is assigned to [OSAC-6820](https://redhat.atlassian.net/browse/OSAC-6820), and broader provider-contract gaps remain under [OSAC-4843](https://redhat.atlassian.net/browse/OSAC-4843).

| Tier | Meaning |
|---|---|
| Unit | Co-located Go/pytest without a cluster, or controller logic with fakes |
| Envtest | Controller tests against envtest API server/etcd |
| Component integration | Deployed Kind / installer suite with real CRDs; providers often mocked |
| Contract | Manager conformance / fixture contract (shared suite) |
| E2E | Cross-component journey; may require real hardware or lab |

| Owner | Meaning |
|---|---|
| [DEV] | Implementation story coverage (Unit/Envtest/component-integration) |
| [QE] | Deployed BM lifecycle / real-pair journeys |

## Classification matrix

| ID | Behavior and boundary | PRD requirement(s) | Tier | Owner | Suite / command (working directory and prerequisites) | Real vs simulated | Gap / follow-up |
|---|---|---|---|---|---|---|---|
| BM-DEV-01 | Selected-port MAC parsing and normalization; inventory repair-mark helpers | FR-7, FR-8, FR-12 | Unit | [DEV] [OSAC-6818](https://redhat.atlassian.net/browse/OSAC-6818) | `bare-metal-fulfillment-operator/internal/inventory/network_ports_test.go` and `bare-metal-fulfillment-operator/internal/inventory/repair_test.go`; run `go test ./internal/inventory` from `bare-metal-fulfillment-operator/` | Inventory parsing, validation, and repair-mark helpers are real; no Kubernetes API or manager job is exercised | The base-branch `buildSubnetMACMap` unit cases are in `bare-metal-fulfillment-operator/internal/controller/baremetalinstance_ip_discovery_test.go`. The MAC-only discovery path no longer uses name-based matching, so those cases do not verify it |
| BM-DEV-02 | BMF networking, IP-discovery, and repair-mark reconciliation; retry, status, and finalizer behavior | FR-7, FR-8, FR-11, FR-12, FR-13, NFR-2 | Envtest | [DEV] [OSAC-6818](https://redhat.atlassian.net/browse/OSAC-6818) | `bare-metal-fulfillment-operator/internal/controller/baremetalinstance_networking_test.go`, `bare-metal-fulfillment-operator/internal/controller/baremetalinstance_ip_discovery_test.go` (reconcile/apply cases), `bare-metal-fulfillment-operator/internal/controller/baremetalinstance_repair_test.go`, `bare-metal-fulfillment-operator/internal/controller/baremetalinstance_metal3_envtest_test.go`, and `bare-metal-fulfillment-operator/internal/controller/baremetalinstance_bcm_envtest_test.go`; run `make test` from `bare-metal-fulfillment-operator/` | Envtest API server/etcd and OSAC CRDs are real; AAP jobs, BMC, Metal3 hardware, and provider transitions use test fixtures | Does not prove real AAP/provider or hardware semantics; see BM-DEV-05 and BM-QE-01 |
| BM-DEV-03 | Fulfillment API create validation, primary normalization, and network-status projection | FR-1, FR-3, FR-4, FR-7, FR-13 | Unit | [DEV] [OSAC-6818](https://redhat.atlassian.net/browse/OSAC-6818) | `fulfillment-service/internal/servers/private_baremetal_instances_server_test.go` and `fulfillment-service/internal/controllers/baremetalinstance/baremetalinstance_reconciler_function_test.go`; run `go test ./internal/servers ./internal/controllers/baremetalinstance -timeout 20m` from `fulfillment-service/` | Co-located Fulfillment suites exercise service logic and a real PostgreSQL test database; Kubernetes and provider transitions are fixtures | No deployed Fulfillment service, OSAC CRDs, BMF operator, or provider boundary is exercised |
| BM-DEV-04 | Deployed BMF CRD/controller cleanup wiring and ownership | FR-11, FR-12 | Component integration | [DEV] [OSAC-6818](https://redhat.atlassian.net/browse/OSAC-6818) | `bare-metal-fulfillment-operator/test/integration/networking_cleanup_test.go`; from the OSAC monorepo root, run `make -C osac-installer install-infra PLATFORM=kind PROFILE=dev NS=osac` to create the Kind cluster, then `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=bmf` to deploy BMF and run its integration suite; see the [OSAC integration-testing guide](https://github.com/osac-project/osac/blob/main/docs/INTEGRATION-TESTING.md#bare-metal-fulfillment-operator). For a focused rerun on a ready cluster, run `make integration-tests` from `bare-metal-fulfillment-operator/` | Kind API/operator and CRDs are real; external provider transitions are simulated | Does not prove a real port move, DHCP lease, or hardware cleanup |
| BM-DEV-05 | Provider contract and real AAP, Fabric Manager, or hardware semantics | FR-7, FR-8, FR-12 | Contract | [DEV] [OSAC-4843](https://redhat.atlassian.net/browse/OSAC-4843) | No qualifying real-provider suite is currently identified | Requires real AAP/provider or hardware when the boundary is in scope | Coverage gap: keep provider-pair semantics under OSAC-4843; deployed BM lifecycle evidence is [OSAC-6820](https://redhat.atlassian.net/browse/OSAC-6820) |
| BM-DEV-06 | BareMetalInstanceType lists named ports and roles; attachment defaults to the first eligible fabric port and primary route | FR-2, FR-4, FR-5 | Component integration | [DEV] Existing API coverage | `fulfillment-service/it/it_private_baremetal_instance_types_test.go` and `fulfillment-service/internal/servers/private_baremetal_instances_server_test.go`; run `ginkgo run --timeout 20m --focus 'Can list bare metal instance types' it` against a deployed Fulfillment service, and `go test ./internal/servers -timeout 20m` from `fulfillment-service/` | Deployed listing uses the Fulfillment API; server validation uses PostgreSQL and fixtures | Confirm the type listing assertion covers both a `fabric` port and a system-only port; add an assertion if absent |
| BM-DEV-07 | ExternalIPAttachment targets a Ready BMI and uses its primary tenant address | FR-6, FR-9, FR-11 | Unit | [DEV] [OSAC-6818](https://redhat.atlassian.net/browse/OSAC-6818) | `osac-operator/internal/controller/externalipattachment_contract_test.go` and `fulfillment-service/internal/controllers/autoexternalipattachment/auto_external_ip_attachment_reconciler_function_test.go`; run `make test` from `osac-operator/` and `ginkgo run -r internal/controllers/autoexternalipattachment` from `fulfillment-service/` | Controller clients and API responses use test doubles; external provider and inbound traffic are not exercised | Does not prove deployed ExternalIP routing or cleanup; see BM-QE-01 |
| BM-QE-01 | Deployed BMI lifecycle: port move, handoff reboot, DHCP by MAC, tenant address, retry, and delete | FR-7, FR-8, FR-12, NFR-2 | E2E | [QE] [OSAC-6820](https://redhat.atlassian.net/browse/OSAC-6820) | From the OSAC repository root: `uv run pytest -n 0 tests/e2e/networking/bmaas/test_bmaas_networking.py`; requires a configured Netris BMaaS lab, BMH SSH endpoints, and `OSAC_BMI_NETWORK_INTERFACE` | Deployed OSAC, Netris, and bare-metal hosts are real | Not claimed passing until the owning QE evidence is recorded |
| BM-QE-02 | Cross-tenant BMaaS networking isolation | FR-7, FR-14 | E2E | [QE] [OSAC-6820](https://redhat.atlassian.net/browse/OSAC-6820) | Run `uv run pytest -n 0 tests/e2e/networking/bmaas/test_cross_tenant_bmaas_networking.py` from repository root; requires provider-backed tenants and hosts | Real provider-backed tenants and hosts | Tenant-labelled fixtures are not real isolation evidence |
| BM-QE-03 | Shared BMI/ComputeInstance Subnet behavior | FR-1, FR-7 | E2E | [QE] [OSAC-6820](https://redhat.atlassian.net/browse/OSAC-6820) | From repository root: `uv run pytest -n 0 -m requires_stretched_networking tests/e2e/networking/stretched`; requires the full-ci profile, BMaaS SSH access, VM template, and CUDN EVPN VTEP/underlay | Deployed BM and VM networking are real | Keep separate from CaaS worker coverage owned by OSAC-5688 |
| BM-QE-04 | Deployed repair-mark lifecycle on real inventory and FabricDomain state | FR-12 | E2E | [QE] [OSAC-6820](https://redhat.atlassian.net/browse/OSAC-6820) | No runnable lab suite is recorded yet | Requires real repair workflow and inventory backend | Coverage gap: do not infer from virtual BMHs or Kind |
| BM-QE-05 | Cohort measurement for servers that reach Ready with a tenant IPv4 address | NFR-1 | E2E | [QE] [OSAC-6820](https://redhat.atlassian.net/browse/OSAC-6820) | No cohort-reporting command or recorded baseline is identified | Requires deployed OSAC and provider-backed BMaaS cohort data | Coverage gap: define the observation window and numerator/denominator, then report whether the rate exceeds 95% |

The implementation PR also changes the shared status proto and installer networking values. These checks validate generated contracts and rendered configuration, not provider behavior. For proto changes, run `make -C proto generate` and `make -C proto lint`; for networking-value rendering, run `make helm-networking-test` from `osac-installer/`.

## Behavior checklist (maps to design)

Use the matrix IDs above; this list is the design coverage index.

### Unit ([DEV])

- Fulfillment: validation rules, worker `fabric_interface`, Subnet deletion while a BMI references it, and each `NETWORK_READY` mapping (BM-DEV-03).
- BMF: selected-interface MAC mapping and normalization helpers (BM-DEV-01); NetworkAttachment spec/annotation/finalizer, handoff, status/phase, deletionTimestamp guards, repair mark, and provider-networking-disabled behavior (BM-DEV-02).
- Networking controller: lease query only after handoff; selected-MAC and tenant-network context; retry cadence; wrong-MAC / invalid-lease rejection (shared manager-contract coverage; BM-DEV-02 verifies BMF consumes the resulting NetworkAttachment status).
- Fulfillment create validation, `primary: true` normalization, and `NETWORK_READY` projection (BM-DEV-03).
- ExternalIPAttachment controller readiness and primary-address selection for a BMI (BM-DEV-07).

### Integration ([DEV])

- Create/delete order and NetworkAttachment cleanup wait; final vs retryable failures; provider networking disabled (BM-DEV-04).

### E2E / Contract ([QE])

- Real manager provision/discover/delete; isolation until ready; Halted handoff; SecurityGroup failure (BM-QE-01).
- Cross-tenant isolation and shared BMI/ComputeInstance Subnet behavior (BM-QE-02, BM-QE-03).
- Deployed repair-mark evidence remains unavailable until BM-QE-04 is recorded.
- NFR-1 success-rate measurement remains unavailable until BM-QE-05 defines and records a cohort result.

## Detailed scenario checklist

These assertions expand the matrix behavior summaries. They are coverage expectations, not a claim that every named suite implements every assertion or that any run passed; use the matrix to identify each suite's boundary and follow-up owner.

### Reproducible requirement scenarios

These cases make the principal inputs and expected API/status outputs explicit. They describe required coverage; the matrix above identifies which current suites cover the boundary and where a gap remains.

1. **Physical interface discovery (FR-2).** Preconditions: a published instance type exposes `data-0` with role `fabric` and `bmc-0` with role `lifecycle`. Step: list the type through the private API. Expected: the response preserves each port name, role, type, and speed; only the `fabric` role is eligible for tenant selection. If the fixture cannot express both roles, add that assertion to BM-DEV-06.
2. **Single primary attachment (FR-4/FR-5).** Preconditions: a catalog item with the type above and a valid Subnet. Step: create one attachment with Subnet `subnet-1` and omitted `interface`/`primary`. Expected: creation succeeds, normalizes `primary` to `true`, selects the first eligible fabric port, and exposes that attachment as the sole primary route. A request with `primary: false` returns `INVALID_ARGUMENT`.
3. **External IP for a BMI (FR-9).** Preconditions: a Ready BMI has primary Subnet `subnet-1` and tenant IP `10.100.0.2`; an ExternalIP is allocated. Step: reconcile an ExternalIPAttachment targeting that BMI. Expected: destination address is `10.100.0.2`, and its routing domain resolves to the VirtualNetwork and Subnet containing `subnet-1`; before the BMI is ready or has its primary IP, no provider job starts.
4. **Selected-MAC lease discovery (FR-7/FR-8).** Preconditions: attachment interface is `data-0`, with inventory MAC `AA-BB-CC-DD-EE-FF`; `data-1` has a different address. Steps: normalize the selected MAC, complete handoff, and consume the NetworkAttachment query result. Expected: only the selected MAC's valid IPv4 lease is copied; a missing or mismatched lease leaves the tenant IP empty and reports a pending/failure status with the latest query message. No interface-name or host-name fallback may supply an address.
5. **NFR-1 cohort rate.** Preconditions: select a reporting window and all BMI create requests with provider networking enabled and OS provisioning completed in that window. Steps: count eligible requests and those reaching `Ready` with a tenant IPv4 address. Expected: report numerator, denominator, exclusions, and calculated rate; the result meets the requirement only when it is greater than 95%. BM-QE-05 tracks the currently undefined reporting window and baseline.

### Unit and Envtest ([DEV])

- **Fulfillment:** Test each network-attachment validation rule, the authorized worker `fabric_interface` path and defaults, ExternalIPAttachment endpoint readiness, Subnet deletion while a BMI references it, and each `NETWORK_READY` mapping including provider networking disabled and deletion.
- **BMF inventory and networking:** Test MAC normalization with `AA-BB-CC-DD-EE-FF` becoming `aa:bb:cc:dd:ee:ff`, malformed or unparsable maps, and selected-port matching. Assert the exact NetworkAttachment spec/annotation/finalizer and that host selection skips missing inventory names or selected-port MACs. Test backend-specific handoff confirmation and failure, including the 15-minute deadline.
- **BMF status and deletion:** Test status and phase mapping with messages and job IDs copied from NetworkAttachment `status.jobs`; BMF must not launch apply or query jobs. After deletion begins, no new NetworkAttachment, handoff reboot, RunStrategy, or `restart_trigger` update should start.
- **Repair marks:** Test each inventory backend's mark write, selection exclusion, and release ordering. A mark is required only when provider networking is enabled and the FabricDomain retains a `status.jobs` entry showing that its create job started while `spec.servers` lists the host; unsupported or failed mark writes must keep the host owned.
- **Networking controller contract:** Query only after `NetworkHandoffComplete=True`; verify the selected MAC and recorded tenant network context, retry cadence, and rejection of a wrong-MAC or invalid lease. Manager tasks remain covered by the shared contract plan.
- **Provider networking disabled and cleanup:** Verify disabled status only after `ProvisionTemplateComplete=True`, no MAC resolution or NetworkAttachment, and finalizer ordering for NetworkAttachment cleanup and feedback.

### Component integration ([DEV])

The BMaaS cleanup Kind suite in BM-DEV-04 proves deployed cleanup wiring, not a real provider move or the entire flow. Where qualifying suites are added, assert:

- Create follows the accepted lifecycle order; RunStrategy and a `restart_trigger` change made before Ready apply only after address discovery.
- Final apply/query failures set failure status; retryable query failures preserve `LeasePending` and `NetworkAttachmentsReady=True`.
- Delete follows the accepted order, keeps finalizers on cleanup failures, and releases only owned resources after cleanup.
- Automatic external access starts only when the endpoint is ready and the ExternalIP is allocated; delete stops new requests, and allocation failure does not block host readiness.
- Provider networking disabled keeps host provisioning/deprovisioning available without networking tasks, tenant address status, or a NetworkAttachment.
- Port moves and handoff reboot are idempotent, retryable, and observable before tenant DHCP discovery.

### E2E acceptance scenarios ([QE])

The QE cases are assigned to OSAC-6820; these are desired deployed assertions and are not claimed passing:

- Provision, discover, and delete a BMI on one Subnet; verify port moves from provisioning to tenant and back, and the freed host can be inspected again (BM-QE-01).
- Verify tenant reachability begins only after the port move and handoff reboot, and the host leaves the provisioning network (BM-QE-01 / BM-QE-02).
- For `RunStrategy=Halted`, verify the handoff powers on the host and discovery completes before RunStrategy applies (BM-QE-01).
- Verify automatic ExternalIP resources and inbound reachability, cleanup after delete, and that a SecurityGroup binding failure blocks readiness and traffic (BM-QE-01).
- Verify cross-tenant isolation and shared BMI/ComputeInstance Subnet behavior (BM-QE-02 / BM-QE-03).

### Explicit gaps and edge cases

- **BM-DEV-05 / OSAC-4843:** Real AAP, Fabric Manager, or hardware provider-pair semantics beyond Envtest/Kind.
- **BM-QE-04 / OSAC-6820:** Deployed repair-mark lifecycle until QE records a runnable lab path; Kind or virtual BMHs are not physical repair evidence.
- Restart at each handoff point must result in exactly one reboot; a cached BareMetalHost without BMF's annotation is not confirmation.
- Measure the handoff deadline from `NetworkAttachmentsReady=True`; a `PoweringOn` write does not reset it, and a confirmation observed after the deadline succeeds.
- Delete during apply/query cancels the job; delete during handoff removes the pending handoff and prevents another reboot.
- Reconcile after writing `networkAttachmentStatuses[0]` but before creating NetworkAttachment; a live BMI resumes creation, while a deleting BMI skips power-off when no NetworkAttachment exists.
- During delete, require a persisted repair mark before release only when a FabricDomain retains a started `create_fabric_domain` entry in `status.jobs` and lists the host in `spec.servers`; with no qualifying domain, no mark is written.
- Restart during offboarding must boot the cleaning ramdisk after ports return, never the tenant OS.

## Documentation acceptance (OSAC-6817)

| Check | Expected |
|---|---|
| Manager ownership | Docs state Fabric Manager owns Fabric ops; BMF/networking controller orchestrate without BMF calling managers |
| Lifecycle agreement | Port move, handoff, MAC lease discovery, repair, retry/delete agree across PRD/design/this testplan and cited code paths |
| Tier/owner | Every matrix row has Tier, Owner, and either a suite/command or a named follow-up |
| No false support | Remaining delta not described as currently supported product behavior |

## Non-goals

- Duplicating the full contract conformance suite (owned by the contract testplan).
- Implementing missing code coverage (OSAC-6818) or writing new deployed QE suites (OSAC-6820) in the documentation story.
- Shared NetworkClass / address-plan documentation (OSAC-6812).
