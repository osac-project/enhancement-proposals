# Clarification Log — OSAC-3976

## Status

- Rounds completed: 5
- Current round: Complete
- Open gaps: 0
- Exit criteria met: Yes

## Round 1 — Status behavior and user views

### R1.Q1: Overall status and component states

The ticket says the overall status represents whether all four minimal requirements have been met, but it does not define what counts as “onboarded” in user-facing terms. Must all four components be successful? Which overall states should users see when components are pending, partially complete, failed, or unavailable?

#### Answer

You asked what “use a different aggregation rule” meant. It means how the four component outcomes combine into the overall tenant indicator. The rule is clarified in R2.Q1; precedence when a pending component coexists with a failed or unavailable one remains open in R3.Q1.

#### Impact

The PRD can define the all-success, pending, and failed/unavailable states. It still needs the precedence rule for mixed component states.

---

### R1.Q2: Cloud Infrastructure Admin view

The Cloud Infrastructure Admin story says the status should distinguish onboarding failures from broader readiness concerns, but does not specify what this persona sees. Should Cloud Infrastructure Admins see per-component details like Cloud Provider Admins, or only the tenant-level indicator?

#### Answer

Cloud Infrastructure Admin status should reflect only the minimal onboarding requirements and show per-component detail. The exact difference from Cloud Provider Admin detail remains open in R3.Q2.

#### Impact

The PRD can specify per-component detail for the minimal onboarding requirements, but cannot yet distinguish exactly what Cloud Infrastructure Admins see from what Cloud Provider Admins see.

---

### R1.Q3: Role-based visibility across interfaces

The ticket says the API and CLI expose status and describes different detail levels for Cloud Provider Admins versus Tenant Admins and Tenant Users. Should the same role-based visibility apply in the API and CLI? What should each role be able to see there?

#### Answer

Use the same role-based visibility in every interface (see R2.Q3).

#### Impact

The PRD can specify consistent role-based visibility across UI, API, and CLI. The precise detail for Cloud Infrastructure Admins remains open in R3.Q2.

---

### R1.Q4: Failure details and user actions

When a component fails, what should the Cloud Provider Admin be able to learn or do from the status view—for example, see the failure reason, get guidance, or request a retry? Automatic remediation is listed as out of scope.

#### Answer

Show the failure reason only. Do not allow a user-triggered retry.

#### Impact

The PRD should state that the status shows the failure reason and offers no user-triggered retry. Automatic remediation remains out of scope.

#### Decision (D1)

Show the failure reason only; do not provide a user-triggered retry.

---

### R1.Q5: Freshness and retry progress

The ticket says status updates automatically when components complete or fail. How quickly should users expect the status to reflect changes? After a failed component is retried, should the status show progress toward success or remain failed until completion?

#### Answer

If possible, show progress until success; if the component fails, show failure.

#### Impact

The PRD should show progress during a retry and show failure if the component fails. The expected update delay is specified as immediate in R2.Q4; the progress display is refined in D3 below.

#### Decision (D2)

During a retry, show available progress toward success; show failure if the component fails.

This decision is refined by D3, which defines the user-visible progress level and terminal result.

---

## Round 2 — Status rules and access details

### R2.Q1: Overall aggregation and states

To make the tenant indicator testable, should it show “Onboarded” only when all four components succeed? How should it appear when one or more components are pending, failed, or unavailable?

#### Answer

The tenant should show “Onboarded” only when all four components have succeeded. A pending component should show “Pending” or “In progress”; a failed or unavailable component should show “Failed.”

#### Impact

The PRD can specify the all-success, pending/in-progress, and failed/unavailable states. Precedence when components have mixed states remains open.

#### Decision (D4)

Show “On-Boarded” only when all four components succeed. Show “Pending” or “In progress” when a component is pending. Show “Failed” when a component has failed or is unavailable.

---

### R2.Q2: Cloud Infrastructure Admin detail level

I understand that Cloud Infrastructure Admins should see more than one tenant-level indicator and that the status should cover only networking, storage, encryption keys, and the breakglass account. Should this be a per-component breakdown of those four requirements?

#### Answer

Cloud Infrastructure Admins should see per-component detail for the minimal onboarding requirements, at a level between Tenant Admin/User and Cloud Provider Admin.

#### Impact

The PRD can specify per-component detail for Cloud Infrastructure Admins, but the exact distinction from Cloud Provider Admin detail remains open.

#### Decision (D5)

Cloud Infrastructure Admins see per-component details for the minimal onboarding requirements, with more detail than Tenant Admins/Users and less than Cloud Provider Admins.

---

### R2.Q3: Role access through API and CLI

Should API and CLI show the same role-based information as the UI—for example, Cloud Provider Admins see component details while Tenant Admins and Tenant Users see one aggregate indicator? What should Cloud Infrastructure Admins see through those interfaces?

#### Answer

Use the same role-based visibility in every interface.

#### Impact

The PRD should apply the same role-based status visibility rules to UI, API, and CLI. The precise Cloud Infrastructure Admin detail remains open in R3.Q2.

#### Decision (D6)

Apply the same role-based visibility rules in every interface.

---

### R2.Q4: Status freshness

How soon should the displayed status reflect a component completing or failing—for example, immediately, within a few minutes, or on a slower schedule?

#### Answer

Immediately.

#### Impact

The PRD should state that status reflects component completion or failure immediately.

#### Decision (D7)

Reflect component completion or failure immediately.

---

### R2.Q5: Meaning of progress during retry

When a component is retried, is a simple “In progress” state until success or failure sufficient, or should users see more detailed progress? If progress is unavailable, what should they see while waiting?

#### Answer

During progress, show only “In progress”; detailed progress is not needed. Show the result as “Succeeded” or “Failed.”

#### Impact

The PRD can specify a simple in-progress state followed by a visible success or failure result.

#### Decision (D3)

Show only “In progress” while a component is progressing; do not show detailed progress. Show “Succeeded” or “Failed” as the result.

---

## Round 3 — Mixed statuses and administrator detail

### R3.Q1: Precedence for mixed component states

If one component is pending while another has failed or is unavailable, which overall status should the tenant show: “Pending/In progress” or “Failed”?

#### Answer

If any component is failed, the overall status is “Failed,” even if another component is pending. If none have failed and one or more are in progress, the overall status is “In progress.” The overall status is successful/onboarded only when all four components have succeeded.

#### Impact

The PRD can specify deterministic overall status precedence for mixed component states.

#### Decision (D8)

Overall status precedence is: “Failed” if any component failed or is unavailable; otherwise “In progress” if any component is pending/in progress; otherwise “On-Boarded” when all four components succeeded.

---

### R3.Q2: Difference between administrator detail levels

Cloud Infrastructure Admins should see per-component status, with less detail than Cloud Provider Admins. Is the intended difference that Cloud Infrastructure Admins see each component’s status, while Cloud Provider Admins also see the failure reason? If not, what detail should differ?

#### Answer

Cloud Infrastructure Admins see only per-component details for the minimal onboarding requirements, so they can distinguish onboarding failures from broader readiness or monitoring concerns. Cloud Provider Admins see the full detail breakdown.

#### Impact

The PRD can distinguish the Cloud Infrastructure Admin view, limited to minimal onboarding requirements, from the full Cloud Provider Admin breakdown.

#### Decision (D9)

Cloud Infrastructure Admins see per-component detail limited to the minimal onboarding requirements. Cloud Provider Admins see the full detail breakdown.

---

## Round 4 — Status freshness threshold

### R4.Q1: Meaning of immediate updates

You said status should reflect component completion or failure immediately. What maximum delay should count as “immediately” for users—for example, a specific number of seconds or minutes? If no numeric threshold is needed, say so.

#### Answer

The status should always update without delay when a component status changes. No numeric threshold is requested.

#### Impact

The PRD can state that status reflects component changes without intentional delay.

#### Decision (D10)

Update the displayed status as soon as a component status changes, without intentional delay.

---

## Round 5 — Tenant-facing status labels

### R5.Q1: Success label

When all four components have succeeded, should the overall status display “Success” or “On-Boarded”?

#### Answer

Display “On-Boarded,” not “Success.”

#### Impact

The PRD should use “On-Boarded” as the user-facing label for successful onboarding.

#### Decision (D11)

When all four components succeed, display “On-Boarded,” not “Success.”

---

### R5.Q2: Tenant Admin and Tenant User indicator

Should Tenant Admins and Tenant Users see the detailed “In progress” and “Failed” states, or only a binary onboarding indicator?

#### Answer

Tenant Admins and Tenant Users should see only a “Not On-Boarded” / “On-Boarded” indicator.

#### Impact

For these personas, pending, failed, and unavailable component states appear as “Not On-Boarded”; individual component details and separate progress/failure labels are not shown.

#### Decision (D12)

Tenant Admins and Tenant Users see only the binary “Not On-Boarded” / “On-Boarded” indicator.

---

## Remaining Gaps

None.
