# UI Design — OSAC-5677

**Story:** OSAC-5677 — UI Design - Normalize and validate CPU architecture compatibility

**Date:** 2026-11-03

**Feature:** OSAC-5672

## Summary

Cloud Provider Admins choose exactly amd64, arm64, or s390x when creating a BareMetalInstanceType. On edit, existing types display their migrated canonical architecture in a disabled selector. The UI provides no legacy repair action. [Design: IC-5, IC-7] [User decision: disabled architecture selector]

Cloud Provider Admins and Tenant Admins who author BareMetalInstanceCatalogItems also check architecture compatibility in the catalog create/edit Configuration step. Compare the configured locked values or editable defaults, using the selected template's type when the catalog item has no type value. When a concrete type and image pair exists, incompatible images stay in the dropdown disabled with a reason; an already selected image stays selected with a field validation error, and the wizard blocks progression or Save until the pair is compatible. Where no concrete pair exists, an optional catalog value may remain empty; BMI Configuration checks the tenant's eventual choice. [PRD: IS-1, IS-7] [User direction: catalog wizard compatibility]

In the tenant bare-metal wizard, the **effective BareMetalInstanceType** is the type the new instance would use after applying the CatalogItem policy, an editable user choice, and any CatalogItem or template default. Its CPU architecture determines image compatibility. Keep every otherwise eligible DiskImage in the dropdown regardless of architecture. Disable incompatible options with a reason naming the image's supported architectures and the effective type's architecture; matching images, including multi-architecture images, remain selectable. [PRD: IS-1, IS-4, IS-7] [Design: §4.1, IC-5] [User decision: show all with disabled reason]

A changed type triggers a new check of the selected or default image. [Design: IC-5] If the confirmed pair is incompatible, keep the image selected, show an image-field validation error explaining the architecture mismatch, and block Next. A user with an editable image field must select a compatible image to proceed. [User direction: retain incompatible image with validation] A locked incompatible image remains visible and blocks Next with catalog correction guidance. The fulfillment service remains authoritative if catalog data changes before Create. [Design: §4.3, IC-5]

No UX handoff is published for OSAC-5676. The interactions below are grounded in the PRD, technical design, test plan, and existing wizards. [Codebase: 01-context.md; existing catalog wizard]

## Component Architecture

The BareMetalInstance (BMI) creation wizard and the BareMetalInstanceCatalogItem
create/edit wizard both have **Configuration** steps with BareMetalInstanceType
and DiskImage selectors. This design updates those existing steps. [Codebase: existing wizard flows]

| Existing surface | UI decision |
|------------------|-------------|
| BareMetalInstanceType creation (provider) | Replace free-text architecture input with the three exact canonical choices. On the type edit screen, show the stored canonical value in a disabled architecture selector. |
| Bare metal catalog item Configuration (create/edit) | Check any configured type and image pair. Keep incompatible images visible but disabled with an architecture reason. Retain an incompatible selected image with field validation; block Next, direct navigation to Review, and Save while a concrete pair is incompatible or its lookup is unresolved. |
| BMI Configuration step | In the existing type and image selectors, show lookup progress and Retry. Keep otherwise eligible incompatible images in the dropdown, disabled with an architecture reason; allow compatible multi-architecture images. Retain an incompatible selection with an image-field validation error and block Next until the user chooses a compatible image. |

In catalog authoring, changing the type or, during creation, the template rechecks a configured image. If the pair becomes incompatible, keep the image selected with a field validation error and block progression and Save until the author chooses a compatible image or explicitly removes an optional image value. The incompatible option stays visible but disabled. On initial edit, keep an already incompatible pair identifiable for correction and block progression and Save. A field with no configured image remains optional unless its policy is Locked. [User direction: retain incompatible image with validation] [Codebase: existing catalog wizard]

BMI Configuration uses these outcomes:

| Result | UI response |
|--------|-------------|
| No effective type or required image | Explain the missing choice and block progression. |
| Lookup in progress | Show progress and block progression. |
| Lookup failed | Show an error and Retry; keep the choice visible. |
| Incompatible editable image after a type change | Keep the image selected, show an image-field validation error, and block Next until the user chooses a compatible image; list the incompatible option as disabled with an architecture reason. |
| Incompatible image on initial load | Keep the selected or default image visible with an image-field validation error and block Next; an editable field allows a different image, while a locked value needs catalog correction. |
| Incompatible locked image after a type change | Keep it selected, explain the mismatch and catalog correction, and block Next until the type or catalog changes. |
| Compatible | Allow normal progression, subject to the wizard's other validation. |

## Persona-Aware Decomposition

Existing persona-aware flows and access rules remain unchanged.

## Accessibility Implementation

- Label the architecture and image controls, and expose loading, lookup failure, and incompatibility messages to assistive technology. [Design: IC-5]
- On the type edit screen, keep the stored architecture visible in a labeled, disabled selector with a short explanation that hardware architecture cannot be changed. [User decision: disabled architecture selector]
- In both Configuration steps, show a short reason with each disabled image option that names both architectures, such as "Image supports arm64; selected type uses amd64." If keyboard navigation skips disabled options, repeat the same reason in associated field help or an accessible status. Verify that keyboard and screen-reader users can read it. [Test plan: TC-IS7-01] [User decision: use the default reason presentation] [User direction: catalog wizard compatibility]
- Keep an incompatible image selected and associate the validation error with its field after a type change in BMI creation or a type/template change in catalog authoring. The field error names both architectures and asks for a compatible image. Announce the mismatch to assistive technology without moving focus while lookup completes. [User direction: retain incompatible image with validation] [User direction: catalog wizard compatibility]
- In BMI creation, a tenant-locked incompatible image stays identifiable with catalog correction guidance. In catalog authoring, Locked does not prevent the author from replacing the value. [Design: IC-5] [Codebase: existing catalog wizard]
- Keep focus stable while data refreshes, make Retry keyboard-operable, and restore focus to the active step when Retry disappears. [Test plan: TC-IS7-03]

## Testing Strategy

Run UI interaction tests with mocked API responses. Use types whose CPU architecture is `amd64`, `arm64`, or `s390x`. For image compatibility checks, use an image that supports only `amd64`, one that supports only `arm64`, and one that supports both. Keep unrelated required fields valid. Check visible controls, field errors, navigation, and submitted values. [Test plan: TC-IS2-03, TC-IS7-01/02/03] [User direction: catalog wizard compatibility]

| Scenario | Setup and action | Expected result |
|----------|------------------|-----------------|
| Provider type create and edit | Submit a new type with each canonical architecture in separate runs; attempt an arbitrary value; open an existing type whose API value is canonical after migration. | Create offers only amd64, arm64, and s390x and sends the exact selected value. Edit shows the stored value in a labeled, disabled selector with an immutability explanation and no repair action. |
| BMI image choices and accessibility | Select a type whose CPU architecture is `amd64`; inspect the dropdown containing all three images with keyboard and accessibility queries. | The image supporting only `arm64` stays visible but disabled with an accessible reason naming `arm64` and `amd64`, including when keyboard navigation skips it. The image supporting only `amd64` and the one supporting both remain selectable. |
| BMI type change | With an editable type, select an `amd64` type and an image supporting only `amd64`, change to an `arm64` type, try Next, then choose a compatible image. | The image supporting only `amd64` stays selected and appears disabled in the dropdown; an associated architecture error blocks Next. Choosing an image supporting `arm64` clears the error and allows progression. |
| BMI defaults and locked values | Mock a List page without the CatalogItem image default and template-derived type, then load references containing their IDs and names; repeat with an incompatible tenant-locked image. | Get resolves the references by ID before Next, and their names stay visible. A locked mismatch gives catalog correction guidance and blocks Next; a compatible multi-architecture default works with either type. Create sends an editable type by name and an editable image by ID; locked values come from the CatalogItem. |
| BMI required choices and lookup failure | Leave a required type or image empty; then delay and fail a selected type or image lookup and use Retry with the keyboard. | Missing choices show field guidance. Pending and failed reads keep the selection and block Next; Retry recovers and returns focus to the active step. |
| BMI submission after catalog drift | Select a compatible pair, then have Create return `INCOMPATIBLE_DISK_IMAGE_ARCHITECTURE`. | The wizard shows the service's safe correction message and does not show a false success. |
| Catalog configured values | With a template whose type uses `amd64`, inspect image choices under Locked and Editable policies. Repeat with no image value and with an existing incompatible default; save compatible pairs in create and edit. | The image supporting only `arm64` stays listed but disabled with a reason naming both architectures, while matching images remain selectable and save their references and policies. An incompatible default stays selected with a field error and blocks Next, direct Review navigation, and Save. An empty optional image is allowed; an empty Locked image is not. |
| Catalog type changes and edit | Start with an explicitly configured `arm64` type and an image supporting only `arm64`, then choose an `amd64` type. Separately, start with an `arm64` type inherited from a template and change to a template whose type uses `amd64`; open an existing incompatible item for edit. | A mismatching image stays selected with a field error and blocks progression. The author can replace it even when Locked for tenants; a compatible image removes the error. |
| Catalog lookup and pre-save check | Delay or fail a selected type or image lookup and use Retry. After Configuration accepts a pair, return conflicting architecture data from the pre-save lookup. | Unresolved lookup blocks progression and Save without losing the selection. Retry recovers. The pre-save check catches the new mismatch, shows correction guidance, and prevents a CatalogItem Create or Update request. |

## Acceptance Criteria Mapping

OSAC-5677 has no issue-level AC identifiers. These criteria trace the current UI behavior and identify coverage that the published design and test plan still need. [Codebase: 01-context.md]

| Source | Observable result | Verification |
|---------------------|-------------------|--------------|
| IC-5; TC-IS2-03 | Provider type creation offers only amd64, arm64, and s390x, submits each exact value, and does not accept free-text architecture input. | Provider creation form submissions. |
| IC-5; user decision; test-plan expansion needed | Type edit shows the migrated canonical architecture in a labeled, disabled selector with an immutability explanation and no repair action. | Provider edit and accessibility check. |
| IS-1, IS-7; user direction; IC-5 / TC-IS7 expansion needed | Catalog create/edit checks every configured type/image pair, including Locked values, editable defaults, and a template-derived type. Incompatible images remain visible but disabled with an accessible architecture reason; a mismatch blocks Next, direct Review navigation, and Save. An optional image may remain unset. | Catalog wizard and keyboard/screen-reader checks. |
| User direction; IC-5 / TC-IS7-02 expansion needed | Catalog type, image, or create-time template changes recheck the pair. A mismatch keeps the selected image and its field error visible; an invalid pair loaded for edit remains correctable, including when its policy is Locked for tenants. | Catalog change and edit checks. |
| User direction; TC-IS7-03 expansion needed | Pending catalog lookups block progression or Save; failed lookups do the same and offer Retry. A pre-save recheck catches a new mismatch and blocks Save with correction guidance. | Catalog async and save checks. |
| IC-5; TC-IS7-01 | BMI Configuration lists all otherwise eligible images. Incompatible options stay visible but disabled with an accessible reason naming both architectures; compatible images, including multi-architecture images, remain selectable. | Option and keyboard/screen-reader checks. |
| IC-5; TC-IS7-02 | A selected or inherited default image remains identifiable and is checked against the effective type even when outside the loaded options. An incompatible locked image blocks Next with catalog correction guidance. | BMI default and off-page checks: retain reference ID and name for lookup and verify that Create sends editable choices while locked values come from the CatalogItem. |
| IC-5; TC-IS7-02; user direction | After a type change, an incompatible BMI image in an editable field stays selected with an image-field validation error and a disabled, explained dropdown option. Next stays blocked until the user chooses a compatible image. | BMI type-change and validation checks. |
| UI design; test-plan expansion needed | A missing required BMI type or image blocks Next with an explanation. | BMI required-field checks. |
| IC-5; TC-IS7-03; user direction | Pending or failed lookups block BMI progression without clearing a selected value; Retry recovers, and a server rejection after catalog drift is shown. | BMI async and submission checks. |
| IC-5; TC-IS9-04; user direction, catalog expansion needed | Provider type, catalog author, and tenant BMI journeys work against a deployed fulfillment service, including disabled reasons and submission errors. | Manual browser verification. |

The published IC-5 and TC-IS7-01/02/03, plus TC-IS9-04, cover provider and BMI flows but omit catalog authoring. TC-IS2-03 also does not cover the disabled type edit control. Update the technical design and test plan for those additions before implementation.

## API Findings

No missing backend field or endpoint is confirmed. Both wizards can compare the type architecture with the image's declared architectures using existing resource reads. The catalog wizard saves checked field policies through BareMetalInstanceCatalogItems.Create/Update, while BareMetalInstances.Create enforces compatibility authoritatively when provisioning is requested. Catalog, type, or image data can change later, so the catalog wizard's check does not replace the instance check. The API review should verify Get visibility and tenant scope for referenced resources in both wizards. [Design: §4.1, §4.3] [User direction: catalog wizard compatibility]

---

## Provenance

Authored: plan @ ui-design 0.1.0 - b369da0, workspace main @ 757d1aafe
Final: revise @ ui-design 0.1.0 - b369da0, workspace codex/osac-6548-cluster-upgrade-dialog @ c2fca2b64

> Context changed between plan and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"ui-design","workflow_version":"0.1.0","ai_workflows":"b369da0","source_repo":"c2fca2b64","source_repo_branch":"codex/osac-6548-cluster-upgrade-dialog","commits_behind_main":0,"commits_ahead_main":836,"main_ref":"main","phases":["plan","revise","revise","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
