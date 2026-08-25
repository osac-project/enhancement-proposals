# Per-Service Enablement (CaaS/VMaaS/BMaaS/MaaS)

| Field       | Value   |
|-------------|---------|
| Author(s)   | Haim Tayrie |
| Jira        | https://redhat.atlassian.net/browse/OSAC-3046 |
| Date        | 2026-08-25 |

## Problem Statement

OSAC deploys all services (CaaS, VMaaS, BMaaS, MaaS) unconditionally. Deployments that only need a subset — for example, a CaaS-only site — still run controllers, expose APIs, and carry the compliance burden for services they do not use. This increases operational complexity and widens the compliance surface area: a deployment that does not provision bare metal hosts must still satisfy BMaaS-specific attestation controls (UEFI Secure Boot, TPM 2.0) during audits. Both the MOC 2.0 program and the Telenor engagement require the ability to tailor deployments to only the services they need. [Jira: OSAC-3046, comment by @Bradford Nichols]

## In Scope

- Cloud Provider Admins select which services are active at installation time via Helm values.
- Disabled services are fully excluded: no running controllers, no registered APIs, no UI surfaces.
- Post-installation enablement of additional services via `helm upgrade`.
- The Capabilities endpoint advertises which services are currently enabled so that clients (CLI, UI) can adapt. [Clarify: R1.Q5]
- When a service is disabled, other enabled services cannot provision resources that depend on it (e.g., disabling BMaaS blocks bare-metal-backed CaaS cluster host types). [Clarify: R1.Q1]

## Out of Scope

- Post-installation **disablement** of services and the lifecycle of existing resources when a service is turned off — unanswered in requirements and deferred pending stakeholder input. [Clarify: R1.Q2]
- Compliance scanning and reporting scoped to enabled services — this feature provides the enablement signal; actual scan-profile scoping is the responsibility of OSAC-3029 (ACM Compliance Policies) and OSAC-3031 (OpenSCAP/Insights Compliance). [Clarify: R1.Q5]
- Disabling shared infrastructure (networking, storage, tenants, identity, events). These remain always-on regardless of which services are enabled. [Clarify: R1.Q3]
- Alignment between the Enclave wizard "experiences" mechanism and per-service enablement — requires cross-team discussion to determine whether experiences drive the Helm enablement values, are replaced by them, or run alongside them. [Clarify: R2.Q2]

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to choose which services (CaaS, VMaaS, BMaaS, MaaS) are active when I install OSAC so that my deployment only runs what I need and my compliance surface matches my actual service offering.

- As a Cloud Provider Admin, I want to enable additional services after installation so that I can expand my deployment as demand grows without reinstalling.

- As a Cloud Provider Admin, I want to see which services are currently enabled so that I can verify my deployment configuration.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want the platform to block provisioning of resources that depend on a disabled service (e.g., bare-metal host types when BMaaS is disabled) so that the compliance boundary is enforced at the infrastructure level, not just the API level. [Clarify: R1.Q1]

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want the catalog, UI, and CLI to only show resource types for enabled services so that I am not confused by options that would fail if I tried to use them.

## Dependencies

- **OSAC-3018 (HIPAA Compliance Readiness) and OSAC-2889 (EU Sovereignty & Compliance Readiness):** Both outcomes depend on per-service enablement to scope compliance to enabled services only. This feature provides the enablement signal they consume.
- **OSAC-3029 (ACM Compliance Policies) and OSAC-3031 (OpenSCAP/Insights Compliance):** Responsible for scoping compliance scanning to enabled services, consuming the enablement configuration this feature provides. [Clarify: R1.Q5]

---

## Provenance

Authored: draft @ prd 0.8.0 - 7efcedb, workspace main @ 4bfc214

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.8.0","ai_workflows":"7efcedb","source_repo":"4bfc214","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
