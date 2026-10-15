# Testplan — OSAC-1433 Network Manager Integration Contract

## Overview

- **Feature:** OSAC-1433 Network Manager Integration Contract
- **Total test cases:** 14
- **Requirements covered:** 12 of 12
- **Interface changes covered:** 8 of 8

This plan covers generic OSAC implementation and provider qualification before a manager is selected in a production NetworkClass. Providers run backend checks against their actual AAP execution environment; OSAC can run the same cases against its supported implementations. It does not define a hosted provider certification service. The PRD uses FR-1 through FR-12 as its testable acceptance outcomes rather than defining a second AC numbering scheme; the `AC` column below cites the relevant FR.

### Existing test patterns and execution context

The registration, NetworkData, generic dispatch, and durable recovery behavior in this design is target work; the existing files below are test patterns, not evidence that the new contract is already implemented. Add contract tests alongside the affected suites and run provider qualification against the actual selected AAP execution environment and backend.

| Test layer | Existing pattern to extend | Existing helpers or fixtures |
|---|---|---|
| Fulfillment API validation and persistence | `fulfillment-service/internal/validation/networking_contract_test.go`; `fulfillment-service/it/it_networkclass_manager_capabilities_test.go`; `fulfillment-service/it/it_networkclass_manager_readiness_test.go` | Ginkgo/Gomega validation suite; fulfillment-service integration setup |
| Operator dispatch, manager results, and reconciliation | `osac-operator/internal/controller/networking_contract_test.go`; `osac-operator/internal/controller/fabric_output_provider_test.go`; `osac-operator/pkg/dispatcher/resolver_test.go` | Ginkgo/envtest controller patterns and mocked providers |
| Ansible manager behavior | `osac-aap/tests/unit/test_agentless_net_network.py`; `osac-aap/tests/integration/targets/agentless_net_stub/` | pytest monkeypatch pattern and the existing Ansible integration harness |
| User-visible networking lifecycle | `tests/e2e/vmaas/regression/test_networking_api_contract.py`; `tests/e2e/vmaas/networking_lifecycle_helpers.py`; `tests/e2e/bmaas/regression/networking/test_bmaas_networking.py`; `tests/e2e/caas/sanity/test_cluster_create.py` | pytest fixtures such as `grpc`, `private_grpc`, and `k8s_hub_client`; `poll_until` and resource wait helpers |

## Test Cases

### FR-1: Provider-supplied and OSAC-supplied implementations follow the same manager contract

#### TC-FR1-01: Run the shared task contract against implementations from different sources

| Story | AC | Interface Change | Priority | Automation |
|-------|----|-----------------|----------|------------|
| Cloud Infrastructure Admin — select a conforming implementation | FR-1 | IC-2 | high | automated |

##### Preconditions

- The AAP execution environment contains an OSAC-supplied manager and a provider-supplied manager for the same test role.
- Each manager has a NetworkManager registration and uses the same registered NetworkDataModel contracts.

##### Steps

1. Run the shared manager qualification selection against each implementation, covering every task assigned to the selected role.
2. Capture the role and task selected for each request, the canonical `osac_job_vars`, and the returned `osac_result`.
3. With `NetworkClass.spec.vip_prefix_length` configured, verify `network_class.vip_prefix_length` carries that value in `create_subnet`; repeat with it omitted and verify the field is absent.
4. Inspect AAP `extra_vars` and verify `osac_network_task_from` identifies the fixed task. Verify no operation or attempt identifier appears inside `osac_job_vars` or `osac_result`; the top-level launch-correlation value remains reserved for OSAC recovery.
5. Compare each implementation's inputs and results with the manager contract.

##### Expected Results

- OSAC selects each manager by its registered `managerName` and invokes the task fixed by resource kind, lifecycle action, role, and interface type.
- Both implementations use the same common input and result envelope; provider source does not select another playbook, operation, or manager stage. The generic job includes the registered `osac.networking.<managerName>` role and the fixed task file.
- A configured VIP reservation prefix is captured in the canonical NetworkClass task context; an unset value is omitted. Manager roles do not fetch NetworkClass fields themselves.
- Each successful result uses `artifacts.osac_result` with stable `resourceID`, current projection `resourceUID`, `observedGeneration`, and `data.network_data`; the network-data list is empty when no new values are expected. Service-extension outputs use the same envelope.
- `osac_job_vars` and `osac_result` contain no operation or attempt identifier; managers cannot use AAP launch correlation to select behavior.
- Both implementations can be registered and selected without implementation-specific OSAC code when they meet their assigned task requirements.

### FR-2: Cloud Infrastructure Admins can assess the role requirements and manager compatibility

#### TC-FR2-01: Review the published manager contract for onboarding completeness

| Story | AC | Interface Change | Priority | Automation |
|-------|----|-----------------|----------|------------|
| Cloud Infrastructure Admin — assess manager requirements and compatibility | FR-2 | — | high | manual |

##### Preconditions

- The [Unified Networking Design](/enhancements/OSAC-1433-unified-networking/design.md), this Network Manager Integration Contract Design, and the [Network Manager Provider Guide](https://github.com/osac-project/osac/pull/1517) are available to the reviewer.

##### Steps

1. Use the documents to identify each manager role, its assigned operations and targets, task naming rules, required inputs, permitted outputs, and shared configuration source.
2. Determine which NetworkDataModel declarations a Fabric Manager must provide for a selected Kubernetes Manager.
3. Find the rules for validation, result handling, retries, uncertain jobs, cleanup, and provider behavioral qualification.

##### Expected Results

- The reviewer can determine which role implements each operation and which task file the provider must package.
- The reviewer can determine the required model names, owner scopes, schemas, and data direction before selecting a manager pair.
- The documents distinguish registration checks from backend behavior qualification and state how failures block readiness or cleanup.

### FR-3: Tenants can use the shared networking behavior with compatible manager combinations

#### TC-FR3-01: Verify attachment, routing, isolation, and stateful policy behavior

| Story | AC | Interface Change | Priority | Automation |
|-------|----|-----------------|----------|------------|
| Tenant User — use shared networking across compatible managers | FR-3 | IC-6 | critical | automated |

##### Preconditions

- A NetworkClass selects a compatible Fabric Manager and Kubernetes Manager.
- Use Subnets `192.0.2.0/25` and `192.0.2.128/25` in one VirtualNetwork and `198.51.100.0/24` in a second VirtualNetwork.
- Test targets exercise `overlay` and `physical` interfaces through service-neutral fixtures. The source SecurityGroup permits TCP/443 egress and the destination SecurityGroup permits TCP/443 ingress; neither permits TCP/8443. Include one-sided cases where only source egress or only destination ingress permits TCP/443.
- Overlay fixtures include two protected kubeconfig contexts named by stable hosting-cluster IDs and same-named VMs in both contexts, so context selection can be verified independently of object names.
- Include one endpoint outside OSAC workload policy, with no selected SecurityGroup, for inbound and outbound direction checks.
- The controllable Fabric and Kubernetes Manager test roles can return a task failure for a selected attachment deletion, then succeed on retry; the harness can observe the SubnetAttachment finalizer and target teardown gate.

##### Steps

1. Create a VirtualNetwork and two Subnets, then attach test workloads to the same Subnet, different Subnets in the same VirtualNetwork, and a separate VirtualNetwork.
2. Apply a SubnetAttachment for each supported normalized interface type. For `overlay`, create the target VM with `runStrategy: Halted`, no running VMI, and no tenant network/interface fields; for `physical`, record the selected host port's initial fabric membership.
3. Inspect the job input and result: the SubnetAttachment is the tracked `resource`, the workload is the separate `target`, and `network_attachment` carries the resolved Subnet, one interface, and complete effective SecurityGroup rules. For `overlay`, verify `target_cluster.id` matches the hosting-cluster ID in immutable placement and names the context used with the protected kubeconfig; no kubeconfig contents appear in the request, `osac_job_vars`, or result.
4. For an extension that realizes a Subnet in multiple clusters, verify each `(Subnet API ID, action, Kubernetes Manager registration ID, target_cluster.id)` has a separate durable stage and exact AAP job correlation. Readiness stays false until every required placement succeeds. Delete cleans every placement whose create may have launched, including one absent from the current extension set, before the single Fabric delete. Make one required cluster context missing or unauthorized and verify that stage makes no backend change and keeps the Subnet non-ready.
5. Test a new TCP/443 flow when both source egress and destination ingress permit it. Repeat with only source egress permitted and only destination ingress permitted; each one-sided case must fail. Test unmatched TCP/8443 and reply packets for the established TCP/443 connection.
6. Attach multiple SecurityGroups to an endpoint and verify their allow rules combine as a union for that endpoint's check; still require the other endpoint's directional check.
7. Test inbound and outbound flows with the external endpoint. Verify the attached workload's rule in the traffic direction controls each flow.
8. Verify the service lifecycle does not proceed before the manager result is accepted: the VM remains halted until the request reports `NetworkAttachmentsReady=True`; BMaaS does not reboot or expose the host to tenant traffic until the same request condition is true; DHCP/IP discovery is not dispatched until after VM start or the BM handoff reboot.
9. Delete each attachment and inspect policy removal and target-specific cleanup ordering: BMaaS reports `NetworkOffboardShutdownComplete=True` before requesting physical cleanup, the request reports `NetworkOffboardComplete=True` only after the port returns to its recorded extension-defined baseline, and deprovision waits for request cleanup; the overlay target is stopped before the manager removes its network/interface fields and policy, and the workload service deletes it only after cleanup completes.
10. For an overlay attachment, configure the Kubernetes Manager test role to fail `delete_subnet_attachment` before confirming policy cleanup. Verify cleanup remains pending, the VM stays stopped, and teardown is blocked; then allow the task to succeed and observe reconciliation resume.
11. Repeat overlay apply with a missing context and with a context that cannot access the exact target. Verify the manager fails before changing either same-named VM, the request remains non-ready, and VMaaS does not start the selected VM.

##### Expected Results

- Workloads in one Subnet share its Layer 2 broadcast domain; Subnets in one VirtualNetwork are Layer 3 routable; separate VirtualNetworks remain isolated.
- Physical apply maps the selected port to the provider segment backing the requested Subnet. Overlay apply adds only the service-defined network/interface fields to the exact halted target VM and installs policy without changing run control or starting the VM.
- OSAC passes the stable target-cluster ID as the context selector; the Kubernetes Manager uses that exact kubeconfig context and cannot fall back to the current context when selection or access fails.
- SecurityGroup policy applies to each attachment. Rules combine as a union for each endpoint's ingress and egress checks, but a new flow succeeds only when both source egress and destination ingress permit it. One-sided allows fail; established replies pass; unmatched new traffic fails.
- The target-only SubnetAttachment owns networking job history, status, and its cleanup finalizer. Its result identifies the request and current projection; the separate target identity and normalized interface scope backend state.
- Policy and the target network configuration are ready before traffic is enabled. A failed apply leaves the request non-ready; the VM stays halted and BMaaS does not perform its tenant handoff reboot. `NetworkAttachmentsReady=True` is persisted before either service advances. IP discovery follows guest start or BM handoff, never precedes it.
- Delete removes policy before target teardown: `NetworkOffboardShutdownComplete=True` confirms the physical host is shut down on the tenant network before the manager restores its port; `NetworkOffboardComplete=True` records successful request cleanup; a stopped VM has its manager-owned network fields and policy removed before its workload service deletes it.
- An injected manager delete-task failure does not clear the SubnetAttachment finalizer or allow target teardown. After the manager succeeds on retry, policy removal and target cleanup complete before the workload lifecycle advances.

### FR-4: Incompatible or unsupported manager selections fail with a clear diagnostic

#### TC-FR4-01: Reject incompatible profiles and unsupported dispatch requests

| Story | AC | Interface Change | Priority | Automation |
|-------|----|-----------------|----------|------------|
| Cloud Infrastructure Admin — receive clear rejection diagnostics | FR-4 | IC-3 | critical | automated |

##### Preconditions

- Register `netris` as Fabric with output `osac-networking-subnet-vxlan-l2-vni`; register `cudn_evpn` as Kubernetes with that model as an input. Also register `agentless_net` with output `osac-networking-subnet-vlan-id`.
- The test can inspect fulfillment-service responses and AAP job history.

##### Steps

1. Create NetworkClasses with a missing `fabricManager`, `cudn_evpn` assigned to the Fabric role, and `agentless_net` paired with the Kubernetes Manager that requires `osac-networking-subnet-vxlan-l2-vni`; `agentless_net` declares only `osac-networking-subnet-vlan-id` as an output.
2. Set `supports_east_west_ethernet: true` when the selected Fabric manager lacks `NETWORK_MANAGER_CAPABILITY_EAST_WEST_ETHERNET`.
3. Create a profile whose Fabric Manager declares `NETWORK_MANAGER_CAPABILITY_EAST_WEST_ETHERNET` but whose NetworkClass omits or disables `supports_east_west_ethernet`; request a FabricDomain.
4. Create a request for an interface type or role that is not assigned in the selected NetworkClass.
5. Inspect API responses, persisted NetworkClass objects, FabricDomain status, and AAP job history.

##### Expected Results

- Fulfillment-service rejects each invalid NetworkClass with a diagnostic naming the missing or incompatible reference; it persists no invalid profile and starts no AAP job.
- Enabling east-west on a manager that lacks the capability rejects NetworkClass creation. A FabricDomain request with the NetworkClass capability omitted or false fails with `FAILED_PRECONDITION` and launches no AAP job. The enabled create/delete behavior is covered by TC-FR6-02.
- An unsupported request fails before provider dispatch. OSAC compares exact NetworkDataModel names and does not use a manager-name allowlist or send work to a manager with a different role or task assignment.

### FR-5: Providers can define and exchange shared networking data

#### TC-FR5-01: Register a provider-defined model and its owner-scoped value

| Story | AC | Interface Change | Priority | Automation |
|-------|----|-----------------|----------|------------|
| Cloud Infrastructure Admin — define and exchange shared network data | FR-5 | IC-7 | critical | automated |

##### Preconditions

- The NetworkDataModel and NetworkData APIs are available to an authorized provider and OSAC service identity.
- No model named `acme-networking-subnet-segment` exists.

##### Steps

1. Call `NetworkDataModels/Create` with `metadata.name: acme-networking-subnet-segment`, `ownerScope: Subnet`, and the design schema requiring `fabric` (string) and `segment` (integer).
2. Call the OSAC-only `NetworkData/Create` for the Subnet API ID with `value: {fabric: "north", segment: 40120}`, then call provider `NetworkData/Get` for the resulting record.
3. Attempt to create, update, or delete that NetworkData as the provider identity.
4. Retry with the same value and then attempt a different value for the same model and owner.

##### Expected Results

- The model and schema are stored as one immutable definition; managers reference it by `metadata.name`.
- The value is stored with its model name and stable Subnet API resource ID under the `(model_name, owner.kind, owner.resourceId)` key; the model has no runtime value fields.
- Provider reads are allowed, but provider create, update, and delete attempts are rejected; OSAC service identity owns runtime writes and owner cleanup.
- An identical retry returns the existing NetworkData object. A conflicting value for the same model and owner is rejected.

#### TC-FR5-02: Exchange newly produced resource-scoped values with a consumer manager

| Story | AC | Interface Change | Priority | Automation |
|-------|----|-----------------|----------|------------|
| Cloud Infrastructure Admin — define and exchange shared network data | FR-5 | IC-5 | critical | automated |

##### Preconditions

- The Fabric Manager declares NetworkClass-, VirtualNetwork-, and Subnet-scoped output models, including one NetworkClass-scoped value not yet stored.
- The selected Kubernetes Manager declares inputs using matching NetworkDataModel names.

##### Steps

1. Create a VirtualNetwork and then a Subnet. Inspect each Fabric task's operation context and result.
2. Verify stored values, including parent-owned VirtualNetwork or profile values, arrive as existing `network_data` and are not expected again. Verify every applicable model/owner key that is still missing is expected exactly once, even when the operation resource is a child.
3. Inspect the subsequent Kubernetes task input and then delete the Subnet while observing cleanup order.
4. Start two VirtualNetwork create operations for the same NetworkClass concurrently while its NetworkClass-scoped value is absent. Verify both eligible Fabric tasks converge on the same owner-scoped value and backend allocation.

##### Expected Results

- OSAC derives expected model/owner keys from the Fabric registration, operation context, and stored NetworkData; it does not pass an output list to the manager. The provider-authored Fabric task knows its declared model names.
- Each Fabric result contains every expected new value once and no unexpected key. OSAC persists the complete validated result before starting the Kubernetes Manager.
- The consumer receives only its declared applicable values. Kubernetes cleanup precedes Fabric deletion, and parent-owned values remain until the parent owner is deleted.
- Concurrent operations that expect the same missing owner/model key return the same value and do not create duplicate backend state. An identical fulfillment-service write is idempotent; a conflicting value is rejected without replacing the stored value or starting dependent work.

### FR-6: OSAC rejects invalid definitions and values before dependent work

#### TC-FR6-01: Reject invalid JSON Schemas, declarations, and manager results

| Story | AC | Interface Change | Priority | Automation |
|-------|----|-----------------|----------|------------|
| Cloud Infrastructure Admin — reject invalid definitions and values | FR-6 | IC-7 | critical | automated |

##### Preconditions

- The fulfillment service can create NetworkDataModel and NetworkManager resources and validate manager results.

##### Steps

1. Call `NetworkDataModels/Create` with no `$schema`, the Draft 2019-09 URI, `$ref: https://example.invalid/model.json`, `ownerScope: ComputeInstance`, the same model name twice, and a schema using an unsupported vocabulary.
2. Call `NetworkManagers/Create` with an unknown model name, place a Fabric output in `networkInputs`, and submit an unknown capability enum value.
3. Call `NetworkData/Create` with `segment: "40120"`, then submit Fabric results with an owner outside `network_owner_context`, a stale `projectionUID`, a duplicate key, an omitted expected key, and an unexpected key.
4. Inspect database state and whether a dependent Kubernetes job starts.

##### Expected Results

- Invalid definitions and registrations are rejected with diagnostics naming the object and invalid field; no invalid object is persisted.
- Invalid values and result envelopes produce no NetworkData writes and no dependent manager dispatch.
- A stored value can be read only for the exact declared model and owner; schema validation does not infer resource-relative backend behavior.

#### TC-FR6-02: Validate ExternalIP allocation and east-west task results

| Story | AC | Interface Change | Priority | Automation |
|-------|----|-----------------|----------|------------|
| Cloud Infrastructure Admin — reject invalid definitions and values | FR-6 | IC-4 | critical | automated |

##### Preconditions

- A ready NetworkClass selects an ExternalIPPool with CIDR `198.51.100.0/29` and IPv4 family.
- The selected Fabric Manager implements the assigned ExternalIP and FabricDomain tasks.

##### Steps

1. Allocate an ExternalIP and capture the Fabric task result. Retry allocation for the same stable API resource ID.
2. In separate attempts, return malformed `198.51.100.999` and canonical out-of-pool `203.0.113.8`.
3. Release the ExternalIP, interrupt provider cleanup, and retry after cleanup is confirmed.
4. With Ethernet east-west enabled, create and delete a FabricDomain through the selected Fabric Manager.

##### Expected Results

- OSAC accepts only a canonical IPv4 address within the selected pool and records it in ExternalIP status after validating the successful result.
- Retrying the same ExternalIP API resource ID returns the same reservation. Invalid results do not report allocation as successful.
- OSAC retains capacity while provider cleanup is unconfirmed and releases it only after confirmed deletion. Manager jobs have no Kubernetes write credential.
- The selected Fabric Manager receives the FabricDomain task only when the NetworkClass enables Ethernet east-west and that manager declares the capability; the operation preserves VirtualNetwork routing and Subnet broadcast domains.

### FR-7: Registrations support Create, Read, and Delete without in-place updates

#### TC-FR7-01: Enforce immutable registration lifecycle and dependency-safe deletion

| Story | AC | Interface Change | Priority | Automation |
|-------|----|-----------------|----------|------------|
| Cloud Infrastructure Admin — manage immutable registrations | FR-7 | IC-1 | high | automated |

##### Preconditions

- NetworkDataModel and NetworkManager resources exist, and a NetworkClass selects one manager. A resource operation has produced one NetworkClass-scoped NetworkData value for that profile.

##### Steps

1. Create, list, and get the registration objects through the provider API.
2. Attempt Update and Patch on NetworkDataModel and NetworkManager.
3. Attempt to delete a model referenced by a manager or NetworkData value, and a manager referenced by a NetworkClass or unresolved operation.
4. Attempt to delete a NetworkClass while resources or unresolved work remain bound to it.
5. Drain resources and operations. Make NetworkData owner cleanup fail, request NetworkClass deletion, and verify deletion remains pending, the profile remains present, and no provider job launches.
6. Restore NetworkData cleanup, reconcile the pending deletion, and verify OSAC removes profile-owned NetworkData before deleting the NetworkClass. Then delete dependent registrations and register a replacement with the same `managerName`.

##### Expected Results

- Create, Read/List, and Delete are exposed for provider registrations; Update and Patch fail.
- Referenced objects remain until their registrations, profiles, owner data, and active or uncertain operations no longer depend on their exact API identity.
- Once drained, NetworkClass deletion submits no provider job and OSAC removes its profile-owned NetworkData through owner cleanup; tenant-owned values have already been removed with their VirtualNetwork or Subnet. A failed cleanup write keeps the profile and deletion request pending. After cleanup recovers, reconciliation removes the profile-owned values and completes deletion.
- Reusing `managerName` creates a new registration identity; delayed work from the old identity cannot be matched to the replacement.

### FR-8: Providers can supply settings and credentials to manager jobs

#### TC-FR8-01: Deliver shared fulfillment-group settings without exposing secrets in job data

| Story | AC | Interface Change | Priority | Automation |
|-------|----|-----------------|----------|------------|
| Cloud Infrastructure Admin — configure backend settings and credentials | FR-8 | IC-2 | high | automated |

##### Preconditions

- The AAP networking fulfillment group imports its ConfigMap and Secret into job pods with `envFrom`.
- The ConfigMap contains a backend endpoint and public CA bundle; the Secret contains a test token and private client key.

##### Steps

1. Put `EXAMPLE_BACKEND_URL=https://network.example.test` and `EXAMPLE_CA_BUNDLE=<PEM>` in the group ConfigMap and `EXAMPLE_BACKEND_TOKEN=test-token` plus `EXAMPLE_CLIENT_KEY=<private-key>` in the Secret. Run both manager roles and inspect the job environment, `osac_job_vars`, `osac_result`, and logs.
2. Remove `EXAMPLE_BACKEND_URL` and then set it to `not-a-url`; run the role in separate attempts.
3. Verify the task client uses the configured CA file while certificate verification remains enabled.

##### Expected Results

- Each manager job can read the fulfillment group's settings and credentials as environment variables; no per-manager credential isolation is implied.
- Settings and secrets do not appear in NetworkClass or NetworkManager fields, `osac_job_vars`, NetworkData, result artifacts, or logs.
- Missing or malformed required settings fail the operation without reporting the resource Ready. A public CA bundle is used by the task's client without changing the pod-wide trust store; private key files use restrictive permissions and are removed after use.

### FR-9: Registration and successful task results are distinct from behavioral qualification

#### TC-FR9-01: Detect a manager that returns success without providing its advertised behavior

| Story | AC | Interface Change | Priority | Automation |
|-------|----|-----------------|----------|------------|
| Cloud Infrastructure Admin — distinguish registration from behavior qualification | FR-9 | IC-8 | high | manual |

##### Preconditions

- The provider has selected a registered manager and can observe its backend.
- The qualification selection includes assertions for the manager's assigned operations, targets, enabled capabilities, and cleanup.

##### Steps

1. Register the manager and return a structurally valid success result from an assigned task without changing backend state.
2. Run qualification assertions for connectivity, address allocation, policy enforcement, and cleanup where those behaviors apply.
3. Repeat with a deliberate no-op only for an operation whose required behavior is genuinely a no-op.

##### Expected Results

- Registration and a valid result demonstrate structural contract compliance only; they do not pass backend assertions for connectivity, allocation, policy, or cleanup.
- A no-op passes only assertions that expect no backend change. A skipped required behavior is incomplete, not a pass.

### FR-10: Uncertain manager work blocks readiness, capacity release, and replacement

#### TC-FR10-01: Recover interrupted jobs without duplicating work or releasing owned state

| Story | AC | Interface Change | Priority | Automation |
|-------|----|-----------------|----------|------------|
| Cloud Infrastructure Admin — resolve interrupted work safely | FR-10 | IC-4 | critical | automated |

##### Preconditions

- A manager operation journal, AAP job history, NetworkData store, and an ExternalIP allocation are available to the test.

##### Steps

1. Persist a `LaunchUnknown` attempt, drop the AAP launch response, and search the complete AAP scope using the exact OSAC-reserved correlation value.
2. Repeat recovery with one matching job, zero matches, and multiple matching jobs; restart reconciliation while each case is unresolved.
3. Deliver a structurally valid artifact from a different AAP job than the tracked attempt; in separate attempts, alter its `resourceID`, `resourceUID`, or `observedGeneration`. Also associate an artifact with the wrong journaled manager stage or task. Separately accept a result, fail partway through NetworkData persistence, and retry result consumption.
4. Request the opposite lifecycle action, owner deletion, ExternalIP release, or manager/profile replacement while work remains uncertain; then resolve the operation and retry cleanup.

##### Expected Results

- One matching job is adopted and polled by its exact AAP job ID. Zero or multiple matches remain unresolved; reconciliation starts no duplicate or opposite operation while any possible execution remains.
- An artifact read from a job other than the tracked AAP job, or one whose resource identity, projection UID, generation, journaled stage, or task does not match the attempt, cannot advance readiness, create NetworkData, or release address capacity. The manager artifact itself does not carry the job, stage, or task identifiers.
- An accepted result is replayed from the durable journal after a database write failure without launching another AAP job.
- Deletion and manager/profile replacement remain blocked with an actionable status until uncertain work and provider cleanup are resolved; a missing projection or timed-out job is not proof of cleanup.

### FR-11: Provider qualification retains pass, fail, and incomplete evidence

#### TC-FR11-01: Produce a machine-readable report for the selected manager profile

| Story | AC | Interface Change | Priority | Automation |
|-------|----|-----------------|----------|------------|
| Cloud Infrastructure Admin — run and retain manager qualification | FR-11 | IC-8 | high | automated |

##### Preconditions

- The versioned qualification selection, environment profile, preflight checks, runner, and report format are available.
- A test backend can satisfy all required cases, fail an assertion, and make a required case unavailable.

##### Steps

1. Run qualification with a conforming backend, then with an assertion failure.
2. Run again with a required case skipped because backend access is unavailable.
3. Inspect the retained report and verify it identifies the tested environment and manager profile.

##### Expected Results

- Reports distinguish `pass`, `fail`, and `incomplete`; a skipped required assertion is incomplete and never contributes to pass.
- The retained report identifies OSAC/AAP versions, NetworkClass and model/manager registrations, test selection, job references, and redacted diagnostics.
- A passing report covers every assigned operation and target, each enabled capability, recovery, and cleanup. It demonstrates the tested provider configuration and is not a hosted OSAC certification.

### FR-12: Supported workload attachments receive tenant IPv4 configuration through DHCP

#### TC-FR12-01: Verify DHCP service on overlay and physical attachments

| Story | AC | Interface Change | Priority | Automation |
|-------|----|-----------------|----------|------------|
| Tenant User — use shared networking across compatible managers | FR-12 | IC-6 | critical | automated |

##### Preconditions

- A NetworkClass selects the Fabric Manager and Kubernetes Manager used by the test deployment.
- VM guest images and bare-metal tenant OS images are configured to run a DHCP client on the selected tenant interface.
- The provider DHCP service returns address, prefix, default gateway, and DNS resolver settings for the test Subnet. A tenant-controlled endpoint can attempt to send rogue DHCP responses.
- Test attachments use SecurityGroups that deny tenant application traffic.

##### Steps

1. Create a Subnet and attach a VM through the overlay path. Confirm the VM is halted without tenant network/interface fields before apply; wait for attachment and policy readiness, then start it.
2. Observe the first-boot DHCP exchange and verify the VM receives one unique IPv4 address inside the Subnet, with the expected prefix, gateway, and resolver settings. Confirm VMaaS discovers the address from VM/VMI status and does not dispatch `query_dhcp_lease`.
3. Provision a bare-metal target on the separate provisioning network, apply its physical attachment, and complete the handoff reboot. Observe tenant DHCP and verify one unique in-Subnet address with the expected prefix, gateway, and resolver settings. Confirm BMaaS discovers it using `query_dhcp_lease` for the selected interface MAC.
4. Repeat the trusted DHCP exchanges while tenant application traffic remains denied. Then send an offer from the tenant-controlled endpoint and attempt to configure a second endpoint from that offer.

##### Expected Results

- The VM receives its tenant settings through DHCP only after the manager has added its network/interface fields and policy to the halted VM; the first boot uses that prepared attachment. The bare-metal tenant interface receives its settings through DHCP only after the selected physical port is attached and the handoff completes.
- Both assigned addresses are unique active leases within the correct Subnet, and the received prefix, default gateway, and resolver settings match that Subnet's provider DHCP configuration. Neither manager writes a static tenant IP into the guest or host OS.
- Trusted DHCP and required gateway address resolution work under deny-all tenant SecurityGroups. The tenant-controlled endpoint cannot provide accepted DHCP responses to another workload.
- VM IP discovery uses VM/VMI status; the BMaaS extension uses the selected-MAC lease query. The manager contract does not impose the BMaaS query operation on VM flows.

## Gaps

### Requirement Coverage Gaps

All PRD requirements have test cases.

### Interface Change Coverage Gaps

All interface changes are exercised by test cases.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 14 |
| Critical | 8 |
| High | 6 |
| Medium | 0 |
| Low | 0 |
| Automated | 12 |
| Manual | 2 |
| Requirements with test cases | 12 / 12 |
| Interface changes with test cases | 8 / 8 |

---

## Provenance

Authored: draft @ design 0.11.3 - 2bd6607, workspace main @ 1f3b63b82 (52 behind origin/main)
Final: manual-edit [manual] @ design 0.11.5 - 1c6e8de, workspace main @ 04cc50101

> Context changed between draft and manual-edit.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"1c6e8de","source_repo":"04cc50101","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","manual-edit","revise","revise","revise","revise","manual-edit","manual-edit","manual-edit"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":false} -->
