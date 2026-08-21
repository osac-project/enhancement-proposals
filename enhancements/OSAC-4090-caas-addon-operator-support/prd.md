# CaaS Add-On Operator Support

| Field     | Value                                                      |
|-----------|------------------------------------------------------------|
| Author(s) | Trey West                                                  |
| Jira      | https://redhat.atlassian.net/browse/OSAC-4090              |
| Date      | 2026-08-18                                                 |

## Problem Statement

CaaS clusters provisioned through OSAC arrive without any specialized software
installed. Tenants who need purpose-built cluster configurations — such as an
NVIDIA AI cluster requiring GPU, network, and driver operators — must install
those operators manually after the cluster is delivered. This is error-prone,
time-consuming, and undermines the self-service value of the catalog experience.
Without automated operator installation, OSAC cannot offer catalog items that
are ready for specific workloads out of the box.

## In Scope

- A new **AddOnOperator** resource representing a platform-supported operator;
  Cloud Provider Admins control which add-on operators are visible to their
  tenants
- Add-on operators can be attached to CaaS catalog items and are visible to
  Tenant Users before they order a cluster
- Add-on operators can also be specified directly when ordering a cluster,
  independently of a catalog item
- When operators are specified both in a catalog item and directly at order
  time, the resulting cluster installs all operators from both sources
- Cluster orders are validated at order time and rejected immediately with a
  descriptive error if they request operators that are:
  - **incompatible** — two or more requested operators are declared mutually
    exclusive and cannot be installed on the same cluster
  - **version-constrained** — a requested operator is not supported on the
    cluster's OpenShift version
  - **unavailable** — a requested operator has not been made available to the
    tenant by the Cloud Provider Admin
- When an add-on operator declares a dependency on another add-on operator,
  that dependency is automatically included in the cluster's operator set and
  validated together with the rest of the order at order time
- Operators are installed as part of cluster provisioning; if any fail, the
  cluster is delivered flagged as degraded and transitions to healthy once all
  operators are successfully installed

## Out of Scope

- Operator lifecycle management after initial installation (upgrades, removal)
- Operator health monitoring or alerting on provisioned clusters
- Governance or validation of operators outside the defined add-on operators —
  operators installed as side-effects of a requested operator are not validated
  against availability or compatibility and may appear on a cluster without the
  Cloud Provider Admin having explicitly offered them
- Non-CaaS services (VMaaS, BMaaS)

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to control which add-on operators are
  available to my tenants so that I can ensure only platform-validated operators
  are offered for cluster provisioning.
- As a Cloud Provider Admin, I want to see the installation status of the
  add-on operators I offer across provisioned clusters, including error details
  for any that failed, so that I can identify platform-level operators that are
  consistently failing and maintain the quality of the catalog.

### Tenant Admin

- As a Tenant Admin, I want to attach add-on operators to CaaS catalog items
  so that I can offer purpose-built cluster configurations to my users.
- As a Tenant Admin, I want to see the installation status of add-on operators
  on clusters provisioned from my catalog items, including error details for any
  that failed, so that I can ensure the configurations I offer are working
  correctly.

### Tenant User

- As a Tenant User, I want to see which add-on operators are included in a
  catalog item before I order a cluster so that I can choose the right
  configuration for my workload.
- As a Tenant User, I want to specify add-on operators when ordering a cluster
  so that my cluster arrives ready for use without manual operator installation.
- As a Tenant User, I want to see which add-on operators were installed on my
  cluster after provisioning, including installation status and error details
  for any that failed, so that I know my cluster is ready and can troubleshoot
  if something went wrong.

## Dependencies

- **Automated operator installation on provisioned clusters:** Clusters
  provisioned via Hosted Control Planes must support automated operator
  installation for supported cluster versions. This capability must be confirmed
  for each supported version.

---

## Provenance

Authored: draft @ prd 0.8.0 - 7efcedb, workspace main @ 0e651b2

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.8.0","ai_workflows":"7efcedb","source_repo":"0e651b2","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
