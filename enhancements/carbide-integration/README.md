---
title: carbide-integration
authors:
  - Trey West
creation-date: 2026-03-09
last-updated: 2026-03-09
tracking-link: # link to the tracking ticket (for example: Github issue) that corresponds to this enhancement
  - None
see-also:
  - enhancements/bare-metal-fulfillment/README.md
replaces:
  - None
superseded-by:
  - None
---

# Carbide Integration for Cluster as a Service


## Summary

This proposal describes integrating O-SAC with **NVIDIA Carbide** (Bare Metal Manager) to deliver cluster-as-a-service. The initial focus is using Carbide as the underlying multi-tenant bare metal layer: Carbide provides bare metal as a service (provisioning, lifecycle, power, console, networking), while O-SAC continues to own fulfillment, cluster orchestration, and tenant-facing APIs. Together they enable tenants to consume OpenShift on hardware managed and isolated by Carbide.

Today, cluster-as-a-service in O-SAC is backed only by ESI; this proposal adds Carbide as a second bare metal backend for the same capability.

This integration is an interim approach. In the long term, the bare metal portion of cluster fulfillment is expected to be backed by the [bare-metal-fulfillment](../bare-metal-fulfillment/README.md) feature, which will support multiple backends (e.g., OpenStack/ESI, Carbide, and others). This proposal unblocks cluster-as-a-service on Carbide today and informs the patterns needed when Carbide is added as a bare-metal-fulfillment provider later.

## Motivation

### What is Carbide?

**Carbide** (NVIDIA Bare Metal Manager) is an API-driven, zero-touch bare metal lifecycle platform. It comprises a **REST** layer (cloud/management API, Temporal workflows, multi-tenant sites and orgs, CLI) and a **Core** layer (site-local gRPC: PXE, DHCP, DNS, hardware health, SSH console, DPU agents). Carbide handles machine ingestion, provisioning, wiping, and release; hardware inventory and health; BMC/power control; IPAM and DNS for managed machines; and DPU-enforced isolation. It does **not** build or manage software clusters (e.g. Kubernetes or SLURM) or configure tenant software—its boundary ends once a machine is booted into a user-defined host OS.

### Why integrate Carbide with O-SAC?

O-SAC needs a robust, multi-tenant bare metal layer for cluster fulfillment. Carbide provides that as a purpose-built bare metal-as-a-service offering with strong isolation and automation. Integrating the two lets O-SAC's fulfillment service and operator drive cluster requests while Carbide supplies and manages the underlying hosts and networking so providers can offer cluster-as-a-service without duplicating bare metal lifecycle or multi-tenancy.

### User Stories

* As a **provider**, I want to use Carbide as a bare metal backend for O-SAC, so that I can easily manage hosts and networks available to tenants.
* As a **provider**, I want O-SAC to use Carbide as an inventory source, so that managed hosts are readily available for cluster fulfillment.
* As a **provider**, I want to scale bare metal across multiple sites or regions, so that I can serve tenants in different locations.
* As a **tenant**, I want to request an OpenShift cluster through O-SAC on bare metal matching a hardware profile, so that I can run GPU or other HW-specific workloads.
* As a **tenant**, I want my cluster’s hosts provisioned and isolated by Carbide, so that I get secure, dedicated capacity without managing the infra.
* As an **operator**, I want the bare metal backend to be observable, so that I can detect failures and remediate at scale.

### Goals

* Providers can offer cluster-as-a-service using Carbide as the bare metal layer.
* O-SAC cluster fulfillment consumes bare metal capacity from Carbide (inventory, provisioning, isolation) so that requested clusters are provisioned on Carbide-managed hosts.
* Tenants can request clusters matching specific hardware profiles through O-SAC.
* Support basic tenant overlay network configuration.
* The bare metal backend is observable so operators can detect failures and remediate at scale.

### Non-Goals

* **Standalone bare metal fulfillment** (e.g. HostPools without a cluster) — the initial focus is cluster-as-a-service; adding Carbide as a provider for bare-metal-fulfillment may be added at a later time.
* **Datacenter underlay management** — physical underlay network and fabric remain outside O-SAC and Carbide’s scope per Carbide’s design.
* **Cluster software installation** — OpenShift (or other) install and day-2 operations remain the responsibility of existing O-SAC cluster fulfillment; this proposal is about wiring Carbide as the inventory and lifecycle source for that flow.

## Proposal

Cluster-as-a-service through Carbide will utilize the existing model O-SAC uses for cluster-as-a-service (as with ESI today): ClusterTemplates reference template roles that create cluster infrastructure, then agents are selected, attached to a tenant network, attached to a tenant cluster, and approved.

- **ClusterTemplates and Carbide InstanceTypes:** Instance type selection will use matching by name: the Carbide instance type name will match the hostclass name from the node request, and the ClusterTemplate’s site parameter will identify the site. Template parameters will also include the Carbide resources the tenant wants for their cluster (VPC, prefix/subnet, SSH key group, etc.) so that the right resources are used or created when provisioning.

- **osac-aap roles and backend selection:** Carbide will be supported by adding roles analogous to massopencloud.esi and extending `cluster_infra` with a variable to select the backend (ESI or Carbide). Parity may require updates to `cluster_infra`, `manage_agents`, and `external_access`; in cluster fulfillment, only the networking roles are ESI-specific. See *Role placement and flow* under Implementation Details.

### Workflow Description

#### Administrator steps
  1. Creates a shared network (or ensures one exists) for booting instances as agents
  2. Pre-provisions instances in Carbide with an agent so they can be quickly attached to tenant clusters; ensures they are in Carbide inventory, labeled by instance type and site, and ready for fulfillment
  3. Creates a ClusterTemplate that:
      1. Uses `cluster_infra` (and related roles) with the Carbide backend selected
      2. Specifies the site; hostclass names in node requests match Carbide instance type names

#### Cluster creation
Tenant steps:
  1. Requests a cluster from an existing cluster template

AAP steps:
  1. Creates HostedCluster
  2. Creates VPC
  3. Creates VPC-prefix or subnet
  4. Selects agents matching tenant-requested instance type and attaches their instances to the tenant VPC
  5. Attaches agents to the cluster and approves agents
  6. Configures external access to the cluster (e.g. API, ingress—implementation TBD; see Open Questions)

#### Scale up
Tenant steps:
  1. Scale nodeset size up

AAP steps:
  1. Selects additional agents matching tenant-requested instance type and attaches their instances to the tenant VPC
  2. Attaches agents to the cluster and approves agents

#### Scale down
Tenant steps:
  1. Scale nodeset size down

AAP steps:
  1. Identifies agents attached to the cluster that match the instance type and exceed the desired count
  2. Removes (allocated − desired) agents from the cluster
  3. Releases instances (e.g. deletes or returns them to Carbide) and returns machines to the shared network / hardware inventory

#### Cluster deletion
Tenant steps:
  1. Deletes existing cluster object

AAP steps:
  1. Deletes HostedCluster
  2. Deletes VPC if it was created
  3. Deletes VPC-prefix or subnet if it was created
  4. Releases instances and returns machines to the shared network / hardware inventory

### API Extensions

None

### Implementation Details/Notes/Constraints

- **Role placement and flow:** ClusterTemplates will continue to invoke `cluster_infra`; a new variable will select the backend (ESI or Carbide). When Carbide is selected, `cluster_infra` delegates to Carbide-backed roles (analogous to how it uses massopencloud.esi for networking today). The role remains responsible for ensuring the cluster’s network exists (VPC and prefix/subnet in Carbide, vs. ESI networks), selecting pre-provisioned agents that match the requested instance type(s), attaching their instances to the tenant network/VPC, and then attaching agents to the cluster and approving them. Scale-up and scale-down are handled by the same role (or sub-tasks) when the play runs with updated node requests.

- **Matching node requests to Carbide instance types:** ClusterOrder `nodeRequests` (e.g. resourceClass + count) use the hostclass name to match a Carbide instance type of the same name at the site given by the ClusterTemplate’s site parameter. Template parameters also supply Carbide resource identifiers or names for site, VPC, prefix/subnet, and SSH key group so the role can create or reference the correct Carbide resources when creating the cluster.

- **Pre-provisioned agent pool:** Instances are pre-provisioned with an agent so they can be attached to tenant clusters without provisioning delay. On scale-down or cluster deletion, the role returns instances to the shared pool.

- **Credentials and API:** The role will need Carbide API credentials (e.g. API URL, token or client credentials) to call Carbide for VPC/prefix/subnet and instance attachment. Credential handling should follow the same pattern as other osac-aap backends (e.g. environment or AAP credential injection).

- **Constraints:** The implementation must respect Carbide’s multi-tenant model (org, site, tenant id) and use the correct Carbide scope for VPC/prefix creation and instance attachment. Overlay networking is supported only on machines with DPUs. The integration supports only simple VPCs per tenant; advanced network configurations are out of scope.

### Risks and Mitigations

- **Carbide API or credential failure:** If the Carbide API is unavailable or credentials are invalid, fulfillment (create/scale/delete) will fail. *Mitigation:* Use the same patterns as other osac-aap backends (credential validation, idempotent roles); operator can retry or alert; document Carbide availability and credential requirements for operators.

- **Leaking or mixing tenant scope:** Incorrect org/site/tenant or VPC scope could attach instances to the wrong tenant’s VPC or expose resources across tenants. *Mitigation:* Use tenant-scoped credentials provided by Carbide so that each tenant’s API access is limited to that tenant’s scope and tenant information cannot be leaked.

- **Pre-provisioned pool exhaustion:** If demand exceeds the pre-provisioned agent pool for an instance type, cluster creation or scale-up can block or fail. *Mitigation:* Operators monitor pool capacity and instance-type usage; document capacity planning.

- **Scope of impact:** This is an optional backend; existing ESI flows are unchanged. Risk is limited to new code paths and configuration. *Mitigation:* New role and template variants only; no changes to core ClusterOrder or HostedCluster behavior; feature can be gated by template choice.

### Drawbacks

No significant drawbacks identified; this is an additive, optional backend (new role and templates only). Existing ESI and operator workflows are unchanged.

## Alternatives (Not Implemented)

- **Defer until bare-metal-fulfillment:** Wait for a bare-metal-fulfillment implementation and add Carbide only as a provider there. *Why not:* Adding Carbide for cluster-as-a-service now lets the team learn the required API usage, permissions, and integration patterns, making it easier to add Carbide as a bare-metal-fulfillment provider later. It also unblocks cluster-as-a-service on Carbide without depending on the broader bare-metal-fulfillment timeline.

## Open Questions [optional]

- **Tenant scope for Carbide:** Can we rely on Keycloak to supply the user’s org/tenant claim so that we know in which Carbide org/tenant to create or attach resources? Is it possible to impersonate this tenant in order to create relevant Carbide objects?
- **Ownership:** Do we expect the provider to run their own Carbide deployment (i.e., the provider operates Carbide and O-SAC consumes its API)? If so, how is this deployment and support model documented or assumed?
- **Instance handoff from pool to tenant:** How do we move (or attach) instances from the shared hardware-inventory tenant to the requesting tenant’s scope in Carbide? What API or workflow does Carbide expose for this?
- **External access:** What is a viable solution for external access to the cluster (e.g. API, ingress)? For example, MetalLB?

## Test Plan

TBD

## Graduation Criteria

TBD

### Removing a deprecated feature

N/A

## Upgrade / Downgrade Strategy

TBD

## Version Skew Strategy

TBD

## Support Procedures

TBD

## Infrastructure Needed [optional]

None
