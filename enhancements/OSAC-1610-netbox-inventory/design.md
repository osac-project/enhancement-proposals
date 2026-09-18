---
title: netbox-inventory-backend
authors:
  - Menny Aboush
creation-date: 2026-09-10
last-updated: 2026-09-17
tracking-link: https://redhat.atlassian.net/browse/OSAC-4347
prd: prd.md
see-also: []
replaces: []
superseded-by: []
---

# NetBox Inventory Backend for Bare Metal as a Service

## Summary

This design adds NetBox as a pluggable inventory backend for bare-metal host allocation in OSAC, following the existing backend pattern. Cloud Infrastructure Admin configures the NetBox endpoint and certificate material through Helm values; the chart renders the API-token and CA Secrets referenced by the operator's inventory configuration. OSAC allocates hosts transparently from NetBox inventory without exposing backend details to tenants. See [PRD](prd.md) for detailed requirements.

## Motivation

OSAC's current inventory backends serve specific infrastructure patterns, but there are operators that manage their primary physical inventory in NetBox, a comprehensive infrastructure resource management system. Lack of NetBox integration forces operators to maintain a separate OSAC-specific inventory, creating data inconsistency and operational overhead during lifecycle changes (adding hosts, decommissioning, updating capability metadata).

The NetBox backend integrates into OSAC's existing pluggable inventory system (`inventory.Client` interface) without changing tenant-facing APIs or workflows. Cloud Infrastructure Admin configures the backend; allocation and deallocation remain transparent to tenants via standard `BareMetalInstance` API.

Deployment is in-tree (compiled into the operator) following established patterns for BCM and Metal3, with configuration exposed as Helm values that an existing Enclave Wizard pipeline may schema-validate. Direct Helm deployment remains supported. This approach avoids operational complexity of separate services while maintaining the option for future out-of-tree extraction per OSAC-3806.

### Goals

- Implement the `inventory.Client` interface for NetBox, following existing backend patterns.

- Prevent double-allocation of hosts via atomic assignment in NetBox with ETag-based optimistic locking (If-Match on PATCH; 412 Precondition Failed on conflict).
- Track allocation state in NetBox's native device status (`staged` available, `active` claimed), with `osac_instance_id` identifying the claiming BareMetalInstance for crash recovery and idempotency.
- Support `BareMetalInstanceType` host selection via pre-created NetBox tags (server-side filtering with AND semantics across tags); selector keys are exact NetBox tag slugs and the generic selector values are ignored by this backend.
- Expose Helm configuration for the NetBox endpoint, credentials, and TLS certificates; an existing Enclave Wizard pipeline may schema-validate these values without exposing secrets in logs or error messages.
- Maintain tenant transparency — allocation/deallocation workflows identical across all backends; no NetBox-specific UX.

### Assumptions

- NetBox is an operator-managed external dependency. OSAC does not create or manage NetBox devices, tags, custom fields, or its infrastructure.
- The NetBox deployment permits OSAC to persist allocation state in the native device `status` and the `osac_instance_id` custom field. These are integration prerequisites, not fields created by OSAC at runtime.
- The `BareMetalInstanceType.host_label_selector` is the placement-label source. For NetBox, each selector key is an existing NetBox tag slug; NetBox tags are names rather than key/value pairs, so the adapter uses the keys and ignores the non-empty generic selector values. The adapter does not derive placement tags from CPU, memory, or accelerator fields and does not fetch the instance type at allocation time.
- The API token is granted only the read/update permissions required for the documented device and custom-field operations.

### Non-Goals

- NetBox catalog management (adding/removing devices or editing hardware metadata) — operator's responsibility; the backend only writes the documented allocation status and owner field.
- OS provisioning or image selection — orthogonal to inventory allocation; existing Metal3/BMH integration used.
- Provisioning status reporting back to NetBox — only the allocation state (`staged`/`active`) and owner identifier are recorded.
- Health checks on assigned nodes — if a node is deleted from NetBox while assigned, OSAC does not proactively detect it.
- Admin host-listing or inventory visibility in OSAC API.

## Proposal

NetBox backend is implemented in `bare-metal-fulfillment-operator/internal/inventory/netbox.go`, following the existing backend pattern. A new `NetBoxClient` struct implements the `Client` interface with the following methods. Because the client reuses the existing `baremetalhost.Manager` BMH lifecycle manager, operator startup wires it through the same dependency-injection/factory path used by the existing BCM backend; this does not change the `inventory.Client` interface or the controller's reconciliation state machine. A small shared logging hardening change is required at the existing controller boundary so raw selectors, host IDs, and instance IDs are not emitted by the generic allocation logs.

- **`FindFreeHost(ctx, matchExpressions)`** — Query NetBox for unassigned pool devices filtered by the NetBox tag slugs in the selector keys (server-side); return the first matching candidate as the deterministic `<metal3 namespace>/netbox-device-<id>` host ID or nil.
- **`AssignHost(ctx, inventoryHostID, bareMetalInstanceID, labels)`** — Resolve the NetBox device ID from the host ID, atomically mark it assigned using ETag-based optimistic locking, and ensure the Metal3 resources; idempotent for crash recovery.
- **`UnassignHost(ctx, inventoryHostID, labels)`** — Resolve the NetBox device ID, clear assignment state, and remove the operator-managed Metal3 resources; idempotent.
- **`GetHostNICs(ctx, inventoryHostID)`** — Parse the deterministic BMH host ID and delegate to the existing `baremetalhost.Manager.GetHardwareNICs`; convert the returned MAC addresses to `inventory.HostNIC` values. Return `(nil, nil)` only when the BMH has not reported hardware NIC data yet. [Codebase: `osac/bare-metal-fulfillment-operator/internal/inventory/bcm.go`]

The implementation affects three existing areas: the BMF operator's NetBox client and startup wiring (`internal/inventory/` and `cmd/main.go`), the BMF and umbrella Helm charts (values, Secrets, mounts, and backend configuration), and the monorepo E2E suite under `osac/tests/e2e/bmaas/` for the real NetBox/Metal3 scenarios. It adds no CRD, gRPC, or tenant-facing API changes.

Configuration flows through the existing BMF inventory configuration Secret and the backend-specific Secrets rendered by Helm. Cloud Infrastructure Admin provides:

- NetBox API endpoint URL
- API token (rendered into a Kubernetes Secret with key `token`)
- Optional CA certificate (rendered into a Kubernetes Secret with key `ca.crt` for self-signed TLS)
- The required per-device BMC custom fields defined below

The backend uses NetBox's native device model and REST API. Host allocation state is tracked in the native device status: `staged` is available and `active` is claimed. The `osac_instance_id` custom field records which BareMetalInstance owns an active device; status alone cannot distinguish an idempotent retry from a different claimant. Credentials are never logged; API errors (401, 403) are permanent at the HTTP retry layer and produce generic messages.

### Workflow Description

#### Cloud Infrastructure Admin: Configure NetBox Backend

1. **Prerequisite:** Devices exist in NetBox with:
   - Capability tags are pre-created in NetBox and applied to devices (for example, `osac-cpu-cores-16`, `osac-gpu-model-a100`, and `osac-memory-gb-128`). The corresponding `BareMetalInstanceType.host_label_selector` keys must use those exact tag slugs. OSAC does not create, update, or remove capability tags.
   - The following exact OSAC-owned custom fields on `dcim.device` (these are not built-in NetBox fields and must be created as part of NetBox preparation):
     - `osac_bmc_username` — text, required; BMC login username.
     - `osac_bmc_password` — text, required; BMC login password. Access is controlled by NetBox RBAC; NetBox custom fields are not a Kubernetes Secret.
     - `osac_bmc_address` — text, required; complete Metal3-compatible BMC address, including protocol and Redfish system path when applicable.
     - `osac_boot_mac` — text, required; the boot NIC MAC address in canonical colon-separated form.
     - `osac_instance_id` — text, optional/nullable, with NetBox custom-field
       filtering set to `exact`; OSAC allocation owner, written and cleared by
       the backend. The exact filter setting enables the server-side
       `cf_osac_instance_id__empty=true` narrowing query.
     OSAC does not use an `osac_labels` custom field; capability selectors are represented by NetBox tags.
   - Tag named `managed_by:osac` applied (NetBox slug `managed-by-osac`; identifies devices available for OSAC allocation)
   - Status set to `staged` (available for allocation). The backend changes it to `active` when it claims the device and restores `staged` on release.

2. **Configure the canonical Helm values** under `bmf.netbox`, `bmf.metal3`,
   and `bmf.secrets` as shown in [Configuration via Helm Values and Enclave
   Wizard](#configuration-via-helm-values-and-enclave-wizard). Helm creates
   the backend credential and configuration Secrets before the operator starts;
   the names under `bmf.secrets` are the names assigned to those chart-owned
   Secrets, not references to Secrets created later by the operator. Supply
   token and CA with `--set-file` or an equivalent protected values mechanism.

3. **Deploy via osac-installer:**
   ```bash
   helm upgrade --install osac ./charts/osac -f values.yaml \
     --set-file bmf.netbox.token=/secure/path/netbox.token \
     --set-file bmf.netbox.caCert=/secure/path/netbox-ca.crt
   ```

4. **Operator starts** with the NetBox client constructed through the existing
   BMF startup factory and given the Metal3 `baremetalhost.Manager`. The operator
   performs the runtime connectivity, authentication, and required-custom-field
   checks described in the startup validation contract; Helm and Enclave Wizard
   do not probe NetBox or Metal3.

#### Existing BareMetalInstance reconciliation

The existing `BareMetalInstanceReconciler` remains the caller of the inventory client; this design does not change its top-level reconciliation flow. The NetBox adapter participates at the existing interface boundaries:

1. The fulfillment-service resolves the referenced `BareMetalInstanceType` `host_label_selector` (or the existing legacy template fallback when no instance type is referenced) into the CRD's immutable `spec.selector.hostSelector`. The reconciler clones that map and passes it unchanged to `FindFreeHost`; the tenant request does not supply a separate arbitrary label map. For new NetBox profiles, the instance type selector keys are the exact pre-created NetBox tag slugs. The adapter ignores the generic map value, then adds the fixed pool tag and `staged` tag/status filters. It checks `osac_instance_id` in each returned device to exclude assigned devices.
   The adapter does not fetch the instance type or add a separate NetBox
   `device_type` filter, and it does not extract selectors from the instance
   type's hardware fields. Any hardware distinction needed for placement must
   be represented by a tag key in the resolved HostSelector.
2. `FindFreeHost` returns an inventory host ID in the existing `<namespace>/<name>` form expected by the controller and Metal3 management client: `<metal3 namespace>/netbox-device-<NetBox device ID>`. The reconciler persists that ID in `ExternalHostID` before calling `AssignHost`, as it does for the other inventory backends. This persisted ID is the recovery pointer: when it is already set, the controller skips `FindFreeHost` and lets `AssignHost` reconcile the NetBox state.
3. `AssignHost` performs the NetBox ownership claim and delegates BMC/BareMetalHost setup to the existing Metal3 lifecycle integration. The reconciler then continues through the existing provisioning and readiness conditions.
4. During deallocation, the reconciler calls `UnassignHost`; the adapter clears the NetBox ownership field and delegates physical cleanup to the existing Metal3 lifecycle integration.

The detailed retry, race, and crash-recovery behavior belongs with the individual client methods below and the existing controller retry policy. Tenant-facing BareMetalInstance APIs and provisioning state transitions remain unchanged.

#### Selector data flow and lifetime

`hostSelector` is a persistent field in the BareMetalInstance **spec**, not a
temporary argument created by the NetBox adapter. Before the CR is created,
fulfillment-service copies the referenced instance type's
`host_label_selector.match_labels` into `spec.selector.hostSelector`. The CRD
requires at least one entry and makes the selector immutable, so the map stays
with that BareMetalInstance for its lifetime, including allocation, provisioning,
deallocation, and controller restarts. The controller uses it for
`FindFreeHost` while no `ExternalHostID` is recorded; after a candidate ID is
persisted, retries use that ID with `AssignHost` and do not select by tags again.
The NetBox client does not fetch or reconstruct the instance type at allocation
time.

### API Extensions

No new CRDs or gRPC services. NetBox integration is entirely within the `inventory.Client` abstraction. Existing APIs remain unchanged:

- **BareMetalInstance API** — no modifications. Tenants request hosts via standard API; backend transparent.
- **inventory.Client interface** — no modifications; NetBox implements existing contract.

Operational impact if controller is down:
- New BareMetalInstance requests pend until controller restarts
- Running hosts remain allocated (assignment recorded in NetBox)
- On controller restart: reconciliation resumes; no re-allocation occurs (`ExternalHostID` is checked before `FindFreeHost`; if already set, allocation resumes from `AssignHost`)

## UX Alignment

N/A — BareMetalInstance API is unchanged. NetBox backend is transparent to tenant-facing UX.

## Implementation Details/Notes/Constraints

### Configuration File Structure

NetBox backend configuration follows the existing `inventory.Config` pattern:

```go
type NetBoxOptions struct {
    Endpoint     string `json:"endpoint"`     // https://netbox.example.com
    TokenSecret  string `json:"tokenSecret"`  // Kubernetes Secret name/key token
    CACertSecret string `json:"caCertSecret"` // Optional Secret/key ca.crt
}
```

The operator unmarshals the generic `inventory.Config` from the YAML in the Secret mounted at `OSAC_INVENTORY_CONFIG_PATH`, then reads `cfg.Options["netbox"]` into `NetBoxOptions`. The canonical rendered inventory configuration is:

```yaml
name: netbox-inventory
type: netbox
hostClass: netbox
options:
  netbox:
    endpoint: "https://netbox.example.com"
    tokenSecret: "osac-netbox-api-token"
    caCertSecret: "osac-netbox-ca" # optional
```

Helm renders this `inventory.yaml` and the referenced Secrets; `tokenSecret`
and `caCertSecret` are names of the Secrets rendered by this chart, not names
of runtime Secrets that the operator creates during allocation. Enclave Wizard
only validates and passes the configuration values through. [Locked: D2]

**Hardcoded Conventions:** The allocation tag and allocation-state fields are fixed. Capability tags are administrator-managed and are not mutated by OSAC:
- Device selection tag: name `managed_by:osac`, slug `managed-by-osac` (identifies OSAC-managed devices)
- Allocation state: device status `staged` (available) or `active` (claimed)
- Allocation owner: `osac_instance_id` custom field (empty when unassigned)
- Capability tags: pre-created NetBox tag slugs such as `osac-cpu-cores-16` and `osac-gpu-model-a100`; the matching `BareMetalInstanceType.host_label_selector` keys are sent unchanged as `tag=` filters.

### Allocation Tracking and Device Filtering

Allocation state, ownership, and device pool selection use three NetBox mechanisms:

**1. Device Pool Selection via NetBox Tags**

Devices are tagged in NetBox with the OSAC pool tag named `managed_by:osac`
(slug `managed-by-osac`). Cloud Infrastructure Admin applies this tag to all
devices that should be available for OSAC allocation; the operator queries
only the slug.

**2. Allocation State via Device Status**

OSAC uses the native device status as the allocation state: `staged` means available for selection, and `active` means claimed by OSAC. The adapter does not change status for any other device lifecycle purpose.

**3. Allocation Owner via Custom Field**

A custom field `osac_instance_id` (string, nullable) on each device stores the BareMetalInstanceID when allocated. Empty value means device is unassigned; populated value means device is owned by that BareMetalInstance.

### Host ID Mapping

The generic controller persists `Host.InventoryHostID` and passes it to both the inventory and management clients. Therefore the NetBox adapter does not expose a bare numeric NetBox ID as `ExternalHostID`. `FindFreeHost` derives the DNS-safe BMH name `netbox-device-<id>` from the numeric NetBox device ID and returns `<metal3 namespace>/netbox-device-<id>`. `AssignHost` and `UnassignHost` parse and validate that form, derive the same NetBox device ID for REST calls, and use the same BMH name for lifecycle operations. The existing manager derives the operator-managed BMC Secret name as `<bmh-name>-bmc-secret`. This keeps the existing Metal3 management client able to power and inspect the BMH created during assignment.

**FindFreeHost Query:**

The query combines server-side device-pool filters with the resolved
`spec.selector.hostSelector` capability tags:

```
GET /api/dcim/devices/?tag=managed-by-osac&tag=osac-cpu-cores-16&tag=osac-gpu-model-a100
&status=staged&cf_osac_instance_id__empty=true&limit=100&offset=0
```

Pool and capability filters are applied server-side. The owner field is
checked after decoding each returned device:

| Filter/check                    | Purpose                                      |
|---------------------------------|----------------------------------------------|
| tag=managed-by-osac             | Device membership                            |
| tag=<hostSelector key> (×N)     | Capability-tag matching (AND)                |
| status=staged                   | Available allocation state                   |
| `cf_osac_instance_id__empty=true` | Server-side empty-owner narrowing          |
| `osac_instance_id` is empty     | Authoritative ownership check in adapter    |

Multiple `tag=` parameters use AND semantics — only devices matching ALL
specified tags are returned. The adapter then discards any returned device
whose `osac_instance_id` is non-empty. The custom-field filter uses NetBox's
`cf_` namespace and `__empty=true` lookup to narrow the response, while the
client-side owner check remains authoritative if data is stale or an external
edit causes status and owner to drift. This query filter does not prove that the
custom field exists; startup schema validation separately verifies that
`osac_instance_id` exists on `dcim.device` and supports the required filter.

The resolved `spec.selector.hostSelector` map is populated from the
`BareMetalInstanceType` by the fulfillment-service. NetBox uses the selector
keys as exact tag slugs; the generic map values remain present for the shared
inventory contract but are ignored by this backend:
```
Input: {"osac-cpu-cores-16": "true", "osac-gpu-model-a100": "true"}
Selector keys: ["osac-cpu-cores-16", "osac-gpu-model-a100"]
Query params: &tag=osac-cpu-cores-16&tag=osac-gpu-model-a100
```

**Advantages:**
- Server-side filtering: only matching pool and capability devices are returned by NetBox; reduced network payload
- No client-side label parsing or matching code; only the owner field is checked client-side
- Administrator-managed capability tags remain unchanged by allocation PATCHes
- ETag protection covers the assignment PATCH and all device fields are preserved during updates

### NetBox REST API Interactions

**HTTP Client Pattern:**
- Thin custom HTTP adapter using `net/http`. NetBox has an official generated Go client, but it is version-coupled to a NetBox OpenAPI schema and does not expose the per-request ETag capture and `If-Match` flow needed here. The adapter keeps URL construction, response sanitization, retry policy, and optimistic-locking behavior explicit. [Official client](https://github.com/netbox-community/go-netbox)
- Base URL: the configured HTTPS origin (e.g., `https://netbox.example.com`)
  with no path other than an optional trailing slash; the adapter trims the
  trailing slash and appends `/api/` exactly once. A configured `/api` path is
  rejected so requests cannot become `/api/api/...`.
- Authentication: NetBox's classic token authentication in the `Authorization: Token <token>` header (the design does not use the word "Bearer" for this scheme)
- TLS validation: system CA bundle + optional custom CA cert (injected into
  the `http.Client` Transport); non-HTTPS endpoints are rejected before a
  request is sent
- Redirect policy: `http.Client.CheckRedirect` rejects any redirect that
  changes the scheme or authority from the configured origin, so the token is
  never sent to an HTTP endpoint or a different host
- Timeout: 30s per request (configurable)
- Retry logic: transient errors (5xx, network) up to 3 times; 412 Precondition Failed triggers race-loss path (not retried as transient — handled by caller); permanent errors (401, 403, 4xx validation) fail fast
- ETag/`If-Match` protection requires NetBox 4.6 or newer; the supported point-release matrix is defined and tested before implementation. [NetBox REST API documentation](https://github.com/netbox-community/netbox/blob/main/docs/integrations/rest-api.md)

**Key Endpoints:**
- `GET /api/dcim/devices/` — List devices with filters (pool tag, hardware
  tags, status, and `cf_osac_instance_id__empty=true`; the owner is still
  checked in the adapter)
- `GET /api/dcim/devices/{id}/` — Fetch single device; response includes ETag header for optimistic locking
- `PATCH /api/dcim/devices/{id}/` — Set device status and update the owner custom field during assignment/unassignment. The body is a partial update under `custom_fields`, and the adapter preserves the other custom fields. It sends `If-Match` with the ETag from the prior GET to detect concurrent modifications (412 Precondition Failed on conflict)

For list/detail responses, the adapter compares the choice object's
`status.value` (`staged` or `active`) and treats a missing, null, or empty
`custom_fields.osac_instance_id` value as unassigned. PATCH requests send the
status slug (`staged` or `active`) and the nested custom-field value shown
below.

Assignment and release payloads are:

```json
{"status":"active","custom_fields":{"osac_instance_id":"<bare-metal-instance-id>"}}
{"status":"staged","custom_fields":{"osac_instance_id":null}}
```

These examples show only the fields changed by OSAC; before sending the
PATCH, the adapter merges the current `custom_fields` map so unrelated NetBox
custom fields are preserved.

**Error Handling:**
- 401 Unauthorized — Secret validation failure; permanent at the HTTP retry layer; actionable message
- 403 Forbidden — Token lacks permissions; permanent at the HTTP retry layer; actionable message
- 4xx validation (excluding 412) — Invalid query/filter; permanent at the HTTP retry layer; actionable message (must include field names for debugging)
- 412 Precondition Failed — Concurrent modification detected (ETag mismatch); another operator or process modified the device since our last GET. In AssignHost: return (nil, nil) — treat as race loss. In UnassignHost: re-read device and retry from step 1.
- 5xx server error — Transient; retry with backoff
- Network error (timeout, connection refused) — Transient; retry with backoff

No secrets or tenant data are logged. Error messages use generic "unable to contact inventory backend" when exposing details would leak information.

#### Label Matching Strategy

**Approach: Server-side tag/status filtering with client-side ownership validation**

Capability labels are pre-created NetBox tags. The pool membership tag, the
selector-key tags, and `status=staged` are filtered server-side by the
FindFreeHost API call. NetBox applies AND semantics on multiple `tag=`
parameters. The adapter checks `osac_instance_id` in each returned device and
skips assigned devices; it does not rely on custom-field filtering for
correctness.

**Why capability tags plus a custom-field owner filter:**
- Capability requirements are multi-valued and must be ANDed; NetBox's
  documented repeated `tag=` filter provides that native semantics. The
  owner custom field represents allocation state, not host capability.
- The `cf_osac_instance_id__empty=true` filter further narrows the normal
  candidate response, while the client-side check preserves correctness if
  NetBox returns a stale or unexpectedly populated device
- ETag-based optimistic locking protects the later assignment update and
  preserves unrelated device metadata; it is not used to create or mutate
  capability tags

This design does not claim a benchmarked performance advantage for tags over
custom-field filtering. Tags are selected for their direct multi-tag matching
semantics; the custom-field filter is only a response-size optimization and
the client-side owner check remains authoritative. The API contract tests
cover both filters and the large-pool scenarios should provide the baseline
needed for a later scale decision.

**Matching contract:**
- The fulfillment-service resolves `BareMetalInstanceType.host_label_selector` into the CRD's `spec.selector.hostSelector` map (for example, `{"osac-cpu-cores-16": "true"}`)
- The operator validates and sends each selector key unchanged as a NetBox `tag=` filter; it does not derive a tag from the key/value pair
- Selector values must be non-empty for the shared CRD contract but are ignored by this backend because NetBox tags have no value component
- NetBox API returns only devices matching ALL requested tags
- Adapter discards devices whose `osac_instance_id` is already populated
- A device with EXTRA tags beyond those requested is still a valid match (superset matching)

The `BareMetalInstanceType` is not a NetBox object and the
fulfillment-service does not query NetBox while resolving it. For a deployment
using this backend, the administrator authors the instance type's selector keys
to match the pre-created NetBox tag slugs; the fulfillment-service copies the
map without interpreting it, and only the NetBox adapter interprets the keys
as tag filters. Other inventory backends continue to use both key and value
according to their own matching contracts. We intentionally do not invent a
`key:value` tag encoding: NetBox's tag filter already accepts one exact tag
slug, so the key itself is the unambiguous tag identity and the non-empty map
value is retained only for the shared selector schema.

**NetBox tag-key rules:**
- The selector key is the exact pre-created NetBox tag slug; the operator does not add a prefix, lowercase it, or otherwise transform it
- Keys must be non-empty and match the supported NetBox tag-slug character set; URL encoding is applied only when constructing the request
- Selector values must be non-empty because the shared selector schema requires them, but changing a value does not change the NetBox query

**Validation:** reject an invalid or empty tag key before any NetBox request; do not silently normalize a key to a different tag. Values are validated only for the existing non-empty selector contract.

### AssignHost Implementation

**Normal Path (Happy Case):**
0. Parse `inventoryHostID` and recover the numeric NetBox device ID from the validated `netbox-device-<id>` name; reject any other host-ID form.
1. Read device from NetBox by ID and check assignment status. **Capture the ETag header from the response.**
   - If status is `active` and `osac_instance_id` is the **same ID** → skip the NetBox claim PATCH and continue with the idempotent Secret/BMH ensure steps below
   - If status is `active` with a **different/non-empty ID**, or status is not `staged` → return (nil, nil) — another request or external lifecycle action owns the device
   - If status is `staged` and `osac_instance_id` is empty → proceed to step 2
2. Extract BMC data: read `osac_bmc_username`, `osac_bmc_password`, `osac_bmc_address`, and `osac_boot_mac` from the device custom fields. Validate the address and MAC before changing the allocation marker.
3. For an unassigned device, PATCH assignment: set `status = active` and `osac_instance_id = bareMetalInstanceID`. **Include `If-Match: <etag>` header from step 1.** If NetBox returns **412 Precondition Failed** → another process modified the device since our read; return (nil, nil) — treat as race loss. For an already-owned device, do not repeat this PATCH.
4. For a newly claimed device, verify the write: read device back and confirm `status=active` and `osac_instance_id` matches. This is now a safety net rather than the primary race detection mechanism — the ETag in step 3 prevents concurrent overwrites.
5. Ensure the namespace-scoped BMC Secret through the existing `BMHLifecycleManager`, using the extracted username/password. The Secret name is deterministic from the NetBox device ID and is labeled as operator-managed.
6. Create the BMH through the existing `BMHLifecycleManager`, passing the validated BMC address, Secret name, boot MAC, and BareMetalInstance consumer reference. The manager's `CreateBMH` operation is idempotent.
7. Check readiness through the existing manager; return `Host.Ready = true/false`. NetBox does not perform power control, inspection, OS provisioning, or readiness transitions.

If an adapter-side preparation step after the NetBox claim fails (for example,
creating the operator-managed BMC Secret or BareMetalHost), the client runs an
internal compensation path before returning the error: it deletes only a BMH
whose consumer reference matches the current BareMetalInstance, deletes only
the operator-managed BMC Secret, then re-reads the device and clears the
NetBox claim with `If-Match`. A failed cleanup or an ownership mismatch leaves
the claim in place and is retried safely rather than risking another instance's
resources. `Host.Ready = false` and a transient readiness-read error are not
preparation failures; the claim and same-owner BMH/Secret are retained so the
existing controller can requeue and continue. This compensation path is what
satisfies the PRD requirement to release a host when adapter-side preparation
fails; provisioning failures handled after this boundary remain part of the
existing BareMetalInstance lifecycle and are released by normal deallocation.

**Idempotency Contract (Safe for Unlimited Retries):**
- Every call starts by reading device and checking current assignment
- If status is `active` and already assigned to the same ID → skip the ownership write, but repeat the idempotent Secret/BMH ensure and readiness checks
- If status is `active` with a different/non-empty ID, or status is not `staged` → return (nil, nil) without writing
- This makes the entire flow idempotent across retries, transient failures, and crashes

**Race Condition Handling (Concurrent Requests with ETag Protection):**
- BareMetalInstance A and B both call `FindFreeHost` → same device returned to both
- A's `AssignHost` reads device (step 1), captures ETag_v1
- B's `AssignHost` reads device (step 1), captures ETag_v1
- A's PATCH includes `If-Match: ETag_v1` → succeeds (first writer wins); NetBox updates device and returns new ETag_v2
- B's PATCH includes `If-Match: ETag_v1` → fails with 412 Precondition Failed (device was modified since B's read)
- B's `AssignHost` returns (nil, nil); caller retries `FindFreeHost`
- Result: true first-writer-wins semantics; no silent overwrites; race detected at PATCH time, not at verify-read time

**Transient Failure Recovery (PATCH Fails):**
- PATCH fails with 5xx, timeout, or network error
- Controller requeues with exponential backoff
- Next reconciliation retries `AssignHost`
- Step 1 finds device already has correct `osac_instance_id` → returns cached state without retrying writes

**Crash Recovery (Operator Restart):**
- Crash after `FindFreeHost` but before recording `ExternalHostID`:
  - No state changes anywhere; reconciliation restarts from `FindFreeHost`
- Crash after recording `ExternalHostID` but before `AssignHost` PATCH:
  - CR has `ExternalHostID` set; NetBox device is still unassigned
  - On restart, controller sees `ExternalHostID`, skips `FindFreeHost`, calls `AssignHost` directly → normal assignment proceeds
  - If device was claimed by another request in the meantime: `AssignHost` returns (nil, nil); controller clears `ExternalHostID` and retries `FindFreeHost`
- Crash after `AssignHost` PATCH succeeds:
  - Both CR (`ExternalHostID`) and NetBox (`status=active`, `osac_instance_id`) are consistent
  - On restart, `AssignHost` step 1 finds matching assignment → skips the ownership write, ensures the Secret/BMH, and reconciliation continues to provisioning

### UnassignHost Implementation

**Normal Path (Happy Case):**
0. Parse `inventoryHostID` and recover the numeric NetBox device ID from the validated `netbox-device-<id>` name; reject any other host-ID form.
1. Read device and check assignment. **Capture the ETag header.**
   - If status is `staged` and `osac_instance_id` is empty → return success (already unassigned)
   - If status is `active` and `osac_instance_id` is non-empty → ask the BMH manager for the existing BMH `ConsumerRef`. If a BMH exists, its consumer ID must equal the NetBox owner; otherwise return an ownership-conflict error without deleting anything. If the BMH is absent, the inventory finalizer continues the deterministic cleanup for this host ID.
2. Delete BMH: call `bmhManager.DeleteBMH()` to remove Metal3 BareMetalHost CR (device remains assigned in NetBox during cleanup)
3. Delete Secret: call `bmhManager.DeleteBMCSecret()` to remove BMC credentials
4. Clear assignment: PATCH NetBox to set `status = staged` and clear `osac_instance_id`. **Include `If-Match: <etag>` header from step 1.** If NetBox returns **412 Precondition Failed** → re-read device and retry from step 1 (another process modified the device concurrently).
5. Verify write (sanity check): read device back; confirm status is `staged` and the owner field is cleared

**Idempotency Contract:**
- Same read-first pattern as AssignHost
- Every retry starts by checking device state
- Safe for multiple retries without duplicate writes
- ETag-based `If-Match` on PATCH prevents concurrent modification; 412 triggers re-read and retry (safe because unassignment is idempotent)
- Because `UnassignHost` has no bare-metal-instance-ID parameter, the existing BMH `ConsumerRef`/NetBox owner comparison is the ownership guard available at this interface boundary; it prevents cleanup from deleting a BMH that belongs to a different BareMetalInstance

### Metal3 BareMetalHost Lifecycle

The NetBox adapter reuses the existing `baremetalhost.Manager` used by the BMF operator. Its responsibility is to translate NetBox's BMC metadata into the manager's `CreateParams`; the manager and Metal3 controller handle Kubernetes objects, power management, inspection, and readiness reporting. The manager gains an internal `GetBMHConsumerID(name)` helper for the release-time ownership guard above; NotFound means that the deterministic BMH is absent. This is an internal helper and does not change `inventory.Client` or the top-level reconciler. This keeps the implementation within locked decision D4: NetBox is the inventory source, while OS provisioning and BMH readiness remain existing Metal3 responsibilities.

**Key Properties:**

- **Coupled lifecycle** — Inventory allocation and BMH creation happen together (steps 5-7 in AssignHost); the device remains claimed while preparation is in progress, and a failed preparation is compensated before the error is returned
- **Idempotent** — `EnsureBMCSecret()` and `CreateBMH()` are idempotent; crash recovery finds existing objects and reuses them
- **Ordered deallocation** — BMH and its operator-managed Secret are deleted before the NetBox allocation marker is cleared (UnassignHost steps 2-4)
- **Readiness reporting** — the existing manager reads BMH status; `AssignHost` returns that status to the caller while the controller requeues until ready

**BMC Credential Security:**

- NetBox stores the configured per-device BMC metadata; it remains the source of truth for the adapter. Because NetBox custom fields are not a secret store, the NetBox API token must be restricted to the operator's device read/update permissions and NetBox roles must restrict who can view these fields.
- Credentials are fetched only during assignment and passed to the existing manager, which creates a namespace-scoped, operator-managed Kubernetes Secret for the BMH
- The Secret is labeled for cleanup and deleted during deallocation; the NetBox adapter never logs or writes the credential values back to NetBox
- Reuses the existing Metal3/BMH integration without adding provisioning logic to the NetBox backend

### TLS and Credential Security

**Credential Management:**
- API token stored in the Helm-created Kubernetes Secret `osac-netbox-api-token`, key `token`
- Secret is mounted read-only at `/etc/osac/secrets/<tokenSecret>/`; the client reads `/etc/osac/secrets/<tokenSecret>/token`
- Operator constructs the HTTP client with the `Authorization: Token <token>` header
- Token never logged; errors sanitized to hide sensitive values

**TLS Configuration:**
- System CA bundle used by default
- Optional custom CA cert provided in the Helm-created `osac-netbox-ca` Secret, key `ca.crt`, and mounted read-only at `/etc/osac/secrets/<caCertSecret>/ca.crt` alongside the token
- Certificate pinning not supported in initial implementation
- Self-signed cert support: Cloud Infrastructure Admin provides CA cert; operator adds to `http.Client.Transport.TLSClientConfig`

**Validation at Startup:**
- Operator reads configuration on startup
- Parses the configured URL, loads the token and optional CA Secret, and builds the authenticated HTTP client
- Performs read-only NetBox API requests that validate connectivity, authentication, and the required `osac_instance_id` custom field (including its `dcim.device` assignment, text/nullable shape, and filtering support)
- Fails backend initialization on invalid URL, TLS/connectivity failure, 401/403, or missing required custom field; no allocation is attempted with an unvalidated backend
- Permission to perform the allocation PATCH is verified by the first real assignment; the token is documented with the required read/update device permissions

### Configuration via Helm Values and Enclave Wizard

NetBox backend **requires Metal3 for power management and host provisioning**. Both must be configured. This is the only canonical values shape; the earlier workflow example and the chart templates use these same names.

The `bmf` subchart adds a `netbox` backend alongside its existing `metal3`
management configuration. The existing chart uses `metal3.enabled` for both
Metal3 inventory and management templates, so the implementation must avoid
rendering two objects with the same `secrets.inventoryConfig` name: when both
`netbox.enabled` and `metal3.enabled` are true, the NetBox template owns
`inventory.yaml`, while the Metal3 template renders only `management.yaml`.
When NetBox is disabled, the existing Metal3-only behavior remains unchanged.
The namespace-scoped BMC Secret Role and the operator's Secret volume mounts
are enabled for the NetBox-plus-Metal3 combination as well.

```yaml
bmf:
  secrets:
    inventoryConfig: "osac-inventory-config"
    managementConfig: "osac-management-config"
    netboxToken: "osac-netbox-api-token"
    netboxCA: "osac-netbox-ca"
  netbox:
    enabled: true
    endpoint: "https://netbox.example.com"
    token: ""                 # supplied with --set-file
    caCert: ""               # optional; supplied with --set-file
    hostClass: "netbox"
  metal3:
    enabled: true
    namespace: "baremetal"
    hostClass: "metal3"
```

The chart creates `bmf.secrets.netboxToken` with key `token`, creates
`bmf.secrets.netboxCA` with key `ca.crt` when `caCert` is non-empty, and
renders `bmf.secrets.inventoryConfig` with the `options.netbox` references
shown above. When no CA is supplied, `caCertSecret` and its volume mount are
omitted. The Deployment mounts the backend Secrets read-only below a
deterministic path derived from each Secret name, following the existing BMF
certificate-volume pattern; the client reads the fixed `token` and `ca.crt`
files from those mounts. This follows the existing BMF `bcm.*` plus
`secrets.*` pattern rather than introducing a second `secretRef` convention,
and avoids asking an operator to create the backend credential Secrets
separately. The per-host BMC Secret is different: `AssignHost` reads the
BMC fields from the selected NetBox device and calls the existing
`baremetalhost.Manager.EnsureBMCSecret`; that namespace-scoped Secret is
created only when a host is assigned, then deleted by `UnassignHost`.

Sensitive values are supplied with `--set-file` (or an equivalent protected values mechanism), for example:

```bash
helm upgrade --install osac ./charts/osac -f values.yaml \
  --set-file bmf.netbox.token=/secure/path/netbox.token \
  --set-file bmf.netbox.caCert=/secure/path/netbox-ca.crt
```

**Validation at deployment:**
- Helm validates that `netbox.enabled` has an endpoint and token, and that `metal3.enabled` has a namespace
- The chart renders the inventory and management configuration Secrets; it does not contact NetBox or inspect the cluster's Metal3 runtime
- Operator startup performs the runtime validation contract above

Optional Enclave Wizard integration (pre-deployment):

This is a values-schema integration contract, not a new Enclave Wizard
component. Deployments may use Helm directly.

1. Accepts and schema-validates the endpoint, token/CA inputs, and Metal3 namespace using the existing Enclave Wizard validation/playbook mechanisms
2. Generates the values input for Helm; it does not create Kubernetes Secrets itself and does not probe NetBox connectivity or Metal3 operator availability
3. Helm creates the Secrets and configuration described above
4. The operator performs runtime connectivity, authentication, and custom-field validation during initialization

**Startup validation contract (operator initialization):**
- Authentication failures (401, 403): detected at operator startup; backend initialization fails with an actionable message
- Connectivity failures: detected at operator startup; operator fails fast
- Schema validation failures (`osac_instance_id` missing or incompatible with the required `dcim.device` text/nullable/exact-filter contract): detected at operator startup; operator fails fast
- Invalid endpoint URL: detected at operator startup; operator fails fast
- Result: if the backend initializes successfully, NetBox is reachable, authenticated, and has the required schema; Enclave Wizard is not a runtime dependency

### Error Messages and Diagnostics

Cloud Infrastructure Admin receives clear, actionable messages:

- **At startup:** "NetBox backend initialized"
- **On connectivity failure:** "Failed to connect to NetBox API: request timeout after 30s. Check endpoint URL and network connectivity."
- **On auth failure:** "NetBox API authentication failed. Verify API token in Secret osac-netbox-api-token is valid and has permissions to read/update devices."

## Security Considerations

### Credential Handling

API-token storage, Secret ownership, mount paths, TLS handling, startup
validation, and log redaction are defined in [TLS and Credential
Security](#tls-and-credential-security). No second credential lifecycle is
introduced here. [PRD: In Scope — API-token configuration, TLS validation, and
credential-safe errors]

### Tenant Isolation

No tenant-identifying data is recorded in NetBox. Assignment identifier is OSAC-internal (BareMetalInstance UID or UUID); NetBox stores only the assignment ID, not tenant name or namespace. [PRD: In Scope — no tenant-identifying data in NetBox]

Tenant users cannot see which backend is in use or any NetBox state; allocation is transparent. Network namespace or firewall rules may restrict NetBox API access to OSAC control plane only. [PRD: In Scope — tenant transparency]

### Input Validation

The controller supplies the resolved `spec.selector.hostSelector` map to the
backend. Its values originate from the `BareMetalInstanceType`/catalog
contract, not from an arbitrary label map in the tenant create request. For
NetBox, the adapter takes each selector **key** as the exact tag slug to send
in the query; it does not convert a key/value pair into a new slug. The map
value is required to be non-empty by the shared BMF schema but is ignored by
this backend because NetBox tag matching is name/slug based. Input validation
requirements:

- Each selector key must be non-empty and must be the pre-created NetBox tag slug; the adapter does not add a prefix, lowercase text, replace underscores, or combine the key with the value.
- Selector values must be non-empty for the shared `hostSelector` contract, but changing a value does not change the NetBox query.
- A key rejected by the BMF/NetBox tag-slug contract is rejected before a device query; an absent but syntactically valid tag simply produces no matching devices.
- URL encoding is applied by `url.Values` to the exact key before constructing the request, preventing query-string injection without changing the tag identity.

NetBox queries constructed defensively:
```go
params := url.Values{}
params.Add("tag", "managed-by-osac")
params.Add("tag", "osac-cpu-cores-16")
params.Add("status", "staged")
requestURL.RawQuery = params.Encode()
// Result: tag=managed-by-osac&tag=osac-cpu-cores-16&status=staged
```

### Authorization

OSAC trusts NetBox API token to enforce authorization. Token should have read/update permissions on `dcim.device` and read access to the required custom-field metadata; no create/delete (the operator never removes devices or changes the NetBox schema). [Assumption: Cloud Infrastructure Admin configures NetBox token with least-privilege scopes]

## Failure Handling and Recovery

The per-method sections above are normative for request ordering, idempotency, race handling, and crash recovery. This section summarizes only the controller-level policy:

- The HTTP adapter retries transient 5xx and network failures up to three times per request. After that budget is exhausted, the existing reconciliation lifecycle requeues the BareMetalInstance with its normal backoff. “Permanent” HTTP errors are not retried within the request, but a runtime credential revocation still follows the controller's normal error backoff; startup validation catches the usual misconfiguration before allocation.
- `FindFreeHost` returning `(nil, nil)` is expected capacity exhaustion, not a NetBox error. The existing controller reports no matching hosts and polls again using `NoFreeHostsPollIntervalDuration`.
- A 412 response follows the method-specific race paths above: `AssignHost` returns no host so the controller selects again; `UnassignHost` re-reads and retries without clearing another instance's assignment.
- Startup URL, TLS, authentication, and required-field failures prevent backend initialization. In this initial design, correcting the mounted Secret requires an operator restart so the client is rebuilt and startup validation runs again.
- `UnassignHost` clears the NetBox marker only after the existing Metal3 manager has completed BMH and operator-managed Secret cleanup. A cleanup failure therefore leaves the marker set and is retried safely.
- If adapter-side BMC Secret or BMH preparation fails after a claim, the compensation path removes only resources owned by the current BareMetalInstance and clears the claim with `If-Match`; if safe cleanup cannot be proven, the claim remains for retry and operator intervention.
- All retry paths are idempotent: the assignment field, `ExternalHostID`, BMH, and BMC Secret are checked before repeating a write or create operation.

## RBAC / Tenancy

No changes to RBAC or tenancy model. Existing BareMetalInstance RBAC applies unchanged.
Tenant data handling is covered under [Tenant Isolation](#tenant-isolation);
the NetBox token authorization boundary is covered under [Authorization](#authorization).

## Observability and Monitoring

### Metrics

New Prometheus metrics emitted by NetBox backend:

| Metric | Type | Labels | Meaning |
|--------|------|--------|---------|
| `osac_netbox_hosts_available` | gauge | `host_class` | Total count of available devices in the pool (tag=managed-by-osac, status=staged, and empty `osac_instance_id`); computed by paginating the server-side pool query and applying the owner check |
| `osac_netbox_assignment_attempts_total` | counter | `result` | Total AssignHost attempts; result = success/race/error |
| `osac_netbox_api_errors_total` | counter | `error_type` | Total API errors by type (401, 403, 5xx, timeout) |

Cross-backend host-search and assignment latency metrics are not defined by
this backend-specific design. They should be added at the shared controller
boundary so BCM, OpenStack, Metal3, and NetBox expose the same measurements.

### Structured Logs

The NetBox adapter and the shared allocation-path logs include:
- `host_selector_key_count` — number of keys in the resolved `spec.selector.hostSelector`
- `query_tag_count` — number of tags sent to NetBox for this request
- `matching_devices_count` — count of devices returned by NetBox matching the server-side pool/tag filters
- `host_selected` — whether a candidate was selected
- `netbox_api_error` — error type/code (never token value or full response)

Selector values, raw tag slugs, host IDs, BareMetalInstance UIDs, tenant data,
and credential details are not logged. The implementation must replace the
generic controller's existing raw `matchExpressions` and `InventoryHostID`
fields with these safe counts/booleans/error codes on the NetBox allocation
path; this is a logging-only hardening change and does not alter reconciliation
behavior.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| NetBox API incompatibility across versions | Features broken in upgrades | Require NetBox 4.6+ for ETag/`If-Match`; document and test the supported point-release matrix in CI |
| Credential exposure via error messages | Security breach | Audit all error paths; sanitize NetBox error responses; never log API responses |
| NetBox network partition | Allocation blocked until recovery | Graceful degradation: timeout after 30s; requeue BareMetalInstance; no tenant-visible difference |
| External status edit on an OSAC-managed device | A claimed device can look available or an available device can be hidden from allocation | Treat only `staged` + empty owner as allocatable, preserve the owner under `If-Match`, and document that OSAC owns the allocation status for tagged devices |
| Race between AssignHost and UnassignHost | Device simultaneously assigned and deallocated; inconsistent state | Idempotent operations: status and owner are updated under `If-Match`; AssignHost detects existing ownership; UnassignHost checks the existing BMH `ConsumerRef` against the NetBox owner before cleanup; safe to retry both |

All mitigations are concrete and testable.

## Drawbacks

**NetBox version floor** — ETag/`If-Match` support makes NetBox 4.6 the minimum for the race-safe implementation. Mitigation: publish the supported point-release matrix and test it in CI.

**Inventory preparation** — Administrators must create the required custom fields and tags, and populate BMC metadata before a device can be allocated. Mitigation: document the exact schema, validate required fields at startup, and provide the Helm/Enclave Wizard input schema.

**Read-then-verify assignment pattern** — The REST API is not transactional across reads and writes. The `If-Match` precondition removes silent overwrites, but a concurrent external edit still causes the assignment to fail safely. Mitigation: retry the controller reconciliation; do not claim the device after a failed precondition.

**Small custom HTTP adapter** — The official generated Go client is version-coupled and does not provide the per-request concurrency controls required by this design. Mitigation: keep the adapter narrow, test the request/response contract against supported NetBox versions, and avoid duplicating general SDK functionality.

## Alternatives (Not Implemented)

### Alternative 1: Status-Only Assignment Tracking

Use only the built-in `status` field (for example, `staged` for available and `active` for claimed), without an owner custom field.

**Pros:**
- No owner custom field required; simpler NetBox schema
- Native status field; operators already familiar with it

**Cons:**
- Cannot distinguish a retry for the same BareMetalInstance from a different claimant
- Other systems managing NetBox state may overwrite status
- A status transition alone does not preserve the assignment owner for crash recovery

**Rejection:** D3 requires using the native status for allocation state, so this design uses status together with `osac_instance_id`; status alone is insufficient for idempotency and ownership checks.

### Alternative 2: Out-of-Tree Backend (Separate Sidecar Service)

Deploy NetBox backend as a gRPC sidecar service instead of in-tree implementation.

**Pros:**
- Loose coupling; backend updates don't require operator recompilation
- Language flexibility; backend could be written in Python (NetBox native)

**Cons:**
- Operational overhead; manage separate service, routing, TLS
- Introduces network latency and failure modes (sidecar unavailable)
- Enclave Wizard setup more complex (manage additional service deployment)

**Rejection:** In-tree is simpler and aligns with the existing pattern. [Locked: D2] Out-of-tree extraction supported via clean internal types (future OSAC-3806).

### Alternative 3: Sync NetBox State Back to OSAC API

Periodically query NetBox; expose available/claimed host counts in OSAC API for Admin visibility.

**Pros:**
- Admin can see inventory utilization without leaving OSAC

**Cons:**
- Increases complexity; requires new API (AdminInventoryStatus or similar)
- Eventual consistency issues; stale data
- Out of scope for current feature

**Rejection:** [PRD: Out of Scope — Admin host-listing / inventory visibility in the OSAC API] Deferred to future enhancement. Current design allows future extension without changes to NetBox backend.

## Open Questions

### NetBox Version Compatibility

**Question:** Which specific NetBox point releases will be supported?

**Owner:** Implementation task; Cloud Infrastructure Admin (testing feedback)

The race-safe assignment design requires NetBox 4.6 or newer because it relies on the REST API's ETag/`If-Match` support. The initial supported matrix is NetBox 4.6.x and 4.7.x, with exact patch images pinned by CI. The client intentionally limits its dependency surface to device list/detail/partial-update endpoints, tags, device status, and custom fields; it does not depend on unrelated NetBox models or response formats.

No runtime version endpoint query or version-dependent code paths are needed. The
client requires the configured NetBox deployment to support ETag/`If-Match`;
startup can fail if the detail response does not provide the required ETag.
NetBox also exposes its API version in the `API-Version` response header, which
can be retained for diagnostics, but the client does not branch on it at
runtime.
Any later NetBox release remains unsupported until its pinned compatibility
image passes the same CI/E2E contract tests and is added to the matrix.

## Test Plan

### Unit Tests

**Configuration Parsing and Validation:**
- Parse valid YAML config; assert all fields populated correctly
- Parse config with missing endpoint; assert error
- Parse config with invalid token Secret reference; assert error
- TLS certificate loading from Secret; assert correct CA added to http.Client
- **Resolved HostSelector and tag-key extraction:**
  - Setup: A `BareMetalInstanceType.spec.host_label_selector.match_labels` map of {"osac-cpu-cores-16": "true", "osac-gpu-model-a100": "true"} is resolved into `spec.selector.hostSelector`
  - Action: Operator builds the NetBox tag filters from the resolved map
  - Expected: Fulfillment-service copies the two key/value entries into the CRD without conversion; the NetBox request contains one `tag=` filter for each key (order is not significant), no selector value is encoded, and no hardware field is consulted
- **Tag-key validation rejects invalid characters:**
  - Setup: Selector key contains spaces or special characters: {"invalid tag!": "true"}
  - Action: Operator validates the selector key
  - Expected: Validation error before any NetBox query; BareMetalInstance status shows error message

**Label Matching → Tag Query Construction (Unit Tests):**
- Input: {"osac-cpu-cores-16": "any-non-empty-value", "osac-gpu-model-a100": "ignored"}
  Expected tags (order independent): ["osac-cpu-cores-16", "osac-gpu-model-a100"]
- Input: {"osac-memory-gb-128": "true"}
  Expected tags (order independent): ["osac-memory-gb-128"]
- Input: {"osac-key-with-underscores": "true"}
  Expected tag (order independent): ["osac-key-with-underscores"] (key is not rewritten)
- Input: {"osac-gpu-model-a100": "H100"}
  Expected tags (order independent): ["osac-gpu-model-a100"] (the value is ignored; the key is not rewritten)
- Input: {"invalid key!": "true"}
  Expected: validation error (invalid key)

**FindFreeHost Logic:**
- **Device with matching tags:** Mock NetBox returns device with tags [managed-by-osac, osac-cpu-cores-16]; resolved HostSelector is {osac-cpu-cores-16: true} → device is returned
- **Device with wrong tags:** Mock NetBox returns empty list (server-side filtering); resolved HostSelector is {osac-gpu-model-v100: true} but no devices have that tag → nil returned
- **Superset match:** Device has tags [osac-cpu-cores-16, osac-gpu-model-a100, osac-memory-gb-128]; resolved HostSelector is {osac-cpu-cores-16: true} → device IS returned (extra tags are fine)
- No devices match device selection tag → nil
- All staged devices returned by NetBox have a non-empty `osac_instance_id` → nil
- Large result set (100+ devices) → pagination handled correctly

**Capacity Count:**
- **Test 1 — Count returns correct number:**
  - Setup: Mock NetBox with 5 devices matching the server-side pool filters (tag=managed-by-osac, status=staged); all have an empty `osac_instance_id`
  - Action: Paginate the pool query and count devices after the owner check
  - Expected: Available count is 5
- **Test 2 — Count updates after assignment:**
  - Setup: 5 available devices; AssignHost one device
  - Action: Re-run the paginated capacity query
  - Expected: "count": 4 (one fewer available)
- **Test 3 — Count with no available devices:**
  - Setup: All devices have status=active and osac_instance_id set
  - Action: Paginate the staged pool query and apply the owner check
  - Expected: "count": 0

**AssignHost Idempotency:**
- Assign host → device now has status=active and osac_instance_id; read-after-write confirms
- Assign same host with same ID again → skips ownership PATCH, ensures BMH/Secret idempotently, returns (host, nil)
- Assign same host with different ID → returns (nil, nil) (race lost)
- Assign to device that was manually cleared (external edit) → proceeds as normal assign
- **ETag capture on read:**
  - Setup: Mock GET returns device with ETag header
  - Action: AssignHost step 1 reads device
  - Expected: ETag value is captured and stored for use in step 3 PATCH
- **If-Match sent on PATCH:**
  - Setup: AssignHost has captured ETag from step 1
  - Action: Step 3 sends PATCH
  - Expected: PATCH request includes If-Match header with the captured ETag value

**UnassignHost Idempotency:**
- Unassign assigned host → status restored to staged and osac_instance_id cleared; read-after-write confirms
- Unassign same host again → idempotent, returns nil
- Unassign host with a conflicting BMH consumer reference → returns an ownership-conflict error without cleanup
- **412 during unassignment:**
  - Setup: Mock GET returns device assigned to our instance; PATCH returns 412 Precondition Failed
  - Action: UnassignHost step 2 sends PATCH with If-Match
  - Expected: UnassignHost re-reads device (back to step 1) and retries; does NOT return error on first 412

**Error Handling:**
- NetBox API returns 401 → error logged; permanent at the HTTP retry layer; no request-level retry
- NetBox API returns 5xx → error logged; transient; retry
- Network timeout → error logged; transient; retry
- No secrets/credentials in any error message or log
- **412 Precondition Failed:**
  - Setup: Mock NetBox PATCH returns 412
  - Action: AssignHost step 3
  - Expected: Returns (nil, nil) — treated as race loss, NOT as a transient error (no automatic retry at HTTP level)
- **412 distinguished from other 4xx:**
  - Setup: Mock returns 400 Bad Request vs 412
  - Expected: 400 → permanent error (fail fast); 412 → race loss path (return nil, nil)

**Concurrent Access (ETag-Based):**
- **Setup:** Mock NetBox returns device with ETag: W/"2026-01-01T00:00:00.000000+00:00"
- **Test 1 — First writer wins:**
  - PATCH with If-Match: W/"2026-01-01T00:00:00..." → mock returns 200 OK with new ETag
  - Expected: AssignHost returns (host, Ready)
- **Test 2 — Second writer gets 412:**
  - PATCH with If-Match: W/"2026-01-01T00:00:00..." → mock returns 412 Precondition Failed
  - Expected: AssignHost returns (nil, nil); does NOT retry the same device; caller retries FindFreeHost
- **Test 3 — Race sequence:**
  - Two goroutines both call AssignHost on same device-42
  - Both capture same ETag from GET
  - First PATCH succeeds (200); second PATCH gets 412
  - Assert: exactly one goroutine returns (host, Ready); exactly one returns (nil, nil)
  - Assert: device-42 has status=active and osac_instance_id set to the winner's ID, not the loser's
- **Concurrent tag-based FindFreeHost:**
  - Setup: 3 devices with osac-cpu-cores-16 tag; 2 tenants request the `osac-cpu-cores-16` selector key simultaneously
  - Action: Both call FindFreeHost with same tag filters
  - Expected: Both get results from NetBox; AssignHost ETag protection prevents double-allocation; one gets device, other retries or gets different device

### Integration Tests

These tests use the existing controller-runtime envtest API server and etcd;
they do not require a full Kind network. The reconciler and an in-process
TLS-capable `httptest.Server` run in the same Go process, and the NetBox endpoint is set to
the server's generated URL rather than a fixed `localhost` port.

- Start the mock NetBox server with the required custom-field and device
  responses
- Start the envtest operator with NetBox config pointing to the mock server
- Create a BareMetalInstance whose resolved `spec.selector.hostSelector` contains the test selector
- Verify FindFreeHost called; host allocated; `spec.externalHostID` set to the deterministic BMH host ID
- Delete BareMetalInstance; verify UnassignHost called; host deallocated
- Verify no regressions in other backends by running the existing Metal3 and BCM configurations as separate test deployments; this does not add multi-backend support to one cluster
- **Concurrent assignment with ETag protection:**
  - Setup: Two BareMetalInstance CRs requesting same label profile; only one device matches in mock NetBox
  - Action: Both controllers attempt AssignHost on same device
  - Expected: Exactly one gets 200; the other gets 412 and retries FindFreeHost; no device is double-assigned

**Failure Recovery:**
- Simulate a failure creating the BMC Secret or BareMetalHost after the NetBox claim
- Verify the compensation path removes only the current instance's BMH/Secret and clears the claim; if cleanup cannot be proven safe, the claim remains for retry
- Simulate NetBox connectivity loss (network partition) during FindFreeHost; observe the normal controller retry after the adapter's request retry budget
- Simulate permanent auth failure; verify the sanitized error and normal controller backoff
- Verify `osac_netbox_api_errors_total{error_type="401"}` increments without exposing the token

**Configuration Lifecycle:**
- Deploy operator with invalid config (bad endpoint); verify startup error
- Fix the mounted configuration Secret and restart the operator; verify it picks up the new endpoint
- Drain NetBox-backed instances before switching to another backend; verify no orphaned state

**Tag Update on Device:**
- Setup: Device has tag osac-memory-gb-64
- Action: Admin removes osac-memory-gb-64 and adds osac-memory-gb-128; the `BareMetalInstanceType` selector key is updated accordingly
- Expected: FindFreeHost with key osac-memory-gb-64 no longer returns this device; FindFreeHost with key osac-memory-gb-128 now returns it

**Capacity Metrics Endpoint:**
- Setup: envtest operator with mock NetBox and 10 staged devices
- Action: Scrape operator's /metrics endpoint
- Expected: osac_netbox_hosts_available gauge shows 10; after one assignment, gauge shows 9

**Server-Side Tag Filtering Verification:**
- Setup: envtest operator with mock NetBox containing 10 devices: 5 have osac-gpu-model-a100, 5 have osac-gpu-model-v100
- Action: The resolved `spec.selector.hostSelector` contains `{osac-gpu-model-a100: "true"}`
- Expected: FindFreeHost query includes tag=osac-gpu-model-a100; NetBox returns only the 5 matching devices; operator does NOT receive or filter the V100 devices

**Tag Mismatch — Zero Results:**
- Setup: Mock NetBox devices have osac-gpu-model-a100
- Action: The resolved `spec.selector.hostSelector` contains `{osac-gpu-model-h100: "true"}`
- Expected: FindFreeHost query includes tag=osac-gpu-model-h100; NetBox returns empty list; operator requeues with "No hosts available"

### E2E Tests

Tests run against a **pinned real NetBox container** (not mock), exposed
through a Kubernetes Service rather than `localhost`. Fixtures provision the
required OSAC custom fields (`osac_instance_id` as a nullable text field with
exact filtering, BMC metadata, boot MAC), the
device selection tag (slug `managed-by-osac`), administrator-managed capability tags
(for example, osac-cpu-cores-16 and osac-gpu-model-a100, matching the
instance type selector keys), and test devices initially in
status `staged`.

**End-to-End Provisioning:**
- Create a BareMetalInstance whose resolved `spec.selector.hostSelector` matches NetBox devices
- Observe allocation from NetBox
- Verify Metal3 BareMetalHost created for power management
- Monitor provisioning completion (existing BareMetalInstance status workflow)
- Delete instance; verify host deallocated and returned to pool
- **Preservation of administrator-managed tags after provisioning:**
  - OSAC never creates or mutates capability or pool tags; after provisioning, verify the partial PATCH preserved them:
    - Device in NetBox still has the pre-existing selector tags (for example, osac-cpu-cores-16)
    - Device has status=active and osac_instance_id set (custom field identifies the owner; status identifies allocation state)
    - The managed-by-osac tag is still present

**Tenant Transparency:**
- Create instance against NetBox backend
- Create instance against Metal3 backend
- Verify both workflows are identical to tenant (same BareMetalInstance API, same status conditions)
- No tenant-visible difference in backend choice

**Stress Test:**
- Rapidly create 20 BareMetalInstance requests simultaneously
- NetBox has only 10 available hosts matching label tags (server-side filtering)
- Verify 10 succeed; 10 remain in the existing no-match condition and continue polling
- Verify no double-allocations in NetBox

**Tag-Based Concurrent Stress:**
- Setup: 50 devices with osac-cpu-cores-16; 20 tenants requesting the osac-cpu-cores-16 selector key simultaneously
- Action: All 20 reconcile loops fire concurrently
- Expected: Exactly 20 devices assigned (one per tenant); 30 remain available; no double-allocations (verified by ETag 412 handling); no orphaned assignments

## Graduation Criteria

The planned 70 scenarios are acceptance criteria, not claims about tests already
passing:

- **Dev Preview:** all 48 unit and 12 envtest integration scenarios pass; Helm
  render/install checks pass for NetBox plus Metal3; the ETag race test produces
  exactly one owner; log tests show no selector values, host IDs, UIDs, or
  credentials.
- **Tech Preview:** all 10 E2E scenarios pass against each pinned NetBox image
  in the 4.6.x/4.7.x matrix; 20 concurrent requests against 10 hosts produce
  exactly 10 assignments and no orphaned BMH or BMC Secrets.
- **GA:** all 70 planned scenarios pass across the supported matrix, with no
  critical allocation or credential-exposure defects, and the administrator
  setup, operations, and recovery procedures are published in osac-docs.

## Upgrade / Downgrade Strategy

This is a new backend with no schema migration, but switching away from it has
an explicit drain requirement. Existing backends remain unchanged.

**Downgrade:** Before downgrading to a version without the NetBox backend, stop
new NetBox allocations, delete or otherwise drain every NetBox-backed
BareMetalInstance, and wait for BMH/BMC Secret cleanup. Verify that no
OSAC-managed NetBox device still has a non-empty `osac_instance_id`; only then
switch the Helm values to the alternative backend. If the pool cannot be
drained, keep the NetBox backend enabled until it can be.

**Version Skew:** Not applicable; NetBox backend is contained within one operator binary. No separate services or versions to coordinate.

## Version Skew Strategy

NetBox backend is part of bare-metal-fulfillment-operator; no separate versioning or version skew concerns. Operator and backend version in lockstep.

If future out-of-tree migration (OSAC-3806) separates backend into sidecar, version skew strategy will be defined then. Current design supports clean extraction (backend implements `inventory.Client`; no operator-internal types leaked).

## Support Procedures

### Detect Failures

**Symptoms of misconfiguration:**
- Operator logs: "NetBox API authentication failed"
- BareMetalInstance status reports the existing allocation failure condition
- Prometheus metric `osac_netbox_api_errors_total{error_type="401"}` increasing

**Symptoms of connectivity issues:**
- Operator logs: "NetBox API request timeout"
- BareMetalInstance has `HostConditionAllocated=False` with reason
  `NoMatchingHosts` when the pool is empty; transient API errors are retried
- Tenant-facing status remains the generic "No hosts available" contract and
  does not expose NetBox-specific errors
- Prometheus metric `osac_netbox_api_errors_total{error_type="timeout"}` increasing

**Symptoms of schema mismatch:**
- Operator startup logs: "Custom field osac_instance_id not found in NetBox"
- Operator exits or marks itself unhealthy
- FindFreeHost returns zero devices when devices exist: verify the exact tag slugs used as the BareMetalInstanceType selector keys are applied to devices in NetBox. OSAC does not generate or rewrite capability tags.

### Disable the Feature

To disable NetBox backend and switch to Metal3:

1. Stop new NetBox allocations and drain every BareMetalInstance currently
   allocated from NetBox; allow finalizers to remove its BMH and BMC Secret.
2. Verify that no OSAC-managed NetBox device still has a non-empty
   `osac_instance_id`.
3. Update Helm values: disable `bmf.netbox` and enable the desired alternative
   backend (for example, `bmf.metal3`).
4. Run `helm upgrade osac ./charts/osac -f values.yaml`; the operator restarts
   and picks up the new backend configuration.

If the pool cannot be drained, do not disable NetBox: the configured backend is
also used for cleanup, so switching first can orphan NetBox assignments.

**Impact on cluster health:** After the drain, no active NetBox-backed
BareMetalInstance remains; new allocations use Metal3 and do not interact with
NetBox. Skipping the drain is unsupported because it can leave assignments or
Secrets orphaned.

**Impact on new workloads:**
- New BareMetalInstance requests allocate from Metal3, not NetBox

### Re-Enable and Recovery

To re-enable NetBox backend after disabling:

1. Verify NetBox status/custom-field conventions are intact (`staged` for available, `active` plus `osac_instance_id` for claimed); verify administrator-managed capability tags are applied to devices
2. Ensure API token Secret is present and valid
3. Update Helm values back to `bmf.netbox.enabled: true` and `bmf.metal3.enabled: true`
4. Helm upgrade; operator restarts
5. New allocations use NetBox again. Recreate or resubmit any drained
   BareMetalInstance resources after the backend is enabled.

**Consistency guarantee:** Re-enable is safe after the drain because no active
BareMetalInstance depends on the disabled backend. NetBox allocation state is
durable and is revalidated before new allocations.

## Infrastructure Needed

None for NetBox itself. NetBox is an externally managed dependency owned by the
Cloud Infrastructure Admin; OSAC does not provision, manage, or own its
infrastructure.

Testing infrastructure:
- In-process TLS `httptest.Server` for unit and envtest integration tests
- A pinned NetBox container exposed through a Kubernetes Service for full Kind
  E2E tests
