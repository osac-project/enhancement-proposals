# OSAC Version Information Display

| Field       | Value   |
|-------------|---------|
| Author(s)   | CrystalChun |
| Jira        | https://redhat.atlassian.net/browse/OSAC-4730 |
| Date        | 2026-11-20 |

## Problem Statement

OSAC users and operators currently cannot identify the deployed versions of
the platform components they are using from the OSAC UI or a single CLI
inventory. They must rely on command-line access, deployment artifacts, or
support assistance to establish deployment context, which makes troubleshooting,
upgrade verification, and bug reporting slower. The platform already provides
service enablement information, but it does not provide a corresponding
version view that reflects the components actually deployed in a given
environment. Without this capability, users cannot reliably determine which
software versions are relevant to an issue or confirm that an expected update
has taken effect.

## In Scope

- A deployment-derived inventory that includes fulfillment-service and any
  other enabled, deployed, versioned OSAC components. Absent or unversioned
  optional components are omitted, while an unavailable required
  fulfillment-service version is clearly indicated. The complete initial
  inventory and inclusion rules are defined in the [Component and service-tier
  inventory](clarifications.md#component-and-service-tier-inventory).
  [Clarify: R2.Q1, R2.Q5]
- Surface-specific version views: the UI displays the fulfillment-service
  version and its own version only when the UI is deployed and versioned; a
  deployed UI without a version omits its version row. The CLI always displays
  its embedded local CLI version and the fulfillment-service version; if no
  server URL is configured or the backend is unreachable, the
  fulfillment-service version is shown as unavailable. The
  CLI displays the UI version only when the UI is deployed and versioned; a
  deployed UI without a version is omitted. The UI does not display the CLI
  version. [Clarify: R3.Q1, R2.Q5]
- Public access to fulfillment-service, UI, and CLI version information, with
  other component versions visible only to users authorized to view protected
  component versions. Unauthorized callers must not receive protected rows,
  and the access rule applies consistently across the UI, CLI, and other
  clients. Role grants follow OSAC-3058. [Clarify: R2.Q4, R3.Q1, R3.Q2, D7]
- Unauthenticated clients that request the fulfillment-service version must
  provide a server URL and be able to reach the fulfillment-service backend.
  Without a configured URL or a reachable backend, the fulfillment-service
  version is unavailable; the CLI still displays its embedded local version.
  [User, Clarify: R2.Q5]
- Version values update automatically when new component versions are deployed,
  without manual user configuration, and users see each component's released
  version without needing to interpret or transform the value.
  [Jira: OSAC-4730, Clarify: R1.Q5]

## Out of Scope

- Deployment timestamps or other installation-time operational metadata.
  [Clarify: R2.Q5]
- Version compatibility validation, version history or changelog display, and
  version-based feature gating. [Jira: OSAC-4730, reviewed PR 249]
- Separate user-facing version rows for shared fulfillment APIs, CRD packages,
  or Helm packaging when they are not independently deployed and versioned
  runtime components. [Clarify: R2.Q1]

## User Stories

### Cloud Provider Admin / Cloud Infrastructure Admin

- As a Cloud Provider Admin or Cloud Infrastructure Admin, I want to view the
  deployed component versions that I am authorized to see so that I can verify
  the platform release state and investigate deployment or upgrade issues.

- As a Cloud Provider Admin or Cloud Infrastructure Admin, I want the version
  inventory to reflect enabled and deployed service tiers so that absent
  services are not presented as if they were part of the deployment.

- As a Cloud Provider Admin or Cloud Infrastructure Admin, I want to retrieve
  the same authorized version inventory through the CLI by providing the
  fulfillment-service server URL so that I can use it in operational checks
  and support workflows.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want to view the public and
  permission-authorized OSAC versions available to me so that I can include
  accurate deployment context when reporting problems or requesting support.

- As a Tenant Admin or Tenant User, I want unavailable required version
  information to be clearly identified so that I can distinguish missing
  deployment data from an absent optional service.

## Assumptions

- The version source and exposure mechanism for each deployed component beyond
  fulfillment-service remains to be established through a codebase and build
  pipeline assessment. [User]

## Dependencies

- **OSAC-3046 — Per-Service Enablement:** Provides the deployment’s enabled
  service-tier state. The version inventory must align with the services and
  dependent components actually enabled and deployed.
- **OSAC-3058 — Configurable Named Roles:** Provides the capability-based
  authorization model used to protect component versions from unauthorized
  users; role grants for the appropriate version-view permission remain
  governed by OSAC-3058.
- **Component build and release pipelines:** Each deployed component included
  in the inventory must publish a usable version value, and new deployments
  must update the value without manual user configuration.
- **Fulfillment-service connectivity:** A configured server URL and reachable
  fulfillment-service backend allow the CLI to retrieve the service version;
  otherwise that version is unavailable while the local CLI version remains
  available.
- **Authorization:** Protected component versions are visible only to users
  with the appropriate permission. Unauthorized users must not see them
  through the UI, CLI, or another client, and role grants follow OSAC-3058.

---

## Provenance

Authored: revise @ prd 0.11.5 - 7653641, workspace enable-system-idp @ be1aa9fb8
Final: revise @ prd 0.11.5 - 7653641, workspace enable-system-idp @ c99003aa0 (dirty)

> Context changed between revise and revise.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"7653641","source_repo":"c99003aa0 (dirty)","source_repo_branch":"enable-system-idp","commits_behind_main":0,"commits_ahead_main":1,"main_ref":"main","phases":["revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":true} -->
