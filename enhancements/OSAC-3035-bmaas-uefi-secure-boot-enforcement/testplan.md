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
- **Provider-gated cases:** 2 of 42 cases (`TC-FR7-03` and `TC-FR7-04`) are
  deferred until a backend passes fail-closed provider qualification.

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
| E1 | `fulfillment-service`: optional image declaration, mutable declaration lifecycles, defaulting, three-state resolution, exhaustive blockers, BMI immutability, and compatibility | FR-1–FR-5, FR-6, NFR-1, NFR-3 / IC-1–IC-5 | Unit / `[DEV]` | TC-FR1-01, TC-FR2-01–03, TC-FR3-01–03, TC-FR4-01, TC-FR6-01–02, TC-NFR1-01–02, TC-NFR3-01 | Existing `internal/servers`, `internal/validation`, and CLI unit suites; new cases proposed |
| E2 | `fulfillment-service`: deployed API/CLI persistence, shared-image update authorization, reference-independent declaration updates, and output | FR-1, FR-2, FR-5, FR-6, NFR-1 / IC-1, IC-2, IC-4 | Component integration / `[DEV]` | TC-FR1-02, TC-FR2-02–03, TC-FR6-01–02, TC-NFR1-01 | Existing `it/` and CLI harness; new cases proposed |
| E3 | `fulfillment-service`: direct three-state projection, legacy hash preservation, status/failure mapping | FR-5, FR-7, NFR-1, NFR-3 / IC-7, IC-8 | Unit / `[DEV]` | TC-FR7-01–02, TC-NFR1-02, TC-NFR3-01 | Existing `internal/controllers/baremetalinstance` suites; new cases proposed |
| E4 | `bare-metal-fulfillment-operator`: hardcoded provider capability results for Metal3, BCM, NetBox, and OpenStack plus legacy desired-config hash logic | FR-5, FR-7, NFR-1, NFR-2 / IC-7, IC-8 | Unit / `[DEV]` | TC-FR7-01–02, TC-NFR1-02 | Existing co-located unit suites; new cases proposed |
| E5 | `bare-metal-fulfillment-operator`: preferred/required capability admission before allocation and status transitions | FR-5, FR-7, NFR-2 / IC-7, IC-8 | Envtest / `[DEV]` | TC-FR7-01–02 | Proposed `internal/controller/baremetalinstance_secure_boot_envtest_test.go` |
| E6 | `bare-metal-fulfillment-operator`: installed BMFO CRD requested field and deployed controller admission for the current `RequestOnly` capability | FR-5, FR-7, NFR-1, NFR-2 / IC-7, IC-8 | Component integration / `[DEV]` | TC-FR7-01 (`RequestOnly` rows), TC-NFR1-02, TC-NFR2-03 | Proposed `test/integration/secure_boot_test.go` |
| E7 | `osac-aap`: real role task construction from the serialized BMI resource for BMH-path and OpenStack requests, including legacy absence | FR-3, FR-5, NFR-1, NFR-2 / IC-7, IC-9 | Component integration / `[DEV]` | TC-NFR1-02, TC-NFR2-01–02 | Proposed extraction of the OpenStack request builder and extension of existing `bm_host_provisioning_patch` target |
| E8 | Cross-component BMaaS required admission on a current request-only adapter | FR-7 / IC-7, IC-8 | E2E / `[QE]` | TC-FR7-05 | Proposed `tests/e2e/bmaas/sanity/test_baremetal_secure_boot.py`; current adapter path, planned |

### Future provider-qualification boundaries

E9 and E10 are not current request-only implementation gates. They become
mandatory before the named adapter can report fail-closed support;
the qualifying real-provider suites and controllable environments are not yet
available.

| Row | Component and changed behavior | Requirements / interfaces | Tier / owner | Test cases | Suite or proposed location |
|---|---|---|---|---|---|
| E9 | Real Metal3/Ironic/BMC semantics for any native Metal3, BCM, or NetBox adapter proposed for fail-closed support | FR-3, FR-7, NFR-2 / IC-8, IC-9 | Contract / `[DEV]` | TC-NFR2-01, TC-FR7-04 (BMH-path row) | Qualifying real-provider suite not yet available; no owning follow-up ticket exists |
| E10 | Real OpenStack/Ironic/BMC semantics for an OpenStack adapter proposed for fail-closed support | FR-3, FR-7, NFR-2 / IC-8, IC-9 | Contract / `[DEV]` | TC-NFR2-02, TC-FR7-04 (OpenStack row) | Qualifying real-provider suite not yet available; the Ironic fail-closed dependency is tracked by [RFE-10199](https://redhat.atlassian.net/browse/RFE-10199) |

### Deployed preferred validation

| Row | Component and changed behavior | Requirements / interfaces | Tier / owner | Test cases | Suite or proposed location |
|---|---|---|---|---|---|
| E11 | Cross-component BMaaS preferred-enabled success on a current request-only adapter | FR-3, FR-6 / IC-3, IC-4, IC-7–IC-9 | E2E / `[QE]` | TC-FR3-04 | Proposed `tests/e2e/bmaas/sanity/test_baremetal_secure_boot.py`; current adapter path, planned |

### Future deployed required validation

| Row | Component and changed behavior | Requirements / interfaces | Tier / owner | Test cases | Suite or proposed location |
|---|---|---|---|---|---|
| E12 | Cross-component BMaaS required confirmation failure on a qualified fail-closed adapter | FR-7 / IC-8, IC-9 | E2E / `[QE]` | TC-FR7-03 | Proposed `tests/e2e/bmaas/sanity/test_baremetal_secure_boot.py`; deferred until E9 or E10 passes; no separate owning ticket exists |

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
| E8 | Proposed: `uv run pytest -n 0 tests/e2e/bmaas/sanity/test_baremetal_secure_boot.py` from repo root | Source-compatible deployed BMaaS profile, declared type/image, an available provider-backed BMH, and a current request-only adapter. BMI create is the trigger; poll API state every 10 seconds for at most 180 attempts using the existing BMI polling pattern | Fulfillment API/database/controller, Kubernetes API, and BMFO run for real. The current adapter's request-only capability is real; no provider allocation, AAP job, or tenant power-on should occur for `ENABLED_REQUIRED` | Planned; validates current deployed required admission and no-fallback behavior |
| E9 | No verified command exists | A real Metal3/BMO/Ironic/BMC environment for each candidate native Metal3, BCM, or NetBox adapter, with controllable supported, unsupported, error, stale-result, and timeout fixtures; tenant power-on must be observable | All provider components and BMC semantics must be real or explicitly qualified fixtures; static BMH state and HTTP doubles do not satisfy this row | Provider-specific qualification is required; not execution-ready or counted as passed |
| E10 | No verified command exists | A real OpenStack/Ironic environment with the same controllable confirmation and power-on observations | OpenStack/Ironic and management-driver semantics must be real or explicitly qualified; rendered `instance_info` alone does not satisfy this row | RFE-10199 tracks the Ironic fail-closed dependency; provider qualification remains pending and this row is not execution-ready or counted as passed |
| E11 | Proposed: `uv run pytest -n 0 tests/e2e/bmaas/sanity/test_baremetal_secure_boot.py` from repo root | Source-compatible deployed BMaaS profile, declared type/image, a provider-backed BMH known to accept and provision the Secure Boot request, and a current request-only adapter | Fulfillment API/database/controller, Kubernetes API, BMFO, AAP, and the selected provider run for real; the test verifies the request, not observed firmware state | Planned; validates the current preferred-enabled success path |
| E12 | Proposed: `uv run pytest -n 0 tests/e2e/bmaas/sanity/test_baremetal_secure_boot.py` from repo root | Source-compatible deployed BMaaS profile, a provider that passed E9 or E10, and a qualified way to force confirmation failure | Fulfillment API/database/controller, Kubernetes API, BMFO, AAP, the selected provider, and its confirmation boundary run for real | Deferred until a fail-closed provider is qualified |

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
| TC-FR3-04 | Deployed BMaaS default-on request succeeds | IC-4, IC-7, IC-9 | critical |
| TC-FR4-01 | Every blocked required combination reports all blockers | IC-5 | critical |
| TC-FR6-01 | Preferred ENABLED request is inspectable | IC-4 | high |
| TC-FR6-02 | Preferred resolved DISABLED is inspectable | IC-4 | medium |
| TC-FR7-01 | Provider capability controls preferred and required admission | IC-7, IC-8 | critical |
| TC-FR7-02 | Rejection is terminal, visible, and never falls back | IC-8 | high |
| TC-FR7-03 | Deployed BMaaS fail-closed journey and separate disabled request | IC-8, IC-9 | critical |
| TC-FR7-04 | Future backend qualification proves the provider-owned gate | IC-8, IC-9 | critical |
| TC-FR7-05 | Current deployed adapter rejects required without allocation | IC-7, IC-8 | critical |
| TC-NFR1-01 | Legacy omissions remain compatible and resolve to DISABLED | IC-1, IC-2, IC-4 | high |
| TC-NFR1-02 | Legacy BMI/CR absence neither reprovisions nor changes behavior | IC-7, IC-9 | high |
| TC-NFR2-01 | BMH-path mapping sets boot mode for each execution mode | IC-9 | high |
| TC-NFR2-02 | OpenStack mapping sets fresh Ironic instance information for each execution mode | IC-9 | high |
| TC-NFR2-03 | Installed BMFO CRD preserves and validates the requested value | IC-7 | high |
| TC-NFR3-01 | Requested behavior survives source lifecycle and status updates | IC-4, IC-7 | high |

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

- The hardware type used by each row expecting `ENABLED_PREFERRED` declares
  `uefi_secure_boot_supported` as `true`.

##### Steps

1. For each row, create an existing `PREFERRED` BMI and catalog item that
   reference the image, then record the BMI's requested behavior.
2. Submit an unrelated update without the compatibility flag for one case;
   for declaration changes, submit the listed API update to
   `uefi_secure_boot_compatible`. Read the image and create another
   `PREFERRED` BMI from the same type and image.

##### Expected Results

| Image scope and stored declaration | Caller | Update | Existing / later BMI requested behavior |
|---|---|---|---|
| Tenant-owned, absent | Owning tenant | Add `true` | `DISABLED` / `ENABLED_PREFERRED` |
| Tenant-owned, `true` | Owning tenant | Change to `false` | `ENABLED_PREFERRED` / `DISABLED` |
| Tenant-owned, `false` | Owning tenant | Set `false` | `DISABLED` / `DISABLED` |
| Shared, absent | Cloud Provider Admin | Add `true` | `DISABLED` / `ENABLED_PREFERRED` |
| Shared, `true` | Ordinary tenant, then Cloud Provider Admin | Tenant attempts `false`; admin sets `false` | `ENABLED_PREFERRED` / `DISABLED` after the authorized update |

- Every authorized update succeeds despite both existing references, and the
  exact updated boolean value is returned. The catalog item keeps the same
  image reference and does not block the update.
- An update that omits the compatibility flag preserves the stored declaration
  and does not change later BMI resolution.
- Every existing BMI retains its recorded requested behavior and projected
  value; only the later BMI uses the updated declaration.
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
| `REQUIRED` | true | true | Created; intention `REQUIRED`, requested `ENABLED_REQUIRED`. |
| `PREFERRED` | true | true | Created; requested `ENABLED_PREFERRED`. |
| `PREFERRED` | false | true | Created; requested `DISABLED`. |
| `PREFERRED` | absent | true | Created; requested `DISABLED`. |
| `PREFERRED` | true | false | Created; requested `DISABLED`. |
| `PREFERRED` | true | absent | Created; requested `DISABLED`. |
| `DISABLED` | true | true | Created; requested `DISABLED`. |
| `DISABLED` | absent | false | Created; requested `DISABLED`. |

#### TC-FR3-02: Omitted BMI intention is stored as PREFERRED

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-3 | high | automated | E1 |

##### Steps

1. Create a BMI without `secure_boot` against two true declarations.

##### Expected Results

- Stored `spec.secure_boot` is `PREFERRED`, not `UNSPECIFIED`.
- Stored requested behavior is `ENABLED_PREFERRED`.

#### TC-FR3-03: BMI intention is immutable

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-3 | high | automated | E1 |

##### Steps

1. Create a `PREFERRED` BMI.
2. Submit an update changing `spec.secure_boot` to `DISABLED`.

##### Expected Results

- Update returns gRPC `InvalidArgument` for the immutable field; intention and
  requested behavior are unchanged.

#### TC-FR3-04: Deployed BMaaS default-on request succeeds

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-4, IC-7, IC-9 | critical | automated | E11 |

##### Preconditions

- A deployed BMaaS environment using a current request-only backend, a host
  and provider path known to accept and provision the Secure Boot request, and
  a type/image whose declarations are both true.

##### Steps

1. Create a BMI without a Secure Boot flag.
2. Wait with the suite's bounded lifecycle helper for `RUNNING`.
3. Read the API BMI, BMFO CR, and selected provider resource.

##### Expected Results

- API spec is `PREFERRED` and `secure_boot_requested` is
  `ENABLED_PREFERRED`.
- The BMFO CR carries the same value and the provider receives its native
  Secure Boot request.
- The BMI reaches `RUNNING`; the test does not claim observed firmware state.

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

| Hardware | Image | Blocking declarations identified |
|---:|---:|---|
| false | true | Hardware unsupported |
| absent | true | Hardware missing |
| true | false | Image incompatible |
| true | absent | Image missing |
| false | false | Hardware unsupported; image incompatible |
| false | absent | Hardware unsupported; image missing |
| absent | false | Hardware missing; image incompatible |
| absent | absent | Hardware missing; image missing |

Every row returns `InvalidArgument` and identifies every blocking declaration
with its state, resource identity, and corrector role in hardware-then-image
order; the exact message wording is implementation-defined. No BMI is created.

### FR-5: Workload consistency through the shared BMI contract

FR-5 cross-maps to existing cases rather than duplicating them:

- TC-FR3-01–02 prove origin-independent declaration resolution and the omitted
  `PREFERRED` default used by existing CaaS worker creates.
- TC-FR6-01–02 prove requested behavior visibility on the worker BMI itself.
- TC-FR7-01–02 and TC-FR7-05 prove capability-based admission and failure
  behavior across current backends.
- TC-NFR2-01–02 prove the common provider requests after projection.

CaaS service resources currently omit `secure_boot`, so workers use
`PREFERRED`. Exposing or overriding the value through CaaS resources is outside
this design. The plan therefore claims current CaaS default and shared-path
coverage, not a tenant-selectable `REQUIRED` CaaS journey.

### FR-6: Requested behavior visibility

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
  `secure_boot_requested: ENABLED_PREFERRED` and identify it as a request
  without a firmware-state guarantee.

#### TC-FR6-02: Preferred resolved DISABLED is inspectable

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-4 | medium | automated | E1, E2 |

##### Steps

1. Create `PREFERRED` with one false declaration.
2. Get and describe the BMI through public API and CLI.

##### Expected Results

- Both surfaces return only `secure_boot_requested: DISABLED`; the exact
  original declaration states remain visible on their resources.

### FR-7: Provider admission and required enforcement

##### Shared Preconditions

- True type/image declarations. TC-FR7-01–02 exercise all capability values,
  TC-FR7-05 uses a current request-only provider, and TC-FR7-03–04 use E9/E10.

#### TC-FR7-01: Provider capability controls preferred and required admission

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-7, IC-8 | critical | automated | E3, E4, E5, E6 (`RequestOnly` rows) |

##### Steps

1. Verify each current provider implementation's hardcoded capability.
2. Reconcile `ENABLED_PREFERRED` and `ENABLED_REQUIRED` using controlled
   `Unsupported`, `RequestOnly`, and `FailClosed` capabilities.

E5 supplies the controlled capability values; E6 deploys the current image
and covers only its hardcoded `RequestOnly` capability.

##### Expected Results

- Every current provider path reports `RequestOnly`.
- `ENABLED_PREFERRED` is admitted for `RequestOnly` and `FailClosed`;
  `ENABLED_REQUIRED` is admitted only for `FailClosed`.
- `Unsupported` rejects either enabled value before allocation with a terminal
  error that identifies Secure Boot as the reason; the exact message is
  implementation-defined.
- `ENABLED_REQUIRED` on a `RequestOnly` provider reports
  `SecureBootEnforcementUnsupported`; on an `Unsupported` provider it reports
  the terminal implementation-defined error. Either rejection creates no
  allocation, external host ID, or AAP job.

#### TC-FR7-02: Rejection is terminal, visible, and never falls back

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-8 | high | automated | E3, E4, E5 |

##### Steps

1. Reconcile rejected required and unsupported-provider CRs repeatedly,
   including after controller restart.
2. Feed its status through fulfillment status synchronization.

##### Expected Results

- Each CR remains failed with an identical immutable requested value and no
  provider calls or retry schedule.
- No job is launched with a disabled request.
- Fulfillment reports `FAILED` with a Secure Boot enforcement failure, not a
  generic allocation message.

#### TC-FR7-03: Deployed BMaaS fail-closed journey and separate disabled request

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-8, IC-9 | critical | automated | E12 |

##### Steps

1. Configure the qualified provider fixture to fail final Secure Boot
   confirmation before tenant-image power-on.
2. Against true declarations, create a BMI with `--secure-boot required`.
3. Wait for its terminal result and inspect its BMFO CR and provider evidence.
4. Create a separate BMI from the same inputs with
   `--secure-boot disabled` and wait for `RUNNING`.

##### Expected Results

- The required BMI fails visibly with the provider's confirmation failure and
  never boots a tenant image; no disabled retry is launched.
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
   provider path to return `FailClosed`.
2. Exercise successful final enable/read-back and unsupported, absent, stale,
   contradictory, provider-error, and bounded-timeout outcomes.
3. Observe provider operation order and tenant-image power-on.

##### Expected Results

| Provider row | Required result |
|---|---|
| Native Metal3, BCM, or NetBox through BMO/Ironic/BMC | For each adapter proposed for support, success confirms enabled before tenant power-on; every non-success result fails with no tenant power-on and no disabled fallback. |
| Direct OpenStack/Ironic/BMC | The same outcomes and ordering hold through the direct provider path. |

No adapter may return `FailClosed` until its E9 or E10 row passes. These rows do
not change current request-only behavior. E12 validates the deployed required
journey after qualification.

#### TC-FR7-05: Current deployed adapter rejects required without allocation

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-7, IC-8 | critical | automated | E8 |

##### Preconditions

- A deployed BMaaS environment using a current request-only adapter, an
  available host, and a type/image whose
  declarations are both true.

##### Steps

1. Create a BMI with `--secure-boot required`.
2. Wait with the suite's bounded lifecycle helper for the terminal result.
3. Read the API BMI, BMFO CR, allocation state, and provider/AAP evidence.

##### Expected Results

- The BMI stores `ENABLED_REQUIRED` and fails with the curated
  `SecureBootEnforcementUnsupported` outcome before host allocation.
- No allocation, external host ID, AAP job, provider provisioning call, or
  tenant-image boot occurs, and the request is not retried with disabled
  behavior.
- The deployed API and BMFO status expose the failure consistently.

### NFR-1: Backward compatibility

##### Shared Preconditions

- New-client and pre-feature fixtures in which Secure Boot declarations or the
  BMFO requested field are absent.

#### TC-NFR1-01: Legacy omissions remain compatible and resolve to DISABLED

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
  BMI resolves `ENABLED_PREFERRED`; the first BMI remains `DISABLED`.

#### TC-NFR1-02: Legacy BMI/CR absence neither reprovisions nor changes behavior

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-7, IC-9 | high | automated | E1, E3, E4, E6, E7 |

##### Steps

1. Seed a pre-feature BMI and BMFO CR with the requested field absent, an
   existing desired-config hash, and completed provisioning history.
2. Reconcile after upgrade and after declaration changes.
3. In a separate legacy-shaped CR with the requested field absent, execute each
   provider request builder.

##### Expected Results

- Reconciliation does not synthesize a requested value, change the legacy
  hash, launch a job, or alter the completed history.
- Both provider builders map the absent field to ordinary UEFI,
  never enabled.

### NFR-2: Backend consistency

##### Shared Preconditions

- Native Metal3, BCM, NetBox, and OpenStack adapter fixtures plus serialized
  BMFO CR inputs for all three requested values and legacy absence.

#### TC-NFR2-01: BMH-path mapping sets boot mode for each execution mode

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-9 | high | automated | E7, E9 |

##### Steps

1. Execute the role's BMH patch builder with both enabled values, disabled, and
   legacy-absent inputs.

##### Expected Results

- Both enabled values yield `spec.bootMode: UEFISecureBoot`.
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

1. Execute the role's OpenStack `instance_info` builder with both enabled
   values, disabled, and legacy-absent inputs after the undeploy path clears
   old instance information.

##### Expected Results

- Both enabled values add `capabilities: {secure_boot: "true"}`.
- Disabled and legacy absence contain no `secure_boot` capability.
- The role obtains the mode from the serialized `bare_metal_instance.spec`, not
  a caller-supplied `templateParameters` key or separate launch variable.
- Image source, checksum/hash, and `root_gb` inputs remain unchanged.

#### TC-NFR2-03: Installed BMFO CRD preserves and validates the requested value

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-7 | high | automated | E6 |

##### Steps

1. Through the installed BMFO CRD, create CRs for each
   `spec.secureBootRequested` value.
2. Read the resources, attempt values outside the schema, and mutate the
   immutable field.
3. Create a legacy-shaped resource with the optional field absent.

##### Expected Results

- All three BMFO requested values round-trip without semantic collapse.
- Invalid values and field mutation are rejected by the API server.
- The legacy-shaped resource remains schema-valid.

### NFR-3: Requested behavior integrity

##### Preconditions

- A created `PREFERRED` BMI whose two source declarations were true at create.

#### TC-NFR3-01: Requested behavior survives source lifecycle and status updates

| Interface Change | Priority | Automation | Coverage |
|---|---|---|---|
| IC-4, IC-7 | high | automated | E1, E3 |

##### Steps

1. Create `PREFERRED` against true declarations and observe
   `ENABLED_PREFERRED`.
2. Change the hardware declaration to unsupported and the selected image
   declaration to incompatible, then create a later `PREFERRED` BMI from the
   updated resources.
3. Run BMFO-to-fulfillment status synchronization with unrelated status
   changes.

##### Expected Results

- BMI intention remains `PREFERRED`; API and projected BMFO values remain
  `ENABLED_PREFERRED`.
- Both source declarations are updated, but the existing BMI remains
  preferred-enabled; the later BMI resolves disabled.
- The status update mask never clears or replaces
  `status.secure_boot_requested`.

## Gaps

### Requirement Coverage Gaps

None against the merged PRD. FR-5 uses the same BMI API,
projection, admission, and provider cases regardless of origin. Current CaaS
creates omit the field and therefore exercise only the shared `PREFERRED`
default. CaaS `REQUIRED` selection is explicitly out of scope, so this plan does
not claim a deployed fail-closed CaaS journey. A future selection surface needs
its own design and tests.

Fulfillment/UI availability preflight is outside the current API/CLI scope and
has no current IC or test case; a future design must define its contract and
coverage.

Current request-only behavior is covered by the preferred success journey in
TC-FR3-04/E11 and required rejection in TC-FR7-01 and TC-FR7-05/E8.
TC-FR7-04 with E9/E10 qualifies a fail-closed provider; TC-FR7-03/E12 validates
its deployed required failure path. The OpenStack/Ironic fail-closed dependency
is tracked by
[RFE-10199](https://redhat.atlassian.net/browse/RFE-10199).

E8 and E11 exercise current admission and request behavior; neither qualifies
provider/BMC confirmation. E12 remains deferred until E9 or E10 passes.

### Interface Change Coverage Gaps

All eight active BMaaS interface changes map to cases. IC-8's `FailClosed`
branch is planned by TC-FR7-04/E9–E10 and TC-FR7-03/E12. This blocks claiming
fail-closed support, not the current request-only implementation.

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
