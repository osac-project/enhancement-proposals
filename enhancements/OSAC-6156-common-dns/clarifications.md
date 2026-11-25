# Clarification log for OSAC-6156

## Status

- Three clarification rounds are complete. The author approved the four Round 3 decisions after the pre-draft audit.
- Following PRD review, the author confirmed provider-operated BIND as the first VM backend to qualify under D8. The design still needs to demonstrate the VM integration.
- The [working PRD](prd.md) covers D1 through D12. D7 records private-zone visibility and D8 records the first-release criterion.

The [Feature](https://redhat.atlassian.net/browse/OSAC-6156) records common publication and a workload resolver as distinct goals. The networking working-group lead confirmed that VMaaS is the first service implementation and that VM naming and ExternalIP naming can each be configured per tenant. The Feature lists tenant-visible ExternalIP names as a later deliverable.

## Round 1 · What the first VM delivery does for a tenant

### R1.Q1 · Which address does a VM name identify?

When VM naming is enabled, should the VM's FQDN always identify its verified primary tenant-network IPv4 address, including after an ExternalIP is attached, detached, or replaced?

#### Answer

Yes. The author selected the internal VM name first and a separate name for the ExternalIP resource in a later increment.

#### Impact

A tenant can keep the same name in an internal job when the VM's external connectivity changes. In the outside-client use case, the client looks up the allocated ExternalIP, which can be privately routed or internet-routable. The guest needs no DNS access for that lookup. OSAC writes the record and the provider controls which clients can query the zone. This supersedes the previous draft's policy for switching the answer to a single VM name.

#### Decision (D1)

When VM naming is enabled for a tenant, a VM's managed FQDN resolves to its verified primary tenant-network IPv4 address. Attaching, replacing, or detaching an ExternalIP leaves the VM name and its internal DNS answer unchanged.

ExternalIP naming has a separate per-tenant setting. With it enabled on its own, OSAC publishes only the ExternalIP name for this VM workflow. Privately routed ExternalIPs use private DNS. An internet-facing ExternalIP gets a public name only if the provider explicitly selects a public zone.

While ExternalIP naming is enabled, a detached allocation keeps its published name. For example, if a tenant moves an ExternalIP from VM A to VM B, the same name resolves to the same address before, during and after the move. If VM A gets a different ExternalIP, that allocation has its own name. Releasing either allocation triggers withdrawal of its own managed record.

Turning ExternalIP naming off withdraws the tenant’s OSAC-owned ExternalIP records for attached and detached allocations alike. Allocations, attachments and internal VM names are preserved. Administrators can see pending, failed or unconfirmed cleanup, and cleanup resumes automatically when DNS access returns. Re-enabling naming publishes the eligible allocations the tenant then holds. Surviving allocations retain their assigned FQDNs, subject to the ownership checks in D4.

---

### R1.Q2 · What happens when a tenant first gets VM naming?

Should a new tenant start with VM name publication off, with enablement covering both existing and newly created supported VMs?

#### Answer

Yes to both the default and existing-VM coverage. Preserve records owned by others and report conflicts.

#### Impact

A tenant with an existing fleet can enable VM names without recreating its VMs.

#### Decision (D2)

VM name publication starts off for a new tenant. Enabling it enrolls existing and new OSAC-managed VMs on supported tenant networks. The author confirmed the eligibility boundary during PRD review. A VM using only the default cluster network when provider networking is disabled is ineligible. An enrolled VM awaiting verification of its primary tenant-network IPv4 address retains its assigned name with pending publication. [VM networking fallback](https://github.com/osac-project/enhancement-proposals/blob/5a264f8f03d2fae2a9a677c6a19eb513f93113b0/enhancements/OSAC-1435-vmaas-networking/design.md#provider-networking-disabled)

---

### R1.Q3 · Where must a lookup work in the first delivery?

Should a supported VM receive a working resolver on a tenant network without public internet egress, including when the provider has VM naming off and the tenant has zero published resource names? Once a VM name is published, should it resolve from both a permitted tenant VM and an authorized client on the tenant organization's network after DNS access is configured?

#### Answer

The author agreed that resolver delivery applies even when a tenant has zero published resource names. A VM-only tenant can start in this state. Tenant onboarding provisions networking resources, VMaaS can run without CaaS, and the CaaS noop backend skips DNS writes. [Onboarding defaults](https://github.com/osac-project/enhancement-proposals/blob/0da0fabdc29adee21e636c9f82c1393b12764c11/enhancements/OSAC-1433-default-networking/design.md#L98-L106) · [VMaaS-only configuration](https://github.com/osac-project/osac/blob/7a1999595c57b3511f7f52c82346e4121c9a4e41/docs/guides/networking/customer-fabric-manager-guide.md#L1148) · [CaaS DNS backend](https://github.com/osac-project/osac/blob/7a1999595c57b3511f7f52c82346e4121c9a4e41/osac-installer/docs/dns-backend.md#L10-L24)

Recommended qualification: with VM naming off, use the guest's normally configured resolver to look up a fresh, permitted test record with a known answer in a provider-supplied test zone used for OSAC. The fixture exists only for the test. A reply for a known absent name is also legitimate, but negative answers can be cached. The existing VM networking test checks the hosting cluster's Kubernetes Service name, which exercises a different DNS namespace. With naming enabled, verify the actual managed VM FQDN returns the verified internal IPv4 address from both proposed client locations. These are proposed checks based on sources; this research did not exercise a deployed resolver. [VM networking test](https://github.com/osac-project/osac/blob/7a1999595c57b3511f7f52c82346e4121c9a4e41/tests/e2e/networking/vmaas/test_vmaas_networking.py#L831-L851) · [RFC 2308, negative caching](https://datatracker.ietf.org/doc/html/rfc2308#section-5)

#### Impact

This establishes where a successful lookup must be observable. The [accepted networking contract](https://github.com/osac-project/enhancement-proposals/blob/0da0fabdc29adee21e636c9f82c1393b12764c11/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#48-addressing) assigns DNS distribution to the DHCP owner at installation scope. Which resolver serves VM queries and how it is reached belong to design. A workload without internet egress can exist in a connected OSAC deployment.

#### Decision (D3)

Every VM on a supported tenant network receives a working DNS resolver, including when managed VM naming is disabled for the tenant. When a record is published in an OSAC zone the VM is allowed to query, the VM can resolve it without public internet access.

## FQDN convention for review

The author requested a concrete naming proposal that protects tenants and projects from interfering with each other's records. The [PRD](prd.md#in-scope) gives the proposed format and the observable ownership rules. The label order and the way OSAC represents a full project identity are open for design validation.

OSAC's resource naming contract distinguishes tenant, project, resource type and immutable name. A project can be the tenant default or part of a hierarchy. For example, both `research.prod` and `finance.prod` can have a VM named `web`. Using just `prod` would lose the distinction. A tenant's login email domain also does not establish authority to write DNS records there. [Resource name scopes](https://github.com/osac-project/enhancement-proposals/blob/0da0fabdc29adee21e636c9f82c1393b12764c11/enhancements/OSAC-1061-resource-names/prd.md#uniqueness-boundaries) · [Project metadata](https://github.com/osac-project/osac/blob/7a1999595c57b3511f7f52c82346e4121c9a4e41/proto/private/osac/private/v1/metadata_type.proto#L91-L107) · [Tenant email domains](https://github.com/osac-project/osac/blob/7a1999595c57b3511f7f52c82346e4121c9a4e41/proto/private/osac/private/v1/tenant_type.proto#L43-L58)

The preferred spelling puts the recognizable resource name first. The OpenShift ExternalDNS Operator's documented ownership format adds `external-dns-a-` to the first label for an A record. That leaves 48 characters for the resource name in that position, while OSAC permits 63. A short leading kind label is one alternative for design to evaluate. Qualification must cover the complete record and ownership names at supported lengths, including the provider suffix. Other cases include the default project, identically named nested projects, simultaneous publication across scopes, and a delayed cleanup after name reuse. [DNS size limits](https://www.rfc-editor.org/rfc/rfc1035.html#section-2.3.4) · [ExternalDNS Operator ownership names](https://github.com/openshift/external-dns-operator#length-of-the-domain-name)

## Round 2 · The first VM delivery

The [earlier VM PRD](https://github.com/osac-project/enhancement-proposals/pull/445) provides the lifecycle and cleanup precedents. The [Feature](https://redhat.atlassian.net/browse/OSAC-6156) records the broader DNS offering and the earlier request for OpenShift ExternalDNS.

### R2.Q1 · Which part of the FQDN convention is a product promise?

What can users rely on when two resources share a name, and which part of the FQDN spelling should design validate?

#### Answer

The author prefers the resource name first, as in `web.vm.build.north.cloud.example`. The kind label distinguishes a VM named `web` from another resource kind named `web` in the same project. The example shows the preferred order while design checks the supported integration.

#### Impact

Tenants and projects can reuse familiar resource names in a shared zone. A user managing one resource cannot claim, redirect or remove another owner's record. Design must preserve these guarantees for valid OSAC names, including 63-character VM names.

#### Decision (D4)

Managed resource names must be stable, discoverable and collision-free across resource kinds, projects and tenants. OSAC must preserve other owners' records. Use resource-name-first examples in the PRD. The exact published spelling remains subject to design qualification.

---

### R2.Q2 · What happens to a stopped VM's DNS record?

Should a published name continue resolving while the VM is stopped if its verified primary IPv4 address remains assigned?

#### Answer

Yes. The address assignment determines whether the record stays published.

#### Impact

Runtime IP status can be empty for a stopped VM. Design must distinguish a confirmed release from a gap in reporting. [VM networking design](https://github.com/osac-project/enhancement-proposals/blob/0da0fabdc29adee21e636c9f82c1393b12764c11/enhancements/OSAC-1435-vmaas-networking/design.md#L386-L393)

#### Decision (D5)

First publication waits for a verified primary internal IPv4 assignment. A previously published record persists across a stop while that assignment holds. OSAC withdraws a released address and publishes a verified replacement under the same FQDN.

---

### R2.Q3 · Do the earlier disablement and cleanup rules carry forward?

When the provider disables and later re-enables VM naming for a tenant, what happens to its records, VMs and resolvers?

#### Answer

Carry forward withdrawal on disablement, restoration on re-enablement, and administrator visibility into unfinished cleanup, including after VM deletion.

#### Impact

A DNS outage can delay a DNS change while VM use and deletion proceed. Completion reflects what the integration can confirm. A resolver may still return an earlier cached answer.

#### Decision (D6)

Disabling tenant VM naming withdraws only that tenant's OSAC-owned VM records and preserves resolver service. Re-enabling covers every eligible VM then present, restores previously assigned names for surviving VMs, and publishes current verified addresses. Otherwise usable VMs remain available and deletion completes independently of DNS cleanup. Administrators can see pending, failed or unconfirmed cleanup and retry status after the VM disappears.

During PRD review the author confirmed that tenants can tell when naming is off in the VM UI, CLI and API. When naming is enabled, they can see each enrolled VM's assigned FQDN and whether publication is pending, published or failed.

After DNS access returns, unfinished cleanup resumes automatically. Cleanup completes when the integration confirms that the deleted VM’s mapping is gone from authoritative DNS or verifies that a replacement VM owns the record. An identical FQDN and IPv4 address alone cannot establish which VM owns it. When ownership is unclear, OSAC preserves the record and keeps cleanup visible as unconfirmed.

Qualification with BIND covers deletion during an outage in a shared zone. It must show that a verified replacement using the same FQDN and IPv4 address keeps its record throughout cleanup and that unrelated records and CaaS endpoints are preserved.

---

### R2.Q4 · Does the first delivery cover lookups from the tenant's own network?

Should a permitted client on the organization's network also be able to resolve a published VM FQDN once the provider supplies DNS access and the Tenant Admin configures the organization's DNS?

#### Answer

Yes. The author asked whether project membership implies separate DNS visibility. The Feature scopes VM publication to the tenant and calls for resolution from the organization's network. It specifies provider DNS access and leaves per-VirtualNetwork private zones outside this delivery. The reviewed contracts establish project-scoped resource access and VirtualNetwork traffic isolation. They specify no project-membership check for DNS queries. [Feature scope](https://redhat.atlassian.net/browse/OSAC-6156) · [Project access model](https://github.com/osac-project/osac/blob/7a1999595c57b3511f7f52c82346e4121c9a4e41/proto/private/osac/private/v1/project_type.proto#L26-L37) · [Network manager addressing contract](https://github.com/osac-project/enhancement-proposals/blob/0da0fabdc29adee21e636c9f82c1393b12764c11/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#L375)

#### Impact

Projects in one tenant can share its default subnet and security group. Ordinary network references are scoped to the workload's tenant and project. Separate VirtualNetworks can use overlapping IPv4 ranges even within one tenant. A permitted client can receive an internal DNS answer while lacking a route or permission to connect to that VM. [Workload attachment scope](https://github.com/osac-project/osac/blob/7a1999595c57b3511f7f52c82346e4121c9a4e41/fulfillment-service/internal/servers/network_attachment_resolution.go#L32-L52) · [Cross-project default and non-default cases](https://github.com/osac-project/osac/blob/7a1999595c57b3511f7f52c82346e4121c9a4e41/fulfillment-service/internal/servers/network_attachment_resolution_test.go#L129-L149) · [VirtualNetwork routing and isolation](https://github.com/osac-project/enhancement-proposals/blob/0da0fabdc29adee21e636c9f82c1393b12764c11/enhancements/OSAC-1433-unified-networking/design.md#L343-L347)

#### Decision (D7)

OSAC publishes the VM’s internal IPv4 record only in a provider-designated private DNS zone. A failed write cannot fall back to public DNS. Permitted tenant workloads and authorized clients on the organization’s network receive the same answer after DNS access is configured for each. The Tenant Admin can find the assigned domain and setup instructions.

The provider controls which networks can query the zone. A shared resolver can serve more than one tenant. Project permissions govern who can manage each VM and its records. If a provider requires a tenant’s names to be hidden from another tenant, verify lookup of a known name from both an allowed and an excluded network. Per-project DNS views and OSAC-managed private zones per VirtualNetwork are outside this delivery.

---

### R2.Q5 · Is OpenShift ExternalDNS a release requirement for the first VM delivery?

Can the first VM delivery ship through another supported integration while OpenShift ExternalDNS qualification continues?

#### Answer

Yes. The author confirmed Infoblox as the DNS provider for the requested OpenShift External DNS Operator integration. VM naming can ship once BIND qualifies. [Feature and comment history](https://redhat.atlassian.net/browse/OSAC-6156)

#### Impact

The first delivery needs a demonstrated, supported path end to end. Design records what the OpenShift Operator and operand can support for VM publication and any remaining gaps against the original request.

#### Decision (D8)

The first VM release can ship once the supported BIND path demonstrates private-zone publication, resolution from the intended networks and ownership-safe cleanup end to end. Evaluation of the Operator and operand with Infoblox can continue in parallel. The proposed RFC 2136 implementation covers CaaS endpoints. Design will determine what can be reused for VMs. [CaaS implementation](https://github.com/osac-project/osac/pull/2526)

For Feature completion, evaluate which VM naming workflows the Operator supports with Infoblox. Exercise ExternalIP-only publication with a lookup from a permitted client outside the VirtualNetwork while the guest has no DNS access. Check that releasing the ExternalIP withdraws its record and preserves records owned by others. Record verified workflows and support limits, and track outstanding delivery gaps separately. Once the remaining Feature criteria are met, OSAC-6156 can close even if a gap remains in that integration. CaaS migration is one of the separate deliverables beyond the first VM release.

## Round 3 · Decisions after the November 23 audit

### R3.Q1 · Should VM naming change which hosting-cluster names a guest can resolve?

#### Answer

Keep the current resolver behavior. The requirement is that a guest can use its normally configured resolver to look up permitted OSAC names, including without public internet access.

#### Impact

The existing VM networking test expects a hosting-cluster Kubernetes Service name to resolve. Design can reuse the existing resolver if it meets D3. [VM networking test](https://github.com/osac-project/osac/blob/22cb2778cb6776999a011df548b6d2daed8493fe/tests/e2e/networking/vmaas/test_vmaas_networking.py#L831-L853)

#### Decision (D9)

Design brings resolver visibility back to the working group only if it proposes changing which names tenant VMs can resolve today.

---

### R3.Q2 · What happens if a DNS configuration change would prevent cleanup?

#### Answer

Reject the change, keep the current configuration and tell the administrator which records still need a cleanup path.

#### Impact

For example, a VM can finish deleting while BIND is unavailable. Switching the installation to Route 53 must preserve a way to remove the old BIND record. Rotating credentials while retaining access to the same zone satisfies this rule. A tenant suffix change also has to preserve the stable names promised in D4.

#### Decision (D10)

OSAC rejects a change to its DNS settings if applying it would prevent cleanup of records it already manages, including records awaiting cleanup after VM deletion. The administrator can identify what prevents the change. If the provider revokes OSAC’s access directly in BIND, the administrator can see the cleanup failure and which records still await removal.

A tenant suffix change must preserve assigned names, including those awaiting first publication, and the DNS answers and visibility expected for published names. OSAC rejects the change if it would break these guarantees, even when the old zone remains writable.

---

### R3.Q3 · What happens when a VM reports a different address from its network assignment?

#### Answer

Keep the FQDN stable and surface the conflicting evidence in publication status. Publish a replacement address only after verifying the VM's primary tenant-network IPv4 assignment.

#### Impact

The VM controller can observe a new IP while the network attachment still holds the old binding. A stopped VM enrolled before its first verified address can already have an assigned FQDN while publication is pending. [VM networking contract](https://github.com/osac-project/enhancement-proposals/blob/5a264f8f03d2fae2a9a677c6a19eb513f93113b0/enhancements/OSAC-1435-vmaas-networking/design.md#L384-L391)

#### Decision (D11)

Conflicting address observations leave publication unresolved. The record follows D5 on a confirmed assignment, release or replacement.

---

### R3.Q4 · What must keep working when VM and CaaS DNS share a backend?

#### Answer

CaaS retains its cluster endpoint records and its existing behavior during cluster creation and deletion, including when DNS fails. VM naming keeps its own availability and cleanup rules under D6.

#### Impact

A provider can enable or disable VM naming in a zone that also serves CaaS. Cluster API and ingress names must keep working throughout. BIND and Route 53 are candidates for reuse. The choice of writer and any later CaaS migration belong to design. [CaaS BIND requirements](https://github.com/osac-project/enhancement-proposals/blob/5a264f8f03d2fae2a9a677c6a19eb513f93113b0/enhancements/OSAC-2281-local-dns-backend-bind/prd.md#L25-L45)

#### Decision (D12)

Enabling, disabling or retrying VM DNS preserves existing CaaS endpoint records and cluster lifecycle behavior, including in a shared zone.

## Coordination with the DNSaaS Feature

On November 24 the older DNSaaS Feature was closed as a duplicate of OSAC-6156. The VM-first PRD can proceed under OSAC-6156. CaaS continues to use its existing endpoint DNS during the first delivery. Moving CaaS onto common publication is a later deliverable. [Jira closure comment](https://redhat.atlassian.net/browse/OSAC-3202?focusedCommentId=19735142) · [Active design task](https://redhat.atlassian.net/browse/OSAC-6159)

The older Feature also proposed tenant-managed zones and records through an API and UI, delegation, and per-zone backend or manual management. These remain inputs for future scoping. The older planning Epic and its two tasks closed as duplicates of the active planning work. The UX/UI Epic moved under OSAC-6156 with its existing UX and UI tasks. Their first deliverables cover how tenants find a VM hostname and its publication status, and how tenant administrators find the assigned domain and resolver instructions. [Active planning Epic](https://redhat.atlassian.net/browse/OSAC-6157) · [UX/UI Epic](https://redhat.atlassian.net/browse/OSAC-7528)

## Remaining gaps

Design still needs to qualify the VM publication, lookup and cleanup path with BIND and document the verified VM workflows, limits and gaps for the Operator with Infoblox. ExternalIP naming has its own tenant setting and lifecycle in a later deliverable.
