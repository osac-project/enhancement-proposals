# Testplan — OSAC-2434

## Overview

- **Feature:** OSAC-2434 — Netris Fabric Manager Integration
- **Total test cases:** 27
- **Requirements covered:** 14 of 14
- **Interface changes covered:** 8 of 8

The plan uses three levels:

- **Unit:** provider-value validation, manager registration parsing, target
  resolution, Netris input/output translation, policy semantics, idempotency,
  and secret redaction with fake clients or AAP result fixtures.
- **Integration:** Helm-rendered ConfigMaps/Secrets, NetworkClass readiness,
  dispatcher/AAP job payloads, operator status feedback, controller retries,
  finalizers, and a contract Netris endpoint or controlled Netris test fixture.
- **E2E:** a connected single-hub IPv4 deployment with Netris, exercising the
  public API/CLI-supported flows for every canonical networking resource and
  VMaaS, BMaaS, and CaaS.

The connected-only deployment boundary is inherited from the [Unified
Networking deployment support boundary](../OSAC-1433-unified-networking/design.md#deployment-support-boundary);
air-gapped and disconnected deployments are negative cases, not supported
Netris profiles.

## Test Cases

### FR-1: Provider can select Netris as the Fabric Manager

#### TC-FR1-01: Valid Netris selection is accepted

| Interface Change | Priority | Automation | Test levels |
|---|---|---|---|
| IC-1, IC-2 | critical | automated | Unit, integration |

##### Preconditions

- Installer values contain one Fabric Manager named `netris` with role
  `fabric` and `capabilities: addressFamily:ipv4`.
- Required Netris endpoint, identity, site, tenant, and Secret values are
  present.

##### Steps

1. Run installer value/schema validation.
2. Render the manager ConfigMap, NetworkClass, and network-fulfillment
   configuration.
3. Start provider admission and wait for NetworkClass reconciliation.

##### Expected Results

- Schema validation exits with status zero.
- Exactly one ConfigMap has the Fabric Manager label and `data.name: netris`.
- NetworkClass has `fabric_manager: netris`, IPv4 status, and valid shared
  defaults.
- NetworkClass reaches `Ready=True` only after the complete Netris profile is
  admitted.

#### TC-FR1-02: Tenant cannot select Netris

| Interface Change | Priority | Automation | Test levels |
|---|---|---|---|
| IC-2 | high | automated | Integration, E2E |

##### Preconditions

- A valid Netris NetworkClass is Ready.

##### Steps

1. Submit a tenant VirtualNetwork containing a manager name, implementation
   annotation, or NetworkClass reference.
2. Submit a workload containing a manager or implementation annotation.
3. Attempt to change the provider-owned NetworkClass through a tenant API
   identity.

##### Expected Results

- Each tenant request is rejected with `PermissionDenied` or `InvalidArgument`
  according to the shared authorization contract.
- No tenant object stores `netris` as caller-supplied routing metadata.
- The provider NetworkClass and manager ConfigMap are unchanged.

### FR-2: Provider can supply Netris configuration

#### TC-FR2-01: Provider configuration fields validate by type and format

| Interface Change | Priority | Automation | Test levels |
|---|---|---|---|
| IC-1 | high | automated | Unit |

##### Preconditions

- Table-driven fixtures cover every field in design §4.2.

##### Steps

1. Validate a complete configuration with an HTTPS controller URL, positive
   decimal site/tenant IDs, valid label key, valid resource-class JSON, and
   non-empty values.
2. Repeat with missing required fields, an HTTP URL, embedded URL credentials,
   non-decimal IDs, invalid label syntax, malformed JSON, empty strings, and
   unsupported capability keys.

##### Expected Results

- The complete fixture is accepted.
- Each invalid fixture returns `InvalidArgument` with the failing field path.
- No invalid configuration produces a manager ConfigMap or Ready NetworkClass.

#### TC-FR2-02: Provider Secret is handed to network jobs

| Interface Change | Priority | Automation | Test levels |
|---|---|---|---|
| IC-3 | critical | automated | Integration |

##### Preconditions

- A rendered deployment contains the Netris username and password in the
  provider configuration and Secret inputs.

##### Steps

1. Render the network-fulfillment instance-group ConfigMap and Secret.
2. Trigger a Netris create job and inspect its mounted environment and
   serialized `osac_job_vars`.
3. Capture the job event, AAP result artifact, controller log, and resource
   status.

##### Expected Results

- The ConfigMap contains non-secret endpoint/site/tenant values and no password.
- The Secret contains the password and is mounted only into the network job
  context.
- `osac_job_vars`, logs, events, status, and result artifacts contain no
  password or credential token.
- The job can authenticate to the Netris fixture and returns a resource result.

### FR-3: Netris is admitted only as a complete manager

#### TC-FR3-01: Complete manager registration covers every operation

| Interface Change | Priority | Automation | Test levels |
|---|---|---|---|
| IC-2, IC-4 | critical | automated | Unit, integration |

##### Preconditions

- The Netris registration contains only identity, role, description, and
  `addressFamily:ipv4`.
- The complete operation catalog contains all eight networking resources,
  both policy layers, and VMaaS/BMaaS/CaaS workload operations.

##### Steps

1. Resolve a Fabric-only NetworkClass.
2. Resolve a combined NetworkClass with Netris and a K8s manager.
3. Generate one create, read, and delete dispatch plan for each canonical
   resource and one workload operation for each service.

##### Expected Results

- Fabric-only resolution produces one Netris target for every operation.
- Combined resolution produces a Fabric target followed by a K8s target for
  every operation.
- No operation has zero targets, a per-resource target omission, or a combined
  implementation-strategy string.
- The NetworkClass status exposes only `addressFamily:ipv4` and ordinary
  readiness/status information.

#### TC-FR3-02: Partial capability declarations are rejected

| Interface Change | Priority | Automation | Test levels |
|---|---|---|---|
| IC-2 | critical | automated | Unit, integration |

##### Preconditions

- Registration fixtures contain `supports_nat`, resource lists, policy lists,
  workload scopes, service lists, IPv6, and unknown capability keys.

##### Steps

1. Submit each partial or unknown declaration as provider configuration.
2. Attempt to reconcile a NetworkClass from each declaration.

##### Expected Results

- Each partial declaration is rejected before NetworkClass readiness.
- No partial status matrix or tenant-visible unsupported branch is created.
- An unfinished operation can instead use the normal successful no-op AAP path
  while retaining the complete manager contract.

### FR-4: Shared deployment and operation boundary is enforced

#### TC-FR4-01: IPv4 connected single-hub admission is enforced

| Interface Change | Priority | Automation | Test levels |
|---|---|---|---|
| IC-1, IC-2 | critical | automated | Integration, E2E |

##### Preconditions

- Provider fixtures describe valid IPv4/connected/one-hub, IPv6, dual-stack,
  air-gapped, zero-hub, and multi-hub deployments.

##### Steps

1. Admit the valid deployment.
2. Repeat provider admission for each unsupported topology or address family.

##### Expected Results

- The valid deployment reaches `NetworkClass Ready=True`.
- IPv6, dual-stack, air-gapped, zero-hub, and multi-hub configurations return
  `InvalidArgument` or `FailedPrecondition` with the boundary field/reason.
- No unsupported deployment admits tenant networking resources.

#### TC-FR4-02: Network-owned updates are rejected

| Interface Change | Priority | Automation | Test levels |
|---|---|---|---|
| IC-8 | high | automated | Integration, E2E |

##### Preconditions

- A Ready Netris-backed VirtualNetwork, Subnet, SecurityGroup, NetworkACL,
  ExternalIPPool, ExternalIP, ExternalIPAttachment, NATGateway, and workload
  exist where required.

##### Steps

1. Call `Update`, `Patch`, and full replacement for every network-owned spec
   field and every workload network attachment field.
2. Inspect AAP job history and backend objects after each request.

##### Expected Results

- Every request is rejected with the shared update/operation error.
- No Netris update job is generated.
- Stored specs, status, target metadata, Netris objects, and pool capacity are
  unchanged.

### FR-5: Shared networking resources use Netris

#### TC-FR5-01: Canonical resource CRUD dispatches to Netris

| Interface Change | Priority | Automation | Test levels |
|---|---|---|---|
| IC-4, IC-5 | critical | automated | Unit, integration, E2E |

##### Preconditions

- The Netris manager is Ready and the Netris fixture has an empty OSAC scope.

##### Steps

1. Create a Ready VirtualNetwork with a canonical IPv4 CIDR.
2. Create a contained Ready Subnet.
3. Create a tenant SecurityGroup with one valid allow rule.
4. Create a tenant NetworkACL with one valid rule and associate it with the
   Subnet.
5. Create an IPv4 ExternalIPPool containing exactly one CIDR.
6. Allocate an ExternalIP, create an ExternalIPAttachment, and create one
   NATGateway using separate valid ExternalIPs.
7. Read and list every object, then delete them in leaf-first order.

##### Expected Results

- Each create produces the documented Netris VPC, IPAM, V-Net, policy, or NAT
  object with the configured site and tenant scope.
- Each read returns the OSAC object and backend status without exposing
  credentials.
- Each delete removes only its corresponding Netris object after dependency
  validation and leaves no orphaned backend object.
- Every selected manager target reaches Ready before the OSAC object is Ready.

#### TC-FR5-02: SecurityGroup and NetworkACL semantics remain separate

| Interface Change | Priority | Automation | Test levels |
|---|---|---|---|
| IC-6 | critical | automated | Integration, E2E |

##### Preconditions

- A Ready Subnet has an associated tenant NetworkACL.
- A workload has a tenant SecurityGroup with an allow rule.

##### Steps

1. Send traffic matching the SecurityGroup allow rule and the NetworkACL rule.
2. Send traffic that matches no SecurityGroup rule.
3. Send traffic that matches an ACL deny rule.
4. Send return-direction traffic without an opposite-direction ACL rule.
5. Attempt to create a SecurityGroup with a deny/action field and a tenant
   NetworkACL with an empty rule list.

##### Expected Results

- Matching traffic passes only when both effective policy layers permit it.
- Unmatched SecurityGroup traffic is denied, including the return direction
  unless stateful SecurityGroup state permits it.
- A matching NetworkACL deny overrides the deployment permit baseline.
- Return traffic is evaluated independently by NetworkACL and is denied when
  no reverse-direction rule or baseline permits it.
- SecurityGroup deny/action input and empty tenant NetworkACL input return
  `InvalidArgument`; no policy object is persisted.

#### TC-FR5-03: ExternalIP and NAT mappings are correct

| Interface Change | Priority | Automation | Test levels |
|---|---|---|---|
| IC-5 | critical | automated | Unit, integration, E2E |

##### Preconditions

- A Ready IPv4 ExternalIPPool has capacity.
- A Ready workload endpoint and VirtualNetwork exist.

##### Steps

1. Create an ExternalIP and wait for `Allocated`.
2. Create an ExternalIPAttachment targeting the Ready endpoint.
3. Create a NATGateway with a different Allocated ExternalIP.
4. Send inbound and outbound traffic and then delete the attachment, gateway,
   IPs, and pool in dependency order.

##### Expected Results

- ExternalIP maps to one Netris `/32` allocation and transitions to
  `Allocated`.
- ExternalIPAttachment maps to one DNAT rule and transitions to Ready only
  after the target endpoint IP is known.
- NATGateway maps to one SNAT rule for the VN CIDR and transitions to Ready.
- An ExternalIP cannot be consumed by both an attachment and NATGateway.
- Deletion removes DNAT before its target/IP and SNAT before its VN/IP.

### FR-6: VMaaS, BMaaS, and CaaS use Netris

#### TC-FR6-01: VMaaS uses one Netris network attachment

| Interface Change | Priority | Automation | Test levels |
|---|---|---|---|
| IC-4, IC-7 | critical | automated | Integration, E2E |

##### Preconditions

- A Ready Netris VN, Subnet, effective ACL, and compatible SecurityGroup exist.

##### Steps

1. Create a VM with omitted/empty attachment input.
2. Create a VM with one explicit typed attachment.
3. Attempt a VM with two entries, `primary:false`, IPv6, or a non-Ready
   reference.

##### Expected Results

- Omitted/empty input resolves to the documented default Subnet and compatible
  SecurityGroup; the sole attachment is implicitly primary.
- Explicit input creates one Netris workload target on the requested Subnet.
- The VM reaches Ready with one discovered IPv4 address.
- Each unsupported request returns the shared validation error and persists no
  VM or backend attachment.

#### TC-FR6-02: BMaaS performs Netris port handoff and DHCP discovery

| Interface Change | Priority | Automation | Test levels |
|---|---|---|---|
| IC-7 | critical | automated | Integration, E2E |

##### Preconditions

- A BareMetalInstanceType has one valid fabric interface.
- A provisioning V-Net, tenant Subnet, Netris server, and DHCP fixture exist.

##### Steps

1. Create a BareMetalInstance with one attachment and then with omitted
   interface.
2. Observe provisioning-network to tenant-V-Net port movement.
3. Allow DHCP lease assignment and run `query_dhcp_lease`.
4. Delete the instance and observe tenant-V-Net to provisioning-V-Net return.

##### Expected Results

- At most one `move_network_attachment` target is dispatched.
- The selected interface is the explicit valid interface or the first valid
  fabric interface.
- The discovered IPv4 lease is written to the sole status entry before BMI
  Ready and is available to ExternalIPAttachment.
- Delete returns the port to the provisioning V-Net, confirms lease release,
  and removes only owned automatic ExternalIP children.

#### TC-FR6-03: CaaS uses the shared Netris worker/network flow

| Interface Change | Priority | Automation | Test levels |
|---|---|---|---|
| IC-4, IC-7 | critical | automated | Integration, E2E |

##### Preconditions

- A complete Netris profile, Ready Subnet/ACL, worker inventory, and required
  management/VIP configuration exist.

##### Steps

1. Create a Cluster with one typed cluster attachment.
2. Observe worker BM creation, one fabric interface per worker, and Netris
   network handoff.
3. Wait for API and ingress endpoint readiness.
4. Verify ExternalIPAttachment/DNAT and NATGateway/SNAT flows.
5. Attempt a second cluster attachment and a create before the Subnet or
   NATGateway is Ready.

##### Expected Results

- The Cluster uses one Subnet for all node sets and each worker uses one
  Netris-managed fabric interface.
- API and ingress endpoints become Ready only after their dependencies and
  Netris operations report Ready.
- The cluster has outbound access through the Ready NATGateway when no direct
  route exists and inbound DNAT through its allocated ExternalIPs.
- Multi-attachment and non-Ready dependency requests return validation errors
  before Cluster persistence.

### FR-7: Installer produces the complete Netris deployment setup

#### TC-FR7-01: Rendered installer output is complete and consistent

| Interface Change | Priority | Automation | Test levels |
|---|---|---|---|
| IC-1, IC-2, IC-3 | critical | automated | Integration |

##### Preconditions

- A valid provider values fixture contains all required Netris values.

##### Steps

1. Render the installer chart with the Netris profile.
2. Parse the manager ConfigMap, NetworkClass, network-fulfillment ConfigMap,
   and Secret.
3. Run chart/schema and rendered-manifest validation.

##### Expected Results

- Exactly one Netris Fabric Manager ConfigMap is rendered.
- NetworkClass points to `netris` and contains valid IPv4 defaults.
- Non-secret connection values are in the ConfigMap and password is only in
  the Secret.
- No rendered object contains region fields, per-resource capability maps, or
  tenant-selectable manager settings.

#### TC-FR7-02: Re-rendering does not require manual networking edits

| Interface Change | Priority | Automation | Test levels |
|---|---|---|---|
| IC-1, IC-2, IC-3 | high | automated | Integration, E2E |

##### Preconditions

- A Netris-backed deployment has reached NetworkClass Ready.

##### Steps

1. Re-run the installer with the same provider values.
2. Reconcile existing manager ConfigMap, NetworkClass, Secret, and Netris
   resources.
3. Compare resource IDs, target annotations, and backend objects before and
   after reconciliation.

##### Expected Results

- Existing ConfigMap, NetworkClass, Secret, and Netris objects remain singular.
- No duplicate VPC, IPAM allocation, ACL, DNAT, or SNAT object is created.
- No manual post-install networking edit is required to keep the deployment
  Ready.

### FR-8: Invalid or unavailable configuration blocks readiness

#### TC-FR8-01: Invalid configuration keeps NetworkClass non-Ready

| Interface Change | Priority | Automation | Test levels |
|---|---|---|---|
| IC-2, IC-8 | critical | automated | Unit, integration |

##### Preconditions

- Provider fixtures cover missing Secret, unknown manager name, duplicate
  registration, invalid site/tenant, incomplete operation profile, and invalid
  NetworkClass defaults.

##### Steps

1. Apply each invalid provider fixture.
2. Reconcile the NetworkClass and attempt a tenant VirtualNetwork create.

##### Expected Results

- NetworkClass remains `Ready=False` with a reason identifying the failed
  non-secret condition.
- Tenant create returns `FailedPrecondition` before persistence or AAP
  dispatch.
- No password or Secret value appears in the reason, event, or API response.

#### TC-FR8-02: Netris outage and authentication failure recover

| Interface Change | Priority | Automation | Test levels |
|---|---|---|---|
| IC-8 | critical | automated | Integration, E2E |

##### Preconditions

- A deployment starts with a valid Netris controller fixture, then the fixture
  is made unreachable or returns authentication failure.

##### Steps

1. Reconcile a new VirtualNetwork while the controller is unavailable.
2. Restore connectivity/credentials.
3. Observe reconciliation and status feedback.

##### Expected Results

- The resource remains Pending/Failed according to the shared controller state
  machine and does not become Ready.
- Retry attempts use bounded backoff and do not create duplicate Netris
  objects.
- After the fixture is restored, the existing resource reaches Ready without a
  tenant spec update.

### FR-9: Strict creation and deletion dependencies are enforced

#### TC-FR9-01: Non-Ready dependencies reject create

| Interface Change | Priority | Automation | Test levels |
|---|---|---|---|
| IC-5, IC-7, IC-8 | critical | automated | Integration, E2E |

##### Preconditions

- Create VN, Subnet, ExternalIPPool, ExternalIP, workload, and policy objects
  in Pending, Failed, Deleting, and Ready states.

##### Steps

1. Attempt each dependent create while its reference is not Ready/Allocated.
2. Repeat through API, private service path, and Catalog/Template resolution.
3. Trigger an OSAC-owned automatic ExternalIP child flow.

##### Expected Results

- Every ordinary dependent create returns `FailedPrecondition` with the
  blocker kind, identity, field path, observed state, required state, and
  remediation.
- No rejected dependent or backend object is persisted.
- Only the allowlisted OSAC-owned automatic ExternalIP/attachment flow creates
  Pending children atomically.

#### TC-FR9-02: Reverse references block deletion

| Interface Change | Priority | Automation | Test levels |
|---|---|---|---|
| IC-8 | critical | automated | Integration, E2E |

##### Preconditions

- Build the complete dependency graph from a workload attachment through
  Subnet, VirtualNetwork, policy, ExternalIP, ExternalIPAttachment, and
  NATGateway.

##### Steps

1. Attempt deletion of every parent while each direct blocker exists.
2. Remove blockers in leaf-first order and retry.

##### Expected Results

- Each blocked delete returns `FailedPrecondition` with all direct blocker
  identities and required next actions.
- No child is detached, deleted, or changed as a side effect.
- Leaf-first retries remove exactly one requested resource and then permit the
  next deletion in the graph.

#### TC-FR9-03: Automatic children use the only allowed cleanup cascade

| Interface Change | Priority | Automation | Test levels |
|---|---|---|---|
| IC-8 | critical | automated | Integration, E2E |

##### Preconditions

- A VM, BM, or Cluster owns an OSAC-created ExternalIP and
  ExternalIPAttachment with the canonical marker and exact immutable owner.
- A tenant-created attachment also targets the workload in a separate case.

##### Steps

1. Delete the workload with the OSAC-owned children.
2. Observe attachment deletion, then ExternalIP deletion, then parent finalizer
   completion.
3. Repeat with the tenant-created attachment.

##### Expected Results

- The OSAC-owned attachment is deleted before its ExternalIP, and both are
  removed only when the exact owner relationship matches.
- Tenant-created attachment causes workload deletion to return a blocker; it is
  never detached or deleted by the workload controller.
- Default VN, Subnet, SecurityGroup, NetworkACL, NATGateway, and ExternalIPPool
  are never cascaded by workload deletion.

### FR-10: Netris operations are idempotent and observable

#### TC-FR10-01: Repeated create/reconcile is idempotent

| Interface Change | Priority | Automation | Test levels |
|---|---|---|---|
| IC-5, IC-8 | critical | automated | Unit, integration, E2E |

##### Preconditions

- Netris fixture supports read-before-create and deterministic object names.

##### Steps

1. Submit the same create request twice.
2. Interrupt the AAP result after the Netris object is created.
3. Reconcile until feedback is delivered.

##### Expected Results

- One OSAC object and one corresponding Netris object exist.
- The retry adopts the matching object by scoped identity and requested
  fields; it does not create a duplicate.
- A mismatched same-name object causes a failed-closed status with a provider
  remediation reason.

#### TC-FR10-02: Unfinished operation uses a normal successful no-op

| Interface Change | Priority | Automation | Test levels |
|---|---|---|---|
| IC-4, IC-8 | critical | automated | Unit, integration |

##### Preconditions

- Configure a development Netris profile whose selected operation is routed to
  the approved no-op AAP role.

##### Steps

1. Create the affected canonical resource or workload.
2. Inspect dispatcher target metadata, AAP job, status transition, and public
   API response.

##### Expected Results

- The normal Netris target and operation-specific AAP job are created.
- The no-op returns a successful job result and the resource follows the normal
  status transition.
- No `unsupported` capability, omitted target, alternate API, or silent
  fallback is exposed to the tenant.

### NFR-1: Netris credentials are not exposed

#### TC-NFR1-01: Secret redaction holds across all surfaces

| Interface Change | Priority | Automation | Test levels |
|---|---|---|---|
| IC-3 | high | automated | Unit, integration, E2E |

##### Preconditions

- Use a unique sentinel password in the provider Secret fixture.

##### Steps

1. Render manifests and trigger successful and failed Netris jobs.
2. Fetch public/private resource status, events, AAP artifacts, controller logs,
   and CLI output.
3. Search every captured surface for the sentinel.

##### Expected Results

- The sentinel appears only in the provider Secret data and the test fixture's
  protected input.
- It is absent from ConfigMaps, `osac_job_vars`, events, statuses, logs, AAP
  artifacts, API responses, and CLI output.

### NFR-2: NetworkClass readiness is deterministic

#### TC-NFR2-01: Readiness cannot precede complete configuration validation

| Interface Change | Priority | Automation | Test levels |
|---|---|---|---|
| IC-2, IC-8 | critical | automated | Unit, integration |

##### Preconditions

- A provider reconciliation fixture controls manager registration, Secret
  availability, endpoint connectivity, and complete-profile checks.

##### Steps

1. Make each prerequisite available one at a time.
2. Observe NetworkClass conditions and attempt dependent resource creation after
   each transition.

##### Expected Results

- NetworkClass remains `Ready=False` until every prerequisite is valid.
- Dependent create remains rejected until the exact transition to Ready.
- Once Ready, the same configuration produces a stable result across repeated
  reconciliations.

### NFR-3: Tenant isolation and dependency guarantees are preserved

#### TC-NFR3-01: Cross-tenant references and backend adoption are rejected

| Interface Change | Priority | Automation | Test levels |
|---|---|---|---|
| IC-5, IC-6, IC-7 | critical | automated | Integration, E2E |

##### Preconditions

- Two tenants have Ready VNs, Subnets, policies, and workloads.
- A Netris object exists under tenant A's configured site/tenant scope.

##### Steps

1. Tenant B references tenant A's OSAC resource in a create request.
2. Alter a backend object's scope or owner metadata and reconcile tenant A's
   resource.
3. Attempt tenant B deletion of tenant A's backend-linked object.

##### Expected Results

- Cross-tenant references return `NotFound` or `PermissionDenied` without
  revealing the other tenant's identity.
- A scope/owner mismatch causes the resource to fail closed; the object is not
  adopted or deleted.
- Tenant B's API, status, and list results contain no tenant A resource.

### NFR-4: Test coverage exists at all required levels

#### TC-NFR4-01: Netris contract matrix runs in unit, integration, and E2E suites

| Interface Change | Priority | Automation | Test levels |
|---|---|---|---|
| IC-1 through IC-8 | high | automated | Unit, integration, E2E |

##### Preconditions

- Unit fixtures, rendered Helm fixtures, a controlled Netris integration target,
  and a connected single-hub E2E deployment are available.

##### Steps

1. Run the manager/configuration/translation unit suites.
2. Run Helm, operator, AAP, and controller integration suites.
3. Run the Netris E2E matrix for all canonical resources and VMaaS, BMaaS, and
   CaaS workflows.
4. Collect the test inventory and compare it with FR-1 through FR-10,
   NFR-1 through NFR-4, and IC-1 through IC-8.

##### Expected Results

- Unit, integration, and E2E commands exit with zero failures.
- The inventory contains at least one test for every requirement and every
  interface change.
- The matrix includes positive and negative paths for configuration, resource
  mapping, policy semantics, workloads, dependencies, deletion, retries,
  credential redaction, and no-op implementation behavior.

## Gaps

### Requirement Coverage Gaps

All PRD requirements have test cases.

### Interface Change Coverage Gaps

All interface changes are exercised by test cases.

## Summary

| Metric | Count |
|---|---:|
| Total test cases | 27 |
| Critical | 21 |
| High | 6 |
| Medium | 0 |
| Low | 0 |
| Automated | 27 |
| Manual | 0 |
| Requirements with test cases | 14 / 14 |
| Interface changes with test cases | 8 / 8 |

---

## Provenance

Authored: draft @ design 0.11.1 - 3f9c3b9, workspace main @ 0ae795e37 (96 behind origin/main)

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.1","ai_workflows":"3f9c3b9","source_repo":"0ae795e37","source_repo_branch":"main","commits_behind_main":96,"commits_ahead_main":0,"main_ref":"main","phases":["draft"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
