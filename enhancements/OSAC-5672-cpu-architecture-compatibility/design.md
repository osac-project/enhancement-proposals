---
title: cpu-architecture-compatibility
authors:
  - ncarboni@redhat.com
creation-date: 2026-10-07
last-updated: 2026-10-14
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

The fulfillment service performs the comparison after resolving the requested resources and existing defaults. A one-time data migration sets every noncanonical BareMetalInstanceType CPU architecture to `amd64`; new writes accept only canonical names. The UI shows incompatible DiskImages disabled with a reason. See the [PRD](prd.md) and [test plan](testplan.md). [User]

# 2. Goals and Non-Goals

## 2.1 Goals

- Constrain the CPU architecture of a BareMetalInstanceType to `amd64`, `arm64`, or `s390x`.
- Migrate existing noncanonical CPU architectures to `amd64` while preserving resource identities, references, and unrelated hardware. [User]
- Validate, when creating a BareMetalInstance, that the requested DiskImage supports the CPU architecture of the selected BareMetalInstanceType.

## 2.2 Non-Goals

- Discovering DiskImage CPU architectures from OCI manifests or image contents
- CPU models/features or provider inventory validation
- Enforcing DiskImage compatibility for VMaaS

# 3. Motivation / Background

`DiskImageSpec.architecture` already lists supported architectures using an enum. `BareMetalCPUSpec.architecture` is a string that currently accepts any nonempty value. Neither declaration is currently compared when creating a BareMetalInstance.

The `BareMetalInstance` create endpoint resolves the selected resources and checks reference visibility and DiskImage lifecycle, without comparing CPU architectures. Existing installations are not production-ready, so a data migration can replace noncanonical architecture values without introducing a permanent compatibility or repair path. `BareMetalInstanceType` hardware remains immutable through Update. [User]

# 4. Design

## 4.1 Architecture

This design builds on the required effective BareMetalInstanceType selection proposed in [PR #1451](https://github.com/osac-project/osac/pull/1451).

Run the data migration in §4.2 before enabling the new API and reconciler against an existing database. Then add a shared comparison helper under `fulfillment-service/internal/validation`. It accepts the resolved BareMetalInstanceType and DiskImage, maps the canonical CPU architecture string to the corresponding existing Architecture enum value, and checks membership in the entire DiskImage architecture list. This accepts multi-architecture images for each listed architecture. The migration and new-write constraint establish canonical stored values; aliases, case conversion, and trimming are not accepted at runtime. [PRD: IS-3, IS-4; User]

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

This constrains new writes without changing the wire/storage representation. DiskImage's enum values, ProtoJSON identifiers, and existing nonempty/unique/known/nonzero list constraints remain. Human-facing labels use `amd64`, `arm64`, and `s390x`; raw enum serialization retains its existing form. Update the DiskImage field comment to describe its use in BMaaS compatibility validation. [PRD: IS-2, IS-3; User]

Add a new numbered SQL migration under `fulfillment-service/internal/database/migrations/`, using the existing migration runner and a transaction. Update `data.spec.hardware.cpu.architecture` in `bare_metal_instance_types` and `archived_bare_metal_instance_types`, including soft-deleted rows. Preserve exact `amd64`, `arm64`, and `s390x` strings; set every other architecture to `amd64`, including aliases, case/whitespace variants, unknown strings, and empty, null, or missing architecture values. In particular, `aarch64` becomes `amd64`, not `arm64`: this is a fallback for development data, not alias normalization or hardware discovery. Preserve IDs, references, scope metadata, and all unrelated fields. A repeated application makes no further data changes; a fresh database has no rows to rewrite. [User]

## 4.3 API Changes

BareMetalInstanceTypes Create rejects noncanonical architecture strings. Update retains existing hardware immutability, authorization, metadata immutability, and version checks; it adds no architecture-correction exception or new nested-mask handling. Get/List return canonical stored values after migration. [PRD: IS-3; User]

Use the existing gRPC status/message error pattern:

| Request | gRPC code | Message |
|---------|-----------|---------|
| New noncanonical architecture string | InvalidArgument | Identify the field and list `amd64`, `arm64`, `s390x` |
| Image/type mismatch | InvalidArgument | Prefix `INCOMPATIBLE_DISK_IMAGE_ARCHITECTURE`; identify the selected resources, supported/required architectures, and compatible selection to make |

For example: `INCOMPATIBLE_DISK_IMAGE_ARCHITECTURE: DiskImage 'image-a' supports [arm64]; BareMetalInstanceType 'type-a' requires amd64. Select a compatible DiskImage or BareMetalInstanceType.` Existing visibility and lifecycle errors take precedence. [PRD: IS-3, IS-4, IS-6, IS-8]

## 4.4 Scalability and Performance

The comparison scans a list constrained to at most three distinct supported architectures. Create reuses the resolved type/image objects; reconciliation reuses the catalog reads needed to build the provisioning configuration.

The one-time migration scans the type tables and rewrites only noncanonical architecture values. It adds no per-request legacy handling.

## 4.5 Security Considerations

Run existing reference visibility, ownership, and image lifecycle checks before producing a compatibility message. Include only the authorized resource names and declared architectures; omit image source URLs and private host selectors. [PRD: IS-8]

## 4.6 Failure Handling and Recovery

Rejected Create and provisioning-changing Update requests return before persistence. The caller selects a compatible image/type pair and retries. Existing dry-run uses the same candidate validation. [PRD: IS-4]

If the data migration fails, roll back its data changes and keep API/reconciler startup blocked until the database migration failure is repaired through the existing migration procedure. The migration must complete before serving requests or reconciling stored resources. Stop old writers during the transition so they cannot reintroduce noncanonical values. [User]

For a rejected CR projection, use the existing `ConfigurationApplied=False` condition with reason `ValidationFailed` and the safe comparison message. With no CR, reuse `setFailed`; with an existing CR, retain its observed state and set only the configuration failure after normal status synchronization. Return through the reconciler's status-update path: `run` otherwise returns on error before persisting status. After correction, the next reconciliation applies the compatible configuration, clears the architecture validation failure, and resumes normal condition synchronization. [PRD: IS-4, IS-5]

## 4.7 RBAC / Tenancy

No RBAC or tenancy changes are required. The data migration runs through the existing database migration mechanism and preserves type scope metadata and references. Type writes retain provider authorization. Instance validation uses the current tenant/shared DiskImage resolution and dependency-ownership rules. [PRD: IS-8; User]

## 4.8 Extensibility / Future-Proofing

The existing Architecture enum supplies the supported vocabulary for the comparison.

# 5. Interface Changes

`IS-1` through `IS-9` identify the PRD's nine In Scope bullets in published order. They are local traceability anchors, not additional requirements.

## IC-1: BareMetalInstanceType architecture input constraint

**Requirements:** IS-2, IS-3.

BareMetalInstanceTypes Create accepts only `amd64`, `arm64`, or `s390x` for `spec.hardware.cpu.architecture`. A noncanonical input returns InvalidArgument identifying the field and accepted values. Update retains hardware immutability.

## IC-2: BareMetalInstance Create and provisioning-changing Update validation

**Requirements:** IS-1, IS-4, IS-5, IS-6, IS-8.

BareMetalInstances Create rejects an incompatible effective image/type pair with InvalidArgument and `INCOMPATIBLE_DISK_IMAGE_ARCHITECTURE`. This applies to caller selections, CatalogItem defaults, and template-provided instance types. The supported provisioning-changing Update receives the same check. Errors identify only authorized resources and explain how to select a compatible pair. Metadata and stop requests remain available as specified in §4.1.

## IC-3: Retired — BareMetalInstanceType architecture correction through Update

The migration in IC-7 removes the need for this interface. Its identifier is retained for traceability and is not reused. [User]

## IC-4: CLI architecture inputs and display

**Requirements:** IS-2, IS-3.

`create baremetalinstancetype --cpu-architecture` and `create diskimage --architecture` accept the three exact canonical strings and reject other spellings with the accepted names. DiskImage describe displays `amd64`, `arm64`, and `s390x` rather than uppercase enum-derived labels.

## IC-5: UI type architecture and compatibility choices

**Requirements:** IS-2, IS-3, IS-4, IS-6, IS-7.

The type creation form offers the three canonical architecture choices instead of free text. Existing types display their post-migration canonical values; no legacy correction control is added. In `BareMetalConfigurationStep`, incompatible images remain visible but disabled with an accessible explanation; matching multi-architecture images remain selectable. A changed type re-evaluates the selected/default image, and an incompatible retained selection blocks submission.

## IC-6: BareMetalInstance status for blocked provisioning configuration

**Requirements:** IS-4, IS-5, IS-6, IS-8.

When catalog incompatibility blocks a provisioning configuration, BareMetalInstances Get/List returns `ConfigurationApplied=False`, reason `ValidationFailed`, and the safe correction message. An initial failure uses the existing FAILED state; an existing CR retains its observed state. After correction, status resumes normal synchronization as described in §4.6.

## IC-7: Existing BareMetalInstanceType architecture data migration

**Requirements:** IS-6, IS-8, IS-9; user revision of the existing-data policy.

Before the new API/reconciler starts, every stored noncanonical BareMetalInstanceType CPU architecture becomes `amd64`. Canonical values, resource identity, references, scope metadata, and unrelated fields are preserved. Get/List and CLI/UI display the migrated value. No provider correction action or legacy provisioning error is introduced. [User]

# 6. Alternatives Considered

| Decision | Alternative | Reason for the chosen approach |
|----------|-------------|--------------------------------|
| Constrain the existing type string | Change field 2 to an enum | A validation constraint and data migration suffice without changing the wire/storage representation |
| Migrate noncanonical values to `amd64` | Keep legacy reads and add explicit provider correction | Requires permanent validation, Update exceptions, and CLI/UI repair flows for installations that are not production-ready |
| Migrate the existing type | Delete and recreate it | Existing instances and CatalogItems reference its identity; migration preserves those references |
| Validate before CR projection as well as Create | Validate only at Create | The reconciler reads mutable catalog data after the request transaction, so an admitted pair can become incompatible before provisioning |

# 7. Observability and Monitoring

API errors and the existing ConfigurationApplied failure condition provide the required correction message. Use the current reconciliation logging and status projection.

# 8. Impact and Compatibility

New writes reject aliases, case variants, and surrounding whitespace. Existing noncanonical BareMetalInstanceType CPU architectures are migrated to `amd64`, while exact canonical values remain unchanged. This user direction replaces the existing-data visibility/correction policy in PRD IS-6 and clarification decisions D3/D6; canonical-only inputs and the provisioning-only compatibility boundary still apply. Update catalog fixtures and examples accordingly, including the CaaS caller's type fixtures. [PRD: IS-3, IS-9; User]

OSAC does not currently support in-place upgrades. For development installations retaining a database, stop old API/reconciler writers, apply the migration through the existing database migration mechanism, and start the canonical-only service. Fresh installations run the same migrations without a data rewrite. The migration deliberately discards original noncanonical values, and `amd64` does not establish the physical host's architecture. Existing installations are not production-ready, which permits this tradeoff. Reverting application code does not restore the original values; restoration requires a pre-migration database backup. The migration changes catalog data without changing downstream CR provisioning inputs directly. Subsequent provisioning must still pass the image/type compatibility check. [User]

Document canonical inputs and protocol forms, existing default resolution, errors, the migration's fallback and ordering, hardware immutability, and non-provisioning management. Include help/filter examples for string versus enum fields. CPU architecture is declared in `DiskImageSpec.architecture` and `BareMetalCPUSpec.architecture`. The CaaS worker's BareMetalInstance requests use the same private Create validation. Document the VM target's undeclared CPU architecture and the PRD's image-inspection/provider-inventory exclusions. [PRD: IS-9; User]

Regenerate the changed shared contract once with `make -C proto generate`, validate with `make -C proto lint`, and advance the UI bindings with `pnpm gen-types`. Unit, component-integration, Contract and deployed BMaaS/UI verification are specified in the [test plan](testplan.md), with existing harnesses and missing execution prerequisites identified.

---

## Provenance

Authored: draft @ design 0.11.3 - 2bd6607, workspace main @ 515ce8758
Final: revise @ design 0.11.5 - 1c6e8de, workspace main @ b06727582

> Context changed between draft and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"design","workflow_version":"0.11.5","ai_workflows":"1c6e8de","source_repo":"b06727582","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":0,"main_ref":"main","phases":["draft","revise","revise","revise","revise","revise","revise","manual-edit","revise","revise","revise","revise","revise","revise","respond","revise","revise"],"authoring_modes":["manual","skill"],"context_changed":true,"origin_untracked":false} -->
