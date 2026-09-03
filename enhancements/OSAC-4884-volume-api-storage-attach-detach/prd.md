# Volume API Storage Attach and Detach

| Field       | Value   |
|-------------|---------|
| Author(s)   | Roy Golan |
| Jira        | [OSAC-4884](https://redhat.atlassian.net/browse/OSAC-4884) |
| Date        | 2026-09-03 |

## Problem Statement

OSAC users have no supported public path to attach or detach a volume from OSAC-managed compute. BMaaS and VMaaS workflows therefore cannot manage the complete volume lifecycle through OSAC, while CaaS attachment follows a separate path with different lifecycle behavior. This prevents consistent authorization, progress visibility, retry behavior, and lifecycle safety across compute services. Without this feature, non-CSI consumers remain incomplete and CaaS storage attachment remains inconsistent with other OSAC services. [Clarify: R4.Q1, R4.Q2]

## In Scope

- Delivery targets the OSAC 0.3 milestone.
- Authorized users and system components can attach and detach volumes through equivalent public gRPC and REST behavior. [Clarify: R1.Q1, R2.Q1]
- Attach and detach support OSAC-managed BMaaS, VMaaS, and CaaS compute targets. CaaS retains its regular CSI workflow while gaining the same attachment lifecycle behavior as other OSAC compute services. [Clarify: R3.Q2, R4.Q1, R4.Q2]
- Callers can observe pending, successful, and failed outcomes. Requests honor caller deadlines, repeated requests for an already-satisfied state succeed without duplicate effects, transient backend failures are retried automatically, and completion time remains backend-dependent. [Clarify: R1.Q4, R2.Q3, R2.Q4, R3.Q5]
- Attachment behavior honors volume access and storage backend capabilities: supported concurrent attachments are accepted, unsupported concurrent attachments are rejected, and attach and detach requests succeed as no-ops when controller-side attachment is not required. [Clarify: R1.Q3, R1.Q5]
- Existing CSI-managed volumes and attachments continue to work without recreation or user action when the CSI driver adopts the Volume API path. [Clarify: R3.Q4]
- User and operator documentation covers public gRPC and REST request, response, progress, error, authorization, lifecycle, and operator-recovery semantics for attach and detach. Automated verification includes one backend-neutral representative end-to-end flow that demonstrates both attach and detach, plus coverage of successful operations, retries, invalid targets, cross-tenant authorization failures, backend failures, and CSI migration. [Clarify: R3.Q3, R4.Q3]

## Out of Scope

- Dedicated UI or CLI support for attach and detach. [Clarify: R2.Q1]
- A user-facing force-detach operation; terminal detach failures require operator recovery. [Clarify: R3.Q3]
- Attachment to targets that are not managed as OSAC compute. [Clarify: R3.Q2]
- Backend-specific attachment interfaces exposed directly to users.
- Changes to volume create, update, or delete behavior beyond the attachment-related lifecycle protections described here. [Clarify: R2.Q5]

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to attach and detach authorized volumes across tenant environments so that I can administer storage while tenant users remain isolated to their own resources. [Clarify: R2.Q2]
- As a Cloud Provider Admin, I want to see pending, successful, and failed attachment outcomes so that I can distinguish ongoing work from failures that require intervention. [Clarify: R1.Q4, R2.Q4]

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want BMaaS, VMaaS, and CaaS storage attachment to use one supported OSAC capability so that storage integrations have consistent lifecycle behavior across compute services. [Clarify: R4.Q1, R4.Q2]
- As a Cloud Infrastructure Admin, I want to attach and detach volumes for BMaaS compute without involving a CSI driver so that bare-metal storage workflows can be completed through OSAC APIs.
- As a Cloud Infrastructure Admin, I want terminal detach failures to remain visible so that I can recover the backend safely instead of masking uncertain attachment state with force detach. [Clarify: R3.Q3]

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want to attach and detach my tenant's volumes from authorized BMaaS and VMaaS compute so that I can complete persistent-storage workflows without backend-specific access. [Clarify: R1.Q1, R2.Q2, R4.Q1]
- As a Tenant Admin or Tenant User, I want CaaS volumes to continue attaching through the regular Kubernetes storage workflow so that CaaS gains consistent attachment lifecycle protections without changing how workloads request storage. [Clarify: R4.Q2]
- As a Tenant Admin or Tenant User, I want existing CSI-managed volumes and attachments to remain usable without recreation or user action so that migration does not disrupt workloads. [Clarify: R3.Q4]
- As a Tenant Admin or Tenant User, I want repeated attach and detach requests to succeed without duplicate effects so that retries are safe after timeouts or interrupted clients. [Clarify: R2.Q3, R3.Q5]
- As a Tenant Admin or Tenant User, I want supported concurrent attachment requests accepted so that volumes with multi-target access capabilities can be used as intended. [Clarify: R1.Q3]
- As a Tenant Admin or Tenant User, I want unsupported concurrent attachment requests rejected according to the volume's access and backend capabilities so that incompatible access does not put data at risk. [Clarify: R1.Q3]
- As a Tenant Admin or Tenant User, I want attach and detach to succeed for volumes that require no controller-side attachment so that the same workflow works across storage capabilities. [Clarify: R1.Q5]
- As a Tenant Admin or Tenant User, I want deleting a compute target to clean up its volume attachments so that target lifecycle operations do not leave stale attachment state. [Clarify: R2.Q5]
- As a Tenant Admin or Tenant User, I want volume deletion blocked until all attachments are removed so that attached storage is not deleted while still in use. [Clarify: R2.Q5]

## Dependencies

- **Public Volume API:** [osac#743](https://github.com/osac-project/osac/pull/743/) must expose the Volume API publicly before public attach and detach behavior can be delivered. [Clarify: R3.Q1]
- **OSAC CSI driver:** The driver must use the Volume API attachment capability for CaaS while preserving existing volumes and attachments without user action. [Clarify: R3.Q4, R4.Q2]

---

## Provenance

Authored: draft @ prd 0.9.0 - 562b610, workspace feature-attach-detach @ 63b090a

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.9.0","ai_workflows":"562b610","source_repo":"63b090a","source_repo_branch":"feature-attach-detach","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
