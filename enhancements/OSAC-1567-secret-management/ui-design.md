---
title: secret-management-ui
authors:
  - rawagner@redhat.com
creation-date: 2026-09-07
last-updated: 2026-09-07
tracking-link:
  - https://redhat.atlassian.net/browse/OSAC-1567
prd:
  - prd.md
see-also:
  - design.md
  - https://redhat.atlassian.net/browse/OSAC-1330
replaces:
  - N/A
superseded-by:
  - N/A
---

# Secret Management UI

## Summary

This design adds tenant-facing Secret management to `osac-ui`. Tenant Users
and Tenant Admins can create, browse, inspect, update, retrieve, and delete
secrets through a single console surface. Resource forms that accept Secret
references use the same surface to select an existing Secret without copying
credential values into the parent resource.

The UI treats Secret data as sensitive at every boundary:

- List responses are rendered as metadata only.
- Secret values are never fetched by the list page. The detail page explicitly
  calls `Get`; because the current API returns metadata and values together,
  opening a Secret is also the retrieval action. The UI masks values
  immediately after the response arrives.
- Values are masked by default and require an explicit reveal or download
  action.
- Backend and storage coordinates are never shown or sent by the public UI.

This document is the UI companion to the Secret Management PRD and backend
design. It does not define the Secret API, storage backend, tenant isolation,
or migration behavior; those remain specified in [design.md](design.md).

## Motivation

The current console has no complete Secret workflow. Users who need a pull
secret, SSH key, OIDC credential, cloud-init credential, or another opaque
credential must either use the API/CLI or enter sensitive data directly into
the resource workflow. That makes credential reuse, safe review, and manual
replacement difficult.

The backend design provides one public `Secrets` CRUD API with opaque
key-value data and a metadata-only list response. The UI can therefore offer a
consistent experience for both user-created Vault-backed Secrets and
system-created Secrets such as cluster kubeconfigs, without exposing which
backend stores the data.

## Goals

- Provide a role-appropriate Secret list and management experience for Tenant
  Users and Tenant Admins.
- Support create, metadata view, value retrieval, update, and delete operations
  for user-managed Secrets.
- Make system-created Secrets discoverable and retrievable while preventing
  users from editing or deleting them once the public API exposes their
  managed/read-only capability. The current public API does not expose that
  capability; this design treats it as an API dependency rather than
  inferring it in the UI.
- Make Secret references first-class inputs in resource forms, beginning with
  the credential fields named in the PRD.
- Keep secret values out of list rows, search results, notifications, browser
  URLs, analytics payloads, and client-side debug output.
- Match the existing PatternFly, routing, API-hook, form, i18n, and
  accessibility conventions in `osac-ui`.

## Non-goals

- Automated rotation, expiry reminders, or scheduled replacement.
- Secret-store configuration, Vault administration, or provider-admin setup.
- Editing the contents of system-managed Hub Secrets.
- A visual editor that understands the format of arbitrary values such as
  Docker configuration, certificates, or kubeconfigs. Secret data remains an
  opaque map of keys to bytes.
- Direct browser access to private API endpoints.
- Changing the existing resource-specific credential migration behavior.

## User experience

### Navigation and access

The existing **Secrets** navigation item remains available to authenticated
tenant users and tenant admins at `/secrets`. The route is visible according to
the same role-based navigation rules used by other tenant resources. A user
who can list no Secrets still sees the page and its empty state; API
authorization, not client-side role assumptions, is the source of truth.

The UI does not add a provider-admin Secret management workflow. Provider
admins may receive no tenant Secret data through the public UI unless a future
requirement explicitly defines that access.

### Secret list

The list page uses the existing `ListPage`, `ListPageBody`, PatternFly
`Toolbar`, `SearchInput`, and compact `Table` patterns already used by the
console.

The table displays:

| Column | Behavior |
| --- | --- |
| Name | Links to the Secret detail page. |
| Scope/project | Shows the Secret's visible project context when supplied by metadata. |
| Type | Shows the recommended `osac.openshift.io/secret-type` label when present; otherwise `Unspecified`. This is descriptive, not a server-enforced type. |
| Managed by | Shows `User managed` or `System managed` only if the public API exposes a capability or read-only field. The UI must not infer this from private backend fields. It never shows Vault, Hub, namespace, or coordinates. |
| Created | Shows the existing localized timestamp component. |
| Actions | Opens the action menu appropriate for the Secret's capabilities. |

The list query requests metadata only. Search filters server-side by supported
metadata fields, with the current name search retained as the first
interaction. Search text is reflected in the existing page-filter query
parameter so refresh and navigation preserve the filter.

The page provides distinct loading, error, filtered-empty, and unfiltered-empty
states. The unfiltered empty state contains a primary **Create Secret** action.

### Create Secret

Selecting **Create Secret** opens a PatternFly form at `/secrets/create`.

The form contains:

1. **Name** — required, validated using the same resource-name rules as other
   OSAC resources.
2. **Project** — shown when the active context permits more than one project;
   defaults to the current project and is not editable when the surrounding
   workflow fixes the project.
3. **Secret type** — an optional label convention selector. The value maps to
   `osac.openshift.io/secret-type`; it does not change the opaque data model.
4. **Data entries** — one or more rows, each with a required key and a value
   editor. The user can add and remove rows. Values are masked by default and
   may be entered as text or supplied through a file-selection affordance when
   supported by the browser and deployment.

The form must require at least one non-empty data key and value before submit.
The UI preserves bytes as bytes when constructing the protobuf request and
does not log, serialize into the URL, or include them in client-side error
text.

On success, the UI navigates to the new Secret's detail page and shows a
non-sensitive success notification. On failure, the form remains populated,
the error is announced accessibly, and the UI provides actionable handling for
validation, authorization, unavailable secret-store, and conflict errors.

### Secret detail and retrieval

The detail page is at `/secrets/:id`. It has a metadata section and a separate
**Secret data** section so that values are not visually prominent. The page
calls `Get` when it opens. The current API does not provide a metadata-only
`Get`: `List` omits `data`, while `Get` returns the Secret with its data. The
UI therefore treats navigation to the detail page as an explicit retrieval
action, masks the returned values immediately, and never prefetches detail
data from the list page.

Metadata includes name, project/scope, labels, creation and update timestamps,
and the managed/read-only state. Backend type, namespace, path, coordinates,
and other private fields are not rendered.

The Secret data section follows these rules:

- Data is loaded by the detail page's `Get` request, not by the list request.
  Under the current API, this request returns both metadata and data; the UI
  masks the returned values immediately and must not treat masking as
  prevention of data retrieval.
- Each key is shown without displaying its value initially.
- **Reveal** exposes one value at a time and **Hide** masks it again.
- **Copy** copies one value only after an explicit user action and provides a
  short, non-sensitive confirmation. The value is not placed in a toast,
  URL, or persistent application state beyond what the browser clipboard
  requires.
- **Download** is available when the workflow needs the complete credential
  (for example, a kubeconfig). The filename is derived from the Secret name,
  not from its value. The UI confirms the download without describing the
  contents.

The page does not render arbitrary bytes as UTF-8 unless the user explicitly
chooses a text-oriented view. Binary values remain downloadable or copyable as
appropriate to the API contract. A missing or malformed value is reported as
an error, not silently replaced with an empty string.

### Update Secret

User-managed Secrets expose **Edit** from the detail page and action menu.
The edit form loads metadata and values only after the user enters the edit
workflow. Existing values remain masked; the user may replace a value or
leave it unchanged. The form supports adding and removing keys and editing
labels that are part of the public metadata contract.

When the public API reports a Secret as system-managed/read-only, it does not
expose Edit. Until that capability is added, the UI cannot reliably hide Edit
for these objects; it must still handle a defensive `FAILED_PRECONDITION`
response if a stale page attempts the operation.

The update request uses the existing field-mask convention. A metadata-only
change must not send secret data, and a data change must not cause unrelated
metadata to be rewritten.

### Delete Secret

User-managed Secrets expose **Delete** through the detail page and action menu.
The existing confirmation modal pattern is used and names the Secret without
showing any values. The dialog explains that deletion is permanent and that
resources referring to the Secret may fail validation or provisioning after
the reference is removed.

When the public API reports a Secret as system-managed/read-only, it does not
expose Delete in the public UI. If deletion is rejected by the API, the UI
reports that the Secret is managed by the platform and cannot be deleted by the
tenant.

### Secret reference picker

Resource forms that accept a Secret reference use a shared
`SecretReferenceField` built on the existing resource-selector and form-field
patterns. The picker:

- lists only Secrets visible in the current project;
- renders API validation failures near the field and in the page-level alert.

The first reference integrations are the PRD fields below. The exact field
names may change with the type-safe resource-reference work tracked by
OSAC-1330, so the picker is shared while each resource page owns its field
mapping.

| Resource | UI field |
| --- | --- |
| Cluster and ClusterTemplate | Pull secret |
| IdentityProvider | Client secret; bind credential |
| Tenant | Break-glass credentials |

The picker must never offer an inline value editor and a Secret reference as
simultaneously required inputs. During any compatibility period in which both
API fields exist, the UI prefers the reference and clearly marks inline
credential entry as deprecated.

## Routes and components

The initial route structure is:

```text
/secrets                 SecretListPage
/secrets/create          SecretCreatePage
/secrets/:id             SecretDetailPage
/secrets/:id/edit        SecretEditPage
```

The page files remain composition and data-wiring layers. Reusable pieces are
extracted under `libs/ui-components/src/components/Secret/`:

- `SecretListPage` — list query, filtering, empty/error states, and actions.
- `SecretCreatePage` and `SecretEditPage` — Formik/Yup form wiring and
  mutation handling.
- `SecretDetailPage` — metadata, capabilities, retrieval, and actions.
- `SecretDataFields` — add/remove key rows and masked value controls.
- `SecretDataView` — masked/revealed values, copy, and download behavior.
- `SecretReferenceField` — reusable picker for resource forms.

Each React component is kept in its own file and uses default exports. API
hooks, field builders, validation utilities, and types use named exports.
PatternFly components and tokens are preferred over custom markup or inline
styles.

## API integration

The UI uses the generated public `osac.public.v1.Secrets` service through the
existing Connect transport and API abstraction:

- list: `Secrets.List`, returning metadata-only items;
- get: `Secrets.Get`, returning metadata and values together. The detail page
  calls it on open; the list page never calls it or prefetches it;
- create: `Secrets.Create`;
- update: `Secrets.Update` with a field mask; and
- delete: `Secrets.Delete`.

The browser never calls the private Secrets service. The public response must
become the source of truth for whether a Secret is editable or deletable. The
current public schema does not expose an operation capability: the private
server knows `backend = HUB`, but the public mapper strips `backend` and
`coordinates`. The UI must not infer managed state from labels such as
`osac.openshift.io/secret-type`, because those labels describe the credential
kind rather than its mutability. Until the public capability is added, the UI
must handle rejected mutations rather than pretend it can hide the actions
reliably.

Queries and mutations follow the repository's existing `useApiQuery`, API
query-key, invalidation, and Connect error-interceptor patterns. Successful
create/update/delete operations invalidate the list and relevant detail query
without retaining secret values in a longer-lived cache than the existing API
policy permits.

## Security and accessibility

- Never write secret bytes to logs, analytics, error boundaries, URLs, test
  snapshots, or translation keys.
- Use accessible labels for every value input and action. Reveal, hide, copy,
  and download controls must be keyboard reachable and expose their state to
  assistive technology.
- Use an assertive live region for failed retrieval, mutation, and download
  preparation; do not announce the value itself.
- Return focus to the invoking action after closing dialogs and preserve focus
  when adding or removing data rows.
- Ensure masked values are not treated as a security boundary: the UI must
  still rely on API authorization and must not prefetch inaccessible values.
- All user-facing strings use the existing `useTranslation` wrapper. The
  generated English translation catalog is updated through the repository's
  i18n command.

## Failure handling

The UI distinguishes the following externally observable cases:

| Condition | User-visible behavior |
| --- | --- |
| Invalid name, empty data, duplicate key, or invalid reference | Inline field errors; submission is blocked. |
| Secret not found or no longer visible | Detail/picker shows a not-found state and invalidates stale queries. |
| Unauthorized/forbidden | Show the standard authorization error and do not retry automatically. |
| Secret store unavailable | Preserve entered form data, show a retryable error, and avoid claiming that the Secret was created. |
| System-managed update/delete rejected | Explain that the Secret is managed by the platform and cannot be changed through this workflow. |
| Download or clipboard failure | Keep the value masked and provide a retryable, non-sensitive error. |

## Test strategy

Unit and component tests use Vitest and React Testing Library with the existing
in-memory Connect transport. Tests assert user-visible behavior rather than
implementation details and cover:

- list loading, populated, filtered-empty, unfiltered-empty, and error states;
- create validation, add/remove key rows, successful creation, and failed
  creation without losing entered data;
- metadata-only rendering of list rows;
- detail retrieval with masked values, per-key reveal/hide, copy, and download;
- edit field-mask behavior, including metadata-only updates and data updates;
- capability-based hiding and defensive handling of system-managed mutations;
- delete confirmation, successful deletion, cancellation, and rejected delete;
- Secret picker search, project scoping, clear, create-and-return, stale
  reference handling, loading, and error states; and
- keyboard navigation, focus restoration, accessible names, and live-region
  announcements for sensitive actions.

The existing manual Playwright harness may be used against a live deployment
to verify the complete flows with real authorization and a configured secret
backend. Such scratch scenarios are manual verification only and are not
persisted as feature coverage.

## Open questions

1. **Who owns capability exposure?** The public Secret schema currently
   describes data and metadata but does not expose whether a Secret is
   system-managed, editable, or deletable. The fulfillment-service/API owners
   must add a public read-only/managed capability (or an equivalent operation
   capability model) before the UI can reliably hide Edit and Delete for Hub
   Secrets. The UI must not inspect private `backend` fields.
2. **How should project selection be presented?** The UI needs confirmation
   of whether the active project context is mandatory for all Secret operations
   or whether Tenant Admins may create organization-scoped Secrets.
