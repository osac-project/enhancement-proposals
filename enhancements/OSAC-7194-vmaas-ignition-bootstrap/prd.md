# Support Ignition for VM First Boot

| Field | Value |
|---|---|
| Author(s) | Riccardo Piccoli |
| Jira | https://redhat.atlassian.net/browse/OSAC-7194 |
| Date | 2026-11-19 |

## Problem Statement

VMaaS tenants can use cloud-init to configure new Linux VMs, but some images, such as Red Hat Enterprise Linux CoreOS (RHCOS), use Ignition instead. VMaaS can pass Ignition data to images that read it from a NoCloud disk, but the OpenStack RHCOS image used in the current CaaS CI profile expects a different data source. VMaaS does not yet provide a validated first-boot Ignition workflow for that worker image.

## In Scope

- A new VM from a compatible image applies the supplied Ignition configuration on first boot—for example, the tenant can sign in with a key from that configuration. Normal reboots do not reapply it.
- VMaaS rejects invalid, unsupported, or oversized configurations with a clear error and keeps sensitive configuration contents out of logs and errors.
- Existing Linux cloud-init and Windows first-boot workflows continue to work unchanged.

## Out of Scope

- Changing the Ignition configuration after VM creation.
- Changes to Bare Metal as a Service (BMaaS). BMaaS tenants can already use Ignition to configure bare-metal instances on first boot when the image supports it. CaaS uses this same capability to bootstrap its bare-metal workers.

## User Stories

### Tenant User

- As a Tenant User, I want to supply an Ignition configuration when I create a VM so I can use images that rely on Ignition without setting them up by hand.

## Dependencies

- [CaaS VM workers (OSAC-1589)](https://redhat.atlassian.net/browse/OSAC-1589) need this capability so RHCOS VMs can join a cluster as workers. The worker provisioning flow is covered separately.

---

## Provenance

Committed: commit @ prd 0.11.5 - 70405a6, workspace rccrdpccl/PRD-for-ignition-support @ d6ec029d0

> Authoring phases not recorded this session (commit-time snapshot only).

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"commit_only","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"70405a6","source_repo":"d6ec029d0","source_repo_branch":"rccrdpccl/PRD-for-ignition-support","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["commit"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
