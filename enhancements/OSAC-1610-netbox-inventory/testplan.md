# Test Plan — OSAC-1610: NetBox Inventory Backend

## Test Strategy Overview

The NetBox backend is a pluggable `inventory.Client` implementation within bare-metal-fulfillment-operator. Testing follows three layers:

1. **Unit tests** — Configuration parsing, custom-field schema discovery, typed selector matching, idempotency logic, error handling (table-driven tests against an **in-process TLS test server**)
2. **Integration tests** — Full allocation workflow with controller-runtime **envtest** and an in-process TLS `httptest.Server`; failure recovery; lifecycle management; a separate **real NetBox Community API** suite verifies filtering, schema, values, and concurrent updates
3. **E2E tests** — Tenant workflows against a **real, pinned NetBox container** exposed through a Kubernetes Service; allocation, provisioning, deallocation; cross-backend transparency across separate backend configurations; inventory exhaustion recovery

Go unit and envtest integration tests follow the existing
bare-metal-fulfillment-operator conventions; the E2E layer follows the
pytest-based `osac/tests/e2e` conventions in the monorepo.
TC-UNIT-057 belongs to fulfillment-service and follows that package's existing
reconciler unit-test conventions.

Scenario headings carry stable `TC-LAYER-NNN` IDs. The Setup/Action/Expected
format below specifies preconditions, steps, and observable results; table
rows within a scenario are parameter cases, not additional scenario IDs.

### Selection Contract and Shared Fixtures

Administrators pre-create separate custom fields on `dcim.device`; OSAC does
not create schema or derive capabilities from hardware metadata. Use these
fixtures unless a scenario explicitly changes them:

| Field | Schema / fixture value | Responsibility |
|-------|------------------------|----------------|
| `osac_managed` | Optional Boolean (`required=false`), default `false`, exact filtering; eligible devices explicitly set JSON `true` | Cloud Infrastructure Admin controls pool membership |
| `osac_instance_id` | Optional text, no nonempty default, exact filtering; missing, `null`, or `""` denotes no owner | OSAC claims and clears the owner |
| `osac_bmc_address`, `osac_boot_mac` | Pre-created text fields containing valid BMC and boot data | Provider/platform admin supplies the connection metadata |
| `cpu_cores`, `memory_gb` | Integer, exact filtering; JSON `16`, `128` | Administrator supplies capabilities |
| `gpu_model` | Text, exact filtering; `"a100"` | Administrator supplies capabilities |

For every fixture device, provider setup also creates a system-scoped OSAC
Secret through the Secret API with the BMC username/password and the label
`osac.openshift.io/netbox-device-<device-id>: "true"`. A single Secret may
carry labels for multiple fixture devices. Tests use redacted Secret API
fixtures; credentials never appear in NetBox fixtures, request logs, or
assertions. The adapter lists Secrets by the constructed device-label key and
requires exactly one match.

Initial projection copies `{"cpu_cores":"16","gpu_model":"a100",
"memory_gb":"128"}` unchanged into the immutable BMI selector. The current
fulfillment CreateOrPatch path re-resolves the catalog, so administrators
must keep referenced selector sources unchanged and create new catalog types
for different selectors. TC-UNIT-057 tests projection under that prerequisite
separately from BMF envtest; it does not promise stability after editing or
deleting/recreating a referenced catalog identity. Query construction only
adds `cf_` to each exact capability field name:

```text
GET /api/dcim/devices/?cf_osac_managed=true&status=staged&cf_osac_instance_id__empty=true&cf_cpu_cores=16&cf_gpu_model=a100&cf_memory_gb=128
```

NetBox must AND distinct fields. Each returned candidate must also pass local
checks for Boolean pool `true`, native `status.value=staged`, empty owner, and
every requested typed capability. Missing/null capabilities and mismatched
data do not match; extra fields and unrelated tags are allowed. `active`
plus the same owner continues the existing assignment retry lifecycle.

Startup validates the fixed integration schema. Each `FindFreeHost` revalidates
pool/owner definitions and refreshes the requested capability schema through paginated
`GET /api/extras/custom-fields/?object_type=dcim.device` discovery before
listing devices. Capabilities added after startup must work without a restart
or a hardcoded name whitelist. Missing, unsupported, wrong-model, disabled,
or non-exact schema is a configuration error before any device-list request,
not empty capacity; invalid selector values are errors at the same boundary.

Supported capability types are scalar `text`, `integer`, `boolean`, and
`select` with `filter_logic=exact`. Integer selectors use canonical signed
decimal strings within int64 (`0` or optional `-` followed by a nonzero digit
and digits); booleans use only `true`/`false`; text and select values are
nonempty, have no leading/trailing whitespace, and reject the exact string
`"null"` because NetBox interprets it as the missing/null sentinel. Accepted
values are preserved exactly without trimming or changing case. Select
matching uses the stored choice value: a plain string in Community 4.6.10
and the string `value` member of a `{value,label}` object in 4.7.1. The
display label is ignored and no value transformation is allowed. JSON,
multiselect, object, date, and all other types are unsupported; arbitrary
capability values can use text fields.

Field names match `^[A-Za-z0-9_]{1,50}$`, cannot contain `__`, and cannot start
with the query prefix `cf_`. The six system keys in the first three fixture
rows are reserved and cannot be capability selectors. Keys are never
rewritten and values never discarded. Admin-only pool/capability management
is an integration responsibility: OSAC may read those values, but must never
change them. Claim/release sends partial PATCH bodies containing only
native status and owner; unrelated fields and tags survive.

### Allocation Context and Ownership Contract

The internal `inventory.Client` interface is extended: AssignHost and
UnassignHost receive `AllocationContext` in addition to their existing host
ID and separate assignment-label map / release-label list. All scenarios use
this context unless testing invalid or mismatched identity:

The OSAC API names `host_label_selector.match_labels` remain unchanged, but
their entries name NetBox custom fields and required values. The separate
assignment/release `labels` parameters are existing inventory metadata, not
custom-field selectors, writes, or deletion requests.

| Context field | Fixture / assertion |
|---------------|---------------------|
| `InstanceID` | BMI Kubernetes UID, e.g. `inst-123`; never a catalog ID or a label-derived identity |
| `InstanceName`, `InstanceNamespace` | Current requesting BMI's Kubernetes name/namespace |
| `CleanupState` | Controller-owned `osac.openshift.io/inventory-cleanup`; empty for assignment, `releasing` or `compensating` before cleanup, and the corresponding `*-ready` after resource absence is persisted |
| `HostSelector` | Snapshot copied from the persisted BMI spec; distinct from assignment labels |
| `ResourceAnnotations` | Controller copies trusted BMI `osac.openshift.io/tenant` and derives `osac.openshift.io/owner-reference` from the BMI Kubernetes UID |

New claims refresh schema and validate the context's selector, Boolean pool,
staged status, and empty owner against a fresh device-detail GET, then PATCH
under that GET's ETag. A changed candidate returns no host so the controller
reselects; invalid schema returns an error. Same-owner recovery bypasses later
pool/capability changes and continues ensuring its existing BMH/Secret, unless
persisted cleanup requires continuing UnassignHost instead.

Release requires the requesting UID to match the NetBox owner and, when
present, the BMH `ConsumerRef.UID` and operator-managed Secret's owner UID.
Ownership and absence checks use direct, uncached Kubernetes API reads;
matching names or informer-cache absence alone are insufficient. Deletion is asynchronous: keep the
Secret and NetBox claim while BMH deletion is pending, then delete the owned
Secret and wait until absent, persist the corresponding `*-ready` checkpoint,
then re-read NetBox, revalidate its owner, and conditionally release using the
fresh ETag. A captured candidate is not proof
of ownership. Trusted annotations go only to per-host Kubernetes resources,
never NetBox. Existing backends consume `InstanceID` and ignore the new
NetBox selector context without changing their behavior.

Unless testing checkpoint validation, release fixtures enter with `releasing`
and the controller harness persists `releasing-ready` when the adapter returns
typed `CleanupCheckpointRequired`; standalone adapter tests supply that saved
state on the next call. Post-claim preparation failures return typed
`PreparationFailed`; persist `compensating` before calling UnassignHost and
never re-enter resource creation while cleanup is pending. Both annotations
are preserved by fulfillment projection. A checkpoint write failure permits
no subsequent destructive step. After a completed release followed by another
claim, a saved `*-ready` checkpoint permits no-op completion only if direct
reads prove no resource at the bound names is still owned by the old UID;
clearly foreign-owned replacements remain untouched. Missing checkpoints,
ownerless/inconsistent resources, or old-UID resources fail closed. TC-INT-030
tests this narrow exception to the ordinary foreign-owner guard.

Only read-only NetBox GET requests retry transient transport/5xx failures
up to the bounded retry budget. A conditional PATCH with an uncertain outcome
returns an error without blind replay: retain ExternalHostID for claims and
the inventory finalizer for release. The next reconciliation reads current
state to determine whether the write committed. Direct 412 responses retain
method-specific ownership checks: after a new-claim 412, GET current ownership
before deciding whether to reselect. Active/same UID resumes BMH/Secret
ensures; another UID or a clearly unassigned device permits `(nil, nil)`;
a failed read or inconsistent state returns an error preserving ExternalHostID.
This GET resolves a failed PATCH's ownership outcome, including a delayed
earlier commit; it is not redundant verification of a successful PATCH.

### Device ID and Durable Identity

Default fixtures use NetBox device ID `42` and BMH namespace `baremetal`. The
device name may be `worker-01`, empty, or null; it does not affect the mapping:

| Field | Expected value |
|---|---|
| `Host.InventoryHostID` / BMI `spec.externalHostID` | `baremetal/netbox-42` |
| `Host.Name` / BMH `metadata.name` | `netbox-42` |
| BMI `spec.externalHostName` | empty/unset |
| BMC Secret | `netbox-42-bmc-secret` |
| NetBox REST path | `/api/dcim/devices/42/` |

The `netbox-` prefix is alphabetic and the result is validated with the
centralized Kubernetes `IsDNS1035Label` helper. The final name is lowercase,
uses only letters/digits/hyphens, starts with a letter, and ends with a letter
or digit. Positive canonical decimal IDs are required; zero, negative,
leading-zero, nonnumeric, and overflowing values fail before any claim or
Kubernetes write. The positive int64 range keeps the result below 63
characters.

The adapter does not query, normalize, or validate `device.name`, site, or
region for identity. NetBox IDs are unique within the configured endpoint, so
no full-inventory name scan or duplicate-name rejection is needed. A foreign
BMH or Secret with the derived name is never adopted. A change to `device.name`
does not change the host identity; a 404 for device `42` retains the binding
and finalizer and never falls back to a replacement device with the old name.

The controller persists only `externalHostID` before calling `AssignHost`. It
does not persist `BackendID`, `osac.openshift.io/inventory-device-id`, or
`externalHostName` for this backend. All detail/claim/release requests parse
the numeric ID from the saved ID-derived host name; errors and uncertain writes
retain that binding, while confirmed reselection clears it.

NetBox inventory returns `HostClass=metal3`; the existing provisioning role
uses the namespace-qualified `externalHostID` for BMH lookup. Both AAP network
playbooks use the same ID-derived name because `externalHostName` is empty and
their existing fallback takes the final segment of `externalHostID`. A
hostname-based fabric must register `netbox-42`; DHCP still prefers the
inspected NIC MAC and uses this value only for its existing name fallback.

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
- Mock NetBox custom-field schema: fixed fields validated at startup;
  requested capability metadata refreshed per `FindFreeHost`
- Real Community API contract suite: real NetBox plus PostgreSQL/Redis and a
  trusted HTTPS endpoint; exercise the adapter directly with a fake Kubernetes
  client or envtest for BMH/Secret calls. NetBox filtering and conditional
  PATCH responses must not be mocked. Capture requests at a forwarding proxy
  or the server access log without recording credentials.

**E2E Tests:**
- Real NetBox Community container: initial matrix is **4.6.10** and **4.7.1**,
  with immutable image digests recorded by the test fixture and corresponding
  upstream source tags, exposed through a Kubernetes Service (not `localhost`).
  Record digest, source revision, and `API-Version` in test artifacts. The
  source audit establishes the planned compatibility contract; it is not
  evidence that these runtime tests have passed.
- Kind cluster: full OSAC deployment; the operator reaches NetBox through the
  Service DNS name
- Real BareMetalInstance CRDs: created via fulfillment-service API or kubectl apply
- Metal3 BareMetalHost lifecycle: managed by operator; verified via Kubernetes API watch
- Race/polling scenarios TC-E2E-006, TC-E2E-008 and TC-E2E-009 use a test-only
  HTTPS forwarding proxy as the configured NetBox endpoint. It forwards to
  real NetBox, exposes count/barrier controls to pytest, and records no
  credentials, bodies, or raw query strings. No production debug hook is needed.

The existing monorepo BMaaS suite is under `osac/tests/e2e/bmaas/`, with
allocation and exhaustion scenarios already present. The NetBox-specific
scenario should be added there, reusing `osac/tests/e2e/core/grpc_client.py`,
`k8s_client.py`, `helpers.py`, and `runner.py` rather than adding tests to the
external `osac-test-infra` checkout. The test must use the existing
`wait_for_bmi_*`, `wait_for_bmh_*`, and `poll_until` patterns and clean up all
BareMetalInstances it creates.

The real API cases below gate compatibility before full provisioning tests.
Create fields/devices with an administrator fixture credential, then exercise
OSAC with the documented runtime token; assert OSAC makes no schema writes.
Use actual metadata response shapes for `object_types`, `type`, and
`filter_logic` from each pinned release; `type.value` and
`filter_logic.value` hold the machine values. Community 4.7.1 metadata must
have `status.value=active`; 4.6.10 lacks this attribute. When status is present,
reject provisioning/deleting or any other non-active/malformed value. Keep enum values
separate from display labels. Follow pagination even when requested fields are on later
pages. The [NetBox custom-field documentation](https://netbox.readthedocs.io/en/stable/customization/custom-fields/)
and [filtering reference](https://netbox.readthedocs.io/en/stable/reference/filtering/)
are background references; the pinned Community API tests establish the
release-specific contract.

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

#### TC-UNIT-001: Parse Valid NetBox Configuration

- **Setup:** YAML config with endpoint, tokenFile, caCertFile (optional), and valid mounted-file fixtures
- **Action:** Call NewNetBoxClient() with valid config
- **Expected:** Client initialized; no error; endpoint stored correctly
- **URL contract:** A trailing slash is normalized so requests use exactly
  `/api/...`; an endpoint already containing `/api` is rejected rather than
  producing `/api/api/...`
- **Location:** netbox_test.go / Describe("Configuration")

#### TC-UNIT-002: Reject Missing Endpoint URL

- **Setup:** Config with empty endpoint
- **Action:** NewNetBoxClient()
- **Expected:** Error: "endpoint required"

#### TC-UNIT-003: Load API Token from Mounted File

- **Setup:** Temporary mounted-Secret filesystem fixture for
  `/etc/osac/secrets/osac-netbox-api-token/token`, containing a synthetic value
- **Action:** Initialize the client using `tokenFile` pointing to the fixture; read
  the token file, without fetching the Secret through Kubernetes API
- **Expected:** Token loaded; not exposed in logs or error messages
- **Negative variants:** Missing path, nonexistent/unreadable file, and empty
  token fail initialization before any authenticated request. A plain Secret
  name is not resolved through Kubernetes. Assert zero Kubernetes Secret API
  requests during token loading; OSAC BMC credential resolution remains a
  separate assignment-time operation.

#### TC-UNIT-004: Load CA Certificate from Optional Mounted File

- **Setup:** Config with caCertFile pointing to a mounted `ca.crt` PEM fixture
- **Action:** Client initialization; TLS config built
- **Expected:** CA cert added to http.Client transport; valid TLS handshake with cert-signed server
- **Variants:** Omitted CA uses system trust and performs no file or Secret API
  lookup for a CA. An explicit nonexistent/unreadable/invalid PEM file fails
  startup without falling back to system trust or exposing file contents.

#### TC-UNIT-005: Validate Fixed Integration Custom Field Schema

- **Setup:** Paginated metadata fixtures contain the shared fixed integration
  fields. Vary `osac_managed` to missing, required, text type, default `true`, wrong
  model, disabled filtering, or loose filtering; vary `osac_instance_id` to
  missing, required, nonempty default, non-text, wrong model, or non-exact filtering. Also omit
  or give a wrong type to each required BMC address/boot-MAC
  field in turn;
  for each fixed field test present non-active status. The compatible 4.6.10
  metadata variant has no status attribute; 4.7.1 reports active status.
- **Action:** Initialize the client against each fixture using
  `GET /api/extras/custom-fields/?object_type=dcim.device`.
- **Expected:** Only the compatible fixed schema permits startup. Otherwise
  initialization returns a configuration error naming the field and expected
  schema without listing devices or changing NetBox. No capability whitelist
  is required at startup; BMC address/boot-MAC fields need no
  capability-filter policy.

#### TC-UNIT-006: TLS Validation Failure on Invalid Certificate

- **Setup:** Table-driven cases: self-signed HTTPS endpoint without its CA,
  direct `http://` endpoint, and an HTTPS endpoint redirecting to HTTP or a
  different authority
- **Action:** Client attempts connection
- **Expected:** Invalid certificate fails with "failed to verify TLS
  certificate"; direct HTTP is rejected before a request; unsafe redirects are
  rejected and the Authorization header is not observed by the redirect target

#### TC-UNIT-007: HostSelector Resolution and Custom-Field Extraction

- **Setup:** Persisted selector fixture
  `{"cpu_cores":"16","gpu_model":"a100","memory_gb":"128"}`;
  provide compatible metadata. Projection from the instance type and exclusion
  of conflicting hardware-description data are tested separately by TC-UNIT-057.
- **Action:** Pass the unchanged resolved map to the NetBox adapter.
- **Expected:** The three keys and values remain unchanged in
  `spec.selector.hostSelector`; the query contains `cf_cpu_cores=16`,
  `cf_gpu_model=a100`, and `cf_memory_gb=128`. No tag, device-type, or
  hardware-derived filter is added.

#### TC-UNIT-008: Custom-Field Name Syntax and Length Validation

- **Setup:** Table-driven selectors include empty keys, spaces, hyphens,
  slashes, punctuation, non-ASCII characters, and 51-character names; positive
  cases include one-character and 50-character names with letters/digits/underscores.
- **Action:** Validate each selector before metadata discovery.
- **Expected:** Names outside `^[A-Za-z0-9_]{1,50}$` return validation errors
  before any NetBox request. Valid names proceed unchanged to schema lookup.

---

### Startup Validation

#### TC-UNIT-009: Validate Co-Requirement — NetBox Requires Metal3 Management

- **Setup:** Operator config with `inventory.type=netbox`; vary wrong/missing
  `management.type`, empty Metal3 namespace, and `inventory.hostClass=netbox`.
  Positive control has management type and inventory host class both `metal3`.
- **Action:** Operator initializes NetBox backend during startup
- **Expected:** Wrong management type fails with "NetBox backend requires
  management.type=metal3"; missing namespace or wrong host class produces a
  configuration error before allocation. Positive control constructs the
  injected BMH manager using that single management namespace, uses uncached
  Secret operations, and returns `HostClass=metal3` for provisioning. No
  separate namespace or NetBox provisioning class is accepted.
- **Note:** Design constraint (see [design.md](design.md#non-goals)); ensures BMH lifecycle is managed by Metal3 controller, not NetBox backend

---

### HTTP Client and Error Handling

#### TC-UNIT-010: Token Header Correctly Set

- **Setup:** Mock HTTPS server; expects Authorization header
- **Action:** FindFreeHost() call
- **Expected:** HTTP request includes `Authorization: Token <fixture value>`;
  no plaintext token in logs

#### TC-UNIT-011: Handle 401 Unauthorized — Permanent Failure

- **Setup:** Mock server returns 401 on device list request
- **Action:** FindFreeHost()
- **Expected:** Error returned (not retried); error message: "NetBox API authentication failed"; no token in error

#### TC-UNIT-012: Handle 403 Forbidden — Permanent Failure

- **Setup:** Mock server returns 403 (insufficient permissions)
- **Action:** FindFreeHost()
- **Expected:** Error returned; message: "NetBox API permissions insufficient"

#### TC-UNIT-013: Handle 404 Not Found — Permanent Failure

- **Setup:** Mock server returns 404 on invalid endpoint path
- **Action:** FindFreeHost()
- **Expected:** Error returned; message includes field/resource name; no exposure of full API response

#### TC-UNIT-014: Handle 5xx Server Error — Transient Failure with Retry

- **Setup:** Mock server returns 500 on the first two device-list GET calls,
  then 200 on the third; metadata discovery succeeds independently
- **Action:** FindFreeHost()
- **Expected:** Three GET attempts (two retries) eventually succeed with no
  error; read-only retries are bounded by the configured budget.
- **PATCH variant:** AssignHost receives 5xx after submitting a conditional
  claim. Exactly one PATCH is sent; return an uncertain-outcome error,
  preserve ExternalHostID, and let the next reconciliation read ownership
  instead of treating the response as race loss or replaying the PATCH.

#### TC-UNIT-015: Handle Network Timeout — Transient Failure with Retry

- **Setup:** Mock server delays a read-only GET indefinitely; client timeout = 500ms
- **Action:** FindFreeHost()
- **Expected:** Timeout error; retries up to 3 times; returns error if all fail
- **PATCH variant:** A timeout or connection drop after submission never
  retries the PATCH at the HTTP layer; TC-UNIT-041 and TC-UNIT-047 check
  subsequent claim/release recovery.

#### TC-UNIT-016: Handle Connection Refused — Transient Failure with Retry

- **Setup:** Endpoint unreachable
- **Action:** FindFreeHost()
- **Expected:** Connection error; retries; returns error after retries exhausted

#### TC-UNIT-017: Error Messages Never Expose Credentials

- **Setup:** Config with a test-local synthetic fixture token
- **Action:** Trigger 401 error; capture error message and logs
- **Expected:** Error message and logs do not contain the fixture token or any
  recognizable token pattern

#### TC-UNIT-018: Handle 412 Precondition Failed — Race Loss

- **Setup:** Mock NetBox PATCH returns 412; the subsequent ownership GET
  reports active status with another requesting UID as owner.
- **Action:** AssignHost sends PATCH with If-Match, then reads ownership.
- **Expected:** Confirmed other-owner state returns `(nil, nil)` for reselection;
  no automatic PATCH retry occurs at the HTTP layer.
- **Ownership-read variants:** Active with the same context UID resumes
  idempotent BMH/Secret ensures and retains ExternalHostID, rather than
  returning nil. Clearly staged/empty owner returns `(nil, nil)` for
  reselection. A failed GET, malformed owner, or inconsistent status/owner
  combination returns an error and retains the pointer without another
  claim, resource deletion, or FindFreeHost call.

#### TC-UNIT-019: Distinguish 412 from Other 4xx Errors

- **Setup:** Mock returns 400 Bad Request vs 412 Precondition Failed; for
  412, the follow-up GET confirms an active device owned by another UID
- **Action:** AssignHost PATCH
- **Expected:** 400 → permanent error (fail fast); 412 → ownership GET, then
  `(nil, nil)` only after confirming the other owner

---

### Concurrent Access (ETag-Based)

#### TC-UNIT-020: First Writer Wins

- **Setup:** Mock NetBox returns device with ETag: W/"2026-01-01T00:00:00.000000+00:00"
- **Action:** PATCH with If-Match: W/"2026-01-01T00:00:00..." → mock returns 200 OK with new ETag
- **Expected:** AssignHost returns `(host, nil)` after resource setup;
  `host.Ready` reflects the mocked BMH readiness state, not the error return.

#### TC-UNIT-021: Second Writer Gets 412

- **Setup:** Distinct requester UIDs; mock returns the same original ETag to
  both, and the losing request's follow-up GET reports the winner's active claim
- **Action:** PATCH with If-Match: same ETag → mock returns 412 Precondition Failed
- **Expected:** After the ownership GET confirms the other UID, AssignHost
  returns `(nil, nil)`; it does not replay the PATCH and the caller reselects

#### TC-UNIT-022: Race Sequence with Goroutines

- **Setup:** Two goroutines with distinct context UIDs both call AssignHost
  on device-42 and capture the same ETag from GET
- **Action:** First PATCH succeeds (200); second PATCH gets 412, then its
  ownership GET observes active status and the first request's UID
- **Expected:** Exactly one goroutine returns `(host, nil)`; exactly one returns `(nil, nil)`; device-42 has status=active and osac_instance_id set to winner's ID, not loser's. Readiness is reported by `host.Ready`, not the error return.

#### TC-UNIT-023: Concurrent Custom-Field FindFreeHost

- **Setup:** 3 staged, managed devices with empty owners and integer
  `cpu_cores=16`; 2 tenants request `{"cpu_cores":"16"}` simultaneously
- **Action:** Both call FindFreeHost with the same custom-field filters
- **Expected:** Both queries contain the same capability and fixed pool/status/owner
  filters, and both return an eligible host ID; they may return the same ID.
  Discovery makes no PATCH or Kubernetes resource writes and does not reserve
  a host. Concurrent assignment protection is exercised by TC-UNIT-022.

---

### FindFreeHost Typed Matching and Query Construction

#### TC-UNIT-024: Custom-Field Pass-Through from Resolved HostSelector

- **Setup:** Resolved `spec.selector.hostSelector` is
  `{"cpu_cores":"16","gpu_model":"a100","memory_gb":"128"}` with valid metadata
- **Action:** Build the device query after metadata validation
- **Expected:** Exactly one parameter per capability: `cf_cpu_cores=16`,
  `cf_gpu_model=a100`, `cf_memory_gb=128`, plus the fixed pool/status/owner
  filters. Order is immaterial; no `tag`, JSON aggregate, or nested lookup is used.

#### TC-UNIT-025: Selector Values Determine the Match

- **Setup:** Text field `gpu_model`; one A100 device stores `"a100"`, one H100
  device stores `"h100"`, and one device stores `"A100"`
- **Action:** Call FindFreeHost with `{"gpu_model":"a100"}`, then
  `{"gpu_model":"h100"}`, then `{"gpu_model":"A100"}`
- **Expected:** Queries and selected devices change with each exact value;
  case remains significant and values are neither ignored nor part of field names.

#### TC-UNIT-026: Selector Key Is Not Rewritten

- **Setup:** Pre-created text field `Placement_Zone` with value `"Lab A"`;
  the instance type's hardware metadata describes a different zone
- **Action:** FindFreeHost with `{"Placement_Zone":"Lab A"}`
- **Expected:** Only the query namespace prefix is added:
  `cf_Placement_Zone=Lab+A` (or equivalent percent encoding). The decoded key
  and value preserve case, underscore, and space; no hardware derivation or
  hardcoded capability-name whitelist is used.
- **Legacy/pool selector variants:** `hostType` and `managedBy` are exact
  custom-field names too. Pre-created text fields match their supplied values;
  missing definitions are configuration errors. No Metal3 alias, implicit
  `osac.openshift.io/host-type` conversion, or built-in pool-selector exception
  is applied.

#### TC-UNIT-027: Reject Reserved Names and Lookup Injection

- **Setup:** Parameterize keys `osac_managed`, `osac_instance_id`,
  `osac_bmc_address`, `osac_boot_mac`,
  `cf_cpu_cores`, `cf_osac_managed`, `gpu_model__ic`, `cpu_cores__gte`,
  `x__y`, and `osac_instance_id__empty`.
- **Action:** Validate each selector before building a query.
- **Expected:** Every key is rejected before any NetBox request; callers
  cannot override fixed filters, supply a pre-prefixed name, or select a
  lookup operator. Reserved names are not silently dropped or rewritten.

#### TC-UNIT-028: Server-Side Custom-Field Filtering — Matching Device

- **Setup:** Managed staged device has empty owner and integer `cpu_cores=16`
- **Action:** FindFreeHost with `{"cpu_cores":"16"}`
- **Expected:** Device returned after local validation; query includes
  `cf_cpu_cores=16`, `cf_osac_managed=true`, `status=staged`, and
  `cf_osac_instance_id__empty=true`.

#### TC-UNIT-029: Server-Side Custom-Field Filtering — Different Value

- **Setup:** Valid text schema for `gpu_model`; only `"a100"` devices exist;
  mock returns an empty list for `cf_gpu_model=v100`
- **Action:** FindFreeHost with `{"gpu_model":"v100"}`
- **Expected:** `(nil, nil)` denotes no capacity for this valid selector;
  unknown or incompatible schema instead follows TC-UNIT-051's error path.

#### TC-UNIT-030: Superset Match — Extra Fields and Unrelated Tags

- **Setup:** Eligible device has `cpu_cores=16`, `gpu_model="a100"`,
  `memory_gb=128`, and unrelated tags; add an unused JSON custom field too
- **Action:** FindFreeHost with `{"cpu_cores":"16"}`
- **Expected:** Device matches; extra fields/tags do not constrain selection.
  Unsupported types are errors only when requested as capability selectors.

### Capability Schema and Defensive Validation

#### TC-UNIT-049: Paginated Metadata Discovery and Wire Shapes

- **Setup:** Serve `GET /api/extras/custom-fields/?object_type=dcim.device`
  over multiple pages with required fields only on later pages. Use captured
  pinned-release `object_types`, `type`, and `filter_logic` shapes, including
  enum objects with `value`/`label` for `type` and `filter_logic`. Include a
  wrong-model row despite the filter, and a malformed metadata variant.
- **Action:** Initialize the client, then FindFreeHost with the three shared
  capability selectors; inspect the ordered request log.
- **Expected:** Both schema reads follow all necessary pages; membership
  explicitly includes `dcim.device`, and enum comparisons use machine values,
  not labels; absent 4.6.10 field status is accepted, while present status
  must be active. No device query precedes successful validation. Malformed or
  incompatible metadata fails closed as a configuration error.

#### TC-UNIT-050: Refresh Capability Schema on Every Search

- **Setup:** Start with the fixed schema only. After startup, add an exact
  text field `placement_zone` and eligible device value `"west"`; return a
  changed metadata response on each subsequent discovery.
- **Action:** FindFreeHost with `{"placement_zone":"west"}`; change its
  filtering to loose and repeat; restore exact filtering and repeat again.
- **Expected:** First call succeeds without a client restart; second returns
  a configuration error with no device-list request; third succeeds. Every
  call refreshes metadata and does not use a stale startup cache or whitelist.

#### TC-UNIT-051: Invalid Requested Schema Is Not Empty Capacity

- **Setup:** For `placement_zone`, vary missing schema, `object_types`
  excluding `dcim.device`, disabled filtering, loose filtering, present
  non-active status (`provisioning`, `deleting`, or unknown), and each
  unsupported type: JSON, multiselect, object, multiobject, date, datetime,
  decimal, URL, and long text. Include a valid unrelated field in each response.
- **Action:** FindFreeHost with `{"placement_zone":"west"}` and record
  calls to `/api/dcim/devices/`.
- **Expected:** Each invalid requested schema returns a configuration error
  identifying the validation category without raw selector keys/values;
  zero device-list requests, allocations,
  or capacity-exhaustion results. The adapter does not use native-field,
  tag, or loose-filter fallback. Exact scalar text schema succeeds.

#### TC-UNIT-052: Supported Scalar Values and Invalid Inputs

- **Setup:** Exact-filter metadata for integer `cpu_cores`, boolean
  `accelerated`, text `placement_zone`, and select `accelerator` whose stored
  value is `"a100"` and display label is `"NVIDIA A100"`.
- **Action:** Build queries for each value in the table, including both int64
  endpoints, and compare decoded query parameters.
- **Expected:** Accepted values retain their exact representation; rejected
  values return a validation error before any device-list request. Select
  uses the stored value; a display label must not be translated into `a100`.

| Type | Accept | Reject |
|------|--------|--------|
| integer | `0`, `16`, `-1`, `-9223372036854775808`, `9223372036854775807` | `+16`, `016`, `-0`, `1.0`, `1e2`, ` 16`, `16 `, empty, `9223372036854775808`, `-9223372036854775809` |
| boolean | `true`, `false` | `True`, `FALSE`, `1`, `0`, `yes`, empty, ` true ` |
| text | `a100`, `A100`, `Lab A`, `&status=active` | empty, exact `null`, leading/trailing whitespace such as ` a100`, `a100 `, or a surrounding tab |
| select | exact stored string such as `a100`; a display-label string is never translated to that value | empty, exact `null`, leading/trailing whitespace |

#### TC-UNIT-053: Revalidate Every Returned Typed Capability

- **Setup:** Mock deliberately ignores filters and returns decoys before one
  valid row for selectors `{"cpu_cores":"16","accelerated":"false",
  "gpu_model":"a100","accelerator":"a100"}`. Decoys individually have
  missing/null fields, integer `8`, numeric string `"16"`, JSON Boolean
  `true`, string `"false"`, text `"A100"`/`"a100 "`, arrays/objects, or a
  select display label instead of its stored value. The valid select value
  uses the pinned release's string or `{value,label}` shape; structured
  select-value decoding is covered by TC-UNIT-058. Also test integer values
  above 2^53 and the int64 endpoints without float rounding.
- **Action:** FindFreeHost with valid schema; repeat with only decoys.
- **Expected:** Only the row with all exact typed values is selected; extra
  fields are allowed. Missing/null/wrong-type/mismatching values never match,
  even if the server ignores an unknown filter. Arrays/objects cannot stand
  in for scalar text/integer/Boolean values. All-decoy results yield
  `(nil, nil)`; integers are compared losslessly.

#### TC-UNIT-054: Escape Exact Values Without Query Injection

- **Setup:** Exact text values include `&status=active`, `a+b`, `x=y`,
  `100%`, `#fragment`, Unicode, and internal spaces such as `Lab A`.
  Separate negative cases are ` a100`, `a100 `, surrounding tabs, and exact
  `null`, for both text and select fields.
- **Action:** Build and decode the URL for each selector, then return an
  eligible device with each accepted exact stored value. For negative cases,
  record that validation prevents device requests.
- **Expected:** One `cf_<name>` parameter carries the original value;
  `&status=active` appears as `%26status%3Dactive` within its value. The only
  status parameter remains `staged`; pool/owner filters are unchanged, no
  fragment is created, and local matching preserves the exact string.
  Negative cases return a configuration/validation error before device
  listing; whitespace is rejected rather than trimmed, and `null` never
  becomes a missing-value search.

#### TC-UNIT-055: Claim and Release Preserve Administrator Metadata

- **Setup:** Device has Boolean `osac_managed=true`, shared capabilities,
  an unrelated nested custom field, and unrelated tags. Snapshot its data.
- **Action:** AssignHost, retry with the same owner, then UnassignHost;
  inject a concurrent administrator capability edit causing a release 412.
- **Expected:** Only status and owner change. PATCH sends only `status` and
  `custom_fields.osac_instance_id`; it never echoes BMC credential values,
  Secret labels, or other custom fields. NetBox's merge retains pool,
  capabilities, BMC address/boot-MAC metadata, unrelated values, and tags.
  Retrying after 412 re-reads and preserves the administrator's latest edit.
  No schema mutation or capability/pool-value update is issued by OSAC.

#### TC-UNIT-056: Empty Owner Forms and Strict Pool Membership

- **Setup:** Table of staged devices with owner missing, `null`, `""`,
  whitespace, a nonempty ID, or a wrong JSON type; cross with pool `true`,
  `false`, missing, `null`, string `"true"`, and numeric `1`. Capabilities match.
- **Action:** Return each row despite filters, then call FindFreeHost.
- **Expected:** Only JSON Boolean pool `true` and an owner missing, `null`,
  or exactly `""` qualify. Whitespace is a populated owner; wrong types are
  excluded. Repeat eligible rows with `active`/`offline` status and exclude
  them. Pool defaults do not opt devices into allocation.

#### TC-UNIT-058: Select Stored Values Across Community Response Shapes

- **Setup:** Exact select schema and selector `{"accelerator":"a100"}`.
  Parameterize candidate values as Community 4.6.10 string `"a100"` and
  4.7.1 object `{"value":"a100","label":"NVIDIA A100"}`. Also provide an
  object with a different/missing label but the same value; decoys have a
  matching label but `value="h100"`, missing/null/numeric/Boolean `value`,
  a label-only object, an array, null, or a differently cased stored value.
- **Action:** Decode each real-release response fixture and run local
  capability matching; inspect the query emitted for the selector.
- **Expected:** Both supported forms match only the exact stored string
  `a100`. Display labels do not affect selection; malformed `.value` shapes
  and nonmatching strings are excluded without panics or coercion. The query
  remains `cf_accelerator=a100`; response labels are never used as filters.

### Fulfillment-Service Selector Projection

#### TC-UNIT-057: Project New Catalog Types with Existing Sources Unchanged

- **Location:**
  `osac/fulfillment-service/internal/controllers/baremetalinstance/baremetalinstance_reconciler_function_test.go`,
  extending the existing instance-type-to-HostSelector tests.
- **Setup:** Fulfillment reconciler unit fixtures with catalog type A
  containing the three shared selector entries and a fake hub client. Keep
  A's identity and selector unchanged while referenced. Add the existing
  legacy-template fallback as a parameter variant.
- **Action:**
  1. Reconcile initial BMI creation; capture its resolved selector.
  2. Create a separate catalog type B with different keys/values, then
     reconcile the existing A-based BMI through CreateOrPatch again,
     including a reconciler restart. Before that reconcile, seed the
     operator-owned namespace-qualified host ID and cleanup checkpoint
     annotation on the CR; verify all survive repeated projection.
  3. Create a new BMI referencing B and inspect its selector.
- **Expected:** Initial projection preserves all exact keys and meaningful
  values. Under the unchanged-source prerequisite, the existing BMI retains
  its original map without merging B's selector; the new BMI uses B's map.
  Tenant metadata and the operator-owned host binding remain intact; source
  projection does not clear or rewrite them. Assert
  intended write payloads explicitly: the fake client alone does not enforce
  CRD immutability. Editing/removing/recreating A or the referenced legacy
  template is unsupported because current reconciliation re-resolves it;
  this scenario does not assume a stable projection fix exists.

### Search Isolation and Remaining Candidates

#### TC-UNIT-031: Search Remains Scoped to the Requested Profile

- **Setup:** Five managed staged devices with empty owners; only one matches
  `{"cpu_cores":"16","gpu_model":"a100"}`. Others have spare capacity
  with different CPU/GPU values. Include non-pool/offline/owned decoys.
- **Action:** FindFreeHost for the requested profile; inspect every device
  request and the selected ID.
- **Expected:** Selection uses both requested capabilities and fixed
  pool/status/owner predicates. Only the matching device is returned; no
  separate pool-wide counting request or background availability refresh occurs.
  Host-name derivation is local to the selected device ID and cannot choose
  another device or broaden capability matching.

#### TC-UNIT-032: Next Search Excludes the Newly Claimed Candidate

- **Setup:** Two devices match one requested profile; AssignHost claims the
  first with valid AllocationContext. The next mock list deliberately returns
  both rows, including the first device's active status and populated owner.
- **Action:** FindFreeHost for a second requester with the same selector.
- **Expected:** The newly claimed row is excluded and only the still-staged,
  owner-empty candidate is returned. The assertion uses candidate IDs and
  state, not an inventory capacity metric.

#### TC-UNIT-033: No Match Does Not Fall Back to Unrelated Capacity

- **Setup:** All matching-profile devices are active with owners, but other
  managed staged devices match different capability values.
- **Action:** FindFreeHost using valid metadata and the original selector;
  return no matching candidates from the mock.
- **Expected:** `(nil, nil)` with no broader fallback search, claim, or
  assignment-attempt increment. Unrelated spare hosts cannot satisfy this profile.

---

### FindFreeHost Pool and Status Filtering

#### TC-UNIT-034: Query Returns Only Staged Devices with Managed Pool Flag

- **Setup:** Mock response includes 10 devices with matching capabilities:
  6 staged with Boolean `osac_managed=true` and empty owners, 2 offline,
  and 2 staged with `osac_managed=false`
- **Action:** FindFreeHost()
- **Expected:** Query includes server-side filters
  `cf_osac_managed=true&status=staged&cf_osac_instance_id__empty=true`; local
  pool/status/owner/capability validation leaves only the six eligible rows.

#### TC-UNIT-035: No Candidates — All Devices Already Assigned

- **Setup:** NetBox has 5 pool devices; three have status=active and a non-empty `osac_instance_id`, and two have status=staged with a stale non-empty `osac_instance_id`
- **Action:** FindFreeHost(); the mock returns the staged stale-owner rows
  despite the empty-owner filter to exercise the defensive client-side check
- **Expected:** nil returned (no error); the adapter skips all five devices,
  including the staged devices with stale owner markers, and the controller retries

#### TC-UNIT-036: No Candidates — Empty Device Pool

- **Setup:** NetBox returns 0 devices matching pool
- **Action:** FindFreeHost()
- **Expected:** nil returned; no error

#### TC-UNIT-037: Pagination of Large Device Lists

- **Setup:** NetBox returns 250 devices over pages of 100, 100, and 50;
  only the last device passes all local pool/status/owner/capability checks
- **Action:** FindFreeHost() queries all pages
- **Expected:** All 250 evaluated; pagination handled transparently; single candidate returned

---

### AssignHost Idempotency and Race Conditions

#### TC-UNIT-059: AllocationContext Is Separate from Assignment Labels

- **Setup:** BMI with UID/name/namespace, persisted selector
  `{"cpu_cores":"16","gpu_model":"a100"}`, trusted tenant/owner-reference
  annotations, and assignment labels containing conflicting selector-like
  and identity-like values. Use the controller's inventory-client mock.
- **Action:** Invoke allocation and release reconciliation, capture arguments
  passed to AssignHost/UnassignHost, and mutate the original maps after capture.
  Run the existing backend contract suites with the extended interface.
- **Expected:** Context contains exactly the requesting BMI identity,
  independent selector snapshot, trusted tenant annotation, and owner-reference
  derived from the BMI UID even if its input owner annotation is absent or
  conflicting. Assign labels and
  release label names remain separate; they cannot override context identity
  or selectors. Context maps are not aliases of mutable input maps. Existing
  backends use `InstanceID`, ignore new selector data, and preserve their
  existing allocation/release behavior.

#### TC-UNIT-060: Revalidate Persisted Candidate Before a New Claim

- **Setup:** Persist ExternalHostID from an earlier FindFreeHost; a new client
  instance has no discovery cache. Context contains the BMI's original
  selector, while assignment labels and the current catalog contain different
  values. Parameterize a fresh detail response with changed capability, pool
  false, non-staged status, or nonempty owner; separately change requested
  field schema to missing/non-active/non-exact.
- **Action:** AssignHost using AllocationContext. Also run a positive case
  with all persisted predicates matching, and change the device after the
  detail GET to force a stale-Etag PATCH.
- **Expected:** Schema refresh and typed detail validation use the persisted
  context selector, never assignment labels, the current catalog, or a
  process-local discovery cache. Data mismatch returns `(nil, nil)` for
  reselection; invalid schema returns an error before a claim. No rejected
  case creates resources or writes NetBox. A valid claim sends only owner and
  status with the detail GET's exact ETag; a later external edit yields 412,
  followed by an ownership GET. For this variant the GET confirms staged/empty
  owner, permitting `(nil, nil)` and reselection.
  Same-owner active recovery remains TC-UNIT-039's bypass path.

#### TC-UNIT-038: Successful Assignment

- **Setup:** Device found unassigned; AssignHost called with instanceID "inst-123"
- **Action:** AssignHost with `inventoryHostID="baremetal/netbox-42"` and
  `InstanceID="inst-123"`
- **Expected:** Device PATCH sets status=active and osac_instance_id to "inst-123"; returns (host, nil)
- **Validation variants:** Omit the address or boot MAC; return no matching,
  multiple matching, or malformed system-scoped OSAC Secret; or provide an
  invalid BMC address/MAC. Deterministic validation fails before the claim
  PATCH or Kubernetes creates, records a sanitized failure for a staged,
  unowned device, and preserves all pool/capability values. Secret API outage
  or access/configuration failure is retryable, leaves NetBox status unchanged,
  and creates no resources. A valid device label resolves username/password
  only in memory and supplies them to the runtime Secret manager.

#### TC-UNIT-039: Idempotent Retry — Same Assignment ID

- **Setup:** Device already has status=active and osac_instance_id = "inst-123"
- **Action:** AssignHost with the same host ID and AllocationContext UID again
- **Expected:** Read returns existing assignment; matches requested ID; skips the ownership PATCH, re-ensures the BMC Secret/BMH idempotently, and returns (host, nil)
- **Retry variants:** Missing BMH/Secret are recreated for the same owner;
  `Host.Ready=false` or a transient readiness-read failure retains the claim
  and existing resources. For this already-owned case, no FindFreeHost or
  capability-schema lookup is required; an administrator capability
  change must not make the same-owner retry allocate a second host.
  Repeat after the pool flag is set false or capability schema changes; the
  existing owner's recovery still proceeds without a new claim.
  If this BMI still owns the device but its native status is inconsistent,
  return an error preserving ExternalHostID for repair rather than reselecting.

#### TC-UNIT-040: Race Condition — Device Assigned to Different Instance

- **Setup:** Device already has status=active and osac_instance_id = "inst-999" (another instance claimed it)
- **Action:** AssignHost with that host ID and `AllocationContext.InstanceID="inst-123"`
- **Expected:** Read-then-compare detects mismatch; returns (nil, nil) — race lost

#### TC-UNIT-041: Crash Recovery — Assignment Persisted

- **Setup:** Device has status=active and osac_instance_id = "inst-123" (from previous AssignHost call)
- **Action:** Operator crashes and restarts; reconciliation retries AssignHost with same ID
- **Expected:** Idempotent: ownership is not rewritten, BMC Secret/BMH state is re-ensured, and reconciliation proceeds without double-assignment
- **Lost-response variants:** NetBox commits a claim but the response is lost
  through timeout/network failure or replaced by 5xx. Return an error and
  retain the persisted ExternalHostID; send no automatic second PATCH and
  do not reselect. On the next reconciliation, a fresh GET finds the same
  owner and resumes idempotent BMH/Secret setup. Repeat where the write did
  not commit: only a fresh read plus eligibility validation permits a new
  conditional claim, never blind transport replay.
- **Delayed-commit variant:** Hold the initial conditional PATCH until its
  caller times out; preserve ExternalHostID. The next reconciliation reads
  still-staged/empty state and prepares a new conditional claim. Let the old
  PATCH commit before the new PATCH, causing the new PATCH to receive 412.
  Its follow-up GET observes active/same UID: retain the pointer and resume
  BMH/Secret ensures, with one committed claim and no reselection or orphaned
  assignment. Change the device's Secret label association or connection
  metadata before that follow-up GET and assert the adapter resolves and
  validates the newly read values, not the stale pre-PATCH values; an invalid
  or ambiguous source Secret or metadata prevents resource creation and
  retains the existing claim for repair. If that ownership GET fails or returns inconsistent state,
  return an error and retain the pointer for the next reconciliation.

#### TC-UNIT-042: ETag Capture on Read

- **Setup:** Mock GET returns device with ETag header: W/"2026-01-01T00:00:00.000000+00:00"
- **Action:** AssignHost step 1 reads device
- **Expected:** ETag value is captured and stored for use in step 3 PATCH
- **Negative variant:** A missing/empty ETag yields an error before any
  claim PATCH; no unconditional update is allowed.

#### TC-UNIT-043: If-Match Sent on PATCH

- **Setup:** AssignHost reads a candidate, refreshes schema, then receives a
  different ETag on the final detail GET that passes all eligibility checks
- **Action:** Step 3 sends PATCH request
- **Expected:** If-Match uses the ETag from that final eligibility-checked
  response, not the earlier discovery/read response.

---

### UnassignHost Idempotency

#### TC-UNIT-061: Requester UID Authorizes Every Release or Compensation

- **Setup:** Requested context UID `inst-123`. Parameterize: NetBox owner
  `inst-999` with matching `inst-999` BMH/Secret; matching NetBox owner but
  BMH ConsumerRef UID `inst-999`; matching NetBox/BMH but foreign Secret owner
  UID; an ownerless residual BMH/Secret; same BMI name/namespace with a
  recreated, different UID; or missing
  requesting UID. Use `releasing`/`compensating`, without a resource-absence
  checkpoint, for these negative cases. Include a valid owner case with
  already-absent resources.
- **Action:** UnassignHost and post-claim preparation compensation with that
  context. For the valid case, persist the absence checkpoint before release.
- **Expected:** Every mismatch returns an ownership/identity error without
  NetBox writes, BMH/Secret deletion, or finalizer removal. Agreement between
  NetBox and BMH alone does not authorize a different requester. A valid
  requester may continue cleanup of already-absent resources; it must never
  clear a new owner's assignment. Completed-cleanup recovery is covered
  separately by TC-INT-030. Same names,
  assignment labels, or a captured ExternalHostID cannot substitute for UID.

#### TC-UNIT-044: Successful Deassignment

- **Setup:** Device has status=active and osac_instance_id = "inst-123"
- **Action:** UnassignHost with that host ID and requesting AllocationContext
- **Expected:** Device PATCH sets status=staged and clears osac_instance_id; returns nil

#### TC-UNIT-045: Idempotent Retry — Already Unassigned

- **Setup:** Device already has status=staged and osac_instance_id = nil
  (unassigned); both BMH and Secret are absent
- **Action:** UnassignHost with that host ID and requesting AllocationContext
- **Expected:** Read returns nil; already unassigned; returns nil without PATCH
- **Residual-resource variant (without a ready checkpoint):** A foreign or ownerless BMH/Secret prevents
  declaring cleanup complete; return an ownership error without deleting it
  or removing the BMI inventory finalizer.

#### TC-UNIT-046: Ownership Guard — BMH Belongs to Different Instance

- **Setup:** Device has status=active and osac_instance_id = "inst-123";
  requesting UID is `inst-123`, but BMH `spec.consumerRef.uid` is `inst-888`
- **Action:** UnassignHost with that host ID and requesting AllocationContext
- **Expected:** Returns an ownership-conflict error; does not delete the BMH or BMC Secret and does not PATCH NetBox

#### TC-UNIT-047: 412 During Unassignment — Retry from Read

- **Setup:** Mock GET returns device assigned to our instance; PATCH returns 412 Precondition Failed
- **Action:** After owned resources are absent, UnassignHost sends the
  release PATCH with If-Match from its final device read
- **Expected:** UnassignHost re-reads device and revalidates the requesting
  UID before retry; a still-matching owner permits retry. A changed owner
  never permits its cleanup or release; only the persisted-ready, no-old-owned-
  resources rule in TC-INT-030 permits no-op completion.
- **Missing-ETag variant:** A final GET without an ETag prevents the release
  PATCH and retains the claim/finalizer for an actionable error or retry.
- **Lost-release-response variants:** NetBox commits staged/empty owner but
  the response times out, drops, or becomes 5xx. Return an error, retain the
  inventory finalizer, and send no automatic second PATCH. Next reconciliation
  reads staged/empty owner and confirms BMH/Secret absence through the direct
  Kubernetes API, then completes without another release write. If the write
  did not commit, a fresh owner/ETag read precedes a later conditional release.
  Retain the persisted ready checkpoint throughout these retries.

---

### GetHostNICs (BMH Hardware Inspection)

#### TC-UNIT-048: GetHostNICs Delegates to BMH Hardware Data

- **Setup:** Existing BMH has inspected hardware with NIC MAC addresses
- **Action:** GetHostNICs(inventoryHostID="baremetal/netbox-42")
- **Expected:** Lowercased MAC addresses are returned as `inventory.HostNIC` values; no NetBox API call is made
- **Note:** If the BMH has no hardware data yet, return `(nil, nil)` following the existing BCM manager contract

### Device ID and Recovery Binding

#### TC-UNIT-062: Generate Kubernetes-Safe ID-Derived Names

- **Setup:** Candidate device ID `42`; parameterize `device.name` as
  `worker-rack3-07`, empty, null, duplicate, uppercase, whitespace, or other
  invalid text. Include a positive one-digit ID, the largest supported
  positive int64 ID, zero, negative, leading-zero, nonnumeric, overflowing,
  and otherwise malformed IDs.
- **Action:** FindFreeHost and inspect the returned Host and request path.
- **Expected:** Every valid device-name variant returns
  `baremetal/netbox-42`, `Name=netbox-42`, an empty `ExternalHostName`, and
  `HostClass=metal3`; the detail path is `/api/dcim/devices/42/`. The
  centralized `IsDNS1035Label` helper accepts the `netbox-<id>` result before
  any claim or Kubernetes write. Invalid IDs return an identity/configuration
  error. Device name, site, region, and unrelated duplicate names do not
  change the result or trigger a full-inventory identity scan; capability
  matching still determines candidates.

#### TC-UNIT-063: Use Persisted Namespace-Qualified ID Identity

- **Setup:** Complete binding `baremetal/netbox-42`; configure Metal3
  namespace `baremetal`. Parameterize wrong namespace, missing slash, wrong
  prefix, zero/negative/noncanonical/overflowing ID, mismatched BMH name, and
  a conflicting assignment label that contains another ID.
- **Action:** Invoke controller allocation/release and adapter methods with
  each binding. Recreate the client between calls and do not create a BMH
  before the claim read.
- **Expected:** The valid path reads/PATCHes `/api/dcim/devices/42/` and
  manages BMH `baremetal/netbox-42`; it never uses an ID from labels,
  `device.name`, a BMH lookup, or an in-memory cache. The namespace must match
  the configured Metal3 namespace. Invalid or partial bindings return an
  identity error before NetBox writes or BMH/Secret mutations and remain for
  repair rather than being inferred or replaced.

#### TC-UNIT-064: Device Name Changes Cannot Redirect Recovery

- **Setup:** Persisted binding `baremetal/netbox-42` and BMH/Secret
  `netbox-42`. Parameterize a raw rename, empty-to-name transition,
  name-to-empty transition, site/region change, and a 404 for ID `42` while ID
  `99` reuses the old device name.
- **Action:** Restart the client and call AssignHost/UnassignHost. Repeat with
  a foreign requesting UID and with a 412 between the eligibility GET and claim
  PATCH.
- **Expected:** Name, site, and region changes do not alter the ID-derived
  BMH or cause reselection; the same-owner path continues using device `42`.
  Authorized release uses only device `42` and `netbox-42`. A 404 retains the
  binding/finalizer with no destructive cleanup or name fallback. Device `99`
  and foreign-owner resources are never touched.

#### TC-UNIT-065: Cleanup Intent and Absence Checkpoints Gate Side Effects

- **Setup:** A owns the claim; parameterize BMC Secret and BMH preparation
  failures. Use controller mocks that can reject each BMI checkpoint update.
  Include missing/unknown cleanup states and every accepted nonempty state.
- **Action:** Handle `PreparationFailed`, retry reconciliation after a restart,
  then observe resource absence and handle `CleanupCheckpointRequired`.
  Repeat normal deletion and deletion that starts during compensation.
- **Expected:** A preparation error alone does not delete resources. Only
  persisted `compensating`/`releasing` permits UnassignHost cleanup; pending
  cleanup never calls FindFreeHost or resource-creating AssignHost. The adapter
  rejects missing/invalid cleanup state for release and any nonempty state
  for assignment. Both resources must be absent before requesting `*-ready`;
  NetBox release cannot precede that successful checkpoint update. Unknown
  state retains the binding/finalizer with an actionable error. Completed
  compensation atomically clears cleanup state and all three binding values
  before another search; deletion completes without a new allocation.
  Readiness false/transient readiness-read errors do not trigger compensation.

---

## Integration Tests

**Structure:** Integration tests use controller-runtime envtest (Kubernetes API
server and etcd managed by the test environment) with a **mock NetBox HTTPS
server** (`httptest.NewTLSServer`). Tests run against the real operator
reconciliation loop with the external API mocked in TC-INT-001 through
TC-INT-014, TC-INT-024 through TC-INT-026, TC-INT-028, and TC-INT-030. TC-INT-015 through TC-INT-023 and TC-INT-029
separately exercise the **real Community API**, whose filtering and concurrency semantics cannot be proved
by envtest or a mock.

**Pattern:** Follow the existing BMF controller integration tests
(`osac/bare-metal-fulfillment-operator/internal/controller/baremetalinstance_bcm_integration_test.go`
and `baremetalinstance_metal3_integration_test.go`) for envtest setup,
`DeferCleanup` patterns, reconciliation, and context usage.

### Full Allocation Workflow with Envtest

#### TC-INT-001: Allocate Host via BareMetalInstance

- **Setup:** envtest API server with bare-metal-fulfillment-operator;
  **mock NetBox HTTPS server** (`httptest.NewTLSServer`); Kubernetes Secret with API token
- **Prerequisites:**
  - Fixed integration and capability fields use the shared schema
  - Mock system-scoped OSAC Secret(s) contain the synthetic username/password
    and label each associated device with
    `osac.openshift.io/netbox-device-<device-id>: "true"`; at least one Secret
    is labeled for multiple devices to verify supported reuse
  - 5 devices have `status=staged`, `osac_managed=true`, empty owner, and
    matching typed capability values
- **Action:**
  1. Create a BareMetalInstance in envtest with the already-resolved
     `spec.selector.hostSelector` map `{"cpu_cores":"16"}` and the required
     tenant/owner-reference annotations; fulfillment-service resolution is
     exercised by TC-E2E-003
  2. Wait for operator to reconcile
- **Expected:**
  1. BareMetalInstance `spec.externalHostID` is
     `<metal3 namespace>/netbox-<id>`; `spec.externalHostName` remains empty,
     and no numeric-ID annotation is persisted before claiming NetBox
  2. Device in NetBox now has status=active and osac_instance_id set to BareMetalInstance UID
  3. No device is double-allocated; this is checked from the NetBox fixture
     state rather than from a Kubernetes Event
  4. The device label resolves exactly one system-scoped Secret through the
     OSAC Secret API, and its values reach only the deterministic
     operator-managed runtime Secret and BMH consumer reference; pool,
     capabilities, unrelated custom fields, and tags are unchanged
  5. The BMH name equals `netbox-<id>` in the configured Metal3 namespace,
     its Secret has the documented suffix, and the ready host's
     BMI `hostClass` is `metal3`, not `netbox`

#### TC-INT-002: Deallocate Host via BareMetalInstance Deletion

- **Setup:** BareMetalInstance allocated to device; host ready
- **Action:**
  1. Delete BareMetalInstance
  2. Wait for operator to reconcile
- **Expected:**
  1. Device in NetBox has osac_instance_id cleared
  2. Device status is restored to staged; host returns to available pool
  3. BareMetalInstance deleted cleanly
  4. BMH and its operator-managed BMC Secret are removed before clearing the
     owner; all administrator metadata is preserved

#### TC-INT-003: Host Preparation Failure Rolls Back the Claim

- **Setup:** BareMetalInstance has claimed a staged device; the mock OSAC
  Secret resolution/runtime BMC Secret or BareMetalHost creation fails after
  the NetBox assignment PATCH
- **Action:**
  1. Reconcile the BareMetalInstance
  2. Persist compensation intent, then allow cleanup to run; restart after
     BMH disappearance and again before the resource-absence checkpoint.
  3. Repeat with a successful BMC/BMH response after compensation completes.
     Also start deletion while compensation is pending.
- **Expected:**
  1. Requesting AllocationContext UID, NetBox owner, BMH ConsumerRef UID,
     and Secret owner UID agree before cleanup; only those resources are removed
  2. NetBox is patched back to `status=staged` with an empty
     `osac_instance_id`, using `If-Match` from a fresh GET after both BMH
     and Secret are confirmed absent and `compensating-ready` is persisted;
     pending deletion retains the claim
  3. The controller retries allocation after the failure; the next successful
     attempt can claim a device without an orphaned BMH, Secret, or owner marker
  4. If cleanup cannot be proven safe, the claim remains for retry and no other
     instance's resources are deleted
  5. Restarts continue cleanup without recreating a BMH/Secret. Only successful
     compensation and atomic clearing of binding/checkpoint allow another
     allocation; a deleting BMI never returns to allocation.

#### TC-INT-013: Network Failure Recovery

- **Setup:** BareMetalInstance allocation is in progress; the mock NetBox server
  returns 5xx for 5 seconds
- **Action:** Wait for the adapter retry budget and controller backoff, then
  restore successful responses
- **Expected:** Allocation eventually succeeds without exposing backend-specific
  details to the tenant

#### TC-INT-004: Permanent Auth Failure

- **Setup:** Operator initializes with a valid token, then NetBox revokes it.
- **Action:**
  1. Create BareMetalInstance
  2. Operator attempts allocation
- **Expected:**
  1. `FindFreeHost` returns a permanent authentication error and the
     reconciliation is retried by the controller's normal error backoff
  2. Operator logs: "NetBox API authentication failed"
  3. Admin sees an actionable instruction to check the mounted `tokenFile`
     credential and its NetBox permissions, without exposing the token
  4. `osac_netbox_api_errors_total{error_type="401"}` increments without
     exposing the token

#### TC-INT-005: Schema Validation Failure on Startup

- **Setup:** Parameterized NetBox metadata missing either `osac_managed` or
  `osac_instance_id`, assigned to the wrong model, or incompatible with the
  Boolean/default-false/exact pool or optional-text/exact owner contract
- **Action:**
  1. Deploy operator with NetBox config
- **Expected:**
  1. Operator logs an actionable configuration error naming the invalid field
  2. Operator exits or marks readiness = false
  3. Admin must create field before operator can start

#### TC-INT-006: Configuration Update After Operator Restart

- **Setup:** Drain all pending/allocated NetBox BMIs and verify cleanup, then
  update Helm values from one endpoint to a new endpoint with prepared inventory
- **Action:**
  1. Run a Helm upgrade with the new endpoint value using the protected
     values mechanism; do not patch the mounted Secret directly
  2. Restart operator
  3. Create BareMetalInstance
- **Expected:**
  1. Operator picks up new endpoint
  2. Allocation queries new endpoint
  3. Succeeds if new endpoint is reachable

#### TC-INT-007: Concurrent Assignment with ETag Protection

- **Setup:** Two BareMetalInstance CRs with distinct UIDs request the same
  capability selector; only one device matches in mock NetBox
- **Action:** Reconcile both BMIs through the existing controller and its
  in-process host lock; allow the winning assignment to complete.
- **Expected:** Exactly one UID owns the device and its BMH/Secret. The other
  request either waits for the lock or reads the winning owner and reselects;
  it cannot overwrite the claim. Do not require an incidental 412 from paths
  serialized by the lock. TC-UNIT-022 and TC-INT-021 deliberately bypass that
  serialization with independent adapter calls to test stale-ETag races.

#### TC-INT-008: Assignment and API Error Counters

- **Setup:** Envtest operator with a registered metrics endpoint and valid
  schema; mock can return successful assignment, 412, and 401 responses.
  The 412 follow-up GET confirms another UID's active claim. Capture baseline
  counters and NetBox request counts.
- **Action:** Produce one successful AssignHost, one stale-ETag claim, and
  one auth failure during AssignHost; then reconcile a valid selector with
  no matching hosts and scrape metrics again without allocating.
- **Expected:** Assignment-attempt counter deltas are one each for
  `result="success"`, `result="race"`, and `result="error"`; API-error
  counter increases for `error_type="401"`. A no-host search never reaches
  AssignHost and adds no assignment attempt. Metrics scraping triggers no
  pool-wide NetBox list request; errors/counters expose no credential values.

#### TC-INT-009: Server-Side Custom-Field Filtering Verification

- **Setup:** envtest operator; mock schema and 10 eligible devices: 5 with
  `gpu_model="a100"`, 5 with `gpu_model="v100"`
- **Action:** Resolve `spec.selector.hostSelector` as `{"gpu_model":"a100"}`
- **Expected:** Metadata validation precedes the device query containing
  `cf_gpu_model=a100`, `cf_osac_managed=true`, `status=staged`, and
  `cf_osac_instance_id__empty=true`; only one of the five matching devices
  is claimed. TC-INT-016 verifies actual server filtering independently.

#### TC-INT-010: Capability Mismatch — Zero Results

- **Setup:** Valid text `gpu_model` schema; only `"a100"` devices exist
- **Action:** Create a BMI with `spec.selector.hostSelector` set to
  `{"gpu_model":"h100"}`, invoke the reconciler directly in envtest, and capture
  its returned `ctrl.Result` and error.
- **Expected:** Query includes `cf_gpu_model=h100` and fixed pool/status/owner
  filters; NetBox returns an empty list. Reconciliation returns a nil error
  and `RequeueAfter=NoFreeHostsPollIntervalDuration`, leaves ExternalHostID
  empty, and sets `HostConditionAllocated=False` with reason `NoMatchingHosts`
  and the generic no-host message. Missing schema is an error, not this
  no-match path. The exact return value is asserted here, not through pytest.

#### TC-INT-011: Capability Value Update on Device

- **Setup:** Eligible device has integer `memory_gb=64`
- **Action:** Admin changes the value to `128`; create a new
  BareMetalInstanceType for subsequent requests, leaving referenced types
  unchanged, then search with each value
- **Expected:** `{"memory_gb":"64"}` no longer matches;
  `{"memory_gb":"128"}` matches. OSAC has not edited the capability.

#### TC-INT-012: Cross-Backend Non-Regression

- **Setup:** Test cluster configured with Metal3 backend; deploy second cluster with NetBox backend
- **Action:**
  1. Create BareMetalInstance in Metal3 cluster
  2. Create BareMetalInstance in NetBox cluster
  3. Verify both allocate successfully
- **Expected:**
  1. Metal3 cluster: allocation uses Metal3 BareMetalHost
  2. NetBox cluster: allocation uses NetBox devices
  3. No cross-contamination
  4. Existing BCM, Metal3, and OpenStack backend suites compile and retain
     their behavior with AllocationContext: use InstanceID where needed and
     do not apply NetBox selector/schema semantics to other backends

#### TC-INT-014: New Instance Type After Operator Startup

- **Setup:** Operator initialized with the fixed schema and original shared
  capabilities; no `placement_zone` field exists yet. Mock can update its
  metadata and device responses while the controller remains running.
- **Action:**
  1. Administrator introduces an exact text capability `placement_zone` with
     value `"west"` and an instance type using it; create a BMI with the new
     resolved selector map in envtest.
  2. Reconcile, then disable filtering and reconcile a second new BMI.
  3. Restore exact filtering and allow the second BMI to retry.
- **Expected:** First BMI allocates without restarting the operator. Invalid
  schema produces a configuration error before a device query and no
  `NoMatchingHosts` capacity result; restoring schema permits retry. Existing
  same-owner assignment continues without rediscovery of capability schema.

#### TC-INT-024: Persisted Candidate Revalidation and Wrong-Requester Deletion

- **Setup:** BMF envtest with BMIs A and B, distinct UIDs, and one candidate
  initially satisfying A's persisted selector. Reconcile A until ExternalHostID
  is recorded but before it claims NetBox; restart the adapter/controller so
  no in-memory selection state survives. Assignment labels differ from A's
  HostSelector.
- **Action:**
  1. In separate runs change the candidate's capability/pool, or its field
     schema, before A's next assignment reconciliation.
  2. Verify a data mismatch causes reselection and a schema problem returns
     an error. Restore valid state for the next run.
  3. Let B claim the candidate and create its owned BMH/Secret; delete A
     while A still has that candidate's ExternalHostID. Repeat with the same
     BMI name but a recreated, different UID.
  4. Repeat deletion with A's `spec.networkAttachments` populated, a discovery
     Allocated condition, empty assigned HostClass, and no networking finalizer.
     Also vary HostClass/finalizer independently; enable the existing network
     configuration prerequisites so they cannot mask the gate under test.
- **Expected:** AssignHost receives A's persisted selector through context;
  no assignment labels or current catalog are used. Changed data is not
  claimed. Deleting A cannot power off/delete B's BMH, delete B's Secret,
  or clear B's NetBox owner. Ownership failure is surfaced and A's inventory
  finalizer is retained; candidate selection never grants release authority.
  Network-offboard shutdown requires both nonempty assigned HostClass and the
  networking finalizer, plus the existing configuration checks. Attachment
  specs or a discovery Allocated condition alone trigger no power/network
  operation. An owned, assigned positive control with both guards retains
  the existing offboard behavior; other backends' matching is unchanged.

#### TC-INT-025: Wait for BMH and Secret Absence Before Release

- **Setup:** A owns the NetBox claim, BMH ConsumerRef UID, and operator-managed
  Secret. Add test finalizers to hold BMH deletion, then Secret deletion;
  exercise normal BMI deletion and post-claim preparation compensation as
  separate cases. Envtest simulates Metal3 and finalizer completion.
- **Action:**
  1. Reconcile cleanup until BMH has deletionTimestamp but still exists;
     run several further reconciliations.
  2. Remove its test finalizer and observe BMH absence; then hold the Secret
     terminating and reconcile again.
  3. Remove the Secret finalizer and observe absence; change an unrelated
     NetBox field before the final GET, then reconcile release.
  4. In a separate run, change the NetBox owner before the final GET or cause
     a 412 on the final PATCH.
  5. Replace a same-named BMH/Secret between its ownership check and DELETE
     in separate runs; inspect Kubernetes deletion preconditions.
  6. Make the informer cache report NotFound while direct API reads show
     the BMH or Secret still present/terminating; also return stale ownership
     from the cache while the API reports a different owner UID.
  7. Reject the BMI update that records resource absence, restart, then allow
     the update and retry. Repeat for normal deletion and compensation.
- **Expected:** Accepting DELETE does not complete cleanup. While BMH exists,
  Secret and active NetBox owner remain; while Secret exists, NetBox owner
  remains. BMI finalizers and the claim persist across retries/restarts.
  Only after both resources are absent and the `*-ready` checkpoint is saved
  does the adapter re-GET, recheck A's UID, and PATCH staged/empty owner with
  the fresh ETag. Failed checkpoint persistence retains the claim. A changed owner
  prevents release; 412 requires another GET/ownership check. No pool,
  capability, or unrelated NetBox value is overwritten. UID/resourceVersion
  deletion preconditions protect replacement objects; a rejected DELETE
  leaves the NetBox claim and finalizer intact. Ownership and absence are
  decided by direct, uncached API reads: cache NotFound cannot permit release,
  and stale cached ownership cannot authorize deletion. Repeat after uncertain
  Kubernetes creates so a delayed informer cannot hide a created resource.

#### TC-INT-030: Completed Release Survives Crash and Immediate Reallocation

- **Setup:** A owns the claim/BMH/Secret and has its full saved binding.
  Exercise normal deletion and preparation compensation independently.
- **Action:**
  1. Clean A's resources, persist `*-ready`, then commit the NetBox release.
  2. Lose the release response or stop the controller before finalizer/binding
     completion. B then claims the same device and creates its own resources.
  3. Restart A's reconciliation. Repeat with B's resources not created yet,
     one resource present, or both present and clearly owned by B.
  4. Repeat with the checkpoint missing, an ownerless resource, or a resource
     still owned by A at either bound name; also deny direct API reads.
- **Expected:** The valid ready-checkpoint variants finish A's cleanup without
  any NetBox PATCH or BMH/Secret mutation; B's claim, metadata, and resources
  are unchanged. A's deleting BMI can remove its inventory finalizer; completed
  compensation can atomically clear A's binding/checkpoint before a new search.
  No ready checkpoint plus a different owner, ambiguous/old-owned resources,
  or unreadable state retains A's binding/finalizer with an error. Neither
  a host name nor another resource's matching name grants cleanup authority.

#### TC-INT-026: Trusted Tenant Metadata on Owned Per-Host Resources

- **Setup:** Two envtest BMIs have different trusted tenant and owner-reference
  metadata; vary the input owner-reference annotation to absent or incorrect.
  Their assignment labels include spoofed annotation/identity
  values; both selectors match separate eligible NetBox devices. Runtime
  fake API records all NetBox mutations without logging credentials.
- **Action:** Reconcile both allocations, inspect each BMH and BMC Secret,
  retry a same-owner allocation, then clean up one BMI. Include a conflicting
  resource with the same name and a different owner UID as a negative case.
- **Expected:** Every new per-host resource carries the correct
  `osac.openshift.io/tenant` and `osac.openshift.io/owner-reference` annotations
  from AllocationContext.ResourceAnnotations: trusted tenant and the actual
  BMI UID respectively. BMH ConsumerRef uses the
  context's actual name/namespace/UID; Secret ownership identifies that UID.
  Spoofed assignment labels never replace trusted metadata; foreign-owned
  resources are neither adopted nor deleted. No cross-namespace Kubernetes
  ownerReference is created. NetBox receives only status and
  the opaque instance UID, never tenant annotations, names, or namespaces.
- **Missing-context variant:** Omit the trusted tenant metadata or required
  instance identity from context; resource validation fails before a new
  claim or Kubernetes create rather than generating unowned resources.
- **Pool-controller variant:** Create a BareMetalPool with a real trusted
  tenant annotation and reconcile its child BMI. Verify the pool controller
  explicitly copies that tenant onto the BMI, and the BMI controller uses it
  for AllocationContext and per-host annotations. Repeat with the parent
  tenant annotation absent: no tenant is invented from a namespace, profile,
  or inventory label, and the NetBox path fails before any claim/create.
  Existing non-NetBox selector/matching behavior is retained.

### Helm Configuration and Deployment

#### TC-INT-027: Render and Install the NetBox Plus Metal3 Configuration

- **Location:** Chart checks alongside
  `osac/bare-metal-fulfillment-operator/charts/operator/` and
  `osac/osac-installer/charts/osac/`; use their existing `make helm-lint`
  conventions and the monorepo Kind installation harness for the install phase.
- **Setup:** Synthetic token/CA files and the canonical `bmf.netbox` and
  `bmf.metal3` values; rely on the chart's default Secret names unless the
  override case is being tested. Enable `global.services.bmaas.enabled`.
  Supply the umbrella schema's required nonempty service hostnames. Prepare a
  Kind cluster with Metal3 and a private TLS NetBox test endpoint with valid
  schema.
- **Action:**
  1. Run `helm lint` and `helm template` for the subchart and umbrella chart
     using protected file inputs and freshly rebuilt BMF chart dependencies.
     Enable only NetBox with `metal3.enabled` omitted/false. Repeat
     with CA omitted, renamed credential Secrets, different release/BMH
     namespaces, and NetBox disabled.
  2. Inspect rendered Secrets, Deployment volumes/mounts, inventory/management
     YAML, the namespace-scoped Secret Role/RoleBinding, and installer hook
     checks/RBAC. Repeat negative renders with missing token, endpoint or
     Metal3 namespace, HTTP endpoint, Metal3 inventory enabled, BCM enabled,
     or fake test backend enabled.
     Exercise BMaaS/hook enablement gates without broadening disabled paths.
  3. Install the valid configuration in Kind, observe successful operator
     initialization, allocate/delete one test BMI, then rotate the token through
     Helm and restart the operator as documented. Deny access from the render
     process to NetBox; runtime operator access remains on the private network.
- **Expected:** NetBox enablement alone produces exactly one inventory-config
  Secret (`type=netbox`, `hostClass=metal3`) and one management-config
  Secret (`type=metal3`). The separately named token Secret and optional CA
  Secret are also present when configured.
  A true Metal3 inventory flag together with NetBox fails rendering, as do
  BCM and fake-backend conflicts; exactly one inventory can be selected.
  Helm creates the named token Secret/key `token` and optional CA/key `ca.crt`,
  and `tokenFile`/`caCertFile` equal their read-only mount paths even when names
  are overridden. Runtime options contain no Secret-reference loading fields;
  omitting CA omits its Secret, path, volume, and mount. There are no duplicate
  resource names from Metal3 inventory templates. Runtime per-host BMC Secrets
  appear only after allocation and disappear after owner-checked release;
  Helm-owned backend Secrets remain. No cluster-wide Secret list/watch is
  introduced. The Role and injected manager use the same Metal3 namespace;
  the RoleBinding subject uses the operator release namespace. The existing
  cluster-scoped BMH permissions remain unchanged. NetBox enables the existing
  installer Metal3 prerequisite check and matching hook RBAC when that hook
  and BMaaS are enabled. Invalid values fail before installation, with no token output.
  NetBox-disabled Metal3 rendering stays unchanged. Rendering needs no NetBox
  connection; in-cluster initialization succeeds. A Secret-only upgrade is
  not assumed to roll the Deployment; the explicit restart loads the rotated
  token. Restricted test artifacts never print rendered secret values.

### Persisted Identity Across Reconciliation

#### TC-INT-028: Persist and Clear the Complete Host Binding Atomically

- **Location:** Extend the BMF envtest/controller patterns used by TC-INT-024.
- **Setup:** Candidate ID `42`, matching capabilities, and
  no BMH/Secret. Watch BMI updates and record NetBox writes. Inject a failed
  or resourceVersion-conflicting BMI update at candidate persistence.
- **Action:**
  1. Reconcile selection with the failed update; then allow a successful retry.
  2. Stop after binding persistence and restart before the first claim.
  3. Allow claim, restart again after its response is lost but before BMH creation,
     and reconcile until the BMH is ready.
  4. Separately arrange a confirmed other-owner race and observe reselection;
     also inject an uncertain PATCH and an invalid partial binding.
- **Expected:** No claim or per-host Kubernetes write precedes successful
  persistence of
  `externalHostID=baremetal/netbox-42` in one update; `externalHostName`
  remains empty and no device-ID annotation is written. Restart parses `42`
  from the saved host ID without a BMH/cache/name lookup for recovery;
  same-owner retry creates at most the one correctly named BMH/Secret pair.
  Ready assignment sets `hostClass=metal3`. Confirmed reselection clears the
  host binding; errors and uncertain writes retain it. Partial binding blocks
  mutation/reselection. Normal finalizer cleanup uses the saved binding until
  complete.

### Real NetBox Community API Semantics

These cases use the real API and independent fixture assertions; recording a
URL on a mock is insufficient. Run serially where schema changes would affect
other cases, use bounded polling, and clean up fields/devices/claims created
by each test. Every case runs against both Community 4.6.10 and 4.7.1; a missing
capability such as `If-Match` must fail compatibility, not skip the assertion.

#### TC-INT-029: Community ID Identity and Numeric-ID Recovery

- **Setup:** Real devices with ID `42` and IDs `43`/`99`, including named,
  empty-name, duplicate-name, case-equivalent-name, allocated, and unavailable
  variants. Register fabric servers as `netbox-42` and `netbox-43`; no server
  is registered under a raw NetBox device name. Include a replacement device
  with a new ID that reuses the old raw name.
- **Action:**
  1. Exercise FindFreeHost against each pinned Community release and capture
     the returned IDs and derived host names across list pages.
  2. Change or clear `device.name`, then retry selection and same-owner
     assignment/release.
  3. Save the binding for ID `42`, delete that device through the fixture
     administrator API, restart the adapter, and attempt recovery and release.
- **Expected:** Named, empty, duplicate, and case-equivalent NetBox names do
  not alter ID-derived names: ID `42` always maps to `netbox-42`, and ID `43`
  maps to `netbox-43`. Name changes do not force reselection or create a new
  BMH. Recovery and release GET/PATCH only `/api/dcim/devices/42/`; a 404
  retains the binding/finalizer and never touches the replacement ID. OSAC
  never writes device names.

#### TC-INT-015: Community Metadata Discovery and Pool Default

- **Setup:** Administrator creates all fixed fields and enough unrelated
  fields to force pagination, plus exact scalar capability fields. Create a
  device without setting `osac_managed` and a second with it explicitly true.
- **Action:**
  1. Request `GET /api/extras/custom-fields/?object_type=dcim.device` with a
     small page limit, following `next` until all relevant fields are found.
  2. Save sanitized metadata fixtures and read both devices through the API.
  3. Start the adapter and FindFreeHost for the matching capability.
- **Expected:** Actual `object_types`, `type`, and `filter_logic` shapes decode
  correctly using `type.value` and `filter_logic.value`. Field status is
  absent in 4.6.10 and active in 4.7.1; fields on
  later pages are found. The omitted pool value is Boolean false; only the
  explicitly managed device qualifies. OSAC sends no schema writes.

#### TC-INT-016: Community AND Semantics Across Distinct Fields

- **Setup:** Real devices include one exact shared-fixture match and decoys
  differing individually in `cpu_cores`, `gpu_model`, `memory_gb`, pool flag,
  native status, or owner. All schemas are valid and exact-filtered.
- **Action:**
  1. Issue the combined shared query directly to `/api/dcim/devices/` and
     collect all result pages before any adapter-side filtering.
  2. Run FindFreeHost with the same three selectors and inspect its query.
  3. Remove the matching device and repeat both calls.
- **Expected:** Real server returns only the one matching ID, proving AND
  across distinct custom fields and the fixed pool/status/owner predicates.
  Adapter selects that ID. With only decoys, both paths return no candidates;
  no partial-match device is claimed.

#### TC-INT-017: Community Empty-Owner Representations

- **Setup:** Three otherwise eligible devices: owner omitted when created,
  owner set to JSON null, and owner set to empty string. Add decoys with an
  actual owner and whitespace-only owner. Use real API writes; retain each
     read-back representation in artifacts.
- **Action:**
  1. Run the combined pool/status query with
     `cf_osac_instance_id__empty=true` directly and collect all IDs.
  2. Exercise FindFreeHost for each eligible device in isolation.
  3. If API creation normalizes missing/empty values, also seed a legacy
     omitted/empty stored owner through the isolated test database and repeat
     real API reads/filters; document the normalization rather than faking it.
- **Expected:** All three unassigned forms remain discoverable; populated
  and whitespace owners are excluded by local validation. Any representation
  excluded by the server but considered unassigned by the contract is a
  compatibility failure requiring a design decision, not a mock workaround.
  TC-UNIT-056 covers defensive decoding of every raw representation.

#### TC-INT-018: Community Invalid Schema Fails Before Device Query

- **Setup:** Valid runtime adapter and exact text field `placement_zone`;
  administrator successively removes it, binds it only to another model,
  disables its filter, changes to loose filtering, or replaces it with each
  unsupported schema type from TC-UNIT-051. Isolate each mutation.
  For 4.7.1, also hold a field in provisioning/deleting status using the
  isolated lifecycle fixture as necessary; read its real API metadata. The
  4.6.10 control has no status attribute.
- **Action:** Call FindFreeHost after each mutation while recording real
  metadata/device-list requests; also attempt startup with incompatible fixed
  pool/owner schema. Restore valid definitions before the next case.
- **Expected:** Each incompatible schema yields a configuration error before
  any device-list request, not a zero-capacity success. Startup rejects bad
  fixed schema; runtime searches see bad capability schema immediately.
  Present non-active field status fails before device listing; absent status
  in 4.6.10 is valid and is not treated as inactive.
  Unsupported schema that the pinned server itself rejects is recorded as
  such, with adapter rejection covered by TC-UNIT-051.

#### TC-INT-019: Community Scalar Filtering and Stored Choice Values

- **Setup:** Exact-filter integer, Boolean, text, and select fields; a select
  choice stores `a100` with label `NVIDIA A100`. Devices cover integer `0`,
  negatives, both int64 endpoints and adjacent values above 2^53; Boolean
  true/false; text with case/space differences; matching/different choices;
  omitted/null capabilities. Use isolated fields/rows where needed.
- **Action:** Query each supported scalar through both the real device API
  and FindFreeHost, then submit the invalid selector values from TC-UNIT-052
  through the adapter. Record raw API results before local validation. Assert
  select device values are strings in 4.6.10 and `{value,label}` objects in
  4.7.1; change only the choice's display label and repeat matching.
  Include text/select selectors with leading/trailing whitespace and exact
  `null` in the adapter-only negative cases; do not send them to the device API.
- **Expected:** Exact typed requests match only the corresponding stored
  value, including Boolean false and lossless integers. Missing/null fields
  do not match. Select queries use `a100`, never its label; local comparison
  extracts the exact stored string in both response shapes and label changes
  leave matching unchanged. Empty or malformed
  selector values, surrounding whitespace, and reserved text/select `null`
  fail before device listing; no sentinel lookup or normalization occurs.
  If the pinned API cannot store
  or filter a required boundary, record a compatibility failure for review.

#### TC-INT-020: Community Tags Are Independent and Metadata Survives

- **Setup:** Two identically eligible devices, one with no tags and one with
  unrelated tags including a legacy `managed-by-osac` tag; a third has the
  legacy tag but `osac_managed=false`. Include unrelated custom fields.
- **Action:**
  1. Query all candidates, add/remove unrelated tags as administrator, and
     repeat the same capability query.
  2. Claim one eligible device with AssignHost, retry as the same owner, then
     release with UnassignHost; snapshot real API state before/after each step.
  3. Administrator toggles the third device's pool Boolean to true and repeats
     the query without altering its capabilities or tags.
- **Expected:** The first two devices match independently of tags; the third
  matches only after admin opt-in. No tag query parameter is used. OSAC
  changes only native status and owner; pool, capability values, BMC
  address/boot-MAC metadata, unrelated fields, and tags remain intact.
  Runtime credential resolution makes no schema writes or
  pool/capability changes. Recorded PATCH bodies contain
  exactly `status` and `custom_fields.osac_instance_id`, proving the real
  Community API preserves other fields through its partial-update merge.

#### TC-INT-021: Community Conditional Claims and Release Races

- **Setup:** One real eligible device; two independent adapter calls for
  distinct instance IDs; a barrier allows both GETs to capture the same real
  ETag before conditional PATCH. Kubernetes BMH/Secret behavior may use envtest.
- **Action:**
  1. Release both PATCH calls concurrently with their captured `If-Match`.
  2. Read back owner/status; retry the winning assignment with the same owner.
  3. During release, administrator edits an unrelated field after GET and
     before PATCH, forcing a stale ETag; allow re-read and retry.
- **Expected:** Community server returns exactly one successful claim and
  one 412; the loser GETs ownership and confirms the winner's distinct UID
  before returning nil/reselecting. One owner and no loser-owned resources
  exist. Same-owner retry
  skips the claim PATCH and ensures BMH/Secret. Stale release fails with 412,
  then safely retries preserving the external edit after rechecking the
  requesting context UID. Invoke release using the losing UID too: owner
  remains the winner and no Kubernetes resource is deleted. Release waits
  for BMH and Secret absence before the final GET/conditional PATCH. A server that silently
  ignores `If-Match` fails the supported-version gate.
- **Delayed same-owner commit variant:** A controlled forwarding proxy holds
  an initial real conditional PATCH beyond the client timeout. The retry GET
  observes staged/empty state; forward the held PATCH and let it commit before
  forwarding the retry's stale conditional PATCH. NetBox must return 412 for
  that retry. Its ownership GET sees active/same UID and resumes BMH/Secret
  ensures while retaining ExternalHostID, with one committed claim and no
  reselection. The proxy controls timing; Community performs the real updates
  and ETag checks.
- **Other ownership-read variants:** An unrelated external edit that leaves
  the device clearly staged/empty makes a stale claim return 412 followed by
  nil/reselection. After a 412, block the ownership GET at the proxy or arrange
  an inconsistent status/owner through the administrator fixture; the adapter
  returns an error preserving ExternalHostID and performs no replacement
  claim or cleanup. Restore fixture state before the next variant.

#### TC-INT-022: Community Exact Escaped String Filtering

- **Setup:** Exact text field stores `&status=active`, `a+b`, `x=y`, Unicode,
  and `Lab A` on otherwise eligible devices; add active and case/space
  near-match decoys.
- **Action:** Send each selector through FindFreeHost and issue its encoded
  URL directly to the real API; inspect decoded query parameters and raw IDs.
  Separately submit surrounding-whitespace and exact `null` text/select
  selectors to the adapter and capture the device-request count.
- **Expected:** Exact stored strings survive encoding and comparison;
  `&status=active` is data in one custom-field parameter, never another
  status predicate. Real API results and the adapter exclude decoys; no trim
  or case normalization changes the meaning.
  Invalid whitespace/sentinel values return configuration errors with zero
  device-list requests; they cannot select unset/null capability fields.

#### TC-INT-023: Community Capability Added After Startup

- **Setup:** Adapter running against real Community API with no
  `placement_zone` custom field; keep the same adapter process for the test.
- **Action:** Administrator creates an exact text field on `dcim.device`,
  sets `placement_zone="west"` on an eligible device, and introduces a new
  instance type with that selector. Call FindFreeHost with the newly resolved
  map, then change schema filtering to loose and repeat; restore exact and retry.
- **Expected:** New capability works without restart or a whitelist update.
  Loose schema returns a configuration error before device listing; restoring
  exact schema permits matching on the next search. Schema refresh uses real
  current metadata, not fixtures captured at startup.

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

#### TC-E2E-001: Allocate and Provision Host Against NetBox

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
- **Verification: Administrator Metadata Preservation After Provisioning**
  - After provisioning succeeds, verify:
    - Device retains Boolean `osac_managed=true` and original typed
      capabilities (`cpu_cores=16`, `gpu_model="a100"`, `memory_gb=128`)
    - Device has status=active and osac_instance_id set (custom field identifies the owner; status identifies allocation state)
    - Unrelated custom fields and tags are unchanged
- **Deployment variants:** Repeat this tenant create/provision/delete flow
  with mirrored/preloaded dependencies and public-network egress blocked;
  NetBox remains reachable through private HTTPS. Initialization and lifecycle
  must succeed without Wizard connectivity probes or Internet access. Run
  the same public API workflow in a separate existing Metal3-inventory
  configuration as a transparency baseline; inventory-specific setup differs,
  but tenant-facing lifecycle semantics do not.

#### TC-E2E-002: Deallocate and Reuse Host

- **Setup:** Host allocated and provisioned from NetBox pool
- **Action:**
  1. Delete BareMetalInstance
  2. Wait for cleanup
  3. Create new BareMetalInstance with the same custom-field capability selector
- **Expected:**
  1. Host deallocated cleanly (power off, BMH deleted)
  2. Device status restored to staged; host returned to NetBox available pool
  3. New request allocates same or different host
  4. No orphaned state
  5. Pool/capability values and unrelated metadata are unchanged after release

#### TC-E2E-012: ID-Derived BMH and AAP Hostname Through Provisioning, Networking, and Restart

- **Location:** Extend the patterns in
  `osac/tests/e2e/bmaas/regression/networking/test_bmaas_networking.py` and its
  `conftest.py`, using CLI/gRPC/Kubernetes and `wait_for_bmi_*`/`wait_for_bmh_*`
  helpers, `bmh_namespace`, and `bmi_template` fixtures. Exercise
  the existing AAP `playbook_osac_move_network_attachment.yml` and
  `playbook_osac_query_dhcp_lease.yml`; use the configured fabric test environment.
- **Setup:** Real NetBox device ID `42` with raw name `worker-01`, matching
  capabilities and BMC address/boot-MAC metadata; create a system-scoped OSAC
  Secret labeled `osac.openshift.io/netbox-device-42: "true"`; use a fabric
  server registered as `netbox-42`.
  Also prepare an otherwise equivalent device with ID `43`, an empty name, and
  a fabric server registered as `netbox-43`. No server is registered under a
  raw NetBox device name.
  Configure the standard Metal3 BMaaS template, network attachments/subnets,
  and controlled DHCP lease fixtures. Use the existing test-only proxy to pause the first claim
  after the BMI binding is saved, without changing production behavior.
- **Action:**
  1. Create a tenant BMI; wait for namespace-qualified ID-derived host-ID
     persistence. Restart
     BMF before BMH creation, release the proxy barrier, and wait for provisioning.
  2. Inspect `hostClass`, BMH name, completed AAP provisioning/network jobs,
     resolved server ports, and DHCP lease/IP results.
  3. Exercise DHCP with its normal inspected NIC MAC. Then invoke the existing
     DHCP playbook against the same real fixture with an empty attachment-MAC
     map to test its supported name fallback; record the job result. Also
     exercise the network playbook with `externalHostName` omitted from its
     input fixture to verify the host-ID suffix fallback, without editing the BMI.
  4. Repeat the allocation, restart, and networking flow for the unnamed
     device; assert empty `ExternalHostName`, `externalHostID=baremetal/netbox-43`,
     and BMH `netbox-43`.
  5. Delete through the API and wait for network offboard, BMH/Secret deletion,
     and NetBox release. Repeat a negative fixture with a missing fabric name.
- **Expected:** The persisted host ID is `baremetal/netbox-42`, BMH name is
  `netbox-42`, `externalHostName` is empty, and no device-ID annotation exists;
  all survive restart. `hostClass=metal3` selects the existing provisioning
  role and finds the BMH. Both AAP networking playbooks resolve `netbox-42`
  from the `externalHostID` fallback and target the same fabric server/port;
  DHCP finds the expected lease by MAC and, when no MAC is supplied, by name.
  Deletion offboards that server before normal owner-checked cleanup.
  The unnamed-device run uses the registered `netbox-43` value and BMH
  `netbox-43`. Missing fabric correspondence reports the existing networking failure,
  never chooses a similarly named server or rewrites the device name. Remove
  all test claims/resources via their owning fixture cleanup. This configured-
  fabric scenario is required acceptance coverage, not a claim that NetBox
  requires a particular fabric product in every deployment.

#### TC-E2E-003: Custom-Field Host Matching in Tenant Workflow

- **Setup:** Managed staged devices have integer `cpu_cores=16` or `8`, text
  `gpu_model="a100"` or `"h100"`, and integer `memory_gb=128` or `64`; include
  devices matching only subsets of the requested capabilities
- **Action:**
  1. Create a published instance type with selector
     `{"cpu_cores":"16","gpu_model":"a100","memory_gb":"128"}`
  2. Submit a tenant request referencing it; verify fulfillment-service copies
     all exact keys and meaningful values into the immutable BMI selector
  3. Verify allocation matched correctly
- **Expected:**
  1. Host has all three requested typed values and `osac_managed=true`
  2. Devices with any differing/missing capability are not allocated
  3. Tenant sees successful allocation

### Inventory Exhaustion Edge Case

#### TC-E2E-004: Allocate, Exhaust, Recover (Inventory Overflow Handling)

- **Setup:** Kind cluster with N available devices; establish N from direct
  NetBox fixture reads before any host allocation
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

#### TC-E2E-005: Custom-Field Concurrent Stress

- **Setup:** Real NetBox with 50 managed staged devices, empty owners, and
  integer `cpu_cores=16`; 20 concurrent tenants request `{"cpu_cores":"16"}`
- **Action:** All 20 reconcile loops fire concurrently
- **Expected:** Exactly 20 devices have distinct requesting owners; 30 remain
  available, with no duplicate assignment or orphaned resources. A naturally
  occurring 412 is not required; TC-INT-021 and TC-E2E-006 control the race.

#### TC-E2E-011: Concurrent Requests Exceed Available Capacity

- **Setup:** Real NetBox with exactly 10 managed, staged, owner-empty devices
  matching `{"cpu_cores":"16","gpu_model":"a100","memory_gb":"128"}`;
  include unrelated/nonmatching devices outside that capacity.
- **Action:** Create 20 BMI requests concurrently using the existing tenant
  fixtures; wait with bounded polling for 10 assignments and no-match
  conditions on the remaining 10, then delete all requests.
- **Expected:** Exactly 10 distinct devices have 10 distinct owners; the
  other 10 requests continue the existing no-host retry behavior. No outside
  device is claimed and no duplicate BMH or orphaned Secret exists. Cleanup
  clears owners, restores staged status, and preserves administrator metadata.

### Observability and Diagnostics

#### TC-E2E-006: Prometheus Metrics — Conditional-Claim Race Detection

- **Setup:** Operator running; Prometheus scraping; real NetBox with one eligible
  device. A test-only forwarding proxy can pause the operator's next claim
  PATCH before forwarding it, after the operator's eligibility GET completed.
  An administrator fixture client reaches NetBox directly. Record initial
  assignment counters; the proxy must not log credentials or request bodies.
- **Action:**
  1. Submit one tenant request and wait until the proxy holds its claim PATCH.
  2. With the fixture client, GET the device and conditionally PATCH it to
     `status=active` and a distinct synthetic owner `fixture-competitor`, using
     that GET's ETag. Assert the fixture's real NetBox PATCH succeeds.
  3. Forward the held operator PATCH unchanged. Real NetBox must return 412;
     the operator's ownership GET observes the competing owner. Scrape metrics
     and inspect the BMI and per-host Kubernetes resources.
  4. Clear only the fixture's own claim with a fresh owner check and conditional
     PATCH. Wait for OSAC's normal polling to allocate the now-available device.
     Delete the tenant request through normal cleanup. A test finalizer must
     clear a remaining fixture claim on failure without clearing an OSAC owner.
- **Expected:**
  1. The controlled conflict increments
     `osac_netbox_assignment_attempts_total{result="race"}` by one. While the
     fixture owns the host, OSAC does not overwrite it or create a BMH/Secret.
  2. After fixture release, the success counter increases, the real device has
     the requesting BMI UID, and exactly that BMI's BMH/Secret are present.
     Readiness retries may add further successful AssignHost calls.
  3. Cleanup leaves no owner, BMH, or per-host Secret. The 412 is produced by
     real NetBox, not fabricated by the proxy. Two-OSAC-request contention is
     covered independently by TC-INT-007, TC-INT-021 and TC-E2E-005/011.

#### TC-E2E-007: Assignment Counters During No-Host Exhaustion

- **Setup:** Operator running; real NetBox with 8 available devices
- **Action:**
  1. Create 10 concurrent BareMetalInstance objects requesting the same capability selector
  2. 8 succeed (allocated)
  3. 2 observe no matching hosts (FindFreeHost returns nil, nil)
- **Expected:**
  1. Direct NetBox fixture reads show eight distinct devices assigned to
     eight distinct owners; the two waiting BMIs have no assigned device
  2. `osac_netbox_assignment_attempts_total{result="success"}` increases for
     successful AssignHost calls; any same-owner readiness retries are
     accounted for separately from the eight distinct assignments
  3. No `osac_netbox_assignment_attempts_total{result="success"}` increment
     occurs for the two requests that never reach AssignHost
  4. A no-match reconciliation is reported through the BareMetalInstance
     condition and requeue interval; it is not an assignment attempt or a
     production inventory-capacity measurement

#### TC-E2E-008: Inventory Exhaustion — Indefinite Retry with Condition

- **Setup:** 10 BareMetalInstance objects with no matching devices in NetBox
- **Action:**
  1. Create 10 BareMetalInstance CRs requesting a valid, pre-created
     capability schema whose requested value has no matching device
  2. Wait for first reconciliation cycle
  3. Observe BareMetalInstance status
  4. Add matching devices to NetBox
  5. Wait for next reconciliation
- **Expected:**
  1. Initial: All 10 instances have `phase=Failed`, condition `HostConditionAllocated=False` with `reason=NoMatchingHosts`
  2. No Kubernetes Event is required; the existing status condition is the
     contract for this path
  3. Read-only proxy request counts show repeated device searches while
     capacity is absent. Polling uses `NoFreeHostsPollIntervalDuration`
     (default 30s); the exact reconcile return is covered in TC-INT-010,
     not inferred from wall-clock scheduling.
  4. After capacity is added: Next reconciliation succeeds; instances move to
     the existing allocation phase
  5. The tenant-facing status/message remains the generic "No hosts available"
     contract and does not mention NetBox
  6. Metrics show successful assignment attempts only after capacity is available

#### TC-E2E-009: Allocation Condition and Requeue on No Matching Hosts

- **Setup:** BareMetalInstance allocating with valid capability schema but no
  matching NetBox devices. Use a test proxy with a count-only device-search
  observer and the existing bounded pytest polling helpers.
- **Action:**
  1. Poll the Kubernetes API for `HostConditionAllocated=False` with reason
     `NoMatchingHosts`; record the device-search count.
  2. Without editing the BMI or restarting the operator, wait for that count
     to increase within the suite's timeout (at least two configured poll
     intervals plus scheduling tolerance).
  3. Add one device matching the persisted selector through the administrator
     fixture, then wait for allocation with the existing BMI lifecycle helpers.
- **Expected:**
  1. `phase=Failed` and `HostConditionAllocated=False` with reason
     `NoMatchingHosts` while capacity is absent; no BMH or per-host Secret exists.
  2. Another device search occurs without a user retry. TC-INT-010 checks the
     exact internal `RequeueAfter`; this scenario checks observable polling.
  3. After capacity is added, the BMI receives an ExternalHostID and allocated
     condition; the device owner equals its UID. Delete the BMI and verify
     normal release cleanup.

#### TC-E2E-010: Structured Logs

- **Setup:** Operator running; logs captured
- **Action:**
  1. Create allocation
  2. Trigger invalid selector/schema and API-error paths with recognizable
     synthetic keys, values, tenant metadata, and credentials
  3. Inspect captured adapter and shared controller logs for relevant entries
- **Expected:**
  1. Logs include:
     - `host_selector_key_count`: number of resolved selector keys
     - `query_capability_filter_count`: capability filters only, excluding
       fixed pool/status/owner filters (three requested capabilities gives three)
     - `matching_devices_count`: count of returned candidates that pass local
       pool/status/owner and typed capability validation
     - `host_selected`: boolean result of candidate selection
  2. Selector keys/values, raw query strings, host IDs, BareMetalInstance UIDs, tenant
     names, credentials, and secrets are absent from logs
  3. Error logs include diagnostic info (e.g., "custom_field not found") but no API responses

---

## Test Coverage Summary

Counts refer to scenario headings, not parameter rows or claims of executed tests.

| Layer | Component | Count | Coverage |
|-------|-----------|-------|----------|
| Unit | Configuration and initialization | 8 | URL/TLS, Secrets, fixed schema, selector names and values |
| Unit | Startup validation | 1 | NetBox requires Metal3 management |
| Unit | HTTP client | 10 | Auth, retries, error handling, credentials, 412 distinction |
| Unit | Concurrent access | 4 | First writer, stale ETag, concurrent custom-field searches |
| Unit | Typed matching and query construction | 7 | Exact keys/values, reserved keys, equality, extra fields |
| Unit | Capability schema and defensive validation | 9 | Pagination, refresh, invalid schema/values/status, typed candidates, escaping, preservation, owner/pool forms, select response shapes |
| Unit | Fulfillment-service projection | 1 | Exact projection for new types with referenced selector sources unchanged |
| Unit | Search isolation and remaining candidates | 3 | Profile-scoped selection, newly claimed candidates, no fallback to unrelated capacity |
| Unit | Pool and status filtering | 4 | Managed Boolean, availability, owner, pagination |
| Unit | Assignment and context | 8 | Separate AllocationContext, claim-time revalidation, success, same-owner retry, race, crash recovery, ETag |
| Unit | Release | 6 | Requester/owner UID guards, cleanup checkpoints, idempotency, 412 retry |
| Unit | NIC discovery | 1 | Existing BMH hardware-data delegation |
| Unit | Device ID and recovery binding | 3 | Kubernetes-safe ID-derived names, namespace-qualified host IDs, numeric-ID recovery, device-name changes |
| **Unit total** | **64 BMF + 1 fulfillment-service** | **65** | |
| Integration | BMF envtest | 19 | Allocation/release, rollback, network/auth recovery, startup, metrics, matching, dynamic profiles, backend regression, persisted candidates, async cleanup, trusted annotations, atomic host-ID binding, release/reallocation recovery |
| Integration | Helm render/install | 1 | File paths/mounts, Secret ownership, one-flag Metal3 wiring, namespace/RBAC/hooks, conflicts, explicit restart |
| Integration | Real Community API | 10 | Metadata/defaults, AND, empty owners, schema, scalar types, preservation/unrelated metadata, concurrency, escaping, new capabilities, ID identity and numeric-ID recovery |
| **Integration total** | **19 envtest + 1 Helm + 10 real API** | **30** | |
| E2E | Tenant workflows | 4 | Provision, release/reuse, selector matching, ID-derived BMH names through networking/DHCP/restart |
| E2E | Inventory exhaustion | 3 | Overflow recovery, indefinite retry, condition/requeue |
| E2E | Concurrent stress | 2 | 20 requests/50 hosts and 20 requests/10 hosts |
| E2E | Observability | 3 | Same-host race metrics, exhaustion metrics, sanitized logs |
| **E2E total** | | **12** | |
| **Grand total** | **65 Unit + 30 Integration + 12 E2E** | **107** | |

All 107 scenarios target automation. Unit scenarios use the owning Go package's
test framework; envtest exercises the BMF controller; real API cases exercise
the adapter and pinned Community server; E2E uses the existing pytest suite.
Allocation, ownership, metadata preservation, and credential-safety assertions
are release-critical. Parameterized negative cases remain part of their
parent scenario count.

---

## Test Case Reference (TC-IDs)

Each scenario has one matching heading and index entry. Original IDs are
preserved where the behavior remains in scope; new IDs extend each layer.
TC-INT-013 gives the existing network-recovery body an ID, and TC-E2E-011
supplies the detailed capacity-stress scenario previously mentioned only in
the summary.

### Unit Tests (65 tests: TC-UNIT-001 to TC-UNIT-065)

- TC-UNIT-001: Parse Valid NetBox Configuration
- TC-UNIT-002: Reject Missing Endpoint URL
- TC-UNIT-003: Load API Token from Mounted File
- TC-UNIT-004: Load CA Certificate from Optional Mounted File
- TC-UNIT-005: Validate Fixed Integration Custom Field Schema
- TC-UNIT-006: TLS Validation Failure on Invalid Certificate
- TC-UNIT-007: HostSelector Resolution and Custom-Field Extraction
- TC-UNIT-008: Custom-Field Name Syntax and Length Validation
- TC-UNIT-009: Validate Co-Requirement — NetBox Requires Metal3 Management
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
- TC-UNIT-020: First Writer Wins
- TC-UNIT-021: Second Writer Gets 412
- TC-UNIT-022: Race Sequence with Goroutines
- TC-UNIT-023: Concurrent Custom-Field FindFreeHost
- TC-UNIT-024: Custom-Field Pass-Through from Resolved HostSelector
- TC-UNIT-025: Selector Values Determine the Match
- TC-UNIT-026: Selector Key Is Not Rewritten
- TC-UNIT-027: Reject Reserved Names and Lookup Injection
- TC-UNIT-028: Server-Side Custom-Field Filtering — Matching Device
- TC-UNIT-029: Server-Side Custom-Field Filtering — Different Value
- TC-UNIT-030: Superset Match — Extra Fields and Unrelated Tags
- TC-UNIT-031: Search Remains Scoped to the Requested Profile
- TC-UNIT-032: Next Search Excludes the Newly Claimed Candidate
- TC-UNIT-033: No Match Does Not Fall Back to Unrelated Capacity
- TC-UNIT-034: Query Returns Only Staged Devices with Managed Pool Flag
- TC-UNIT-035: No Candidates — All Devices Already Assigned
- TC-UNIT-036: No Candidates — Empty Device Pool
- TC-UNIT-037: Pagination of Large Device Lists
- TC-UNIT-038: Successful Assignment
- TC-UNIT-039: Idempotent Retry — Same Assignment ID
- TC-UNIT-040: Race Condition — Device Assigned to Different Instance
- TC-UNIT-041: Crash Recovery — Assignment Persisted
- TC-UNIT-042: ETag Capture on Read
- TC-UNIT-043: If-Match Sent on PATCH
- TC-UNIT-044: Successful Deassignment
- TC-UNIT-045: Idempotent Retry — Already Unassigned
- TC-UNIT-046: Ownership Guard — BMH Belongs to Different Instance
- TC-UNIT-047: 412 During Unassignment — Retry from Read
- TC-UNIT-048: GetHostNICs Delegates to BMH Hardware Data
- TC-UNIT-049: Paginated Metadata Discovery and Wire Shapes
- TC-UNIT-050: Refresh Capability Schema on Every Search
- TC-UNIT-051: Invalid Requested Schema Is Not Empty Capacity
- TC-UNIT-052: Supported Scalar Values and Invalid Inputs
- TC-UNIT-053: Revalidate Every Returned Typed Capability
- TC-UNIT-054: Escape Exact Values Without Query Injection
- TC-UNIT-055: Claim and Release Preserve Administrator Metadata
- TC-UNIT-056: Empty Owner Forms and Strict Pool Membership
- TC-UNIT-057: Project New Catalog Types with Existing Sources Unchanged
- TC-UNIT-058: Select Stored Values Across Community Response Shapes
- TC-UNIT-059: AllocationContext Is Separate from Assignment Labels
- TC-UNIT-060: Revalidate Persisted Candidate Before a New Claim
- TC-UNIT-061: Requester UID Authorizes Every Release or Compensation
- TC-UNIT-062: Preserve Valid Names and Reject Ambiguous Candidates
- TC-UNIT-063: Use Persisted Numeric Identity Independently of Hostname
- TC-UNIT-064: Rename or Replacement Cannot Redirect Recovery
- TC-UNIT-065: Cleanup Intent and Absence Checkpoints Gate Side Effects

### Integration Tests (30 tests: TC-INT-001 to TC-INT-030)

- TC-INT-001: Allocate Host via BareMetalInstance
- TC-INT-002: Deallocate Host via BareMetalInstance Deletion
- TC-INT-003: Host Preparation Failure Rolls Back the Claim
- TC-INT-004: Permanent Auth Failure
- TC-INT-005: Schema Validation Failure on Startup
- TC-INT-006: Configuration Update After Operator Restart
- TC-INT-007: Concurrent Assignment with ETag Protection
- TC-INT-008: Assignment and API Error Counters
- TC-INT-009: Server-Side Custom-Field Filtering Verification
- TC-INT-010: Capability Mismatch — Zero Results
- TC-INT-011: Capability Value Update on Device
- TC-INT-012: Cross-Backend Non-Regression
- TC-INT-013: Network Failure Recovery
- TC-INT-014: New Instance Type After Operator Startup
- TC-INT-015: Community Metadata Discovery and Pool Default
- TC-INT-016: Community AND Semantics Across Distinct Fields
- TC-INT-017: Community Empty-Owner Representations
- TC-INT-018: Community Invalid Schema Fails Before Device Query
- TC-INT-019: Community Scalar Filtering and Stored Choice Values
- TC-INT-020: Community Tags Are Independent and Metadata Survives
- TC-INT-021: Community Conditional Claims and Release Races
- TC-INT-022: Community Exact Escaped String Filtering
- TC-INT-023: Community Capability Added After Startup
- TC-INT-024: Persisted Candidate Revalidation and Wrong-Requester Deletion
- TC-INT-025: Wait for BMH and Secret Absence Before Release
- TC-INT-026: Trusted Tenant Metadata on Owned Per-Host Resources
- TC-INT-027: Render and Install the NetBox Plus Metal3 Configuration
- TC-INT-028: Persist and Clear the Complete Host Binding Atomically
- TC-INT-029: Community Name Uniqueness and Numeric-ID Recovery
- TC-INT-030: Completed Release Survives Crash and Immediate Reallocation

### E2E Tests (12 tests: TC-E2E-001 to TC-E2E-012)

- TC-E2E-001: Allocate and Provision Host Against NetBox
- TC-E2E-002: Deallocate and Reuse Host
- TC-E2E-003: Custom-Field Host Matching in Tenant Workflow
- TC-E2E-004: Allocate, Exhaust, Recover (Inventory Overflow Handling)
- TC-E2E-005: Custom-Field Concurrent Stress
- TC-E2E-006: Prometheus Metrics — Conditional-Claim Race Detection
- TC-E2E-007: Assignment Counters During No-Host Exhaustion
- TC-E2E-008: Inventory Exhaustion — Indefinite Retry with Condition
- TC-E2E-009: Allocation Condition and Requeue on No Matching Hosts
- TC-E2E-010: Structured Logs
- TC-E2E-011: Concurrent Requests Exceed Available Capacity
- TC-E2E-012: Location-Qualified BMH and Provider Hostname Through Provisioning, Networking, and Restart

---

## BMC/BMH Lifecycle Test Coverage

The NetBox adapter coordinates with the existing BMH lifecycle manager; it does not implement Metal3 power control, inspection, OS provisioning, or readiness transitions itself:

- **BMC credential resolution:** Assignment reads the NetBox BMC address and boot-MAC fields, constructs the device label `osac.openshift.io/netbox-device-<id>`, and requires exactly one matching system-scoped Secret through the OSAC Secret API. TC-INT-001 verifies label-based resolution, including reuse of one Secret for multiple devices; TC-UNIT-005 covers NetBox schema and TC-UNIT-038 covers Secret/metadata validation before claiming.
- **BMC Secret creation:** The adapter ensures an operator-managed runtime Secret with the resolved username/password, requesting owner UID, and trusted tenant annotations. TC-INT-001 verifies creation; TC-INT-026 verifies metadata and isolation; TC-INT-025 verifies completed deletion before release while the source OSAC Secret remains.
- **BMH lifecycle:** TC-UNIT-059 to TC-UNIT-061 and TC-INT-024 to TC-INT-026 cover AllocationContext, claim-time revalidation, UID authorization, and asynchronous cleanup. TC-INT-001 to TC-INT-003 retain create/cleanup/rollback coverage; Metal3 remains responsible for provisioning and readiness. TC-UNIT-048 verifies NIC delegation.

---

## Requirement Traceability

The PRD uses In Scope bullets and persona stories rather than FR/AC numbers.
These mappings cover those requirements and the custom-field selection
contract; they do not claim verification against unprovided Jira task ACs.

| Requirement / acceptance boundary | Detailed scenarios |
|-----------------------------------|--------------------|
| Admin config, secure token/CA, startup and actionable errors | TC-UNIT-001 to TC-UNIT-019; TC-INT-004 to TC-INT-006; TC-INT-013; TC-INT-027 |
| Exact capability selection and selector projection | TC-UNIT-007 to TC-UNIT-008; TC-UNIT-024 to TC-UNIT-030; TC-UNIT-049 to TC-UNIT-054; TC-UNIT-057 to TC-UNIT-058; TC-INT-009 to TC-INT-011; TC-INT-014 to TC-INT-019; TC-INT-022 to TC-INT-023; TC-E2E-003 |
| Pool membership, empty owner, native status, profile-scoped selection | TC-UNIT-031 to TC-UNIT-037; TC-UNIT-056; TC-INT-015 to TC-INT-017 |
| Safe concurrent claims | TC-UNIT-018 to TC-UNIT-023; TC-UNIT-040; TC-UNIT-042 to TC-UNIT-043; TC-INT-007; TC-INT-021; TC-E2E-005 to TC-E2E-006; TC-E2E-011 |
| Provision/deprovision, retry/crash recovery, preparation rollback | TC-UNIT-038 to TC-UNIT-048; TC-INT-001 to TC-INT-003; TC-INT-021; TC-E2E-001 to TC-E2E-002 |
| Administrator controls pool/capabilities; unrelated metadata survives | TC-UNIT-055; TC-INT-002; TC-INT-020; TC-E2E-001 to TC-E2E-002 |
| Persisted context, claim revalidation, requester UID, completed cleanup, tenant annotations | TC-UNIT-059 to TC-UNIT-061; TC-INT-024 to TC-INT-026 |
| ID-derived BMH name, durable host ID, Metal3 namespace, and AAP hostname consumers | TC-UNIT-009; TC-UNIT-057; TC-UNIT-062 to TC-UNIT-064; TC-INT-001; TC-INT-027 to TC-INT-029; TC-E2E-012 |
| Persisted compensation/release checkpoints and immediate reallocation | TC-UNIT-047; TC-UNIT-065; TC-INT-003; TC-INT-025; TC-INT-030 |
| Tenant transparency and cross-backend non-regression | TC-INT-012; TC-E2E-001 to TC-E2E-003 |
| Generic no-host status, polling, capacity recovery | TC-INT-010; TC-E2E-004; TC-E2E-007 to TC-E2E-009; TC-E2E-011 |
| Metrics, sanitized diagnostics, no tenant/credential data exposure | TC-UNIT-003; TC-UNIT-017; TC-UNIT-055; TC-INT-001; TC-INT-004; TC-INT-008; TC-E2E-006 to TC-E2E-010 |

## Gaps and Compatibility Decisions

- The source-audited Community matrix is 4.6.10 and 4.7.1. Runtime validation
  in TC-INT-015 through TC-INT-023 remains an implementation requirement;
  source inspection is not a test pass. Fixtures must record immutable image
  digests. A semantic mismatch fails compatibility rather than being hidden
  by a mock or skipped assertion.
- AllocationContext requires implementation changes tested by TC-UNIT-059 to
  TC-UNIT-061 and TC-INT-024 to TC-INT-026. Fulfillment still re-resolves
  mutable catalog sources: keep referenced instance types/templates unchanged
  and create new identities for new selectors. TC-UNIT-057 covers that
  supported workflow, not a fix for editing/deleting/recreating live sources.
- TC-INT-027 covers Helm rendering and deployment, including chart-owned
  versus runtime Secrets, file-path loading, automatic Metal3 management,
  installer hooks, and explicit restart after rotation. Optional Wizard use
  follows the existing schema-only mechanism; it adds no live NetBox probe.
- ID-derived name validation and the existing namespace-qualified host-ID
  binding require implementation and runtime coverage in TC-UNIT-062 to
  TC-UNIT-064 and TC-INT-028 to TC-INT-029. TC-UNIT-057 verifies fulfillment
  preserves that host ID. TC-E2E-012 covers the existing AAP/fabric hostname
  consumers. NetBox device-name changes do not change the BMH identity;
  endpoint/namespace changes and migrations from the old location/name contract
  require draining pending/active BMIs.
- Restart-safe cleanup requires the controller-owned cleanup annotation and
  typed preparation/checkpoint errors. TC-UNIT-065 and TC-INT-003/025/030
  cover persistence failures, rollback routing, and completion after release
  followed by reallocation; these are new implementation work, not existing
  controller guarantees.

## Success Criteria

All **107 planned test scenarios** must pass before OSAC-1610 is considered
complete, and the gaps/compatibility decisions above must be resolved.

| Layer / harness | Planned count | Test IDs |
|-----------------|---------------|----------|
| Unit (BMF and fulfillment-service) | 65 | TC-UNIT-001 to TC-UNIT-065 |
| BMF envtest integration | 19 | TC-INT-001 to TC-INT-014; TC-INT-024 to TC-INT-026; TC-INT-028; TC-INT-030 |
| Helm render/install integration | 1 | TC-INT-027 |
| Real NetBox Community API integration | 10 | TC-INT-015 to TC-INT-023; TC-INT-029 |
| E2E | 12 | TC-E2E-001 to TC-E2E-012 |
| **Total** | **107** | **65 Unit + 30 Integration + 12 E2E** |

The real API gate must prove combined equality filters, empty-owner forms,
metadata/value semantics, preservation, and conditional updates on every
supported pin. E2E must show exactly 10 assignments for 20 concurrent requests
against 10 matching hosts, with safe retries and no orphaned resources.
Logs must contain no selector values, tenant identifiers, UIDs, credentials,
or raw API responses. The scenario index must have zero missing, duplicate,
or index-only IDs.

These are planned coverage targets, not pass-rate claims. This documentation
change does not execute or implement the runtime scenarios.
