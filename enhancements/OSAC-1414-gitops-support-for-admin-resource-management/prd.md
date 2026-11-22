# GitOps support for admin resource management

| Field | Value |
|-------|-------|
| Author(s) | Haim Tayrie |
| Jira | [OSAC-1414](https://redhat.atlassian.net/browse/OSAC-1414) |
| Date | 2026-10-28 |

## Problem Statement

Cloud Provider Admins manage platform resources through the OSAC API and CLI.
They can write their own scripts, but have no documented way to apply reviewed
Git changes automatically, see what applied, or keep resources aligned with Git.

## In Scope

- Admins create, view, update, and remove syncs in the external tool.
  A sync specifies a repository URL, branch or tag, directory, credential
  reference, and configurable polling interval. The external tool applies
  YAML definitions through the API on the first sync and when Git changes. It
  retries failed operations against the latest revision even without a new
  commit. [Clarify: R1.Q3, R1.Q7, R1.Q8, R2.Q1]
- The API supports apply by resource type and name. It creates missing
  resources and updates existing ones where the API permits updates.
  `osac apply -f` uses the same behavior for manual apply. [Clarify: R1.Q6]
- Git sync covers all current and future platform-scoped resource types,
  including those used by CaaS, VMaaS, BMaaS, and networking. Examples include
  `ClusterTemplate`, `ComputeInstanceTemplate`, `ClusterCatalogItem`,
  `ComputeInstanceCatalogItem`, `DiskImage`,
  `BareMetalInstanceTemplate`, `BareMetalInstanceCatalogItem`,
  `BareMetalInstanceType`, `NetworkClass`, `ExternalIPPool`, and `Hub`.
  [Clarify: R2.Q1, R2.Q2]
- Each sync uses its own OSAC API identity with independently limited
  permissions. OSAC authorizes every sync API call as that identity, and the
  tool reports denied operations as sync errors. Admins can restrict writes
  to managed resources to the assigned identity using standard OSAC access
  controls. OSAC rejects unauthorized updates and deletes through every API
  and CLI path, including `osac apply -f`. The inventory identifies the
  managing sync, and OSAC metadata records the API identity that created the
  resource.
  [Clarify: R1.Q6, R1.Q10, R2.Q1]
- The external tool's UI shows the latest observed commit SHA, the last fully
  applied commit, errors, and the managed resource inventory. It shows whether
  the latest sync fully applied, partly applied, or failed. Independent changes
  can still apply after a failure. [Clarify: R1.Q7, R1.Q8, R2.Q1]
- Multiple sources can sync at the same time, including different repositories.
  Each resource has one managing sync. The tool rejects overlapping declarations
  as sync errors and leaves resources managed by another sync untouched.
  [Clarify: R1.Q9]
- The tool deletes a managed resource only when a complete, unambiguous
  inventory of its Git source confirms it is absent. Unrelated deletions may
  proceed when an apply fails. Dependent operations follow resource ordering
  and retry rules, including deletions needed before replacements. The tool
  reports failed deletions and keeps those resources in its inventory for
  retry. Removing a sync keeps its resources and releases them from that
  sync's management. Admins with write access can then edit or delete them
  through the API or CLI. [Clarify: R1.Q4, R1.Q5, R1.Q8, R2.Q2]
- Document setup, permissions, status, and manual recovery. Verify create,
  update, delete, and conflict handling through the external sync workflow
  and the OSAC API in integration tests.

## Out of Scope

- OSAC-managed GitReference resources, Git polling, and sync setup or status
  in the OSAC UI.
- Git-specific write restrictions in the OSAC API.
- Tenant resource GitOps.
- Managing OSAC resources by writing Kubernetes CRs.
- Webhook triggers and all-or-nothing apply across files.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to set up a scheduled sync in the external
  tool's UI so platform resources follow reviewed Git changes.
- As a Cloud Provider Admin, I want to see the revision, errors, and resources
  in the tool's UI so I can check or fix the sync.
- As a Cloud Provider Admin, I want each sync to have its own API permissions
  so I can limit what it changes and protect managed resources from other writers.
- As a Cloud Provider Admin, I want conflicting sources reported so one sync
  cannot take over resources managed by another.
- As a Cloud Provider Admin, I want resources deleted only after a complete,
  unambiguous inventory of their managing Git source confirms they are absent,
  so a failed read of Git cannot cause accidental deletion.
- As a Cloud Provider Admin, I want to remove a sync and keep its resources
  so I can recover or manage them directly when needed.
- As a Cloud Provider Admin, I want to use `osac apply -f` for manual changes
  I am authorized to make so I can reuse the same resource definitions.

## Dependencies

- The tool runs where it can reach the Git source, including private
  repositories. Its only connection to OSAC is through the gRPC endpoints
  allowed for its sync identity. The tool uses existing credential references
  for Git and OSAC access. Hub kubeconfigs use existing OSAC secret references.

---

## Provenance

Authored: draft @ prd 0.11.5 - 7b2b8de, workspace main @ f0a8211
Final: revise @ prd 0.11.5 - 922de34, workspace main @ f0a8211

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"922de34","source_repo":"f0a8211","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","respond","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
