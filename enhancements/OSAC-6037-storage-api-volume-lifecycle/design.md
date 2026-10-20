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

For each boot and additional disk on a newly created ComputeInstance, VMaaS will call the existing private Volume API with a stable metadata.name to create a Volume record and receive its ID. Fulfillment saves the request identity before Create and uses the existing List operation to recover a committed record if its response is lost. Fulfillment persists the per-disk IDs in ComputeInstance status before passing them to AAP. AAP puts each ID in an annotation on the corresponding DataVolume. Publishing this annotation completes the handoff to future Storage tracking; no Storage observer is included. [PRD: In Scope—creation and visibility; User: stable disk names and recovery without Volume API changes]

The existing physical disk path remains responsible for provisioning and removal: AAP creates DataVolumes, while CDI, Kubernetes scheduling, the existing StorageClasses and their vendor CSI provisioners create and delete the physical disks. This design assumes Volume API Create returns a record ID and Delete removes that record without managing the physical backing disk. Implementing or changing that API behavior is outside this feature. The inspected implementation currently provisions through Volume reconciliation, so this remains a working assumption with a known compatibility concern. If changes are needed, they will be raised separately with Storage. UI work remains separate. [User; Codebase: private Volume Create and Volume reconciliation]

# 2. Goals and Non-Goals

## 2.1 Goals

- Create one Storage API record and retain its returned ID for each ComputeInstance boot/additional disk.
- Supply the required stable Volume name and recover the original ID after a lost Create response using existing API operations. Prove this recovery before release. [User]
- Carry each ID from Fulfillment through AAP to its matching DataVolume using an annotation.
- Publish the Volume ID annotation for possible future use by Storage.
- Preserve the existing AAP/CDI/StorageClass/vendor-CSI path for physical disk provisioning and deletion.
- Strengthen AAP completion so physical disk cleanup is confirmed before Fulfillment deletes any associated Volume record or completes parent deletion. [User: stronger deletion check]
- Expose the per-disk Volume IDs in ComputeInstance status for correlation.

## 2.2 Non-Goals

- Change physical storage provisioning, StorageClass selection, scheduling, CDI population or vendor CSI behavior.
- Route VM disks through OSAC CSI.
- Add a Volume-to-ComputeInstance reverse link, independent attach/detach state, resize/migration, sharing, snapshots or backups.
- Change Volume API endpoints, request/response schemas, Create/Delete behavior, validation, authorization or idempotency. Changes to Volume reconciliation or backend handling, including LVMS handling, are also outside this feature.
- Implement or test a Storage DataVolume watcher, lifecycle-state mapping or Volume status-update mechanism. Future Storage tracking is not a delivery requirement for this feature.
- Change UI presentation, implementation or testing; those remain separate design and work.
- Adopt or replace disks for legacy ComputeInstances that have neither managed registration state nor recorded Volume IDs.

# 3. Motivation / Background

The existing AAP path creates DataVolumes using the configured VM storage tiers. CDI, Kubernetes scheduling and the selected StorageClass provisioner create the physical disks. That path does not currently provide the Volume API ID as a DataVolume correlation value.

The current AAP delete role waits for VM and DataVolume absence, but does not explicitly wait for PVC/PV or backend deletion. This feature strengthens that completion boundary for instances with recorded Volume IDs. The storage provisioner continues to perform physical deletion. [Codebase: osac-aap/collections/ansible_collections/osac/templates/roles/ocp_virt_vm/tasks/delete_resources.yaml; User]

The private Volume API already has Create and Delete operations, but its current Create implementation resolves the backend, sets the record to CREATING and causes Volume reconciliation that provisions storage. It also requires LVMS node topology for node-local volumes. These observations conflict with the working assumption for this design. The feature consumes the existing API; an integration problem must be reported for separate Storage follow-up rather than adding API, reconciler or LVMS implementation work here. [Codebase: fulfillment-service/internal/servers/private_volumes_server.go and fulfillment-service/internal/controllers/volume/volume_reconciler_function.go; User: no Volume API changes in this feature]

Create requires a caller-supplied metadata.name and clears a caller-supplied Volume ID. The existing API also exposes filtered List. Migration 100 enforces name uniqueness for Volumes within tenant/project, including records awaiting archival; after archival a name can be reused. These are existing building blocks for caller recovery, not an exactly-once Create or permanent idempotency-key guarantee. The combined recovery path must be qualified by TC-C-06 against the real API/database. [Codebase: private_volumes_server.go; proto/private/osac/private/v1/volumes_service.proto; fulfillment-service/internal/database/migrations/100_add_name_uniqueness_and_immutability.up.sql]

# 4. Design

## 4.1 Architecture

The VMaaS lifecycle covered by this feature is:

1. Fulfillment enumerates the immutable disk keys, boot and disk-1 through disk-N, and persists each disk's stable Volume name, intended request and registration state before making an API call.
2. Fulfillment calls the existing private Volume Create with that name. Known non-committed failures may be retried with the same name/request; ambiguous outcomes and AlreadyExists enter the List-based recovery contract below. Record-only creation remains the working assumption.
3. Fulfillment persists each returned or recovered disk-key/ID pair in ComputeInstance status before invoking AAP. It never starts AAP with an unresolved registration.
4. Fulfillment passes the same key/ID mapping to AAP.
5. AAP adds the ID to the matching DataVolume annotation and creates the DataVolume with its existing source and StorageClass.
6. CDI, Kubernetes scheduling and the existing vendor CSI provisioner create the physical disk.
7. On deletion, resolve attempted registrations first. If AAP was durably never dispatched, clean up only the recovered records under the record-only assumption. Otherwise AAP saves the disk identities before deleting the VM or disk objects, then waits for the physical-cleanup condition below. Only after every disk satisfies that condition may AAP report successful deprovisioning and Fulfillment call the existing Volume Delete for each recorded ID. Parent cleanup completes after all record deletes succeed.

The Volume ID is created and persisted before AAP receives it. Passing the disk key with the ID prevents AAP from associating an ID with a different disk by list order. The handoff to future Storage tracking ends at writing the DataVolume annotation; this feature includes no Storage observer or Volume status-update step.

AAP adds the Volume ID to the DataVolume annotation osac.openshift.io/storage-volume-id. An annotation is the right fit for an opaque record identifier: it carries metadata but is not intended to select objects. Labels remain available for selectors if Storage later needs a separate stable discovery marker. See the Kubernetes documentation for [annotations](https://kubernetes.io/docs/concepts/overview/working-with-objects/annotations/) and [labels and selectors](https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/). Preserve existing tenant and applicable owner-reference annotations. Do not treat the Volume ID annotation as authorization evidence.

AAP continues to create the same boot and additional DataVolumes with the existing sources, StorageClasses and CDI behavior. Existing scheduling, vendor CSI provisioning, guest readiness and physical-disk deletion behavior remain unchanged. ComputeInstance readiness continues to follow the existing VM and DataVolume conditions; it does not wait for the Storage API record to become AVAILABLE.

The annotation supplies a correlation value that Storage may consume later. This feature does not implement, require or test a Storage consumer of that annotation, map DataVolume states to Volume states, or update Volume status.

### Stable Volume names and Create recovery

The name passed in the existing Volume metadata.name field is `ci-<compute-instance-id>-<disk-key>`. Use the immutable, server-assigned Fulfillment ComputeInstance UUID and the disk's original key; do not use its display name or Kubernetes UID. For ComputeInstance 019a0112-3456-7890-abcd-0123456789ab, the names are:

```text
ci-019a0112-3456-7890-abcd-0123456789ab-boot
ci-019a0112-3456-7890-abcd-0123456789ab-disk-1
ci-019a0112-3456-7890-abcd-0123456789ab-disk-2
```

Persist the chosen names before the first request and reuse them byte-for-byte across reconciliation, restarts and retries. Validate the existing lowercase DNS-label/63-character constraint before dispatch; never truncate a name, renumber a disk or add a random retry suffix. The Volume ID is still generated by the API. The name is a correlation key, not authorization evidence or a new Volume API field. [User; Codebase: fulfillment-service/docs/API.md, internal/uuid/uuid.go]

1. **Persist intent and serialize dispatch.** Save each name with its disk key, exact tenant/project, expected authenticated creator and resolved Volume Create spec in the private registration state from Section 4.2. Atomically mark the request attempted before sending it, using the existing database locking/version mechanisms so concurrent reconcilers cannot independently dispatch the same intent. Keep successful IDs and unresolved intents across parent deletion requests.
2. **Recover after uncertainty.** A timeout, lost response, process crash before ID persistence or AlreadyExists triggers a fresh existing Volume List request for exact metadata.name, metadata.tenant and metadata.project equality. Use safely encoded filter literals and examine the complete matching result set/total; do not select the first result of an unfiltered or partial list. Verify the returned name, scope, expected creator, intended spec and deletion state against the saved request before accepting its ID. A name match alone is insufficient. Persist the recovered ID before any AAP dispatch.
3. **Keep unresolved work pending.** A failed/forbidden lookup, zero visible matches after an attempted Create, multiple matches, mismatched attribution/spec or a deleting record cannot authorize another Create or successful cleanup. Retain the intent and parent and retry lookup using the existing controller backoff; report conflicts for diagnosis. A newly dispatched request is allowed only for an intent never attempted or a positively known non-committed failure, using the identical name and payload. A timeout or empty lookup is not proof of rollback. This conservative rule also covers a crash after recording intent but before the request was sent.
4. **Preserve identity through deletion.** Once an ID is stored, use it for all subsequent work and Delete calls; never replace it by rediscovering a reused name. Parent cancellation during recovery must first resolve every attempted registration. A durably recorded state proving AAP was never dispatched permits cleanup of the recovered records without waiting for nonexistent workload disks, under the record-only API assumption. Mark AAP dispatch before sending the job; if it might have started, the physical-cleanup condition below applies. Never recreate a Volume during deletion or interpret an unresolved intent as a legacy instance.

Name uniqueness is a defense against duplicate registrations, not a permanent request log. Independent deletion/archival before recovery may make the original record undiscoverable; this leaves registration unresolved and prevents automatic replacement. TC-C-06 must demonstrate lost-response recovery, concurrent reconciliation and deletion of the recovered ID using the existing contract. Until it passes, recovery is an explicit release blocker. If existing name uniqueness, visibility or attribution semantics cannot support the contract, raise separate Storage work; this feature does not modify the Volume API.

### Physical-cleanup condition

For managed instances whose AAP dispatch has started or might have started, AAP and the operator enforce the following deletion contract. The durable no-dispatch exception is defined above. This is VMaaS/AAP implementation work in this feature; it requires no Volume API or Storage status-tracking change. [User]

1. **Save identities before destructive operations.** Serialize creation and deletion for the instance. Before deleting the VM, DataVolumes or PVCs, AAP resolves every disk key/Volume ID to its workload-cluster identity, DataVolume name/UID, PVC name/UID and bound PV name/UID. Validate the PV claimRef against the PVC UID and capture the CSI driver/volumeHandle, reclaim policy and deletion-protection finalizer. Persist the complete inventory in the internal ComputeInstance CR status described in Section 4.2 and read it back before proceeding. AAP job memory and job logs are insufficient for recovery.
2. **Verify the cleanup mechanism.** Each recorded PV must use reclaimPolicy Delete and a qualified CSI external provisioner with external-provisioner.volume.kubernetes.io/finalizer. Verify this protection before starting deletion. A Retain policy, missing protection, unresolved binding or inconsistent identity leaves cleanup unconfirmed; do not change the reclaim policy or remove finalizers to force success. A storage tier is qualified only when TC-D-01 demonstrates its CSI/backend deletion behavior.
3. **Delete through the existing path and wait.** AAP stops/removes the VM and deletes its DataVolumes as today. It then polls the recorded DataVolume, PVC and PV identities on the recorded workload cluster. Completion requires successful API reads confirming all three objects are absent for every disk, with the PV removed through the normal protected CSI deletion path. API errors, a terminating object or a different UID under a recorded name are not completion evidence. Poll at 5-second intervals within a 300-second cleanup budget per attempt; timeout fails the job and leaves the operation retryable. These are job controls, not a product latency guarantee.
4. **Persist completion before releasing the parent.** AAP records each disk's confirmed result in the same internal checkpoint. The operator accepts deprovisioning completion and releases its ComputeInstance finalizer only when the checkpoint covers every expected disk and all are complete for that parent UID. The AAP workflow must not remove its finalizer or report success earlier. Retry jobs reload the checkpoint even when the VM, DataVolume or PVC is already absent. Fulfillment consumes this validated completion through the existing operator/deprovisioning path, then deletes the Volume records. Fulfillment retains its parent record and IDs until all record Delete calls succeed.

For Delete-policy CSI volumes, Kubernetes documents that the external provisioner's deletion finalizer keeps the PV until backing-storage deletion completes. This supplies the runtime acknowledgment; the deployed test also checks the backend by the saved CSI volumeHandle to qualify that contract. Plain VM/DataVolume absence, PVC absence alone, a PV deletionTimestamp, elapsed time or Volume record deletion do not establish it. Administrative removal of storage finalizers invalidates this evidence. See [PersistentVolume deletion protection](https://kubernetes.io/docs/concepts/storage/persistent-volumes/#persistentvolume-deletion-protection-finalizer).

Missing objects before their identities were saved are not proof that a disk never existed. For cancellation during provisioning, an unbound PVC or unresolved allocation remains unconfirmed until its backing identity and cleanup can be established; no successful cleanup is inferred from an empty lookup. Preserve the IDs and report the unresolved disk for retry or diagnosis. A lost checkpoint must never be replaced with an empty successful inventory.

## 4.2 Data Model / Schema Changes

Add a read-only per-disk correlation list to ComputeInstance status, with one entry containing the stable disk key and returned Volume ID. This is the durable source Fulfillment uses to pass IDs to AAP and retry deletion. Public clients can correlate a boot or additional disk with its Storage API record without receiving vendor or backend details.

The public status list is written by Fulfillment lifecycle handling; other status writers must preserve it. Legacy ComputeInstances with neither registration state nor ID entries are not adopted or assigned records during this work. A managed instance with unresolved registration state remains managed even when its public ID list is still empty.

Add private Fulfillment ComputeInstance status.volume_registration state containing per-disk request names, frozen tenant/project/creator attribution and resolved Create specs, dispatch/outcome state, and an instance-level aap_dispatch_started marker. Persist intent/dispatch before API/job calls and persist recovered IDs with the resolved registration state in one status update. Keep this state out of the generated public API using the existing private-field mechanism. Public status.volumes remains only disk_key/volume_id pairs. This state lives with the existing ComputeInstance persistence; no separate allocation database or new Volume field is introduced.

Add an internal status.volumeCleanup checkpoint to the operator's ComputeInstance CR for managed-instance deletion. It contains the parent UID, complete expected disk-key/Volume-ID set, and each disk's workload-cluster reference, DataVolume/PVC names and UIDs, PV name/UID, CSI driver/volumeHandle, verified reclaim policy/finalizer and cleanup result. AAP persists the inventory before destructive work and patches completion as disks are confirmed deleted; concurrent operator status updates must preserve it using conflict-aware updates. Once deletion starts, retries must not replace recorded identities or reset completed entries. The CR finalizer retains this checkpoint through physical cleanup. After validated deprovisioning, Fulfillment's persisted Volume IDs remain sufficient for record-delete retries, even if the CR has disappeared.

This checkpoint is internal Kubernetes lifecycle state, not a Volume API field or a separate allocation database. It is never copied into public ComputeInstance status, DataVolume annotations or tenant-visible job output. The public correlation list still contains only disk_key and volume_id. Add the CR status field in its source type and use the operator's documented generators for CRDs and clients during implementation.

The ComputeInstance API/protobuf status addition is additive. No schema migration is expected if the existing status persistence supports the additive field; confirm this against the implementation during decomposition. Update source protos and regenerate through the documented proto workflow if the field is added.

## 4.3 API Changes

The public API schema addition is the ComputeInstance status correlation list described below. Private Fulfillment status gains registration state, and the operator's Kubernetes CR gains the internal cleanup checkpoint from Section 4.2. There are no changes to the Volume API's RPCs, request/response messages, validation, authorization or Create/Delete behavior. Fulfillment consumes existing Create/Delete under the record-only assumption and existing filtered List for recovery.

Fulfillment supplies `metadata.name = ci-<compute-instance-id>-<disk-key>` on every Create, freezes it in private registration state and stores the returned or recovered ID in ComputeInstance status. Recovery uses existing List filter fields for exact name/tenant/project matching. The mapping passed to AAP contains the same disk key and Volume ID; the name never substitutes for that ID in the DataVolume annotation or Volume Delete.

The public ComputeInstance status exposes a read-only list equivalent to status.volumes[{disk_key, volume_id}]. Public Create/Update callers cannot choose, replace or clear those IDs. Volume visibility and ComputeInstance visibility remain tenant-scoped under existing API authorization.

The existing AAP-job/operator deprovisioning completion path gains the physical-cleanup precondition in Section 4.1. A generic successful task or removed workload object cannot bypass it. No Volume status or new Storage API completion signal is used.

If integration shows that the existing Volume API cannot satisfy the working assumption, report that finding for separate Storage work. It does not authorize Volume API changes under this feature. Implementing a Storage DataVolume observer or updating Volume status is also separate future work.

## 4.4 Scalability and Performance

For a ComputeInstance with N disks, the successful path adds N Volume record Create calls, N private registration entries, N public ID entries, N DataVolume annotations, N private cleanup entries and N record Delete calls. Recovery adds narrowly filtered List requests for unresolved disks under existing controller backoff. Cleanup polling makes O(N) exact-object Kubernetes reads per interval within the bounded AAP attempt; it performs no cluster-wide scan or direct CSI/backend RPC. The existing physical provisioning workload is unchanged.

The design adds no Storage status observer, periodic background scan, metrics or latency SLA. Fulfillment retains the per-disk IDs while the ComputeInstance is active or deleting and uses them to delete the records after AAP confirms physical cleanup for every disk.

## 4.5 Security Considerations

Use authenticated private API access for record creation and deletion. Fulfillment derives tenant/project attribution from the ComputeInstance and does not trust caller-supplied status IDs. Only Fulfillment lifecycle handling may write the public correlation list.

Recovery uses the exact saved tenant/project, including the default project, rather than all scopes visible to the service account. Compare authenticated creator attribution and the frozen request spec before adopting a match; a conflicting record must not be adopted, changed or deleted. Do not copy private registration payloads or creator details into public status or logs. No Volume reverse-reference field or new Volume annotation is required for recovery.

Fulfillment derives the disk-key/ID mapping from authenticated API responses for the owning ComputeInstance tenant. AAP writes that mapping on the corresponding tenant DataVolumes and preserves osac.openshift.io/tenant and applicable osac.openshift.io/owner-reference annotations. The annotation grants no permission to read or modify a Volume. Do not put credentials, provider identifiers or sensitive backend details in the DataVolume or public ComputeInstance status.

Cleanup lookups must follow the validated instance-to-DataVolume-to-PVC-to-PV ownership/UID chain on the correct workload cluster. Keep the CSI handle and other private checkpoint details accessible only to lifecycle service identities; redact them from tenant-facing status, events and job output. Never delete or adopt a replacement object with a mismatching UID.

## 4.6 Failure Handling and Recovery

| Failure | Behavior |
|---------|----------|
| Volume Create is positively known not to have committed | Keep the saved name/request and retry that same intent under the existing controller policy. Do not start AAP with an incomplete ID mapping. |
| One disk Create succeeds and a later disk Create fails | Retain the known ID. Retry the same named request only for a known non-committed failure; otherwise use List recovery. Do not start AAP until all required IDs are persisted. |
| AAP fails after IDs are stored | Retry AAP with the same disk-key/ID mapping. Do not create replacement records for disks whose IDs are already persisted. |
| AAP creates a DataVolume but loses its response | Retry with the same ID and disk key; the DataVolume annotation remains the correlation value. Existing AAP idempotency behavior applies. |
| Create commits but its response is lost, ID persistence fails or the caller restarts | Recover by the saved name and exact tenant/project through existing List, validate the result and persist the same ID. Do not issue another Create while the outcome remains ambiguous. |
| Recovery lookup is empty, forbidden, failed, ambiguous, deleting or mismatched | Keep the saved intent and parent pending; retry lookup/report the conflict. Do not substitute another name, adopt an unrelated Volume or clear the intent. |
| Parent deletion starts before registration recovery completes | Resolve all attempted registrations first. If AAP was durably never dispatched, delete the recovered records under the record-only assumption; otherwise require the full physical-cleanup condition. Never create new records during deletion. |
| Cleanup inventory cannot be saved or is incomplete; a UID, binding, reclaim policy or finalizer check fails | Do not begin destructive disk cleanup or claim completion. Retain the private checkpoint, parent and Volume IDs; report the specific disk and retry/diagnose. |
| DataVolume/PVC/PV remains, CSI deletion fails, or the cleanup budget expires | Fail the AAP deletion attempt. Keep the CR finalizer, checkpoint and all Volume records; issue no record Delete until all disks are confirmed cleaned. |
| AAP restarts after disk objects disappear or loses the completion response | Reload persisted identities and results, repeat exact-object checks where needed and persist complete results before reporting success. An empty lookup without a saved identity is unconfirmed. |
| Volume record Delete fails after confirmed physical cleanup | Keep the ID and Fulfillment parent cleanup state; retry Delete without reprovisioning disks or records. Do not report parent cleanup complete until all record deletes succeed. |
| A legacy ComputeInstance has neither registration state nor recorded IDs | Preserve its existing provisioning and deletion behavior; do not infer or adopt records from DataVolumes. An unresolved managed intent does not qualify for this path. |

A persisted ID is reused without repeating Create for that disk. The required recovery guarantee is caller behavior built on existing name uniqueness and lookup semantics, qualified by TC-C-06. A transport error is never treated as a known rollback. If a committed record cannot be reliably recovered and later cleaned up, the feature is blocked from release; any needed Volume API enhancement remains separate Storage work.

## 4.7 RBAC / Tenancy

No new tenant-facing permission is required. ComputeInstance status visibility follows the existing tenant-scoped ComputeInstance API. Volume Create/List/Delete use authenticated private service access and tenant/project attribution derived from the parent ComputeInstance. The recovery caller must be able to read its own created record; denied visibility is an error, not evidence of absence.

AAP continues to create DataVolumes in the tenant workload namespace. Cleanup needs get access to the exact DataVolumes/PVCs and their bound, cluster-scoped PVs on the workload cluster, plus get/patch access to ComputeInstance status in the management namespace. Audit existing service-account permissions and add only missing verbs; no PV list, delete, update or finalizer-patch permission is needed by the new check. Preserve tenant checks when following the cluster-scoped PV claimRef. The feature adds no Storage watcher or Volume status-update permissions and changes no Volume API authorization rules.

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

Fulfillment saves the stable `ci-<compute-instance-id>-<disk-key>` name and request intent before calling existing Volume Create. It recovers an uncertain result through exact-scope existing List, validates the match and persists the original ID before passing the key/ID pair to AAP. Concurrent reconciliation preserves a single durable intent per disk. TC-C-06 must qualify this caller recovery contract before release. Record-only creation remains an assumption; no Volume API schema, lookup operation or server-side idempotency behavior is added.

## IC-4: ComputeInstance public disk correlations

**Requirements:** In Scope—visibility; Out of Scope—reverse linkage and attachment state.

Get/List expose a read-only status.volumes[{disk_key, volume_id}] collection. Public callers cannot set it. The collection contains only the disk key and Volume ID; it does not expose provider, hub or backend details. UI use is owned by separate design and work.

## IC-5: Managed Volume record deletion

**Requirements:** In Scope—deletion; Dependencies—private Storage API.

Fulfillment first resolves every attempted registration, then calls the existing private Volume Delete using persisted IDs only. For an instance whose AAP dispatch might have started, every disk must meet the Section 4.1 physical-cleanup condition before any record Delete. A persisted proof that AAP was never dispatched permits cleanup of records without nonexistent workload disks, under the record-only assumption. Pending registration or unconfirmed physical cleanup blocks record deletion and parent completion. No new Delete request fields, server behavior or authorization policy are introduced. The existing PRD ambiguity about standalone deletion remains recorded in Section 9.3.

## IC-6: ComputeInstance cleanup and retained IDs

**Requirements:** In Scope—deletion.

AAP persists the private disk-identity checkpoint before destructive cleanup, reloads it on retries, and reports success only after every expected disk meets Section 4.1. The operator keeps the ComputeInstance CR finalizer while evidence is incomplete; status writers preserve the checkpoint. Fulfillment retains registration intents, Volume IDs and its parent record until registration is resolved, physical cleanup is established as required and all record Delete calls succeed. Only instances with neither managed registration state nor IDs use the legacy cleanup path.

# 6. Alternatives Considered

| Decision | Alternative | Reason |
|----------|-------------|--------|
| Keep AAP/CDI/vendor CSI for physical disks | Route VM claims through OSAC CSI | Would change the existing physical provisioning path and make Volume API Create participate in backend provisioning. The requested design keeps physical storage behavior in the current VM path. |
| Put Volume ID in a DataVolume annotation | Put the ID in a label | Labels support selection but are intended for queryable classification and have value-format/length limits. The Volume ID is opaque correlation metadata and no selection by ID is required. Use a separate label only if Storage later needs a selector. |
| Stable name, persisted request intent and existing scoped List | Generate a fresh name on retry or require a new Volume idempotency field | Names are already mandatory. Reusing the saved identity permits recovery and uniqueness checks without API changes; a fresh retry name can hide a committed record. TC-C-06 qualifies the actual recovery contract. |
| Delete records after confirmed physical cleanup | Use VM/DataVolume absence as the completion boundary | Object removal can precede vendor cleanup. The strengthened AAP check preserves correlation and blocks parent completion while physical cleanup remains pending. |
| Keep public correlation in Fulfillment status and a private cleanup checkpoint in the existing CR | Add a dedicated allocation database or rely on AAP job memory | The CR supplies restart-safe identity persistence until physical cleanup, while Fulfillment status supplies record-delete retries. Job memory cannot recover identities after object removal; a separate database is unnecessary. |

# 7. Observability and Monitoring

Use existing ComputeInstance provisioning and deletion conditions/events for Volume record Create/Delete failures. Include the disk key and Volume ID when known; do not log credentials or backend details. No Storage tracking events or metrics are introduced by this feature.

Registration diagnostics distinguish known rejection, unresolved Create, failed lookup, conflicting match and recovered ID. Keep the instance pending while any registration is unresolved and include the stable request name in restricted diagnostics so operators can investigate without generating a replacement record.

AAP/operator deletion diagnostics distinguish inventory capture failure, unsupported reclaim/finalizer evidence, cleanup timeout, identity mismatch and confirmed physical cleanup. A pending or failed attempt must not emit successful deprovisioning. Public diagnostics identify the disk key and reason; private infrastructure identities remain in restricted diagnostics/checkpoint state.

No new VM readiness condition or latency metric is introduced. A Volume record's Storage status does not replace the existing DataVolume/VM readiness signals.

# 8. Impact and Compatibility

The ComputeInstance public status gains an additive per-disk ID list; private Fulfillment status gains the registration intents and AAP-dispatch marker. Existing public API clients may ignore the ID field and cannot see or alter private registration state. Regenerate shared protos from source if required; do not edit generated files directly.

AAP's DataVolume metadata changes by adding one annotation for managed ComputeInstances. Managed deletion gains the durable checkpoint, Kubernetes read permissions and physical-cleanup wait described above, so deletion can remain pending while CSI retries. The physical DataVolume source, StorageClass selection, scheduler behavior, CDI behavior and vendor CSI provisioning/deletion remain unchanged. Legacy ComputeInstances without registration state or IDs keep their current lifecycle; there is no backfill or disk adoption.

Qualify each supported storage tier's Delete policy and external-provisioner finalizer behavior before relying on this completion contract. Retain-policy volumes, absent protection or missing allocation evidence must remain unconfirmed; this feature does not silently rewrite storage policy or introduce a backend-specific deletion implementation.

The design proceeds on the assumption that the existing Volume API provides record-only Create/Delete and returns the required IDs. Source inspection found backend provisioning and LVMS topology validation in the current path; runtime compatibility with that assumption has not been established. If integration exposes this mismatch, it is reported for separate Storage follow-up. This feature does not change the Volume API or require a Storage status-tracking implementation.

Release is blocked until TC-C-06 demonstrates recovery after a real committed Create loses its response, including caller restart, concurrent reconciliation and later cleanup of the original record. Existing uniqueness/filtering code is supporting evidence, not a passing recovery test. A failure of the consumed API contract requires separate Storage follow-up without widening this feature's API scope.

The accompanying [test plan](testplan.md) assigns VMaaS caller/status tests, AAP annotation/checkpoint tests and operator completion tests to DEV, and deployed VM lifecycle/CSI deletion coverage to QE. It treats the existing Volume API as a consumed dependency. Tests of new Volume API behavior or future Storage status tracking are outside this feature.

# 9. Open Questions

## 9.1 Defined recovery contract; release qualification remains required

- **Owner:** VMaaS maintainers.
- **Decision:** Persist stable request names/intents before Create; recover through exact-scope existing List, validate attribution/spec and persist the original ID. Ambiguous outcomes cannot authorize another Create. Section 4.1 defines the caller contract and cancellation handling. [User]
- **Release gate:** TC-C-06 must pass against real API/database commits. If it cannot, keep this feature blocked and raise separate Storage work; neither a mocked success nor the successful-ID-return assumption closes the gap. Name reuse after independent deletion/archival is not an idempotency guarantee and must not trigger automatic replacement.

## 9.2 What if the existing Volume API cannot satisfy the record-only assumption?

- **Owner:** VMaaS maintains the integration assumption; Storage owns any separate follow-up.
- **Impact:** Sections 3, 4.3 and 8. Record the compatibility finding and raise it with Storage. Keep API, Volume reconciler and LVMS changes outside this feature. Future consumption of the DataVolume annotation for status tracking is not a requirement or acceptance criterion here. [User]

## 9.3 How should the PRD's standalone-delete wording be interpreted?

- **Owner:** Storage and VMaaS maintainers / PRD owner.
- **Impact:** IC-5. The PRD says Volumes cannot be deleted independently while existing public Volume CRUD supports standalone Delete. This feature coordinates its own Delete calls with ComputeInstance cleanup and uses existing authorization. Clarifying the PRD does not authorize a Volume API deletion-policy change in this feature.

## 9.4 Resolved: what proves physical disk cleanup is complete?

- **Owner:** VMaaS/AAP maintainers.
- **Decision:** Apply the concrete condition in Section 4.1: saved disk identities, verified Delete-policy CSI protection, confirmed DataVolume/PVC/PV absence and a persisted complete checkpoint before successful deprovisioning. Fulfillment record deletion and parent completion remain blocked until their respective prerequisites hold. [User: strengthen the deletion check]
- **Implementation and evidence:** AAP/VMaaS DEV owns checkpoint persistence, retry and finalizer handling. TC-D-01 qualifies the real backend and proves ordering while CSI deletion is delayed or failing; TC-D-03 covers controlled API/persistence failures. Exact supported driver/sidecar versions and the fault-injection fixture remain execution prerequisites, not an undefined completion condition. No Volume API or Storage status-tracking change is included.

---

## Provenance

Authored: draft @ design 0.11.5 - 1c6e8de, workspace design/OSAC-6040 @ d30e35d27
Final: revise @ design 0.11.5 - a58bdf7, workspace design/OSAC-6040 @ 0034f1eb6

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"a58bdf7","source_repo":"0034f1eb6","source_repo_branch":"design/OSAC-6040","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
