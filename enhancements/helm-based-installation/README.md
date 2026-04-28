---
title: helm-based-installation
authors:
  - avishayt
creation-date: 2026-04-27
last-updated: 2026-04-27
tracking-link:
  - https://issues.redhat.com/browse/MGMT-24053
see-also:
replaces:
superseded-by:
---

# Helm-Based OSAC Installation

## Summary

Replace the current Kustomize-based installation with a Helm chart to provide a standard, production-ready installation method for OSAC. The Helm chart will use an umbrella chart architecture that composes component-specific charts for fulfillment-service, osac-operator, and osac-aap.

## Motivation

The current installation method uses Kustomize with git submodules to pin component versions. While this works for development and testing, it has limitations for production deployments:

- **No separation between OSAC and prerequisites:** The current installer mixes prerequisite deployment (AAP, cert-manager) with OSAC installation, making it inflexible for environments where prerequisites are managed separately
- **Manual configuration:** Users must manually copy overlays, edit multiple YAML files, and create secrets in specific locations
- **No built-in lifecycle management:** Upgrades and health checks require manual intervention
- **Limited parameter validation:** No pre-install validation of configuration values
- **Non-standard for production:** Helm is the industry-standard packaging format for Kubernetes applications, with better tooling support and ecosystem integration

Helm provides:
- Templating and parameterization through values.yaml
- Built-in lifecycle hooks for pre/post-install and upgrade operations
- Version management capabilities
- Package repository support for distribution
- Dependency management between components
- Validation and testing frameworks

### User Stories

**As a Cloud Service Provider admin**, I want to install OSAC using a standard Helm command, so that I can deploy OSAC with a single operation rather than manually editing multiple configuration files.

**As a Cloud Service Provider admin**, I want to install OSAC through the OpenShift console UI, so that I can configure OSAC using a form-based interface with validation and tooltips rather than editing YAML files.

**As a Cloud Service Provider admin**, I want to upgrade OSAC components safely, so that database migrations and configuration updates happen automatically in the correct order.

**As a Cloud Service Provider admin**, I want installation errors caught before deployment starts, so that I can fix configuration issues before affecting the running system.

**As a platform engineer**, I want OSAC components independently versioned, so that I can update individual components without redeploying the entire stack.

### Goals

- **Separate OSAC installation from prerequisite deployment:** Helm chart installs OSAC components, with optional bundled PostgreSQL/Keycloak (non-HA) for simplified deployments, while prerequisite operators (AAP, cert-manager) must be installed separately
- **Make installation available via OpenShift Software Catalog:** Provide form-based installation UI in the OpenShift console for ease of use
- Provide Helm charts for all OSAC components (fulfillment-service, osac-operator, osac-aap)
- Create an umbrella chart that composes component charts with proper dependency ordering
- Support both development workflows (git submodules with `file://` chart references) and production workflows (OCI registry with versioned charts)
- Handle database migrations during upgrades through Helm hooks
- Validate prerequisites and configuration before installation
- Separate CRD lifecycle from operator lifecycle

### Non-Goals

- Migrate existing Kustomize installations to Helm (clean install only, as OSAC is pre-GA)
- Install prerequisite operators (AAP, cert-manager, etc.) - these remain out of scope
- **Deploy AAP operator or instance** - AAP (operator and instance) is a prerequisite, managed separately from OSAC installation
- **Provide HA PostgreSQL or Keycloak** - bundled PostgreSQL/Keycloak are single-replica (not HA):
  - Suitable for deployments where downtime risk is acceptable
  - For high-availability requirements, use external PostgreSQL/Keycloak instances
- Support multi-cluster installation in a single Helm release

## Proposal

Introduce a Helm-based installation architecture with the following structure:

```
osac-installer/
  charts/
    osac/                          # Umbrella chart
      Chart.yaml                   # Defines dependencies on component charts
      values.yaml                  # Default configuration
      templates/
        namespace.yaml
        secrets.yaml               # Auto-generated secrets

Component repositories maintain their own charts:
  fulfillment-service/charts/service/    # Already exists
  osac-operator/charts/operator-crds/    # New: CRD chart
  osac-operator/charts/operator/         # New: Operator chart
  osac-aap/charts/aap/                   # New: AAP configuration chart
```

### Workflow Description

**CSP Administrator** is the human user responsible for installing and operating OSAC.

#### Initial Installation

1. **CSP Administrator** ensures prerequisites are installed:
   - AAP operator and instance (licensed and running)
   - cert-manager
   - StorageClass with ReadWriteMany (RWX) support (required for VM live migration - e.g., NFS, Ceph, enterprise SAN)
   - Optional: OpenShift Virtualization (for VM support)
   - Optional: Red Hat Advanced Cluster Management (for cluster provisioning)

   **Note:** PostgreSQL and Keycloak can be deployed by the Helm chart (see step 3) or provided externally for high-availability requirements. The automated setup script (for dev/test) can deploy NFS storage provisioner, but production environments should use enterprise-grade storage.

2. **CSP Administrator** creates required secrets:
   ```bash
   # AAP credentials for fulfillment-service to call AAP
   kubectl create secret generic aap-credentials \
     --from-literal=url=https://aap.example.com \
     --from-literal=token=<aap-api-token> \
     -n osac

   # PostgreSQL connection (if using external database - optional if using bundled)
   kubectl create secret generic postgres-credentials \
     --from-literal=url=postgresql://user:pass@postgres.example.com:5432/osac \
     -n osac
   ```

3. **CSP Administrator** customizes installation via values file:

   **Option A: Using external PostgreSQL and Keycloak (HA recommended)**
   ```yaml
   # values.yaml
   aap:
     url: "https://aap.example.com"
     credentials:
       secretName: aap-credentials

   fulfillment-service:
     externalHostname: "osac-api.example.com"
     auth:
       issuerUrl: "https://keycloak.example.com/realms/osac"
     database:
       connection:
         secret:
           name: postgres-credentials
           key: url
     # Disable bundled components
     postgres:
       enabled: false
     keycloak:
       enabled: false
   ```

   **Option B: Using bundled PostgreSQL and Keycloak (non-HA)**
   ```yaml
   # values.yaml
   aap:
     url: "https://aap.example.com"
     credentials:
       secretName: aap-credentials

   fulfillment-service:
     externalHostname: "osac-api.example.com"
     # Enable bundled components (single replica, not HA)
     postgres:
       enabled: true
     keycloak:
       enabled: true
   ```

4. **CSP Administrator** installs OSAC:
   ```bash
   helm install osac oci://ghcr.io/osac-project/charts/osac \
     --version 1.0.0 \
     --namespace osac \
     --create-namespace \
     --values values.yaml
   ```

5. **Helm** executes installation in this order:
   - Pre-install hooks validate prerequisites (AAP reachable, cert-manager installed, StorageClass with RWX support available for VM live migration)
   - Install CRDs (from operator-crds chart)
   - Install operators and services
   - Deploy PostgreSQL and Keycloak (if enabled) or validate external instances are reachable
   - Deploy fulfillment-service
   - Deploy osac-operator
   - Deploy osac-aap
   - Post-install hook runs aap-bootstrap job to load OSAC automation into AAP
   - Post-install hook runs smoke tests (if enabled via values.yaml)

6. **CSP Administrator** verifies installation:
   ```bash
   helm status osac -n osac
   kubectl get pods -n osac
   ```

7. **CSP Administrator** registers management hub clusters (operational, not installation):
   ```bash
   osac-admin create hub --id prod-hub-01 \
     --kubeconfig /path/to/hub.kubeconfig \
     --namespace cloudkit-provisioning
   ```

#### Upgrade Workflow

1. **CSP Administrator** reviews release notes for new version

2. **CSP Administrator** upgrades OSAC:
   ```bash
   helm upgrade osac oci://ghcr.io/osac-project/charts/osac \
     --version 1.1.0 \
     --namespace osac \
     --values values.yaml
   ```

3. **Helm** executes upgrade in this order:
   - Pre-upgrade hook runs database migration job (new `fulfillment-service migrate` command)
   - Updates CRDs (if needed)
   - Rolling update of fulfillment-service deployment
   - Updates osac-operator
   - Updates osac-aap configuration

4. **CSP Administrator** verifies upgrade:
   ```bash
   helm status osac -n osac
   kubectl get pods -n osac
   ```

### API Extensions

This enhancement does not add or modify API extensions. It changes the installation method but not the APIs themselves.

### Implementation Details/Notes/Constraints

#### Component Chart Structure

**fulfillment-service** (already has Helm chart):
- `charts/service/` - Main service chart
- `charts/postgres/` - PostgreSQL (optional subchart, single replica, non-HA)
- `charts/keycloak/` - Keycloak (optional subchart, single replica, non-HA)
- `charts/ca/` - Certificate authority (optional subchart)

**osac-operator** (new charts):
- `charts/operator-crds/` - CRD definitions only
  - Installed before operator
  - Never deleted (to protect user data)
  - Updated independently from operator
- `charts/operator/` - Operator deployment
  - Depends on CRDs existing
  - Includes RBAC, deployment, config

**osac-aap** (new chart):
- `charts/aap/` - AAP configuration
  - Deploys playbooks, collections, rulebooks as ConfigMaps
  - Creates bootstrap job as post-install hook
  - Does NOT deploy AAP instance (prerequisite)
  - Does NOT handle AAP license (prerequisite)

**osac umbrella chart**:
- Declares dependencies on all component charts
- Provides unified configuration interface
- Manages secrets for OSAC-owned services
- Validates prerequisites through pre-install hooks

#### Deployment Flexibility

**External PostgreSQL/Keycloak (HA):**
- Connect to separately managed instances via credentials
- Recommended for zero-downtime requirements
- Set `postgres.enabled=false`, `keycloak.enabled=false`

**Bundled PostgreSQL/Keycloak (Simplified):**
- Deploy as subcharts (single replica, NOT HA)
- Suitable for dev/test, small deployments, or where downtime is acceptable
- Set `postgres.enabled=true`, `keycloak.enabled=true`

**AAP (Always External):**
- Must be deployed before OSAC installation
- Often shared infrastructure, complex multi-component deployment
- Out of scope for OSAC Helm chart

**Automated Setup Script:** Optional tooling for end-to-end deployment (installs prerequisites including NFS storage provisioner, AAP, calls Helm with bundled PostgreSQL/Keycloak enabled and smoke tests enabled, optionally registers hub, creates test tenants). Suitable for dev/test environments. Production deployments should use external storage, PostgreSQL, and Keycloak.

#### Umbrella Chart Dependencies

```yaml
# charts/osac/Chart.yaml
apiVersion: v2
name: osac
description: Open Sovereign AI Cloud
type: application
version: 1.0.0

dependencies:
  - name: operator-crds
    version: "1.0.0"
    repository: "oci://ghcr.io/osac-project/charts"
    condition: operator.enabled

  - name: operator
    version: "1.0.0"
    repository: "oci://ghcr.io/osac-project/charts"
    condition: operator.enabled

  - name: service
    version: "1.0.0"
    repository: "oci://ghcr.io/osac-project/charts"
    alias: fulfillment-service
    condition: fulfillment-service.enabled

  - name: aap
    version: "1.0.0"
    repository: "oci://ghcr.io/osac-project/charts"
    condition: aap.enabled
```

For development with git submodules:
```yaml
# charts/osac/Chart.yaml (development variant)
dependencies:
  - name: operator-crds
    version: "*"
    repository: "file://../../base/osac-operator/charts/operator-crds"
  - name: operator
    version: "*"
    repository: "file://../../base/osac-operator/charts/operator"
  - name: service
    version: "*"
    repository: "file://../../base/osac-fulfillment-service/charts/service"
    alias: fulfillment-service
  - name: aap
    version: "*"
    repository: "file://../../base/osac-aap/charts/aap"
```

#### Secret Management

**Required secrets (both scenarios):**
- AAP credentials: URL and API token
- OCI registry credentials: For VM image management

**External PostgreSQL/Keycloak:**
- PostgreSQL connection secret with database URL
- Keycloak issuer URL in values.yaml
- Set `postgres.enabled=false`, `keycloak.enabled=false`

**Bundled PostgreSQL/Keycloak:**
- Helm auto-generates database passwords using `randAlphaNum`
- Set `postgres.enabled=true`, `keycloak.enabled=true`
- AAP and registry credentials still required

#### Database Migration Strategy

Add new `migrate` subcommand to fulfillment-service:
```bash
fulfillment-service migrate --db-url postgres://...
```

This command:
- Runs all pending migrations from `internal/database/migrations/`
- Exits 0 on success, non-zero on failure
- Is idempotent (safe to run multiple times)

Helm pre-upgrade hook runs a Job that executes `./fulfillment-service migrate` with database credentials from the secret. If migration fails, the upgrade is blocked.

#### AAP Bootstrap Job

The existing `aap-bootstrap` job becomes a Helm post-install hook: a Job that waits for AAP availability, then runs `ansible-playbook cloudkit.config_as_code.configure` with 15 retry attempts.

Scope of bootstrap:
- Create AAP Projects pointing to osac-aap Git repository
- Create AAP Job Templates for VM/cluster provisioning
- Create AAP Execution Environments
- Configure credentials, inventories, etc.

NOT in scope:
- AAP license activation (prerequisite)
- AAP instance creation (prerequisite)

#### Optional Smoke Tests

The Helm chart supports optional post-install smoke tests controlled by `values.yaml`:

```yaml
smokeTests:
  enabled: false  # Default: disabled for production
```

When enabled (`smokeTests.enabled: true`), a post-install hook Job runs basic verification:
- Wait for fulfillment-service ready
- Create test tenant via API
- Create test VirtualNetwork via API
- Verify operator reconciles resources
- Clean up test resources
- Report results in Job logs

**Use cases:**
- **Development/demo**: Enable smoke tests for immediate installation feedback
- **Production**: Disable smoke tests (default) - avoid auto-creating test resources
- **CI/CD**: Enable smoke tests to validate deployment pipeline

The automated setup script enables smoke tests by default. Manual production installations should leave them disabled.

#### CRD Lifecycle Management

**Separate CRD chart** prevents accidental deletion and allows independent updates. CRDs include `"helm.sh/resource-policy": keep` annotation to prevent Helm from deleting them on chart uninstall, protecting user data (all VM/cluster CRs).

Upgrade process:
1. `operator-crds` chart updated with new fields
2. `operator` chart updated to use new fields
3. Helm dependency ordering ensures CRDs update before operator

#### CLI Restructuring

Create new `osac-admin` CLI for platform operations:

**osac CLI** (tenant users):
- `osac create compute-instance`
- `osac create cluster`
- `osac list compute-instances`
- `osac delete cluster`

**osac-admin CLI** (platform admins):
- `osac-admin create hub` - Register RHACM hub for cluster provisioning
- `osac-admin create tenant` - Create tenant namespace/isolation
- `osac-admin create host-pool` - Add compute capacity
- `osac-admin list hubs`

Hub registration is operational (adding capacity), not part of installation. Automated setup scripts can automate `osac-admin create hub` for testing environments.

#### Distribution and Versioning

**Development workflow:**
- Git submodules in osac-installer pin component commits
- `file://` chart references in umbrella Chart.yaml
- `helm dependency build` reads charts from submodule paths
- Used for local development and CI

**Release workflow:**
- Component repos tag releases (e.g., `v1.2.3`)
- CI publishes charts to `oci://ghcr.io/osac-project/charts/<component>:1.2.3`
- osac-installer umbrella chart references OCI charts by version
- Production installations use OCI registry, not git

**Independent consumption:**
Users can install individual components:
```bash
# Install only fulfillment-service (without operator/aap)
helm install fulfillment oci://ghcr.io/osac-project/charts/service \
  --version 1.2.3
```

#### OpenShift Software Catalog Integration

The umbrella chart will be available in the OpenShift Software Catalog for form-based installation via the console UI.

**Requirements:**
- **values.schema.json** - JSON Schema defining configuration parameters (AAP URL, credentials, external hostname, enable/disable PostgreSQL/Keycloak)
- **Chart.yaml annotations** - Catalog metadata (provider, support URL, architecture, display name)
- **README.md** and logo - Documentation and icon for catalog UI

**User Workflow:**
1. Navigate to OpenShift console → Developer Catalog → Helm Charts
2. Search for "OSAC", click Install
3. Fill form with AAP credentials, hostname, PostgreSQL/Keycloak options
4. Install and monitor via Helm Releases view

**Benefits:** Discoverability, form validation, consistent with OpenShift operational patterns

#### Testing Strategy

**Component-level tests** (each repository):
- fulfillment-service already has integration tests that deploy via Helm
- osac-operator adds similar tests for its charts
- osac-aap tests bootstrap job against mock AAP

**Integration tests** (osac-installer):
- Deploy umbrella chart to kind cluster
- Verify all components running
- Smoke tests: create VM, create cluster
- Test upgrade path: install v1.0, upgrade to v1.1

Test matrix:
- OpenShift 4.18+ (production target)
- Kubernetes 1.29+ with kind (development/CI)

### Risks and Mitigations

#### Risk: Helm learning curve for contributors

**Mitigation:**
- Comprehensive documentation and examples
- Keep Kustomize in component repos for development (operator-sdk generates it)
- Helm is only for final distribution, not day-to-day development

#### Risk: CRD upgrade failures

**Mitigation:**
- Separate CRD chart with `keep` annotation prevents deletion
- Pre-upgrade validation hook checks CRD compatibility
- Documented manual CRD upgrade process for complex changes
- Rolling updates for operator ensure CRD/operator version skew is bounded

#### Risk: Database migration failures during upgrade

**Mitigation:**
- Pre-upgrade hook runs migration as dedicated Job (not in pod lifecycle)
- Job failure blocks deployment update
- Migrations are idempotent and tested in CI
- Migrations are forward-only (no rollback) - schema changes must be backward-compatible
- Breaking schema changes require major version bump with documented manual migration path

#### Risk: Breaking changes between Kustomize and Helm

**Mitigation:**
- No migration path from Kustomize to Helm (clean install only)
- OSAC is pre-GA, no production deployments to migrate
- Development installations can be recreated
- Kustomize remains in repos for development, Helm is for distribution

#### Risk: Secrets management complexity

**Mitigation:**
- Auto-generate secrets for OSAC-managed services (good defaults)
- Support external secret references for prerequisites (flexible)
- Document integration with external secret operators (Vault, AWS Secrets Manager)
- Clear error messages when required secrets are missing

#### Risk: Helm hooks failing silently

**Mitigation:**
- Hook jobs have clear names and labels for debugging
- Hooks use `hook-delete-policy: before-hook-creation` to preserve failed jobs
- Pre-install hooks validate prerequisites before any resources are created
- Post-install hooks have retry logic (backoffLimit)

### Drawbacks

**Increased complexity:** Adds Helm as a dependency and introduces chart maintenance overhead across multiple repositories.

**Migration effort:** Existing Kustomize users must recreate installations (mitigated by pre-GA status).

**Two packaging formats:** Kustomize remains for development (operator-sdk default), Helm for distribution. However, this is common practice (e.g., cert-manager, prometheus-operator) and provides the best of both worlds.

**Chart testing burden:** Requires testing Helm charts in addition to application code. However, this is offset by better integration testing capabilities and validates the actual deployment path.

## Alternatives (Not Implemented)

**Keep Kustomize Only:** Rejected because manual configuration, no lifecycle hooks, no parameter validation, non-standard for production.

**Use operator-sdk bundle/OLM:** Rejected because OSAC is a multi-component platform (not a single operator), OLM not available on all Kubernetes distributions, doesn't fit umbrella architecture.

**Ansible-based installer:** Rejected because requires Ansible runtime on admin workstation, no native Kubernetes resource management, doesn't integrate with GitOps. Ansible remains for AAP-based resource provisioning, not platform installation.

## Open Questions

None. All design questions have been resolved.

## Test Plan

### Unit Tests

Each component chart includes template tests:
```bash
helm lint charts/operator
helm template test charts/operator --values test-values.yaml
```

### Integration Tests

**Component level** (fulfillment-service, osac-operator, osac-aap):
- Deploy chart to kind cluster
- Verify resources created correctly
- Run component-specific smoke tests

**Full stack** (osac-installer):
- Use automated setup script to deploy prerequisites and OSAC to kind cluster
- Deploy umbrella chart with bundled PostgreSQL/Keycloak enabled
- Verify all components running and healthy
- Smoke tests:
  - Create ComputeInstance via API
  - Create VirtualNetwork via API
  - Verify operator reconciles resources
- Upgrade test:
  - Install version N
  - Upgrade to version N+1
  - Verify migration ran and components updated

### End-to-End Tests

Deploy to real OpenShift cluster with full prerequisites:
- OpenShift 4.18+
- AAP operator and instance
- RHACM for cluster provisioning
- OpenShift Virtualization for VMs

Test full workflows:
1. **Install OSAC via Helm CLI**
2. Register management hub via `osac-admin create hub`
3. Create tenant via `osac-admin create tenant`
4. As tenant user, create VM via `osac create compute-instance`
5. Verify VM runs on cluster
6. As tenant user, create OpenShift cluster via `osac create cluster`
7. Verify cluster provisions via RHACM
8. Upgrade OSAC to new version
9. Verify existing VMs/clusters continue running
10. Verify upgraded components functional

### OpenShift Console UI Tests

Validate installation through OpenShift Software Catalog:
1. **Navigate to OpenShift console** → Developer Catalog → Helm Charts
2. **Search for "OSAC"** chart
3. **Verify chart metadata** displays correctly (description, logo, version)
4. **Click Install** and verify form-based UI appears
5. **Test form validation:**
   - Required fields show errors when empty
   - URL fields validate format
   - Tooltips display on hover
6. **Fill form** with valid AAP credentials and configuration
7. **Install** and verify Helm release created
8. **Monitor installation** via Helm Releases view in console
9. **Verify all pods running** in installed namespace
10. **Test upgrade** via console UI: update externalHostname value, save
11. **Verify rolling update** completes successfully

## Graduation Criteria

This enhancement targets GA (general availability) for OSAC 1.0.

**Alpha:** Not applicable - direct to GA since OSAC is pre-GA and this is installation method, not feature.

**GA criteria:**
- Helm charts available for all components (fulfillment-service, osac-operator, osac-aap)
- Umbrella chart published to OCI registry
- **OpenShift Software Catalog integration complete:**
  - values.schema.json provides form-based configuration UI
  - Chart metadata and logo included
  - Tested installation via OpenShift console
- Automated setup script available for end-to-end deployment
- Documentation includes:
  - Installation guide with prerequisites
  - Deployment scenarios guide (bundled vs external PostgreSQL/Keycloak)
  - OpenShift console installation guide
  - Automated setup script guide
  - Upgrade guide with failure recovery procedures
  - Troubleshooting guide for common installation issues
  - Values.yaml reference for all configuration options
- CI/CD pipeline publishes charts on release tags
- Integration tests pass for OpenShift 4.18+ and Kubernetes 1.29+
- At least one production deployment successfully installed via Helm (CLI or console)
- Migration from Kustomize documented (clean install approach)

## Upgrade / Downgrade Strategy

### Initial Installation

OSAC 1.0 will be Helm-only. No upgrade from Kustomize installations is supported.

Existing Kustomize users must:
1. Export data if needed (tenant VMs, cluster definitions)
2. Uninstall Kustomize deployment
3. Install via Helm
4. Re-import data

Since OSAC is pre-GA, no production deployments exist requiring migration. Development installations can be recreated.

### Helm-to-Helm Upgrades

**Patch version upgrades** (1.0.0 → 1.0.1):
- Bug fixes, no schema changes
- `helm upgrade osac ...`
- No manual intervention required
- Automatic rollout of updated containers

**Minor version upgrades** (1.0.0 → 1.1.0):
- New features, possible schema changes
- Pre-upgrade hook runs database migrations
- `helm upgrade osac ...`
- Review release notes for breaking changes
- May require updating values.yaml for new configuration options

**Major version upgrades** (1.0.0 → 2.0.0):
- Breaking API changes
- May require manual steps (documented in release notes)
- `helm upgrade osac ...`
- Follow upgrade guide in documentation

## Version Skew Strategy

During upgrades, components briefly run at different versions (maximum supported skew: 1 minor version).

**Control plane:**
- fulfillment-service and osac-operator upgraded together, tolerate N and N+1 communication
- Database migrations forward-compatible (new columns nullable, no drops)
- CRDs updated before operator, operator supports N and N+1 CRD versions
- APIs use protobuf backward compatibility (add fields, never remove)

**Compute plane:**
- VMs and clusters continue running during control plane upgrades
- Existing resources function with old spec, new fields optional

**AAP:**
- Post-upgrade hook updates projects/templates
- Jobs idempotent (safe to retry during version skew)

## Support Procedures

### Common Failure Modes

**Installation failures:**
- Pre-install hook validates AAP reachable, cert-manager installed
- Check hook status: `kubectl get jobs -n osac -l "helm.sh/hook=pre-install"`
- Common issues: AAP unreachable, missing secrets, cert-manager not installed
- Resolution: Fix issue, `helm uninstall`, retry with corrected values

**Upgrade failures:**
- Pre-upgrade migration job runs before deployment updates
- Check migration: `kubectl logs -n osac job/osac-service-migrate`
- Common issues: Database connectivity, CRD version mismatch, image pull failures
- Resolution: Fix database issue, manually apply CRDs if needed, retry upgrade

**Runtime failures:**
- AAP bootstrap job failed: Check `kubectl logs -n osac job/osac-aap-bootstrap`
- fulfillment-service CrashLoop: Check database connection in values.yaml
- ComputeInstance stuck Pending: Check AAP credentials and operator logs

### Component Management

Disable components via Helm upgrade:
- `--set fulfillment-service.enabled=false` - API unavailable, existing workloads continue
- `--set operator.enabled=false` - No reconciliation, existing workloads continue
- AAP cannot be disabled (prerequisite)

### Recovery

- **Migration failure:** Job blocks upgrade, fix database and retry
- **Bootstrap failure:** Retries 15 times, manually delete job to recreate
- **CRD issues:** `helm.sh/resource-policy: keep` prevents deletion, manually apply CRDs

## Infrastructure Needed

### GitHub

- OCI registry publication access (ghcr.io/osac-project/charts)
- CI/CD workflows for chart linting, testing, publishing
- Branch protection for chart directories

### CI/CD

- Kind cluster for integration tests
- Helm 3.12+ in CI environment
- Chart testing (ct) tool
- Access to image registries for pulling test images

### Documentation

- New "Installation Guide" section in osac-docs
- OpenShift console installation guide with screenshots
- Helm chart README.md files for each component
- values.yaml comments documenting all options
- Troubleshooting guide for common Helm issues

### OpenShift Software Catalog

- values.schema.json for each component chart
- Chart metadata (annotations, keywords) for catalog listing
- Logo/icon assets (PNG format, multiple sizes)
- OCI registry accessible from OpenShift clusters
- Optional: Custom CatalogSource for enterprise installations

### Automated Setup Tooling

- Automated setup script (e.g., `scripts/setup.sh` in osac-installer) for end-to-end deployment
  - Installs prerequisite operators on kind/OpenShift
  - Creates and configures AAP instance
  - Calls Helm chart with bundled PostgreSQL/Keycloak enabled
  - Registers local cluster as hub
  - Creates test tenants
- Uses same Helm chart as manual installations, just with different values
