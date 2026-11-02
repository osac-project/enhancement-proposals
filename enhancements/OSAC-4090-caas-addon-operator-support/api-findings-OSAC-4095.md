# API review evidence — OSAC-4095

This is the source-verified API review for the [UI design](ui-design-OSAC-4095.md). The main design summarizes its implementation blockers; this file keeps the endpoint mapping and gap evidence needed for backend follow-up.

## API Findings

- **Review date:** 2026-11-01
- **Source snapshot:** local OSAC `91e852e8f`, locally available `upstream/main` `a60651a8f`, UI generated API baseline `v0.0.131`
- **Endpoints verified:** 21 (20 Fulfillment RPCs and the UI proxy login endpoint)
- **Mappings confirmed:** 21 of 28 atomic data, operation, and supporting-capability needs
- **Gaps identified:** 7

Each routed operation is counted once even when several components use it. The seven unmet needs are the specific contract, query, permission, and deployment-profile capabilities in the gap table. HTTP paths below come from proto annotations; the browser calls their typed Connect RPCs through `/api/fulfillment`. This review checks source and tests, not a deployed browser session.

### Verified Endpoint Mappings

| UI element | Data needed | Endpoint | Response/request field | Verified |
| --- | --- | --- | --- | --- |
| Operator picker/cards | Published inventory, display and compatibility fields | `GET /api/fulfillment/v1/add_on_operators` | `items[].id/title/description/min_ocp_version/max_ocp_version/dependencies/exclusions`, `total` | Yes — public handler composes `this.published`. |
| Operator detail/fallback lookup | One published operator | `GET /api/fulfillment/v1/add_on_operators/{id}` | `object` with display and compatibility fields | Yes — unpublished returns NotFound. |
| Provider operator inventory | Published and unpublished records, update version | `GET /api/private/v1/add_on_operators` | `items[].published`, `items[].metadata.version`, `total` | Yes — private generic List. |
| Provider publication action | Update publication flag | `PATCH /api/private/v1/add_on_operators/{object.id}` | Request `object.published`, `update_mask`, `lock`; response `object` | Yes — private Update validates graph and references. |
| Catalog browse | Scoped items, published flag and policy summary | `GET /api/fulfillment/v1/cluster_catalog_items` | `items[].published/template/fields.add_on_operators/metadata`, `total` | Yes — visible unpublished items also appear. |
| Catalog detail/launch | One item's template, policy and scope | `GET /api/fulfillment/v1/cluster_catalog_items/{id}` | `object.template/fields.add_on_operators/metadata` | Yes — whole-list policy populated. |
| Catalog editor create | Save a scoped CaaS catalog item | `POST /api/fulfillment/v1/cluster_catalog_items` | Request/response `object.fields.add_on_operators` | Yes — public mapping and private validation. |
| Catalog editor update | Patch policy without replacing other fields | `PATCH /api/fulfillment/v1/cluster_catalog_items/{object.id}` | Request `object`, `update_mask`, `lock`; response `object` | Yes — optimistic lock requires `lock: true`. |
| Direct-template chooser | Available templates | `GET /api/fulfillment/v1/cluster_templates` | `items[].id/title/metadata`, `total` | Yes — public handler maps private items. |
| Direct-template details | Required parameters and defaults | `GET /api/fulfillment/v1/cluster_templates/{id}` | `object.parameters[]`, `object.spec_defaults` | Yes — node sets remain caller input. |
| Node-set hardware chooser | Supported bare-metal types | `GET /api/fulfillment/v1/bare_metal_instance_types` | `items[].id/metadata.name/spec`, `total` | Yes when BMaaS is enabled; the route is absent in valid CaaS + VMaaS-only profiles. |
| Version chooser | Selectable OCP versions | `GET /api/fulfillment/v1/cluster_versions` | `items[].spec.version/state/enabled`, `total` | Yes — public handler applies lifecycle defaults. |
| Version detail | Referenced version and compatibility | `GET /api/fulfillment/v1/cluster_versions/{id}` | `object.spec.version/state/enabled` | Yes — public handler maps private object. |
| Cluster order | Catalog or template source, requested operators, validation | `POST /api/fulfillment/v1/clusters` | Request `object.spec.catalog_item` or `template` and `add_on_operators[]`; response `object.spec.add_on_operators[]`; add-on resolver error details | Yes — exactly one source; resolver expands dependencies. |
| Cluster detail | Operator status and aggregate condition | `GET /api/fulfillment/v1/clusters/{id}` | `object.spec.add_on_operators[]`, `object.status.add_on_operators[].name/state/message`, `object.status.conditions[]` | Yes — feedback controller populates status after order feedback. |
| Cross-cluster outcomes | Per-row operator status and total count | `GET /api/fulfillment/v1/clusters` | `items[].spec.add_on_operators[]`, `items[].status.add_on_operators[]`, `items[].status.conditions[]`, `total` | Yes — public handler maps scoped private results. |
| Public permission gate | Method-level decision | `POST /api/fulfillment/v1/self_subject_access_reviews` | `object.status.allowed` | Yes — public services only; resource ownership still checked on action. |
| Session persona | Username, role claims, tenant | `GET /api/login/info` | `username`, `roles[]`, `groups[]`, `tenantId` | Yes — proxy reads OIDC session tokens. |
| CaaS route gate | Enabled service tier | `GET /api/fulfillment/v1/capabilities` | `enabled_services[]` | Yes — handler uses deployment service flags. |
| Tenant target chooser | Visible tenant names/IDs | `GET /api/fulfillment/v1/tenants` | `items[].id/metadata.name`, `total` | Yes — public handler maps scoped private results. |
| Project target chooser | Visible tenant/project choices | `GET /api/fulfillment/v1/projects` | `items[].id/metadata.name/metadata.tenant/metadata.project`, `total` | Yes — public handler maps scoped private results. |

Route/type and handler evidence: `proto/public/osac/public/v1/*_service.proto`, `proto/private/osac/private/v1/add_on_operators_service.proto`, `fulfillment-service/internal/servers/{add_on_operators_server.go,private_add_on_operators_server.go,cluster_catalog_items_server.go,cluster_templates_server.go,bare_metal_instance_types_server.go,cluster_versions_server.go,clusters_server.go,private_clusters_server.go}`. Status production is in `osac-operator/internal/controller/feedback_controller.go`. The proxy route and identity response are in `osac-ui/proxy/{main.go,bridge/connectjson.go,auth/handler.go}`; service registration is in `fulfillment-service/internal/cmd/service/start/grpcserver/register_servers.go`.

### Pagination, Filtering, and Sorting

| List endpoint | Pagination | Filtering | Sorting | Notes |
| --- | --- | --- | --- | --- |
| Public `AddOnOperators.List` | Offset/limit; `size/total` | CEL title/name/description and scalar metadata; published always required | `order` ignored | Search across pages is supported by server filtering. |
| Private `AddOnOperators.List` | Offset/limit; `size/total` | CEL fields including `published` | `order` ignored | Returns unpublished for authorized provider identities. |
| `ClusterCatalogItems.List` | Offset/limit; `size/total` | CEL `published`/title and metadata tenant/project | `order` ignored | Tenant-user browse must request `this.published`. |
| `ClusterTemplates.List` | Offset/limit; `size/total` | CEL title/name and metadata | `order` dropped | Public handler omits request order. |
| `BareMetalInstanceTypes.List` | Offset/limit; `size/total` | CEL metadata/name and scalar fields | `order` ignored | Registered only with BMaaS; use server search when available. |
| `ClusterVersions.List` | Offset/limit; `size/total` | CEL state/enabled/version; lifecycle defaults | `order` ignored | Existing UI filter requests enabled Active/Deprecated versions. |
| `Clusters.List` | Offset/limit; `size/total` | CEL scalar/nested fields; no predicate over operator-status messages | `order` dropped | Cannot filter all pages by failed operator or operator name. |
| `Tenants.List` | Offset/limit; `size/total` | CEL metadata/name | `order` ignored | Page or search target choices. |
| `Projects.List` | Offset/limit; `size/total` | CEL metadata tenant/project/name | `order` ignored | Page or search target choices. |

The generic DAO defaults to 100 items, caps a page at 1000, and returns only `total` for explicit `limit: 0`. It hard-codes `ORDER BY id`; `GenericServer.List` never reads `order`, and public Cluster/Template handlers also omit it. The supported CEL subset includes scalar comparisons, `contains`/`startsWith`/`endsWith`, array membership, and array `size()`; it has no message-array predicate for `status.add_on_operators[].state/name`. [Codebase: `generic_dao.go`, `generic_dao_list.go`, `generic_server.go`, `filter_translator.go`, `fulfillment-service/docs/FILTER.md`]

For authorization, `admins` group members receive all-tenant visibility; `tenant-admin` gets all projects in its own tenant and cannot edit a shared catalog item. The UI also recognizes the `cloud-provider-admin` realm role as provider admin, but Fulfillment's `is_admin` does not. RoleBinding maps `cloud-provider-admin` to a realm role. Public SelfSubjectAccessReviews can check a public method with a tenant hint, not a private service or the ownership of an existing item. [Codebase: `authz.rego`, `default_tenancy_logic.go`, `private_self_subject_access_reviews_server.go`, `oidc-login.tsx`, `role_binding_reconciler_function.go`]

Installable operators are shared-scoped, have unique immutable names, and are stored as canonical cluster spec references; the feedback controller emits those names in status. The detail view can join a status name to a spec reference only when it matches uniquely and otherwise display the name without metadata. [Codebase: `113_create_add_on_operators_tables.up.sql`, `add_on_operator_validation.go`, `feedback_controller.go`]

Status polling can use the existing 10-second TanStack Query refetch interval; `Events.Watch` also exists but is not required for this design. The planned writes update one catalog item or operator at a time, so no batch API is required. The UI implementation must deliberately advance its protobuf baseline to include `ClusterCatalogItem.fields.add_on_operators`, then regenerate types and add manual exports/query keys; this is client contract alignment, not a missing backend endpoint. `useClusters` must retain `total` when adding pagination. No generated file should be hand-edited. [Codebase: `osac-ui/AGENTS.md`, `libs/types/.buf-api-version`, `libs/types/src/index.ts`, `api/types.ts`, `api/v1/cluster.ts`]

### API Gaps

| # | Gap ID | Gap / canonical data element | Category | UI impact | Severity |
| --- | --- | --- | --- | --- | --- |
| 1 | `field-38c2d7639b85` | per-entry mandatory and optional-default add-on policy | field | Catalog editor and launch picker cannot enforce the selected UX rules. | critical |
| 2 | `shape-281469e0b39f` | explicit empty add-on selection distinct from omitted override | shape | Tenant cannot remove every optional default. | critical |
| 3 | `field-4b10034f7620` | tenant-targeted add-on operator visibility | field | Provider cannot publish to selected tenants; public availability is global. | critical |
| 4 | `permission-46ba3aec69fe` | cloud-provider-admin role authorization for provider operator management and cross-tenant reads | permission | Role-only provider sees controls but receives denials and limited cluster scope. | critical |
| 5 | `filtering-5a6c733a5cca` | server-side failed operator and operator-name cluster filtering | filtering | Cross-cluster failure search cannot be correct across pages. | high |
| 6 | `sorting-3680a3deac47` | server-side ordering of paged operator and cluster lists | sorting | Inventory and outcome lists have fixed ID order despite requested sort. | medium |
| 7 | `data-ef5b91178d6e` | hardware choices for CaaS when BMaaS is disabled | data | Direct-template node-set chooser has no hardware list in a valid CaaS + VMaaS-only deployment. | high |

Gap IDs were computed with `compute-hash.py gap-id` from the category, the canonical data element above, and the existing endpoint path given below. Preserve these IDs when refining a finding so `/sync` can update its eventual Jira issue.

### Gap Details

#### Gap 1: Mandatory and optional catalog entries

- **Gap ID:** `field-38c2d7639b85`
- **Category:** field
- **UI need:** form-input: per-entry mandatory and optional-default add-on policy
- **Current state:** `ClusterCatalogItem.fields.add_on_operators` is one whole-list `locked.items[]` or `editable.default_value.items[]` policy. An editable nonempty request replaces the default list; the server does not retain a mandatory subset.
- **What's missing:** A persisted per-entry mode and server validation that rejects removal of mandatory operators while allowing optional-default removal and compatible extras.
- **Affected components:** `ClusterCatalogItemEditorPage`, `CatalogAddOnOperatorsStep`, `CatalogAddOnOperatorSummary`, `ClusterAddOnOperatorsStep`, `AddOnOperatorPicker`
- **Severity:** critical
- **Suggested approach:** Extend the catalog policy contract and order validation to express and enforce mandatory versus optional entries; account for required dependencies and existing catalog references.
- **Evidence:** `proto/public/osac/public/v1/field_policy_type.proto`, `fulfillment-service/internal/servers/cluster_catalog_item_policies.go`, `fulfillment-service/internal/database/migrations/140_add_on_operator_catalog_item_deletion_protection.up.sql`.
- **Gap ID endpoint input:** `/api/fulfillment/v1/cluster_catalog_items/{id}`

#### Gap 2: Explicitly empty editable selection

- **Gap ID:** `shape-281469e0b39f`
- **Category:** shape
- **UI need:** form-input: explicit empty add-on selection distinct from omitted override
- **Current state:** `ClusterSpec.add_on_operators` is repeated, and `applyClusterCatalogItemPolicies` checks `len(...) > 0`. An empty submitted list is treated as omitted and receives editable defaults; an existing unit test asserts this behavior.
- **What's missing:** A presence-aware way to express “select none” separately from “use defaults,” with correct validation when mandatory entries exist.
- **Affected components:** `ClusterCreateWizard`, `ClusterAddOnOperatorsStep`, `ClusterOperatorSummary`
- **Severity:** critical
- **Suggested approach:** Define a presence-aware selection contract and apply it consistently during catalog policy resolution and cluster creation.
- **Evidence:** `proto/public/osac/public/v1/cluster_type.proto`, `fulfillment-service/internal/servers/cluster_catalog_item_policies.go`, `fulfillment-service/internal/servers/catalog_item_field_policies_test.go`.
- **Gap ID endpoint input:** `/api/fulfillment/v1/clusters`

#### Gap 3: Tenant-targeted publication

- **Gap ID:** `field-4b10034f7620`
- **Category:** field
- **UI need:** form-input: tenant-targeted add-on operator visibility
- **Current state:** Public and private `AddOnOperator` have only `published`; operators are forced into the shared tenant. Public List/Get expose every published operator to all authorized tenants, and catalog/order validation resolves published shared operators.
- **What's missing:** A tenant visibility field and consistent enforcement for public discovery, catalog attachment, and order-time reference validation; existing references need lifecycle handling when scope narrows.
- **Affected components:** `AddOnOperatorVisibilityDialog`, `AddOnOperatorsPage`, `AddOnOperatorPicker`, `CatalogAddOnOperatorsStep`
- **Severity:** critical
- **Suggested approach:** Add an operator availability scope and enforce it across read and reference-resolution paths, including updates that affect existing catalog references.
- **Evidence:** `proto/public/osac/public/v1/add_on_operator_type.proto`, `proto/private/osac/private/v1/add_on_operator_type.proto`, `fulfillment-service/internal/servers/add_on_operators_server.go`, `fulfillment-service/internal/servers/private_add_on_operators_server.go`.
- **Gap ID endpoint input:** `/api/private/v1/add_on_operators/{id}`

#### Gap 4: Provider identity and server permissions

- **Gap ID:** `permission-46ba3aec69fe`
- **Category:** permission
- **UI need:** permission-gate: cloud-provider-admin role authorization for provider operator management and cross-tenant reads
- **Current state:** The UI treats either `admins` group or `cloud-provider-admin` realm role as `admin`. Fulfillment grants all-method and all-tenant access only to `admins` group or privileged service accounts. Private RPCs cannot be checked through public SelfSubjectAccessReviews.
- **What's missing:** Server authorization and tenant visibility aligned with the provider identity represented by the UI, including private operator List/Update, catalog writes, and cross-tenant Cluster List/Get.
- **Affected components:** `AddOnOperatorsPage`, `AddOnOperatorVisibilityDialog`, `ClusterCatalogItemEditorPage`, `CatalogPage`, `ClustersPage`, `ClusterDetailsPage`
- **Severity:** critical
- **Suggested approach:** Align the provider role's server grants and tenancy with the intended identity, then verify real group-only and role-only tokens through public and private RPCs; keep UI gates advisory.
- **Evidence:** `osac-ui/apps/app-frontend/src/hooks/oidc-login.tsx`, `fulfillment-service/internal/auth/policies/authz.rego`, `fulfillment-service/internal/controllers/rolebinding/role_binding_reconciler_function.go`, `fulfillment-service/internal/servers/private_self_subject_access_reviews_server.go`.
- **Gap ID endpoint input:** `/api/private/v1/add_on_operators`

#### Gap 5: Cross-cluster operator outcome filtering

- **Gap ID:** `filtering-5a6c733a5cca`
- **Category:** filtering
- **UI need:** filtering: server-side failed operator and operator-name cluster filtering
- **Current state:** `Clusters.List` returns each page's `status.add_on_operators[]` and `total`, but the supported CEL translator has no predicate over repeated status messages. Client filtering one page changes the displayed count and misses matches on later pages.
- **What's missing:** A scoped server query for clusters with a selected operator name and/or failed operator state across the full result set.
- **Affected components:** `ClustersPage`, `ClustersTable`, `ClusterOperatorStatusCell`
- **Severity:** high
- **Suggested approach:** Support a server-side operator-outcome filter on Cluster List with tenant visibility applied before counting and paging.
- **Evidence:** `proto/public/osac/public/v1/cluster_type.proto`, `fulfillment-service/internal/servers/clusters_server.go`, `fulfillment-service/internal/database/dao/filter_translator.go`.
- **Gap ID endpoint input:** `/api/fulfillment/v1/clusters`

#### Gap 6: Sort paged inventory and outcomes

- **Gap ID:** `sorting-3680a3deac47`
- **Category:** sorting
- **UI need:** sorting: server-side ordering of paged operator and cluster lists
- **Current state:** List proto requests expose `order`, but `GenericServer.List` ignores it and the DAO orders by ID. Public Clusters and ClusterTemplates handlers also drop the field. Client sorting only a page cannot reorder the full collection.
- **What's missing:** Validated server ordering for the paged operator inventory and cluster outcome list, with the same behavior on other source-choice lists.
- **Affected components:** `AddOnOperatorsPage`, `AddOnOperatorPicker`, `ClustersPage`, `ClustersTable`
- **Severity:** medium
- **Suggested approach:** Honor validated order criteria in the shared list path and forward the request field from public handlers.
- **Evidence:** `fulfillment-service/internal/servers/generic_server.go`, `fulfillment-service/internal/database/dao/generic_dao_list.go`, `fulfillment-service/internal/servers/clusters_server.go`, `fulfillment-service/internal/servers/cluster_templates_server.go`.
- **Gap ID endpoint input:** `/api/fulfillment/v1/add_on_operators`

#### Gap 7: Hardware discovery in a valid CaaS profile

- **Gap ID:** `data-ef5b91178d6e`
- **Category:** data
- **UI need:** data-display: hardware choices for CaaS when BMaaS is disabled
- **Current state:** `ClusterSpec.node_sets` entries require `BareMetalInstanceTypeReference` and the current wizard queries `BareMetalInstanceTypes.List`. CaaS + VMaaS without BMaaS passes service validation and keeps CaaS APIs registered, but the hardware-type RPC is registered only with BMaaS; no compatible alternative was found in the current public proto.
- **What's missing:** Discoverable node-set choices for a CaaS deployment that does not enable BMaaS, or an explicit product scope restriction for direct-template ordering in that profile.
- **Affected components:** `ClusterCreateWizard`, `ClusterCatalogItemEditorPage`
- **Severity:** high
- **Suggested approach:** Resolve the CaaS node-set discovery contract across supported service combinations and expose only types the current deployment can provision.
- **Evidence:** `fulfillment-service/internal/services/flags.go`, `fulfillment-service/internal/cmd/service/start/grpcserver/register_servers.go`, `proto/public/osac/public/v1/cluster_type.proto`, `osac-ui/libs/ui-components/src/components/Cluster/CreateWizard/ClusterNodeSetsArrayField.tsx`.
- **Gap ID endpoint input:** `/api/fulfillment/v1/bare_metal_instance_types`

---

## Provenance

Authored: revise @ ui-design 0.1.0 - b369da0, workspace main @ 91e852e8f
Phases: plan, review-api, revise

<!-- ai-workflow-provenance:{"schema_version":1,"provenance_kind":"session","workflow":"ui-design","workflow_version":"0.1.0","ai_workflows":"b369da0","source_repo":"91e852e8f","source_repo_branch":"main","commits_behind_main":0,"commits_ahead_main":595,"main_ref":"main","phases":["plan","review-api","revise"],"authoring_modes":["skill"],"context_changed":false,"origin_untracked":false} -->
