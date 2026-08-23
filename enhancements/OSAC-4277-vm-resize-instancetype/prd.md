# VM Resize via InstanceType Selection

| Field       | Value   |
|-------------|---------|
| Author(s)   | Ygal Blum |
| Jira        | https://redhat.atlassian.net/browse/OSAC-4277 |
| Date        | 2026-08-23 |

## Problem Statement

Tenant Users provision VMaaS ComputeInstances and need to scale their CPU and
memory as workload demands change, but today the only way to change a
running VM's compute resources is to recreate it. The fulfillment-service
API no longer accepts direct CPU and RAM values from tenants — as
originally proposed in OSAC-39 — because compute sizing is now derived from
a selected InstanceType. Without a way to change a ComputeInstance's
InstanceType directly, Tenant Users face unnecessary downtime and
disruption from re-provisioning just to right-size a VM they already have
running. [Jira: OSAC-4277]

## In Scope

- InstanceType changes apply to VMaaS ComputeInstances — this does not
  cover BMaaS or CaaS resource resizing.
- Both increasing and decreasing to a different InstanceType are supported.
  [Clarify: R1.Q1]

## Out of Scope

- Disk size resize — a ComputeInstance's storage is unaffected by an
  InstanceType change.
- Quota validation on InstanceType changes.
- Audit or tracking of InstanceType changes.
- Automatic scaling or auto-resize — InstanceType changes are only made in
  response to an explicit Tenant User request.
- Live migration during a resize — a VM restart is the fallback when
  hot-plug isn't supported for the requested change.
- OSAC UI console support — InstanceType resize is available via API only
  in this feature; the OSAC UI does not currently support ComputeInstance
  updates beyond power management. [Clarify: R1.Q3]

## User Stories

### Tenant User

- As a Tenant User, I want to change a running VM's InstanceType via API so
  that I can scale CPU and memory up or down without recreating the VM.
- As a Tenant User, I want to know whether an InstanceType change will
  require restarting my VM before I request it, so that I can plan for the
  downtime. To be determined — whether the Tenant User must initiate that
  restart themselves or OSAC restarts the VM automatically. [Clarify: R1.Q2]
- As a Tenant User, I want a request for an InstanceType that's invalid or
  incompatible with my ComputeInstance to be rejected immediately when
  possible, so that I don't wait for a change that can't succeed. [Clarify:
  R1.Q5]

## Assumptions

- Whether an InstanceType change is eligible for hot-plug or requires a
  restart is assumed to be a predictable, cluster-level capability that a
  Tenant User can know ahead of time — not an outcome that varies
  unpredictably per individual request. [Clarify: R1.Q2]

## Dependencies

- **fulfillment-service InstanceType-based sizing:** This feature depends
  on ComputeInstance CPU and memory already being derived from a selected
  InstanceType rather than set directly, replacing the model originally
  proposed in OSAC-39.

---

## Provenance

Authored: draft @ prd 0.8.0 - 7efcedb, workspace main @ 6e8f396

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.8.0","ai_workflows":"7efcedb","source_repo":"6e8f396","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
