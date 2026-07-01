# Restructure osac-installer as a Production-Only Helm Installer

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor |
| Jira        | N/A — conversation-driven |
| Date        | 2026-07-01 |

## 1. Problem Statement

osac-installer evolved from a developer convenience tool into a repository that attempts to serve developers, CI pipelines, and production deployments simultaneously. The result is a codebase with dual deployment methods (Helm and Kustomize), 15 shell scripts that mix production setup with CI-only concerns, and 5 different configuration surfaces. A Cloud Provider Admin attempting to install OSAC in production cannot determine the supported installation path, must run post-install shell scripts after `helm install`, and has no versioned release to pin against. Without restructuring, every new OSAC deployment is a bespoke scripted process — fragile, unreproducible, and incompatible with production tooling like enclave and ArgoCD.

## 2. Goals and Non-Goals

### 2.1 Goals

- Cloud Provider Admins can install OSAC using a single versioned Helm chart pulled from an OCI registry, with no shell scripts required.
- Cloud Infrastructure Admins can configure backend integrations (networking, storage, identity) entirely through Helm values files, with no post-deploy patching.
- The installer supports deploying different OSAC profiles (CaaS, VMaaS, full-stack) by layering values files, without maintaining separate charts or deployment paths.
- OSAC releases are versioned — each release is a tested, reproducible combination of component chart versions published to an OCI registry.
- The installer supports `helm upgrade` for in-place version upgrades.

### 2.3 Non-Goals

- Developer local/lab installation tooling — moves to osac-test-infra.
- CI/E2E test infrastructure (overlays, CI-specific scripts, remote cluster setup) — moves to osac-test-infra.
- Demo or proof-of-concept environment scripts — moves to osac-test-infra.
- Kustomize as a supported deployment method.
- A BMaaS-specific profile (planned for a future milestone). `[Clarify: R2.Q3]`

## 3. Requirements

### 3.1 Functional Requirements

#### Prerequisites Installation

- **FR-1:** The installer must provide a separate Helm chart for cluster prerequisites (cert-manager, trust-manager, Keycloak, AAP operator, LVMS, MetalLB, CNV, MCE) with per-component enable/disable toggles. `[Clarify: R1.Q1]`
- **FR-2:** Each prerequisite component must default to enabled, allowing production environments where prerequisites are already installed to disable them individually.

#### OSAC Deployment

- **FR-3:** The installer must provide an umbrella Helm chart that composes all OSAC components (osac-operator, fulfillment-service, osac-aap, bare-metal-fulfillment-operator, osac-ui) as versioned sub-chart dependencies pulled from an OCI registry. `[Clarify: R1.Q4]`
- **FR-4:** The umbrella chart must include Helm post-install hook Jobs for imperative operations that cannot be expressed as templates: AAP API token creation, hub cluster registration, AAP project synchronization, template publishing, and initial tenant setup.
- **FR-5:** All configuration currently applied by post-deploy scripts (AAP instance group ConfigMaps and Secrets, Keycloak credentials, network backend settings) must be expressible through Helm values with no external patching required.

#### Deployment Profiles

- **FR-6:** The installer must ship values files for each supported profile: CaaS (cluster provisioning), VMaaS (compute instances), and full-stack (all capabilities). `[Clarify: R2.Q3]`
- **FR-7:** Users must be able to layer profile values with site-specific overrides (e.g., `helm install osac -f profiles/caas.yaml -f my-site.yaml`).

#### Installation Automation

- **FR-8:** The installer must include a CLI wrapper (Makefile or script) that orchestrates the two-phase install: prerequisites chart installation, readiness verification, then OSAC chart installation. `[Clarify: R2.Q2]`

#### Versioning and Distribution

- **FR-9:** Each component repository must publish its Helm chart to an OCI registry with semantic versioning. `[Clarify: R2.Q1]`
- **FR-10:** The umbrella chart version must represent the OSAC release version, with its Chart.yaml pinning specific component chart versions. A release is a tested combination of component versions.
- **FR-11:** The production osac-installer repository must contain only the umbrella chart, profiles, CLI wrapper, and documentation — no Git submodules, no kustomize manifests, no shell scripts beyond the CLI wrapper. `[Clarify: R1.Q4]`

#### Migration

- **FR-12:** The restructuring must be executed incrementally across 5 phases, keeping CI green at each phase boundary: (1) prerequisites chart and profiles, (2) post-install hook Jobs, (3) OCI publishing with semantic versioning, (4) CI/dev script migration to osac-test-infra, (5) kustomize removal.

### 3.2 Non-Functional Requirements

- **NFR-1:** The installer must support `helm upgrade` for in-place OSAC version upgrades. Chart templates must be idempotent and handle pre-existing resources. `[Clarify: R1.Q3]`
- **NFR-2:** The installer must be deployable in air-gapped environments by mirroring the OCI registry. No installation step may require internet access beyond the registry.
- **NFR-3:** CI must validate a full Helm-only deployment (prerequisites + OSAC) on a test cluster with zero scripts as the acceptance test for each phase of the migration. `[Clarify: R2.Q4]`
- **NFR-4:** The Helm values schema (values.schema.json) must validate all required configuration fields at install time, providing clear error messages when mandatory values are missing.

## 4. Acceptance Criteria

- [ ] A Cloud Provider Admin can install OSAC on a clean OpenShift cluster by running `helm install` for the prerequisites chart, then `helm install` for the OSAC chart with a profile values file — no scripts, no kustomize, no manual steps.
- [ ] A Cloud Infrastructure Admin can configure all backend integrations (Netris, ESI, VAST, Keycloak, AAP) through Helm values files alone.
- [ ] The CLI wrapper (`make install PROFILE=caas VALUES=my-site.yaml`) successfully orchestrates a two-phase deployment from a clean cluster to a working OSAC installation.
- [ ] `helm upgrade` from OSAC version N to version N+1 completes without errors and preserves existing tenant data and configuration.
- [ ] The osac-installer repository contains no kustomize files, no Git submodules, and no shell scripts other than the CLI wrapper.
- [ ] CI runs a full Helm-only deployment and verifies OSAC services are healthy without invoking any shell scripts.
- [ ] Each OSAC release is published to the OCI registry with a semantic version and documents the component chart versions it includes.

## 5. Assumptions

- Component repositories (osac-operator, fulfillment-service, osac-aap, bare-metal-fulfillment-operator, osac-ui) will add CI pipelines to publish their Helm charts to the OCI registry with semantic versions. This is a prerequisite for FR-9 and FR-3.
- The existing `publish-charts.yaml` CI workflow can be extended to support semantic versioning and OCI publishing without a full rewrite.
- Post-install imperative operations (AAP token creation, hub registration) can be reliably expressed as Kubernetes Jobs running as Helm hooks, including idempotent retry behavior.

## 6. Dependencies

- **Component repos** — Each component must publish its Helm chart to the OCI registry before the umbrella chart can consume it. FR-3 and FR-9 are blocked until this is in place.
- **osac-test-infra** — Must accept the migrated CI/dev scripts (teardown, snapshot recovery, remote cluster setup, CaaS agent setup) and update its CI workflows to source them from the new location.
- **OCI registry** — A container registry (ghcr.io or equivalent) must be available for publishing and pulling Helm charts.
- **Enclave team** — Must validate that the restructured Helm chart works with enclave's deployment orchestration.

## 7. Risks

### 7.1 CI disruption during migration

Moving CI scripts to osac-test-infra while CI pipelines still reference them in osac-installer could break automated testing.

- **Owner:** OSAC platform team
- **Mitigation:** Phase 4 (script migration) updates CI workflows in the same PR that moves the scripts. Incremental approach ensures each phase is independently validated.

### 7.2 Helm hook Jobs may not cover all imperative operations

Some post-install operations (e.g., hub registration via fulfillment CLI, AAP project sync) involve complex retry logic and external API calls that may be difficult to express as reliable Kubernetes Jobs.

- **Owner:** OSAC platform team
- **Mitigation:** Prototype the most complex hook Job (hub registration) early in Phase 2. If Jobs prove insufficient, evaluate moving these operations into the osac-operator's reconciliation loop as a longer-term alternative.

### 7.3 Component repos not ready for OCI publishing

FR-3 depends on all component repos publishing versioned charts. If any component repo lacks chart publishing CI, the umbrella chart cannot consume it from the registry.

- **Owner:** Component repo maintainers
- **Mitigation:** Track chart publishing readiness per component. The umbrella chart can temporarily use `file://` references for components not yet publishing, with a clear timeline for each to migrate.

## 8. Open Questions

### 8.1 What semantic versioning scheme should components use?

Should component charts follow independent semver (osac-operator 1.2.0, fulfillment-service 2.1.0) or lockstep versioning (all components at 1.0.0 for OSAC 1.0.0)?

- **Owner:** OSAC platform team
- **Impact:** Affects FR-9, FR-10, and the release process. Independent versioning is more flexible but harder to communicate; lockstep is simpler but forces version bumps on unchanged components.

### 8.2 Should the prerequisites chart be published to the same OCI registry?

The prerequisites chart installs third-party operators (cert-manager, Keycloak). Should it be versioned and published alongside the OSAC chart, or maintained as a local chart in the repo?

- **Owner:** OSAC platform team
- **Impact:** Affects FR-1 and the installation workflow. Publishing it enables `helm install osac-prereqs oci://...` in air-gapped environments.
