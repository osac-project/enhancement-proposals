| Field       | Value   |
|-------------|---------|
| Author(s)   | Roy Golan rgolan@redhat.com |
| Status      | Draft |
| Jira        | https://redhat.atlassian.net/browse/OSAC-1111 |
| Date        | 2026-06-04 |


# StorageBackend API — Product Requirements

## Summary

This enhancement adds a first-class StorageBackend entity to the OSAC fulfillment-service for registering and managing storage backends. Cloud Provider Admins register storage arrays (VAST Data, Ceph, Pure Storage, etc.) through the private gRPC API with provider type, management endpoint, and credentials reference. The fulfillment-service PostgreSQL database becomes the source of truth for available storage infrastructure, replacing environment-variable-based configuration. The entity is DB-backed with no Kubernetes CRD, following the existing OSAC pattern for infrastructure-level resources like NetworkClass.

## Motivation

OSAC currently relies on environment variables (`STORAGE_TIERS`, `VAST_ENDPOINT`) passed as Ansible Automation Platform extra vars for storage backend configuration. This approach has significant operational drawbacks: no API discoverability, no credential rotation without redeployment, no status visibility, and no integration with the OSAC data model. As OSAC matures toward production deployment, Cloud Provider Admins need the ability to register and manage storage backends through the OSAC private API with full CRUD capabilities, status tracking, and credential lifecycle management.

This enhancement builds on the existing tenant-specific StorageClass mechanism (established in the `tenant-specific-storageclasses` and `tenant-storage-tiers` enhancement proposals) by adding the missing infrastructure layer: a registered, discoverable, API-managed inventory of storage backends. StorageClasses are associated with tenants and tiers by labels.

### User Stories

As a **Cloud Provider Admin**, I want to register a storage backend (e.g., VAST Data management endpoint) through the OSAC private API with its provider type, management endpoint, and credentials reference, so that the platform has a source of truth for available storage infrastructure instead of relying on environment variables.

As a **Cloud Provider Admin**, I want to list all registered storage backends with their operational status (model, firmware version, state, permission conditions), so that I can verify which storage arrays are available to the platform and troubleshoot connectivity issues.

As a **Cloud Provider Admin**, I want to update a storage backend's configuration (e.g., rotate credentials by changing the credentials_ref field), so that I can maintain secure credential hygiene without redeploying the fulfillment-service or modifying Ansible playbooks.

As a **Cloud Provider Admin**, I want to decommission a storage backend through the API (soft delete), so that the platform stops using it for new tenant storage provisioning without breaking references from existing StorageTier entities (future work).

As a **Cloud Provider Admin**, I want to query the list of available storage backends when creating a StorageTier, so that I can compose tiered storage offerings from the registered infrastructure inventory.

### Goals

- Enable self-service registration of storage backends through the OSAC private API, removing the operational burden of environment-variable-based configuration and manual Ansible variable updates.
- Provide API-driven credential rotation capabilities for storage backend credentials, supporting secure credential lifecycle management without service downtime.
- Expose storage backend status visibility (operational state, auto-detected model and firmware version) through the API, enabling Cloud Infrastructure Admins to verify backend availability and troubleshoot connectivity issues.
- Establish pattern consistency with existing OSAC infrastructure entities (NetworkClass, PublicIPPool) by following the same private API and DB-backed implementation approach.
- Create the foundation for future StorageTier composition, where Cloud Provider Admins will reference registered backends when defining tenant-facing storage offerings.

### Non-Goals

- **Full StorageTier design** — StorageTier entity design (OSAC-1110) is documented in this EP as a "Future: StorageTier" appendix showing entity model and reconciliation flow only. Full design (proto definitions, DB schema, server implementation) is deferred to a separate enhancement proposal.
- **Provider-specific integration beyond VAST** — This enhancement defines the StorageBackend entity schema and API with a generic `provider` field (e.g., "vast", "ceph", "pure"). Provider-specific integration logic for model/firmware auto-detection and credential validation is implemented incrementally (VAST first, others follow the same pattern).
- **Storage observability and monitoring** — Metrics, health checks, and capacity tracking for storage backends are separate features covered by the "OSAC Storage Observability" roadmap item, not this enhancement.
- **Automatic backend discovery** — Storage backends are explicitly registered by Cloud Provider Admins through the API. Automatic discovery from infrastructure management systems (e.g., VAST API auto-discovery of all arrays in a datacenter) is out of scope.
- **StorageBackend as a Kubernetes CRD** — The StorageBackend entity has no CRD. It is DB-backed and managed exclusively through the fulfillment-service private API, following the NetworkClass pattern. Reconciliation is triggered by Tenant onboarding (which references StorageTier, which references StorageBackend), not by backend registration events.

## Predecessor Evolution

Storage management in OSAC has evolved through three prior stages, each addressing a specific operational gap while leaving the infrastructure-layer registration problem unsolved:

### Stage 1: Environment Variables

Storage configuration flowed via Ansible Automation Platform extra vars (`storage_provider_tiers`, `storage_provider_action`, `VAST_ENDPOINT`, `VAST_USERNAME`, `VAST_PASSWORD`). The `osac.service.storage_provider` Ansible role accepted these variables to provision storage.

**Limitations:**
- No API discoverability — backends were opaque configuration, not queryable entities.
- Credential rotation required redeployment — updating `VAST_PASSWORD` meant modifying the deployment manifests and restarting the fulfillment-service.
- No status visibility — failures in storage connectivity had to be diagnosed from Ansible logs, not from the OSAC API.

### Stage 2: Tenant-Specific StorageClasses (EP: tenant-specific-storageclasses)

The `tenant-specific-storageclasses` enhancement proposal introduced the `osac.openshift.io/tenant` label on StorageClasses for per-tenant resolution. The Tenant controller could now discover which StorageClass to use for a given tenant by querying label selectors.

**Advancement:** Structured per-tenant resolution, moving away from single global StorageClass.

**Remaining gap:** StorageClasses were the source of truth, but backends were still invisible. The Tenant controller had no visibility into which storage arrays backed the StorageClasses it was using.

### Stage 3: Storage Tier Labels (EP: tenant-storage-tiers)

The `tenant-storage-tiers` enhancement proposal added the `osac.openshift.io/storage-tier` label to StorageClasses, enabling multiple tiers per tenant (fast, standard, archival). The Tenant controller populated `status.storageClasses` with all resolved StorageClasses grouped by tier.

**Advancement:** Multi-tiered storage offerings per tenant, supporting diverse workload requirements.

**Remaining gap:** Still no backend entity. Tiers were labels on StorageClasses, not first-class entities with SLA properties and backend references.

### Stage 4: StorageBackend API (This EP)

This enhancement introduces the StorageBackend entity as a DB-backed resource in the fulfillment-service with a private gRPC API. Cloud Provider Admins register backends with provider type, endpoint, and credentials. The database becomes the source of truth for storage infrastructure inventory.

**What this enables:**
- API-driven backend registration and credential rotation
- Status visibility (model, firmware, operational state)
- Foundation for future StorageTier composition (Cloud Provider Admins will reference backends when creating tiers)
- Decoupling of infrastructure management (Infra Admin registers backends) from tenant offerings (Provider Admin creates tiers referencing backends)

**Reconciliation path (future work):** Tenant onboarding will trigger: resolve tier → backend(s) → install CSI driver on hub → create Secret with tenant-scoped credentials → create StorageClass for tenant on hub.

## Risks and Mitigations

## Drawbacks

### Adds New Entity Type to API Surface

This enhancement introduces a new top-level entity (`StorageBackend`) to the OSAC private API, increasing the API surface area and documentation burden. Each new entity requires ongoing maintenance: proto evolution, DB migrations, server logic, integration tests, and operational runbooks.

**Steel-man argument:** Could the same problem be solved without a new entity? For example, by extending the existing `osac.service.storage_provider` Ansible role to accept backend definitions as structured extra vars (JSON/YAML) instead of flat environment variables. This would preserve the environment-variable configuration pattern while adding structure.

**Counter-argument:** Structured extra vars would still lack API discoverability, credential rotation, and status visibility. The operational gap (no CRUD API for backends) would remain. A first-class entity is the right long-term design for an infrastructure component that needs lifecycle management, even at the cost of API surface growth.

### Maintenance Burden for Multi-Provider Support

The `provider` field ("vast", "ceph", "pure") creates an ongoing maintenance burden as new storage vendors are integrated. Each provider requires specific credential schemas, model/firmware auto-detection logic, and validation rules. Without careful abstraction, provider-specific code can proliferate across the server, DB layer, and validation logic.

**Mitigation:** Start with VAST as the reference implementation, establish provider abstraction patterns (interface or strategy pattern for backend validation and model detection), and document the provider integration process for future contributors.

## Alternatives (Not Implemented)

### Alternative 1: Extend AAP Extra Vars with Structured Backend Definitions

**Description:** Instead of creating a StorageBackend entity, extend the Ansible Automation Platform extra vars to accept structured backend definitions (JSON/YAML arrays) describing provider, endpoint, and credentials. The `osac.service.storage_provider` role would parse these structured vars instead of flat `VAST_ENDPOINT` environment variables.

**Advantages:**
- No new entity, no API surface growth
- Preserves existing Ansible-centric configuration pattern
- Simpler implementation (no proto, no DB schema, no server code)

**Disadvantages:**
- No API discoverability — backends remain opaque configuration, not queryable resources
- No credential rotation without redeployment — updating credentials still requires modifying deployment manifests
- No status visibility — backend connectivity issues still diagnosed from Ansible logs only
- Does not establish a foundation for StorageTier composition (future work would require reworking the entire backend management approach)

**Rejection rationale:** This alternative solves the "structured configuration" problem but not the "API-driven infrastructure management" problem. It is a lateral move, not a forward step.

### Alternative 2: StorageBackend as a Kubernetes CRD

**Description:** Implement StorageBackend as a Kubernetes Custom Resource Definition with a controller that reconciles backend registration and status updates.

**Advantages:**
- Leverages Kubernetes reconciliation patterns (watch, reconcile, status updates)
- Consistent with other OSAC cluster-scoped resources (ClusterOrder, VirtualNetwork)
- Built-in status subresource for state tracking

**Disadvantages:**
- Backend registration is not a reconciliation event — there is no continuous reconciliation loop for a registered backend until it is referenced by a Tenant onboarding flow.
- CRDs create cluster-level API surface for infrastructure-only resources, exposing backend registration to any cluster user with RBAC access instead of restricting it to the private API.
- AWS EBS analogy: AWS does not have an "EBSBackend" Kubernetes CRD for registering EBS storage infrastructure. Storage backends are registered through cloud provider APIs, not cluster resources.

**Rejection rationale:** Reconciliation is triggered by Tenant onboarding (which references StorageTier, which references StorageBackend), not by backend registration. The CRD model is a poor fit for this lifecycle. The DB-backed private API pattern (like NetworkClass) is the right choice.

### Alternative 3: Single Combined EP for StorageBackend + StorageTier

**Description:** Design both StorageBackend (OSAC-1111) and StorageTier (OSAC-1110) in a single enhancement proposal with complete proto definitions, DB schemas, and server implementation details for both entities.

**Advantages:**
- Reviewers see the full picture of storage infrastructure management in one document
- Reduces risk of API inconsistencies between related entities
- Avoids potential rework if StorageTier design requires changes to StorageBackend

**Disadvantages:**
- Significantly larger EP document (likely 2000+ lines), increasing review burden and time-to-approval
- Couples two separate Jira work items (OSAC-1111 and OSAC-1110) with different scopes and timelines
- Delays progress on StorageBackend implementation while StorageTier design details are debated

**Rejection rationale:** The two entities have distinct scopes (infrastructure management vs. tenant offering composition) and different timelines. StorageBackend can be implemented and deployed independently; StorageTier depends on it but not vice versa. A focused EP for StorageBackend with a forward-looking appendix for StorageTier strikes the right balance between completeness and reviewability.

## Open Questions

### ~~Question 1: Hub vs. Management Cluster Terminology~~ (Resolved)

**Resolution:** The hub cluster and management cluster are the same thing in OSAC's HCP model. The management cluster is the one that runs the Hosted Control Planes operator and creates HostedClusters. The term "hub" is inherited from ACM (Advanced Cluster Management) and refers to the same cluster. This EP uses "management cluster" consistently. PROJECT.md terminology should be unified to match.
