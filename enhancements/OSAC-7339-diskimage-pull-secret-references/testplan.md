# Testplan — OSAC-7339

## Overview

- **Feature:** OSAC-7339 — DiskImage Pull-Secret References.
- **Status:** Review draft dated 2026-11-12; §9.1 PROPOSED (VMaaS confirms CDI wiring). Former §9.2 content-refresh open question closed: live contents when source exists; safety copy only if deleted. Not implementation-ready. No planned feature tests executed.
- **Total test cases:** 20.
- **Requirements covered:** 8 of 9 LOCAL requirements have behavioral cases; L9 requires the separate editorial review recorded under Gaps.
- **Interface changes covered:** 6 of 7; IC-7 documentation review is not a behavioral test.
- **Source:** merged [PRD](prd.md), [design](design.md), and
  [workflow](assets/workflow.mmd). L1–L9 are local review IDs mapped from
  PRD In Scope, not PRD FR/NFR labels.

## Test Case Index

| ID | Scenario | IC | Priority |
|---|---|---|---|
| TC-L1-01 | API configure/change/clear | IC-1 | critical |
| TC-L1-02 | CLI reference lifecycle | IC-1 | high |
| TC-L1-03 | UI reference lifecycle | IC-1 | high |
| TC-L2-01 | Reject invalid or unauthorized references | IC-1 | critical |
| TC-L3-01 | Complete-secret selection without supplementation | IC-2, IC-5 | critical |
| TC-L3-02 | Empty selection supplies no credential | IC-2 | medium |
| TC-L4-01 | Create before provisioning and mutate source | IC-2 | critical |
| TC-L4-02 | Concurrent image patch/delete versus create | IC-2, IC-4 | critical |
| TC-L4-03 | Existing secret-content update compatibility | IC-2, IC-5 | high |
| TC-L4-04 | Live contents vs safety copy on retry | IC-2, IC-5 | critical |
| TC-L5-01 | Protected provider image inheritance | IC-3, IC-5 | critical |
| TC-L5-02 | Identity/presence oracle and explicit reuse denial | IC-3 | critical |
| TC-L5-03 | Provisioner transport confidentiality | IC-5, IC-6 | critical |
| TC-L6-01 | Tenant reference redaction and masked update | IC-1, IC-3 | high |
| TC-L7-01 | Independent active-image deletion guards | IC-4 | critical |
| TC-L7-02 | Failed deletion/server-owned marking | IC-4 | critical |
| TC-L8-01 | Create versus source deletion | IC-2, IC-4 | critical |
| TC-L8-02 | Retained credential survives import retry | IC-2, IC-5, IC-6 | critical |
| TC-L8-03 | Success releases acquisition retention | IC-4, IC-5 | critical |
| TC-L8-04 | Worker recovery and population-complete cleanup | IC-4, IC-5 | high |

## Test Cases

The planned tiers and harnesses for each ID are mandatory in the evidence matrix below. In API-only cases provider behavior is omitted, not implied passing. Race tests use explicit barriers at actual request/transaction boundaries and bounded request completion under the suite timeout; no sleep-based scheduling or fallback reconciliation is accepted as evidence. For deployed cases wait on the documented public provisioning terminal condition within the environment's configured provisioning timeout; that timeout and supported runtime must be recorded before execution. No PRD latency target is invented.

### L1: Authorized DiskImage configuration via API/CLI/UI

##### Shared Preconditions

- Provider and tenant admin identities, permitted typed pull secrets A/B and image-write authority; retain a separate no-write identity. Existing APIs run against real PostgreSQL; UI/CLI use authenticated public APIs.

#### TC-L1-01: API configure/change/clear

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1 | critical | automated |

##### Steps
1. Create provider and tenant DiskImages with A through the public API and read back as authorized admins.
2. Patch to B, then explicitly clear using the update mask; read after each action.
3. Repeat a write as the no-write identity.

##### Expected Results
- Authorized reads return A, then B, then an absent reference; denied write returns PermissionDenied and does not change the authorized readback.

#### TC-L1-02: CLI reference lifecycle

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1 | high | automated |

**Steps:** 1. Run the implemented documented configure/change/clear CLI operations against a permitted tenant image. → 2. Read after each operation using structured and normal output.
**Expected:** Both formats show the authorized current reference or its explicit absence after clear, matching API readback.

#### TC-L1-03: UI reference lifecycle

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1 | high | automated |

**Steps:** 1. Select A, change to B, then clear in the DiskImage editor, saving each operation. → 2. Reload the editor after each save.
**Expected:** The persisted editor state matches each authorized selection and the final empty configuration.

### L2: Immediate existence/type/authority validation

#### TC-L2-01: Reject invalid or unauthorized references

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1 | critical | automated |

##### Preconditions
- Authorized image writer and valid image; fixtures include opaque wrong-type secret, marked-deleting secret and foreign/protected secret. The explicit caller supplies each ID deliberately; do not discover protected IDs through the product.

##### Steps
1. Submit create and patch with malformed reference, nonexistent ID, wrong type, deleting target, foreign secret and protected explicit target.
2. Read the image through the same authorized surface after each rejection.

##### Expected Results
- Each operation rejects before accepted success: malformed references and missing/type mismatch in a caller-discoverable scope use InvalidArgument; denied explicit use and unknown/inaccessible targets in an undiscoverable scope use the proposed uniform generic PermissionDenied mapping; marked-deleting uses proposed FailedPrecondition. Existing selection is unchanged and no hidden resolved identity appears in responses. This one scenario covers all rejection categories, not separately counted parameterized rows.

### L3: One complete selected secret or no DiskImage credential

##### Shared Preconditions

- Isolated registry challenge endpoint records which test identity authenticates; credentials A and B contain disjoint registry authorization. Environment records and isolates node/default credentials so fallback cannot accidentally satisfy the image challenge.

#### TC-L3-01: Complete-secret selection without supplementation

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2, IC-5 | critical | automated |

**Steps:** 1. Provision image using A where only B can authorize the image; repeat with A authorizing it. → 2. Observe terminal provisioning and registry authentication audit without logging credential values.
**Expected:** The first attempt fails authentication without B supplementation; the second succeeds using only A's identity.

#### TC-L3-02: Empty selection supplies no credential

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2 | medium | automated |

**Steps:** 1. Create an instance from an empty-reference public image and provision it. → 2. Inspect the isolated registry authentication audit.
**Expected:** Acquisition succeeds without any DiskImage credential identity being used; no OSAC-selected-secret indicator appears in the instance response.

### L4: Creation-time selection and unchanged content-update rules

##### Shared Preconditions

- A/B authorize distinct fixture registries or distinguishable authentication principals. Pause asynchronous provisioning using a test-controlled barrier, not by delaying creation. Public instance create and actual PostgreSQL remain real.

#### TC-L4-01: Create before provisioning and mutate source

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2 | critical | automated |

##### Steps
1. Create I1 from image using A and I0 from an empty image; confirm create accepted before provisioning starts.
2. Set both images to B; create I2. Clear the source and create I3.
3. Release provisioning and observe registry authentication for each instance.

##### Expected Results
- I1 uses A, I0 remains without a selected secret, I2 uses B, and I3 remains empty; no instance exposes internal selection fields. Final acquisition outcomes distinguish selections, not private database assertions.

#### TC-L4-02: Concurrent image patch/delete versus create

Distinct from TC-L8-01: this case is DiskImage revision/delete vs create
ordering; L8-01 is Secret delete / acquisition-hold races.

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2, IC-4 | critical | automated |

**Steps:** 1. Force both commit orders for image patch versus create and server-delete marking versus create using request barriers. → 2. Provision any accepted instances and retry a later create.
**Expected:** Patch yields one complete old/new selection consistent with ordering; deletion winning rejects creation, while creation winning retains its accepted selection. No mixture or accepted unprotected acquisition occurs.

#### TC-L4-03: Existing secret-content update compatibility

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2, IC-5 | high | automated |

**Steps:** 1. Run the existing content-update contract against the selected Secret backend before and after enabling this feature, with source identity unchanged. → 2. Compare accepted updates and subsequent acquisition outcomes.
**Expected:** Existing permitted/refused updates and documented reader behavior remain identical; changing content never reselects a different source Secret. The inspected baseline writes permitted Vault updates and fetches current content; HUB fetches the current referenced object and rejects nonempty OSAC data updates. This case proves ordinary update/read compatibility; retry content vs safety-copy behavior is TC-L4-04.

#### TC-L4-04: Live contents vs safety copy on retry

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2, IC-5 | critical | automated |

##### Additional Preconditions

- Decided design policy: when the source Secret still exists, use its
  **current contents**; when it is gone, use the acquisition **safety
  copy**. Same selected Secret identity throughout (not a DiskImage
  reselection).
- Keep synthetic credentials A and B both valid at the controlled registry.
  Pause/fail the first initial-population attempt deliberately. This
  fixture controls credential validity; it does not claim real-world
  rotation always leaves A usable.

##### Steps
1. Retain safety copy A and start initial population with A; while that
   attempt is active, update the same source Secret to B via permitted
   existing methods.
2. Fail the first attempt; start the next initial attempt while the source
   still exists; observe which registry principal authenticates.
3. Repeat from a retained A, but delete the source before the next initial
   attempt; observe authentication and that retry can still complete.

##### Expected Results

| Decision point | Expected registry-observable outcome |
|---|---|
| Attempt already running with A when B is written | No automatic hot-reload of the in-flight attempt is required. Do not assert instantaneous B replacement; document any importer reread separately if observed. |
| Next initial attempt, source still exists | Uses **current contents B** of the same selected Secret; no merge; no DiskImage reselection. |
| Next initial attempt, source already deleted | Uses **safety copy A**; retry remains possible; no fallback to a different Secret. |

Once initial DataVolume population is ready, this scenario does not start
new acquisitions for VM lifetime, VM deletion, or a new post-terminal
retry feature. Observe via registry authentication and public population
outcome, not private-row assertions. (L3/L4/L8; User; PR #477)

### L5: Protected inherited use without discovery or reuse

##### Shared Preconditions

- Provider-managed image is usable by tenant identity lacking protected-secret discovery/read/select. Privileged fixtures know the source identity and recognizable synthetic credential sentinel solely for leak assertions; no real credentials enter logs.

#### TC-L5-01: Protected provider image inheritance

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3, IC-5 | critical | automated |

**Steps:** 1. Request and provision the permitted provider image as tenant. → 2. Attempt direct secret retrieval and selection with that identity.
**Expected:** VM provisioning succeeds, while secret retrieval/explicit reuse is denied; no new tenant secret permission is granted.

#### TC-L5-02: Identity/presence oracle and explicit reuse denial

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3 | critical | automated |

##### Steps
1. Compare hidden-source configured/unconfigured controls through public/private tenant get/list, filters, sort/pagination, selectors, create/update responses, CLI JSON/text and UI details.
2. Submit guessed protected IDs and nonexistent controls in the same undiscoverable scope, then trigger inherited acquisition failures.
3. Check all captured responses/output for identity, value, origin, nonempty marker and field-dependent membership differences.

##### Expected Results
- Neither identity nor inherited-secret presence is disclosed on any surface; unauthorized reuse and nonexistent controls in the same undiscoverable scope have identical generic denial codes/text; errors name no protected source. Authorized normal selections retain visibility. Timing analysis is not claimed covered by these content/membership checks.

#### TC-L5-03: Provisioner transport confidentiality

| Interface Change | Priority | Automation |
|---|---|---|
| IC-5, IC-6 | critical | automated |

**Steps:** 1. Provision and fail/retry with a synthetic protected sentinel while collecting tenant-visible objects/events and operator/AAP job inputs/artifacts under their documented access roles. → 2. Attempt tenant Secret read and pod-mount access to any staging location.
**Expected:** Tenant cannot retrieve/mount credential material or identify its source, and ordinary job records/CRs/logs contain neither sentinel nor source identity; only the authorized acquisition boundary can consume it. Supported runtime placement is prerequisite G1.

### L6: Tenant DiskImage reference visibility

#### TC-L6-01: Tenant reference redaction and masked update

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-3 | high | automated |

##### Preconditions
- Same tenant image is viewed by an authorized secret discoverer and an image editor without secret discovery; both use real API, CLI and UI.

**Steps:** 1. Read/list the image as both identities in all three surfaces; the hidden viewer changes an unrelated image property. → 2. Read as the authorized discoverer, then explicitly clear as an authorized selector.
**Expected:** Only the discoverer sees the source reference; unrelated masked update preserves it; authorized clear removes it. No hidden-value placeholder or populated flag is returned.

### L7: Independent active DiskImage deletion guards

##### Shared Preconditions

- Real PostgreSQL/server delete path; images D1/D2 reference S. Test both supported source backend classes, explicitly including HUB. No instance is needed to demonstrate image guards.

#### TC-L7-01: Independent active-image deletion guards

| Interface Change | Priority | Automation |
|---|---|---|
| IC-4 | critical | automated |

**Steps:** 1. Delete S with both images active, then after D1 alone receives committed server deletion marking. → 2. Mark D2 for deletion while holding background cleanup paused and delete S.
**Expected:** First two deletes are in-use failures; final delete succeeds before background image cleanup, including HUB-backed S. Removing one image never releases another's guard.

#### TC-L7-02: Failed deletion/server-owned marking

| Interface Change | Priority | Automation |
|---|---|---|
| IC-4 | critical | automated |

**Steps:** 1. Attempt a client-supplied deletion timestamp and a server deletion that fails/rolls back. → 2. Attempt S deletion after each and read the image lifecycle.
**Expected:** Image remains active and blocks S deletion in both cases; only successfully committed server marking releases that image's guard.

### L8: Initial-acquisition safety without VM-lifetime retention

##### Shared Preconditions

- Real API/database, controlled copy/acquisition barriers and valid registry credential. Remove image references through authorized clear/server marking when testing acquisition-only protection; otherwise image guards would mask release behavior.

#### TC-L8-01: Create versus source deletion

Distinct from TC-L4-02 (image patch/delete vs create) and TC-L4-04 (which
bytes on retry): this case is Secret delete vs create/hold/copy ordering.

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2, IC-4 | critical | automated |

##### Steps
1. While the image still references S, confirm source deletion is blocked. Race image clear against create with durable acquisition copy paused, forcing both legal image-lock orders.
2. If create wins, clear the image and attempt source deletion before and after resuming durable copy; finish initial population. If clear wins, create an empty-selection instance and delete otherwise-unreferenced S.
3. Separately use a clearly marked stale/deleting-source fixture to test defensive nonempty-create rejection; do not claim this fixture is a reachable source-delete win against an active-image guard.

##### Expected Results
- Active image blocks deletion. Create-first retains S and an uncopied hold after image clear; deletion is blocked until durable retention, then succeeds without breaking initial population. Clear-first yields an empty selected credential and permits otherwise-unreferenced deletion. The defensive stale-source fixture rejects nonempty creation; no accepted create loses retry access.

#### TC-L8-02: Retained credential survives import retry

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2, IC-5, IC-6 | critical | automated |

##### Steps
1. Accept instance, persist retained credential, clear image reference and delete S.
2. Force a first import/job failure, restart the responsible controller and retry initial acquisition without registry node-cache success masking authentication.
3. Observe final provisioning and registry audit.

##### Expected Results
- Source delete succeeds, initial retry completes using the retained selected credential, and failure/recovery messages expose no protected identity. No DiskImage reread changes selection.

#### TC-L8-03: Success releases acquisition retention

| Interface Change | Priority | Automation |
|---|---|---|
| IC-4, IC-5 | critical | automated |

**Steps:** 1. Successfully provision VM and remove all active source-image references. → 2. Delete S while VM remains alive, then restart VM from its acquired disk.
**Expected:** Source deletion succeeds without deleting VM; VM remains usable and ordinary restart from its completed disk does not need credentials for that completed population. This does not promise a general post-terminal reacquisition/retry capability. Runtime observation must establish successful population, not a mocked Ready status.

#### TC-L8-04: Worker recovery and population-complete cleanup

| Interface Change | Priority | Automation |
|---|---|---|
| IC-4, IC-5 | high | automated |

**Steps:** 1. Restart the worker after retained-object write but before acknowledgment, then let the same initial DataVolume population reach ready. → 2. Repeat completion cleanup and delete the source after other active-image guards are removed.
**Expected:** The original population completes without duplicate acquisition or lost retry material; repeated cleanup is idempotent and source deletion succeeds while the VM remains. No general cancellation, VM-deletion or post-terminal retry feature is asserted.

## Gaps

### Requirement Coverage Gaps

- L9 / IC-7: documentation-only requirement. Manual editorial review must verify UI/CLI/API examples, validation/error conventions, redaction and lifecycle against implementation; not counted as a behavioral test case.
- G1: real CDI/node-pull version, format and confidentiality placement unverified. TC-L3-01/02, TC-L5-01/03 and TC-L8-02/03 require it. Owner To be determined; impact is design §9.1 and deployed authentication/privacy proof. API library pins are not deployed-runtime evidence. No follow-up ticket assigned.
- G2: content policy decided (live contents when source exists; safety copy if deleted). TC-L4-04 expected outcomes follow that rule; TC-L8-01/02/04 still require retention-safety implementation for delete races.
- G3: all cases are planned, not existing passing feature coverage. Deployed private-registry runner command and timeout are not established in the inspected baseline; implementation/QE owners must supply these before executing G1 cases. No guessed pytest invocation substitutes for that boundary.

### Interface Change Coverage Gaps

- IC-7 uses documentation review as above. IC-1 through IC-6 have planned cases; their runtime prerequisites are not satisfied merely by API harness coverage.

### Boundary evidence matrix

Role ownership below is proposed implementation responsibility, not a named person's approval. Existing commands come from `docs/INTEGRATION-TESTING.md` and component Makefiles; new file locations are explicitly proposed.

| Cases / behavior / interfaces | Component and owner role | Required tier / actual boundary | Existing suite or proposed extension | Verified command / working directory | Real versus omitted / prerequisites |
|---|---|---|---|---|---|
| L1-01, L2-01, L6-01; IC-1/3 | fulfillment [DEV] | Component integration: authenticated APIs, database and CLI projection | Extend `fulfillment-service/it/it_disk_images_api_test.go`, `it_disk_images_tenant_isolation_test.go`, `it_metadata_test.go` | From fulfillment-service: `make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment` | Real service/PostgreSQL/Keycloak/CLI; Kind/toolchains required; provider/network readiness fixtures, no actual VM. |
| L1-02; IC-1 | fulfillment [DEV] | Contract + deployed CLI/API | Existing create/diskimage unit suite; proposed lifecycle cases in `it/` | Same deployed fulfillment command; unit `ginkgo run -r internal` from fulfillment-service | Real CLI and API for integration; unit mocks cannot establish authority. New clear/change syntax implementation required. |
| L2-01, L4-02, L7-01/02, L8-01/04; IC-1/2/4 | fulfillment [DEV] | Component integration: request transactions and actual PostgreSQL lock/delete paths | Proposed tests in `internal/servers` and `internal/database/migrations`; extend real DiskImage API suite for public outcomes | `go test ./internal/servers ./internal/database/migrations -timeout 20m` from fulfillment-service | Real PostgreSQL test container, backend failure injection for rollback; provider omitted. Transaction barriers required; no mock DAO race proof. |
| L5-02, L6-01; IC-1/3 | fulfillment [DEV] | Contract and authenticated API projection/filter boundary | Extend `it_metadata_test.go` and DiskImage isolation suite | Deployed fulfillment command above | Real public/private request auth and DB; protected fixture identities synthetic; provider omitted. |
| L1-03, L5-02, L6-01; IC-1/3 | UI [DEV] | UI component workflow plus authenticated API integration | Existing `osac-ui/apps/e2e-tests/src/vmaas/create.disk_images.spec.ts` extension | Runner command not verified; unresolved G3, do not invent one | A mocked UI fixture proves rendering only; real API variant required for server redaction. UI dependencies/identity setup needed. |
| L3-01/02, L4-01/03/04, L5-01/03, L8-02/03; IC-2/3/5/6 | cross-component [QE] | Deployed E2E: fulfillment → operator → AAP → CDI → registry → usable VM | Proposed extension under existing `tests/e2e/vmaas/`; runtime auth cases not found | Deployed runner command unresolved G1/G3 | All components, storage, node pull and registry real; isolate accidental cache/fallback authentication. Record CDI distribution/version and provisioning timeout. L4-04 expects live B when source exists, safety copy A when deleted (G2 decided). |
| L8-02/04; IC-5/6 | operator [DEV] | Envtest: real API server/controller lifecycle; provider acknowledgment simulated | Proposed acquisition-handoff tests under existing operator controller test suites | `make test` from osac-operator | Real envtest API server, fake AAP/CDI; validates restart/idempotency only, never actual registry acquisition. |
| L5-03, L8-02/04; IC-5/6 | AAP [DEV] | Unit/isolated role: rendered transport and sanitized failure paths | Proposed extension under `osac-aap/tests/unit` | `make test` from osac-aap | Real role rendering with mocked Kubernetes/AAP dependencies; does not prove target RBAC or node-pull credentials. |

All matrix case shorthand `Lx-yy` denotes `TC-Lx-yy`. For asynchronous races, force each ordering and require both requests to terminate within the documented server/database suite timeout; deployed acquisition pass/fail uses actual registry audit plus public terminal outcome within the recorded provisioning timeout, never periodic-resync coincidence.

## Summary

| Metric | Count |
|---|---|
| Total test cases | 20 |
| Critical | 14 |
| High | 5 |
| Medium | 1 |
| Low | 0 |
| Automated (planned) | 20 |
| Manual behavioral cases | 0 |
| Requirements with test cases | 8 / 9 LOCAL |
| Interface changes with test cases | 6 / 7 |
| Executed feature cases | 0 |
