# Test Plan — OSAC-1319 BareMetalInstance UI

## Overview

- **Design:** [Public design](design.md)
- **Total test cases:** 15

Execution entries identify assertions on OSAC main. These tests were not run for this backfill. Gap entries specify planned assertions and name the responsible role. No individual follow-up is recorded.

The current design replaces the draft’s no-op Networking slot with a Networking step and moves SSH and user data to Access & initial run. OSAC main documents React/jsdom cases with a Connect double as Unit.

## Test Cases

#### TC-BUI-01: The status label maps every state to its label and color

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — unit test matrix](design.md#test-plan)
- **Gap:** BareMetalInstance render specs checked on OSAC main do not assert the complete state-to-label/color table.

**Preconditions.** Prepare one synthetic BMI per state in the design’s status table.

1. Render each status label in the tenant locale.
2. Read its text and semantic color.

**Expected results.** Each state has the corresponding design label and color, including the transitional and failed states.

#### TC-BUI-02: Power actions reflect the BMI state

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — unit test matrix](design.md#test-plan)
- **Gap:** BareMetalInstance action-hook specs cover callbacks and mutations, but the full menu-availability matrix is unverified.

**Preconditions.** Render a details action menu with synthetic running, stopped and transitional BMIs. Capture callbacks.

1. Inspect the power toggle and Restart for each state.
2. Activate each enabled action using a fresh fixture.

**Expected results.** Running offers Stop and Restart, stopped offers Start, and transitional states disable the power actions. Each enabled control calls its designated action once.

#### TC-BUI-03: Builds a catalog-item create request object

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — unit test matrix](design.md#test-plan)
- **Execution:** `osac-ui/libs/ui-components/src/components/BareMetalInstance/CreateWizard/payload.test.ts`
- **Evidence:** `buildBareMetalInstanceCreatePayload / builds a catalog-item create payload` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-ui/libs/ui-components/src/components/BareMetalInstance/CreateWizard/payload.test.ts#L21)).
- **Selector:** `pnpm --filter @osac/app-frontend run test libs/ui-components/src/components/BareMetalInstance/CreateWizard/payload.test.ts -t 'builds a catalog-item create payload'` from `osac-ui` in OSAC.

**Preconditions.** Use name `my-bmi`, empty project and catalog item ID `catalog-bm-1` with empty wizard defaults.

1. Run the BMI payload builder without field overrides.
2. Compare the full request object before transport serialization.

**Expected results.** Metadata contains the name and empty project. Spec has the catalog ID, ALWAYS strategy, empty disk image ID, empty attachments and automatic external IP false.

#### TC-BUI-04: Access rejects a malformed SSH key

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — unit test matrix](design.md#test-plan) and [Current design — Networking and Access](https://github.com/osac-project/enhancement-proposals/blob/55618504c773791f5363815a4300b71f1028b376/enhancements/OSAC-1319-bare-metal-instance-ui/design.md#L80)
- **Gap:** BMI Access schema and step tests exercise authentication selection. No BMI SSH format matrix was verified.

**Preconditions.** Prepare generated public-only RSA, Ed25519 and supported ECDSA fixtures and a malformed single-token value. Supply valid inline data when required to isolate SSH validation.

1. Validate the nonempty keys on Access individually.
2. Read the SSH field result.

**Expected results.** Each supported OpenSSH public key passes format validation. The malformed value produces the SSH field’s format error.

#### TC-BUI-05: Conditions display the empty state and condition values

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — unit test matrix](design.md#test-plan)
- **Gap:** BMI details and progress specs checked on OSAC main do not assert both conditions-list presentations.

**Preconditions.** Use one BMI without conditions and one with Ready=False and message `Image pending`.

1. Render the conditions list for each fixture.
2. Read the empty state or the populated row.

**Expected results.** The first view renders its empty indicator. The second shows Ready, False and Image pending.

#### TC-BUI-06: Delete confirmation opens and closes

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — unit test matrix](design.md#test-plan)
- **Gap:** No matching BMI action-menu confirmation assertion was verified in the details or action specs.

**Preconditions.** Render actions for a deletable BMI named `bm-demo`; capture delete calls.

1. Choose Delete.
2. Verify the confirmation names the fixture, then cancel.

**Expected results.** The confirmation opens and closes. The delete callback receives zero calls.

#### TC-BUI-07: An unset run strategy leaves the correct power control available

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — unit test matrix](design.md#test-plan)
- **Gap:** The BMI action-hook tests do not establish the unset-strategy rendering behavior.

**Preconditions.** Render a Running BMI without run_strategy and a control stopped BMI with HALTED.

1. Open the actions for each instance.
2. Inspect the toggle and Restart.

**Expected results.** Running with unset strategy offers Stop, while the halted control offers Start.

#### TC-BUI-08: Access bounds inline user data at 65,536 bytes

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — unit test matrix](design.md#test-plan) and [Current design — Networking and Access](https://github.com/osac-project/enhancement-proposals/blob/55618504c773791f5363815a4300b71f1028b376/enhancements/OSAC-1319-bare-metal-instance-ui/design.md#L80)
- **Gap:** A VM Access size test exists. The BMI Access schema and wizard specs inspected do not assert both byte boundaries.

**Preconditions.** Use synthetic ASCII user data of exactly 65,536 and 65,537 bytes with the inline source selected.

1. Validate both fixtures on Access.
2. Inspect the inline field error independently of other fields.

**Expected results.** The first value passes the size guard. The second produces a size error and blocks Next.

#### TC-BUI-09: Networking serializes chosen subnet and security group

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Current design — Networking and Access](https://github.com/osac-project/enhancement-proposals/blob/55618504c773791f5363815a4300b71f1028b376/enhancements/OSAC-1319-bare-metal-instance-ui/design.md#L80) and [BMaaS networking UI — field mapping](https://github.com/osac-project/enhancement-proposals/blob/55618504c773791f5363815a4300b71f1028b376/enhancements/OSAC-1437-bmaas-networking/ui-design.md#7-field-mapping)
- **Execution:** `osac-ui/libs/ui-components/src/components/BareMetalInstance/CreateWizard/payload.test.ts`
- **Evidence:** `buildBareMetalInstanceCreatePayload — useDefaultNetwork / includes networkAttachments when useDefaultNetwork is false` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-ui/libs/ui-components/src/components/BareMetalInstance/CreateWizard/payload.test.ts#L216)).
- **Selector:** `pnpm --filter @osac/app-frontend run test libs/ui-components/src/components/BareMetalInstance/CreateWizard/payload.test.ts -t 'includes networkAttachments when useDefaultNetwork is false'` from `osac-ui` in OSAC.

**Preconditions.** Disable default networking. Set subnet `subnet-1` and security group `sg-1`.

1. Build the BMI create object.
2. Compare the attachment array.

**Expected results.** Exactly one item contains the selected subnet and group IDs. No interface or primary property is set in this fixture.

#### TC-BUI-10: Networking serializes opt-in to automatic external IP

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Current design — Networking and Access](https://github.com/osac-project/enhancement-proposals/blob/55618504c773791f5363815a4300b71f1028b376/enhancements/OSAC-1319-bare-metal-instance-ui/design.md#L80) and [BMaaS networking UI — field mapping](https://github.com/osac-project/enhancement-proposals/blob/55618504c773791f5363815a4300b71f1028b376/enhancements/OSAC-1437-bmaas-networking/ui-design.md#7-field-mapping)
- **Execution:** `osac-ui/libs/ui-components/src/components/BareMetalInstance/CreateWizard/payload.test.ts`
- **Evidence:** `buildBareMetalInstanceCreatePayload — autoExternalIpAttachment / sets autoExternalIpAttachment when enabled` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-ui/libs/ui-components/src/components/BareMetalInstance/CreateWizard/payload.test.ts#L247)).
- **Selector:** `pnpm --filter @osac/app-frontend run test libs/ui-components/src/components/BareMetalInstance/CreateWizard/payload.test.ts -t 'sets autoExternalIpAttachment when enabled'` from `osac-ui` in OSAC.

**Preconditions.** Use a wizard fixture with the automatic external IP option enabled and editable.

1. Build the BMI create object.
2. Inspect the option on spec.

**Expected results.** `autoExternalIpAttachment` is true.

#### TC-BUI-11: Custom networking requires both network and subnet

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Current design — Networking and Access](https://github.com/osac-project/enhancement-proposals/blob/55618504c773791f5363815a4300b71f1028b376/enhancements/OSAC-1319-bare-metal-instance-ui/design.md#L80) and [BMaaS networking UI — field mapping](https://github.com/osac-project/enhancement-proposals/blob/55618504c773791f5363815a4300b71f1028b376/enhancements/OSAC-1437-bmaas-networking/ui-design.md#7-field-mapping)
- **Execution:** `osac-ui/libs/ui-components/src/components/BareMetalInstance/CreateWizard/schemas.test.ts`
- **Evidence:** `Bare Metal networking validation / requires virtual network and subnet when useDefaults is false` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-ui/libs/ui-components/src/components/BareMetalInstance/CreateWizard/schemas.test.ts#L132)).
- **Selector:** `pnpm --filter @osac/app-frontend run test libs/ui-components/src/components/BareMetalInstance/CreateWizard/schemas.test.ts -t 'requires virtual network and subnet when useDefaults is false'` from `osac-ui` in OSAC.

**Preconditions.** Disable default networking and leave both resource picker IDs empty.

1. Validate the Networking step.
2. Read the nested error object.

**Expected results.** Both `virtualNetwork.id` and `subnet.id` under the attachment value have their required-field errors.

#### TC-BUI-12: Access blocks Next when both authentication inputs are absent

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Current design — Networking and Access](https://github.com/osac-project/enhancement-proposals/blob/55618504c773791f5363815a4300b71f1028b376/enhancements/OSAC-1319-bare-metal-instance-ui/design.md#L80)
- **Dependencies:** Real wizard, Formik, i18n and render tree in jsdom. Connect uses an in-memory transport and canned resource lists. Browser, proxy and fulfillment deployment are absent.
- **Execution:** `osac-ui/libs/ui-components/src/components/BareMetalInstance/CreateWizard/BareMetalInstanceCreateWizard.test.tsx`
- **Evidence:** `BareMetalInstanceCreateWizard / shows the authentication error on Access before allowing Next` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-ui/libs/ui-components/src/components/BareMetalInstance/CreateWizard/BareMetalInstanceCreateWizard.test.tsx#L199)).
- **Selector:** `pnpm --filter @osac/app-frontend run test libs/ui-components/src/components/BareMetalInstance/CreateWizard/BareMetalInstanceCreateWizard.test.tsx -t 'shows the authentication error on Access before allowing Next'` from `osac-ui` in OSAC.

**Preconditions.** Mount the wizard using a fixture catalog item and an empty SSH and user data selection.

1. Advance to Access with the earlier steps satisfied.
2. Click Next and check the authentication alert and step.

**Expected results.** The authentication error is visible and Review is not reached.

#### TC-BUI-13: Networking carries the chosen instance-type port selection

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Current design — Networking and Access](https://github.com/osac-project/enhancement-proposals/blob/55618504c773791f5363815a4300b71f1028b376/enhancements/OSAC-1319-bare-metal-instance-ui/design.md#L80) and [BMaaS networking UI — field mapping](https://github.com/osac-project/enhancement-proposals/blob/55618504c773791f5363815a4300b71f1028b376/enhancements/OSAC-1437-bmaas-networking/ui-design.md#7-field-mapping)
- **Dependencies:** Real wizard, Formik, i18n and render tree in jsdom. Connect uses an in-memory transport and canned resource lists. Browser, proxy and fulfillment deployment are absent.
- **Gap:** BMI payload coverage verifies the subnet and security group without a port. A port selection through Review and submission is unverified.

**Preconditions.** Use a selected instance type exposing two synthetic network ports and a custom subnet.

1. Select a port on Networking.
2. Open Review and inspect the create request captured by the test transport.

**Expected results.** Review identifies the selected port and the request carries its port name in `spec.networkAttachments[0].interface` along with the selected subnet.

#### TC-BUI-14: Networking offers only fabric ports and blocks an empty type

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Current design — Networking and Access](https://github.com/osac-project/enhancement-proposals/blob/55618504c773791f5363815a4300b71f1028b376/enhancements/OSAC-1319-bare-metal-instance-ui/design.md#L80) and [Networking UI — interface pickers](https://github.com/osac-project/enhancement-proposals/blob/55618504c773791f5363815a4300b71f1028b376/enhancements/OSAC-1437-bmaas-networking/ui-design.md#2-create-wizard-networking-step)
- **Dependencies:** Real wizard, Formik, i18n and render tree in jsdom. Connect uses an in-memory transport and canned resource lists. Browser, proxy and fulfillment deployment are absent.
- **Gap:** The Networking step render and schemas checked on OSAC main cover shared network controls and required resource picks. The per-type port matrix is unverified.

**Preconditions.** Use three catalog types with two fabric ports and one management port, a single fabric port, and no fabric port.

1. Change the selected type and inspect the Interface control. Try Next with the no-fabric fixture.
2. Repeat with Tenant default and Custom modes.

**Expected results.** Only fabric ports are selectable. The first is selected on type change; a single port is displayed without a selector, and the no-fabric fixture blocks Next.

#### TC-BUI-15: Default network sends no explicit default-port attachment

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Current design — Networking and Access](https://github.com/osac-project/enhancement-proposals/blob/55618504c773791f5363815a4300b71f1028b376/enhancements/OSAC-1319-bare-metal-instance-ui/design.md#L80) and [BMaaS networking UI — field mapping](https://github.com/osac-project/enhancement-proposals/blob/55618504c773791f5363815a4300b71f1028b376/enhancements/OSAC-1437-bmaas-networking/ui-design.md#7-field-mapping)
- **Execution:** `osac-ui/libs/ui-components/src/components/BareMetalInstance/CreateWizard/payload.test.ts`
- **Evidence:** `buildBareMetalInstanceCreatePayload — useDefaultNetwork / sends an empty networkAttachments list when useDefaultNetwork is true` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-ui/libs/ui-components/src/components/BareMetalInstance/CreateWizard/payload.test.ts#L207)).
- **Selector:** `pnpm --filter @osac/app-frontend run test libs/ui-components/src/components/BareMetalInstance/CreateWizard/payload.test.ts -t 'sends an empty networkAttachments list when useDefaultNetwork is true'` from `osac-ui` in OSAC.

**Preconditions.** Enable default networking and leave the fixture without an explicit port override.

1. Build the BMI create payload.
2. Read the networkAttachments field.

**Expected results.** The array is empty.
