---
title: default-networking
authors:
  - dmanor@redhat.com
creation-date: 2026-07-08
last-updated: 2026-10-22
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1433
prd: "prd.md"
see-also:
  - "/enhancements/OSAC-1433-unified-networking"
  - "/enhancements/OSAC-1435-vmaas-networking"
  - "/enhancements/OSAC-1436-caas-networking"
  - "/enhancements/OSAC-1437-bmaas-networking"
replaces:
  - N/A
superseded-by:
  - N/A
---

# Default Networking — Simplified Resource Creation

## Contents

- [Summary](#summary)
- [Motivation](#motivation)
  - [Goals](#goals)
  - [Non-Goals](#non-goals)
- [Proposal](#proposal)
  - [Workflow Description](#workflow-description)
    - [Default networking at tenant onboarding](#default-networking-at-tenant-onboarding)
    - [Shared attachment resolution](#shared-attachment-resolution)
    - [Automatic external access](#automatic-external-access)
    - [Inspecting default resources](#inspecting-default-resources)
    - [Default Subnet address plan](#default-subnet-address-plan)
    - [Replacing the NetworkClass](#replacing-the-networkclass)
  - [API Extensions](#api-extensions)
    - [Proto (fulfillment-service)](#proto-fulfillment-service)
    - [Tenant status (fulfillment-service)](#tenant-status-fulfillment-service)
    - [NetworkClass (osac-operator)](#networkclass-osac-operator)
    - [Server validation (fulfillment-service)](#server-validation-fulfillment-service)
  - [Implementation Details/Notes/Constraints](#implementation-detailsnotesconstraints)
    - [Default resource lifecycle](#default-resource-lifecycle)
    - [Service-specific endpoint flows](#service-specific-endpoint-flows)
    - [Provider networking disabled](#provider-networking-disabled)
    - [Component responsibilities](#component-responsibilities)
  - [Security Considerations](#security-considerations)
  - [Failure Handling and Recovery](#failure-handling-and-recovery)
    - [Tenant onboarding failures](#tenant-onboarding-failures)
  - [RBAC / Tenancy](#rbac--tenancy)
  - [Observability and Monitoring](#observability-and-monitoring)
  - [Risks and Mitigations](#risks-and-mitigations)
    - [Risk: ExternalIPPool exhaustion](#risk-externalippool-exhaustion)
    - [Risk: Default SecurityGroup too permissive](#risk-default-securitygroup-too-permissive)
  - [Drawbacks](#drawbacks)
- [Edge cases that need handling](#edge-cases-that-need-handling)
  - [Onboarding races](#onboarding-races)
- [Alternatives (Not Implemented)](#alternatives-not-implemented)
- [Test Plan](#test-plan)
  - [Unit Tests](#unit-tests)
  - [Integration Tests](#integration-tests)
  - [Edge-case tests (later)](#edge-case-tests-later)
- [Graduation Criteria](#graduation-criteria)
- [Upgrade and Downgrade Strategy](#upgrade-and-downgrade-strategy)
- [Version Skew Strategy](#version-skew-strategy)
- [Support Procedures](#support-procedures)
- [Infrastructure Needed](#infrastructure-needed)

## Summary

This design extends [Unified Networking](/enhancements/OSAC-1433-unified-networking/design.md) with tenant defaults. Tenant onboarding creates a default VirtualNetwork, IPv4 Subnet, and SecurityGroup from the NetworkClass defaults, plus an ExternalIP and a NATGateway when provider networking is enabled. When it is disabled, default attachment resolution works, but OSAC promises no connectivity and no outbound NAT. Defaults are IPv4 only.

The [VMaaS](/enhancements/OSAC-1435-vmaas-networking/design.md), [CaaS](/enhancements/OSAC-1436-caas-networking/design.md), and [BMaaS](/enhancements/OSAC-1437-bmaas-networking/design.md) designs define each workload's request field, interface mapping, and endpoint flows. The Unified [deployment](/enhancements/OSAC-1433-unified-networking/design.md#deployment-support-boundary) and [hub](/enhancements/OSAC-1433-unified-networking/design.md#networking-hub-support-boundary) support boundaries apply. Unified owns [automatic external access](/enhancements/OSAC-1433-unified-networking/design.md#automatic-external-access). Managers follow the [Network Manager Integration Contract](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md). Requirements are in the [PRD](prd.md).

## Motivation

A provider-connected resource needs a VirtualNetwork, Subnet, SecurityGroup, ExternalIP, and ExternalIPAttachment besides itself. With provider networking enabled, default networking makes this one create command.

### Goals

- Single-call resource creation with sensible networking defaults
- Default networking resources created at tenant onboarding
- Optional network attachment field on every resource type, at most one per workload
- Tenant-scoped defaults under the unified create/read/delete lifecycle, with its [SecurityGroup rule update](/enhancements/OSAC-1433-unified-networking/design.md#api-operation-constraint)

### Non-Goals

- Custom defaults per tenant (all tenants get the same defaults)
- Auto-provisioning VirtualNetworks or Subnets beyond the defaults
- UI simplified creation beyond the workload wizards' **Use tenant default network** toggle ([UI design](/enhancements/OSAC-1433-unified-networking/ui-design.md#workload-network-attachment-pickers)); other simplified creation is API and CLI only

## Proposal

### Workflow Description

#### Default networking at tenant onboarding

1. **Cloud Infrastructure Admin sets the NetworkClass defaults** (IPv4 CIDRs, SecurityGroup rules) in the Helm value `global.networking.networkClass`; the installer creates the NetworkClass from it ([Unified — NetworkClass](/enhancements/OSAC-1433-unified-networking/design.md#networkclass)). None of its values, the address plan included, can change later; to change them, see [Replacing the NetworkClass](#replacing-the-networkclass). Onboarding waits for the NetworkClass and pools as [Default resource lifecycle](#default-resource-lifecycle) states.

2. **Cloud Provider Admin creates Tenant with provider networking enabled:**
   ```bash
   osac create tenant --name acme-corp
   ```
   - The fulfillment service creates the Tenant record, then, from the deployment's single NetworkClass, the [default-labeled](#proto-fulfillment-service) VirtualNetwork (`virtual_network_ipv4_cidr`), IPv4 Subnet (`subnet_ipv4_cidr`), SecurityGroup (default rules), ExternalIP, and NATGateway (on the default VirtualNetwork).
   - They go through its own API and the normal path of tenant-created resources ([Unified — Proposal](/enhancements/OSAC-1433-unified-networking/design.md#proposal)).
   - The Tenant condition `DefaultNetworkingReady` tracks readiness ([Tenant status](#tenant-status-fulfillment-service)); with provider networking enabled, default-based workload creates need it True ([Unified — Creation readiness gates](/enhancements/OSAC-1433-unified-networking/design.md#creation-readiness-gates)).

3. **If provisioning fails,** see [Tenant onboarding failures](#tenant-onboarding-failures).

#### Shared attachment resolution

For omitted or unspecified network fields, the fulfillment service applies the shared [network attachment presence and defaulting rules](/enhancements/OSAC-1433-unified-networking/design.md#network-attachment-field-presence-and-defaulting) and stores the resolved Subnet and SecurityGroups with the workload.

#### Automatic external access

A workload's automatic external access follows [Unified — Automatic external access](/enhancements/OSAC-1433-unified-networking/design.md#automatic-external-access); its endpoints follow the [service designs](#service-specific-endpoint-flows).

#### Inspecting default resources

```bash
osac get virtualnetworks --filter "this.metadata.labels['osac.openshift.io/default'] == 'true'"
osac get subnets --filter "this.metadata.labels['osac.openshift.io/default'] == 'true'"
osac get securitygroups --filter "this.metadata.labels['osac.openshift.io/default'] == 'true'"
osac get externalips --filter "this.metadata.labels['osac.openshift.io/default'] == 'true'"
osac get natgateways --filter "this.metadata.labels['osac.openshift.io/default'] == 'true'"
```

- Only the fulfillment service sets the label `osac.openshift.io/default` ([Unified — Error codes](/enhancements/OSAC-1433-unified-networking/design.md#error-codes)). Labels are immutable, so a default cannot be unlabeled.
- Tenants cannot delete defaults ([Unified — Deletion dependency guards](/enhancements/OSAC-1433-unified-networking/design.md#deletion-dependency-guards)); OSAC deletes them only with the Tenant. A tenant can replace the default SecurityGroup's rules ([Unified — API operation constraint](/enhancements/OSAC-1433-unified-networking/design.md#api-operation-constraint)); every other default stays as created. For other settings, a Tenant Admin selects other resources explicitly.
- Default selection uses the tenant's one default-labeled resource of each kind. A missing or not READY default fails the create ([Unified — Error codes](/enhancements/OSAC-1433-unified-networking/design.md#error-codes)).

#### Default Subnet address plan

The default Subnet gets the deployment's [address plan](/enhancements/OSAC-1433-unified-networking/design.md#subnet-address-plan). The installer checks that the default `subnet_ipv4_cidr` meets the plan's [prefix limit](/enhancements/OSAC-1433-unified-networking/design.md#subnet-address-layout), so onboarding never fails that check.

Enabling BMaaS or CaaS once tenant defaults exist is [not supported in this release](/enhancements/OSAC-1433-unified-networking/design.md#subnet-address-plan).

#### Replacing the NetworkClass

Replacing the fixed NetworkClass replaces the deployment's networking; a rollout with changed NetworkClass values fails without these steps ([Unified — NetworkClass](/enhancements/OSAC-1433-unified-networking/design.md#networkclass)). The Cloud Infrastructure Admin:

1. Deletes every workload, then every non-default tenant networking resource, then every Tenant (which deletes its defaults) except the reserved `system` and `shared` tenants, which have no defaults. Each delete must be able to finish: it runs the recorded managers' delete tasks, so the execution environment image must still hold the recorded roles (a wrong role name: [contract §4.3](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#43-invocation-settings-and-secrets)).
2. Deletes every ExternalIPPool, then the NetworkClass ([deletion guards](/enhancements/OSAC-1433-unified-networking/design.md#deletion-dependency-guards)).
3. Rolls out the new Helm values; the installer creates the new NetworkClass. Once it is READY, creates the ExternalIPPools, which take their managers from it.
4. Re-creates the Tenants, whose defaults come from the new NetworkClass.

### API Extensions

#### Proto (fulfillment-service)

**NetworkClass defaults:** private `NetworkClassSpec.defaults` ([Unified — NetworkClass](/enhancements/OSAC-1433-unified-networking/design.md#networkclass)).

**Default label:** every onboarding default (VirtualNetwork, Subnet, SecurityGroup, ExternalIP, NATGateway) carries:
```yaml
metadata:
  labels:
    osac.openshift.io/default: "true"
```

The default NATGateway's ExternalIP, `default-nat`, has creator `system` and the default label but no `auto-created` labels, so it is not [automatic](/enhancements/OSAC-1433-unified-networking/design.md#automatic-external-access). Tenants cannot use `default-nat` or create a NATGateway on the default VirtualNetwork ([Unified — gates](/enhancements/OSAC-1433-unified-networking/design.md#creation-readiness-gates)).

#### Tenant status (fulfillment-service)

The private fulfillment Tenant `status.conditions` has `TENANT_CONDITION_TYPE_DEFAULT_NETWORKING_READY` (shown as `DefaultNetworkingReady`) with status, reason, and message. The Tenant `state` does not use it.

- `True`, `AllResourcesReady`: provider networking enabled; the default VirtualNetwork, IPv4 Subnet, SecurityGroup, and NATGateway are READY.
- `True`, `ReservedTenant`: the reserved tenants `system` and `shared` need no defaults.
- `True`, `ProvisioningDisabled`: provider networking disabled; the default VirtualNetwork, IPv4 Subnet, and SecurityGroup are READY; a default ExternalIP or NATGateway is not required.
- `False`, `ResourcesPending`: a required default is PENDING, or onboarding waits for the NetworkClass or a READY ExternalIPPool; the message says which.
- `False`, `ResourceFailed`: a required default is FAILED, or the default ExternalIP create failed because every READY IPv4 ExternalIPPool is full; the message names the resources or the pool problem.
- `False`, `Deleting`: the Tenant is DELETING ([Tenant deletion](#default-resource-lifecycle)); the message names the defaults left.

#### NetworkClass (osac-operator)

The operator NetworkClass CR carries the same `defaults`. Default SecurityGroups are ordinary SecurityGroups ([Unified — SecurityGroup](/enhancements/OSAC-1433-unified-networking/design.md#securitygroup)).

#### Server validation (fulfillment-service)

**NetworkClass defaults validation:** [Unified — NetworkClass](/enhancements/OSAC-1433-unified-networking/design.md#networkclass) (CIDRs, the default Subnet against the address plan's [prefix limit](/enhancements/OSAC-1433-unified-networking/design.md#subnet-address-layout), excluded ranges, rule schema), so onboarding cannot fail a CIDR or rule check. For physical range sizing, see [BMaaS — Risks and Mitigations](/enhancements/OSAC-1437-bmaas-networking/design.md#risks-and-mitigations).

**Resource creation with optional network attachment fields:** see [Shared attachment resolution](#shared-attachment-resolution).

**Default ExternalIP pool:** the default NATGateway's ExternalIP uses the READY IPv4 pool with the lowest API ID that has `available` > 0 (automatic ExternalIPs choose differently: [Unified](/enhancements/OSAC-1433-unified-networking/design.md#automatic-external-access)).

### Implementation Details/Notes/Constraints

#### Default resource lifecycle

- **Creation:** with provider networking enabled, the VirtualNetwork and the ExternalIP; then the Subnet and SecurityGroup once the VirtualNetwork is READY; then the NATGateway once the VirtualNetwork is READY and the ExternalIP ALLOCATED. With provider networking disabled, the VirtualNetwork; then the Subnet and SecurityGroup; it creates no ExternalIP or NATGateway ([Provider networking disabled](#provider-networking-disabled)). The fulfillment service's internal reconciler drives the steps on Signal RPC status updates, under the shared [creation readiness gates](/enhancements/OSAC-1433-unified-networking/design.md#creation-readiness-gates).
- **Names:** Subnet `default-ipv4`, ExternalIP `default-nat`, every other kind `default`. A repeated step finds the existing default by tenant, kind, name, and the label `osac.openshift.io/default`, and never creates a second one; a tenant resource with the same name and no label is ignored.
- **Waiting for the NetworkClass and pools:** while the NetworkClass is not READY, or, with provider networking enabled, no IPv4 ExternalIPPool is READY, onboarding waits with `DefaultNetworkingReady=False`, reason `ResourcesPending`, and a message naming what it waits for. It retries on NetworkClass and pool Signal events. If READY IPv4 pools exist but all are full, the default ExternalIP create fails at once ([Tenant onboarding failures](#tenant-onboarding-failures)); freed capacity later does not restart onboarding.
- **Tenant deletion:** subject to the Tenant [deletion guard](/enhancements/OSAC-1433-unified-networking/design.md#deletion-dependency-guards); otherwise Delete returns OK and the Tenant is DELETING. DELETING is `metadata.deletion_timestamp` set on the Tenant; `DefaultNetworkingReady` becomes `False`, reason `Deleting`, with a message naming the defaults left. From then on the reconciler creates no default, and the fulfillment service rejects any create in that tenant with `FAILED_PRECONDITION`, so no record is stored in a tenant after its delete is accepted ([Unified — Concurrent requests](/enhancements/OSAC-1433-unified-networking/design.md#concurrent-requests)). The fulfillment service's internal reconciler deletes the defaults, each after its dependents are gone: the NATGateway, then its ExternalIP; the Subnet and SecurityGroup; then the VirtualNetwork ([contract §4.7](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#47-ordering-concurrency-retries-and-ownership)). It removes the Tenant record when the last default is gone. A default whose delete task keeps failing stays DELETING and is retried ([contract §4.6](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#46-task-result-and-errors)), so the Tenant stays DELETING until the provider repairs the backend.

#### Service-specific endpoint flows

Endpoint count, address discovery, bootstrap dependencies, routing domains, cluster bootstrap, and endpoint publication belong to the [VMaaS](/enhancements/OSAC-1435-vmaas-networking/design.md), [BMaaS](/enhancements/OSAC-1437-bmaas-networking/design.md), and [CaaS](/enhancements/OSAC-1436-caas-networking/design.md) designs.

#### Provider networking disabled

With [provider networking disabled](/enhancements/OSAC-1433-unified-networking/design.md#provider-networking-control), onboarding creates the default VirtualNetwork, IPv4 Subnet, and SecurityGroup through their normal API paths; they become READY with reason `ProvisioningDisabled` once their gates pass. It creates no default ExternalIP or NATGateway: an ExternalIP create is rejected while provider networking is disabled, and a NATGateway needs an ALLOCATED ExternalIP. `DefaultNetworkingReady=True`, reason `ProvisioningDisabled`, means default attachment resolution works, not provider connectivity or outbound NAT.

#### Component responsibilities

| Component | Responsibility |
|-----------|---------------|
| fulfillment-service | Validate NetworkClass defaults; create and delete the tenant defaults with provider networking enabled or disabled ([Default resource lifecycle](#default-resource-lifecycle)); resolve attachment defaults; track DefaultNetworkingReady |
| Networking controller | Reconcile defaults like any other networking resource |
| osac-installer | Create the NetworkClass, with its validated address plan, from the Helm values when none exists, and fail the rollout when a fixed value differs ([Unified — Subnet address plan](/enhancements/OSAC-1433-unified-networking/design.md#subnet-address-plan)) |

### Security Considerations

No new authentication or authorization changes ([Unified — RBAC / Tenancy](/enhancements/OSAC-1433-unified-networking/design.md#rbac--tenancy)).
- `osac.openshift.io/tenant` propagates from the Tenant to its defaults.
- Default SecurityGroup rules apply to all tenants, so the Cloud Infrastructure Admin should allow only minimal access (for example SSH and HTTPS). Cluster workers do not depend on them; each Cluster gets an automatic SecurityGroup ([CaaS design](/enhancements/OSAC-1436-caas-networking/design.md)).
- Tenant Admins can tighten the default SecurityGroup's rules, which also applies to running workloads that use it, or create other SecurityGroups for later workloads.

### Failure Handling and Recovery

Workload creates and automatic access: [Unified — Failure Handling and Recovery](/enhancements/OSAC-1433-unified-networking/design.md#failure-handling-and-recovery).

#### Tenant onboarding failures

Each case below sets `DefaultNetworkingReady=False`, reason `ResourceFailed`:
- **A default VirtualNetwork, IPv4 Subnet, SecurityGroup, or (provider networking enabled) NATGateway becomes FAILED.** The message names it (for example `Default networking resources failed: subnet default`).
- **READY IPv4 ExternalIPPools exist, but all are full.** The default ExternalIP create fails at once; the message says no READY IPv4 pool has capacity. (No READY pool at all: onboarding waits, [Default resource lifecycle](#default-resource-lifecycle).)
- **Default ExternalIP allocation fails finally** ([contract §4.6](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#46-task-result-and-errors)). It becomes FAILED.

**Recovery:** OSAC retries no onboarding step. The condition follows the defaults' states, so a FAILED default SecurityGroup fixed by an [Update](/enhancements/OSAC-1433-unified-networking/design.md#securitygroup) makes it True once every other default is READY. Otherwise the Cloud Infrastructure Admin adds pool capacity, or the Cloud Provider Admin repairs the cause (see networking controller and AAP job logs), then deletes and re-creates the Tenant.

### RBAC / Tenancy

No RBAC or tenancy changes ([Security Considerations](#security-considerations)). Tenant Users can list and get, but not delete, default resources.

### Observability and Monitoring

Structured fulfillment service logs (no Kubernetes events):
- `CreatingDefaultNetworking` (info): onboarding started creating the tenant's defaults.
- `DefaultNetworkingReady` (info): the condition became True, with its reason.
- `DefaultNetworkingFailed` (error): the condition became False, reason `ResourceFailed`, naming the failed resource.
- `PopulatedNetworkAttachmentsDefaults` (info): a workload's network attachment field was filled from tenant defaults.

No new metrics or alerts. Automatic external access logs: [Unified — Observability and Monitoring](/enhancements/OSAC-1433-unified-networking/design.md#observability-and-monitoring).

### Risks and Mitigations

#### Risk: ExternalIPPool exhaustion

**Impact:** New Tenants fail onboarding (`ResourceFailed`), and automatic external access is rejected ([Unified](/enhancements/OSAC-1433-unified-networking/design.md#automatic-external-access)).

**Mitigation:** Pool capacity is visible in status; the error tells the tenant to contact the admin; the Cloud Infrastructure Admin adds pools.

#### Risk: Default SecurityGroup too permissive

**Impact:** All tenants get the same default rules; a misconfiguration may expose every tenant's resources.

**Mitigation:** Minimal default rules and tenant replacement groups ([Security Considerations](#security-considerations)).

### Drawbacks

- All tenants get the same default CIDRs, which can confuse tenants who expect unique ranges ([Alternatives](#alternatives-not-implemented)).

## Edge cases that need handling

These cases are not normative yet: the body describes the normal flow and does not depend on them. Each entry gives the case, why it matters, and the handling we propose. Fulfillment service cases shared with every resource are in [Unified — Edge cases that need handling](/enhancements/OSAC-1433-unified-networking/design.md#edge-cases-that-need-handling).

### Onboarding races

| Case | Why it matters | Proposed handling |
|---|---|---|
| Two onboarding steps for one tenant run at once (for example after a fulfillment service restart). | Both could create the same default. | The fixed name plus the default label make the step idempotent; the create transaction locks the Tenant record, so the second step finds the first one's default. |
| A Tenant delete races an onboarding step or a create in that tenant. | A default or other record could be stored after the delete is accepted. | The delete sets DELETING under the Tenant lock, and every onboarding step and tenant create checks DELETING under the same lock ([Unified — Fulfillment service concurrency](/enhancements/OSAC-1433-unified-networking/design.md#fulfillment-service-concurrency)). |
| The chosen pool for `default-nat` fills between the choice and the commit. | Onboarding would fail although another READY pool has room. | Recheck the pool under its lock; if it filled, try the next READY pool by API ID. |

## Alternatives (Not Implemented)

| Alternative | Why rejected |
|---|---|
| A unique default CIDR per tenant, allocated from a global pool. | Needs IPAM, allocation tracking, and exhaustion handling, and overlap is allowed: every manager isolates overlapping VirtualNetworks ([contract §4.7](/enhancements/OSAC-1433-network-manager-integration-contract-networking/design.md#47-ordering-concurrency-retries-and-ownership)). One default CIDR is simpler. |
| On pool exhaustion, create a FAILED resource instead of returning an error. | OSAC checks pool capacity synchronously and fails the call atomically with nothing stored; a FAILED resource would add cleanup work. Trade-off: rejected requests leave no audit trail. |

## Test Plan

Automatic external access is tested in [Unified](/enhancements/OSAC-1433-unified-networking/design.md#test-plan) and the workload service designs.

### Unit Tests

fulfillment-service unless noted:
- NetworkClass defaults validation: CIDRs, SecurityGroupRule fields; a default `subnet_ipv4_cidr` over the address plan's prefix limit fails the rollout and names the field
- Attachment resolution: omitted, empty, partial, and complete explicit attachments
- Default ExternalIP pool: lowest API ID among READY IPv4 pools with `available` > 0; no READY pool waits; all full fails with `ResourceFailed`
- Onboarding with provider networking enabled: default-labeled VirtualNetwork, IPv4 Subnet, SecurityGroup, ExternalIP, and NATGateway, in the creation order above
- `DefaultNetworkingReady` with provider networking enabled, with it disabled, and when a required default fails
- Onboarding with provider networking disabled: no ExternalIP or NATGateway create, gates not weakened, `True`/`ProvisioningDisabled`
- Tenant delete: OK and DELETING; defaults deleted in order; record removed after the last default
- Tenant DELETING: `DefaultNetworkingReady=False`, reason `Deleting`; no pending default is created; a create in that tenant fails with `FAILED_PRECONDITION`

### Integration Tests

- Onboarding with provider networking enabled and disabled creates the right defaults, all readable and usable by workloads.
- Failed default provisioning keeps the tenant unready with an actionable diagnostic.
- Attachment resolution follows the shared matrix; incompatible Subnet/SecurityGroup combinations are rejected.
- Defaults allow create/read/delete only, plus the default SecurityGroup's rule update, which updates its policy objects and so its workloads; they are replaceable once dependents are gone.
- Tenant created before the NetworkClass or any ExternalIPPool is READY: `False`/`ResourcesPending`, then defaults created on the Signal event.
- Default Subnet provisioning fails: `False`/`ResourceFailed`; deleting and re-creating the Tenant recovers.
- A FAILED default SecurityGroup fixed by an Update: the condition becomes True once every other default is READY, without an onboarding retry.
- Every READY pool full at onboarding: `False`/`ResourceFailed` at once; freeing capacity later does not restart onboarding.
- Tenant Admin creates a NATGateway on the default VirtualNetwork, or attaches `default-nat`, during onboarding: `FAILED_PRECONDITION`; onboarding reaches `AllResourcesReady`.
- Tenant Admin creates a VirtualNetwork named `default` before the onboarding step: onboarding ignores it and creates the labeled default.
- A default's delete task keeps failing: the default and the Tenant stay DELETING; after repair the retries finish and the Tenant record is removed.
- NetworkClass replacement: each out-of-order delete (pool holding `default-nat`, NetworkClass, Tenant with dependents) fails with `FAILED_PRECONDITION`; after the full sequence, a new Tenant's `default-nat` comes from a pool under the new NetworkClass.

### Edge-case tests (later)

Once the [edge-case handling](#edge-cases-that-need-handling) is accepted:
- The chosen pool fills between the choice and the create: the next READY pool by API ID is used.
- Tenant delete racing an onboarding step or a create in that tenant: nothing is stored after the delete is accepted.

## Graduation Criteria

Ready for OSAC 0.2, with [Unified](/enhancements/OSAC-1433-unified-networking/design.md#graduation-criteria), when:
- Onboarding creates the defaults with provider networking enabled and disabled, and `DefaultNetworkingReady` reports every reason above.
- Workload services can omit network selection and use the shared defaulting.
- Tenant delete removes the defaults in order.
- Unit and integration tests pass.
- User documentation covers simplified resource creation and default resources.

## Upgrade and Downgrade Strategy

Not supported: delete everything and reinstall ([Unified — Upgrade and Downgrade Strategy](/enhancements/OSAC-1433-unified-networking/design.md#upgrade-and-downgrade-strategy)).

## Version Skew Strategy

Shared rules: [Unified](/enhancements/OSAC-1433-unified-networking/design.md#version-skew-strategy). Default Networking adds no component of its own.

## Support Procedures

**`DefaultNetworkingReady=False` while provider networking is enabled.** Read the condition with `osac get tenant acme-corp -o yaml` (`status.conditions`). A required default VirtualNetwork, IPv4 Subnet, SecurityGroup, ExternalIP, or NATGateway failed. Find the default that is not READY ([Inspecting default resources](#inspecting-default-resources)), check the networking controller and AAP job logs, and fix the cause (for example AAP connectivity or a Fabric Manager error). A FAILED default SecurityGroup can be fixed by an Update; otherwise run `osac delete tenant acme-corp`, then `osac create tenant --name acme-corp`.

**Deletion waits for automatic external cleanup.** The workload and its automatic ExternalIPAttachment or ExternalIP stay DELETING, with the failed `detach_external_ip` or `delete_external_ip` task's message. A Tenant stays DELETING the same way when a default's delete task fails. Read the failed `status.jobs` entry and its AAP job, then repair the provider backend or manager settings; retries finish the cleanup in the [Unified order](/enhancements/OSAC-1433-unified-networking/design.md#automatic-external-access). Admission rejects removing finalizers by hand ([Unified — Non-Goals](/enhancements/OSAC-1433-unified-networking/design.md#non-goals)).

**Disabling automatic ExternalIP requests by exhausting pools.** Applies only with provider networking enabled; this is not the `global.networking.provisioningEnabled` setting. No switch disables automatic ExternalIP requests, but when no READY pool has capacity they fail at admission; manual ExternalIP workflows are unaffected. Every Cluster create needs automatic ExternalIPs ([CaaS](/enhancements/OSAC-1436-caas-networking/design.md#automatic-external-access)), so all Cluster creates fail too. New Tenants get `DefaultNetworkingReady=False`, reason `ResourceFailed`, because the default NATGateway needs an ExternalIP.

**Installing with provider networking disabled.** Set `global.networking.provisioningEnabled=false` in Helm or the Enclave Wizard at installation; it cannot change later ([Unified — Provider networking control](/enhancements/OSAC-1433-unified-networking/design.md#provider-networking-control)). Onboarding then behaves as [Provider networking disabled](#provider-networking-disabled) describes.

## Infrastructure Needed

- osac-installer and fulfillment-service changes: [Component responsibilities](#component-responsibilities)
- Integration test environment: kind cluster with Tenant, NetworkClass, ExternalIPPool resources

---

## Provenance

Authored: revise @ design 0.11.3 - cc0daa6, workspace main @ 06d340f90 (43 behind origin/main)
Final: manual-edit [manual] @ design 0.11.5 - 0c7ea35, workspace main @ 14c4d6f1c (17 behind origin/main)

> Context changed between revise and manual-edit.

> This document's phase history does not include an initial /draft — structure was not verified against the template from origin.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"0c7ea35","source_repo":"14c4d6f1c","source_repo_branch":"main","commits_behind_main":17,"commits_ahead_main":0,"main_ref":"main","phases":["revise","revise","respond","revise","revise","revise","manual-edit","revise","manual-edit","revise","manual-edit","revise","respond","manual-edit","revise","manual-edit"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":true} -->
