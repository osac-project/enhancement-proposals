# CUDN EVPN Kubernetes Manager: VM-to-Fabric Networking

| Field | Value |
|---|---|
| Author(s) | Benny Kopilov |
| Jira | [OSAC-4291](https://redhat.atlassian.net/browse/OSAC-4291) |
| Date | 2026-10-28 |

## Problem Statement

OSAC can create and delete EVPN overlay networks, but tenants still need SecurityGroups, reliable addressing and policy protection from first boot before those networks are usable for VMs. Tenants need permitted VM-to-physical connectivity, stable addresses and actionable failures without changing how they create VirtualNetworks and Subnets. Successful network creation alone does not establish connectivity or isolation.

## In Scope

- VMaaS on one provider-owned networking hub in connected IPv4 deployments.
- Existing VirtualNetwork/Subnet Create/Get/List/Delete APIs, immutable specifications, IDs, parent references and recorded allocations remain compatible. Supported retries preserve network identity and workload placement. New behavior activates only on fresh installations; existing live legacy networks remain unchanged.
- Connectivity through a compatible selected Fabric pair, with disjoint VM, physical-host and ingress address allocations. Netris is the initial required real-pair validation; additional pairs need separate evidence.
- One VM-capable Subnet per VirtualNetwork under the platform limit. Unsupported VM attachment reports the limitation without disrupting the existing owner or physical siblings.
- DHCP supplies workload addresses, gateway and the agreed reachable DNS resolvers. A VM keeps its address through restart and live migration. Permitted traffic reaches physical workloads and other Subnets in the same VirtualNetwork.
- VM SecurityGroups protect traffic from first boot, keep unbound workloads isolated, apply rule changes consistently and preserve other workloads during retries and cleanup.
- Explicit ICMP SecurityGroup rules are unsupported with this manager. They fail with a permanent, actionable error and are never broadened. Administrators receive the same validation for default rules before tenant onboarding; unsupported defaults prevent activation. Other managers retain their own supported protocols.
- SecurityGroups can exist before any Subnet and remain available while their VirtualNetwork exists. Removing a VM or its Subnet preserves other live groups and workloads.
- Administrator guidance for prerequisites, unsupported paths, diagnostics and the difference between configuration checks and proven connectivity.

## Out of Scope

- Additional hubs, cross-hub connectivity, secondary tenant attachments, IPv6, dual-stack and disconnected deployments.
- VM attachment to multiple Subnets in one VirtualNetwork, or automatic handover to an existing sibling after owner deletion.
- Tenant-task configuration of physical links, host tunnel endpoints or BGP peering.
- Inter-VirtualNetwork peering, new network types, provider-written Kubernetes Managers, legacy-state adoption/migration and MetalLB address-pool provisioning.
- Changes to physical-port SecurityGroup support or the shared update-status protocol.

## User Stories

### Cloud Infrastructure Admin

- Select the supported EVPN manager with a compatible Fabric during installation and verify the resulting network.
- Prepare documented peering, address allocation and DNS prerequisites before tenant traffic starts.
- Identify missing prerequisites, unsupported default policies, manager limits and connectivity failures from actionable diagnostics.

### Tenant Admin / Tenant User

- Use existing VirtualNetwork/Subnet requests and references, retaining CIDRs, gateways, segment identities and workload placement through supported retries.
- Connect a VM on a supported Subnet to permitted physical workloads using normal OSAC networking resources.
- Share a Subnet without VM/physical address collisions.
- Apply selected SecurityGroups from first boot and keep application traffic blocked before policy preparation completes.
- Receive an explicit unsupported-policy error for ICMP without changing an existing working policy.
- Retain a VM's address through restart and live migration.
- Receive a clear owner-Subnet limitation for unsupported attachments while existing workloads continue working.
- Delete owned networking state after VM/network removal without damaging another live resource or recreating deleted state later.

## Assumptions

- The selected platform versions support the primary EVPN network, policy and persistent-address mechanisms specified in the [design](design.md).
- The agreed DNS list is deliverable through the installed platform's supported DHCP DNS-Service path; an unsupported configuration prevents activation.
- Supported-pair claims require actual route and traffic evidence.

## Dependencies

- The manager integration contract must agree on the gateway, VN/Subnet identifiers, route targets, shared namespace lifetime and installer ownership before activation.
- Shared-core networking supplies compatible inputs, recorded state and workload lifecycle integration; the installer and Enclave configuration path must deliver and validate the matching settings.
- Manager implementation and a compatible Fabric implementation must pass their component checks and the deployed VM journey.
- Strict deletion requires a reviewed backend mechanism preventing already-issued creates from restoring deleted state. This remains an implementation blocker; retained tombstones and eventual cleanup are not selected.

---

## Provenance

Authored: revise @ prd 0.11.5 - 1c6e8de, workspace codex/cudn-evpn-route-targets @ 38d18d944 (7 behind origin/main)
Final: respond @ prd 0.11.5 - 1c6e8de, workspace codex/osac-6761-cudn-evpn-contract @ a6aa33f0b (79 behind origin/main)

> Context changed between revise and respond.
>
> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"1c6e8de","source_repo":"a6aa33f0b","source_repo_branch":"codex/osac-6761-cudn-evpn-contract","commits_behind_main":79,"commits_ahead_main":2,"main_ref":"main","phases":["revise","revise","revise","revise","revise","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":true} -->
