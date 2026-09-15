---
title: netbox-inventory-backend
authors:
  - Menny Aboush
creation-date: 2026-09-10
last-updated: 2026-09-14
tracking-link: https://redhat.atlassian.net/browse/OSAC-4347
prd: prd.md
see-also: []
replaces: []
superseded-by: []
---

# NetBox Inventory Backend for Bare Metal as a Service

## Summary

This design adds NetBox as a pluggable inventory backend for bare-metal host allocation in OSAC, following the existing backend pattern. Cloud Infrastructure Admin configures NetBox endpoint, credentials, and optional CA certificate via Helm values; OSAC allocates hosts transparently from NetBox inventory without exposing backend details to tenants. See [PRD](prd.md) for detailed requirements.

## Motivation

OSAC's current inventory backends serve specific infrastructure patterns, but there are operators that manage their primary physical inventory in NetBox, a comprehensive infrastructure resource management system. Lack of NetBox integration forces operators to maintain a separate OSAC-specific inventory, creating data inconsistency and operational overhead during lifecycle changes (adding hosts, decommissioning, updating capability metadata).

The NetBox backend integrates into OSAC's existing pluggable inventory system (`inventory.Client` interface) without changing tenant-facing APIs or workflows. Cloud Infrastructure Admin configures the backend; allocation and deallocation remain transparent to tenants via standard `BareMetalInstance` API.

Deployment is in-tree (compiled into the operator) following established patterns for BCM and Metal3, with configuration via Helm values processed by the Enclave Wizard pipeline. This approach avoids operational complexity of separate services while maintaining the option for future out-of-tree extraction per OSAC-3806.

### Goals

- Implement the `inventory.Client` interface for NetBox, following existing backend patterns.

- Prevent double-allocation of hosts via atomic assignment in NetBox with ETag-based optimistic locking (If-Match on PATCH; 412 Precondition Failed on conflict).
- Track allocation state in NetBox via `osac_instance_id` custom field for crash recovery and idempotency.
- Support label-based host selection via NetBox tags (server-side filtering with AND semantics across tags).
- Enable Helm + Enclave Wizard configuration of NetBox endpoint, credentials, and TLS certificates without exposing secrets in logs or error messages.
- Maintain tenant transparency — allocation/deallocation workflows identical across all backends; no NetBox-specific UX.

### Non-Goals

- NetBox device management (adding/removing/editing devices) — operator's responsibility.
- OS provisioning or image selection — orthogonal to inventory allocation; existing Metal3/BMH integration used.
- Status reporting back to NetBox — allocation identifier recorded only.
- Health checks on assigned nodes — if a node is deleted from NetBox while assigned, OSAC does not proactively detect it.
- Admin host-listing or inventory visibility in OSAC API.

## Proposal

NetBox backend is implemented in `bare-metal-fulfillment-operator/internal/inventory/netbox.go`, extending the existing registry pattern in `inventory.go`. A new `NetBoxClient` struct implements the `Client` interface with the following methods:

- **`FindFreeHost(ctx, matchExpressions)`** — Query NetBox for unassigned pool devices filtered by hardware label tags (server-side); return first matching candidate or nil.
- **`AssignHost(ctx, inventoryHostID, bareMetalInstanceID, labels)`** — Atomically mark a device as assigned in NetBox using ETag-based optimistic locking; idempotent for crash recovery.
- **`UnassignHost(ctx, inventoryHostID, labels)`** — Clear assignment marker from NetBox device; idempotent.
- **`GetHostNICs(ctx, inventoryHostID)`** — Retrieve NIC information from the Metal3 BareMetalHost CR created during AssignHost by querying its hardware inspection data. Returns (nil, nil) when hardware inspection has not yet completed; actual NIC discovery happens in the provisioning layer.

Configuration flows through environment variables and Kubernetes Secrets. Cloud Infrastructure Admin provides:

- NetBox API endpoint URL
- API token (stored as a Kubernetes Secret)
- Optional CA certificate (for self-signed TLS)

The backend uses NetBox's native device model and REST API. Host allocation state is tracked using a custom field or metadata mechanism determined during implementation (locked decision D3). Credential security is maintained — secrets never logged; API errors (401, 403) trigger permanent failure with generic messages.

### Workflow Description

#### Cloud Infrastructure Admin: Configure NetBox Backend

1. **Prerequisite:** Devices exist in NetBox with:
   - Hardware label tags in osac-<key>-<value> format (e.g., osac-cpu-cores-16, osac-gpu-model-a100, osac-memory-gb-128). Tags must be pre-created in NetBox before applying to devices.
   - BMC credentials (stored in custom fields, e.g., `bmc_username`, `bmc_password`, `bmc_address`)
   - Tag `managed_by:osac` applied (identifies devices available for OSAC allocation)
   - Status set to `staged` (ready for allocation)
   - Custom field pre-created: `osac_instance_id` (string, nullable)

2. **Create Secret** (one-time setup):
   ```bash
   # Use --from-file to avoid exposing token in shell history or process arguments
   echo "<api-token>" > /tmp/netbox-token.txt
   kubectl create secret generic netbox-api-token \
     --from-file=token=/tmp/netbox-token.txt \
     -n osac
   rm /tmp/netbox-token.txt
   ```

3. **Configure Helm values** (`values.yaml`):
   ```yaml
   inventory:
     type: netbox
     endpoint: "https://netbox.example.com"
     secretRef: netbox-api-token
     caCert: |
       -----BEGIN CERTIFICATE-----
       ...
       -----END CERTIFICATE-----
     provisioning:
      type: metal3
      # Metal3 config required
   ```

4. **Deploy via osac-installer:**
   ```bash
   helm install osac ./charts/osac -f values.yaml
   ```

5. **Operator starts** with NetBox backend registered in inventory client registry. Configuration is validated:
   - Connectivity test to NetBox endpoint (can reach the URL)
   - Token validity check (401/403 → authentication failed)

#### Tenant User: Request and Release Bare-Metal Host

1. **Create BareMetalInstance** (via fulfillment-service API):
   ```protobuf
   BareMetalInstancesCreateRequest {
     object {
       spec {
         catalog_item { id: "ubuntu-22.04" }
         instance_type { id: "type-gpu-a100" }
         ssh_public_key: "ssh-rsa AAAA..."
         network_attachments { ... }
       }
     }
   }
   ```
   Hardware requirements and capabilities come from the `instance_type` specification (CPU cores, memory, GPU, etc.), not from request-level labels.

2. **Operator reconciliation** (bare-metal-fulfillment-operator):
   - If `ExternalHostID` is already set on the BareMetalInstance CR:
     - Skip `FindFreeHost`; go directly to `AssignHost` with the recorded device ID
     - If `AssignHost` returns (host, Ready) → device is ours; proceed to provisioning
     - If `AssignHost` returns (nil, nil) → device was claimed by another request during a prior crash window; clear `ExternalHostID` and fall through to `FindFreeHost` below
   - Extract hardware requirements from the instance_type specification (CPU cores, memory, GPU, etc.)
   - Convert tenant label selectors from instance_type to tag slugs (e.g., cpu_cores=16 → osac-cpu-cores-16)
   - Query NetBox for unassigned devices matching device tag AND all hardware label tags (server-side filtering): tag=managed_by:osac, tag=osac-cpu-cores-16, tag=osac-gpu-model-a100, status=staged, osac_instance_id__empty=true
   - Call `FindFreeHost` with first result → returns host or nil
   - If nil: requeue with exponential backoff; tenant sees "No hosts available"
   - If found: record `ExternalHostID` in BareMetalInstance CR status (persist the candidate device ID BEFORE assignment)
   - Call `AssignHost` on the candidate device
   - On race condition (another request claims same host): `AssignHost` returns (nil, nil); clear `ExternalHostID`; retry from `FindFreeHost`
   - On success: proceed to power/provisioning

3. **Host Provisioning** (existing Metal3/BMH workflow):
   - Create or update Metal3 BareMetalHost for power management
   - Status progresses: Provisioning → Provisioned → Ready
   - Tenant monitors progress via BareMetalInstance status conditions

4. **Delete BareMetalInstance** (tenant deallocation):
   - Controller calls `UnassignHost` to clear assignment marker in NetBox
   - Host returns to available pool
   - Physical cleanup (BMH deletion, power management) handled by existing controllers

#### Failure Scenarios

For detailed failure handling flows (race conditions, transient failures, crash recovery), see **AssignHost Implementation** and **UnassignHost Implementation** sections above.

Crash recovery is handled by pre-recording `ExternalHostID` on the CR before NetBox assignment. On restart, the controller checks `ExternalHostID` first and resumes from the correct step. See **Crash Recovery (Operator Restart)** under **AssignHost Implementation** for details on all three crash scenarios.

**Operational Failure Modes:**

**NetBox Unreachable (Transient Network Error)**
- `FindFreeHost` or `AssignHost` network request fails
- Controller requeues with exponential backoff
- On recovery: reconciliation retries; idempotency ensures safe retry
- Tenant sees "No hosts available" (not NetBox-specific)

**Invalid Credentials (Permanent Failure)**
- API request fails with 401 Unauthorized or 403 Forbidden
- Controller logs permanent error; event emitted to BareMetalInstance
- Cloud Infrastructure Admin sees actionable message in logs
- Secret validation at operator startup should catch this before allocation attempts
- Remediation: fix Secret; operator picks up changes on restart

**Inventory Exhaustion (No Matching Hosts)**
- `FindFreeHost` returns (nil, nil) when no devices match the tenant's label selectors or all matching devices are already assigned
- Controller sets BareMetalInstance phase to `Failed` with condition `HostConditionAllocated = False`, reason `NoMatchingHosts`
- Controller requeues reconciliation after `NoFreeHostsPollIntervalDuration` (configurable, default: 30 seconds)
- Requeue attempts continue indefinitely until:
  - **Capacity becomes available:** Cloud Infrastructure Admin adds devices with matching labels to NetBox and tags them with `managed_by:osac` → next reconciliation retry succeeds
  - **Existing hosts deallocated:** Other BareMetalInstance objects deleted → freed devices become available → next reconciliation retry succeeds
  - **Request cancelled:** Tenant deletes the BareMetalInstance
- Tenant sees condition: `HostConditionAllocated = False`, `reason = "NoMatchingHosts"`, `message = "No matching hosts available"`
- Tenant sees event emitted to BareMetalInstance object
- Remediation: Cloud Infrastructure Admin adds matching capacity to NetBox inventory (no operator restart needed)

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
type NetBoxConfig struct {
    Endpoint      string `json:"endpoint"`      // https://netbox.example.com
    TokenSecret   string `json:"tokenSecret"`   // Kubernetes Secret name
    CACertSecret  string `json:"caCertSecret"`  // Optional Secret for CA cert
}
```

Configuration is unmarshaled from YAML in a Kubernetes Secret mounted at `OSAC_INVENTORY_CONFIG_PATH`. Helm charts and Enclave Wizard pipeline process user input into this structure. [Locked: D2]

**Hardcoded Conventions:** Device selection tag and hardware label tag format are not configurable; OSAC uses fixed names to maintain consistent conventions across all deployments:
- Device selection tag: `managed_by:osac` (identifies OSAC-managed devices)
- Allocation tracking field: `osac_instance_id` (...)
- Hardware label tags: osac-<key>-<value> format (e.g., osac-cpu-cores-16, osac-gpu-model-a100). Tags are indexed in NetBox and used for server-side filtering during FindFreeHost queries.

### Allocation Tracking and Device Filtering

Allocation state and device pool selection use two NetBox mechanisms:

**1. Device Pool Selection via NetBox Tags**

Devices are tagged in NetBox with the OSAC pool tag (`managed_by:osac`). Cloud Infrastructure Admin applies this tag to all devices that should be available for OSAC allocation; the operator queries only tagged devices.

**2. Allocation Tracking via Custom Field**

A custom field `osac_instance_id` (string, nullable) on each device stores the BareMetalInstanceID when allocated. Empty value means device is unassigned; populated value means device is owned by that BareMetalInstance.

**FindFreeHost Query:**

The query combines device selection filters with tenant hardware label tags:

```
GET /api/dcim/devices/?tag=managed_by:osac&tag=osac-cpu-cores-16&tag=osac-gpu-model-a100
&status=staged&osac_instance_id__empty=true&limit=100&offset=0
```

All filters are server-side and indexed:

| Filter parameter               | Purpose                           |
|--------------------------------|-----------------------------------|
| tag=managed_by:osac            | Device membership                 |
| tag=osac-<key>-<value> (×N)    | Hardware label matching (AND)     |
| status=staged                  | Readiness for allocation          |
| osac_instance_id__empty=true   | Unassigned devices only           |

Multiple tag= parameters use AND semantics — only devices matching ALL specified tags are returned.

The tenant's label selectors (from the BareMetalInstance instance_type spec) are converted to tag slugs before query construction:
```
Input: {"cpu_cores": "16", "gpu_model": "A100"}
Slugified: ["osac-cpu-cores-16", "osac-gpu-model-a100"]
Query params: &tag=osac-cpu-cores-16&tag=osac-gpu-model-a100
```

**Advantages:**
- Server-side filtering: only matching devices returned by NetBox; reduced network payload
- No client-side label parsing or matching code
- Tags are indexed — efficient even with large device counts
- Consistent tag pattern: managed_by:osac for device membership, osac-<key>-<value> for hardware labels
- ETag protection covers tag modifications identically to custom field modifications

### NetBox REST API Interactions

**HTTP Client Pattern:**
- Thin custom HTTP client (no external NetBox SDK; follow BCM pattern of hand-rolled client)
- Base URL: from config (e.g., `https://netbox.example.com/api/`)
- Authentication: Bearer token in `Authorization: Token <token>` header
- TLS validation: system CA bundle + optional custom CA cert (injected into http.Client Transport)
- Timeout: 30s per request (configurable)
- Retry logic: transient errors (5xx, network) up to 3 times; 412 Precondition Failed triggers race-loss path (not retried as transient — handled by caller); permanent errors (401, 403, 4xx validation) fail fast

**Key Endpoints:**
- `GET /api/dcim/devices/` — List devices with filters (pool tag, status, assignment field)
- `GET /api/dcim/devices/{id}/` — Fetch single device; response includes ETag header for optimistic locking
- `PATCH /api/dcim/devices/{id}/` — Update device `osac_instance_id` field during assignment/unassignment. Sends `If-Match` header with ETag from prior GET to detect concurrent modifications (412 Precondition Failed on conflict)

**Error Handling:**
- 401 Unauthorized — Secret validation failure; permanent; actionable message
- 403 Forbidden — Token lacks permissions; permanent; actionable message
- 4xx validation (excluding 412) — Invalid query/filter; permanent; actionable message (must include field names for debugging)
- 412 Precondition Failed — Concurrent modification detected (ETag mismatch); another operator or process modified the device since our last GET. In AssignHost: return (nil, nil) — treat as race loss. In UnassignHost: re-read device and retry from step 1.
- 5xx server error — Transient; retry with backoff
- Network error (timeout, connection refused) — Transient; retry with backoff

No secrets or tenant data logged. Error messages use generic "unable to contact inventory backend" when exposing would leak information.

#### Label Matching Strategy

**Approach: Server-side tag filtering**

Hardware labels are stored as NetBox tags in osac-<key>-<value> format. Label matching is performed entirely server-side by including tenant label selectors as tag query parameters in the FindFreeHost API call. NetBox applies AND semantics on multiple tag= parameters, returning only devices that match all requested labels.

**Why tags over custom fields:**
- Tags are indexed in NetBox; custom field values (especially JSON sub-keys) are not efficiently queryable via the API
- Server-side filtering reduces network payload and eliminates client-side matching code
- ETag-based optimistic locking protects tag modifications identically to custom field modifications
- Each inventory backend optimizes for its own capabilities; the inventory.Client interface abstracts the matching strategy

**Matching contract:**
- Tenant provides: key=value label selectors from instance_type (e.g., cpu_cores=16, gpu_model=A100)
- Operator converts each to tag slug: osac-<key>-<value> (e.g., osac-cpu-cores-16, osac-gpu-model-a100)
- NetBox API returns only devices matching ALL requested tags
- A device with EXTRA tags beyond those requested is still a valid match (superset matching)

**Tag slug rules:**
- Format: osac-<key>-<value>
- Characters allowed: [a-z0-9-] only (lowercase alphanumeric and hyphens)
- Key underscores become hyphens (cpu_cores → cpu-cores)
- Values are lowercased and slugified (A100 → a100)
- Label keys and values that cannot be slugified are rejected at the API level with a validation error

**Validation:** strict slug-safe enforcement. Label keys and values must contain only alphanumeric characters, underscores, and hyphens. Spaces and special characters are rejected.

### AssignHost Implementation

**Normal Path (Happy Case):**
1. Read device from NetBox by ID and check assignment status. **Capture the ETag header from the response.**
   - If already assigned to **same ID** → return (host, Ready status) — skip to readiness check
   - If assigned to **different ID** → return (nil, nil) — another request won the race
   - If unassigned → proceed to step 2
2. Extract BMC credentials: read `bmc_username`, `bmc_password`, `bmc_address` from device custom fields
3. PATCH assignment: update NetBox device with `osac_instance_id = bareMetalInstanceID`. **Include `If-Match: <etag>` header from step 1.** If NetBox returns **412 Precondition Failed** → another process modified the device since our read; return (nil, nil) — treat as race loss.
4. Verify write (sanity check): read device back; confirm `osac_instance_id` matches. This is now a safety net rather than the primary race detection mechanism — the ETag in step 3 prevents concurrent overwrites.
5. Create BMC Secret: create Kubernetes Secret with extracted BMC credentials
6. Create BMH: call `bmhManager.CreateBMH()` to create Metal3 BareMetalHost CR (idempotent)
7. Check readiness: query BMH status; return `Host.Ready = true/false`

**Idempotency Contract (Safe for Unlimited Retries):**
- Every call starts by reading device and checking current assignment
- If already assigned to same ID → skip all write operations, return cached state
- If assigned to different ID → return (nil, nil) without writing
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
  - Both CR (`ExternalHostID`) and NetBox (`osac_instance_id`) are consistent
  - On restart, `AssignHost` step 1 finds matching assignment → returns (host, Ready); reconciliation continues to provisioning

### UnassignHost Implementation

**Normal Path (Happy Case):**
1. Read device and check assignment. **Capture the ETag header.**
   - If `osac_instance_id` is empty → return success (already unassigned)
   - If has **different assignment** → return success (not ours; don't touch)
   - If has **matching assignment** → proceed to step 2
2. Delete BMH: call `bmhManager.DeleteBMH()` to remove Metal3 BareMetalHost CR (device remains assigned in NetBox during cleanup)
3. Delete Secret: call `bmhManager.DeleteBMCSecret()` to remove BMC credentials
4. Clear assignment: PATCH NetBox to clear `osac_instance_id`. **Include `If-Match: <etag>` header from step 1.** If NetBox returns **412 Precondition Failed** → re-read device and retry from step 1 (another process modified the device concurrently).
5. Verify write (sanity check): read device back; confirm field is cleared

**Idempotency Contract:**
- Same read-first pattern as AssignHost
- Every retry starts by checking device state
- Safe for multiple retries without duplicate writes
- ETag-based `If-Match` on PATCH prevents concurrent modification; 412 triggers re-read and retry (safe because unassignment is idempotent)

### Metal3 BareMetalHost Lifecycle

The inventory client manages Metal3 BareMetalHost CR creation and deletion (see AssignHost/UnassignHost Implementation above for full flow). The BMH reconciler handles power management, hardware inspection, and readiness reporting.

**Key Properties:**

- **Coupled lifecycle** — Inventory allocation and BMH creation happen together (steps 6-7 in AssignHost); device is unavailable until provisioning infrastructure is ready
- **Idempotent** — `CreateBMH()` is idempotent; crash recovery finds BMH already exists and reuses it
- **Atomic deallocation** — allocation marker cleared and BMH deleted together (UnassignHost steps 2-5); no orphaned resources
- **Readiness reporting** — BMH status indicates Ready/not-ready; `AssignHost` returns this status to caller; controller requeues until ready

**BMC Credential Security:**

- Credentials stored in NetBox (infrastructure inventory), not in Kubernetes
- Fetched at assignment time (AssignHost step 2) and injected into operator-created Secret (step 5)
- Secret labeled with ownership marker for cleanup on deallocation
- Credentials never logged; error messages sanitized
- Reuses Metal3/BMH integration without modifying provisioning layer

### TLS and Credential Security

**Credential Management:**
- API token stored in Kubernetes Secret (e.g., `netbox-api-token`)
- Secret is mounted into operator Pod via volume or injected at startup
- Operator reads Secret; constructs HTTP client with Bearer token
- Token never logged; errors sanitized to hide sensitive values

**TLS Configuration:**
- System CA bundle used by default
- Optional custom CA cert provided via separate Kubernetes Secret (e.g., `netbox-ca-cert`)
- Certificate pinning not supported in initial implementation 
- Self-signed cert support: Cloud Infrastructure Admin provides CA cert; operator adds to `http.Client.Transport.TLSClientConfig`

**Validation at Startup:**
- Operator reads configuration on startup
- Test connectivity to NetBox endpoint with provided credentials
- If connectivity fails: emit warning event; continue (graceful degradation) or fail fast (configurable)
- Invalid token detected at first `FindFreeHost` call; BareMetalInstance status shows diagnostic message

### Configuration via Helm Values and Enclave Wizard

NetBox backend **requires Metal3 for power management and host provisioning**. Both must be configured.

osac-installer/charts/osac/values.yaml schema:

```yaml
inventory:
  type: "netbox"
  options:
    endpoint: "https://netbox.example.com"
    tokenSecret: "netbox-api-token"  # Kubernetes Secret name
    caCertSecret: "netbox-ca-cert"   # Optional

management:
  type: "metal3"
  options:
    namespace: "baremetal"            # Metal3 BareMetalHost namespace
    # Metal3 configuration
```

**Validation at deployment:**
- Operator startup checks `inventory.type == "netbox"` AND `management.type == "metal3"`
- Fails fast if either is missing or misconfigured
- On NetBox configuration: attempts immediate connectivity and schema validation; fails operator startup if NetBox is unreachable or schema is invalid

Enclave Wizard pipeline (pre-deployment):
1. Accepts user input (NetBox endpoint, credentials, Metal3 namespace)
2. Creates Kubernetes Secret with NetBox API token
3. Validates NetBox connectivity and schema: confirms osac_instance_id custom field exists; verifies managed_by:osac device selection tag is defined; attempts authentication with provided token
4. Validates Metal3 availability (BareMetalHost CRD installed)
5. Generates values.yaml with resolved configuration
6. Helm chart deploys operator with both inventory and management backends configured

**Startup validation contract (operator initialization):**
- Authentication failures (401, 403): detected at operator startup via schema validation call; operator fails fast with actionable message
- Connectivity failures: detected at operator startup; operator fails fast
- Schema validation failures (osac_instance_id missing): detected at operator startup; operator fails fast
- Invalid endpoint URL: detected at operator startup; operator fails fast
- Result: if operator starts successfully, NetBox backend is reachable, authenticated, and properly configured

### Error Messages and Diagnostics

Cloud Infrastructure Admin receives clear, actionable messages:

- **At startup:** "NetBox backend initialized (endpoint: netbox.example.com)"
- **On connectivity failure:** "Failed to connect to NetBox API (https://netbox.example.com): request timeout after 30s. Check endpoint URL and network connectivity."
- **On auth failure:** "NetBox API authentication failed. Verify API token in Secret netbox-api-token is valid and has permissions to read/update devices."

## Security Considerations

### Credential Handling

NetBox API token is stored in a Kubernetes Secret with RBAC restrictions. Operator Pod has read-only access to the token Secret; no other workloads do. Token is never logged; audit logging is managed by Kubernetes RBAC (Secret reads are auditable).

No plaintext credentials in OSAC logs, config files, or error messages. API errors that might leak token details (e.g., 401 responses) are caught and replaced with generic messages. [PRD: FR-2, FR-3]

### Tenant Isolation

No tenant-identifying data is recorded in NetBox. Assignment identifier is OSAC-internal (BareMetalInstance UID or UUID); NetBox stores only the assignment ID, not tenant name or namespace. [PRD: FR-10]

Tenant users cannot see which backend is in use or any NetBox state; allocation is transparent. Network namespace or firewall rules may restrict NetBox API access to OSAC control plane only. [PRD: FR-11]

### Input Validation

Label selectors from BareMetalInstance API are user-provided key=value pairs. These are converted to tag slugs and included in NetBox API query URLs. Input validation requirements:

- Keys and values must match [a-zA-Z0-9_-]+ (alphanumeric, underscores, hyphens only)
- Values are lowercased and slugified before query construction
- Keys with underscores are converted to hyphens in the slug
- Any label key or value containing characters outside the allowed set is rejected with a validation error before any NetBox query is made
- The osac- prefix is added by the operator, never by the tenant — tenants provide raw key=value pairs (e.g., cpu_cores=16), not tag slugs (e.g., osac-cpu-cores-16)
- URL encoding is applied to the final query string to prevent injection via special characters in tag parameters

NetBox queries constructed defensively:
```go
// Safe: URL parameters are URL-encoded by http.Client
params := url.Values{}
params.Add("tag", "managed_by:osac")
params.Add("tag", "osac-cpu-cores-16")
params.Add("status", "staged")
params.Add("osac_instance_id__empty", "true")
// Result: tag=managed_by:osac&tag=osac-cpu-cores-16&status=staged&osac_instance_id__empty=true
```

### Authorization

OSAC trusts NetBox API token to enforce authorization. Token should have read/update permissions on the device model only; no create/delete (operator never removes devices from NetBox). [Assumption: Cloud Infrastructure Admin configures NetBox token with least-privilege scopes]

## Failure Handling and Recovery

### Transient Failures (Retried)

**Network timeout during FindFreeHost:**
- Operator logs: "inventory backend request timeout; requeuing BareMetalInstance"
- BareMetalInstance status: no change (remains in previous state)
- Retry: exponential backoff (existing provisioning lifecycle handles retries)
- Tenant observation: provisioning stalls; monitoring/alerting (Prometheus metrics) detects slowdown

**5xx server error from NetBox:**
- AssignHost request fails; logged as transient
- Retry up to 3 times with backoff
- If all retries fail: requeue BareMetalInstance (controller retries reconciliation)

### Permanent Failures (No Retry)

**401 Unauthorized (bad token):**
- Operator logs: "NetBox API authentication failed; check Secret netbox-api-token"
- BareMetalInstance status condition: "InventoryAllocationFailed", message includes "Invalid NetBox credentials"
- Recovery: Cloud Infrastructure Admin fixes Secret; operator picks up on next reconciliation (no automatic Secret reload required if using mounted volume)

**NetBox device not found:**
- Returned by `FindFreeHost`; not an error (nil, nil is expected when no candidates)
- No diagnostic action needed

### Idempotency and Crash Recovery

If operator crashes or is restarted during reconciliation:

1. **Crash after AssignHost succeeds but before CR update:**
   - Operator restarts; reconciliation resumes with stale BareMetalInstance (no ExternalHostID)
   - Calls AssignHost again with same ID → returns (host, nil) — idempotent
   - Proceeds to update CR with ExternalHostID; completes reconciliation

2. **Crash during UnassignHost:**
   - Operator restarts; reconciliation resumes
   - BareMetalInstance still in terminating state
   - Calls UnassignHost again with same ID → returns nil (idempotent)
   - Completes deletion

All failure modes are designed to be safely retriable without side effects (idempotent operations).

## RBAC / Tenancy

No changes to RBAC or tenancy model. Existing BareMetalInstance RBAC applies unchanged.

NetBox backend records assignment identifier (BareMetalInstance UID) in NetBox, not tenant name. Tenant isolation is enforced at the BareMetalInstance API level (fulfillment-service OPA policies); NetBox stores no tenant-identifying data.

If NetBox API is externally accessible (not recommended), network policies or firewall rules should restrict access to OSAC control plane only.

## Observability and Monitoring

### Metrics

New Prometheus metrics emitted by NetBox backend:

| Metric | Type | Labels | Meaning |
|--------|------|--------|---------|
| `osac_netbox_hosts_available` | gauge | `host_class` | Total count of unassigned staged devices in the pool (tag=managed_by:osac, status=staged, osac_instance_id empty); sampled via dedicated capacity count query to NetBox (independent of tenant label filters) |
| `osac_netbox_assignment_attempts_total` | counter | `result` | Total AssignHost attempts; result = success/race/error |
| `osac_netbox_api_errors_total` | counter | `error_type` | Total API errors by type (401, 403, 5xx, timeout) |

### Structured Logs

Controller logs include:
- `host_search_label_selector` — labels requested by tenant
- `label_tags_queried` — tag slugs sent to NetBox for this tenant's request (e.g., ["osac-cpu-cores-16", "osac-gpu-model-a100"])
- `matching_devices_count` — count of devices returned by NetBox matching this tenant's label tags
- `selected_host_id` — NetBox device ID selected (if non-nil)
- `assignment_id` — BareMetalInstance UID assigned to device
- `netbox_api_error` — error type/code (never token value or full response)

No tenant data or credential details logged.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| NetBox API incompatibility across versions | Features broken in upgrades | Document minimum NetBox version (4.x); test against multiple versions in CI |
| Credential exposure via error messages | Security breach | Audit all error paths; sanitize NetBox error responses; never log API responses |
| NetBox network partition | Allocation blocked until recovery | Graceful degradation: timeout after 30s; requeue BareMetalInstance; no tenant-visible difference |
| Race between AssignHost and UnassignHost | Device simultaneously assigned and deallocated; inconsistent state | Idempotent operations: AssignHost detects existing assignment; UnassignHost checks assignment ID before clearing; safe to retry both |

All mitigations are concrete and testable.

## Drawbacks

**Read-then-verify assignment pattern** — Not transactional; brief window between read and write. If NetBox is modified externally during that window, assignment may fail. Mitigation: retry loop; acceptable for rare scenarios (operator editing device state concurrently).

## Alternatives (Not Implemented)

### Alternative 1: Use NetBox Device Status Enum for Assignment Tracking

Instead of a custom field, use the built-in `status` field (offline/active/planned/staged/failed/inventory). Assign hosts would have status set to "osac-assigned" or similar.

**Pros:**
- No custom field required; simpler NetBox schema
- Native status field; operators already familiar with it

**Cons:**
- Conflicts with device lifecycle (e.g., device goes offline → status changes, losing OSAC assignment marker)
- Other systems managing NetBox state may overwrite status
- Incompatible with parallel operations (if operator sets status to "failed" for maintenance, OSAC loses track of assignment)

**Rejection:** Custom field is more robust; status field should reflect device operational state, not allocation ownership.

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

**Rejection:** [PRD: Out of Scope] Deferred to future enhancement. Current design allows future extension without changes to NetBox backend.

## Open Questions

### NetBox Version Compatibility — CRITICAL: Minor Versions Have Breaking Changes

**Question:** Which specific NetBox versions will be supported? **NetBox does NOT follow semantic versioning** — minor version updates (e.g., 4.6 → 4.7) introduce breaking API changes.

**Owner:** Implementation task; Cloud Infrastructure Admin (testing feedback)

**Critical Breaking Changes in Minor Versions (Real Examples):**

**NetBox 4.7.0 (minor update from 4.6)** contains major API breaks:

- Selection custom field return format changed: `"value"` → `{"value": "x", "label": "X"}`
- Infrastructure dependencies: PostgreSQL 14 dropped (requires 15+), Redis 5.x dropped (requires 6.0+)
- Django upgraded to 6.1 (may affect plugins and integrations)
- Custom field filtering API syntax changed
- Service `protocol`/`ports` fields replaced by `port_mappings` array

**NetBox 4.0.0 (major)** changed:

- `device_role` → `role` field rename
- Token authentication format (v1 → v2)

Decision impacts:

- HTTP client implementation must handle selection field format variations
- Custom field filtering varies by version
- PostgreSQL/Redis version constraints must match target NetBox version
- CI test matrix must cover supported version range (e.g., NetBox 4.3-4.7)
- Documentation must specify exact supported versions

**Expected Resolution:**

- Target specific point releases (e.g., "NetBox 4.3 through 4.7") NOT just "4.x"
- E2E tests run against multiple versions to catch breaking changes
- Implementation maintains version-specific API handling where needed
- Document compatibility matrix clearly (e.g., OSAC 1.0 supports NetBox 4.3-4.7)

## Test Plan

### Unit Tests

**Configuration Parsing and Validation:**
- Parse valid YAML config; assert all fields populated correctly
- Parse config with missing endpoint; assert error
- Parse config with invalid token Secret reference; assert error
- TLS certificate loading from Secret; assert correct CA added to http.Client
- **Tag slug generation from config:**
  - Setup: Tenant instance_type has labels: {"cpu_cores": "16", "GPU_Model": "A100", "arch": "x86_64"}
  - Action: Operator converts to tag slugs
  - Expected: ["osac-cpu-cores-16", "osac-gpu-model-a100", "osac-arch-x86-64"]
- **Tag slug validation rejects invalid characters:**
  - Setup: Label value contains spaces: {"desc": "big server"}
  - Action: Operator attempts slug conversion
  - Expected: Validation error before any NetBox query; BareMetalInstance status shows error message

**Label Matching → Tag Query Construction (Unit Tests):**
- Input: {"cpu_cores": "16", "gpu_model": "A100"}
  Expected tags: ["osac-cpu-cores-16", "osac-gpu-model-a100"]
- Input: {"memory_gb": "128"}
  Expected tags: ["osac-memory-gb-128"]
- Input: {"key_with_underscores": "value"}
  Expected tags: ["osac-key-with-underscores-value"]
- Input: {"key": "UPPERCASE_Value"}
  Expected tags: ["osac-key-uppercase-value"]
- Input: {"invalid key!": "value"}
  Expected: validation error (invalid characters)
- Input: {"key": "value with spaces"}
  Expected: validation error (invalid characters)

**FindFreeHost Logic:**
- **Device with matching tags:** Mock NetBox returns device with tags [managed_by:osac, osac-cpu-cores-16]; tenant requests cpu_cores=16 → device is returned
- **Device with wrong tags:** Mock NetBox returns empty list (server-side filtering); tenant requests gpu_model=V100 but no devices have osac-gpu-model-v100 → nil returned
- **Superset match:** Device has tags [osac-cpu-cores-16, osac-gpu-model-a100, osac-memory-gb-128]; tenant requests only cpu_cores=16 → device IS returned (extra tags are fine)
- No devices match device selection tag → nil
- All staged devices assigned → nil
- Large result set (100+ devices) → pagination handled correctly

**Capacity Count Query:**
- **Test 1 — Count returns correct number:**
  - Setup: Mock NetBox with 5 devices matching device selection filters (tag=managed_by:osac, status=staged, osac_instance_id empty)
  - Action: Capacity count query with brief=true&limit=1
  - Expected: Response JSON has "count": 5; results array has exactly 1 device (brief format)
- **Test 2 — Count updates after assignment:**
  - Setup: 5 available devices; AssignHost one device
  - Action: Re-run capacity count query
  - Expected: "count": 4 (one fewer available)
- **Test 3 — Count with no available devices:**
  - Setup: All devices have osac_instance_id set
  - Action: Capacity count query
  - Expected: "count": 0; results array empty

**AssignHost Idempotency:**
- Assign host → device now has osac_instance_id; read-after-write confirms
- Assign same host with same ID again → idempotent, returns (host, nil)
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
- Unassign assigned host → osac_instance_id cleared; read-after-write confirms
- Unassign same host again → idempotent, returns nil
- Unassign host with different assignment ID → returns nil (not ours)
- **412 during unassignment:**
  - Setup: Mock GET returns device assigned to our instance; PATCH returns 412 Precondition Failed
  - Action: UnassignHost step 2 sends PATCH with If-Match
  - Expected: UnassignHost re-reads device (back to step 1) and retries; does NOT return error on first 412

**Error Handling:**
- NetBox API returns 401 → error logged; permanent; no retry
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
  - Assert: device-42 has osac_instance_id set to the winner's ID, not the loser's
- **Concurrent tag-based FindFreeHost:**
  - Setup: 3 devices with osac-cpu-cores-16 tag; 2 tenants request cpu_cores=16 simultaneously
  - Action: Both call FindFreeHost with same tag filters
  - Expected: Both get results from NetBox; AssignHost ETag protection prevents double-allocation; one gets device, other retries or gets different device

### Integration Tests

**Against Real Kind Cluster:**
- NetBox simulator (mock HTTP server) listening at localhost:8080
- Deploy operator with NetBox config pointing to simulator
- Create BareMetalInstance with label selectors
- Verify FindFreeHost called; host allocated; ExternalHostID set in status
- Delete BareMetalInstance; verify UnassignHost called; host deallocated
- Verify no regressions in other backends (Metal3, BCM still work if configured)
- **Concurrent assignment with ETag protection:**
  - Setup: Two BareMetalInstance CRs requesting same label profile; only one device matches in mock NetBox
  - Action: Both controllers attempt AssignHost on same device
  - Expected: Exactly one gets 200; the other gets 412 and retries FindFreeHost; no device is double-assigned

**Failure Recovery:**
- Simulate NetBox connectivity loss (network partition) during FindFreeHost
- Observe operator retries; eventual recovery when connectivity restored
- Simulate permanent auth failure; verify error condition in BareMetalInstance status

**Configuration Lifecycle:**
- Deploy operator with invalid config (bad endpoint); verify startup error
- Fix config (update Secret/ConfigMap); verify operator picks up change
- Switch from one backend to another; verify no orphaned state

**Tag Update on Device:**
- Setup: Device has tag osac-memory-gb-64
- Action: Admin removes osac-memory-gb-64 tag and adds osac-memory-gb-128
- Expected: FindFreeHost for memory_gb=64 no longer returns this device; FindFreeHost for memory_gb=128 now returns it

**Capacity Metrics Endpoint:**
- Setup: Kind cluster with operator running; mock NetBox with 10 staged devices
- Action: Scrape operator's /metrics endpoint
- Expected: osac_netbox_hosts_available gauge shows 10; after one assignment, gauge shows 9

**Server-Side Tag Filtering Verification:**
- Setup: Kind cluster; mock NetBox with 10 devices: 5 have osac-gpu-model-a100, 5 have osac-gpu-model-v100
- Action: Tenant requests gpu_model=A100
- Expected: FindFreeHost query includes tag=osac-gpu-model-a100; NetBox returns only the 5 matching devices; operator does NOT receive or filter the V100 devices

**Tag Mismatch — Zero Results:**
- Setup: Mock NetBox devices have osac-gpu-model-a100
- Action: Tenant requests gpu_model=H100
- Expected: FindFreeHost query includes tag=osac-gpu-model-h100; NetBox returns empty list; operator requeues with "No hosts available"

### E2E Tests

Tests run against **real NetBox container** (not mock). Fixtures provision NetBox instance with osac_instance_id custom field, device selection tag (managed_by:osac), hardware label tags (osac-cpu-cores-16, osac-gpu-model-a100, etc.), and test devices.

**End-to-End Provisioning:**
- Create BareMetalInstance with label selector matching NetBox devices
- Observe allocation from NetBox
- Verify Metal3 BareMetalHost created for power management
- Monitor provisioning completion (existing BareMetalInstance status workflow)
- Delete instance; verify host deallocated and returned to pool
- **Tag preservation after provisioning:**
  - After provisioning succeeds, verify:
    - Device in NetBox still has all original hardware label tags (osac-cpu-cores-16, etc.) — assignment does not remove them
    - Device has osac_instance_id set (custom field, not tag)
    - The managed_by:osac tag is still present

**Tenant Transparency:**
- Create instance against NetBox backend
- Create instance against Metal3 backend
- Verify both workflows are identical to tenant (same BareMetalInstance API, same status conditions)
- No tenant-visible difference in backend choice

**Stress Test:**
- Rapidly create 20 BareMetalInstance requests simultaneously
- NetBox has only 10 available hosts matching label tags (server-side filtering)
- Verify 10 succeed; 10 requeue and eventually fail ("No hosts available")
- Verify no double-allocations in NetBox

**Tag-Based Concurrent Stress:**
- Setup: 50 devices with osac-cpu-cores-16; 20 tenants requesting cpu_cores=16 simultaneously
- Action: All 20 reconcile loops fire concurrently
- Expected: Exactly 20 devices assigned (one per tenant); 30 remain available; no double-allocations (verified by ETag 412 handling); no orphaned assignments

## Graduation Criteria

Graduation criteria will be defined when targeting a release. Expected stages:

- **Dev Preview:** NetBox backend implemented and tested in Kind cluster; ready for internal evaluation
- **Tech Preview:** Deployed to test environment with representative NetBox instance; feedback incorporated
- **GA:** Production deployment feedback confirms reliability; full documentation in osac-docs

## Upgrade / Downgrade Strategy

This is a new backend with no upgrade/downgrade impact. Deployment adds a new inventory backend option; existing backends remain unchanged.

**Downgrade:** If OSAC is downgraded before NetBox backend is added (earlier version), simply revert Helm values to use different backend (e.g., Metal3). All BareMetalInstance resources remain; allocation state recorded in NetBox persists (no cleanup needed, as NetBox is SoT for inventory).

**Version Skew:** Not applicable; NetBox backend is contained within one operator binary. No separate services or versions to coordinate.

## Version Skew Strategy

NetBox backend is part of bare-metal-fulfillment-operator; no separate versioning or version skew concerns. Operator and backend version in lockstep.

If future out-of-tree migration (OSAC-3806) separates backend into sidecar, version skew strategy will be defined then. Current design supports clean extraction (backend implements `inventory.Client`; no operator-internal types leaked).

## Support Procedures

### Detect Failures

**Symptoms of misconfiguration:**
- Operator logs: "NetBox API authentication failed"
- Events on BareMetalInstance: "InventoryAllocationFailed — Invalid NetBox credentials"
- Prometheus metric `netbox_api_errors_total{error_type="401"}` increasing

**Symptoms of connectivity issues:**
- Operator logs: "NetBox API request timeout"
- Events on BareMetalInstance: "NoHostsAvailable" (if retry backoff exhausted)
- Prometheus metric `netbox_api_errors_total{error_type="timeout"}` increasing

**Symptoms of schema mismatch:**
- Operator startup logs: "Custom field osac_instance_id not found in NetBox"
- Operator exits or marks itself unhealthy
- FindFreeHost returns zero devices when devices exist: verify hardware label tags (osac-<key>-<value>) are applied to devices in NetBox. Check tag slugs match expected format.

### Disable the Feature

To disable NetBox backend and switch to Metal3:

1. Update Helm values: `inventory.type: metal3` (or other backend)
2. Helm upgrade: `helm upgrade osac ./charts/osac -f values.yaml`
3. Operator restarts; picks up new backend configuration
4. Existing BareMetalInstance resources remain; future allocations use Metal3

**Impact on cluster health:**
- Existing hosts allocated via NetBox remain allocated (assignment state persists in NetBox)
- New allocations use Metal3 (no interaction with NetBox)
- No data loss or consistency issues

**Impact on existing workloads:**
- Running BareMetalInstance resources unaffected; continue to function
- Deletion of BareMetalInstance instances works normally (calls Metal3 backend instead of NetBox)

**Impact on new workloads:**
- New BareMetalInstance requests allocate from Metal3, not NetBox

### Re-Enable and Recovery

To re-enable NetBox backend after disabling:

1. Verify NetBox osac_instance_id custom field exists and is properly configured; verify hardware label tags are applied to devices
2. Ensure API token Secret is present and valid
3. Update Helm values back to `inventory.type: netbox`
4. Helm upgrade; operator restarts
5. Existing BareMetalInstance resources remain unaffected; new allocations use NetBox again

**Consistency guarantee:** All state is stored durably (NetBox for allocations, Kubernetes for BareMetalInstance resources); no consistency issues on re-enable.

## Infrastructure Needed

None. NetBox is assumed to be managed by the operator (external dependency); OSAC does not provision, manage, or own NetBox infrastructure.

Testing infrastructure:
- Mock NetBox HTTP server (already built into test suite; no external infra required)
- Existing Kind cluster for integration tests (OSAC-standard osac-dev)
