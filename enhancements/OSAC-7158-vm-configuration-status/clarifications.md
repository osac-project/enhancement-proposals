# Clarification Log — OSAC-7158

## Status

- Rounds completed: 3
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

## Remaining Gaps

None. Exact date/time formatting, error-to-message mapping, and any API data needed to support the UI are design details, not open user requirements.
