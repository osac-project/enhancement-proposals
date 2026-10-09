# Testplan — OSAC-5675

## Overview

- **Feature:** [OSAC-5672](https://redhat.atlassian.net/browse/OSAC-5672) — Validate CPU architecture compatibility.
- **Design:** [design.md](design.md).
- **Total test cases:** 23.
- **Requirements with planned cases:** 9 of 9 published In Scope bullets, including their cross-cutting constraints.
- **Interface changes with planned cases:** 6 of 6.
- **Execution status:** no implementation tests executed; new scenarios are planned extensions, not current passing coverage.
- **Test focus:** the new type constraint, image/type comparison, legacy correction, CLI/UI behavior, and related documentation. Existing behavior is exercised where the added validation or correction path could affect it.
- **Scope:** use the effective-type selection contract proposed in [PR #1451](https://github.com/osac-project/osac/pull/1451); this feature preserves its defaults and adds no new template fields. DiskImage retains its existing enum transport. [User]

## Coverage and Execution Evidence

The numbered IS anchors map exactly to the published PRD In Scope bullets; the original PRD has no FR/NFR identifiers. Non-functional confidentiality, lifecycle, and stable-error assertions remain mapped to their source IS bullets rather than invented NFRs. Documentation review uses `—` because it is not an interface change. Each case's Coverage line identifies its tier/owner and the execution environment below. All cases are planned; none of the feature behavior has been executed during drafting.

| Environment | Tier / owner | Existing suite or proposed location; command and CWD | Real boundary / omitted dependencies | Prerequisites and gaps |
|-------------|--------------|-----------------------------------------------------|------------------------------------|------------------------|
| E1 | Unit / DEV | Existing `fulfillment-service/internal/validation/baremetal_hardware_spec_contract_test.go`, CLI co-located tests, `internal/controllers/baremetalinstance/baremetalinstance_reconciler_function_test.go`; `ginkgo run -r internal` from fulfillment-service, as documented in its AGENTS.md | Validation/mapping/CLI/reconciler logic; external service and Kubernetes clients mocked in isolated cases | Go/Ginkgo; pure contract validation is Unit even where filenames say contract; not a live service/CR boundary |
| E2 | Contract / DEV | Proposed `fulfillment-service/ct/baremetalarchitecture/`: a running fulfillment service with PostgreSQL plus envtest; actual reconciler driven explicitly. Runner and bootstrap command not yet defined | Fulfillment service persistence and a real Kubernetes API server/etcd; in-process reconciler. No operator/AAP/provider/hardware | New harness, test assets, auth fixture, and runner required. Owning feature-specific implementation ticket unresolved; do not substitute the fake-client Unit suite |
| E3 | Component integration / DEV | Existing `fulfillment-service/it/it_private_baremetal_instance_types_test.go`, `it_baremetal_instance_lifecycle_test.go`, catalog/default/lifecycle/tenant-isolation/CLI suites; root: `make -C osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment`; command defined in osac-installer/Makefile | Deployed fulfillment service, PostgreSQL, CLI, Kind. Target explicitly sets `service.controller.sync=false`; provider/controller progression omitted | Fresh dedicated Kind/database, auth and CRD fixtures. Synthetic legacy data needs a controlled pre-validation fixture. This command does not prove CR suppression |
| E4 | Unit / DEV | Existing type wizard/detail and BareMetalConfigurationStep tests; `pnpm test` from osac-ui. Independently `pnpm run typecheck` and `pnpm lint` per osac-ui/AGENTS.md | React behavior with in-memory Connect transport; no proxy/deployed service/provider | pnpm dependencies; generated baseline deliberately advanced; typecheck/lint are static checks, not integration coverage |
| E5 | E2E / QE | Existing `tests/e2e/bmaas/sanity/test_baremetal_instance_lifecycle.py`; root: `uv run pytest tests/e2e/bmaas/sanity/test_baremetal_instance_lifecycle.py`. Proposed focused `tests/e2e/bmaas/regression/test_cpu_architecture_compatibility.py`; its runner follows the existing pytest harness after implementation | Deployed fulfillment service, including its reconciler, and Kubernetes/operator/AAP/provider journey | PR #1451 supplies the instance-type fixture; extend it with the architecture cases and prepared noncanonical data. Source-pinned deployment, hub/auth access and hosts/images required. New regression file and feature-specific QE owner ticket unresolved. Existing provider gaps: [OSAC-4843](https://redhat.atlassian.net/browse/OSAC-4843), [OSAC-4850](https://redhat.atlassian.net/browse/OSAC-4850) do not substitute for this feature's ownership |
| E6 | E2E manual verification / QE | Existing osac-ui/apps/playwright manual harness; `pnpm playwright:setup`, then `pnpm playwright:run` from osac-ui, per osac-ui/AGENTS.md | Browser, deployed console proxy and fulfillment service; actual catalog controls and service errors | Existing live deployment/auth required. UI regression uses E4; this environment supplies deployed manual verification |
| E7 | Component integration database boundary / DEV | Existing internal/servers tests; `ginkgo run internal/servers` from fulfillment-service | In-process handlers and real PostgreSQL container; tenancy/attribution mocked; no Kubernetes/provider | Container runtime; seed synthetic legacy objects below new-write validation only in the controlled fixture. Disclosure required despite the guide's broad Unit label for internal/ |
| E8 | Documentation review / DEV | API/CLI/provider/tenant docs in owning components and docs/; applicable pre-commit on touched files | Review against the final schema/behavior; no running services | Owner reviews the final contract and documented selection/default resolution; no executable doc test proves provisioning |

The following rows are the behavior-to-boundary evidence matrix. A case can appear in more than one row because Unit handling and a real boundary are distinct assertions.

| Behavior; source / interface | Case IDs | Required tier and owner | Suite / environment to extend | Execution readiness |
|-----------------------------|----------|-------------------------|-------------------------------|---------------------|
| Compatibility after CatalogItem or direct-template selection; IS-1 / IC-2 | TC-IS1-01, TC-IS1-02 | Component integration, DEV | Catalog/instance/template API suites, E3; merged-candidate DB assertions, E7 | Existing reference-resolution paths identified; no new template schema |
| Canonical type input constraint; IS-2, IS-3 / IC-1 | TC-IS3-01 | Unit and component integration, DEV | Validation E1; API/database E3/E7 | Existing harnesses for the changed type constraint |
| CLI architecture input/display and legacy correction; IS-2, IS-3, IS-6 / IC-4, IC-3 | TC-IS2-02, TC-IS3-02, TC-IS6-02 | Unit and component integration, DEV | Specialized CLI co-located E1 plus deployed CLI/API E3 | Existing harnesses; implementation not present |
| UI canonical controls, visible disabled choices and changed defaults; IS-2, IS-7 / IC-5 | TC-IS2-03, TC-IS7-01, TC-IS7-02, TC-IS7-03 | Unit, DEV | UI tests E4 | Existing harness; cover CatalogItem defaults and caller-selected references |
| Nine-pair matrix, multi-architecture, dry-run and rollback; IS-4 / IC-2 | TC-IS4-01, TC-IS4-02 | Unit and database/component integration, DEV | Comparison E1; server/database E7 and API E3 | Existing harnesses; no feature execution |
| Drift/no CR creation or provisioning patch, recovery/status persistence; IS-4 / IC-6 | TC-IS4-03 | Unit plus Contract, DEV | Reconciler fake-client E1 plus real E2 | Unit harness exists; real Contract harness missing |
| Non-provisioning updates and guarded user-data migration; IS-5 / IC-2 | TC-IS5-01, TC-IS5-02 | Component integration plus Contract, DEV | API/database E3/E7; CR fields/status E2 | API paths identified; real projection harness missing |
| Legacy readability, provisioning rejection, correction and denial/conflicts; IS-6 / IC-2, IC-3 | TC-IS6-01, TC-IS6-02, TC-IS6-03 | Component integration, DEV | API/database/CLI E3/E7; provider UI controls E4 | Controlled legacy fixture required; implementation not present |
| Hidden references, lifecycle precedence, warning preservation; IS-8 / IC-2 | TC-IS8-01, TC-IS8-02 | Component integration, DEV | Tenant/lifecycle API suites E3/E7 | Existing harnesses |
| Safe returned compatibility status; IS-8 / IC-6 | TC-IS8-03 | Unit plus Contract, DEV | Reconciler E1 and real E2 | Contract execution not ready |
| Documentation of architecture validation and correction; IS-9 / — | TC-IS9-01 | Documentation review, DEV | E8 | Depends on final decisions |
| Deployed explicit-type BMaaS and inherited private caller; IS-9 / IC-2 | TC-IS9-03 | E2E, QE | E5; proposed focused regression file | New cases/fixtures/deployment needed; owner ticket unresolved |
| Browser/persona behavior with real API; IS-9 / IC-5 | TC-IS9-04 | E2E manual verification, QE | E6 | Existing manual harness; UI regression uses E4 |

E2 Contract assertions cannot execute until the proposed runner is implemented; fake-client Unit checks do not replace them. For Contract assertions, explicitly invoke the actual outer reconciler with persisted state and inspect CR writes and stored status when it returns. For deployed lifecycle progression, use the existing fixture/helper polling limits and fail when they expire. Establish a rejected Create through its response and absent admitted identity; establish a blocked projection through ConfigurationApplied=False with reason ValidationFailed and the architecture-error message before checking that provisioning fields remain unchanged.

## Test Cases

### Shared request data

Use the existing suite builders for valid hardware, template, image source, and authentication fields. The following labels identify architecture variants of those fixtures; use the IDs returned by Create and unique names per test. BareMetalInstanceType references set `shared=true`, as required by the existing platform-scoped type contract. DiskImage references retain the scope of their fixture.

| Fixture label | Architecture declaration |
|---------------|--------------------------|
| type-amd64 | `spec.hardware.cpu.architecture = "amd64"` |
| type-arm64 | `spec.hardware.cpu.architecture = "arm64"` |
| type-s390x | `spec.hardware.cpu.architecture = "s390x"` |
| image-amd64 | `spec.architecture = [ARCHITECTURE_AMD64]` |
| image-arm64 | `spec.architecture = [ARCHITECTURE_ARM64]` |
| image-s390x | `spec.architecture = [ARCHITECTURE_S390X]` |
| image-multi | `spec.architecture = [ARCHITECTURE_AMD64, ARCHITECTURE_ARM64]` |

For `BareMetalInstances.Create`, set `object.metadata.name` to the unique request name and supply the template/catalog reference and valid authentication from the existing fixture. Set `object.spec.instance_type.id` and `object.spec.disk_image.id` to the selected fixture IDs. Omit only the references being supplied by catalog/template selection in IS-1. Provider-only type Create/Update calls use the private service; instance calls use public/private clients where exposed. Field paths below use protobuf names.

### IS-1: Effective selections after existing defaults and reference resolution

#### TC-IS1-01: Compatibility uses effective CatalogItem selections

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-2 | critical | automated |

**Coverage:** Component integration / DEV, E3.

##### Preconditions

A template and visible canonical types/images exist. Prepare locked and editable CatalogItems whose image/type defaults include matching and mismatching pairs.

##### Steps

1. Call `BareMetalInstances.Create` with `object.spec.catalog_item.id` set and `instance_type`/`disk_image` omitted. Use catalog defaults selecting type-amd64 with image-amd64, then type-amd64 with image-arm64.
2. For an editable catalog, repeat with explicit `object.spec.instance_type.id` and `object.spec.disk_image.id` selecting matching and mismatching pairs. For accepted requests, inspect `response.object.spec.instance_type.id` and `response.object.spec.disk_image.id`.

##### Expected Results

1. Compatibility is evaluated against the effective image/type pair. Matching defaults or overrides are accepted; mismatching pairs return InvalidArgument with INCOMPATIBLE_DISK_IMAGE_ARCHITECTURE and leave no persisted instance.

#### TC-IS1-02: Caller and template-provided instance types receive the same validation

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-2 | critical | automated |

**Coverage:** Component integration / DEV, E3 and E7.

##### Preconditions

A visible template supplies type-amd64 under the PR #1451 contract. type-arm64, image-amd64, and image-arm64 are visible. Retain the existing template/authentication fixture fields.

##### Steps

1. Call `BareMetalInstances.Create` with `object.spec.template.id` set, `instance_type` omitted, and `disk_image.id` selecting image-amd64; repeat with image-arm64.
2. Set `object.spec.instance_type.id` to type-arm64 and `shared=true`; repeat with image-arm64 and image-amd64.
3. Repeat using reference `name` instead of `id`, preserving each reference's scope.

##### Expected Results

1. The fulfillment service compares the resolved effective pair, including a template-provided type. Matching requests are accepted; mismatches return InvalidArgument with INCOMPATIBLE_DISK_IMAGE_ARCHITECTURE and leave no persisted instance.

### IS-2: Canonical vocabulary across UI, CLI, and API

#### TC-IS2-02: DiskImage describe displays canonical architecture labels

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-4 | high | automated |

**Coverage:** Unit and component integration / DEV, E1 and E3.

##### Preconditions

The CLI can read an image for each supported architecture and a multi-architecture image.

##### Steps

1. Run `describe diskimage <image-id>` for image-amd64, image-arm64, image-s390x, and image-multi; inspect the architecture labels in the command output.

##### Expected Results

1. Architecture labels are amd64, arm64, and s390x. Every declared member of a multi-architecture image is displayed; uppercase enum-derived labels and aliases are absent.

#### TC-IS2-03: UI type creation offers and submits canonical architecture choices

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-5 | high | automated |

**Coverage:** Unit / DEV, E4.

##### Preconditions

The type creation form uses mock Connect transport with valid remaining hardware fields.

##### Steps

1. Open the type creation form and inspect the architecture choices.
2. Select amd64, arm64, and s390x in separate submissions. Capture the Connect request and inspect `object.spec.hardware.cpu.architecture`.

##### Expected Results

1. The selector offers exactly amd64, arm64, and s390x. Each selection submits the corresponding exact lowercase string; arbitrary free-text architecture input is unavailable.

### IS-3: Exact inputs; aliases, case, whitespace, and unknown values rejected

#### TC-IS3-01: Type architecture validation accepts canonical strings and rejects variants

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-1 | critical | automated |

**Coverage:** Unit and component integration / DEV, E1 and E3/E7.

##### Preconditions

Valid remaining hardware fields are supplied. Prepare amd64, arm64, s390x and invalid inputs x86_64, aarch64, AMD64, ARM64, leading/trailing spaces, empty string, and ppc64le.

##### Steps

1. Set `spec.hardware.cpu.architecture` to each listed value in otherwise valid public/private type messages and run the changed schema validation in E1.
2. Call private `BareMetalInstanceTypes.Create` with each value in `object.spec.hardware.cpu.architecture`; inspect the returned value or gRPC error.
3. For the seeded legacy type, call private `BareMetalInstanceTypes.Update` with its `object.id`, each invalid replacement, and `update_mask.paths=["spec.hardware.cpu.architecture"]`. Read the stored architecture after each rejection.

##### Expected Results

1. The three canonical strings are accepted. Every invalid write returns InvalidArgument identifying the architecture field and accepted values amd64, arm64, s390x. No invalid value is trimmed, lowercased, mapped, or persisted.

#### TC-IS3-02: Specialized CLI architecture flags reject noncanonical input

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-4 | high | automated |

**Coverage:** Unit and component integration / DEV, E1 and E3.

##### Preconditions

CLI is configured for the component-integration fulfillment service; valid remaining arguments are provided.

##### Steps

1. For each invalid variant from TC-IS3-01, run `create baremetalinstancetype --cpu-architecture <value>` and `create diskimage --architecture <value>` with valid remaining fixture arguments. Capture the exit code and error output.
2. Repeat with amd64, arm64, and s390x; inspect the submitted type string and image enum.

##### Expected Results

1. Invalid architecture flags exit nonzero and list the three allowed names; no resource is created. Canonical type flags submit exact strings, and canonical image flags submit the corresponding existing enum values.

### IS-4: Image membership, multi-architecture matching, and early mismatch errors

#### TC-IS4-01: Exhaustive single-architecture compatibility matrix

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-2 | critical | automated |

**Coverage:** Unit and component integration / DEV, E1 and E3/E7.

##### Preconditions

Three canonical types and three single-architecture images are visible and available.

##### Steps

1. In E1, pass each of the three type fixtures and three single-architecture image fixtures to the proposed comparison helper: all nine ordered type/image pairs.
2. For each pair, call public/private `BareMetalInstances.Create` using the shared request fields and a fresh `object.metadata.name`. Inspect `response.object` for acceptance or the gRPC status/message for rejection.
3. Repeat the six mismatches with gRPC metadata `x-dry-run: true`, using the existing dry-run context helper for in-process handler tests.
4. After each rejection, call `BareMetalInstances.List` with `filter='this.metadata.name == "<request-name>"'` and assert that `items` is empty.

##### Expected Results

1. The three matching pairs are accepted. Each of six mismatches returns InvalidArgument with INCOMPATIBLE_DISK_IMAGE_ARCHITECTURE, the selected authorized resources and their required/supported architectures, and corrective guidance. Rejected requests, including dry-run, leave no persisted instance.

#### TC-IS4-02: Every matching member of a multi-architecture image is accepted

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-2 | critical | automated |

**Coverage:** Unit and component integration / DEV, E1 and E3/E7.

##### Preconditions

An image declares amd64 and arm64 in both list orders; an s390x type and matching amd64/arm64 types exist.

##### Steps

1. Pass image-multi with type-amd64, type-arm64, and type-s390x to the proposed comparison helper.
2. Call `BareMetalInstances.Create` with each of those pairs and a fresh name. Inspect the accepted object or mismatch status/message.
3. Repeat with the image architecture list reversed to `[ARCHITECTURE_ARM64, ARCHITECTURE_AMD64]`.

##### Expected Results

1. amd64 and arm64 succeed regardless of list order. s390x returns INCOMPATIBLE_DISK_IMAGE_ARCHITECTURE. Compatibility uses membership rather than the first architecture.

#### TC-IS4-03: Catalog drift blocks first CR creation and changed provisioning inputs

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-6 | critical | automated |

**Coverage:** Unit and Contract / DEV, E1 and E2.

##### Preconditions

E2 has two persisted instances selecting type-amd64/image-multi: one before first CR creation, and one with an existing CR whose provisioning fields are captured. Change the type's mutable `spec.host_label_selector` through provider Update to produce a pending selector projection for the second instance; retain all other fixture fields.

##### Steps

1. Call `DiskImages.Update` for image-multi with `object.spec.architecture=[ARCHITECTURE_ARM64]` and `update_mask.paths=["spec.architecture"]`.
2. Explicitly invoke the actual outer reconciler for each instance. Query the Kubernetes API for CR absence/unchanged provisioning fields, then `BareMetalInstances.Get(id)` for persisted `object.status`.
3. Restore `[ARCHITECTURE_AMD64, ARCHITECTURE_ARM64]` through the same image Update, invoke each reconciler again, and reread the CR and persisted status.

##### Expected Results

1. Before correction, no first CR is created and an existing CR's provisioning fields remain byte-for-byte unchanged. ConfigurationApplied=False with reason ValidationFailed and the safe comparison message is persisted. After correction, the next explicit invocation writes the compatible configuration, clears the architecture validation failure, and resumes existing condition synchronization. With an existing CR its observed state is retained; without a CR the existing FAILED state is used.

### IS-5: Provisioning-changing requests guarded; other management preserved

#### TC-IS5-01: Non-provisioning updates remain possible under catalog incompatibility

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-2 | critical | automated |

**Coverage:** Component integration and Contract / DEV, E3/E7 for API behavior and E2 for CR projections.

##### Preconditions

An instance and CR exist with known applied provisioning fields and an incompatible current image/type catalog. Exercise running and stopped observations.

##### Steps

1. Call `BareMetalInstances.Update` with `object.id`, a changed `object.metadata.labels`, and `update_mask.paths=["metadata.labels"]`.
2. On the private service, update `object.status.state` with mask `["status.state"]`. Separately update `object.spec.run_strategy` to HALTED and ALWAYS with mask `["spec.run_strategy"]`, and increment `object.spec.restart_trigger` with mask `["spec.restart_trigger"]`.
3. Invoke reconciliation after each update and read the CR. Also submit the current full object with unchanged provisioning references/parameters and no mask.
4. Repeat metadata/HALTED updates for the persisted instance without a CR and query the Kubernetes API after reconciliation.

##### Expected Results

1. Requests are not rejected solely for architecture incompatibility. Identical provisioning values do not trigger the comparison. CR metadata/power/restart fields follow the permitted request while incompatible provisioning fields retain their prior values.
2. Accepting a metadata/stop request does not create a CR for an incompatible pair.

#### TC-IS5-02: Provisioning-changing user-data migration receives the guard

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-2 | critical | automated |

**Coverage:** Component integration and Contract / DEV, E3/E7 for admission and E2 for downstream parameters.

##### Preconditions

An instance uses inline user data and permits the existing atomic migration. A visible Secret contains nonempty `data["userdata"]`; capture the stored user-data fields and applied CR parameters. The selected catalog pair is incompatible.

##### Steps

1. Call `BareMetalInstances.Update` with `object.id`, `object.spec.user_data=""`, `object.spec.user_data_secret.id=<secret-id>`, and `update_mask.paths=["spec.user_data", "spec.user_data_secret"]`.
2. After rejection, call `BareMetalInstances.Get(id)` and compare the stored user-data fields with the captured values.
3. Restore the image's compatible architecture list, repeat the same migration, invoke reconciliation, and inspect the stored references and projected user-data parameters.

##### Expected Results

1. The incompatible migration returns InvalidArgument with INCOMPATIBLE_DISK_IMAGE_ARCHITECTURE and preserves stored user-data references and provisioning parameters. The compatible migration succeeds and projects the intended user-data parameters.

### IS-6: Legacy visibility, correction, and canonical-only new provisioning

#### TC-IS6-01: Legacy types remain readable and cannot serve new provisioning

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-2 | critical | automated |

**Coverage:** Component integration and Contract / DEV, E3/E7 for API behavior, E4 for UI visibility and E2 for CR absence.

##### Preconditions

Seed synthetic legacy types with x86_64, aarch64, uppercase, whitespace, and unknown architectures in a controlled pre-validation database fixture. Each has stable ID and valid remaining hardware.

##### Steps

1. Call `BareMetalInstanceTypes.Get(id)` and `List` for each seeded legacy type, run its CLI describe command, and render the provider list/detail with those returned objects.
2. Call `BareMetalInstances.Create` selecting each legacy type and a visible image. After rejection, query List using the request name and the Kubernetes API for any derived CR.

##### Expected Results

1. Reads preserve the exact legacy string and identity. Provider UI marks correction required. New provisioning returns FailedPrecondition and NONCANONICAL_INSTANCE_TYPE_ARCHITECTURE; no CR is created. The fulfillment service does not normalize any legacy value.

#### TC-IS6-02: Explicit provider correction preserves identity and other hardware

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-3 | critical | automated |

**Coverage:** Component integration and Unit / DEV, E3/E7 for API/CLI and E4 for provider controls.

##### Preconditions

A legacy type is referenced by a CatalogItem and existing instance. Provider credentials and current object version are available.

##### Steps

1. As provider, call private `BareMetalInstanceTypes.Update` with the legacy `object.id`, `object.spec.hardware.cpu.architecture="amd64"`, and `update_mask.paths=["spec.hardware.cpu.architecture"]`; read back the type with Get.
2. Repeat equivalent corrections on separate legacy fixtures through generic CLI edit and the provider UI, then call `BareMetalInstances.Create` with the corrected type and image-amd64.
3. Attempt to change `spec.hardware.cpu.cores` using its nested mask, then the now-canonical architecture to arm64 with the architecture mask. Read back the type after each rejection.

##### Expected Results

1. The explicitly selected canonical name persists under the same ID. Existing references and other hardware remain unchanged. New compatible provisioning is accepted. Other hardware and canonical-to-different-canonical changes remain immutable; UI does not infer a replacement from the alias.

#### TC-IS6-03: Correction honors authority, versioning, and validation

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-3 | high | automated |

**Coverage:** Component integration / DEV, E3 and E7.

##### Preconditions

A provider and tenant client can view a legacy type; retain a stale version. A competing provider update changes the version.

##### Steps

1. Attempt private `BareMetalInstanceTypes.Update` as the tenant with `object.id`, architecture="amd64", and mask `["spec.hardware.cpu.architecture"]`.
2. As provider, repeat with `lock=true` and the stale value in `object.metadata.version`. Then submit each invalid architecture from TC-IS3-01 using the same mask.
3. Reread the type with Get and submit the valid correction with `lock=true` and the current metadata version. Compare stored hardware after each response.

##### Expected Results

1. Tenant writes retain existing denial. Stale optimistic writes return Aborted. Noncanonical replacements return InvalidArgument. Failed requests change neither architecture nor other hardware. Fresh authorized correction succeeds.

### IS-7: Visible disabled incompatible UI images with reasons

#### TC-IS7-01: Incompatible images stay visible and disabled with an accessible reason

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-5 | high | automated |

**Coverage:** Unit / DEV, E4.

##### Preconditions

Mock Connect returns an amd64 type and visible available images for amd64, arm64, and amd64+arm64.

##### Steps

1. Select type-amd64 and open the image selector populated with image-amd64, image-arm64, and image-multi.
2. Use keyboard/accessibility queries to inspect image-arm64's disabled state and reason.
3. Select image-amd64 and image-multi in separate runs and attempt to advance.

##### Expected Results

1. The arm64-only option remains visible but disabled with a reason identifying amd64 incompatibility. Matching and multi-architecture options remain selectable.

#### TC-IS7-02: Changed types and default selections re-evaluate compatibility

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-5 | high | automated |

**Coverage:** Unit / DEV, E4.

##### Preconditions

A wizard has an image selected or defaulted under one type. Prepare another type and a selected/default reference outside the loaded list page.

##### Steps

1. Start with type-amd64/image-amd64 selected, change to type-arm64 where policy permits, and attempt to advance/submit without replacing the image.
2. Load a CatalogItem default or direct-template selection whose type/image reference is outside the mocked list page. Inspect the Get request and attempt to advance before and after resolution.
3. Repeat with image-multi defaulted for type-amd64 and type-arm64.

##### Expected Results

1. Compatibility is re-evaluated for the effective pair. An incompatible retained image stays identifiable with a reason, and advancing/submitting is blocked. The selected off-page resource is fetched before comparison. Multi-architecture defaults remain valid for each listed target.

#### TC-IS7-03: Loading, lookup failures, and stale submission expose actionable feedback

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-5 | medium | automated |

**Coverage:** Unit / DEV, E4.

##### Preconditions

Mock Connect supports delayed and failed type/image lookups and an admission mismatch after UI selection. A raw noncanonical selected type is also available.

##### Steps

1. Delay the selected type/image Get responses; attempt to advance. Fail a lookup, select Retry, and resolve it with the matching fixture.
2. After a compatible selection, have the mock Create return InvalidArgument with INCOMPATIBLE_DISK_IMAGE_ARCHITECTURE and the design's correction message; inspect the displayed error.
3. Return a selected type with architecture="x86_64" and attempt image-based submission.

##### Expected Results

1. The wizard does not display a false compatible result or allow an unresolved pair through a local success path. Load errors show Retry. A server mismatch shows its safe correction message. A noncanonical type indicates provider correction required and disables image-based submission.

### IS-8: Tenant confidentiality and existing lifecycle checks

#### TC-IS8-01: Architecture errors do not disclose unauthorized references

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-2 | critical | automated |

**Coverage:** Component integration / DEV, E3 and E7.

##### Preconditions

Two tenants have distinct image catalogs. Prepare a hidden image whose architecture can be changed between matching and mismatching, and an authorized shared image with an incompatible architecture.

##### Steps

1. As tenant A, call `BareMetalInstances.Create` with its type-amd64 and tenant B's image reference, first by ID and then by name in B's scope. Repeat with the hidden image declaring amd64, then arm64.
2. Submit the authorized shared image-arm64 with `disk_image.shared=true`; compare the returned status/message with those for the hidden references.

##### Expected Results

1. Hidden references produce the existing resolution/authorization error before comparison, regardless of their architecture; no compatibility message reveals hidden catalog data. The authorized mismatch returns the architecture error identifying only the selected visible resources and declared architectures.

#### TC-IS8-02: Lifecycle validation and warnings precede architecture comparison

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-2 | high | automated |

**Coverage:** Component integration / DEV, E3 and E7.

##### Preconditions

Prepare matching and mismatching images marked available, deprecated, obsolete, and deleting.

##### Steps

1. Call `BareMetalInstances.Create` with type-amd64 and each available/deprecated/obsolete/deleting image fixture, using both matching and mismatching architecture lists and caller/catalog-selected references.
2. For the matching deprecated multi-architecture image, inspect `response.warnings`; for rejected requests, inspect the gRPC code/message to determine which validation ran first.

##### Expected Results

1. Obsolete/deleting images retain existing rejection before a compatibility message. A matching deprecated image is accepted with its current deprecation warning. An authorized available/deprecated mismatch uses the stable architecture reason; warnings do not bypass matching.

#### TC-IS8-03: Returned validation status contains only permitted comparison details

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-6 | critical | automated |

**Coverage:** Unit and Contract / DEV, E1 and E2.

##### Preconditions

E2 has a persisted instance with a blocked projection. Its authorized image has a source URL and its type has a private host selector distinguishable from their catalog names.

##### Steps

1. Invoke the actual outer reconciler for the blocked instance.
2. Call public/private `BareMetalInstances.Get(id)` and List; locate the condition of type `BARE_METAL_INSTANCE_CONDITION_TYPE_CONFIGURATION_APPLIED` in the returned object's `status.conditions`.
3. Inspect that condition's `status`, `reason`, and `message` for the expected failure and omission of the fixture's source URL/host selector.

##### Expected Results

1. The condition has `status=CONDITION_STATUS_FALSE`, `reason="ValidationFailed"`, and an actionable message naming the authorized catalogs and supported/required architectures. The message omits the image source URL and private host selector.

### IS-9: Documentation, audited boundaries, and regression verification

#### TC-IS9-01: Documentation explains the changed behavior and enforcement limits

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| — | high | manual |

**Coverage:** Documentation review / DEV, E8.

##### Preconditions

The implementation's API reference, CLI help, and provider/tenant documentation changes are available with this design.

##### Steps

1. Review canonical inputs, rejection and protocol examples, compatibility after effective selection, legacy correction, mismatch errors, and non-provisioning management. Check the help/filter examples against the retained string/enum field definitions.

##### Expected Results

1. Documentation accurately explains the new constraint and compatibility check, accepted human inputs and protocol forms, correction through Update/CLI/UI, and allowed management of incompatible instances. It identifies DiskImageSpec/BareMetalCPUSpec as the architecture declarations, the inherited CaaS Create check, and the VM/image-inspection/provider-inventory exclusions; no unsupported path is described as protected.

#### TC-IS9-03: Deployed BMaaS journeys accept matching and reject incompatible selections

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-2 | critical | automated |

**Coverage:** E2E / QE, E5.

##### Preconditions

E5 has compatible source-pinned deployments of the fulfillment service, bare-metal operator, AAP and provider, including PR #1451's effective-type contract, with the fulfillment service reconciler enabled. Tenant authentication, hub access, available hosts, a template, and type/image fixtures are configured. Legacy architecture tests require prepared pre-feature data.

##### Steps

1. Through the deployed CLI/API, create matching catalog/direct-template pairs including type-amd64/image-multi; poll the existing BMaaS lifecycle using E5 helpers.
2. Submit type-amd64/image-arm64 with a fresh name, including a private Create with explicit type/image references as used by the CaaS caller. Inspect the error, persisted instances, hub CRs and provider allocation observations.
3. Submit a seeded legacy type, correct its architecture through provider `BareMetalInstanceTypes.Update`, and retry a matching Create.
4. Remove amd64 from the image used by an existing instance. Submit metadata and HALTED updates with their masks from TC-IS5-01, invoke/poll reconciliation, and compare the prior provisioning fields.

##### Expected Results

1. Matching pairs reach the existing observable BMaaS lifecycle. Mismatches return InvalidArgument with INCOMPATIBLE_DISK_IMAGE_ARCHITECTURE and leave no admitted instance, CR, or provider allocation; the private caller receives the same protection.
2. A legacy type returns FailedPrecondition with NONCANONICAL_INSTANCE_TYPE_ARCHITECTURE until corrected. Compatible provisioning succeeds after correction. Metadata/stop updates remain accepted after catalog incompatibility without changing provisioning inputs.

#### TC-IS9-04: Live browser verification covers architecture choices and submission rejection

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-5 | high | manual |

**Coverage:** E2E manual verification / QE, E6.

##### Preconditions

E6 has a deployed UI and fulfillment service, provider and tenant accounts, authorized catalogs, and a source-pinned build.

##### Steps

1. As provider, create a type with each canonical architecture choice and explicitly correct a seeded legacy type.
2. As tenant, select type-amd64 and inspect image-amd64/image-arm64/image-multi; use keyboard navigation to read the disabled reason and select the compatible multi-architecture image.
3. Load an incompatible default and attempt submission. Separately change catalog architecture after a compatible selection and inspect the returned submission error.

##### Expected Results

1. Provider controls offer canonical choices and permit explicit legacy correction. Tenants see incompatible images disabled with reasons and can select matching multi-architecture images. An incompatible default blocks submission, and a catalog change before submission displays the fulfillment service's actionable architecture error.

## Gaps

### Requirement Coverage Gaps

All nine source In Scope bullets have planned cases, with the PRD's constraints represented in the expected results. IS-1/IS-9 cover validation after existing selection/default resolution and documentation of those values; no new defaulting capability is required. [User] This is behavioral mapping, not a readiness or execution claim.

### Interface Change Coverage Gaps

All six interface changes have planned cases: IC-1 type input validation, IC-2 instance request validation/errors, IC-3 provider correction through Update, IC-4 CLI inputs/display, IC-5 UI choices, and IC-6 returned failure status. Existing-default selection cases exercise IC-2. Documentation review maps directly to IS-9 with `—`. IC-6's real-boundary cases still require the proposed E2 runner; the controller-disabled fulfillment service integration target cannot close that execution gap. IC-5 uses existing UI Unit regression and manual deployed-browser verification.

### Execution and Ownership Gaps

- E2 fulfillment service/PostgreSQL/envtest Contract setup, runner, and feature-specific DEV ticket are not implemented/assigned. Lower-tier tests do not satisfy CR suppression and status-persistence assertions.
- E5 focused architecture regression scenarios, canonical/multi-architecture/mismatching image/type fixtures, source-pinned provider environment, legacy architecture fixture preparation, and feature-specific QE ticket remain to be established. Extend the instance-type fixture provided by PR #1451.
- E6 requires a deployed UI/service and authorized personas for manual verification. Automated UI regression uses the existing E4 harness; no new browser framework is required by this plan.
- Legacy read/correction tests require synthetic persisted pre-validation data in E7 or a prepared pre-feature E5 fixture. A new canonical-only Create cannot seed a legacy type; tests must not weaken production validation to do so.
- No new proto/service/CLI/UI/provider implementation exists yet, so no feature test has passed. Static artifact checks and source inspection do not change that status.
- Planning follows [Integration testing](https://github.com/osac-project/osac/blob/515ce87588967055537a8fd8e7edb0e2d728eb85/docs/INTEGRATION-TESTING.md#planning-evidence). Missing owner tickets are reported as unresolved rather than invented.

## Summary

| Metric | Count |
|--------|-------|
| Total test cases | 23 |
| Critical | 13 |
| High | 9 |
| Medium | 1 |
| Low | 0 |
| Automated scenarios | 21 |
| Manual scenarios | 2 |
| Requirements with planned cases | 9 / 9 |
| Interface changes with planned cases | 6 / 6 |
| Feature cases executed during draft | 0 |

Automation describes the intended verification mode; it does not imply that the new automated cases or their proposed runners already exist.
