# ClusterVersion — Managed Version Catalog for Cluster Provisioning

| Field       | Value   |
|-------------|---------|
| Author(s)   | Ilya Skornyakov |
| Jira        | [OSAC-1269](https://issues.redhat.com/browse/OSAC-1269) |
| Date        | 2026-06-24 |

## 1. Problem Statement

The Cluster API requires users to provide a full OCI release image URL (e.g., `quay.io/openshift-release-dev/ocp-release:4.17.0-multi`) when creating a cluster. This leaks infrastructure implementation details into the user-facing API: users must know the exact registry path and tag format, typos are caught only at provisioning time rather than at API validation, and there is no way to discover which versions are available or to specify an update channel.

The cost is visible across the stack. Catalog items resort to regex `validation_schema` patterns to constrain the registry prefix — a workaround that cannot verify the version actually exists or is supported. AAP template roles independently construct release image URLs from version numbers (e.g., `{{ ocp_release_version }}-multi`), duplicating URL format knowledge across templates with no central validation. Each layer works around the same missing abstraction: a managed catalog of validated cluster versions.

A ClusterVersion resource eliminates these workarounds. Users select from a curated, queryable list of versions — no URLs, no guessing. Catalog items reference versions by name instead of embedding URL patterns. AAP templates receive pre-validated release images from the API, removing template-level URL construction. And the version catalog becomes the foundation for future upgrade operations (OSAC-1415) and ACM version synchronization, which require a queryable set of available versions and their upgrade paths.

## 2. Goals and Non-Goals

### 2.1 Goals

- Users specify an OpenShift version by number (e.g., "4.17.0") instead of a raw OCI URL when creating a cluster, with the server resolving the version to the correct release image internally.
- The server validates version and channel at API time, rejecting invalid or disabled versions with descriptive error messages before any provisioning begins.
- Cloud Provider Admins manage available versions through a ClusterVersion resource.
- Tenant Users can discover available versions through the public API, enabling self-service version selection in the CLI and wizard.

### 2.2 Non-Goals

- Cluster upgrade operations and channel propagation to HostedCluster — triggering, tracking, or rolling back upgrades, and propagating `channel` to `HostedCluster.spec.channel`. Both are owned by OSAC-1415. The `channel` field is validated in v0.2 but not propagated. [Clarify: R1.Q3, R2.Q2]
- ACM ClusterImageSet auto-sync — automatic discovery and population of ClusterVersion objects from ACM. Versions are admin-managed in v0.2. [Clarify: R1.Q7]
- VM image management — ComputeInstance image catalog (OSAC-979) uses a separate `ComputeImage` resource. Both features share the same architectural pattern (raw URL to managed catalog with server-side resolution) but are distinct resources. [Clarify: R1.Q4]
- In-place upgrade migration — OSAC does not support in-place upgrades. This feature assumes fresh deployment. [Clarify: R2.Q4]

## 3. Requirements

### 3.1 Functional Requirements

#### ClusterVersion Resource

- **FR-1:** OSAC must provide a ClusterVersion resource with the following domain fields: `release_image` (resolved OCI URL), `enabled` (admin availability toggle), `default` (used when version is omitted), and `available_channels` (list of update channel strings, e.g., `["stable-4.17", "fast-4.17"]`). The resource includes standard OSAC metadata (id, name, labels, annotations, timestamps). The resource `name` is the version number itself (e.g., "4.17.0") — there is no separate version string field. [Clarify: R1.Q1, R1.Q8]

- **FR-2:** The resource must be named `ClusterVersion` and the ClusterSpec field must be named `cluster_version`. The naming is cluster-scoped, distinguishing it from other versioned resources in the platform (e.g., ComputeImage for VMaaS). [User]

- **FR-3:** Cloud Provider Admins can create, update, and delete ClusterVersion resources. Tenant Users can list and view available versions. Tenant-visible listings are filtered to enabled versions only. Getting a specific ClusterVersion by identifier returns the resource regardless of its `enabled` status. [Clarify: R1.Q6, R3.Q1]

- **FR-4:** At most one ClusterVersion resource may be marked as `default`. The global default ClusterVersion is the lowest-priority fallback — it is used only when the user omits `cluster_version` and neither template defaults nor catalog item field_definitions supply one. [Clarify: R1.Q1]

- **FR-5:** Cloud Provider Admins must be able to create ClusterVersion objects via the CLI (e.g., `osac create -f cluster-versions.yaml`). [Clarify: R1.Q7]

#### Cluster API Changes

- **FR-6:** Users specify a `cluster_version` (e.g., "4.17.0") that references a ClusterVersion resource by name when creating a cluster. This field replaces `release_image` on the user-facing API. [Clarify: R1.Q2, R1.Q5]

- **FR-7:** Users can specify a `channel` (e.g., "stable-4.17") when creating a cluster. When specified, the server validates the channel against the referenced ClusterVersion's `available_channels` list. The channel is not propagated to the HostedCluster in v0.2. [Clarify: R1.Q3]

- **FR-8:** The `release_image` field must be removed from the user-facing Cluster API and ClusterTemplate defaults. Users see only `cluster_version` and `channel`; `release_image` is not visible to API consumers. [Clarify: R1.Q5, R2.Q1, R2.Q4, R3.Q3, R3.Q4]

#### Version Resolution

- **FR-9:** During cluster creation, the server must resolve the `cluster_version` to a `release_image` using the referenced ClusterVersion resource. Version resolution is fully contained in the fulfillment-service — the ClusterOrder CRD, osac-operator, and AAP are unchanged and continue to receive `release_image` with no downstream changes. [Clarify: R1.Q2, R1.Q5, R2.Q4, R3.Q3]

- **FR-10:** ClusterTemplate defaults must support a `cluster_version` field replacing `release_image`. Template authors set `cluster_version: "4.17.0"` in defaults. Any ClusterVersion can be used with any template; templates provide version defaults but do not constrain version selection. The server applies template defaults before version resolution. [Clarify: R2.Q1]

#### Validation

- **FR-11:** The server must validate `cluster_version` and `channel` at API time, rejecting invalid requests with descriptive error messages that include the invalid value and valid alternatives. Validation applies to the effective spec after template defaults and the global default ClusterVersion have been applied. Validation covers: version not found, version not enabled, version deleted, invalid channel for the given version, channel present without a resolved cluster_version (after all defaults), and empty `available_channels` (specifying any channel is invalid). The `cluster_version` and `channel` fields are immutable after cluster creation — attempts to change either on update must be rejected. [Clarify: R2.Q3, R3.Q6]

#### CLI and Catalog Items

- **FR-12:** The CLI must replace the `--release-image` flag with `--cluster-version` and `--channel` flags for cluster creation. [Clarify: R1.Q5]

- **FR-13:** Catalog item field_definitions must reference the `cluster_version` field path instead of `release_image`. [Clarify: R1.Q5]

#### Lifecycle Protection

- **FR-14:** Deleting a ClusterVersion must be rejected when it is referenced by active clusters or ClusterTemplate defaults. The error message must identify the referencing resource (e.g., "cannot delete cluster version '4.17.0': it is in use by at least cluster 'cluster-abc'"). [Clarify: R3.Q2]

- **FR-15:** Creating or updating a cluster or ClusterTemplate with a `cluster_version` that references a non-existent or deleted ClusterVersion must be rejected. Concurrent create and delete operations must not produce inconsistent state. [Clarify: R3.Q2]

- **FR-16:** Disabling a ClusterVersion is always allowed regardless of references. Disabled versions block new cluster creation (FR-11 validation) but do not affect existing clusters or templates that reference them. [Clarify: R3.Q5]

### 3.2 Non-Functional Requirements

- **NFR-1:** The ClusterVersion resource must be consistent with existing admin-managed reference data resources (HostType, NetworkClass) in API conventions, access patterns, and lifecycle behavior. [Clarify: R1.Q6, R3.Q1]

- **NFR-2:** Field names and reference patterns must align with the OCM Clusters Management API where applicable: `cluster_version` as a reference by readable name (aligned with OCM's `link Version Version` pattern), `channel` as a plain string (aligned with OCM's `Channel String`). [Clarify: R1.Q8]

- **NFR-3:** The ClusterVersion resource must be extensible. OSAC-1415 is expected to add fields such as `available_upgrades` and activate channel propagation to HostedCluster. These additions must be non-breaking proto field additions. [Clarify: R2.Q2]

## 4. Acceptance Criteria

- [ ] A user can create a cluster by specifying `--cluster-version 4.17.0` instead of a release image URL, and the server resolves the version to the correct release image internally.
- [ ] Specifying a non-existent or deleted `cluster_version` is rejected with a descriptive error — both when creating a cluster and when setting ClusterTemplate defaults.
- [ ] Specifying a disabled version is rejected with a message indicating the version is not enabled.
- [ ] Specifying a channel not in the ClusterVersion's `available_channels` is rejected with an error listing valid channels. A request whose effective spec contains `channel` but no `cluster_version` (after defaults) is rejected.
- [ ] Attempting to change `cluster_version` or `channel` on an existing cluster is rejected (both fields are immutable).
- [ ] Listing ClusterVersions as a Tenant User returns only enabled versions with their `available_channels`.
- [ ] A Cloud Provider Admin can create, update, and delete ClusterVersion resources.
- [ ] Deleting a ClusterVersion that is referenced by an active cluster or a ClusterTemplate's defaults is rejected with a message identifying the referencing resource.
- [ ] Disabling a ClusterVersion succeeds even when referenced by active clusters or templates; new cluster creation with that version is blocked.
- [ ] When a user omits `cluster_version` and neither template defaults nor catalog item field_definitions supply one, the server uses the ClusterVersion marked as `default`.
- [ ] At most one ClusterVersion is marked as `default` at any time — setting `default` on a second ClusterVersion either clears the previous default or is rejected.
- [ ] A cluster creation and a ClusterVersion deletion racing on the same version do not produce a cluster referencing a deleted ClusterVersion.
- [ ] Template defaults support `cluster_version` — when a template specifies `cluster_version: "4.17.0"`, the server applies it as the default and resolves it to `release_image`.
- [ ] Catalog item field_definitions can reference the `cluster_version` path.
- [ ] The `release_image` field is not visible to API consumers. Internally, the server stores and forwards `release_image` to downstream systems.
- [ ] The osac-operator and AAP continue to receive `release_image` through the ClusterOrder CRD — no downstream changes are required.

## 5. Assumptions

- OSAC does not support in-place upgrades. This feature assumes fresh deployment or environment re-creation. Existing clusters created with `release_image` will not automatically display a `cluster_version` value after redeployment. Administrators must re-create templates and catalog items with `cluster_version` replacing `release_image`. [Clarify: R2.Q4]
- No production catalog items exist that reference `release_image` in field_definitions, so the field path change from `release_image` to `cluster_version` requires no migration. [Clarify: R1.Q5]

## 6. Dependencies

- **OSAC-1531 (Default Catalog Items)** — Default ClusterVersion objects should ship alongside default catalog items. ClusterVersion creation is a prerequisite for catalog items that reference version-based clusters.
- **OSAC-1415 (Cluster Upgrade)** — The ClusterVersion resource is designed as an extension point. OSAC-1415 is expected to add fields such as `available_upgrades` and activate `channel` propagation to HostedCluster. This PRD does not constrain OSAC-1415's design. [Clarify: R2.Q2]

## 7. Risks

### 7.1 ClusterVersion catalog must be populated before cluster creation

Without ClusterVersion objects, users cannot create clusters via the public API. If admins deploy OSAC but do not populate versions, the system appears broken.

- **Owner:** CaaS team
- **Mitigation:** Ship default ClusterVersion objects alongside OSAC-1531 default catalog items. Document version population in the admin guide.

### 7.2 Shared pattern divergence with VM image management

OSAC-1269 (ClusterVersion) and OSAC-979 (ComputeImage) follow the same architectural pattern — raw URL to managed catalog with server-side resolution. If designed independently, their APIs may diverge in naming conventions, resolution behavior, or error handling.

- **Owner:** CaaS / VMaaS teams
- **Mitigation:** Both resources follow the HostType/NetworkClass reference data pattern. Coordinate API conventions during design review.

## OSAC Dimensions

### Services

This feature applies to **CaaS** (Cluster as a Service) only. VMaaS has an analogous pattern (OSAC-979) but uses a separate resource.

### Personas

| Persona | Interaction |
|---------|-------------|
| Cloud Provider Admin | Creates and manages ClusterVersion resources. Populates the version catalog. Sets default version. |
| Tenant User | Selects a version from the available list when creating a cluster. Discovers available versions via `ListClusterVersions`. |
| Cloud Infrastructure Admin | Not affected. |
| Tenant Admin | Not affected beyond Tenant User capabilities. |

### Provisioning

Version resolution occurs during cluster creation in the fulfillment-service. The provisioning flow downstream (ClusterOrder CRD, osac-operator, AAP) is unchanged — it continues to receive `release_image`.

### User-Facing API

| Surface | Impact |
|---------|--------|
| Fulfillment API (gRPC/REST) | New ClusterVersion resource (admin-managed, tenant-readable). Modified ClusterSpec (`cluster_version` and `channel` replace `release_image` for API consumers). Modified ClusterTemplate defaults (`cluster_version` replaces `release_image`). Deletion protection when referenced by clusters or templates. |
| OSAC CRDs | No change. ClusterOrder CRD retains `releaseImage`. |
| Catalog Items | Field_definitions reference `cluster_version` path instead of `release_image`. |

### Milestone Scoping

- **Target milestone:** v0.2
- **Deferred:** Cluster upgrades (OSAC-1415), ACM version auto-sync, channel propagation to HostedCluster, in-place migration of existing data.
- **Upgrades:** OSAC does not support in-place upgrades. No data migration is in scope.

### Installation

No changes to Helm charts, kustomize manifests, or `osac-installer/setup.sh` beyond the standard fulfillment-service image version bump.

### Tenant Onboarding, Inventory, Networking, Storage

Not applicable. The ClusterVersion resource is global (not tenant-scoped) and does not interact with inventory, networking, or storage subsystems.
