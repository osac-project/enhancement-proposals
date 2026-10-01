---
title: netbox-inventory-backend
authors:
  - Menny Aboush
creation-date: 2026-09-10
last-updated: 2026-09-24
tracking-link: https://redhat.atlassian.net/browse/OSAC-4347
prd: prd.md
see-also: []
replaces: []
superseded-by: []
---

# NetBox Inventory Backend for Bare Metal as a Service

## Summary

This design adds an in-tree NetBox backend to the existing bare-metal inventory
contract. NetBox supplies host capabilities, allocation state, and BMC
connection metadata; OSAC resolves a system-scoped Secret by device label, and
the existing Metal3 lifecycle provisions the corresponding BareMetalHost. One
source Secret may serve multiple devices. See [PRD](prd.md) for product
requirements.

## Motivation

OSAC currently cannot allocate bare-metal hosts from an operator's NetBox
inventory. A separate inventory duplicates device, capability, and allocation
state and can diverge during host lifecycle changes.

The backend reuses the existing BMF reconciliation path and Metal3 manager.
It adds only the NetBox adapter, its configuration, and the Secret API
consumer needed to resolve BMC credentials. Tenant-facing APIs remain
unchanged.

### Goals

- Implement the existing inventory backend contract in the BMF operator.
- Make allocation safe under concurrent requests and controller restarts.
- Preserve OSAC selector key/value semantics with administrator-managed NetBox
  custom fields.
- Keep BMC credential values outside NetBox and tenant-facing interfaces.
- Keep provisioning and deprovisioning behavior consistent with other backends.

### Assumptions

- NetBox Community is externally deployed and exposes custom fields, device
  status, pagination, and conditional updates. The provider manages the NetBox
  schema and device inventory lifecycle. OSAC manages allocation and
  provisioning, and may quarantine an eligible device with status `failed` for
  a deterministic credential-configuration error; an administrator restores
  `staged` after repair.
- [OSAC-5618](https://redhat.atlassian.net/browse/OSAC-5618) provides the
  system-scoped Secret API used for infrastructure credentials. The provider
  creates a system-scoped BMC Secret, adds one label per associated device in
  the form `osac.openshift.io/netbox-device-<device-id>: "true"`, and grants
  the BMF controller authorized read access. One Secret may carry labels for
  multiple devices; the returned Secret ID is not stored in NetBox.
- Releasing a host deletes only the runtime Kubernetes Secret; the source OSAC
  Secret remains. Automatic credential rotation is outside OSAC-1610.
- The fulfillment service persists the resolved host selector in the BMI before
  inventory allocation. The NetBox adapter does not fetch the instance type.
- The configured NetBox token, Secret API credentials, and TLS trust material
  are provided by the Cloud Infrastructure Admin through the deployment
  configuration.
- NetBox device names are optional metadata. The stable OSAC identity is
  derived from the numeric device ID as netbox-<id>; endpoint or Metal3
  namespace changes require draining affected instances.

### Non-Goals

- Creating or maintaining NetBox devices, custom-field definitions, or
  capability data.
- OS provisioning, image selection, or a new power-management implementation.
- Writing provisioning status or tenant identity back to NetBox.
- Admin inventory listing, pool monitoring, or automatic BMC credential
  rotation.

## Proposal

The BMF operator adds a NetBox client implementing the existing
inventory.Client interface. The client uses the NetBox REST API to find and
claim devices, while the existing Metal3 manager creates the BMH and its
runtime BMC Secret.

The adapter:

- Finds eligible devices using administrator-managed pool, status, owner, and
  capability fields.
- Claims and releases devices with ETag/If-Match conditional updates.
- Uses the persisted BMI selector and UID for revalidation and ownership.
- Resolves exactly one system-scoped BMC Secret by a NetBox device label
  through the authenticated OSAC private Secrets API before claiming a new
  device.
- Derives the BMH and host identity from the NetBox numeric device ID.

No new CRD or tenant-facing gRPC method is introduced. Helm values configure
the NetBox and Secret API clients; the existing Enclave Wizard may validate
their shape without contacting either service.

### Workflow Description

#### Provider onboarding

Starting state: the provider has a reachable NetBox deployment and a configured
OSAC Secret API.

1. The administrator creates the required NetBox device and scalar capability
   fields, enrolls devices with osac_managed=true, and sets their available
   status to staged.
2. The administrator creates a system-scoped BMC Secret through the OSAC
   Secret API with username and password data and adds a device-association
   label for each device that may use it. The administrator writes the BMC
   address and boot MAC to each corresponding NetBox device. Raw credentials
   and Secret IDs are never entered in NetBox.
3. The administrator configures the NetBox endpoint, API token, CA material,
   Secret API endpoint, and controller credentials in the deployment values.
4. The operator validates connectivity and fixed NetBox fields when it starts.
   Capability fields are validated when they are used by a selector.

#### Allocation (`FindFreeHost` and `AssignHost`)

1. The fulfillment service resolves the normal OSAC host selector. The
   controller calls the inventory backend's `FindFreeHost` with the persisted
   key/value map.
2. `FindFreeHost` queries NetBox for staged, managed, unowned devices matching
   all capability values and validates the returned device before selecting it.
3. The controller persists only the namespace-qualified ExternalHostID,
   containing the ID-derived name netbox-<id>.
4. The controller calls the inventory backend's `AssignHost`. `AssignHost`
   reads the device by numeric ID, revalidates ownership, availability,
   selector values, BMC address, and boot MAC, and captures its ETag.
5. Before the claim write, `AssignHost` constructs the validated device label
   key and lists system-scoped Secrets by label-key existence. It requires
   exactly one match, gets that Secret, and validates username/password.
   Missing, ambiguous, or malformed credentials are quarantined with a
   conditional `failed` status and sanitized changelog message when the device
   is still staged and unowned; no NetBox claim or Metal3 resource is created.
   Secret API outages or access configuration failures are retried without
   changing device status.
6. `AssignHost` conditionally changes status to active and writes the BMI UID
   to the owner field. A 412 response is re-read to distinguish a race from
   an already committed claim.
7. `AssignHost` runs the existing manager, which ensures the BMC Secret,
   creates or reuses the BMH, and reports readiness. The resolved values are
   used in memory and in the operator-managed runtime Secret only.

If Metal3 preparation fails after the claim, the controller keeps the
persisted host binding and retries `AssignHost`. A same-owner retry continues
from the current NetBox and Kubernetes state, so the claim is not released
while resources from that allocation remain.

#### Release (`UnassignHost`)

During deletion, the controller calls the configured inventory backend's
`UnassignHost`. For the NetBox backend, `UnassignHost` verifies that the
requesting BMI owns the NetBox claim, deletes the BMH and runtime BMC Secret
created for that allocation, waits for both resources to disappear, and then
conditionally restores status staged and clears the owner. The source OSAC
Secret is not deleted.

### Internal Contract and Implementation Changes

No public API or CRD changes are required.

The BMI provides the resolved selector in `spec.selector.hostSelector` and the
selected host identity in `spec.externalHostID`. The internal inventory
contract is extended as follows:

- `AssignHost` also receives the persisted selector so NetBox can revalidate
  it before claiming the device.
- `UnassignHost` receives the BMI UID so NetBox can verify ownership before
  cleanup and release.

`ExternalHostID` is passed to both methods as the resource identity. Existing
controller finalizer and retry behavior handles recovery from the persisted BMI
fields and current resource state.

The NetBox backend adds:

- REST client and startup factory wiring.
- Authenticated Secret API resolution.
- NetBox-specific Helm values and mounted configuration.
- Idempotent `FindFreeHost`, `AssignHost`, and `UnassignHost` operations using
  the persisted host identity and current NetBox/Kubernetes state.

## User-facing impact

The tenant-facing API and UI are unchanged: tenants continue to allocate and
release hosts through the existing BareMetalInstance workflow and do not need
NetBox or BMC credentials. Provider onboarding creates and labels the
system-scoped source Secret through the Secret API; OSAC resolves it during
allocation and raw credentials are not entered in NetBox.

## Implementation Details/Notes/Constraints

### NetBox data model

The provider creates the fields; OSAC writes allocation/quarantine state and
owner.

| Data | Owner | Use |
|---|---|---|
| osac_managed=true | Provider | Enrolls a device in the OSAC pool |
| status=staged/active/failed | OSAC | Available, claimed, or quarantined state |
| osac_instance_id | OSAC | BMI UID owning an active claim |
| osac_bmc_address | Provider | Metal3-compatible BMC address |
| osac_boot_mac | Provider | Boot NIC MAC address |
| Capability custom fields | Provider | Exact selector matches |

Fixed fields must be associated with dcim.device, use exact filtering where
queried, and allow unassigned values. Capability fields are separate scalar
fields; tags and a generic JSON capability field are not used.

Device-association labels are maintained on the system-scoped OSAC Secret, not
on the NetBox device. Releasing a host does not remove the association; the
provider changes it only when the credential association changes.

### Host identity

For NetBox device ID 42 and Metal3 namespace baremetal:

| Resource or field | Value |
|---|---|
| BMI ExternalHostID | baremetal/netbox-42 |
| BMH name | netbox-42 |
| ExternalHostName | empty |
| Runtime BMC Secret | netbox-42-bmc-secret |
| NetBox endpoint | /api/dcim/devices/42/ |

The adapter accepts only a positive canonical numeric ID and validates the
derived Kubernetes name before persistence or resource creation. It never
uses device.name, site, or region for identity or recovery. A foreign BMH or
Secret with the derived name is not adopted.

The controller persists ExternalHostID before claiming the device. On restart,
the adapter parses that ID and reads the same NetBox device. A missing or
malformed device retains the binding for repair; it is never replaced by a
lookup using a mutable name.

The existing AAP fallback uses the final segment of ExternalHostID when
ExternalHostName is empty, so networking and DHCP hostname lookup use the same
netbox-<id> value. The provider registers that value in any hostname-based
fabric inventory.

### NetBox REST contract

The adapter uses a narrow HTTPS REST surface:

- GET extras/custom-fields: paginate and validate fixed field definitions.
- GET dcim/devices: apply managed, status, empty-owner, and capability filters.
- GET dcim/devices/{id}: read the current device and ETag.
- PATCH dcim/devices/{id}: update only status and osac_instance_id with
  If-Match; credential quarantine may also include a sanitized
  `changelog_message`.

Allocation sends status active and the BMI UID. Release sends status staged and
an empty owner. A deterministic pre-claim credential error sends status failed
with an empty owner and a sanitized changelog message. PATCH never echoes BMC
credentials or overwrites unrelated custom fields.

GET requests retry bounded transient failures. A conditional PATCH is not
blindly replayed after a timeout or 5xx; reconciliation reads the device to
determine whether it committed. A direct 412 follows the same ownership
check.

The adapter requires the NetBox capabilities listed above, rather than
hardcoding a point-release matrix in this design. Pinned Community images and
their exact response shapes are tested in testplan.md.

### Selector matching

The persisted selector remains a map of field names to values. Each key is
validated against the fetched dcim.device field metadata and becomes one
exact cf_<key> query parameter. Reserved integration fields and lookup
suffixes are rejected. Supported initial field types are exact scalar text,
integer, boolean, and select values. Unsupported types and invalid values
fail closed before a candidate is claimed.

The adapter validates returned devices as well as relying on server-side
filters. Missing fields, wrong types, disabled filters, or mismatches cannot
turn a device into an eligible candidate. A valid query with no candidates is
ordinary capacity exhaustion.

### Secret resolution and Metal3

The selected credential flow is:

Provider creates or updates a system-scoped Secret with one label per device ->
BMF lists by the constructed device-label key and gets the single match ->
EnsureBMCSecret creates the namespace-scoped runtime Secret -> BMH references
the runtime Secret.

The BMF uses an authenticated private Secret API client. It does not connect
directly to Vault, Thales KMS, or another provider backend. OSAC-5618 provides
the system-scoped Secret authorization; tenant users cannot retrieve the source
Secret data.

The source Secret data contract is username and password plus at least one
device-association label. The values are validated, kept in memory during
assignment, and passed to the existing manager. EnsureBMCSecret remains
required because Metal3 expects a Kubernetes Secret named by
BareMetalHost.spec.bmc.credentialsName.

The runtime Secret is operator-managed and owner-checked. It is updated or
created only for the requesting BMI and is deleted during release. Source
Secret deletion and automatic rotation are not part of this enhancement;
providers must coordinate rotation by their normal secret lifecycle and,
where needed, drain and reassign hosts.

### Assignment and cleanup contract

AssignHost is read-first:

1. Parse and validate the saved host ID.
2. Read the device and compare status, owner, and selector.
3. Resolve and validate exactly one system-scoped labeled BMC Secret and
   connection metadata.
4. Claim with the captured ETag.
5. Ensure the runtime Secret and BMH.

A deterministic pre-claim credential-resolution failure conditionally quarantines
the still-staged, unowned device with status `failed` and a sanitized changelog
message; it writes no claim or Kubernetes resource. Transient Secret API
failures do not change NetBox status. A failed post-claim preparation retains
the claim until owned resources are removed. Same-owner retries skip the claim
PATCH and repeat idempotent resource ensures.
Different-owner claims return a race loss and are reselected by the controller.

UnassignHost requires the requesting BMI UID, uses Kubernetes deletion
preconditions, waits for resource absence, and then uses a fresh NetBox ETag.
Pool membership and capability changes do not block release of an owned host.

### Configuration

Helm values configure:

- NetBox HTTPS endpoint, API token file, and optional CA file.
- OSAC Secret API address, controller token file, and optional CA file.
- The Metal3 namespace and enabled inventory backend.

NetBox and Secret API credentials are mounted as files and are never written
to logs. BMC usernames and passwords are not deployment values and are not
mounted into BMF. The Enclave Wizard may validate required values and mutual
exclusion of inventory backends, but does not perform remote NetBox or Secret
API calls.

### Kubernetes ownership

The BMF service account retains its existing access to BMHs and namespaced
runtime Secrets. The controller adds the standard tenant and owner-reference
annotations to BMH and runtime Secret objects using trusted BMI metadata.
Cross-namespace Kubernetes ownerReferences are not used. Foreign or ownerless
objects are never adopted.

## Security Considerations

- Raw BMC credentials are stored only through OSAC Secret Management and the
  short-lived runtime Secret required by Metal3. They are not stored in NetBox,
  BMI fields, logs, error messages, or tenant-facing responses.
- System-scoped Secret reads require the controller's protected identity.
  Tenant users cannot retrieve, update, or delete the source Secret data.
- NetBox communication requires HTTPS, certificate validation, redirect
  protection, and a least-privilege API token that can read required metadata
  and update device allocation fields only.
- Selector keys, query parameters, IDs, and API responses are validated and
  sanitized before use or logging.
- The controller writes no tenant name or namespace to NetBox. The owner value
  is the BMI UID required for allocation recovery.

## Failure Handling and Recovery

| Failure | Behavior |
|---|---|
| Missing or invalid fixed NetBox fields | Startup or assignment fails closed; no broad fallback query |
| Missing, ambiguous, or malformed Secret | If still staged and unowned, set status `failed` with a sanitized changelog message; no claim, BMH, or runtime Secret |
| Secret API outage or access configuration failure | No NetBox status change; bounded retry/reconciliation backoff |
| NetBox 401/403 | Permanent request error with a sanitized admin-facing diagnostic |
| NetBox timeout/5xx | Bounded retry for reads; reconciliation requeues |
| PATCH timeout/5xx | No blind replay; next reconciliation reads ownership and resumes safely |
| PATCH 412 | Re-read; same owner resumes, another owner loses the race and is reselected |
| BMH/runtime Secret preparation failure | Claim is retained while controller performs owned-resource compensation |
| Release deletion pending | Claim and finalizer remain until resource absence is confirmed |
| Controller restart | Persisted ExternalHostID and idempotent backend reads resume the flow |
| No eligible devices | Existing generic no-hosts behavior; no backend-specific tenant error |

All write paths are idempotent. An uncertain operation never authorizes
deleting or modifying another BMI's resources.

## RBAC / Tenancy

No tenant-facing RBAC changes are required. The existing BMF service account
is limited to its configured Metal3 namespace for runtime BMH and Secret
operations. The Secret API, not the BMF service account, authorizes access to
the system-scoped source Secret.

BMHs and runtime Secrets carry the required
osac.openshift.io/tenant and osac.openshift.io/owner-reference annotations.
The controller uses the trusted BMI UID and tenant metadata; assignment labels
and NetBox values are not ownership authority. No tenant-identifying data is
sent to NetBox.

## Observability and Monitoring

The backend adds:

- osac_netbox_assignment_attempts_total, labeled by success, race, or error.
- osac_netbox_api_errors_total, labeled by sanitized error type such as 401,
  403, 5xx, timeout, or secret-resolution failure.

Structured logs record operation, error category, candidate-found status, and
field counts. They do not record selector values, full URLs, tokens,
credentials, tenant identity, or host IDs. Existing BMI conditions and
reconciliation metrics expose user-visible progress; no pool-wide capacity
gauge is added.

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| NetBox API capability or response changes | Pin and test Community images against the capability contract in testplan.md |
| External NetBox outage | Timeouts, bounded retries, reconciliation backoff, and no destructive fallback |
| Concurrent claim or release | ETag/If-Match plus owner re-read before every decision |
| Credential exposure | Secret API platform scope, least privilege, redacted logs, and no raw NetBox fields |
| Provider changes custom-field schema | Startup/per-search validation and fail-closed selection |
| Incorrect credential quarantine | Only deterministic pre-claim errors may set `failed`; use ETag/owner checks and require administrator reset to `staged` |
| Replacement device reuses a name | Numeric ID identity; never recover by device.name |

## Drawbacks

The provider must prepare several NetBox fields and maintain device-association
labels on system-scoped Secrets. Allocation performs read-before-write
validation and requires NetBox conditional-update support, so setup and
compatibility testing are more demanding than a local inventory. These costs
preserve typed selector behavior, safe concurrency, and credential isolation.

## Alternatives (Not Implemented)

### Raw BMC credentials in NetBox

This is simpler for the adapter but violates the requirement that NetBox not
be a credential store and exposes secrets to NetBox administrators and
backups. Rejected.

### BMF connects directly to Vault or a provider KMS

This avoids a Secret API call but couples the inventory backend to each
provider's secret technology and duplicates authentication and policy logic.
Rejected in favor of the existing OSAC Secret API.

### Status-only allocation

Using only NetBox status cannot distinguish an idempotent retry from another
claimant. The owner custom field and conditional update are required for
recovery. Rejected.

### Tags or one JSON capability field

Tags and a JSON blob require encoding or client-side matching and do not
preserve the existing selector key/value contract as directly as separate
scalar custom fields. Rejected.

### Separate sidecar backend

A sidecar would add deployment, networking, and version-skew cost. The
in-tree implementation follows existing BMF backend patterns and leaves a
future extraction possible. Rejected.

## Test Plan

The complete scenario inventory and requirement traceability are in
[testplan.md](testplan.md). The design retains only the coverage summary:

- Unit tests cover NetBox schema/query construction, exact selector matching,
  device-label Secret resolution, exactly-one matching, pre-claim quarantine
  behavior, ETag races, and safe logging.
- Integration tests cover BMF reconciliation with NetBox and Metal3 mocks,
  persisted host identity, same-owner recovery, cleanup ordering, and runtime
  Secret/BMH ownership.
- E2E tests cover provider onboarding, valid system-scoped Secret resolution,
  one Secret associated with multiple devices, missing/ambiguous credential
  quarantine, administrator recovery, concurrent tenant allocations,
  deallocation, restart recovery, and real NetBox API behavior.

The missing, ambiguous, or malformed Secret cases must prove that the device is
quarantined without a claim, runtime Secret, or BMH. Transient Secret API
failures must prove that device status is unchanged. The valid case must prove
that source Secret values do not appear in NetBox fixtures or logs.

## Graduation Criteria

- Dev Preview: unit and controller integration coverage passes, including
  races, cleanup, Secret isolation, and no sensitive logging.
- Tech Preview: real Community NetBox API and E2E workflows pass against the
  supported capability matrix.
- GA: the complete testplan passes with no critical allocation, recovery, or
  credential-exposure defects and provider operations documentation is
  published.

## Upgrade / Downgrade Strategy

No public API or CRD migration is required. A first deployment requires the
provider to create the NetBox fields and system-scoped Secrets with device
labels before enabling the backend. OSAC does not import raw credentials or
earlier Secret associations from any NetBox prototype.

To switch away from NetBox, stop new allocation, drain NetBox-backed BMIs, wait
for BMH/runtime Secret cleanup, verify that managed devices have no owner, and
then change the backend configuration. Do not rewrite live ExternalHostID
values or rename BMHs in place. Source OSAC Secrets are retained or retired by
the provider's normal secret lifecycle.

## Version Skew Strategy

The BMF operator, its chart, and the system-scoped Secret API from OSAC-5618
must be deployed compatibly. The Secret API must support labeled system Secrets
with username/password data and authorized reads. The configured NetBox
deployment must support the REST capability contract and ETag/If-Match updates.
Do not mix an older identity or field contract with live NetBox-backed
instances; drain before switching.

## Support Procedures

### Detect Failures

Check operator startup logs for NetBox schema, TLS, authentication, or Secret
API configuration errors. Check BMI conditions for generic allocation failure
or no-host status and inspect the NetBox owner/status fields. The metrics above
identify authentication, connectivity, race, and Secret resolution failures.

### Disable the Feature

Drain all NetBox-backed BMIs and verify BMHs, runtime Secrets, and NetBox owner
fields are cleared. Disable the NetBox backend and enable the replacement
backend through Helm. Switching before the drain can orphan NetBox claims and
is unsupported.

### Re-enable and Recovery

Restore the endpoint, token, CA, Secret API access, fields, and staged/owner
state. For a quarantined device, fix its source Secret labels or data and
restore its status to `staged`. Re-enable the backend and restart the operator.
New allocations use NetBox; existing source Secrets and prepared device
metadata remain available.

## Infrastructure Needed

NetBox and existing Metal3 management are provider-owned dependencies. The
system-scoped OSAC Secret API from OSAC-5618 is an OSAC dependency. OSAC adds
no production infrastructure. Tests require a TLS HTTP fixture, an envtest
Kubernetes API, and pinned NetBox Community images as described in testplan.md.

## Provenance

Authored: revise @ design 0.11.3 - 9b25062, workspace feat/OSAC-4742-netbox-tags-etag-design @ f0a8211

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.3","ai_workflows":"9b25062","source_repo":"f0a8211","source_repo_branch":"feat/OSAC-4742-netbox-tags-etag-design","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["revise","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":true} -->
