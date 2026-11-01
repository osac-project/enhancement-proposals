# Clarification Log — OSAC-1414

## Status

- Rounds completed: 1
- Open gaps: 3
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
reporting, and that resources removed from Git are deleted. The desired state
must be clear before deletion. If all files can be read and parsed but applying
one present resource fails, should resources confirmed absent from that
complete inventory still be deleted?

#### Answer

The full, readable Git inventory is the desired state. Resources absent from
that inventory are deleted during reconciliation, even if applying another
resource fails. Resources must not be deleted based on an incomplete or
ambiguous inventory. Design will define ordering and retries for dependent
operations, such as replacing one resource with another.

#### Impact

The system needs a complete, readable inventory before treating a resource as
removed. An apply failure on one resource does not globally block unrelated
deletions. Design must define safe ordering and retry behavior when operations
depend on each other.

#### Decision (D4)

Delete resources absent from a complete, unambiguous inventory during
reconciliation. An apply error on one resource does not globally block
unrelated deletions. Design defines ordering and retries for dependent
operations; never delete based on an incomplete or ambiguous inventory.

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

Does the feature need UI workflows for managing Git references and viewing sync
status, or are API-based GitReference CRUD/status and the CLI `osac apply -f`
sufficient?

#### Answer

Intentionally left open at the user's direction; UI support has not been
decided.

#### Impact

This determines whether OSAC UI workflows are part of the feature scope.

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
  manage Git references and view sync status, or whether the specified API and
  CLI interfaces are sufficient. **Owner:** Feature owner (to be assigned).
  **Impact:** Determines whether OSAC UI changes are part of the feature.

## Design Follow-up

- Confirm which repository credential types work with existing secret
  references. Jira excludes new secret management integration.
