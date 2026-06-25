# ClusterVersion — Managed Version Catalog for Cluster Provisioning

| Field       | Value   |
|-------------|---------|
| Author(s)   | Ilya Skornyakov |
| Jira        | [OSAC-1269](https://issues.redhat.com/browse/OSAC-1269) |
| Date        | 2026-06-24 |

## 1. Problem Statement

The Cluster API requires users to provide a full OCI release image URL (e.g., `quay.io/openshift-release-dev/ocp-release:4.17.0-multi`) when creating a cluster. This leaks infrastructure implementation details into the user-facing API: users must know the exact registry path and tag format, typos are caught only at provisioning time rather than at API validation, and there is no way to discover which versions are available.

The cost compounds across layers. Catalog items resort to regex patterns to constrain the image URL prefix — a workaround that cannot verify the version actually exists or is supported. Multiple components independently construct release image URLs from version numbers, duplicating format knowledge with no central validation. Each layer works around the same missing abstraction: a managed catalog of validated cluster versions.

A ClusterVersion resource eliminates these workarounds. Users select from a curated, queryable list of versions — no URLs, no guessing. Catalog items reference versions by name instead of embedding URL patterns. Automation receives pre-validated release images from the API, removing URL construction. And the version catalog becomes the foundation for future upgrade operations (OSAC-1415) and ACM version synchronization, which require a queryable set of available versions and their upgrade paths.

## 2. Goals and Non-Goals

### 2.1 Goals

- Users specify an OpenShift version by number (e.g., "4.17.0") instead of a raw OCI URL when creating a cluster, with the server resolving the version to the correct release image internally.
- Users receive immediate, descriptive feedback when specifying an invalid, obsolete, or deprecated version — before any provisioning begins.
- Cloud Provider Admins manage available cluster versions through the CLI and UI console.
- Tenant Users can discover and select from available versions when creating a cluster — in the CLI, UI, and API.

### 2.2 Non-Goals

- Cluster upgrade operations and channel propagation to the hosted cluster — triggering, tracking, or rolling back upgrades, and propagating the version's channel to the hosted cluster. Owned by OSAC-1415. Channels are stored as version catalog metadata but not propagated to the cluster in v0.2. [Clarify: R1.Q3, R2.Q2]
- ACM ClusterImageSet auto-sync — automatic discovery and population of version catalog entries from ACM. Versions are admin-managed in v0.2. [Clarify: R1.Q7]
- VM image management — the VM image catalog (OSAC-979) uses a separate resource. Both features share the same architectural pattern (raw URL to managed catalog with server-side resolution) but are distinct resources. [Clarify: R1.Q4]
- In-place upgrade migration — OSAC does not support in-place upgrades. This feature assumes fresh deployment. [Clarify: R2.Q4]

## 3. Requirements

### 3.1 Functional Requirements

#### Version Catalog Management

- **FR-1:** Each version in the catalog is identified by its version number (e.g., "4.17.0"), maps to a release image, has a lifecycle state (active, deprecated, or obsolete), can optionally be marked as the default, and is associated with update channels (e.g., "stable-4.17", "fast-4.17"). Channels are informational metadata in v0.2; channel-based selection and propagation are deferred to OSAC-1415. [Clarify: R1.Q1, R1.Q8]

- **FR-2:** Admins can create, update, and delete catalog entries. Users can list versions filtered to active and deprecated entries by default; obsolete versions are hidden from the default list but visible via explicit filter. Viewing a specific version by identifier returns it regardless of its lifecycle state, so users can inspect versions referenced by their existing clusters. [Clarify: R1.Q6, R3.Q1]

- **FR-3:** At most one version can be marked as default. The default version is used when no version is specified by the user or template. [Clarify: R1.Q1]

#### Cluster Creation

- **FR-4:** Users specify a version number (e.g., "4.17.0") when creating a cluster. Release image URLs are not visible in cluster creation or listing responses — only the version is exposed. [Clarify: R1.Q2, R1.Q5, R2.Q1, R2.Q4, R3.Q3, R3.Q4]

- **FR-5:** Templates can specify a default version (e.g., "4.17.0"). Any version can be used with any template; templates provide defaults but do not constrain version selection. [Clarify: R2.Q1]

- **FR-6:** A cluster's version is visible in responses when viewing or listing clusters.

#### Validation

- **FR-7:** Version is validated at creation time with descriptive error messages that include the invalid value and valid alternatives. Validation covers: version not found and version obsolete. Creating a cluster with a deprecated version succeeds but includes a warning identifying the replacement version, if one is set. [Clarify: R2.Q3, R3.Q6]

#### User Interfaces

- **FR-8:** The CLI supports catalog management (create, update, delete) and cluster creation with a version option replacing the release image option. [Clarify: R1.Q5, R1.Q7]

- **FR-9:** The UI console supports catalog management for admins and version selection in the cluster creation wizard for users.

- **FR-10:** Catalog items reference version instead of release image in their field definitions, following the existing catalog item pattern. [Clarify: R1.Q5]

#### Lifecycle Protection

- **FR-11:** Deleting a version is rejected when it is referenced by active clusters or template defaults. The error identifies the referencing resource (e.g., "cannot delete version '4.17.0': in use by cluster 'cluster-abc'"). [Clarify: R3.Q2]

- **FR-12:** Creating or updating a cluster or template with a version that does not exist or has been deleted is rejected. A cluster cannot reference a deleted version. [Clarify: R3.Q2]

- **FR-13:** Lifecycle state transitions (active, deprecated, obsolete) are always allowed regardless of references. Existing clusters and templates referencing a deprecated or obsolete version are not affected. Admins can transition a version between any states in any direction. [Clarify: R3.Q5]

- **FR-14:** Version is immutable after cluster creation. [Clarify: R2.Q3]

- **FR-15:** A version can be marked as deprecated with an optional replacement version. Deprecated versions remain available for new cluster creation but include a warning identifying the replacement, if one is set. Obsolete versions are blocked for new cluster creation. Deprecation and obsolescence timestamps are recorded automatically when the version enters each state.

### 3.2 Non-Functional Requirements

- **NFR-1:** Admins manage the version catalog using the same patterns they already know from other admin-managed resources — consistent commands, access model, lifecycle states (active/deprecated/obsolete), and visibility rules with no new interaction model to learn. [Clarify: R1.Q6, R3.Q1]

- **NFR-2:** Future additions to the version catalog (e.g., upgrade paths, channel-based selection) must not break existing cluster creation workflows. [Clarify: R2.Q2]

## 4. Acceptance Criteria

- [ ] A user can create a cluster by specifying a version number (e.g., 4.17.0) instead of a release image URL. The server resolves the version to the correct release image internally. Release image URLs are not visible in cluster creation or listing responses. Version is immutable after creation.
- [ ] Specifying a non-existent, deleted, or obsolete version is rejected with a descriptive error indicating the reason and identifying the replacement if one is set. Deprecated versions allow creation with a warning. Validation applies to both cluster creation and template defaults.
- [ ] Admins can create, update, and delete version catalog entries. Deleting a version referenced by an active cluster or template defaults is rejected with a message identifying the referencing resource.
- [ ] Admins can transition a version between active, deprecated, and obsolete in any direction, even when referenced by active clusters or templates. Listing versions returns active and deprecated entries by default; obsolete versions are hidden unless explicitly filtered. Deprecation and obsolescence timestamps are recorded automatically on each transition.
- [ ] At most one version is marked as default at any time — setting a new default clears the previous one. When a user omits the version and template defaults do not supply one, the server uses the default version. Templates can specify a default version, and the server resolves it to a release image.
- [ ] The CLI supports version catalog management and cluster creation with a version option. Catalog items can reference version in their field definitions. The UI console supports catalog management for admins and version selection in the cluster creation wizard.

## 5. Assumptions

- OSAC does not support in-place upgrades. This feature assumes fresh deployment or environment re-creation. Existing clusters created with a release image URL will not automatically display a version value after redeployment. Administrators must re-create templates and catalog items with version references replacing release image URLs. [Clarify: R2.Q4]
- No production catalog items exist that reference the release image, so the change to version-based selection requires no migration. [Clarify: R1.Q5]

## 6. Dependencies

- **OSAC-1531 (Default Catalog Items)** — Default version catalog entries should ship alongside default catalog items. Version catalog population is a prerequisite for catalog items that reference version-based clusters.
- **OSAC-1415 (Cluster Upgrade)** — The version catalog is designed as an extension point. OSAC-1415 is expected to add upgrade capabilities, channel-based version selection, and channel propagation to the hosted cluster. This PRD does not constrain OSAC-1415's design. [Clarify: R2.Q2]

## 7. Risks

### 7.1 Version catalog must be populated before cluster creation

Without version catalog entries, users cannot create clusters via the public API. If admins deploy OSAC but do not populate versions, the system appears broken.

- **Owner:** CaaS team
- **Mitigation:** Ship default version catalog entries alongside OSAC-1531 default catalog items. Document version population in the admin guide.

### 7.2 Shared pattern divergence with VM image management

OSAC-1269 (cluster version catalog) and OSAC-979 (VM image catalog) follow the same architectural pattern — raw URL to managed catalog with server-side resolution. If designed independently, their APIs may diverge in naming conventions, resolution behavior, or error handling.

- **Owner:** CaaS / VMaaS teams
- **Mitigation:** Both catalogs follow the existing admin-managed reference data pattern. Coordinate API conventions during design review.

## OSAC Dimensions

### Services

This feature applies to **CaaS** (Cluster as a Service) only. VMaaS has an analogous pattern (OSAC-979) but uses a separate resource.

### Personas

| Persona | Interaction |
|---------|-------------|
| Cloud Provider Admin | Creates and manages the version catalog via CLI, API, and UI. Populates available versions. Sets the default version. |
| Tenant User | Selects a version when creating a cluster via CLI, UI wizard, or catalog items. Discovers available versions via the API and UI. |
| Cloud Infrastructure Admin | Not affected. |
| Tenant Admin | Same as Tenant User. May also reference versions when authoring org-specific catalog items. |

### Provisioning

Version resolution occurs during cluster creation. The provisioning flow for the cluster itself is unchanged — this feature adds version selection and validation, not new provisioning steps.

### User-Facing API

| Surface | Impact |
|---------|--------|
| Fulfillment API (gRPC/REST) | New version catalog resource. Cluster creation uses version instead of release image URL. Template defaults updated. Deletion protection when referenced. |
| OSAC CRDs | No change. |
| UI Console | Version catalog management for admins. Version selection in the cluster creation wizard. |
| Catalog Items | Support version selection. |

### Milestone Scoping

- **Target milestone:** v0.2
- **Deferred:** Cluster upgrades (OSAC-1415), ACM version auto-sync, channel-based version selection, channel propagation to hosted cluster, in-place migration of existing data.
- **Upgrades:** OSAC does not support in-place upgrades. No data migration is in scope.

### Installation

No changes to Helm charts, kustomize manifests, or `osac-installer/setup.sh` beyond the standard fulfillment-service image version bump.

### Tenant Onboarding, Inventory, Networking, Storage

Not applicable. The version catalog is global (not tenant-scoped) and does not interact with inventory, networking, or storage subsystems.
