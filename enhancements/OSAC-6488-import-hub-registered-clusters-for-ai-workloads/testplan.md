# Testplan — OSAC-6488

## Overview

- **Feature:** OSAC-6488 — Import HUB-Registered Clusters for AI Workloads
- **Total test cases:** 93
- **Requirement coverage:** FR-1–FR-4 are covered; FR-5 is partially covered.
- **Interface changes:** IC-1–IC-7 are cross-referenced in §10.16.

FR-5 cases verify capability and availability filtering and that freshness
timestamps are maintained and exposed. They do not verify consumer-side
exclusion of stale records, live AI workload routing, or tenant-isolation
enforcement; the merged design defers those contracts to a later MaaS
placement design. The gaps for IC-6's browser/API integration coverage and
IC-7's placement behavior are also called out below.

Case IDs and §10.x numbering are retained from the merged design because the
decomposed stories and synchronized Jira task descriptions reference them.
Each row states a test action and observable outcome. Section 10.14 maps case
ranges to test tiers, owners, suite locations, commands, prerequisites, and
dependency boundaries.


## 10.1 Requirement Traceability

| ID | PRD In Scope Item | Summary |
|---|---|---|
| FR-1 | Register clusters through OSAC UI, CLI, and API | Create a WorkloadCluster referencing a Hub-managed cluster |
| FR-2 | See registration outcome through UI, CLI, and API | View conditions and metadata |
| FR-3 | Registered cluster details visible only to CPAs | CPA-only authorization |
| FR-4 | Registration issues show the cause; no recovery action required | Condition-based failure reporting |
| FR-5 | AI workloads can use workload clusters preserving tenant isolation | Registration provides shared provider capacity metadata; detailed Praxis placement, trusted service access, tenant isolation, and dedicated infrastructure are deferred to a future cross-workload design |

## 10.2 Unit Tests

**Location:** `fulfillment-service/internal/servers/` (Ginkgo/Gomega)

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| U1 | Create with metadata.name="ai-worker-01-osac", source_hub_id="hub-001", managed_cluster_name="ai-worker-01", supported_workloads=["maas"] | FR-1 | Returns a WorkloadCluster with generated ID, matching metadata and spec, and `Available=Unknown` and `HubReachable=Unknown` conditions |
| U2 | Create with empty managed_cluster_name | FR-1 | Returns InvalidArgument |
| U3 | Create with unknown supported_workloads value | FR-1 | Returns InvalidArgument listing accepted values |
| U4 | Create with source_hub_id not matching configured Hub | FR-1 | Returns InvalidArgument |
| U5 | Create with duplicate (source_hub_id, managed_cluster_name) — application check | FR-4 | Returns AlreadyExists with descriptive message |
| U6 | Create when the DAO reports a unique-constraint conflict | FR-4 | Returns AlreadyExists; the database concurrency guarantee is exercised by I9 |
| U7 | Create with same managed_cluster_name but different source_hub_id | FR-1 | Returns InvalidArgument — source_hub_id must match the single configured Hub identity (§4.3). Multi-hub scenarios where different source_hub_ids coexist are deferred to the multi-hub increment (§4.8). |
| U8 | Update source_hub_id (immutable) | FR-1 | Returns InvalidArgument |
| U9 | Update managed_cluster_name (immutable) | FR-1 | Returns InvalidArgument |
| U10 | List returns only WorkloadClusters (no tenant filter) | FR-2, FR-3 | All clusters returned to CPA |
| U11 | Get by ID | FR-2 | Returns WorkloadCluster with current conditions |
| U12 | Delete RPC returns PermissionDenied | — | Returns PermissionDenied — no `workload_cluster:delete` permission in OPA policy (see IC-4) |
| U13 | Private fields not in public API | FR-3 | `managed_cluster_uid` absent from public response |
| U14 | MaaS service disabled | — | All RPCs return Unavailable |
| U15 | Registration-triggered reconciliation for existing ManagedCluster | FR-2 | Conditions transition from Unknown immediately after Create |
| U16 | Registration-triggered reconciliation for missing ManagedCluster (Hub client ready, informer synced) | FR-4 | Available=False with ManagedClusterNotFound after Create |
| U17 | ManagedCluster exists but ManagedClusterConditionAvailable=False | FR-4 | Available=False with ManagedClusterUnavailable |
| U18 | Registration-triggered reconciliation when Hub credential resolution fails or list/watch authentication fails | FR-4 | Hub readiness gate prevents informer cache lookup; sets HubReachable=False and Available=False with HubUnreachable — never ManagedClusterNotFound |
| U19 | Update a mutable label; reject an unknown workload value | FR-1 | The label change succeeds while `supported_workloads=["maas"]` is unchanged. A request with `["vmaas"]` returns `InvalidArgument` and leaves the stored object unchanged. This does not test persistence of a changed capability value. |

### CLI Unit Tests

**Location:** `fulfillment-service/internal/cmd/cli/` (Go unit tests)

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| CL1 | Create command sends Hub identity, ManagedCluster name, and MaaS capability | FR-1 | Fake client receives the requested fields; output includes the returned resource ID and condition |
| CL2 | Update command sends a mutable label change | FR-1 | Fake client receives the target ID and new label; output reflects the returned label and preserves immutable identity |
| CL3 | Update command renders an API validation error | FR-4 | Command exits non-zero and displays the API error message without success output |

## 10.3 Integration Tests

**Location:** `fulfillment-service/it/` (deployed service + database)

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| I1 | Register with a Kind test-Hub ManagedCluster fixture with `HubAcceptedManagedCluster=True`, `ManagedClusterConditionAvailable=True`, and a non-empty `id.k8s.io` ClusterClaim | FR-1, FR-2 | Create → controller watches → Available=True |
| I2 | Register with non-existent ManagedCluster | FR-4 | Available=False, reason ManagedClusterNotFound |
| I3 | Register with unaccepted ManagedCluster | FR-4 | Available=False, reason ManagedClusterNotAccepted |
| I4 | Register with unreachable Hub | FR-4 | Available=False, HubReachable=False |
| I5 | Hub watch reconnect after separate Kind test-Hub API server interruption | — | HubReachable becomes False while the test Hub API is unavailable; after it recovers, the watch reconnects and conditions become accurate within the 60-second test timeout, without restarting fulfillment-service or waiting for the five-minute re-validation cycle. The timeout is a test bound, not a product SLO. |
| I6 | ManagedCluster removed after registration | — | Available=False, reason ManagedClusterNotFound |
| I7 | ManagedCluster created after registration (delayed availability) | FR-4 | Available transitions Unknown→True |
| I8 | Cluster identity mismatch (UID changes) | — | Available=False, reason ClusterIdentityMismatch |
| I9 | Duplicate (source_hub_id, managed_cluster_name) via DB constraint | FR-4 | One succeeds, other returns AlreadyExists |
| I10 | List filter: MaaS capability and Available=True; expose freshness timestamp | FR-5 | With a fixed test clock `T0` and the design's recommended 15-minute reference threshold, matching records observed at `T0-10m` and `T0-16m` with `Available=True` are both returned with their timestamps; an `Available=False` cluster is excluded. The List filter is status-based; consumer-side stale-record exclusion is deferred. |
| I11 | Registration after informer sync — existing upstream name | FR-2 | Create returns; conditions transition from Unknown immediately via registration-triggered reconciliation |
| I12 | Registration after informer sync — missing upstream name (Hub ready) | FR-4 | Create returns; Available=False with ManagedClusterNotFound via registration-triggered reconciliation |
| I13 | Startup reconciliation after controller restart | FR-2 | All WorkloadCluster conditions refreshed against informer cache |
| I14 | Retry after failed status write | FR-4 | Condition write retried; eventually succeeds |
| I15 | ManagedCluster accepted but ManagedClusterConditionAvailable=False | FR-4 | Available=False, reason ManagedClusterUnavailable |
| I16 | Freshness re-validation updates last_observed_time without changing last_transition_time | — | last_observed_time updated within re-validation interval; last_transition_time unchanged when status/reason did not transition |
| I17 | Create during Hub credential failure, then recovery | FR-4 | Create RPC succeeds; registration-triggered reconciliation sets HubReachable=False and Available=False (HubUnreachable), not ManagedClusterNotFound. After credential fix on Hub resource, periodic re-validation or restart restores accurate conditions (Available=True for existing ManagedClusters) |
| I18 | Persist a mutable label update while resubmitting the existing `supported_workloads=["maas"]` value | FR-1 | Update succeeds; a subsequent Get returns the new label and unchanged MaaS capability while physical identity remains unchanged. This does not test persistence of a changed capability value. |

## 10.4 API Tests

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| A1 | REST POST /api/fulfillment/v1/workload-clusters with the example body below | FR-1 | HTTP 200; response body contains the created WorkloadCluster, including the generated ID, matching metadata and spec, and `Available=Unknown` and `HubReachable=Unknown` conditions |
| A2 | REST GET /api/fulfillment/v1/workload-clusters | FR-2 | Lists with filter/pagination |
| A3 | REST GET /api/fulfillment/v1/workload-clusters/{id} | FR-2 | Returns single WorkloadCluster |
| A4 | gRPC WorkloadClusters.Create | FR-1 | Creates WorkloadCluster |
| A5 | Public API excludes private fields | FR-3 | managed_cluster_uid not present |

Example request for A1 (ProtoJSON field names):

```json
{
  "metadata": {
    "name": "ai-worker-01-osac"
  },
  "spec": {
    "sourceHubId": "hub-001",
    "managedClusterName": "ai-worker-01",
    "supportedWorkloads": ["maas"]
  }
}
```

The fixture Hub `hub-001` is the configured OSAC Hub, and its accepted
ManagedCluster is named `ai-worker-01`. The relevant successful response
shape is:

```json
{
  "id": "wc-001",
  "metadata": {
    "name": "ai-worker-01-osac"
  },
  "spec": {
    "sourceHubId": "hub-001",
    "managedClusterName": "ai-worker-01",
    "supportedWorkloads": ["maas"]
  },
  "status": {
    "conditions": [
      {"type": "Available", "status": "Unknown"},
      {"type": "HubReachable", "status": "Unknown"}
    ]
  }
}
```

## 10.5 UI Tests

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| V1 | Registration form submits Create RPC | FR-1 | UI sends Create with Hub identity and capabilities |
| V2 | Registration outcome displayed | FR-2 | Conditions rendered in detail view |
| V3 | Condition reason displayed for issues | FR-4 | Available=False reason and message shown |
| V4 | CPA-only view enforcement | FR-3 | Non-CPA roles cannot access WorkloadCluster views |

## 10.6 Security and Isolation Tests

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| S1 | CPA can create WorkloadCluster | FR-1 | Create succeeds |
| S2 | CPA can list WorkloadClusters | FR-2, FR-3 | List succeeds |
| S3 | Tenant Admin cannot create WorkloadCluster | FR-3 | PermissionDenied |
| S4 | Tenant Admin cannot list WorkloadClusters | FR-3 | PermissionDenied |
| S5 | Tenant User cannot list WorkloadClusters | FR-3 | PermissionDenied |
| S6 | Tenant User cannot get WorkloadCluster by ID | FR-3 | PermissionDenied |
| S7 | Unauthenticated request rejected | FR-3 | Unauthenticated |

## 10.7 Capability and Placement Tests

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| C1 | Register with supported_workloads=["maas"] | FR-1 | Succeeds; cluster registered with MaaS capability declared |
| C2 | Register with supported_workloads=["vmaas"] (not yet allowed) | FR-1 | InvalidArgument — "vmaas" not in allow-list |
| C3 | Placement filters by supported_workloads | FR-5 | Only clusters with "maas" in list returned |
| C4 | Placement filters by Available=True | FR-5 | Unavailable clusters excluded |

## 10.8 Hub Identity and Watch Tests

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| H1 | source_hub_id validated against configured Hub | FR-1 | Mismatched hub_id returns InvalidArgument |
| H2 | Controller watch receives ManagedCluster add event | FR-2 | Corresponding WorkloadCluster conditions update |
| H3 | Controller watch receives ManagedCluster delete event | — | Available=False, reason ManagedClusterNotFound |
| H4 | Watch relist after reconnect | — | All WorkloadCluster conditions reconciled |
| H5 | managed_cluster_uid immutability enforced | — | UID change sets Available=False |

## 10.9 Credential Tests

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| K1 | Hub resource present with valid kubeconfig | — | Controller resolves credential via ResolveHubKubeconfig, watch established |
| K2 | Hub resource missing or kubeconfig unresolvable | — | Controller logs error, HubReachable=False and Available=False (reason HubUnreachable) on all clusters; recovery after credential fix on Hub resource and periodic re-validation or restart restores conditions |
| K3 | Hub resource present with invalid credentials (list/watch fails authentication) | — | HubReachable=False and Available=False (reason HubUnreachable) on all clusters; condition message describes auth failure without exposing credentials |
| K4 | Create WorkloadCluster while Hub credential is invalid, then fix credential | FR-4 | Create RPC succeeds (local validation only). Registration-triggered reconciliation sets HubReachable=False and Available=False (HubUnreachable) — informer cache not consulted, ManagedClusterNotFound never reported. After credential fix on Hub resource, periodic re-validation or restart transitions to accurate conditions (Available=True if ManagedCluster exists and is healthy) |

## 10.10 Direct OCM Compatibility Tests

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| O1 | ManagedCluster v1 API available on Hub | — | Watch established, conditions reconcile |
| O2 | ManagedCluster has HubAcceptedManagedCluster=True | FR-1 | Available=True |
| O3 | ManagedCluster has id.k8s.io ClusterClaim | — | managed_cluster_uid populated |
| O4 | Test both missing and empty `id.k8s.io` claims before and after a UID has been recorded | — | In both variants, `Available=False` with reason `ClusterIdentityMissing` and `HubReachable=True`. Before the first valid claim, `managed_cluster_uid` stays empty; after a UID has been recorded, missing or empty claims retain it. When the claim returns, a matching UID allows normal condition evaluation and a different UID yields `ClusterIdentityMismatch`. |

## 10.11 External Registration and Scope Tests

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| R1 | Register externally prepared cluster | FR-1 | WorkloadCluster created; no provisioning triggered |
| R2 | No CRD created on target cluster or operator | FR-1 | Verify no CRD side effects |
| R3 | Site/multi-cluster aggregation not supported | — | No parent resource API exists; document confirms 1:1 mapping |

## 10.12 Logging Redaction Tests

| # | Scenario | Expected Behavior |
|---|---|---|
| L1 | Registration success — log contains only allowed fields | workload_cluster_id, supported_workloads, condition, component, operation, request_id; no denied fields |
| L2 | Registration failure — log redacts denied fields | Reason code present; no ManagedCluster name, Hub URL, credentials, stack trace |
| L3 | Hub watch error — log redacts denied fields | Error category present; no internal addresses, bearer tokens |

## 10.13 Failure Tests

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| F1 | Hub unreachable during registration | FR-4 | Available=False, HubReachable=False |
| F2 | Hub recovers after outage | — | Available condition updates via watch |
| F3 | Controller restart mid-reconciliation | FR-4 | Resumes from database state; no duplicate records |
| F4 | Database unavailable during Create | FR-4 | Returns Internal error; no partial state |
| F5 | Concurrent duplicate registrations (DB constraint) | FR-4 | Exactly one succeeds |
| F6 | Create during Hub credential failure (Hub readiness gate) | FR-4 | Create succeeds locally; reconciliation sets HubUnreachable, never ManagedClusterNotFound; recovery restores accurate conditions |

## 10.14 Integration-Test Planning Evidence Matrix

The following matrix satisfies the [Integration testing: planning
evidence](https://github.com/osac-project/osac/blob/main/docs/INTEGRATION-TESTING.md#planning-evidence)
requirement. Each row identifies the owning component, required tier,
real vs. simulated dependencies, and follow-up gaps.

| Component | Behavior / Boundary | Required Tier | DEV/QE Owner | Case IDs / Suite Location | Command / Prerequisites | Real Dependencies | Simulated / Mocked Dependencies | Follow-up Gaps |
|---|---|---|---|---|---|---|---|---|
| fulfillment-service | Create RPC validation, capability validation, Hub identity validation, and immutability | Unit | [DEV] [OSAC-6916](https://redhat.atlassian.net/browse/OSAC-6916) | U1–U14, C1–C2, H1 / `fulfillment-service/internal/servers/` (Ginkgo) | From `fulfillment-service/`: `ginkgo run --timeout 10m internal/servers` | None | DAO mocked; Hub client mocked | U6 tests DAO conflict-to-AlreadyExists mapping; I9 tests the real concurrent database constraint. |
| fulfillment-service | Label Update validation and persistence | Unit + component integration | [DEV] [OSAC-6916](https://redhat.atlassian.net/browse/OSAC-6916) | U19 / `fulfillment-service/internal/servers/`; I18 / `fulfillment-service/it/` | U19: `ginkgo run --timeout 10m internal/servers` from `fulfillment-service/`; I18: run the Fulfillment Kind target below | Deployed Fulfillment and PostgreSQL for I18 | DAO mocked for U19; I18 uses the deployed API and database; Hub is not involved | Only `maas` is allowed today. These cases test label persistence and unknown-value rejection, not a successful capability-value mutation. |
| fulfillment-service CLI | Create/update command request construction and API error rendering | Unit | [DEV] [OSAC-6918](https://redhat.atlassian.net/browse/OSAC-6918) | CL1–CL3 / `fulfillment-service/internal/cmd/cli/` | From `fulfillment-service/`: `ginkgo run --timeout 20m -r internal` | None | WorkloadClusters gRPC client is fake | — |
| fulfillment-service | Registration-triggered reconciliation and Hub readiness gate | Unit | [DEV] [OSAC-6917](https://redhat.atlassian.net/browse/OSAC-6917) | U15–U18 / `fulfillment-service/internal/controllers/` (Ginkgo) | From `fulfillment-service/`: `ginkgo run --timeout 20m -r internal` | None | Informer cache and DAO mocked | These tests cover controller-side handling only; the Kind component suite exercises real list/watch behavior. |
| fulfillment-service | Controller watch, cache sync, authentication, condition transitions, startup reconciliation, OCM claim validation | Component integration | [DEV] [OSAC-6917](https://redhat.atlassian.net/browse/OSAC-6917) | I1–I8, I11–I17, H2–H5, K1–K4, O1–O4, F1–F3, F6 / `fulfillment-service/it/` | From the repo root, install the Kind test environment with `make -C osac-installer install-infra PLATFORM=kind PROFILE=dev NS=osac`, then run `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment` | Deployed Fulfillment, PostgreSQL, Keycloak, and a separate Kind test-Hub Kubernetes API server | **Proposed test fixture:** provision a separate Kind test-Hub cluster, install the OCM ManagedCluster and ClusterClaim CRDs, and configure the OSAC Hub resource to use a scoped test ServiceAccount kubeconfig. The API server handles real list/watch, authentication, cache sync, and reconnects; test-Hub interruption does not interrupt the OSAC deployment cluster. Fixture objects stand in for ACM-managed state, and no ACM controller is present. | OSAC-6917 owns the fixture. Live ACM compatibility remains E2E coverage under OSAC-6920; no ACM Hub is provisioned in CI. |
| fulfillment-service | Database uniqueness, List filters, and query metadata | Component integration | [DEV] [OSAC-6916](https://redhat.atlassian.net/browse/OSAC-6916) | I9–I10, C3–C4 / `fulfillment-service/it/` | Fulfillment Kind target above; use fixed timestamps in fixture data for deterministic freshness assertions | Deployed Fulfillment and PostgreSQL | No Hub API or Praxis consumer; conditions and timestamps are fixture data | Consumer-side stale-record exclusion, live routing, and tenant-to-cluster assignment remain deferred to the cross-workload design. |
| fulfillment-service | REST/gRPC API shape and CPA-only authorization | Component integration | [DEV] [OSAC-6916](https://redhat.atlassian.net/browse/OSAC-6916) | A1–A5, S1–S7, F4–F5 / `fulfillment-service/it/` | Fulfillment Kind target above | Deployed Fulfillment, PostgreSQL, Keycloak, REST gateway, and CLI | No external provider workflows | — |
| fulfillment-service | Logging redaction | Unit + component integration | [DEV] [OSAC-6917](https://redhat.atlassian.net/browse/OSAC-6917) | L1–L3 / `fulfillment-service/internal/` + `it/` | Unit: `ginkgo run --timeout 20m -r internal` from `fulfillment-service/`; integration: Fulfillment Kind target above | Deployed Fulfillment and PostgreSQL for integration | Hub state is fixture-driven; no real ACM controller | — |
| fulfillment-service | Credential lifecycle and freshness timestamps | Component integration | [DEV] [OSAC-6917](https://redhat.atlassian.net/browse/OSAC-6917) | I16–I17, K1–K4 / `fulfillment-service/it/` | Fulfillment Kind target above | Deployed Fulfillment, PostgreSQL, Kind Kubernetes API server | Test Hub ServiceAccount credentials and ManagedCluster fixtures; no ACM controller | Staleness threshold interaction with Praxis remains deferred. |
| Documentation | Document 1:1 registration mapping and deferred aggregate/site behavior | Docs review | [DOCS] [OSAC-6921](https://redhat.atlassian.net/browse/OSAC-6921) | R3 / WorkloadCluster user and API documentation | Review the user-facing/API docs with the docs task | Documentation only | No runtime dependencies | — |
| tests/e2e | Register, verify, CPA-only access, duplicate detection, and filtered List query | E2E | [QE] [OSAC-6920](https://redhat.atlassian.net/browse/OSAC-6920) | E1–E8, R1–R2 / proposed under `tests/e2e/` | Exact suite command is not defined until the live-Hub test environment and suite are added | Deployed OSAC stack, PostgreSQL, live ACM Hub with ManagedCluster | None — all dependencies real | OSAC-6920 owns the cases; live Hub environment and access owner remain unresolved. |
| tests/e2e | Tenant-to-cluster assignment and placement isolation | E2E | [QE] | Deferred | Deferred to future cross-workload design | — | — | Tenant-specific cluster assignment, dedicated infrastructure, and placement isolation E2E: deferred until cross-workload tenant-to-cluster model is designed. Owner: Praxis/MaaS team. |
| UI | Registration form, condition display, failure display, and role-dependent views | Unit | [UI] [OSAC-6919](https://redhat.atlassian.net/browse/OSAC-6919) | V1–V4 / proposed tests alongside `osac-ui/apps/app-frontend/src/` components | From `osac-ui/`: `pnpm test` | React components and app test runner | Connect API responses use `createMockConnectTransport`; no deployed service or browser E2E | OSAC-6919 owns V1–V4; no specific delivery date is set on the task. A persisted browser/API E2E suite does not exist; UI unit tests do not prove that deployed boundary. |

**Limitations and honest disclosures:**

- **Kind test Hub limitation:** Planned component-integration tests use a
  separate Kind test-Hub cluster's real Kubernetes API server with the OCM
  ManagedCluster and ClusterClaim CRDs installed. A scoped ServiceAccount
  kubeconfig exercises actual list/watch requests, authentication, cache sync, and
  reconnect behavior. The suite creates fixture objects directly; it does
  not run the ACM controller, so it does not establish ACM-managed condition
  behavior or compatibility with a production ACM Hub. Real ACM compatibility
  remains E2E coverage (E1–E6).
- **No ACM Hub in CI:** The E2E environment does not currently provision a
  live ACM Hub. OSAC-6920 owns E1–E8 and the live-Hub environment prerequisite.
- **Proposed commands and locations:** Test file paths and commands
  marked "proposed" do not yet exist. They represent the intended
  location following existing fulfillment-service conventions.
- **UI browser coverage:** V1–V4 can run in the existing Vitest and React
  Testing Library harness with the mock Connect transport. The repository has
  no persisted browser E2E suite, so these cases do not prove the deployed
  browser/API boundary.
- **Praxis placement E2E:** Tenant-to-cluster assignment, dedicated
  infrastructure, placement isolation, and consumer-side stale-record
  exclusion are deferred to the future cross-workload design. The proposed E8
  test is intended to verify that List returns capability, availability, and
  freshness metadata; it does not prove executed coverage until the test
  exists and runs.

## 10.15 E2E Tests

**Location:** `tests/e2e/` (pytest via osac-test-infra)

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| E1 | Register Hub-managed cluster via API | FR-1 | WorkloadCluster with Available=True |
| E2 | Verify outcome via CLI `osac workload-cluster list` | FR-2 | Cluster in list with Available status |
| E3 | Verify outcome via CLI `osac workload-cluster describe` | FR-2 | Conditions, spec, metadata shown |
| E4 | Register non-existent ManagedCluster | FR-4 | Available=False with descriptive reason |
| E5 | Verify CPA-only access | FR-3 | Tenant roles get PermissionDenied |
| E6 | Register same cluster twice | FR-4 | AlreadyExists |
| E7 | Delete RPC returns PermissionDenied | — | PermissionDenied — no `workload_cluster:delete` in OPA policy; handler not reached (see IC-4) |
| E8 | List query with MaaS capability and Available=True filters | FR-5 | With a fixed test clock and the design's recommended 15-minute reference threshold, the response includes matching `Available=True` records observed 10 and 16 minutes earlier with their `last_observed_time` values; it excludes `Available=False` records. The List filter is status-based; consumer-side stale-record exclusion is deferred. |

**E2E infrastructure requirement:** An ACM Hub with at least one
registered ManagedCluster in the test environment.

## 10.16 Decomposition Traceability Addendum

This addendum was added while rehydrating the merged design for
decomposition. It makes interface-to-test references explicit and records
the execution evidence missing from the approved plan; it does not change the
merged design document.

### Interface Change → Test Case Crosswalk

| Interface Change | Test cases in this plan | Coverage notes |
|-----------------|-------------------------|----------------|
| IC-1: Create/Register RPC | U1–U7, A1, A4, S1, E1, E6, R1, R2 | R1/R2 verify external registration has no provisioning or target/operator CRD side effects; deployed execution is proposed. |
| IC-2: Get/List RPCs | U10–U11, A2–A3, S2, S4–S6, E2–E5, E8 | Includes CPA-only visibility, capability and condition filters, and exposure of freshness timestamps. |
| IC-3: Update RPC | U8–U9, U19, I18 | Covers immutable-field rejection, mutable-label persistence, and rejection of unknown `vmaas`. Resubmitting the existing `maas` value does not prove persistence of a changed capability value; that remains untested while `maas` is the only allowed value. |
| IC-4: Delete RPC — Deferred | U12, E7 | Verifies Delete remains denied; it does not implement disconnect. |
| IC-5: CLI commands | CL1–CL3, E2–E3 | Unit tests cover create/update requests and API error rendering; deployed tests cover list/describe. |
| IC-6: UI registration/status views | V1–V4 | Scenarios exist, but the approved plan does not define an executable UI integration harness. Existing UI unit tests are not deployed UI/API coverage. |
| IC-7: MaaS placement query data foundation | I10, C1, C3–C4, E8 | These cases verify capability and Available filters and expose freshness timestamps; they do not test consumer-side stale-record exclusion, workload routing, or tenant isolation. |

### External Registration Test Planning Evidence

| Component | Behavior / Boundary | Required Tier | Owner | Cases / Location | Command / Prerequisites | Real Dependencies | Simulated / Mocked Dependencies | Gap |
|---|---|---|---|---|---|---|---|---|
| tests/e2e | R1: external registration creates only the OSAC WorkloadCluster and triggers no provisioning | E2E | [QE] [OSAC-6920](https://redhat.atlassian.net/browse/OSAC-6920) | R1 / proposed `tests/e2e/test_workload_cluster.py` | Proposed: `uv run pytest -n 0 tests/e2e/test_workload_cluster.py` from repository root; deployed OSAC and a registered ManagedCluster | OSAC API, database, controller, ACM Hub; inspect provisioning/API state | None | OSAC-6920 owns R1/R2; the proposed test file, live Hub environment, and Hub access owner remain unresolved. |
| tests/e2e | R2: no target-cluster or OSAC-operator CRD side effects | E2E | [QE] [OSAC-6920](https://redhat.atlassian.net/browse/OSAC-6920) | R2 / proposed `tests/e2e/test_workload_cluster.py` | Proposed: same command and root working directory; requires access to the target ManagedCluster and OSAC operator API | OSAC operator and target cluster API, plus live ACM Hub | None | OSAC-6920 owns R1/R2; test file, target-cluster/OSAC-operator access, and live Hub environment remain unresolved. |
| Documentation | R3: document one-to-one WorkloadCluster/ManagedCluster mapping and no site aggregation | Documentation review | [DOCS] [OSAC-6921](https://redhat.atlassian.net/browse/OSAC-6921) | R3 / user-facing API and admin documentation | No test command; review the published documentation against the design's one-to-one scope | Published documentation | Not applicable | Covered by documentation task OSAC-6921. |
