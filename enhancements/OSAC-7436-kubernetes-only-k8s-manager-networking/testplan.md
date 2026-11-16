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
| TC-IS1-01 | Installer and NetworkClass preserve the immutable K8S-only port list | IC-1, IC-2, IC-3 | high |
| TC-IS1-02 | Enclave renders profile/port settings and rejects BMaaS/CaaS | IC-1, IC-2 | medium |
| TC-IS2-01 | BMaaS and CaaS are rejected with the Kubernetes-only profile (parameterized) | IC-1 | high |
| TC-IS2-02 | Provider networking cannot be disabled for this profile | IC-1 | high |
| TC-IS3-01 | Provider L2 ingress and EgressIP address path meet installation prerequisites | IC-4, IC-5, IC-6 | high |
| TC-IS4-01 | Tenant onboarding creates default networking including NATGateway | IC-4, IC-6 | critical |
| TC-IS4-02 | Tenant-created networks and SecurityGroups preserve authorization and default policy | IC-4 | high |
| TC-IS4-03 | Explicit ICMP-only rules fail while `all` includes ICMP | IC-4 | medium |
| TC-IS5-01 | Only the owner Subnet accepts VM attachment | IC-4 | high |
| TC-IS5-02 | Overlapping VirtualNetworks remain isolated | IC-4 | critical |
| TC-IS6-01 | VM networking becomes Ready only after K8S attachment and address discovery | IC-4 | critical |
| TC-IS6-02 | Failed attachment is actionable and deletion removes owned resources | IC-4 | high |
| TC-IS7-01 | Default TCP/22 ExternalIP ingress works; unlisted ports do not | IC-2, IC-5 | critical |
| TC-IS7-02 | Configured TCP and UDP pairs share one ExternalIP and are SG-limited | IC-2, IC-5 | high |
| TC-IS7-03 | External client source IP is visible to the VM | IC-5 | high |
| TC-IS7-04 | Empty port-pair list disables inbound VM ExternalIP attachment but permits NATGateway use | IC-2, IC-5, IC-6 | medium |
| TC-IS8-01 | Without NATGateway, external egress is blocked without node-IP fallback | IC-6 | critical |
| TC-IS8-02 | With NATGateway, VM egress uses its ExternalIP and replies return | IC-6 | critical |
| TC-IS8-03 | EgressIP node failover preserves source and prevents node-IP leakage | IC-6 | high |
| TC-IS8-04 | ExternalIP claims are unique per address and consumers are exclusive | IC-5, IC-6 | high |

## Coverage Matrix

Each row describes a required boundary. Commands are existing commands when the suite exists; proposed suites are explicitly marked and are not execution-ready. E2E CRUD follows the existing `GRPCClient` wrappers (`create_virtual_network`, `create_subnet`, `create_security_group_with_rules`, `create_external_ip`, `create_external_ip_attachment`, and `create_nat_gateway`) and `stack.create_vm`; tenant creation uses the existing tenant fixture. Hub-object state is read through `K8sClient` helpers. These wrappers call the Fulfillment API.

| Cases | Owner / tier | Harness and execution path | Boundary and prerequisites |
|---|---|---|---|
| TC-IS1-01, TC-IS2-01, TC-IS2-02 | [DEV] osac-installer — Component integration (Helm contract) | From `osac-installer/`: `make helm-networking-test` | Real Helm render/schema validation; no cluster, Fulfillment API, or AAP. Uses `global.networking.profile`, `global.networking.externalIPProtocolPorts`, `global.networking.provisioningEnabled`, and `global.services.{bmaas,caas}.enabled`; asserts failures identify the incompatible profile/value. |
| TC-IS1-01 | [DEV] osac-installer — Unit | From `osac-installer/`: `make network-class-step-test` | Fake Fulfillment API. Verifies the install step creates and compares the empty-Fabric/K8S-only NetworkClass input and rejects a changed immutable port list before updating the stored class. |
| TC-IS1-01, TC-IS2-01, TC-IS2-02 | [DEV] fulfillment-service — Unit | From `fulfillment-service/`: `ginkgo run --timeout 10m internal/servers` | Validates private NetworkClass combinations and immutability of the private NetworkClass spec; existing tenant-facing APIs are exercised without hub controllers or provider network. |
| TC-IS1-01 | [DEV] osac-operator — Envtest | From `osac-operator/`: `make test` | Real local API server/etcd and NetworkClass CRD; manager registration ConfigMaps are test fixtures and AAP is a recording fake. Verifies standalone K8S resolution and `NetworkManagers.fabric` absence. |
| TC-IS1-02 | [DEV] Enclave — Contract | Enclave plugin/Wizard schema-consumption suite; command and repository are outside this checkout and are not defined here. | Must verify profile selection, the protocol/port pair editor, conditional BMaaS/CaaS rejection, and schema uptake. **Execution gap:** the local workspace has no Enclave test harness for this field shape. |
| TC-IS3-01 | [QE] Cloud infrastructure qualification — E2E (manual) | Proposed no-Fabric installation preflight; no test-infra profile or command is defined. | Requires actual provider L2 reachability for a MetalLB VIP, an eligible EgressIP node/address, provider return routing, and a reachable external probe. **Execution gap:** owner is identified, but no runnable harness or follow-up ticket exists yet. |
| TC-IS4-01, TC-IS4-02, TC-IS5-01, TC-IS5-02, TC-IS6-01, TC-IS6-02, TC-IS7-01, TC-IS7-02, TC-IS7-03, TC-IS7-04, TC-IS8-01, TC-IS8-02, TC-IS8-03, TC-IS8-04 | [QE] VMaaS networking — E2E | Proposed `uv run pytest -n 0 -x tests/e2e/networking/vmaas/test_vmaas_k8s_only_networking.py`; the file and test-infra profile do not exist yet. Use the current ordered-module pattern in `test_vmaas_networking.py`, including `stack.create_network`, `stack.create_vm`, resource wait helpers, and guest probes, with a no-Fabric external-path fixture. | New profile must run deployed Fulfillment, operator, AAP, OVN-Kubernetes, MetalLB, KubeVirt, a routed ExternalIP pool, egress-assignable nodes, guest listeners, and an external traffic probe. No Netris/Fabric Manager should run. **Execution gap:** the proposed pytest command cannot run until QE/test-infra adds the no-Fabric profile and test module. |
| TC-IS4-03, TC-IS6-01, TC-IS6-02 | [DEV] Fulfillment/operator — Unit and Envtest | Fulfillment: `ginkgo run --timeout 10m internal/servers`; operator: `make test` from `osac-operator/` | Fulfillment validation and real operator API/etcd behavior are covered at separate boundaries. TC-IS6-01 holds a Ready NetworkAttachment with no valid tenant IPv4 in VMI status, then supplies an in-Subnet address to control the address-discovery window. AAP manager results are test doubles. These do not prove deployed guest traffic. |
| TC-IS4-02, TC-IS4-03, TC-IS6-01, TC-IS6-02, TC-IS7-01, TC-IS7-02, TC-IS7-04, TC-IS8-01, TC-IS8-02, TC-IS8-04 | [DEV] osac-aap — Unit and Component integration | From `osac-aap/`: existing `make test`; planned extension of the Ansible collection's network-task component contract with a `k8s_only` target (target name/command TBD). | Unit tests use Ansible/module doubles. The current Kind/component contract is the pattern for the new manager tests; it does not prove a production MetalLB advertisement, EgressIP SNAT, or external return path. **Execution gap:** the `k8s_only` target and follow-up ticket do not exist yet. |
| IS-9 (no behavioral TC) | [DEV] OSAC docs — Documentation review | Review the provider guide delivered with the feature; no behavioral test command. | Documentation-only requirement. Must cover install selection, OCP/provider prerequisites, ExternalIP ports, NATGateway behavior, limitations, and troubleshooting. |

## Test Cases

### IS-1: Select and configure the Kubernetes-only profile

#### TC-IS1-01: Installer and NetworkClass preserve the immutable K8S-only port list

| Interface Change | Priority | Automation | Owner / tier |
|---|---|---|---|
| IC-1, IC-2, IC-3 | high | automated | [DEV] osac-installer — component integration |

**Steps:** 1. Render and run the NetworkClass install step with `global.networking.profile=kubernetesOnly`, `global.networking.fabricManager=""`, `global.networking.provisioningEnabled=true`, `global.services.vmaas.enabled=true`, and `global.services.bmaas.enabled=global.services.caas.enabled=false` → 2. Exercise two fresh installations: omit `global.networking.externalIPProtocolPorts` in one and set it to `[]` in the other → 3. Reconcile each NetworkClass against the `k8s_only` registration → 4. On the default-port installation, rerun the installer step with TCP/22 and UDP/53 in `global.networking.externalIPProtocolPorts`.
**Expected:** Helm accepts both the default and empty list. The hub NetworkClass has `spec.fabricManager=""`, `spec.k8sManager="k8s_only"`, and the corresponding `spec.externalIPProtocolPorts`; `.status.conditions[type=Ready].status=True`, `status.networkManagers.kubernetes` is populated, `status.networkManagers.fabric` is absent, and `status.networkType` is empty. The attempted port-list change fails the installer step with an error naming the immutable port setting; the stored TCP/22 list is unchanged.

#### TC-IS1-02: Enclave renders profile/port settings and rejects BMaaS/CaaS

| Interface Change | Priority | Automation | Owner / tier |
|---|---|---|---|
| IC-1, IC-2 | medium | manual | [DEV] Enclave — contract |

**Steps:** 1. Select the Kubernetes-only option in Enclave and save the default TCP/22 pair → 2. Remove every pair and save the explicit empty list → 3. Enable BMaaS while keeping the Kubernetes-only profile and try to continue → 4. Repeat with CaaS enabled instead of BMaaS.
**Expected:** Valid selections generate `global.networking.profile=kubernetesOnly` and the matching `global.networking.externalIPProtocolPorts` value. Enclave blocks each incompatible service selection before producing installer values, and its actionable message names both `kubernetesOnly` and the selected unsupported service. This manual contract test is planned; the Enclave harness is not available in this checkout.

### IS-2: Reject incompatible service combinations

#### TC-IS2-01: BMaaS and CaaS cannot be enabled with the Kubernetes-only profile (parameterized)

| Interface Change | Priority | Automation | Owner / tier |
|---|---|---|---|
| IC-1 | high | automated | [DEV] osac-installer — component integration |

##### Steps

1. Render the chart with `global.networking.profile=kubernetesOnly`, `global.networking.fabricManager=""`, `global.networking.provisioningEnabled=true`, and `global.services.vmaas.enabled=true`.
2. Parameterize the service flags so exactly one of `global.services.bmaas.enabled` or `global.services.caas.enabled` is `true`; keep the other `false`.

##### Expected Results

| Enabled service | Expected result |
|---|---|
| BMaaS | Helm rendering fails; the message identifies `kubernetesOnly` and BMaaS as an unsupported combination. |
| CaaS | Helm rendering fails; the message identifies `kubernetesOnly` and CaaS as an unsupported combination. |

#### TC-IS2-02: Provider networking cannot be disabled for this profile

| Interface Change | Priority | Automation | Owner / tier |
|---|---|---|---|
| IC-1 | high | automated | [DEV] osac-installer — component integration |

**Steps:** 1. Render the chart with `global.networking.profile=kubernetesOnly`, `global.networking.provisioningEnabled=false`, and both `global.services.bmaas.enabled` and `global.services.caas.enabled` set to `false`.
**Expected:** Helm rendering fails; the message identifies `kubernetesOnly` and `global.networking.provisioningEnabled` and explains provider networking is required for ExternalIP and NATGateway provisioning.

### IS-3: Use a connected, preconfigured provider underlay

#### TC-IS3-01: Provider L2 advertisement and EgressIP return path are reachable

| Interface Change | Priority | Automation | Owner / tier |
|---|---|---|---|
| IC-4, IC-5, IC-6 | high | manual | [QE] provider qualification — manual E2E |

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

| Interface Change | Priority | Automation | Owner / tier |
|---|---|---|---|
| IC-3, IC-4, IC-6 | critical | automated | [QE] VMaaS networking — E2E |

**Steps:** 1. Create a Tenant through the existing Fulfillment tenant-create API after the Kubernetes-only NetworkClass Ready condition is `True` and the provider ExternalIPPool Ready condition is `True` → 2. Poll the Tenant's `DefaultNetworkingReady` condition → 3. Read the tenant's default VirtualNetwork, Subnet, SecurityGroup, ExternalIP, and NATGateway through their existing Get APIs.
**Expected:** `Tenant.status.conditions[type=DefaultNetworkingReady].status=True`; the default VirtualNetwork, Subnet, SecurityGroup, ExternalIP, and NATGateway each have `.status.conditions[type=Ready].status=True`; ExternalIP `.status.state=ALLOCATED`; and the NATGateway's `spec.externalIP` references that ExternalIP. No Fabric Manager resource is created for the tenant.

#### TC-IS4-02: Tenant-created networks and defaults remain isolated

| Interface Change | Priority | Automation | Owner / tier |
|---|---|---|---|
| IC-4 | high | automated | [QE] VMaaS networking — E2E |

**Steps:** 1. Create tenant-owned VirtualNetworks, one Subnet, and SecurityGroups with the same supported rules as the current API → 2. Attach VMs and probe allowed and denied traffic, including an unbound VM pod.
**Expected:** Tenant ownership is enforced; bound VMs follow their selected SecurityGroup rules and unbound workloads remain denied; one tenant cannot reach another tenant's VirtualNetwork.

#### TC-IS4-03: ICMP-only SecurityGroup rules are rejected and `all` includes ICMP

| Interface Change | Priority | Automation | Owner / tier |
|---|---|---|---|
| IC-4 | medium | automated | [DEV] Fulfillment/operator — unit and Envtest |

**Steps:** 1. Create/update a SecurityGroup with an explicit ICMP-only rule → 2. Repeat with `PROTOCOL_ALL` and probe ICMP within the permitted CIDR.
**Expected:** The explicit ICMP-only request returns `INVALID_ARGUMENT`; the all-protocol rule is accepted and permits ICMP subject to the selected network policy.

### IS-5: Keep the one-VM-Subnet boundary and tenant isolation

#### TC-IS5-01: VM attachment to a non-owner Subnet fails with an actionable limit

| Interface Change | Priority | Automation | Owner / tier |
|---|---|---|---|
| IC-4 | high | automated | [QE] VMaaS networking — E2E |

**Steps:** 1. Create two Subnets in one VirtualNetwork → 2. Attach a VM to the non-owner Subnet.
**Expected:** The non-owner Subnet reports VM support `false`; `ComputeInstance.status.conditions[type=NetworkReady].status=False` and its message names the one-VM-Subnet limit. No VM becomes Ready.

#### TC-IS5-02: Overlapping VirtualNetworks remain isolated

| Interface Change | Priority | Automation | Owner / tier |
|---|---|---|---|
| IC-4 | critical | automated | [QE] VMaaS networking — E2E |

**Steps:** 1. Use the existing `stack.create_network` pattern to create VirtualNetwork A and B with the same IPv4 CIDR and one VM-capable Subnet each → 2. Use `stack.create_vm` to create a source VM and a same-network peer VM in each VirtualNetwork, each with a permissive SecurityGroup → 3. Record all four guest IPv4 addresses and select addresses so no VM in A has the same address as a VM in B → 4. Start a unique TCP listener on port 8080 in each peer VM → 5. Run a probe from each source VM to its same-network peer and to the peer VM in the other VirtualNetwork, identifying the destination by its unique response token.
**Expected:** Each source receives the unique response token from its own peer; probes to the other VirtualNetwork's peer time out or are rejected and that peer records no received connection. The recorded destination guest identity proves that an overlapping address did not route the probe back to the source or another local VM. External destinations are not part of this isolation assertion.

### IS-6: Report VM attachment readiness, failure, and cleanup

#### TC-IS6-01: VM networking becomes Ready only after K8S attachment and address discovery

| Interface Change | Priority | Automation | Owner / tier |
|---|---|---|---|
| IC-4 | critical | automated | [DEV] osac-operator — Envtest; [QE] VMaaS networking — E2E |

**Steps:** 1. Create a VM with a valid K8S-only Subnet (`10.20.0.0/24`) and SecurityGroup → 2. Make the VM's NetworkAttachment Ready while its running VMI `status.interfaces` has no valid IPv4 on the `tenant` interface → 3. Reconcile the ComputeInstance and inspect `status.conditions[type=NetworkReady]` → 4. Add `10.20.0.10` to the VMI tenant interface's reported IPs and reconcile again.
**Expected:** After NetworkAttachment Ready but before address discovery, `ComputeInstance.status.conditions[type=NetworkReady].status` is not `True` and its reason is `WaitingForIPAddress`. Once `10.20.0.10` is reported within the Subnet CIDR, `NetworkReady=True` with reason `IPDiscovered`; the VMI has exactly one primary `l2bridge` interface.

#### TC-IS6-02: Attachment failure is visible and deletion removes owned resources

| Interface Change | Priority | Automation | Owner / tier |
|---|---|---|---|
| IC-4 | high | automated | [DEV] osac-aap — component integration |

##### Steps

1. Inject a retryable CUDN/NetworkPolicy API failure and confirm the VM is not Ready.
2. Allow the retry to succeed, then delete the VM and wait for its NetworkAttachment cleanup.

##### Expected Results

- During the retryable failure, `ComputeInstance.status.conditions[type=NetworkReady].status=False` and its message identifies the failed NetworkAttachment setup; raw task diagnostics remain administrator-visible.
- After the retry succeeds, `NetworkReady=True` and the NetworkAttachment Ready condition is `True`.
- After deletion, the VM pod binding is removed and no NetworkAttachment-owned policy/resource remains.

### IS-7: Enforce installation-wide ExternalIP port pairs

#### TC-IS7-01: Default TCP/22 is exposed and other ports are not

| Interface Change | Priority | Automation | Owner / tier |
|---|---|---|---|
| IC-2, IC-5 | critical | automated | [QE] VMaaS networking — E2E |

**Steps:** 1. Use the default TCP/22 profile and create an ExternalIPAttachment for a VM → 2. Inspect the `LoadBalancer` Service and probe TCP/22 and TCP/23 from an allowed external client.
**Expected:** The Service has `spec.ports=[{protocol: TCP, port: 22}]`, the assigned VIP, and `externalTrafficPolicy: Local`. TCP/22 reaches the VM when its SecurityGroup permits it; TCP/23 has no Service listener and does not reach the VM.

#### TC-IS7-02: Configured TCP and UDP pairs share one ExternalIP

| Interface Change | Priority | Automation | Owner / tier |
|---|---|---|---|
| IC-2, IC-5 | high | automated | [QE] VMaaS networking — E2E |

**Steps:** 1. Install with TCP/22, TCP/443, and UDP/53 pairs → 2. Attach one ExternalIP and probe all three ports plus unlisted UDP/54.
**Expected:** One TCP Service contains ports 22 and 443; one UDP Service contains port 53. Both Services set the same assigned `spec.loadBalancerIP`; TCP/22, TCP/443, and UDP/53 reach the VM when permitted by its SecurityGroup, while UDP/54 is not exposed.

#### TC-IS7-03: External client source IP is preserved and SecurityGroups can narrow access

| Interface Change | Priority | Automation | Owner / tier |
|---|---|---|---|
| IC-5 | high | automated | [QE] VMaaS networking — E2E |

**Steps:** 1. Attach a VM ExternalIP with `externalTrafficPolicy: Local` and a SecurityGroup permitting one client CIDR → 2. Connect from an allowed and a denied source.
**Expected:** The VM observes the allowed client's original source IP; the allowed connection reaches the VM and the denied source does not.

#### TC-IS7-04: Empty port-pair list disables inbound VM ExternalIP attachment but permits NATGateway use

| Interface Change | Priority | Automation | Owner / tier |
|---|---|---|---|
| IC-2, IC-5, IC-6 | medium | automated | [DEV] osac-aap — component integration |

**Steps:** 1. Install with `externalIPProtocolPorts: []` → 2. Allocate an ExternalIP and request an attachment to a VM → 3. Inspect the attachment condition and MetalLB Services → 4. Delete the failed attachment and create a NATGateway using the same ExternalIP.
**Expected:** The installation accepts the empty list; the VM ExternalIPAttachment has `Ready=False`, reason `NoConfiguredPorts`, and message `No ExternalIP protocol/port pairs are configured for this installation.` No MetalLB Service or active consumer slot is created, and the ExternalIP remains `ALLOCATED`. After the failed attachment is deleted, the NATGateway can claim the address and becomes Ready after its EgressIP is assigned.

### IS-8: Enforce NATGateway outbound behavior

#### TC-IS8-01: VM egress outside its VirtualNetwork is blocked without NATGateway

| Interface Change | Priority | Automation | Owner / tier |
|---|---|---|---|
| IC-6 | critical | automated | [QE] VMaaS networking — E2E |

##### Preconditions

- A supported no-NATGateway guard is configured on the target primary Layer 2 CUDN.
- The provider supplies test destinations for one provider-infrastructure connection allowed by the existing SecurityGroup defaults and one connection denied by those defaults.

**Steps:** 1. Create a custom VirtualNetwork, one Subnet, and a VM whose SecurityGroup uses `PROTOCOL_ALL` for an internal peer and the public probe, allows one provider-infrastructure CIDR, and omits a second provider-infrastructure CIDR; do not create a NATGateway → 2. Probe the internal peer, public destination over TCP and ICMP, the allowed provider destination, and the denied provider destination → 3. Capture source IPs at the external probes.
**Expected:** The internal peer succeeds. The public TCP and ICMP probes are denied and observe no packet with a node-IP source. The allowed provider destination succeeds under the existing provider configuration; the denied destination remains blocked even if the egress guard has a broader provider-range exception. This critical case is blocked until §9.1 identifies a supported guard and verifies SecurityGroup precedence and fail-closed behavior.

#### TC-IS8-02: NATGateway egress uses its ExternalIP and replies return

| Interface Change | Priority | Automation | Owner / tier |
|---|---|---|---|
| IC-6 | critical | automated | [QE] VMaaS networking — E2E |

##### Preconditions

- The test can temporarily leave the cluster with no EgressIP-assignable nodes, then make an eligible provider-connected node available. The external probe captures source addresses and the test records the eligible nodes' primary IPs.

**Steps:** 1. Create a VM with its primary `l2bridge` interface and a NATGateway while no egress node is eligible → 2. Inspect `EgressIP.status.items` and the NATGateway Ready condition while unassigned; send guest traffic to a public external probe outside provider-infrastructure destinations and capture all packets received → 3. Make an eligible node available and wait for EgressIP assignment and NATGateway Ready=True → 4. Connect from the guest OS to the external probe and record source and reply → 5. Recreate the VMI or `virt-launcher` pod and repeat the connection.
**Expected:** While EgressIP is unassigned, NATGateway Ready is not `True` and the public external probe receives no guest packet from any source address. Provider-infrastructure destinations allowed by provider configuration are outside this probe. After assignment, the external probe observes the NATGateway ExternalIP as the source and its response reaches the guest; the same source and reply behavior holds after VMI/launcher recreation. A VM SecurityGroup may narrow permitted egress destinations.

#### TC-IS8-03: EgressIP failover preserves source and prevents node-IP leakage

| Interface Change | Priority | Automation | Owner / tier |
|---|---|---|---|
| IC-6 | high | manual | [QE] VMaaS networking — manual E2E |

##### Preconditions

- The test cluster has at least two eligible egress nodes on a provider-reachable subnet and a controlled method to make the assigned node unavailable. The test guest runs on a node that remains available when the assigned egress node is stopped. A public external probe outside provider-infrastructure destinations logs every received packet and can return a unique response for each TCP request. Record the eligible nodes' primary IPs.

##### Steps

1. Establish VM outbound traffic through a NATGateway and record the observed source address.
2. Begin a continuous external-probe capture and send a uniquely identified TCP request from the guest every second; record each attempt and its guest-side result.
3. Make the assigned egress node unavailable while the requests continue, and watch `EgressIP.status.items` through the unassigned interval and reassignment.
4. Continue the same probe sequence until the external probe receives a request after reassignment and the guest receives its reply.

##### Expected Results

- OVN assigns the same EgressIP address to another eligible node.
- Probe attempts are recorded continuously across node loss, the EgressIP assignment gap, and reassignment, so the failover interval is exercised.
- While `EgressIP.status.items` is empty, the public external probe receives zero guest packets, regardless of source address.
- The full capture contains no guest packet sourced from any eligible node's primary IP, including before OVN updates `EgressIP.status.items`, while it is empty, and after reassignment is reported.
- Outside the unassigned interval, every guest packet received by the public probe uses the NATGateway ExternalIP as its source. After reassignment, the guest receives the probe's reply.

This test requires a provider-capable failover environment and an observable assignment-loss interval; it is not covered by current VMaaS CI. It remains blocked until §9.1 and §9.2 validate the guard transition and OVN behavior.

#### TC-IS8-04: ExternalIP claims are unique per address and consumers are exclusive

| Interface Change | Priority | Automation | Owner / tier |
|---|---|---|---|
| IC-5, IC-6 | high | automated | [DEV] osac-aap — component integration |

**Steps:** 1. Create a pool with one free address and concurrently call `create_external_ip` for two distinct ExternalIP API IDs → 2. Inspect both ExternalIP status and the address-keyed claim ConfigMap → 3. Use the ExternalIP that owns the address to concurrently request a NATGateway and a VM ExternalIPAttachment → 4. Identify the consumer that acquires the consumer slot, delete it, and wait for its EgressIP or Services to be removed → 5. Create the other consumer with the same ExternalIP → 6. Delete the second consumer and ExternalIP.
**Expected:** At most one ExternalIP API ID owns the single pool address; the claim ConfigMap name is derived from that address and its owner metadata names that API ID. Exactly one concurrent consumer acquires the consumer slot; the losing consumer has `Ready=False`, reason `ExternalIPInUse`, and an actionable message naming the already claimed ExternalIP. No EgressIP or Service is created for that consumer. After the winning consumer is fully cleaned up, the other consumer can acquire the slot. The no-NAT guard is restored before EgressIP removal, and the address claim is released only after all consumers are removed.

## Gaps

### Requirement Coverage Gaps

- **IS-9, provider documentation:** Documentation-only requirement; no behavioral test case applies. Review the published setup and troubleshooting guide for the exact provider prerequisites and limitations.

### Interface Change Coverage Gaps

- **IC-7, provider documentation:** Documentation-only interface change; review it with the provider guide rather than creating a behavior test.

### Execution Readiness Gaps

- The no-Fabric E2E file and test-infra profile are proposed but do not exist. The current `tests/e2e/networking/vmaas/test_vmaas_networking.py` uses an ordered pytest module, `stack.create_network` / `stack.create_vm`, resource-wait helpers, guest SSH, and a Netris external-path fixture; it cannot prove the no-Fabric K8S-only manager, MetalLB-only ingress, or EgressIP path. Owner: QE/test-infra. The proposed command is `uv run pytest -n 0 -x tests/e2e/networking/vmaas/test_vmaas_k8s_only_networking.py` after the module and profile are added. A follow-up Jira ticket is required; no ticket ID is recorded in this draft.
- The Enclave Wizard's array-of-object port setting and BMaaS/CaaS rejection have no test command in this OSAC checkout. Owner: Enclave. The plugin/UI verification path and a follow-up Jira ticket remain to be assigned.
- The AAP `k8s_only` component-test target does not exist. Owner: osac-aap. The existing `make test` unit target and Kind/component-contract tests are the implementation pattern; a dedicated `k8s_only` contract target and follow-up Jira ticket remain to be added.
- The no-NAT egress guard's support, one-per-namespace ownership, and policy precedence on the target primary Layer 2 CUDN remain unresolved in §9.1; TC-IS8-01 is planned but not implementation-ready.
- EgressIP guest source translation, reply routing, VMI/launcher recreation, and failover are planned in TC-IS8-02/03 but are not established by the existing Fabric-backed suite.

## Release Readiness Gates

The profile is ready for release only when all of these conditions hold:

1. All six critical cases pass: TC-IS4-01, TC-IS5-02, TC-IS6-01, TC-IS7-01, TC-IS8-01, and TC-IS8-02.
2. Open questions §9.1 and §9.2 have supported answers for the target OCP z-stream. In particular, no-NAT egress and EgressIP assignment-loss transitions must fail closed without node-IP leakage, and guest EgressIP source translation and reply routing must work.
3. The proposed no-Fabric E2E suite and test-infra profile exist and pass, including provider ingress/return-path qualification and failover coverage.
4. The existing fabric-backed regression command, `uv run pytest -n 0 -x tests/e2e/networking/vmaas/test_vmaas_networking.py`, passes without regressions.
5. Enclave schema/UI coverage and the AAP `k8s_only` component contract are runnable and pass; each execution gap above has an owner and a linked follow-up Jira issue before implementation starts.
6. The provider setup and troubleshooting documentation is reviewed against the actual installation and test results.

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
