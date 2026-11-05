# Storage Connectivity Through Networking

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor |
| Jira        | [OSAC-5073](https://redhat.atlassian.net/browse/OSAC-5073) |
| Phase       | 1 — near-term IP storage connectivity through tenant SNAT |
| Date        | 2026-11-05 |

## Terminology

| Term | Meaning |
|------|---------|
| **IP storage** | Storage reached over an IP network, such as NFS, iSCSI, or NVMe over TCP. |
| **Storage address** | An address a workload connects to for storage: a data address or a storage management address. |
| **Reserved ranges** | The address ranges that the Cloud Infrastructure Admin reserves for the provider's infrastructure at installation, so that no tenant network uses them. Storage ranges are listed there. |
| **Outbound address** | The single address that a tenant network's outbound traffic leaves with. The storage system sees it as the client. |
| **Managed network fabric** | The tenant networks that OSAC networking manages, up to the point where outbound traffic gets its outbound address. |
| **Cluster internal networks** | The address ranges a cluster uses inside itself for its pods and services. |

## Problem Statement

The storage that OSAC offers is not attached to the servers that use it. Workloads reach it over the
network, so every volume, disk, and mount depends on a working network path from the workload to the
storage system. That is why networking has to provide this path and keep tenant networks from getting in
its way. For now, this covers storage reached over Ethernet.

Tenant workloads need the provider's IP storage: persistent volumes on CaaS clusters, disks that VMs
use, and storage that a bare-metal host or a VM mounts itself. Today an admin can keep tenant networks
off reserved ranges, and every tenant's default network can reach outside through an outbound address.
Nothing ties these to storage. The storage designs assume that workloads reach storage and leave the
network path to the provider. No document says which path each workload takes, which addresses must
stay out of tenant networks, or how a storage system tells tenants apart.

The gaps show up as storage that silently does not work. A cluster's internal networks can cover a
storage address, so its volumes never mount. Nothing stops that cluster from being created, and this
feature keeps it that way so that existing installations keep working. Each provider also has to work
out the paths and the capacity limits on its own.

## In Scope

- Storage connectivity for VMaaS, CaaS, and BMaaS through the networking OSAC already offers, for any
  storage system that serves IP storage and any supported network fabric.
- Storage ranges listed among the reserved ranges, at installation or in a later rollout.
- Refusing tenant networks that overlap a reserved range, as OSAC already does.
- Guidance for choosing cluster internal networks that do not cover storage.
- Outbound-only storage access through the tenant network's outbound address, which tells tenant networks
  apart at the storage system.
- Documentation for every storage consumer: the path, what OSAC guarantees, what the provider must
  supply, capacity, and what to do when capacity is not enough.

## Out of Scope

- Any product change. This feature is documentation only.
- Storage reached over anything other than Ethernet, such as Fibre Channel or InfiniBand, and storage that
  is not IP.
- Dedicated storage networks, second storage network cards, and per-tenant storage networks (OSAC-6121
  and later phases of OSAC-5073).
- New fields, new installation settings, new checks, and new network fabric behavior.
- Refusing a cluster whose internal networks overlap a reserved range.
- The path after the outbound address: routing to storage and everything between the managed network
  fabric and the storage system. The provider owns it.
- Storage-side access control, such as export rules, storage accounts, and rules keyed on client
  addresses. The provider and the storage designs own it.
- Connections that the storage system opens toward workloads.
- Bandwidth reservation or quality of service for storage traffic.
- GPU-to-storage paths inside the data center fabric (OSAC-1382).
- Configuring storage clients on BMaaS hosts. The tenant configures them.

## User Stories

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to list my storage ranges among the reserved ranges at
  installation or in a later rollout, so that no tenant network can capture storage traffic.
- As a Cloud Infrastructure Admin, I want a rollout that adds a storage range already used by a tenant
  network to fail and name that network, so that I fix the conflict before workloads lose storage.
- As a Cloud Infrastructure Admin, I want the documentation to tell me which cluster internal networks
  are used when none are chosen, and how to check existing clusters before I add a storage range, so
  that no cluster silently loses storage.
- As a Cloud Infrastructure Admin, I want one table that shows, for every storage consumer, the path and
  what I must supply, so that I prepare the network once for any storage system and any network fabric.
- As a Cloud Infrastructure Admin, I want capacity numbers for one outbound address, so that I know
  whether my storage load fits and what to do when it does not.
- As a Cloud Infrastructure Admin, I want to know which address the storage system sees for each tenant
  network, and for how long, so that the storage administrator can tell tenants apart.

### Cloud Provider Admin

- As a Cloud Provider Admin, I want a newly onboarded tenant's default network to reach storage, so that
  the tenant gets storage without an extra step.

### Tenant Admin

- As a Tenant Admin, I want to know that a tenant network needs a ready outbound address to reach
  storage, so that workloads on extra networks I create keep storage access.
- As a Tenant Admin, I want a clear rejection when my tenant network overlaps a storage range, so that I
  pick another range before creating workloads.

### Tenant User

- As a Tenant User, I want the documentation to tell me which cluster internal networks to avoid, so
  that I never create a cluster whose volumes cannot mount.
- As a Tenant User, I want a VM or bare-metal host on my network to mount the provider's file storage, so
  that I run stateful workloads on it.

## Requirements

### Functional Requirements

- **FR-1:** A Cloud Infrastructure Admin lists storage ranges among the reserved ranges, at installation
  or in a later rollout. [Clarify: R1.Q3]
- **FR-2 (existing behavior, verified here):** Creating a tenant network that overlaps a reserved range is
  rejected through every interface that creates tenant networks. Creating a provider address pool that
  overlaps one is rejected too; only the provider creates pools, through its administrative interface.
  Each error names the range.
- **FR-3:** The documentation tells the Cloud Infrastructure Admin and catalog authors that cluster
  internal networks must not cover a storage address. It names the internal networks a cluster gets when
  none are chosen, and where those come from. Nothing enforces this: the admin and the catalog author
  choose the networks, and a tenant who chooses them follows the same guidance. [Clarify: R3.Q1]
- **FR-4 (existing behavior, verified here):** A rollout that adds a reserved range overlapping the
  default tenant network range, an existing tenant network, or a provider address pool fails, and its
  error names the overlap. Rollouts do not check existing clusters; the documentation tells the admin how
  to check them first. [Clarify: R2.Q1]
- **FR-5 (existing behavior, verified here):** A workload on a tenant network with a ready outbound
  address can open connections to storage, and the storage system sees that outbound address as the
  client. This holds for VMs, CaaS workers, and BMaaS hosts. [Clarify: R1.Q2]
- **FR-6 (existing behavior, verified here):** A tenant's default network reaches storage with no tenant
  action when the provider's managed networking is enabled.
- **FR-7:** The documentation covers every storage consumer (VMaaS volumes, VMs mounting storage, CaaS
  workers, BMaaS hosts, and deployments without managed networking): the path, what OSAC guarantees, what
  the provider must supply, how to choose and extend storage ranges, how to check existing clusters before
  adding one, the outbound address as tenant identity and how long it lasts, the connection limit per
  outbound address with its assumptions, and troubleshooting. Tenant documentation states that a tenant
  network needs a ready outbound address to reach storage. [Clarify: R1.Q4]

### Non-Functional Requirements

- **NFR-1:** Storage connectivity needs no setting specific to a storage vendor or a network fabric.
  [Clarify: R1.Q1]
- **NFR-2:** A connection that storage opens toward a tenant network's outbound address is not delivered.
  Workloads that a tenant has made reachable from outside on purpose stay reachable as designed.
- **NFR-3:** Two tenant networks with the same address range reach storage with different outbound
  addresses.

## Acceptance Criteria

- [ ] With a storage range reserved, creating a tenant network that overlaps it fails and names the
  range; a network outside it is created.
- [ ] The installation guide states that cluster internal networks must not cover storage, names the
  internal networks a cluster gets when none are chosen, and says that nothing enforces this.
- [ ] A rollout that adds a range overlapping an existing tenant network fails and names that network;
  removing the range from the rollout lets it complete.
- [ ] A VM on a new tenant's default network mounts file storage outside the managed network fabric, and
  the storage system records the tenant's outbound address as the client.
- [ ] A persistent volume on a CaaS cluster and a file storage mount on a BMaaS host both work, and the
  storage system records each network's outbound address as the client.
- [ ] Two tenants whose networks use the same address range mount from one storage system, and it sees
  two different client addresses.
- [ ] A connection opened from storage toward a VM that has no address of its own outside the tenant
  network does not reach the VM.
- [ ] The installation guide holds the consumer table, what the provider must supply, the check of
  existing clusters, and the connection limit per outbound address; the tenant guide states the outbound
  address requirement.

## Assumptions

- The outbound address works as OSAC networking promises. Everything after it, including the routes to
  storage and back, is outside OSAC networking and the provider supplies it.
- Storage addresses sit outside the managed network fabric.
- Storage clients open every connection; no storage protocol in use needs storage to connect to the
  client.
- The storage system controls which tenant may use what. OSAC networking does not.
- An outbound address identifies a tenant network only while the tenant holds it. A released address can
  later go to another tenant. A tenant's default outbound address stays for the tenant's whole life.
  Keeping storage access rules in step with these addresses is outside OSAC.
- Admins and catalog authors keep cluster internal networks off storage addresses, as the documentation
  tells them.

## Dependencies

- **Unified networking (OSAC-1433):** tenant networks, outbound addresses, provider address pools, the
  reserved ranges, and their checks.
- **CaaS networking (OSAC-1436):** the rule that a cluster needs an outbound address, which exists. It
  also designs checks of cluster internal networks that are not built; this feature does not add them.
- **Storage designs (OSAC-1332, OSAC-1111, OSAC-2117, OSAC-2872):** the storage clients and storage-side
  access control. They depend on this feature for the path and the tenant identity. Some of them limit
  access by the address of a worker or a node. The storage system sees the outbound address instead, so
  those designs must use the outbound address of the workload's tenant network, or credentials. The
  storage team owns that follow-up.

## Risks

### 1. Outbound capacity

- **Owner:** Cloud Infrastructure Admin, with the network fabric provider
- **Mitigation:** The documentation gives limits per outbound address and the steps to take when a
  network exceeds them. A dedicated storage network (OSAC-6121 or a later phase of OSAC-5073) removes the
  limit later.

### 2. Cluster internal networks over storage

- **Owner:** Cloud Infrastructure Admin
- **Mitigation:** Nothing refuses a cluster whose internal networks cover a storage address, and a range
  added later is not checked against existing clusters. Such a cluster loses storage. The documentation
  names the internal networks a cluster gets when none are chosen, tells the admin to keep storage ranges
  outside them, and tells the admin how to check existing clusters before a rollout.

### 3. Shared path

- **Owner:** Cloud Infrastructure Admin
- **Mitigation:** Every tenant's storage traffic crosses the same outbound path and provider network, so
  one tenant can load it for others. The documentation states this.

### 4. Storage rules keyed on node addresses

- **Owner:** Storage team
- **Mitigation:** Storage designs that allow access by worker or node address would refuse tenant
  traffic, because the storage system sees the outbound address. Those designs move to the outbound
  address or to credentials.

## Open Questions

None.

---

## Provenance

Authored: draft @ prd 0.11.5 - 70405a6, workspace main @ 21e5dba7c (52 behind origin/main)

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"70405a6","source_repo":"21e5dba7c","source_repo_branch":"main","commits_behind_main":52,"commits_ahead_main":0,"main_ref":"main","phases":["draft"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
