# VMaaS multi-NIC with a NetworkClass capability

| Field | Value |
|---|---|
| Author(s) | Vladik Romanovsky |
| Jira | https://redhat.atlassian.net/browse/OSAC-6121 |
| Date | 2026-10-14 |
| Target milestone | OSAC-6121 increment; release TBD |

## Problem Statement

VMaaS tenants can create a ComputeInstance with an omitted or single tenant network attachment. The sole attachment supplies the VM's primary network; an omitted attachment uses tenant defaults. Deployments differ in whether they can provision multiple guest interfaces, yet the current single-attachment contract cannot express that difference. A tenant needing a VM on two subnets in one VirtualNetwork cannot use a capable deployment, while accepting multiple attachments everywhere would send unsupported configurations into provisioning.

## In Scope

- VMaaS ComputeInstances on connected, IPv4 deployments using the existing single networking hub and VirtualNetwork model.
- A Cloud Infrastructure Admin can make VMaaS multi-NIC availability visible through the provider-managed NetworkClass. The capability is derived from the relevant networking managers; tenants cannot enable it.
- When the capability is enabled, a Tenant User can create a VM with two to eight attachments to distinct supported subnets of one VirtualNetwork and explicitly select one primary attachment.
- When the capability is false or unset, zero or one attachment works as before and a request with more than one fails before the VM is stored or provisioned.
- The primary attachment determines VM placement, default route, and the VM address used for inbound ExternalIP access. Outbound traffic follows that route through the VirtualNetwork's NATGateway when one is configured.
- Each configured attachment and its assigned IP are visible in ComputeInstance status. Invalid ownership, readiness, subnet, SecurityGroup, and primary combinations fail before provisioning.
- API and CLI creation, readback, error messages, documentation, and deployed end-to-end coverage for enabled and disabled paths.

## Out of Scope

- CaaS and BMaaS attachment behavior. A CaaS VM worker's pod network plus one tenant attachment is not this VMaaS multi-tenant-attachment use case.
- Attachments across VirtualNetworks or networking hubs; IPv6, dual-stack, and disconnected deployments.
- Adding, removing, switching the primary, or changing a subnet attachment on an existing VM. These changes require delete and recreate; hot-plug is follow-up work.
- Tenant overrides of provider-advertised capabilities.

## User Stories

### Tenant User

- As a Tenant User, I want to create a VM with a primary application subnet and a secondary service subnet in the same VirtualNetwork, so the VM can use both networks while keeping a predictable default route.
- As a Tenant User, I want to see the subnet and assigned IP for each VM interface, so I can configure and troubleshoot workloads on both networks.
- As a Tenant User, I want a clear rejection before creation when my deployment lacks multi-NIC support or my requested subnets and SecurityGroups are invalid, so I can correct the request without a failed VM to clean up.
- As a Tenant User, I want a VM created with no attachment or one attachment to retain today's defaults and external access behavior, so existing automation continues to work.

### Cloud Infrastructure Admin

- As a Cloud Infrastructure Admin, I want the NetworkClass to report whether the configured managers support VMaaS multi-NIC, so tenants are offered multiple attachments only on capable deployments.
- As a Cloud Infrastructure Admin, I want multi-NIC VMs to use only subnets and SecurityGroups from the tenant's VirtualNetwork, so enabling the capability preserves network isolation.

## Functional Requirements

1. **Provider capability.** The deployment NetworkClass reports a provider-controlled VMaaS multi-NIC capability derived from manager declarations. An absent declaration is false. Tenant requests cannot set this capability.
2. **Disabled behavior.** With the capability false or unset, creation accepts an omitted or single attachment under the existing rules and rejects two or more attachments before persistence. The same rule applies to API and CLI requests.
3. **Enabled cardinality.** With the capability true, creation accepts up to eight attachments. An omitted or single attachment retains existing defaulting and implicit-primary behavior. A request above eight fails before persistence.
4. **Primary selection.** A request with two or more attachments must mark exactly one primary. That subnet determines placement and the default route; the remaining attachments do not introduce competing default routes. A single attachment is primary even when the optional marker is omitted or false.
5. **Network validation.** Every attachment resolves to a distinct, ready subnet owned by the same tenant and project as the VM. All attached subnets belong to one ready VirtualNetwork using the capable NetworkClass. Each attached SecurityGroup is ready, tenant-owned, and belongs to its attachment's VirtualNetwork. Existing single-attachment field defaulting continues; missing SecurityGroups use tenant defaults only under the existing default-VirtualNetwork rule.
6. **External access.** An ExternalIPAttachment targeting a multi-NIC VM uses the discovered IP of its primary attachment for inbound DNAT. The VirtualNetwork NATGateway remains VN-scoped; VM outbound traffic uses the primary default route and its source address. Auto-provisioned ExternalIP behavior and cleanup remain available.
7. **Status.** A tenant can read the configured attachments and the discovered IP address for each interface. The primary attachment is identifiable, and the existing single primary IP remains consistent with it.
8. **Immutability.** After creation, the attachment set, subnet references, and primary designation are fixed. Existing SecurityGroup update behavior is preserved. Start, stop, restart, and deletion do not change attachment topology.
9. **Compatibility.** The existing repeated attachment shape is extended. No new tenant network object or replacement attachment field is introduced. Existing default-networking and single-NIC creation paths retain their behavior when the capability is off.

## Acceptance Criteria

- [ ] A Cloud Infrastructure Admin configures managers that advertise VMaaS multi-NIC and sees the capability enabled on the NetworkClass; when a required manager does not advertise it, the NetworkClass reports it disabled.
- [ ] On an enabled NetworkClass, a Tenant User creates a VM with two ready subnets in one VirtualNetwork, marks one primary, and sees both guest interfaces and their assigned addresses. The selected primary supplies the default route.
- [ ] The same enabled deployment accepts eight attachments and rejects nine. Requests with no primary or two primaries are rejected before a ComputeInstance is stored.
- [ ] On a disabled or unset NetworkClass, a two-attachment request fails before persistence, while omitted, default-networking, and single-attachment VM creation still succeed.
- [ ] A request using another tenant's subnet or SecurityGroup, an unready subnet or SecurityGroup, a mismatched VirtualNetwork, or the same subnet twice fails before provisioning with an actionable error.
- [ ] An ExternalIPAttachment to a multi-NIC VM reaches the primary attachment's discovered IP; outbound traffic follows the primary route through the VirtualNetwork NATGateway when configured.
- [ ] A Tenant User can inspect a VM's per-attachment IPs and identify its primary; changing the attachment set, subnet, or primary after creation is rejected, and existing SecurityGroup update rules are unchanged.
- [ ] Automated deployed coverage exercises the enabled and disabled paths, secondary network availability in the VM namespace, invalid combinations, ExternalIP/NAT behavior, and single-NIC/default regression.

## Assumptions and Risks

- The networking managers and OpenShift Virtualization environment can provide a primary VM network plus reachable secondary networks on the same hosting cluster. The design must define how a secondary network attachment is made available in the VM namespace without selecting a second primary CUDN there.
- Capability advertisement must reflect the full provisioning path. If it is enabled before the secondary-network path is ready, VM creation could pass validation and fail during provisioning.

## Related Work

- [OSAC-1435 VMaaS Networking](../OSAC-1435-vmaas-networking/design.md) defines the single-attachment baseline extended here.
- [OSAC-5557 Single-NIC Contract Corrections](https://redhat.atlassian.net/browse/OSAC-5557) preserves defaulting and validation behavior that must regress cleanly.
- [OSAC-5288 VMaaS multi-subnet network support](https://redhat.atlassian.net/browse/OSAC-5288) is related work, not a hard dependency for this capability-gated increment.

---

## Provenance

Committed: commit @ prd 0.8.0 - 7efcedb, workspace main @ d165396

> Authoring phases not recorded this session (commit-time snapshot only).

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"commit_only","workflow":"prd","workflow_version":"0.8.0","ai_workflows":"7efcedb","source_repo":"d165396","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["commit","commit"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
