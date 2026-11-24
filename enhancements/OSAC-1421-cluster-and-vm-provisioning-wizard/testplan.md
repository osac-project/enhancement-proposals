# Test Plan — OSAC-1421 Cluster and VM provisioning wizard

## Overview

- **Design:** [Public design](design.md)
- **Total test cases:** 25

Execution entries identify assertions on OSAC main. These tests were not run for this backfill. Gap entries specify planned assertions and name the responsible role. No individual follow-up is recorded.

The design’s component tests render the actual wizard or adapter step in jsdom. They use Formik, QueryClient and i18n with an in-memory Connect transport; the full-wizard specs replace route navigation with a spy. OSAC classifies this test boundary as Unit. Cases below distinguish a whole-wizard interaction from a single step or helper. The routed SPA and Go proxy boundary has its own Component integration gap, and the manual smoke uses a deployed environment. [OSAC UI test boundaries](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-ui/AGENTS.md#test-boundaries)

## Test Cases

#### TC-WZ-01: Cluster schema returns a nested SSH field error

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Unit tests](design.md#unit-tests-existing-pattern)
- **Execution:** `osac-ui/libs/ui-components/src/components/Cluster/CreateWizard/schemas.test.ts`
- **Evidence:** `buildClusterStepSchema / rejects malformed ssh public key on general step` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-ui/libs/ui-components/src/components/Cluster/CreateWizard/schemas.test.ts#L143)).
- **Selector:** `pnpm --filter @osac/app-frontend run test libs/ui-components/src/components/Cluster/CreateWizard/schemas.test.ts -t 'rejects malformed ssh public key on general step'` from `osac-ui` in OSAC.

**Preconditions.** Use a cluster catalog item, name `my-cluster`, a populated pull-secret fixture and SSH input `not-a-key`.

1. Validate the General step.
2. Compare the nested errors.

**Expected results.** Only the nested `spec.sshPublicKey.value` error is returned, with the supported OpenSSH types.

#### TC-WZ-02: Wizard step ordering reflects the selected resource and launch entry

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Unit tests](design.md#unit-tests-existing-pattern)
- **Dependencies:** Real wizard, Formik, i18n and render tree in jsdom. Connect uses an in-memory transport and canned resource lists. Browser, proxy and fulfillment deployment are absent.
- **Gap:** VM and cluster wizard tests assert direct launch on General. A complete ordered step-list assertion across both entry points is unverified.

**Preconditions.** Use one VM and one cluster catalog fixture. Start each from its list and directly from its catalog item.

1. Read the ordered step labels before and after selecting the catalog item.
2. Advance through each step and record which screen is active.

**Expected results.** The list launch starts on Catalog; direct launch starts on General. The subsequent labels and ordering match the designed resource flow.

#### TC-WZ-03: VM submit omits catalog-locked fields

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — VM submit omits catalog-locked fields](design.md#submit-and-api-errors)
- **Dependencies:** Real wizard, Formik, i18n and render tree in jsdom. Connect uses an in-memory transport and canned resource lists. Browser, proxy and fulfillment deployment are absent.
- **Execution:** `osac-ui/libs/ui-components/src/components/vm/CreateWizard/VmCreateWizard.test.tsx`
- **Evidence:** `VmCreateWizard / submits the catalog-governed payload and navigates to the new VM on success` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-ui/libs/ui-components/src/components/vm/CreateWizard/VmCreateWizard.test.tsx#L117)).
- **Selector:** `pnpm --filter @osac/app-frontend run test libs/ui-components/src/components/vm/CreateWizard/VmCreateWizard.test.tsx -t 'submits the catalog-governed payload and navigates to the new VM on success'` from `osac-ui` in OSAC.

**Preconditions.** Provide `catalog-vm-1` with a locked instance type, disk image, boot disk and run strategy. Mock Create returning `vm-new-1`.

1. Select the catalog item, enter `my-vm`, and advance to Review.
2. Create and inspect the Connect request and navigation.

**Expected results.** One request carries `my-vm` and the catalog ID, excludes the four locked fields, and navigates to `/vms/vm-new-1`.

#### TC-WZ-04: VM payload omits an empty selected user-data source

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Unit tests](design.md#unit-tests-existing-pattern)
- **Execution:** `osac-ui/libs/ui-components/src/components/vm/CreateWizard/payload.test.ts`
- **Evidence:** `buildComputeInstanceCreatePayload / omits user data when the selected source is empty` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-ui/libs/ui-components/src/components/vm/CreateWizard/payload.test.ts#L160)).
- **Selector:** `pnpm --filter @osac/app-frontend run test libs/ui-components/src/components/vm/CreateWizard/payload.test.ts -t 'omits user data when the selected source is empty'` from `osac-ui` in OSAC.

**Preconditions.** Choose the Secret source with a blank Secret name and stale inline data in the inactive source.

1. Build the VM payload.
2. Inspect spec for all three user-data fields.

**Expected results.** Spec omits `userData`, `userDataSecret` and `userDataSource`.

#### TC-WZ-05: Catalog Next reports a missing selection

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Catalog Next reports a missing selection](design.md#validation-and-step-gating)
- **Dependencies:** Real wizard, Formik, i18n and render tree in jsdom. Connect uses an in-memory transport and canned resource lists. Browser, proxy and fulfillment deployment are absent.
- **Execution:** `osac-ui/libs/ui-components/src/components/vm/CreateWizard/VmCreateWizard.test.tsx`
- **Evidence:** `VmCreateWizard / blocks Next on the catalog step until a catalog item is selected` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-ui/libs/ui-components/src/components/vm/CreateWizard/VmCreateWizard.test.tsx#L184)).
- **Selector:** `pnpm --filter @osac/app-frontend run test libs/ui-components/src/components/vm/CreateWizard/VmCreateWizard.test.tsx -t 'blocks Next on the catalog step until a catalog item is selected'` from `osac-ui` in OSAC.

**Preconditions.** Mount the VM wizard and return one published item via the test transport.

1. Wait for the item and leave it unselected.
2. Select Next and read the step alert.

**Expected results.** The wizard shows “Fix the highlighted errors before continuing.” This source asserts the alert; the field-level error and step retention are tracked in TC-WZ-19.

#### TC-WZ-06: Invalid fields keep the current step and clear after correction

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Invalid fields keep the current step and clear after correction](design.md#validation-and-step-gating)
- **Dependencies:** Real wizard, Formik, i18n and render tree in jsdom. Connect uses an in-memory transport and canned resource lists. Browser, proxy and fulfillment deployment are absent.
- **Gap:** Resource schema specs assert errors, but the full wizard touched-state and correction sequence is unverified.

**Preconditions.** Use a catalog fixture with an editable, bounded field. Use a VM fixture with empty name, disk image and instance type, and a cluster fixture with missing pull secret and nonempty malformed pod CIDR.

1. Click Next on General and Configuration before field blur. Inspect touched errors.
2. In a cluster fixture, set the optional pod CIDR to a malformed value and select Next. Correct the invalid input and select Next again.

**Expected results.** Required fields and the catalog-rule field surface their own errors. Invalid CIDR keeps the Networking step active. Corrected values clear errors and Next advances.

#### TC-WZ-07: Back preserves edits and changing the catalog resets them

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Back preserves edits and changing the catalog resets them](design.md#back-navigation-and-form-state)
- **Dependencies:** Real wizard, Formik, i18n and render tree in jsdom. Connect uses an in-memory transport and canned resource lists. Browser, proxy and fulfillment deployment are absent.
- **Gap:** VM and cluster wizard fixtures inspected do not verify full backward state retention and catalog reset.

**Preconditions.** Set distinct catalog defaults and enter a name, picker values and cluster node-set values.

1. Advance from each step and navigate Back through Review to General.
2. Change to the second catalog item and inspect defaults and locked controls.

**Expected results.** Back retains entered values. A catalog change resets prior edits, and locked defaults are visible but disabled.

#### TC-WZ-08: Cancel on a pristine VM wizard invokes the close callback

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Cancel on a pristine VM wizard invokes the close callback](design.md#cancel-breadcrumb-and-discard-guard)
- **Dependencies:** Real wizard, Formik, i18n and render tree in jsdom. Connect uses an in-memory transport and canned resource lists. Browser, proxy and fulfillment deployment are absent.
- **Execution:** `osac-ui/libs/ui-components/src/components/vm/CreateWizard/VmCreateWizard.test.tsx`
- **Evidence:** `VmCreateWizard / calls onClosed when Cancel is clicked` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-ui/libs/ui-components/src/components/vm/CreateWizard/VmCreateWizard.test.tsx#L175)).
- **Selector:** `pnpm --filter @osac/app-frontend run test libs/ui-components/src/components/vm/CreateWizard/VmCreateWizard.test.tsx -t 'calls onClosed when Cancel is clicked'` from `osac-ui` in OSAC.

**Preconditions.** Mount the VM wizard with a mocked close callback at the initial step.

1. Click Cancel once.
2. Inspect the callback.

**Expected results.** The callback runs exactly once.

#### TC-WZ-09: Dirty wizard discard guard protects draft edits

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Dirty wizard discard guard protects draft edits](design.md#cancel-breadcrumb-and-discard-guard)
- **Dependencies:** Real wizard, Formik, i18n and render tree in jsdom. Connect uses an in-memory transport and canned resource lists. Browser, proxy and fulfillment deployment are absent.
- **Gap:** Existing VM and cluster cancel cases only inspect close. The dirty-page guard journeys are unverified.

**Preconditions.** Edit a field on the VM or cluster create wizard and spy on Create and app navigation.

1. Choose Cancel, then Stay. Reopen the guard from the breadcrumb and choose Discard.
2. Repeat for history navigation if the route wires the same guard.

**Expected results.** Stay retains the value and wizard. Discard navigates to the list with zero Create calls.

#### TC-WZ-10: Cluster submit navigates to the returned ID

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Cluster submit navigates to the returned ID](design.md#submit-and-api-errors)
- **Dependencies:** Real wizard, Formik, i18n and render tree in jsdom. Connect uses an in-memory transport and canned resource lists. Browser, proxy and fulfillment deployment are absent.
- **Execution:** `osac-ui/libs/ui-components/src/components/Cluster/CreateWizard/ClusterCreateWizard.test.tsx`
- **Evidence:** `ClusterCreateWizard / submits the catalog-governed payload and navigates to the new cluster on success` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-ui/libs/ui-components/src/components/Cluster/CreateWizard/ClusterCreateWizard.test.tsx#L127)).
- **Selector:** `pnpm --filter @osac/app-frontend run test libs/ui-components/src/components/Cluster/CreateWizard/ClusterCreateWizard.test.tsx -t 'submits the catalog-governed payload and navigates to the new cluster on success'` from `osac-ui` in OSAC.

**Preconditions.** Provide a catalog fixture that governs cluster configuration. Capture the Create request and return the fixture ID.

1. Enter the required General fields and proceed to Review.
2. Submit and inspect the request and route.

**Expected results.** One request contains `my-cluster` and `catalog-cluster-1`, omits locked version and pullSecretSecret, and carries no node-set entries. Navigation uses `/clusters/cluster-new-1`.

#### TC-WZ-11: Create error remains on Review

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Create error remains on Review](design.md#submit-and-api-errors)
- **Dependencies:** Real wizard, Formik, i18n and render tree in jsdom. Connect uses an in-memory transport and canned resource lists. Browser, proxy and fulfillment deployment are absent.
- **Execution:** `osac-ui/libs/ui-components/src/components/vm/CreateWizard/VmCreateWizard.test.tsx`
- **Evidence:** `VmCreateWizard / shows a submission error on the review step without navigating away` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-ui/libs/ui-components/src/components/vm/CreateWizard/VmCreateWizard.test.tsx#L154)).
- **Selector:** `pnpm --filter @osac/app-frontend run test libs/ui-components/src/components/vm/CreateWizard/VmCreateWizard.test.tsx -t 'shows a submission error on the review step without navigating away'` from `osac-ui` in OSAC.

**Preconditions.** Provide a VM catalog fixture and return ResourceExhausted with text `Instance type is at capacity`.

1. Fill the required fields and submit from Review.
2. Inspect the error and navigation spy.

**Expected results.** Review shows the returned text and never navigates to Details.

#### TC-WZ-12: A success response missing an ID keeps the wizard on Review

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — A success response missing an ID keeps the wizard on Review](design.md#submit-and-api-errors)
- **Dependencies:** Real wizard, Formik, i18n and render tree in jsdom. Connect uses an in-memory transport and canned resource lists. Browser, proxy and fulfillment deployment are absent.
- **Gap:** The success and Connect-error wizard tests leave the missing-ID response unverified.

**Preconditions.** Use valid VM or cluster inputs and let the Create double return an object without an ID.

1. Submit, then check the alert, values and history.

**Expected results.** An error is displayed, form values remain, and no detail route is entered.

#### TC-WZ-13: Review shows the selected configuration and omitted fields

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Review shows the selected configuration and omitted fields](design.md#forward-navigation-and-review)
- **Dependencies:** Real wizard, Formik, i18n and render tree in jsdom. Connect uses an in-memory transport and canned resource lists. Browser, proxy and fulfillment deployment are absent.
- **Gap:** The existing submit and per-step specs do not assert the complete Review, Back and omission sequence.

**Preconditions.** Use a catalog item with an SSH default, single-option synthetic picker lists, one cluster node set and optional service CIDR left blank.

1. Advance to Review and go Back once. Replace a node count and return to Review.
2. Read labels and values, then inspect the mock submission.

**Expected results.** Review echoes the resolved picker names, SSH default and updated node count. The request omits the blank service CIDR.

#### TC-WZ-14: Picker errors and nonblocking create warnings have distinct outcomes

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Picker errors and nonblocking create warnings have distinct outcomes](design.md#submit-and-api-errors)
- **Dependencies:** Real wizard, Formik, i18n and render tree in jsdom. Connect uses an in-memory transport and canned resource lists. Browser, proxy and fulfillment deployment are absent.
- **Gap:** No wizard assertion was verified for picker-specific errors combined with the separate successful warning behavior.

**Preconditions.** In separate fixtures, return a network-picker list error and a successful Create with an ID plus a deprecation warning.

1. Open the failing picker and inspect its scoped error or retry control.
2. Submit the second fixture from Review and inspect the warning and route.

**Expected results.** The picker exposes its failure in the step. The warning is shown and navigation still uses the returned ID.

#### TC-WZ-15: Adapter controls enforce resource-specific choices

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Adapter controls enforce resource-specific choices](design.md#adapter-specific-component-tests)
- **Dependencies:** Real wizard, Formik, i18n and render tree in jsdom. Connect uses an in-memory transport and canned resource lists. Browser, proxy and fulfillment deployment are absent.
- **Gap:** Picker and schema tests provide narrower evidence. The documented adapter interaction matrix is unverified.

**Preconditions.** Use fixture lists containing an obsolete VM type, two VNs with distinct subnet/group lists, and two cluster host types.

1. Toggle the VM OS family and change the selected VN. Inspect option lists and dependent picks.
2. Add/remove cluster node rows. Try an empty row set and duplicate host-type selection, then correct the rows.

**Expected results.** The OS choice changes `spec.is_windows` and obsolete types are absent. VN changes reset stale dependent picks. Empty rows or duplicate host types block Next, and corrected rows appear with host type and node count in Review.

#### TC-WZ-16: VM and cluster create routes reach Details in a deployed smoke fixture

| Priority | Automation |
|---|---|
| high | manual |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [Design — manual smoke](design.md#manual-smoke)
- **Dependencies:** Real browser, SPA, Go proxy, authentication, fulfillment and relevant provisioners in a disposable environment; fixtures are synthetic. No service doubles.
- **Gap:** The shared Vitest harness uses Connect doubles. No deployed suite matching both wizard journeys and optional-field omissions was verified.

**Preconditions.** Prepare isolated synthetic tenant catalogs, instance type and cluster host type in a disposable deployment.

1. Open each wizard from its create route, supply required values, and leave optional fields blank.
2. Submit, check the details ID and clean up the fixture resources.

**Expected results.** Each Details page shows the distinct created resource, and the cluster records the selected node type and count.

#### TC-WZ-17: Cluster payload omits blank version, node sets and CIDRs

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Unit tests](design.md#unit-tests-existing-pattern)
- **Execution:** `osac-ui/libs/ui-components/src/components/Cluster/CreateWizard/payload.test.ts`
- **Evidence:** `buildClusterCreatePayload / omits blank optional fields, version, and node sets when no rows exist` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-ui/libs/ui-components/src/components/Cluster/CreateWizard/payload.test.ts#L74)).
- **Selector:** `pnpm --filter @osac/app-frontend run test libs/ui-components/src/components/Cluster/CreateWizard/payload.test.ts -t 'omits blank optional fields, version, and node sets when no rows exist'` from `osac-ui` in OSAC.

**Preconditions.** Use a named fixture with a catalog reference and pull secret name, blank version and CIDRs, and an empty node-set array.

1. Build the cluster request.
2. Compare the spec before transport serialization.

**Expected results.** Version, nodeSets and network are absent. Spec retains the catalog reference, named pull secret and automatic external IP false.

#### TC-WZ-18: Direct VM catalog launch starts on General

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Direct VM catalog launch starts on General](design.md#forward-navigation-and-review)
- **Dependencies:** Real wizard, Formik, i18n and render tree in jsdom. Connect uses an in-memory transport and canned resource lists. Browser, proxy and fulfillment deployment are absent.
- **Execution:** `osac-ui/libs/ui-components/src/components/vm/CreateWizard/VmCreateWizard.test.tsx`
- **Evidence:** `VmCreateWizard / starts on General without a catalog step for catalog launches` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-ui/libs/ui-components/src/components/vm/CreateWizard/VmCreateWizard.test.tsx#L107)).
- **Selector:** `pnpm --filter @osac/app-frontend run test libs/ui-components/src/components/vm/CreateWizard/VmCreateWizard.test.tsx -t 'starts on General without a catalog step for catalog launches'` from `osac-ui` in OSAC.

**Preconditions.** Render the wizard with a preselected catalog item using the tenant fixture.

1. Open the preselected wizard.
2. Read the visible Name field and look for the Catalog item step.

**Expected results.** The General name input is shown and the catalog selection step is absent.

#### TC-WZ-19: Catalog gates identify an untouched selection and keep the step active

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Catalog gates identify an untouched selection and keep the step active](design.md#validation-and-step-gating)
- **Dependencies:** Real wizard, Formik, i18n and QueryClient in jsdom. Connect and navigation are controlled; browser, proxy and fulfillment are absent.
- **Gap:** The named wizard suites assert the generic step alert, without a verified combined assertion for the field, active step and recovery.

**Preconditions.** Mount the VM and cluster wizards independently. Supply a single published catalog item and no selected item.

1. Select Next without touching a catalog card.
2. Confirm the field error and active step, select the card, and select Next again.

**Expected results.** The first click shows an inline selection error and the step alert and keeps Catalog Item active. The second click advances to General and clears the error.

#### TC-WZ-20: Cluster Review shows the selected node type and count

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Cluster Review shows the selected node type and count](design.md#forward-navigation-and-review)
- **Dependencies:** Real React component, Formik, i18n and QueryClient in jsdom. Connect is in-memory; browser, proxy and fulfillment are absent.
- **Execution:** `osac-ui/libs/ui-components/src/components/Cluster/CreateWizard/ClusterReviewStep.test.tsx`
- **Evidence:** `ClusterReviewStep / uses the simple host type and size display for a node set` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-ui/libs/ui-components/src/components/Cluster/CreateWizard/ClusterReviewStep.test.tsx#L76)).
- **Selector:** `pnpm --filter @osac/app-frontend run test libs/ui-components/src/components/Cluster/CreateWizard/ClusterReviewStep.test.tsx -t 'uses the simple host type and size display for a node set'` from `osac-ui` in OSAC.

**Preconditions.** Render the Review component with one fixture node set held in Formik.

1. Open the rendered Review panel.
2. Inspect the corresponding node-set row.

**Expected results.** The row renders the host type and node count from the fixture.

#### TC-WZ-21: Locked catalog node-set defaults remain visible and disabled

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Locked catalog node-set defaults remain visible and disabled](design.md#back-navigation-and-form-state)
- **Dependencies:** Real React component, Formik, i18n and QueryClient in jsdom. Connect is in-memory; browser, proxy and fulfillment are absent.
- **Execution:** `osac-ui/libs/ui-components/src/components/Cluster/CreateWizard/ClusterConfigurationStep.test.tsx`
- **Evidence:** `ClusterConfigurationStep / prepopulates locked catalog node sets and disables editing` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-ui/libs/ui-components/src/components/Cluster/CreateWizard/ClusterConfigurationStep.test.tsx#L250)).
- **Selector:** `pnpm --filter @osac/app-frontend run test libs/ui-components/src/components/Cluster/CreateWizard/ClusterConfigurationStep.test.tsx -t 'prepopulates locked catalog node sets and disables editing'` from `osac-ui` in OSAC.

**Preconditions.** Seed a catalog item with locked workers node set, worker type and size two.

1. Render Cluster Configuration with the catalog initial values.
2. Inspect the node-set controls.

**Expected results.** Workers, worker and two are visible in their respective fields. Name, count and Add node set controls are disabled.

#### TC-WZ-22: Cluster version picker shows an inline retry control on load failure

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Cluster version picker shows an inline retry control on load failure](design.md#submit-and-api-errors)
- **Dependencies:** Real React component, Formik, i18n and QueryClient in jsdom. Connect is in-memory; browser, proxy and fulfillment are absent.
- **Execution:** `osac-ui/libs/ui-components/src/components/Cluster/CreateWizard/ClusterConfigurationStep.test.tsx`
- **Evidence:** `ClusterConfigurationStep / surfaces a load error with a retry action when versions fail to load` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-ui/libs/ui-components/src/components/Cluster/CreateWizard/ClusterConfigurationStep.test.tsx#L113)).
- **Selector:** `pnpm --filter @osac/app-frontend run test libs/ui-components/src/components/Cluster/CreateWizard/ClusterConfigurationStep.test.tsx -t 'surfaces a load error with a retry action when versions fail to load'` from `osac-ui` in OSAC.

**Preconditions.** Use the Cluster Configuration fixture. The cluster version list handler returns Connect Unavailable.

1. Mount the step.
2. Inspect the inline version error and recovery control.

**Expected results.** The step displays “Could not load cluster versions” and a Retry button.

#### TC-WZ-23: Cluster Configuration adds a second node-set row

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Cluster Configuration adds a second node-set row](design.md#adapter-specific-component-tests)
- **Dependencies:** Real React component, Formik, i18n and QueryClient in jsdom. Connect is in-memory; browser, proxy and fulfillment are absent.
- **Execution:** `osac-ui/libs/ui-components/src/components/Cluster/CreateWizard/ClusterConfigurationStep.test.tsx`
- **Evidence:** `ClusterConfigurationStep / adds another node set row when Add node set is clicked` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-ui/libs/ui-components/src/components/Cluster/CreateWizard/ClusterConfigurationStep.test.tsx#L148)).
- **Selector:** `pnpm --filter @osac/app-frontend run test libs/ui-components/src/components/Cluster/CreateWizard/ClusterConfigurationStep.test.tsx -t 'adds another node set row when Add node set is clicked'` from `osac-ui` in OSAC.

**Preconditions.** Render Cluster Configuration with the default node set and the fixture version list.

1. Select Add node set.
2. Inspect the new row and its actions.

**Expected results.** Node set 2 and its Remove node set control appear.

#### TC-WZ-24: Switching the cluster network back to default clears custom picks

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [Design — Switching the cluster network back to default clears custom picks](design.md#adapter-specific-component-tests)
- **Dependencies:** Real React component, Formik, i18n and QueryClient in jsdom. Connect is in-memory; browser, proxy and fulfillment are absent.
- **Execution:** `osac-ui/libs/ui-components/src/components/Cluster/CreateWizard/ClusterNetworkingStep.test.tsx`
- **Evidence:** `ClusterNetworkingStep / clears custom selections when returning to tenant defaults` ([source](https://github.com/osac-project/osac/blob/46531b8c4da14b8e0f420b4de72ae350e80d3641/osac-ui/libs/ui-components/src/components/Cluster/CreateWizard/ClusterNetworkingStep.test.tsx#L251)).
- **Selector:** `pnpm --filter @osac/app-frontend run test libs/ui-components/src/components/Cluster/CreateWizard/ClusterNetworkingStep.test.tsx -t 'clears custom selections when returning to tenant defaults'` from `osac-ui` in OSAC.

**Preconditions.** Use a cluster Networking fixture with a ready tenant default and a second VN with a subnet and group.

1. Select the custom network, subnet and group. Switch to Tenant default and back to Custom network.
2. Inspect the VN, Subnet and selected group state.

**Expected results.** Custom VN is blank, Subnet is disabled pending selection and selected groups are empty.

#### TC-WZ-25: Routed wizard submits through the UI proxy

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [Design — Routed wizard submits through the UI proxy](design.md#submit-and-api-errors)
- **Dependencies:** Real SPA, browser routing, Connect serialization and Go proxy in an isolated fixture. Upstream fulfillment responses and test identity are controlled. No actual provisioner or tenant infrastructure.
- **Gap:** The VM and cluster Vitest suites stop at an in-memory Connect handler and navigation spy. The scoped UI routes, proxy and browser-spec search on OSAC main yielded no repeatable two-resource fixture for this boundary.

**Preconditions.** Use a disposable local UI deployment with the normal create routes and synthetic catalog/identity fixtures. Configure the fixture upstream to return a valid ID on one request and a normal validation status on another.

1. Open the real VM and cluster create routes and submit fixtures through their Review buttons.
2. Observe the request at the proxy/upstream boundary, the success route and the error state with the original values still present.

**Expected results.** A valid create sends exactly one request with that resource’s catalog ID and navigates to Details using the returned ID. A validation failure stays on Review and preserves input.
