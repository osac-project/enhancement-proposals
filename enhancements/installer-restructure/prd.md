# OSAC Installer: Structured Helm-Based Installation

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor |
| Jira        | N/A — conversation-driven |
| Date        | 2026-07-02 |

## 1. Problem Statement

OSAC deploys across multiple clusters — a management cluster (fulfillment-service, AAP), regional hub clusters (osac-operator), and optionally dedicated workload clusters (VMaaS dedicated mode). Today, installing OSAC requires navigating a repository that mixes production deployment artifacts with developer scripts and CI tooling, uses multiple configuration surfaces (Helm values, environment variables, `.env` files, post-deploy script patching), and requires shell scripts to run after `helm install` to complete the setup. A Cloud Provider Admin cannot install OSAC from the Helm chart alone, has no versioned release to pin against, and must understand which scripts to run and in what order. The chart structure does not reflect the multi-cluster deployment topology, making it unclear what to install where.

## 2. Goals and Non-Goals

### 2.1 Goals

- Cloud Provider Admins can install OSAC using versioned Helm charts with no shell scripts required — `helm install` is the complete installation interface.
- The chart structure reflects OSAC's deployment topology, so it is clear what to install on each cluster (management, hub, workload).
- Cloud Infrastructure Admins can configure all backend integrations (networking, storage, identity) entirely through Helm values.
- The installer supports different deployment profiles (CaaS, VMaaS, VMaaS dedicated-cluster, full-stack, BMaaS) through composable values files.
- OSAC releases are versioned — each release is a tested, reproducible combination of component versions.
- The installer supports `helm upgrade` for in-place version upgrades.

### 2.3 Non-Goals

- CI/E2E test infrastructure (CI-specific overlays, remote cluster setup scripts) — managed in osac-test-infra.
- Demo or proof-of-concept environment scripts — managed in osac-test-infra.

## 3. Requirements

### 3.1 Functional Requirements

#### Deployment Topology

- **FR-1:** The installer must provide Helm charts that align with OSAC's multi-cluster deployment boundaries. Each cluster type (management, hub, workload) must be installable with a single `helm install` command producing a complete manifest for that cluster. `[User: sk-ilya review, rccrdpccl review]`
- **FR-2:** For single-cluster development and testing environments, the charts must be installable together on one cluster with appropriate values.
- **FR-3:** The same charts must be usable across all environments (production, development, CI) — environment differences are expressed through values, not different charts or tools. `[User: rccrdpccl review]`

#### Prerequisites

- **FR-4:** Cluster prerequisites (cert-manager, trust-manager, Keycloak, AAP operator, LVMS, MetalLB, CNV, MCE) must be installable as optional components with per-component enable/disable toggles (e.g., `certManager.enabled: true`). `[Clarify: R1.Q1]`
- **FR-5:** The installer should aim for a single `helm install` experience where prerequisites that are not already present on the cluster can be included in the installation, avoiding a mandatory two-step process. `[User: rccrdpccl review]`

#### Configuration

- **FR-6:** All configuration currently applied by post-deploy scripts (AAP instance group settings, Keycloak credentials, network backend settings, hub registration) must be expressible through Helm values with no external patching required.
- **FR-7:** Post-install imperative operations (AAP API token creation, hub registration, template publishing, tenant setup) must complete automatically as part of the installation without manual script execution.

#### Deployment Profiles

- **FR-8:** The installer must define deployment profiles for supported configurations: CaaS (cluster provisioning), VMaaS (compute instances), VMaaS dedicated-cluster mode, BMaaS (bare metal), and full-stack (all capabilities). `[User: sk-ilya review, rccrdpccl review]`
- **FR-9:** Users must be able to compose profiles with site-specific overrides to customize their deployment.
- **FR-10:** Profile definitions must be distributable separately from the packaged chart, since published Helm packages do not bundle arbitrary values files. `[User: rccrdpccl review]`

#### Versioning and Distribution

- **FR-11:** OSAC releases must be versioned with semantic versioning. Each release represents a tested combination of component versions.
- **FR-12:** Component charts must be publishable to an OCI registry, enabling air-gapped deployments via registry mirroring.
- **FR-13:** Chart versions must have a clear relationship to their container image versions. Semver must be enforced across both charts and images to ensure smooth lifecycle management (install, upgrade, rollback). `[User: rccrdpccl review]`

#### Secret Management

- **FR-14:** The installer must define a strategy for how secrets (AAP credentials, network backend passwords, SSH keys, Keycloak configuration, cloud provider credentials) are provided to the Helm chart at install time. `[User: rccrdpccl review]`
- **FR-15:** The secret management approach must support both manual pre-creation (user creates secrets before helm install) and integration with external secret management systems (e.g., External Secrets Operator, Vault).

#### Chart Ownership

- **FR-16:** Each chart must have a clearly defined owning team responsible for its maintenance, versioning, and release lifecycle. `[User: rccrdpccl review]`

#### Repository Scope

- **FR-17:** The osac-installer repository must contain only production installation artifacts (charts, profiles, documentation). CI-only scripts, developer convenience scripts, and teardown tooling belong in osac-test-infra.

### 3.2 Non-Functional Requirements

- **NFR-1:** The installer must support `helm upgrade` for in-place OSAC version upgrades. Templates must be idempotent and handle pre-existing resources.
- **NFR-2:** The installer must be deployable in air-gapped environments. No installation step may require internet access beyond the chart and image registries.
- **NFR-3:** CI must validate that a full deployment from Helm charts alone (no scripts) produces a healthy OSAC installation.
- **NFR-4:** The Helm values schema must validate required configuration fields at install time, providing clear error messages when mandatory values are missing.
- **NFR-5:** The installer must be compatible with GitOps deployment tools (ArgoCD, Flux). Charts must produce valid manifests via `helm template` without requiring Helm hooks or other lifecycle features that GitOps tools do not support well. `[User: rccrdpccl review]`

## 4. Acceptance Criteria

- [ ] A Cloud Provider Admin can install OSAC on a clean OpenShift cluster using `helm install` with a profile values file — no scripts, no manual steps beyond providing site-specific values.
- [ ] A Cloud Infrastructure Admin can configure all backend integrations (Netris, ESI, VAST, Keycloak, AAP) through Helm values alone.
- [ ] The chart structure makes it clear which components install on management, hub, and workload clusters.
- [ ] The same chart works for both single-cluster dev environments and multi-cluster production topologies, differentiated only by values.
- [ ] `helm upgrade` from OSAC version N to version N+1 completes without errors and preserves existing configuration.
- [ ] CI runs a full Helm-only deployment and verifies OSAC services are healthy without invoking any shell scripts.
- [ ] Each OSAC release is published with a semantic version and documents the component versions it includes.
- [ ] `helm template` produces a valid, complete manifest for each cluster type without relying on hooks.
- [ ] Secrets can be provided via pre-created Kubernetes secrets or via an external secrets integration.

## 5. Assumptions

- Component repositories (osac-operator, fulfillment-service, osac-aap, bare-metal-fulfillment-operator, osac-ui) will add CI pipelines to publish their Helm charts with semantic versions.
- Post-install imperative operations (AAP token creation, hub registration) can be reliably automated within the Helm installation lifecycle.

## 6. Dependencies

- **Component repos** — Each component must publish its Helm chart before the installer can consume versioned dependencies.
- **osac-test-infra** — Must accept migrated CI/dev scripts and update its workflows accordingly.
- **OCI registry** — A container registry must be available for publishing and pulling Helm charts.
- **Enclave team** — Must validate that the restructured charts work with enclave's deployment orchestration.

## 7. Risks

### 7.1 Multi-cluster chart boundaries are complex

Defining clean chart boundaries across management, hub, and workload clusters requires careful design. Shared resources (CRDs, cluster-scoped RBAC) must be handled without duplication or conflicts.

- **Owner:** OSAC platform team
- **Mitigation:** Prototype multi-cluster chart separation with CaaS (management + hub) before tackling VMaaS dedicated-cluster mode.

### 7.2 Imperative post-install operations may be difficult to automate

Some post-install operations (hub registration, AAP project sync) involve external API calls with retry logic. Helm hooks are one approach but conflict with GitOps/ArgoCD compatibility (NFR-5). Moving these into operator reconciliation loops is more GitOps-friendly but requires more development.

- **Owner:** OSAC platform team
- **Mitigation:** Evaluate operator-driven reconciliation as the primary approach, since it aligns with both GitOps compatibility and Kubernetes-native patterns. Prototype the most complex operation early.

### 7.3 Component repos not ready for versioned publishing

The installer depends on all component repos publishing versioned charts. If any component lacks this, the installer cannot consume it from the registry.

- **Owner:** Component repo maintainers
- **Mitigation:** Track chart publishing readiness per component. Allow temporary local references during the transition.

## 8. Open Questions

### 8.1 How should charts be structured across clusters?

Should the installer provide one chart per cluster type (management chart, hub chart, workload chart), a single umbrella with cluster-targeting values, or a hybrid approach? Production deployments span multiple independently-maintained clusters, while dev environments run everything on one.

- **Owner:** OSAC platform team
- **Impact:** Affects FR-1, FR-2, and the overall chart architecture. This is the most significant design decision for the EP.

### 8.2 What semantic versioning scheme should components use?

Should component charts follow independent semver (osac-operator 1.2.0, fulfillment-service 2.1.0) or lockstep versioning (all at 1.0.0 for OSAC 1.0.0)?

- **Owner:** OSAC platform team
- **Impact:** Affects FR-11 and the release process.

### 8.3 How should deployment profiles be distributed?

Published Helm packages do not bundle arbitrary values files. Should profiles live in a separate repository, be published as OCI artifacts, or be documented as reference configurations?

- **Owner:** OSAC platform team
- **Impact:** Affects FR-10 and the user experience for selecting a deployment configuration.

### 8.4 Who owns each chart?

Should component charts be maintained by the component team (osac-operator team owns the operator chart) or centrally by the installer/platform team? How are dependency-of-dependency charts managed?

- **Owner:** OSAC platform team
- **Impact:** Affects FR-16 and the release coordination process.

### 8.5 What is the secret management strategy?

How should secrets be provided at install time? Options include: manual pre-creation, Helm values with sops-encrypted files, External Secrets Operator, HashiCorp Vault integration. The strategy must work for both initial install and day-2 secret rotation.

- **Owner:** OSAC platform team (cc @trewest)
- **Impact:** Affects FR-14, FR-15, and the overall security posture.

### 8.6 Should prerequisites be subcharts or a separate chart?

Including prerequisites as optional subcharts within the main chart(s) enables a single `helm install`. A separate chart gives more flexibility for environments where prerequisites are already managed externally.

- **Owner:** OSAC platform team
- **Impact:** Affects FR-4, FR-5, and the installation workflow complexity.
