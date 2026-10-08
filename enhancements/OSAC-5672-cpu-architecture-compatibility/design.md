---
title: cpu-architecture-compatibility
authors:
  - ncarboni@redhat.com
creation-date: 2026-10-07
last-updated: 2026-10-08
tracking-link: https://redhat.atlassian.net/browse/OSAC-5672
prd: prd.md
replaces: N/A
superseded-by: N/A
---

# Validate CPU architecture compatibility

| Field | Value |
|-------|-------|
| Author(s) | Nick Carboni |
| Jira | [OSAC-5672](https://redhat.atlassian.net/browse/OSAC-5672) |
| PRD | [prd.md](prd.md) |
| Date | 2026-10-07 |

# 1. Overview

This design introduces validation between the chosen DiskImage and BareMetalInstanceType when a BareMetalInstance is created. The aim is to reject a request before provisioning starts if the DiskImage does not support the BareMetalInstanceType's CPU architecture.

The fulfillment service performs the comparison after resolving the requested resources and existing defaults. The design also constrains architecture names, supports correction of legacy BareMetalInstanceType values, and shows incompatible DiskImages disabled with a reason in the UI. See the [PRD](prd.md) and [test plan](testplan.md).

# 2. Goals and Non-Goals

## 2.1 Goals

- Constrain the CPU architecture of a BareMetalInstanceType to `amd64`, `arm64`, or `s390x`.
- Validate, when creating a BareMetalInstance, that the requested DiskImage supports the CPU architecture of the selected BareMetalInstanceType.

## 2.2 Non-Goals

- Discovering DiskImage CPU architectures from OCI manifests or image contents
- CPU models/features or provider inventory validation
- Enforcing DiskImage compatibility for VMaaS

# 3. Motivation / Background

`DiskImageSpec.architecture` already lists supported architectures using an enum. `BareMetalCPUSpec.architecture` is a string that currently accepts any nonempty value. Neither declaration is currently compared when creating a BareMetalInstance.

The `BareMetalInstance` create endpoint resolves the selected resources and checks reference visibility and DiskImage lifecycle, without comparing CPU architectures. `BareMetalInstanceType` updates reject all hardware changes, so legacy architecture correction needs a specific exception.

# 4. Design

## 4.1 Architecture

This design builds on the required effective BareMetalInstanceType selection proposed in [PR #1451](https://github.com/osac-project/osac/pull/1451).

Add a shared comparison helper under `fulfillment-service/internal/validation`. It accepts the resolved BareMetalInstanceType and DiskImage, maps the exact CPU architecture string to the corresponding existing Architecture enum value, and checks membership in the entire DiskImage architecture list. This accepts multi-architecture images for each listed architecture. Noncanonical type values require provider correction; aliases, case conversion, and trimming are not accepted. [PRD: IS-3, IS-4, IS-6]

In `prepareCreate`, use the resolved type and image, run the existing scope/lifecycle checks, and then compare architectures before returning the candidate for persistence. Use the existing locked-reference helpers so the compared resources remain stable until the transaction completes. Preserve caller selections, CatalogItem policies, template-provided instance types, and template parameter defaults from the baseline. This feature adds no template fields or defaulting layer. [PRD: IS-1, IS-8; User]

In `PrivateBareMetalInstancesServer.Update`, compare the stored and merged candidate before validation. Existing image/type/template/parameter immutability remains enforced. The supported inline-user-data-to-Secret migration changes projected provisioning parameters and receives the architecture check. Metadata, status, power, and restart-only updates do not receive that check. [PRD: IS-5]

The reconciler reads current type/image metadata, and DiskImage architectures are mutable. Reuse the comparison before first CR creation or a change to the CR's provisioning inputs. Build the proposed configuration on a copy, compare the selector, template ID, and template parameters, and validate before writing changed values. These fields contribute to the operator's provisioning configuration version; run strategy and restart trigger do not. If comparison fails, keep existing provisioning inputs while applying permitted metadata/power changes. [PRD: IS-1, IS-4, IS-5]

For CLI architecture flags, replace the current case-insensitive DiskImage architecture parsing without changing unrelated enum parsers. In the UI wizard, resolve an off-page selected type/image reference before evaluating compatibility; retain existing loading/error states and surface a rejection if catalog data changes before submission.

## 4.2 Data Model / Schema Changes

Keep `BareMetalCPUSpec.architecture` as string field 2 in `proto/private/osac/private/v1/baremetal_instance_type_type.proto`; replace the nonempty constraint with:

```protobuf
string architecture = 2 [(buf.validate.field).string = {
  in: ["amd64", "arm64", "s390x"]
}];
```

This constrains new writes while retaining the representation needed to read existing noncanonical strings. DiskImage's enum values, ProtoJSON identifiers, and existing nonempty/unique/known/nonzero list constraints remain. Human-facing labels use `amd64`, `arm64`, and `s390x`; raw enum serialization retains its existing form. Update the DiskImage field comment to describe its use in BMaaS compatibility validation. [PRD: IS-2, IS-3, IS-6; User]

## 4.3 API Changes

BareMetalInstanceTypes Create rejects noncanonical architecture strings. Update permits a stored noncanonical architecture to change to an explicitly selected canonical value, with all other hardware unchanged. Use `UpdateWithCandidatePreparation` to validate the merged object inside the existing transaction and support the nested mask `spec.hardware.cpu.architecture`; the current custom merge helper does not handle that mask. Preserve the existing ID, authorization, metadata immutability, and version checks. An already canonical architecture remains immutable. Get/List return stored legacy values unchanged. [PRD: IS-3, IS-6]

Use the existing gRPC status/message error pattern:

| Request | gRPC code | Message |
|---------|-----------|---------|
| New noncanonical architecture string | InvalidArgument | Identify the field and list `amd64`, `arm64`, `s390x` |
| Image/type mismatch | InvalidArgument | Prefix `INCOMPATIBLE_DISK_IMAGE_ARCHITECTURE`; identify the selected resources, supported/required architectures, and compatible selection to make |
| New provisioning with a legacy type | FailedPrecondition | Prefix `NONCANONICAL_INSTANCE_TYPE_ARCHITECTURE`; request provider correction to a listed canonical value |

For example: `INCOMPATIBLE_DISK_IMAGE_ARCHITECTURE: DiskImage 'image-a' supports [arm64]; BareMetalInstanceType 'type-a' requires amd64. Select a compatible DiskImage or BareMetalInstanceType.` Existing visibility and lifecycle errors take precedence. [PRD: IS-3, IS-4, IS-6, IS-8]

## 4.4 Scalability and Performance

The comparison scans a list constrained to at most three distinct supported architectures. Create reuses the resolved type/image objects; reconciliation reuses the catalog reads needed to build the provisioning configuration.

## 4.5 Security Considerations

Run existing reference visibility, ownership, and image lifecycle checks before producing a compatibility message. Include only the authorized resource names and declared architectures; omit image source URLs and private host selectors. [PRD: IS-8]

## 4.6 Failure Handling and Recovery

Rejected Create and provisioning-changing Update requests return before persistence. The caller corrects the selection or the provider corrects the legacy type and retries. Existing dry-run uses the same candidate validation. [PRD: IS-4, IS-6]

For a rejected CR projection, use the existing `ConfigurationApplied=False` condition with reason `ValidationFailed` and the safe comparison message. With no CR, reuse `setFailed`; with an existing CR, retain its observed state and set only the configuration failure after normal status synchronization. Return through the reconciler's status-update path: `run` otherwise returns on error before persisting status. After correction, the next reconciliation applies the compatible configuration, clears the architecture validation failure, and resumes normal condition synchronization. [PRD: IS-4, IS-5]

## 4.7 RBAC / Tenancy

Correction uses the existing provider-authorized BareMetalInstanceTypes Update operation. Instance validation uses the current tenant/shared DiskImage resolution and dependency-ownership rules. [PRD: IS-6, IS-8]

## 4.8 Extensibility / Future-Proofing

The existing Architecture enum supplies the supported vocabulary for the comparison.

# 5. Interface Changes

`IS-1` through `IS-9` identify the PRD's nine In Scope bullets in published order. They are local traceability anchors, not additional requirements.

## IC-1: BareMetalInstanceType architecture input constraint

**Requirements:** IS-2, IS-3.

BareMetalInstanceTypes Create and Update accept only `amd64`, `arm64`, or `s390x` for `spec.hardware.cpu.architecture`. A noncanonical input returns InvalidArgument identifying the field and accepted values.

## IC-2: BareMetalInstance Create and provisioning-changing Update validation

**Requirements:** IS-1, IS-4, IS-5, IS-6, IS-8.

BareMetalInstances Create rejects an incompatible effective image/type pair with InvalidArgument and `INCOMPATIBLE_DISK_IMAGE_ARCHITECTURE`; a noncanonical type returns FailedPrecondition and `NONCANONICAL_INSTANCE_TYPE_ARCHITECTURE`. This applies to caller selections, CatalogItem defaults, and template-provided instance types. The supported provisioning-changing Update receives the same check. Errors identify only authorized resources and explain the correction. Metadata and stop requests remain available as specified in §4.1.

## IC-3: BareMetalInstanceType architecture correction through Update

**Requirements:** IS-3, IS-6, IS-8.

An authorized provider can Update a legacy type's `spec.hardware.cpu.architecture` to an exact canonical name, including through that nested update mask. Other hardware and already canonical architecture values remain immutable. Get/List continue to expose the stored legacy value until corrected.

## IC-4: CLI architecture inputs and display

**Requirements:** IS-2, IS-3.

`create baremetalinstancetype --cpu-architecture` and `create diskimage --architecture` accept the three exact canonical strings and reject other spellings with the accepted names. DiskImage describe displays `amd64`, `arm64`, and `s390x` rather than uppercase enum-derived labels.

## IC-5: UI type architecture and compatibility choices

**Requirements:** IS-2, IS-3, IS-4, IS-6, IS-7.

The type creation form offers the three canonical architecture choices instead of free text. A provider can explicitly choose a canonical replacement for a legacy value and submit the correction through Update. In `BareMetalConfigurationStep`, incompatible images remain visible but disabled with an accessible explanation; matching multi-architecture images remain selectable. A changed type re-evaluates the selected/default image, and an incompatible retained selection blocks submission.

## IC-6: BareMetalInstance status for blocked provisioning configuration

**Requirements:** IS-4, IS-5, IS-6, IS-8.

When catalog incompatibility blocks a provisioning configuration, BareMetalInstances Get/List returns `ConfigurationApplied=False`, reason `ValidationFailed`, and the safe correction message. An initial failure uses the existing FAILED state; an existing CR retains its observed state. After correction, status resumes normal synchronization as described in §4.6.

# 6. Alternatives Considered

| Decision | Alternative | Reason for the chosen approach |
|----------|-------------|--------------------------------|
| Constrain the existing type string | Change field 2 to an enum | Changes the wire/storage representation needed to keep legacy values readable |
| Correct the existing type | Delete and recreate it | Existing instances and CatalogItems reference its identity; a narrow Update exception preserves those references |
| Validate before CR projection as well as Create | Validate only at Create | The reconciler reads mutable catalog data after the request transaction, so an admitted pair can become incompatible before provisioning |

# 7. Observability and Monitoring

API errors and the existing ConfigurationApplied failure condition provide the required correction message. Use the current reconciliation logging and status projection.

# 8. Impact and Compatibility

New writes reject aliases, case variants, and surrounding whitespace. Existing BareMetalInstanceTypes with noncanonical CPU architecture values remain readable and require provider correction before use in new provisioning. Update catalog fixtures and examples accordingly, including the CaaS caller's type fixtures. [PRD: IS-3, IS-6, IS-9]

Document canonical inputs and protocol forms, existing default resolution, errors, correction through Update/CLI edit/UI, and non-provisioning management. Include help/filter examples for string versus enum fields. CPU architecture is declared in `DiskImageSpec.architecture` and `BareMetalCPUSpec.architecture`. The CaaS worker's BareMetalInstance requests use the same private Create validation. Document the VM target's undeclared CPU architecture and the PRD's image-inspection/provider-inventory exclusions. [PRD: IS-9]

Regenerate the changed shared contract once with `make -C proto generate`, validate with `make -C proto lint`, and advance the UI bindings with `pnpm gen-types`. Unit, component-integration, Contract and deployed BMaaS/UI verification are specified in the [test plan](testplan.md), with existing harnesses and missing execution prerequisites identified.

---

## Provenance

Authored: revise @ design 0.11.3 - 2bd6607, workspace main @ 515ce8758
Phases: draft, revise, revise, revise, revise, revise, revise, manual-edit, revise, revise, revise, revise, revise, revise, respond, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.3","ai_workflows":"2bd6607","source_repo":"515ce8758","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","revise","manual-edit","revise","revise","revise","revise","revise","revise","respond","revise"],"authoring_modes":["manual","skill"],"context_changed":false,"origin_untracked":false} -->
