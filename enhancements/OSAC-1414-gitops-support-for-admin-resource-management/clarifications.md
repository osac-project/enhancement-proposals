# Clarification Log — OSAC-1414

## Status

- Rounds completed: 1
- Open gaps: 1
- Exit criteria met: No

## Round 1 — User workflows and synchronization behavior

### R1.Q1: Personas and access

The ticket names Cloud Provider Admin, while several in-scope resources also
relate to Cloud Infrastructure Admin responsibilities. Which persona or
personas should be able to register Git sources, manage platform resources,
and view sync status? Should tenant personas have no access to these workflows?

#### Answer

As stated in Jira, Cloud Provider Admin is the persona for this feature.
Tenant-facing resource GitOps is out of scope.

#### Impact

The PRD will identify Cloud Provider Admin as the user of GitOps management and
will retain the ticket's tenant-facing exclusion.

#### Decision (D1)

Cloud Provider Admin is the persona for GitOps management; tenant-facing
resource GitOps is out of scope.

---

### R1.Q2: User interfaces

The ticket calls for API CRUD for Git references and `osac apply -f` in the
CLI, but does not describe how users register Git sources or view their sync
status. Should those workflows also be available in the UI? Which management
and status operations should the UI and CLI support, in addition to the API?

#### Answer

Jira specifies GitReference CRUD and status reporting through the API, and
requires CLI support for `osac apply -f`. It does not specify UI support or
CLI commands for managing Git references.

#### Impact

The PRD will preserve the API and apply-CLI behaviors stated in Jira and will
not add UI or GitReference-management CLI requirements based on this ticket.

#### Decision (D2)

The scoped interfaces are the API for GitReference CRUD and status, plus the
CLI `osac apply -f` command. UI support and CLI GitReference management are
not included as requirements because Jira does not specify them.

---

### R1.Q3: Sync freshness

The ticket includes a poll interval but gives no expected time from a commit to
an applied change. Should admins be able to configure the polling interval for
each Git reference?

#### Answer

Yes. The polling interval should be configurable per Git reference.

#### Impact

Admins can set the polling interval for each Git reference. A fixed
commit-to-apply delay is not established.

#### Decision (D3)

The polling interval is configurable per Git reference.

---

### R1.Q4: Deletion safety with partial apply

Jira says multi-file applies are best-effort and non-atomic, with error
reporting, and that resources removed from Git are deleted. The desired state
must be clear before deletion. If all files can be read and parsed but applying
one present resource fails, should resources confirmed absent from that
complete inventory still be deleted?

#### Answer

Deletion must wait until the desired state is clear. Once the complete Git
inventory is known, any apply error in that sync blocks deletion of resources
confirmed absent from it. Deletion can proceed on a later error-free sync.

#### Impact

The system must have a complete, readable inventory before it treats an absent
resource as removed. If any apply operation fails during the sync, deletions
wait until a later error-free sync.

#### Decision (D4)

Do not delete resources based on an incomplete or ambiguous Git inventory.
Any apply error blocks deletion for that sync, even if the inventory is
complete; deletion can proceed in a later error-free sync.

---

### R1.Q5: Git reference and resource ownership lifecycle

The ticket says resources removed from Git are deleted and direct API updates
or deletes of Git-managed resources are rejected, but it does not say what
happens when a Git reference is deleted or disabled. Should its managed
resources be deleted, retained and made editable, or retained and still
protected? Should admins have a supported way to detach a resource for manual
management?

#### Answer

Intentionally left open at the user's direction; no behavior was selected.

#### Impact

Resource retention and the transition to manual management remain undefined
when an admin deletes or disables a Git reference.

#### Owner

Feature owner (to be assigned).

---

## Remaining Gaps

- **Open question — Git reference deletion:** Decide whether managed resources
  are deleted, retained and editable, or retained and protected when the Git
  reference is deleted or disabled, and whether admins can detach resources.
  **Owner:** Feature owner (to be assigned). **Impact:** Resource retention and
  the handoff to manual management remain undefined.

## Design Follow-up

- Confirm which repository credential types work with existing secret
  references. Jira excludes new secret management integration.
