# Register an existing VMaaS workload cluster at runtime

| Field | Value |
|-------|-------|
| Author(s) | OSAC-VMaaS (owning team; draft for human review) |
| Jira | [OSAC-7828](https://redhat.atlassian.net/browse/OSAC-7828) |
| Date | 2026-11-17 |

## Problem Statement

Today, the VMaaS workload-cluster connection and credentials are configured
during OSAC installation, rather than through runtime administration. Cloud
Provider Admins need to register an existing OpenShift Virtualization cluster
after installation, including a cluster that is not registered with Advanced
Cluster Management (ACM), without rerunning the installer. Without this
capability, configuring the single VMaaS target remains tied to installation
instead of the provider's operational workflow. Runtime registration lets
providers use a cluster dedicated to and optimized for tenant VM workloads.

## In Scope

- For OSAC 0.6, runtime registration designates one existing OpenShift
  Virtualization cluster as the installation's VMaaS target and supplies
  access credentials, including when the cluster is not registered with
  ACM. The one-target restriction applies only to VMaaS and does not limit
  AI registrations.
- The install-time VMaaS workload-cluster configuration option is removed.
  Registration and updates to VMaaS workload-cluster configuration are
  supported only through the workload-cluster API. The Cloud Provider Admin
  UI and CLI submit these operations through that API rather than providing
  separate configuration paths.
- Registration administration is available through the Cloud Provider Admin
  UI and applicable API/CLI workflows. It requires provider-admin
  authorization and is not available to tenant roles.
- Registration verifies cluster identity, connectivity, required access and
  existing VMaaS prerequisites. Admins can distinguish a usable registration
  from a failed one and receive actionable errors identifying what needs
  correction; registration does not provision or prepare the cluster.
- Credential updates take effect for the same registered cluster without
  re-registration or rerunning the installer. Credentials are not disclosed
  in read responses, UI details or logs.
- In this first increment, removal and replacement are rejected after
  successful registration, even when the cluster contains no OSAC-managed
  resources. Credential changes must not silently switch the target to a
  different cluster; neither credential updates nor another API path can
  bypass the removal/replacement restriction.
- Supported VM creation and lifecycle operations, status reporting and
  console access use the runtime-configured target, without requiring
  tenants to know about, configure or select a cluster. Missing, invalid or
  unavailable registration produces an explicit admin-visible error or
  status, never silent fallback to the management cluster.
- User and operator documentation covers registration, readiness failures,
  same-cluster credential updates and this increment's removal/replacement
  restriction. The registration, authorization, same-target credential-update
  and supported VM-behavior outcomes above are covered by automated
  acceptance verification.

## Out of Scope

This PRD covers a deliberately limited initial registration increment.
Safe removal and replacement of registered VMaaS workload clusters are
product requirements that must be supported before GA, but their
implementation is deferred to subsequent lifecycle work so this first
delivery stays focused on simpler, single-target registration. This
increment rejects removal and replacement after successful registration,
including for an empty cluster.

- Provisioning workload clusters or installing OpenShift Virtualization.
- Adopting or migrating pre-existing VMs.
- Multiple VMaaS targets, workload-cluster placement decisions, scheduling,
  placement policies, tenant-placement changes or load balancing.
- Implementation of cluster deregistration, replacement, draining, and
  cluster-migration workflows in this initial increment.
- Installing or reconfiguring the workload cluster's networking or storage
  infrastructure. Registration assumes a prepared cluster.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to register an existing OpenShift
  Virtualization cluster at runtime through the UI or API/CLI, including
  when the cluster is not registered with ACM, so that VMs can run on a
  cluster dedicated to and optimized for tenant workloads.
- As a Cloud Provider Admin, I want to inspect registration details,
  readiness and actionable validation errors so that I can determine
  whether the target is usable and correct access or prerequisite problems.
- As a Cloud Provider Admin, I want to update credentials for the same
  registered cluster so that I can maintain valid cluster access without
  silently switching VM operations to a different target.

### Cloud Infrastructure Admin

This persona is not directly affected: no new cluster-provisioning or
infrastructure-preparation workflow is introduced.

### Tenant Admin

This persona is not directly affected: no registration-administration,
cluster-selection or placement controls are introduced.

### Tenant User

This persona is not directly affected: registration is a provider concern.
Existing VM workflows do not require tenant awareness of the underlying
cluster.

## Assumptions

- The provider supplies a prepared OpenShift Virtualization cluster and
  credentials with the required access. Its actual connectivity, access and
  VMaaS prerequisites remain subject to registration validation; the
  existence of a usable target is not a provisioning guarantee.

## Dependencies

- Existing VMaaS lifecycle, status and console capabilities depend on the
  registered target remaining usable. Their existing supported behavior
  must remain available through runtime registration.

---

## Provenance

Authored: respond @ prd 0.11.5 - unknown (not a git repository), workspace main @ d786d4924
Phases: draft, respond, respond, respond

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"unknown (not a git repository)","source_repo":"d786d4924","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","respond","respond","respond"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
