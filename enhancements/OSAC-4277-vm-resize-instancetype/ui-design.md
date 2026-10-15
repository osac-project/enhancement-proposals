# UI Design — OSAC-4282

**Story:** OSAC-4282 — UI Design - VM Resize via InstanceType Selection
**Date:** 2026-10-15 (revised; original 2026-10-14)
**Parent:** OSAC-5635 (UIX - VM Resize Instancetype Selection), feature OSAC-4277

## Summary

This design delivers day-2 instance-type editing (resize) for VMaaS virtual
machines in the VM details Overview: an edit pencil on the Instance type row
of the Details card opens an **Edit instance type** modal where the tenant
selects a new instance type from the same ACTIVE catalog used at create,
restricted to the VM's GPU class. Both **Tenant Admins and Tenant Users**
can resize (updated handoff, aligned to the OSAC-4277 PRD); other Overview
config (SSH, Network, Storage) stays read-only for Tenant Users and is
untouched by this feature. [Handoff: Entry — Roles] Because the platform currently has no
hot-plug mechanism (restart is the only resize delivery path, deferred
multi-node hot-plug tracked by OSAC-5335) and the API exposes no boot-disk
access mode, the UI implements the handoff's two restart paths — Running VMs
get an inline restart warning, Stopped VMs get an inline "applies on next
start" info — both with a **Save** CTA submitting
`ComputeInstances/Update` with `updateMask: { paths: ["spec.instance_type"] }`.
[Handoff: Resize paths] [Design: IC-1] [Codebase: osac-aap restart-only
profile] [User: confirmed split]

The hot-plug path from the handoff (Running + RWX, no warning, CTA "Apply
Resize") is **flagged as a split**: it requires OSAC-5335 backend work plus a
UI-readable signal for boot-disk access mode or restart necessity. This
document records exactly what that follow-up needs (see Open Questions). The
modal follows the established AttachExternalIpModal two-layer pattern
(generic Formik form modal + VM-specific data/mutation wrapper), and the
mutation follows the useVmPowerAction toast pattern. [Codebase:
components/ExternalIp/AttachExternalIpModal.tsx] [Codebase:
components/vm/useVmPowerAction.ts]

## Component Architecture

### Component Tree

```mermaid
graph TD
    VmDetailsPage[VmDetailsPage] --> VmDetails[VmDetails]
    VmDetails --> VmDetailsSummary[VmDetailsSummary]
    VmDetails --> VmDetailsActionButtons[VmDetailsActionButtons]
    VmDetails --> VmDetailsOverviewTab[VmDetailsOverviewTab]
    VmDetailsOverviewTab --> VmDetailsCard["VmDetailsCard — modified<br/>(pencil + modal state)"]
    VmDetailsCard --> WrapperModal["EditInstanceTypeModal (wrapper)<br/>components/vm/DetailsPage/ — new"]
    WrapperModal --> FormModal["EditInstanceTypeModal (form)<br/>components/vm/ — new"]
    FormModal --> TypeaheadSelectField[TypeaheadSelectField — reused]
    WrapperModal --> UpdateHook["useUpdateVmInstanceType — new"]
```

Narrative: `VmDetailsPage` fetches the VM (`useComputeInstance`) and renders
`VmDetails`, which already fetches the current full `InstanceType`
(`useInstanceType`) for the summary — the TanStack query cache makes that
same data available to the new wrapper modal without a second request.
`VmDetailsCard` (Overview tab's Details card) gains the pencil affordance on
the Instance type row and owns the modal-open boolean, mirroring how
`VmDetailsActionButtons` owns its modal-open states. [Codebase:
components/vm/DetailsPage/VmDetails.tsx:42-46] [Codebase:
components/vm/DetailsPage/VmDetailsActionButtons.tsx:34-35]

### New Components

#### EditInstanceTypeModal (generic form modal)

- **File:** `osac-ui/libs/ui-components/src/components/vm/EditInstanceTypeModal.tsx`
- **Purpose:** Presentational Formik modal for selecting an instance type.
  Owns form state, validation, the changed-selection alert, and submit/cancel
  wiring. Kept separate from the wrapper so the form behavior (alert-on-change
  rule, validation, submit lifecycle) is testable without API mocking of the
  instance-type catalog. [Codebase: mirrors components/ExternalIp/
  AttachExternalIpModal.tsx structure]
- **Source:** [Handoff: Modal content] [User: confirmed two-layer pattern]
- **Props:**

```typescript
export interface EditInstanceTypeModalProps {
  title: string;                      // "Edit instance type"
  description: string;                // GPU / non-GPU guidance text
  options: TypeaheadSelectOption[];   // ACTIVE catalog, GPU-class filtered
  initialInstanceTypeId: string;      // current type — preselected
  alert: {                            // shown only when selection differs
    variant: 'warning' | 'info';
    text: string;
  };
  isLoading: boolean;                 // catalog / current-type still loading
  onSave: (instanceTypeId: string) => Promise<unknown>;
  onClose: () => void;
}
```

- **Children:** `OsacForm` > `TypeaheadSelectField`; PF `Modal`, `Alert`,
  `Button`.
- **State:** Formik form values `{ instanceTypeId: string }` (initialized to
  `initialInstanceTypeId`); no other local state — submit errors surface as
  toasts from the action hook (see Notes), so there is no `submitError`
  state.
- **Notes:** Follows `ExternalIpAttachModal` structure (Formik + Yup +
  `OsacForm` + PF `Modal variant="small"` + `aria-labelledby`) except for
  error surfacing: the External IP modal shows an inline danger alert, while
  this modal surfaces errors as danger toasts from the action hook, matching
  the VM-domain `useVmPowerAction` pattern and the handoff's "mismatch
  blocked with toast". On rejection the modal stays open; on success it
  closes. The inline alert renders only when
  `values.instanceTypeId !== initialInstanceTypeId`. [Handoff: Alerts appear
  only after the user selects a different instance type] The primary CTA is
  always **Save** (label `t('Save')`), enabled when a selection exists and
  `!isLoading && !isSubmitting` — submitting the unchanged current type is
  allowed and is a backend no-op per IC-3. [Handoff: Primary] [Design: IC-3]
  Modal `onClose` is `undefined` while submitting (matches External IP
  pattern).

#### EditInstanceTypeModal (VM-specific wrapper)

- **File:** `osac-ui/libs/ui-components/src/components/vm/DetailsPage/EditInstanceTypeModal.tsx`
- **Purpose:** Owns data and mutation for the resize: fetches the ACTIVE
  instance-type catalog, derives the GPU-class filter from the current type,
  computes the alert variant/text from VM power state, and invokes the
  update action hook. Same-basename/two-directory split mirrors
  `AttachExternalIpModal` (generic in `components/ExternalIp/`, wrapper in
  `components/vm/DetailsPage/`). [Codebase:
  components/vm/DetailsPage/AttachExternalIpModal.tsx]
- **Source:** [Handoff: Resize paths] [Handoff: Modal content]
- **Props:**

```typescript
interface EditInstanceTypeModalProps {
  vm: ComputeInstance;       // VM being resized
  onClose: () => void;
}
```

- **Children:** generic `EditInstanceTypeModal` (form modal).
- **State:** none of its own — derives everything from queries + props.
- **Notes:** Calls `useInstanceType(vm.spec?.instanceType?.id)` (cached from
  `VmDetails`) and `useInstanceTypes({ filter: INSTANCE_TYPE_ACTIVE_LIST_FILTER })`.
  DEPRECATED instance types are valid resize targets server-side (accepted
  with a deprecation warning — see Verified Backend Behaviors) but are
  intentionally not offered here: the handoff scopes the picker to the same
  ACTIVE catalog used at create. [Handoff: Modal content]
  Options are built with `formatInstanceTypeOptionLabel` and filtered to the
  VM's GPU class: `instanceTypes.filter((it) => Boolean(it.spec?.gpu) ===
  hasGpu)` where `hasGpu = Boolean(currentType?.spec?.gpu)`. If the current
  type has not resolved (load error), no GPU filter is applied and the
  server's `FailedPrecondition` backstop governs. Alert computation:
  `vm.status?.state === RUNNING` → warning "This resize requires a VM
  restart. The VM will not be restarted automatically."; `STOPPED` → info
  "Resize will apply on next start." [Handoff: Resize paths] Description
  text: GPU VM — "This virtual machine uses a GPU instance type. You can
  only select other GPU instance types."; non-GPU VM — "This virtual machine
  uses a non-GPU instance type. GPU instance types are not available for
  this virtual machine." (proposed copy — handoff specifies guidance content
  by GPU class but not wording). `onSave` delegates to
  `useUpdateVmInstanceType().updateInstanceType(vm, instanceTypeId, label)`.

### Reused Components

| Component | Location | Usage | Changes Needed |
|-----------|----------|-------|----------------|
| `VmDetailsCard` | `components/vm/DetailsPage/VmDetailsCard.tsx` | Gains pencil button + modal-open state on the Instance type row | Modified (see below) |
| `TypeaheadSelectField` | `components/Form/TypeaheadSelectField.tsx` | Instance type select in the modal | None |
| `OsacForm` | `components/Form/OsacForm.tsx` | Form layout in modal | None |
| PF `Modal`, `Alert`, `Button`, `Tooltip` | `@patternfly/react-core` | Modal chrome, inline alert, footer, disabled-pencil tooltip | None |
| `ToastProvider`/`useToast` | `components/Toast/` | Success/error toasts | None |

**VmDetailsCard modification:** the Instance type `DescriptionListDescription`
becomes a `Flex` with the existing `displayValue(...)` text plus a plain
`Button` (`variant="plain"`, `PencilAltIcon`, `aria-label={t('Edit instance
type')}`), always rendered — the control is visible to every persona and is
gated by power state only, per the updated handoff.
Gating (mirrors `VmDetailsActionButtons.tsx:49-54`):

```typescript
const state = vm.status?.state;
const canEditInstanceState =
  state === ComputeInstanceState.RUNNING || state === ComputeInstanceState.STOPPED;
```

The button is disabled when `!canEditInstanceState`.
Tooltip copy when disabled:
- STARTING/STOPPING/PAUSED/FAILED/UNSPECIFIED: "The instance type can be
  changed when the virtual machine is running or stopped." [Handoff: Entry]
- DELETING: "This virtual machine is being deleted." [Handoff: Entry]

PF requires a disabled button to be wrapped (e.g., in a `span` with
`tabIndex={0}`... or PF `Tooltip` around a `Button` with `component="span"`)
for the tooltip to be keyboard-reachable; follow the PatternFly 6
disabled-button tooltip guidance. [User: confirmed gating including PAUSED
disabled]

## Hook Design

### New Hooks

#### useUpdateComputeInstanceInstanceType (API mutation hook)

- **File:** `osac-ui/libs/ui-components/src/api/v1/compute-instance.ts`
  (added beside `usePatchComputeInstance`)
- **Purpose:** Submits the resize via `ComputeInstances/Update` with an
  explicit `spec.instance_type` update mask, and exposes the full response
  (including `warnings`) to the caller.
- **Source:** [Design: IC-1] [Codebase: api/v1/compute-instance.ts:105-120]
- **Pattern:** follows `usePatchComputeInstance` (useMutation over
  `useApiFetch(ComputeInstances)`, invalidates compute-instance queries on
  success).

```typescript
export type UpdateComputeInstanceInstanceTypeInput = {
  id: string;              // ComputeInstance id
  instanceTypeId: string;  // target InstanceType id
};

// Returns the full UpdateResponse — { object, warnings } — because the
// success path needs response.warnings, unlike usePatchComputeInstance
// which discards it via .then((r) => r.object).
export const useUpdateComputeInstanceInstanceType = () => {
  /* useMutation<ComputeInstancesUpdateResponse, Error, UpdateComputeInstanceInstanceTypeInput> */
};
```

- **Data source:** `ComputeInstances/Update`
  (`PATCH /api/fulfillment/v1/compute_instances/{id}`) with body
  `{ object: { id, spec: { instanceType: { id: instanceTypeId } } },
  updateMask: { paths: ['spec.instance_type'] } }`. The mask is hardcoded,
  not derived via `buildUpdateMaskPaths`, because the body is a deliberately
  partial spec — auto-derivation would emit `spec.instance_type.id` instead
  of the contract's `spec.instance_type`. [Design: IC-1]
- **Cache strategy:** TanStack mutation; `onSuccess` calls
  `invalidateComputeInstancesQueries(qc)` (existing helper) so the details
  page reflects the new type.
- **Error handling:** rejected promise propagates to the action hook, which
  surfaces a danger toast.
- **Dependencies:** `useApiFetch`, `useApiQueryClient`,
  `invalidateComputeInstancesQueries`.

#### useUpdateVmInstanceType (action hook)

- **File:** `osac-ui/libs/ui-components/src/components/vm/useUpdateVmInstanceType.ts`
- **Purpose:** Wraps the API mutation with the handoff's success toasts
  (power-state-dependent copy, plus response `warnings`) and a danger error
  toast — the same role `useVmPowerAction` plays for power actions.
- **Source:** [Handoff: Success toasts] [Codebase:
  components/vm/useVmPowerAction.ts]
- **Pattern:** follows `useVmPowerAction` (hook composes mutation + toasts;
  callers await the returned promise).

```typescript
export const useUpdateVmInstanceType = () => {
  // Returns a promise that resolves on success and rejects on error.
  // vmName/label power the toast copy; state is read from vm at call time.
  const updateInstanceType = (
    vm: ComputeInstance,
    instanceTypeId: string,
    instanceTypeLabel: string,
  ): Promise<void>;
  return { updateInstanceType };
};
```

- **Data source:** delegates to `useUpdateComputeInstanceInstanceType`.
- **Cache strategy:** n/a (mutation hook owns invalidation).
- **Error handling:** `onError` → `addToast({ variant: 'danger', title:
  t('Failed to update the instance type for {{name}}', { name: vmName }),
  description: getErrorMessage(error) })` — this is the backstop surface for
  the server's GPU-mismatch `FailedPrecondition` and OBSOLETE
  `FailedPrecondition`. [Handoff: mismatch blocked with toast] [Design: IC-2]
- **Dependencies:** `useUpdateComputeInstanceInstanceType`, `useToast`,
  `useTranslation`, `getErrorMessage`.
- **Toast copy helper:** `components/vm/instanceTypeUpdateToast.ts` (mirrors
  `powerActionErrorTitle.ts`) exporting:
  - success, Running: "Instance type updated to {label}. Restart the virtual
    machine to apply the resize." [Handoff: Success toasts]
  - success, Stopped: "Instance type updated to {label}. Resize will apply
    on next start." [Handoff: Success toasts]
  - success, other states (defensive): "Instance type updated to {label}."
  - when the response carries `warnings`, join them into the toast
    description. [Design: IC-2] [Codebase:
    compute_instances_service_pb.ts L240-252]

### Reused Hooks

| Hook | Location | Usage in This Feature |
|------|----------|-----------------------|
| `useInstanceTypes` | `api/v1/instance-types.ts` | ACTIVE catalog for the select options (with `INSTANCE_TYPE_ACTIVE_LIST_FILTER`) |
| `useInstanceType` | `api/v1/instance-types.ts` | Current type: GPU class, display label, initial selection (cache shared with `VmDetails`) |
| `useToast` | `components/Toast/useToast` | Success/error toasts from the action hook |
| `useTranslation` | `hooks/useTranslation` | All copy (English-text-as-key) |
| `useComputeInstance` | `api/v1/compute-instance.ts` | Unchanged — `VmDetailsPage` keeps fetching the VM |

## State Management

### State Decisions

| State | Scope | Location | Justification |
|-------|-------|----------|---------------|
| Modal open boolean | Local | `VmDetailsCard` | Only the pencil and the modal consume it; matches `attachExternalIpOpen` in `VmDetailsActionButtons` |
| Form values `{ instanceTypeId }` | Local | generic `EditInstanceTypeModal` (Formik) | Form state is modal-local by convention (`ExternalIpAttachModal`) |
| Instance-type catalog + current type | Server cache | TanStack Query via `useInstanceTypes`/`useInstanceType` | Already cached for `VmDetails`; no duplication |
| VM power state | Prop | `vm` prop | Read-only input to gating and alert computation |

### New State Structures

None. No shared or global state is introduced — the feature is fully local
to the VM details page plus server cache.

### State Unchanged

- TanStack Query cache keys (`v1/compute_instances`, `v1/instance_types`) —
  the new mutation only invalidates existing keys.
- Toast state (`ToastProvider`) — consumed via `useToast`.

## Route Structure

### New Routes

None.

### Route Configuration

No route changes. The feature lives entirely inside the existing VM details
route (`/vms/:id` → `VmDetailsPage`). No lazy-loading, guards, or error
boundaries are added. [Codebase: components/vm/DetailsPage/VmDetailsPage.tsx]

### Routes Unchanged

- `/vms`, `/vms/:id` — used as-is by this feature.

## Data Flow Mapping

### Resolved Data Sources

| UI Element | Data Needed | Source Type | API Endpoint | Response Field | Notes |
|------------|-------------|-------------|-------------|----------------|-------|
| Instance type select | ACTIVE instance types in the VM's GPU class | API | `InstanceTypes/List` via `useInstanceTypes({ filter: INSTANCE_TYPE_ACTIVE_LIST_FILTER })` | `items[].{id, metadata.name, spec.vcpus, spec.memoryGib, spec.gpu}` | Client-side GPU filter + `formatInstanceTypeOptionLabel`; "same catalog as create" [Handoff: Modal content] [User: confirmed ACTIVE-only] |
| Initial selection / GPU class / toast label | Current instance type | API | `InstanceTypes/Get` via `useInstanceType(vm.spec.instanceType.id)` | `object.spec.gpu`, `object.metadata.name` | Cache shared with `VmDetails` — no extra request |
| Pencil enablement | VM power state | Prop | — (from `vm.status.state` on the `vm` prop) | — | RUNNING/STOPPED enabled, all personas [Handoff: Entry] |
| Modal alert variant + text | VM power state | Computed | — | — | Derived in wrapper from `vm.status.state` [Handoff: Resize paths] |
| Modal description | GPU class of current type | Computed | — | — | Derived from `currentType.spec.gpu` [Handoff: Modal content] |
| Submit | Target instance type | User input | `ComputeInstances/Update` (`PATCH .../compute_instances/{id}`) | request `{ object: { id, spec: { instanceType: { id } } }, updateMask: { paths: ['spec.instance_type'] } }`; response `{ object, warnings }` | [Design: IC-1] |
| Success toasts | Label + power state + response warnings | Computed | — | — | Static handoff copy + `warnings[]` appended [Handoff: Success toasts] |
| Error toast | Server error | API | same Update call | rejected error | `getErrorMessage`; GPU-mismatch/OBSOLETE `FailedPrecondition` backstop [Design: IC-2] |

### Unresolved Data Sources

Both entries were investigated in `/review-api` and confirmed as API gaps
(see API Findings → Gap Details). Neither blocks the restart-only scope;
both are owned by the OSAC-5335 hot-plug split.

| UI Element | Data Needed | Expected Source | Gap Description |
|------------|-------------|-----------------|-----------------|
| Hot-plug eligibility (handoff's Running + RWX path) | Boot-disk access mode (RWX/RWO) | API — no source exists | Confirmed gap `field-gap-b8d4646e90fd`: `ComputeInstanceDisk` exposes only `size_gib` + `storage_tier`; no access mode anywhere on the API. Cannot be resolved client-side |
| Pre-submit restart necessity | Whether this resize requires a restart | API — no source exists | Confirmed gap `data-gap-f9f26da3fe39`: `RESTART_REQUIRED` is set post-submit by the operator (mirrors KubeVirt's post-apply condition). UI uses static power-state-derived messaging instead |

## Persona-Aware Decomposition

### Shared Components

All components (pencil, modal, hooks) are rendered identically for every
role; the pencil's enablement depends on power state only, not persona.

### Persona-Specific Components

None — no persona-specific rendering branches.

### Permission Gates

| Action/Element | Permission | Implementation | Source |
|----------------|------------|----------------|--------|
| Instance type pencil | Tenant Admin and Tenant User (power state only) | `isDisabled={!canEditInstanceState}` in `VmDetailsCard` — no persona term | [Handoff: Entry — Roles] |
| Resize submit | Existing `ComputeInstances/Update` permission | No UI permission gate beyond the pencil; backend RBAC unchanged | [Design: §4.7 RBAC — "No RBAC or tenancy changes required"] |

Both Tenant Admins and Tenant Users can resize, per the updated handoff
(2026-10-15) and Yifat's answer on OSAC-4281 — the original handoff line
reflected the generic Overview "read-only config" mock rule, not a
resize-specific product choice, and it conflicted with the OSAC-4277 PRD
user stories (Tenant User as resize actor). Other Overview config (SSH,
Network, Storage) stays read-only for Tenant Users and is untouched by this
feature. [Handoff: Entry — Roles]

Server-side verification (`/review-api`): the authorization policy allows
plain clients — including tenant users — to call `ComputeInstances/Update`
(`authz.rego:198-288`), so the platform already supports the updated
enablement; no backend permission change is needed.

### Portal Targeting

Not applicable — the project does not use portal/slot-based persona
rendering for this surface.

## Accessibility Implementation

### ARIA Roles and Labels

| Component | ARIA Role | Labels | Notes |
|-----------|-----------|--------|-------|
| Generic `EditInstanceTypeModal` | dialog (PF Modal) | `aria-labelledby="edit-instance-type-modal-title"` with `ModalHeader labelId` | Mirrors `attach-external-ip-modal-title` pattern |
| Instance type select | combobox (PF TypeaheadSelect) | `aria-label` from `TypeaheadSelectField` `toggleProps` (label "Instance type") | Built into the reused field |
| Pencil button | button | `aria-label={t('Edit instance type')}` | Icon-only button requires the label |
| Disabled pencil tooltip | tooltip | text per gating copy | Must stay keyboard-reachable (PF disabled-button tooltip guidance) |
| Toasts | status (PF AlertGroup) | title + description | Existing `ToastProvider` behavior |

### Keyboard Navigation

| Interaction | Keys | Component | Behavior |
|------------|------|-----------|----------|
| Open modal | Enter/Space on pencil | `VmDetailsCard` | Disabled pencil is not activatable |
| Navigate/filter options | arrows, typeahead text | TypeaheadSelectField | Built into PF TypeaheadSelect |
| Submit / cancel | Enter (form), Esc (modal) | modal | PF Modal Esc closes (disabled while submitting); Cancel button is first footer control |

### Focus Management

| Trigger | Focus Target | Method |
|---------|-------------|--------|
| Modal opens | Modal title / first focusable | PF Modal default (`variant="small"`) |
| Modal closes | Triggering pencil button | PF Modal default focus-return |

### Screen Reader Considerations

The inline warning/info alert uses PF `Alert isInline`, which is announced
when it appears; toasts land in the existing `AlertGroup` live region.
The changed-selection alert appearing/disappearing mid-interaction is the
handoff's specified behavior (only after a different type is selected).
[Handoff: Resize paths]

## Testing Strategy

### Component Tests

#### EditInstanceTypeModal (generic form modal)
- **Test file:** `osac-ui/libs/ui-components/src/components/vm/EditInstanceTypeModal.test.tsx`
- **Test pattern:** Vitest + RTL, `renderWithProviders` — follows
  `components/Cluster/Details/AttachExternalIpModal.test.tsx`.
- **What to test:**
  - Renders title, description, preselected current type; Save disabled
    while `isLoading` or no selection.
  - No alert initially; alert (correct variant + text) appears once a
    different option is selected; disappears if the selection reverts.
  - Submit calls `onSave` with the selected id and closes on resolve; stays
    open on rejection.
  - Cancel calls `onClose`.
  - ARIA: `aria-labelledby` wiring, icon-only pencil label (in card tests).

#### EditInstanceTypeModal (VM wrapper)
- **Test file:** `osac-ui/libs/ui-components/src/components/vm/DetailsPage/EditInstanceTypeModal.test.tsx`
- **What to test:**
  - Options filtered to the VM's GPU class (GPU VM sees only GPU types and
    vice versa); unfiltered fallback when the current type fails to load.
  - Alert variant: RUNNING → warning copy; STOPPED → info copy.
  - Submit issues `ComputeInstances/Update` with
    `updateMask.paths = ['spec.instance_type']` and the target id (captured
    via `transportOverrides.onComputeInstanceUpdate`).
  - Response `warnings` reach the success toast; rejected update surfaces a
    danger toast (GPU-mismatch `FailedPrecondition` backstop).

#### VmDetailsCard (modified)
- **Test file:** extend `osac-ui/libs/ui-components/src/components/vm/DetailsPage/VmDetailsCard.test.tsx` (create if absent)
- **What to test:**
  - Pencil enabled for RUNNING/STOPPED; disabled (with tooltip text) for
    STARTING/STOPPING/DELETING/PAUSED/FAILED.
  - Pencil enabled for both `tenant-user` and `tenant-admin` sessions —
    persona does not gate the control (updated handoff). [Handoff: Entry —
    Roles]
  - Pencil click opens the modal.

### Hook Tests

#### useUpdateVmInstanceType
- **Test file:** `osac-ui/libs/ui-components/src/components/vm/useUpdateVmInstanceType.test.ts` (or covered via the wrapper component tests if the codebase's prevailing pattern mocks hooks — prefer real transport coverage)
- **What to test:**
  - Success toast copy per power state (Running vs Stopped messages).
  - `warnings` appended to the success toast description.
  - Error toast with `getErrorMessage` on rejection.

The API hook `useUpdateComputeInstanceInstanceType` is exercised through the
wrapper tests via the mock transport (the codebase tests mutations through
component-level transport overrides rather than isolated hook suites).

### Mock transport support (required new test plumbing)

`osac-ui/libs/ui-components/src/test-utils/createMockConnectTransport.ts`
currently has no `computeInstances` fixture and no
`onComputeInstanceUpdate` override — add both (fixture with RUNNING/STOPPED
VMs referencing instance types of both GPU classes; override capturing the
Update request and returning a configurable `{ object, warnings }` response).
[Codebase: createMockConnectTransport.ts L168-199, L414-417]

### Integration Tests

No separate integration suite — the wrapper component tests with the mock
transport cover the component↔hook↔transport interactions for this story.
Cross-component deployed journeys (real resize + restart) belong to QE E2E
work under the parent epic, per the repo's integration-testing policy.

### Coverage Goals

Every handoff behavior is covered by at least one test: entry gating per
state (both personas enabled), GPU-class option filtering, alert-on-change
with correct variant per power state, CTA enablement, the exact Update
request shape, success toasts (both restart paths), warnings surfacing, and
the FailedPrecondition backstop toast.

## Acceptance Criteria Mapping

OSAC-4282 has no formal AC list; the implicit ACs below are derived from the
handoff and parent feature. [Handoff: full contract]

| AC | Description | Components | Hooks | Test Coverage |
|----|-------------|------------|-------|---------------|
| AC-1 | Pencil on Instance type row; enabled RUNNING/STOPPED, disabled otherwise with tooltip | `VmDetailsCard` | — | `VmDetailsCard.test.tsx` |
| AC-2 | Modal: title, GPU/non-GPU guidance, required typeahead with create catalog | both modals | `useInstanceTypes`, `useInstanceType` | both modal tests |
| AC-3 | GPU VMs stay in GPU set (and non-GPU in non-GPU) | wrapper modal | `useInstanceType` | wrapper modal test |
| AC-4 | Running VM: inline warning + Save | both modals | — | generic modal test |
| AC-5 | Stopped VM: inline info + Save | both modals | — | generic modal test |
| AC-6 | Alerts only when selection differs from current | generic modal | — | generic modal test |
| AC-7 | Success toasts per path | — | `useUpdateVmInstanceType` | hook/wrapper tests |
| AC-8 | GPU mismatch blocked with toast (client filter + server backstop) | wrapper modal | `useUpdateVmInstanceType` | wrapper modal test |
| AC-9 | Tenant Admin and Tenant User can both open Edit instance type; other Overview config stays read-only for Tenant User (out of scope here) | `VmDetailsCard` | — | `VmDetailsCard.test.tsx` |
| AC-10 | Submit = `ComputeInstances/Update` with `spec.instance_type` mask; response warnings surfaced | wrapper modal | `useUpdateComputeInstanceInstanceType` | wrapper modal test |

### Traced Acceptance Criteria

**AC-4: Running VM resize shows restart warning**
Given a Running VM and a user with edit rights
When the user opens the Edit instance type modal and selects a different type
Then an inline warning reads "This resize requires a VM restart. The VM will
not be restarted automatically." and the primary CTA is Save
**Implemented by:** both `EditInstanceTypeModal` layers
**Tested in:** `components/vm/EditInstanceTypeModal.test.tsx`

**AC-5: Stopped VM resize shows next-start info**
Given a Stopped VM
When the user selects a different instance type
Then an inline info reads "Resize will apply on next start." and the primary
CTA is Save
**Implemented by:** both `EditInstanceTypeModal` layers
**Tested in:** `components/vm/EditInstanceTypeModal.test.tsx`

**AC-7: Success toasts**
Given a successful save
When the VM is Running, the toast reads "Instance type updated to {label}.
Restart the virtual machine to apply the resize."
When the VM is Stopped, the toast reads "Instance type updated to {label}.
Resize will apply on next start."
**Implemented by:** `useUpdateVmInstanceType` + `instanceTypeUpdateToast.ts`
**Tested in:** `useUpdateVmInstanceType` coverage / wrapper modal test

## API Findings

- **Review date:** 2026-10-14
- **Endpoints verified:** 6 — `ComputeInstances/{Update,Get,List}`,
  `InstanceTypes/{List,Get}`, and the authorization policy covering
  `ComputeInstances/Update`
- **Mappings confirmed:** 9 of 9 data needs (7 resolved rows verified;
  2 previously-unresolved rows confirmed as gaps). The former
  persona-gating row (user role) was removed during `/revise` — Tenant
  User enablement landed, so the design no longer consumes `role`
- **Gaps:** 2 — both owned by the OSAC-5335 hot-plug split; neither blocks
  this design's restart-only scope

### Verified Endpoint Mappings

| UI Element | Data Needed | Endpoint | Response Field | Verified |
|------------|-------------|----------|----------------|----------|
| Instance type select | ACTIVE instance types in the VM's GPU class | `osac.public.v1.InstanceTypes/List` | `items[].{id, metadata.name, spec.vcpus, spec.memoryGib, spec.gpu}` | Yes — `instance_types_server.go:143-187` passes offset/limit/filter/order through and composes server-side filter defaults |
| Current instance type | type incl. GPU class + label | `osac.public.v1.InstanceTypes/Get` | `object.spec.gpu`, `object.metadata.name` | Yes — `spec.gpu` is `GpuSpec {pci_device_selector, resource_name, count}` (`instance_type_type.proto:85-94,118`) |
| Pencil enablement | VM power state | `osac.public.v1.ComputeInstances/Get` | `status.state` | Yes — existing DetailsPage data; List/Get delegate 1:1 |
| Modal alert variant + text | VM power state | computed | — | Yes — derived in wrapper from `vm.status.state` |
| Submit | Target instance type | `osac.public.v1.ComputeInstances/Update` | request `{ object: { id, spec: { instanceType: { id } } }, updateMask: { paths: ['spec.instance_type'] } }` | Yes — public server validates id/mask, applies field-mask merge semantics, passes mask through (`compute_instances_server.go:260-346`); private server triggers `validateInstanceTypeResize` on the `spec.instance_type` mask path (`private_compute_instances_server.go:561-626`) |
| Success toasts | Label + power state + response warnings | same Update call | `warnings[]` | Yes — public server propagates warnings (`compute_instances_server.go:344`); generated TS response type carries `warnings`. The preliminary "warnings unreachable" concern is resolved |
| Error toast | Server error semantics | same Update call | rejected gRPC status | Yes — see Verified Error Semantics below |

### Verified Backend Behaviors

Verified by reading the handler code, not just the types:

- **No-op precedence (IC-3):** `validateInstanceTypeResize` returns
  `resizeNoOp=true` for a same-type target **before** lifecycle validation
  runs, and a `spec.instance_type`-only mask no-op succeeds with the current
  type retained (`private_compute_instances_server.go:742-793`). Save with an
  unchanged selection is a safe success.
- **DEPRECATED warning format:** `Instance type '{name}' is deprecated and
  will become obsolete on {RFC3339}. Consider using '{replacement}'
  instead.` — appended to `warnings[]`, not an error
  (`instance_type_validation.go:56-84`). ACTIVE-only options mean this is
  only reachable when the current type drifts to DEPRECATED; handled
  defensively as a toast description.
- **GPU mismatch check is full `GpuSpec` equality:** the backend rejects any
  change to `spec.gpu` via `proto.Equal(current, target)` —
  `FailedPrecondition "cannot change GPU configuration when resizing from
  instance type '%s' to '%s'"`. This is stricter than the handoff's set-level
  guidance: a GPU VM selecting a *different* GPU type (different
  count/device) also fails. The handoff's set-level filter + mismatch toast
  remains correct UX — within-set cross-GPU changes surface as the same
  `FailedPrecondition` error toast. No design change needed.
- **RESTART_REQUIRED is post-submit only:** the operator mirrors KubeVirt's
  `VirtualMachineRestartRequired` condition *after* spec changes have been
  applied (`computeinstance_controller.go:809-815`), synced to fulfillment
  status via the feedback controller
  (`computeinstance_feedback_controller.go:136`). There is no pre-submit
  restart prediction.
- **Permission verification (former Open Question 1, resolved):** the
  authorization policy places `ComputeInstances/Update` in the plain-client
  allowlist (`authz.rego:198-288`). A tenant user (no `tenant-admin` realm
  role) is a plain client and **can** call Update server-side. The updated
  handoff (2026-10-15) enables both Tenant Admin and Tenant User resize —
  which the platform already supports; no backend permission change is
  needed.

### Verified Error Semantics

| Case | gRPC code | Message shape |
|------|-----------|---------------|
| Target instance type not found | `InvalidArgument` | `instance type '{id}' not found` |
| Target instance type OBSOLETE | `FailedPrecondition` | `instance type '{name}' is obsolete and cannot be used` |
| GPU configuration change (incl. GPU→different-GPU, GPU→non-GPU) | `FailedPrecondition` | `cannot change GPU configuration when resizing from instance type '{a}' to '{b}'` |
| Same-type no-op (only `spec.instance_type` in mask) | success | current type retained, no warnings |

All surface through the existing `getErrorMessage` toast path — no new
error handling needed.

### Pagination, Filtering, and Sorting

| Endpoint | Pagination | Filtering | Sorting | Notes |
|----------|------------|-----------|---------|-------|
| `InstanceTypes/List` | Yes — `offset`/`limit`, response `size`/`total` | Yes — CEL `filter`, composed with server-side per-field defaults | Yes — `order` | UI reuses the create-flow hook with `INSTANCE_TYPE_ACTIVE_LIST_FILTER`; catalog is small, no UI pagination needed |
| `ComputeInstances/Get` | n/a | n/a | n/a | Single object |
| `ComputeInstances/Update` | n/a | n/a | n/a | Single object + `warnings[]` |

### API Gaps

| # | Gap ID | Gap | Category | UI Impact | Severity |
|---|--------|-----|----------|-----------|----------|
| 1 | `field-gap-b8d4646e90fd` | Boot-disk access mode (RWX/RWO) not exposed on the API | field gap | Hot-plug branch cannot distinguish Running+RWX from Running+RWO | Medium (deferred to OSAC-5335) |
| 2 | `data-gap-f9f26da3fe39` | No pre-submit restart-necessity signal | data gap | Modal messaging is static (power-state-derived) rather than backend-authoritative | Medium (deferred to OSAC-5335) |

### Gap Details

#### Gap 1: Boot-disk access mode not exposed

- **Gap ID:** `field-gap-b8d4646e90fd`
- **Category:** field gap
- **UI need:** data-display — determine hot-plug eligibility (Running + RWX
  boot disk) to suppress the restart warning and show the "Apply Resize"
  CTA.
- **Current state:** `ComputeInstanceDisk` exposes only `size_gib` and
  `storage_tier` (`compute_instance_common_type.proto:41-47`); no access
  mode exists anywhere on the public or private API surface.
- **What's missing:** A boot-disk access-mode field (RWX/RWO/unknown) on
  `ComputeInstance` (e.g. `spec.boot_disk.access_mode`) or an equivalent
  hot-plug-eligibility indication.
- **Affected components:** `EditInstanceTypeModal` (VM-specific wrapper).
- **Severity:** Medium — blocks the hot-plug path only, which is explicitly
  split to OSAC-5335; the restart-only scope delivered here is unaffected.
- **Suggested approach:** Backend [DEV] story under OSAC-5335 to expose the
  boot disk's access mode (the KubeVirt volume access mode already known
  to the operator) on `ComputeInstances/Get`.

#### Gap 2: No pre-submit restart-necessity signal

- **Gap ID:** `data-gap-f9f26da3fe39`
- **Category:** data gap
- **UI need:** other — know before submit whether a given resize will
  require a restart, so the modal can branch between hot-plug and
  restart messaging pre-submit.
- **Current state:** `RESTART_REQUIRED` exists as a compute-instance
  condition, but it is set by the operator only *after* the spec change is
  applied (mirroring KubeVirt's post-apply condition). No endpoint predicts
  restart necessity for a candidate target type.
- **What's missing:** Either a synchronous restart-required indication on
  the Update response (usable for the post-submit toast) or a
  predict/validate endpoint the modal can call pre-submit.
- **Affected components:** `EditInstanceTypeModal` (VM-specific wrapper).
- **Severity:** Medium — the current design's static power-state-derived
  messaging is correct for the restart-only scope (Running → restart
  warning, Stopped → next-start info); the gap only matters once the
  hot-plug branch lands (OSAC-5335).
- **Suggested approach:** Backend [DEV] story under OSAC-5335; the
  synchronous-response option composes with Gap 1 (access mode + restart
  signal can share one response extension).

### Summary

- 9 of 9 data needs reviewed; 7 verified against handler code, 2
  confirmed as gaps. (The persona-gating data need was removed during
  `/revise` when Tenant User enablement landed.)
- 2 gaps, both medium, both owned by the OSAC-5335 hot-plug split
  (1 field gap, 1 data gap). Zero gaps block this design's restart-only
  delivery.
- The preliminary `warnings[]`-reachability concern is resolved: warnings
  propagate through the public Update response.
- One behavioral nuance documented (GPU check is full `GpuSpec` equality,
  stricter than the handoff's set-level guidance) — no design change
  required; the mismatch toast covers it.
- **Implementation readiness: high.** Every data need in this design's
  scope resolves to a confirmed endpoint and field; no new endpoints or
  fields are required for the restart-only scope.

## Open Questions

1. **What signal will the hot-plug branch key on when OSAC-5335 lands?**
   - **Source:** Handoff Running+RWX path vs. codebase (no access mode on
     the API; `RESTART_REQUIRED` is post-submit).
   - **Impact:** Determines the future modal branch: alert suppression +
     "Apply Resize" CTA. The UI needs either a boot-disk access-mode field
     on `ComputeInstance` or a synchronous restart-required indication on
     the Update response.
   - **Default:** Out of scope here; this design delivers the restart paths
     and records the requirement. [User: confirmed split]

2. **GPU/non-GPU guidance and disabled-state tooltip wording** — the
   handoff specifies guidance content by GPU class and a tooltip on
   disabled states but not exact copy.
   - **Source:** Handoff Modal content / Entry sections.
   - **Impact:** Copy-only; strings live in `instanceTypeUpdateToast.ts` /
     `VmDetailsCard` and i18n.
   - **Default:** Proposed wording in this document; Yifat can adjust during
     design review of the published doc.

## Resolved Questions

- **Tenant User access (was Open Question 1, resolved 2026-10-15):** Tenant
  Users **can** resize. Yifat's answer on OSAC-4281 — the handoff's earlier
  disablement reflected the generic Overview "read-only config" mock rule,
  not a resize-specific product choice, and conflicted with the OSAC-4277
  PRD. The refreshed handoff enables both Tenant Admin and Tenant User;
  this design was revised accordingly (power-state-only pencil gating) in
  `/revise`.

---

## Provenance

Authored: plan @ ui-design 0.1.0 - 1c6e8de, workspace main @ 14c4d6f1c (5 behind origin/main)
Final: respond @ ui-design 0.1.0 - 0c7ea35, workspace main @ 14c4d6f1c (17 behind origin/main)

> Context changed between plan and respond.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"ui-design","workflow_version":"0.1.0","ai_workflows":"0c7ea35","source_repo":"14c4d6f1c","source_repo_branch":"main","commits_behind_main":17,"commits_ahead_main":0,"main_ref":"main","phases":["plan","review-api","revise","respond"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
