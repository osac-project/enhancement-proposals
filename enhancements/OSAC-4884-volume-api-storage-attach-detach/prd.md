# Volume API Storage Attach and Detach

| Field       | Value   |
|-------------|---------|
| Author(s)   | Roy Golan |
| Jira        | [OSAC-4884](https://redhat.atlassian.net/browse/OSAC-4884) |
| Date        | 2026-09-03 |

## Problem Statement

OSAC users have no supported public path to attach or detach a volume from OSAC-managed compute. BMaaS and VMaaS workflows therefore cannot manage the complete volume lifecycle through OSAC, while CaaS attachment follows a separate path with different lifecycle behavior. This prevents consistent authorization, progress visibility, retry behavior, and lifecycle safety across compute services. Without this feature, non-CSI consumers remain incomplete and CaaS storage attachment remains inconsistent with other OSAC services.

## In Scope

- Delivery targets the OSAC 0.3 milestone.
- Authorized users and system components can attach and detach volumes through equivalent public gRPC, REST, CLI, and UI behavior.
- Direct attach and detach support OSAC-managed BMaaS and VMaaS compute targets. VMaaS uses the capability for boot disks and additional disks. CaaS retains its regular PVC and CSI workflow while gaining the same attachment lifecycle behavior as other OSAC compute services.
- Callers can observe pending, successful, and failed outcomes. Requests honor caller deadlines, repeated requests for an already-satisfied state succeed without duplicate effects, transient backend failures are retried automatically, and completion time remains backend-dependent.
- Attachment behavior honors volume access and storage backend capabilities: supported multi-attachments are accepted, unsupported multi-attachments are rejected, and attach and detach requests succeed as no-ops when controller-side attachment is not required.
- Existing CSI-managed volumes and attachments continue to work without recreation or user action when the CSI driver adopts the Volume API path.
- User and operator documentation covers public gRPC, REST, CLI, and UI request, response, progress, error, authorization, lifecycle, and operator-recovery semantics for attach and detach. Automated verification includes one backend-neutral representative end-to-end flow that demonstrates both attach and detach, plus coverage of successful operations, retries, invalid targets, cross-tenant authorization failures, backend failures, and CSI migration.

## Out of Scope

- A user-facing force-detach operation; terminal detach failures require operator recovery.
- Direct attachment to CaaS clusters or nodes, or to targets that are not managed as OSAC compute.
- Backend-specific attachment interfaces exposed directly to users.
- Changes to volume create, update, or delete behavior beyond the attachment-related lifecycle protections described here.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to attach and detach authorized volumes across tenant environments through the public APIs or CLI so that I can administer storage while tenant users remain isolated to their own resources.
- As a Cloud Provider Admin, I want to attach and detach authorized volumes through the OSAC UI so that I can administer storage without switching interfaces.
- As a Cloud Provider Admin, I want to see pending, successful, and failed attachment outcomes so that I can distinguish ongoing work from failures that require intervention.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want BMaaS and VMaaS direct attachment and CaaS CSI attachment to share consistent lifecycle behavior so that storage integrations behave consistently across compute services.
- As a Cloud Infrastructure Admin, I want to attach and detach volumes for BMaaS compute without involving a CSI driver so that bare-metal storage workflows can be completed through OSAC APIs.
- As a Cloud Infrastructure Admin, I want terminal detach failures to remain visible so that I can recover the backend safely instead of masking uncertain attachment state with force detach.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want to attach and detach my tenant's volumes from authorized BMaaS and VMaaS compute through the public APIs or CLI so that I can complete persistent-storage workflows without backend-specific access.
- As a Tenant Admin or Tenant User, I want to attach and detach authorized volumes through the OSAC UI so that I can complete persistent-storage workflows through click-ops.
- As a Tenant Admin or Tenant User, I want VMaaS to attach volumes as boot disks and additional disks so that VM storage can use the same supported lifecycle.
- As a Tenant Admin or Tenant User, I want CaaS volumes to continue attaching through the regular Kubernetes PVC and CSI workflow so that CaaS gains consistent attachment lifecycle protections without changing how workloads request storage.
- As a Tenant Admin or Tenant User, I want existing CSI-managed volumes and attachments to remain usable without recreation or user action so that migration does not disrupt workloads.
- As a Tenant Admin or Tenant User, I want repeated attach and detach requests to succeed without duplicate effects so that retries are safe after timeouts or interrupted clients.
- As a Tenant Admin or Tenant User, I want supported multi-attachment requests accepted so that volumes with multi-target access capabilities can be used as intended.
- As a Tenant Admin or Tenant User, I want unsupported multi-attachment requests rejected according to the volume's access and backend capabilities so that incompatible access does not put data at risk.
- As a Tenant Admin or Tenant User, I want deleting a compute target to clean up its volume attachments so that target lifecycle operations do not leave stale attachment state.
- As a Tenant Admin or Tenant User, I want volume deletion blocked until all attachments are removed so that attached storage is not deleted while still in use.

## Dependencies

- **Public Volume API:** [osac#743](https://github.com/osac-project/osac/pull/743/) must expose the Volume API publicly before public attach and detach behavior can be delivered.
- **OSAC CSI driver:** The driver must use the Volume API attachment capability for CaaS while preserving existing volumes and attachments without user action.

---

## Provenance

Committed: commit @ prd 0.9.0 - 562b610, workspace prd/OSAC-4884 @ 666aafd (163 behind origin/main, dirty)

> Authoring phases not recorded this session (commit-time snapshot only).

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"commit_only","workflow":"prd","workflow_version":"0.9.0","ai_workflows":"562b610","source_repo":"666aafd (dirty)","source_repo_branch":"prd/OSAC-4884","commits_behind_main":163,"commits_ahead_main":2,"main_ref":"main","phases":["commit"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
