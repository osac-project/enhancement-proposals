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
| Compatibility after CatalogItem or direct-template selection; IS-1 / IC-3 | TC-IS1-01, TC-IS1-02 | Component integration, DEV | Catalog/instance/template API suites, E3; merged-candidate DB assertions, E7 | Existing reference-resolution paths identified; no new template schema |
| Canonical type input constraint; IS-2, IS-3 / IC-1 | TC-IS3-01 | Unit and component integration, DEV | Validation E1; API/database E3/E7 | Existing harnesses for the changed type constraint |
| CLI architecture input/display and legacy correction; IS-2, IS-3, IS-6 / IC-5, IC-4 | TC-IS2-02, TC-IS3-02, TC-IS6-02 | Unit and component integration, DEV | Specialized CLI co-located E1 plus deployed CLI/API E3 | Existing harnesses; implementation not present |
| UI canonical controls, visible disabled choices and changed defaults; IS-2, IS-7 / IC-6 | TC-IS2-03, TC-IS7-01, TC-IS7-02, TC-IS7-03 | Unit, DEV | UI tests E4 | Existing harness; cover CatalogItem defaults and caller-selected references |
| Nine-pair matrix, multi-architecture, dry-run and rollback; IS-4 / IC-3 | TC-IS4-01, TC-IS4-02 | Unit and database/component integration, DEV | Comparison E1; server/database E7 and API E3 | Existing harnesses; no feature execution |
| Drift/no CR creation or provisioning patch, recovery/status persistence; IS-4 / IC-7 | TC-IS4-03 | Unit plus Contract, DEV | Reconciler fake-client E1 plus real E2 | Unit harness exists; real Contract harness missing |
| Non-provisioning updates and guarded user-data migration; IS-5 / IC-3 | TC-IS5-01, TC-IS5-02 | Component integration plus Contract, DEV | API/database E3/E7; CR fields/status E2 | API paths identified; real projection harness missing |
| Legacy readability, provisioning rejection, correction and denial/conflicts; IS-6 / IC-3, IC-4 | TC-IS6-01, TC-IS6-02, TC-IS6-03 | Component integration, DEV | API/database/CLI E3/E7; provider UI controls E4 | Controlled legacy fixture required; implementation not present |
| Hidden references, lifecycle precedence, warning preservation; IS-8 / IC-3 | TC-IS8-01, TC-IS8-02 | Component integration, DEV | Tenant/lifecycle API suites E3/E7 | Existing harnesses |
| Safe returned compatibility status; IS-8 / IC-7 | TC-IS8-03 | Unit plus Contract, DEV | Reconciler E1 and real E2 | Contract execution not ready |
| Documentation of architecture validation and correction; IS-9 / — | TC-IS9-01 | Documentation review, DEV | E8 | Depends on final decisions |
| Deployed explicit-type BMaaS and inherited private caller; IS-9 / IC-3 | TC-IS9-03 | E2E, QE | E5; proposed focused regression file | New cases/fixtures/deployment needed; owner ticket unresolved |
| Browser/persona behavior with real API; IS-9 / IC-6 | TC-IS9-04 | E2E manual verification, QE | E6 | Existing manual harness; UI regression uses E4 |

For Contract assertions, explicitly invoke the actual outer reconciler with persisted state and inspect CR writes and stored status when it returns. For deployed lifecycle progression, use the existing fixture/helper polling limits and fail when they expire. Establish a rejected Create through its response and absent admitted identity; establish a blocked projection through ConfigurationApplied=False with reason ValidationFailed and the architecture-error message before checking that provisioning fields remain unchanged.

## Test Cases

### IS-1: Effective selections after existing defaults and reference resolution

#### TC-IS1-01: Compatibility uses effective CatalogItem selections

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-3 | critical | automated |

**Coverage:** Component integration / DEV, E3.

##### Preconditions

A template and visible canonical types/images exist. Prepare locked and editable CatalogItems whose image/type defaults include matching and mismatching pairs.

##### Steps

1. Create instances with omitted references and with permitted caller overrides of editable references.

##### Expected Results

1. Compatibility is evaluated against the effective image/type pair. Matching defaults or overrides are accepted; mismatching pairs return InvalidArgument with INCOMPATIBLE_DISK_IMAGE_ARCHITECTURE and leave no persisted instance.

#### TC-IS1-02: Caller and template-provided instance types receive the same validation

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-3 | critical | automated |

**Coverage:** Component integration / DEV, E3 and E7.

##### Preconditions

A visible BareMetalInstanceTemplate supplies an instance type under the PR #1451 contract. Visible canonical types/images include matching and mismatching pairs.

##### Steps

1. Create directly from the template with an explicit image, first using its provided type and then an explicit caller type. Submit matching and mismatching pairs, including name-based references.

##### Expected Results

1. The fulfillment service compares the resolved effective pair, including a template-provided type. Matching requests are accepted; mismatches return InvalidArgument with INCOMPATIBLE_DISK_IMAGE_ARCHITECTURE and leave no persisted instance.

### IS-2: Canonical vocabulary across UI, CLI, and API

#### TC-IS2-02: DiskImage describe displays canonical architecture labels

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-5 | high | automated |

**Coverage:** Unit and component integration / DEV, E1 and E3.

##### Preconditions

The CLI can read an image for each supported architecture and a multi-architecture image.

##### Steps

1. Run the specialized DiskImage describe command for those images.

##### Expected Results

1. Architecture labels are amd64, arm64, and s390x. Every declared member of a multi-architecture image is displayed; uppercase enum-derived labels and aliases are absent.

#### TC-IS2-03: UI type creation offers and submits canonical architecture choices

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-6 | high | automated |

**Coverage:** Unit / DEV, E4.

##### Preconditions

The type creation form uses mock Connect transport with valid remaining hardware fields.

##### Steps

1. Inspect the architecture selector and create a type with each offered value.

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

1. Exercise the changed public/private type constraint and private Create with each value. Repeat masked legacy architecture correction with each invalid value.

##### Expected Results

1. The three canonical strings are accepted. Every invalid write returns InvalidArgument identifying the architecture field and accepted values amd64, arm64, s390x. No invalid value is trimmed, lowercased, mapped, or persisted.

#### TC-IS3-02: Specialized CLI architecture flags reject noncanonical input

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-5 | high | automated |

**Coverage:** Unit and component integration / DEV, E1 and E3.

##### Preconditions

CLI is configured for the component-integration fulfillment service; valid remaining arguments are provided.

##### Steps

1. Pass each invalid variant from TC-IS3-01 to create baremetalinstancetype --cpu-architecture and create diskimage --architecture. Submit every canonical value.

##### Expected Results

1. Invalid architecture flags exit nonzero and list the three allowed names; no resource is created. Canonical type flags submit exact strings, and canonical image flags submit the corresponding existing enum values.

### IS-4: Image membership, multi-architecture matching, and early mismatch errors

#### TC-IS4-01: Exhaustive single-architecture compatibility matrix

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-3 | critical | automated |

**Coverage:** Unit and component integration / DEV, E1 and E3/E7.

##### Preconditions

Three canonical types and three single-architecture images are visible and available.

##### Steps

1. Exercise the shared comparison and generated public/private Create with all nine image/type combinations. Repeat each mismatch as dry-run.

##### Expected Results

1. The three matching pairs are accepted. Each of six mismatches returns InvalidArgument with INCOMPATIBLE_DISK_IMAGE_ARCHITECTURE, the selected authorized resources and their required/supported architectures, and corrective guidance. Rejected requests, including dry-run, leave no persisted instance.

#### TC-IS4-02: Every matching member of a multi-architecture image is accepted

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-3 | critical | automated |

**Coverage:** Unit and component integration / DEV, E1 and E3/E7.

##### Preconditions

An image declares amd64 and arm64 in both list orders; an s390x type and matching amd64/arm64 types exist.

##### Steps

1. Exercise the shared comparison and Create for each matching target and for the unmatched target.

##### Expected Results

1. amd64 and arm64 succeed regardless of list order. s390x returns INCOMPATIBLE_DISK_IMAGE_ARCHITECTURE. Compatibility uses membership rather than the first architecture.

#### TC-IS4-03: Catalog drift blocks first CR creation and changed provisioning inputs

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-7 | critical | automated |

**Coverage:** Unit and Contract / DEV, E1 and E2.

##### Preconditions

E2 Contract harness has a persisted compatible instance and access to the running fulfillment service and its catalog. Pause before explicit reconciler invocation; optionally create an existing CR with a different pending selector/template-parameter projection.

##### Steps

1. Change the image architecture list to remove the target, then explicitly invoke the real reconciler. Test first creation and a pending provisioning-input patch. Correct the image and invoke again.

##### Expected Results

1. Before correction, no first CR is created and an existing CR's provisioning fields remain byte-for-byte unchanged. ConfigurationApplied=False with reason ValidationFailed and the safe comparison message is persisted. After correction, the next explicit invocation writes the compatible configuration, clears the architecture validation failure, and resumes existing condition synchronization. With an existing CR its observed state is retained; without a CR the existing FAILED state is used.

### IS-5: Provisioning-changing requests guarded; other management preserved

#### TC-IS5-01: Non-provisioning updates remain possible under catalog incompatibility

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-3 | critical | automated |

**Coverage:** Component integration and Contract / DEV, E3/E7 for API behavior and E2 for CR projections.

##### Preconditions

An instance and CR exist with known applied provisioning fields and an incompatible current image/type catalog. Exercise running and stopped observations.

##### Steps

1. Apply metadata edits, status-only internal updates, HALTED, ALWAYS, and restart-trigger changes separately through masked API updates; invoke reconciliation after each. Also submit a full update with identical provisioning references and parameters.
2. Repeat a metadata/stop update with no existing CR.

##### Expected Results

1. Requests are not rejected solely for architecture incompatibility. Identical provisioning values do not trigger the comparison. CR metadata/power/restart fields follow the permitted request while incompatible provisioning fields retain their prior values.
2. Accepting a metadata/stop request does not create a CR for an incompatible pair.

#### TC-IS5-02: Provisioning-changing user-data migration receives the guard

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-3 | critical | automated |

**Coverage:** Component integration and Contract / DEV, E3/E7 for admission and E2 for downstream parameters.

##### Preconditions

An instance uses inline user data and permits the existing atomic migration to a user-data Secret. The selected catalog pair is made incompatible.

##### Steps

1. In one masked update clear inline user_data and set user_data_secret. Repeat with a compatible pair. Inspect persistence and projected parameters.

##### Expected Results

1. The incompatible migration returns InvalidArgument with INCOMPATIBLE_DISK_IMAGE_ARCHITECTURE and preserves stored user-data references and provisioning parameters. The compatible migration succeeds and projects the intended user-data parameters.

### IS-6: Legacy visibility, correction, and canonical-only new provisioning

#### TC-IS6-01: Legacy types remain readable and cannot serve new provisioning

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-3 | critical | automated |

**Coverage:** Component integration and Contract / DEV, E3/E7 for API behavior, E4 for UI visibility and E2 for CR absence.

##### Preconditions

Seed synthetic legacy types with x86_64, aarch64, uppercase, whitespace, and unknown architectures in a controlled pre-validation database fixture. Each has stable ID and valid remaining hardware.

##### Steps

1. Read/list/describe the types as permitted personas; render provider list/detail. Attempt new instances selecting each legacy type.

##### Expected Results

1. Reads preserve the exact legacy string and identity. Provider UI marks correction required. New provisioning returns FailedPrecondition and NONCANONICAL_INSTANCE_TYPE_ARCHITECTURE; no CR is created. The fulfillment service does not normalize any legacy value.

#### TC-IS6-02: Explicit provider correction preserves identity and other hardware

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-4 | critical | automated |

**Coverage:** Component integration and Unit / DEV, E3/E7 for API/CLI and E4 for provider controls.

##### Preconditions

A legacy type is referenced by a CatalogItem and existing instance. Provider credentials and current object version are available.

##### Steps

1. Correct only spec.hardware.cpu.architecture through private masked Update, generic CLI edit, and provider UI. Then submit a matching instance. Attempt another hardware change and a different canonical-to-canonical architecture change.

##### Expected Results

1. The explicitly selected canonical name persists under the same ID. Existing references and other hardware remain unchanged. New compatible provisioning is accepted. Other hardware and canonical-to-different-canonical changes remain immutable; UI does not infer a replacement from the alias.

#### TC-IS6-03: Correction honors authority, versioning, and validation

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-4 | high | automated |

**Coverage:** Component integration / DEV, E3 and E7.

##### Preconditions

A provider and tenant client can view a legacy type; retain a stale version. A competing provider update changes the version.

##### Steps

1. Attempt correction as a tenant, with a stale provider version/lock, and with invalid replacement strings. Then reread and correct as the provider.

##### Expected Results

1. Tenant writes retain existing denial. Stale optimistic writes return Aborted. Noncanonical replacements return InvalidArgument. Failed requests change neither architecture nor other hardware. Fresh authorized correction succeeds.

### IS-7: Visible disabled incompatible UI images with reasons

#### TC-IS7-01: Incompatible images stay visible and disabled with an accessible reason

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-6 | high | automated |

**Coverage:** Unit / DEV, E4.

##### Preconditions

Mock Connect returns an amd64 type and visible available images for amd64, arm64, and amd64+arm64.

##### Steps

1. Select the type, open the image selector, inspect the disabled reason using keyboard and accessibility queries, and choose a compatible image.

##### Expected Results

1. The arm64-only option remains visible but disabled with a reason identifying amd64 incompatibility. Matching and multi-architecture options remain selectable.

#### TC-IS7-02: Changed types and default selections re-evaluate compatibility

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-6 | high | automated |

**Coverage:** Unit / DEV, E4.

##### Preconditions

A wizard has an image selected or defaulted under one type. Prepare another type and a selected/default reference outside the loaded list page.

##### Steps

1. Change type where policy allows. Load CatalogItem-defaulted and direct-template selections, including an off-page selected reference. Try to advance/submit with an incompatible retained image.

##### Expected Results

1. Compatibility is re-evaluated for the effective pair. An incompatible retained image stays identifiable with a reason, and advancing/submitting is blocked. The selected off-page resource is fetched before comparison. Multi-architecture defaults remain valid for each listed target.

#### TC-IS7-03: Loading, lookup failures, and stale submission expose actionable feedback

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-6 | medium | automated |

**Coverage:** Unit / DEV, E4.

##### Preconditions

Mock Connect supports delayed and failed type/image lookups and an admission mismatch after UI selection. A raw noncanonical selected type is also available.

##### Steps

1. Render each loading/error state; retry lookups. Submit after changing catalog data server-side. Select a legacy type in a permitted existing catalog.

##### Expected Results

1. The wizard does not display a false compatible result or allow an unresolved pair through a local success path. Load errors show Retry. A server mismatch shows its safe correction message. A noncanonical type indicates provider correction required and disables image-based submission.

### IS-8: Tenant confidentiality and existing lifecycle checks

#### TC-IS8-01: Architecture errors do not disclose unauthorized references

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-3 | critical | automated |

**Coverage:** Component integration / DEV, E3 and E7.

##### Preconditions

Two tenants have distinct image catalogs. Prepare a hidden image whose architecture can be changed between matching and mismatching, and an authorized shared image with an incompatible architecture.

##### Steps

1. As one tenant submit the other tenant's image by ID and name before and after changing its architecture. Then submit the authorized shared mismatch.

##### Expected Results

1. Hidden references produce the existing resolution/authorization error before comparison, regardless of their architecture; no compatibility message reveals hidden catalog data. The authorized mismatch returns the architecture error identifying only the selected visible resources and declared architectures.

#### TC-IS8-02: Lifecycle validation and warnings precede architecture comparison

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-3 | high | automated |

**Coverage:** Component integration / DEV, E3 and E7.

##### Preconditions

Prepare matching and mismatching images marked available, deprecated, obsolete, and deleting.

##### Steps

1. Create through caller/default references for each lifecycle case; use a deprecated matching multi-architecture image and inspect warnings.

##### Expected Results

1. Obsolete/deleting images retain existing rejection before a compatibility message. A matching deprecated image is accepted with its current deprecation warning. An authorized available/deprecated mismatch uses the stable architecture reason; warnings do not bypass matching.

#### TC-IS8-03: Returned validation status contains only permitted comparison details

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-7 | critical | automated |

**Coverage:** Unit and Contract / DEV, E1 and E2.

##### Preconditions

E2 has a persisted instance with a blocked projection. Its authorized image has a source URL and its type has a private host selector distinguishable from their catalog names.

##### Steps

1. Invoke the real reconciler and read the persisted failure condition through public/private Get and List.

##### Expected Results

1. ConfigurationApplied=False has reason ValidationFailed and an actionable message identifying the authorized catalog names and supported/required architectures. The message omits the image source URL and private host selector.

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
| IC-3 | critical | automated |

**Coverage:** E2E / QE, E5.

##### Preconditions

E5 has compatible source-pinned deployments of the fulfillment service, bare-metal operator, AAP and provider, including PR #1451's effective-type contract, with the fulfillment service reconciler enabled. Tenant authentication, hub access, available hosts, a template, and type/image fixtures are configured. Legacy architecture tests require prepared pre-feature data.

##### Steps

1. Create matching and mismatching catalog/direct-template requests through CLI/API, including a multi-architecture match and a private Create shaped like the CaaS worker caller.
2. Attempt provisioning with a legacy type, correct it as the provider, and retry a matching request. Make an existing instance's catalog pair incompatible and apply metadata/stop updates.

##### Expected Results

1. Matching pairs reach the existing observable BMaaS lifecycle. Mismatches return InvalidArgument with INCOMPATIBLE_DISK_IMAGE_ARCHITECTURE and leave no admitted instance, CR, or provider allocation; the private caller receives the same protection.
2. A legacy type returns FailedPrecondition with NONCANONICAL_INSTANCE_TYPE_ARCHITECTURE until corrected. Compatible provisioning succeeds after correction. Metadata/stop updates remain accepted after catalog incompatibility without changing provisioning inputs.

#### TC-IS9-04: Live browser verification covers architecture choices and submission rejection

| Interface Change | Priority | Automation |
|------------------|----------|------------|
| IC-6 | high | manual |

**Coverage:** E2E manual verification / QE, E6.

##### Preconditions

E6 has a deployed UI and fulfillment service, provider and tenant accounts, authorized catalogs, and a source-pinned build.

##### Steps

1. As provider create/correct type architectures. As tenant select matching, mismatching, multi-architecture and default images, and receive a stale-catalog submission error. Check disabled explanations with keyboard navigation.

##### Expected Results

1. Provider controls offer canonical choices and permit explicit legacy correction. Tenants see incompatible images disabled with reasons and can select matching multi-architecture images. An incompatible default blocks submission, and a catalog change before submission displays the fulfillment service's actionable architecture error.

## Gaps

### Requirement Coverage Gaps

All nine source In Scope bullets have planned cases, with the PRD's constraints represented in the expected results. IS-1/IS-9 cover validation after existing selection/default resolution and documentation of those values; no new defaulting capability is required. [User] This is behavioral mapping, not a readiness or execution claim.

### Interface Change Coverage Gaps

All six interface changes have planned cases: IC-1 type input validation, IC-3 instance request validation/errors, IC-4 provider correction through Update, IC-5 CLI inputs/display, IC-6 UI choices, and IC-7 returned failure status. Existing-default selection cases exercise IC-3. Documentation review maps directly to IS-9 with `—`. IC-7's real-boundary cases still require the proposed E2 runner; the controller-disabled fulfillment service integration target cannot close that execution gap. IC-6 uses existing UI Unit regression and manual deployed-browser verification.

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
