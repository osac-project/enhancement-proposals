# Clarification Log — OSAC-6204

## Status

- Rounds completed: 5
- Open gaps: 0
- Exit criteria met: Yes
- Current administrator wording: [D8](#decision-d8) consolidates the administrator persona under existing access permissions.

## Round 1 — Scope and user-visible behavior

### R1.Q1: Services and resource scope

Which OSAC services and resource types should support administrator-only labels and annotations? Should this cover every resource that exposes labels/annotations, or a named subset? Please name the subset if applicable.

#### Answer

All OSAC resources that expose labels or annotations.

#### Impact

The feature covers every OSAC resource that exposes labels or annotations. Admin access within that coverage follows each persona's resource scope in Jira.

#### Decision (D1)

Administrator-only labels and annotations apply to all OSAC resources that expose labels or annotations. Cloud Provider Admin access spans supported resources; Cloud Infrastructure Admin access is scoped to infrastructure resources.

---

### R1.Q2: Admin permissions

Should both Cloud Provider Admin and Cloud Infrastructure Admin be able to view, add, change, and remove reserved-prefix labels and annotations? If permissions differ by role or operation, what is the intended boundary?

#### Answer

Treat both admin personas the same unless Jira specifies a difference. Jira scopes Cloud Provider Admin access across supported resources and Cloud Infrastructure Admin access to infrastructure resources. Both personas can view, add, change, and remove reserved-prefix labels and annotations within their respective resource scopes.

#### Impact

Both admin personas have the same actions, but their resource scopes differ: Cloud Provider Admin access spans supported resources, while Cloud Infrastructure Admin access covers infrastructure resources.

#### Decision (D2)

Cloud Provider Admin and Cloud Infrastructure Admin can both view, add, change, and remove reserved-prefix labels and annotations; Cloud Provider Admin access spans supported resources, while Cloud Infrastructure Admin access is limited to infrastructure resources.

---

### R1.Q3: Interfaces

Jira names a privileged API and console. Should both admin personas be able to perform the same view/add/change/remove actions through both interfaces, and should CLI support also be included?

#### Answer

Both admin personas should have the same actions through the privileged API, console, and CLI. These interfaces apply within each persona's resource scope in Jira. The user confirmed that CLI and the other interfaces are equivalent.

#### Impact

Both admin personas can use the privileged API, console, and CLI for the same metadata actions within their respective resource scopes.

#### Decision (D3)

Cloud Provider Admin and Cloud Infrastructure Admin have the same view/add/change/remove actions through the privileged API, console, and CLI, within their respective resource scopes.

---

### R1.Q4: Tenant update containing protected and ordinary metadata

If a tenant update includes both a reserved-prefix key and ordinary metadata, should the whole update fail with a clear error, or should the reserved key be ignored while the ordinary changes are applied?

#### Answer

Reject the entire request and return an error; do not apply the ordinary metadata changes. The user explicitly does not want the request to fail silently.

#### Impact

Tenants receive an error when an update attempts to change reserved-prefix metadata, and no part of that request—including ordinary metadata changes—is applied.

#### Decision (D4)

Reject a tenant request that attempts to change reserved-prefix metadata as a whole, return a clear error, and leave all stored metadata unchanged.

---

## Round 2 — Equal admin resource access

### R2.Q1: Do the admin roles have the same resource scope?

The existing Jira-derived clarification limits Cloud Infrastructure Admin to infrastructure resources. Does “same permissions” mean the two roles also have identical resource coverage for this feature?

#### Answer

Yes. The user clarified that there is no difference between the admin roles for this feature. Both can view, add, change, and remove reserved-prefix labels and annotations on every OSAC resource that exposes them.

#### Impact

Both roles use the same resource allowlist through the privileged API, console, and CLI. The earlier role-specific resource-scope interpretation no longer applies to this feature.

#### Decision (D5)

Cloud Provider Admin and Cloud Infrastructure Admin have identical reserved-metadata permissions and resource coverage across all OSAC resources that expose labels or annotations. D5 supersedes the role-specific scope clauses in D1, D2, and D3.

## Round 3 — Whole-map tenant update semantics

### R3.Q1: What happens to reserved keys omitted from a tenant update?

Should whole-map tenant updates retain existing reserved entries, including keys omitted from the supplied labels or annotations?

#### Answer

Existing reserved keys should be retained in any tenant update request.

#### Impact

Tenant whole-map omission always preserves stored reserved entries. The server rejects supplied reserved entries and accepted explicit reserved-key targets as a whole. Updated CLI and console controls reject named reserved set/removal operations before constructing or sending an Update, including mixed ordinary operations. A server cannot infer a removed target once a client has discarded it from the map; older clients may report an ordinary update as successful while the server retains reserved entries.

Authorized private administrators continue replacing selected maps, with omitted keys removed. Existing masks and version locking are reused.

#### Decision (D6)

Every tenant update retains the reserved portion of the locked stored object. Omission from a whole-map request is not reserved-key removal intent. D6 clarifies D4 for whole-map requests; explicit forbidden input and named client operations still fail without applying an ordinary subset.

## Round 4 — Backend-only enforcement

### R4.Q1: Should clients reject named reserved-key operations locally?

The CLI discards a removal target when editing its fetched map. Should clients add validation to report this attempt, or rely on backend preservation and rejection of explicit request input?

#### Answer

Rely on the backend only. No client-side reserved-key validation is required.

#### Impact

The public API rejects supplied reserved entries and accepted explicit reserved-key targets as a whole. Omitted reserved entries are always retained from stored state. A client removal that becomes map omission may return success, and ordinary edits in that request may be applied. The reserved entry remains unchanged. Existing CLI request construction and error reporting continue to work; console clients consume backend projections and errors.

#### Decision (D7)

Enforce reserved labels and annotations in the backend. D7 supersedes D6's named-client rejection requirement and limits D4's clear-error guarantee to forbidden input observable in the request. Omission carries no removal intent and requires no error. Private API behavior and existing authorization remain unchanged.

## Round 5 — Administrator wording

### R5.Q1: Consolidate administrator references

User feedback: the documents still mention two administrator personas together.

#### Decision (D8)

Use one Administrator persona in the current PRD and test plan. Describe private API behavior through existing method and object permissions. This consolidates D5's equivalent administrator capabilities without adding a role distinction, account-provisioning requirement, or authorization change. All resources, metadata actions, and API/CLI/console coverage remain in scope. The test plan uses an existing authorized administrator account and retains tenant and restricted-client controls.

## Remaining Gaps

None. The exact reserved prefix and matching rules remain for the design, as specified by the source issue.
