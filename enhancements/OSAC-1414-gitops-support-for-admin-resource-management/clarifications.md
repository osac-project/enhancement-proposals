# Clarification Log — OSAC-1414

## Status

- Rounds completed: 1
- Open gaps: 4
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

### R1.Q4: Deletion safety with partial apply

Jira says multi-file applies are best-effort and non-atomic, with error
reporting, and that resources removed from Git are deleted. Should resources
confirmed absent from a complete inventory be deleted when another resource
apply fails? Cross-reference ownership is addressed in R1.Q9.

#### Answer

The inventory for the Git reference must be complete and unambiguous before
resources absent from it are considered for deletion. Apply errors do not block
unrelated deletions; design will define ordering and retries for dependent
operations, including deletions needed before replacements. Cross-reference
deletion behavior remains open under R1.Q9.

#### Impact

The system needs a complete, readable inventory for the relevant Git reference
before treating a resource as removed from it. An apply failure does not block
unrelated deletions; design defines safe ordering and retries for dependent
operations, including deletions needed before replacements. Whether other Git
references can also declare the resource remains open under R1.Q9.

#### Decision (D4)

Delete a resource only when a complete, unambiguous inventory for its Git
reference shows it is absent. An apply error does not block unrelated
deletions. Design defines ordering and retries for dependent operations,
including deletions needed before replacements; incomplete or ambiguous
inventories never trigger deletion. Cross-reference ownership is open under
R1.Q9.

---

### R1.Q5: Git reference and resource ownership lifecycle

The ticket says resources removed from Git are deleted and direct API updates
or deletes of Git-managed resources are rejected, but it does not say whether
disabling a Git reference is supported or what happens when one is deleted or
disabled. Should its managed resources be deleted, retained and made editable,
or retained and still protected? Should admins have a supported way to detach a
resource for manual management?

#### Answer

Intentionally left open at the user's direction; no behavior was selected.

#### Impact

Resource retention and the transition to manual management remain undefined
when an admin deletes or disables a Git reference.

#### Owner

Feature owner (to be assigned).

---

### R1.Q6: Direct writes to platform-scoped resources

Should human admins be able to create or update platform-scoped resources that
are not managed by Git, or should only the Git sync runtime be allowed to write
any in-scope platform resource? Can OSAC enforce this using the caller identity
alone, or must it track which resources belong to Git references?

#### Answer

Intentionally left open at the user's direction; the write policy and the
need for per-resource Git ownership tracking have not been decided.

#### Impact

This determines whether write authorization is uniform across all in-scope
resource types or selective by Git ownership. Selective authorization requires
OSAC to track which resources belong to each Git reference.

#### Owner

Feature owner (to be assigned).

---

### R1.Q7: UI support

Should Cloud Provider Admins have a UI to register and configure Git references
(repository, branch or tag, directory, existing credential reference, and
polling interval) and view the last applied commit, sync errors, and resources
associated with each reference, or are API GitReference CRUD/status and the
CLI `osac apply -f` sufficient?

#### Answer

Intentionally left open at the user's direction; UI support has not been
decided.

#### Impact

This determines whether OSAC UI workflows for source configuration and sync
status are part of the feature scope. UI behavior for deleting or disabling a
reference depends on R1.Q5.

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
more than one reference? If so, should it be deleted only when absent from all
references, or should overlapping declarations be rejected?

#### Answer

Intentionally left open at the user's direction; reference cardinality and
overlap behavior have not been decided.

#### Impact

This determines whether reconciliation must combine inventories across
references or prevent duplicate declarations, and how to avoid deleting a
resource still desired by another reference.

#### Owner

Feature owner (to be assigned).

---

## Remaining Gaps

- **Open question — Git reference deletion:** Decide whether managed resources
  are deleted, retained and editable, or retained and protected when the Git
  reference is deleted or disabled, and whether admins can detach resources.
  **Owner:** Feature owner (to be assigned). **Impact:** Resource retention and
  the handoff to manual management remain undefined.
- **Open question — platform resource write policy:** Decide whether admins may
  directly write resources not managed by Git, or whether only the Git sync
  runtime may write any in-scope platform resource. **Owner:** Feature owner
  (to be assigned). **Impact:** Determines whether authorization is uniform or
  requires tracking Git ownership per resource.
- **Open question — UI support:** Decide whether admins need UI workflows to
  register/configure Git references and view the last applied commit, errors,
  and associated resources, or whether the specified API and CLI interfaces
  are sufficient. UI deletion/disable behavior depends on R1.Q5. **Owner:**
  Feature owner (to be assigned). **Impact:** Determines whether OSAC UI work
  for source configuration and sync status is part of the feature.
- **Open question — multiple Git references:** Decide whether multiple Git
  references, including distinct repositories, are supported and whether
  resources may overlap across them. **Owner:** Feature owner (to be assigned).
  **Impact:** Determines whether inventories must be aggregated for deletion or
  duplicate declarations rejected.

## Design Follow-up

- Confirm which repository credential types work with existing secret
  references. Jira excludes new secret management integration.
- Define the polling interval default, supported range, and invalid-value
  behavior in API design. **Owner:** Feature owner (to be assigned).
- Define how the sync runtime aggregates resource declarations across Git
  references for safe deletion, without requiring Git ownership annotations on
  resource objects. **Owner:** Feature owner (to be assigned).
- If R1.Q6 permits direct writes to resources not managed by Git, define how
  API authorization and Git sync avoid racing to claim or update the same
  resource. **Owner:** Feature owner (to be assigned).
