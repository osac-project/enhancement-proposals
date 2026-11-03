---
title: OSAC-1437 BMaaS Networking Test Plan
last-updated: 2026-11-02
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
| BM-DEV-01 | BMF selects and records the attachment MAC, waits for NetworkAttachment handoff, mirrors the lease for that MAC, and writes repair marks fail-closed | FR-7, FR-8, FR-12, NFR-2 | Unit | [DEV] [OSAC-6818](https://redhat.atlassian.net/browse/OSAC-6818) | `bare-metal-fulfillment-operator/internal/controller/baremetalinstance_networking_test.go`, `baremetalinstance_ip_discovery_test.go`, `baremetalinstance_repair_test.go`, and `bare-metal-fulfillment-operator/internal/inventory/network_ports_test.go` / `repair_test.go`; run `make test` from `bare-metal-fulfillment-operator/` | Controller and inventory logic are real; manager jobs and provider outcomes use fixtures | Does not prove a Fabric Manager or hardware boundary |
| BM-DEV-02 | Retry, status, finalizer, and Metal3 state persistence across controller reconciliation | FR-11, FR-12, FR-13 | Envtest | [DEV] [OSAC-6818](https://redhat.atlassian.net/browse/OSAC-6818) | `bare-metal-fulfillment-operator/internal/controller/baremetalinstance_metal3_envtest_test.go` and `baremetalinstance_bcm_envtest_test.go`; run `make test` from `bare-metal-fulfillment-operator/` | Envtest API server/etcd are real; BMC, Metal3 hardware, and Fabric provider transitions are test-controlled | Real hardware and provider-pair semantics remain under [OSAC-4843](https://redhat.atlassian.net/browse/OSAC-4843) |
| BM-DEV-03 | NetworkAttachment cleanup ownership and BMI status/validation feedback across OSAC controllers | FR-1, FR-3, FR-7, FR-10, FR-13 | Unit | [DEV] [OSAC-6818](https://redhat.atlassian.net/browse/OSAC-6818) | `osac-operator/pkg/networkattachment/delete_test.go` (`make test` from `osac-operator/`); `fulfillment-service/internal/controllers/baremetalinstance/baremetalinstance_reconciler_function_test.go` and `fulfillment-service/internal/servers/private_baremetal_instances_server_test.go` (`ginkgo run --timeout 20m -r internal` from `fulfillment-service/`) | Controller and API logic are real; Kubernetes, database, and provider transitions are test-controlled | No live manager or provider boundary in these suites |
| BM-DEV-04 | Deployed BMF CRD/controller cleanup wiring and ownership | FR-11, FR-12 | Kind component integration | [DEV] [OSAC-6818](https://redhat.atlassian.net/browse/OSAC-6818) | `bare-metal-fulfillment-operator/test/integration/networking_cleanup_test.go`; run `make integration-tests` from `bare-metal-fulfillment-operator/` against a pre-existing Kind cluster | Kind API/operator and CRDs are real; external provider transitions are simulated | Does not prove a real port move, DHCP lease, or hardware cleanup |
| BM-DEV-05 | Provider contract and real AAP, Fabric Manager, or hardware semantics | FR-7, FR-8, FR-12 | Contract gap | [DEV] [OSAC-4843](https://redhat.atlassian.net/browse/OSAC-4843) | No qualifying real-provider suite is claimed by the BMF Envtest or Kind commands | Requires real AAP/provider or hardware when the boundary is in scope | Keep unavailable semantics under OSAC-4843; deployed BM lifecycle evidence is [OSAC-6820](https://redhat.atlassian.net/browse/OSAC-6820) |
| BM-QE-01 | Deployed BMI lifecycle: port move, handoff reboot, DHCP by MAC, tenant address, retry, and delete | FR-7, FR-8, FR-12, NFR-2 | E2E | [QE] [OSAC-6820](https://redhat.atlassian.net/browse/OSAC-6820) | From repository root: `uv run pytest -n 0 -m 'requires_netris and requires_netris_bmaas' tests/e2e/networking/bmaas`; requires a configured Netris BMaaS lab, BMH SSH endpoints, and `OSAC_BMI_NETWORK_INTERFACE` | Deployed OSAC, Netris, and bare-metal hosts are real | Not claimed passing until the owning QE evidence is recorded |
| BM-QE-02 | Cross-tenant BMaaS networking isolation | FR-7, FR-14 | E2E | [QE] [OSAC-6820](https://redhat.atlassian.net/browse/OSAC-6820) | Run `uv run pytest -n 0 tests/e2e/networking/bmaas/test_cross_tenant_bmaas_networking.py` from repository root; requires provider-backed tenants and hosts | Real provider-backed tenants and hosts | Tenant-labelled fixtures are not real isolation evidence |
| BM-QE-03 | Shared BMI/ComputeInstance Subnet behavior | FR-1, FR-7 | E2E | [QE] [OSAC-6820](https://redhat.atlassian.net/browse/OSAC-6820) | From repository root: `uv run pytest -n 0 -m requires_stretched_networking tests/e2e/networking/stretched`; requires the full-ci profile, BMaaS SSH access, VM template, and CUDN EVPN VTEP/underlay | Deployed BM and VM networking are real | Keep separate from CaaS worker coverage owned by OSAC-5688 |
| BM-QE-04 | Deployed repair-mark lifecycle on real inventory and FabricDomain state | FR-12 | E2E gap | [QE] [OSAC-6820](https://redhat.atlassian.net/browse/OSAC-6820) | No runnable lab suite is recorded yet | Requires real repair workflow and inventory backend | Unavailable; do not infer from virtual BMHs or Kind |

The implementation PR also changes the shared status proto and installer networking values. These supporting checks validate generated contracts and rendered configuration, not provider behavior: run `make -C proto generate` and `make -C proto lint` for proto changes, and `make helm-networking-test` from `osac-installer/` for networking-value rendering.

## Behavior checklist (maps to design)

Use the matrix IDs above; this list is the design coverage index.

### Unit ([DEV])

- Fulfillment: validation rules; worker `fabric_interface`; ExternalIPAttachment endpoint-ready; Subnet delete while BMI references; each `NETWORK_READY` case (BM-DEV-03).
- BMF: MAC resolution per backend; NetworkAttachment spec/annotation/finalizer; handoff per backend; status/phase rows; deletionTimestamp guards; repair mark; provider networking disabled (BM-DEV-01, BM-DEV-02).
- Networking controller: lease query only after handoff; selected-MAC and tenant-network context; retry cadence; wrong-MAC / invalid-lease rejection (shared manager-contract coverage; BM-DEV-01 verifies BMF consumes the resulting NetworkAttachment status).
- Cleanup / feedback controllers: owned NetworkAttachment deletion and finalizer lifecycle (BM-DEV-03, BM-DEV-04).

### Integration ([DEV])

- Create/delete order and NetworkAttachment cleanup wait; final vs retryable failures; provider networking disabled (BM-DEV-04).

### E2E / Contract ([QE])

- Real manager provision/discover/delete; isolation until ready; Halted handoff; SecurityGroup failure (BM-QE-01).
- Cross-tenant isolation and shared BMI/ComputeInstance Subnet behavior (BM-QE-02, BM-QE-03).
- Deployed repair-mark evidence remains unavailable until BM-QE-04 is recorded.

## Detailed scenario checklist

These assertions expand the matrix behavior summaries. They are coverage expectations, not a claim that every named suite implements every assertion or that any run passed; use the matrix to identify each suite's boundary and follow-up owner.

### Unit and Envtest ([DEV])

- **Fulfillment:** Test each network-attachment validation rule, the authorized worker `fabric_interface` path and defaults, ExternalIPAttachment endpoint readiness, Subnet deletion while a BMI references it, and each `NETWORK_READY` mapping including provider networking disabled and deletion.
- **BMF inventory and networking:** Test MAC resolution and normalization for each backend, malformed or unparsable maps, selected-port matching, exact NetworkAttachment spec/annotation/finalizer, and host-selection skips for missing inventory names or selected-port MACs. Test backend-specific handoff confirmation and failure, including the 15-minute deadline.
- **BMF status and deletion:** Test status and phase mapping with messages and job IDs copied from NetworkAttachment `status.jobs`; BMF must not launch apply or query jobs. After deletion begins, no new NetworkAttachment, handoff reboot, RunStrategy, or `restart_trigger` update should start.
- **Repair marks:** Test each inventory backend's mark write, selection exclusion, and release ordering. A mark is required only when provider networking is enabled and a started FabricDomain create job lists the host; unsupported or failed mark writes must keep the host owned.
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
- During delete, a started FabricDomain create job that lists the host requires a persisted mark before release; with no qualifying domain, no mark is written.
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
