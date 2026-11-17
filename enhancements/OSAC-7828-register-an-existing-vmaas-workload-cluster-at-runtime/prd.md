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
instead of the provider's operational workflow.

## In Scope

- For OSAC 0.6, runtime registration configures the installation's single
  VMaaS workload cluster through the shared WorkloadCluster registration
  capability, including clusters without ACM. A separate VMaaS registration
  API is not introduced. Existing AI workload-cluster registration behavior
  is preserved; the one-target restriction applies only to VMaaS. [User]
- Cloud Provider Admins can register the target, inspect its details and
  readiness, and update its credentials through the UI and applicable
  API/CLI workflows. Registration administration requires provider-admin
  authorization and is not available to tenant roles.
- Registration verifies cluster identity, connectivity, required access and
  existing VMaaS prerequisites. Admins can distinguish a usable registration
  from a failed one and receive actionable errors identifying what needs
  correction; registration does not provision or prepare the cluster.
- Credential updates take effect for the same registered cluster without
  re-registration or rerunning the installer. Credentials are not disclosed
  in read responses, UI details or logs.
- After successful registration, cluster identity cannot change: removal
  and replacement are rejected even when the cluster contains no
  OSAC-managed resources. Updating credentials to point to another cluster,
  or using another API path, cannot bypass this restriction. [User]
- Supported VM creation and lifecycle operations, status reporting and
  console access use the runtime-configured target, without requiring
  tenants to configure or select a cluster. Missing, invalid or unavailable
  registration produces an explicit error or status, never silent fallback
  to the management cluster.
- Runtime registration replaces installation-time VMaaS target configuration
  as the authoritative configuration. Existing installations have a
  documented, tested transition that avoids conflicting target configuration
  and preserves existing OSAC-managed resources without removing or
  recreating them. Registration and credential changes do not require
  rerunning the installer. [User]
- User and operator documentation covers registration, readiness failures,
  same-cluster credential updates, the removal/replacement restriction and
  the transition for existing installations. The registration, authorization,
  identity-protection and VM-continuity outcomes above are covered by
  automated acceptance verification.

## Out of Scope

- Provisioning workload clusters or installing OpenShift Virtualization.
- Adopting or migrating pre-existing VMs.
- Multiple VMaaS targets, workload-cluster placement decisions, scheduling,
  placement policies, tenant-placement changes or load balancing.
- Cluster deregistration, replacement, draining or cluster-migration
  workflows. Removal and replacement after successful registration are
  rejected, not deferred operations that this feature enables.
- Networking or storage expansion beyond the integration needed to preserve
  existing supported VMaaS behavior.

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to register an existing OpenShift
  Virtualization cluster at runtime through the UI or API/CLI, including
  when the cluster is not registered with ACM, so that VMaaS configuration
  does not require rerunning installation.
- As a Cloud Provider Admin, I want to inspect registration details,
  readiness and actionable validation errors so that I can determine
  whether the target is usable and correct access or prerequisite problems.
- As a Cloud Provider Admin, I want to update credentials for the same
  registered cluster so that I can maintain access without removing or
  replacing the target.
- As a Cloud Provider Admin, I want removal, replacement and credential
  retargeting attempts to be rejected after successful registration, even
  for an empty cluster, so that the registered cluster's identity remains
  protected throughout its use. [User]
- As a Cloud Provider Admin, I want to transition an installation's
  existing VMaaS target configuration to runtime registration without
  removing or recreating OSAC-managed resources so that existing workloads
  retain their management continuity.

### Cloud Infrastructure Admin

This persona is not directly affected: no new cluster-provisioning or
infrastructure-preparation workflow is introduced.

### Tenant Admin

This persona is not directly affected: no registration-administration,
cluster-selection or placement controls are introduced.

### Tenant User

- As a Tenant User, I want supported VM creation and lifecycle operations,
  status and console access to use the registered workload cluster without
  selecting or configuring a cluster so that I can manage VMs through the
  existing self-service workflow.
- As a Tenant User, I want an explicit error or status when registration is
  missing, invalid or unavailable so that I can recognize why a VM operation
  cannot proceed rather than unknowingly using the management cluster.

## Assumptions

- The provider supplies an existing OpenShift Virtualization cluster and
  credentials with the required access. Its actual connectivity, access and
  VMaaS prerequisites remain subject to registration validation; the
  existence of a usable target is not a provisioning guarantee.

## Dependencies

- The shared WorkloadCluster registration capability associated with
  OSAC-6488 provides the common registration surface. This feature extends
  that capability for non-ACM VMaaS targets while retaining AI registration;
  it does not depend on ACM registration of the VMaaS cluster.
- Existing VMaaS lifecycle, status and console capabilities depend on the
  registered target remaining usable. Their existing supported behavior
  must remain available through runtime configuration and the documented
  transition from installation-time configuration.

---

## Provenance

Authored: draft @ prd 0.11.5 - unknown (not a git repository), workspace main @ d786d4924

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"unknown (not a git repository)","source_repo":"d786d4924","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
