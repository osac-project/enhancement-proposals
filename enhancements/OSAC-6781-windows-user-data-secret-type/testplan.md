# Testplan — OSAC-6781

## Overview

- **Feature:** OSAC-6781 — Add a Dedicated Secret Type for Windows User Data
- **Total test cases:** 33 (parameterized rows count individually)
- **Requirements covered:** 9 of 10
- **Interface changes covered:** 5 of 6

The PRD has no numbered requirements. The FR/NFR identifiers below are the
design-local traceability aliases defined in the design's Proposal section;
they label the PRD clauses, Jira's UI delivery scope, and direct feature-owner
decisions without adding requirements.

## Test Case Index

| ID | Scenario | IC | Priority |
|----|----------|----|----------|
| TC-FR1-01 | Public API exposes and stores the dedicated type | IC-1 | critical |
| TC-FR1-02 | CLI creates a Windows user-data Secret | IC-3 | high |
| TC-FR1-03 | Create Secret UI exposes the dedicated type | IC-4 | high |
| TC-FR1-04 | Live console creates a Windows user-data Secret | IC-4 | high |
| TC-FR2-01 | Creation rejects invalid XML forms (6 variants) | IC-1 | high |
| TC-FR2-02 | Creation accepts format-only XML | IC-1 | high |
| TC-NFR1-01 | Creation rejects prohibited directives without external access (4 variants) | IC-1 | critical |
| TC-NFR1-02 | Validation errors and diagnostics redact Secret content | IC-1, IC-2 | critical |
| TC-NFR1-03 | Live console rejects malformed XML without exposing content | IC-4 | high |
| TC-FR3-01 | Windows VM accepts the dedicated type | IC-2 | critical |
| TC-FR3-02 | VM creation rejects OS/type mismatches (2 variants) | IC-2 | critical |
| TC-FR3-03 | VM picker filters by selected guest OS | IC-5 | critical |
| TC-FR3-04 | Live console selects and submits a compatible Windows Secret | IC-5 | high |
| TC-NFR2-01 | VM creation preserves Secret access boundaries (3 variants) | IC-2 | critical |
| TC-NFR2-02 | VM responses omit resolved Secret data | IC-2 | critical |
| TC-FR4-01 | Linux and bare-metal compatibility remains exact (3 variants) | IC-2 | critical |
| TC-FR4-02 | Bare-metal picker remains restricted to USER_DATA | IC-5 | high |
| TC-FR6-01 | Existing legacy Windows VM remains manageable | IC-2 | high |
| TC-FR7-01 | Windows user-data Secret data is immutable | IC-1 | critical |
| TC-FR8-01 | Hub-backed Windows user-data Secret is rejected | IC-1 | high |

## Test Cases

### FR-1: Expose the dedicated type through the public API, CLI, and web console

#### TC-FR1-01: Public API exposes and stores the dedicated type

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

**Steps:** 1. Create a Secret through the public API with type `WINDOWS_USER_DATA` and valid `data["userdata"]` XML. → 2. Get the Secret through the public API.
**Expected:** Create and Get return type `WINDOWS_USER_DATA`; Get returns the submitted `userdata` bytes, while the Create response follows the existing mutating-response data-omission contract.

#### TC-FR1-02: CLI creates a Windows user-data Secret

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | automated |

**Steps:** 1. Run `osac create secret --name windows-answer --type=windows-user-data --from-file=userdata=Unattend.xml` with a valid XML file. → 2. Get the Secret through the public API.
**Expected:** The command prints the created name and ID, and Get returns type `WINDOWS_USER_DATA` with `data["userdata"]` byte-equal to the file.

#### TC-FR1-03: Create Secret UI exposes the dedicated type

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | automated |

**Steps:** 1. Open the Create Secret form and select "Windows user data". → 2. Inspect the data field and type filter/label mappings.
**Expected:** The type card is selectable, the first immutable key is `userdata`, a nonempty value is required, and list/filter labels identify the type as Windows user data.

#### TC-FR1-04: Live console creates a Windows user-data Secret

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | manual |

##### Preconditions

- A live OSAC web console is connected to a deployment containing the new API
  and fulfillment-service behavior.
- A Tenant Admin or Tenant User can create Secrets in an existing project.

##### Steps

1. Sign in to the console and open Create Secret for the project.
2. Select "Windows user data", upload a valid XML value as `userdata`, and
   submit the form.
3. Open the created Secret and verify its public type through the UI or public
   API without displaying its value in a list or mutating response.

##### Expected Results

- The console reports successful creation and lists the Secret as Windows user
  data.
- Public Get reports `WINDOWS_USER_DATA`; no Secret value appears in the list
  or mutating response.

### FR-2: Require nonempty, well-formed XML at Secret creation and limit acceptance to format validation

##### Shared Preconditions

- A tenant identity may create Secrets in an existing project.
- Each request uses type `WINDOWS_USER_DATA` and a unique name.

#### TC-FR2-01: Creation rejects invalid XML forms (parameterized)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Steps

1. Call public `Secrets/Create` using the `{input}` row.
2. Get or list the attempted Secret by its unique name.

##### Expected Results

| Input | Expected Result |
|---|---|
| Missing `userdata` key | Create returns `InvalidArgument` stating that `data["userdata"]` is required and nonempty; no Secret is found. |
| Zero-length `userdata` | Create returns the same required/nonempty `InvalidArgument`; no Secret is found. |
| Whitespace-only `userdata` | Create returns `InvalidArgument` stating that a well-formed XML document with one root is required; no Secret is found. |
| Truncated/malformed XML | Create returns the fixed malformed-document `InvalidArgument`; no Secret is found. |
| Two root elements | Create returns the fixed malformed-document `InvalidArgument`; no Secret is found. |
| Non-whitespace text outside the root | Create returns the fixed malformed-document `InvalidArgument`; no Secret is found. |

#### TC-FR2-02: Creation accepts format-only XML

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

**Steps:** 1. Create a Windows user-data Secret whose value is well-formed XML with an arbitrary root that is not an Unattend schema. → 2. Get the Secret.
**Expected:** Create succeeds and Get returns the submitted bytes unchanged, demonstrating that admission checks XML form rather than Microsoft Unattend semantics.

### NFR-1: Reject directives, perform no external resolution, and keep errors content-free

##### Shared Preconditions

- A controlled HTTP endpoint records any request made to it.
- A controlled temporary local file contains a second unique sentinel.
- Each Secret value contains a unique sentinel that must not appear in API
  errors or captured fulfillment-service logs.

#### TC-NFR1-01: Creation rejects prohibited directives without external access (parameterized)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Steps

1. Call public `Secrets/Create` with `{directive input}`.
2. Inspect the gRPC status and controlled HTTP endpoint request count.

##### Expected Results

| Directive input | Expected Result |
|---|---|
| Internal DTD declaration | Create returns `InvalidArgument` naming prohibited DTD/directive input; the sentinel is absent and the HTTP request count remains zero. |
| `SYSTEM` external entity pointing at the controlled endpoint | Create returns the same content-free `InvalidArgument`; the HTTP request count remains zero. |
| `SYSTEM` external entity pointing at the controlled local file | Create returns the same content-free `InvalidArgument`; neither the file sentinel nor file contents appear in the response or logs, and no Secret is found. |
| Other XML directive token | Create returns the same content-free `InvalidArgument`; the HTTP request count remains zero. |

#### TC-NFR1-02: Validation errors and diagnostics redact Secret content

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-2 | critical | automated |

##### Steps

1. Submit malformed Windows XML containing a unique credential-like sentinel to `Secrets/Create`.
2. Through a controlled server fixture, attempt a Windows ComputeInstance create against invalid stored XML containing the same sentinel.
3. Capture both gRPC statuses and fulfillment-service structured logs.

##### Expected Results

- Both API calls return `InvalidArgument` with a rule category and no submitted
  bytes or sentinel.
- Captured logs contain the applicable safe validation reason code but no raw
  decoder error, submitted bytes, or sentinel.
- Neither rejected object is persisted.

#### TC-NFR1-03: Live console rejects malformed XML without exposing content

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-4 | high | manual |

##### Preconditions

- A live OSAC web console is connected to a deployment containing the new API
  and fulfillment-service behavior.
- A tenant identity can create Secrets in an existing project.

##### Steps

1. Open Create Secret, select "Windows user data", and submit malformed XML
   containing a unique credential-like sentinel in `userdata`.
2. Inspect the rendered error and list/Get the attempted Secret by its unique
   name through the public interface.

##### Expected Results

- The console displays an actionable malformed-XML category without the
  submitted sentinel or XML fragment.
- No Secret with the attempted name is found.

### FR-3: New Windows VM references require the dedicated type and retain image-OS checks

##### Shared Preconditions

- The tenant project contains Windows and Linux DiskImages and valid Secrets of
  both user-data types.

#### TC-FR3-01: Windows VM accepts the dedicated type

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

**Steps:** 1. Create a ComputeInstance selecting a Windows DiskImage and a valid `WINDOWS_USER_DATA` Secret by name. → 2. Get the ComputeInstance.
**Expected:** Create succeeds; Get contains the canonical Secret ID and name and retains the Windows DiskImage reference.

#### TC-FR3-02: VM creation rejects OS/type mismatches (parameterized)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Steps

1. Call `ComputeInstances/Create` using the `{image/type}` row.
2. Get or list the attempted ComputeInstance by its unique name.

##### Expected Results

| Image/type | Expected Result |
|---|---|
| Windows image with legacy `USER_DATA` | Create returns `InvalidArgument` naming `user_data_source.secret` and expected type `WINDOWS_USER_DATA`; no ComputeInstance is found. |
| Linux image with `WINDOWS_USER_DATA` | Create returns `InvalidArgument` naming `user_data_source.secret` and expected type `USER_DATA`; no ComputeInstance is found. |

#### TC-FR3-03: VM picker filters by selected guest OS

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | critical | automated |

##### Steps

1. Render the VM Access step with a project containing both Secret types and a
   Windows guest family; open the Secret picker.
2. Verify the source card, selection label, and placeholder, then select the
   Windows Secret.
3. Return to configuration, change the guest family to Linux, and reopen the
   Access step and Secret picker.
4. Repeat the guest-family change with a catalog-locked Secret policy value.

##### Expected Results

- For Windows, the query includes the project and
  `type == WINDOWS_USER_DATA`, only the Windows Secret is displayed, and the
  source and selection copy explicitly says "Windows user data".
- Changing to Linux clears the editable selected Secret rather than retaining
  its name in Formik or the eventual request payload.
- For Linux, the query includes the same project and `type == USER_DATA`, and
  only the Linux Secret is displayed.
- A catalog-locked Secret value is not silently cleared; submission remains
  subject to the server's exact-type compatibility check.

#### TC-FR3-04: Live console selects and submits a compatible Windows Secret

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | manual |

##### Preconditions

- A live console deployment contains a Windows DiskImage, a valid
  `WINDOWS_USER_DATA` Secret, and a legacy `USER_DATA` Secret in the same
  project.
- The tenant identity can create and delete ComputeInstances.

##### Steps

1. Start the Create VM wizard, select the Windows guest family and DiskImage,
   and open the user-data Secret picker.
2. Select the Windows Secret and submit the ComputeInstance request.
3. Observe the created ComputeInstance through the console or public API, then
   delete it using the normal lifecycle.

##### Expected Results

- The picker displays the `WINDOWS_USER_DATA` Secret and excludes the legacy
  `USER_DATA` Secret.
- ComputeInstance creation is accepted and its public response contains the
  canonical Secret reference without Secret data.
- Normal cleanup completes without forced finalizer removal.

### NFR-2: Preserve project/tenant boundaries and omit resolved data

#### TC-NFR2-01: VM creation preserves Secret access boundaries (parameterized)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Steps

1. As a tenant user, call `ComputeInstances/Create` with the `{reference}` row.
2. Get or list the attempted ComputeInstance by its unique name.

##### Expected Results

| Reference | Expected Result |
|---|---|
| Windows Secret in another project of the same tenant | Create returns `InvalidArgument` without Secret data; no ComputeInstance is found. |
| Windows Secret in the shared tenant | Create returns `InvalidArgument` stating shared Secrets cannot be used; no ComputeInstance is found. |
| Windows Secret owned by another tenant | Create returns a sanitized not-found/denied `InvalidArgument` without revealing the foreign Secret; no ComputeInstance is found. |

#### TC-NFR2-02: VM responses omit resolved Secret data

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

**Steps:** 1. Create and Get a Windows ComputeInstance using a Secret whose XML contains a unique sentinel. → 2. Serialize the public Create/Get responses and captured request logs.
**Expected:** Responses contain only the canonical Secret ID/name reference, and neither responses nor logs contain the `userdata` bytes or sentinel.

### FR-4: Preserve Linux USER_DATA and BareMetalInstance behavior

#### TC-FR4-01: Linux and bare-metal compatibility remains exact (parameterized)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

##### Steps

1. Create the `{workload}` using the `{type}` Secret.
2. Get or list the workload by its unique name.

##### Expected Results

| Workload | Type | Expected Result |
|---|---|---|
| Linux ComputeInstance | `USER_DATA` | Create succeeds and Get contains the canonical Secret reference. |
| BareMetalInstance | `USER_DATA` | Create succeeds and Get contains the canonical Secret reference. |
| BareMetalInstance | `WINDOWS_USER_DATA` | Create returns `InvalidArgument` expecting `USER_DATA`; no BareMetalInstance is found. |

#### TC-FR4-02: Bare-metal picker remains restricted to USER_DATA

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-5 | high | automated |

**Steps:** 1. Render `BareMetalAccessStep` for a project containing `USER_DATA` and `WINDOWS_USER_DATA` Secrets. → 2. Open its user-data Secret picker.
**Expected:** The generated CEL query contains the current-project predicate and exact `type == USER_DATA` predicate, and only the ordinary user-data Secret is displayed.

### FR-5: Document creation, use, restrictions, and validation limits

FR-5 is documentation-only and is recorded under Requirement Coverage Gaps.

### FR-6: Preserve existing VMs without migration and reject legacy type for new Windows requests

#### TC-FR6-01: Existing legacy Windows VM remains manageable

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- A PostgreSQL-backed server fixture contains a pre-feature Windows
  ComputeInstance whose canonical Secret reference points to `USER_DATA`.

##### Steps

1. Get the existing ComputeInstance through the public API.
2. Update unrelated mutable metadata with a narrow update mask that does not
   select `spec.user_data_source`.
3. Submit a full-object replacement with no update mask, changing only mutable
   metadata and preserving the canonical Secret reference.
4. Submit an update whose mask explicitly selects `spec.user_data_source` but
   resubmits the same Secret by ID or name.
5. Attempt to replace the existing reference with a different valid
   `WINDOWS_USER_DATA` Secret.
6. Attempt a new Windows ComputeInstance with the legacy Secret.

##### Expected Results

- Get and all three unchanged-reference update forms succeed; each response
  retains the stored canonical Secret ID and name.
- Replacing the reference returns the existing immutable-field
  `InvalidArgument` without changing the stored ComputeInstance.
- The new create returns the `WINDOWS_USER_DATA` type-mismatch
  `InvalidArgument`, and no new ComputeInstance is found.

### FR-7: Make data for the new type immutable

#### TC-FR7-01: Windows user-data Secret data is immutable

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

**Steps:** 1. Update `data` on an existing `WINDOWS_USER_DATA` Secret with an update mask selecting `data`. → 2. Get the Secret.
**Expected:** Update returns `InvalidArgument` stating `data` is immutable for `WINDOWS_USER_DATA`, and Get returns the original bytes.

### FR-8: Reject the new type for Hub-backed Secrets

#### TC-FR8-01: Hub-backed Windows user-data Secret is rejected

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Steps

1. Through the authorized private API, create a Secret with type
   `WINDOWS_USER_DATA`, backend `HUB`, complete Hub coordinates, and empty data.
2. Get or list the attempted Secret by its unique name.
3. Submit the equivalent request with the existing `USER_DATA` type and unique
   valid Hub coordinates.

##### Expected Results

- The Windows-type Create returns deterministic `InvalidArgument` stating that
  `WINDOWS_USER_DATA` cannot use the Hub backend, and no Secret is found.
- The existing `USER_DATA` Hub request retains its pre-feature response and
  persistence behavior.

## Gaps

### Requirement Coverage Gaps

- **FR-5** is a documentation deliverable, not runtime behavior. Review must
  verify `docs/guides/secrets-guide.md`,
  `docs/guides/developer/computeinstance-guide.md`, and the generated public
  proto comments cover the creation/use/security/compatibility contract.

All behavioral requirements have automated test cases.

### Interface Change Coverage Gaps

- **IC-6** is documentation-only. It has no behavioral test case; pre-commit
  validation and human/design review verify the files and wording.

All behavioral interface changes are exercised by test cases.

### Automation and Execution-Readiness Gaps

- **TC-FR1-04, TC-NFR1-03, and TC-FR3-04** are manual because the repository
  has no supported persisted feature-level browser suite. The existing
  `osac-ui/apps/playwright` harness permits only gitignored scratch scenarios
  for live-cluster verification; committing feature specs there is explicitly
  prohibited. No owning Jira follow-up for browser-regression infrastructure
  exists, so that automation gap remains unresolved. Story 2.04 owns manual
  execution and evidence collection.

## Planning Evidence Matrix

| Behavior / owner | Requirement / IC / test cases | Required tier and proved boundary | Existing or proposed location | Command, working directory, prerequisites | Real, simulated, and omitted dependencies |
|---|---|---|---|---|---|
| Shared enum contract (`proto`) | FR-1 / IC-1 / TC-FR1-01 | Static generation and lint; private source produces public and Go API values | `proto/private/osac/private/v1/secret_type.proto` and generated outputs | `make generate && make lint` from `proto/`; CleanAPI/Buf toolchain installed | Real generators; no runtime service or persistence |
| Secret create validation (`fulfillment-service`) | FR-2, NFR-1 / IC-1 / TC-FR2-01, TC-FR2-02, TC-NFR1-01, TC-NFR1-02 | Unit/server integration; request validation occurs before Vault/database commit | Extend `internal/servers/secret_validation_test.go`, `private_secrets_server_test.go`, and `user_data_validation_test.go` | `ginkgo run --timeout 10m internal/servers` from `fulfillment-service/`; test PostgreSQL available through suite setup | In-process real server validation and real PostgreSQL where suite fixtures apply; Vault and external HTTP endpoint controlled; no deployed API |
| Secret lifecycle/backend (`fulfillment-service`) | FR-7, FR-8 / IC-1 / TC-FR7-01, TC-FR8-01 | Unit/server integration; update-mask and private Hub admission boundary | Extend `internal/servers/private_secrets_server_test.go` | `ginkgo run --timeout 10m internal/servers` from `fulfillment-service/` | In-process servers and real test PostgreSQL; Hub fetcher/Vault controlled |
| Compute/BMI reference compatibility (`fulfillment-service`) | FR-3, NFR-2, FR-4, FR-6 / IC-2 / TC-FR3-01, TC-FR3-02, TC-NFR2-01, TC-NFR2-02, TC-FR4-01, TC-FR6-01 | Unit/server integration; exact type, access, canonicalization, masked/full/explicit legacy updates, and no-persistence boundary | Extend `internal/servers/user_data_secret_validation_test.go`, `private_compute_instances_server_test.go`, and `private_baremetal_instances_server_test.go` | `ginkgo run --timeout 10m internal/servers` from `fulfillment-service/` | In-process servers and real test PostgreSQL; tenancy, Vault, and resource dependencies controlled; no operator/AAP/provider |
| CLI token/help (`fulfillment-service`) | FR-1, FR-2 / IC-3 / TC-FR1-02 | Unit; Cobra parser, help, and request construction | Extend `internal/cmd/cli/create/secret/create_secret_cmd_test.go` | `go test ./internal/cmd/cli/create/secret` from `fulfillment-service/` | Real command/parser/filesystem; gRPC client controlled or omitted per case |
| Public Secret/VM workflow (`fulfillment-service`) | FR-1, FR-2, FR-3, NFR-2, FR-6 / IC-1, IC-2, IC-3 / TC-FR1-01, TC-FR1-02, TC-FR2-01, TC-FR3-01, TC-FR3-02, TC-NFR2-01, TC-NFR2-02 | Component integration; deployed public/private APIs, auth, storage, reference validation, and CLI | Proposed `fulfillment-service/it/it_windows_user_data_secret_test.go` | `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment` from repository root; compatible Kind cluster and installer prerequisites | Deployed Fulfillment, Keycloak/auth, PostgreSQL, and Vault; fixture DiskImages/network/storage; operator, AAP, KubeVirt, provider, and Windows guest omitted |
| Create Secret UI (`osac-ui`) | FR-1, FR-2 / IC-4 / TC-FR1-03 | Unit; rendered form choice, defaults, validation, labels, and filters | Extend colocated `Secret/CreatePage/validation.test.ts`, add/extend type-field and values tests | `pnpm run typecheck && pnpm lint && pnpm test` from `osac-ui/`; dependencies installed and API baseline deliberately advanced | jsdom and React Testing Library; Connect transport mocked; no browser or deployed API |
| VM and bare-metal picker UI (`osac-ui`) | FR-3, FR-4 / IC-5 / TC-FR3-03, TC-FR4-02 | Unit; each guest-family caller supplies the exact CEL type filter, Windows copy is explicit, and editable stale selections are cleared | Extend `libs/ui-components/src/components/Form/UserDataField.test.tsx`, VM Access/configuration step tests, and a BareMetal Access step test | `pnpm run typecheck && pnpm lint && pnpm test` from `osac-ui/` | jsdom with controlled Secret list responses and Formik state; no live browser or Fulfillment service |
| Live console creation and selection (`QE`) | FR-1, FR-2, NFR-1, FR-3 / IC-4, IC-5 / TC-FR1-04, TC-NFR1-03, TC-FR3-04 | Manual deployed UI journey; browser-to-console-to-Fulfillment request and public response | Existing `osac-ui/apps/playwright` live-cluster harness may assist execution, but scratch specs are not persisted coverage; browser automation has no owning Jira follow-up | Manual execution against a compatible live OSAC deployment; record URL/version, identity role, project, selected DiskImage/Secrets, observed responses, and cleanup result | Real console, proxy, Fulfillment, authentication, PostgreSQL, and Vault; normal deployment dependencies for ComputeInstance admission; no claim of guest customization success |
| User/API documentation (`docs`, `proto`) | FR-5 / IC-6 / gap only | Documentation/static review | `docs/guides/secrets-guide.md`, `docs/guides/developer/computeinstance-guide.md`, proto comments | Applicable pre-commit checks from repository root; human review required | No runtime boundary; not claimed as behavioral coverage |

No new provider-backed E2E row is required: the feature changes
Fulfillment admission and UI selection, while operator/AAP payloads and
`userdata`-to-`Unattend.xml` delivery remain unchanged. Existing Windows
delivery coverage continues to own that downstream boundary.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 33 |
| Critical | 18 |
| High | 15 |
| Medium | 0 |
| Low | 0 |
| Automated | 30 |
| Manual | 3 |
| Requirements with test cases | 9 / 10 |
| Interface changes with test cases | 5 / 6 |
