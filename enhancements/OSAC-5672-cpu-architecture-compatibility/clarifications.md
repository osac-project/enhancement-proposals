# Clarification Log — OSAC-5674

## Status

- Rounds completed: 1
- Current round: 1 — Architecture vocabulary and compatibility behavior; complete
- Open gaps: 0
- Exit criteria met: Yes
- Source: [OSAC-5672](https://redhat.atlassian.net/browse/OSAC-5672), captured in `01-requirements.md`
- Effective locked decisions: D1, D4, D5, D6
- D2 and D3 are superseded by D6; their entries below reflect the final canonical-only outcome.
- Final architecture direction: “Only the canonical architecture names should be accepted”.
- Provisioning direction: “For q4 only block changes that would trigger provisioning.”

## Verified Context

These observations describe the current checkout; they are not new requirements or user decisions.

- Disk images declare AMD64, ARM64, and S390X architectures; the disk-image UI displays `amd64`, `arm64`, and `s390x`. The current contract requires at least one distinct, known architecture and disallows unspecified values. Sources: `proto/private/osac/private/v1/disk_image_type.proto` and `osac-ui/libs/ui-components/src/components/DiskImage/DiskImageTable.tsx`.
- Bare-metal type CPU architecture accepts a non-empty string. The type creation UI accepts free text with `x86_64` and `aarch64` examples. Sources: `proto/private/osac/private/v1/baremetal_instance_type_type.proto` and `osac-ui/libs/ui-components/src/components/BareMetalInstanceType/CreatePage/steps/CpuMemoryStep.tsx`.
- Instance creation resolves catalog/template choices and image references; the inspected image validation checks lifecycle and scope, without an architecture comparison. The selected instance disk image is immutable after creation. Sources: `fulfillment-service/internal/servers/private_baremetal_instances_server.go` and `fulfillment-service/internal/servers/disk_image_validation.go`.
- This inspection is not the comprehensive architecture-bearing resource audit required by the Feature.

## Round 1 — Architecture Vocabulary and Compatibility Behavior

### R1.Q1: Canonical values

Disk-image choices currently use `amd64`, `arm64`, and `s390x`. Which values should users see consistently across bare-metal types, disk images, UI, CLI, and API?

Suggested answers: `amd64`, `arm64`, `s390x`; or `x86_64`, `aarch64`, `s390x`. The user may specify another vocabulary explicitly.

#### Answer

The user selected the recommended vocabulary: `amd64`, `arm64`, and `s390x`.

#### Impact

The PRD will require consistent canonical architecture names across bare-metal types, disk images, UI, CLI, and API, with acceptance scenarios for aligned inputs, displays, and filters.

#### Decision (D1)

The canonical user-visible CPU architecture values are `amd64`, `arm64`, and `s390x`.

---

### R1.Q2: Accepted architecture inputs

Which architecture names should be accepted, and how should aliases, case variations, and surrounding whitespace be handled?

#### Answer

The user's later revision replaces the original normalization answer: accept only the exact names `amd64`, `arm64`, and `s390x`. Reject aliases such as `x86_64` and `aarch64`, case variations, surrounding whitespace, and unknown values.

#### Impact

The PRD requires canonical-only validation with actionable rejection of every noncanonical input. There is no runtime alias mapping, case conversion, or whitespace trimming. Displays and filters use the same canonical names across interfaces.

#### Decision (D2)

The original alias-normalization decision is superseded by D6. The effective decision is to accept only exact canonical names and reject all noncanonical inputs.

---

### R1.Q3: Existing catalog data

How should existing `BareMetalInstanceType` resources with noncanonical architecture strings behave when this feature is introduced?

#### Answer

Under the user's canonical-only revision, all existing noncanonical architecture values remain visible for correction. An admin must correct them to exact canonical names before the affected `BareMetalInstanceType` resources can be used for new provisioning. Recognized aliases receive no special treatment.

#### Impact

The PRD requires correction of every existing noncanonical architecture value, including previously recognized aliases, before new provisioning can use it. No runtime normalization preserves compatibility for legacy values. The correction mechanism belongs in the design. D4 continues to allow changes that do not trigger provisioning.

#### Decision (D3)

The original legacy-alias normalization decision is superseded by D6. The effective decision is to keep existing noncanonical values visible and require correction before the affected `BareMetalInstanceType` resources can be used for new provisioning.

---

### R1.Q4: Compatibility checks on existing instance updates

If an existing instance's selected image and type become incompatible after catalog metadata changes, should every instance update be rejected, as the ticket currently states, or only updates that can trigger provisioning?

Suggested answers: check every instance update, including metadata edits and stop requests; or check provisioning-related updates while allowing metadata edits and stop requests.

#### Answer

The user explicitly directed: “For q4 only block changes that would trigger provisioning.”

#### Impact

The PRD will apply compatibility enforcement to new provisioning and to instance updates that would trigger provisioning. Architecture incompatibility will not block metadata edits or stop requests that do not trigger provisioning. This explicit user direction narrows the Feature's blanket create-or-update wording; other tenant-scope, authorization, immutability, and lifecycle rules still apply.

#### Decision (D4)

Reject incompatible architecture selections before new provisioning starts, including instance updates that would trigger provisioning. Do not reject instance changes solely for architecture incompatibility when they would not trigger provisioning.

---

### R1.Q5: Incompatible image choices in the UI

After a user chooses a bare-metal type, how should architecture-incompatible images appear? Compatible images that support multiple architectures would remain selectable.

Suggested answers: show incompatible images disabled with a reason; hide incompatible images; or allow selection and reject submission with an actionable error.

#### Answer

The user selected the recommended behavior: show incompatible images disabled with a reason. Compatible multi-architecture images remain selectable.

#### Impact

The PRD will require users to see why an incompatible image cannot be selected after choosing a bare-metal type. Compatible multi-architecture choices remain usable. The existing requirement for an authoritative compatibility error before provisioning also applies to CLI and API submissions, including requests made outside the UI.

#### Decision (D5)

After a bare-metal type is selected, show architecture-incompatible images disabled with an explanation. Keep compatible images selectable, including images that declare the target architecture among multiple supported architectures.

---

## Revision Direction — Canonical-Only Inputs

### User instruction: Hard cut to canonical names

The user requested: “actually let's make this a hard cut to avoid having to carry normalization forever. Only the canonical architecture names should be accepted”. This is an explicit override of D2 and the normalization part of D3; no additional confirmation is required.

#### Answer

Accept only the exact names `amd64`, `arm64`, and `s390x`. Reject aliases, case variations, surrounding whitespace, and other unknown values rather than normalizing them.

#### Impact

The PRD describes canonical-only validation and correction of all existing noncanonical catalog values before new provisioning can use them. Documentation, regression scenarios, provider stories, and catalog requirements follow this rule. Existing noncanonical values remain visible for correction. D4 still limits blocking to requests that would trigger provisioning, and D5 still defines the UI behavior for incompatible image choices.

#### Decision (D6)

Only exact canonical architecture names are accepted: `amd64`, `arm64`, and `s390x`. No runtime alias mapping, case conversion, or whitespace trimming is supported. Existing noncanonical `BareMetalInstanceType` architecture values require correction to exact canonical names before use in new provisioning. D6 supersedes D2 and the normalization behavior in D3; D1, D4, and D5 remain binding.

---

## Revision Direction — Resource Names

The user directs the PRD to use proper resource names whenever it references a resource, for example `BareMetalInstanceType` rather than “bare-metal type”. Resource references use `BareMetalInstanceType`, `BareMetalInstance`, `DiskImage`, `BareMetalInstanceCatalogItem`, and `BareMetalInstanceTemplate` as applicable. This is a terminology correction and does not change the effective behavioral decisions.

## Revision Direction — Omit Dependencies

The user requests removal of the Dependencies section. Its former entries describe runtime validation behavior and this effort's delivery scope, which are already covered in In Scope. No separate delivery prerequisite or external coordination constraint is identified, so the optional Dependencies section is omitted.

## Remaining Gaps

None remain that block PRD drafting. The comprehensive resource audit, migration mechanism, exact error representation, and identification of provisioning-triggering update paths are design work under the locked product behavior; they are not assumed completed here.

## Exit Criteria

- [x] Functional requirements are enumerable: exact canonical vocabulary, rejection of noncanonical inputs, compatibility checking after selection/default resolution, existing-data correction, consistent UI/CLI/API behavior, actionable errors, documented audit boundaries, and regression coverage.
- [x] Target users are identified: Cloud Provider Admin, Cloud Infrastructure Admin, Tenant Admin, and Tenant User.
- [x] Scope boundaries are clear: BMaaS, with the Feature's explicit exclusions retained. User direction removes milestone references from the PRD.
- [x] No unresolved contradictions remain: D4 explicitly overrides the blanket update wording; D6 explicitly supersedes normalization in D2/D3 with canonical-only validation and correction of existing noncanonical values.
- [x] Key assumptions are confirmed or corrected through the effective decisions D1, D4, D5, and D6. Technical decisions will not be presented as user requirements.
- [x] Concrete non-functional constraints are enumerable: reject before provisioning, preserve tenant isolation and confidentiality, preserve existing lifecycle validation, and keep errors actionable and consistent. No numerical performance target is invented.
- [x] Dependencies are assessed: no separate delivery prerequisite or external coordination constraint is identified. Catalog data correction, default resolution, and UI/CLI/API consistency are requirements within this effort and remain in In Scope. User direction removes the optional Dependencies section.
