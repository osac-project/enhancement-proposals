# Clarification Log — OSAC-7307

## Status

- Rounds completed: 2
- Open gaps: 0
- Exit criteria met: Yes
- Scope note: after PR review the PRD is limited to networking. D5 and D6
  record the corrected position; the answers and impact statements below are
  reconciled with that scope.
- Superseded: D2, D3, and D8 are replaced by D10 (tenant-scoped placement).
  D11 corrects D10's assignment persona, D12 records delivery sequencing, D13
  removes the installation-time placement mode, and D14 removes the runtime
  cluster registration target.

## Round 1 — scope, placement, and defaults

### R1.Q1: Versioning irrelevant to the PRD

The Feature lists "expanding the declared Dev Preview / 0.4 support scope" as
out of scope but carries fix version 0.5, while the PRD task has no fix version.
Asked whether a split management/workload topology belongs to 0.5 and what the
0.4 statement means.

#### Answer

Version does not matter here; this is management work. The PRD should define
what is needed regardless of versioning.

#### Impact

The PRD will not declare a target milestone or argue about 0.4 versus 0.5. It
describes the required capability, supported topology, prerequisites, and
limitations; release assignment stays with the release process and the Feature.

#### Decision (D1)

The PRD is version-agnostic. Do not scope the document to a release number or
treat the Feature's 0.4/0.5 wording as a constraint on requirements.

---

### R1.Q2: Placement is an OSAC-wide configuration

The Feature asks the Cloud Infrastructure Admin for explicit
management-versus-workload placement but does not say whether placement is a
deployment-wide setting or a per-VM or per-tenant choice.

#### Answer

Placement is an OSAC-wide configuration. If a workload cluster is used, all VMs
are deployed on the workload cluster; otherwise all VMs are deployed on the
hub/management cluster. Those two options are the only supported ones for now.

#### Impact

The PRD states a single deployment-level placement mode with exactly two
supported outcomes. It promises no per-VM, per-tenant, or per-project placement
control, and no mixed deployments where some VMs run on the hub and others on a
workload cluster.

#### Decision (D2)

Exactly two supported topologies: all VMs on the hub, or all VMs on one
workload cluster. Placement is configured deployment-wide by the provider side,
not selected by tenants.

---

### R1.Q3: Tenant networks are not duplicated per cluster

Asked whether tenant defaults and VirtualNetwork/Subnet/SecurityGroup resources
must work on both clusters, or whether each cluster needs its own networking
resources.

#### Answer

Answered by the placement decision: there cannot be more than one cluster
spawning tenant VMs.

#### Impact

The PRD treats tenant networking resources as belonging to the single
VM-hosting cluster's networking context rather than duplicated per cluster. It
does not need cross-cluster network semantics, per-cluster network sets, or
rules for using one tenant network simultaneously on the hub and a workload
cluster.

#### Decision (D3)

One VM-hosting cluster per deployment. Tenant VirtualNetwork, Subnet,
SecurityGroup, tenant defaults, and VM attachments are defined against that
cluster's networking; no cross-cluster or per-cluster network duplication is
required.

---

### R1.Q4: Networking-enabled is the supported path; disabled is a CI path

OSAC-7297 shows that with provider networking disabled the tenant namespace is
missing on the workload cluster, and that work is assigned separately. Asked
whether this PRD should treat that path as supported, a known limitation, or
leave it out.

#### Answer

Users only use this with networking. Disabling networking is mainly for CI
testing. The flow with networking must be supported, and skipping networking
parts when networking is disabled must also work for CI purposes. This should
not add complexity: run the networking parts conditionally, as is already done
today for the hub cluster.

#### Impact

The PRD states two behaviors for a workload-cluster deployment: the supported
user-facing path with provider networking enabled, and a provider-networking-
disabled path whose purpose is CI testing, where networking steps are skipped
rather than replaced by another mechanism. The disabled path must not degrade
VM provisioning or introduce new deployment modes.

#### Decision (D4)

Both paths are in scope. Networking-enabled is the user-facing supported path;
networking-disabled is CI-only and behaves like the existing hub behavior, with
networking steps conditionally skipped rather than newly invented.

---

### R1.Q5: Workload-cluster capability baseline follows the hub

Asked which tenant-visible VM capabilities must work on a workload cluster.

#### Answer

Whatever VM capabilities are supported on the hub/management cluster today is
the guideline for what must be supported on the workload cluster.

#### Impact

The hub capability set is the reference for what already runs against a remote
cluster. Most non-networking capabilities work there today, so the increment this
PRD must deliver is the networking path with provider networking enabled; the
PRD does not re-scope storage, metering, console, power, or GPU behavior.

---

## Round 2 — parity baseline, prerequisites, addressing, visibility

Question numbering is normalized here; the fabric and external-access questions
were both sent under the same label.

### R2.Q1: Hub capability set is the reference

Confirmed the baseline for non-networking capabilities on a workload cluster.

#### Answer

Same as the hub cluster: existing behavior applies, with nothing added or
dropped by this document.

#### Impact

The hub capability set is the reference, not the deliverable. The PRD requires
the networking path on a workload cluster and leaves existing non-networking
capabilities untouched: creation from catalog item or template, instance type,
disk image, disks and storage tiers, SSH key, user data, run strategy, restart,
delete, console, metering, and GPU continue to depend on existing behavior.

#### Decision (D5)

The PRD scope is limited to networking on the workload cluster. Non-networking
capabilities that already work against a remote cluster are unchanged and are
not claimed as new capability by this document.

---

### R2.Q2: Kubernetes Manager acts on the workload cluster

Asked whether the fabric manager remains registered on the hub and operates
against the workload cluster, or must be registered or pointed per cluster.

#### Answer

Correction after review: the fabric manager never talks to a cluster; its tasks
call the fabric controller's API. The component that must act on the workload
cluster is OSAC's Kubernetes Manager, which owns the per-VirtualNetwork
namespace, the EVPN ClusterUserDefinedNetwork, and the NetworkPolicies. The
fabric manager keeps its existing tasks and stays registered once.

#### Impact

The PRD requires the Kubernetes Manager to configure tenant networking on the
workload cluster, while fabric manager registration and credentials stay as they
are. Per-cluster fabric registration and per-cluster manager copies are not
required.

#### Decision (D6)

OSAC's Kubernetes Manager configures tenant networking on the workload cluster.
The fabric manager is unchanged and stays registered once.

---

### R2.Q3: External access keeps hub semantics

Asked whether ExternalIP, ExternalIPAttachment, and NATGateway keep their
tenant-visible semantics for a VM on the workload cluster.

#### Answer

If external access exists for VMs on the hub cluster then it is in scope, and it
should work as it does on the hub. ExternalIPs are normally allocated from the
pool, so it will be the same here.

#### Impact

The PRD requires external access parity for remote VMs, including pool-based
allocation, attachment, and the existing rules about when an attachment may
target a VM. No new addressing model is introduced for the workload cluster.

#### Decision (D7)

External access behavior for VMs on the workload cluster matches the hub:
pool-allocated ExternalIPs, ExternalIPAttachment, and NATGateway semantics
unchanged.

---

### R2.Q4: Placement is not user-visible

Asked whether a tenant or administrator must be able to see which cluster a VM
runs on.

#### Answer

UI is out of scope, so it will be internal only until further notice.

#### Impact

The PRD does not require a placement field, indicator, or filter in the API,
CLI, or console. Placement stays deployment configuration that the provider side
knows about; tenants interact with VMs exactly as they do on the hub.

#### Decision (D8)

Placement is internal administration information, not tenant-visible product
surface. No new user-facing placement control or display is required.

---

### R2.Q5: Acceptance criteria cover product outcomes only

The Feature's Definition of Done mixes process, design, test, and documentation
outcomes with product behavior. Asked whether the PRD's acceptance criteria
should list only observable product outcomes or also restate the design, test,
and documentation items.

#### Answer

Option A: product outcomes only.

#### Impact

The PRD acceptance criteria are PM-verifiable scenarios about running VMs on a
workload cluster. The Definition of Done items for design, placement-distinguishing
tests, and deployment documentation are recorded as dependencies and delivery
obligations of the design and implementation work, not restated as PRD
acceptance criteria.

#### Decision (D9)

PRD acceptance criteria describe observable product behavior only. Design,
test-engineering, and documentation deliverables from the Feature's Definition
of Done are referenced as dependencies rather than converted into acceptance
criteria.

---

## Round 3 — multiple workload clusters and tenant-scoped placement

### R3.Q1: Support more than one workload cluster

PR review asked whether the PRD supports more than one workload cluster, because
OSAC deployments can use several workload clusters and placement is already the
main blocker for the workload-cluster feature.

#### Answer

The clusters available to a deployment are the hub cluster plus the workload
clusters connected to it at installation. The Cloud Provider Admin assigns one
of those clusters at tenant creation, and all of that tenant's VMs run on it.
Changing a tenant's cluster after creation is not supported. Networking must not
become a second blocker, so the PRD follows this placement model instead of
defining it.

#### Impact

Placement is no longer deployment-wide: one cluster per tenant is chosen at
tenant creation from the clusters available to the deployment. Tenant
networking objects live on the tenant's cluster and are not duplicated across
clusters. Per-VM and per-project placement, placement changes, and moving a
tenant between clusters are out of scope.

#### Decision (D10)

Supersedes D2, D3, and D8. The Cloud Provider Admin assigns one cluster per
tenant at tenant creation; all of a tenant's VMs and tenant networking stay on
that cluster. The PRD depends on the placement foundation that records the
tenant's cluster and does not deliver it. The persona was corrected in Round 4
(D11), and the installation-time placement mode was removed in Round 5 (D13).

---

## Round 4 — cluster-assignment persona and delivery sequencing

### R4.Q1: Cluster assignment is provider-side, not tenant-side

PR review pointed out that choosing the workload cluster cannot be a Tenant
Admin action, because tenants are not supposed to know anything about the
OpenShift clusters behind OSAC. Asked which persona assigns the cluster.

#### Answer

The Cloud Provider Admin, not the Tenant Admin. It is provider-side tenant
onboarding work, like quotas and catalog access.

#### Impact

The PRD assigns the per-tenant cluster choice to the Cloud Provider Admin and
states that tenants neither choose nor see the hosting cluster. The Tenant Admin
stories keep only tenant networking behavior and isolation; no Tenant Admin or
Tenant User story mentions a cluster selection.

#### Decision (D11)

The Cloud Provider Admin assigns the workload cluster when a tenant is created.
The cluster is provider-side administration and stays invisible to tenants. This
corrects D10 and R3.Q1.

### R4.Q2: First implementation targets the existing separate-cluster install

PR review noted that adding workload clusters at runtime is not implemented yet,
and asked that the first implementation focus on the existing way to install
OSAC with a separate workload cluster from the start.

#### Answer

Agreed. The first increment is the existing installation-time configuration,
where one workload cluster is supplied at installation. Runtime cluster
registration is not a target of this PRD.

#### Impact

The PRD adds a Delivery Sequencing section: the first increment adds provider
networking to the existing separate-workload-cluster installation, where the
clusters available to the deployment are fixed at installation. Workload
clusters are created in advance. The placement foundation is recorded as a
dependency that is not implemented yet.

#### Decision (D12)

The first implementation delivers provider networking on the installation-time
separate-workload-cluster configuration. Per-tenant cluster assignment follows
with the placement foundation, and its ordering is agreed before implementation
starts.

---

## Round 5 — no installation-time placement mode

### R5.Q1: Drop the deployment-level management-versus-workload choice

Review asked to remove the requirement that the deployment choose at
installation whether it hosts VMs on the management cluster or on workload
clusters, and instead let the Cloud Provider Admin choose the tenant's cluster
regardless of whether it is the management cluster or a workload cluster.

#### Answer

Agreed. There is no deployment-level placement mode. The Cloud Provider Admin
assigns one cluster per tenant from the clusters the deployment was installed
with, and that cluster can be the management cluster or a workload cluster.

#### Impact

The PRD drops the installation-time choice from In Scope and from the Cloud
Infrastructure Admin stories. The placement bullet states that one deployment
can host different tenants on different clusters, and the Cloud Infrastructure
Admin keeps only the workload-cluster preparation and prerequisite stories. The
EVPN host setup statement now applies per tenant: a deployment that also hosts
tenant VMs on the management cluster keeps that setup. The Kubernetes Manager
statement refers to the tenant's assigned cluster rather than a workload
cluster.

#### Decision (D13)

There is no installation-time placement mode. The Cloud Provider Admin assigns
each tenant one cluster, which can be the management cluster or a workload
cluster the deployment was installed with, and one deployment can mix tenants
across clusters. This supersedes the installation-time mode in D2 and D10 and
the deployment-wide description in D12.

---

## Round 6 — workload clusters exist in advance

### R6.Q1: Remove the runtime cluster registration target

Review asked to remove the target of adding workload clusters at runtime and to
refer only to workload clusters created in advance with existing capabilities.

#### Answer

Agreed. Workload clusters are created in advance and connected at installation.
Registering additional clusters at runtime is not part of this PRD.

#### Impact

In Scope refers to the workload clusters the deployment was installed with,
Assumptions and Dependencies describe clusters created in advance, and Out of
Scope lists adding workload clusters to a running deployment. Delivery
Sequencing describes the existing installation-time shape without a follow-on
runtime increment.

#### Decision (D14)

Workload clusters are created in advance and connected at installation using
existing capabilities. Adding workload clusters to a running deployment is out
of scope. This supersedes the runtime-registration target in R3.Q1, D10, D12,
and D13.

---

## Remaining Gaps

None.
