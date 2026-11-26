# Testplan — OSAC-6488

## Overview

- **Feature:** OSAC-6488 — Register MaaS Hubs and Spokes as External Clusters
- **Total test cases:** 113
- **Requirement coverage:** FR-1–FR-4 are covered; FR-5 is partially covered.
- **Interface changes:** IC-1–IC-7 are cross-referenced in §10.16.

FR-5 cases verify MaaS Hub, spoke type, role, and availability filtering and that freshness
timestamps are maintained and exposed. They do not verify consumer-side
exclusion of stale records, live AI workload routing, or tenant-isolation
enforcement; the design defers those contracts to a later MaaS
placement design. The execution prerequisites for IC-6's browser/API coverage and the
deferred IC-7 placement behavior are called out below.

Existing case IDs and §10.x numbering are retained for traceability with the
merged design and synchronized Jira task descriptions. Cases retain their IDs for Jira traceability.
All cases are planned and have not been run against this revision. Each row states a test action and
observable outcome. Section 10.14 maps case ranges to test tiers, owners, suite
locations, commands, prerequisites, and dependency boundaries.


## 10.1 Requirement Traceability

| ID | PRD In Scope Item | Summary |
|---|---|---|
| FR-1 | Register MaaS Hubs and spokes through OSAC UI, CLI, and API | Register a MaaS Hub and link its ACM-managed spokes via the private Fulfillment service |
| FR-2 | See registration outcome through UI, CLI, and API | View conditions and metadata |
| FR-3 | Registered cluster details visible only to CPAs | CPA-only authorization |
| FR-4 | Registration issues show the cause; no recovery action required | Condition-based failure reporting |
| FR-5 | AI workloads can use workload clusters preserving tenant isolation | Registration provides shared provider capacity metadata; detailed Praxis placement, trusted service access, tenant isolation, and dedicated infrastructure are deferred to a future cross-workload design |

## 10.2 Unit Tests

**Location:** `fulfillment-service/internal/servers/` (Ginkgo/Gomega)

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| U1 | Create MaaS Hub `maas-east` with `source_hub.id=osac-main`, `secret.id=east-kubeconfig`, type `CLUSTER_TYPE_MAAS_HUB`, and `maas_hub_config.namespace=maas-system` | FR-1 | Returns a generated ID, matching spec, and `Available=Unknown` and `HubReachable=Unknown` |
| U2 | Create with empty `metadata.name` | FR-1 | Returns `InvalidArgument` |
| U3 | Create with no types, duplicate types, an undefined type, or `CLUSTER_TYPE_UNSPECIFIED` | FR-1 | Each request returns `InvalidArgument` |
| U4 | Create with missing `source_hub`, unknown OSAC Hub ID, or mismatched source Hub ID and name | FR-1 | Each request returns `InvalidArgument` |
| U5 | Try to reuse hub record name `maas-east` for an unlinked spoke. Try to reuse spoke record name `inference-east` for a spoke on another MaaS Hub with a different effective ACM name and for a dual-type record. Also submit distinct registration names that target the same effective ACM name on one hub, referring to that hub by name and ID. | FR-4 | Every attempt returns `AlreadyExists`. The first three attempts collide on the ExternalCluster name in the `shared` tenant. The last attempt collides on the per-hub ACM identity. |
| U6 | Create when the DAO reports an ExternalCluster name conflict or an ACM identity conflict | FR-4 | Both return `AlreadyExists`. F5 covers concurrent OSAC name collisions and I9 covers concurrent ACM identity collisions. |
| U7 | An existing spoke named `inference-east` uses override `ai-worker-01` on `maas-east`. Create a spoke named `inference-west` using override `ai-worker-01` on `maas-west`. Both use `source_hub.id=osac-main`. | FR-1 | Both registrations can coexist. Their ExternalCluster names are distinct and each spoke resolves its ACM name on its own MaaS Hub. |
| U8 | Update `source_hub` or change `cluster_types` | FR-1 | Returns `InvalidArgument` and preserves the stored spec |
| U9 | Update `metadata.name`, add, change, or clear `managed_cluster_name`, or replace or remove an assigned `maas_spoke_config.maas_hub` | FR-1 | Each change returns `InvalidArgument` and preserves the stored binding |
| U10 | CPA lists ExternalClusters | FR-2, FR-3 | The response includes all declared types and hub assignments. Each record belongs to the `shared` tenant and has no project assignment. |
| U11 | Get by ID | FR-2 | Returns ExternalCluster with current conditions |
| U12 | A CPA calls the private ExternalClusters Delete RPC | — | The explicit ExternalCluster Delete denial returns `PermissionDenied` even for admins (see IC-4). |
| U13 | A CPA supplies forged conditions and UID on Create, targets status through an Update mask, then sends an Update without a mask that includes status | FR-2, FR-3 | Create initializes status and leaves the UID unset. The masked Update returns `InvalidArgument`. The unmasked Update preserves the stored status and UID. |
| U14 | MaaS service disabled | — | All RPCs return Unavailable |
| U15 | Registration-triggered reconciliation for existing ManagedCluster | FR-2 | Conditions transition from Unknown immediately after Create |
| U16 | Registration-triggered reconciliation for missing ManagedCluster (Hub client ready, informer synced) | FR-4 | Available=False with ManagedClusterNotFound after Create |
| U17 | Hub is authenticated and informer synced; ManagedCluster has HubAcceptedManagedCluster=True, a non-empty `id.k8s.io` claim, and ManagedClusterConditionAvailable=False | FR-4 | Available=False with ManagedClusterUnavailable |
| U18 | Registration-triggered reconciliation when Hub credential resolution fails or list/watch authentication fails | FR-4 | Hub readiness gate prevents informer cache lookup; sets HubReachable=False and Available=False with HubUnreachable — never ManagedClusterNotFound |
| U19 | Update label `site=east` and change a spoke role from `INGRESS` to `COMBINED`; then attempt `AI_GRID_ROLE_UNSPECIFIED` | FR-1 | Valid update succeeds; invalid role returns `InvalidArgument` and retains the previously stored values |
| U20 | Create a hub-only or dual-type record without `secret`, or supply an opaque, tenant-local, shared-tenant, or missing Secret | FR-1, FR-3 | Each request returns `InvalidArgument` without exposing Secret data |
| U21 | Create a MaaS Hub with no `maas_hub_config` or an invalid namespace; create a spoke with missing config or undefined role; supply a role config for an undeclared type | FR-1 | Each invalid request returns `InvalidArgument` |
| U22 | Create a spoke that references a missing ExternalCluster or a spoke-only ExternalCluster as its MaaS Hub; update an unlinked dual-type record to reference itself | FR-1 | Each invalid request returns `InvalidArgument` |
| U23 | Reconcile an unlinked spoke while another MaaS Hub has a same-name ManagedCluster | FR-2, FR-4 | Both conditions remain `Unknown` with `MaasHubUnassigned`. The controller does not query any hub or write a UID. |
| U24 | Update a dual-type record with a valid namespace and role; reconcile with its own watch healthy and its selected hub unreachable | FR-1, FR-2 | Config is accepted. Both conditions are `False` with `HubUnreachable` until both watch checks pass; no recursive reconcile of the selected hub as a spoke. |
| U25 | Create a spoke-only record first without `secret` and then, under a different name, with a valid provider-global kubeconfig Secret reference | FR-1 | Both succeed. The first persists no Secret reference, and the second persists only the reference. |
| U26 | Create a spoke with `managed_cluster_name=""` or `managed_cluster_name="ai worker"` | FR-1 | Both return `InvalidArgument`. Omitting the field uses `metadata.name` as verified in I1. |

### CLI Unit Tests

**Location:** `fulfillment-service/internal/cmd/cli/` (Go unit tests)

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| CL1 | In private CLI mode, register a MaaS Hub with named OSAC Hub and Secret references and a namespace, then a spoke with a MaaS Hub reference, a combined role, and a different ACM name | FR-1 | The mock private gRPC service receives both Creates. The spoke request includes the name override and omits its Secret reference. Output includes returned IDs and conditions. |
| CL2 | In private CLI mode, edit an ExternalCluster label | FR-1 | The mock private gRPC service receives the target ID and new label. Output reflects the returned label and preserves immutable identity. |
| CL3 | Run edit in private CLI mode and have the service reject the request | FR-4 | The command exits non-zero and displays the validation error. |

## 10.3 Integration Tests

**Location:** `fulfillment-service/it/` (deployed service + database)

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| I1 | Create a spoke named `ai-worker-01` without an override or Secret reference. Its Kind test MaaS Hub has a ManagedCluster named `ai-worker-01` with `HubAcceptedManagedCluster=True`, `ManagedClusterConditionAvailable=True`, and a non-empty `id.k8s.io` ClusterClaim. | FR-1, FR-2 | The controller uses the registration name for lookup. The spoke becomes `Available=True` and Get returns no Secret reference. |
| I2 | Register with non-existent ManagedCluster | FR-4 | Available=False, reason ManagedClusterNotFound |
| I3 | Register with unaccepted ManagedCluster | FR-4 | Available=False, reason ManagedClusterNotAccepted |
| I4 | Register with unreachable Hub | FR-4 | Available=False, HubReachable=False |
| I5 | Hub watch reconnect after separate Kind test-Hub API server interruption | — | HubReachable becomes False while the test Hub API is unavailable; after it recovers, the watch reconnects and conditions become accurate within the 60-second test timeout, without restarting fulfillment-service or waiting for the five-minute re-validation cycle. The timeout is a test bound, not a product SLO. |
| I6 | Previously available ManagedCluster removed, then recreated with the same name and recorded UID while the Hub is reachable and informer synced | — | Available=False with ManagedClusterNotFound while absent; after recreation with HubAcceptedManagedCluster=True, ManagedClusterConditionAvailable=True, and a non-empty `id.k8s.io` claim matching the retained UID, Available=True |
| I7 | ManagedCluster created after registration (delayed availability) while the Hub is reachable and informer synced, with HubAcceptedManagedCluster=True, ManagedClusterConditionAvailable=True, and a non-empty `id.k8s.io` claim; no UID has been recorded yet | FR-4 | Available transitions Unknown→True and the first UID is recorded only after validation succeeds |
| I8 | Same-name ManagedCluster recreated with a different non-empty UID after a UID was recorded, while the Hub is reachable and informer synced | — | Available=False with reason ClusterIdentityMismatch; the previously recorded UID is retained |
| I9 | Submit concurrent Create requests against the same MaaS Hub via its name and ID. One names the registration `ai-worker-01` and omits the override. The other names it `inference-east` with override `ai-worker-01`. | FR-4 | One succeeds and one returns `AlreadyExists`. List returns one registration for that hub and effective ManagedCluster name. |
| I10 | List `maas-east` inference-capable spokes with `Available=True`; seed matching timestamps at T0−10m and T0−16m, plus an unavailable spoke, ingress-only spoke, hub-only record, and a spoke on `maas-west` | FR-5 | Only the two matching spokes are returned, with both `last_observed_time` values. List leaves freshness enforcement to consumers. |
| I11 | After informer sync, create a spoke registration named `inference-east` with override `ai-worker-01`. Both names exist on the hub with different `id.k8s.io` claims. | FR-2 | Registration-triggered reconciliation sets `Available=True` and records the claim from `ai-worker-01`. |
| I12 | Registration after informer sync — missing upstream name (Hub ready) | FR-4 | Create returns; Available=False with ManagedClusterNotFound via registration-triggered reconciliation |
| I13 | Restart the fulfillment controller while observing `maas-east` and `maas-west` | FR-2 | Conditions for both MaaS Hubs and their spokes are refreshed against their respective synchronized watches |
| I14 | Retry after failed status write | FR-4 | Condition write retried; eventually succeeds |
| I15 | Reachable, synchronized test Hub has a ManagedCluster with HubAcceptedManagedCluster=True, a non-empty `id.k8s.io` claim, and ManagedClusterConditionAvailable=False | FR-4 | Available=False, reason ManagedClusterUnavailable |
| I16 | Freshness re-validation updates last_observed_time without changing last_transition_time | — | last_observed_time updated within re-validation interval; last_transition_time unchanged when status/reason did not transition |
| I17 | Create during a MaaS Hub credential failure, then rotate its Secret while its accepted and available ManagedCluster has a non-empty `id.k8s.io` claim | FR-4 | Create succeeds, then status is `HubUnreachable` with no `ManagedClusterNotFound`. Within one re-validation interval plus watch sync, or after restart, the spoke becomes `Available=True` and records the UID. |
| I18 | Update a spoke label and role from `INGRESS` to `COMBINED`; update the registered MaaS Hub namespace | FR-1 | A subsequent Get returns the new label, role, and namespace. The previously assigned hub and other identity fields remain stable. |
| I19 | Register `maas-east` and `maas-west` with distinct kubeconfig Secrets under an OSAC Hub without OCM. Each MaaS Hub has an accepted, available `ai-worker-01` with a different `id.k8s.io` claim. Register spokes `inference-east` and `inference-west` with override `ai-worker-01` on their respective hubs. Remove the ManagedCluster on east, then interrupt east's API. | FR-1, FR-2, FR-4 | Both hubs and spokes initially become available and the spokes record their own hub's claims. East alone reports `ManagedClusterNotFound` after delete, then `HubUnreachable` on outage. West retains `Available=True`. |
| I20 | Create `ai-worker-01` with no MaaS Hub while both hubs have a same-name ManagedCluster. Assign `maas-west` through Update. | FR-1, FR-2 | Initially `MaasHubUnassigned` with no UID. Reconciliation after Update observes west's claim and becomes available. A subsequent Update to `maas-east` returns `InvalidArgument`. |
| I21 | Validate two updates against the same unlinked spoke version, each assigning a different available MaaS Hub, then allow the two writes to race | FR-1 | Exactly one binding persists. The conflicting write returns `Aborted`; reconciliation uses the winning hub's claim and never commits a UID from the losing binding. |
| I22 | Create unlinked spoke `inference-east` with override `ai-worker-01`. Assign it to `maas-east`, where an existing spoke registration already targets `ai-worker-01`. | FR-1, FR-4 | Update returns `AlreadyExists`. Get returns the original unlinked spoke and reconciliation keeps `MaasHubUnassigned`. |

## 10.4 API Tests

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| A1 | On the internal REST gateway, POST `/api/private/v1/external_clusters` as a CPA, using the spoke-only example below | FR-1 | HTTP 200. The response contains the generated ID, registration name and override, and `Available=Unknown` and `HubReachable=Unknown`. The Secret reference is absent. |
| A2 | GET `/api/private/v1/external_clusters` as a CPA with a CEL filter and pagination | FR-2 | Returns the matching page from the `shared` tenant. |
| A3 | GET `/api/private/v1/external_clusters/{id}` as a CPA | FR-2 | Returns that ExternalCluster and its conditions. |
| A4 | Invoke `osac.private.v1.ExternalClusters/Create` as a CPA for `maas-east` with the MaaS Hub type, namespace `maas-system`, and its provider kubeconfig Secret reference | FR-1 | Returns an ExternalCluster ID and persists the hub configuration and Secret reference. |
| A5 | As a CPA, call the public REST and gRPC ExternalCluster methods on the internal gateway and server. Then try the private REST and gRPC paths through the external listener. | FR-3 | Public REST collection and item paths under `/api/fulfillment/v1/external_clusters` return HTTP 404 and `osac.public.v1.ExternalClusters/List` returns `Unimplemented`. The external listener blocks the private paths. A1–A4 verify the corresponding internal paths work. |
| A6 | Read a verified spoke with a Secret reference through the private REST API as a CPA | FR-2, FR-3 | Its status returns the controller-recorded `managed_cluster_uid`. The response contains the Secret reference and omits kubeconfig data. |

Example request for A1. The REST gateway uses proto field names in JSON.
The fixture provides `osac-main` and the registered MaaS Hub `maas-east`
with its own kubeconfig Secret. The OSAC Hub has no ACM API.
`maas-east` has an accepted, available `ManagedCluster` named
`ai-worker-01`. The spoke uses the OSAC registration name
`inference-east`.

```json
{
  "metadata": {
    "name": "inference-east"
  },
  "spec": {
    "source_hub": {"id": "osac-main"},
    "cluster_types": ["CLUSTER_TYPE_MAAS_SPOKE"],
    "maas_spoke_config": {
      "maas_hub": {"id": "maas-east"},
      "role": "AI_GRID_ROLE_INFERENCE",
      "managed_cluster_name": "ai-worker-01"
    }
  }
}
```

Omitting `managed_cluster_name` makes the controller look for
`inference-east` on `maas-east`. The private response reports the
controller-owned UID once verification records it.

## 10.5 UI Tests

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| V1 | In the admin UI, register a hub with a namespace and kubeconfig Secret, then register an inference spoke with that hub selected and an explicit ACM name | FR-1 | The hub form requires the Secret selector. The spoke form allows submission without a Secret. The mock Connect transport receives the private service Create request with the hub ID, role, and ACM name. |
| V2 | Display a healthy registered MaaS Hub and unlinked spoke | FR-2 | Hub detail shows `HubReachable=True`; spoke detail indicates the pending MaaS Hub selection |
| V3 | Condition reason displayed for issues | FR-4 | Available=False reason and message shown |
| V4 | Render the ExternalCluster UI as a Tenant Admin and as a Tenant User | FR-3 | Both roles lack navigation or controls for ExternalClusters. E9 verifies authorization on the deployed private service. |

## 10.6 Security and Isolation Tests

Use the internal private endpoint to exercise Create, List, Get, and
Update as CPAs, Tenant Admins, and Tenant Users. These cases verify the
private authorization boundary independently of the external routing check
in A5.

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| S1 | CPA can create ExternalCluster | FR-1 | Create succeeds |
| S2 | CPA can list ExternalClusters | FR-2, FR-3 | List succeeds |
| S3 | Tenant Admin cannot create ExternalCluster | FR-3 | PermissionDenied |
| S4 | Tenant Admin cannot list ExternalClusters | FR-3 | PermissionDenied |
| S5 | Tenant User cannot list ExternalClusters | FR-3 | PermissionDenied |
| S6 | Tenant User cannot get ExternalCluster by ID | FR-3 | PermissionDenied |
| S7 | Unauthenticated List request rejected | FR-3 | Unauthenticated |
| S8 | CPA can get an existing ExternalCluster by ID | FR-3 | Get succeeds |
| S9 | CPA can update a mutable field on an existing ExternalCluster | FR-3 | Update succeeds |
| S10 | Tenant Admin cannot get an ExternalCluster by ID | FR-3 | PermissionDenied |
| S11 | Tenant Admin cannot update an ExternalCluster | FR-3 | PermissionDenied |
| S12 | Tenant User cannot create an ExternalCluster | FR-3 | PermissionDenied |
| S13 | Tenant User cannot update an ExternalCluster | FR-3 | PermissionDenied |

## 10.7 Capability and Placement Tests

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| C1 | Register hub-only, spoke-only, and dual-type records with the corresponding role configurations. Supply a kubeconfig Secret for records that include the MaaS Hub type. | FR-1 | Each configuration persists its declared `cluster_types`; a spoke-only record succeeds without a Secret. |
| C2 | Register with defined but unsupported `CLUSTER_TYPE_VMAAS` or `CLUSTER_TYPE_CLAAS` | FR-1 | Both requests return `InvalidArgument` |
| C3 | List by MaaS Hub `maas-east`, spoke type, and inference or combined role | FR-5 | Excludes hub-only records, ingress-only spokes, unlinked spokes, and spokes on `maas-west` |
| C4 | Placement filters by Available=True | FR-5 | Unavailable clusters excluded |

## 10.8 Hub Identity and Watch Tests

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| H1 | Register a MaaS Hub and spoke with `source_hub` set to the existing OSAC Hub identifier | FR-1 | Source Hub reference resolves locally. The selected MaaS Hub and its credential govern ACM observation. |
| H2 | A spoke named `inference-east` sets override `ai-worker-01`. The selected MaaS Hub first emits a ManagedCluster add event for `inference-east` and then for healthy `ai-worker-01`. | FR-2 | The first event leaves the spoke at `ManagedClusterNotFound`. The second event sets `Available=True` before periodic re-validation. |
| H3 | Controller watch receives ManagedCluster delete event | — | Available=False, reason ManagedClusterNotFound |
| H4 | Restore `maas-east` after a watch outage with `maas-west` healthy throughout | FR-2 | East records refresh after relist and sync. West's watch remains active and its records remain available. |
| H5 | managed_cluster_uid immutability enforced | — | UID change sets Available=False with reason ClusterIdentityMismatch; the recorded UID is retained |

## 10.9 Credential Tests

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| K1 | MaaS Hub has a valid scoped kubeconfig Secret and its source OSAC Hub lacks ACM. Create one linked spoke without a Secret and another with a provider-scoped kubeconfig Secret whose credentials cannot read ManagedClusters. | FR-1, FR-2 | Both spokes reach `Available=True` through the selected MaaS Hub's watch. |
| K2 | MaaS Hub credential becomes unresolvable after registration; another MaaS Hub stays healthy | FR-4 | Affected hub and linked spokes report `HubUnreachable`. Unrelated registrations remain available. Restoring the Secret and re-validating refreshes conditions. |
| K3 | MaaS Hub credential cannot authenticate or lacks ManagedCluster list/watch permissions | FR-4 | Affected hub and spokes report `HubUnreachable`. The message identifies the failure category without exposing credentials. |
| K4 | Create ExternalCluster while Hub credential is invalid, then fix credential when the Hub has an accepted, available ManagedCluster with a non-empty `id.k8s.io` claim | FR-4 | Create RPC succeeds (local validation only). Registration-triggered reconciliation sets HubReachable=False and Available=False (HubUnreachable) — informer cache not consulted, ManagedClusterNotFound never reported. After rotating the MaaS Hub Secret, periodic re-validation or restart sets Available=True and records the first UID only after all validation succeeds |

## 10.10 Direct OCM Compatibility Tests

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| O1 | ManagedCluster v1 API available on Hub | — | Watch established, conditions reconcile |
| O2 | Reachable, synchronized Hub has a ManagedCluster with HubAcceptedManagedCluster=True, ManagedClusterConditionAvailable=True, and a non-empty `id.k8s.io` claim | FR-1 | After all validation succeeds, Available=True and the first `managed_cluster_uid` is recorded |
| O3 | Reachable, synchronized Hub has a ManagedCluster with HubAcceptedManagedCluster=True, ManagedClusterConditionAvailable=True, and a non-empty `id.k8s.io` claim; verify the first UID write follows successful validation | — | Available=True and `managed_cluster_uid` equals the claim value |
| O4 | Test both missing and empty `id.k8s.io` claims before and after a UID has been recorded | — | In both variants, `Available=False` with reason `ClusterIdentityMissing` and `HubReachable=True`. Before the first valid claim, `managed_cluster_uid` stays empty; after a UID has been recorded, missing or empty claims retain it. When the claim returns, a matching UID allows normal condition evaluation and a different UID yields `ClusterIdentityMismatch`. |

## 10.11 External Registration and Scope Tests

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| R1 | Register a MaaS Hub and an externally prepared spoke | FR-1 | ExternalCluster records appear in OSAC. No provisioning job is dispatched. |
| R2 | No CRD created on target cluster or operator | FR-1 | Verify no CRD side effects |
| R3 | Review the documented mapping and site scope | — | Each linked spoke maps to one ManagedCluster on its selected MaaS Hub. The API exposes no site aggregate. |

## 10.12 Logging Redaction Tests

| # | Scenario | Expected Behavior |
|---|---|---|
| L1 | Registration success — log contains only allowed fields | external_cluster_id, cluster_types, condition, component, operation, request_id; no denied fields |
| L2 | Registration failure — log redacts denied fields | Reason code present; no ManagedCluster name, Hub URL, credentials, stack trace |
| L3 | Hub watch error — log redacts denied fields | Error category present; no internal addresses, bearer tokens |
| L4 | Controller unit test checks each condition reason and structured log field on a simulated credential failure | Opaque record ID and allow-listed fields only; credential material and raw request or response bodies absent |

## 10.13 Failure Tests

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| F1 | Hub unreachable during registration | FR-4 | Available=False, HubReachable=False |
| F2 | Hub recovers after outage | — | Available condition updates via watch |
| F3 | Controller restart mid-reconciliation | FR-4 | Resumes from database state; no duplicate records |
| F4 | Database unavailable during Create | FR-4 | Returns Internal error; no partial state |
| F5 | Race two Creates with the same `metadata.name` in the `shared` tenant. Run one variant with a MaaS Hub and an unlinked spoke, and another with two spokes linked to different MaaS Hubs. | FR-4 | In each variant, one Create succeeds and the other returns `AlreadyExists`. List shows exactly one ExternalCluster with that name. |
| F6 | Create during Hub credential failure (Hub readiness gate) | FR-4 | Create succeeds locally; reconciliation sets HubUnreachable, never ManagedClusterNotFound; recovery restores accurate conditions |

## 10.14 Integration-Test Planning Evidence Matrix

The matrix follows the [integration testing planning
guidance](https://github.com/osac-project/osac/blob/main/docs/INTEGRATION-TESTING.md#planning-evidence).
Each row identifies the owning component, required tier,
real and simulated dependencies, and follow-up gaps. Every row describes
planned work. The proposed fixtures, specs, and deployment commands have not
been run.

| Component | Behavior / Boundary | Required Tier | DEV/QE Owner | Case IDs / Suite Location | Command / Prerequisites | Real Dependencies | Simulated / Mocked Dependencies | Follow-up Gaps |
|---|---|---|---|---|---|---|---|---|
| fulfillment-service | Create RPC validation, including conditional Secret references, ExternalCluster and ACM identities, and cluster types, plus identity immutability | Unit | [DEV] [OSAC-6916](https://redhat.atlassian.net/browse/OSAC-6916) | U1–U11, U13–U14, U20–U22, U25–U26, C1–C2, H1 / `fulfillment-service/internal/servers/` (Ginkgo) | From `fulfillment-service/`: `ginkgo run --timeout 10m internal/servers` | None | DAO mocked; Hub client mocked | U6 tests DAO conflict-to-AlreadyExists mapping. I9 and F5 test the real database constraints. |
| fulfillment-service | Private Delete denial (IC-4) | Unit | [DEV] [OSAC-6916](https://redhat.atlassian.net/browse/OSAC-6916) | U12 / `fulfillment-service/internal/auth/` | From `fulfillment-service/`: `ginkgo run --timeout 20m -r internal` | In-process authorization interceptor and Rego policy | CPA identity supplied by the fixture. No network listener. | E7 checks the private RPC against a deployed server. |
| fulfillment-service | Label and role Update validation (IC-3) | Unit | [DEV] [OSAC-6916](https://redhat.atlassian.net/browse/OSAC-6916) | U19 / `fulfillment-service/internal/servers/` | From `fulfillment-service/`: `ginkgo run --timeout 10m internal/servers` | No external services | DAO and dependencies mocked | I18 verifies deployed persistence. |
| fulfillment-service | Persist a role, namespace, or hub-binding Update (IC-3) | Component integration | [DEV] [OSAC-6916](https://redhat.atlassian.net/browse/OSAC-6916) | I18, I21–I22 / `fulfillment-service/it/` | Fulfillment Kind target below. For I21, use the two test-Hub fixture and the same starting metadata.version on both writes. For I22, pre-register a spoke with the target ManagedCluster name. | Deployed Fulfillment, PostgreSQL, and separate test-Hub APIs for I21–I22 | No ACM controller. I18 asserts against persisted data without using Hub APIs. | Proposed test-Hub fixture is owned by OSAC-6917. |
| fulfillment-service CLI | Private create/edit CLI request construction and error rendering | Unit | [DEV] [OSAC-6918](https://redhat.atlassian.net/browse/OSAC-6918) | CL1–CL3 / `fulfillment-service/internal/cmd/cli/` | From `fulfillment-service/`: `ginkgo run --timeout 20m -r internal` | None | Private ExternalClusters gRPC client is fake | — |
| fulfillment-service | Registration-triggered reconciliation and Hub readiness gate | Unit | [DEV] [OSAC-6917](https://redhat.atlassian.net/browse/OSAC-6917) | U15–U18, U23–U24 / `fulfillment-service/internal/controllers/` (Ginkgo) | From `fulfillment-service/`: `ginkgo run --timeout 20m -r internal` | None | Informer cache and DAO mocked | These tests cover controller-side handling only; the Kind component suite exercises real list/watch behavior. |
| fulfillment-service | Controller watch, cache sync, authentication, condition transitions, startup reconciliation, OCM claim validation | Component integration | [DEV] [OSAC-6917](https://redhat.atlassian.net/browse/OSAC-6917) | I1–I8, I11–I17, I19–I20, H2–H5, K1–K4, O1–O4, F1–F3, F6 / `fulfillment-service/it/` | From the repo root, install the Kind test environment with `make -C osac-installer install-infra PLATFORM=kind PROFILE=dev NS=osac`, then run the proposed MaaS-enabled variant of `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment`. The suite needs a MaaS-enabled fulfillment deployment phase and isolated test-Hub provisioning | Deployed Fulfillment, PostgreSQL, Keycloak, and two separate Kind test-Hub Kubernetes API servers | **Proposed test fixture:** install the ManagedCluster CRD on two standalone Kind clusters and register them through distinct scoped kubeconfig Secrets on MaaS Hub ExternalClusters. The servers handle real list/watch, authentication, cache sync, and reconnects. The OSAC Hub fixture has no OCM CRD. Interrupt east's API independently of the OSAC deployment and west's watch. Fixture objects stand in for ACM-managed state, and no ACM controller is present. | OSAC-6917 owns the fixture. Live ACM compatibility remains E2E coverage under OSAC-6920; no ACM Hub is provisioned in CI. |
| fulfillment-service | Database uniqueness for ExternalCluster names in `shared` and for per-hub ACM identities, List filters, and query metadata | Component integration | [DEV] [OSAC-6916](https://redhat.atlassian.net/browse/OSAC-6916) | I9–I10, C3–C4, F5 / `fulfillment-service/it/` | Fulfillment Kind target above. Seed MaaS Hub records for linked-spoke requests. Use fixed fixture timestamps for deterministic freshness assertions. | Deployed Fulfillment and PostgreSQL | No Hub API or Praxis consumer; conditions and timestamps are fixture data | Consumer-side stale-record exclusion, live routing, and tenant-to-cluster assignment remain deferred to the cross-workload design. |
| fulfillment-service | Private REST/gRPC, public routing exclusion, and CPA-only authorization | Component integration | [DEV] [OSAC-6916](https://redhat.atlassian.net/browse/OSAC-6916) | A1–A6, S1–S13, F4 / `fulfillment-service/it/` | Fulfillment Kind target above. Use the internal endpoints and test A5 against the deployed external listener. For A6, use the proposed Kind test-Hub fixture and wait for the controller to verify a spoke. | Deployed Fulfillment, PostgreSQL, Keycloak, internal REST gateway, external API listener, and the Kind test-Hub API for A6 | A6 uses fixture ManagedClusters and a real watch. No ACM controller runs in Kind. | The MaaS test phase must reach both listeners. |
| fulfillment-service | Controller redaction on credential failure (IC-1, IC-2) | Unit | [DEV] [OSAC-6917](https://redhat.atlassian.net/browse/OSAC-6917) | L4 / `fulfillment-service/internal/controllers/` | From `fulfillment-service/`: `ginkgo run --timeout 20m -r internal` | No external services | Secret resolver and watcher are mocked | The component-integration row checks real deployed logs. |
| fulfillment-service | Logging redaction | Component integration | [DEV] [OSAC-6917](https://redhat.atlassian.net/browse/OSAC-6917) | L1–L3 / `fulfillment-service/it/` | Fulfillment Kind target above and capture service logs for success and failing watch cases | Deployed Fulfillment and PostgreSQL for integration | Hub state is fixture-driven; no real ACM controller | — |
| fulfillment-service | Credential lifecycle and freshness timestamps | Component integration | [DEV] [OSAC-6917](https://redhat.atlassian.net/browse/OSAC-6917) | I16–I17, K1–K4 / `fulfillment-service/it/` | Fulfillment Kind target above | Deployed Fulfillment, PostgreSQL, Kind Kubernetes API server | Test Hub ServiceAccount credentials and ManagedCluster fixtures; no ACM controller | Staleness threshold interaction with Praxis remains deferred. |
| Documentation | Document 1:1 registration mapping and deferred aggregate/site behavior | Docs review | [DOCS] [OSAC-6921](https://redhat.atlassian.net/browse/OSAC-6921) | R3 / ExternalCluster user and API documentation | Review the user-facing/API docs with the docs task | Documentation only | No runtime dependencies | — |
| tests/e2e | Register, verify, CPA-only access, duplicate detection, and filtered List query | E2E | [QE] [OSAC-6920](https://redhat.atlassian.net/browse/OSAC-6920) | E1–E8 / proposed `tests/e2e/maas/test_external_cluster.py` | Proposed from OSAC root: `uv run pytest -n 0 tests/e2e/maas/test_external_cluster.py`. Provision MaaS-enabled OSAC and live ACM fixtures in an isolated test deployment. | Deployed OSAC stack, PostgreSQL, live MaaS ACM hubs with ManagedClusters | None — all dependencies real | OSAC-6920 owns the cases; live Hub environment and access owner remain unresolved. |
| tests/e2e | Verify registration causes no target-cluster provisioning side effects | E2E | [QE] [OSAC-6920](https://redhat.atlassian.net/browse/OSAC-6920) | R1–R2 / same proposed MaaS suite as E1–E8 | Run the proposed command above and inspect the target cluster and OSAC operator API/CRD inventory | Deployed OSAC stack, PostgreSQL, live ACM Hub with the registered target ManagedCluster, target-cluster API access, and OSAC operator API access | None — all dependencies real | OSAC-6920 owns the cases; live Hub and target-cluster access owners remain unresolved. |
| tests/e2e | Tenant-to-cluster assignment and placement isolation | E2E | [QE] | Deferred | Deferred to future cross-workload design | — | — | Tenant-specific cluster assignment, dedicated infrastructure, and placement isolation E2E: deferred until cross-workload tenant-to-cluster model is designed. Owner: Praxis/MaaS team. |
| UI | Registration form, condition display, failure display, and role-dependent views | Unit | [UI] [OSAC-6919](https://redhat.atlassian.net/browse/OSAC-6919) | V1–V4 / proposed tests alongside `osac-ui/apps/app-frontend/src/` components | From `osac-ui/`: `pnpm test` | React components and app test runner | Connect responses from the private service use `createMockConnectTransport`; no deployed service or browser E2E | OSAC-6919 tracks the UI work and needs an API baseline that includes the private descriptors. E9 covers the deployed browser/API boundary. |
| osac-ui | CPA registration and status through deployed browser, and tenant denial (IC-6) | E2E | [QE] owner unresolved | E9 / proposed spec under `osac-ui/apps/e2e-tests/src/generic/` and proposed `maas-external-clusters` Playwright project | Proposed from `osac-ui/`: `pnpm playwright --project=maas-external-clusters`. Seed a live MaaS Hub and spoke in ACM and set `OSAC_UI_BASE_URL` with CPA and tenant test identities. Include the private service descriptors in the deployed UI API baseline. | Browser, deployed UI and Connect proxy, Keycloak, private Fulfillment service, PostgreSQL, and live MaaS ACM Hub | None | The Playwright harness and private Connect transport exist. The MaaS project, live environment, and QE owner for E9 are unresolved. |

**Limitations and honest disclosures:**

- **Kind test Hub limitation.** Two real Kubernetes API servers exercise
  per-hub list/watch, permissions, cache sync, and reconnect. The suite
  writes OCM fixture objects and claims directly. Live ACM reconciliation
  is covered by the proposed E2E cases.
- **No ACM Hub in CI:** The E2E environment does not currently provision a
  live ACM Hub. OSAC-6920 owns E1–E8 and the live-Hub environment prerequisite.
- **Proposed commands and locations:** Test file paths and commands
  marked "proposed" do not yet exist. They represent the intended
  location following existing fulfillment-service conventions.
- **UI browser coverage.** V1–V4 use the mock Connect transport.
  E9 uses the existing Playwright harness with a proposed MaaS project.
- **Praxis placement E2E:** Tenant-to-cluster assignment, dedicated
  infrastructure, placement isolation, and consumer-side stale-record
  exclusion are deferred to the future cross-workload design. The proposed E8
  test is intended to verify that List returns role, availability, and
  freshness metadata; it does not prove executed coverage until the test
  exists and runs.

## 10.15 E2E Tests

**Location:** `tests/e2e/` (pytest via osac-test-infra)

| # | Scenario | Requirement | Expected Behavior |
|---|---|---|---|
| E1 | Use the deployed private API to register a live MaaS ACM Hub outside an OSAC Hub without ACM. Import an accepted and available ManagedCluster with a non-empty `id.k8s.io` claim as a spoke using its ACM name as the registration name. Omit the spoke Secret and name override. | FR-1, FR-2 | Hub record becomes `HubReachable=True`. Spoke Create returns `Available=Unknown`. Bounded polling of Get observes `Available=True` and confirms that the selected MaaS Hub ID differs from the OSAC Hub reference. |
| E2 | Log in with `osac login --private` as a CPA and run `osac get external-cluster` | FR-2 | The spoke appears in the list with its availability status. |
| E3 | With the private CPA session, run `osac describe external-cluster <id>` | FR-2 | Displays the spoke’s conditions, spec, and metadata. |
| E4 | Create two separately named spokes that use the same ACM name override. Link one to a MaaS Hub where the named ManagedCluster is absent but exists on another hub. Leave the other unlinked. | FR-4 | The linked request becomes `Available=False` with `ManagedClusterNotFound` on the selected hub. The unlinked request reports `MaasHubUnassigned`. |
| E5 | As Tenant Admin and Tenant User, call ExternalClusters on the internal private API | FR-3 | Both roles receive `PermissionDenied`. |
| E6 | Register same cluster twice | FR-4 | AlreadyExists |
| E7 | Call the private Delete RPC as a CPA | — | Fulfillment’s explicit ExternalCluster Delete denial returns `PermissionDenied` (see IC-4). |
| E8 | List available inference and combined spokes on the registered MaaS Hub | FR-5 | Returns matching spokes with `last_observed_time`. Excludes ingress-only and hub-only records and other MaaS Hubs. No consumer-side age threshold is tested. |
| E9 | As a CPA, register a MaaS Hub and inference spoke in the deployed admin UI. Supply an ACM name override and omit the spoke Secret. Verify the browser calls the private Connect service. With a tenant session, attempt direct navigation and invoke the same private service through Connect. | FR-1, FR-2, FR-3 | The hub is offered in the selector and the spoke becomes `Available=True`. Private Get shows the selected hub ID, name override, and absent Secret reference. The tenant receives no registration data and the private Connect call returns `PermissionDenied`. |

**E2E infrastructure requirement:** OSAC with MaaS enabled, an OSAC Hub
without ACM, and a distinct live ACM Hub with a registered ManagedCluster.
E4's wrong-hub path needs a second ACM Hub with the fixture cluster. Use an
isolated test deployment because Delete is deferred. The run owns the
environment and tears it down after the cases finish.

## 10.16 Decomposition Traceability Addendum

The crosswalk identifies the tests that exercise each interface and their
remaining execution prerequisites.

### Interface Change → Test Case Crosswalk

| Interface Change | Test cases in this plan | Coverage notes |
|-----------------|-------------------------|----------------|
| IC-1: Create/Register RPC | U1–U7, U20–U22, U25–U26, A1, A4–A5, S1, S3, S12, I1, I9, I11, I19, F5, E1, E6, R1, R2 | Covers ExternalCluster name uniqueness in `shared`, the per-hub ACM identity, name override and fallback, and type-specific Secret validation. R1/R2 verify registration has no provisioning or target/operator CRD side effects. |
| IC-2: Get/List RPCs | U10–U11, A2–A3, A5–A6, S2, S4–S6, S8, S10, E2–E5, E8 | Includes CPA-only visibility, hub, role, and condition filters, and exposure of observation timestamps. |
| IC-3: Update RPC | U8–U9, U13, U19, I18, I20–I22, S9, S11, S13 | Covers immutable identity, first hub assignment and its uniqueness checks, concurrent assignment, role and namespace persistence, and CPA-only Update authorization. |
| IC-4: Delete RPC — Deferred | U12, E7 | Verifies Delete remains denied; it does not implement disconnect. |
| IC-5: CLI commands | CL1–CL3, E2–E3 | Unit tests cover private create/edit requests and error rendering. Deployed tests cover get and describe in private mode. |
| IC-6: UI registration/status views | V1–V4, E9 | E9 uses the existing private Connect transport. It needs the API baseline, Playwright project, live environment, and QE owner. |
| IC-7: MaaS placement query data foundation | I10, C1, C3–C4, E8 | These cases verify hub, type, role, and Available filters and expose freshness timestamps; they do not test consumer-side stale-record exclusion, workload routing, or tenant isolation. |

### External Registration Test Planning Evidence

| Component | Behavior / Boundary | Required Tier | Owner | Cases / Location | Command / Prerequisites | Real Dependencies | Simulated / Mocked Dependencies | Gap |
|---|---|---|---|---|---|---|---|---|
| tests/e2e | R1: external registration creates only the OSAC ExternalCluster and triggers no provisioning | E2E | [QE] [OSAC-6920](https://redhat.atlassian.net/browse/OSAC-6920) | R1 / proposed `tests/e2e/maas/test_external_cluster.py` | Proposed: `uv run pytest -n 0 tests/e2e/maas/test_external_cluster.py` from repository root; deployed OSAC and a registered ManagedCluster | OSAC API, database, controller, ACM Hub; inspect provisioning/API state | None | OSAC-6920 owns R1/R2; the proposed test file, live Hub environment, and Hub access owner remain unresolved. |
| tests/e2e | R2: no target-cluster or OSAC-operator CRD side effects | E2E | [QE] [OSAC-6920](https://redhat.atlassian.net/browse/OSAC-6920) | R2 / proposed `tests/e2e/maas/test_external_cluster.py` | Proposed: same command and root working directory; requires access to the target ManagedCluster and OSAC operator API | OSAC operator and target cluster API, plus live ACM Hub | None | OSAC-6920 owns R1/R2; test file, target-cluster/OSAC-operator access, and live Hub environment remain unresolved. |
| Documentation | R3: document one-to-one linked spoke/ManagedCluster mapping and no site aggregation | Documentation review | [DOCS] [OSAC-6921](https://redhat.atlassian.net/browse/OSAC-6921) | R3 / user-facing API and admin documentation | No test command; review the published documentation against the selected MaaS Hub and one-to-one spoke mapping | Published documentation | Not applicable | Covered by documentation task OSAC-6921. |
