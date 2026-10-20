# Testplan — OSAC-6040

## Overview

- **Feature:** [OSAC-6037](https://redhat.atlassian.net/browse/OSAC-6037) — Storage API integration for ComputeInstance volume lifecycle management.
- **Design:** [design.md](design.md), Volume API record IDs correlated through DataVolume annotations while the existing AAP/CDI/vendor CSI physical disk path remains in place.
- **Total planned cases:** 11.
- **Requirements covered:** backend creation, deletion and status/API visibility have planned cases. UI display remains separate design and work.
- **Interface changes covered:** all five active interface changes (IC-1, IC-3, IC-4, IC-5 and IC-6).
- **Execution:** No implementation tests or cluster experiments were run for this revision. Planned cases are not claims of existing assertions or passing coverage.
- **Baseline:** OSAC 0034f1eb6; [merged PRD at its pinned revision](https://github.com/osac-project/enhancement-proposals/blob/3da4e31a12a626f0571a42f076c89333c11a3e01/enhancements/OSAC-6037-storage-api-volume-lifecycle/prd.md).

The PRD has no FR/NFR identifiers. C, D, V and P below are local test-ID aliases for its actual In Scope and Dependencies bullets, not new published requirements. UI visibility is owned by separate design and work. This plan tests stable named requests to the Volume API, caller recovery of committed records after lost responses, persisted ComputeInstance IDs, the AAP annotation handoff and confirmed Volume-record removal after existing workload cleanup. Existing AAP/operator completion is the accepted acknowledgment; production PVC/PV/backend cleanup verification and manual-recovery behavior are outside this feature. Volume API implementation changes, new server-side idempotency guarantees and Storage-side status tracking are also outside scope. Implementation may start against the record-only contract, but every feature implementation PR remains unmerged until TC-P-02 qualifies Create/Delete with active controllers, including LVMS compatibility. Missing, skipped, unexecuted or failing qualification blocks merge. TC-C-06 remains an explicit recovery release gate; mocked recovery or existing uniqueness code alone cannot satisfy it. [User]

| Local alias | Actual source | Design/interface mapping | Planned cases |
|-------------|---------------|--------------------------|---------------|
| C | In Scope — create a Storage API Volume record for each boot/additional disk and retain its ID from provisioning; user clarification — stable names and lost-response recovery | Sections 4.1–4.6; IC-1, IC-3 and IC-4 | TC-C-01, TC-C-02, TC-C-05, TC-C-06, TC-P-02 |
| D | In Scope — delete all associated Volumes through Storage API; user clarification — consume existing workload completion, resolve registrations and confirm record absence before parent archival | Sections 4.1–4.3, 4.6–4.7; IC-5 and IC-6 | TC-D-01–03, TC-C-06, TC-P-02 |
| V | In Scope — IDs in ComputeInstance status and UI | Backend status/API: Sections 4.2–4.3; IC-4. UI coverage is separate. | TC-V-01 |
| P | Dependencies — private Storage Create/List/Get/Delete; user clarification — record-only qualification before merge; no separate attach/detach prerequisite | Sections 4.1, 4.3, 4.7 and 8; IC-3 and IC-5 | TC-P-01, TC-P-02, TC-C-06 |
| Compatibility | Existing ComputeInstances and existing AAP physical disk flow | Sections 4.1 and 8; IC-1, IC-3, IC-5 and IC-6 | TC-C-02, TC-P-02, TC-S-01 |

## Planning evidence and ownership

Unit, Envtest, component integration and Contract cases belong to DEV implementation work. Deployed cross-component user journeys belong to QE. No implementation or QE Tasks were created by this revision. The feature's UI display requirement is outside this design and plan.

Commands identify existing documented runners or explicitly proposed invocations from the listed working directories. Proposed assertions and test files do not exist yet. Existing runner availability does not mean a new case already runs. VMaaS DEV owns TC-P-02's fixture and qualification evidence; Storage owns validating or providing record-only behavior and any separate API/reconciler/backend changes.

### Merge qualification

Implementation can proceed immediately against the record-only contract. Before any feature implementation PR merges, attach passing TC-P-02 evidence for the candidate commits/images and every supported backend, including LVMS: the exact command, nonzero executed case count, backend/configuration matrix, API results, reconciliation/restart trace and provider-operation observations. A missing fixture, unavailable environment, skipped backend, empty selection, unexecuted test or failed assertion keeps the PR unmerged. Green H1–H5 results alone do not satisfy this gate. Reviewers enforce this prerequisite until a required CI check is wired; existing CI enforcement is not claimed by this plan. [User]

### Harness registry

| Harness | Existing evidence / planned extension | Command and working directory | Prerequisites and real/fake boundary | Execution readiness |
|---------|---------------------------------------|-------------------------------|--------------------------------------|---------------------|
| H1 — Fulfillment server/database | Existing ComputeInstance server tests and database fixtures; extend under fulfillment-service/internal/servers/ | ginkgo run --timeout 10m internal/servers from fulfillment-service/ | Go/Ginkgo and PostgreSQL container; real ComputeInstance server, transaction and database code; auth/attribution and Volume API responses may be controlled. No real vendor backend. | Existing runner; add private request-intent/dispatch persistence, concurrent status updates, retained IDs/parent finalizer and tenant/private-field visibility assertions. This harness does not prove the real Volume API recovery or its physical side effects. |
| H2 — Fulfillment controller | Existing ComputeInstance controller tests; extend the focused controller suite | ginkgo run --timeout 20m -r internal from fulfillment-service/ | Go/Ginkgo; controller logic with controlled API/AAP dependencies; no deployed cluster, CDI or vendor backend. | Existing broad runner; add stable naming, uncertainty handling, exact lookup/collision checks, AAP arguments and record Delete/Get ordering across all parent-finalizer release paths. |
| H3 — AAP component integration | Existing create/delete targets under osac-aap/tests/integration/targets/compute_instance_create/ and compute_instance_delete/ | make test from osac-aap/ | Ansible dependencies, container engine and Kind; real role execution and Kubernetes metadata persistence. Minimal VM/CDI APIs with controlled workload behavior; no real CSI controller or vendor disk. | Existing baselines bypass some real tasks. Register the annotation case against actual creation tasks and retain existing deletion behavior in compatibility cases. No new physical-cleanup checker or checkpoint is planned. |
| H4 — deployed VM lifecycle | Existing tests/e2e/vmaas/regression/test_compute_instance_storage_tier.py and test_compute_instance_delete_during_provision.py | uv run pytest tests/e2e/vmaas/regression/test_compute_instance_storage_tier.py tests/e2e/vmaas/regression/test_compute_instance_delete_during_provision.py from repository root | Isolated deployed Fulfillment, operator, AAP, CDI/KubeVirt and usable vendor storage; tenant/infrastructure credentials and private API reads. Proposed fixtures control existing AAP job progression and hold a test-owned Volume-record finalizer through the existing API. No backend-absence verifier or CSI failure injection is required. | Existing runner; add annotation, existing AAP/CR completion, Volume Delete/Get and parent-finalizer ordering assertions. Early-cancellation and record-retention fixtures are required. This tier exercises the existing physical path but does not independently qualify backend deletion. |
| H5 — VMaaS client to existing Volume API | Existing fulfillment-service/it/ deployed-service harness and it_volume_lifecycle_test.go; proposed caller-contract cases in it_compute_instance_volume_records_test.go | make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment from repository root | Kind, Helm, container engine, service images and auth fixtures; real private API, caller and PostgreSQL commits. Proposed response-loss fixture withholds a real committed Create response. A test-owned metadata.finalizers entry holds record deletion for Get/absence assertions and is removed by fixture teardown using the existing API. AAP/CDI/vendor progress is omitted or controlled; the operator is disabled. | Existing runner; new named recovery, Delete-accepted/Get-present, restart and eventual-NotFound cases are required. This tier qualifies record recovery and removal. API incompatibilities are external findings, not authorization for API changes. |
| H7 — record-only API qualification | Extend the existing Ginkgo integration suite in fulfillment-service/it/it_suite_test.go with proposed it_volume_record_only_test.go and provider-operation/reconciliation fixtures. | Proposed focused invocation: ginkgo run --timeout 20m --focus 'Volume record-only qualification' it from fulfillment-service/, against a prepared isolated stack. This case and its environment setup are not implemented yet. | Real private API, PostgreSQL, Fulfillment Volume reconciler, operator Volume controller and configured supported provider/backend, including LVMS/TopoLVM. Test-only observers record provider operations and LVMS resource writes; a fixture-owned positive control proves the observers and provider are active. AAP dispatch is held to isolate API side effects; no Volume API/provider response is mocked. H5's operator-disabled installer profile cannot qualify this boundary. | Merge-blocking gap G1: implement the case, reproducible setup and documented invocation; verify cases actually execute. Record controller progress and provider-operation traces through create, retry, restart and delete. No passing qualification exists yet. |

### Boundary-to-case ownership

| Changed boundary | Tier / owner | Cases | Harness / gap |
|------------------|--------------|-------|---------------|
| Fulfillment private intent → stable named Create → durable disk-key/ID status → AAP input | Database component integration and controller unit / DEV | C-01, C-05, C-06 | H1/H2; H5 qualifies real recovery |
| Committed Volume Create with lost response → scoped List → original ID → later Delete | Contract / component integration / Fulfillment DEV | C-06 | H5; release-blocking response-loss/restart fixture required |
| AAP disk-key/ID input → DataVolume annotation while retaining existing sources/classes | Component integration / DEV | C-02 | H3 |
| VMaaS client → existing private Create/List/Get/Delete requests, tenant/project attribution and responses | Contract / component integration / VMaaS DEV | P-01, C-06 | H5; caller cases required, API compatibility unverified |
| VMaaS registration/record deletion → real Volume reconciliation → no provider allocation or deletion, including LVMS before AAP | Contract / VMaaS DEV; Storage owns the consumed behavior | P-02 | H7 / G1; required passing qualification before every feature implementation PR merges |
| Existing AAP/operator completion → Volume Delete → Get confirms every record absent → parent finalizer release | Deployed E2E / QE; controller retry / DEV | D-01, D-02 | H4, H2; API finalizer-retention fixture and ordered trace required |
| Early cancellation, CR absence and existing parent-finalizer shortcuts → persistent record cleanup across restart | Controller unit and database component integration / Fulfillment DEV; deployed cancellation / QE | D-03, C-06 | H2/H1; H4 cancellation fixture; no new operator checkpoint or physical evidence gate |
| Tenant-visible, read-only ComputeInstance status | Component integration / DEV | V-01 | H1 |
| Existing VM path and legacy ComputeInstances | Component integration / DEV | C-02, S-01 | H3, H4 |

### Timing and fault evidence

These are proposed test budgets, not product SLAs.

- Unit/controller cases use controlled responses or barriers. Avoid arbitrary sleeps; assert the next API call, persisted status or finalizer after releasing the barrier.
- Server/database cases use committed transactions and verify persisted status after the server response. Simulate one API failure at a time and inspect the exact stored disk-key/ID pairs.
- AAP Kind cases inspect DataVolume metadata and storage source/class fields after the role has completed. They do not claim a physical disk was created.
- Deployed cases capture each disk key/Volume ID and its DataVolume annotation, then record an ordered trace of existing AAP deprovisioning, ComputeInstance CR disappearance, Volume Delete acceptance, per-ID Get results and parent-finalizer release. This proves lifecycle/record ordering and does not claim backend disk absence.
- TC-D-01 keeps the existing AAP job pending behind a fixture barrier, then releases it to complete its normal tasks. A separate test-owned Volume-record finalizer keeps at least one record present after Delete succeeds. Hold that barrier until the caller has observed the pending record and retained its parent; then remove only the fixture-owned finalizer through the existing API. Restore fixtures in teardown even on failure. Use existing suite deadlines and controller polling/backoff; expiry fails the test and cannot authorize production cleanup.
- TC-D-03 controls early cancellation and controller restarts. Missing PV/CSI metadata is deliberately allowed; no physical inventory, CSI finalizer manipulation or manual-recovery state is needed. Existing AAP tasks remain responsible for their current checks.
- Caller-contract tests use existing Volume API request/response shapes and verify stable names, exact tenant/project filters, recovered IDs, Delete arguments and Get confirmation. TC-P-01 proves real deletion-pending visibility and eventual archival; TC-C-06 proves lost-response recovery against real commits. Their operator-disabled harness cannot prove absence of physical side effects. TC-P-02 qualifies that separate boundary before merge; required API changes remain separate Storage work.
- TC-P-02 starts operation recording before Create and keeps it active through recovery/retry, controller restart, Delete, Get-confirmed archival and the resulting controller work. Fixture barriers capture actual request routing and completed reconciliations; an immediate ID response, quiet interval or final inventory alone is insufficient. Use the proposed H7 suite's 20-minute deadline: timeout, missing progress/observation evidence or any provider allocation/deletion attributable to these API requests fails qualification. The fixture must prove its observers work with a separate positive control so a disabled or unconfigured controller/provider cannot produce a false pass.
- TC-C-06 places a barrier after the real Create commits, confirmed by an independent database/API read, and before the response reaches the caller. The test may retain the ID as an oracle; restarted production caller state must receive only its persisted request intent. Repeat with concurrent reconcilers and temporarily failed/empty lookups. Use controlled barriers and the existing H5 test deadline; expiry fails release qualification rather than authorizing replacement Create calls.
- Parent deletion completion requires existing workload-lifecycle completion/no-resource handling, all attempted registrations resolved and every saved Volume ID confirmed absent through authorized Get. Successful Delete, DELETED status, an empty List, denied visibility and elapsed time cannot satisfy record-removal confirmation.

## Test Cases

### C: In Scope — creation and tracking of every required disk

#### TC-C-01: Fulfillment creates and persists one returned ID per disk before invoking AAP

**Interface Change:** IC-3, IC-4
**Priority:** Critical
**Tier / owner / harness:** Component integration / DEV / H1 and H2.

##### Preconditions

- A ComputeInstance with one boot disk and at least two additional disks.
- A controlled Volume API that returns distinct IDs and a controlled AAP client that records its input.

##### Steps

1. Start ComputeInstance provisioning and inspect persisted private request intent before allowing each Volume Create. Capture each request and response, including metadata.name and tenant/project.
2. Inspect persisted ComputeInstance status before allowing the AAP call.
3. Inspect the disk-key/ID mapping passed to AAP.

##### Expected Results

- Exactly one record Create is requested for each required disk key.
- Names equal `ci-<immutable-compute-instance-id>-boot` and `ci-<immutable-compute-instance-id>-disk-N`, satisfy the existing DNS-label/63-character rule and remain unchanged across reconciliation. A second instance with the same display name receives different Volume names. No truncated or random replacement name is used.
- The existing parent finalizer and exact name, attribution and resolved request spec are committed before Create; a failed finalizer/intent write prevents dispatch. Private registration state is preserved by other status writers.
- Every returned ID is durably associated with its disk key before AAP is invoked.
- AAP receives the same key/ID pairs, with no ordering-based ambiguity.
- Public status later exposes the same IDs.

#### TC-C-02: AAP annotates the matching DataVolume and retains the existing physical disk path

**Interface Change:** IC-1
**Priority:** Critical
**Tier / owner / harness:** Component integration / DEV / H3.

##### Preconditions

- An AAP integration scenario executes the real DataVolume creation tasks.
- Inputs include boot and additional disk keys/IDs, existing tenant storage mappings and a legacy instance fixture.

##### Steps

1. Create managed boot and additional DataVolumes through the AAP role.
2. Inspect annotations, sources, StorageClasses and existing tenant/owner metadata.
3. Run the legacy fixture and inspect its DataVolumes.

##### Expected Results

- Each managed DataVolume has osac.openshift.io/storage-volume-id set to the ID for its disk key.
- Boot and additional DataVolume sources and StorageClass selection remain as before.
- The AAP tasks select the existing physical-storage path and no OSAC CSI class. TC-P-02 separately proves that Volume API calls do not create another physical path; this AAP-only case cannot establish that assertion.
- Tenant and applicable owner-reference annotations remain present; legacy DataVolumes do not gain fabricated Volume IDs.

#### TC-C-05: Partial registration and AAP retries preserve known Volume IDs

**Interface Change:** IC-3
**Priority:** Critical
**Tier / owner / harness:** Controller unit / DEV / H2, with database persistence assertions in H1.

##### Preconditions

- A ComputeInstance requiring boot and additional disks, with the boot Volume ID already persisted.
- Controlled Volume API responses and AAP calls; the additional-disk Create can return an explicit failure without committing, then return an ID on a later attempt.

##### Steps

1. Fail registration for the additional disk with an explicit known non-committed outcome and inspect the persisted name/request, status and AAP call count.
2. Return a successful ID for that disk on a later reconciliation and inspect the full AAP mapping.
3. Fail and retry AAP while observing Volume Create calls and persisted IDs.

##### Expected Results

- The known boot ID is retained and its Create call is not repeated.
- The known non-committed additional-disk attempt retries with the identical saved metadata.name, attribution and request spec.
- AAP is not invoked while any required disk lacks a persisted ID; no ID is fabricated for the failed request.
- Once all returned IDs are persisted, AAP receives the complete mapping and retries reuse it without additional Volume Create calls.
- This case covers known non-committed outcomes and AAP retries. TC-C-06 covers committed Create responses lost before ID persistence and is a release gate.

#### TC-C-06: Lost Create responses recover the original record and remain safe across restart and cancellation

**Interface Change:** IC-3, IC-4, IC-5, IC-6
**Priority:** Critical
**Tier / owner / harness:** Contract / component integration / Fulfillment DEV / H5, with intent/concurrency persistence in H1 and failure-matrix unit coverage in H2.
**Release gate:** Required before feature release. Missing fixtures or a failing recovery contract leave the release blocked; existing uniqueness tests or mocked responses alone do not qualify it.

##### Preconditions

- The real existing Volume API and PostgreSQL are available with their normal name-uniqueness, attribution and List behavior. The caller persists private registration state before dispatch.
- A boot/additional-disk fixture has deterministic names, frozen tenant/project/creator/spec and no AAP job dispatched. A second tenant/project and conflicting records are available for isolation checks.
- H5 has a transport fixture that forwards Create to the real server and drops the response only after independently confirming commit. The test knows the original ID as an oracle but must not hand it to the restarted caller.

##### Steps

1. Start registration, let the API commit the selected disk's Volume, suppress the response and stop the caller before it persists the ID. Verify the database contains exactly one matching Volume and the ComputeInstance has a saved attempted intent but no ID for that disk.
2. Restart the caller from persisted state. Temporarily return a lookup failure and an empty visible result before allowing the actual exact-scope List result through. Assert no new Create, AAP dispatch or parent completion occurs during uncertainty.
3. Allow recovery. Verify the caller queries the saved name/tenant/project, validates creator/spec/deletion state, persists the original ID and only then makes the completed mapping eligible for AAP. Repeat the crash immediately after receiving Create success but before committing the ID to status.
4. Run two reconcilers against the same pending intent, with a barrier around intent dispatch and ID persistence. Verify only one dispatcher claims the intent and both converge on the same ID. Separately issue simultaneous same-name requests against the real API to qualify its existing uniqueness behavior and AlreadyExists handling without modifying the server.
5. Exercise forbidden/incomplete lookup, a same-name record in another tenant/project, mismatched creator/spec, multiple matches in a controlled caller fixture, a deleting record and disappearance/archival before recovery. Verify none causes adoption of an unrelated ID, a replacement Create or successful parent cleanup. Restore a valid original match where possible and confirm recovery resumes.
6. Repeat response loss with parent deletion requested before recovery. Let the existing workload lifecycle complete or take its no-resource path, recover the original ID, delete that exact Volume through the existing API and wait for authorized Get to return NotFound before parent completion. Hold the record with a fixture finalizer after Delete succeeds to prove that acknowledgment alone is insufficient. Existing AAP completion is controlled in H5; H4 covers deployed ordering.

##### Expected Results

- A real committed record is recovered after process restart without a second record or a fabricated ID. The public status and subsequent AAP mapping contain the original ID.
- All attempts retain the same name/request. Empty or failed lookups after an attempted Create remain unresolved; they are not classified as rollback. Concurrent reconciliation cannot overwrite a recovered ID or dispatch independent replacement requests.
- Exact tenant/project, creator, spec and deletion-state checks prevent adopting or deleting conflicting records. A persisted ID is never replaced by a reused name after deletion/archival.
- Cancellation retains unresolved intents and known IDs, issues no new Create and deletes the recovered original record after existing workload completion/no-resource handling. The parent remains until Get confirms record absence. A managed instance with no returned IDs is not mistaken for a legacy instance.
- The test records the real commit, lost response, restart, scoped recovery and final record deletion. No Volume API schema, new idempotency key, server behavior or Storage lifecycle-status update is needed to make it pass. If those existing semantics cannot support the contract, report a release blocker and separate Storage follow-up.

### D: In Scope — deletion of associated Volume records

#### TC-D-01: Existing workload completion and confirmed record removal gate parent cleanup

**Interface Change:** IC-5, IC-6
**Priority:** Critical
**Tier / owner / harness:** Deployed E2E / QE / H4.

##### Preconditions

- H4 runs deployed Fulfillment, operator, AAP and the existing VM storage path in an isolated stack satisfying the record-only API contract. TC-P-02 separately qualifies that contract before merge; this case proves workload/record-cleanup ordering.
- A ComputeInstance has boot/additional Volume IDs and matching DataVolume annotations.
- Fixtures can hold and release the existing AAP deletion job, add/remove their own Volume-record finalizers through the existing private API, and capture ordered API/job/CR/parent events. They never remove a production controller or CSI finalizer.

##### Steps

1. Save the complete disk-key/ID list and verify the DataVolume annotations. Add fixture-owned finalizers to the associated Volume records and start the ordered trace.
2. Delete the ComputeInstance while holding its existing AAP deletion job pending. Verify no Volume Delete occurs while the existing workload lifecycle remains pending; the parent and IDs remain.
3. Release the AAP job to execute its existing tasks. Observe normal deprovisioning completion and ComputeInstance CR disappearance before Fulfillment requests Volume deletion.
4. Let every Volume Delete return success while the fixture finalizers retain the records. Verify Get still returns them, and the Fulfillment parent finalizer and full ID list remain.
5. Remove one fixture finalizer and confirm that record becomes NotFound. Restart/reconcile Fulfillment while another record remains; verify partial completion does not release the parent or recreate any Volume.
6. Remove the remaining fixture finalizers. Verify Get confirms every saved ID absent before the parent finalizer is removed and the parent is archived.

##### Expected Results

- Existing AAP deletion operations and checks execute unchanged. The feature introduces Volume API deletion and confirmation reads without new physical deletion or evidence-gathering operations.
- The ordered trace establishes existing AAP/operator completion, then Volume Delete requests, then confirmed absence of all records, then parent completion.
- Successful Delete responses alone do not release the parent. Pending records preserve all correlation IDs across restart, including after the ComputeInstance CR is gone.
- The test makes no independent backend-absence claim and requires no physical-disk inventory or manual-recovery condition.

##### Gap

H4 needs job-progression and test-owned record-finalizer fixtures plus ordered observations. Existing tests do not yet assert this sequence. Track the missing QE work under G5 until concrete Tasks are created; controlled H2 tests do not replace the deployed path.

#### TC-D-02: Delete and confirmation failures retain IDs and retry until records are absent

**Interface Change:** IC-5, IC-6
**Priority:** High
**Tier / owner / harness:** Controller unit / Fulfillment DEV / H2; real API confirmation contract in TC-P-01 / H5.

##### Preconditions

- A managed ComputeInstance has persisted disk IDs and has reached its existing workload-lifecycle completion point.
- Controlled Volume Get/Delete results, a parent-finalizer observer and explicit reconciliation barriers are available.

##### Steps

1. Fail one Delete while another is accepted. Return the accepted record from Get with a deletion timestamp; repeat with status DELETED while the record remains present.
2. Return PermissionDenied, Unavailable and timeout errors from confirmation Get. Exercise a caller-scope mismatch and a returned record with unexpected attribution. Observe parent finalization after each attempt.
3. Lose a Delete response after acceptance, then restart the caller. Return the original record as deletion-pending, then NotFound through the authorized Get path. Separately return NotFound from Delete while Get is still inconclusive.
4. Allow only some IDs to become NotFound and inspect the parent and full correlation list. Finally return NotFound for every saved ID and inspect finalization.

##### Expected Results

- Delete errors, accepted-but-pending deletion, DELETED status and inconclusive Get results keep the parent finalizer and all IDs.
- Delete NotFound alone is insufficient; authorized Get must confirm absence. Wrong scope, failed access and an empty List cannot substitute for confirmation.
- Restarted reconciliation uses original IDs. It observes already-deleting records, retries Delete for existing records that are not marked deleting, and never recreates an absent record.
- The parent is finalized only after all saved IDs are confirmed absent. Retry cadence follows the existing controller backoff and introduces no new AAP or physical deletion call.

#### TC-D-03: Early cancellation and existing finalizer release paths preserve record cleanup

**Interface Change:** IC-5, IC-6
**Priority:** Critical
**Tier / owner / harness:** Controller unit / Fulfillment DEV / H2; database persistence / DEV / H1; deployed early-cancellation confirmation / QE / H4.

##### Preconditions

- Managed fixtures contain persisted boot/additional IDs or unresolved registration intent; TC-C-06 supplies the real lost-Create-response contract.
- H2 can represent an existing AAP job in progress, an absent ComputeInstance CR, no assigned hub and a decommissioned hub. H1 persists parent finalizers and status across caller restart.
- H4 can cancel an instance during existing provisioning before PVC binding, using a reproducible fixture barrier. No PV name or CSI handle is supplied to the new record-cleanup caller.

##### Steps

1. Cancel while existing AAP/operator cleanup is pending and the PVC is unbound. Verify no premature Volume Delete; release the existing lifecycle to complete its current deletion tasks and checks.
2. Observe the record-cleanup caller after CR disappearance. Verify absence of PV/CSI metadata adds no new prerequisite; record Get/Delete can proceed.
3. Independently exercise no assigned hub, absent CR and decommissioned-hub branches. At each existing parent-finalizer release point, keep a Volume record present and assert the parent remains.
4. Restart the caller after CR removal and partial record deletion. Inject a concurrent status update and verify the registration state, full ID list and finalizer are preserved.
5. Cancel with an unresolved Create intent and an empty public ID list. Let workload cleanup finish, but keep the parent pending until recovery resolves the attempted registration. Resolve to the original ID, then delete/recheck it; never create a new record during cancellation.
6. Confirm all saved IDs absent through Get and verify parent archival. Repeat early cancellation through the deployed H4 path, recording current AAP completion, record absence and parent-removal ordering.

##### Expected Results

- Every existing Fulfillment parent-finalizer release path applies the record-cleanup gate; a still-present record or unresolved registration prevents archival.
- Existing AAP/operator checks, finalizers and failure/skip policies remain unchanged. The feature does not require PVC binding, PV/CSI identity capture, backend probes or a manual-recovery state.
- Parent status and IDs survive restart and concurrent updates. Already-absent IDs are not recreated, and managed instances with unresolved requests cannot enter the legacy path.
- Once existing workload handling completes and registration/record cleanup finishes, cancellation can complete without the removed physical-evidence prerequisite.
- H2/H1 prove caller control flow and persistence; H4 proves deployed early-cancellation ordering. Neither asserts a new physical-disk cleanup guarantee.

### V: In Scope — Volume IDs in ComputeInstance status

#### TC-V-01: Status exposes only the tenant-visible disk key and Volume ID

**Interface Change:** IC-4
**Priority:** Critical
**Tier / owner / harness:** Component integration / DEV / H1.

##### Preconditions

- A ComputeInstance with recorded boot/additional Volume IDs, private registration state and a second tenant fixture.
- Public Get/List and update paths available.

##### Steps

1. Read the ComputeInstance using an authorized tenant identity.
2. Attempt to set or replace the Volume correlation list through public Create/Update.
3. Read the same instance as an unrelated tenant.

##### Expected Results

- Authorized Get/List returns the disk keys and matching Volume IDs.
- Public callers cannot choose, replace or clear the lifecycle-owned values.
- Other tenants cannot observe the ComputeInstance or its Volume IDs.
- Public callers cannot set private registration intent or Create dispatch state, and public responses expose no frozen request payloads or creator attribution. No provider, hub or backend details appear in the public correlation list.

### P: Dependencies — private Storage API

#### TC-P-01: Existing API supports named recovery and Get-confirmed record removal

**Interface Change:** IC-3, IC-5
**Priority:** Critical
**Tier / owner / harness:** Contract / component integration / VMaaS DEV / H5.

##### Preconditions

- A VMaaS client using the existing private API, a deployed Fulfillment service and authenticated tenant fixtures.
- A Volume API installation accepting the actual VMaaS registration requests. H5 tests record persistence/recovery/removal only; TC-P-02 separately qualifies asynchronous side effects before merge. A required API behavior change belongs to Storage.

##### Steps

1. Run the VMaaS record-creation caller and inspect its stable metadata.name, tenant/project attribution and returned ID. Run existing List with exact name/tenant/project filters and validate the ID; TC-C-06 separately qualifies response-loss recovery.
2. Add a test-owned Volume metadata.finalizers entry through the existing private API. Supply existing workload completion as a controlled dependency and let the caller request deletion of the persisted ID.
3. Verify Delete succeeds while Get still returns the deletion-pending record from the real database. Assert the parent finalizer and IDs remain; repeat after caller restart.
4. Remove only the fixture-owned finalizer through the existing API. Verify the record is archived, Get returns NotFound and the caller may complete parent cleanup. Restore the fixture in teardown even if assertions fail.
5. Exercise existing authentication/authorization rejection and incorrect caller scope; inspect error handling and ensure neither is treated as confirmed absence.

##### Expected Results

- Requests use existing RPCs and fields, with tenant/project attribution derived from the ComputeInstance.
- Create always supplies the stable disk name, and recovery List uses safely encoded exact scope/name filters. Names never replace Volume IDs in Delete requests or DataVolume annotations.
- The caller persists the returned Create ID and uses that exact ID for Get/Delete.
- A real deletion-pending record remains visible to Get after Delete succeeds. Parent completion follows confirmed NotFound after archival, including across restart. A successful Delete response alone cannot satisfy this contract.
- Existing API errors propagate to the caller's failure handling; no incomplete AAP mapping or successful parent cleanup is reported on a rejected request.
- No new Volume API validation, authorization, Create/Delete semantics or status-tracking behavior is required by this test.

##### Gap

H5 has an existing runner but needs the VMaaS caller-contract fixtures and assertions. Its disabled operator prevents this case from qualifying physical side effects. TC-P-02 supplies that merge prerequisite. The current Volume implementation is in the monorepo; its behavior is a consumed dependency, and changes to it are outside this feature.

#### TC-P-02: Volume Create/Delete satisfy the record-only contract with active controllers

**Interface Change:** IC-1, IC-3, IC-5
**Priority:** Critical
**Tier / owner / harness:** Contract / VMaaS DEV / H7. Storage owns validating or providing the consumed API behavior; any API/reconciler/LVMS implementation changes are separate work.
**Merge gate:** Required before any feature implementation PR merges. Development may proceed against the contract. Missing, skipped, unexecuted or failing qualification leaves every such PR unmerged.

##### Preconditions

- An isolated stack running the candidate real Volume API/database, Fulfillment Volume reconciler, operator Volume controller and configured supported storage providers. Record the tested commits/images and backend matrix; include LVMS/TopoLVM and every backend supported by the feature. Do not use H5's disabled operator or its fake provider configuration.
- The fixture supplies the same authenticated tenant/project, name and disk spec that VMaaS has before AAP dispatch. The LVMS case omits node placement that is not yet available; inventing topology or moving registration after AAP does not satisfy this design.
- AAP is held before disk creation so no workload operation can mask an allocation caused by Volume Create. Test-only observers capture provider allocation/deletion calls and LVMS LogicalVolume writes. Validate those observers and the active provider using a separately identified fixture-owned positive control, whose operations are excluded from the qualification trace.
- Implement the proposed H7 file, setup and focused command before claiming execution readiness. Fixture barriers expose request routing and completed asynchronous controller work; controller restarts preserve the operation trace. An unavailable observer or completion barrier is a blocking fixture gap.

##### Steps

1. Start operation recording, then submit the actual pre-AAP boot/additional-disk Volume Create requests for each backend. Capture returned IDs and confirm the records through Get. Fail if LVMS rejects the available request for missing topology.
2. Allow asynchronous reconciliation to complete under fixture observation. Recover a lost Create response through the saved name, repeat caller reconciliation, and restart the Volume controllers; observe the replayed work before advancing. Keep AAP held throughout this phase.
3. Assert that no provider allocation or LVMS allocation resource is attributable to those Volume requests, including transient resources that disappear before the final observation. Only the separately identified positive control may have physical operations.
4. Delete the saved Volume IDs through the real API and wait for authorized Get to return NotFound. Repeat after a lost Delete response and controller restart. Keep recording until the resulting controller work completes; assert that these deletes invoke no provider physical-deletion path and do not mutate the positive-control disk.
5. Repeat for the complete backend matrix, restore fixture barriers and clean up fixture-owned resources. Save the exact command, executed case count, candidate versions, backend configuration, API outcomes and ordered controller/provider traces as PR evidence. Qualification failure remains a failure even if teardown succeeds.

##### Expected Results

- Every supported pre-AAP request returns a record ID without physical allocation. LVMS succeeds without node placement unavailable to VMaaS at that point.
- No Volume-originated backend allocation or deletion occurs during initial requests, subsequent reconciliation, recovery, retry or restart. Provider/LogicalVolume observations establish this; passing API responses or Get returning NotFound alone do not.
- Record deletion completes through the existing API, while physical-storage ownership stays with the existing AAP/CDI/vendor-CSI path. No production cleanup check, manual finalizer removal or new Volume API mode is implemented by this feature to make the test pass.
- The suite reports the expected nonzero cases and a passing result for every supported backend. Missing execution, skips, timeout, inactive controllers/providers, unsupported LVMS requests or any physical side effect block merging all feature implementation PRs and require Storage follow-up where behavior must change.

##### Gap

G1 owns the proposed fixture, reproducible environment setup, execution evidence and merge-check wiring. The existing integration runner is available; this case and its recording/barrier fixtures are not implemented, and no qualifying run has been performed. Implementing and running the qualification is part of VMaaS DEV work; changing Volume API behavior remains separate Storage work. H4 continues to own the deployed VM create/delete journey and its existing cleanup assertions.

### Compatibility

#### TC-S-01: Existing ComputeInstances keep their current disk lifecycle

**Interface Change:** IC-1, IC-6
**Priority:** High
**Tier / owner / harness:** Component integration / DEV / H3; deployed confirmation / QE / H4.

##### Preconditions

- A legacy ComputeInstance fixture with neither private managed registration state nor Volume ID status entries. Unresolved managed requests are covered by TC-C-06 and must not enter this path.
- Existing AAP storage mappings and the current physical storage backend.

##### Steps

1. Reconcile and delete the legacy instance using the existing workflow.
2. Inspect AAP inputs, DataVolumes and Storage API calls.

##### Expected Results

- No Volume IDs are fabricated or adopted from existing DataVolumes.
- Legacy AAP storage selection and deletion remain unchanged.
- No managed record Delete is issued for an ID that was never persisted.

## Gaps

### Requirement Coverage Gaps

The backend portions of the PRD's create, delete and status visibility behaviors have planned cases. The UI portion of visibility is outside this design and requires separate UI work. TC-P-02 is a merge blocker until record-only Create/Delete is qualified with active controllers and every supported backend, including LVMS; implementation may start while that gate is unresolved. TC-C-06's recovery contract remains an explicit release blocker until qualified against real API/database commits. Deletion coverage uses the accepted existing AAP/operator completion boundary and adds confirmed record removal before parent archival. TC-D-01 covers deployed ordering, TC-D-02 retry/confirmation failures, TC-D-03 early cancellation/restart/finalizer branches and TC-P-01 the real API/database contract. TC-P-02's test-only side-effect observations add no production physical-disk cleanup checks.

### Interface Change Coverage Gaps

| Interface | Cases |
|-----------|-------|
| IC-1 | TC-C-02, TC-P-02, TC-S-01 |
| IC-3 | TC-C-01, TC-C-05, TC-C-06, TC-P-01, TC-P-02 |
| IC-4 | TC-C-01, TC-C-06, TC-V-01 |
| IC-5 | TC-C-06, TC-D-01, TC-D-02, TC-D-03, TC-P-01, TC-P-02 |
| IC-6 | TC-C-06, TC-D-01, TC-D-02, TC-D-03, TC-S-01 |

### Execution and decision gaps

| Gap | Missing evidence / required action | Owner and tracking |
|-----|------------------------------------|--------------------|
| G1 | Merge blocker: implement the runnable H7/TC-P-02 fixture and pass record-only Create/Delete qualification with active controllers and every supported backend, including LVMS without pre-AAP topology. Current Create triggers provisioning; Delete can invoke provider deletion. Define reproducible setup, operation observers, reconciliation barriers and required merge-check wiring. Missing/skipped/failing qualification keeps all feature implementation PRs unmerged; implementation may start now. | VMaaS DEV owns the fixture, evidence and merge gate under [OSAC-6040](https://redhat.atlassian.net/browse/OSAC-6040); Storage owns validating/providing record-only behavior and any separate API/reconciler/LVMS changes. Concrete fixture Task and separate Storage follow-up URL are not yet supplied. |
| G2 | Release blocker: implement stable request intent and exact-scope recovery, and pass TC-C-06 against a real committed Create whose response is lost. Existing required names, uniqueness and filtered List are building blocks; the combined recovery has not been executed. Any required API change belongs to separate Storage work. | Fulfillment DEV; [OSAC-6040](https://redhat.atlassian.net/browse/OSAC-6040). Concrete implementation Task not created. |
| G4 | Existing AAP tests need a registered case that executes real DataVolume tasks and checks annotation while proving source/class selection is unchanged. | AAP DEV; add assertions to H3 in the OSAC-6040 implementation work. |
| G5 | H4 needs fixtures for existing AAP job progression, early cancellation and test-owned Volume-record finalizer retention, plus ordered assertions for TC-D-01/03. Add them in an isolated stack using current AAP deletion tasks. Backend absence verification is not required by the accepted contract. | QE with VMaaS support; [OSAC-6040](https://redhat.atlassian.net/browse/OSAC-6040). Concrete QE Task not created. |
| G6 | The PRD's standalone-delete wording conflicts with existing public Volume CRUD behavior. Clarify the requirement; this feature uses existing Volume API authorization and introduces no deletion-policy change. | PRD owner; [OSAC-6037](https://redhat.atlassian.net/browse/OSAC-6037). |
| G7 | UI display of ComputeInstance Volume IDs is outside this backend design and plan. Link the separate UI design/work when its tracking issue is available. | UI owner; parent feature [OSAC-6037](https://redhat.atlassian.net/browse/OSAC-6037). |
| G8 | Add Fulfillment Get/Delete cleanup before every existing parent-finalizer release path. Extend H2/H1 with TC-D-02/03 for partial deletion, pending records, lookup failures, cancellation and restart. Existing AAP/operator completion remains a consumed dependency. | Fulfillment DEV; [OSAC-6040](https://redhat.atlassian.net/browse/OSAC-6040). Concrete Tasks not created. No new AAP physical check, operator cleanup checkpoint or Volume API implementation is included. |
| G9 | Add H5 response-loss/restart cases for TC-C-06 and real Delete/Get/finalizer-retention assertions for TC-P-01, including normal deletion-pending visibility and archival. Qualify name uniqueness, creator attribution and exact-scope reads. Mocked clients cannot qualify the recovery release gate. | VMaaS DEV; [OSAC-6040](https://redhat.atlassian.net/browse/OSAC-6040), concrete implementation Task not created. |

No new Jira issues were created, and no follow-up URLs were inferred. The former Storage implementation/status-tracking cases TC-C-03 and TC-C-04 and gap G3 remain outside this feature. TC-C-05 covers known caller outcomes; TC-C-06 retains the lost-response recovery contract using existing capabilities. TC-D-01/02/03 retain their IDs and IC mappings and exercise the accepted existing-workload/record-removal contract. Their earlier independent physical-cleanup assertions and the proposed H6 operator-checkpoint harness are superseded. H7/TC-P-02 qualifies consumed record-only behavior before implementation PRs merge; it does not restore that production checkpoint proposal. Release qualification also requires the documented real API fixtures and passing recovery evidence.

## Summary

| Metric | Count |
|--------|-------|
| Planned test cases | 11 |
| Critical | 9 |
| High | 2 |
| Medium | 0 |
| Low | 0 |
| Automated (planned) | 11 |
| Manual | 0 |
| Backend PRD groups with planned cases | 4 / 4 |
| UI visibility covered by this plan | No; separately owned |
| Active backend interface changes with planned cases | 5 / 5 |
| Cases executed during drafting/revision | 0 |
