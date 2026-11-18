# Testplan — OSAC-6781

## Overview

- **Feature:** OSAC-6781 — Add a Dedicated Secret Type for Windows User Data
- **Total test cases:** 42 (parameterized rows count individually)
- **Requirements covered:** 9 of 10
- **Interface changes covered:** 3 of 4

The PRD has no numbered requirements. The FR/NFR identifiers below are the
design-local traceability aliases defined in the design's Proposal section;
they label the PRD clauses and direct feature-owner decisions without adding
requirements.

The existing 16 `[DEV]` groups (41 parameter-expanded cases) retain their Unit
or Fulfillment component-integration boundaries. One additional `[QE]` case,
TC-FR3-03, plans the deployed typed-Secret-to-Windows-guest journey. Public
API/CLI use alone does not make a test QE-owned; the real cross-component
provisioning and guest assertion do. Counts describe planned automation, not
executed or passing coverage. Downstream delivery behavior is unchanged.

## Test Case Index

| ID | Scenario | IC | Priority |
|----|----------|----|----------|
| TC-FR1-01 | [DEV] Public API exposes and stores the dedicated type | IC-1 | critical |
| TC-FR1-02 | [DEV] CLI creates a Windows user-data Secret | IC-3 | high |
| TC-FR2-01 | [DEV] Creation rejects invalid XML forms (9 variants) | IC-1 | high |
| TC-FR2-02 | [DEV] Creation accepts format-only XML (3 variants) | IC-1 | high |
| TC-FR2-03 | [DEV] Creation enforces the 64 KiB limit before parsing (2 variants) | IC-1 | high |
| TC-FR2-04 | [DEV] Windows XML byte and transport boundaries (7 variants) | IC-1, IC-2 | high |
| TC-NFR1-01 | [DEV] Creation rejects prohibited directives without external access (4 variants) | IC-1 | critical |
| TC-NFR1-02 | [DEV] Secret creation errors and diagnostics redact content | IC-1 | critical |
| TC-FR3-01 | [DEV] Windows VM accepts the dedicated type | IC-2 | critical |
| TC-FR3-02 | [DEV] VM creation rejects OS/type mismatches (2 variants) | IC-2 | critical |
| TC-FR3-03 | [QE] Windows guest consumes the dedicated Secret through real provisioning | IC-2 | critical |
| TC-NFR2-01 | [DEV] VM creation preserves Secret access boundaries (3 variants) | IC-2 | critical |
| TC-NFR2-02 | [DEV] VM responses omit resolved Secret data | IC-2 | critical |
| TC-FR4-01 | [DEV] Linux and bare-metal compatibility remains exact (3 variants) | IC-2 | critical |
| TC-FR6-01 | [DEV] Existing legacy Windows VM remains manageable | IC-2 | high |
| TC-FR7-01 | [DEV] Windows user-data Secret data is immutable | IC-1 | critical |
| TC-FR8-01 | [DEV] Hub-backed Windows user-data Secret is rejected | IC-1 | high |

## Test Cases

### FR-1: Expose the dedicated type through the public API and CLI

#### TC-FR1-01: [DEV] Public API exposes and stores the dedicated type

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

**Steps:** 1. Create a Secret through the public API with type `WINDOWS_USER_DATA` and valid `data["userdata"]` XML. → 2. Get the Secret through the public API.
**Expected:** Create and Get return type `WINDOWS_USER_DATA`; Get returns the submitted `userdata` bytes, while the Create response follows the existing mutating-response data-omission contract.

#### TC-FR1-02: [DEV] CLI creates a Windows user-data Secret

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-3 | high | automated |

**Steps:** 1. Run `osac create secret --name windows-answer --type=windows-user-data --from-file=userdata=Unattend.xml` with a valid XML file. → 2. Get the Secret through the public API.
**Expected:** The command prints the created name and ID, and Get returns type `WINDOWS_USER_DATA` with `data["userdata"]` byte-equal to the file.

### FR-2: Require nonempty UTF-8 XML at Secret creation and limit acceptance to format validation

##### Shared Preconditions

- A tenant identity may create Secrets in an existing project.
- Each request uses type `WINDOWS_USER_DATA` and a unique name.

#### TC-FR2-01: [DEV] Creation rejects invalid XML forms (parameterized)

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
| Attributes without separating whitespace, e.g. `<unattend a="1"b="2"/>` | Create returns the fixed malformed-document `InvalidArgument`; no Secret is found. |
| Malformed processing-instruction target, e.g. `<?a/b data?><unattend/>` | Create returns the fixed malformed-document `InvalidArgument`; no Secret is found. |
| Duplicate attributes in one start tag, e.g. `<unattend x="1" x="2"/>` | Create returns the fixed malformed-document `InvalidArgument`; no Secret is found. |
| Two root elements | Create returns the fixed malformed-document `InvalidArgument`; no Secret is found. |
| Non-whitespace text outside the root | Create returns the fixed malformed-document `InvalidArgument`; no Secret is found. |

#### TC-FR2-02: [DEV] Creation accepts format-only XML (parameterized)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Steps

1. Create a Windows user-data Secret for each XML value below.
2. Get each Secret.

##### Expected Results

| XML value | Expected result |
|---|---|
| `<?xml version="1.0"?><?setup mode?><custom-root/>` | Create succeeds and Get returns the submitted bytes unchanged. The declaration and processing instruction are accepted, and the arbitrary root demonstrates format-only validation. |
| `<unbound:custom-root unbound:setting="value"/>` | Create succeeds and Get returns the submitted bytes unchanged. XML 1.0 name syntax is checked, but prefix binding is not. |
| `<custom-root xmlns:a="urn:example" xmlns:b="urn:example" a:setting="one" b:setting="two"/>` | Create succeeds and Get returns the submitted bytes unchanged. The two attribute names are distinct under XML 1.0; expanded-name uniqueness from Namespaces in XML is not checked. |

#### TC-FR2-03: [DEV] Creation enforces the 64 KiB limit before parsing (parameterized)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | high | automated |

##### Steps

1. Call public `Secrets/Create` using the `{input}` row.
2. Get or list the attempted Secret by its unique name.

##### Expected Results

| Input | Expected Result |
|---|---|
| Well-formed XML in `userdata` exactly 65,536 bytes long | Create succeeds; Get returns the submitted bytes unchanged. |
| Malformed XML in `userdata` 65,537 bytes long | Create returns the fixed, content-free size-limit `InvalidArgument`, showing the length check ran before XML parsing; no Secret is found. |

#### TC-FR2-04: [DEV] Windows XML byte and transport boundaries (parameterized)

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1, IC-2 | high | automated |

##### Steps

1. For rows marked Secret API, call public `Secrets/Create`; for rows marked
   inline API, submit a transport-valid protobuf string to the existing
   Windows `ComputeInstances/Create` validation path.
2. For raw-byte rows, call the shared XML helper and public Secret API. For the
   invalid inline string row, test protobuf serialization/decoding separately.
3. Get successful Secrets. For rejected Secret API requests, look up the
   unique Secret name and inspect Vault write calls.

##### Expected Results

| Path | Input | Expected result |
|---|---|---|
| Secret API and inline API | Valid UTF-8 XML without an XML declaration | Both Create paths succeed; Secret Get returns the exact submitted bytes. |
| Secret API and inline API | Valid UTF-8 XML with `encoding="utf-8"` | Both paths succeed; Secret Get returns the exact submitted bytes. Encoding-name comparison is case-insensitive. |
| Secret API and inline API | Valid UTF-8 XML with a UTF-8 BOM | Both paths succeed; Secret Get returns the original bytes including the BOM. |
| Secret API and inline API | UTF-8 text with an XML declaration specifying `UTF-16` | The transport accepts the string; both paths reach the XML validator and return the fixed, content-free unsupported-encoding `InvalidArgument`. No Secret or ComputeInstance is persisted; Secret creation performs zero Vault writes. |
| Shared helper and Secret API | Actual UTF-16 bytes with a UTF-16 BOM and declaration | The helper rejects the bytes without exposing them or parser details; Secret Create returns a fixed, content-free `InvalidArgument`. No Secret is found and Secret creation performs zero Vault writes. Do not submit these bytes through the inline string field. |
| Shared helper and Secret API | Raw invalid UTF-8 byte sequence without an encoding declaration | The helper rejects the bytes without exposing them or parser details; Secret Create returns a fixed, content-free `InvalidArgument`. No Secret is found and Secret creation performs zero Vault writes. Do not submit these bytes through the inline string field. |
| Inline protobuf transport | Invalid UTF-8 bytes in `UserDataSource.inline` | Protobuf serialization or decoding rejects the value before XML validation. Do not require the validator's custom error or prescribe a particular API status. No ComputeInstance is persisted. |

### NFR-1: Reject directives, perform no external resolution, and keep errors content-free

##### Shared Preconditions

- A controlled HTTP endpoint records any request made to it.
- A controlled temporary local file contains a second unique sentinel.
- Each Secret value contains a unique sentinel that must not appear in API
  errors or captured fulfillment-service logs.

#### TC-NFR1-01: [DEV] Creation rejects prohibited directives without external access (parameterized)

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

#### TC-NFR1-02: [DEV] Secret creation errors and diagnostics redact content

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

##### Steps

1. Submit malformed Windows XML containing a unique credential-like sentinel to `Secrets/Create`.
2. Capture the gRPC status and fulfillment-service structured logs.

##### Expected Results

- The API call returns `InvalidArgument` with a rule category and no submitted
  bytes or sentinel.
- Captured logs contain the applicable safe validation reason code but no raw
  decoder error, submitted bytes, or sentinel.
- No Secret is persisted.

### FR-3: New Windows VM references require the dedicated type and retain image-OS checks

##### Shared Preconditions

- The tenant project contains Windows and Linux DiskImages and valid Secrets of
  both user-data types.

#### TC-FR3-01: [DEV] Windows VM accepts the dedicated type

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

**Steps:** 1. Create a ComputeInstance selecting a Windows DiskImage and a valid `WINDOWS_USER_DATA` Secret by name. → 2. Get the ComputeInstance.
**Expected:** Create succeeds; Get contains the canonical Secret ID and name and retains the Windows DiskImage reference.

#### TC-FR3-02: [DEV] VM creation rejects OS/type mismatches (parameterized)

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

#### TC-FR3-03: [QE] Windows guest consumes the dedicated Secret through real provisioning

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated (planned; not implemented or run) |

**Requirement mapping:** FR-3 maps to the PRD In Scope clause supporting the
new type on Windows VM Secret references while retaining image-OS checks.
Public creation also traverses FR-1/FR-2 and IC-1/IC-3; their validation
permutations remain DEV-owned. Delivery and guest consumption validate the
new typed admission integrated with the unchanged downstream path; they do
not add product answer-file generation or semantic validation. This case does
not cover FR-5 or IC-4 documentation.

##### Preconditions

- Deploy the new enum, Secret XML validation, and CLI support **and** Windows
  ComputeInstance typed-reference admission. The draft
  [Secret-type change at c8059c6](https://github.com/osac-project/osac/blob/c8059c6f12aa310212d5dd41d9db91b2fda9088d/fulfillment-service/internal/servers/user_data_secret_validation.go#L60-L78)
  still requires `USER_DATA` at the reference boundary; PR2494 alone is not
  sufficient. Confirm the deployed build supports both changes before running.
- Use an authorized tenant/project, a Windows DiskImage explicitly declaring
  the Windows OS family, and a supported generalized Windows image with
  sysprep/answer-file support. Pin the image version and its supported answer
  file pass/component. Use a fresh boot disk/guest, never a previously
  customized guest or a snapshot carrying the marker.
- Provide a **proposed, image-specific valid UTF-8 answer-file fixture**, not
  merely arbitrary well-formed XML. The fixture must be reviewed for that
  image's supported unattended pass and execute the marker creation there.
  Substitute only a run ID containing ASCII letters/digits/hyphens. It must
  create `C:\ProgramData\OSAC\E2E\<run-id>.txt` with exactly the UTF-8 bytes
  `OSAC-6781:<run-id>` (non-secret; no BOM or newline). This file/directory must not be
  pre-baked into the image. Retain the final submitted XML bytes in protected
  test storage for byte comparison; do not print XML or credentials.
- Run real Fulfillment, authentication, storage, operator, AAP, and KubeVirt
  controllers with working Windows compute/storage/network capacity. Do not
  replace resources, waits, reconciliation, or provisioning with noops/mocks.
  Give the harness narrowly scoped read access to the actual target-namespace
  Secret and VM/VMI, and cleanup access to its own resources.
- Provide a **proposed authenticated WinRM-over-HTTPS guest assertion helper**
  with certificate/hostname verification and environment-managed credentials
  from the test secret store (never requested from a user or logged). Secure
  access must already be supported by the image/test environment independently
  of the marker; the helper may read/assert but must not create the marker or
  run customization itself. Set finite provisioning and guest-access deadlines
  appropriate to the pinned image before execution and record them in results.

##### Steps

1. Allocate a unique run ID and resource names. Verify the pinned generalized
   image has no E2E marker and prepare the image-appropriate fixture with that
   ID. Save its exact final bytes as the comparison baseline before submission.
2. As the tenant, run `osac create secret --name <run-name> --type=windows-user-data --from-file=userdata=<fixture-path>`
   against the deployed public endpoint. Get the Secret through the public API
   and assert type `WINDOWS_USER_DATA` and exact `data["userdata"]` bytes.
3. Through the public ComputeInstances API create a fresh Windows
   ComputeInstance in the same project, selecting the pinned Windows DiskImage
   and the new Secret in `user_data_source.secret`. Get it and assert the
   canonical Secret ID/name and selected image. Follow its actual resource
   identity through Fulfillment, operator, AAP, and KubeVirt reconciliation;
   record correlated resource IDs and successful real provisioning outcomes.
4. Discover the actual target namespace and applied VM/VMI for this instance,
   not a rendered template. Read the Kubernetes Secret referenced by the
   sysprep volume there; base64-decode its `Unattend.xml` value and compare
   byte-for-byte with the saved submitted XML. Inspect both the applied VM
   template and active VMI: the sysprep volume references that same Secret,
   and the disk matching the volume name is a CD-ROM on the SATA bus.
5. Wait within the recorded deadlines for this fresh VMI and guest access.
   Using only the authenticated read/assert helper, read
   `C:\ProgramData\OSAC\E2E\<run-id>.txt` inside that guest and compare exact
   bytes with `OSAC-6781:<run-id>`. Correlate the guest connection with this
   run's instance/VMI; assert the run-unique marker, not just a successful
   connection, Running status, or VM template. Do not inject the marker using
   WinRM, a guest agent, or a post-provisioning helper.

##### Expected Results

- All public Secret and Windows typed-reference admission assertions succeed;
  real Fulfillment/operator/AAP/KubeVirt provision this instance without test
  task overrides. The target Secret contains exactly the submitted XML bytes
  and both actual VM/VMI resources have the required sysprep/SATA wiring.
- The fresh guest contains the exact run-unique marker created by consuming
  the supplied answer file. Only completion of **all** assertions establishes
  a pass; Running status, template/spec checks, or copying alone are not enough.
- If typed admission, image/sysprep support, valid fixture, secure guest
  tooling, or capacity is unavailable, record **BLOCKED / NOT RUN** with the
  unmet prerequisite. Do not count a skip as a pass or silently reduce this
  case to Secret/spec checks. An attempted run with a failed assertion fails.

##### Cleanup

1. In a finally/teardown path, delete the ComputeInstance through the public
   API and wait with a bounded deadline for its VM/VMI and owned target Secret,
   disks, and other run-created resources to be removed by real reconciliation.
2. Delete the public source Secret after the instance is gone; remove only
   run-owned fixtures/local protected XML copies and temporary access material.
   Do not delete shared images or environment-managed credentials. Report any
   leaked resources or failed cleanup separately; never conceal them as a pass.

##### Proposed Automation and Selection

QE owns proposed `tests/e2e/vmaas/sanity/test_windows_user_data_secret.py`, an
image-specific fixture under proposed `tests/e2e/vmaas/fixtures/windows/`, and
the secure guest assertion helper. None is claimed to exist or run today.
After implementation, select the proposed file explicitly in the existing
VMaaS pytest container/environment, e.g.
`pytest tests/e2e/vmaas/sanity/test_windows_user_data_secret.py` from the OSAC
repository root. The VMaaS CI caller must use the implementing test ref and
select this case with all prerequisites; record collected/executed/pass counts
and any blocked reason. This is a proposed invocation, not current CI wiring
or evidence of execution. No E2E implementation or provisioning is performed
by this plan revision.

### NFR-2: Preserve project/tenant boundaries and omit resolved data

#### TC-NFR2-01: [DEV] VM creation preserves Secret access boundaries (parameterized)

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

#### TC-NFR2-02: [DEV] VM responses omit resolved Secret data

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | critical | automated |

**Steps:** 1. Create and Get a Windows ComputeInstance using a Secret whose XML contains a unique sentinel. → 2. Serialize the public Create/Get responses and captured request logs.
**Expected:** Responses contain only the canonical Secret ID/name reference, and neither responses nor logs contain the `userdata` bytes or sentinel.

### FR-4: Preserve Linux USER_DATA and BareMetalInstance behavior

#### TC-FR4-01: [DEV] Linux and bare-metal compatibility remains exact (parameterized)

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

### FR-5: Document creation, use, restrictions, and validation limits

FR-5 is documentation-only and is recorded under Requirement Coverage Gaps.

### FR-6: Preserve existing VMs without migration and reject legacy type for new Windows requests

#### TC-FR6-01: [DEV] Existing legacy Windows VM remains manageable

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-2 | high | automated |

##### Preconditions

- A PostgreSQL-backed server fixture contains a pre-feature Windows
  ComputeInstance whose canonical Secret reference points to `USER_DATA`.
- A second fixture contains a pre-feature Windows ComputeInstance whose inline
  value is `<legacy:unattend/>` with no namespace declaration.

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
6. Submit the request shape produced by an older client: attempt a new Windows
   ComputeInstance with the legacy `USER_DATA` Secret.
7. Update the second existing ComputeInstance with an update mask selecting
   `spec.user_data_source`, resubmitting its exact inline value.

##### Expected Results

- Get and all three unchanged-reference update forms succeed; each response
  retains the stored canonical Secret ID and name.
- Replacing the reference returns the existing immutable-field
  `InvalidArgument` without changing the stored ComputeInstance.
- The old-client request receives the intentional `WINDOWS_USER_DATA`
  type-mismatch `InvalidArgument`, and no new ComputeInstance is found. This
  version-skew combination is unsupported and requires the user to update the
  client.
- The explicitly masked update of the unchanged inline value succeeds. The
  update re-runs XML validation, which accepts the unbound prefix under the
  XML 1.0 profile; it does not rely on an unchanged-value validation bypass.

### FR-7: Make data for the new type immutable

#### TC-FR7-01: [DEV] Windows user-data Secret data is immutable

| Interface Change | Priority | Automation |
|-----------------|----------|------------|
| IC-1 | critical | automated |

**Steps:** 1. Update `data` on an existing `WINDOWS_USER_DATA` Secret with an update mask selecting `data`. → 2. Get the Secret.
**Expected:** Update returns `InvalidArgument` stating `data` is immutable for `WINDOWS_USER_DATA`, and Get returns the original bytes.

### FR-8: Reject the new type for Hub-backed Secrets

#### TC-FR8-01: [DEV] Hub-backed Windows user-data Secret is rejected

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

All behavioral requirements have planned automated test cases; this is not an
execution claim. FR-3's full-stack delivery/guest-consumption boundary remains
unproved until TC-FR3-03 is implemented and passes with its prerequisites.

### Interface Change Coverage Gaps

- **IC-4** is documentation-only. It has no behavioral test case; pre-commit
  validation and human/design review verify the files and wording.

All behavioral interface changes have planned cases. IC-2's typed-reference
admission through real Windows provisioning and guest consumption is not yet
established by executed coverage; TC-FR3-03 is the planned QE closure.

## Planning Evidence Matrix

| Behavior / owner | Requirement / IC / test cases | Required tier and proved boundary | Existing or proposed location | Command, working directory, prerequisites | Real, simulated, and omitted dependencies |
|---|---|---|---|---|---|
| Shared enum contract (`proto`) | FR-1 / IC-1 / TC-FR1-01 | Static generation and lint; private source produces public and Go API values | `proto/private/osac/private/v1/secret_type.proto` and generated outputs | `make generate && make lint` from `proto/`; CleanAPI/Buf toolchain installed | Real generators; no runtime service or persistence |
| Secret create validation (`fulfillment-service`) | FR-2, NFR-1 / IC-1 / TC-FR2-01, TC-FR2-02, TC-FR2-03, TC-FR2-04, TC-NFR1-01, TC-NFR1-02 | Unit/server integration; request validation occurs before Vault/database commit | Extend `internal/servers/secret_validation_test.go`, `private_secrets_server_test.go`, and `user_data_validation_test.go` | `ginkgo run --timeout 10m internal/servers` from `fulfillment-service/`; test PostgreSQL available through suite setup | In-process real server validation and real PostgreSQL where suite fixtures apply; Vault and external HTTP endpoint controlled; no deployed API |
| Secret lifecycle/backend (`fulfillment-service`) | FR-7, FR-8 / IC-1 / TC-FR7-01, TC-FR8-01 | Unit/server integration; update-mask and private Hub admission boundary | Extend `internal/servers/private_secrets_server_test.go` | `ginkgo run --timeout 10m internal/servers` from `fulfillment-service/` | In-process servers and real test PostgreSQL; Hub fetcher/Vault controlled |
| Compute/BMI reference compatibility (`fulfillment-service`) | FR-2, FR-3, NFR-2, FR-4, FR-6 / IC-2 / TC-FR2-04, TC-FR3-01, TC-FR3-02, TC-NFR2-01, TC-NFR2-02, TC-FR4-01, TC-FR6-01 | Unit/server integration; Windows inline UTF-8 validation, exact type, access, canonicalization, masked/full/explicit legacy updates, and no-persistence boundary | Extend `internal/servers/user_data_secret_validation_test.go`, `private_compute_instances_server_test.go`, and `private_baremetal_instances_server_test.go` | `ginkgo run --timeout 10m internal/servers` from `fulfillment-service/` | In-process servers and real test PostgreSQL; tenancy, Vault, and resource dependencies controlled; no operator/AAP/provider |
| CLI token/help (`fulfillment-service`) | FR-1, FR-2 / IC-3 / TC-FR1-02 | Unit; Cobra parser, help, and request construction | Extend `internal/cmd/cli/create/secret/create_secret_cmd_test.go` | `go test ./internal/cmd/cli/create/secret` from `fulfillment-service/` | Real command/parser/filesystem; gRPC client controlled or omitted per case |
| Public Secret/VM workflow (`fulfillment-service`) | FR-1, FR-2, FR-3, NFR-2, FR-6 / IC-1, IC-2, IC-3 / TC-FR1-01, TC-FR1-02, TC-FR2-01, TC-FR2-03, TC-FR2-04, TC-FR3-01, TC-FR3-02, TC-NFR2-01, TC-NFR2-02 | Component integration; deployed public/private APIs, auth, storage, reference validation, and CLI | Proposed `fulfillment-service/it/it_windows_user_data_secret_test.go` | `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment` from repository root; compatible Kind cluster and installer prerequisites | Deployed Fulfillment, Keycloak/auth, PostgreSQL, and Vault; fixture DiskImages/network/storage; operator, AAP, KubeVirt, provider, and Windows guest omitted |
| User/API documentation (`docs`, `proto`) | FR-5 / IC-4 / gap only | Documentation/static review | `docs/guides/secrets-guide.md`, `docs/guides/developer/computeinstance-guide.md`, proto comments | Applicable pre-commit checks from repository root; human review required | No runtime boundary; not claimed as behavioral coverage |
| Typed Secret to Windows guest (`QE`) | FR-3 / IC-2 / TC-FR3-03; traverses FR-1, FR-2 / IC-1, IC-3 | Planned full-stack E2E; public typed admission, real delivery, and guest consumption | Proposed `tests/e2e/vmaas/sanity/test_windows_user_data_secret.py`, Windows fixture and secure guest helper | Proposed explicit pytest file selection above, OSAC root in VMaaS test environment; deployed typed admission, supported image, fixture, secure guest access, capacity required | Real Fulfillment/auth/storage, operator, AAP, KubeVirt, target Secret/VM/VMI and Windows guest; no noops; not implemented or run |

### Existing Coverage Evidence and Remaining Gap

At public OSAC revision `04cdccad4238f097eeb3f0c591068824101afa75`,
[AAP TC3.5](https://github.com/osac-project/osac/blob/04cdccad4238f097eeb3f0c591068824101afa75/osac-aap/tests/integration/targets/compute_instance_create/tasks/sysprep_secret_copy.yml#L20-L209)
creates an `Opaque` Kubernetes source Secret, noops resources/wait tasks, and
checks exact `userdata`-to-`Unattend.xml` copying and generated sysprep/SATA
specs. The [runner selects it](https://github.com/osac-project/osac/blob/04cdccad4238f097eeb3f0c591068824101afa75/osac-aap/tests/integration/run_tests.sh#L184-L218)
through the [AAP CI job](https://github.com/osac-project/osac/blob/04cdccad4238f097eeb3f0c591068824101afa75/.github/workflows/tests.yml#L309-L352).
This is DEV component coverage, not Fulfillment typed admission or real VM
provisioning/guest consumption. The existing
[generic VM lifecycle E2E](https://github.com/osac-project/osac/blob/04cdccad4238f097eeb3f0c591068824101afa75/tests/e2e/vmaas/sanity/test_compute_instance_creation.py#L26-L82)
uses the [Fedora image fixture](https://github.com/osac-project/osac/blob/04cdccad4238f097eeb3f0c591068824101afa75/tests/e2e/vmaas/conftest.py#L173-L188),
not a Windows guest. Thus existing tests do not establish the full typed-Secret
journey. TC-FR3-03 adds planned QE validation without changing downstream
delivery implementation. No live E2E was run in this revision; fixture/helper
implementation, CI selection, and successful guest evidence remain pending.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 42 |
| Critical | 18 |
| High | 24 |
| Medium | 0 |
| Low | 0 |
| Automated (planned) | 42 |
| Manual | 0 |
| DEV groups / expanded cases | 16 / 41 |
| QE groups / expanded cases (planned) | 1 / 1 |
| Requirements with test cases | 9 / 10 |
| Interface changes with test cases | 3 / 4 |

---

## Provenance

Authored: draft @ design 0.14.0 - 70405a6, workspace ibengal/secret-type-for-Windows-user-data @ d902bd8a1
Final: respond @ design 0.15.0 - 87d14ea, workspace ibengal/secret-type-for-Windows-user-data @ d902bd8a1

> Context changed between draft and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.15.0","ai_workflows":"87d14ea","source_repo":"d902bd8a1","source_repo_branch":"ibengal/secret-type-for-Windows-user-data","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","draft","revise","revise","revise","revise","revise","respond","respond","respond","respond","revise","respond","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
