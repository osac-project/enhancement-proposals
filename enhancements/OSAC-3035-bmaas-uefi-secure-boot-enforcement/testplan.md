# Testplan — OSAC-3035

## Overview

- **Feature:** OSAC-3035 — BMaaS UEFI Secure Boot Enforcement
- **Total test cases:** 42 (19 single cases plus 23 parameterized rows)
- **Requirements with planned cases:** 10 of 10; current CaaS workers reuse the
  origin-independent `PREFERRED` BMI cases and do not expose `REQUIRED`
  selection
- **Interface changes covered:** 8 of 8 active changes (IC-1–IC-5,
  IC-7–IC-9); retired IC-6 has no case
- **Execution status:** Planning only; no implementation tests have run.
- **Provider-gated cases:** 3 of 42 cases (`TC-FR3-04`, `TC-FR7-03`, and
  `TC-FR7-04`) are deferred or blocked until a backend supports enabled
  requests and passes provider-specific qualification.

`[DEV]` owns Unit, Envtest, component-integration, and Contract coverage for
changed implementation. `[QE]` owns deployed cross-component journeys. The
matrix follows [Integration testing](https://github.com/osac-project/osac/blob/main/docs/INTEGRATION-TESTING.md) and
the affected components' touched-area maps.

Story and acceptance-criterion keys are intentionally absent because
decomposition is deferred. Requirement, interface, owner, and test-case
mappings are complete for the shared BMI contract. CaaS service-level controls,
including `REQUIRED` selection, are out of scope and are not claimed as a
current test boundary.

## Coverage and Execution Matrix

### Current implementation boundaries

| Row | Component and changed behavior | Requirements / interfaces | Tier / owner | Test cases | Suite or proposed location |
|---|---|---|---|---|---|
| E1 | `fulfillment-service`: optional image declaration, mutable declaration lifecycles, defaulting, resolution, exhaustive blockers, BMI immutability, and compatibility | FR-1–FR-5, FR-6, NFR-1, NFR-3 / IC-1–IC-5 | Unit / `[DEV]` | TC-FR1-01, TC-FR2-01–03, TC-FR3-01–03, TC-FR4-01, TC-FR6-01–02, TC-NFR1-01–02, TC-NFR3-01 | Existing `internal/servers`, `internal/validation`, and CLI unit suites; new cases proposed |
| E2 | `fulfillment-service`: deployed API/CLI persistence, shared-image update authorization, reference-independent declaration updates, and output | FR-1, FR-2, FR-5, FR-6, NFR-1 / IC-1, IC-2, IC-4 | Component integration / `[DEV]` | TC-FR1-02, TC-FR2-02–03, TC-FR6-01–02, TC-NFR1-01 | Existing `it/` and CLI harness; new cases proposed |
| E3 | `fulfillment-service`: BMI reconciler policy projection, legacy hash preservation, status/failure mapping | FR-5, FR-7, NFR-1, NFR-3 / IC-7, IC-8 | Unit / `[DEV]` | TC-FR7-01–02, TC-NFR1-02, TC-NFR3-01 | Existing `internal/controllers/baremetalinstance` suites; new cases proposed |
| E4 | `bare-metal-fulfillment-operator`: provider-path capability results for Metal3, BCM, NetBox, and OpenStack plus legacy desired-config hash logic | FR-5, FR-7, NFR-1, NFR-2 / IC-7, IC-8 | Unit / `[DEV]` | TC-FR7-01–02, TC-NFR1-02 | Existing co-located unit suites; new cases proposed |
| E5 | `bare-metal-fulfillment-operator`: terminal enabled-request admission before allocation and status transitions | FR-5, FR-7, NFR-2 / IC-7, IC-8 | Envtest / `[DEV]` | TC-FR7-01–02 | Proposed `internal/controller/baremetalinstance_secure_boot_envtest_test.go` |
| E6 | `bare-metal-fulfillment-operator`: installed BMFO CRD policy representation and deployed controller admission | FR-5, FR-7, NFR-1, NFR-2 / IC-7, IC-8 | Component integration / `[DEV]` | TC-FR7-01, TC-NFR1-02, TC-NFR2-03 | Proposed `test/integration/secure_boot_test.go` |
| E7 | `osac-aap`: real role task construction from the serialized BMI resource for BMH-path and OpenStack requests, including legacy absence | FR-3, FR-5, NFR-1, NFR-2 / IC-7, IC-9 | Component integration / `[DEV]` | TC-NFR1-02, TC-NFR2-01–02 | Proposed extraction of the OpenStack request builder and extension of existing `bm_host_provisioning_patch` target |
| E8 | Cross-component BMaaS fail-closed admission on a current unsupported adapter | FR-7 / IC-7, IC-8 | E2E / `[QE]` | TC-FR7-05 | Proposed `tests/e2e/bmaas/sanity/test_baremetal_secure_boot.py`; current adapter path, planned |

### Future provider-qualification boundaries

E9 and E10 are not current false-capability implementation gates. They become
mandatory before the named adapter can report Secure Boot enforcement support;
the qualifying real-provider suites and controllable environments are not yet
available.

| Row | Component and changed behavior | Requirements / interfaces | Tier / owner | Test cases | Suite or proposed location |
|---|---|---|---|---|---|
| E9 | Real Metal3/Ironic/BMC semantics for any native Metal3, BCM, or NetBox adapter proposed for enabled-request support | FR-3, FR-7, NFR-2 / IC-8, IC-9 | Contract / `[DEV]` | TC-NFR2-01, TC-FR7-04 (BMH-path row) | Qualifying real-provider suite not yet available; provider-specific follow-up required |
| E10 | Real OpenStack/Ironic/BMC semantics for an OpenStack adapter proposed for enabled-request support | FR-3, FR-7, NFR-2 / IC-8, IC-9 | Contract / `[DEV]` | TC-NFR2-02, TC-FR7-04 (OpenStack row) | Qualifying real-provider suite not yet available; the Ironic fail-closed dependency is tracked by [RFE-10199](https://redhat.atlassian.net/browse/RFE-10199) |

### Future deployed validation

| Row | Component and changed behavior | Requirements / interfaces | Tier / owner | Test cases | Suite or proposed location |
|---|---|---|---|---|---|
| E11 | Cross-component BMaaS default-on success and provider-confirmation fail-closed journeys on a qualified adapter | FR-3, FR-6, FR-7 / IC-3, IC-4, IC-7–IC-9 | E2E / `[QE]` | TC-FR3-04, TC-FR7-03 | Proposed `tests/e2e/bmaas/sanity/test_baremetal_secure_boot.py`; deferred until a backend supports enabled requests and provider-specific qualification is available |

### Execution evidence

| Row | Command and working directory | Prerequisites and exercised boundary | Real versus controlled dependencies | Status / follow-up |
|---|---|---|---|---|
| E1 | `ginkgo run --timeout 20m -r internal` from `fulfillment-service/` | Local Go/protobuf toolchain and the existing server test prerequisites | Real validation, server, mapper, and persistence harness code; Kubernetes, AAP, and providers omitted | Planned; command verified from component guidance |
| E2 | `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment` from repo root | Disposable Kind `osac-dev` environment and installer prerequisites | Real deployed Fulfillment, PostgreSQL, authentication, and CLI; BMFO, AAP, and provider behavior are omitted | Planned; command verified from component guidance |
| E3 | `ginkgo run --timeout 20m -r internal` from `fulfillment-service/` | Existing controller unit fixtures | Real projection and presentation logic; Kubernetes clients, BMFO, and providers controlled by test doubles | Planned; command verified, cases proposed |
| E4 | `make test` from `bare-metal-fulfillment-operator/` | Component test tools | Real adapter and hash logic; inventory/provider APIs mocked or intercepted | Planned; command verified from component guidance |
| E5 | `make test` from `bare-metal-fulfillment-operator/` | Envtest assets and static OSAC/Metal3 CRDs | Real API server, etcd, CRD validation, and reconciler; inventory and AAP providers are fakes with call recording | Planned; proposed case, command verified |
| E6 | `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=bmf` from repo root | Disposable Kind infrastructure and installer prerequisites. The target builds, loads, and deploys the current BMFO image and CRDs before running the suite. CR creation triggers admission; poll status once per second for at most two minutes, matching the suite defaults | Real deployed BMFO, installed CRDs, Kubernetes API, and status updates; BMH transitions are static, while Metal3/Ironic/BMC and hardware are omitted | Planned; proposed case, installer-owned command and polling bounds verified |
| E7 | `uv run ansible-playbook targets/bm_host_provisioning_patch/tasks/baseline.yml -e '@common_vars.yml'` from `osac-aap/tests/integration/` | AAP development dependencies; extract a pure OpenStack `instance_info` builder task file and extend the target with its assertions | Real Ansible execution of role task files and Jinja transforms; no AAP server, Kubernetes API, OpenStack, Metal3 controller, Ironic, or BMC | Planned; proposed extension using an existing target and verified command pattern |
| E8 | `uv run pytest -n 0 tests/e2e/bmaas/sanity/test_baremetal_secure_boot.py` from repo root | Source-compatible deployed BMaaS profile, declared type/image, an available provider-backed BMH, and a current adapter reporting unsupported. BMI create is the trigger; poll API state every 10 seconds for at most 180 attempts using the existing BMI polling pattern | Fulfillment API/database/controller, Kubernetes API, and BMFO run for real. The current adapter's unsupported capability is real; no provider allocation, AAP job, provider confirmation, or tenant power-on should occur | Planned; validates current deployed fail-closed admission and no-fallback behavior |
| E9 | No verified command exists | A real Metal3/BMO/Ironic/BMC environment for each candidate native Metal3, BCM, or NetBox adapter, with controllable supported, unsupported, error, stale-result, and timeout fixtures; tenant power-on must be observable | All provider components and BMC semantics must be real or explicitly qualified fixtures; static BMH state and HTTP doubles do not satisfy this row | Provider-specific qualification is required; not execution-ready or counted as passed |
| E10 | No verified command exists | A real OpenStack/Ironic environment with the same controllable confirmation and power-on observations | OpenStack/Ironic and management-driver semantics must be real or explicitly qualified; rendered `instance_info` alone does not satisfy this row | RFE-10199 tracks the Ironic fail-closed dependency; provider qualification remains pending and this row is not execution-ready or counted as passed |
| E11 | Proposed: `uv run pytest -n 0 tests/e2e/bmaas/sanity/test_baremetal_secure_boot.py` from repo root | Source-compatible deployed BMaaS profile, declared type/image, an available provider-backed BMH, an adapter that has passed E9 or E10, and a qualified way to force confirmation failure | Fulfillment API/database/controller, Kubernetes API, BMFO, AAP, the selected provider, and its qualified confirmation boundary run for real. No provider confirmation or tenant power-on may be faked | Deferred until a backend supports enabled requests and provider-specific qualification is available |

Supplemental build/static validation does not satisfy a test tier:

- `make -C proto generate` and `make -C proto lint`.
- `make manifests generate helm-crds check-helm-crds` in
  `bare-metal-fulfillment-operator/`.
- Applicable component format, lint, and Helm checks from each `AGENTS.md`.

## Test Case Index

| ID | Scenario | IC | Priority |
|---|---|---|---|
| TC-FR1-01 | Admin creates and updates the hardware declaration | IC-1 | high |
| TC-FR1-02 | Authorized tenant inspects the hardware declaration | IC-1 | high |
| TC-FR2-01 | New DiskImage creation permits an absent declaration | IC-2 | critical |
| TC-FR2-02 | Explicit true and false image declarations persist and display | IC-2 | high |
| TC-FR2-03 | Authorized owners update DiskImage compatibility without changing existing BMIs | IC-2 | critical |
| TC-FR3-01 | Intention and declaration states resolve per contract | IC-3, IC-4 | critical |
| TC-FR3-02 | Omitted BMI intention is stored as PREFERRED | IC-3 | high |
| TC-FR3-03 | BMI intention is immutable | IC-3 | high |
| TC-FR3-04 | Deployed BMaaS default-on journey succeeds after confirmation | IC-4, IC-7, IC-9 | critical |
| TC-FR4-01 | Every blocked required combination reports all blockers | IC-5 | critical |
| TC-FR6-01 | Preferred ENABLED request is inspectable | IC-4 | high |
| TC-FR6-02 | Preferred resolved DISABLED is inspectable | IC-4 | medium |
| TC-FR7-01 | Every current adapter rejects enabled requests before host allocation | IC-7, IC-8 | critical |
| TC-FR7-02 | Rejection is terminal, visible, and never falls back | IC-8 | high |
| TC-FR7-03 | Deployed BMaaS fail-closed journey and separate disabled request | IC-8, IC-9 | critical |
| TC-FR7-04 | Future backend qualification proves the provider-owned gate | IC-8, IC-9 | critical |
| TC-FR7-05 | Current deployed adapter rejects enabled requests without allocation | IC-7, IC-8 | critical |
| TC-NFR1-01 | Legacy omissions remain compatible and disable Secure Boot | IC-1, IC-2, IC-4 | high |
| TC-NFR1-02 | Legacy BMI/CR absence neither reprovisions nor changes behavior | IC-7, IC-9 | high |
| TC-NFR2-01 | BMH-path mapping sets boot mode for each execution mode | IC-9 | high |
| TC-NFR2-02 | OpenStack mapping sets fresh Ironic instance information for each execution mode | IC-9 | high |
| TC-NFR2-03 | Installed BMFO CRD preserves and validates Secure Boot policy | IC-7 | high |
| TC-NFR3-01 | Effective behavior survives source lifecycle and status updates | IC-4, IC-7 | high |

## Test Cases

### FR-1: Hardware support declaration

#### TC-FR1-01: Admin creates and updates the hardware declaration

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-1 | high | automated | E1 |

##### Preconditions

- A private-API client authenticated as Cloud Provider Admin.

##### Steps

1. Create a BareMetalInstanceType without
   `spec.hardware.uefi_secure_boot_supported` and get it.
2. Update the field to `true`, then `false`, then clear it, getting the type
   after each update.

##### Expected Results

- The omitted create succeeds and reports an absent declaration interpreted as
  unsupported.
- Updates report explicit `true`, explicit `false`, then absent interpreted as
  unsupported.
- No automatic hardware probe or verification runs.

#### TC-FR1-02: Authorized tenant inspects the hardware declaration

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-1 | high | automated | E2 |

##### Preconditions

- One viewable type with `true`, one with `false`, and one type with the field
  absent.

##### Steps

1. As an authorized tenant, Get and describe each type through API and CLI.
2. Repeat against a type the tenant cannot view.

##### Expected Results

- API presence and CLI output distinguish `true`, `false`, and undeclared
  (treated as unsupported).
- The unauthorized API read returns gRPC `PermissionDenied`; the CLI exits
  nonzero and neither response exposes a declaration value.

### FR-2: Image compatibility declaration

##### Shared Preconditions

- API and CLI clients authorized to create DiskImages, plus API clients for
  tenant-owned and shared-image update paths.

#### TC-FR2-01: New DiskImage creation permits an absent declaration

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-2 | critical | automated | E1 |

##### Steps

1. Submit API and CLI DiskImage creates without
   `uefi_secure_boot_compatible` and read both images.

##### Expected Results

- Both creates succeed and the API/CLI reads show an absent declaration,
  interpreted as incompatible.

#### TC-FR2-02: Explicit true and false image declarations persist and display

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-2 | high | automated | E1, E2 |

##### Steps

1. Create one image with
   `--uefi-secure-boot-compatible=true` and one with `false`.
2. Get and describe both images.

##### Expected Results

- Both creates succeed and every API/CLI read displays the exact declared
  boolean.

#### TC-FR2-03: Authorized owners update DiskImage compatibility without changing existing BMIs (parameterized)

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-2 | critical | automated | E1, E2 |

##### Preconditions

- The hardware type used by each row expecting `ENABLED` declares
  `uefi_secure_boot_supported` as `true`.

##### Steps

1. For each row, create an existing `PREFERRED` BMI and catalog item that
   reference the image, then record the BMI's effective behavior.
2. Submit an unrelated update without the compatibility flag for one case;
   for declaration changes, submit the listed API update to
   `uefi_secure_boot_compatible`. Read the image and create another
   `PREFERRED` BMI from the same type and image.

##### Expected Results

| Image scope and stored declaration | Caller | Update | Existing / later BMI effective behavior |
|---|---|---|---|
| Tenant-owned, absent | Owning tenant | Add `true` | `DISABLED` / `ENABLED` |
| Tenant-owned, `true` | Owning tenant | Change to `false` | `ENABLED` / `DISABLED` |
| Tenant-owned, `false` | Owning tenant | Set `false` | `DISABLED` / `DISABLED` |
| Shared, absent | Cloud Provider Admin | Add `true` | `DISABLED` / `ENABLED` |
| Shared, `true` | Ordinary tenant, then Cloud Provider Admin | Tenant attempts `false`; admin sets `false` | `ENABLED` / `DISABLED` after the authorized update |

- Every authorized update succeeds despite both existing references, and the
  exact updated boolean value is returned. The catalog item keeps the same
  image reference and does not block the update.
- An update that omits the compatibility flag preserves the stored declaration
  and does not change later BMI resolution.
- Every existing BMI retains its recorded effective behavior and projected
  policy; only the later BMI uses the updated declaration.
- The ordinary tenant's shared-image update returns gRPC `PermissionDenied`
  without changing the declaration; the Cloud Provider Admin's update succeeds.

### FR-3: Instance intention and resolution

##### Shared Preconditions

- A BMI-creating tenant client and type/image fixtures covering explicit true,
  explicit false, and legacy-absent declarations.

#### TC-FR3-01: Intention and declaration states resolve per contract (parameterized)

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-3, IC-4 | critical | automated | E1 |

##### Steps

1. Create a BMI using each row's intention and declaration states.
2. Read the stored spec and status.

##### Expected Results

| Intention | Hardware declaration | Image declaration | Result |
|---|---:|---:|---|
| `REQUIRED` | true | true | Created; intention `REQUIRED`, effective `ENABLED`. |
| `PREFERRED` | true | true | Created; effective `ENABLED`. |
| `PREFERRED` | false | true | Created; effective `DISABLED`. |
| `PREFERRED` | absent | true | Created; effective `DISABLED`. |
| `PREFERRED` | true | false | Created; effective `DISABLED`. |
| `PREFERRED` | true | absent | Created; effective `DISABLED`. |
| `DISABLED` | true | true | Created; effective `DISABLED`. |
| `DISABLED` | absent | false | Created; effective `DISABLED`. |

#### TC-FR3-02: Omitted BMI intention is stored as PREFERRED

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-3 | high | automated | E1 |

##### Steps

1. Create a BMI without `secure_boot` against two true declarations.

##### Expected Results

- Stored `spec.secure_boot` is `PREFERRED`, not `UNSPECIFIED`.
- Stored effective behavior is `ENABLED`.

#### TC-FR3-03: BMI intention is immutable

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-3 | high | automated | E1 |

##### Steps

1. Create a `PREFERRED` BMI.
2. Submit an update changing `spec.secure_boot` to `DISABLED`.

##### Expected Results

- Update returns gRPC `InvalidArgument` for the immutable field; intention and
  effective behavior are unchanged.

#### TC-FR3-04: Deployed BMaaS default-on journey succeeds after confirmation

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-4, IC-7, IC-9 | critical | automated | E11 |

##### Preconditions

- A deployed BMaaS environment using an E9/E10-qualified backend, an available
  host, and a type/image whose declarations are both true.

##### Steps

1. Create a BMI without a Secure Boot flag.
2. Wait with the suite's bounded lifecycle helper for `RUNNING`.
3. Read the API BMI, BMFO CR, and selected provider resource.

##### Expected Results

- API spec is `PREFERRED` and effective behavior is `ENABLED`.
- The BMFO CR carries enabled fail-closed behavior.
- The provider confirms Secure Boot before the first tenant-image boot, and the
  BMI reaches `RUNNING` without a disabled fallback.

### FR-4: Actionable create-time validation

##### Shared Preconditions

- An authorized BMI client and type/image fixtures for all nine combinations
  of true, false, and absent declarations.

#### TC-FR4-01: Every blocked required combination reports all blockers (parameterized)

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-5 | critical | automated | E1 |

##### Steps

1. Create a `REQUIRED` BMI for each declaration pair.

##### Expected Results

| Hardware | Image | Exact blocker set in `INCOMPATIBLE_SECURE_BOOT_DECLARATIONS` |
|---:|---:|---|
| false | true | Hardware unsupported. |
| absent | true | Hardware declaration missing. |
| true | false | Image incompatible. |
| true | absent | Image declaration missing. |
| false | false | Hardware unsupported; image incompatible. |
| false | absent | Hardware unsupported; image declaration missing. |
| absent | false | Hardware declaration missing; image incompatible. |
| absent | absent | Both declarations missing. |

Every row returns `InvalidArgument`, lists blockers in hardware-then-image
order with resource identities and corrector roles, and creates no BMI.

### FR-5: Workload consistency through the shared BMI contract

FR-5 cross-maps to existing cases rather than duplicating them:

- TC-FR3-01–02 prove origin-independent declaration resolution and the omitted
  `PREFERRED` default used by existing CaaS worker creates.
- TC-FR6-01–02 prove effective behavior visibility on the worker BMI itself.
- TC-FR7-01–02 and TC-FR7-05 prove that any BMI carrying the fail-closed mode receives
  identical admission and failure behavior across current backends.
- TC-NFR2-01–02 prove the common provider requests after projection.

CaaS service resources currently omit `secure_boot`, so workers use
`PREFERRED`. Exposing or overriding the value through CaaS resources is outside
this design. The plan therefore claims current CaaS default and shared-path
coverage, not a tenant-selectable `REQUIRED` CaaS journey. [User] [Codebase:
osac-operator/internal/controller/baremetalworker/bmi.go]

### FR-6: Effective behavior visibility

##### Shared Preconditions

- An authorized tenant client and viewable type/image resources with known
  declarations.

#### TC-FR6-01: Preferred ENABLED request is inspectable

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-4 | high | automated | E1, E2 |

##### Steps

1. Create `PREFERRED` against two true declarations.
2. Get and describe the BMI through public API and CLI.

##### Expected Results

- Both surfaces return the declaration-derived
  `secure_boot_effective: ENABLED`. Successful provisioning requires the FR-7
  confirmation gate; on current adapters the request fails before allocation.

#### TC-FR6-02: Preferred resolved DISABLED is inspectable

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-4 | medium | automated | E1, E2 |

##### Steps

1. Create `PREFERRED` with one false declaration.
2. Get and describe the BMI through public API and CLI.

##### Expected Results

- Both surfaces return only `secure_boot_effective: DISABLED`; the exact
  original declaration states remain visible on their resources.

### FR-7: Pre-boot enforcement for effective-enabled requests

##### Shared Preconditions

- True type/image declarations. TC-FR7-01–02 and TC-FR7-05 use a current
  provider path that reports Secure Boot enforcement unsupported; TC-FR7-03
  uses the qualified provider boundary E11, and TC-FR7-04 uses E9/E10.

#### TC-FR7-01: Every current adapter rejects enabled requests before host allocation

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-7, IC-8 | critical | automated | E3, E4, E5, E6 |

##### Steps

1. For each current inventory adapter—native Metal3, BCM, NetBox, and
   OpenStack—create BMFO CRs from `REQUIRED` and `PREFERRED` requests whose
   effective behavior is enabled fail closed.
2. Read its typed capabilities and reconcile through the allocation stage.

##### Expected Results

- Every current provider path reports Secure Boot enforcement unsupported.
- Every row reaches phase `Failed`; `Allocated=False` has reason
  `SecureBootEnforcementUnsupported`, and backend names do not alter the
  failure classification.
- For every row, `FindFreeHost`, assignment, and provisioning-provider call
  counts remain zero; no external host ID or AAP job exists.

#### TC-FR7-02: Rejection is terminal, visible, and never falls back

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-8 | high | automated | E3, E4, E5 |

##### Steps

1. Reconcile the failed CR repeatedly, including after controller restart.
2. Feed its status through fulfillment status synchronization.

##### Expected Results

- The CR remains failed with an identical immutable Secure Boot policy and no
  provider calls or retry schedule.
- No job is launched with a disabled policy.
- Fulfillment reports `FAILED` with the curated Secure Boot enforcement message,
  not a generic allocation message or provider detail.

#### TC-FR7-03: Deployed BMaaS fail-closed journey and separate disabled request

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-8, IC-9 | critical | automated | E11 |

##### Steps

1. Configure the qualified provider fixture to fail final Secure Boot
   confirmation before tenant-image power-on.
2. Against true declarations, create a BMI with `--secure-boot required`.
3. Wait for its terminal result and inspect its BMFO CR and provider evidence.
4. Create a separate BMI from the same inputs with
   `--secure-boot disabled` and wait for `RUNNING`.

##### Expected Results

- The required BMI reports the curated failure and never boots a tenant image;
  provider activity may exist, but no disabled retry is launched.
- The disabled BMI resolves `DISABLED`, provisions independently, and requests
  ordinary UEFI.

#### TC-FR7-04: Future backend qualification proves the provider-owned gate (parameterized)

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-8, IC-9 | critical | automated | E9, E10 |

##### Preconditions

- A candidate backend implementation and the real-boundary fixtures required
  by E9 or E10.

##### Steps

1. Run the conformance sequence for each provider row before allowing its
   provider path to advertise Secure Boot enforcement support.
2. Exercise successful final enable/read-back and unsupported, absent, stale,
   contradictory, provider-error, and bounded-timeout outcomes.
3. Observe provider operation order and tenant-image power-on.

##### Expected Results

| Provider row | Required result |
|---|---|
| Native Metal3, BCM, or NetBox through BMO/Ironic/BMC | For each adapter proposed for support, success confirms enabled before tenant power-on; every non-success result fails with no tenant power-on and no disabled fallback. |
| Direct OpenStack/Ironic/BMC | The same outcomes and ordering hold through the direct provider path. |

No adapter may advertise support until its E9 or E10 row passes. These rows are
not evidence for the current false-capability adapters. E11 does not qualify an
adapter; it validates the deployed journey after qualification.

#### TC-FR7-05: Current deployed adapter rejects enabled requests without allocation

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-7, IC-8 | critical | automated | E8 |

##### Preconditions

- A deployed BMaaS environment using a current adapter that reports Secure Boot
  enforcement unsupported, an available host, and a type/image whose
  declarations are both true.

##### Steps

1. Create a BMI with `--secure-boot required`.
2. Wait with the suite's bounded lifecycle helper for the terminal result.
3. Read the API BMI, BMFO CR, allocation state, and provider/AAP evidence.

##### Expected Results

- The BMI fails with the curated
  `SecureBootEnforcementUnsupported` outcome before host allocation.
- No allocation, external host ID, AAP job, provider provisioning call, or
  tenant-image boot occurs, and the request is not retried with disabled
  behavior.
- The deployed API and BMFO status expose the failure consistently.

### NFR-1: Backward compatibility

##### Shared Preconditions

- New-client and pre-feature fixtures in which Secure Boot declarations or the
  BMFO policy are absent.

#### TC-NFR1-01: Legacy omissions remain compatible and disable Secure Boot

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-1, IC-2, IC-4 | high | automated | E1, E2 |

##### Steps

1. Create a new type and a new image without declarations.
2. Seed equivalent pre-feature resources with both fields absent.
3. Perform unrelated updates that leave both legacy declarations absent.
4. Create `PREFERRED`, then attempt `REQUIRED`, from the legacy resource pair.
5. Update both declarations to true and create another `PREFERRED` BMI from the
   same type and image.

##### Expected Results

- Both creates succeed. Unrelated updates preserve absent declarations.
- Legacy `PREFERRED` resolves `DISABLED`; `REQUIRED` reports both missing
  blockers.
- The image update succeeds even while the first BMI references it. The later
  BMI resolves `ENABLED`; the first BMI remains `DISABLED`.

#### TC-NFR1-02: Legacy BMI/CR absence neither reprovisions nor changes behavior

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-7, IC-9 | high | automated | E1, E3, E4, E6, E7 |

##### Steps

1. Seed a pre-feature BMI and BMFO CR with the Secure Boot policy absent, an
   existing desired-config hash, and completed provisioning history.
2. Reconcile after upgrade and after declaration changes.
3. In a separate legacy-shaped CR with the policy absent, execute each
   provider request builder.

##### Expected Results

- Reconciliation does not synthesize a Secure Boot policy, change the legacy
  hash, launch a job, or alter the completed history.
- Both provider builders map the absent policy to ordinary UEFI,
  never enabled.

### NFR-2: Backend consistency

##### Shared Preconditions

- Native Metal3, BCM, NetBox, and OpenStack adapter fixtures plus serialized
  BMFO CR inputs for enabled, disabled, and legacy-absent policies.

#### TC-NFR2-01: BMH-path mapping sets boot mode for each execution mode

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-9 | high | automated | E7, E9 |

##### Steps

1. Execute the role's BMH patch builder with enabled, disabled, and
   legacy-absent policy inputs.

##### Expected Results

- Enabled yields `spec.bootMode: UEFISecureBoot`.
- Disabled and legacy absence yield `spec.bootMode: UEFI`.
- The role obtains the mode from the serialized `bare_metal_instance.spec`, not
  a caller-supplied `templateParameters` key or separate launch variable.
- Every generated patch sets boot mode explicitly and preserves unrelated
  image, checksum, secret, network-data, and root-device fields.

#### TC-NFR2-02: OpenStack mapping sets fresh Ironic instance information for each execution mode

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-9 | high | automated | E7, E10 |

##### Steps

1. Execute the role's OpenStack `instance_info` builder with enabled, disabled,
   and legacy-absent policy inputs after the undeploy path clears old instance
   information.

##### Expected Results

- Enabled adds `capabilities: {secure_boot: "true"}`.
- Disabled and legacy absence contain no `secure_boot` capability.
- The role obtains the mode from the serialized `bare_metal_instance.spec`, not
  a caller-supplied `templateParameters` key or separate launch variable.
- Image source, checksum/hash, and `root_gb` inputs remain unchanged.

#### TC-NFR2-03: Installed BMFO CRD preserves and validates Secure Boot policy

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-7 | high | automated | E6 |

##### Steps

1. Through the installed BMFO CRD, create CRs for each execution mode in the
   implementation's chosen policy representation.
2. Read the resources, attempt values outside the chosen schema, and mutate the
   immutable BMFO policy.
3. Create a legacy-shaped resource with the optional policy absent.

##### Expected Results

- Both BMFO execution modes round-trip without semantic collapse.
- Invalid values and BMFO policy mutation are rejected by the API server.
- The legacy-shaped resource remains schema-valid.

### NFR-3: Effective behavior integrity

##### Preconditions

- A created `PREFERRED` BMI whose two source declarations were true at create.

#### TC-NFR3-01: Effective behavior survives source lifecycle and status updates

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-4, IC-7 | high | automated | E1, E3 |

##### Steps

1. Create `PREFERRED` against true declarations and observe `ENABLED`.
2. Change the hardware declaration to unsupported and the selected image
   declaration to incompatible, then create a later `PREFERRED` BMI from the
   updated resources.
3. Run BMFO-to-fulfillment status synchronization with unrelated status
   changes.

##### Expected Results

- BMI intention remains `PREFERRED`; API effective behavior and projected BMFO
  policy remain enabled fail closed.
- Both source declarations are updated, but the existing BMI remains enabled;
  the later BMI resolves disabled from the updated declarations.
- The status update mask never clears or replaces
  `status.secure_boot_effective`.

## Gaps

### Requirement Coverage Gaps

None against the merged PRD. FR-5 uses the same BMI API,
projection, admission, and provider cases regardless of origin. Current CaaS
creates omit the field and therefore exercise only the shared `PREFERRED`
default. CaaS `REQUIRED` selection is explicitly out of scope, so this plan does
not claim a deployed fail-closed CaaS journey. A future selection surface needs
its own design and tests. [User]

Fulfillment/UI availability preflight is outside the current API/CLI scope and
has no current IC or test case; a future design must define its contract and
coverage.

Current-backend effective-enabled behavior is the fail-closed admission
rejection in TC-FR7-01 and the deployed outcome in TC-FR7-05. TC-FR3-04 and
TC-FR7-03 are deferred deployed provider journeys, and TC-FR7-04 is the
provider qualification gate. E9–E11 disclose the unavailable real boundaries,
which require provider-specific follow-up. The OpenStack/Ironic fail-closed
dependency is tracked by
[RFE-10199](https://redhat.atlassian.net/browse/RFE-10199).

E8 exercises the current deployed fail-closed admission path and does not
qualify fresh provider/BMC confirmation. E11 requires the deployed OSAC and BMH
lifecycle named in its execution row and may run only after the selected
adapter passes E9 or E10.

### Interface Change Coverage Gaps

All eight active BMaaS interface changes map to cases. IC-8's future
true-capability branch is planned by TC-FR7-04 and E11 but blocked as described
above; this blocks enabling a provider adapter, not implementation of the
current false branch, which has identified execution paths through E5/E6/E8.

## Summary

| Metric | Count |
|---|---:|
| Total test cases | 42 |
| Critical | 28 |
| High | 13 |
| Medium | 1 |
| Low | 0 |
| Automated | 42 |
| Manual | 0 |
| Requirements with test cases | 10 / 10 |
| Fully covered requirements | 10 / 10 |
| Interface changes with test cases | 8 / 8 |
