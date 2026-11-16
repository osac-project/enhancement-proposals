# Testplan — OSAC-7436

## Overview

- **Feature:** OSAC-7436 — Tenant networking for VMaaS without a Fabric Manager
- **Total test cases:** 21 (the two BMaaS/CaaS rows under `TC-IS2-01` count separately)
- **Requirements covered:** 8 of 9 behavioral/scope items; IS-9 is documentation-only
- **Interface changes covered:** 6 of 7; IC-7 is documentation-only

The PRD has no FR/NFR identifiers. `IS-1` through `IS-9` below are testplan-only trace keys for the ordered bullets in PRD §In Scope; they do not add or renumber requirements.

| Trace key | PRD source |
|---|---|
| IS-1 | §In Scope, item 1 — Kubernetes-only profile, installer/Helm, Enclave, new install, VMaaS, OCP baseline |
| IS-2 | §In Scope, item 2 — reject BMaaS/CaaS combinations |
| IS-3 | §In Scope, item 3 — provider connected/preconfigured underlay |
| IS-4 | §In Scope, item 4 — tenant resources, SG defaults, unbound deny, ICMP behavior |
| IS-5 | §In Scope, item 5 — one VM Subnet per VirtualNetwork and tenant isolation |
| IS-6 | §In Scope, item 6 — VM attachment readiness, actionable failure, cleanup |
| IS-7 | §In Scope, item 7 — installation-wide ExternalIP protocol/port set |
| IS-8 | §In Scope, item 8 — no-NAT egress denial and NATGateway source address |
| IS-9 | §In Scope, item 9 — provider documentation |

## Test Case Index

| ID | Scenario | IC | Priority |
|---|---|---|---|
| TC-IS1-01 | Kubernetes-only install resolves a K8S-only NetworkClass and preserves its port list | IC-1, IC-2, IC-3 | high |
| TC-IS1-02 | Enclave renders profile and port-pair settings | IC-1, IC-2 | medium |
| TC-IS2-01 | BMaaS and CaaS are rejected with the Kubernetes-only profile (parameterized) | IC-1 | high |
| TC-IS2-02 | Provider networking cannot be disabled for this profile | IC-1 | high |
| TC-IS3-01 | Provider L2 ingress and EgressIP address path meet installation prerequisites | IC-4, IC-5, IC-6 | high |
| TC-IS4-01 | Tenant onboarding creates default networking including NATGateway | IC-4, IC-6 | critical |
| TC-IS4-02 | Tenant-created networks and SecurityGroups preserve authorization and default policy | IC-4 | high |
| TC-IS4-03 | Explicit ICMP-only rules fail while `all` includes ICMP | IC-4 | medium |
| TC-IS5-01 | Only the owner Subnet accepts VM attachment | IC-4 | high |
| TC-IS5-02 | Overlapping VirtualNetworks remain isolated | IC-4 | critical |
| TC-IS6-01 | VM networking becomes Ready only after K8S attachment setup | IC-4 | critical |
| TC-IS6-02 | Failed attachment is actionable and deletion removes owned resources | IC-4 | high |
| TC-IS7-01 | Default TCP/22 ExternalIP ingress works; unlisted ports do not | IC-2, IC-5 | critical |
| TC-IS7-02 | Configured TCP and UDP pairs share one ExternalIP and are SG-limited | IC-2, IC-5 | high |
| TC-IS7-03 | External client source IP is visible to the VM | IC-5 | high |
| TC-IS7-04 | Empty port-pair list disables inbound VM ExternalIP attachment but permits NATGateway use | IC-2, IC-5, IC-6 | medium |
| TC-IS8-01 | Without NATGateway, external egress is blocked without node-IP fallback | IC-6 | critical |
| TC-IS8-02 | With NATGateway, VM egress uses its ExternalIP and replies return | IC-6 | critical |
| TC-IS8-03 | EgressIP node failover preserves the source address and restores egress | IC-6 | high |
| TC-IS8-04 | NATGateway and VM ExternalIPAttachment are exclusive consumers | IC-5, IC-6 | high |

## Coverage Matrix

Each row describes a required boundary. Commands are existing commands when the suite exists; proposed suites are explicitly marked and are not execution-ready.

| Cases | Owner / tier | Harness and execution path | Boundary and prerequisites |
|---|---|---|---|
| TC-IS1-01, TC-IS2-01, TC-IS2-02 | [DEV] osac-installer — Component integration (Helm contract) | From `osac-installer/`: `make helm-networking-test` | Real Helm render/schema validation; no cluster, Fulfillment API, or AAP. Covers allowed profile combinations and actionable template failures. |
| TC-IS1-01 | [DEV] osac-installer — Unit | From `osac-installer/`: `make network-class-step-test` | Fake Fulfillment API. Verifies the install step creates and compares the empty-Fabric/K8S-only NetworkClass input and immutable port list. |
| TC-IS1-01, TC-IS2-01, TC-IS2-02 | [DEV] fulfillment-service — Unit | From `fulfillment-service/`: `ginkgo run --timeout 10m internal/servers` | Validates private NetworkClass combinations and existing tenant-facing APIs. Fulfillment/database are exercised by the component suite; no hub controllers or provider network. |
| TC-IS1-01 | [DEV] osac-operator — Envtest | From `osac-operator/`: `make test` | Real local API server/etcd and NetworkClass CRD; manager registration ConfigMaps are test fixtures and AAP is a recording fake. Verifies standalone K8S resolution and `NetworkManagers.fabric` absence. |
| TC-IS1-02 | [DEV] Enclave — Contract | Enclave plugin/Wizard schema-consumption suite; command and repository are outside this checkout and are not defined here. | Must verify profile selection, the protocol/port pair editor, conditional validation, and schema uptake. **Execution gap:** the local workspace has no Enclave test harness for this field shape. |
| TC-IS3-01 | [QE] Cloud infrastructure qualification — E2E (manual) | Proposed no-Fabric installation preflight; no test-infra profile or command is defined. | Requires actual provider L2 reachability for a MetalLB VIP, an eligible EgressIP node/address, provider return routing, and a reachable external probe. **Execution gap:** owner is identified, but no runnable harness or follow-up ticket exists yet. |
| TC-IS4-01, TC-IS4-02, TC-IS5-01, TC-IS5-02, TC-IS6-01, TC-IS6-02, TC-IS7-01, TC-IS7-02, TC-IS7-03, TC-IS7-04, TC-IS8-01, TC-IS8-02, TC-IS8-03, TC-IS8-04 | [QE] VMaaS networking — E2E | Proposed `tests/e2e/networking/vmaas/test_vmaas_k8s_only_networking.py`; command/test-infra profile not yet defined. Existing baseline `uv run pytest -n 0 -x tests/e2e/networking/vmaas/test_vmaas_networking.py` uses Netris + `cudn_evpn` and does not cover this profile. | New profile must run deployed Fulfillment, operator, AAP, OVN-Kubernetes, MetalLB, KubeVirt, a routed ExternalIP pool, egress-assignable nodes, guest SSH/UDP listeners, and an external traffic probe. No Netris/Fabric Manager should run. **Execution gap:** test-infra provisioning for the no-Fabric profile is not present in the current repo. |
| TC-IS4-03, TC-IS6-01, TC-IS6-02 | [DEV] Fulfillment/operator — Unit and Envtest | Fulfillment: `ginkgo run --timeout 10m internal/servers`; operator: `make test` from `osac-operator/` | Fulfillment validation and real operator API/etcd behavior are covered at separate boundaries; AAP manager results are test doubles. These do not prove deployed guest traffic. |
| TC-IS4-02, TC-IS4-03, TC-IS6-01, TC-IS6-02, TC-IS7-01, TC-IS7-02, TC-IS7-04, TC-IS8-01, TC-IS8-02, TC-IS8-04 | [DEV] osac-aap — Unit and Component integration | From `osac-aap/`: `make test`; extend the network-task playbook component contract with a `k8s_only` target. | Unit tests use Ansible/module doubles. Component integration uses the documented Kind harness and test CRDs; it does not prove a production MetalLB advertisement, EgressIP SNAT, or external return path. The new `k8s_only` target does not yet exist. |
| TC-IS9 | [DEV] OSAC docs — Documentation review | Review the provider guide delivered with the feature; no behavioral test command. | Documentation-only requirement. Must cover install selection, OCP/provider prerequisites, ExternalIP ports, NATGateway behavior, limitations, and troubleshooting. |

## Test Cases

### IS-1: Select and configure the Kubernetes-only profile

#### TC-IS1-01: Installer and NetworkClass select the standalone K8S manager

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2, IC-3 | high | automated |

**Steps:** 1. Render and run the NetworkClass install step with `profile=kubernetesOnly`, empty `fabricManager`, BMaaS/CaaS disabled, once with default TCP/22 and once with an explicit empty port list → 2. Reconcile each NetworkClass against the `k8s_only` registration.
**Expected:** Helm accepts both port-list values; the default is stored as TCP/22 and the explicit empty list stays empty. Each NetworkClass reaches `Ready=True` with a Kubernetes Manager reference and no Fabric Manager reference; `status.networkType` and the Fabric VNI/segment fields remain empty.

#### TC-IS1-02: Enclave presents the same profile and ExternalIP settings

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1, IC-2 | medium | manual |

**Steps:** 1. Select the Kubernetes-only option in Enclave → 2. Save the default TCP/22 pair, then remove all pairs and save again.
**Expected:** The generated installer values select the no-Fabric profile and preserve both the default pair and explicit empty-list settings accepted by Helm. This test is planned; the Enclave harness is not available in this checkout.

### IS-2: Reject incompatible service combinations

#### TC-IS2-01: BMaaS and CaaS cannot be enabled with the Kubernetes-only profile (parameterized)

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1 | high | automated |

##### Steps

1. Render the chart with the Kubernetes-only profile and each parameterized service selection.

##### Expected Results

| Enabled service | Expected result |
|---|---|
| BMaaS | Helm rendering fails and names BMaaS as unsupported by the profile. |
| CaaS | Helm rendering fails and names CaaS as unsupported by the profile. |

#### TC-IS2-02: Provider networking cannot be disabled for this profile

| Interface Change | Priority | Automation |
|---|---|---|
| IC-1 | high | automated |

**Steps:** 1. Render the chart with `profile=kubernetesOnly` and `provisioningEnabled=false`.
**Expected:** Helm rendering fails with a message that the profile requires provider networking to be enabled for ExternalIP and NATGateway provisioning.

### IS-3: Use a connected, preconfigured provider underlay

#### TC-IS3-01: Provider L2 advertisement and EgressIP return path are reachable

| Interface Change | Priority | Automation |
|---|---|---|
| IC-4, IC-5, IC-6 | high | manual |

##### Preconditions

- OpenShift 4.22+ uses OVN-Kubernetes and has the K8S-only profile installed.
- The provider supplies an ExternalIP pool reachable by MetalLB at Layer 2, an eligible EgressIP node/subnet, and an external probe reachable through the provider gateway.

##### Steps

1. Advertise a test `LoadBalancer` Service from the provider pool and probe its VIP from the provider network.
2. Send a VM outbound connection through a ready NATGateway and record the source address at the external probe.

##### Expected Results

- The provider network resolves the Service VIP to a MetalLB-announcing node and reaches its configured service port.
- The external probe observes the NATGateway ExternalIP as the source and the reply reaches the VM.

This is an installation qualification test; the no-Fabric test-infra profile and command are not defined yet.

### IS-4: Preserve tenant network and SecurityGroup behavior

#### TC-IS4-01: Tenant onboarding creates the default network and NATGateway

| Interface Change | Priority | Automation |
|---|---|---|
| IC-3, IC-4, IC-6 | critical | automated |

**Steps:** 1. Create a Tenant when the Kubernetes-only NetworkClass and provider ExternalIPPool are Ready → 2. Wait for `DefaultNetworkingReady`.
**Expected:** The default VirtualNetwork, Subnet, SecurityGroup, ExternalIP, and NATGateway are Ready; the default NATGateway references an Allocated ExternalIP.

#### TC-IS4-02: Tenant-created networks and defaults remain isolated

| Interface Change | Priority | Automation |
|---|---|---|
| IC-4 | high | automated |

**Steps:** 1. Create tenant-owned VirtualNetworks, one Subnet, and SecurityGroups with the same supported rules as the current API → 2. Attach VMs and probe allowed and denied traffic, including an unbound VM pod.
**Expected:** Tenant ownership is enforced; bound VMs follow their selected SecurityGroup rules and unbound workloads remain denied; one tenant cannot reach another tenant's VirtualNetwork.

#### TC-IS4-03: ICMP-only SecurityGroup rules are rejected and `all` includes ICMP

| Interface Change | Priority | Automation |
|---|---|---|
| IC-4 | medium | automated |

**Steps:** 1. Create/update a SecurityGroup with an explicit ICMP-only rule → 2. Repeat with `PROTOCOL_ALL` and probe ICMP within the permitted CIDR.
**Expected:** The explicit ICMP-only request returns `INVALID_ARGUMENT`; the all-protocol rule is accepted and permits ICMP subject to the selected network policy.

### IS-5: Keep the one-VM-Subnet boundary and tenant isolation

#### TC-IS5-01: VM attachment to a non-owner Subnet fails with an actionable limit

| Interface Change | Priority | Automation |
|---|---|---|
| IC-4 | high | automated |

**Steps:** 1. Create two Subnets in one VirtualNetwork → 2. Attach a VM to the non-owner Subnet.
**Expected:** The non-owner Subnet reports VM support false; the ComputeInstance reaches a failed network condition with the documented Subnet-limit message and no VM becomes Ready.

#### TC-IS5-02: Overlapping VirtualNetworks remain isolated

| Interface Change | Priority | Automation |
|---|---|---|
| IC-4 | critical | automated |

**Steps:** 1. Create two VirtualNetworks with the same IPv4 CIDR and one VM-capable Subnet in each → 2. Create VMs with permissive SecurityGroups and probe each other by address.
**Expected:** Each VM reaches only its own VirtualNetwork peers and external permitted destinations; packets do not reach the overlapping-address VM in the other VirtualNetwork.

### IS-6: Report VM attachment readiness, failure, and cleanup

#### TC-IS6-01: VM networking becomes Ready after CUDN attachment succeeds

| Interface Change | Priority | Automation |
|---|---|---|
| IC-4 | critical | automated |

**Steps:** 1. Create a VM with a valid K8S-only Subnet and SecurityGroup → 2. Wait for the Kubernetes `apply_network_attachment` task and VM address discovery.
**Expected:** `NetworkReady=True` is reported only after the namespace/network attachment succeeds and the VM has its tenant IPv4 address; the VM has one primary `l2bridge` interface.

#### TC-IS6-02: Attachment failure is visible and deletion removes owned resources

| Interface Change | Priority | Automation |
|---|---|---|
| IC-4 | high | automated |

##### Steps

1. Inject a retryable CUDN/NetworkPolicy API failure and confirm the VM is not Ready.
2. Allow the retry to succeed, then delete the VM and wait for its NetworkAttachment cleanup.

##### Expected Results

- During the retryable failure, the VM networking condition remains not Ready and exposes the fixed actionable status message; raw task diagnostics remain administrator-visible.
- After deletion, the VM pod binding is removed and no NetworkAttachment-owned policy/resource remains.

### IS-7: Enforce installation-wide ExternalIP port pairs

#### TC-IS7-01: Default TCP/22 is exposed and other ports are not

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2, IC-5 | critical | automated |

**Steps:** 1. Use the default TCP/22 profile and attach an ExternalIP to a VM → 2. Probe TCP/22 and an unlisted TCP port from an allowed external client.
**Expected:** TCP/22 reaches the VM when its SecurityGroup permits it; the unlisted port has no Service listener and does not reach the VM.

#### TC-IS7-02: Configured TCP and UDP pairs share one ExternalIP

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2, IC-5 | high | automated |

**Steps:** 1. Install with TCP/22 and UDP/53 pairs → 2. Attach one ExternalIP and probe both ports plus an unlisted UDP port.
**Expected:** The TCP and UDP Services share the assigned ExternalIP and reach the VM on their configured ports; the unlisted UDP port is not exposed.

#### TC-IS7-03: External client source IP is preserved and SecurityGroups can narrow access

| Interface Change | Priority | Automation |
|---|---|---|
| IC-5 | high | automated |

**Steps:** 1. Attach a VM ExternalIP with `externalTrafficPolicy: Local` and a SecurityGroup permitting one client CIDR → 2. Connect from an allowed and a denied source.
**Expected:** The VM observes the allowed client's original source IP; the allowed connection reaches the VM and the denied source does not.

#### TC-IS7-04: Empty port-pair list disables inbound VM ExternalIP attachment but permits NATGateway use

| Interface Change | Priority | Automation |
|---|---|---|
| IC-2, IC-5, IC-6 | medium | automated |

**Steps:** 1. Install with `externalIPProtocolPorts: []` → 2. Allocate an ExternalIP and request an attachment to a VM → 3. Inspect the attachment condition and MetalLB Services → 4. Delete the failed attachment and create a NATGateway using the same ExternalIP.
**Expected:** The installation accepts the empty list; the VM ExternalIPAttachment fails with an actionable status, no MetalLB Service or active consumer slot is created, and the ExternalIP remains allocated. After the failed attachment is deleted, the NATGateway can claim the address and create its EgressIP.

### IS-8: Enforce NATGateway outbound behavior

#### TC-IS8-01: VM egress outside its VirtualNetwork is blocked without NATGateway

| Interface Change | Priority | Automation |
|---|---|---|
| IC-6 | critical | automated |

##### Preconditions

- A supported no-NATGateway guard is configured on the target primary Layer 2 CUDN.
- The provider supplies test destinations for one provider-infrastructure connection allowed by the existing SecurityGroup defaults and one connection denied by those defaults.

**Steps:** 1. Create a custom VirtualNetwork and a VM with effective SecurityGroup rules that allow an internal peer, a public probe, and one provider-infrastructure destination, but do not allow a second provider-infrastructure destination; omit the NATGateway → 2. Probe the internal peer, the public destination over TCP and ICMP, and both provider-infrastructure destinations.
**Expected:** Internal traffic follows SecurityGroup rules; the public probe is blocked for TCP and ICMP without a node-IP source leak even though the SecurityGroup permits it. The allowed provider-infrastructure connection succeeds, while the unmatched provider destination remains blocked even if the egress guard has a broader provider-range exception. This test is blocked until §9.1 identifies a supported guard and verifies policy precedence.

#### TC-IS8-02: NATGateway egress uses its ExternalIP and replies return

| Interface Change | Priority | Automation |
|---|---|---|
| IC-6 | critical | automated |

##### Preconditions

- The test can temporarily leave the cluster with no EgressIP-assignable nodes, then make an eligible provider-connected node available.

**Steps:** 1. Create a VM with its primary `l2bridge` interface and a NATGateway while no egress node is eligible → 2. Probe guest egress and wait for the NATGateway condition → 3. Make an eligible node available and wait for EgressIP assignment and NATGateway readiness → 4. Send a connection from the guest OS to an external probe → 5. Recreate the VMI or `virt-launcher` pod and repeat the guest connection.
**Expected:** While EgressIP is unassigned, the NATGateway does not become Ready and guest traffic cannot escape using a node-IP source. After assignment, the external probe observes the NATGateway ExternalIP as the source and its response reaches the guest; the same behavior holds after VMI/launcher recreation. A VM SecurityGroup may narrow the permitted egress destinations.

#### TC-IS8-03: EgressIP failover preserves the source address

| Interface Change | Priority | Automation |
|---|---|---|
| IC-6 | high | manual |

##### Preconditions

- The test cluster has two eligible egress nodes on a provider-reachable subnet and a controlled method to make the assigned node unavailable.

##### Steps

1. Establish VM outbound traffic through a NATGateway and record the observed source address.
2. Make the assigned egress node unavailable and open a new connection after OVN reports reassignment.

##### Expected Results

- OVN assigns the same EgressIP address to another eligible node.
- New external connections still use the same NATGateway ExternalIP and replies reach the VM after reassignment.

This test requires a provider-capable failover environment; it is not covered by current VMaaS CI.

#### TC-IS8-04: NATGateway and VM ExternalIPAttachment are exclusive consumers

| Interface Change | Priority | Automation |
|---|---|---|
| IC-5, IC-6 | high | automated |

**Steps:** 1. Allocate one ExternalIP → 2. Concurrently request a NATGateway and a VM ExternalIPAttachment that reference it → 3. Identify the consumer that acquires the claim, then delete it and wait for its EgressIP or Services to be removed → 4. Create the other consumer with the same ExternalIP → 5. Delete that consumer and the ExternalIP.
**Expected:** Exactly one concurrent consumer acquires the ExternalIP; the other fails with an actionable conflict before creating an EgressIP or Service. After the winning consumer is fully cleaned up, the other consumer can acquire the claim. The no-NAT guard is restored before EgressIP removal, and the address claim is released only after all consumers are removed.

## Gaps

### Requirement Coverage Gaps

- **IS-9, provider documentation:** Documentation-only requirement; no behavioral test case applies. Review the published setup and troubleshooting guide for the exact provider prerequisites and limitations.

### Interface Change Coverage Gaps

- **IC-7, provider documentation:** Documentation-only interface change; review it with the provider guide rather than creating a behavior test.

### Execution Readiness Gaps

- The no-Fabric E2E file and test-infra profile are proposed but do not exist. The current `tests/e2e/networking/vmaas/test_vmaas_networking.py` runs Netris + `cudn_evpn`; it cannot prove the no-Fabric K8S-only manager, MetalLB-only ingress, or EgressIP path. Owner: QE/test-infra. No follow-up ticket is recorded in this draft.
- The Enclave Wizard's array-of-object port setting has no test command in this OSAC checkout. Owner: Enclave. The plugin/UI verification path and follow-up ticket remain to be assigned.
- The no-NAT egress guard's support, one-per-namespace ownership, and policy precedence on the target primary Layer 2 CUDN remain unresolved in §9.1; TC-IS8-01 is planned but not implementation-ready.
- EgressIP guest source translation, reply routing, VMI/launcher recreation, and failover are planned in TC-IS8-02/03 but are not established by the existing Fabric-backed suite.

## Summary

| Metric | Count |
|---|---:|
| Total test cases | 21 |
| Critical | 6 |
| High | 12 |
| Medium | 3 |
| Low | 0 |
| Automated | 18 |
| Manual | 3 |
| Requirements with test cases | 8 / 9 (IS-9 is documentation-only) |
| Interface changes with test cases | 6 / 7 (IC-7 is documentation-only) |
