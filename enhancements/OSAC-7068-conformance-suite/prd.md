---
title: osac-conformance-suite
authors:
  - dmanor@redhat.com
creation-date: 2026-10-22
last-updated: 2026-11-03
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-7068
see-also:
  - OSAC Conformance Suite Design: /enhancements/OSAC-7068-conformance-suite/design.md
  - Network Manager Integration Contract: /enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md
  - Per-Service Enablement: /enhancements/OSAC-3046-per-service-enablement/design.md
replaces:
  - N/A
superseded-by:
  - N/A
---

# OSAC Conformance Suite

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor (dmanor@redhat.com) |
| Jira        | https://redhat.atlassian.net/browse/OSAC-7068 |
| Date        | 2026-10-22 |

## Problem Statement

OSAC lets providers plug their own components into an installation, and the network Fabric Manager is the first such component. Today there is no shared way for a provider to show that a component works with a given OSAC release: the installation guides give manual checks, each team checks something different, and a resource can report READY while traffic still does not flow. Without a common suite, every area that becomes pluggable would build its own runner, configuration, test tenant, cleanup and report, and a provider could mistake a successful task for a working component.

## In Scope

- One conformance image per OSAC release, tagged with that release. Every supported release publishes one, the suite refuses to run against an installation on a different release, and it replaces the networking-only suite image so no release ships both. [Clarify: R2.Q2]
- Two layers of checks: component tests that run a provider's component the way OSAC runs it, against the provider's backend and in isolation from the running installation; and profiles that exercise end-to-end scenarios through OSAC's APIs in the installation.
- A shared test tenant per run, with cleanup even after a failure and a list of anything the suite could not delete.
- Test selection from what the installation has: the suite runs only the tests that apply to the enabled services and registered components. Tests that do not apply are reported as skipped and do not affect the verdict. [Clarify: R1.Q5]
- One configuration file: settings common to all areas, plus one section per area. A configuration error stops the run before any test runs, names the problem and writes no report.
- A verdict the user can act on: results per test, per profile and per component, plus a named-check verdict that states what was checked, the rule it applies and the remedy. A machine-readable report, per-test evidence and a diagnostics bundle of the installation's state and logs accompany it. The installation passes when no check fails, and a component is conformant for a release when every blocking component test that applies passes and every required profile passes. [Clarify: R1.Q3] [Clarify: R2.Q3]
- An area plug-in model, with networking as the first area.
- OSAC runs the component tests in CI against reference components for each release and runs the component tests and the profiles in its E2E lab, so every test is proven before it is used in the field.
- The report is self-reported and attached to the component's design; a passing report covers one OSAC release and one component version, and a provider reruns the suite for each new component version or execution environment image.
- Live output modelled on OpenShift's conformance tests, with commands to list the tests a run would select, rerun a subset of them, and keep resources for debugging. A subset run is reported as focused and never as a conformance verdict.
- Secret values never appear in output, logs, evidence, the report or diagnostics.
- The installation guide ends with running the suite, and the Fabric Manager guide and its go-live checklist point to it, replacing their manual verification steps.

## Out of Scope

- The tests, profiles, configuration keys, configuration errors and component identity of any area. Each area defines them in its own design; networking is defined in the Network Manager Integration Contract.
- Upgrade and air-gapped modes. [Clarify: R2.Q1]
- Independent verification or certification of reports, and enforcement of any area's support condition. [Clarify: R2.Q4]
- Running the suite from the OSAC console, API or CLI; the suite is a standalone image.
- Any change to OSAC's own APIs, CRDs or controllers.

## User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to run the conformance suite of a release against my installation after installing it, so that I know the installation works for the variant I deployed.
- As a Cloud Infrastructure Admin, I want to rerun the suite after a configuration change, so that I know the installation still works.
- As a Cloud Infrastructure Admin, I want the suite to run only the tests that apply to the services I enabled and the components I registered, so that a VM-only installation is not failed by bare-metal or cluster tests.
- As a Cloud Infrastructure Admin, I want a verdict made of named checks, each stating its rule and how to fix a failure, so that I know exactly what is wrong and what to do.
- As a Cloud Infrastructure Admin, I want the suite to create and delete its own test tenant, so that I can run it on an environment other tenants share.
- As a Cloud Infrastructure Admin, I want the report to list anything the suite could not delete, so that I know what to clean up after a failure or an interrupted run.
- As a Cloud Infrastructure Admin, I want to list the tests a run would select and rerun only the failed ones, so that iterating after a fix does not take a full run.
- As a Cloud Infrastructure Admin, I want to keep the test tenant and its resources after a failure, so that I can debug without rerunning the whole suite.
- As a Cloud Infrastructure Admin, I want to see each step as it runs, what a failing test expected versus what it observed, and a machine-readable report with per-test evidence and a diagnostics bundle, so that I can fix the installation without asking OSAC for help.
- As a Cloud Infrastructure Admin, I want the suite to read the installation's own configuration, so that I do not maintain a second copy of it.
- As a Cloud Infrastructure Admin, I want the suite to report whether the component I integrated is conformant with a release, so that I can prove it works before going live and when asking for support.
- As a Cloud Infrastructure Admin, I want component tests that run the component I integrated the way OSAC runs it, against its backend, so that a failure points at that component and not at OSAC.
- As a Cloud Infrastructure Admin, I want tests that are not yet proven in OSAC CI to be marked informing, so that they are reported without failing the run until someone decides to make them blocking. [Clarify: R1.Q4]
- As a Cloud Infrastructure Admin, I want the suite to redact the component's secrets from everything it prints or stores, so that I can share a report safely.

## Assumptions

- The Cloud Infrastructure Admin can run a lab with the target OSAC release and the components they integrated installed, for each release and component version they validate.
- The Cloud Infrastructure Admin owns and operates the pre-production lab used as the onboarding gate.
- End-to-end tests that are selected for conformance read their settings from the conformance configuration and need no CI-only access.

## Dependencies

- **Per-service enablement ([OSAC-3046](/enhancements/OSAC-3046-per-service-enablement/design.md)):** reports which services are enabled, which drives test selection.
- **Network Manager Integration Contract ([OSAC-1433](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md)):** defines the networking area, including its tests, profiles, configuration and support condition.
- **OSAC release process:** publishes the conformance image with each release.
- **OSAC CI and E2E lab:** run the component tests against reference components and the profiles against real components.
- **Diagnostics gather roles ([osac-test-infra](https://github.com/osac-project/osac-test-infra)):** provide the installation state and logs for a run's diagnostics bundle.

## Provenance

Authored: draft @ prd 0.11.5 - b369da0 (dirty), workspace main @ f0a8211 (dirty)
Final: manual-edit [manual] @ 2026-11-03, based on PR #410 head f2e49a0
Phases: draft, manual-edit

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"b369da0 (dirty)","source_repo":"f0a8211 (dirty)","source_repo_branch":"main","commits_behind_main":null,"commits_ahead_main":null,"main_ref":"main","phases":["draft","manual-edit"],"authoring_modes":["skill","manual"],"context_changed":false,"origin_untracked":false} -->
