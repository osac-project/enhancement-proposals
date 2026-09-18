# Test Plan — OSAC-1610: NetBox Inventory Backend

## Test Strategy Overview

The NetBox backend is a pluggable `inventory.Client` implementation within bare-metal-fulfillment-operator. Testing follows three layers:

1. **Unit tests** — Configuration parsing, label matching, idempotency logic, error handling (table-driven tests against an **in-process TLS test server**)
2. **Integration tests** — Full allocation workflow with controller-runtime **envtest** and an in-process TLS `httptest.Server`; failure recovery; lifecycle management
3. **E2E tests** — Tenant workflows against a **real, pinned NetBox container** exposed through a Kubernetes Service; allocation, provisioning, deallocation; cross-backend transparency across separate backend configurations; inventory exhaustion recovery

Go unit and envtest integration tests follow the existing
bare-metal-fulfillment-operator conventions; the E2E layer follows the
pytest-based `osac/tests/e2e` conventions in the monorepo.

## Testing Infrastructure & Patterns

### References to Existing Backend Implementations

The NetBox backend testing patterns follow the same conventions as existing inventory backends:

- **BCM Backend** (`osac/bare-metal-fulfillment-operator/internal/inventory/`):
  - `bcm.go`, `bcm_test.go`, and `bcm_mock_test.go` — inventory-client behavior,
    mock HTTP patterns, and BMC credential handling
  - `internal/controller/baremetalinstance_bcm_integration_test.go` — envtest
    reconciliation and in-process TLS-server patterns

- **Metal3 Backend** (`osac/bare-metal-fulfillment-operator/internal/inventory/`):
  - `metal3.go` and `metal3_test.go` — idempotency contract tests for
    FindFreeHost/AssignHost/UnassignHost
  - `internal/controller/baremetalinstance_metal3_integration_test.go` —
    BareMetalHost lifecycle and envtest reconciliation timing

The existing controller tests provide `reconcileN`, `getBMI`, `getBMH`, and
cleanup helpers. The NetBox tests should reuse those patterns rather than
inventing a second set of helper names.

### Test Fixtures and Provisioning

**Unit Tests:**
- Mock HTTPS server provisioned via `httptest.NewTLSServer` (standard Go testing package; no external dependencies)
- Mock Kubernetes Secrets via the controller-runtime `fake.NewClientBuilder()`
  client (test utilities)
- NetBox custom-field responses hardcoded for each test case (no external NetBox instance needed)

**Integration Tests:**
- Mock NetBox HTTPS server: `httptest.NewTLSServer` running in-process with the
  envtest operator
- Kubernetes API server and etcd: controller-runtime envtest (not a Kind
  network dependency)
- Mock NetBox custom field schema: provided by test setup; validated by client startup

**E2E Tests:**
- Real NetBox container: a pinned image for each supported 4.6.x/4.7.x matrix
  entry, exposed through a Kubernetes Service (not `localhost`)
- Kind cluster: full OSAC deployment; the operator reaches NetBox through the
  Service DNS name
- Real BareMetalInstance CRDs: created via fulfillment-service API or kubectl apply
- Metal3 BareMetalHost lifecycle: managed by operator; verified via Kubernetes API watch

The existing monorepo BMaaS suite is under `osac/tests/e2e/bmaas/`, with
allocation and exhaustion scenarios already present. The NetBox-specific
scenario should be added there, reusing `osac/tests/e2e/core/grpc_client.py`,
`k8s_client.py`, `helpers.py`, and `runner.py` rather than adding tests to the
external `osac-test-infra` checkout. The test must use the existing
`wait_for_bmi_*`, `wait_for_bmh_*`, and `poll_until` patterns and clean up all
BareMetalInstances it creates.

### Startup Validation Testing

The design requires both `inventory.type=netbox` AND `management.type=metal3` to be set. This constraint is enforced at operator startup:

- **Test location:** Unit / Configuration and Initialization section
- **Test case:** "Validate Co-Requirement: NetBox Requires Metal3 Management"
  - Setup: Operator config with `inventory.type=netbox` but `management.type` unset or non-Metal3
  - Action: Operator startup
  - Expected: Operator logs error "NetBox backend requires management.type=metal3" and exits with non-zero status

---

## Unit Tests

**Structure:** Unit tests use the existing Go package conventions (Ginkgo/Gomega
where the package uses the BMF suite, and standard `testing` where it does
not), an in-process mock HTTP/TLS server, and the controller-runtime fake
client. No external dependencies.

### Configuration and Initialization

**Test: Parse Valid NetBox Configuration**
- **Setup:** YAML config with endpoint, tokenSecret, caCertSecret (optional)
- **Action:** Call NewNetBoxClient() with valid config
- **Expected:** Client initialized; no error; endpoint stored correctly
- **URL contract:** A trailing slash is normalized so requests use exactly
  `/api/...`; an endpoint already containing `/api` is rejected rather than
  producing `/api/api/...`
- **Location:** netbox_test.go / Describe("Configuration")

**Test: Reject Missing Endpoint URL**
- **Setup:** Config with empty endpoint
- **Action:** NewNetBoxClient()
- **Expected:** Error: "endpoint required"

**Test: Load API Token from Kubernetes Secret**
- **Setup:** Mock Secret reader; Secret named "osac-netbox-api-token" with key
  "token" set to a test-local synthetic fixture value
- **Action:** Client initialization; read token
- **Expected:** Token loaded; not exposed in logs or error messages

**Test: Load CA Certificate from Optional Secret**
- **Setup:** Config with caCertSecret; Secret contains PEM-encoded cert
- **Action:** Client initialization; TLS config built
- **Expected:** CA cert added to http.Client transport; valid TLS handshake with cert-signed server

**Test: Validate Custom Field Exists in NetBox Schema**
- **Setup:** Mock HTTPS server for `GET /api/extras/custom-fields/?object_type=dcim.device&name=osac_instance_id` returns no matching field
- **Action:** Client startup calls the custom-fields endpoint and validates that the required field is defined for `dcim.device` with text type, nullable values, and exact filtering
- **Expected:** Missing or incompatible schema returns an actionable error identifying `osac_instance_id`; a compatible field allows startup to continue

**Test: TLS Validation Failure on Invalid Certificate**
- **Setup:** Table-driven cases: self-signed HTTPS endpoint without its CA,
  direct `http://` endpoint, and an HTTPS endpoint redirecting to HTTP or a
  different authority
- **Action:** Client attempts connection
- **Expected:** Invalid certificate fails with "failed to verify TLS
  certificate"; direct HTTP is rejected before a request; unsafe redirects are
  rejected and the Authorization header is not observed by the redirect target

**Test: HostSelector Resolution and NetBox Tag-Key Extraction**
- **Setup:** `BareMetalInstanceType.spec.host_label_selector.match_labels` resolves to `spec.selector.hostSelector` as {"osac-cpu-cores-16": "true", "osac-gpu-model-a100": "true", "osac-arch-x86-64": "true"}
- **Action:** Operator builds the NetBox tag filters from the resolved HostSelector
- **Expected:** Fulfillment-service copies the three key/value entries into the CRD without conversion; the NetBox request contains one `tag=` filter for each key (order is not significant), selector values are not encoded into the query, and no hardware field is consulted

**Test: NetBox Tag-Key Validation Rejects Invalid Characters**
- **Setup:** Selector key contains spaces or special characters: {"invalid tag!": "true"}
- **Action:** Operator validates the selector key
- **Expected:** Validation error before any NetBox query; BareMetalInstance status shows error message

---

### Startup Validation

**Test: Validate Co-Requirement — NetBox Requires Metal3 Management**
- **Setup:** Operator config with `inventory.type=netbox` but `management.type` not set to "metal3"
- **Action:** Operator initializes NetBox backend during startup
- **Expected:** Initialization fails with error: "NetBox backend requires management.type=metal3"; operator startup blocked; admin must fix config before retry
- **Note:** Design constraint (see [design.md](design.md#non-goals)); ensures BMH lifecycle is managed by Metal3 controller, not NetBox backend

---

### HTTP Client and Error Handling

**Test: Token Header Correctly Set**
- **Setup:** Mock HTTPS server; expects Authorization header
- **Action:** FindFreeHost() call
- **Expected:** HTTP request includes `Authorization: Token <fixture value>`;
  no plaintext token in logs

**Test: Handle 401 Unauthorized — Permanent Failure**
- **Setup:** Mock server returns 401 on device list request
- **Action:** FindFreeHost()
- **Expected:** Error returned (not retried); error message: "NetBox API authentication failed"; no token in error

**Test: Handle 403 Forbidden — Permanent Failure**
- **Setup:** Mock server returns 403 (insufficient permissions)
- **Action:** FindFreeHost()
- **Expected:** Error returned; message: "NetBox API permissions insufficient"

**Test: Handle 404 Not Found — Permanent Failure**
- **Setup:** Mock server returns 404 on invalid endpoint path
- **Action:** FindFreeHost()
- **Expected:** Error returned; message includes field/resource name; no exposure of full API response

**Test: Handle 5xx Server Error — Transient Failure with Retry**
- **Setup:** Mock server returns 500 on first two calls, 200 on third
- **Action:** FindFreeHost()
- **Expected:** Retries 3 times; eventually succeeds; no error returned

**Test: Handle Network Timeout — Transient Failure with Retry**
- **Setup:** Mock server delays response indefinitely; client timeout = 500ms
- **Action:** FindFreeHost()
- **Expected:** Timeout error; retries up to 3 times; returns error if all fail

**Test: Handle Connection Refused — Transient Failure with Retry**
- **Setup:** Endpoint unreachable
- **Action:** FindFreeHost()
- **Expected:** Connection error; retries; returns error after retries exhausted

**Test: Error Messages Never Expose Credentials**
- **Setup:** Config with a test-local synthetic fixture token
- **Action:** Trigger 401 error; capture error message and logs
- **Expected:** Error message and logs do not contain the fixture token or any
  recognizable token pattern

**Test: Handle 412 Precondition Failed — Race Loss**
- **Setup:** Mock NetBox PATCH returns 412 Precondition Failed
- **Action:** AssignHost step 3 sends PATCH with If-Match
- **Expected:** Returns (nil, nil) — treated as race loss, NOT as transient error; no automatic retry at HTTP level

**Test: Distinguish 412 from Other 4xx Errors**
- **Setup:** Mock returns 400 Bad Request vs 412 Precondition Failed
- **Action:** AssignHost PATCH
- **Expected:** 400 → permanent error (fail fast); 412 → race loss path (return nil, nil)

---

### Concurrent Access (ETag-Based)

**Test: First Writer Wins**
- **Setup:** Mock NetBox returns device with ETag: W/"2026-01-01T00:00:00.000000+00:00"
- **Action:** PATCH with If-Match: W/"2026-01-01T00:00:00..." → mock returns 200 OK with new ETag
- **Expected:** AssignHost returns (host, Ready)

**Test: Second Writer Gets 412**
- **Setup:** Mock NetBox returns device with ETag
- **Action:** PATCH with If-Match: same ETag → mock returns 412 Precondition Failed
- **Expected:** AssignHost returns (nil, nil); does NOT retry same device; caller retries FindFreeHost

**Test: Race Sequence with Goroutines**
- **Setup:** Two goroutines both call AssignHost on device-42; both capture same ETag from GET
- **Action:** First PATCH succeeds (200); second PATCH gets 412
- **Expected:** Exactly one goroutine returns (host, Ready); exactly one returns (nil, nil); device-42 has status=active and osac_instance_id set to winner's ID, not loser's

**Test: Concurrent Tag-Based FindFreeHost**
- **Setup:** 3 devices with osac-cpu-cores-16 tag; 2 tenants request the osac-cpu-cores-16 selector key simultaneously
- **Action:** Both call FindFreeHost with same tag filters
- **Expected:** Both get results from NetBox; AssignHost ETag protection prevents double-allocation

---

### FindFreeHost Label Matching and Tag-Key Construction

**Test: Tag-Key Pass-Through from Resolved HostSelector**
- **Setup:** Resolved `spec.selector.hostSelector` is {osac-cpu-cores-16: "true", osac-gpu-model-a100: "true"}
- **Action:** Operator builds the NetBox tag filters
- **Expected:** One `tag=` filter is sent for each exact key (order is not significant); values are ignored

**Test: Selector Value Is Ignored**
- **Setup:** Resolved `spec.selector.hostSelector` is {osac-gpu-model-a100: "A100"}
- **Action:** Invoke tag-filter construction again with value "H100" and the same key
- **Expected:** The query remains `tag=osac-gpu-model-a100`; values are not converted into tag names

**Test: Selector Key Is Not Rewritten**
- **Setup:** Resolved `spec.selector.hostSelector` is {osac-cpu-cores-16: "true"}
- **Action:** Operator constructs the query
- **Expected:** Exact key `osac-cpu-cores-16` is used; no prefix, case, underscore, or value transformation occurs

**Test: NetBox Tag-Key Validation Rejects Invalid Characters**
- **Setup:** Resolved `spec.selector.hostSelector` contains {"invalid tag!": "true"}
- **Action:** Operator validates the selector key
- **Expected:** Validation error before any NetBox query; BareMetalInstance status shows error

**Test: Server-Side Tag Filtering — Device with Matching Tags**
- **Setup:** Resolved HostSelector is {osac-cpu-cores-16: "true"}; NetBox device has tags [managed-by-osac, osac-cpu-cores-16]
- **Action:** FindFreeHost({osac-cpu-cores-16: "true"})
- **Expected:** Device returned; query includes tag=osac-cpu-cores-16,
  `status=staged`, and `cf_osac_instance_id__empty=true`

**Test: Server-Side Tag Filtering — Device with Wrong Tags**
- **Setup:** Resolved HostSelector is {osac-gpu-model-v100: "true"}; mock NetBox returns empty (no such-tag devices)
- **Action:** FindFreeHost({osac-gpu-model-v100: "true"})
- **Expected:** nil returned (server-side filtering; operator never receives non-matching devices)

**Test: Superset Match — Device Has Extra Tags**
- **Setup:** Resolved HostSelector is {osac-cpu-cores-16: "true"}; device has tags [osac-cpu-cores-16, osac-gpu-model-a100, osac-memory-gb-128]
- **Action:** FindFreeHost({osac-cpu-cores-16: "true"})
- **Expected:** Device matches (extra tags are fine; superset matching)

### Capacity Count

**Test: Count Returns Correct Number**
- **Setup:** Mock NetBox with 5 devices matching server-side pool filters (tag=managed-by-osac, status=staged); all have an empty `osac_instance_id`
- **Action:** Paginate the pool query and count devices after the owner check
- **Expected:** Available count is 5

**Test: Count Updates After Assignment**
- **Setup:** 5 available devices; one device assigned via AssignHost
- **Action:** Re-run the paginated capacity query
- **Expected:** "count": 4 (one fewer available)

**Test: Count with No Available Devices**
- **Setup:** All devices have status=active and osac_instance_id set (all assigned)
- **Action:** Paginate the staged pool query and apply the owner check
- **Expected:** "count": 0

---

### FindFreeHost tags and Status Filtering

**Test: Query Returns Only Staged Devices with Managed Tag**
- **Setup:** Mock HTTP response includes 10 devices; 6 with status=staged + tag managed-by-osac, 2 status=offline, 2 status=staged but wrong tag
- **Action:** FindFreeHost()
- **Expected:** Query includes server-side filters
  `tag=managed-by-osac&status=staged&cf_osac_instance_id__empty=true`; the
  adapter still skips any returned device whose `osac_instance_id` is
  non-empty, leaving only the six unassigned pool devices

**Test: No Candidates — All Devices Already Assigned**
- **Setup:** NetBox has 5 pool devices; three have status=active and a non-empty `osac_instance_id`, and two have status=staged with a stale non-empty `osac_instance_id`
- **Action:** FindFreeHost(); the mock returns the staged stale-owner rows
  despite the empty-owner filter to exercise the defensive client-side check
- **Expected:** nil returned (no error); the adapter skips all five devices,
  including the staged devices with stale owner markers, and the controller retries

**Test: No Candidates — Empty Device Pool**
- **Setup:** NetBox returns 0 devices matching pool
- **Action:** FindFreeHost()
- **Expected:** nil returned; no error

**Test: Pagination of Large Device Lists**
- **Setup:** NetBox has 250 devices; API limits response to 100 per page
- **Action:** FindFreeHost() queries all pages
- **Expected:** All 250 evaluated; pagination handled transparently; single candidate returned

---

### AssignHost Idempotency and Race Conditions

**Test: Successful Assignment**
- **Setup:** Device found unassigned; AssignHost called with instanceID "inst-123"
- **Action:** AssignHost(inventoryHostID="baremetal/netbox-device-1", bareMetalInstanceID="inst-123")
- **Expected:** Device PATCH sets status=active and osac_instance_id to "inst-123"; read-after-write confirms both; returns (host, nil)

**Test: Idempotent Retry — Same Assignment ID**
- **Setup:** Device already has status=active and osac_instance_id = "inst-123"
- **Action:** AssignHost(inventoryHostID="baremetal/netbox-device-1", bareMetalInstanceID="inst-123") called again
- **Expected:** Read returns existing assignment; matches requested ID; skips the ownership PATCH, re-ensures the BMC Secret/BMH idempotently, and returns (host, nil)

**Test: Race Condition — Device Assigned to Different Instance**
- **Setup:** Device already has status=active and osac_instance_id = "inst-999" (another instance claimed it)
- **Action:** AssignHost(inventoryHostID="baremetal/netbox-device-1", bareMetalInstanceID="inst-123")
- **Expected:** Read-then-compare detects mismatch; returns (nil, nil) — race lost

**Test: Crash Recovery — Assignment Persisted**
- **Setup:** Device has status=active and osac_instance_id = "inst-123" (from previous AssignHost call)
- **Action:** Operator crashes and restarts; reconciliation retries AssignHost with same ID
- **Expected:** Idempotent: ownership is not rewritten, BMC Secret/BMH state is re-ensured, and reconciliation proceeds without double-assignment

**Test: ETag Capture on Read**
- **Setup:** Mock GET returns device with ETag header: W/"2026-01-01T00:00:00.000000+00:00"
- **Action:** AssignHost step 1 reads device
- **Expected:** ETag value is captured and stored for use in step 3 PATCH

**Test: If-Match Sent on PATCH**
- **Setup:** AssignHost has captured ETag from step 1
- **Action:** Step 3 sends PATCH request
- **Expected:** PATCH request includes If-Match header with captured ETag value

---

### UnassignHost Idempotency

**Test: Successful Deassignment**
- **Setup:** Device has status=active and osac_instance_id = "inst-123"
- **Action:** UnassignHost(inventoryHostID="baremetal/netbox-device-1")
- **Expected:** Device PATCH sets status=staged and clears osac_instance_id; read-after-write confirms both; returns nil

**Test: Idempotent Retry — Already Unassigned**
- **Setup:** Device already has status=staged and osac_instance_id = nil (unassigned)
- **Action:** UnassignHost(inventoryHostID="baremetal/netbox-device-1") called
- **Expected:** Read returns nil; already unassigned; returns nil without PATCH

**Test: Ownership Guard — BMH Belongs to Different Instance**
- **Setup:** Device has status=active and osac_instance_id = "inst-999"; the existing BMH has `spec.consumerRef.name = "inst-888"`
- **Action:** UnassignHost(inventoryHostID="baremetal/netbox-device-1")
- **Expected:** Returns an ownership-conflict error; does not delete the BMH or BMC Secret and does not PATCH NetBox

**Test: 412 During Unassignment — Retry from Read**
- **Setup:** Mock GET returns device assigned to our instance; PATCH returns 412 Precondition Failed
- **Action:** UnassignHost step 2 sends PATCH with If-Match
- **Expected:** UnassignHost re-reads device (back to step 1) and retries; does NOT return error on first 412

---

### GetHostNICs (BMH Hardware Inspection)

**Test: GetHostNICs Delegates to BMH Hardware Data**
- **Setup:** Existing BMH has inspected hardware with NIC MAC addresses
- **Action:** GetHostNICs(inventoryHostID="baremetal/netbox-device-1")
- **Expected:** Lowercased MAC addresses are returned as `inventory.HostNIC` values; no NetBox API call is made
- **Note:** If the BMH has no hardware data yet, return `(nil, nil)` following the existing BCM manager contract

---

## Integration Tests

**Structure:** Integration tests use controller-runtime envtest (Kubernetes API
server and etcd managed by the test environment) with a **mock NetBox HTTPS
server** (`httptest.NewTLSServer`). Tests run against the real operator
reconciliation loop with the external API mocked.

**Pattern:** Follow the existing BMF controller integration tests
(`osac/bare-metal-fulfillment-operator/internal/controller/baremetalinstance_bcm_integration_test.go`
and `baremetalinstance_metal3_integration_test.go`) for envtest setup,
`DeferCleanup` patterns, reconciliation, and context usage.

### Full Allocation Workflow with Envtest

**Test: Allocate Host via BareMetalInstance**
- **Setup:** envtest API server with bare-metal-fulfillment-operator;
  **mock NetBox HTTPS server** (`httptest.NewTLSServer`); Kubernetes Secret with API token
- **Prerequisites:**
  - `osac_instance_id` custom field exists in mock NetBox schema
  - 5 devices in mock NetBox with status=staged, managed-by-osac tag, and matching pre-created capability tags
- **Action:**
  1. Through fulfillment-service, create a BareMetalInstance whose resolved `spec.selector.hostSelector` is `{osac-cpu-cores-16: "true"}`
  2. Wait for operator to reconcile
- **Expected:**
  1. BareMetalInstance spec.externalHostID set to `<metal3 namespace>/netbox-device-<id>` (the BMH/management host ID)
  2. Device in NetBox now has status=active and osac_instance_id set to BareMetalInstance UID
  3. No device is double-allocated; this is checked from the NetBox fixture
     state rather than from a Kubernetes Event

**Test: Deallocate Host via BareMetalInstance Deletion**
- **Setup:** BareMetalInstance allocated to device; host ready
- **Action:**
  1. Delete BareMetalInstance
  2. Wait for operator to reconcile
- **Expected:**
  1. Device in NetBox has osac_instance_id cleared
  2. Device status is restored to staged; host returns to available pool
  3. BareMetalInstance deleted cleanly

**Test: Host Preparation Failure Rolls Back the Claim**
- **Setup:** BareMetalInstance has claimed a staged device; the mock BMC Secret
  or BareMetalHost creation fails after the NetBox assignment PATCH
- **Action:**
  1. Reconcile the BareMetalInstance
  2. Allow the compensation path to run
  3. Repeat with a successful BMC/BMH response
- **Expected:**
  1. Only a BMH whose consumer reference matches the current instance and its
     operator-managed BMC Secret are removed
  2. NetBox is patched back to `status=staged` with an empty
     `osac_instance_id`, using `If-Match`
  3. The controller retries allocation after the failure; the next successful
     attempt can claim a device without an orphaned BMH, Secret, or owner marker
  4. If cleanup cannot be proven safe, the claim remains for retry and no other
     instance's resources are deleted

**Network Failure Recovery:**
- **Setup:** BareMetalInstance allocation is in progress; the mock NetBox server
  returns 5xx for 5 seconds
- **Action:** Wait for the adapter retry budget and controller backoff, then
  restore successful responses
- **Expected:** Allocation eventually succeeds without exposing backend-specific
  details to the tenant

**Test: Permanent Auth Failure**
- **Setup:** Operator is initialized with a token that NetBox rejects (or the
  token is revoked after startup)
- **Action:**
  1. Create BareMetalInstance
  2. Operator attempts allocation
- **Expected:**
  1. `FindFreeHost` returns a permanent authentication error and the
     reconciliation is retried by the controller's normal error backoff
  2. Operator logs: "NetBox API authentication failed"
  3. Admin sees actionable message: "Check Secret osac-netbox-api-token"
  4. `osac_netbox_api_errors_total{error_type="401"}` increments without
     exposing the token

**Test: Schema Validation Failure on Startup**
- **Setup:** NetBox mock schema missing `osac_instance_id`, or the field is
  assigned to the wrong object type or lacks the required text/nullable/exact-
  filtering shape
- **Action:**
  1. Deploy operator with NetBox config
- **Expected:**
  1. Operator logs an actionable `osac_instance_id` schema validation error
  2. Operator exits or marks readiness = false
  3. Admin must create field before operator can start

**Test: Configuration Update After Operator Restart**
- **Setup:** Operator running with one endpoint; Helm values updated with a new endpoint
- **Action:**
  1. Update the mounted inventory configuration Secret with the new endpoint URL
  2. Restart operator
  3. Create BareMetalInstance
- **Expected:**
  1. Operator picks up new endpoint
  2. Allocation queries new endpoint
  3. Succeeds if new endpoint is reachable

**Test: Concurrent Assignment with ETag Protection**
- **Setup:** Two BareMetalInstance CRs requesting same label profile; only one device matches in mock NetBox
- **Action:** Both controllers attempt AssignHost on same device
- **Expected:** Exactly one gets 200 OK; the other gets 412 Precondition Failed and retries FindFreeHost; no device is double-assigned

**Test: Capacity Metrics Endpoint**
- **Setup:** envtest operator running; mock NetBox with 10 staged devices
- **Action:** Scrape operator's /metrics endpoint
- **Expected:** osac_netbox_hosts_available gauge shows 10; after one assignment, gauge shows 9

**Test: Server-Side Tag Filtering Verification**
- **Setup:** envtest operator; mock NetBox with 10 devices: 5 have osac-gpu-model-a100, 5 have osac-gpu-model-v100
- **Action:** The resolved `spec.selector.hostSelector` contains `{osac-gpu-model-a100: "true"}`
- **Expected:** FindFreeHost query includes tag=osac-gpu-model-a100,
  `status=staged`, and `cf_osac_instance_id__empty=true`; NetBox returns only
  5 matching; operator does NOT receive V100 devices

**Test: Tag Mismatch — Zero Results**
- **Setup:** Mock NetBox devices have osac-gpu-model-a100
- **Action:** The resolved `spec.selector.hostSelector` contains `{osac-gpu-model-h100: "true"}`
- **Expected:** FindFreeHost query includes tag=osac-gpu-model-h100,
  `status=staged`, and `cf_osac_instance_id__empty=true`; NetBox returns empty
  list; operator requeues with "No hosts available"

**Test: Tag Update on Device**
- **Setup:** Device has tag osac-memory-gb-64
- **Action:** Admin removes osac-memory-gb-64 and adds osac-memory-gb-128; the `BareMetalInstanceType` used by subsequent requests is updated accordingly (an existing BareMetalInstance selector is immutable)
- **Expected:** A request with key osac-memory-gb-64 no longer returns this device; a request with key osac-memory-gb-128 now returns it

**Test: Cross-Backend Non-Regression**
- **Setup:** Test cluster configured with Metal3 backend; deploy second cluster with NetBox backend
- **Action:**
  1. Create BareMetalInstance in Metal3 cluster
  2. Create BareMetalInstance in NetBox cluster
  3. Verify both allocate successfully
- **Expected:**
  1. Metal3 cluster: allocation uses Metal3 BareMetalHost
  2. NetBox cluster: allocation uses NetBox devices
  3. No cross-contamination

---

## E2E Tests (osac/tests/e2e)

**Structure:** E2E tests run against a **pinned real NetBox container** and a
real Kind cluster with all OSAC components deployed (fulfillment-service,
operator, Metal3). NetBox is exposed through a Kubernetes Service and the
operator uses its Service DNS address, never `localhost`. Tests follow pytest
patterns in `osac/tests/e2e`.

**Prerequisites:** Real NetBox container and PostgreSQL/Redis dependencies
available through the test stack; NetBox Service reachable from the Kind
cluster; Keycloak for API auth; fulfillment-service API running.

**Reference:** Add the NetBox BMaaS scenario under
`osac/tests/e2e/bmaas/`, alongside the existing lifecycle and inventory
exhaustion tests. The closest existing references are
`osac/tests/e2e/bmaas/conftest.py`,
`osac/tests/e2e/bmaas/sanity/test_baremetal_instance_lifecycle.py`, and
`osac/tests/e2e/bmaas/serial/test_baremetal_instance_inventory_exhausted.py`.
Reuse the monorepo's gRPC client, Kubernetes client, namespace, and polling
fixtures; the external `osac-test-infra` repository owns infrastructure
backends, not test suites.

### Tenant Workflow Transparency

**Test: Allocate and Provision Host Against NetBox**
- **Setup:** Real NetBox instance is reachable at its in-cluster Service DNS
  address; use the existing BMaaS catalog-item fixture and a
  BareMetalInstanceType that resolves to a `host_label_selector`
- **Action:**
  1. Create the BareMetalInstance through the existing BMaaS CLI/gRPC fixture,
     referencing that catalog item/instance type
  2. Operator allocates from NetBox
  3. Metal3 BareMetalHost created; power on / inspection / provisioning proceeds
  4. Use the existing `wait_for_bmi_running` and
     `wait_for_bmh_provisioned` helpers
- **Expected:**
  1. The fulfillment API reports
     `BARE_METAL_INSTANCE_STATE_RUNNING` and the CR has
     `HostConditionAllocated=True`
  2. The corresponding BareMetalHost reaches the provisioned/readiness state
     used by the existing Metal3 workflow
  3. Tenant sees no backend-specific details (NetBox transparent)
- **Verification: Tag Preservation After Provisioning**
  - After provisioning succeeds, verify:
    - Device in NetBox still has all original administrator-managed capability tags (osac-cpu-cores-16, etc.) — assignment does not remove them
    - Device has status=active and osac_instance_id set (custom field identifies the owner; status identifies allocation state)
    - The managed-by-osac tag is still present

**Test: Deallocate and Reuse Host**
- **Setup:** Host allocated and provisioned from NetBox pool
- **Action:**
  1. Delete BareMetalInstance
  2. Wait for cleanup
  3. Create new BareMetalInstance with same label selectors
- **Expected:**
  1. Host deallocated cleanly (power off, BMH deleted)
  2. Device status restored to staged; host returned to NetBox available pool
  3. New request allocates same or different host
  4. No orphaned state

**Test: Label Selector Matching in Tenant Workflow**
- **Setup:** NetBox has pools: [16-core nodes] and [8-core nodes]
- **Action:**
  1. The resolved `spec.selector.hostSelector` is `{osac-cpu-cores-16: "true"}`
  2. Request processed; allocation searches NetBox
  3. Verify allocation matched correctly
- **Expected:**
  1. Host allocated from 16-core pool
  2. 8-core nodes not allocated
  3. Tenant sees successful allocation

### Inventory Exhaustion Edge Case

**Test: Allocate, Exhaust, Recover (Inventory Overflow Handling)**
- **Setup:** Kind cluster with N available devices; observe initial count
- **Action:**
  1. Create N BareMetalInstance objects (consume all inventory)
  2. Wait for all to reach Ready
  3. Create BMI N+1 (overflow; no devices left)
  4. Assert N+1 does not reach Ready (stalls in allocation)
  5. Delete one allocated BMI to free a device
  6. Assert N+1 recovers to Ready
- **Expected:**
  1. N succeed; N+1 stalls (no available NetBox devices)
  2. N+1 requeues internally; does not create zombie BMH
  3. After device freed: N+1 eventually reaches Ready
  4. No corruption; all allocations idempotent

**Test: Tag-Based Concurrent Stress**
- **Setup:** Real NetBox with 50 devices tagged osac-cpu-cores-16; 20 concurrent tenants all requesting the osac-cpu-cores-16 selector key
- **Action:** All 20 reconcile loops fire concurrently
- **Expected:** Exactly 20 devices assigned (one per tenant); 30 remain available; no double-allocations (verified by ETag 412 handling); no orphaned assignments

### Observability and Diagnostics

**Test: Prometheus Metrics — Same-Host Race Detection**
- **Setup:** Operator running; Prometheus scraping; real NetBox with 1 device available
- **Action:**
  1. Coordinate two concurrent AssignHost calls for the same device
  2. First call gets device with ETag_v1; second call also gets ETag_v1
  3. First PATCH succeeds (ETag_v1 matches); second PATCH fails with 412
- **Expected:**
  1. `osac_netbox_assignment_attempts_total{result="success"}` incremented for first
  2. `osac_netbox_assignment_attempts_total{result="race"}` incremented for second
  3. No device is double-allocated

**Test: Prometheus Metrics — No-Host Exhaustion**
- **Setup:** Operator running; real NetBox with 8 available devices
- **Action:**
  1. Create 10 concurrent BareMetalInstance objects requesting same label profile
  2. 8 succeed (allocated)
  3. 2 observe no matching hosts (FindFreeHost returns nil, nil)
- **Expected:**
  1. `osac_netbox_hosts_available{host_class="netbox"}` gauge:
     - Initial: 8 (8 staged devices with an empty osac_instance_id and managed-by-osac tag)
     - After 8 assignments: 0 (no remaining available)
  2. `osac_netbox_assignment_attempts_total{result="success"}` = 8
  3. No `osac_netbox_assignment_attempts_total{result="success"}` increment
     occurs for the two requests that never reach AssignHost
  4. NOTE: The availability gauge reflects pool-wide availability, while a
     no-match reconciliation is reported through the BareMetalInstance
     condition and requeue interval rather than an assignment-attempt result

**Test: Inventory Exhaustion — Indefinite Retry with Condition**
- **Setup:** 10 BareMetalInstance objects with no matching devices in NetBox
- **Action:**
  1. Create 10 BareMetalInstance CRs requesting non-existent label profile
  2. Wait for first reconciliation cycle
  3. Observe BareMetalInstance status
  4. Add matching devices to NetBox
  5. Wait for next reconciliation
- **Expected:**
  1. Initial: All 10 instances have `phase=Failed`, condition `HostConditionAllocated=False` with `reason=NoMatchingHosts`
  2. No Kubernetes Event is required; the existing status condition is the
     contract for this path
  3. Controller continues retrying at `NoFreeHostsPollIntervalDuration` (default 30s)
  4. After capacity is added: Next reconciliation succeeds; instances move to
     the existing allocation phase
  5. The tenant-facing status/message remains the generic "No hosts available"
     contract and does not mention NetBox
  6. Metrics show successful assignment attempts only after capacity is available

**Test: Allocation Condition and Requeue on No Matching Hosts**
- **Setup:** BareMetalInstance allocating with no matching NetBox devices
- **Action:**
  1. Observe the BareMetalInstance status and reconcile result
- **Expected:**
  1. `phase=Failed` and `HostConditionAllocated=False` with reason
     `NoMatchingHosts`
  2. Reconcile returns `NoFreeHostsPollIntervalDuration`
  3. After a matching device is added, the next reconciliation allocates it

**Test: Structured Logs**
- **Setup:** Operator running; logs captured
- **Action:**
  1. Create allocation
  2. Grep logs for relevant entries
- **Expected:**
  1. Logs include:
     - `host_selector_key_count`: number of resolved selector keys
     - `query_tag_count`: number of tags sent to NetBox
     - `matching_devices_count`: count of devices returned by NetBox matching the server-side pool/tag filters
     - `host_selected`: boolean result of candidate selection
  2. Selector values, raw tag slugs, host IDs, BareMetalInstance UIDs, tenant
     names, credentials, and secrets are absent from logs
  3. Error logs include diagnostic info (e.g., "custom_field not found") but no API responses

---

## Test Coverage Summary

| Layer | Component | Count | Test Scenarios | Coverage |
|-------|-----------|-------|--------|----------|
| **Unit** | Config parsing | **8** | 8 scenarios | Endpoint validation, Secret loading, TLS cert, schema validation, **tag-key extraction, validation** |
| **Unit** | Startup validation | **1** | 1 scenario | NetBox+Metal3 co-requirement constraint |
| **Unit** | HTTP client | **10** | 10 scenarios | Auth headers, error codes (401/403/404/5xx), timeouts, **412 vs 400 distinction**, credential safety |
| **Unit** | FindFreeHost label matching | **7** | 7 scenarios | **Exact tag-key pass-through, ignored values, validation, server-side filtering, superset match** |
| **Unit** | Capacity count | **3** | 3 scenarios | **Count correct number, count after assignment, zero devices** |
| **Unit** | FindFreeHost filtering | **4** | 4 scenarios | Tag and status filtering, no candidates, pagination |
| **Unit** | Concurrent Access (ETag-Based) | **4** | 4 scenarios | **First writer wins, second writer 412, race sequence, concurrent tag filtering** |
| **Unit** | AssignHost | **6** | 6 scenarios | Success, idempotency, race condition, crash recovery, **ETag capture, If-Match header** |
| **Unit** | UnassignHost | **4** | 4 scenarios | Success, idempotency (same ID), idempotency (different ID), **412 retry handling** |
| **Unit** | GetHostNICs | **1** | 1 scenario | Delegates to BMH hardware data; returns `(nil, nil)` only before inspection |
| | **UNIT TOTAL** | **48** | **48 tests** | |
| **Integration** | Allocation workflow | **6** | 6 scenarios | Allocate via BareMetalInstance, deallocate via deletion, host-preparation rollback, permanent auth failure, schema validation, config reload |
| **Integration** | ETag/Concurrent | **1** | 1 scenario | **Concurrent assignment with ETag protection** |
| **Integration** | Capacity metrics | **1** | 1 scenario | **Metrics endpoint scrape, gauge validation** |
| **Integration** | Tag filtering | **3** | 3 scenarios | **Server-side filtering, tag mismatch, tag lifecycle** |
| **Integration** | Cross-backend | **1** | 1 scenario | Metal3 and NetBox configurations pass separately without cross-backend regressions |
| | **INTEGRATION TOTAL** | **12** | **12 tests** | |
| **E2E** | Tenant workflow | **3** | 3 scenarios | Allocate and provision (**+ preservation of administrator-managed tags**), deallocate and reuse, tag-key matching |
| **E2E** | Inventory exhaustion | **1** | 1 scenario | Overflow handling and recovery |
| **E2E** | Stress test | **2** | 2 scenarios | Generic stress (20 requests against 10 hosts), tag-based concurrent stress (20 requests against 50 hosts) |
| **E2E** | Observability | **4** | 4 scenarios | Prometheus metrics (same-host race + no-host exhaustion), allocation condition/requeue, structured logs |
| | **E2E TOTAL** | **10** | **10 tests** | |
| | | | | |
| | **GRAND TOTAL** | **70** | **70 test scenarios** | **48 Unit + 12 Integration + 10 E2E** |

**Planned Coverage:**
- **Unit scenarios:** 48
- **Integration scenarios:** 12
- **E2E scenarios:** 10
- **Total planned scenarios:** 70 (48 Unit + 12 Integration + 10 E2E)

---

## Test Case Reference (TC-IDs)

Each test is identified by a TC-ID for traceability in Jira subtasks and CI logs. Format: `TC-LAYER-NNN` (LAYER = UNIT/INT/E2E).

### Unit Tests (48 tests: TC-UNIT-001 to TC-UNIT-048)

**Configuration and Initialization (TC-UNIT-001 to TC-UNIT-008):**
- TC-UNIT-001: Parse Valid NetBox Configuration
- TC-UNIT-002: Reject Missing Endpoint URL
- TC-UNIT-003: Load API Token from Kubernetes Secret
- TC-UNIT-004: Load CA Certificate from Optional Secret
- TC-UNIT-005: Validate Required Custom Field Schema
- TC-UNIT-006: TLS Validation Failure on Invalid Certificate
- TC-UNIT-007: HostSelector Resolution and NetBox Tag-Key Extraction
- TC-UNIT-008: NetBox Tag-Key Validation Rejects Invalid Characters

**Startup Validation (TC-UNIT-009):**
- TC-UNIT-009: Validate Co-Requirement — NetBox Requires Metal3 Management

**HTTP Client and Error Handling (TC-UNIT-010 to TC-UNIT-019):**
- TC-UNIT-010: Token Header Correctly Set
- TC-UNIT-011: Handle 401 Unauthorized — Permanent Failure
- TC-UNIT-012: Handle 403 Forbidden — Permanent Failure
- TC-UNIT-013: Handle 404 Not Found — Permanent Failure
- TC-UNIT-014: Handle 5xx Server Error — Transient Failure with Retry
- TC-UNIT-015: Handle Network Timeout — Transient Failure with Retry
- TC-UNIT-016: Handle Connection Refused — Transient Failure with Retry
- TC-UNIT-017: Error Messages Never Expose Credentials
- TC-UNIT-018: Handle 412 Precondition Failed — Race Loss
- TC-UNIT-019: Distinguish 412 from Other 4xx Errors

**Concurrent Access — ETag-Based (TC-UNIT-020 to TC-UNIT-023):**
- TC-UNIT-020: First Writer Wins
- TC-UNIT-021: Second Writer Gets 412
- TC-UNIT-022: Race Sequence with Goroutines
- TC-UNIT-023: Concurrent Tag-Based FindFreeHost

**FindFreeHost Label Matching and Tag-Key Construction (TC-UNIT-024 to TC-UNIT-030):**
- TC-UNIT-024: Tag-Key Pass-Through from Resolved HostSelector
- TC-UNIT-025: Selector Value Is Ignored
- TC-UNIT-026: Selector Key Is Not Rewritten
- TC-UNIT-027: NetBox Tag-Key Validation Rejects Invalid Characters
- TC-UNIT-028: Server-Side Tag Filtering — Device with Matching Tags
- TC-UNIT-029: Server-Side Tag Filtering — Device with Wrong Tags
- TC-UNIT-030: Superset Match — Device Has Extra Tags

**Capacity Count Query (TC-UNIT-031 to TC-UNIT-033):**
- TC-UNIT-031: Count Returns Correct Number
- TC-UNIT-032: Count Updates After Assignment
- TC-UNIT-033: Count with No Available Devices

**FindFreeHost Tags and Status Filtering (TC-UNIT-034 to TC-UNIT-037):**
- TC-UNIT-034: Query Returns Only Staged Devices with Managed Tag
- TC-UNIT-035: No Candidates — All Staged Devices Already Assigned
- TC-UNIT-036: No Candidates — Empty Device Pool
- TC-UNIT-037: Pagination of Large Device Lists

**AssignHost Idempotency and Race Conditions (TC-UNIT-038 to TC-UNIT-043):**
- TC-UNIT-038: Successful Assignment
- TC-UNIT-039: Idempotent Retry — Same Assignment ID
- TC-UNIT-040: Race Condition — Device Assigned to Different Instance
- TC-UNIT-041: Crash Recovery — Assignment Persisted
- TC-UNIT-042: ETag Capture on Read
- TC-UNIT-043: If-Match Sent on PATCH

**UnassignHost Idempotency (TC-UNIT-044 to TC-UNIT-047):**
- TC-UNIT-044: Successful Deassignment
- TC-UNIT-045: Idempotent Retry — Already Unassigned
- TC-UNIT-046: Ownership Guard — BMH Belongs to Different Instance
- TC-UNIT-047: 412 During Unassignment — Retry from Read

**GetHostNICs (TC-UNIT-048):**
- TC-UNIT-048: GetHostNICs Delegates to BMH Hardware Data

### Integration Tests (12 tests: TC-INT-001 to TC-INT-012)

**Full Allocation Workflow with Envtest (TC-INT-001 to TC-INT-006):**
- TC-INT-001: Allocate Host via BareMetalInstance
- TC-INT-002: Deallocate Host via BareMetalInstance Deletion
- TC-INT-003: Host Preparation Failure Rolls Back the Claim
- TC-INT-004: Permanent Auth Failure
- TC-INT-005: Schema Validation Failure on Startup
- TC-INT-006: Configuration Update After Operator Restart

**Concurrent Assignment with ETag Protection (TC-INT-007):**
- TC-INT-007: Concurrent Assignment with ETag Protection

**Capacity Metrics Endpoint (TC-INT-008):**
- TC-INT-008: Capacity Metrics Endpoint

**Server-Side Tag Filtering (TC-INT-009 to TC-INT-011):**
- TC-INT-009: Server-Side Tag Filtering Verification
- TC-INT-010: Tag Mismatch — Zero Results
- TC-INT-011: Tag Update on Device

**Cross-Backend (TC-INT-012):**
- TC-INT-012: Cross-Backend Non-Regression

### E2E Tests (10 tests: TC-E2E-001 to TC-E2E-010)

**Tenant Workflow Transparency (TC-E2E-001 to TC-E2E-003):**
- TC-E2E-001: Allocate and Provision Host Against NetBox
- TC-E2E-002: Deallocate and Reuse Host
- TC-E2E-003: Label Selector Matching in Tenant Workflow

**Inventory Exhaustion (TC-E2E-004):**
- TC-E2E-004: Allocate, Exhaust, Recover (Inventory Overflow Handling)

**Stress Tests (TC-E2E-005 to TC-E2E-006):**
- TC-E2E-005: Tag-Based Concurrent Stress
- TC-E2E-006: Prometheus Metrics — Same-Host Race Detection

**Observability and Diagnostics (TC-E2E-007 to TC-E2E-010):**
- TC-E2E-007: Prometheus Metrics — No-Host Exhaustion
- TC-E2E-008: Inventory Exhaustion — Indefinite Retry with Condition
- TC-E2E-009: Allocation Condition and Requeue on No Matching Hosts
- TC-E2E-010: Structured Logs

---

## BMC/BMH Lifecycle Test Coverage

The NetBox adapter coordinates with the existing BMH lifecycle manager; it does not implement Metal3 power control, inspection, OS provisioning, or readiness transitions itself:

- **BMC metadata extraction:** Assignment reads the exact NetBox custom fields `osac_bmc_username`, `osac_bmc_password`, `osac_bmc_address`, and `osac_boot_mac`. TC-INT-001 verifies that valid metadata reaches the full allocation path; missing or malformed fields are covered by the assignment error cases.
- **BMC Secret creation:** The adapter calls the existing manager to create/ensure a namespace-scoped, operator-managed Secret. TC-INT-001 verifies the Secret and its ownership label; TC-INT-002 verifies it is deleted during deallocation.
- **BMH lifecycle:** The adapter passes the BMC address, Secret name, boot MAC, and BareMetalInstance consumer reference to the existing manager. TC-INT-001, TC-INT-002, and TC-INT-003 verify idempotent create, cleanup ordering, preparation rollback, and retry behavior while Metal3 remains responsible for provisioning and readiness. TC-UNIT-048 verifies that post-inspection NIC data is read through the same manager.

---

## Success Criteria

All **70 planned test scenarios** must pass before OSAC-1610 is considered complete:

| # | Criterion | Test Count | Test IDs | Status |
|---|-----------|-----------|----------|--------|
| 1 | All unit tests pass | **48 tests** | TC-UNIT-001 to TC-UNIT-048 | Target |
| 2 | All integration tests pass | **12 tests** | TC-INT-001 to TC-INT-012 | Target |
| 3 | All E2E tests pass | **10 tests** | TC-E2E-001 to TC-E2E-010 | Target |
| 4 | Server-side tag filtering tested | **10 tests** | TC-UNIT-024 to TC-UNIT-030, TC-INT-009 to TC-INT-011 | Target |
| 5 | ETag/412 race protection validated | **9 tests** | TC-UNIT-018 to TC-UNIT-023, TC-UNIT-042 to TC-UNIT-043, TC-INT-007 | Target |
| 6 | Capacity counting validated | **4 tests** | TC-UNIT-031 to TC-UNIT-033, TC-INT-008 | Target |
| 7 | No double-allocations under concurrency | **3 tests** | TC-UNIT-040, TC-INT-007, TC-E2E-005 | Target |
| 8 | No credential exposure in logs | **2 tests** | TC-UNIT-017, TC-E2E-010 | Target |
| 9 | Prometheus metrics working | **4 tests** | TC-INT-004, TC-INT-008, TC-E2E-006, TC-E2E-007 | Target |
| 10 | Cross-backend non-regression | **1 test** | TC-INT-012 | Target |
| 11 | Startup validation enforced | **1 test** | TC-UNIT-009 | Target |
| 12 | Idempotency verified (crash recovery, ETag retries) | **9 tests** | TC-UNIT-038 to TC-UNIT-039, TC-UNIT-041, TC-UNIT-044 to TC-UNIT-047, TC-INT-003, TC-E2E-002 | Target |
| 13 | Tenant workflow transparency | **3 tests** | TC-E2E-001 to TC-E2E-003 | Target |
| 14 | Inventory exhaustion behavior documented | **2 tests** | TC-E2E-004, TC-E2E-008 | Target |
| 15 | Observability & diagnostics | **2 tests** | TC-E2E-009, TC-E2E-010 | Target |

The counts above are planned coverage targets. They are not pass-rate claims
until the implementation and CI tests exist.
