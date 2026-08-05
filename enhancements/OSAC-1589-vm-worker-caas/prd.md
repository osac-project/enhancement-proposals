# VM Worker Node Support for CaaS Clusters

| Field       | Value   |
|-------------|---------|
| Author(s)   | Vladik Romanovsky |
| Jira        | [OSAC-1589](https://redhat.atlassian.net/browse/OSAC-1589) |
| Date        | 2026-07-27 |

## Problem Statement

Cluster-as-a-Service (CaaS) today requires bare-metal worker nodes. Every cluster order depends on the availability and provisioning of physical hardware. This creates several hard limitations:

- Organizations or tenants that do not own (or cannot allocate) bare-metal capacity cannot use CaaS at all.
- Development, QA, and internal platform teams that need short-lived or experimental clusters must wait for physical nodes to be allocated, which is slow and operationally expensive.
- A single physical host can typically back only one worker node, leading to poor density and idle capacity when workloads are small or bursty.
- The platform and tenants are tightly coupled to specific machine types, firmware, and hardware configurations, reducing flexibility and increasing operational complexity.
- Strong multi-tenant or compliance-driven isolation is harder to achieve when worker nodes run directly on the physical host.

As a result, CaaS adoption is constrained to environments that already have dedicated bare-metal inventory, and the platform cannot efficiently serve the broader set of users and use cases that would benefit from on-demand OpenShift clusters. [User]

## Motivation

Extending CaaS to support VM-based worker nodes removes these limitations while preserving the same user experience and API surface. The value is both immediate and strategic:

- **No bare-metal required** — Organizations, teams, or tenants that do not own (or cannot allocate) physical nodes can still provision full OpenShift clusters. This is especially relevant for smaller teams, development environments, and tenants who want strong isolation without hardware ownership.
- **Better resource utilization and economic model** — A single physical host can back multiple VM-based worker nodes (or one large VM that consumes most of the host). This improves density, reduces idle capacity, and enables more granular chargeback compared to dedicating entire bare-metal nodes.
- **Hardware abstraction** — Bare-metal CaaS forces the platform and tenants to deal with specific machine types, firmware, BIOS settings, and NIC configurations. VM workers abstract most of that away, allowing the platform to offer consistent machine types across hardware generations and vendors.
- **Ephemeral and easily re-provisionable clusters** — VM workers can be created, destroyed, and recreated far more quickly and cheaply than bare-metal equivalents. This is ideal for short-lived test/CI/certification clusters, customer demos, proof-of-concepts, and internal development/testing of the CaaS control plane itself (which is currently difficult to exercise end-to-end without physical nodes).
- **Stronger isolation model** — Running worker nodes as VMs provides an additional isolation boundary. This is attractive for multi-tenant platforms and for regulated or compliance-sensitive workloads.
- **Foundation for advanced lifecycle operations** — Once workers are VMs, capabilities that are extremely difficult with bare metal become possible in the future: live migration for host maintenance, snapshotting/cloning of workers, and easier capacity rebalancing.

In short, VM-backed CaaS makes the existing bare-metal CaaS capability available to a much broader set of users and use cases without changing the consumption model. It also improves infrastructure density and unblocks internal testing of the CaaS control plane. [User]

## In Scope

- Ordering, provisioning, and deleting CaaS clusters with VM-based worker nodes through the existing ClusterOrder workflow [Clarify: R2.Q1]
- Tenant network isolation for VM workers — each cluster's worker VMs are attached to a tenant-owned subnet; the platform enforces that tenants can only reference subnets they own, rejecting cross-tenant subnet references at order time [Clarify: R1.Q3]
- Scaling (adding and removing worker nodes) for VM-backed clusters, using the same update workflow as bare-metal CaaS [Clarify: R1.Q1]
- Configurable worker VM sizing (vCPU cores, memory, root volume size) through cluster template offerings [Clarify: R1.Q4]
- Running standard Kubernetes workloads on the provisioned guest cluster

## Out of Scope

- **GPU and accelerator passthrough** — covered by [OSAC-1373](https://redhat.atlassian.net/browse/OSAC-1373) and composable with VM-backed cluster templates once delivered [Clarify: D1]
- **Mixed bare-metal and VM worker pools in a single cluster** — may be considered in a future phase once pure VM-backed clusters are stable.
- **Multi-interface and east-west networking** (L3VPN, SR-IOV) — deferred to align with multi-fabric networking work ([OSAC-1382](https://redhat.atlassian.net/browse/OSAC-1382)) [Clarify: D7]
- **Live migration, snapshotting, and cloning of worker VMs** — future capabilities enabled by the VM foundation [Clarify: D5]
- **Full feature parity with bare-metal CaaS** — the initial release delivers a usable CaaS experience, not 100% parity [Clarify: D5]

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to publish VM-backed cluster templates in the catalog so that tenants can order clusters without bare-metal hardware.
- As a Cloud Provider Admin, I want to offer different VM sizing presets (dev/small, production/large) as distinct templates so that tenants choose an appropriate cluster profile from the catalog.

### Cloud Infrastructure Admin

No new user stories for this persona — VM-based CaaS relies on existing VMaaS infrastructure.

### Tenant Admin

- As a Tenant Admin, I want to create a VirtualNetwork and Subnet for my organization before ordering a VM-backed cluster so that my cluster's worker nodes are connected to an isolated tenant network. [Clarify: D3]
- As a Tenant Admin, I want to order a VM-backed cluster by selecting a VM cluster template and specifying the subnet my workers should join so that I get an operational, network-isolated OpenShift cluster without needing bare-metal nodes. [Clarify: D2, D3]
- As a Tenant Admin, I want to scale my VM-backed cluster up or down by modifying the node count so that I can adjust capacity without ordering a new cluster. [Clarify: R1.Q1]
- As a Tenant Admin, I want to delete a VM-backed cluster and have all associated resources (VMs, network attachments) cleaned up so that I am not charged for idle infrastructure.

### Tenant User

- As a Tenant User, I want to deploy workloads on a VM-backed cluster using the same tools (oc, kubectl, Helm) I use on bare-metal clusters so that the worker platform is transparent to my applications.
- As a Tenant User, I want the cluster I receive to have a Ready worker node and a functional API server so that I can start deploying immediately after the cluster reaches Available status.
- As a Tenant User, I should not be able to see or act on the underlying virtual machines or infrastructure resources (e.g., reboot, delete VMs) so that the abstraction boundary between my cluster and the platform is maintained.

## Assumptions

- The platform's virtualization infrastructure (VMaaS) is operational on the management cluster.
- A storage class capable of provisioning persistent volumes of at least 64 GiB is available for VM root volumes.

## Dependencies

- **Unified Networking Architecture ([OSAC-1433](https://redhat.atlassian.net/browse/OSAC-1433)):** The initial networking implementation provides tenant subnet attachment for VM workers. As the unified networking architecture matures (including east-west networking via [OSAC-1382](https://redhat.atlassian.net/browse/OSAC-1382)), the networking path will evolve to support SR-IOV/Ethernet interfaces and east-west traffic. [Clarify: D6]
- **GPU/Accelerator Support ([OSAC-1373](https://redhat.atlassian.net/browse/OSAC-1373)):** Once delivered, GPU support is composable with VM-backed cluster templates. No changes to this feature are required. [Clarify: D1]

---

## Provenance

Authored: respond @ prd 0.6.1 - 96de078, workspace main @ 0987735
Phases: draft, respond

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.6.1","ai_workflows":"96de078","source_repo":"0987735","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","respond"],"authoring_modes":["skill"],"context_changed":false} -->
