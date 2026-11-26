# VMaaS managed multi-NIC with role-based networks

| Field | Value |
|---|---|
| Author(s) | Vladik Romanovsky |
| Jira | https://redhat.atlassian.net/browse/OSAC-6121 |
| Date | 2026-10-19 |
| Related proposal | [Alona’s role-based network types design, PR #393](https://github.com/osac-project/enhancement-proposals/pull/393) |

## Problem Statement

Some provider-managed VMs need an externally reachable out-of-band (OOB) interface in addition to their primary workload network. Other managed VMs need only the primary network. The current VMaaS path is designed around one attachment and does not describe how providers select different network implementations, prepare a physical OOB network, or configure a static guest address. Deployments also differ in whether their managers and virtualization platform can support more than one interface.

The provider, rather than the tenant, owns this managed workflow: the provider admin creates the VirtualNetworks and ComputeInstance, while the tenant receives and uses the VM. The design must preserve a safe single-NIC path when the deployment does not advertise multi-NIC support.

## In Scope

- VMaaS provider-managed ComputeInstances. The provider admin creates the primary and OOB VirtualNetworks, their Subnets and required SecurityGroups, reserves the OOB address, and creates the ComputeInstance. The tenant consumes the resulting VM.
- Role-based network selection on VirtualNetwork. The deployment retains one NetworkClass, which maps each network type to its fabric-manager and K8s-manager pair.
- A primary VirtualNetwork whose role resolves to the existing CUDN plus EVPN path.
- One provider-managed shared OOB VirtualNetwork whose role resolves to a localnet K8s manager. Each managed VM that needs OOB attaches to a Subnet in this same shared OOB VirtualNetwork.
- A provider-controlled multi-NIC capability computed from the configured manager declarations. Deployments without complete support continue to allow zero or one attachment only.
- The existing operator ceiling of eight attachments when multi-NIC is enabled, exactly one ComputeNetworkAttachment.primary=true marker for a multi-attachment VM, and immutable attachment membership after creation.
- Static IPv4 configuration for each OOB attachment, supplied by the provider admin and injected into the guest during VM creation.
- Per-attachment IP visibility in ComputeInstance status and the existing read-only ComputeInstance details surface where it displays status. The tenant can inspect addresses but cannot select or provision OOB networking.
- A fabric-to-K8s-manager handoff contract for physical-network information after the fabric manager has configured the switch path.
- Existing ExternalIP and NAT behavior targeting the primary interface only.

## Out of Scope

- IPv6, dual-stack, and disconnected networking; this feature does not change the current connected IPv4 support boundary.
- CaaS and BMaaS networking changes, including the CaaS VM-worker pod-network plus tenant-attachment pattern.
- Hot-plug, attachment updates, or changing the primary after creation.
- Tenant-created OOB VirtualNetworks or tenant self-service OOB selection such as a future --enable-oob option.
- Arbitrary cross-VirtualNetwork attachment. The sole cross-VirtualNetwork case in this increment is the provider-managed primary VirtualNetwork plus the one configured shared OOB VirtualNetwork.
- Additional provider-shared networks and arbitrary cross-tenant network sharing.
- Replacing the network_types and SubnetNetworkBinding model proposed in PR #393 with new resource types.
- A tenant UI for creating managed VMs or selecting OOB networks; the UI scope is read-only attachment status.

## User Stories

### Provider Admin

- As a Provider Admin, I want to declare network roles and their manager pairs in the deployment NetworkClass, so primary and OOB VirtualNetworks use the correct provisioning paths.
- As a Provider Admin, I want to prepare one shared OOB VirtualNetwork and have the fabric and localnet managers configure it, so managed VMs can connect to the physical OOB network without tenants configuring infrastructure.
- As a Provider Admin, I want to create a managed VM with a primary workload attachment and an optional OOB attachment with a reserved static IP, so the guest is reachable on both intended networks.
- As a Provider Admin, I want unsupported deployments to keep multi-NIC disabled until every required manager path is ready, so requests cannot be accepted and then fail during provisioning.
- As a Provider Admin, I want to inspect per-attachment addresses and provisioning errors, so I can diagnose the VM’s primary and OOB connectivity independently.

### Tenant User

- As a Tenant User, I want to receive and use the VM created for me by the provider, so I can run my workload without configuring provider networking.
- As a Tenant User, I want the existing ComputeInstance details surface to show each attachment’s Subnet and IP, so I can use the provider-configured addresses without selecting OOB networking.
- As a Tenant User, I want ordinary single-network VM behavior to remain available when the deployment does not support multi-NIC, so existing VM usage is not blocked.

## Functional Requirements

1. **Role-based network selection.** Each VirtualNetwork has an immutable network_type. The deployment has one NetworkClass mapping each unique network type to one fabric_manager and one k8s_manager and declaring whether that type supports primary, secondary, or both positions. The primary workload type resolves to CUDN plus EVPN. The OOB type resolves to a localnet K8s manager such as cudn_localnet. When network_type is omitted, the existing default-manager behavior remains for the single-NIC path; multi-NIC requests require explicit role mappings.
2. **One shared OOB network.** The provider configures one shared OOB VirtualNetwork per deployment using the OOB network type. Managed VMs that need OOB attach to a Subnet in this VirtualNetwork. The provider may reuse this network across managed VMs; tenant users cannot create or select other provider OOB networks in this increment.
3. **Managed creation flow.** The Provider Admin creates the primary VirtualNetwork and Subnet, the shared OOB VirtualNetwork and Subnet, required SecurityGroups, reserves the static OOB address, and creates the ComputeInstance with the intended attachment set. The Tenant User does not create or mutate these resources as part of this workflow. Existing UI surfaces remain read-only: they may display per-attachment status, but do not add a tenant VM creation or OOB-selection form.
4. **Capability and cardinality.** NetworkClass advertises supports_multi_nic only when every manager in both required role paths advertises support: the primary workload fabric manager and CUDN K8s manager, and the OOB fabric manager and localnet K8s manager. Missing or incomplete declarations mean false. When false or unset, requests with more than one attachment are rejected before persistence. When true, the existing operator ceiling of eight attachments is preserved; exactly one attachment must have ComputeNetworkAttachment.primary=true when there are multiple. A one-attachment VM remains implicitly primary, and the spec marker identifies it on readback while status entries map to it by Subnet reference. The managed primary-plus-OOB pattern uses the primary workload VirtualNetwork and the configured shared OOB VirtualNetwork; no other cross-VirtualNetwork combination is accepted. Multi-NIC requests require explicit network_type roles; omitted network_type retains the existing manager default for the single-NIC path.
5. **Validation.** Before persistence, fulfillment validates that the primary Subnet is ready and belongs to the VM’s tenant, that the OOB Subnet is ready and belongs to the configured shared OOB VirtualNetwork, and that the provider caller is authorized to attach that shared network to the tenant-owned VM. It validates unique Subnet references, supported network roles, readiness and VirtualNetwork alignment of SecurityGroups, the primary count, and the static OOB IPv4 address against the OOB Subnet CIDR and the provider’s reservation source. Invalid requests do not create a ComputeInstance or auto-created dependent ExternalIP.
6. **Static OOB address.** Every OOB attachment in a managed multi-NIC VM has one provider-assigned static IPv4 address. The VM template injects this address into the guest’s OOB interface during creation. The OOB interface does not replace the primary interface’s default route. Address reservation and uniqueness are checked through the provider’s authoritative OOB address allocation process.
7. **Primary routing and external access.** The primary attachment remains the VM’s default-route path. ExternalIPAttachment inbound DNAT targets the primary attachment’s discovered IP. NATGateway egress remains scoped to the primary VirtualNetwork and uses the primary route. OOB does not become the default route. Preserve a symmetric OOB return path: directly connected OOB clients use the connected OOB route; any routed OOB client prefixes require provider-supplied routes through the OOB interface.
8. **Status.** ComputeInstance status exposes one attachment status per configured attachment, including its Subnet reference and IP address, and makes the primary identifiable through the immutable spec marker. The OOB static address is visible against its attachment.
9. **Generic VM composition.** The VM reconciler consumes each Subnet’s SubnetNetworkBinding status. It renders the binding-provided KubeVirt binding for the primary and the binding-provided Multus NAD name and namespace requirements for secondaries. It contains no manager-specific branching.
10. **Immutability.** Attachments, Subnet references, primary designation, and OOB static address are create-time-only. SecurityGroup update behavior remains as currently defined. Changing the topology requires deleting and recreating the VM.
11. **Regression.** When multi-NIC capability is false or unset, zero-attachment default networking and one-attachment behavior continue to follow OSAC-1435 and OSAC-5557. CaaS and BMaaS contracts remain unchanged.

## Acceptance Criteria

- [ ] NetworkClass role mappings resolve a primary type to the CUDN plus EVPN managers and the OOB type to a localnet K8s manager; the computed supports_multi_nic capability remains false unless both paths advertise support.
- [ ] A Provider Admin can create one shared OOB VirtualNetwork and its Subnet, and use that same VirtualNetwork for OOB attachments on multiple managed VMs.
- [ ] A Provider Admin can create a managed VM with a primary workload attachment and an OOB attachment. The VM has a primary l2bridge interface and a secondary Multus/bridge interface, and the OOB guest interface receives its reserved static IPv4 address.
- [ ] Fulfillment rejects multi-attachment requests before persistence when the capability is false or unset, and preserves omitted/default and single-attachment VM creation.
- [ ] An enabled deployment accepts up to eight valid attachments and rejects nine. Fulfillment rejects a missing or multiple primary marker, unsupported role combinations, a foreign or unready primary Subnet, an OOB Subnet outside the configured shared OOB VirtualNetwork, a non-ready or misaligned SecurityGroup, a duplicate Subnet, and an invalid or already-reserved OOB static IP.
- [ ] The VM reconciler consumes SubnetNetworkBinding for both primary and secondary attachments without network-manager-specific logic. The localnet manager creates a local NAD in the VM namespace selected by the binding’s namespace-label contract.
- [ ] ComputeInstance API/status and any existing details UI report each attachment and its IP; the primary is identifiable by the immutable spec marker and Subnet reference. ExternalIP DNAT targets the primary IP, and OOB does not change the primary default route or NAT behavior. OOB replies use the OOB interface for the configured OOB client prefixes.
- [ ] Attachment membership, Subnet references, primary selection, and OOB static address cannot be changed after VM creation.
- [ ] Regression coverage confirms that unsupported deployments retain the OSAC-1435 single-NIC and default-networking behavior and that CaaS and BMaaS behavior is unchanged.

## Assumptions

- The Provider Admin has an authoritative reservation workflow for OOB static IPv4 addresses. The Subnet API currently carries a CIDR but does not define a gateway or address-reservation resource.
- The first managed VM template supports guest network-data injection for the supported guest OS. Any Windows template must provide an equivalent Sysprep/Unattend path before it is considered supported for OOB static addressing. Routed OOB client prefixes are provider-supplied and must not replace the primary default route.
- The configured K8s manager can select each primary VM namespace that needs the shared OOB NAD without making unrelated tenant namespaces eligible.

## Related Work

- **PR #393:** Provides the proposed NetworkClass network_types mapping, VirtualNetwork network_type, SubnetNetworkBinding, and generic VM composition. This PRD adds the provider-managed OOB operating model and static address.
- **OSAC-4291 fabric-output handoff:** Provides the existing ConfigMap and AAP dependency pattern used for fabric output consumed by the K8s manager.
- **Localnet K8s manager:** An implementation by OSAC or the provider is required before the OOB role can advertise multi-NIC support.
- **OSAC-1435:** Defines the VMaaS single-attachment and default-networking baseline.
- **OSAC-5557:** Defines single-NIC compatibility corrections that must continue to pass.

---

## Provenance

Authored: revise @ prd 0.8.0 - 7efcedb, workspace design/OSAC-6121-vmaas-multi-nic @ 8a1340b (30 behind origin/main, dirty)

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"prd","workflow_version":"0.8.0","ai_workflows":"7efcedb","source_repo":"8a1340b (dirty)","source_repo_branch":"design/OSAC-6121-vmaas-multi-nic","commits_behind_main":30,"commits_ahead_main":0,"main_ref":"main","phases":["revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":true} -->
