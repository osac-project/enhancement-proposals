# Testplan — OSAC-1269

## Overview

- **Feature:** OSAC-1269 — ClusterVersion — Managed Version Catalog for Cluster Provisioning
- **Scope:** `osac-ui` only (see `04-epics.md` scope note)
- **Total test cases:** 33
- **Requirements covered:** 14 of 17 (15 FR + 2 NFR)

## Test Cases

### FR-1: Admins can create, update, and delete version catalog entries

#### TC-FR1-01: Admin creates a version entry with version, image, and enabled fields

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 3.03 | AC-1, AC-2 | critical | automated |

##### Preconditions

- Logged in as a Cloud Provider Admin on the "Cluster versions" admin page.

##### Steps

1. Click "Create".
2. Enter version `4.19.0`, image `quay.io/openshift-release-dev/ocp-release:4.19.0-multi`, leave "enabled" checked.
3. Submit the form.

##### Expected Results

- The `ClusterVersions.Create` request payload contains `spec.version: "4.19.0"`, `spec.image: "quay.io/openshift-release-dev/ocp-release:4.19.0-multi"`, `spec.enabled: true`.
- The new row appears in the list with STATE = "Active".

#### TC-FR1-02: List page reflects a newly created or deleted version without manual refresh

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 3.03 | AC-5 | medium | automated |

##### Preconditions

- Admin list page is open with N existing versions.

##### Steps

1. Create a new version via the create form.
2. Observe the list without navigating away or reloading.
3. Delete a version via the delete confirm modal.
4. Observe the list again.

##### Expected Results

- After step 1, the list shows N+1 rows including the new entry, with no page reload.
- After step 3, the list shows N rows with the deleted entry absent, with no page reload.

### FR-2: Users can browse and view available versions

#### TC-FR2-01: Cluster detail page resolves a version regardless of lifecycle state

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 2.02 | AC-3 | medium | automated |

##### Preconditions

- A cluster exists with `spec.versionName` pointing to a `ClusterVersion` whose `state` is `OBSOLETE`.

##### Steps

1. Open that cluster's detail page.

##### Expected Results

- The configuration card shows the version's `spec.version` string and an "Obsolete" `ClusterVersionStateLabel` — the page does not omit or error on an obsolete version.

#### TC-FR2-02: Admin list page includes obsolete and disabled versions by default

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 3.02 | AC-3 | medium | automated |

##### Preconditions

- The version catalog contains at least one `ACTIVE`, one `DEPRECATED`, one `OBSOLETE`, and one `enabled: false` entry.

##### Steps

1. Open the "Cluster versions" admin list page with no filter applied.

##### Expected Results

- All four entries appear in the table, including the obsolete and disabled ones, with no explicit filter needed.

### FR-3: At most one version can be marked as default

#### TC-FR3-01: Admin sets a version as default via confirmation

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 3.04 | AC-3 | high | automated |

##### Preconditions

- Version `4-17-0` is currently marked DEFAULT; version `4-18-0` is `ACTIVE` and `enabled: true`.

##### Steps

1. Open the actions menu for `4-18-0` and select "Set as default".
2. Confirm the warning dialog.

##### Expected Results

- The `ClusterVersions.Update` request for `4-18-0` includes `spec.isDefault: true`.
- The list, after the mutation resolves, shows `4-18-0`'s DEFAULT column as "Yes" and `4-17-0`'s as "No".

#### TC-FR3-02: "Set as default" is disabled for obsolete or disabled versions

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 3.04 | AC-4 | high | automated |

##### Preconditions

- Version `4-16-0` has `state: OBSOLETE`; version `4-15-0` has `enabled: false`.

##### Steps

1. Open the actions menu for `4-16-0`.
2. Open the actions menu for `4-15-0`.

##### Expected Results

- "Set as default" is rendered disabled for both entries, each with a tooltip explaining the reason (obsolete state / disabled).

#### TC-FR3-03: Concurrent default-set race surfaces AlreadyExists without a false success

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 3.04 | AC-5 | medium | automated |

##### Preconditions

- Mock transport configured to return a gRPC `AlreadyExists` error for a `ClusterVersions.Update` call setting `isDefault: true`.

##### Steps

1. Trigger "Set as default" on a version and confirm.

##### Expected Results

- A submission error referencing the conflicting default is displayed to the admin.
- The version's DEFAULT column does not change to "Yes" in the UI.

### FR-4: Users specify a version number when creating a cluster

#### TC-FR4-01: Wizard configuration step shows a version dropdown populated with active versions

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.03 | AC-1 | critical | automated |

##### Preconditions

- Mock transport serves `ClusterVersions.List` with three `ACTIVE` versions and one `OBSOLETE` version.

##### Steps

1. Open the cluster-creation wizard and reach the configuration step.
2. Open the version dropdown.

##### Expected Results

- The dropdown lists the three active versions by their `spec.version` string.
- The obsolete version does not appear in the dropdown options.

#### TC-FR4-02: Submitting the wizard sends spec.versionName, not spec.releaseImage

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.03 | AC-3 | critical | automated |

##### Preconditions

- Wizard configuration step has a version selected (`4-18-0`).

##### Steps

1. Complete the remaining wizard steps and submit.

##### Expected Results

- The `Clusters.Create` request payload contains `spec.versionName: "4-18-0"`.
- The request payload contains no `releaseImage` field.

#### TC-FR4-03: Wizard review step shows the selected version under a "Version" label

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.03 | AC-6 | low | automated |

##### Preconditions

- Version `4-18-0` selected in the configuration step.

##### Steps

1. Navigate to the wizard's review step.

##### Expected Results

- The review step shows a "Version" row with value `4-18-0` (or its resolved `spec.version` string) — no "Release image" label appears anywhere in the review step.

### FR-6: A cluster's version and current lifecycle state are visible when viewing or listing clusters

#### TC-FR6-01: Cluster list table shows Version and Lifecycle columns for every cluster

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 2.01 | AC-1 | critical | automated |

##### Preconditions

- Three clusters exist, each referencing a different `ClusterVersion`.

##### Steps

1. Open the cluster list page.

##### Expected Results

- Each row shows a Version column with the resolved version string and a Lifecycle column with a colored state label matching that version's state.

#### TC-FR6-02: Cluster list table resolves versions via a single batched fetch

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 2.01 | AC-2 | medium | automated |

##### Preconditions

- Ten clusters exist, referencing five distinct versions.

##### Steps

1. Open the cluster list page and let it fully render.

##### Expected Results

- The mock `ClusterVersions.List` handler is called exactly once, regardless of the ten rows rendered.

#### TC-FR6-03: Cluster list falls back to raw version_name when a version can't be resolved

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 2.01 | AC-4 | medium | automated |

##### Preconditions

- A cluster's `spec.versionName` is `"deleted-version"`, which is absent from the `ClusterVersions.List` response.

##### Steps

1. Open the cluster list page.

##### Expected Results

- That row's Version column shows the literal string `"deleted-version"`.
- That row's Lifecycle column is blank — no error is thrown and no other row is affected.

#### TC-FR6-04: Cluster detail page shows resolved version and lifecycle label with a loading skeleton

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 2.02 | AC-1, AC-2 | high | automated |

##### Preconditions

- A cluster references version `4-17-0`, `state: DEPRECATED`. The mock `ClusterVersions.Get` response is delayed.

##### Steps

1. Open the cluster's detail page.
2. Observe the configuration card immediately, then again after the request resolves.

##### Expected Results

- Immediately after opening, a `Skeleton` placeholder renders in place of the version value.
- After the request resolves, the card shows `4.17.0` and a "Deprecated" state label.

#### TC-FR6-05: Cluster detail page falls back to raw version_name with no label when unresolved

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 2.02 | AC-4 | medium | automated |

##### Preconditions

- A cluster's `spec.versionName` is `"deleted-version"`; `ClusterVersions.Get` returns not-found.

##### Steps

1. Open the cluster's detail page.

##### Expected Results

- The configuration card shows the literal string `"deleted-version"` with no state label rendered.

#### TC-FR6-06: Cluster list version fetch includes obsolete and disabled entries

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 2.01 | AC-3 | medium | automated |

##### Preconditions

- A cluster references a version whose `state` is `OBSOLETE`.

##### Steps

1. Open the cluster list page.

##### Expected Results

- That row's Lifecycle column correctly shows "Obsolete" — the underlying `ClusterVersions.List` call used by the table does not filter out obsolete/disabled entries.

#### TC-FR6-07: ClusterVersionStateLabel renders the correct color for each lifecycle state

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 2.01 | AC-5 | medium | automated |

##### Preconditions

- None (isolated component test).

##### Steps

1. Render `ClusterVersionStateLabel` with `state: ACTIVE`, then `DEPRECATED`, then `OBSOLETE`.

##### Expected Results

- `ACTIVE` renders with the green label style, `DEPRECATED` with gold/amber, `OBSOLETE` with grey — each with the corresponding text ("Active"/"Deprecated"/"Obsolete").

#### TC-FR6-08: Cluster detail page compiles and renders the raw version_name after the releaseImage field is removed

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.03 | AC-7 | medium | automated |

##### Preconditions

- `libs/types` has been regenerated (Story 1.01) so `ClusterSpec` no longer has a `releaseImage` field; a cluster fixture has `spec.versionName: "4-18-0"`.

##### Steps

1. Open that cluster's detail page, before Story 2.02's live lookup exists (i.e., testing Story 1.03's state in isolation).

##### Expected Results

- The configuration card renders the literal string `"4-18-0"` under a "Version" label.
- No reference to `releaseImage`/`spec.releaseImage` remains in the component or its test file; the test suite and `tsc -b` both pass.

### FR-7: Version is validated at creation time with descriptive error messages

#### TC-FR7-01: Selecting a deprecated version shows an inline warning without blocking submission

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.03 | AC-2 | high | automated |

##### Preconditions

- `4-17-0` is `DEPRECATED` and appears in the wizard's version dropdown.

##### Steps

1. Select `4-17-0` in the configuration step.
2. Complete and submit the wizard.

##### Expected Results

- An inline warning alert reading a deprecation notice for `4.17.0` appears below the dropdown immediately after selection.
- The wizard submission still succeeds (the `Clusters.Create` request is sent and no client-side validation blocks it).

#### TC-FR7-02: Server rejection of an invalid, obsolete, or unresolvable version surfaces as a submission error

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.03 | AC-5 | critical | automated |

##### Preconditions

- Mock transport configured so `Clusters.Create` returns `InvalidArgument` with a "version not found" message.

##### Steps

1. Submit the wizard with a version selected.

##### Expected Results

- The wizard's existing submission-error UI displays the "version not found" message returned by the server — no separate, wizard-specific error component is rendered.

### FR-9: The UI console supports catalog management for admins and version selection in the wizard

#### TC-FR9-01: "Cluster versions" nav entry opens the admin list page with the expected columns

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 3.02 | AC-1, AC-2 | high | automated |

##### Preconditions

- Logged in as a Cloud Provider Admin.

##### Steps

1. Click the "Cluster versions" entry under the Administration nav section.

##### Expected Results

- The admin list page renders with columns NAME, VERSION, STATE, ENABLED, DEFAULT, IMAGE, in that order.

#### TC-FR9-02: Wizard version selection is present (cross-reference to FR-4)

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.03 | AC-1 | critical | automated |

##### Preconditions

- Same as TC-FR4-01.

##### Steps

1. Same as TC-FR4-01.

##### Expected Results

- Same as TC-FR4-01 — recorded under FR-9 as well because FR-9 explicitly names "version selection in the cluster creation wizard" as one of its two deliverables.

### FR-10: Catalog items reference version instead of release image in field definitions

#### TC-FR10-01: A catalog item locking version_name drives the wizard field's editability and default

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.03 | AC-4 | high | automated |

##### Preconditions

- Selected catalog item has `field_definitions: [{ path: "version_name", editable: false, default: "4-17-0" }]`.

##### Steps

1. Select that catalog item and reach the configuration step.

##### Expected Results

- The version field is pre-filled with `4-17-0` and rendered disabled (not editable) — matching how a locked `release_image` field behaved before.

### FR-11: Deleting a version in use is rejected, identifying the referencing resource

#### TC-FR11-01: Deleting a referenced version shows the server's exact in-use error

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 3.03 | AC-4 | critical | automated |

##### Preconditions

- Mock transport configured so `ClusterVersions.Delete` for `4-17-0` returns `FailedPrecondition`: `cannot delete version '4.17.0': in use by cluster 'cluster-abc'`.

##### Steps

1. Open the delete confirmation modal for `4-17-0` and confirm.

##### Expected Results

- The error text `cannot delete version '4.17.0': in use by cluster 'cluster-abc'` is displayed verbatim to the admin.
- The row for `4-17-0` remains in the list (deletion did not proceed).

### FR-12: Creating or updating with a nonexistent or deleted version is rejected

#### TC-FR12-01: Creating a cluster with a nonexistent version is rejected with a descriptive error

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.03 | AC-5 | high | automated |

##### Preconditions

- Mock transport configured so `Clusters.Create` returns `InvalidArgument`: "version 'nonexistent-4' not found".

##### Steps

1. Submit the wizard referencing a version that no longer exists.

##### Expected Results

- The message "version 'nonexistent-4' not found" is displayed via the wizard's existing submission-error UI.

### FR-13: Lifecycle state transitions are always allowed regardless of references

#### TC-FR13-01: Actions menu offers only transitions valid from the current state

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 3.04 | AC-1 | high | automated |

##### Preconditions

- Three versions exist: one `ACTIVE`, one `DEPRECATED`, one `OBSOLETE`.

##### Steps

1. Open the actions menu for each of the three versions in turn.

##### Expected Results

- The `ACTIVE` entry's menu offers "Mark deprecated" and "Mark obsolete", not "Reactivate".
- The `DEPRECATED` entry's menu offers "Mark obsolete" and "Reactivate", not "Mark deprecated".
- The `OBSOLETE` entry's menu offers "Reactivate" and "Mark deprecated", not "Mark obsolete".

#### TC-FR13-02: A lifecycle transition updates only spec.state

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 3.04 | AC-2 | high | automated |

##### Preconditions

- Version `4-17-0` is `ACTIVE`.

##### Steps

1. Select "Mark deprecated" from its actions menu.

##### Expected Results

- The `ClusterVersions.Update` request payload contains only `spec.state: CLUSTER_VERSION_STATE_DEPRECATED` — no `version`, `image`, `enabled`, or `isDefault` fields are present in the payload.

#### TC-FR13-03: List page reflects a lifecycle or default change without manual refresh

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 3.04 | AC-6 | medium | automated |

##### Preconditions

- Admin list page is open.

##### Steps

1. Mark a version as deprecated via its actions menu.
2. Observe the list without reloading.

##### Expected Results

- That row's STATE column updates to "Deprecated" with no page reload.

### FR-14: A version entry cannot be redefined after creation

#### TC-FR14-01: Admin UI never offers editing version or image after creation

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 3.03 | AC-3 | critical | automated |

##### Preconditions

- Version `4-17-0` exists.

##### Steps

1. Inspect every admin affordance available for `4-17-0` (row actions, any edit surface).

##### Expected Results

- No control anywhere in the admin UI allows changing `4-17-0`'s version string or image URL — only lifecycle, enabled, and default-related actions are exposed.

### FR-15: A version can be marked deprecated; obsolete versions are blocked for new cluster creation

#### TC-FR15-01: Obsolete versions never appear as selectable options in the wizard

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 1.03 | AC-1 | high | automated |

##### Preconditions

- Same mock data as TC-FR4-01 (includes one `OBSOLETE` version).

##### Steps

1. Open the wizard's version dropdown.

##### Expected Results

- The obsolete version's `spec.version` string does not appear anywhere in the dropdown's option list.

#### TC-FR15-02: Deprecated/obsolete lifecycle label shows a timestamp tooltip

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 2.01 | AC-6 | medium | automated |

##### Preconditions

- Version `4-17-0` has `state: DEPRECATED`, `deprecation.deprecationTimestamp: "2026-03-15T00:00:00Z"`.
- Version `4-16-0` has `state: OBSOLETE`, `deprecation.obsolescenceTimestamp: "2026-06-01T00:00:00Z"`, no `deprecationTimestamp`.
- Version `4-18-0` has `state: ACTIVE`.

##### Steps

1. Render (or hover/focus, if rendered via a list) the `ClusterVersionStateLabel` for each of the three versions.

##### Expected Results

- `4-17-0`'s label shows a tooltip reading "Deprecated since 3/15/2026".
- `4-16-0`'s label shows a tooltip reading "Obsolete since 6/1/2026".
- `4-18-0`'s label shows no tooltip.

### NFR-1: Admins manage the version catalog using familiar, consistent patterns

#### TC-NFR1-01: Admin list page search filters by name and shows an empty state

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 3.02 | AC-4 | low | automated |

##### Preconditions

- Three versions exist: `4-17-0`, `4-18-0`, `4-19-0`.

##### Steps

1. Type `4-18` into the search input.
2. Clear the search input, then search for a string matching no versions.

##### Expected Results

- After step 1, only `4-18-0` is shown in the table.
- After step 2's non-matching search, the table shows the empty-state message instead of any rows.

#### TC-NFR1-02: Cluster versions page is a standalone admin page, not nested in Catalog management's tabs

| Story | AC | Priority | Automation |
|-------|-----|----------|------------|
| Story 3.02 | AC-5 | low | automated |

##### Preconditions

- None.

##### Steps

1. Navigate to `/admin/catalog` (Catalog management).
2. Navigate to the Cluster versions route directly.

##### Expected Results

- `/admin/catalog`'s tab set (Clusters/VMs/Bare Metal catalog items) does not include a "Cluster versions" tab.
- The Cluster versions page renders at its own distinct route, reachable only via its own nav entry.

## Gaps

- **FR-5** (templates can specify a default version) and **FR-8** (CLI support) have no `osac-ui` surface — `osac-ui` doesn't have a cluster-template admin UI at all (templates are CLI/private-API-managed), and the CLI lives in a separate repo. Not testable from this repo; already shipped and covered by the fulfillment-service/CLI's own test suites.
- **NFR-2** (future catalog additions must not break existing workflows) is addressed by an architectural property of the design (§4.8 Extensibility — the public/private hook split and hardcoded-widget pattern generalize to future fields) rather than a specific implementation story with observable behavior today. No test case is generated; this should be revisited if/when a future feature actually extends the version catalog.
- **FR-15's timestamp-visibility aspect** ("deprecation and obsolescence timestamps are recorded automatically") is now covered: `03-design.md`'s Open Question 5 was resolved in favor of display, via a tooltip on `ClusterVersionStateLabel` (Story 2.01, AC-6; `TC-FR15-02`).
- **FR-2's "browse" framing** is covered for the admin (full list, all states) and detail (single lookup, any state) surfaces, but the wizard's active-only filtered view (Story 1.03) is covered under FR-4/FR-15 rather than re-listed under FR-2, to avoid duplicate test cases for the same UI behavior under multiple headings.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 33 |
| Critical | 8 |
| High | 10 |
| Medium | 12 |
| Low | 3 |
| Automated | 33 |
| Manual | 0 |
| Requirements with test cases | 14 / 17 |
| Requirements without test cases | 3 (see Gaps) |
