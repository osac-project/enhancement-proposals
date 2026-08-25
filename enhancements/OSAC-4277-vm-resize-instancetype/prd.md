# VM Resize via InstanceType Selection

| Field       | Value   |
|-------------|---------|
| Author(s)   | Ygal Blum |
| Jira        | https://redhat.atlassian.net/browse/OSAC-4277 |
| Date        | 2026-08-23 |

## Problem Statement

Tenant Admins and Tenant Users provision VMaaS ComputeInstances and need to
scale their CPU and memory as workload demands change, but today the only
way to change a running VM's compute resources is to recreate it. The OSAC
API no longer accepts direct CPU and RAM values from tenants — as originally
proposed in OSAC-39 — because compute sizing is now derived from a selected
InstanceType. Without a way to change a ComputeInstance's InstanceType
directly, tenants face unnecessary downtime and disruption from
re-provisioning just to right-size a VM they already have running. [Jira:
OSAC-4277]

## In Scope

- InstanceType changes apply to VMaaS ComputeInstances — this does not
  cover BMaaS or CaaS resource resizing.
- Both increasing and decreasing to a different InstanceType are supported —
  a target InstanceType is valid regardless of whether it moves CPU and
  memory in the same direction (e.g., increasing CPU while decreasing memory
  is supported the same as any other target). [Clarify: R1.Q1]
- A resize target's eligibility follows the same InstanceType lifecycle-state
  rules as VM creation (see OSAC-46): an `ACTIVE` or `DEPRECATED` target is a
  valid resize target (`DEPRECATED` succeeds with a warning), and an
  `OBSOLETE` target is invalid and rejected per the existing "invalid or
  incompatible" requirement. Resizing to the ComputeInstance's current
  InstanceType is a no-op — the no-op check takes precedence over lifecycle
  validation, so a request targeting the current InstanceType is always a
  no-op even when that InstanceType is `DEPRECATED` or `OBSOLETE`.

## Out of Scope

- Disk size resize — a ComputeInstance's storage is unaffected by an
  InstanceType change.
- Specific API error codes and response formats for rejected or no-op resize
  requests — a design-level concern for the design document.
- Quota validation on InstanceType changes.
- Audit or tracking of InstanceType changes.
- Automatic scaling or auto-resize — InstanceType changes are only made in
  response to an explicit request from a Tenant Admin or Tenant User.
- Guaranteed restart-free resize — whether a restart is required depends on
  the OSAC deployment (see the restart-notice note under User Stories).
- OSAC UI console support — InstanceType resize is available via API only
  in this feature; the OSAC UI does not currently support ComputeInstance
  updates beyond power management. [Clarify: R1.Q3]

## User Stories

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want to change a running VM's
  InstanceType via API so that I can scale CPU and memory up or down without
  recreating the VM.
- As a Tenant Admin or Tenant User, I want a request for an InstanceType
  that's invalid or incompatible with my ComputeInstance to be rejected
  immediately when possible, so that I don't wait for a change that can't
  succeed. [Clarify: R1.Q5]

**Note:** Whether an InstanceType resize requires a VM restart is a property
of the OSAC deployment, documented for Tenant Admins and Tenant Users — in
most deployments no restart is required. Where one is required, the user who
requested the change is responsible for restarting the VM themselves; OSAC
does not restart it automatically.

## Dependencies

- **InstanceType-based sizing:** This feature depends on ComputeInstance CPU
  and memory already being derived from a selected InstanceType rather than
  set directly through the OSAC API, replacing the model originally proposed
  in OSAC-39.

---

## Provenance

Authored: draft @ prd 0.8.0 - 7efcedb, workspace main @ 6e8f396
Final: respond @ prd 0.8.0 - 7efcedb, workspace main @ 505e141

> Context changed between draft and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.8.0","ai_workflows":"7efcedb","source_repo":"505e141","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","respond","respond","respond","respond","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
