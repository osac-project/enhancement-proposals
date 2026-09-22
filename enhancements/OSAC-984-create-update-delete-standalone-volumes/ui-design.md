---
title: volume-cud-console-ui
authors:
  - AI-assisted (design skill)
creation-date: 2026-09-17
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-984
prd:
  - "enhancements/OSAC-984-create-update-delete-standalone-volumes/prd.md"
see-also:
  - "enhancements/OSAC-984-create-update-delete-standalone-volumes/design.md (backend API design)"
  - "OSAC-4542 (Volume Get/List public API)"
  - "OSAC-4884 (attach/detach — future)"
---

# Volume CUD Console UI

## 1. Overview

Add Create, Update, and Delete volume management to the OSAC console. This
design covers the tenant-facing UI that consumes the public Volume CUD API
(OSAC-2685) at `/api/fulfillment/v1/volumes`. The backend API and its
implementation are complete; this document specifies the console experience.

The UI delivers three views: a volume list page (extending OSAC-4542's
read-only list), a create volume wizard (3-step: General → Configuration →
Review), and a volume details page with inline description editing and
a delete confirmation modal. All views follow existing OSAC UI patterns
(PatternFly 6, Formik + Yup, TanStack Query, Connect/gRPC-Web) and reuse
shared components from `libs/ui-components`, including the generic resource
hooks from `use-resource.ts`.

## 2. Goals and Non-Goals

### Goals

- Enable Tenant Users and Tenant Admins to create, update, and delete
  standalone storage volumes through the OSAC console.
- Display volume lifecycle states (Creating, Available, Failed, Deleting)
  with clear visual indicators and state-appropriate available actions.
- Surface actionable error messages for all failure modes (invalid input,
  duplicate name, version conflict, unauthorized access, backend failure).
- Maintain parity with the API and CLI — the console must show the same
  states, behaviors, and error results as the other interfaces (explicit
  PRD requirement).
- Follow established OSAC UI conventions so the volume experience is
  consistent with compute instances, clusters, and other managed resources.
- Meet WCAG 2.1 AA accessibility standards.

### Non-Goals

- Cloud Provider Admin cross-tenant volume management UI — Cloud Provider
  Admins use the same tenant-scoped views; no separate admin volume page is
  introduced.
- Volume attach/detach UI — covered by OSAC-4884.
- Volume list view design — covered by OSAC-4542. This design extends that
  list with CUD actions but does not redesign the list itself.
- Volume expansion, snapshot, clone, or backup UI.
- File/object storage or NFS volume creation.

## 3. Motivation / Background

OSAC-4542 delivered read-only volume visibility (Get/List) in the console.
OSAC-2685 added Create, Update, and Delete endpoints to the public API. The
console still has no way for tenants to manage volume lifecycle — they must
use the CLI or API directly. This design closes that gap.

The existing admin-facing storage management UI (storage tiers and backends
at `/admin/infrastructure/storage/`) proves the OSAC component patterns
work for storage resources. The volume CUD UI follows the same patterns but
targets tenant users at a different navigation path.

## 4. Design

### 4.1 Architecture

#### Component Hierarchy

```text
osac-ui/
├── apps/app-frontend/src/shell/
│   └── VolumeRoutes.tsx                 # Route definitions
├── libs/ui-components/src/
│   ├── api/use-resource.ts              # Generic resource hooks (existing, shared)
│   ├── components/Volume/
│   │   ├── VolumeWizardPage.tsx         # Create wizard page (breadcrumb + title)
│   │   ├── VolumeWizard.tsx             # Multi-step wizard (Formik + PF Wizard)
│   │   ├── GeneralStep.tsx              # Step 1: Project, Name, Description
│   │   ├── ConfigurationStep.tsx        # Step 2: Storage tier, Size, Access mode
│   │   ├── ReviewStep.tsx               # Step 3: Read-only summary before submission
│   │   ├── VolumeDeleteConfirmModal.tsx
│   │   ├── VolumeStatusLabel.tsx        # State → ResourceStatusLabel mapping
│   │   ├── VolumeActionsMenu.tsx        # Kebab menu (Delete)
│   │   ├── VolumeDetailsPage.tsx        # Details page shell (header + delete action)
│   │   └── VolumeDetailsPageContent.tsx # Column-layout details content
│   └── pages/tenant/
│       └── VolumesListPage.tsx          # List view with toolbar + table
```

#### Data Flow

```text
Browser
  → Connect JSON via generated `Volumes` client (POST per RPC to generated service/method paths)
  → Go proxy (Connect JSON → native gRPC bridge)
  → fulfillment-service gRPC server
  → public VolumesServer (inMapper, validation, delegation)
  → private VolumesServer → GenericDAO → PostgreSQL
  → Response: public Volume (outMapper preserves lifecycle status fields — state, message — while stripping internal-only fields: vendor_volume_id, backend, protocol, hub, vendor_context)
  → TanStack Query cache update → React re-render
```

The UI talks exclusively to the **public** API. Private fields
(`vendor_volume_id`, `backend`, `protocol`, `hub`, `vendor_context`) never
reach the browser.

#### Technology Stack

| Layer | Technology | Notes |
|---|---|---|
| UI framework | React 19 + PatternFly 6 | Existing stack |
| Forms | Formik + Yup | Existing pattern (`OsacForm` wrapper, ESLint-enforced) |
| API client | `@connectrpc/connect-web` | Connect JSON transport via `useApiFetch` |
| Server state | TanStack Query 5 | `useApiQuery` for reads, `useMutation` for writes |
| Types | `@osac/types` (generated) | `pnpm gen-types` after public volume proto is available |
| i18n | i18next | English text as key, `useTranslation` from `@osac/ui-components` |

### 4.2 Routing

New routes under the tenant navigation:

| Path | Component | Purpose |
|---|---|---|
| `/storage/volumes` | `VolumesListPage` | Volume list with table, toolbar, pagination |
| `/storage/volumes/create` | `VolumeWizardPage` | Create volume wizard |
| `/storage/volumes/:id` | `VolumeDetailsPage` | Volume details with column-layout sections |

Route file (`VolumeRoutes.tsx`):

```tsx
export const VolumeRoutes = () => (
  <Routes>
    <Route index element={<VolumesListPage />} />
    <Route path="create" element={<VolumeWizardPage />} />
    <Route path=":id" element={<VolumeDetailsPage />} />
  </Routes>
);
```

The sidebar navigation adds a "Volumes" entry under a "Storage" section in
the tenant navigation, following the pattern used by Compute and Networking.

### 4.3 Volume List Page

The volume list page extends the OSAC-4542 read-only list with CUD
capabilities.

#### Toolbar

| Element | Behavior |
|---|---|
| **"Create volume" button** | Primary button, navigates to `/storage/volumes/create` |
| **Filter/search** | CEL-based filter on name, state, storage_tier (existing pattern) |
| **Pagination** | Standard offset/limit pagination (existing `ListParams` pattern) |

#### Table Columns

| Column | Source Field | Sortable | Notes |
|---|---|---|---|
| Name | `metadata.name` | Yes | Link to details page |
| Status | `status.state` | Yes | `VolumeStatusLabel` component |
| Storage Tier | `spec.storage_tier` | Yes | Tier name as text |
| Size | `spec.size_gib` | Yes | Formatted as "{n} GiB" |
| Access Mode | `spec.access_mode` | No | Human-readable label (see mapping below) |
| Created | `metadata.creation_timestamp` | Yes | Relative time ("3 hours ago") with tooltip showing absolute time |
| Actions | — | No | Kebab menu (`VolumeActionsMenu`) |

#### Access Mode Display Labels

| Enum Value | Display Label |
|---|---|
| `VolumeAccessMode.VOLUME_ACCESS_MODE_READ_WRITE_ONCE` | ReadWriteOnce |
| `VolumeAccessMode.VOLUME_ACCESS_MODE_READ_ONLY_MANY` | ReadOnlyMany |
| `VolumeAccessMode.VOLUME_ACCESS_MODE_READ_WRITE_MANY` | ReadWriteMany |
| `VolumeAccessMode.VOLUME_ACCESS_MODE_READ_WRITE_ONCE_POD` | ReadWriteOncePod |

These labels match the Kubernetes PersistentVolume access mode names that
cloud-native users expect.

#### Row Actions (Kebab Menu)

| Action | Available States | Disabled States | Behavior |
|---|---|---|---|
| **Delete** | AVAILABLE, FAILED | CREATING, DELETING, DELETED | Open `VolumeDeleteConfirmModal` |

Actions in disabled states are hidden from the kebab menu, not shown as
greyed-out items — this follows the OSAC convention of only displaying
actions that are currently valid.

#### Empty State

When no volumes exist, display a centered empty state:

- **Icon:** Storage/database icon
- **Heading:** "No volumes"
- **Description:** "Create a volume to prepare storage independently from
  compute resources."
- **Action:** Primary "Create volume" button

### 4.4 Create Volume Wizard

A multi-step wizard following the agreed-upon resource creation pattern
used by `ExternalIpPoolWizard` in osac-ui. All new resources should adopt
this 3-step wizard structure: **General → Configuration → Review**.

The wizard uses PatternFly's `Wizard` and `WizardStep` components, wrapped
in a `Formik` provider with `FieldValidationProvider`. Navigation is
handled by `OSACWizardFooter` (shared component from
`libs/ui-components/src/components/Wizard/`). Each step is a separate
component file (`GeneralStep`, `ConfigurationStep`, `ReviewStep`) for
maintainability.

#### Wizard Steps

**Step 1 — General**

Identity and ownership fields common to all resource types.

| Field | Component | Required | Notes |
|---|---|---|---|
| Project | `ProjectSelectField` | Yes | Selects the tenant project scope for the resource. |
| Name | `NameField` | Yes | DNS label: `^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$`. Cannot be changed after creation. |
| Description | `InputField` (textarea) | No | Free-text description. |
| Labels | _(future)_ | No | Key-value labels. Placeholder for future implementation. |

**Step 2 — Configuration**

Volume-specific specification fields.

| Field | Component | Required | Notes |
|---|---|---|---|
| Storage tier | `StorageTierSelectField` | Yes | Fetches active tiers via public API, filtered to `STORAGE_PROTOCOL_BLOCK` tiers only (NFS creation is a non-goal). |
| Size (GiB) | `InputField` (type="number") | Yes | Must be > 0. Cannot be changed after creation. |
| Access mode | `RadioButtonField` | Yes | 4 options (see Access Mode Display Labels in section 4.3). |

**Step 3 — Review**

Read-only summary of all selections before submission.

| Section | Displayed Fields |
|---|---|
| General | Project, Name, Description |
| Configuration | Storage tier, Size, Access mode |

The Review step presents all entered values in a read-only summary so
the user can verify before submitting. A "Back" button allows returning
to previous steps to make corrections.

#### Page Layout

```text
┌──────────────────────────────────────────────────────────┐
│ Breadcrumb: Storage > Volumes > Create                   │
│                                                          │
│ Title: Create volume                                     │
│                                                          │
│ ┌─────────────────────────────────────────────────────┐  │
│ │  (1) General    (2) Configuration    (3) Review     │  │
│ └─────────────────────────────────────────────────────┘  │
│                                                          │
│ Step 1 — General:                                        │
│ ┌──────────────────────────────────────────────────────┐ │
│ │ Project *                                            │ │
│ │ ┌──────────────────────────────────────────────────┐ │ │
│ │ │ Select project                               ▼   │ │ │
│ │ └──────────────────────────────────────────────────┘ │ │
│ │                                                      │ │
│ │ Name *                                               │ │
│ │ ┌──────────────────────────────────────────────────┐ │ │
│ │ │ my-volume-name                                   │ │ │
│ │ └──────────────────────────────────────────────────┘ │ │
│ │ Helper: Lowercase letters, digits, and hyphens.      │ │
│ │         Max 63 characters. Cannot be changed later.  │ │
│ │                                                      │ │
│ │ Description                                          │ │
│ │ ┌──────────────────────────────────────────────────┐ │ │
│ │ │                                                  │ │ │
│ │ └──────────────────────────────────────────────────┘ │ │
│ └──────────────────────────────────────────────────────┘ │
│                                                          │
│ Step 2 — Configuration:                                  │
│ ┌──────────────────────────────────────────────────────┐ │
│ │ Storage tier *                                       │ │
│ │ ┌──────────────────────────────────────────────────┐ │ │
│ │ │ Select a storage tier                        ▼   │ │ │
│ │ └──────────────────────────────────────────────────┘ │ │
│ │                                                      │ │
│ │ Size (GiB) *                                         │ │
│ │ ┌──────────────────────────────────────────────────┐ │ │
│ │ │ 100                                              │ │ │
│ │ └──────────────────────────────────────────────────┘ │ │
│ │ Helper: Must be greater than zero.                   │ │
│ │         Cannot be changed after creation.            │ │
│ │                                                      │ │
│ │ Access mode *                                        │ │
│ │ ○ ReadWriteOnce     ○ ReadOnlyMany                   │ │
│ │ ○ ReadWriteMany     ○ ReadWriteOncePod               │ │
│ └──────────────────────────────────────────────────────┘ │
│                                                          │
│ Step 3 — Review:                                         │
│ ┌──────────────────────────────────────────────────────┐ │
│ │ General                                              │ │
│ │   Project:      analytics-prod                       │ │
│ │   Name:         my-volume-name                       │ │
│ │   Description:  Primary data store                   │ │
│ │                                                      │ │
│ │ Configuration                                        │ │
│ │   Storage tier: standard-block                       │ │
│ │   Size:         100 GiB                              │ │
│ │   Access mode:  ReadWriteOnce                        │ │
│ └──────────────────────────────────────────────────────┘ │
│                                                          │
│ [!] Inline danger alert (shown on API error)             │
│                                                          │
│ [ Back ]  [ Create ]  Cancel                             │
└──────────────────────────────────────────────────────────┘
```

#### Form Fields (All Steps)

**Step 1 — General:**

| Field | Component | Yup Schema | Required | Notes |
|---|---|---|---|---|
| Project | `ProjectSelectField` | `Yup.string().required()` | Yes | Tenant project scope for the resource. |
| Name | `NameField` | `resourceNameSchema(t)` | Yes | DNS label: `^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$`. Cannot be changed after creation. |
| Description | `InputField` (textarea) | `Yup.string()` | No | Free-text description. |

**Step 2 — Configuration:**

| Field | Component | Yup Schema | Required | Notes |
|---|---|---|---|---|
| Storage tier | `StorageTierSelectField` | `Yup.string().required()` | Yes | Fetches active tiers via public API, filtered to `STORAGE_PROTOCOL_BLOCK` tiers only (NFS creation is a non-goal). |
| Size (GiB) | `InputField` (type="number") | `positiveIntegerSchema(t)` | Yes | Must be > 0. Cannot be changed after creation. |
| Access mode | `RadioButtonField` | `Yup.string().oneOf([...]).required()` | Yes | 4 options. Cannot be changed after creation. |

#### Submission

The wizard is create-only — there is no standalone edit page. After
creation, the only mutable field (`description`) is edited inline on
the details page (section 4.5) using the generic `useUpdateResource`
hook. This avoids a separate edit form where most fields would be
disabled.

- Title: "Create volume"
- Submit button: "Create" (on the Review step, via `OSACWizardFooter`)
- On success: navigate to `/storage/volumes/:id` (details page)

#### Validation

Client-side validation (Formik + Yup) fires on blur and on submit:

```typescript
const getVolumeSchema = (t: TFunction) =>
  Yup.object({
    metadata: Yup.object({ name: resourceNameSchema(t) }),
    description: Yup.string(),
    storageTier: Yup.string().required(t('Storage tier is required')),
    sizeGib: positiveIntegerSchema(t).required(t('Size is required')),
    accessMode: Yup.string()
      .oneOf(
        [
          VolumeAccessMode.VOLUME_ACCESS_MODE_READ_WRITE_ONCE,
          VolumeAccessMode.VOLUME_ACCESS_MODE_READ_ONLY_MANY,
          VolumeAccessMode.VOLUME_ACCESS_MODE_READ_WRITE_MANY,
          VolumeAccessMode.VOLUME_ACCESS_MODE_READ_WRITE_ONCE_POD,
        ],
        t('Access mode is required'),
      )
      .required(t('Access mode is required')),
  });
```

#### Form-to-Resource Mapping

On submit, a `toCreateRequest` mapper converts Formik values to the
create request shape, following the pattern used by
`ExternalIpPoolWizard`:

```typescript
const toCreateRequest = (values: VolumeFormValues) => ({
  object: {
    metadata: {
      name: values.metadata.name,
      description: values.description || undefined,
    },
    spec: {
      storageTier: values.storageTier,
      sizeGib: values.sizeGib,
      accessMode: values.accessMode as VolumeAccessMode,
    },
  },
});
```

Server-side errors (API responses) are caught and displayed via the
`OSACWizardFooter`'s error prop (matching the ExternalIPPools pattern),
using `getErrorMessage(error)` to extract human-readable text from the
gRPC error.

#### Form Behavior

- **`LeaveFormConfirmation`** — included to prompt the user when navigating
  away with unsaved changes (same as ExternalIPPools wizard).
- **Submit loading state** — the `OSACWizardFooter` manages loading and
  disabled states during submission.
- **Cancel** — handled by the `OSACWizardFooter`, navigates back to the
  volume list.

### 4.5 Volume Details Page

Displays a single volume's full information using a column layout
**without cards**, following the `ExternalIpPoolDetailsPage` pattern
from osac-ui. The page is split into two components:

- **`VolumeDetailsPage`** — shell component that uses `ResourceDetailsPage`
  and `ResourceDetailHeader` (shared components), handles loading/error
  states, and renders the Delete button.
- **`VolumeDetailsPageContent`** — renders the column-based detail
  sections using PatternFly `Grid`/`GridItem` with `DescriptionList`.

#### Page Layout

The details content uses a 3-column `Grid` layout (`GridItem md={4}`),
matching the ExternalIPPools details page. Each column contains a
`Title headingLevel="h2"` section header followed by a compact
`DescriptionList`. No `Card` wrappers are used.

```text
┌──────────────────────────────────────────────────────────┐
│ Breadcrumb: Storage > Volumes > {name}                   │
│                                                          │
│ ResourceDetailHeader                                     │
│ Name: {metadata.name}                        [Delete]    │
│ Description: {metadata.description} [pencil]             │
│ ─────────────────────────────────────────────────────────│
│                                                          │
│  Overview              Configuration          Status     │
│  ─────────             ─────────────          ──────     │
│  Project  analytics..  Storage Tier  std-blk  State  OK  │
│  Status   Available    Size          100 GiB  Message —  │
│  Created  3 hours ago  Access Mode   RWO                 │
│  ID       abc-123...                                     │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

#### Header Action Buttons

| Button | Variant | Visible When | Behavior |
|---|---|---|---|
| **Delete** | Danger | AVAILABLE, FAILED | Open `VolumeDeleteConfirmModal` |

The Delete button is hidden (not disabled) in states where the action is
invalid (`CREATING`, `DELETING`, `DELETED`).

#### Failed State Message

When a volume is in FAILED state, the `status.message` field (set by the
backend reconciler) is displayed in an inline danger alert at the top of
the details page, below the header:

```text
Warning: Volume provisioning failed
  Backend reported: <status.message content>
```

This gives the user an actionable error message. The volume can still be
deleted from this state.

#### Inline Description Editing

The details page supports inline editing for `description` using
PatternFly's field-specific inline edit pattern:

- A pencil icon appears beside the description in the header area.
- Clicking the icon switches that field to edit mode (text input appears).
- Check icon saves; close icon cancels.
- The save action calls the Update API via `useUpdateResource(Volumes)`
  (the generic hook automatically computes `update_mask` paths from the
  request object).
- On success, TanStack Query cache is invalidated to refresh the display.

The pencil icon is **hidden** when the volume is in `DELETING` or
`DELETED` state. When the volume is in `CREATING` state, description
editing remains available (the PRD explicitly allows metadata updates
during creation).

#### Detail Columns

| Column | Section Title | Fields |
|---|---|---|
| Left (`GridItem md={4}`) | Overview | Project, Status (`VolumeStatusLabel`), Created (`Timestamp`), ID |
| Center (`GridItem md={4}`) | Configuration | Storage Tier, Size (formatted as "{n} GiB"), Access Mode |
| Right (`GridItem md={4}`) | Status | State, Message (shown only when set) |

### 4.6 Volume Status Label

A new `VolumeStatusLabel` component maps `VolumeState` enum values to the
existing `ResourceStatusLabel`. The lookup normalizes `undefined` to
`VOLUME_STATE_UNSPECIFIED` so that volumes with an absent `state` field
safely render the "Unspecified" label instead of crashing:

```typescript
const VOLUME_STATUS_MAP: Record<VolumeState, { status: StatusKind; text: string }> = {
  [VolumeState.VOLUME_STATE_UNSPECIFIED]: { status: 'unspecified',  text: 'Unspecified'  },
  [VolumeState.VOLUME_STATE_CREATING]:    { status: 'progressing',  text: 'Creating' },
  [VolumeState.VOLUME_STATE_AVAILABLE]:   { status: 'ready',        text: 'Available'},
  [VolumeState.VOLUME_STATE_FAILED]:      { status: 'failed',       text: 'Failed'   },
  [VolumeState.VOLUME_STATE_DELETING]:    { status: 'progressing',  text: 'Deleting' },
  [VolumeState.VOLUME_STATE_DELETED]:     { status: 'unspecified',  text: 'Deleted'  },
};

const VolumeStatusLabel = ({ state }: { state?: VolumeState }) => {
  const resolved = state ?? VolumeState.VOLUME_STATE_UNSPECIFIED;
  const { status, text } = VOLUME_STATUS_MAP[resolved];
  return <ResourceStatusLabel status={status} text={text} />;
};
```

| State | Color | Icon |
|---|---|---|
| Creating | Blue | InProgressIcon |
| Available | Green | CheckCircleIcon |
| Failed | Red | ExclamationCircleIcon |
| Deleting | Blue | InProgressIcon |
| Deleted | Grey | QuestionCircleIcon |
| Unspecified | Grey | QuestionCircleIcon |

### 4.7 Delete Confirmation

Uses the existing `DeleteResourceModal`:

```tsx
import { Volumes } from '@osac/types/public';
import { useDeleteResource } from '../../api/use-resource';

const VolumeDeleteConfirmModal = ({ volume, onClose, onSuccess }) => {
  const { t } = useTranslation();
  const deleteVolume = useDeleteResource(Volumes);
  const volumeName = volume.metadata?.name ?? volume.id;

  return (
    <DeleteResourceModal
      resourceName={volumeName}
      label={t(
        'This permanently deletes the volume and all of its data. This action cannot be undone.',
      )}
      errorLabel={t('Failed to delete volume')}
      onClose={onClose}
      onSuccess={onSuccess}
      mutation={deleteVolume}
      variables={{ id: volume.id }}
    />
  );
};
```

**Delete behavior by state:**

| Current State | Delete Action | Result |
|---|---|---|
| AVAILABLE | Delete button visible | Modal opens; API sets state to DELETING |
| FAILED | Delete button visible | Modal opens; API sets state to DELETING |
| CREATING | Delete button hidden | User must wait for creation to complete or fail |
| DELETING | Delete button hidden | Deletion already in progress |
| DELETED | Not visible (archived) | Volume not shown in list |

**Post-delete navigation:** On successful delete, navigate back to the
volume list. An inline success alert ("Volume deleted") is shown briefly on
the list page.

**Idempotent delete:** If the user manages to trigger delete for a volume
that is already in DELETING state (race condition), the API returns success
(idempotent). No error is shown.

### 4.8 API Hooks

The volume UI uses the **generic resource hooks** from
`libs/ui-components/src/api/use-resource.ts` rather than defining
custom per-resource hooks. This follows the pattern established by
ExternalIPPools and other resources in osac-ui.

```typescript
import { Volumes } from '@osac/types/public';
import {
  useListResource,
  useGetResource,
  useCreateResource,
  useUpdateResource,
  useDeleteResource,
} from '../../api/use-resource';
```

#### Hook Usage by Component

| Component | Hook | Purpose |
|---|---|---|
| `VolumesListPage` | `useListResource(Volumes, params)` | List volumes with pagination |
| `VolumeDetailsPage` | `useGetResource(Volumes, { id })` | Fetch single volume |
| `VolumeWizard` | `useCreateResource(Volumes)` | Create volume on wizard submit |
| `VolumeDetailsPage` (inline edit) | `useUpdateResource(Volumes)` | Update description |
| `VolumeDeleteConfirmModal` | `useDeleteResource(Volumes)` | Delete volume |

The generic hooks handle cache invalidation automatically — on
successful create, update, or delete, all queries keyed by the
service's `typeName` are invalidated. The `useUpdateResource` hook
automatically computes `update_mask` paths from the request object
via `buildUpdateMaskPaths`.

#### DELETED-Volume Exclusion

The `Volumes.list` API is expected to omit volumes in `DELETED` state.
As a defensive measure, the list page component filters out any
`DELETED` volumes that may appear during the brief window between a
successful delete RPC and the next list refresh.

**Prerequisites:** The `Volumes` service descriptor must be exported from
`@osac/types`. This requires running `pnpm gen-types` after the public
volume proto files are included in the UI's protobuf source.

### 4.9 Error Handling

#### gRPC Error Code to UI Message Mapping

| gRPC Code | Backend Message (example) | Alert Title | Alert Variant |
|---|---|---|---|
| `InvalidArgument` | "field 'metadata.name' is required" | "Failed to create volume" | danger |
| `AlreadyExists` | "volume with name 'x' already exists in tenant 'y'" | "Failed to create volume" | danger |
| `NotFound` | standard not-found | "Volume not found" | danger |
| `FailedPrecondition` | "volume in state 'DELETING' cannot be updated" | "Failed to update description" | danger |
| `Aborted` | "optimistic lock failure: version mismatch" | "This volume was modified" (see below) | warning |
| `Unauthenticated` | — | Redirects to login (handled by `connectErrorInterceptor`) | — |
| `PermissionDenied` | — | "You do not have permission to perform this action" | danger |
| `Internal` | "failed to process volume" | "An unexpected error occurred" | danger |

#### Optimistic Locking Conflict (Aborted)

When the update API returns `Aborted` (version mismatch), the UI shows a
distinct warning alert (not danger) with a refresh action:

```text
Warning: This volume was modified
  Another user or process updated this volume while you were editing.
  [ Refresh and retry ]
```

The "Refresh and retry" action:
1. Invalidates the TanStack Query cache for the volume.
2. Re-fetches the volume from the API.
3. Resets the inline edit field with the fresh value.
4. The user can then re-apply their change and save again.

### 4.10 Security Considerations

- **No private fields reach the browser.** The public API and its outMapper
  strip `vendor_volume_id`, `backend`, `protocol`, `hub`, and
  `vendor_context` before the response leaves the fulfillment service.
- **Status field is read-only.** The inMapper on the server ignores
  client-set status fields. The create form does not include status inputs.
- **Tenant isolation is server-enforced.** The UI does not implement
  tenant-scoping logic — the API handles it via gRPC interceptors.
- **Input validation is defense-in-depth.** Client-side Yup validation
  catches common errors before the API call. Server-side validation is
  authoritative.

### 4.11 Failure Handling and Recovery

| Scenario | UI Behavior |
|---|---|
| **Create fails (invalid input)** | Inline danger alert with backend error message. Form remains populated — user corrects and retries. |
| **Create fails (duplicate name)** | Inline danger alert: "volume with name 'x' already exists...". User chooses a different name. |
| **Create fails (NFS tier selected)** | Inline danger alert with protocol-specific message from backend. User selects a block-protocol tier. |
| **Create fails (network/server error)** | Inline danger alert: "An unexpected error occurred". User retries. |
| **Create succeeds, volume stays CREATING** | Status label shows blue "Creating". UI refreshes state on default intervals. |
| **Create succeeds, volume moves to FAILED** | Details page shows red "Failed" status with `status.message` in danger alert. Delete remains available. |
| **Inline description update fails (version conflict)** | Warning alert: "This volume was modified". User clicks "Refresh and retry". |
| **Delete fails (not found)** | Modal shows inline danger alert: "Volume not found". User closes modal; list refreshes. |
| **Delete fails (server error)** | Modal shows inline danger alert: "Failed to delete volume" with error detail. User can retry or close. |
| **API unreachable** | TanStack Query shows loading state, then error after timeout. `QueryErrorState` component renders. |

### 4.12 RBAC / Tenancy

The UI does not implement authorization checks. All authorization is
enforced by the API's OPA layer. The UI renders actions (Create, Delete)
for all authenticated users and handles `PermissionDenied`
responses by displaying an appropriate error message.

## 5. Accessibility

### WCAG 2.1 AA Compliance

| Concern | Implementation |
|---|---|
| **Required fields (SC 1.3.1)** | All required fields use `required` attribute AND visible asterisk (*) with legend |
| **Error identification (SC 3.3.1)** | Formik validation messages appear as helper text below the field, not color-alone. `aria-describedby` links field to error. |
| **Error suggestion (SC 3.3.3)** | Yup messages are actionable: "Name must only contain lowercase letters, digits, and hyphens" not "Invalid name" |
| **Status messages (SC 4.1.3)** | Volume state transitions announced via `role="status"` live region. API errors use PatternFly `Alert` (implicit `role="alert"`). |
| **Focus management (SC 2.4.3)** | After form submission with errors, focus moves to first error field. After modal close, focus returns to trigger element. |
| **Delete confirmation (SC 3.2.2)** | PatternFly `Modal` provides `role="dialog"`, `aria-modal="true"`, focus trapping, and Escape key dismissal. |
| **Keyboard navigation** | All actions reachable via keyboard. Tab order follows visual order. Kebab menu opens with Enter/Space. |

### Screen Reader Announcements

- **Volume created:** Page title change is announced by the router.
- **Volume deleted:** Inline success alert announced via `role="alert"`.
- **State transition:** Status label update announced via `role="status"` live region.

## 6. Impact and Compatibility

### New Dependencies

- **`@osac/types` update:** Public volume types must be generated (`pnpm gen-types`).

### No Breaking Changes

- Existing admin storage management UI unaffected.
- No changes to the Go proxy, backend API, or shared components.

### Navigation Changes

- "Volumes" link added to tenant sidebar under a "Storage" section.

## 7. Test Plan

### Requirement Traceability

| PRD Requirement | Test Cases | Type |
|---|---|---|
| Create volume through console | TC-UI-C1, TC-UI-C2, TC-UI-C3 | Unit, Playwright |
| Update volume description (inline edit) | TC-UI-U1, TC-UI-U2 | Unit |
| Delete volume through console | TC-UI-D1, TC-UI-D2 | Unit |
| Show lifecycle status | TC-UI-S1, TC-UI-S2, TC-UI-S3 | Unit |
| Actionable error display | TC-UI-E1, TC-UI-E2, TC-UI-E3, TC-UI-E4 | Unit |
| Same states/behavior as API and CLI | TC-UI-S1, TC-UI-S2, TC-UI-E1-E4 | Unit |
| Tenant-scoped permissions | TC-UI-A1 | Unit |
| DELETED volumes excluded from list | TC-UI-L1 | Unit |

### Unit Tests (Vitest + React Testing Library)

**VolumeWizard (create):**
- TC-UI-C1: Renders all wizard steps; submitting with empty fields shows validation errors per step.
- TC-UI-C2: Successful creation calls `useCreateResource(Volumes)` with correct payload and navigates to details.
- TC-UI-C3: API error displays in wizard footer.

**VolumeDetailsPage (inline description edit):**
- TC-UI-U1: Inline description edit calls `useUpdateResource(Volumes)` with correct payload; cache refreshes on success.
- TC-UI-U2: Version conflict shows warning alert with "Refresh and retry".

**VolumeDeleteConfirmModal:**
- TC-UI-D1: Renders modal; Delete calls API and closes on success.
- TC-UI-D2: API error shows inline danger alert within modal.

**VolumeStatusLabel:**
- TC-UI-S1: Each VolumeState renders correct color and text.
- TC-UI-S2: `VOLUME_STATE_UNSPECIFIED` renders grey "Unspecified".
- TC-UI-S3: When `state` prop is `undefined` (absent from API response), the component renders grey "Unspecified" (normalizes to `VOLUME_STATE_UNSPECIFIED`).

**Error display:**
- TC-UI-E1: InvalidArgument shows "Failed to create volume".
- TC-UI-E2: AlreadyExists shows duplicate name message.
- TC-UI-E3: FailedPrecondition shows state-specific message.
- TC-UI-E4: Aborted shows warning variant with refresh action.

**VolumesListPage (list filtering):**
- TC-UI-L1: When the API response includes a volume with `VOLUME_STATE_DELETED`, the component filters it out of the displayed list.

**VolumeActionsMenu:**
- TC-UI-A1: Actions hidden based on volume state.

### Manual Verification (Playwright)

Using `apps/playwright/scratch/` against a live cluster:
- Create volume via wizard; verify "Creating" transitions to "Available".
- Edit description inline on details page; verify change persists.
- Delete volume; verify it disappears from list.
- Duplicate name; verify error message in wizard.

## 8. Task Decomposition

### Epic Summary

| # | Epic | Size | Stories | Depends On |
|---|---|---|---|---|
| 1 | Volume API Layer & Shared Components | M | 3 | — |
| 2 | Create Volume Wizard | M | 3 | Epic 1 |
| 3 | Volume Details Page | S | 2 | Epics 1, 2 |
| 4 | Volume Deletion | S | 2 | Epics 1, 3 |

**Total: 4 epics, 10 stories (8 [DEV], 1 [QE], 1 [DOCS])**

### Epic 1: Volume API Layer & Shared Components (M)

Foundation: typed API hooks, VolumeStatusLabel, VolumeActionsMenu, list
page, routing, and navigation.

| # | Title | Prefix | Size |
|---|---|---|---|
| 1 | Register public Volume types and API hooks | [DEV] | M |
| 2 | Add VolumeStatusLabel, VolumeActionsMenu, and list page | [DEV] | L |
| 3 | Add volume routing and sidebar navigation | [DEV] | S |

### Epic 2: Create Volume Wizard (M)

Multi-step wizard (General → Configuration → Review) with Formik + Yup,
error handling, and e2e test coverage.

| # | Title | Prefix | Size |
|---|---|---|---|
| 1 | Implement VolumeWizard with 3-step wizard and Formik + Yup validation | [DEV] | L |
| 2 | Add create volume error handling and edge cases | [DEV] | M |
| 3 | Volume create and delete e2e scenarios | [QE] | M |

### Epic 3: Volume Details Page (S)

Details page with column layout (no cards), inline description editing,
and optimistic locking.

| # | Title | Prefix | Size |
|---|---|---|---|
| 1 | Implement VolumeDetailsPage with column layout and inline description edit | [DEV] | L |
| 2 | Add optimistic locking conflict handling for inline edits | [DEV] | S |

### Epic 4: Volume Deletion (S)

Delete confirmation modal and user documentation.

| # | Title | Prefix | Size |
|---|---|---|---|
| 1 | Implement VolumeDeleteConfirmModal and deletion flow | [DEV] | S |
| 2 | Document volume management console workflows | [DOCS] | S |

### PRD Requirement Coverage

All PRD requirements are covered by at least one implementing story and
one validating test case. See the full coverage matrix in the design
artifacts for detailed requirement-to-story-to-test mapping.
