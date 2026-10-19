# Import HUB-Registered Clusters for AI Workloads

| Field       | Value |
|-------------|-------|
| Author(s)   | Eran Cohen |
| Jira        | [OSAC-6488](https://redhat.atlassian.net/browse/OSAC-6488) |
| Date        | 2026-10-19 |

## Problem Statement

Cloud providers may already manage AI Grid clusters through ACM, but OSAC
cannot represent them as MaaS workload clusters. Their capacity therefore
cannot participate in OSAC AI workload flows within OSAC's tenant model for
tenant roles, model access, quotas, and token usage tracking. Providers must
provision separate clusters or operate AI capacity outside OSAC's tenant-aware
MaaS flows, limiting reuse of existing infrastructure and fragmenting tenant
controls. [User]

## In Scope

- Cloud Provider Admins can import clusters registered with an ACM hub cluster
  (HUB) through the OSAC UI, CLI, and API. Each imported cluster is represented
  as an OSAC workload cluster exposed through the OSAC API. [User]
- Cloud Provider Admins can see import outcome through the UI, CLI, and API.
- Imported workload-cluster details are visible only to Cloud Provider Admins.
  Tenant Admins and Tenant Users access AI capacity through OSAC workload
  flows without seeing or managing the underlying cluster. [User]
- Import failures show the cause. The import flow does not require an
  additional recovery action. [Clarify: R1.Q4]
- OSAC AI workloads can use workload clusters while preserving tenant
  isolation. [User]

## Out of Scope

- Importing clusters that are not registered with the HUB.
- Using imported clusters for VMaaS, CaaS, or BMaaS workloads, or adding their
  workload scheduling and placement logic.
- Reporting AI workload readiness or displaying observed AI Grid role and
  policy state for imported clusters is deferred to a later enhancement.
- Defining or managing AI Grid policy placement through OSAC, including
  creating or changing ACM/Praxis policies or cluster labels, or managing
  customer GitOps workflows for that configuration.
- Disconnecting imported clusters from OSAC and removing their workload-cluster
  representations is deferred to a later enhancement. If introduced later,
  disconnecting rejects requests while workloads are assigned to an AI Grid,
  unlinks only the OSAC representation, and does not change the cluster's HUB
  registration. [Clarify: R1.Q3] [User]
- Provisioning new workload clusters or general lifecycle management beyond
  import.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to import an ACM HUB-registered cluster
  through the OSAC UI, CLI, or API so its existing provider-managed capacity
  can serve OSAC AI workloads without provisioning a separate cluster.
- As a Cloud Provider Admin, I want to see import outcome through the OSAC UI,
  CLI, and API so I can verify whether the cluster was imported.
- As a Cloud Provider Admin, I want imported cluster details to remain visible
  only to Cloud Provider Admins so tenant access to OSAC AI workloads does not
  expose provider cluster configuration.

### Tenant Admin / Tenant User

- As a Tenant Admin or Tenant User, I want OSAC AI workloads to use imported
  workload clusters while preserving tenant isolation so my organization can
  consume provider-managed AI capacity without seeing or managing the
  underlying cluster.

## Dependencies

- **HUB registration:** A target cluster must already be registered with the
  HUB before it can be imported.
- **MaaS AI workload flows:** Workload flows must be able to use imported
  workload clusters while preserving tenant isolation. [User]

## Open Questions

### 1. Tenant allocation

Are imported workload clusters shared provider capacity available to multiple
tenants, or assigned to one tenant? [Clarify: R1.Q2; User]

- **Owner:** OSAC-MaaS
- **Impact:** Determines how imported capacity is allocated while preserving
  tenant isolation.

---

## Provenance

Authored: draft @ prd 0.11.3 - d9d66a5, workspace feat/OSAC-6344-keycloak-mcp-scope @ 16dcc4e78
Final: revise @ prd 0.11.3 - d9d66a5, workspace main @ 002f4abfd

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.3","ai_workflows":"d9d66a5","source_repo":"002f4abfd","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","respond","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
