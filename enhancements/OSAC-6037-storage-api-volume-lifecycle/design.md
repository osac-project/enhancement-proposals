# Storage API Integration for ComputeInstance Volume Lifecycle

| Field | Value |
|-------|-------|
| Author(s) | Tzif |
| Jira | [OSAC-6037](https://redhat.atlassian.net/browse/OSAC-6037) |
| Design task | [OSAC-6040](https://redhat.atlassian.net/browse/OSAC-6040) |
| PRD | [prd.md](prd.md) |
| Date | 2026-10-20 |
| Status | Draft for review; existing Volume API consumed under a record-only assumption |

# 1. Overview

For each boot and additional disk on a newly created ComputeInstance, VMaaS will call the existing private Volume API to create a Volume record and receive its ID. Fulfillment will persist the per-disk IDs in ComputeInstance status and pass them to AAP. AAP will put each ID in an annotation on the corresponding DataVolume. Publishing this annotation completes this feature's handoff; Storage may use it for correlation and status tracking in future work. [PRD: In Scope—creation and visibility; User: Volume API changes and Storage-side tracking are outside this feature]

The existing physical disk path remains responsible for provisioning and removal: AAP creates DataVolumes, while CDI, Kubernetes scheduling, the existing StorageClasses and their vendor CSI provisioners create and delete the physical disks. This design assumes Volume API Create returns a record ID and Delete removes that record without managing the physical backing disk. Implementing or changing that API behavior is outside this feature. The inspected implementation currently provisions through Volume reconciliation, so this remains a working assumption with a known compatibility concern. If changes are needed, they will be raised separately with Storage. UI work remains separate. [User; Codebase: private Volume Create and Volume reconciliation]

# 2. Goals and Non-Goals

## 2.1 Goals

- Create one Storage API record and retain its returned ID for each ComputeInstance boot/additional disk.
- Carry each ID from Fulfillment through AAP to its matching DataVolume using an annotation.
- Publish the Volume ID annotation for possible future use by Storage.
- Preserve the existing AAP/CDI/StorageClass/vendor-CSI path for physical disk provisioning and deletion.
- Delete each Volume record through the Storage API after AAP has removed the corresponding workload disk objects.
- Expose the per-disk Volume IDs in ComputeInstance status for correlation.

## 2.2 Non-Goals

- Change physical storage provisioning, StorageClass selection, scheduling, CDI population or vendor CSI behavior.
- Route VM disks through OSAC CSI.
- Add a Volume-to-ComputeInstance reverse link, independent attach/detach state, resize/migration, sharing, snapshots or backups.
- Change Volume API endpoints, request/response schemas, Create/Delete behavior, validation, authorization or idempotency. Changes to Volume reconciliation or backend handling, including LVMS handling, are also outside this feature.
- Implement or test a Storage DataVolume watcher, lifecycle-state mapping or Volume status-update mechanism. Future Storage tracking is not a delivery requirement for this feature.
- Change UI presentation, implementation or testing; those remain separate design and work.
- Adopt or replace disks for existing ComputeInstances that have no recorded Volume IDs.

# 3. Motivation / Background

The existing AAP path creates DataVolumes using the configured VM storage tiers. CDI, Kubernetes scheduling and the selected StorageClass provisioner create the physical disks. That path does not currently provide the Volume API ID as a DataVolume correlation value.

The private Volume API already has Create and Delete operations, but its current Create implementation resolves the backend, sets the record to CREATING and causes Volume reconciliation that provisions storage. It also requires LVMS node topology for node-local volumes. These observations conflict with the working assumption for this design. The feature consumes the existing API; an integration problem must be reported for separate Storage follow-up rather than adding API, reconciler or LVMS implementation work here. [Codebase: fulfillment-service/internal/servers/private_volumes_server.go and fulfillment-service/internal/controllers/volume/volume_reconciler_function.go; User: no Volume API changes in this feature]

# 4. Design

## 4.1 Architecture

The VMaaS lifecycle covered by this feature is:

1. Fulfillment enumerates the immutable disk keys: boot and disk-1 through disk-N.
2. Fulfillment calls the existing private Volume Create once per disk, assuming a successful response containing a record ID without provisioning a physical disk.
3. Fulfillment persists each disk-key/ID pair in ComputeInstance status before invoking AAP.
4. Fulfillment passes the same key/ID mapping to AAP.
5. AAP adds the ID to the matching DataVolume annotation and creates the DataVolume with its existing source and StorageClass.
6. CDI, Kubernetes scheduling and the existing vendor CSI provisioner create the physical disk.
7. On deletion, AAP removes the VM workload and DataVolumes through the existing path and confirms the disk cleanup supported by that path. Fulfillment then calls the existing Volume Delete for each recorded ID and completes parent cleanup after all record deletes succeed. Record deletion is not evidence that the physical disk was removed.

The Volume ID is created and persisted before AAP receives it. Passing the disk key with the ID prevents AAP from associating an ID with a different disk by list order. This flow ends at writing the DataVolume annotation; it includes no Storage observer or Volume status-update step.

AAP adds the Volume ID to the DataVolume annotation osac.openshift.io/storage-volume-id. An annotation is the right fit for an opaque record identifier: it carries metadata but is not intended to select objects. Labels remain available for selectors if Storage later needs a separate stable discovery marker. See the Kubernetes documentation for [annotations](https://kubernetes.io/docs/concepts/overview/working-with-objects/annotations/) and [labels and selectors](https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/). Preserve existing tenant and applicable owner-reference annotations. Do not treat the Volume ID annotation as authorization evidence.

AAP continues to create the same boot and additional DataVolumes with the existing sources, StorageClasses and CDI behavior. Existing scheduling, vendor CSI provisioning, guest readiness and physical-disk deletion behavior remain unchanged. ComputeInstance readiness continues to follow the existing VM and DataVolume conditions; it does not wait for the Storage API record to become AVAILABLE.

The annotation supplies a correlation value that Storage may consume later. This feature does not implement, require or test a Storage consumer of that annotation, map DataVolume states to Volume states, or update Volume status.

For deletion, AAP removes the VM workload and DataVolumes using the existing cleanup path and reports its supported physical-disk cleanup completion. Fulfillment then calls Volume Delete for each recorded ID. Delete removes only the Storage API record under this design; physical cleanup remains the existing DataVolume/PVC/StorageClass/vendor CSI responsibility. Fulfillment retains IDs and retries record deletion until every call succeeds, then completes parent cleanup. If AAP's current acknowledgment does not prove the required physical cleanup boundary, that boundary must be resolved before record deletion is treated as complete.

## 4.2 Data Model / Schema Changes

Add a read-only per-disk correlation list to ComputeInstance status, with one entry containing the stable disk key and returned Volume ID. This is the durable source Fulfillment uses to pass IDs to AAP and retry deletion. Public clients can correlate a boot or additional disk with its Storage API record without receiving vendor or backend details.

No separate allocation table, PV/PVC identity ledger or Volume-to-ComputeInstance field is proposed. The status list is written by Fulfillment lifecycle handling; other status writers must preserve it. Existing ComputeInstances with no entries are not adopted or assigned records during this work.

The ComputeInstance API/protobuf status addition is additive. No schema migration is expected if the existing status persistence supports the additive field; confirm this against the implementation during decomposition. Update source protos and regenerate through the documented proto workflow if the field is added.

## 4.3 API Changes

The only API schema addition in this design is the ComputeInstance status correlation list described below. There are no changes to the Volume API's RPCs, request/response messages, validation, authorization or Create/Delete behavior. Fulfillment consumes its existing Create and Delete operations under the working assumption that they create/remove records and return the IDs needed by VMaaS.

Fulfillment calls Create once for each disk key and stores the returned ID in ComputeInstance status. The mapping passed to AAP contains the same disk key and ID. AAP writes the ID to osac.openshift.io/storage-volume-id on the matching DataVolume.

The public ComputeInstance status exposes a read-only list equivalent to status.volumes[{disk_key, volume_id}]. Public Create/Update callers cannot choose, replace or clear those IDs. Volume visibility and ComputeInstance visibility remain tenant-scoped under existing API authorization.

If integration shows that the existing Volume API cannot satisfy the working assumption, report that finding for separate Storage work. It does not authorize Volume API changes under this feature. Implementing DataVolume observation or updating Volume status is also separate future work.

## 4.4 Scalability and Performance

For a ComputeInstance with N disks, this adds N Volume record Create calls, N status entries, N DataVolume annotations and N record Delete calls. Work is O(N) per instance. The existing physical provisioning workload is unchanged, and no CSI polling or new provider call is added to the VMaaS path.

The design adds no Storage status observer, periodic scans, metrics or latency SLA. Fulfillment retains the per-disk IDs while the ComputeInstance is active or deleting and uses them to delete the records after AAP workload cleanup is confirmed.

## 4.5 Security Considerations

Use authenticated private API access for record creation and deletion. Fulfillment derives tenant/project attribution from the ComputeInstance and does not trust caller-supplied status IDs. Only Fulfillment lifecycle handling may write the public correlation list.

Fulfillment derives the disk-key/ID mapping from authenticated API responses for the owning ComputeInstance tenant. AAP writes that mapping on the corresponding tenant DataVolumes and preserves osac.openshift.io/tenant and applicable osac.openshift.io/owner-reference annotations. The annotation grants no permission to read or modify a Volume. Do not put credentials, provider identifiers or sensitive backend details in the DataVolume or public ComputeInstance status.

## 4.6 Failure Handling and Recovery

| Failure | Behavior |
|---------|----------|
| Volume Create fails before returning an ID | Do not pass an incomplete disk mapping to AAP. Report the existing provisioning failure and retry according to the Fulfillment controller policy. |
| One disk Create succeeds and a later disk Create fails | Retain each returned ID in status. Do not start AAP until all required disk IDs are available. Retry only disks without a persisted ID, subject to the Storage API retry contract. |
| AAP fails after IDs are stored | Retry AAP with the same disk-key/ID mapping. Do not create replacement records for disks whose IDs are already persisted. |
| AAP creates a DataVolume but loses its response | Retry with the same ID and disk key; the DataVolume annotation remains the correlation value. Existing AAP idempotency behavior applies. |
| Create commits but its response is lost before Fulfillment stores the ID | Report the ambiguous result and retain all known IDs. Recovery may use only existing API capabilities. This design does not claim crash-safe recovery for an unreturned ID or introduce new API idempotency/lookup behavior. |
| DataVolume deletion or physical cleanup is incomplete | Do not delete the associated Volume record yet. Retry existing AAP/Kubernetes cleanup and retain the ID. |
| Volume record Delete fails after workload cleanup | Keep the ID and parent cleanup state; retry Delete. Do not report parent cleanup complete until all record deletes succeed. |
| A legacy ComputeInstance has no recorded IDs | Preserve its existing provisioning and deletion behavior; do not infer or adopt records from DataVolumes. |

A persisted ID can be reused without repeating Create for that disk. An ambiguous Create response can leave an unknown record, and retrying it may create a duplicate. The successful-ID-return assumption does not establish a crash-recovery guarantee. Any need for new Volume API recovery capabilities is a separate follow-up, outside this feature.

## 4.7 RBAC / Tenancy

No new tenant-facing permission is required. ComputeInstance status visibility follows the existing tenant-scoped ComputeInstance API. Volume Create/Delete use authenticated private service access and tenant attribution derived from the parent ComputeInstance.

AAP continues to create DataVolumes in the tenant workload namespace under existing permissions. The feature adds no Storage watcher or Volume status-update permissions and changes no Volume API authorization rules. The annotation alone grants no permission to read or modify a Volume.

## 4.8 Extensibility / Future-Proofing

The DataVolume annotation provides a stable correlation point if Storage later changes how it provisions or tracks a backend. If a future Storage implementation needs labels for selection, it can add a separate selector label without changing the meaning of the opaque Volume ID annotation.

Any future switch to OSAC CSI, LVMS-specific provisioning through Volume API, or a different physical-disk owner requires a separate design decision. This proposal does not preclude those changes and does not assume them.

# 5. Interface Changes

The PRD has no numbered FR/NFR identifiers. Requirements below refer to its actual In Scope and Dependencies bullets. Interface numbers remain stable; removed interface changes are retired and their numbers are not reused. The previous IC-2 (CSI claim resolution), IC-7 (provider lifecycle changes), IC-8 (CSI deployment configuration) and IC-10 (new Storage readiness interface) are retired because this direction does not introduce those changes.

## IC-1: DataVolume Volume ID annotation and existing physical disk path

**Requirements:** In Scope—creation; Dependencies—private Storage API.

AAP receives a disk-key/Volume-ID mapping and adds osac.openshift.io/storage-volume-id to each corresponding DataVolume. Existing tenant and owner-reference annotations remain. The existing CDI, StorageClass, scheduler and vendor CSI path provisions the physical disk. OSAC CSI is not used for these VM disks.

## IC-3: Private Volume record creation and durable ID correlation

**Requirements:** In Scope—creation and visibility; Dependencies—private Storage API.

Fulfillment calls the existing Volume Create for each required disk, persists each returned ID in the owning ComputeInstance status, and passes the key/ID pair to AAP. The observable change is in the VMaaS caller, its persistence and its handoff to AAP. Record-only creation and successful ID return are working assumptions; this interface change does not modify the Volume API or add an idempotency/lookup mechanism.

## IC-4: ComputeInstance public disk correlations

**Requirements:** In Scope—visibility; Out of Scope—reverse linkage and attachment state.

Get/List expose a read-only status.volumes[{disk_key, volume_id}] collection. Public callers cannot set it. The collection contains only the disk key and Volume ID; it does not expose provider, hub or backend details. UI use is owned by separate design and work.

## IC-5: Managed Volume record deletion

**Requirements:** In Scope—deletion; Dependencies—private Storage API.

After AAP confirms workload disk-object cleanup, Fulfillment calls the existing private Volume Delete for each recorded ID. The call assumes record-only deletion; physical cleanup remains on the existing AAP/DataVolume/PVC/vendor CSI path. No new Delete request fields, server behavior or authorization policy are introduced. The existing PRD ambiguity about standalone deletion remains recorded in Section 9.3.

## IC-6: ComputeInstance cleanup and retained IDs

**Requirements:** In Scope—deletion.

Fulfillment retains Volume IDs while AAP cleanup or record deletion is pending. It retries cleanup and completes parent deletion only after workload cleanup and all record Delete calls succeed. Existing ComputeInstances with no IDs continue through the legacy cleanup path.

# 6. Alternatives Considered

| Decision | Alternative | Reason |
|----------|-------------|--------|
| Keep AAP/CDI/vendor CSI for physical disks | Route VM claims through OSAC CSI | Would change the existing physical provisioning path and make Volume API Create participate in backend provisioning. The requested design keeps physical storage behavior in the current VM path. |
| Put Volume ID in a DataVolume annotation | Put the ID in a label | Labels support selection but are intended for queryable classification and have value-format/length limits. The Volume ID is opaque correlation metadata and no selection by ID is required. Use a separate label only if Storage later needs a selector. |
| Delete the record after AAP workload cleanup | Delete the record before removing the DataVolume | Retaining the record and ID through workload cleanup preserves correlation while the disk is still in use. This ordering does not depend on a Storage watcher. |
| Use ComputeInstance status as the correlation source | Add a dedicated allocation table and Kubernetes PV/PVC identity ledger | The requested design needs only the per-disk ID mapping. A separate ledger would add state and lifecycle machinery beyond this contract. Revisit only if implementation evidence shows status cannot provide required durability. |

# 7. Observability and Monitoring

Use existing ComputeInstance provisioning and deletion conditions/events for Volume record Create/Delete failures. Include the disk key and Volume ID when known; do not log credentials or backend details. No Storage tracking events or metrics are introduced by this feature.

No new VM readiness condition or latency metric is introduced. A Volume record's Storage status does not replace the existing DataVolume/VM readiness signals.

# 8. Impact and Compatibility

The ComputeInstance public status gains an additive per-disk ID list. Existing API clients may ignore the new field. Regenerate shared protos from source if required; do not edit generated files directly.

AAP's DataVolume metadata changes by adding one annotation for managed ComputeInstances. The physical DataVolume source, StorageClass selection, scheduler behavior, CDI behavior and vendor CSI provisioning/deletion remain unchanged. Existing ComputeInstances without IDs keep their current lifecycle; there is no backfill or disk adoption.

The design proceeds on the assumption that the existing Volume API provides record-only Create/Delete and returns the required IDs. Source inspection found backend provisioning and LVMS topology validation in the current path; runtime compatibility with that assumption has not been established. If integration exposes this mismatch, it is reported for separate Storage follow-up. This feature does not change the Volume API or require a Storage status-tracking implementation.

The accompanying [test plan](testplan.md) assigns VMaaS caller, status and AAP annotation tests to DEV and deployed VM lifecycle coverage to QE. It treats the existing Volume API as a consumed dependency. Tests of new Volume API behavior or future Storage status tracking are outside this feature.

# 9. Open Questions

## 9.1 What recovery is possible using the existing API after an ambiguous Create response?

- **Owner:** VMaaS maintainers.
- **Impact:** Section 4.6. The inspected Create clears caller-supplied IDs, and no stable per-disk idempotency/lookup contract was found. Retain known IDs and report ambiguity. This feature assumes successful ID return and does not introduce a stronger API guarantee; any additional recovery capability belongs to separate Storage work.

## 9.2 What if the existing Volume API cannot satisfy the record-only assumption?

- **Owner:** VMaaS maintains the integration assumption; Storage owns any separate follow-up.
- **Impact:** Sections 3, 4.3 and 8. Record the compatibility finding and raise it with Storage. Keep API, Volume reconciler and LVMS changes outside this feature. Future consumption of the DataVolume annotation for status tracking is not a requirement or acceptance criterion here. [User]

## 9.3 How should the PRD's standalone-delete wording be interpreted?

- **Owner:** Storage and VMaaS maintainers / PRD owner.
- **Impact:** IC-5. The PRD says Volumes cannot be deleted independently while existing public Volume CRUD supports standalone Delete. This feature coordinates its own Delete calls with ComputeInstance cleanup and uses existing authorization. Clarifying the PRD does not authorize a Volume API deletion-policy change in this feature.

## 9.4 What acknowledgment proves the existing physical disk cleanup is complete?

- **Owner:** VMaaS/AAP maintainers.
- **Impact:** Sections 4.1, 4.6 and IC-5/IC-6. Confirm what the existing AAP deletion result guarantees and whether it waits for physical cleanup. Record its limits and verify the existing cleanup path in deployed tests. This feature introduces no new Volume status, Storage watcher or Storage API completion signal.

---

## Provenance

Authored: draft @ design 0.11.5 - 1c6e8de, workspace design/OSAC-6040 @ d30e35d27
Final: revise @ design 0.11.5 - a58bdf7, workspace design/OSAC-6040 @ 0034f1eb6

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"a58bdf7","source_repo":"0034f1eb6","source_repo_branch":"design/OSAC-6040","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
