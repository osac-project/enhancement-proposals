# Clarification Log — OSAC-7436

## Status

- Rounds completed: 3
- Rounds asked: 3
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

Technical feasibility review: OpenShift 4.22 documents EgressIP support for primary Layer2 ClusterUserDefinedNetworks. Its EgressIP limitations include requiring a default gateway for Layer2 UserDefinedNetwork CRs, not supporting Google Cloud for that path, and forwarding through only one gateway. OVN-Kubernetes' Layer2 UDN design uses a transit switch connected to each node's gateway router; traffic is steered to the selected egress node, where the gateway router SNATs it to the EgressIP. See the [OpenShift 4.22 support matrix](https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/multiple_networks/index), the [OVN-Kubernetes UDN design](https://github.com/ovn-kubernetes/ovn-kubernetes/blob/master/docs/okeps/okep-5193-user-defined-networks.md), and the [OVN-Kubernetes v1.2.0 release notes](https://github.com/ovn-kubernetes/ovn-kubernetes/releases/tag/v1.2.0).

#### Answer

Revive inbound ExternalIP support through MetalLB L2 for the VMaaS-only profile. NATGateway should be implemented for outbound SNAT; the user suspects an OVN transit router is needed.

#### Impact

The PRD includes provider ExternalIPPool, tenant ExternalIP, VM ExternalIPAttachment, and NATGateway lifecycles in the Kubernetes-only VMaaS profile. OpenShift 4.22 documents EgressIP for primary Layer2 CUDNs, and the OVN-Kubernetes UDN design describes a transit-router path for Layer2 egress. This is a promising design candidate, not evidence that OSAC currently supports NATGateway without a Fabric Manager. Design work must validate the target version, VM guest traffic selection, gateway and address-pool prerequisites, and exclusive address ownership between MetalLB and EgressIP.

#### Decision (D2)

Revive inbound ExternalIP support through MetalLB Layer 2 for the Kubernetes-only VMaaS profile.

#### Decision (D3)

NATGateway is in scope and must be implemented for the Kubernetes-only VMaaS profile. The design must validate an OVN-Kubernetes EgressIP/transit-router implementation and document its platform and underlay prerequisites.

---

### R1.Q4: Default traffic policy

What should a tenant VM be able to reach before a Tenant Admin configures SecurityGroup rules: deny both ingress and egress by default, or allow outbound traffic while denying unsolicited ingress and cross-tenant traffic?

#### Answer

Use the same default policy as the existing fabric-backed deployment: preserve the provider-configured NetworkClass default SecurityGroup rules and the baseline deny for unbound workloads. Do not add a no-Fabric-Manager-specific default allow or deny policy.

#### Impact

The PRD will require parity with the current configured defaults and enforcement behavior. The existing baseline deny for unbound workloads remains; the configured default SecurityGroup rules continue to determine allowed traffic for attached VMs. This resolves the Feature's default-deny criterion as a baseline-deny requirement, not a new deny-all policy that overrides provider defaults.

#### Decision (D4)

Preserve the current provider-configured default SecurityGroup rules and baseline deny for unbound workloads in the no-Fabric-Manager profile.

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

The design must target a version whose OVN-Kubernetes supports EgressIP for the selected primary Layer2 CUDN topology and validate the provider's underlay prerequisites.

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

## Remaining Gaps

None for PRD scope. The design must still validate the OVN-Kubernetes EgressIP path for the VM guest network, NAT ExternalIP ownership handoff from MetalLB, and the Layer2 underlay/default-gateway prerequisites.
