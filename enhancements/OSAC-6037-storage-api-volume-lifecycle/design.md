# Storage API Integration for ComputeInstance Volume Lifecycle

| Field | Value |
|-------|-------|
| Author(s) | Tzif |
| Jira | [OSAC-6037](https://redhat.atlassian.net/browse/OSAC-6037) |
| Design task | [OSAC-6040](https://redhat.atlassian.net/browse/OSAC-6040) |
| PRD | [prd.md](prd.md) |
| Date | 2026-10-20 |
| Status | Draft for review; implementation may start; record-only qualification required before implementation PRs merge |

# 1. Overview

For each boot and additional disk on a newly created ComputeInstance, VMaaS will call the existing private Volume API with a stable metadata.name to create a Volume record and receive its ID. Fulfillment saves the request identity before Create and uses the existing List operation to recover a committed record if its response is lost. Fulfillment persists the per-disk IDs in ComputeInstance status before passing them to AAP. AAP puts each ID in an annotation on the corresponding DataVolume. Publishing this annotation completes the handoff to future Storage tracking; no Storage observer is included. [PRD: In Scope—creation and visibility; User: stable disk names and recovery without Volume API changes]

The existing physical disk path remains responsible for provisioning and removal: AAP creates DataVolumes, while CDI, Kubernetes scheduling, the existing StorageClasses and their vendor CSI provisioners create and delete the physical disks. The consumed Volume API contract requires Create to return a record ID and Delete to remove that record without managing physical storage. Current Volume reconciliation invokes backend provisioning and deletion, so this contract is unverified. VMaaS implementation may start against the contract, but no implementation PR for this feature may merge until TC-P-02 qualifies record-only behavior with active controllers, including LVMS compatibility. Storage owns any required API, reconciler or backend changes as separate work. UI work remains separate. [User; Codebase: private Volume Create and Volume reconciliation]

Deletion consumes the existing AAP/operator completion acknowledgment. Fulfillment then deletes the registered Volume records and confirms their absence before releasing its parent finalizer; existing physical deletion checks and operations remain unchanged. [User: accepted finalizer pattern]

# 2. Goals and Non-Goals

## 2.1 Goals

- Create one Storage API record and retain its returned ID for each ComputeInstance boot/additional disk.
- Supply the required stable Volume name and recover the original ID after a lost Create response using existing API operations. Prove this recovery before release. [User]
- Carry each ID from Fulfillment through AAP to its matching DataVolume using an annotation.
- Publish the Volume ID annotation for possible future use by Storage.
- Preserve the existing AAP/CDI/StorageClass/vendor-CSI path for physical disk provisioning and deletion.
- Use existing AAP/operator deletion completion before requesting Volume-record deletion, and retain the Fulfillment parent until every associated record is confirmed removed. [User: follow the existing finalizer pattern]
- Expose the per-disk Volume IDs in ComputeInstance status for correlation.

## 2.2 Non-Goals

- Change physical storage provisioning, StorageClass selection, scheduling, CDI population or vendor CSI behavior.
- Add physical deletion operations, runtime PVC/PV/backend cleanup verification, a physical-cleanup checkpoint or a manual-recovery state. Existing AAP checks and provider/finalizer completion semantics remain in use. Test-only observation in TC-P-02 qualifies the consumed API contract. [User]
- Route VM disks through OSAC CSI.
- Add a Volume-to-ComputeInstance reverse link, independent attach/detach state, resize/migration, sharing, snapshots or backups.
- Change Volume API endpoints, request/response schemas, Create/Delete behavior, validation, authorization or idempotency. Changes to Volume reconciliation or backend handling, including LVMS handling, are also outside this feature.
- Implement or test a Storage DataVolume watcher, lifecycle-state mapping or Volume status-update mechanism. Future Storage tracking is not a delivery requirement for this feature.
- Change UI presentation, implementation or testing; those remain separate design and work.
- Adopt or replace disks for legacy ComputeInstances that have neither managed registration state nor recorded Volume IDs.

# 3. Motivation / Background

The existing AAP path creates DataVolumes using the configured VM storage tiers. CDI, Kubernetes scheduling and the selected StorageClass provisioner create the physical disks. That path does not currently provide the Volume API ID as a DataVolume correlation value.

The current AAP delete role waits for VMI, VM and DataVolume absence, but does not explicitly wait for PVC/PV or backend deletion. The operator runs its existing deprovisioning lifecycle and releases the ComputeInstance CR finalizers according to that lifecycle. This feature consumes that completion boundary and adds Volume-record cleanup before the Fulfillment parent can be archived. It does not strengthen the physical-storage completion guarantee. [Codebase: osac-aap/collections/ansible_collections/osac/templates/roles/ocp_virt_vm/tasks/delete_resources.yaml; osac-operator/internal/controller/computeinstance_controller.go; User]

Current VMaaS removes Fulfillment's controller finalizer when the ComputeInstance CR is gone, subject to its existing cleanup branches. It does not coordinate associated Volume API records or wait for their Get calls to return NotFound. Record Delete/Get coordination and retaining the same finalizer until every record is absent are new Fulfillment caller behavior proposed by this feature. [Codebase: fulfillment-service/internal/controllers/computeinstance/computeinstance_reconciler_function.go:delete]

The existing Volume Delete API sets a deletion timestamp; finalizers can keep the record present after a successful RPC. The database archives the record only after its finalizers are gone. Existing Get reads deletion-pending records until archival. The normal Volume lifecycle removes the database finalizer after its Kubernetes CR disappears, relying on provider completion rather than an additional database-side disk check. The VMaaS caller must therefore confirm record absence through Get before releasing its own parent finalizer. [Codebase: generic_dao_delete.go; generic_dao_update.go; generic_dao_get.go; volume_reconciler_function.go]

The private Volume API already has Create and Delete operations, but its current Create implementation resolves the backend, sets the record to CREATING and causes Volume reconciliation that provisions storage. It also requires LVMS node topology for node-local volumes. The operator's Volume deletion path invokes the vendor provisioner when vendor state exists. These behaviors conflict with the consumed record-only contract and can produce a second allocation, reject registration before AAP, or introduce another physical deletion owner. Receiving an ID before reconciliation finishes does not establish record-only behavior. TC-P-02 must resolve this compatibility gap before implementation PRs merge; development may proceed meanwhile. Any required API, reconciler or LVMS changes belong to separate Storage work. [Codebase: fulfillment-service/internal/servers/private_volumes_server.go; fulfillment-service/internal/controllers/volume/volume_reconciler_function.go; osac-operator/internal/controller/volume_controller.go; User]

Create requires a caller-supplied metadata.name and clears a caller-supplied Volume ID. The existing API also exposes filtered List. Migration 100 enforces name uniqueness for Volumes within tenant/project, including records awaiting archival; after archival a name can be reused. These are existing building blocks for caller recovery, not an exactly-once Create or permanent idempotency-key guarantee. The combined recovery path must be qualified by TC-C-06 against the real API/database. [Codebase: private_volumes_server.go; proto/private/osac/private/v1/volumes_service.proto; fulfillment-service/internal/database/migrations/100_add_name_uniqueness_and_immutability.up.sql]

# 4. Design

## 4.1 Architecture

The VMaaS lifecycle covered by this feature is:

1. Fulfillment enumerates the immutable disk keys, boot and disk-1 through disk-N, and persists each disk's stable Volume name, intended request and registration state before making an API call.
2. Fulfillment calls the private Volume Create with that name under the record-only contract qualified by TC-P-02 before merge. Known non-committed failures may be retried with the same name/request; ambiguous outcomes and AlreadyExists enter the List-based recovery contract below.
3. Fulfillment persists each returned or recovered disk-key/ID pair in ComputeInstance status before invoking AAP. It never starts AAP with an unresolved registration.
4. Fulfillment passes the same key/ID mapping to AAP.
5. AAP adds the ID to the matching DataVolume annotation and creates the DataVolume with its existing source and StorageClass.
6. CDI, Kubernetes scheduling and the existing vendor CSI provisioner create the physical disk.
7. On deletion, let the existing AAP/operator workflow perform its usual cleanup and checks. Resolve any attempted registrations before record cleanup. At the point the existing ComputeInstance lifecycle would release Fulfillment's controller finalizer, request deletion of every persisted Volume ID and confirm all records are absent through the existing Volume Get API. Only then release that finalizer and allow parent archival.

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

1. **Persist intent and serialize dispatch.** Ensure the existing Fulfillment parent finalizer is durably present before the first Volume Create. Save each name with its disk key, exact tenant/project, expected authenticated creator and resolved Volume Create spec in the private registration state from Section 4.2. Atomically mark the request attempted before sending it, using the existing database locking/version mechanisms so concurrent reconcilers cannot independently dispatch the same intent. Keep successful IDs and unresolved intents across parent deletion requests.
2. **Recover after uncertainty.** A timeout, lost response, process crash before ID persistence or AlreadyExists triggers a fresh existing Volume List request for exact metadata.name, metadata.tenant and metadata.project equality. Use safely encoded filter literals and examine the complete matching result set/total; do not select the first result of an unfiltered or partial list. Verify the returned name, scope, expected creator, intended spec and deletion state against the saved request before accepting its ID. A name match alone is insufficient. Persist the recovered ID before any AAP dispatch.
3. **Keep unresolved work pending.** A failed/forbidden lookup, zero visible matches after an attempted Create, multiple matches, mismatched attribution/spec or a deleting record cannot authorize another Create or successful cleanup. Retain the intent and parent and retry lookup using the existing controller backoff; report conflicts for diagnosis. A newly dispatched request is allowed only for an intent never attempted or a positively known non-committed failure, using the identical name and payload. A timeout or empty lookup is not proof of rollback. This conservative rule also covers a crash after recording intent but before the request was sent.
4. **Preserve identity through deletion.** Once an ID is stored, use it for all subsequent work and Delete/Get calls; never replace it by rediscovering a reused name. Parent cancellation must resolve every attempted registration before record cleanup and parent archival. Existing AAP/operator deletion or no-resource handling proceeds through its current lifecycle; this feature adds no AAP-dispatch marker or allocation-evidence prerequisite. Never create a new Volume during deletion or interpret an unresolved intent as a legacy instance.

Name uniqueness is a defense against duplicate registrations, not a permanent request log. Independent deletion/archival before recovery may make the original record undiscoverable; this leaves registration unresolved and prevents automatic replacement. TC-C-06 must demonstrate lost-response recovery, concurrent reconciliation and deletion of the recovered ID using the existing contract. Until it passes, recovery is an explicit release blocker. If existing name uniqueness, visibility or attribution semantics cannot support the contract, raise separate Storage work; this feature does not modify the Volume API.

### Deletion completion through existing finalizers

Use the existing AAP/operator completion contract for workload cleanup and add a Fulfillment gate for Volume-record removal. The parent finalizer already exists; waiting for associated Volume records to disappear is new caller behavior, not current VMaaS functionality. This supersedes the earlier proposal for independent physical-cleanup evidence. The only new deletion calls are to the existing Volume API. [User]

1. **Consume existing workload completion.** Keep AAP's existing deletion tasks, waits, retry policy and CR finalizers. In the normal path, AAP completes deprovisioning and the ComputeInstance CR disappears after its finalizers release. Fulfillment then reaches its existing parent-finalizer removal point. While that lifecycle is still pending, do not call Volume Delete. Preserve existing no-hub, absent-CR and decommissioned-hub handling; route every path that would release the Fulfillment parent finalizer through the record-cleanup gate below. These existing shortcuts are not evidence of physical disk absence.
2. **Resolve registrations and request record deletion.** Preserve the existing Fulfillment controller finalizer, registration intents and complete disk-key/ID list. Resolve every attempted Create using the named recovery contract before beginning record cleanup. For each persisted ID, use existing authenticated Volume Get/Delete with the parent tenant/project context. If Get returns the matching record without a deletion timestamp, request Delete. If it is already deleting, continue observing it. Never use a name to replace the saved ID, recreate a record or add a direct PVC/PV/CSI/backend deletion call.
3. **Confirm record removal.** A successful Delete RPC, deletion timestamp or DELETED status does not mean the record is gone. Reconcile with existing controller backoff and Get each saved ID until it returns NotFound through the qualified, authorized API path. Get errors, denied access and any returned record keep cleanup pending. A Delete error, including an uncertain response or NotFound race, is followed by Get on retry; only confirmed absence completes that ID. Do not infer absence from an empty List or altered caller visibility. Never clear Volume finalizers to accelerate cleanup.
4. **Release the parent last.** Fulfillment removes its own parent finalizer only when every attempted registration is resolved and all recorded IDs are confirmed absent. Persist the IDs until parent archival so a restart can repeat these reads even after the ComputeInstance CR has gone. Partial success retains the parent and full correlation list; already absent IDs are complete and are never recreated. No separate deletion checkpoint or completion field is required.

Cancellation before PVC binding or before any PV/CSI handle exists follows the same existing AAP/operator path. Missing physical-allocation metadata adds no new blocker or manual-recovery state. Cancellation before workload resources exist uses the existing lifecycle's no-resource handling, followed by resolution and deletion of any registered Volumes. Unresolved Create outcomes still retain the parent under TC-C-06's record-recovery contract.

This completion boundary confirms that the existing workload lifecycle finished according to its current policies and the associated Volume records were removed. It does not independently prove physical disk absence. Existing AAP failure/skip policies, storage reclaim behavior and provider cleanup limitations are inherited. In particular, a record-only Volume API cannot verify an independently provisioned VM disk through this correlation annotation. Stronger physical verification or changes to Volume API/backend behavior require separate work. [User; Codebase: computeinstance_reconciler_function.go; computeinstance_controller.go; provision_lifecycle.go]

## 4.2 Data Model / Schema Changes

Add a read-only per-disk correlation list to ComputeInstance status, with one entry containing the stable disk key and returned Volume ID. This is the durable source Fulfillment uses to pass IDs to AAP and retry deletion. Public clients can correlate a boot or additional disk with its Storage API record without receiving vendor or backend details.

The public status list is written by Fulfillment lifecycle handling; other status writers must preserve it. Legacy ComputeInstances with neither registration state nor ID entries are not adopted or assigned records during this work. A managed instance with unresolved registration state remains managed even when its public ID list is still empty.

Add private Fulfillment ComputeInstance status.volume_registration state containing per-disk request names, frozen tenant/project/creator attribution and resolved Create specs, and Create dispatch/outcome state. Persist intent/dispatch before Volume Create and persist recovered IDs with the resolved registration state in one status update. Keep this state out of the generated public API using the existing private-field mechanism. Public status.volumes remains only disk_key/volume_id pairs. This state lives with the existing ComputeInstance persistence; no separate allocation database or new Volume field is introduced.

The existing Fulfillment parent finalizer retains registration state and IDs through record cleanup. Restarted reconciliation repeats Get/Delete using those IDs; it does not require a physical-disk inventory, an AAP-dispatch marker or an additional operator CR cleanup checkpoint.

The ComputeInstance API/protobuf status addition is additive. No schema migration is expected if the existing status persistence supports the additive field; confirm this against the implementation during decomposition. Update source protos and regenerate through the documented proto workflow if the field is added.

## 4.3 API Changes

The public API schema addition is the ComputeInstance status correlation list described below. Private Fulfillment status gains registration state from Section 4.2. This feature makes no changes to the Volume API's RPCs, request/response messages, validation, authorization or Create/Delete behavior. Fulfillment consumes Create/Delete under the record-only contract, filtered List for Create recovery and Get for confirmation of record removal. TC-P-02 must qualify that consumed contract before implementation PRs merge.

Fulfillment supplies `metadata.name = ci-<compute-instance-id>-<disk-key>` on every Create, freezes it in private registration state and stores the returned or recovered ID in ComputeInstance status. Recovery uses existing List filter fields for exact name/tenant/project matching. The mapping passed to AAP contains the same disk key and Volume ID; the name never substitutes for that ID in the DataVolume annotation or Volume Delete.

The public ComputeInstance status exposes a read-only list equivalent to status.volumes[{disk_key, volume_id}]. Public Create/Update callers cannot choose, replace or clear those IDs. Volume visibility and ComputeInstance visibility remain tenant-scoped under existing API authorization.

The existing AAP-job/operator deprovisioning completion path is consumed unchanged. The added gate runs before Fulfillment releases its parent finalizer and requires existing Volume Get to confirm record absence. No new Storage API completion signal is introduced, and DELETED status alone cannot release the parent.

If qualification shows that the Volume API cannot satisfy the record-only contract, keep implementation PRs unmerged and report the finding for separate Storage work. VMaaS development may continue against the contract. This does not authorize Volume API changes under this feature. Implementing a Storage DataVolume observer or updating Volume status is also separate future work.

## 4.4 Scalability and Performance

For a ComputeInstance with N disks, the successful path adds N Volume record Create calls, N private registration entries, N public ID entries, N DataVolume annotations and N record Delete calls. Recovery adds narrowly filtered List requests for unresolved disks. Deletion confirmation makes O(N) ID-based Get calls per reconciliation under existing controller backoff; it adds no Kubernetes inventory scan or direct CSI/backend RPC. The existing physical provisioning and deletion workload is unchanged.

The design adds no Storage status observer, periodic background scan, metrics or latency SLA. Fulfillment retains the per-disk IDs while the ComputeInstance is active or deleting and until all records are confirmed absent after existing workload cleanup.

## 4.5 Security Considerations

Use authenticated private API access for record creation and deletion. Fulfillment derives tenant/project attribution from the ComputeInstance and does not trust caller-supplied status IDs. Only Fulfillment lifecycle handling may write the public correlation list.

Recovery uses the exact saved tenant/project, including the default project, rather than all scopes visible to the service account. Compare authenticated creator attribution and the frozen request spec before adopting a match; a conflicting record must not be adopted, changed or deleted. Do not copy private registration payloads or creator details into public status or logs. No Volume reverse-reference field or new Volume annotation is required for recovery.

Fulfillment derives the disk-key/ID mapping from authenticated API responses for the owning ComputeInstance tenant. AAP writes that mapping on the corresponding tenant DataVolumes and preserves osac.openshift.io/tenant and applicable osac.openshift.io/owner-reference annotations. The annotation grants no permission to read or modify a Volume. Do not put credentials, provider identifiers or sensitive backend details in the DataVolume or public ComputeInstance status.

Record-cleanup reads and Delete calls use the saved IDs and the same authorized parent tenant/project context used for registration. Validate that returned records match that scope. An authorization error or caller-scope change cannot establish record absence. No new cluster-scoped storage reads or backend credentials are required by this feature.

## 4.6 Failure Handling and Recovery

| Failure | Behavior |
|---------|----------|
| Volume Create is positively known not to have committed | Keep the saved name/request and retry that same intent under the existing controller policy. Do not start AAP with an incomplete ID mapping. |
| One disk Create succeeds and a later disk Create fails | Retain the known ID. Retry the same named request only for a known non-committed failure; otherwise use List recovery. Do not start AAP until all required IDs are persisted. |
| AAP fails after IDs are stored | Retry AAP with the same disk-key/ID mapping. Do not create replacement records for disks whose IDs are already persisted. |
| AAP creates a DataVolume but loses its response | Retry with the same ID and disk key; the DataVolume annotation remains the correlation value. Existing AAP idempotency behavior applies. |
| Create commits but its response is lost, ID persistence fails or the caller restarts | Recover by the saved name and exact tenant/project through existing List, validate the result and persist the same ID. Do not issue another Create while the outcome remains ambiguous. |
| Recovery lookup is empty, forbidden, failed, ambiguous, deleting or mismatched | Keep the saved intent and parent pending; retry lookup/report the conflict. Do not substitute another name, adopt an unrelated Volume or clear the intent. |
| Parent deletion starts before registration recovery completes | Allow existing workload cleanup; resolve all attempted registrations before record cleanup and parent archival. Never create new records during deletion. |
| Existing AAP/operator deletion is still pending or retrying | Retain the Volume records and parent. Consume existing lifecycle progress; do not add deletion operations or stronger physical checks. |
| Cancellation occurs with an unbound PVC or no PV/CSI handle | Follow existing AAP/operator cancellation behavior. Missing allocation metadata adds no new gate; after existing completion, delete/recheck the recovered records. |
| ComputeInstance CR is already absent, no hub was assigned or the hub was decommissioned | Preserve the existing workload-lifecycle decision, but run Volume-record cleanup before releasing the Fulfillment parent finalizer. These paths do not prove physical cleanup. |
| Volume Delete succeeds but Get still returns the record, even with DELETED status | Retain the ID and parent finalizer; retry Get with controller backoff until the record is absent. |
| Volume Delete or confirmation Get fails, or the caller restarts | Keep all saved IDs. Recheck each ID through authorized Get; retry Delete when the record exists and is not already deleting. Errors and altered visibility are not completion evidence. |
| Some Volume records are absent and others remain | Keep the parent and full ID list; recheck on restart and never recreate an absent record. Complete parent cleanup only after every ID is confirmed absent. |
| A legacy ComputeInstance has neither registration state nor recorded IDs | Preserve its existing provisioning and deletion behavior; do not infer or adopt records from DataVolumes. An unresolved managed intent does not qualify for this path. |

A persisted ID is reused without repeating Create for that disk. The required recovery guarantee is caller behavior built on existing name uniqueness and lookup semantics, qualified by TC-C-06. A transport error is never treated as a known rollback. If a committed record cannot be reliably recovered and later cleaned up, the feature is blocked from release; any needed Volume API enhancement remains separate Storage work.

## 4.7 RBAC / Tenancy

No new tenant-facing permission is required. ComputeInstance status visibility follows the existing tenant-scoped ComputeInstance API. Volume Create/List/Get/Delete use authenticated private service access and tenant/project attribution derived from the parent ComputeInstance. The caller must retain visibility of its own created records through deletion; denied visibility is an error, not evidence of absence.

AAP continues to create DataVolumes in the tenant workload namespace with existing ownership metadata. Its deletion tasks and Kubernetes permissions are unchanged. The feature adds no PV/backend inspection, physical-cleanup status-patch, Storage watcher or Volume status-update permissions, and changes no Volume API authorization rules.

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

Fulfillment saves the stable `ci-<compute-instance-id>-<disk-key>` name and request intent before calling existing Volume Create. It recovers an uncertain result through exact-scope existing List, validates the match and persists the original ID before passing the key/ID pair to AAP. Concurrent reconciliation preserves a single durable intent per disk. TC-C-06 must qualify this caller recovery contract before release. TC-P-02 must qualify record-only Create/Delete before implementation PRs merge; no Volume API schema, lookup operation or server-side idempotency behavior is added by this feature.

## IC-4: ComputeInstance public disk correlations

**Requirements:** In Scope—visibility; Out of Scope—reverse linkage and attachment state.

Get/List expose a read-only status.volumes[{disk_key, volume_id}] collection. Public callers cannot set it. The collection contains only the disk key and Volume ID; it does not expose provider, hub or backend details. UI use is owned by separate design and work.

## IC-5: Managed Volume record deletion

**Requirements:** In Scope—deletion; Dependencies—private Storage API.

After existing AAP/operator cleanup reaches the Fulfillment parent-finalizer removal point, Fulfillment resolves every attempted registration and calls the existing private Volume Get/Delete using persisted IDs only. Delete acknowledgment requests removal; only subsequent authorized Get returning NotFound confirms it. Existing no-resource and decommissioned-hub paths also run this record-cleanup gate. No new physical deletion operations, API request fields, server behavior or authorization policy are introduced. The existing PRD ambiguity about standalone deletion remains recorded in Section 9.3.

## IC-6: ComputeInstance cleanup and retained IDs

**Requirements:** In Scope—deletion.

Existing AAP/operator completion and CR finalizer behavior remain unchanged. Fulfillment retains its controller finalizer, registration intents, full Volume-ID list and parent record until registration is resolved and all associated records are confirmed absent. Retries and restarts recheck stored IDs even after the ComputeInstance CR disappears. Delete/Get errors or a still-present record block parent completion. Only instances with neither managed registration state nor IDs use the legacy cleanup path.

# 6. Alternatives Considered

| Decision | Alternative | Reason |
|----------|-------------|--------|
| Keep AAP/CDI/vendor CSI for physical disks | Route VM claims through OSAC CSI | Would change the existing physical provisioning path and make Volume API Create participate in backend provisioning. The requested design keeps physical storage behavior in the current VM path. |
| Put Volume ID in a DataVolume annotation | Put the ID in a label | Labels support selection but are intended for queryable classification and have value-format/length limits. The Volume ID is opaque correlation metadata and no selection by ID is required. Use a separate label only if Storage later needs a selector. |
| Stable name, persisted request intent and existing scoped List | Generate a fresh name on retry or require a new Volume idempotency field | Names are already mandatory. Reusing the saved identity permits recovery and uniqueness checks without API changes; a fresh retry name can hide a committed record. TC-C-06 qualifies the actual recovery contract. |
| Consume existing AAP/operator completion, then confirm record removal | Add independent PVC/PV/backend evidence and manual recovery | The selected scope preserves existing physical deletion operations and completion guarantees. Stronger evidence requires additional cancellation/recovery contracts; the user explicitly superseded that proposal. |
| Wait for each Volume Get to return NotFound | Release the parent on successful Delete or DELETED status | The existing API can acknowledge deletion while finalizers still retain the record. Confirmed absence prevents premature parent archival. |
| Keep registration intents and IDs in Fulfillment status | Add a separate allocation database or physical-cleanup CR checkpoint | Existing status and the parent finalizer preserve everything needed for record recovery and deletion retries. Physical inventory is outside this completion contract. |

# 7. Observability and Monitoring

Use existing ComputeInstance provisioning and deletion conditions/events for Volume record Create/Delete failures. Include the disk key and Volume ID when known; do not log credentials or backend details. No Storage tracking events or metrics are introduced by this feature.

Registration diagnostics distinguish known rejection, unresolved Create, failed lookup, conflicting match and recovered ID. Keep the instance pending while any registration is unresolved and include the stable request name in restricted diagnostics so operators can investigate without generating a replacement record.

Record-cleanup diagnostics distinguish existing workload deletion pending, unresolved registration, Delete failure, record still present, Get failure and confirmed record absence. Identify the disk key and Volume ID; preserve existing AAP/operator diagnostics. Report parent deletion complete only after all records are absent. No new physical-cleanup condition or manual-recovery state is added.

No new VM readiness condition or latency metric is introduced. A Volume record's Storage status does not replace the existing DataVolume/VM readiness signals.

# 8. Impact and Compatibility

The ComputeInstance public status gains an additive per-disk ID list; private Fulfillment status gains the registration intents. Existing public API clients may ignore the ID field and cannot see or alter private registration state. Regenerate shared protos from source if required; do not edit generated files directly.

AAP's DataVolume metadata changes by adding one annotation for managed ComputeInstances. Its deletion tasks, checks, Kubernetes permissions and operator completion remain unchanged. Fulfillment adds record cleanup before each existing parent-finalizer release path, so the parent can remain pending while Volume records still exist. The physical DataVolume source, StorageClass selection, scheduler behavior, CDI behavior and vendor CSI provisioning/deletion remain unchanged. Legacy ComputeInstances without registration state or IDs keep their current lifecycle; there is no backfill or disk adoption.

The accepted completion guarantee is existing workload-lifecycle completion followed by confirmed record removal. It does not qualify backend disk deletion, change reclaim policies or require saved PV/CSI identities for early cancellation. This replaces the earlier stronger physical-cleanup proposal at the user's request.

### Record-only qualification before merge

VMaaS implementation may start against the record-only Create/Delete contract. Every implementation PR for this feature remains unmerged until TC-P-02 passes against the candidate API/controller versions and each supported storage backend, including LVMS. Missing fixtures, unavailable environments, skipped or unexecuted cases, and failing results keep merge blocked. Passing unit tests, the AAP-only TC-C-02, or the operator-disabled H5 API suite cannot satisfy this gate. [User: start implementation now; verify before any implementation PR merges]

TC-P-02 requires a runnable fixture with the real API, database, Fulfillment Volume reconciler and operator Volume controller active. It submits the actual request available before AAP, including LVMS without node topology that VMaaS does not yet know. It verifies an ID is returned without physical allocation and that Delete removes the record without physical-storage deletion, including subsequent reconciliation, retry and restart. Its test-only provider-operation observations do not add production cleanup checks or alter AAP deletion behavior. The test plan defines the fixture, proposed command, required evidence and current execution gap.

VMaaS DEV owns the qualification fixture and passing evidence required on each implementation PR; Storage owns validating or providing the consumed behavior and any separate API/reconciler/LVMS changes. Evidence identifies the tested commits/images, backend matrix, exact command and result, completed reconciliation and provider-operation trace. A missing or skipped qualification is not a successful check; reviewers must enforce the merge gate until a required CI check is wired. This document does not claim that such a check already exists. The existing AAP/CDI/vendor-CSI path remains the sole physical disk lifecycle owner.

Release is blocked until TC-C-06 demonstrates recovery after a real committed Create loses its response, including caller restart, concurrent reconciliation and later cleanup of the original record. Existing uniqueness/filtering code is supporting evidence, not a passing recovery test. A failure of the consumed API contract requires separate Storage follow-up without widening this feature's API scope.

The accompanying [test plan](testplan.md) assigns VMaaS caller/status, AAP annotation, record-deletion/absence tests and TC-P-02 consumed-contract qualification to DEV, and deployed existing-lifecycle/record-cleanup ordering to QE. It treats the Volume API and AAP/operator completion as consumed dependencies. Implementation of new Volume API behavior, production physical-cleanup verification and future Storage status tracking are outside this feature.

# 9. Open Questions

## 9.1 Defined recovery contract; release qualification remains required

- **Owner:** VMaaS maintainers.
- **Decision:** Persist stable request names/intents before Create; recover through exact-scope existing List, validate attribution/spec and persist the original ID. Ambiguous outcomes cannot authorize another Create. Section 4.1 defines the caller contract and cancellation handling. [User]
- **Release gate:** TC-C-06 must pass against real API/database commits. If it cannot, keep this feature blocked and raise separate Storage work; neither a mocked success nor the successful-ID-return assumption closes the gap. Name reuse after independent deletion/archival is not an idempotency guarantee and must not trigger automatic replacement.

## 9.2 Record-only qualification remains a merge prerequisite

- **Owner:** VMaaS DEV owns TC-P-02 and the merge evidence; Storage owns validating/providing record-only behavior and any separate follow-up.
- **Decision:** Implementation starts against the consumed contract; all feature implementation PRs remain unmerged until TC-P-02 passes with active controllers and the supported backend matrix, including LVMS. Missing, skipped or failing qualification blocks merge. [User]
- **Impact:** Sections 3, 4.3 and 8. Current provisioning/deletion side effects and LVMS topology validation are known incompatibilities to resolve before merge. Keep API, Volume reconciler and LVMS implementation changes outside this feature. Future Storage status tracking is not required by this qualification.

## 9.3 How should the PRD's standalone-delete wording be interpreted?

- **Owner:** Storage and VMaaS maintainers / PRD owner.
- **Impact:** IC-5. The PRD says Volumes cannot be deleted independently while existing public Volume CRUD supports standalone Delete. This feature coordinates its own Delete calls with ComputeInstance cleanup and uses existing authorization. Clarifying the PRD does not authorize a Volume API deletion-policy change in this feature.

## 9.4 Resolved: what completion signal gates record and parent cleanup?

- **Owner:** VMaaS/Fulfillment maintainers; AAP/operator retains its existing workload-lifecycle contract.
- **Decision:** Use existing AAP/operator completion and finalizer behavior as the workload cleanup acknowledgment. At each existing Fulfillment parent-finalizer release point, delete the registered Volumes and wait for Get to confirm every record is absent. Successful Delete alone cannot complete the parent. [User: follow the existing finalizer pattern; supersedes stronger physical checks]
- **Guarantee and evidence:** This feature does not independently prove physical disk absence or add physical deletion/checkpoint/manual-recovery behavior. TC-D-01 proves deployed ordering, TC-D-02 covers record-delete/confirmation failures and TC-D-03 covers early cancellation, restart and all parent-finalizer release paths. Missing PV/CSI identity is not a new completion prerequisite. No Volume API or Storage status-tracking change is included.

---

## Provenance

Authored: draft @ design 0.11.5 - 1c6e8de, workspace design/OSAC-6040 @ d30e35d27
Final: revise @ design 0.11.5 - a58bdf7, workspace design/OSAC-6040 @ 0034f1eb6

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"a58bdf7","source_repo":"0034f1eb6","source_repo_branch":"design/OSAC-6040","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
