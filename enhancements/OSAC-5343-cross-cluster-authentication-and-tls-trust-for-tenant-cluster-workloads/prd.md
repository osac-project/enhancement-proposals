# Cross-cluster authentication and TLS trust for tenant cluster workloads

| Field | Value |
|---|---|
| Author(s) | Daniel Erez |
| Jira | [OSAC-5343](https://redhat.atlassian.net/browse/OSAC-5343) |
| Date | 2026-09-07 |

## Problem Statement

In a multi-cluster OSAC deployment, workloads on a workload or tenant cluster cannot reliably authenticate to the fulfillment service using credentials issued by their own Kubernetes cluster. The resulting failure blocks the intended management-cluster and workload-cluster topology. Tenant-cluster workloads also cannot establish a trusted TLS connection until they trust the management cluster's certificate authority. Without this capability, consumers such as the CSI driver cannot securely make required fulfillment-service calls across cluster boundaries.

## In Scope

- Consumption of tenant-scoped Keycloak service identities, reused by the tenant's clusters, for cross-cluster fulfillment-service access. [Clarify: R1.Q1] [Clarify: R1.Q2]
- Secure client-credentials and TLS connectivity for operator and tenant-cluster consumers using credentials supplied by the tenant-identity lifecycle. [Clarify: R1.Q2]
- Automatic trust setup for newly provisioned tenant clusters. [Clarify: R1.Q4]
- Verified end-to-end TLS-authenticated gRPC connectivity from a supported tenant-cluster workload to fulfillment service. [Clarify: R1.Q3]

## Out of Scope

- CSI-driver deployment, CSI credential-Secret propagation, StorageClass configuration, and vendor-specific volume-provisioning behavior, which are addressed by related follow-up work. [Clarify: R1.Q3]

## User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want OSAC components on separate clusters to use a trusted service identity when communicating with fulfillment service so that the supported multi-cluster deployment topology works securely.

- As a Cloud Infrastructure Admin, I want tenant clusters to receive the certificate trust required for fulfillment-service access during provisioning so that tenant workloads can establish secure connections without manual trust-store setup.

- As a Cloud Infrastructure Admin, I want trust setup to reconcile automatically for newly provisioned tenant clusters so that supported workloads can connect securely without manual repair. [Clarify: R1.Q4]

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want workloads on my tenant cluster to communicate securely with fulfillment service so that tenant-cluster services such as storage can use the capabilities assigned to the tenant.

## Assumptions

- To be determined — whether UI, CLI, Kubernetes readiness status, and troubleshooting support are in scope for this Feature. [Clarify: R1.Q5]

## Dependencies

- **Keycloak:** Provides the tenant-scoped trusted service identities and credentials needed for cross-cluster authentication.
- **Certificate management on tenant clusters:** Provides the certificate-management capability required to establish fulfillment-service TLS trust.
- **OSAC-3291:** Deploys the tenant-cluster CSI driver and propagates its credential Secret; it consumes the trust and authentication model established by this Feature. [Clarify: R1.Q3]
- **OSAC-4197:** Owns creation, rotation, and synchronization of the tenant-specific Keycloak client credentials. [Clarify: R1.Q2] [Clarify: R1.Q4]

---

## Provenance

Authored: draft @ prd 0.9.0 - 562b610, workspace main @ ad9ec2979
Final: revise @ prd 0.9.0 - 562b610, workspace prd/OSAC-1644 @ ad9ec2979

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.9.0","ai_workflows":"562b610","source_repo":"ad9ec2979","source_repo_branch":"prd/OSAC-1644","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
