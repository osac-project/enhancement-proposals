# Clarification Log — OSAC-7436

## Status

- Rounds completed: 5
- Rounds asked: 5
- Open gaps: 0
- Exit criteria met: Yes

## Round 1 — Initial VMaaS profile scope

### R1.Q1: Provider setup surface

For the initial VMaaS-only profile, where must a Cloud Infrastructure Admin be able to select and configure the no-Fabric-Manager option: installer/Helm configuration only, or also the Enclave Wizard UI?

#### Answer

Installer/Helm configuration only; no Enclave Wizard UI selection in the initial release. Confirmed in Round 2.

#### Impact

Provider setup and documentation cover the installation configuration surface.

### R1.Q2: Tenant network resources

Current product status: with a Fabric Manager configured, tenants can create VirtualNetworks, Subnets, and SecurityGroups through the networking API. Tenant onboarding also provisions default networking. The accepted contract does not yet support the no-Fabric-Manager profile.

Should the new profile preserve tenant-created VirtualNetworks, Subnets, and SecurityGroups, or initially limit tenants to provider/default networks and groups?

#### Answer

Preserve the existing tenant-facing networking model in the no-Fabric-Manager profile, including tenant-created VirtualNetworks, Subnets, and SecurityGroups. Do not restrict tenants to provider/default networks.

#### Impact

The PRD will retain tenant API and authorization behavior. The Kubernetes-only path must enforce supported tenant SecurityGroup rules and explicitly reject any rule it cannot enforce rather than broadening access.

#### Decision (D1)

Keep tenant-created VirtualNetworks, Subnets, and SecurityGroups available with the same tenant authorization and supported rule semantics in the VMaaS-only profile.

---

### R1.Q3: External connectivity

Current code status: the `metallb_l2` role creates ExternalIPPool, ExternalIP, and ExternalIPAttachment resources through MetalLB L2, but its registration identifies it as a Fabric Manager. The current Kubernetes-only manager contract cannot select it in a deployment with no Fabric Manager. Existing NATGateway tasks also belong to Fabric Manager roles.

Technical feasibility review: OpenShift 4.22 documents EgressIP support for primary Layer2 ClusterUserDefinedNetworks, but this does not establish support for the NATGateway behavior required by this profile. The existing MetalLB service path exposes configured protocol/port pairs. The design must validate the supported inbound path, NATGateway path, and their provider-network prerequisites.

#### Answer

Limit inbound ExternalIP access to an installation-wide, provider-configured set of protocol/port pairs, defaulting to TCP/22. A Cloud Infrastructure Admin configures the set at installation time. Require NATGateway for VM-initiated outbound connectivity in the VMaaS-only profile; replies to permitted inbound ExternalIP connections remain part of the inbound path. The implementation approach is for the design phase.

#### Impact

The PRD includes provider ExternalIPPool, tenant ExternalIP, VM ExternalIPAttachment, and NATGateway in the VMaaS-only profile. Design work must validate the configured inbound protocol/port pairs, outbound NATGateway behavior, and provider address-pool and gateway prerequisites.

#### Decision (D2)

Support inbound ExternalIP access through MetalLB Layer 2 using the installation-wide protocol/port pairs.

#### Decision (D3)

NATGateway is required for VM-initiated outbound connectivity and remains part of default tenant onboarding in this profile. Replies to permitted inbound ExternalIP connections remain part of the inbound path. The implementation approach is for the design.

---

### R1.Q4: Default traffic policy

What should a tenant VM be able to reach before a Tenant Admin configures SecurityGroup rules: deny both ingress and egress by default, or allow outbound traffic while denying unsolicited ingress and cross-tenant traffic?

#### Answer

Use the same default policy as the existing fabric-backed deployment: preserve the provider-configured NetworkClass default SecurityGroup rules and the baseline deny for unbound workloads. Do not add a no-Fabric-Manager-specific default allow or deny policy.

#### Impact

The PRD will require parity with the current configured defaults and enforcement behavior. The existing baseline deny for unbound workloads remains; the configured default SecurityGroup rules continue to determine allowed traffic for attached VMs. This resolves the Feature's default-deny criterion as a baseline-deny requirement, not a new deny-all policy that overrides provider defaults.

#### Decision (D4)

Preserve the current provider-configured default SecurityGroup rules and baseline deny for unbound workloads in the no-Fabric-Manager profile.

Scope note: D3's requirement that a VM without a NATGateway cannot initiate outbound connections outside its VirtualNetwork is separate from the SecurityGroup default policy. Enforcing D3 does not change the configured SecurityGroup rules; when a NATGateway is ready, the existing SecurityGroup rules and provider routing determine permitted outbound destinations. Replies to permitted inbound ExternalIP connections are part of the inbound path and must be validated.

### R1.Q5: Existing deployments

Is the no-Fabric-Manager profile intended for new installations only, or must an existing fabric-backed installation be convertible?

#### Answer

The no-Fabric-Manager profile is for new installations only.

#### Impact

The PRD excludes converting existing fabric-backed installations. The profile is selected at installation time; current deployments keep their existing NetworkClass and manager configuration.

#### Decision (D5)

Support the no-Fabric-Manager profile for new installations only; do not include conversion of existing fabric-backed deployments.

---

## Round 2 — Provider and platform constraints

### R2.Q1: Provider setup surface

Should the no-Fabric-Manager profile be selectable through installer/Helm configuration only, or also through the Enclave Wizard?

#### Answer

Installer/Helm configuration only.

#### Impact

The initial release does not add an Enclave Wizard selection for this profile.

#### Decision (D6)

Initial decision: expose the profile through installer/Helm configuration only. This was superseded by D8 in Round 3.

---

### R2.Q2: Minimum platform version

What minimum OpenShift version should the no-Fabric-Manager VMaaS profile support?

#### Answer

OpenShift 4.22 or newer.

#### Impact

The design must validate that the supported OpenShift baseline can provide the required tenant connectivity and policy behavior, and document provider-network prerequisites.

#### Decision (D7)

Set OpenShift 4.22 as the minimum supported version for this profile.

## Round 3 — Enclave Wizard support

### R3.Q1: No-Fabric-Manager configuration in Enclave

Should Cloud Infrastructure Admins be able to select the no-Fabric-Manager profile through the Enclave Wizard as well as through installer/Helm configuration?

#### Answer

Yes. Provide the same applicable networking options for fabric-less networking through Enclave.

#### Impact

The PRD includes Enclave Wizard support for selecting the no-Fabric-Manager profile and configuring its applicable network settings. Fabric Manager-specific configuration is not required for this profile.

#### Decision (D8)

Expose the no-Fabric-Manager profile and its applicable networking settings in the Enclave Wizard. This supersedes D6.

## Round 4 — VM Subnet boundary

### R4.Q1: Subnets per VirtualNetwork for VMaaS

Should the no-Fabric-Manager VMaaS profile support VM attachments to multiple Subnets in one VirtualNetwork, or carry forward the current single-VM-Subnet limitation?

#### Answer

Carry forward the current VMaaS limit: one VM-capable Subnet per VirtualNetwork. Do not require inter-Subnet VM routing in the no-Fabric-Manager profile.

#### Impact

The PRD no longer promises inter-Subnet routing for VM workloads. The shared networking model can represent multiple Subnet resources and the Fabric Manager-backed design describes routing between them; the current `cudn_evpn` VM path makes only the owner Subnet VM-capable. This profile keeps that VM-facing limit and retains isolation between distinct VirtualNetworks, including overlapping CIDRs.

#### Decision (D9)

Support VM attachments on one Subnet per VirtualNetwork in the VMaaS-only no-Fabric-Manager profile; multi-Subnet VM routing is out of scope.

**Design references:** [Unified Networking — VirtualNetwork](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-1433-unified-networking/design.md#virtualnetwork) and [Network Manager contract — Kubernetes Manager tasks](https://github.com/osac-project/enhancement-proposals/blob/main/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#osac-kubernetes-manager-tasks-osac-internal).

## Round 5 — ExternalIP protocol and port exposure

### R5.Q1: ExternalIP exposure policy

Should an ExternalIP expose all protocols and ports, or a configurable set of protocol/port pairs? If configurable, who sets the list and at what scope?

#### Answer

Use a non-empty, installation-wide protocol/port set for inbound VM ExternalIP attachments. The default is TCP/22, matching current behavior. A Cloud Infrastructure Admin configures the set during installation through installer/Helm or the Enclave Wizard. It applies to every VM ExternalIP attachment in the installation; tenant SecurityGroups may further restrict traffic, but tenants cannot add pairs or set per-ExternalIP overrides. An empty list is invalid. ICMP is not exposed through this port-based setting.

#### Impact

The PRD limits inbound VM ExternalIP reachability to the installation's configured protocol/port set. Tenants attach ExternalIPs and use SecurityGroups within that provider-defined limit; the same set applies uniformly to every VM ExternalIP attachment in the installation.

#### Decision (D10)

Configure one non-empty provider-wide set of protocol/port pairs for VM ExternalIP attachments per installation, defaulting to TCP/22. The Cloud Infrastructure Admin sets it at installation time; an empty set and tenant or per-ExternalIP overrides are out of scope.

## Remaining Gaps

None for PRD scope. The design must validate supported implementation paths for inbound ExternalIP and NATGateway connectivity, including the target OpenShift version, address-pool capacity, provider routing, and reply-path requirements.
