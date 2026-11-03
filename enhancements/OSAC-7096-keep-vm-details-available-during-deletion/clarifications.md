# Clarification Log — OSAC-7097

## Status

- Rounds completed: 1
- Open gaps: 0
- Exit criteria met: Yes
- Requirements source: [OSAC-7096](https://redhat.atlassian.net/browse/OSAC-7096), captured in `01-requirements.md`
- Workflow context: [OSAC-7097](https://redhat.atlassian.net/browse/OSAC-7097)
- PRD tracking task: [OSAC-7098](https://redhat.atlassian.net/browse/OSAC-7098)

## Source Handling

The user chose to continue from the saved Jira requirements rather than retry the optional networking-reference check. This round does not rely on unverified local networking designs or assert that the reported current behavior has been checked against code or a deployed system.

The user reviewed the decision summary and approved saving this log and finishing clarification. Drafting was not authorized by that approval.

## Round 1 — Details During Deletion and After Failure

### R1.Q1: Visible VM Details

Which VM details must remain visible while deletion is running or has failed?

#### Answer

Existing details when available. Keep the information already shown by VM details when available. Mark potentially stale values as last known and missing values as unavailable.

#### Impact

Describe continued access to the existing details view and its available information. Make the treatment of stale and missing values explicit in the requirements and acceptance criteria.

#### Decision (D1)

While deletion is in progress or has failed, show the information already shown by VM details when available. Identify potentially stale values as **last known** and missing values as **unavailable**.

---

### R1.Q2: Read-Only Behavior After Failure

If deletion fails and the VM still exists, should configuration, power, networking, and console actions remain disabled?

#### Answer

Initial answer: Keep read-only. Keep details accessible, but leave these actions disabled after failure too. No new retry or cancel controls.

User-approved revision during PRD review: Allow authorized users to attempt a console connection during deletion and after a deletion failure. If the console accepts the connection, they can use it. OSAC warns that deletion may interrupt the session. Console access does not delay or cancel cleanup.

#### Impact

Keep configuration, power, and networking controls disabled during deletion and after failure. Replace the source's and the initial D2 decision's console prohibition with the user-approved exception, and include the console capability in the user stories. Successful connection determines whether the console can be used; no advance guarantee of availability is required.

#### Decision (D2)

During deletion and after a deletion failure, the VM's configuration, power, and networking controls remain disabled. Authorized users may attempt a console connection under existing console permissions. If the console accepts the connection, they can use it. OSAC warns that deletion may interrupt the session. Console access does not delay or cancel cleanup. New deletion retry and cancel controls remain outside the source-defined scope.

---

### R1.Q3: Safe Failure Explanation

What should the deletion failure explanation tell the user, given that provider job IDs, links, logs, and raw errors must not be exposed?

#### Answer

Safe cause when known. Show a plain-language cause when safely available. Otherwise explain that deletion could not finish and the reason is unavailable.

#### Impact

Define observable behavior for both an available safe cause and an unavailable cause. Preserve the source's prohibition on exposing provider job IDs, links, logs, or raw errors.

#### Decision (D3)

On deletion failure, show a safe, plain-language cause when one is available. Otherwise explain that deletion could not finish and the reason is unavailable. Do not expose provider job IDs, links, logs, or raw errors.

## Exit Criteria Review

- **Functional requirements are enumerable:** The source requirements, as revised by D1–D3 and the user-approved D2 exception, define details access, information availability, deletion status, failure explanations, disabled configuration/power/networking controls, console connection attempts, successful-removal navigation, and tenant access controls.
- **Target users are identified:** Tenant Admin and Tenant User, as specified by the source. The source identifies Cloud Provider Admin and Cloud Infrastructure Admin as unaffected.
- **Scope boundaries are clear:** The VMaaS 0.5 feature keeps existing VM details accessible during deletion and after failure, with console access when a connection succeeds. The four source-defined exclusions remain unchanged.
- **No unresolved contradictions remain:** D2 records the user's explicit override of the console prohibition while retaining the other control restrictions.
- **Key assumptions are confirmed:** D1 resolves the meaning of available details, D2 resolves the control restrictions and console exception, and D3 resolves failure explanation behavior.
- **Non-functional requirements are enumerable:** Preserve existing tenant and console access controls; do not expose provider identifiers, links, logs, or raw errors; distinguish stale and unavailable information; keep configuration, power, and networking controls disabled; warn that deletion may interrupt console access; do not delay or cancel cleanup for a console session.
- **Dependencies are identified:** The affected capabilities are the existing VM details view and its available information, deletion-state visibility, console connectivity, and tenant access controls. A console can be used only if the connection succeeds. Showing a specific cause depends on a safe cause being available, with the D3 fallback required otherwise. No new external dependency is identified.

## Remaining Gaps

None blocking PRD drafting. Current implementation behavior and networking-design freshness remain unverified; these are evidence limits, not additional product requirements or changes to scope.
