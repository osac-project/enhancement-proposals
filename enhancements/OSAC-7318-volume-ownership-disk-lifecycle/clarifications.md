# Clarification Log — OSAC-7318

## Status

- Rounds completed: 6
- Open gaps: 1
- Exit criteria met: No — VM deletion behavior for independently created and
  transferred volumes remains a tentative policy for VMaaS Design to validate.

## Round 1 — Ownership, delete semantics, and terminology

### R1.Q1: Moving a volume between ComputeInstances

No multi-ownership (sharing one volume between two VMs) is recorded as a locked
decision. Is moving a volume from one ComputeInstance to another in scope —
remove disk from VM A, then add disk to VM B?

#### Answer

Yes — remove then add elsewhere.

#### Impact

The PRD needs a transfer path expressed as two separate operations, with one
owner at a time. This makes the no-sharing constraint a real boundary rather
than a lifetime lock.

#### Decision (D1)

A volume is added to at most one ComputeInstance at a time. Sharing a single
volume between two ComputeInstances is not supported and is not a goal of this
PRD.

#### Decision (D2)

Transfer between ComputeInstances is supported as two operations: remove disk
from the current ComputeInstance, then add disk to the other.

---

### R1.Q2: Deleting a volume that is added to a ComputeInstance

What should happen when a tenant deletes a volume that is currently added as a
disk to a ComputeInstance? Delete ends with the backing PVC and the array
volume removed.

#### Answer

Reject until remove disk.

#### Impact

Delete gains a precondition that the PRD must state, and the rejection message
becomes a user-visible behavior worth defining.

#### Decision (D3)

Deleting a volume is a distinct action from remove disk. Delete is rejected
while the volume is added to a ComputeInstance; the tenant removes the disk
first. A completed delete removes the backing PVC and the volume from the
storage array.

---

### R1.Q3: Volumes created during ComputeInstance provisioning

For volumes created as part of ComputeInstance provisioning, the boot disk and
any data disks declared at creation: when the ComputeInstance is deleted, what
happens to those volumes?

#### Answer

Deleted with the VM. Round 3 clarified that this is in scope, and VMaaS owns
that behavior.

#### Impact

The PRD states the outcome as a requirement and records VMaaS ownership of the
deletion behavior in Dependencies.

#### Decision (D4)

Volumes provisioned as part of creating a ComputeInstance are deleted when that
ComputeInstance is deleted. VMaaS owns this behavior.

---

### R1.Q4: What a tenant sees about a volume

What should a tenant be able to see about a volume's disk usage and deletion
state?

#### Answer

Simple states plus a failure reason, with other in-progress detail surfaced as
events.

#### Impact

The PRD describes the states a tenant reads and the failure reason, and treats
intermediate progress as events rather than additional states.

#### Decision (D5)

A tenant sees whether a volume is ready and not added to any ComputeInstance, is
in use by a named ComputeInstance, is being deleted, or has failed with a
reason. Intermediate progress is surfaced as events, not as additional states.

---

### R1.Q5: Create-time versus runtime disk changes

Do the add disk and remove disk terms apply to disks declared when the
ComputeInstance is created, or only to changes made later?

#### Answer

Both — same terms.

#### Impact

The PRD uses one vocabulary for disks declared at creation and disks changed
later.

#### Decision (D6)

Add disk covers disks declared in the ComputeInstance create request and disks
added later. Remove disk covers removing a disk from an existing
ComputeInstance.

---

## Round 2 — Lifecycle, interfaces, and failure

### R2.Q1: Scope of deletion with the VM

Does deletion with the VM apply to every volume added to the ComputeInstance or
only those created as part of its provisioning?

#### Answer

Initially answered that the PRD should not handle this concern; clarified in
Round 3 that deletion with the VM is in scope and VMaaS is responsible for it.

#### Impact

No scope change. See D4.

---

### R2.Q2: Remove disk on a running ComputeInstance

Can a tenant remove disk while the ComputeInstance is running?

#### Answer

Allowed while running.

#### Impact

The PRD states running-VM removal as supported, alongside adding a disk to a
running VM.

#### Decision (D7)

Add disk and remove disk are both supported while the ComputeInstance is
running.

---

### R2.Q3: Tenant-facing interfaces

Which tenant-facing interfaces must expose add disk and remove disk in this
milestone? UI is out of scope.

#### Answer

API + CLI.

#### Impact

User stories and acceptance scenarios reference the API and the `osac` CLI, and
the PRD states that console support is deferred.

#### Decision (D8)

The Fulfillment API and the `osac` CLI expose add disk, remove disk, and delete
volume. Console support is deferred and out of scope.

---

### R2.Q4: Partial delete failure

If removing the PVC or the array volume fails partway through delete, what
should the tenant see and be able to do?

#### Answer

Failed state, retryable.

#### Impact

The PRD defines the failed state, the reason shown, and tenant-initiated retry.

#### Decision (D9)

A delete that fails shows the volume in a failed state with a reason, and the
tenant can retry the delete.

---

### R2.Q5: Quota

Does tenant quota apply to add disk and to volume creation, and what does the
tenant see when a limit is hit?

#### Answer

Quota enforcement is given, because that is what the Volume API already does.

#### Impact

No new quota work. The PRD records existing Volume API quota behavior as a
dependency and assumption rather than a requirement of this Feature.

#### Decision (D10)

Quota enforcement is inherited from existing Volume API behavior. This PRD does
not add or change quota semantics.

---

## Round 3 — Scope reconciliation

### R3.Q1: VM-deletion contradiction

Round 1 chose deletion with the VM; Round 2 said the PRD should not handle the
concern. Which stands?

#### Answer

In scope, meaning delete with the VM; VMaaS is responsible for that.

#### Impact

See D4. The PRD states the user-visible outcome and names VMaaS as the owner of
the behavior.

---

### R3.Q2: Relationship to OSAC-5888 and OSAC-5889

The Feature's Out of Scope delegates the attach journeys to OSAC-5888/5889, but
the direction is that this PRD covers add disk, remove disk, and delete volume.
How should the PRD treat those sibling Features?

#### Answer

PRD owns the journeys.

#### Impact

The PRD describes the tenant-visible journeys end to end. OSAC-5888 and
OSAC-5889 are recorded as implementation and tracking vehicles, not as separate
user-facing scope. The Feature's Out of Scope wording is superseded by this
decision and the Feature body should be corrected to match.

#### Decision (D11)

This PRD owns the tenant-visible add disk, remove disk, and delete volume
journeys end to end. OSAC-5888 and OSAC-5889 are implementation tracks for those
journeys.

---

## Round 4 — Disk source

### R4.Q1: What "source" means for a VM disk

The Volume API should support a source for a VM disk. Which sources are in
scope for this milestone?

#### Answer

Source is whatever VMaaS supports today, for example specifying a container disk
image such as `quay.io/my-org/golden-image`. Expanding to OSAC images or
snapshots is future work.

#### Impact

The PRD states source support as a goal and scopes it to today's VMaaS
capability, with OSAC disk images and snapshots deferred.

#### Decision (D12)

The Volume API supports a source for a VM disk. In this milestone the source is
what VMaaS supports today: an OCI registry image reference, for example
`quay.io/my-org/golden-image`. OSAC disk images, snapshots, and cloning are not
sources in this milestone.

---

### R4.Q2: Which disks carry a source

Does the source apply to every ComputeInstance disk, or only the boot disk?

#### Answer

Whatever VMaaS supports today.

#### Impact

The PRD does not narrow source support to a single disk; it preserves the disk
options tenants have now.

#### Decision (D13)

Source support covers the same disks VMaaS supports today. The PRD does not
introduce a new restriction on which disk may declare a source.

---

### R4.Q3: New capability or preserved behavior

Is creating a volume with a source a new tenant-visible capability in this PRD,
or is it there to keep existing ComputeInstance disk behavior intact?

#### Answer

Preserve existing behavior.

#### Impact

No new standalone "create a volume from an image" workflow is described as a
new capability. The PRD states that disk options available today continue to
work when the disk is backed by an OSAC volume.

#### Decision (D14)

Source support preserves existing ComputeInstance disk behavior. This PRD does
not introduce a new tenant-visible workflow for creating a standalone volume
from an image.

---

## Round 5 — Review feedback and scope corrections

### R5.Q1: VM deletion of pre-existing and transferred volumes

The review asked what happens when a ComputeInstance is deleted while it has a
separately created volume added as a disk, and how deletion behavior changes if
a volume is moved from one ComputeInstance to another.

#### Answer

The preferred direction is to delete volumes currently added to a
ComputeInstance when that instance is deleted. When a volume is removed from one
ComputeInstance and added to another, the deletion behavior should follow the
current ComputeInstance. This is tentative and needs further investigation,
without blocking this PRD.

#### Impact

The PRD records the current-attachment behavior as a tentative assumption.
OSAC-5888 and OSAC-5889 currently describe different VM-deletion boundaries and
need alignment in the follow-on work.

---

### R5.Q2: Existing boot-image source behavior

The review noted that the current ComputeInstance API accepts a DiskImage
reference rather than a raw OCI registry URL, and that the current image source
applies to the boot disk, not additional data disks.

#### Answer

Preserve current behavior. Tenants select an existing DiskImage for the boot
disk; the DiskImage contains the underlying registry reference. This Feature
does not add raw URL input or image sources for data disks.

#### Impact

The PRD preserves the existing boot DiskImage experience without promising a
new image-source workflow. This supersedes D12 and D13 to the extent they imply
that tenants provide raw registry URLs or that every disk supports an image
source.

#### Decision (D15)

Preserve the current boot DiskImage selection behavior for Volume-backed boot
disks. Do not add raw registry URL input or DiskImage sources for data disks in
this Feature.

---

### R5.Q3: Failed add or remove disk

The review asked what association a tenant sees after an add or remove disk
operation fails, and how they recover.

#### Answer

Keep the last confirmed attachment state, show the failure, and allow the
tenant to retry the same operation.

#### Impact

The PRD specifies visible failure and retry behavior for add/remove, in addition
to the existing delete-retry behavior.

#### Decision (D16)

If add or remove disk fails, the last confirmed volume-to-ComputeInstance
association remains in effect and visible. The tenant sees the failure reason
and can retry the same operation.

---

### R5.Q4: Project scope for a volume and ComputeInstance

The review asked whether an attachment can cross project boundaries within a
tenant.

#### Answer

The volume and ComputeInstance must be in the same project. Cross-tenant
requests remain rejected by tenant isolation.

#### Impact

The PRD states same-project validation alongside the tenant boundary.

#### Decision (D17)

A volume may be added as a disk only to a ComputeInstance in the same tenant
and project.

---

### R5.Q5: Quota behavior

The review questioned the statement that Volume API quota enforcement already
exists.

#### Answer

Remove that enforcement claim. This Feature does not add or define quota
behavior.

#### Impact

The PRD no longer describes quota enforcement as an existing Volume API
guarantee.

#### Decision (D18)

This Feature does not define or change storage quota behavior and does not
assert that the current Volume API enforces a volume quota.

---

## Round 6 — Additional VM lifecycle constraints

### R6.Q1: Warning before ComputeInstance deletion

The review asked whether a tenant must receive a separate warning and
confirmation before deleting a ComputeInstance that has volumes added as
disks.

#### Answer

No additional warning or confirmation step is required by this Feature.

#### Impact

The PRD states the VM-deletion outcome and explicitly does not add a separate
pre-delete confirmation requirement.

#### Decision (D19)

Deleting a ComputeInstance does not require an additional warning or
confirmation step for its currently added volumes.

---

### R6.Q2: Cross-cluster volume move

The review asked whether a volume can be moved to a ComputeInstance in a
different VMaaS cluster.

#### Answer

A volume can be moved only between ComputeInstances on the same VMaaS cluster.
A cross-cluster add request is rejected with a clear reason.

#### Impact

The PRD limits volume moves to a single cluster and makes the rejection visible
to the tenant.

#### Decision (D20)

Cross-cluster volume moves are not supported. Add disk rejects a target
ComputeInstance on a different VMaaS cluster with a clear error.

---

## Remaining Gaps

1. VMaaS Design must validate the tentative policy for deleting independently
   created or transferred volumes when their current ComputeInstance is
   deleted. This policy remains open and is intentionally not a blocker for this
   PRD.

Storage tier, volume size, and volume type selection continue to use existing
Volume API behavior and are not redefined here.
