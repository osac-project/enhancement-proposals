# Raw Requirements — OSAC-7019

## Source Issue

- **Key:** [OSAC-7019](https://redhat.atlassian.net/browse/OSAC-7019)
- **Summary:** VM pause/resume
- **Status:** New
- **Priority:** Major
- **Labels:** osac-ui, osac-ux
- **Fix Version:** 0.5
- **Component:** VMaaS
- **Team:** OSAC-VMaaS
- **Size:** Not set in the returned issue.
- **Captured:** 2026-10-30 through the Jira MCP.

## Description

### Feature Goal

Allow tenant users to pause a running VM and resume its execution later through the OSAC API and UI, preserving its RAM contents, application execution state, configuration, disks, and network identity.

In this Feature, **resume** means KubeVirt **unpause**: execution continues in the same VM instance without shutting down or booting again.

### Problem Statement

Tenants need to temporarily freeze a workload and later continue it from its existing execution state. Stopping a VM and starting it again does not preserve its RAM contents or running application state.

KubeVirt already provides pause/unpause operations. This Feature exposes that capability through OSAC with tenant authorization, accurate state reporting, clear errors, and UI actions.

Pause freezes guest execution and I/O while the VM's memory remains allocated. Resume uses that retained memory; it does not reload a saved memory image or perform a new boot. Pausing does not automatically release Kubernetes resource reservations and is not a mechanism for reclaiming the VM's allocated memory.

### Tenant User Stories

- As a Tenant User, I want to pause a running VM so that its execution freezes while its RAM contents and application execution state are retained.
- As a Tenant User, I want to resume a paused VM so that its applications continue from their retained execution state without booting again.
- As a Tenant User, I want my VM's configuration, disks, and network identity to remain associated with the same VM across pause/resume.
- As a Tenant User, I want to see whether my VM is running or paused, and see progress while an operation is pending.
- As a Tenant User, I want clear feedback when pause or resume fails so that I understand the VM's observed state and what action is needed.
- As a Tenant User, I want to understand which resources remain allocated while my VM is paused.

### Definition of Done

#### VM Lifecycle and Persistence

- A tenant can pause a running VM and resume a paused VM through the API and UI using KubeVirt pause/unpause semantics.
- Pause/resume does not delete or recreate the OSAC ComputeInstance, the KubeVirt VirtualMachine, or its running VirtualMachineInstance.
- Guest execution and I/O freeze while paused; RAM remains allocated and retains application execution state.
- Resume continues execution in the same VM instance without a shutdown, reboot, or fresh operating-system boot.
- The VM's configuration, associated disks, and persisted disk contents are retained across pause/resume.
- Network identity is retained according to explicitly documented guarantees. Preservation of external connections or sessions is not implied by preserving VM memory.
- Memory allocation and Kubernetes resource-reservation behavior while paused are documented and validated. Pause must not be described as releasing the VM's allocated RAM.

#### State and Error Handling

- The API and UI distinguish running and paused VMs and show progress while pause/resume is pending.
- Failed operations return clear errors and leave the reported state consistent with the observed VM state.
- Behavior is defined and tested for repeated requests, conflicting requests, and requests received while an operation is in progress.
- Behavior is defined and tested when pause/resume is requested for a VM that is stopped, failed, or being deleted.
- Deletion behavior for paused VMs and interactions with existing lifecycle operations are defined and tested.

#### Authorization and UI

- Pause and resume enforce the agreed tenant authorization rules.
- Attempts to perform these operations against another tenant's VM are rejected.
- The UI exposes the appropriate actions for the current state and displays operation progress and failures.

#### Validation and Documentation

- API operations, state transitions, authorization requirements, and error responses are documented.
- Automated tests cover pause/resume, retained memory and execution state, persistence guarantees, repeated or conflicting requests, failure handling, and tenant isolation.
- E2E validation covers the API and UI workflows, including verification that application execution continues from retained RAM after resume without a fresh boot.
- User documentation distinguishes pause/resume from stop/start and suspend-to-disk, explains resource retention, and describes any application or external-session limitations.

### Out of Scope

- Scheduled or automated pause/resume, such as power schedules.
- Suspend-to-disk / hibernation or saving RAM to persistent storage.
- Live migration of VMs between hosts or clusters.
- Changes to existing stop/start/restart, graceful-shutdown, or force-stop behavior.

### Open Questions — Resolve During PRD and Design

- What exactly does network identity preservation guarantee, including IP and MAC addresses where applicable?
- What are the expected responses to repeated requests and conflicting requests during transitions?
- How should pause/resume interact with existing stop/start/restart and deletion, including deletion of a paused VM?
- What user-visible behavior is expected if the underlying VM instance or host fails while a VM is paused?
- How should paused VMs be represented in tenant quota and resource-allocation reporting, given that RAM and resource reservations remain allocated?
- Do Tenant Admins, Cloud Provider Admins, or Cloud Infrastructure Admins require additional controls or visibility?
- How should this Feature be coordinated with [OSAC-1844](https://redhat.atlassian.net/browse/OSAC-1844), which also describes exposing KubeVirt pause/unpause in the UI?

### Reference

- [KubeVirt lifecycle — pausing and unpausing a virtual machine](https://kubevirt.io/user-guide/user_workloads/lifecycle/#pausing-and-unpausing-a-virtual-machine)

## Acceptance Criteria / Definition of Done

The complete source Definition of Done is preserved under Description above,
including lifecycle and persistence, state/error handling, authorization/UI,
and validation/documentation. No implementation or QE child issues are used
as requirements.

## Comments

No comments were returned for the Feature.

## Linked Issues

### OSAC-1844: Expose VM Pause/Resume and additional KubeVirt lifecycle states in UI

- **Relationship:** Referenced in the Feature description as overlapping work;
  no formal Jira issue link was returned.
- **Status:** New
- **Use:** Context for scope coordination. Its billing statements and additional
  lifecycle states are not adopted as requirements of OSAC-7019.
- **Source:** https://redhat.atlassian.net/browse/OSAC-1844

#### Feature Goal
Expose additional KubeVirt VM lifecycle operations in the OSAC UI — starting with **Pause** — so users can manage VM state beyond Start, Stop, Restart, and Delete, with clarity on billing implications per state.

#### Problem Statement
The current VM operations exposed in the UI are: **Start**, **Stop**, **Restart**, **Delete**.

These map to `run\_strategy` and `restart\_requested\_at` spec fields. While a VM is fully running, all used resources are billed. When fully stopped, typically only storage is billed.

KubeVirt supports additional states that are not exposed today — for example **Pause**, where RAM contents are retained so the machine is not fully off. In a paused state, RAM is also billed and may be useful for certain applications \(fast resume without cold boot\).

Pause \(and potentially other KubeVirt\-supported states\) could be implemented similarly to the existing start/stop/restart options.

#### User Stories
  - As an OSAC user, I want to **Pause* a running VM so I can suspend execution while keeping RAM state for faster resume than a full stop/start cycle.
- As an OSAC user, I want to understand billing impact per VM state \(running, stopped, paused\) when choosing an operation.
- As an OSAC operator, I want UI operations aligned with KubeVirt lifecycle capabilities rather than a subset of supported states.
- As an OSAC admin, I want pause/resume governed by the same RBAC and tenant boundaries as other VM operations.

#### Proposed Solution
1. **UI operations**
      - Add **Pause** and **Resume** \(unpause\) actions alongside Start, Stop, Restart, Delete where the VM state allows.
      - Disable or hide actions with clear tooltips when not applicable.
1. **Backend alignment**
      - Wire operations to KubeVirt pause/unpause \(and related spec/status fields\) via fulfillment/operator path used for start/stop/restart.
1. **State and billing clarity**
      - Surface current VM state in the UI \(running, paused, stopped, etc.\).
      - Document or display billing notes: running = full resources; stopped ≈ storage; paused = RAM \+ storage \(per platform billing model\).
1. **Future states**
      - Evaluate other KubeVirt\-supported lifecycle states for follow\-on exposure if valuable.

#### Definition of Done
- \ \ Pause and Resume available in UI when KubeVirt supports them for the VM
- \ \ Operations integrated with existing VM action pattern \(same as start/stop/restart\)
- \ \ VM state reflected accurately in list and detail views
- \ \ Billing/resource implications documented or surfaced for running vs stopped vs paused
- \ \ RBAC and error handling consistent with existing VM operations

#### Out of Scope
- Changing platform metering/billing engine logic \(document behavior only unless API changes required\)
- Exposing every KubeVirt internal state in v1 \(prioritize Pause/Resume\)

## Attachments

No attachments were returned. No remote document links were returned.

## Initial Observations

The Feature now defines pause/resume as KubeVirt pause/unpause with RAM and
execution state retained in the same VM. UI and API delivery, milestone 0.5,
tenant isolation, persistence, state/error reporting, and validation are
specified. Network guarantees, detailed lifecycle responses, host-failure
handling, quota reporting, admin capabilities, and coordination with OSAC-1844
remain open; CLI scope has not been decided in the conversation.

## Background Evidence

This material grounds the draft; it does not substitute for product decisions
or prove deployed functionality.

- The current UI lifecycle client declares Start, Stop, and Restart actions
  in `osac-ui/libs/ui-components/src/api/v1/compute-instance.ts`. Source
  inspection supports the existing interface baseline described by OSAC-1844;
  no live end-to-end validation was performed.
- [KubeVirt lifecycle](https://kubevirt.io/user-guide/user_workloads/lifecycle/#pausing-and-unpausing-a-virtual-machine)
  documents frozen guest CPU execution and I/O with memory kept allocated.
  Resume corresponds to unpause.
- OSAC's [networking decisions](https://github.com/osac-project/osac/blob/main/docs/agent-context/networking-decisions.md)
  and [VMaaS networking design](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-1435-vmaas-networking/design.md#network-status-and-address-discovery)
  define the accepted networking target. The latter commits to keeping the
  guest address across restarts and live migration. Pause-specific IP/MAC
  and long-pause guarantees must align with that contract.
- The enhancement-proposals checkout and live upstream main both resolved to
  `84b705f723b2e73a359de7c502786583184b0849` when the template and networking
  design were read on 2026-10-30. Accepted designs are target contracts, not
  claims that all target behavior is deployed.

## Drafting Sources

- Workflow: installed `prd` skill, version 0.11.5.
- Project section guidance: `.prd/templates/section-guidance.md`.
- Template: `enhancement-proposals/guidelines/prd_template.md`, identified by
  the authoritative project section guidance. It uses Problem Statement,
  In Scope, Out of Scope, User Stories, and optional Assumptions/Dependencies.
- Source decisions from the conversation are recorded in
  `02-clarifications.md`.
