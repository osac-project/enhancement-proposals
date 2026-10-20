# Storage API Integration for ComputeInstance Volume Lifecycle

| Field | Value |
|-------|-------|
| Author(s) | Tzif |
| Jira | [OSAC-6037](https://redhat.atlassian.net/browse/OSAC-6037) |
| Design task | [OSAC-6040](https://redhat.atlassian.net/browse/OSAC-6040) |
| PRD | [prd.md](prd.md) |
| Date | 2026-10-20 |
| Status | Draft for review; implementation may start; Storage owns extra physical allocations caused by Volume API integration |

# 1. Overview

For each boot and additional disk on a newly created ComputeInstance, VMaaS will call the existing private Volume API with a stable metadata.name to create a Volume record and receive its ID. Fulfillment persists each disk key and Create dispatch state before Create, derives the request from the ComputeInstance's immutable ID, tenant/project and disk fields, and uses the existing List operation to recover a committed record if its response is lost. Fulfillment persists the per-disk IDs in ComputeInstance status before passing them to AAP. AAP puts each ID in an annotation on the corresponding DataVolume. Publishing this annotation completes the handoff to future Storage tracking; no Storage observer is included. [PRD: In Scope—creation and visibility; User: stable disk names and recovery without Volume API changes]

The preserved workload disk path starts with the ComputeInstance CR and its corresponding Ansible template. The ComputeInstance operator invokes that template through AAP; its DataVolume tasks use CDI, Kubernetes scheduling, the existing StorageClasses and vendor CSI provisioners for workload disk provisioning and removal. Fulfillment uses the Volume API to register records and later request their removal; current Volume reconciliation can also provision and delete backend resources. Extra physical disks created by Volume API alongside the ComputeInstance workflow are an accepted risk owned by Storage, including their handling and cleanup. This feature does not test for their absence or require proof of record-only behavior before implementation PRs merge. Storage owns any required API, reconciler or backend changes as separate work. Actual API success, ID correlation, record recovery and record-removal checks remain required. UI work remains separate. [User: agreement with Storage; Review: preserve the ComputeInstance CR/template path; Codebase: private Volume Create and Volume reconciliation]

Deletion consumes the existing AAP/operator completion acknowledgment. Fulfillment then deletes the registered Volume records and confirms their absence before releasing its parent finalizer; existing physical deletion checks and operations remain unchanged. [User: accepted finalizer pattern]

# 2. Goals and Non-Goals

## 2.1 Goals

- Create one Storage API record and retain its returned ID for each ComputeInstance boot/additional disk.
- Supply the required stable Volume name and recover the original ID after a lost Create response using existing API operations. Prove this recovery before release. [User]
- Carry each ID from Fulfillment through AAP to its matching DataVolume using an annotation.
- Publish the Volume ID annotation for possible future use by Storage.
- Preserve physical disk provisioning and deletion driven by the ComputeInstance CR and its corresponding Ansible template, through AAP, CDI, StorageClasses and vendor CSI.
- Use existing AAP/operator deletion completion before requesting Volume-record deletion, and retain the Fulfillment parent until every associated record is confirmed removed. [User: follow the existing finalizer pattern]
- Expose the per-disk Volume IDs in ComputeInstance status for correlation.

## 2.2 Non-Goals

- Change the existing ComputeInstance CR/template workload disk provisioning and deletion path, StorageClass selection, scheduling or vendor CSI behavior.
- Add physical deletion operations, runtime PVC/PV/backend cleanup verification, a physical-cleanup checkpoint or a manual-recovery state. Existing AAP checks and provider/finalizer completion semantics remain in use. [User]
- Detect, prevent or qualify the absence of extra physical disks created by Volume API alongside AAP; Storage owns that accepted risk. This does not waive caller recovery for duplicate or untracked Volume API records. [User: clarified physical-disk scope]
- Route VM disks through OSAC CSI.
- Add a Volume-to-ComputeInstance reverse link, independent attach/detach state, resize/migration, sharing, snapshots or backups.
- Change Volume API endpoints, request/response schemas, Create/Delete behavior, validation, authorization or idempotency. Changes to Volume reconciliation or backend handling, including LVMS handling, are also outside this feature.
- Implement or test a Storage DataVolume watcher, lifecycle-state mapping or Volume status-update mechanism. Future Storage tracking is not a delivery requirement for this feature.
- Change UI presentation, implementation or testing; those remain separate design and work.
- Adopt or replace disks for legacy ComputeInstances that have neither managed registration state nor recorded Volume IDs.

# 3. Motivation / Background

The existing ComputeInstance CR initiates provisioning through its corresponding Ansible template, executed by AAP. That template creates DataVolumes using the configured VM storage tiers; CDI, Kubernetes scheduling and the selected StorageClass provisioner create the physical disks. That path does not currently provide the Volume API ID as a DataVolume correlation value.

The current AAP delete role waits for VMI, VM and DataVolume absence, but does not explicitly wait for PVC/PV or backend deletion. The operator runs its existing deprovisioning lifecycle and releases the ComputeInstance CR finalizers according to that lifecycle. This feature consumes that completion boundary and adds Volume-record cleanup before the Fulfillment parent can be archived. It does not strengthen the physical-storage completion guarantee. [Codebase: osac-aap/collections/ansible_collections/osac/templates/roles/ocp_virt_vm/tasks/delete_resources.yaml; osac-operator/internal/controller/computeinstance_controller.go; User]

Current VMaaS removes Fulfillment's controller finalizer when the ComputeInstance CR is gone, subject to its existing cleanup branches. It does not coordinate associated Volume API records or wait for their Get calls to return NotFound. Record Delete/Get coordination and retaining the same finalizer until every record is absent are new Fulfillment caller behavior proposed by this feature. [Codebase: fulfillment-service/internal/controllers/computeinstance/computeinstance_reconciler_function.go:delete]

The existing Volume Delete API sets a deletion timestamp; finalizers can keep the record present after a successful RPC. The database archives the record only after its finalizers are gone. Existing Get reads deletion-pending records until archival. The normal Volume lifecycle removes the database finalizer after its Kubernetes CR disappears, relying on provider completion rather than an additional database-side disk check. The VMaaS caller must therefore confirm record absence through Get before releasing its own parent finalizer. [Codebase: generic_dao_delete.go; generic_dao_update.go; generic_dao_get.go; volume_reconciler_function.go]

The private Volume API already has Create and Delete operations, but its current Create implementation resolves the backend, sets the record to CREATING and causes Volume reconciliation that provisions storage. It also requires LVMS node topology for node-local volumes. The operator's Volume deletion path invokes the vendor provisioner when vendor state exists. An extra physical allocation is accepted under Storage ownership; receiving an ID does not imply that the API has no backend side effects. A rejected pre-AAP request still prevents the required ID handoff and remains a functional compatibility issue. TC-P-01 checks actual request acceptance, including LVMS without node topology that VMaaS does not yet have. Any required API, reconciler or LVMS changes belong to separate Storage work. [Codebase: fulfillment-service/internal/servers/private_volumes_server.go; fulfillment-service/internal/controllers/volume/volume_reconciler_function.go; osac-operator/internal/controller/volume_controller.go; User]

Create requires a caller-supplied metadata.name and clears a caller-supplied Volume ID. The existing API also exposes filtered List. Migration 100 enforces name uniqueness for Volumes within tenant/project, including records awaiting archival; after archival a name can be reused. These are existing building blocks for caller recovery, not an exactly-once Create or permanent idempotency-key guarantee. The combined recovery path must be qualified by TC-C-06 against the real API/database. [Codebase: private_volumes_server.go; proto/private/osac/private/v1/volumes_service.proto; fulfillment-service/internal/database/migrations/100_add_name_uniqueness_and_immutability.up.sql]

# 4. Design

## 4.1 Architecture

The existing workload path in this proposal is the ComputeInstance CR and its corresponding Ansible template, invoked by the operator through AAP. The Volume subsystem may also invoke AAP; that separate workflow is Storage-owned and is outside this change. [Review: workflow origin and scope]

### Synchronous request handling and asynchronous reconciliation

The synchronous ComputeInstance Create handler applies existing validation, Catalog/Template defaults and reference resolution, persists the ComputeInstance and returns it. The response does not wait for Volume registration or promise populated Volume IDs. After the ComputeInstance transaction commits, the asynchronous Fulfillment ComputeInstance reconciler owns finalizer protection, registration intent, dispatch serialization, Volume Create/List recovery and ID persistence. It completes registration before creating the managed ComputeInstance CR that starts the operator/template workflow. Volume Delete/Get confirmation also runs in this reconciler's asynchronous deletion path. [Review: clarify sync/async ownership; Codebase: private_compute_instances_server.go:Create/prepareCreate; computeinstance_reconciler_function.go:run/update/delete]

The reconciler preserves the existing add-finalizer-and-return sequence: when it adds the parent finalizer, it persists that update and returns; subsequent reconciliation proceeds from the committed state. Intent and the atomic attempted transition must likewise be committed before Volume Create is sent. Updating an in-memory object for persistence at the end of reconciliation is insufficient. Only the reconciler that successfully commits the dispatch claim may send that request; other reconcilers use the saved state and recovery rules below. [Codebase: computeinstance_reconciler_function.go:run/update; Review: execution and persistence boundary]

The VMaaS lifecycle covered by this feature is:

1. The asynchronous Fulfillment ComputeInstance reconciler validates and maps the persisted, resolved ComputeInstance disks using the per-disk Create contract below, then persists each disk key and registration dispatch/outcome state before making a Volume API call. Request names, tenant/project and disk specs are derived from the retained ComputeInstance.
2. Fulfillment calls the private Volume Create with that name and obtains the record ID. Storage owns any backend side effects of that API call. Known non-committed failures may be retried with the same name/request; ambiguous outcomes and AlreadyExists enter the List-based recovery contract below.
3. Fulfillment persists each returned or recovered disk-key/ID pair in ComputeInstance status before creating the managed ComputeInstance CR. An unresolved registration prevents that CR creation and the resulting Ansible template execution.
4. The existing ComputeInstance CR/operator/template workflow carries the same key/ID mapping to AAP.
5. AAP adds the ID to the matching DataVolume annotation and creates the DataVolume with its existing source and StorageClass.
6. CDI, Kubernetes scheduling and the existing vendor CSI provisioner create the physical disk.
7. On deletion, let the existing AAP/operator workflow perform its usual cleanup and checks. Resolve any attempted registrations before record cleanup. At the point the existing ComputeInstance lifecycle would release Fulfillment's controller finalizer, request deletion of every persisted Volume ID and confirm all records are absent through the existing Volume Get API. Only then release that finalizer and allow parent archival.

The Volume ID is created and persisted before AAP receives it. Passing the disk key with the ID prevents AAP from associating an ID with a different disk by list order. The handoff to future Storage tracking ends at writing the DataVolume annotation; this feature includes no Storage observer or Volume status-update step.

AAP adds the Volume ID to the DataVolume annotation osac.openshift.io/storage-volume-id. An annotation is the right fit for an opaque record identifier: it carries metadata but is not intended to select objects. Labels remain available for selectors if Storage later needs a separate stable discovery marker. See the Kubernetes documentation for [annotations](https://kubernetes.io/docs/concepts/overview/working-with-objects/annotations/) and [labels and selectors](https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/). Preserve existing tenant and applicable owner-reference annotations. Do not treat the Volume ID annotation as authorization evidence.

AAP continues to create the same boot and additional DataVolumes with the existing sources, StorageClasses and CDI behavior. Existing scheduling, vendor CSI provisioning, guest readiness and physical-disk deletion behavior remain unchanged. ComputeInstance readiness continues to follow the existing VM and DataVolume conditions; it does not wait for the Storage API record to become AVAILABLE.

The annotation supplies a correlation value that Storage may consume later. This feature does not implement, require or test a Storage consumer of that annotation, map DataVolume states to Volume states, or update Volume status.

### Per-disk Volume Create contract

Build requests from the persisted ComputeInstance spec after existing Catalog policies, Template defaults and storage-tier reference resolution have completed. Use the same resolved disk values projected into the ComputeInstance CR and consumed by AAP. Registration does not re-read Catalog/Template defaults, resolve a different tier, or apply AAP-local fallback values. Existing resolution stores both the tier ID and its canonical name; VolumeSpec.storage_tier consumes the name. [User; Codebase: private_compute_instances_server.go:prepareCreate/validateStorageTiers; utils/spec_defaults.go; computeinstance_reconciler_function.go:addExplicitFields]

| Volume Create field | Boot disk (`boot`) | Additional disk (`disk-N`, N starts at 1) |
|---------------------|--------------------|------------------------------------------|
| `spec.storage_tier` | `compute_instance.spec.boot_disk.storage_tier.name` | `compute_instance.spec.additional_disks.items[N-1].storage_tier.name` |
| `spec.size_gib` | `int64(compute_instance.spec.boot_disk.size_gib)` | `int64(compute_instance.spec.additional_disks.items[N-1].size_gib)` |
| `spec.access_mode` | `VOLUME_ACCESS_MODE_READ_WRITE_ONCE` | `VOLUME_ACCESS_MODE_READ_WRITE_ONCE` |

The tier value is the canonical StorageTier name, even when the original ComputeInstance request used a tier ID. ComputeInstanceDisk.size_gib and the ComputeInstance CR's DiskSpec.sizeGiB currently use int32; VolumeSpec.size_gib uses int64. Widening the resolved ComputeInstance value to int64 is lossless and preserves the requested integer GiB value without converting units or adding capacity. Both access modes explicitly match ReadWriteOnce in the current AAP boot and additional DataVolume tasks. The API requires a nonempty tier, positive size and non-UNSPECIFIED access mode; this mapping supplies all three. [Codebase: proto/private/osac/private/v1/compute_instance_common_type.proto:ComputeInstanceDisk; osac-operator/api/v1alpha1/computeinstance_types.go:DiskSpec; proto/private/osac/private/v1/volume_type.proto:VolumeSpec; private_volumes_server.go:validateVolumeCreate; osac-aap/collections/ansible_collections/osac/templates/roles/ocp_virt_vm/tasks/create_resources.yaml]

Other access modes, such as ReadWriteMany (RWX), can be supported in future work. Such support must keep the Volume Create access mode consistent with the corresponding DataVolume/PVC access mode in the ComputeInstance Ansible template and validate support in the selected storage tier/backend. This feature retains the current ReadWriteOnce behavior. [Review: future access-mode support]

Validate every resolved disk before dispatching the first Volume Create. A missing disk, missing/nonpositive size or missing canonical tier name prevents all Volume Create and AAP dispatch for that attempt and follows existing validation/provisioning error handling. Preserve the stored additional-disk order: `items[0]` maps to `disk-1`, `items[1]` to `disk-2`, and so on. An omitted list may already have received Catalog defaults during ComputeInstance creation; an explicitly empty list remains empty where the Catalog policy permits it. A resolved empty list creates only the boot record. Registration never inserts additional disks or copies boot values onto an additional disk.

Reconstruct each `VolumeSpec` from the persisted, immutable ComputeInstance disk fields using the mapping above. Known non-committed retries produce the same payload after restart even if Catalog/Template defaults later change; uncertain outcomes compare the recovered record against that same derived spec. The private registration state stores the disk key and Create dispatch/outcome, without a separate copy of the request spec. ComputeInstance disk size, tier and additional-disk order are immutable after creation. [Review: reuse parent data; Codebase: private_compute_instances_server.go:validateComputeDiskImmutability] Leave optional topology unset because VMaaS has no node placement before AAP; TC-P-01 checks whether the actual request is accepted for supported tiers, including LVMS. Storage owns any required compatibility fix. This defines caller behavior without changing Volume API fields or validation.

### Stable Volume names and Create recovery

The name passed in the existing Volume metadata.name field is `ci-<compute-instance-id>-<disk-key>`. Use the immutable, server-assigned Fulfillment ComputeInstance UUID and the disk's original key; do not use its display name or Kubernetes UID. For ComputeInstance 019a0112-3456-7890-abcd-0123456789ab, the names are:

```text
ci-019a0112-3456-7890-abcd-0123456789ab-boot
ci-019a0112-3456-7890-abcd-0123456789ab-disk-1
ci-019a0112-3456-7890-abcd-0123456789ab-disk-2
```

Derive each name from the immutable parent UUID and persisted disk key; the same formula produces the identical name across reconciliation, restarts and retries, without storing a separate name per disk. Validate the existing lowercase DNS-label/63-character constraint before dispatch; never truncate a name, renumber a disk or add a random retry suffix. The Volume ID is still generated by the API. The name is a correlation key, not authorization evidence or a new Volume API field. [User; Codebase: fulfillment-service/docs/API.md, internal/uuid/uuid.go]

1. **Persist intent and serialize dispatch in the asynchronous reconciler.** Follow the finalizer persistence sequence above before the first Volume Create. Save each disk key and its Create dispatch/outcome state in the private registration state from Section 4.2. Derive its name, tenant/project and request spec from the retained ComputeInstance. The expected Volume creator is the existing private API attribution value, `system`. Atomically mark the request attempted and commit that state before sending it, using the existing database locking/version mechanisms so concurrent reconcilers cannot independently dispatch the same intent. Keep successful IDs and unresolved intents across parent deletion requests.
2. **Recover after uncertainty.** A timeout, lost response, process crash before ID persistence or AlreadyExists triggers a fresh existing Volume List request for exact metadata.name, metadata.tenant and metadata.project equality. Use safely encoded filter literals and examine the complete matching result set/total; do not select the first result of an unfiltered or partial list. Derive the exact name and scope from the parent and disk key, verify the returned spec against the parent-derived mapping, require the private API creator `system`, and check deletion state before accepting the ID. The ComputeInstance creator is not the expected Volume creator. A name match alone is insufficient. Persist the recovered ID before any AAP dispatch.
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

This completion boundary confirms that the existing workload lifecycle finished according to its current policies and the associated Volume records were removed. It does not independently prove physical disk absence. Existing AAP failure/skip policies, storage reclaim behavior and provider cleanup limitations are inherited. The correlation annotation alone is not evidence of backend cleanup. Storage owns handling and cleanup of any extra physical disks caused by Volume API calls. Stronger physical verification or changes to Volume API/backend behavior require separate work. [User; Codebase: computeinstance_reconciler_function.go; computeinstance_controller.go; provision_lifecycle.go]

## 4.2 Data Model / Schema Changes

Add a read-only per-disk correlation list to ComputeInstance status, with one entry containing the stable disk key and returned Volume ID. This is the durable source Fulfillment uses to pass IDs to AAP and retry deletion. Public clients can correlate a boot or additional disk with its Storage API record without receiving vendor or backend details.

The public status list is written by Fulfillment's asynchronous ComputeInstance reconciler; other status writers must preserve it. Legacy ComputeInstances with neither registration state nor ID entries are not adopted or assigned records during this work. A managed instance with unresolved registration state remains managed even when its public ID list is still empty.

The additional private state supports recovery when Volume Create commits but its response is lost, or the reconciler stops before saving the returned ID. In that window, public status.volumes has no ID for the disk even though its Volume record may exist. After restart, the reconciler reconstructs the request from the retained ComputeInstance and uses the saved dispatch history to recover the record, validate the match and resolve it before parent cleanup. These are the existing Section 4.1 recovery requirements, qualified by TC-C-06. [Review: rationale for private registration state]

Add private Fulfillment ComputeInstance status.volume_registration entries containing only the disk key and Create dispatch/outcome state. That state distinguishes work never attempted, a known non-committed failure, an uncertain outcome and a resolved registration. Persist it before Volume Create, and persist returned or recovered IDs in public status.volumes with the resolved private registration state in one status update. Keep registration state out of the generated public API using the existing private-field mechanism. Public status.volumes remains only disk_key/volume_id pairs. This state lives with existing ComputeInstance persistence; no separate allocation database or new Volume field is introduced. [Review: remove duplicated registration data]

| Recovery information | Source |
|----------------------|--------|
| Disk key and Create dispatch/outcome | Private status.volume_registration; progress that cannot be reconstructed from desired state. |
| Returned or recovered Volume ID | Public status.volumes entry for the disk key. |
| Volume request name | `ci-<compute-instance-id>-<disk-key>`, derived from the immutable parent ID and disk key. |
| Exact tenant/project | Persisted, immutable ComputeInstance metadata, including the empty/default project. |
| Expected VolumeSpec | Persisted, immutable ComputeInstance disk fields and Section 4.1's mapping, including READ_WRITE_ONCE and unset topology. |
| Expected Volume creator | Existing private API attribution: `system`, independently of the ComputeInstance creator. |

The parent is the source of request identity, scope and disk values throughout recovery. Per-disk registration entries do not duplicate names, tenant/project, creator or VolumeSpec. Each Volume record still has its normal API metadata/spec. The private Volume API assigns creator `system`; a user-created ComputeInstance may have a different creator, so recovery does not compare those creators for equality. [Codebase: generic_server.go:setCreator; system_attribution_logic.go:DetermineAssignedCreator; register_servers.go:privateVolumesServer; migrations/69_add_project_column.up.sql; private_compute_instances_server.go:validateComputeDiskImmutability]

The existing Fulfillment parent finalizer retains the ComputeInstance metadata/spec, registration state and IDs through record cleanup. Restarted reconciliation repeats Get/Delete using those IDs; it does not require a physical-disk inventory, an AAP-dispatch marker or an additional operator CR cleanup checkpoint.

The ComputeInstance API/protobuf status addition is additive. No schema migration is expected if the existing status persistence supports the additive field; confirm this against the implementation during decomposition. Update source protos and regenerate through the documented proto workflow if the field is added.

## 4.3 API Changes

The public API schema addition is the ComputeInstance status correlation list described below. Private Fulfillment status gains registration state from Section 4.2. This feature makes no changes to the Volume API's RPCs, request/response messages, validation, authorization or Create/Delete behavior. Fulfillment consumes Create/Delete for record registration/removal, filtered List for Create recovery and Get for confirmation of record removal. TC-P-01 checks these API interactions; Storage owns physical backend side effects.

Fulfillment derives `metadata.name = ci-<compute-instance-id>-<disk-key>` on every Create and recovery lookup, uses the parent tenant/project and mapped disk spec, and stores the returned or recovered ID in ComputeInstance status. Recovery uses existing List filter fields for exact name/tenant/project matching. The mapping passed to AAP contains the same disk key and Volume ID; the name never substitutes for that ID in the DataVolume annotation or Volume Delete.

Every Create supplies the canonical disk tier name, the same requested integer GiB size and explicit READ_WRITE_ONCE access mode from Section 4.1's per-disk mapping. TC-C-01 asserts each field for boot and additional disks, defaulted inputs, tier-ID resolution, empty lists, invalid inputs and identical retries derived from persisted parent data.

The public ComputeInstance status exposes a read-only list equivalent to status.volumes[{disk_key, volume_id}]. Public Create/Update callers cannot choose, replace or clear those IDs. Volume visibility and ComputeInstance visibility remain tenant-scoped under existing API authorization.

The existing AAP-job/operator deprovisioning completion path is consumed unchanged. The added gate runs before Fulfillment releases its parent finalizer and requires existing Volume Get to confirm record absence. No new Storage API completion signal is introduced, and DELETED status alone cannot release the parent.

Extra physical allocation caused by Volume API alongside AAP does not block this feature's implementation PRs; Storage handles it under the accepted agreement. A Create rejection, unresolved record identity or failure to confirm record removal still follows the caller failure handling below and cannot be reported as successful provisioning or cleanup. Required API changes belong to separate Storage work. Implementing a Storage DataVolume observer or updating Volume status is also separate future work.

## 4.4 Scalability and Performance

For a ComputeInstance with N disks, the successful path adds N Volume record Create calls, N private registration entries, N public ID entries, N DataVolume annotations and N record Delete calls. Recovery adds narrowly filtered List requests for unresolved disks. Deletion confirmation makes O(N) ID-based Get calls per reconciliation under existing controller backoff; it adds no Kubernetes inventory scan or direct CSI/backend RPC. The existing AAP workload path is unchanged; Volume API backend side effects may add Storage-owned allocation and cleanup work.

The design adds no Storage status observer, periodic background scan, metrics or latency SLA. Fulfillment retains the per-disk IDs while the ComputeInstance is active or deleting and until all records are confirmed absent after existing workload cleanup.

## 4.5 Security Considerations

Use authenticated private API access for record creation and deletion. Fulfillment derives tenant/project attribution from the ComputeInstance and does not trust caller-supplied status IDs. Only Fulfillment lifecycle handling may write the public correlation list.

Recovery reads the exact tenant/project from the retained ComputeInstance metadata, including the empty/default project, and uses that scope for lookup and record cleanup. It derives the request name from the parent UUID and disk key and the expected spec from the immutable parent disk fields. Before adopting a match, verify those values, deletion state and the private API creator `system`; the parent creator may differ. No per-disk copies of scope, creator or request spec are needed. A conflicting record must not be adopted, changed or deleted. Keep private dispatch/outcome state out of public responses and avoid logging full request payloads or creator details. No Volume reverse-reference field or new Volume annotation is required for recovery. [Review: use ComputeInstance as source; Codebase: system_attribution_logic.go]

Fulfillment derives the disk-key/ID mapping from authenticated API responses for the owning ComputeInstance tenant. AAP writes that mapping on the corresponding tenant DataVolumes and preserves osac.openshift.io/tenant and applicable osac.openshift.io/owner-reference annotations. The annotation grants no permission to read or modify a Volume. Do not put credentials, provider identifiers or sensitive backend details in the DataVolume or public ComputeInstance status.

Record-cleanup reads and Delete calls use the saved IDs and the same authorized parent tenant/project context used for registration. Validate that returned records match that scope. An authorization error or caller-scope change cannot establish record absence. No new cluster-scoped storage reads or backend credentials are required by this feature.

## 4.6 Failure Handling and Recovery

| Failure | Behavior |
|---------|----------|
| A resolved boot/additional disk is missing a valid size or canonical tier name | Reject invalid input through existing validation; if encountered in persisted reconciliation state, report the provisioning error. Dispatch neither Volume Create nor AAP for that attempt until all disk mappings are valid. |
| Volume Create is positively known not to have committed | Rebuild the same name/request from the retained parent and retry that disk intent under the existing controller policy. Do not start AAP with an incomplete ID mapping. |
| One disk Create succeeds and a later disk Create fails | Retain the known ID. Retry the same named request only for a known non-committed failure; otherwise use List recovery. Do not start AAP until all required IDs are persisted. |
| AAP fails after IDs are stored | Retry AAP with the same disk-key/ID mapping. Do not create replacement records for disks whose IDs are already persisted. |
| AAP creates a DataVolume but loses its response | Retry with the same ID and disk key; the DataVolume annotation remains the correlation value. Existing AAP idempotency behavior applies. |
| Create commits but its response is lost, ID persistence fails or the caller restarts | Recover through existing List using the derived name and the parent's exact tenant/project, validate the result and persist the same ID. Do not issue another Create while the outcome remains ambiguous. |
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

Any future switch of the VM workload disk path to OSAC CSI or a different physical-disk owner requires a separate design decision. Storage owns changes to the separate Volume API backend path.

# 5. Interface Changes

The PRD has no numbered FR/NFR identifiers. Requirements below refer to its actual In Scope and Dependencies bullets. Interface numbers remain stable; removed interface changes are retired and their numbers are not reused. The previous IC-2 (CSI claim resolution), IC-7 (provider lifecycle changes), IC-8 (CSI deployment configuration) and IC-10 (new Storage readiness interface) are retired because this direction does not introduce those changes.

## IC-1: DataVolume Volume ID annotation and existing physical disk path

**Requirements:** In Scope—creation; Dependencies—private Storage API.

The ComputeInstance CR's corresponding Ansible template receives the disk-key/Volume-ID mapping through the existing operator/AAP workflow and adds osac.openshift.io/storage-volume-id to each corresponding DataVolume. Existing tenant and owner-reference annotations remain. The existing CDI, StorageClass, scheduler and vendor CSI path provisions the physical disk. OSAC CSI is not used for these VM disks.

## IC-3: Private Volume record creation and durable ID correlation

**Requirements:** In Scope—creation and visibility; Dependencies—private Storage API.

Fulfillment's asynchronous ComputeInstance reconciler maps each persisted resolved disk to its canonical tier name, integer GiB size and explicit READ_WRITE_ONCE access mode using Section 4.1. It derives the stable `ci-<compute-instance-id>-<disk-key>` name and tenant/project from the retained parent and commits the disk key and dispatch/outcome state before calling existing Volume Create. Recovery checks the reconstructed request and the private API creator `system`. It recovers an uncertain result through exact-scope existing List, validates the match and persists the original ID before creating the managed ComputeInstance CR with the key/ID mapping for AAP. Concurrent reconciliation preserves a single durable intent per disk. TC-C-01 qualifies the synchronous/asynchronous boundary, exact payload mapping and identical retries reconstructed from the parent; TC-C-06 must qualify lost-response recovery before release. TC-P-01 covers actual API acceptance and record lifecycle; no Volume API schema, lookup operation or server-side idempotency behavior is added by this feature.

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
| Keep the ComputeInstance CR and its Ansible template as the workload disk path, using AAP/CDI/vendor CSI | Route VM claims through OSAC CSI | Would change the existing workload provisioning path. The requested design retains that path and assigns any extra Volume API backend allocations to Storage. |
| Put Volume ID in a DataVolume annotation | Put the ID in a label | Labels support selection but are intended for queryable classification and have value-format/length limits. The Volume ID is opaque correlation metadata and no selection by ID is required. Use a separate label only if Storage later needs a selector. |
| Stable name, persisted request intent and existing scoped List | Generate a fresh name on retry or require a new Volume idempotency field | Names are already mandatory. Deriving the same identity from the immutable parent and disk key permits recovery and uniqueness checks without API changes; a fresh retry name can hide a committed record. TC-C-06 qualifies the actual recovery contract. |
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

### Storage ownership and API compatibility

Storage owns any extra physical disks created by Volume API alongside the existing AAP workload path, including their handling and cleanup. Such duplication is accepted for this feature. There is no VMaaS test or special merge prerequisite proving zero extra physical allocations or record-only backend behavior. VMaaS adds no backend-operation observer or duplicate-disk cleanup mechanism. [User: agreement with Storage; clarified to mean extra physical disks, not duplicate API records]

Functional API validation remains required: Create must accept the actual pre-AAP request and return a usable ID, and Delete/Get must support confirmed record removal. TC-P-01 retains those assertions, including LVMS without unavailable node topology; H4 retains the deployed workload/record lifecycle cases. Current LVMS rejection is a separate compatibility issue for Storage to resolve. Accepting physical duplication does not turn a failed API request into a successful handoff or cleanup.

Release is blocked until TC-C-06 demonstrates recovery after a real committed Create loses its response, including caller restart, concurrent reconciliation and later cleanup of the original record. Existing uniqueness/filtering code is supporting evidence, not a passing recovery test. A failure of the consumed API contract requires separate Storage follow-up without widening this feature's API scope.

The accompanying [test plan](testplan.md) assigns VMaaS caller/status, AAP annotation, record-deletion/absence and API compatibility tests to DEV, and deployed existing-lifecycle/record-cleanup ordering to QE. It treats the Volume API and AAP/operator completion as consumed dependencies. Implementation of new Volume API behavior, duplicate physical disk handling, production physical-cleanup verification and future Storage status tracking are outside this feature.

# 9. Open Questions

## 9.1 Defined recovery contract; release qualification remains required

- **Owner:** VMaaS maintainers.
- **Decision:** Persist per-disk dispatch/outcome state before Create; derive stable request names, exact tenant/project and expected disk specs from the retained ComputeInstance. Recover through existing List, validate the derived values and private API creator `system`, and persist the original ID. Ambiguous outcomes cannot authorize another Create. Section 4.1 defines the caller contract and cancellation handling. [User]
- **Release gate:** TC-C-06 must pass against real API/database commits. If it cannot, keep this feature blocked and raise separate Storage work; neither a mocked success nor the successful-ID-return assumption closes the gap. Name reuse after independent deletion/archival is not an idempotency guarantee and must not trigger automatic replacement.

## 9.2 Storage-owned physical side effects and LVMS request compatibility

- **Owner:** Storage owns extra physical disk handling and any API/reconciler/LVMS changes; VMaaS DEV owns caller/API compatibility assertions in TC-P-01.
- **Decision:** Extra physical disks created by Volume API alongside AAP are accepted under Storage ownership, with no absence test or special merge gate. Record recovery and record-removal requirements remain in force. [User]
- **Impact:** Sections 3, 4.3 and 8. VMaaS sends no node topology before AAP; the current LVMS API rejects that request. TC-P-01 must establish actual request acceptance for supported tiers; any required compatibility fix is separate Storage work. No passing LVMS result or implementation fix is claimed here.

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

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"a58bdf7","source_repo":"0034f1eb6","source_repo_branch":"design/OSAC-6040","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
