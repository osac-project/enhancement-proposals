---
title: OSAC-1437 BMaaS Networking Test Plan
last-updated: 2026-10-28
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

This plan classifies BMaaS networking verification by **tier** and **owner**. It names existing suites and commands where they exist. It does **not** claim that every accepted-design row is already implemented ([design — Implementation status](design.md#implementation-status)). Real Fabric Manager + Metal3/Ironic hardware evidence for the remaining PR #357 delta is owned by [OSAC-6820](https://redhat.atlassian.net/browse/OSAC-6820); broader provider-contract gaps remain under [OSAC-4843](https://redhat.atlassian.net/browse/OSAC-4843).

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

| ID | Behavior | Tier | Owner | Suite / command | Real vs simulated | Gap / follow-up |
|---|---|---|---|---|---|---|
| BM-DOC-01 | Fulfillment network-attachment validation (single attachment, fabric port, defaults, immutability, worker interface skip) | Unit | [DEV] | `fulfillment-service` server/validation tests for BareMetalInstance networking; run component `make test` / focused packages under `fulfillment-service/` | Real validation logic; no provider | Extend under [OSAC-6818](https://redhat.atlassian.net/browse/OSAC-6818) where PR #357 delta rules are missing |
| BM-DOC-02 | `NETWORK_READY` / phase mapping (incl. provider networking disabled and delete) | Unit | [DEV] | Fulfillment BareMetalInstance status mapping tests under `fulfillment-service/` | Real mapping; CR fixtures | OSAC-6818 if delta cases missing |
| BM-DOC-03 | BMF NetworkAttachment reconcile, MAC recording, deletion guards | Unit | [DEV] | `bare-metal-fulfillment-operator/internal/controller/baremetalinstance_networking_test.go`; `make test` from `bare-metal-fulfillment-operator/` | Controller real; inventory/AAP faked | OSAC-6818 for remaining handoff/repair delta |
| BM-DOC-04 | BMF IP discovery / lease artifact handling after handoff | Unit | [DEV] | `bare-metal-fulfillment-operator/internal/controller/baremetalinstance_ip_discovery_test.go`; `make test` from `bare-metal-fulfillment-operator/` | Controller real; AAP/job artifacts faked | OSAC-6818 for MAC-scoped query timing alignment |
| BM-DOC-05 | BMF Metal3/BCM envtest persistence for networking-related BMI status | Envtest | [DEV] | `baremetalinstance_metal3_envtest_test.go`, `baremetalinstance_bcm_envtest_test.go`; included by `make test` from `bare-metal-fulfillment-operator/` | Real envtest API/etcd; Metal3/BCM hardware faked | OSAC-6818 |
| BM-DOC-06 | BareMetalInstance cleanup finalizer / automatic ExternalIP ownership | Unit / Envtest | [DEV] | `osac-operator/internal/controller/baremetalinstance_cleanup_controller_test.go`; `make test` from `osac-operator/` | Real client/envtest objects; AAP/provider controlled | Shared core may also touch OSAC-6766 |
| BM-DOC-07 | Deployed BMF ownership boundary (networking cleanup wait; no network resource mutation) | Component integration | [DEV] | NET-CLEAN-08 in mono-repo `docs/INTEGRATION-TESTING.md`; installer Kind path for BMF | Real Kind/operator; no real Fabric | Documented boundary only |
| BM-DOC-08 | BMF Kind component integration (pool/instance flows) | Component integration | [DEV] | `make integration-tests` from `bare-metal-fulfillment-operator/`; CI `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=bmf` | Real Kind CRDs; static Metal3/provider simulation | Does not prove Fabric port move or DHCP |
| BM-DOC-09 | Mock-manager BM create/delete order, handoff-before-lease, teardown port restore | Component integration | [DEV] | Contract [TC-WORKLOAD-01](/enhancements/OSAC-1433-network-manager-integration-contract-networking/testplan.md#tc-workload-01-exercise-bare-metal-and-cluster-workload-flows) (mock manager) | Mock Fabric Manager | Implementation wiring under OSAC-6818 / OSAC-6766 |
| BM-DOC-10 | Provider conformance: bare-metal profile (address, SSH, egress, blocked port) | Contract / E2E | [QE] | Contract [TC-BM-01](/enhancements/OSAC-1433-network-manager-integration-contract-networking/testplan.md); lab `baremetal` profile | Requires conformant Fabric Manager + hosts | Mark unavailable without lab; [OSAC-6820](https://redhat.atlassian.net/browse/OSAC-6820), [OSAC-4843](https://redhat.atlassian.net/browse/OSAC-4843) |
| BM-DOC-11 | Baseline BMI lifecycle E2E (incl. historical Netris attachment path) | E2E | [QE] | `tests/e2e/bmaas/sanity/test_baremetal_instance_lifecycle.py` from repo root (environment-dependent) | Lab-dependent | Closed [OSAC-1510](https://redhat.atlassian.net/browse/OSAC-1510) baseline; **do not** treat as full PR #357 delta pass |
| BM-DOC-12 | Deployed PR #357 delta: port move, handoff reboot, MAC lease discovery, repair mark, retry/delete | E2E | [QE] | Suite to be named under [OSAC-6820](https://redhat.atlassian.net/browse/OSAC-6820) | Real Fabric + Metal3/Ironic | **Unavailable** until OSAC-6820; not supported as passing today |
| BM-DOC-13 | Edge cases (BMF restart at handoff points, cancel on delete, repair mark races) | Unit / Envtest then E2E | [DEV] then [QE] | Extend BMF/operator tests first ([design edge cases](design.md#edge-cases-that-need-handling)); deployed proof under OSAC-6820 | Fixtures first; hardware later | Design marks “later”; track under OSAC-6818 / OSAC-6820 |

## Behavior checklist (maps to design)

Use the matrix IDs above; this list is the design coverage index.

### Unit ([DEV])

- Fulfillment: validation rules; worker `fabric_interface`; ExternalIPAttachment endpoint-ready; Subnet delete while BMI references; each `NETWORK_READY` case (BM-DOC-01, BM-DOC-02).
- BMF: MAC resolution per backend; NetworkAttachment spec/annotation/finalizer; handoff per backend; status/phase rows; deletionTimestamp guards; repair mark; provider networking disabled (BM-DOC-03, BM-DOC-04, BM-DOC-05).
- Networking controller: `target.host_name`; query only after handoff; retry cadence; wrong-MAC / out-of-range lease reject (BM-DOC-09 / shared controller tests; extend OSAC-6818).
- Cleanup / feedback controllers: finalizer lifecycle (BM-DOC-06).

### Integration ([DEV])

- Create/delete order with mock Fabric Manager; final vs retryable failures; automatic access gating; provider networking disabled (BM-DOC-08, BM-DOC-09).

### E2E / Contract ([QE])

- Real manager provision/discover/delete; isolation until ready; Halted handoff; automatic ExternalIP; SecurityGroup failure (BM-DOC-10, BM-DOC-12).
- Baseline lifecycle path only as historical evidence (BM-DOC-11).

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
