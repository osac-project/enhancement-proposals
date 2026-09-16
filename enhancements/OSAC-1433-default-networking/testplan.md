# Testplan — OSAC-1433 Default Networking

## Overview

- **Feature:** OSAC-1433 — Default Networking and simplified resource creation
- **Source design:** [design.md](design.md)
- **Shared contract:** [Unified Networking test plan](../OSAC-1433-unified-networking/testplan.md)
- **Deployment support boundary:** [Unified Networking deployment support
  boundary](../OSAC-1433-unified-networking/design.md#deployment-support-boundary);
  default networking is supported only in connected deployments, not air-gapped
  or disconnected deployments.
- **Inherited creation rule:** The [strict dependency-ready creation
  contract](../OSAC-1433-unified-networking/design.md#strict-dependency-ready-creation)
  is tested here for ordered onboarding and default resolution; only the
  OSAC-owned automatic ExternalIP/ExternalIPAttachment path may create
  Pending children.
- **Scope:** Tenant onboarding, default-resource lifecycle, readiness, default
  attachment resolution, automatic ExternalIP creation, cleanup, and
  complete-manager SecurityGroup/NetworkACL/NAT behavior.
- **Non-goals:** Per-tenant default configuration, additional automatic
  VirtualNetwork or Subnet creation, retroactive migration of existing
  resources, and UI support. API, REST, private API, and CLI are the tested
  surfaces.

## Test infrastructure and traceability

The test cases below are design-level requirements with implementation anchors
in the OSAC monorepo. New or extended tests should follow these existing
patterns rather than inventing a separate harness.

| Test level | Framework and environment | Existing implementation anchors |
|---|---|---|
| Unit | Ginkgo v2/Gomega; fulfillment-service in-memory DAO and fake manager state | `fulfillment-service/internal/servers/default_networking_provisioner_test.go`, `fulfillment-service/internal/servers/external_ip_pool_selector_test.go`, `fulfillment-service/internal/servers/cidr_validation_test.go`, `fulfillment-service/internal/servers/private_virtual_networks_server_test.go` |
| Integration | Ginkgo v2/Gomega; fulfillment-service integration harness with private gRPC clients, ephemeral database, and Kubernetes test clients | `fulfillment-service/it/it_default_networking_test.go`, `fulfillment-service/it/it_tenant_onboarding_test.go`, `fulfillment-service/it/it_validation_test.go`, `fulfillment-service/it/it_external_ip_test.go` |
| Operator integration | Ginkgo v2/Gomega with Kind and Kubernetes CR clients | `osac-operator/test/integration/networking_test.go` |
| E2E | pytest; connected single-hub deployment, `GRPCClient`, `K8sClient`, bounded polling helpers | `tests/e2e/vmaas/conftest.py`, `tests/e2e/core/grpc_client.py`, `tests/e2e/core/k8s_client.py`, `tests/e2e/core/helpers.py`, `tests/e2e/vmaas/sanity/test_virtual_network_lifecycle.py`, `tests/e2e/vmaas/sanity/test_subnet_lifecycle.py`, `tests/e2e/vmaas/sanity/test_network_acl_lifecycle.py`, `tests/e2e/vmaas/regression/external_ip/test_external_ip_pool_capacity.py`, `tests/e2e/vmaas/regression/external_ip/test_external_ip_pool_lifecycle.py` |

### Shared test data and assertion contract

Unless a case overrides the value, use these concrete objects:

| Object | Concrete value |
|---|---|
| NetworkClass | `test-default-nc` |
| Tenant | `test-defnet-001` |
| VirtualNetwork CIDR | `10.200.0.0/16` |
| Default Subnet CIDR | `10.200.0.0/20` |
| Valid alternate Subnet CIDR | `10.200.1.0/24` |
| Invalid IPv6 CIDR | `2001:db8::/32` |
| Invalid host-bit CIDR | `10.200.0.7/20` |
| Invalid outside Subnet | `10.201.0.0/24` |
| MetalLB prefix | `32` |
| Default label | `osac.openshift.io/default: "true"` |
| Auto-created label | `osac.openshift.io/auto-created: "true"` |
| Default SecurityGroup | Empty allow-rule list; empty means default deny |
| Default ACL policy | Explicit deny-all ingress and allow-all egress rules on the tenant's default NetworkACL |
| Deployment baseline | Provider-owned least-specific fallback, hard-coded to permit all traffic and unavailable to tenant configuration |

Use private gRPC methods such as `NetworkClasses/Create`, `Tenants/Create`,
`Tenants/Get`, `VirtualNetworks/List`, `VirtualNetworks/Get`,
`Subnets/List`, `NetworkACLs/List`, and `ExternalIPs/Create`. For rejected
requests assert the gRPC status described by the shared design:

- `InvalidArgument` for malformed, missing, contradictory, or unsupported
  request values;
- `FailedPrecondition` for a valid request whose referenced resource is not in
  the required Ready/Allocated state, or for exhausted capacity/deletion
  dependencies; and
- `PermissionDenied` when a tenant attempts a provider-only operation and the
  resource is visible to the caller.

Assert the exact condition reason and message where the Default Networking
design defines one, including `ResourcesPending`, `AllResourcesReady`,
`NoDefaultNetworking`, `VirtualNetworkProvisioningFailed`,
`SubnetProvisioningFailed`, `NetworkACLProvisioningFailed`,
`NATGatewayProvisioningFailed`, and:

`ExternalIPPool exhaustion: no available capacity in any READY pool for IPv4`

## Coverage summary

| Requirement | Test cases | Unit | Integration | E2E |
|---|---:|---:|---:|---:|
| R1 NetworkClass defaults | 2 | Yes | Yes | Rejection path |
| R2 Tenant onboarding | 3 | Yes | Yes | Yes |
| R3 Readiness/recovery | 2 | Yes | Yes | Yes |
| R4 Workload default resolution and immutability | 3 | Yes | Yes | Yes |
| R5 Automatic ExternalIP lifecycle | 3 | Yes | Yes | Yes |
| R6 Unsupported behavior | 1 | Yes | Yes | Rejection paths |
| R7 CLI defaulting and automatic external access | 1 | Yes | Yes | Yes |
| **Total** | **15** | **All applicable** | **All applicable** | **All user-visible flows** |

## Test cases

### R1: NetworkClass defaults are valid and mandatory

#### TC-R1-01: Valid defaults are accepted

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration | critical | automated |

**Implementation references:**
`default_networking_provisioner_test.go` default-class builders,
`network_classes_server_test.go`, and `it_default_networking_test.go`.

##### Preconditions

- The test database has no active `test-default-nc`.
- The caller uses the provider/private client authorized to create a
  deployment NetworkClass.
- The provider has registered the configured Fabric Manager, the deployment
  is connected and single-hub, and the CaaS/MetalLB VIP path is
  enabled for this validation case.

##### Steps

1. Call `NetworkClasses/Create` with `metadata.name: test-default-nc`, a
   configured `fabric_manager`, and:

   ```yaml
   spec:
     defaults:
       virtual_network_cidr: 10.200.0.0/16
       ipv4_subnet_cidr: 10.200.0.0/20
     metallb_vip_prefix_length: 32
   ```

2. Read the response and then call `NetworkClasses/Get` using the returned ID.
3. Run the same request through the integration client used by
   `it_default_networking_test.go`.

##### Expected results

- The create call succeeds with gRPC status `OK`.
- `spec.defaults.virtual_network_cidr` is exactly `10.200.0.0/16`.
- `spec.defaults.ipv4_subnet_cidr` is exactly `10.200.0.0/20`.
- `spec.metallb_vip_prefix_length` is accepted because the configured
  deployment provides the CaaS/MetalLB VIP path.
- No separate enable/disable flag is accepted or required.

#### TC-R1-02: Invalid defaults are rejected before persistence

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated |

**Implementation references:** `cidr_validation_test.go`,
`network_classes_server_test.go`, `it_validation_test.go`, and
`tests/e2e/core/grpc_client.py` request/error helpers.

##### Preconditions

- Use a fresh NetworkClass name for every invalid request.
- The caller has provider authorization so failures test validation rather
  than authorization, except for the final tenant-authorization case.

##### Steps

1. Submit each input mutation to `NetworkClasses/Create` using a fresh
   NetworkClass name.
2. For each rejected request, call `NetworkClasses/Get` and verify the
   rejected object is absent or unchanged.

##### Expected results

| Input mutation | Expected status and assertion |
|---|---|
| Omit `spec.defaults` | `InvalidArgument`; field violation identifies `spec.defaults`; no NetworkClass or tenant resources are persisted. |
| Set VN CIDR to `2001:db8::/32` | `InvalidArgument`; IPv6 is rejected. |
| Set VN CIDR to `10.200.0.7/20` | `InvalidArgument`; host bits are rejected. |
| Set Subnet CIDR to `10.201.0.0/24` | `InvalidArgument`; Subnet is outside the VN. |
| Set Subnet CIDR to `10.200.0.0/16` | `InvalidArgument`; Subnet cannot equal the VN range. |
| Configure a CaaS/MetalLB-capable deployment path but omit the prefix length | `InvalidArgument`; `spec.metallb_vip_prefix_length` is required for that path. |
| Set MetalLB prefix to `0`, `33`, or a value not more specific than the participating Subnet | `InvalidArgument`; the prefix is outside the supported IPv4/reserved-range contract. |
| Set a MetalLB prefix whose reserved range is outside the Subnet | `InvalidArgument`; the reserved range must remain contained by the Subnet. |
| Supply `metallb_vip_prefix_length` without the CaaS/MetalLB path | `InvalidArgument`; the conditionally supported field must be omitted. |
| Submit provider-only defaults as a tenant | `PermissionDenied` or the platform visibility error; no provider configuration is changed. |

### R2: Tenant onboarding creates exactly the supported graph

#### TC-R2-01: Combined-manager onboarding

| Test type | Priority | Automation |
|---|---|---|
| Integration, E2E | critical | automated |

**Implementation references:** `it_default_networking_test.go`,
`it_tenant_onboarding_test.go`, `default_networking_provisioner_test.go`,
`tests/e2e/vmaas/conftest.py`, and `tests/e2e/core/helpers.py`.

##### Preconditions

- `test-default-nc` exists with the valid values from the shared test-data
  table, and the configured manager(s) are complete manager profiles.
- `test-defnet-001` does not exist.

##### Steps

1. Call `Tenants/Create` with `metadata.name: test-defnet-001`.
2. Poll `Tenants/Get` with `wait_for_tenant_condition` until the condition
   type is `DEFAULT_NETWORKING_READY`.
3. List `VirtualNetworks`, `Subnets`, `SecurityGroups`, and `NetworkACLs` with the tenant and
   default-label filter:

   ```text
   this.metadata.labels['osac.openshift.io/default'] == 'true'
   ```

4. List `NATGateways` and inspect the referenced `ExternalIP` for the tenant.
5. Repeat onboarding with every candidate
   ExternalIPPool exhausted; for this subcase, poll until
   `DefaultNetworkingReady=False` with the exhaustion reason.

##### Expected results

- `Tenants/Create` returns `OK` and one tenant ID.
- Exactly one default VirtualNetwork, one IPv4 Subnet, one default
  SecurityGroup, and one default NetworkACL exist for `test-defnet-001`.
- The default SecurityGroup has an empty allow-rule list and therefore means
  default deny.
- The default NetworkACL is explicitly associated with the default Subnet and
  contains deny-all ingress and allow-all egress rules.
- Each default resource has tenant ownership and the default label.
- NATGateway exists, carries the default label, and references a
  Ready/Allocated unconsumed ExternalIP.
- `DefaultNetworkingReady` transitions from `ResourcesPending` to
  `AllResourcesReady` only after every default resource is Ready.
- The `DefaultNetworkingCreated` event is emitted when default
  resource creation starts.
- When every Ready pool is exhausted,
  onboarding creates neither the default ExternalIP nor NATGateway, leaves
  `DefaultNetworkingReady=False`, reports the explicit ExternalIPPool
  exhaustion condition, and leaves no capacity reservation behind.

#### TC-R2-02: Default resources follow the complete manager profile

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

**Implementation references:** `default_networking_provisioner_test.go`,
`it_default_networking_test.go`, and `it_tenant_onboarding_test.go`.

##### Preconditions

- Configure a K8s-only manager, a Fabric-only manager, and both managers as
  complete profiles.
- Use a distinct tenant for each combination.

##### Steps

1. Call `NetworkClasses/Create` for the selected complete manager profile.
2. Call `Tenants/Create` for the corresponding test tenant.
3. Poll `Tenants/Get` and list the tenant's default resources.
4. Inspect the fake manager calls in the unit test and the Kubernetes CRs in
   the integration/E2E environment.
5. Call `SecurityGroups/Create`, `NetworkACLs/Create`, and
   `NATGateways/Create`. Exercise the shared complete-manager Create matrix for
   the remaining canonical resources as part of
   [Unified Networking TC-R1-04](../OSAC-1433-unified-networking/testplan.md).

##### Expected results

- VN and Subnet reach Ready.
- A default SecurityGroup exists; it may be empty and means deny.
- A default NetworkACL exists; it is associated with the default
  Subnet and contains deny-all ingress/allow-all egress.
- One configured manager receives one internal target; two configured managers
  receive two targets. All targets must be Ready, or a development no-op must
  return success.
- No resource is omitted or rejected due to a manager subset declaration.
  Kubernetes NetworkPolicy is never treated as a substitute for the OSAC
  policy contracts.
- Tenant onboarding reaches `DefaultNetworkingReady=True` with reason
  `AllResourcesReady`.
- In the current K8s-only profile, default resource dispatch follows the
  [K8s-only manager test plan](../OSAC-1433-k8s-only-k8s-manager/testplan.md).
  MetalLB ExternalIP support is not treated as NAT/SNAT support.
- In a combined deployment, each default resource is dispatched to both
  managers and waits for both targets.

#### TC-R2-03: Onboarding is idempotent and does not create extra defaults

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration | high | automated |

**Implementation references:** `default_networking_provisioner_test.go`,
`it_default_networking_test.go`, and `it_tenant_lifecycle_test.go` concurrency
and reconciliation patterns.

##### Preconditions

- `test-idempotent-001` has no default resources.
- `test-tenant-delete-001` has no default resources.
- `test-default-nc` has the valid shared test data.

##### Steps

1. Submit two concurrent `Tenants/Create`/onboarding requests for
   `test-idempotent-001`.
2. Interrupt reconciliation after VN creation, after Subnet creation, and
   after NetworkACL creation, then invoke the tenant signal/reconciliation
   path.
3. Repeat onboarding after the graph is complete.
4. Onboard `test-tenant-delete-001`, wait for its default graph to be Ready,
   delete the Tenant, and list its former default resources.
5. Create a deliberately mismatched default resource with the same tenant and
   default label, then rerun onboarding.

##### Expected results

- The matching graph is adopted idempotently.
- Exactly one default VN, Subnet, and NetworkACL exist after every retry.
- No duplicate jobs, ExternalIP capacity reservations, or default resources
  are created.
- Deleting `test-tenant-delete-001` does not bypass dependency guards. Its
  default graph is deleted through the explicit leaf-first workflow; each
  delete reports blockers and no default resource is implicitly detached or
  cascaded merely because it has a tenant owner reference.
- The mismatched graph returns a provider configuration error and is not
  silently adopted or overwritten.

### R3: Default readiness and failure recovery

#### TC-R3-01: Readiness waits for every supported default

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

**Implementation references:** `it_default_networking_test.go`,
`default_networking_provisioner_test.go`, `tests/e2e/core/helpers.py`
(`wait_for_tenant_condition`), and `tests/e2e/core/k8s_client.py`.

##### Preconditions

- Use a controllable fake manager for unit/integration tests.
- Create `test-readiness-001` under a NetworkClass with the valid defaults.

##### Steps

1. Set each manager/resource state in the table below.
2. Call `Tenants/Get` and inspect the Tenant condition and Kubernetes events.
3. Attempt workload creation without an explicit attachment while the default
   graph is not Ready.

##### Expected results

| Manager/resource state | Required assertion |
|---|---|
| VN Pending | `DefaultNetworkingReady=False`, reason `ResourcesPending`; workload create is rejected with `FailedPrecondition`. |
| VN Failed | `DefaultNetworkingReady=False`, reason `VirtualNetworkProvisioningFailed`; the event includes `DefaultNetworkingFailed`. |
| Subnet Failed | `DefaultNetworkingReady=False`, reason `SubnetProvisioningFailed`; no workload receives a default Subnet. |
| SecurityGroup Failed | `DefaultNetworkingReady=False`, reason `SecurityGroupProvisioningFailed`; no workload relying on the default Subnet is created while its effective groups are unavailable. |
| NetworkACL Failed | `DefaultNetworkingReady=False`, reason `NetworkACLProvisioningFailed`; no workload relying on the default Subnet is created while its effective ACL is unavailable. |
| NATGateway Failed | `DefaultNetworkingReady=False`, reason `NATGatewayProvisioningFailed`. |
| Feedback for another tenant/VN | Ignore the feedback; the target tenant condition and resource state do not change. |
| All required resources Ready | `DefaultNetworkingReady=True`, reason `AllResourcesReady`; all returned references are Ready, and the `DefaultNetworkingReady` event is present. |

#### TC-R3-02: Failure and documented recovery path

| Test type | Priority | Automation |
|---|---|---|
| Integration, E2E | high | automated |

**Implementation references:** `it_default_networking_test.go`,
`it_tenant_lifecycle_test.go`, and `tests/e2e/core/helpers.py` bounded polling
helpers.

##### Preconditions

- `test-recovery-001` has a valid NetworkClass and a controllable manager.
- Configure the manager to fail one operation at a time.

##### Steps

1. Fail VN provisioning and read `Tenants/Get` plus the Kubernetes Tenant CR.
2. Restore the manager and signal reconciliation.
3. Repeat steps 1–2 for Subnet, NetworkACL, and NATGateway.
4. For a terminal graph error, delete the tenant as specified by the design,
   recreate it, and poll until recovery completes.

##### Expected results

- Each failure emits `DefaultNetworkingFailed` and the exact reason listed in
  TC-R3-01; the message includes the failed resource name.
- Transient failure retries without setting `DefaultNetworkingReady=True`.
- After recovery, exactly one clean default graph exists and the condition is
  `DefaultNetworkingReady=True/AllResourcesReady`.
- Existing immutable workload attachments are not rewritten while readiness
  is degraded.

#### TC-R3-03: Onboarding creates defaults only after dependencies are Ready

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Steps

1. Start onboarding with a controllable manager that leaves the default
   VirtualNetwork `Pending`.
2. Inspect the tenant and all default-resource tables/CRs before advancing
   the VN.
3. Advance the VN to `Ready` but leave the Subnet `Pending`; inspect again.
4. Advance the Subnet to `Ready`, leave the auto-created NAT ExternalIP
   `Pending`, and inspect again.
5. Advance the ExternalIP to `Allocated`, then allow the supported policy and
   NAT managers to reconcile.
6. During each incomplete phase, attempt a workload create using omitted or
   empty attachments.

##### Expected results

- While VN is Pending, no default Subnet, SecurityGroup, NetworkACL, or
  NATGateway is created. The tenant remains non-Ready.
- After VN is Ready, the Subnet and default SecurityGroup may be
  admitted; the default NetworkACL is not admitted until the Subnet is Ready.
- A workload create while any resolved default is not Ready returns
  `FailedPrecondition` with the default resource identity and exact field
  path; it creates no workload or attachment.
- The default NATGateway is not created while its ExternalIP is Pending. It is
  created only after the VN is Ready and the ExternalIP is Allocated.
- No phase creates a dependent default merely to wait for a prerequisite. The
  only Pending dependency exception is the OSAC-owned automatic ExternalIP
  (and its owned attachment when applicable).
- After all supported defaults become Ready, `DefaultNetworkingReady=True`,
  omitted/empty workload attachments resolve successfully, and exactly one
  default graph exists after retries.

### R4: Workload default resolution

#### TC-R4-01: Omitted, empty, partial, and complete inputs

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

**Implementation references:** `default_networking_provisioner_test.go`,
`fulfillment-service/internal/servers/private_virtual_networks_server_test.go`,
`tests/e2e/vmaas/conftest.py`, `tests/e2e/core/grpc_client.py`, and the
service-specific VM/CaaS/BMaaS networking test plans.

##### Preconditions

- Tenant `test-defaulting-001` has a Ready default Subnet
  `default-ipv4` (`10.200.0.0/20`) with a Ready system-created default
  SecurityGroup and NetworkACL associated/available for it.
- Create an explicit Ready alternate Subnet `explicit-subnet`
  (`10.200.1.0/24`) in the same VN and associate a Ready NetworkACL
  `explicit-acl` with it. Its effective ACL is `explicit-acl`.
- Create a second Ready VirtualNetwork and Subnet
  `non-default-vn`/`non-default-subnet` without a SecurityGroup default or
  NetworkACL association. Use this pair to test cross-VN defaulting and the
  workload readiness guard.
- Use the typed local reference `{name: "explicit-subnet"}`.

##### Steps

1. Submit each request row below as a separate VM, Cluster, or BM create
   request.
2. Read the created parent with the corresponding `Get` method.
3. Inspect the resolved network fields and assert the
   `NetworkAttachmentsPopulated` event when defaulting occurred.

##### Expected results

| Request | Expected result and assertion |
|---|---|
| VM `network_attachments` omitted | One resolved attachment: Subnet `default-ipv4`, default SecurityGroup, `primary=true`; the effective ACL is obtained from the Subnet. |
| VM attachment list empty | Same result as omitted; no second attachment is created. |
| Cluster `network_attachment` omitted | One cluster attachment containing the default Subnet and default SecurityGroup; the effective ACL is obtained from the Subnet. |
| Cluster attachment message empty | Same result as omitted; no arbitrary Subnet is selected. |
| BM `network_attachments` omitted or empty | Exactly one resolved attachment with default Subnet, default SecurityGroup, and the first eligible fabric interface; the effective ACL is obtained from the Subnet. |
| Only Subnet supplied as `{name: "explicit-subnet"}` | Preserve `explicit-subnet`; default only SecurityGroup; its effective ACL is obtained from the Subnet. |
| Only `non-default-subnet` supplied with SecurityGroup omitted | `InvalidArgument` naming the selected VN and the tenant default SecurityGroup VN; no default-VN group is attached and no workload is persisted. |
| Explicit SecurityGroup belongs to a different VN from the selected Subnet | `InvalidArgument`; the resolved attachment must use one VirtualNetwork. |
| Only compatible SecurityGroup list supplied, Subnet omitted | Preserve the explicit group list; default only the Subnet and service-specific interface when the groups belong to the tenant default VirtualNetwork; the effective ACL is obtained from the Subnet. |
| SecurityGroup list supplied from a non-default VirtualNetwork, Subnet omitted | `InvalidArgument`; the resolved default Subnet and explicit groups would be in different VirtualNetworks, so no default-VN SecurityGroup substitution or workload persistence occurs. |
| `non-default-subnet` selected before ACL association | `FailedPrecondition` identifying the missing Ready effective NetworkACL; no deployment-baseline fallback and no workload is persisted. |
| `non-default-subnet` after a Ready NetworkACL is associated | Workload creation succeeds and uses that ACL as the effective policy. |
| Tenant-created empty SecurityGroup | `InvalidArgument`; tenant-created groups require at least one allow-only rule. |
| Default SecurityGroup with empty rules | Accepted during onboarding; means default deny. |
| NetworkACL supplied inside a workload attachment | `InvalidArgument`; ACL membership is managed only through NetworkACL-to-Subnet association. |
| Non-Ready explicit Subnet | `FailedPrecondition`; no default substitution occurs. |
| VM/BM list has two attachments | `InvalidArgument`; no workload is persisted or dispatched. |
| VM attachment has `primary=false` | `InvalidArgument`; the supported single attachment is always primary. |

#### TC-R4-02: Default resources and network-owned fields are immutable

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated |

**Implementation references:** `private_virtual_networks_server_test.go`,
`private_subnets_server_test.go`, `network_acls_server_test.go`,
`it_validation_test.go`, and `tests/e2e/vmaas/regression/test_name_immutability.py`.

##### Preconditions

- Create Ready default VN `default`, Subnet `default-ipv4`, and the default
  NetworkACL associated with that Subnet for `test-defaulting-001`.
- Create a VM referencing `default-ipv4` so deletion has a dependency.

##### Steps

1. Call `VirtualNetworks/Update`, `Subnets/Update`, `SecurityGroups/Update`,
   and `NetworkACLs/Update` with a network-owned field mask.
2. Repeat with `PATCH` and full replacement payloads.
3. Call `Subnets/Delete` while the VM exists.
4. Delete the VM, then call `Subnets/Delete` and recreate the desired Subnet.

##### Expected results

- Every network-owned update, patch, and replacement returns
  `InvalidArgument` or `FailedPrecondition` according to the shared API
  operation guard; the stored spec is unchanged.
- Subnet deletion while referenced returns `FailedPrecondition` and leaves the
  Subnet present.
- After dependencies are removed, delete succeeds and a replacement can be
  created with a new immutable specification.

#### TC-R4-03: Authorized default replacement is validated

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated where user-visible |

**Implementation references:** `default_networking_provisioner_test.go`,
`network_acls_server_test.go`, `it_validation_test.go`, and
`tests/e2e/core/grpc_client.py` request/error helpers.

##### Cases

- Tenant Admin creates a replacement default in the same effective tenant
  scope after deleting the old default and removing its dependencies.
- Repeat the authorized replacement flow for the default VirtualNetwork,
  default Subnet, default SecurityGroup, default NetworkACL, and supported
  default NATGateway.
- A replacement default SecurityGroup may be empty and means default deny;
  every non-default tenant SecurityGroup requires at least one allow-only rule.
- Replacement default NetworkACL contains deny-all ingress and allow-all
  egress and is associated with the default Subnet.
- An ordinary custom NetworkACL associated with the default Subnet while the
  default ACL exists is rejected because the default ACL is already the one
  effective association. Replacing the default ACL follows the default
  replacement workflow.
- Non-default tenant-created NetworkACL has at least one valid rule and one or
  more explicit Subnet associations.
- A second active default of the same kind is created.
- A caller supplies the default label for another tenant, wrong VN, wrong
  address family, non-canonical CIDR, or an unauthorized caller tries to set
  the label.
- A replacement is created before the old default is deleted or while its
  dependency graph is still active.

##### Expected results

- Only the authorized Tenant Admin replacement in the effective scope is
  accepted; the old default must be fully deleted first.
- Each default resource kind allows at most one active default, and
  replacement uses the ordinary IPv4, same-VN, readiness, complete-manager,
  and immutable-field validation for that kind.
- The replacement default SecurityGroup retains the default-deny empty rule
  set. The replacement default NetworkACL retains the explicit default ACL
  policy. Every other user-created SecurityGroup requires at least one
  allow-only rule, and every other user-created NetworkACL requires at least
  one valid rule and one or more explicit Subnet associations.
- Competing defaults, wrong ownership/scope, invalid parent/family/CIDR,
  unauthorized labels, and premature replacement are rejected before
  persistence.
- Replacement resources remain immutable and omitted/empty workload defaulting
  remains unavailable until the replacement graph is Ready.

### R5: Automatic ExternalIP lifecycle

#### TC-R5-01: Successful automatic external access

| Test type | Priority | Automation |
|---|---|---|
| Integration, E2E | critical | automated |

**Implementation references:** `it_default_networking_test.go`,
`it_external_ip_test.go`, `external_ip_pool_selector_test.go`,
`tests/e2e/vmaas/regression/external_ip/test_external_ip_pool_lifecycle.py`,
`tests/e2e/core/grpc_client.py`, and `tests/e2e/core/helpers.py`.

##### Preconditions

- A Ready IPv4 ExternalIPPool exists with CIDR `198.51.100.0/29`, at least
  four available addresses, and no overlapping pool.
- The VM, Cluster, and BM target resources each have one Ready network
  attachment and a discoverable workload IP/VIP.
- A separate explicitly managed ExternalIP and ExternalIPAttachment exist for
  one Ready target and do not carry the auto-created label.

##### Steps

1. Set `auto_external_ip_attachment=true` in the VM and BM create requests.
2. Set it for the Cluster API and Ingress endpoints in the Cluster create
   request.
3. Observe `ExternalIPs/Create` and `ExternalIPAttachments/Create` records
   through the private API.
4. Complete target IP/VIP discovery and wait for the attachment status.
5. Delete each parent resource and observe the cleanup order.
6. Attempt to delete the target that owns the explicitly managed
   ExternalIPAttachment and verify that deletion is blocked.
7. Delete the manual attachment, delete the target, and inspect the manual
   ExternalIP.

##### Expected results

- VM and BM receive one ExternalIP; Cluster receives two, one for API and one
  for Ingress.
- Create persists Pending records only after synchronous capacity validation;
  allocation, discovery, DNAT, and Ready transitions are asynchronous.
- `ExternalIP` transitions `Pending -> Allocated` and the attachment
  transitions `Pending -> Ready`.
- DNAT targets the discovered workload IP/VIP.
- Auto-created attachments are deleted before their ExternalIPs and carry
  the canonical `osac.openshift.io/auto-created: "true"` marker and an exact
  immutable workload owner relationship. An ExternalIP may also carry
  `osac.openshift.io/auto-created-for: <resource-id>` for indexed discovery,
  but the label alone is not ownership proof.
- The `AutoExternalIPCreated` event is present on each workload that received
  automatic external access.
- The explicitly managed ExternalIPAttachment blocks target deletion until the
  tenant deletes the attachment; it is never implicitly detached or changed to
  Pending.
- After the attachment is deleted, the target can be deleted and the
  explicitly managed ExternalIP remains tenant-managed until separately
  deleted.

#### TC-R5-02: Capacity and cleanup-failure behavior

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | critical | automated |

**Implementation references:** `external_ip_pool_selector_test.go`,
`external_ip_pools_server_test.go`, `it_external_ip_test.go`,
`tests/e2e/vmaas/regression/external_ip/test_external_ip_pool_capacity.py`,
and `tests/e2e/core/helpers.py` `assert_grpc_rejected`/polling helpers.

##### Preconditions

- Create a Ready IPv4 pool `small-pool` with CIDR `198.51.100.0/30`; the
  usable capacity is two addresses.
- Configure every pool considered by automatic selection with `available: 0`
  for the exhaustion subcase.
- Create two additional Ready IPv4 pools with non-overlapping CIDRs and
  controlled capacities so that one has the greatest capacity and two can be
  configured with equal capacity for the deterministic tie-break check.
- Provide a controllable manager/finalizer fixture that can inject transient
  and permanent cleanup failures.

##### Steps

1. Call `ExternalIPs/Create` for `small-pool` when `available: 0`, then call
   `ComputeInstances/Create` with `auto_external_ip_attachment=true` for an
   otherwise valid VM while every candidate pool is exhausted.
2. Restore capacity in the additional pools and submit equivalent automatic
   ExternalIP requests while the pools have different available capacities,
   then reset capacity and repeat while two candidate pools have equal
   capacity.
3. Complete one automatic allocation successfully, delete its parent, and
   observe attachment deletion, ExternalIP release, and parent finalizer
   completion.
4. Create another automatic allocation, inject a transient cleanup failure,
   delete its parent, and observe the finalizer retry before allowing parent
   deletion.
5. Create another automatic allocation, inject a permanent cleanup failure,
   delete its parent, and wait until the controller retains the parent
   finalizer and continues reporting the parent as `Deleting`.
6. Create two test Subnets in one VirtualNetwork and associate one
   NetworkACL with both; attach a workload to one of the Subnets. Attempt
   deletion of a referenced Subnet and the VirtualNetwork and verify the ACL,
   workload attachment, and child Subnet blockers are all reported. Delete
   the workload attachment and the ACL, delete both child Subnets, and then
   retry the VirtualNetwork delete.

##### Expected results

- Pool selection chooses the Ready pool with greatest available capacity.
  Equal-capacity selection is deterministic, but the tie-break remains
  implementation-defined as specified by the design; the test asserts that
  repeated equivalent requests select the same pool without imposing a
  pool-ID ordering that the contract does not define.
- Exhaustion returns `FailedPrecondition` with the exact message:
  `ExternalIPPool exhaustion: no available capacity in any READY pool for IPv4`.
- Both explicit and automatic exhaustion failures happen before persistence;
  no parent, ExternalIP, attachment, or capacity reservation remains.
- A successful automatic request persists the ExternalIP and attachment as
  `Pending`; manager allocation and attachment/DNAT activation then proceed
  asynchronously.
- After successful parent deletion, cleanup order is
  `ExternalIPAttachment -> ExternalIP -> parent`, and the released capacity
  is available again.
- A transient cleanup failure retries through the parent finalizer.
- After permanent cleanup failure, the finalizer remains, the parent remains
  `Deleting`, and no cleanup is authorized from the auto-created label alone.
  The controller reports the failed child and retries after recovery; it does
  not intentionally leave an orphan by deleting the parent.
- Manual deletion of a tenant-created attachment must precede deletion of its
  target workload or ExternalIP. Automatic cleanup is limited to the exact
  immutable owner pair and still deletes the attachment before the ExternalIP.
- Subnet deletion reports every direct workload and NetworkACL blocker,
  including a child already `Deleting` but not archived. VirtualNetwork
  deletion reports its Subnet, SecurityGroup, NetworkACL, and NATGateway blockers. Deleting a
  NetworkACL never deletes or detaches its associated Subnets or
  VirtualNetwork.
- Every rejected delete leaves the target, dependencies, finalizers, backend
  state, and capacity unchanged; successful deletion follows leaf-first order.

#### TC-R5-03: Default NATGateway ExternalIP ownership and cleanup

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

##### Steps

1. Onboard a tenant with the complete manager profile and wait until its
   default NATGateway and ExternalIP are ready/allocated; an unfinished
   development operation must follow the approved successful no-op path.
2. Verify the ExternalIP has the canonical auto-created marker and the exact
   immutable `NATGateway/<id>` owner reference. Verify that the owner reference,
   not the label alone, is used for cleanup authorization.
3. Attempt to delete the VirtualNetwork while the default NATGateway exists.
4. Delete the default NATGateway and observe backend cleanup, ExternalIP
   cleanup, capacity release, and finalizer completion.
5. Inject a NAT backend or ExternalIP cleanup failure and retry reconciliation.
6. Recreate the default NATGateway and verify replacement allocates a new
   owned ExternalIP without changing or deleting the ExternalIPPool.

##### Expected results

- VirtualNetwork deletion is rejected with the NATGateway as a direct blocker;
  VirtualNetwork deletion does not cascade to either resource. An admitted
  NATGateway deletion may clean only its exact OSAC-owned ExternalIP under the
  separate default-NAT cleanup path below.
- An admitted NATGateway deletion cleans only its exact OSAC-owned automatic
  ExternalIP, and only after NAT backend cleanup succeeds.
- A cleanup failure retains the appropriate finalizer and leaves the resource
  visible in `Deleting`; retry succeeds after the injected failure is removed.
- The ExternalIPPool is never deleted or modified except for the released
  allocation capacity, and a tenant-created ExternalIP is never cleaned by
  this path.

### R6: Provider-owned Default Networking behavior

#### TC-R6-01: Provider-owned defaults cannot be overridden

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E rejection | high | automated |

**Implementation references:** `it_default_networking_test.go`,
`it_validation_test.go`, `private_virtual_networks_server_test.go`,
`tests/e2e/vmaas/sanity/test_virtual_network_lifecycle.py`, and
`tests/e2e/vmaas/regression/test_name_immutability.py`.

##### Preconditions

- Use `test-default-nc` and tenant `test-unsupported-001` with the valid
  shared test data.
- The default graph is Ready before exercising workload and deletion guards.

##### Steps

1. Submit each unsupported request in the table below through its corresponding
   API or CLI operation.
2. For every rejection, call the relevant `Get`/`List` method and inspect
   Kubernetes events for the affected Tenant or workload.
3. Verify that no manager job, capacity reservation, or partial resource graph
   was created.

##### Expected results

| Unsupported request | Expected result |
|---|---|
| Tenant supplies custom default CIDRs or provider defaults | `PermissionDenied`/`InvalidArgument`; provider defaults remain unchanged. |
| Tenant supplies a deployment-baseline action or override | `InvalidArgument`/`PermissionDenied`; the provider-owned baseline remains hard-coded to permit all traffic. |
| Tenant requests an automatic second VN or Subnet | `InvalidArgument`; no second resource or manager job is created. |
| Existing tenant is retroactively assigned defaults | No mutation; request is rejected or excluded by the API contract. |
| UI-only simplified creation through the API/CLI | No hidden UI behavior is exposed; normal API validation applies. |
| Ordinary tenant-created empty SecurityGroup or SecurityGroup with an action/deny rule | `InvalidArgument`; tenant-created groups require at least one allow-only rule and no action field. |
| Ordinary tenant-created empty NetworkACL or NetworkACL without Subnet associations | `InvalidArgument`; user-created ACLs require at least one rule and one or more explicit Subnet associations. |
| Authorized replacement default NetworkACL without the default ACL policy or default Subnet association | `InvalidArgument`; the replacement must install deny-all ingress and allow-all egress and be associated with the default Subnet. |
| Workload omits networking while defaults are missing | `FailedPrecondition` with `No default networking resources available. Please contact your administrator.` plus machine-readable details naming the attachment field, missing/non-Ready default, observed state, required `Ready` state, and retry remediation; no workload or attachment is persisted. |
| Workload references Pending or Failed defaults | `FailedPrecondition`; no workload or attachment is persisted and no fallback substitution occurs. |
| Delete a default resource with active dependents | `FailedPrecondition`; parent and dependent resources remain. |
| Network-owned update, patch, or replacement | Rejected with the shared CRUD guard; stored network fields are unchanged. |
| Tenant supplies an arbitrary ExternalIP address instead of a Ready pool | `InvalidArgument`; only pool allocation is accepted. |

##### Final assertions

1. For every rejected request, call the corresponding `Get`/`List` method.
2. Assert no hidden fallback, partial resource graph, manager job, capacity
   reservation, or workload dispatch was created.
3. Assert the rejection includes the expected gRPC status and field path when
   the API contract defines one.

### R7: CLI defaulting and automatic external access

#### TC-R7-01: CLI defaulting, flag mapping, and rejection parity

| Test type | Priority | Automation |
|---|---|---|
| Unit, integration, E2E | critical | automated |

The CLI must exercise the same defaulting and validation contract as the API;
it must not introduce a second defaulting path.

**Unit:** Parse `osac create computeinstance`, `osac create
baremetalinstance`, and `osac create cluster` with no
`--network-attachment`, with only `subnet=...`, with
`security-groups=...`, and with all supported fields.
Verify that the parser
preserves omitted fields for server-side defaulting, maps the resource-specific
typed attachment message, and rejects empty compound values, unknown keys,
empty keys/values, IPv6 CIDRs, multiple attachment options, `primary=false`,
malformed/duplicate/wrong-scope/non-Ready SecurityGroup references, and
unsupported interface fields for VM/Cluster. The API-level empty attachment
message remains covered by R4. Verify `--external-ip-attachment` is a
create-time boolean and has no update/patch form.

**Integration:** Submit each parsed request through the public and private
validation paths and compare it with the equivalent direct API request:

- omitted CLI attachment resolves the Subnet from the tenant default, while
  the equivalent empty attachment message follows the API-level R4 case;
- an attachment containing only Subnet preserves the explicit reference and
  receives only the default SecurityGroup;
- an attachment containing only SecurityGroups preserves the explicit groups
  and receives only the default Subnet/interface fields;
- an invalid explicit reference fails instead of silently falling back; and
- a pending or failed default returns the documented readiness error.

Run each case for VM, BM, and Cluster. Verify that the resolved request uses
the correct repeated VM/BM field or singular Cluster field and that no
resource or backend operation is persisted after a rejection.

**E2E:** In a connected single-hub deployment, create one VM, one BM, and one
Cluster for each of these two states:

1. `--external-ip-attachment` present: verify the stored create-time switch is
   `true`, VM/BM receive one automatic ExternalIP path, and Cluster receives
   its API and ingress paths.
2. The flag omitted: verify the switch is `false`, no automatic ExternalIP or
   attachment is created, and no pool capacity is consumed.

For both states, exercise omitted and explicit CLI Subnet/SecurityGroup networking
attachments. Attempt an empty compound value, a conflicting explicit
reference, a second attachment, and a network-owned update/patch; verify the
expected validation error, no fallback over an invalid explicit value, and no
partial resource graph. The API-level empty attachment message is covered by
the R4 matrix.

## Graduation gate

- All 14 test cases have explicit implementation references.
- Every test case has concrete preconditions, numbered steps or a complete
  input/case table, and observable expected results.
- Every onboarding and defaulting rule maps to a unit or integration test.
- One-manager and two-manager complete profiles have E2E coverage.
- All three workload services have omitted/empty/partial/complete coverage.
- Authorized default replacement, default SecurityGroup default-deny behavior,
  default ACL policy validation, and ordinary empty/unassociated policy
  rejection are covered.
- Failure, retry, idempotency, capacity exhaustion, cleanup, and immutability
  tests assert exact condition reasons, gRPC statuses, or resource fields.
