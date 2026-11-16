# Tenant networking for VMaaS without a Fabric Manager

| Field     | Value |
|-----------|-------|
| Author(s) | Ori Amizur |
| Jira      | [OSAC-7436](https://redhat.atlassian.net/browse/OSAC-7436) |
| Date      | 2026-11-16 |

## Problem Statement

Cloud providers that operate a connected, preconfigured network and want to retain control of their physical fabric cannot offer tenant-isolated VM networking through OSAC today without deploying a Fabric Manager. Disabling provider networking also removes the tenant networking and SecurityGroup policy VMaaS needs, so these providers lack a supported way to serve tenant VMs over their own network. [Jira: OSAC-7436]

## In Scope

- Cloud Infrastructure Admins can select the no-Fabric-Manager profile and configure its applicable network settings, including the ExternalIP protocol/port set, through installer/Helm or the Enclave Wizard for a new installation. The initial profile supports VMaaS on the hub cluster only and OpenShift 4.22 or newer; VMs on separate workload clusters are out of scope. [Clarify: R1.Q5] [Clarify: R2.Q2] [Clarify: R3.Q1] [Jira: OSAC-7436]
- Installer/Helm and the Enclave Wizard reject a configuration that combines this profile with BMaaS or CaaS, with an actionable message that the profile is limited to VMaaS. [Jira: OSAC-7436] [User]
- The profile uses a provider's connected, preconfigured underlay; OSAC does not configure the physical fabric. [Jira: OSAC-7436]
- Tenant onboarding continues to provide the default VirtualNetwork, Subnet, SecurityGroup, ExternalIP, and NATGateway. Tenant Admins can also create tenant VirtualNetworks, Subnets, and SecurityGroups with the same authorization and supported rule behavior as existing deployments. Provider-configured default SecurityGroup rules remain in effect, unbound workloads remain denied, and unsupported rules fail explicitly rather than broadening access. Explicit ICMP SecurityGroup rules remain unsupported for VMs; all-protocol rules include ICMP, as in existing VM deployments. [Clarify: R1.Q2] [Clarify: R1.Q4] [User]
- Tenant networks preserve current IPv4 addressing and isolation between VirtualNetworks, including when their CIDRs overlap. For VMaaS in the no-Fabric-Manager profile, only one Subnet per VirtualNetwork is supported for VM attachment; inter-Subnet VM routing is not part of this profile. [Jira: OSAC-7436] [Clarify: R4.Q1]
- Tenant Users can attach VMs to tenant networks and see whether network setup succeeded or failed with an actionable result. Transient provisioning failures do not report the VM network as ready, and deletion cleans up the VM network attachment. [Jira: OSAC-7436]
- Providers configure a non-empty, installation-wide set of protocol/port pairs for inbound VM ExternalIP attachments. The default set is TCP/22, matching current behavior, and applies to every VM ExternalIP attachment in the installation. Tenant SecurityGroups can further restrict inbound traffic but cannot expose pairs outside the configured set. ICMP is not exposed through this port-based setting. [Clarify: R5.Q1] [User]
- A VM without a NATGateway cannot initiate outbound connections to any destination outside its VirtualNetwork, including provider infrastructure, even when a SecurityGroup rule permits that destination. Replies to permitted inbound ExternalIP connections remain part of the inbound path and must be validated. This restriction does not change the configured SecurityGroup defaults. With a NATGateway, allowed outbound connections use the gateway's ExternalIP; the NATGateway does not initiate inbound connections, and existing provider-configured SecurityGroup rules and provider routing determine which destinations are allowed. [Clarify: R1.Q3] [Clarify: R1.Q4] [User]
- Provider documentation describes installation prerequisites, external address behavior, policy defaults, supported connectivity, and limitations. [Jira: OSAC-7436]

## Out of Scope

- BMaaS and CaaS networking. [Jira: OSAC-7436]
- OSAC provisioning or configuration of the provider's physical fabric, multi-hub networking, IPv6, and dual-stack networking. [Jira: OSAC-7436]
- External connectivity other than inbound access through an ExternalIP and outbound access through a NATGateway. [Jira: OSAC-7436] [Clarify: R1.Q3]
- Tenant-specific or per-ExternalIP protocol/port overrides. [Clarify: R5.Q1] [User]
- Existing fabric-backed profiles remain supported with their current behavior. Converting an existing deployment to the no-Fabric-Manager profile is out of scope. [Clarify: R1.Q5] [User]
- VMaaS workloads placed on separate workload clusters. [Jira: OSAC-7436]
- VM attachment to multiple Subnets within one VirtualNetwork and inter-Subnet VM routing in this profile. [Clarify: R4.Q1]

## User Stories

### Cloud Provider Admin

- As a Cloud Provider Admin, I want to offer OSAC tenant networking over a preconfigured provider underlay without selecting a Fabric Manager, so that my organization retains ownership of physical fabric connectivity. [Jira: OSAC-7436]

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want to select the no-Fabric-Manager profile and configure its applicable network settings through installer/Helm or the Enclave Wizard, so that a new VMaaS installation matches my provider's underlay. [Clarify: R2.Q2] [Clarify: R3.Q1]
- As a Cloud Infrastructure Admin, I want to set the inbound protocol/port pairs for VM ExternalIP attachments during installation, so that external VM access follows my provider's policy. [Clarify: R5.Q1] [User]

### Tenant Admin

- As a Tenant Admin, I want to create and manage VirtualNetworks, Subnets, and SecurityGroups through the existing API and CLI workflows, with the same access boundaries and supported rules as existing OSAC deployments, so that tenant network administration remains consistent. [Clarify: R1.Q2] [Clarify: R1.Q4]

### Tenant User

- As a Tenant User, I want to select the tenant default network or a tenant-created network when provisioning a VM, so that the VM receives the intended tenant connectivity. [Jira: OSAC-7436]
- As a Tenant User, I want to see whether my VM's networking is ready or has failed with an actionable result, so that I know when it is usable or how to diagnose a failure. [Jira: OSAC-7436]
- As a Tenant User, I want to attach an ExternalIP to a VM so clients can reach services on the protocol/port pairs enabled for this installation and allowed by my SecurityGroup. [Clarify: R5.Q1] [User]
- As a Tenant User, I want outbound connections from my VM to use its VirtualNetwork's NATGateway address, so external services see a stable source address and replies return to my VM; without a NATGateway, my VM cannot initiate outbound connections to destinations outside its VirtualNetwork. [Clarify: R1.Q3]

## Assumptions

- OpenShift 4.22 or newer and the provider's network can support the ExternalIP and NATGateway behavior required by this PRD. The design must validate a supported path before implementation. If it cannot, this profile is blocked until a supported path is identified; NATGateway remains required for default tenant onboarding and is not made optional or deferred. [Clarify: R1.Q3] [User]

## Dependencies

- **Provider network and address capacity:** The provider supplies a connected network and working gateway, plus a pool of addresses reachable by intended clients through the provider's network. For inbound ExternalIP access, the provider network must allow MetalLB to advertise the pool's addresses at Layer 2. Capacity must cover one address per tenant's default NATGateway, one per VM that needs inbound ExternalIP access, and one per additional NATGateway. [Jira: OSAC-7436] [Clarify: R1.Q3] [User]
- **OpenShift platform:** OpenShift 4.22 or newer is the supported baseline for the VM networking profile. [Clarify: R2.Q2]

---

## Provenance

Authored: revise @ prd 0.11.5 - cd88680, workspace main @ 74219998b
Phases: draft, draft, revise, revise, revise, respond, respond, respond, respond, respond, respond, revise, manual-edit, revise, revise, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.11.5","ai_workflows":"cd88680","source_repo":"74219998b","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","draft","revise","revise","revise","respond","respond","respond","respond","respond","respond","revise","manual-edit","revise","revise","revise"],"authoring_modes":["manual","skill"],"context_changed":false,"origin_untracked":false} -->
