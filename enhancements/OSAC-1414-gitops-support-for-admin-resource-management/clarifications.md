# Clarification Log — OSAC-1414

## Status

- Rounds completed: 1
- Open gaps: 2
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

The PRD preserves Jira's API and apply-CLI requirements. Whether the feature
also needs UI support remains open under R1.Q7.

#### Decision (D2)

The Jira-specified interfaces are the API for GitReference CRUD and status,
plus the CLI `osac apply -f` command. Jira does not require UI support or CLI
GitReference management; the need for UI support remains open under R1.Q7.

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

### R1.Q4: Deletion safety with partial apply and reference overlap

Jira says multi-file applies are best-effort and non-atomic, with error
reporting, and that resources removed from Git are deleted. Should resources
confirmed absent from a complete inventory be deleted when another resource
apply fails? If another active Git reference declares the same resource, may it
be deleted based on only one reference's inventory? Reference cardinality and
overlap policy are addressed in R1.Q9.

#### Answer

The inventory must be complete and unambiguous before a resource is considered
absent. Apply errors do not block unrelated deletions; design will define
ordering and retries for dependent operations, including deletions needed
before replacements. If multiple references may declare the same resource,
deletion waits until complete inventories show it is absent from every active
reference. R1.Q9 remains open on whether multiple references and overlapping
declarations are supported or rejected.

#### Impact

The system needs a complete, readable inventory before treating a resource as
removed. An apply failure does not block unrelated deletions; design defines
safe ordering and retries for dependent operations, including deletions needed
before replacements. When multiple references may declare the resource,
deletion waits until it is absent from all active references. R1.Q9 remains open
on whether multiple references or overlapping declarations are supported.

#### Decision (D4)

Delete a resource only after complete, unambiguous inventories show it is absent
from every active reference that can declare it. If overlapping declarations
are supported, a resource remains while any active reference declares it. An
apply error does not block unrelated deletions. Design defines ordering and
retries for dependent operations, including deletions needed before
replacements; incomplete or ambiguous inventories never trigger deletion.
R1.Q9 remains open on whether multiple references and overlaps are supported.

---

### R1.Q5: Git reference deletion

The ticket says resources removed from Git are deleted and direct API updates
or deletes of Git-managed resources are rejected, but it does not say what
happens when a Git reference is deleted. Should its managed resources be
deleted, retained and made editable, or retained and still protected?

#### Answer

Deleting a Git reference retains its resources and removes that reference's
ownership associations. Resources released from Git management can be edited
or deleted through the normal API and CLI paths. The user supplied this answer
from approvers on 2026-11-02.

Any remaining management by other Git references is governed by the overlap
policy in R1.Q9.

#### Impact

Deleting a reference does not cascade-delete its resources. Manual management
becomes available when Git management is released.

#### Decision (D5)

Deleting a Git reference retains its resources and removes that reference's
ownership associations so resources released from Git management can be edited
or deleted manually.

---

### R1.Q6: Direct writes to platform-scoped resources

May admins use the API or CLI to create or update platform resources not
managed by Git, or must all writes to in-scope platform resources come from
Git sync?

#### Answer

Admins can create or update resources not managed by Git through the API or
CLI, including `osac apply -f`. Manual updates and deletes of Git-managed
resources are rejected through every API and CLI write path, including apply.
Changes to Git-managed resources are applied through Git sync. The user
confirmed this policy while addressing Avishay's review on 2026-11-02.

#### Impact

Regular admin write workflows remain available for resources outside Git
management. Every API and CLI write path must enforce the protection of
Git-managed resources.

#### Decision (D6)

Admins may create or update resources not managed by Git through the API or
CLI. Manual updates and deletes of Git-managed resources are rejected through
every API and CLI write path, including `osac apply -f`; changes to those
resources come through Git sync.

---

### R1.Q7: UI support

Should Cloud Provider Admins have a UI to register and configure Git references
(repository, branch or tag, directory, existing credential reference, and
polling interval) and view the latest observed commit SHA, sync errors, and resources
associated with each reference, or are API GitReference CRUD/status and the
CLI `osac apply -f` sufficient?

#### Answer

Intentionally left open at the user's direction; UI support has not been
decided.

#### Impact

This determines whether OSAC UI workflows for source configuration and sync
status are part of the feature scope.

#### Owner

Feature owner (to be assigned).

---

### R1.Q8: Initial sync and retry behavior

Should OSAC apply the first revision it observes for a Git reference? After an
apply failure, should it retry even when the Git reference has not advanced?

#### Answer

Yes. OSAC applies the first observed revision and retries failed resource
operations on later syncs even if the reference has not advanced. Each retry
reconciles the latest observed revision.

#### Impact

Transient apply failures do not require a new Git commit to trigger another
attempt. Sync status must show whether the latest revision is fully or partially
applied.

#### Decision (D8)

Apply the first observed revision and retry failed operations on later syncs,
reconciling the latest observed revision each time.

---

### R1.Q9: Multiple Git references and overlapping resources

Does the feature support multiple concurrent Git references, including
references to different repositories? Can the same platform resource appear in
more than one reference, or should overlapping declarations be rejected? If
overlap is supported, deletion waits until no active reference declares the
resource.

#### Answer

Intentionally left open at the user's direction; reference cardinality and
whether overlapping declarations are supported or rejected have not been
decided.

#### Impact

This determines reference cardinality and overlap policy. If overlapping
declarations are supported, deletion must wait until no active reference
declares the resource.

#### Owner

Feature owner (to be assigned).

---

## Remaining Gaps

- **Open question — UI support:** Decide whether admins need UI workflows to
  register/configure Git references and view the latest observed commit SHA, errors,
  and associated resources, or whether the specified API and CLI interfaces
  are sufficient. **Owner:** Feature owner (to be assigned). **Impact:**
  Determines whether OSAC UI work for source configuration and sync status is
  part of the feature.
- **Open question — multiple Git references:** Decide whether multiple Git
  references, including distinct repositories, are supported and whether
  overlapping resource declarations are supported or rejected. If overlaps are
  supported, deletion waits until no active reference declares the resource.
  **Owner:** Feature owner (to be assigned). **Impact:** Determines reference
  cardinality and overlap policy.

## Design Follow-up

- Confirm which repository credential types work with existing secret
  references. Jira excludes new secret management integration.
- Define the polling interval default, supported range, and invalid-value
  behavior in API design. **Owner:** Feature owner (to be assigned).
- If R1.Q9 allows overlapping declarations, define how sync checks all active
  references before deletion and how conflicts are reported, without requiring
  Git ownership annotations on resource objects. **Owner:** Feature owner (to
  be assigned).
- Define how API and CLI authorization distinguishes Git sync writes from
  manual requests and enforces D6 across every write path. **Owner:** Feature
  owner (to be assigned).
- Define how manual writes and Git synchronization avoid conflicting claims or
  updates to the same resource. **Owner:** Feature owner (to be assigned).
