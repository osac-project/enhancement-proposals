# Clarification Log — OSAC-7158

## Status

- Rounds completed: 6
- Open gaps: 0
- Exit criteria met: Yes

## Round 1 — Configuration status and list behavior

### R1.Q1: Status after configuration succeeds

The goal says users can see which VMs completed configuration, while the Definition of Done says successful configuration should no longer appear as outstanding work. What should the VM row show after configuration succeeds?

#### Answer

Show a clear positive indication in the VM row that the requested configuration is applied. The exact wording is left to design.

#### Impact

The PRD should describe a positive applied state after success without prescribing the exact wording.

#### Decision (D1)

After configuration succeeds, the VM row shows a clear positive indication that the requested configuration is applied. The exact wording is left to design.

---

### R1.Q2: Prerequisite-blocked configuration

When a prerequisite blocks a configuration change, should the row treat it as waiting with a reason, or show a separate blocked state?

#### Answer

Use the waiting state and include the prerequisite reason.

#### Impact

The PRD should describe prerequisite-blocked work as waiting, with the reason visible, rather than as a separate blocked state.

#### Decision (D2)

Prerequisite-blocked work is shown as waiting with its reason.

---

### R1.Q3: Elapsed-time meaning

The ticket asks for elapsed time in the current VM state and elapsed time since configuration became unapplied. Which timing should the VM list show?

#### Answer

Show elapsed time only while a configuration status condition indicates “Applying configuration.” For permanent conditions such as “Applied” or “Failed to apply,” show the exact date and time when the condition changed. Do not show time for overall VM state, such as RUNNING.

#### Impact

Elapsed time applies only to the active Applying configuration condition. Permanent condition changes are represented by their date and time. Overall VM state has no timer.

---

### R1.Q4: User-facing interfaces

The ticket focuses on the VM list and also requires public status. Which user-facing interfaces should this feature cover?

#### Answer

The UI list is in scope. CLI output such as `osac get` is not in scope. API data may need to be provided to support the UI.

#### Impact

The PRD should focus on the UI list. API data is in scope only as needed to support that UI; no separate CLI behavior is required.

#### Decision (D3)

The UI list is the user-facing surface. CLI behavior is not in scope. API support may be needed to supply the UI.

---

## Round 2 — Configuration timing and status coverage

### R2.Q1: Configuration timing instead of VM-state timing

The ticket asks for elapsed time in the current VM state and elapsed time since configuration became unapplied. Which timing should the VM list show, and how should it behave across status changes?

#### Answer

Do not show time for overall VM state, such as RUNNING. Show elapsed time only while a configuration status condition indicates “Applying configuration.” For permanent “Applied” or “Failed to apply” conditions, show the exact date and time when the condition changed.

#### Impact

The PRD should specify elapsed time only for the active Applying configuration condition, and condition-change date and time for permanent Applied or Failed to apply conditions. Overall VM state has no timer.

#### Decision (D4)

Do not show elapsed time for overall VM state, such as RUNNING. Show it only while a configuration condition indicates Applying configuration.

---

### R2.Q2: Retry and failure message detail

The ticket asks for safe, plain-language retry and failure explanations. How much should the row message tell the user?

#### Answer

Error-specific messages cannot be predicted in advance; the user asked whether the PRD needs to state them.

#### Impact

The PRD does not need to enumerate messages for individual errors. Keep the source's generic requirement for safe, plain-language explanations. Detailed error-to-message mapping can be addressed in design.

---

### R2.Q3: Scope of the positive applied state

Should a positive applied state appear for every VM whose requested configuration is currently applied, or only after a configuration change completes successfully?

#### Answer

Show the positive applied state for every VM whose requested configuration is applied. The exact wording is left to design.

#### Impact

The positive applied state describes the current configuration, not only the result of a recent change. The PRD should not prescribe its exact wording.

#### Decision (D5)

Show a positive applied state for every VM whose requested configuration is applied. Leave the exact wording to design.

---

## Round 3 — Configuration time display

### R3.Q1: Event time for completed and failed states

For the positive applied state and final failure, should the row show an exact date/time, relative age, or both?

#### Answer

Show the date and time when the state occurred.

#### Impact

The PRD should specify the exact date and time when permanent Applied or Failed to apply conditions changed. Do not show elapsed time from those transitions. The exact format can be settled in design.

#### Decision (D6)

For permanent Applied or Failed to apply conditions, show the exact date and time when the condition changed, not an elapsed-time value.

---

### R3.Q2: Duration while configuration is applying

While configuration is applying, should its duration reset for each retry attempt, or measure the total time since configuration first became unapplied, including retry waits?

#### Answer

Show elapsed time only while a configuration status condition indicates “Applying configuration.” Do not aggregate the duration across retry waits or other non-Applying conditions.

#### Impact

The timer measures time in the active Applying configuration condition, not the total age of the unresolved configuration change.

#### Decision (D7)

Show elapsed time only while the Applying configuration condition is active. Do not accumulate elapsed time across retry waits or other non-Applying conditions.

---

### R3.Q3: Retry state visibility

After a failed attempt that will be retried, what should the VM row communicate?

#### Answer

Indicate that the system will retry. The message may say a retry is scheduled or that the system will retry. Exact wording is left to design.

#### Impact

The row should distinguish an expected retry from a final failure. The retry start time is not the priority.

#### Decision (D8)

When another attempt will occur after a failure, make that retry intent clear in the row and keep it distinct from final failure. Exact wording is left to design.

---

## Round 4 — Scope and presentation boundaries

### R4.Q1: Personas for OSAC-7158

Should the revised PRD keep the Cloud Provider Admin story from the existing PRD, given that the current OSAC-7158 user stories name Tenant User and Tenant Admin while the linked OSAC-6578 parent outcome includes Cloud Provider Admin?

#### Answer

Keep Tenant User and Tenant Admin only. Do not include a Cloud Provider Admin story in OSAC-7158. The parent outcome remains broader.

#### Impact

The Problem Statement and User Stories should describe Tenant User and Tenant Admin only. Keep the ticket's statement that existing access controls do not change.

#### Decision (D9)

This PRD covers Tenant User and Tenant Admin. Do not add Cloud Provider Admin as an affected persona for this feature; the parent outcome may cover that role.

---

### R4.Q2: Unsupported status distinctions

If available information cannot establish one of the status distinctions named in the ticket, should the PRD treat that distinction as covered or document it as a limitation?

#### Answer

Require the design to identify unsupported distinctions and what is needed to show them. An unsupported distinction must not be claimed as covered unless it is supported or explicitly accepted as a limitation.

#### Impact

The PRD should preserve the desired user-facing states without implying that every distinction is already supported. The design must assess data support and document any limitation before coverage is claimed.

#### Decision (D10)

Unsupported status distinctions and what is needed to support them must be documented. They are not considered covered unless supported or explicitly accepted as a limitation.

---

### R4.Q3: Timing in the Details view

Should the PRD set timestamp or elapsed-time requirements for Details in addition to the existing list timing decisions?

#### Answer

Leave timing in Details to the design.

#### Impact

The PRD should define the operation, status, and safe explanation shown in Details without prescribing its timing display. Existing clarified timing requirements for the VM list remain unchanged.

#### Decision (D11)

Do not add a timing requirement for Details to this PRD. The design decides whether and how Details shows timing; the previously clarified list timing remains in force.

---

## Round 5 — API and CLI user representation

### R5.Q1: How API and CLI users should appear in the PRD

Jira now includes API and CLI behavior and a generic API/CLI User story. OSAC's canonical personas are Tenant User and Tenant Admin, and either may use API or CLI. Should the PRD keep a separate generic API/CLI story or describe those interfaces through the tenant personas?

#### Answer

Describe API and CLI as additional ways for Tenant Users and Tenant Admins to view operation status. Do not treat API/CLI users as a separate OSAC persona.

#### Impact

The PRD will keep the canonical Tenant User and Tenant Admin stories and include UI, API, and CLI behavior in them. This replaces the earlier UI-only interface decision in R1.Q4. The precise API route is not required in the PRD. Existing applying-only elapsed-time and no-history decisions remain unchanged.

#### Decision (D12)

The feature covers the VM list and Details view, API list/get access, and CLI table, JSON, YAML, and describe output. API and CLI are interfaces for Tenant User and Tenant Admin, not separate personas. The PRD does not need to name an exact API route.

---

## Round 6 — History and retry controls

### R6.Q1: Operation history and shared tracking

A Jira comment asks whether OSAC-7158 should preserve history for all VM changes or track all VM operations through a shared mechanism. Should either capability be included?

#### Answer

Do not include operation history or a shared way to track all VM operations. Keep the feature focused on configuration-operation status.

#### Impact

Details continues to show only the current or most recent configuration operation. The feature does not add full history or a cross-operation tracking capability.

#### Decision (D13)

OSAC-7158 remains focused on configuration operations. Full history and a shared tracking capability for all VM operations are out of scope.

---

### R6.Q2: User control to stop retries

A Jira comment asks whether users should be able to stop a configuration operation that is retrying. Jira's Out of Scope excludes changes to retry behavior. Should OSAC-7158 add a stop or cancel action?

#### Answer

Do not add a stop or cancel action. Retry behavior remains unchanged.

#### Impact

The UI, API, and CLI communicate retry status, but do not let users stop or cancel a retrying configuration operation as part of OSAC-7158.

#### Decision (D14)

OSAC-7158 does not add a user control to stop or cancel retrying configuration operations. Retry behavior remains unchanged.

---

## Remaining Gaps

No open requirements-level gaps remain. Design must assess whether the available information supports each status distinction and document any unsupported distinction before claiming it is covered. Details timing remains for design.
