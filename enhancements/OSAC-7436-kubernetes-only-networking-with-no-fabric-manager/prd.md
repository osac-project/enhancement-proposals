# Support Kubernetes-only networking with no Fabric Manager

| Field     | Value |
|-----------|-------|
| Author(s) | Ori Amizur |
| Jira      | [OSAC-7436](https://redhat.atlassian.net/browse/OSAC-7436) |
| Date      | 2026-11-15 |

## Problem Statement

Today, OSAC's supported tenant-networking profile requires a provider Fabric Manager, even when the provider already has a connected, preconfigured underlay. Disabling provider networking also skips the Kubernetes networking and policy work that VM tenants need, so it does not provide a usable alternative. Providers therefore lack a supported way to offer tenant-isolated VM networking while retaining ownership of their physical fabric. [Jira: OSAC-7436]

## In Scope

- Cloud Infrastructure Admins can select the no-Fabric-Manager profile and configure its applicable network settings through installer/Helm or the Enclave Wizard for a new installation. The initial profile supports VMaaS on one hub and OpenShift 4.22 or newer. [Clarify: R1.Q5] [Clarify: R2.Q2] [Clarify: R3.Q1]
- The profile uses a provider's connected, preconfigured underlay; OSAC does not configure the physical fabric. [Jira: OSAC-7436]
- Tenant onboarding continues to provide the default VirtualNetwork, Subnet, SecurityGroup, ExternalIP, and NATGateway. Tenant Admins can also create tenant VirtualNetworks, Subnets, and SecurityGroups with the same authorization and supported rule behavior as existing deployments. Provider-configured default SecurityGroup rules remain in effect, unbound workloads remain denied, and unsupported rules fail explicitly rather than broadening access. [Clarify: R1.Q2] [Clarify: R1.Q4]
- Tenant networks preserve current IPv4 addressing and isolation between VirtualNetworks, including when their CIDRs overlap. For VMaaS in the no-Fabric-Manager profile, only one Subnet per VirtualNetwork is supported for VM attachment; inter-Subnet VM routing is not part of this profile. [Jira: OSAC-7436] [Clarify: R4.Q1]
- Tenant Users can attach VMs to tenant networks and see whether network setup succeeded or failed with an actionable result. Transient provisioning failures do not report the VM network as ready, and deletion cleans up the VM network attachment. [Jira: OSAC-7436]
- Providers can supply ExternalIP pools whose addresses are reachable through their Layer 2 network. Tenant Users can attach an ExternalIP to a VM for inbound access. [Clarify: R1.Q3]
- Tenant VM outbound connections use the NATGateway associated with their VirtualNetwork and its ExternalIP as the source address. NATGateway does not initiate inbound connections. [Clarify: R1.Q3]
- Provider documentation describes installation prerequisites, external address behavior, policy defaults, supported connectivity, and limitations. [Jira: OSAC-7436]

## Out of Scope

- BMaaS and CaaS networking. [Jira: OSAC-7436]
- OSAC provisioning or configuration of the provider's physical fabric, multi-hub networking, IPv6, and dual-stack networking. [Jira: OSAC-7436]
- Historical `k8s_only` capabilities not listed in this PRD, and external access beyond Layer 2 ExternalIP attachment and NATGateway outbound SNAT. [Jira: OSAC-7436] [Clarify: R1.Q3]
- Existing fabric-backed profiles remain supported with their current behavior. Converting an existing deployment to the no-Fabric-Manager profile is out of scope. [Clarify: R1.Q5] [User]
- VM attachment to multiple Subnets within one VirtualNetwork and inter-Subnet VM routing in this profile. [Clarify: R4.Q1]

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to offer OSAC tenant networking over a preconfigured provider underlay without selecting a Fabric Manager, so that my organization retains ownership of physical fabric connectivity. [Jira: OSAC-7436]

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to select the no-Fabric-Manager profile and configure its applicable network settings through installer/Helm or the Enclave Wizard, so that a new VMaaS installation matches my provider's underlay. [Clarify: R2.Q2] [Clarify: R3.Q1]

### Tenant Admin

- As a Tenant Admin, I want to create and manage VirtualNetworks, Subnets, and SecurityGroups through the existing API and CLI workflows, with the same access boundaries and supported rules as existing OSAC deployments, so that tenant network administration remains consistent. [Clarify: R1.Q2] [Clarify: R1.Q4]

### Tenant User

- As a Tenant User, I want to select the tenant default network or a tenant-created network when provisioning a VM, so that the VM receives the intended tenant connectivity. [Jira: OSAC-7436]
- As a Tenant User, I want to see whether my VM's networking is ready or has failed with an actionable result, so that I know when it is usable or how to diagnose a failure. [Jira: OSAC-7436]
- As a Tenant User, I want to attach an ExternalIP to a VM for inbound access, so that clients that can reach the provider's Layer 2 network can connect to it. [Clarify: R1.Q3]
- As a Tenant User, I want VM outbound connections to use the VirtualNetwork's NATGateway address, so that external services see a stable source address and replies return to my VM. [Clarify: R1.Q3]

## Dependencies

- **Provider underlay:** The provider supplies connected Layer 2 networking, a working default gateway, and an address pool reachable by cluster egress nodes and MetalLB announcements. [Jira: OSAC-7436] [Clarify: R1.Q3]
- **OpenShift platform:** OpenShift 4.22 or newer is the supported baseline for primary Layer 2 VM networking. The design validates VM connectivity and provider gateway/address-pool prerequisites. [Clarify: R2.Q2]
- **External address service:** The cluster supports Layer 2 advertisement for provider ExternalIP pools (MetalLB Layer 2 mode). [Clarify: R1.Q3]
- **Enclave Wizard:** The Wizard exposes the no-Fabric-Manager profile and its applicable network configuration options alongside existing fabric-backed setup. [Clarify: R3.Q1]

---

## Provenance

Authored: respond @ prd 0.11.5 - cd88680, workspace main @ 74219998b
Phases: draft, draft, revise, revise, revise, respond, respond

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"cd88680","source_repo":"74219998b","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","draft","revise","revise","revise","respond","respond"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
