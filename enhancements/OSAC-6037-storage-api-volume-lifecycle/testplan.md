# Testplan — OSAC-6040

## Overview

- **Feature:** [OSAC-6037](https://redhat.atlassian.net/browse/OSAC-6037) — Storage API integration for ComputeInstance volume lifecycle management.
- **Design:** [design.md](design.md), Volume API record IDs correlated through DataVolume annotations while the existing AAP/CDI/vendor CSI physical disk path remains in place.
- **Total planned cases:** 8.
- **Requirements covered:** backend creation, deletion and status/API visibility have planned cases. UI display remains separate design and work.
- **Interface changes covered:** all five active interface changes (IC-1, IC-3, IC-4, IC-5 and IC-6).
- **Execution:** No implementation tests or cluster experiments were run for this revision. Planned cases are not claims of existing assertions or passing coverage.
- **Baseline:** OSAC 0034f1eb6; [merged PRD at its pinned revision](https://github.com/osac-project/enhancement-proposals/blob/3da4e31a12a626f0571a42f076c89333c11a3e01/enhancements/OSAC-6037-storage-api-volume-lifecycle/prd.md).

The PRD has no FR/NFR identifiers. C, D, V and P below are local test-ID aliases for its actual In Scope and Dependencies bullets, not new published requirements. UI visibility is owned by separate design and work. This plan tests VMaaS calls to the existing Volume API, persisted ComputeInstance IDs and the AAP annotation handoff. Volume API changes, new API idempotency guarantees and Storage-side status tracking are outside this feature. Record-only API behavior remains a working assumption with a known compatibility concern; tests must report a mismatch without adding Volume API implementation work.

| Local alias | Actual source | Design/interface mapping | Planned cases |
|-------------|---------------|--------------------------|---------------|
| C | In Scope — create a Storage API Volume record for each boot/additional disk and retain its ID from provisioning | Sections 4.1–4.6; IC-1 and IC-3 | TC-C-01, TC-C-02, TC-C-05 |
| D | In Scope — delete all associated Volumes through Storage API | Sections 4.1, 4.3, 4.6; IC-5 and IC-6 | TC-D-01–02 |
| V | In Scope — IDs in ComputeInstance status and UI | Backend status/API: Sections 4.2–4.3; IC-4. UI coverage is separate. | TC-V-01 |
| P | Dependencies — private Storage API; no separate attach/detach prerequisite | Sections 4.1, 4.3 and 4.7; IC-3 and IC-5 | TC-P-01 |
| Compatibility | Existing ComputeInstances and existing AAP physical disk flow | Sections 4.1 and 8; IC-1 and IC-6 | TC-C-02, TC-S-01 |

## Planning evidence and ownership

Unit, Envtest, component integration and Contract cases belong to DEV implementation work. Deployed cross-component user journeys belong to QE. No implementation or QE Tasks were created by this revision. The feature's UI display requirement is outside this design and plan.

Commands are existing documented runners from the listed working directories. Proposed assertions and test files do not exist yet. Existing runner availability does not mean a new case already runs.

### Harness registry

| Harness | Existing evidence / planned extension | Command and working directory | Prerequisites and real/fake boundary | Execution readiness |
|---------|---------------------------------------|-------------------------------|--------------------------------------|---------------------|
| H1 — Fulfillment server/database | Existing ComputeInstance server tests and database fixtures; extend under fulfillment-service/internal/servers/ | ginkgo run --timeout 10m internal/servers from fulfillment-service/ | Go/Ginkgo and PostgreSQL container; real ComputeInstance server, transaction and database code; auth/attribution and Volume API responses may be controlled. No real vendor backend. | Existing runner; add ComputeInstance ID persistence, field ownership and tenant-visibility assertions. This harness does not prove the Volume API's physical side effects. |
| H2 — Fulfillment controller | Existing ComputeInstance controller tests; extend the focused controller suite | ginkgo run --timeout 20m -r internal from fulfillment-service/ | Go/Ginkgo; controller logic with controlled API/AAP dependencies; no deployed cluster, CDI or vendor backend. | Existing broad runner; add returned-ID persistence, AAP argument and retry/cleanup assertions. |
| H3 — AAP component integration | Existing create/delete targets under osac-aap/tests/integration/targets/compute_instance_create/ and compute_instance_delete/ | make test from osac-aap/ | Ansible dependencies, container engine and Kind; real role execution and Kubernetes object persistence; test cluster has minimal VM/CDI APIs and no real CDI import or vendor disk. | Existing create baseline skips some real resource tasks; register a scenario that executes the actual DataVolume tasks and checks annotation plus unchanged class/source selection. |
| H4 — deployed VM lifecycle | Existing tests/e2e/vmaas/regression/test_compute_instance_storage_tier.py and test_compute_instance_delete_during_provision.py | uv run pytest tests/e2e/vmaas/regression/test_compute_instance_storage_tier.py tests/e2e/vmaas/regression/test_compute_instance_delete_during_provision.py from repository root | Deployed Fulfillment, operator, AAP, CDI/KubeVirt and real configured storage backend; tenant and infrastructure credentials. Real physical disk path is required; privileged inspection may verify records and annotations. | Existing runner; add exact Volume-ID/DataVolume correlation and record-only deletion assertions. Current tests do not establish the new correlation contract or full physical cleanup. |
| H5 — VMaaS client to existing Volume API | Existing fulfillment-service/it/ deployed-service harness and it_volume_lifecycle_test.go; proposed caller-contract cases in it_compute_instance_volume_records_test.go | make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment from repository root | Kind, Helm, container engine, service images and auth fixtures; real private API, client and database. AAP/CDI/vendor progress is omitted or fixture-controlled; this tier does not prove physical provisioning. | Existing runner; new caller-contract cases are required. The operator is disabled in the service-only suite. API compatibility is a precondition; mismatches are external findings, not authorization to change the Volume API. |

### Boundary-to-case ownership

| Changed boundary | Tier / owner | Cases | Harness / gap |
|------------------|--------------|-------|---------------|
| Fulfillment Create response → durable disk-key/ID status → AAP input | Database component integration and controller unit / DEV | C-01, C-05 | H1/H2 |
| AAP disk-key/ID input → DataVolume annotation while retaining existing sources/classes | Component integration / DEV | C-02 | H3 |
| VMaaS client → existing private Create/Delete requests, tenant attribution and responses | Contract / component integration / VMaaS DEV | P-01 | H5; caller cases required, API compatibility unverified |
| AAP workload cleanup → record deletion → parent cleanup | Deployed E2E / QE; controller retry / DEV | D-01, D-02 | H4, H2; real deletion evidence required |
| Tenant-visible, read-only ComputeInstance status | Component integration / DEV | V-01 | H1 |
| Existing VM path and legacy ComputeInstances | Component integration / DEV | C-02, S-01 | H3, H4 |

### Timing and fault evidence

These are proposed test budgets, not product SLAs.

- Unit/controller cases use controlled responses or barriers. Avoid arbitrary sleeps; assert the next API call, persisted status or finalizer after releasing the barrier.
- Server/database cases use committed transactions and verify persisted status after the server response. Simulate one API failure at a time and inspect the exact stored disk-key/ID pairs.
- AAP Kind cases inspect DataVolume metadata and storage source/class fields after the role has completed. They do not claim a physical disk was created.
- Deployed cases capture the Volume ID, disk key, DataVolume annotation, DataVolume/PVC identity and backend test evidence. Poll existing asynchronous readiness at the suite's established intervals and record diagnostics on timeout.
- Caller-contract tests use the existing Volume API request/response shapes and verify tenant attribution, returned IDs and Delete arguments. They do not introduce a new API mode, recovery guarantee or Storage watcher. Report any contradiction of the record-only assumption as a compatibility finding.
- Deletion assertions require both workload cleanup evidence and Storage API record deletion. An accepted Delete request alone is not sufficient.

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

1. Start ComputeInstance provisioning and capture each Volume Create request and response.
2. Inspect persisted ComputeInstance status before allowing the AAP call.
3. Inspect the disk-key/ID mapping passed to AAP.

##### Expected Results

- Exactly one record Create is requested for each required disk key.
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
- No OSAC CSI class or new physical-storage provisioning path is selected by this change.
- Tenant and applicable owner-reference annotations remain present; legacy DataVolumes do not gain fabricated Volume IDs.

#### TC-C-05: Partial registration and AAP retries preserve known Volume IDs

**Interface Change:** IC-3
**Priority:** Critical
**Tier / owner / harness:** Controller unit / DEV / H2, with database persistence assertions in H1.

##### Preconditions

- A ComputeInstance requiring boot and additional disks, with the boot Volume ID already persisted.
- Controlled Volume API responses and AAP calls; the additional-disk Create can return an explicit failure without committing, then return an ID on a later attempt.

##### Steps

1. Fail registration for the additional disk and inspect the persisted status and AAP call count.
2. Return a successful ID for that disk on a later reconciliation and inspect the full AAP mapping.
3. Fail and retry AAP while observing Volume Create calls and persisted IDs.

##### Expected Results

- The known boot ID is retained and its Create call is not repeated.
- AAP is not invoked while any required disk lacks a persisted ID; no ID is fabricated for the failed request.
- Once all returned IDs are persisted, AAP receives the complete mapping and retries reuse it without additional Volume Create calls.
- This case covers caller recovery for known outcomes. It does not assert a new Volume API guarantee for a committed Create whose response is lost; that remains a documented limitation.

### D: In Scope — deletion of associated Volume records

#### TC-D-01: AAP removes the physical disk through the existing path before record deletion

**Interface Change:** IC-5, IC-6
**Priority:** Critical
**Tier / owner / harness:** Deployed E2E / QE / H4.

##### Preconditions

- A deployed stack with a real CDI/KubeVirt environment and a supported vendor CSI storage tier.
- A ComputeInstance with one boot disk and one additional disk, with persisted Volume IDs.

##### Steps

1. Create the ComputeInstance and verify each ID is annotated on its DataVolume.
2. Delete the ComputeInstance.
3. Capture AAP workload-object cleanup, physical storage cleanup, and Volume record deletion in order.

##### Expected Results

- AAP uses the existing DataVolume/PVC/StorageClass/vendor CSI cleanup path.
- Fulfillment retains Volume records while workload or physical-disk cleanup is pending.
- After the existing path's physical-disk cleanup acknowledgment is confirmed, the corresponding record Delete calls succeed.
- Parent cleanup completes only after all associated records are deleted.

##### Gap

Existing E2E runners do not prove this Volume-ID correlation or record-deletion ordering. Add durable assertions and backend evidence to H4; do not treat VM absence alone as proof of physical cleanup.

#### TC-D-02: Failed record deletion retains IDs and retries after workload cleanup

**Interface Change:** IC-5, IC-6
**Priority:** High
**Tier / owner / harness:** Controller unit / VMaaS DEV / H2.

##### Preconditions

- A managed ComputeInstance with persisted disk IDs and confirmed AAP workload cleanup.
- The Volume API can fail one Delete call and later succeed.

##### Steps

1. Fail record deletion for one disk while allowing another disk's deletion to succeed.
2. Restart or re-reconcile the parent.
3. Allow the remaining Delete call to succeed and inspect final status.

##### Expected Results

- IDs for failed/unconfirmed deletes remain persisted and retryable.
- Successfully deleted IDs are not recreated.
- Parent cleanup does not complete until all record Delete operations succeed.
- Delete calls use only the stored IDs and existing API request shape; this case tests caller retry behavior, not changes to the Volume API implementation.

### V: In Scope — Volume IDs in ComputeInstance status

#### TC-V-01: Status exposes only the tenant-visible disk key and Volume ID

**Interface Change:** IC-4
**Priority:** Critical
**Tier / owner / harness:** Component integration / DEV / H1.

##### Preconditions

- A ComputeInstance with recorded boot/additional Volume IDs and a second tenant fixture.
- Public Get/List and update paths available.

##### Steps

1. Read the ComputeInstance using an authorized tenant identity.
2. Attempt to set or replace the Volume correlation list through public Create/Update.
3. Read the same instance as an unrelated tenant.

##### Expected Results

- Authorized Get/List returns the disk keys and matching Volume IDs.
- Public callers cannot choose, replace or clear the lifecycle-owned values.
- Other tenants cannot observe the ComputeInstance or its Volume IDs.
- No provider, hub or backend details are added to public status.

### P: Dependencies — private Storage API

#### TC-P-01: VMaaS uses the existing Volume API with tenant attribution and stored IDs

**Interface Change:** IC-3, IC-5
**Priority:** Critical
**Tier / owner / harness:** Contract / component integration / VMaaS DEV / H5.

##### Preconditions

- A VMaaS client using the existing private API, a deployed Fulfillment service and authenticated tenant fixtures.
- A Volume API installation compatible with the working assumption; a mismatch is an external compatibility finding.

##### Steps

1. Run the VMaaS record-creation caller for a ComputeInstance and inspect the request's tenant/project attribution and returned ID.
2. Run deletion using the persisted ID after the caller's AAP cleanup precondition is satisfied.
3. Exercise an existing authentication/authorization rejection and inspect how the caller handles the error.

##### Expected Results

- Requests use existing RPCs and fields, with tenant/project attribution derived from the ComputeInstance.
- The caller persists the returned Create ID and uses that exact ID for Delete.
- Existing API errors propagate to the caller's failure handling; no incomplete AAP mapping or successful parent cleanup is reported on a rejected request.
- No new Volume API validation, authorization, Create/Delete semantics or status-tracking behavior is required by this test.

##### Gap

H5 has an existing runner but needs the VMaaS caller-contract fixtures and assertions. The current Volume implementation is in the monorepo; its behavior is a consumed dependency, and changes to it are outside this feature.

### Compatibility

#### TC-S-01: Existing ComputeInstances keep their current disk lifecycle

**Interface Change:** IC-1, IC-6
**Priority:** High
**Tier / owner / harness:** Component integration / DEV / H3; deployed confirmation / QE / H4.

##### Preconditions

- A legacy ComputeInstance fixture with no Volume ID status entries.
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

The backend portions of the PRD's create, delete and status visibility behaviors have planned cases. The UI portion of visibility is outside this design and requires separate UI work. Physical storage behavior is intentionally unchanged, but TC-D-01 still requires deployed confirmation that the existing path cleans up the tested tier.

### Interface Change Coverage Gaps

| Interface | Cases |
|-----------|-------|
| IC-1 | TC-C-02, TC-S-01 |
| IC-3 | TC-C-01, TC-C-05, TC-P-01 |
| IC-4 | TC-C-01, TC-V-01 |
| IC-5 | TC-D-01, TC-D-02, TC-P-01 |
| IC-6 | TC-D-01, TC-D-02, TC-S-01 |

### Execution and decision gaps

| Gap | Missing evidence / required action | Owner and tracking |
|-----|------------------------------------|--------------------|
| G1 | Record-only API behavior is an assumption; current Create triggers backend provisioning and requires LVMS topology. Report incompatible behavior to the feature owner for separate Storage follow-up. No API/reconciler implementation task is assigned by this plan. | External compatibility concern recorded under [OSAC-6040](https://redhat.atlassian.net/browse/OSAC-6040); separate follow-up URL not supplied. |
| G2 | Recovery of an ID lost after Create commit is not guaranteed by the existing API. TC-C-05 covers known caller outcomes only. New idempotency/lookup behavior is outside this feature. | Known limitation under [OSAC-6040](https://redhat.atlassian.net/browse/OSAC-6040); any API enhancement needs separate work. |
| G4 | Existing AAP tests need a registered case that executes real DataVolume tasks and checks annotation while proving source/class selection is unchanged. | AAP DEV; add assertions to H3 in the OSAC-6040 implementation work. |
| G5 | Existing deployed VM tests do not establish Volume ID correlation, record deletion ordering or backend cleanup. Add assertions and real backend evidence. | QE with Storage/VMaaS support; use H4 and assign the concrete QE follow-up during decomposition. |
| G6 | The PRD's standalone-delete wording conflicts with existing public Volume CRUD behavior. Clarify the requirement; this feature uses existing Volume API authorization and introduces no deletion-policy change. | PRD owner; [OSAC-6037](https://redhat.atlassian.net/browse/OSAC-6037). |
| G7 | UI display of ComputeInstance Volume IDs is outside this backend design and plan. Link the separate UI design/work when its tracking issue is available. | UI owner; parent feature [OSAC-6037](https://redhat.atlassian.net/browse/OSAC-6037). |
| G8 | Existing AAP deletion acknowledgment may prove Kubernetes object removal but not physical vendor CSI cleanup. Document and qualify its existing guarantees in H4. No new Storage watcher or Volume API completion signal is included. | AAP/VMaaS DEV and QE; [OSAC-6040](https://redhat.atlassian.net/browse/OSAC-6040), concrete follow-up URL not supplied. |
| G9 | Add the VMaaS caller-contract cases to H5; server/database fixtures with mocked clients do not prove the real private API boundary. | VMaaS DEV; [OSAC-6040](https://redhat.atlassian.net/browse/OSAC-6040), concrete implementation Task not created. |

No new Jira issues were created, and no follow-up URLs were inferred. The former Storage implementation/status-tracking cases TC-C-03 and TC-C-04 and gap G3 are removed from this feature. TC-C-05 now covers caller behavior using existing capabilities. Future Storage work is not part of this plan's acceptance criteria. Runnable VMaaS boundary coverage still requires the documented fixtures and compatibility assumptions to be satisfied.

## Summary

| Metric | Count |
|--------|-------|
| Planned test cases | 8 |
| Critical | 6 |
| High | 2 |
| Medium | 0 |
| Low | 0 |
| Automated (planned) | 8 |
| Manual | 0 |
| Backend PRD groups with planned cases | 4 / 4 |
| UI visibility covered by this plan | No; separately owned |
| Active backend interface changes with planned cases | 5 / 5 |
| Cases executed during drafting/revision | 0 |
