# TLS Trust for Fulfillment-Service Clients Across Management and Tenant Clusters

| Field | Value |
|---|---|
| Author(s) | Daniel Erez |
| Jira | [OSAC-1644](https://redhat.atlassian.net/browse/OSAC-1644) |
| Date | 2026-09-15 |

## Problem Statement

In a multi-cluster OSAC deployment, fulfillment-service clients run on both management and tenant clusters. The OSAC management installation provides the certificate authority (CA) that signs the fulfillment-service certificate, but tenant-cluster clients do not have the CA certificate needed to trust it, and some existing clients bypass TLS verification. Without verified TLS trust, OSAC cannot securely support fulfillment-service connections across CaaS, VMaaS, and BMaaS workflows.

## In Scope

- Every OSAC-deployed component that connects to fulfillment service, including components on tenant clusters, trusts the management CA and verifies the fulfillment-service certificate and hostname.
- Newly provisioned tenant clusters receive the management CA certificate needed by their OSAC-managed fulfillment-service clients without manual trust-store setup.
- Production fulfillment-service connections do not use TLS-verification bypasses.
- Explicit, isolated TLS-verification overrides for test environments when required.
- Validation of TLS trust for CaaS, VMaaS, BMaaS, AAP publishing, metering, tenant CSI, and installer Helm hooks in supported integration and E2E environments.

## Out of Scope

- Tenant-scoped Keycloak service-account APIs and lifecycle, including OSAC-5137.
- Auditing or remediating Kubernetes service-account tokens used by fulfillment-service clients.
- CSI identity and credential lifecycle, tenant-specific CSI deployment, credential provisioning, StorageClass configuration, and vendor-specific volume provisioning.
- Mutual TLS.
- Cert-manager rollout as an independent feature outcome.
- External certificate authorities, including Let's Encrypt.

## User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want OSAC-managed components to verify fulfillment service before connecting so that the platform does not rely on insecure TLS configuration.

- As a Cloud Infrastructure Admin, I want newly provisioned tenant clusters to receive the required fulfillment-service trust automatically so that dependent OSAC services work without manual certificate configuration.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want OSAC-managed services on my tenant cluster to communicate securely with fulfillment service so that I can use my provisioned cluster capabilities without manual certificate-trust setup.

## Assumptions

N/A

## Dependencies

- **Management certificate management:** The OSAC installer installs cert-manager and creates the management-cluster CA that signs the fulfillment-service certificate. Supported integration and E2E environments provide an equivalent CA setup.
- **Tenant-cluster provisioning:** The supported provisioning path provides the certificate-management prerequisite and must make the management CA available to tenant-cluster clients.
- **Fulfillment-service client owners:** The owners of the in-scope client classes validate the required TLS trust behavior.

---

## Provenance

Authored: draft @ prd 0.9.0 - 562b610, workspace main @ ad9ec2979
Final: revise @ prd 0.11.1 - 3f9c3b9, workspace main @ 81f908385

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.1","ai_workflows":"3f9c3b9","source_repo":"81f908385","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
