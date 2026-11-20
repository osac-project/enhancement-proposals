# UI design — CaaS add-on operators (OSAC-4095)

- **Feature:** OSAC-4090, Operator Support for CaaS Catalog Items
- **Inputs:** [PRD](prd.md), [backend design](design.md), [UX PR #434](https://github.com/osac-project/enhancement-proposals/pull/434)

## Experience

| Persona | Console flow |
| --- | --- |
| Cloud Provider Admin | Review and publish operators; manage permitted shared or tenant catalog items; inspect operator outcomes across authorized clusters without lifecycle actions. |
| Tenant Admin | Attach operators to catalog items in their tenant, order clusters, and inspect outcomes in their tenant. |
| Tenant User | See included operators before ordering, choose permitted operators, and inspect installation status and errors on their clusters. |

A catalog item governs the **whole operator list** when it sets an operator policy. Locked lists show included operators as read-only cards and send no override. Editable lists preselect defaults; users can replace them or add compatible operators. If the item has no configured operators and is not explicitly locked, the picker starts empty and lets users choose operators. There is no per-operator mandatory mode. The shared picker auto-includes dependencies and explains version or exclusion conflicts. Fulfillment validates the final order. [PRD: In Scope and User Stories] [Design: Ordering a cluster with operators] [UX PR: sections 1–4 and editable-policy review]

Every cluster order starts with a catalog item in the existing wizard. Users choose operators at order time when its list is editable or unset, even if the item has no operator defaults. General and Review summarize those choices; invalid orders retain the draft and display `BadRequest.FieldViolation` beside the affected field. [PRD: direct selection and order-time validation] [Codebase: `Cluster/CreateWizard`]

After creation, cluster detail shows each requested operator between Networking and Conditions as Pending, Installing, Installed, or Failed, including the failure message. The cluster's Degraded condition appears separately. Operator cards use the available title, description, OpenShift compatibility range, dependencies, and exclusions. Historical status falls back to the stored operator name when display metadata cannot be resolved. [PRD: installation outcomes] [Design: ClusterStatus and feedback] [Codebase: `add_on_operator_type.proto`]

## Pages and components

Paths below are relative to `osac-ui/libs/ui-components/src/`. Extend existing PatternFly 6 pages and the Formik cluster wizard.

Add Add-on operators after Configuration in the existing cluster catalog wizard, which already covers version and node sets. Keep its General, Networking, and Review steps; catalog scope stays in General. The order wizard places Add-on operators after Networking and before Review. [UX PR: sections 1–4] [Codebase: `ClusterCatalogItemWizard.tsx`]

| Route or host | Components | Behavior |
| --- | --- | --- |
| `/admin/infrastructure/add-on-operators` | New `AddOnOperatorsPage` and `AddOnOperatorVisibilityDialog` | Provider inventory includes unpublished operators; a field-masked Update with an optimistic lock saves publication and supported scope. |
| `/catalog/cluster/create` and `/catalog/cluster/:id/edit` | Existing `CatalogItemCreatePage`, `CatalogItemEditPage`, and `ClusterCatalogItemWizard`; new `CatalogAddOnOperatorsStep` | Provider and Tenant Admins use the same wizard to create or edit permitted items; the new step uses the shared picker and whole-list locked/editable policy. |
| `/catalog` and `/catalog/:kind/:id` | Existing catalog pages plus `CatalogAddOnOperatorSummary` | Show the included/default operators before launch and role-appropriate edit actions. |
| `/clusters/create/:catalogItemId?` | Existing `ClusterCreateWizard` plus `ClusterAddOnOperatorsStep`, `ClusterOperatorSummary`, and shared `AddOnOperatorPicker`/`AddOnOperatorOption` | Choose a catalog item, select permitted operators even when it has no defaults, and review the payload. |
| `/clusters` and `/clusters/:clusterId` | Existing `ClustersPage`, `ListPage/ClustersTable`, and detail page plus `ClusterOperatorStatusCell` and `ClusterAddOnOperatorsCard` | Show scoped outcomes, failed names, and drilldown; provider view is read-only. |

Place the provider page under `pages/admin/`, the catalog step under `components/ClusterCatalogItem/CreateWizard/`, shared choice under `components/AddOnOperator/`, and status views under `components/Cluster/ListPage/` and `components/Cluster/Details/`. Reuse the current catalog routes in `AppShell` and the CaaS `ServiceRoute`; provider users cannot enter the order wizard by URL.

The shared picker accepts `operators`, `selectedIds`, `requiredDependencyIds`, `disabledReasons`, optional `readOnly`, and `onToggle(id)`. A pure `operatorSelection.ts` derives dependency closure and disabled reasons for the UI; the server remains authoritative. [Codebase: `AppShell.tsx`, `ClusterRoutes.tsx`, `Cluster/CreateWizard`, `Cluster/ListPage`] [UX PR: sections 1–5]

New views handle loading, empty/no-results, error, and retry states, and retain drafts on failure.
The picker labels choices, explains disabled reasons (`aria-describedby`), and announces dependencies.
Wizard errors focus the summary; dialogs restore focus; status combines text and icons and announces
only changes or failures. Use translated PatternFly controls and meet WCAG 2.1 AA. [Codebase: `osac-ui/AGENTS.md`]

## State and API

Formik owns each editor or wizard draft. TanStack Query owns server records; page search, pagination, and dialog state stay local or in existing URL parameters. No global store is needed. [Codebase: `api/use-api-query.ts` and existing Formik wizards]

`OperatorPage = { items: AddOnOperator[]; total: number }`. Extend the existing `ClusterCatalogItemValues` and payload builders with the operator list and policy. `VisibilityPatch` contains `published` and the tenant scope when that contract is available. New operator hooks follow `useApiFetch`, `useApiQuery`, and `useMutation`:

| Hook | RPC and effect |
| --- | --- |
| `useAddOnOperators(params?, enabled?): UseQueryResult<OperatorPage, unknown>` | Public `AddOnOperators.List`; cache published inventory by list params. |
| `useAdminAddOnOperators(params?): UseQueryResult<OperatorPage, unknown>` | Private `AddOnOperators.List`; separate cache for published and unpublished records. |
| `useUpdateAddOnOperatorVisibility(): UseMutationResult<AddOnOperator, unknown, VisibilityPatch>` | Private Update with field mask, `lock: true`, and `metadata.version`; invalidate operator and affected catalog queries. |

Extend the catalog wizard's existing create/update payloads with operator values while preserving its other field policies. Reuse the current cluster, version, project, and session hooks. For the scoped operator-status list, extend `useClusters` with `limit`/`offset` and a filtered total. Use generated `@osac/types`; refresh its API baseline through the generator when the operator contract requires it. [Codebase: `ClusterCatalogItemWizard.tsx`, `ClusterCreateWizard.tsx`, `api/v1/cluster.ts`, `libs/types/.buf-api-version`]

1. **Publish:** private operator List/Update provides `published` and `metadata.version`; public List/Get supplies offered titles, descriptions, compatibility, dependencies, and exclusions. Search the public list on the server across pages. `/api/login/info` and `Capabilities.Get` drive UI gates; SelfSubjectAccessReviews provides public-method hints. The backend decides access.
2. **Author catalog:** `ClusterCatalogItems.List/Get/Create/Update` reads and saves `fields.add_on_operators`. `Tenants.List` and `Projects.List` provide server-visible targets. Page or search choices rather than relying on the first page.
3. **Order:** `ClusterCatalogItems.List/Get`, `ClusterVersions.List/Get`, and hardware choices populate the wizard. `Clusters.Create` always sends `spec.catalog_item`; editable or unset operator lists send the user's `spec.add_on_operators[]` selection. Locked lists send no operator override.
4. **Inspect:** `Clusters.List/Get` supplies `spec.add_on_operators[]`, `status.add_on_operators[].name/state/message`, `status.conditions[]`, and `total`. Poll with the existing 10-second interval. Match status names to a spec reference only when the match is unique.

All list views use server-side paging and authorization. Filters that describe the whole result set must run before paging and counting. [Codebase: `clusters_server.go`, `cluster_catalog_item_policies.go`, `feedback_controller.go`]

## Verification

OSAC-4095 has no numbered Jira acceptance criteria. These cases cover the PRD's persona outcomes and the selected UX behavior. [PRD: User Stories] [Project: `docs/INTEGRATION-TESTING.md` planning evidence]

| Case | Owner and tier | Observable check |
| --- | --- | --- |
| Publication and scope | UI [DEV] Unit: new inventory/dialog tests; Fulfillment [DEV] component integration and IT: `add_on_operators_server_test.go` plus visibility/auth cases | Provider can publish; allowed tenants can discover and order; denied tenants cannot. Check group-only and role-only identities. |
| Catalog editing and preview | UI [DEV] Unit: extend `ClusterCatalogItemWizard` tests and add summary tests; Fulfillment [DEV] component integration and IT: catalog policy and scoped-write cases | Admins edit only permitted items; locked/editable policy survives save; users see included/default operators before launch. |
| Catalog orders and operator choices | UI [DEV] Unit: picker, `ClusterCreateWizard.test.tsx`, review; Fulfillment [DEV] component integration and IT: operator validation and `it_public_clusters_test.go`; [QE] E2E: CaaS regression | Every order uses a catalog item. Locked lists send no override; editable or unset lists allow choices, including when the item has no defaults. Dependencies resolve; unavailable or incompatible choices fail without creating a cluster; installation succeeds on a deployed cluster. |
| Outcomes | UI [DEV] Unit: cluster list/detail tests; Fulfillment [DEV] IT: scoped List/Get; [QE] E2E: CaaS regression | Pending, Installing, Installed, Failed, error message, Degraded, retry, and recovery display correctly across authorized clusters. |
| Accessibility | UI [DEV] Unit plus manual browser pass | Keyboard, labels, focus, announcements, and error recovery work across picker, dialog, wizard, list, and detail. |

UI unit tests run with `pnpm test` in `osac-ui/` against mock Connect transport. Fulfillment component tests run `go test ./internal/servers -timeout 20m` in `fulfillment-service/` with PostgreSQL; IT uses `make -C ../osac-installer test PLATFORM=kind PROFILE=dev NS=osac SUITE=fulfillment` for deployed Fulfillment and auth. The proposed QE suite is `tests/e2e/caas/regression/` with AAP and a CaaS provider; its owner, command, and retry bound still need assignment. During UI implementation also run `pnpm run typecheck` and `pnpm lint`. A manual browser pass is not persisted regression coverage.

## API prerequisites

Checked against OSAC upstream `main` at `e70a054` (2026-11-18). The UI uses
existing Connect RPCs.

- **Core:** `Clusters.Create` must distinguish an empty editable selection from
  omitted defaults (`shape-281469e0b39f`); operator visibility must cover
  discovery, catalog attachment, and orders (`field-4b10034f7620`); and Cloud
  Provider Admin publication and cross-tenant reads need correct grants
  (`permission-46ba3aec69fe`). Confirm PRD union versus backend replacement of
  catalog defaults.
- **Conditional:** Operator/failed-status filters and sortable lists need
  full-result server filtering (`filtering-5a6c733a5cca`) and ordering
  (`sorting-3680a3deac47`) if those controls ship. CaaS without BMaaS needs
  node-set hardware discovery (`data-ef5b91178d6e`) when the UI offers those
  choices.

---

## Provenance

Authored: plan @ ui-design 0.1.0 - b369da0, workspace main @ 91e852e8f
Final: revise @ ui-design 0.1.0 - 7653641, workspace design/cluster-details-vm-alignment @ 767aecb3b (dirty)

> Context changed between plan and revise.

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"ui-design","workflow_version":"0.1.0","ai_workflows":"7653641","source_repo":"767aecb3b (dirty)","source_repo_branch":"design/cluster-details-vm-alignment","commits_behind_main":0,"commits_ahead_main":233,"main_ref":"main","phases":["plan","review-api","revise","revise","revise","revise","revise","revise","revise","revise"],"authoring_modes":["skill"],"context_changed":true,"origin_untracked":false} -->
