# Adopt Existing OpenShift Virtualization VMs

| Field | Value |
|---|---|
| Author(s) | Marc Sluiter |
| Jira | [OSAC-4661](https://redhat.atlassian.net/browse/OSAC-4661) |
| Date | 2026-11-13 |

## Problem Statement

OSAC VMaaS lets tenants provision and manage new VMs, but does not provide a supported way to bring an existing OpenShift Virtualization VM under OSAC management. To use OSAC today, a tenant must provision a replacement VM and may need to move its data, disrupting the workload.

**VM adoption** brings an eligible existing VM under OSAC management as a ComputeInstance without recreating it or copying its disk.

## In Scope

- MVP for VMaaS in OSAC 0.6: adopt one eligible existing VM with one persistent guest disk and one network interface in an OSAC-managed namespace, regardless of how the VM was created. [Clarify: R8.Q1] [Clarify: R10.Q1]
- Use the CLI or API to identify the VM explicitly, check its eligibility and report whether adoption succeeded or why it failed. Reject the request if OSAC cannot verify that it is still the intended VM. Repeated or concurrent requests must not create duplicate ComputeInstances. [Clarify: R1.Q2] [Clarify: R9.Q2]
- Preserve the existing VM and disk during adoption, including the VM's machine identity (such as its hostname), applications, data and network attachment. A stop is permitted when necessary but should be avoided; the requester must approve it beforehand. [Clarify: R7.Q3] [Clarify: R8.Q3]
- Use existing OSAC networking and storage capabilities without changing those features. Reject adoption with a reason if OSAC cannot verify tenant network isolation, manage the existing disk as a full OSAC Volume, or provide the required VM and Volume operations. [Clarify: R3.Q3] [Clarify: R7.Q2] [Clarify: R10.Q2]
- After adoption, the VM has the same supported management operations, including authorized deletion, console access and metadata behavior as other VMaaS VMs in the same OSAC release. Tenant isolation, quota and accounting continue to apply; adoption is rejected if quota limits or required checks cannot be met. [Clarify: R2.Q4] [Clarify: R3.Q1] [Clarify: R4.Q2] [Clarify: R7.Q1] [Clarify: R10.Q3]
- Document adoption eligibility, the CLI/API workflow and recovery from failures.

## Out of Scope

- Migrating VMs, installing or registering clusters, and discovering fleets of existing VMs.
- Changes to OSAC networking or storage features, new UI workflows, and automatic mapping of existing source labels into OSAC. [Clarify: R1.Q2] [Clarify: R7.Q1] [Clarify: R10.Q1]

Bringing existing clusters under OSAC management and automatic source-label mapping remain broader OSAC-4661 requirements until delivered or explicitly assigned. [Clarify: R1.Q1] [Clarify: R7.Q1]

## User Stories

### Cloud Provider Admin / Tenant Admin

- As an authorized Cloud Provider Admin or Tenant Admin, I want to adopt a specified eligible VM into a tenant I can manage so that the tenant can use it as an OSAC ComputeInstance without replacing it. [Clarify: R5.Q2]
- As an authorized Cloud Provider Admin or Tenant Admin, I want an actionable reason when adoption fails and a safe way to retry after the issue is corrected so that the existing VM and its data are not lost. [Clarify: R4.Q4]
- As an authorized Cloud Provider Admin or Tenant Admin, I want to approve any required stop before OSAC stops the VM so that I can control disruption to its workload. [Clarify: R8.Q3]
- As an authorized Cloud Provider Admin or Tenant Admin, I want OSAC to restore the VM's prior running state when safe after an adoption attempt so that the workload can resume. If restoration is unsafe, OSAC does not restart the VM and reports why; after failed adoption, the prior owner coordinates recovery. OSAC also reports restoration failures. [Clarify: R8.Q4] [Clarify: R9.Q3]

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want adoption to reject VMs whose existing tenant network or storage is incompatible or cannot be verified so that an adoption does not compromise isolation or the existing workload. [Clarify: R3.Q3] [Clarify: R10.Q2]

### Tenant Admin / Tenant User

- As an authorized Tenant Admin or Tenant User, I want to list and inspect an adopted ComputeInstance and its existing Volume so that I can find and manage my organization's existing workload through OSAC.
- As an authorized Tenant Admin or Tenant User, I want to open the adopted VM's console so that I can access its guest without switching to OpenShift Virtualization. [Clarify: R4.Q2]
- As an authorized Tenant Admin or Tenant User, I want to use the same supported VM and Volume operations as for other VMaaS resources in the same OSAC release so that I can manage the workload consistently. [Clarify: R8.Q2]

## Assumptions

- The VM's existing owner remains responsible until adoption succeeds and ownership is explicitly handed over. On failure, the VM and its data remain with that owner. [Clarify: R5.Q1] [Clarify: R5.Q4]
- After handoff, the VM is managed only through OSAC. Users and other management tools must not change it outside OSAC; OSAC cannot prevent such changes. [Clarify: R7.Q4] [Clarify: R12.Q1]
- The tenant is not deleted during the MVP. This assumption does not waive tenant isolation or existing data-safety protections. [Clarify: R9.Q4]

## Dependencies

- **Pilot qualification:** Before the first pilot adoption, select and record one VM operating system, OSAC and OpenShift versions, network, and storage backend. Trial adoption with a disposable VM using that combination. It qualifies only if the same VM is exposed as a ComputeInstance and its original disk as a full OSAC Volume, without recreating the VM or copying the disk; the tenant can access its console and use supported VM and Volume operations; and its network remains isolated to that tenant. This verifies only the tested combination; others remain unsupported until tested. [Clarify: R4.Q3] [Clarify: R6.Q1] [Clarify: R7.Q2] [Clarify: R8.Q2] [Clarify: R10.Q2]
- **Recovery:** The existing owner coordinates repair of a partial adoption with an authorized OSAC administrator; the requester receives status and can escalate. [Clarify: R6.Q3]

---

## Provenance

Authored: revise @ prd 0.11.5 - cd88680, workspace slintes/OSAC-4661 @ 6d1dae702 (86 behind origin/main)
Phases: draft, revise, revise, revise, revise, revise, revise, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"cd88680","source_repo":"6d1dae702","source_repo_branch":"slintes/OSAC-4661","commits_behind_main":86,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
