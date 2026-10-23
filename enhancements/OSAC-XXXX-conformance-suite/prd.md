---
title: osac-conformance-suite
authors:
  - dmanor@redhat.com
creation-date: 2026-10-22
last-updated: 2026-10-22
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-XXXX
see-also:
  - OSAC Conformance Suite Design: /enhancements/OSAC-XXXX-conformance-suite/design.md
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
| Jira        | https://redhat.atlassian.net/browse/OSAC-XXXX |
| Date        | 2026-10-22 |

## Problem Statement

OSAC lets providers plug their own components into OSAC; the first is the network Fabric Manager. Today the only way to prove such a component works is a networking-only conformance suite defined inside the networking contract, so OSAC has no shared way for a provider to prove that any component works with an OSAC release. Without one, each new pluggable area would need its own suite, configuration, and report, and a provider could mistake a successful task for a working component. [User]

## In Scope

- One conformance suite per OSAC release, published as a container image tagged with that release, which a Cloud Infrastructure Admin runs on their own machine with podman. It replaces the networking-only suite image. [User]
- Two layers. Component tests run the provider's component exactly as OSAC runs it, against the provider's backend, without OSAC. Profiles are end-to-end scenarios through OSAC's normal APIs in a lab that runs the release.
- Profiles run in a test Tenant that the suite creates and deletes, so the lab can be shared with other Tenants. Cleanup runs even after a failure, and the suite lists anything it could not delete. A timeout, including on delete, fails the test, and each timeout can be overridden.
- The suite runs only what applies to the lab: the services enabled there and the components registered there. Anything else is reported as skipped and does not block the result.
- One configuration file holds the settings shared by all areas and one section per area. The suite reads everything else from the lab, and stops with a configuration error only when a required run cannot run. [User]
- A result per test (pass, fail, or skip), per profile, and per component, an overall result (conformant or in progress), and the list of leftovers, both in a machine-readable report and in JUnit XML. A component is conformant for a release when every component test that applies passes and every profile its area requires passes.
- Areas plug in: each area defines its own component tests, profiles and when each is required, configuration section, component identity in the report, configuration errors, and support condition. Networking is the first area.
- OSAC runs the component tests in its CI for each release with reference components, and runs the profiles in its E2E lab.
- The report is self-reported and attached to the component's design. Each area states its own support condition, which OSAC does not enforce. Providers run the suite for every OSAC release and every new version of their component.
- Verbose output, modelled on the OpenShift conformance tests (`openshift-tests`): every test has a readable name, every step a test takes is shown as it happens, a failure says what was expected and what was observed and keeps the evidence, and a summary closes the run. A Cloud Infrastructure Admin can list the tests a run would select, and rerun one test or a subset by name. [User]

## Out of Scope

- The tests, profiles, configuration keys, configuration errors, component identity, and support condition of any area. Each area defines them in its own design; for networking, the [Network Manager Integration Contract](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md), including its follow-up network-behavior tests.
- Independent verification or certification of reports, and enforcement of an area's support condition by OSAC.
- Running the suite from the OSAC console, API, or CLI; the suite is a standalone image the Cloud Infrastructure Admin runs outside OSAC.

## User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to run the conformance suite of an OSAC release against my component in my lab, so that I can show my component works with that release before I go live.
- As a Cloud Infrastructure Admin, I want the component tests to run my component the way OSAC runs it, against my backend but without OSAC, so that a component test failure points to my component and not to OSAC.
- As a Cloud Infrastructure Admin, I want to run the profiles in a lab that other Tenants share, so that I do not need a dedicated lab for conformance.
- As a Cloud Infrastructure Admin, I want the suite to require only the tests and profiles for the services I enable and the components I register, so that a provider that offers only VMs is not blocked by bare-metal or cluster tests.
- As a Cloud Infrastructure Admin, I want to write one configuration file with only what the suite cannot read from my lab, so that I do not keep two copies of my lab's settings in sync.
- As a Cloud Infrastructure Admin, I want a report with pass, fail, or skip per test, a result per component, and the resources the suite could not delete, so that I know whether my component is conformant and what to clean up by hand.
- As a Cloud Infrastructure Admin, I want to see every step the suite takes and, when a test fails, what it expected, what it observed, and the evidence, so that I can fix my component without asking OSAC for help.
- As a Cloud Infrastructure Admin, I want to list the tests a run would select and rerun only the failing ones, so that I do not wait for the whole suite after each fix.

## Assumptions

- Providers can run a lab with the target OSAC release and their component installed for each release and component version they validate.

## Dependencies

- **Per-service enablement ([OSAC-3046](/enhancements/OSAC-3046-per-service-enablement/design.md)):** the Capabilities endpoint reports which services are enabled in the lab; the suite uses it to decide which runs apply.
- **Network Manager Integration Contract ([OSAC-1433](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md)):** the first area. It moves its suite-wide rules here and keeps its Fabric Manager tests, profiles, configuration keys, errors, identity, and support condition, linking to this proposal. Both land in the same OSAC release, so no release ships the networking-only suite and this one together.
- **OSAC release process:** publishes the suite image with each release.
- **OSAC CI and E2E lab:** run the component tests with reference components for each release, and the profiles with real components.

---

## Provenance

Authored: draft @ prd 0.11.5 - e2b0d87, workspace provider-networking-docs @ d3d48c727
Final: revise [manual] @ prd 0.11.5 - e2b0d87, workspace provider-networking-docs @ 28ffb6868

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"e2b0d87","source_repo":"28ffb6868","source_repo_branch":"provider-networking-docs","commits_behind_main":0,"commits_ahead_main":1,"main_ref":"main","phases":["draft","revise","revise"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":false} -->
