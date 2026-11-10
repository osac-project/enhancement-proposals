# Clarifications - OSAC-7068

Questions raised while clarifying the PRD, and the decisions the PRD reflects. Each `[Clarify: <ID>]` marker in [prd.md](prd.md) points to an entry here.

| ID | Question | Decision | Reflected in |
|---|---|---|---|
| R1.Q3 | What makes an installation pass, and how does a user act on a failure? | The verdict is a list of named checks, each stating its rule and its remedy. The installation passes when no check fails. A component is conformant when every blocking component test that applies passes and every required profile passes. | In Scope, verdict item; design Result rules |
| R1.Q4 | How are tests that are not yet proven in OSAC CI handled? | A test is `blocking` or `informing` as its area declares. A test may start `informing` until a human owner promotes it to `blocking`; an area may declare its tests blocking from the start, as networking does. An informing failure is reported and does not fail the run. | In Scope; user stories; design Policy |
| R1.Q5 | How does the suite decide which tests to run? | Selection is declared: every conformance test carries selector labels, the configuration names the selectors the lab has (the generic set always applies), and the plan is their union. The plan is written out and printed, so the set can be reviewed, kept, and rerun. | In Scope, test selection item; design Lab selectors and the plan |
| R2.Q1 | Are upgrade and air-gapped modes in scope? | No. The suite runs against an installed release; upgrade and air-gapped modes are out of scope. | Out of Scope |
| R2.Q2 | Does the new suite image replace the networking-only image, or ship alongside it? | One image per OSAC release, tagged with that release. It replaces the networking-only image, and no release ships both. | In Scope, first item |
| R2.Q3 | What is the conformance rule for a component? | Every blocking component test in the plan passes and every required profile passes; otherwise the component is `in progress`. | In Scope, verdict item; design Result rules |
| R2.Q4 | Does OSAC verify or certify reports, or enforce an area's support condition? | No. The report is self-reported, and each area states its support condition without OSAC enforcing it. | Out of Scope; design Policy |
