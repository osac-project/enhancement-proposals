# Unified OSAC Test Infrastructure

| Field       | Value   |
|-------------|---------|
| Author(s)   | Dan Manor |
| Jira        |         |
| Date        | 2026-07-05 |

## 1. Problem Statement

OSAC test infrastructure is fragmented across three places: osac-test-infra (E2E tests), netris-test-infra (Netris lab provisioning), and Prow step scripts in openshift/release (cluster-tool and baremetal provisioning logic). This creates fragmented CI ownership, duplicated patterns, and forces contributors to navigate multiple repos and CI config to work with a single test flow. Infrastructure provisioning logic for cluster-tool and baremetal exists only as inline shell scripts in Prow step definitions, making it untestable locally and invisible to developers outside the CI system. Adding a new infrastructure backend or test suite requires changes across multiple repos with no shared contract, making the system brittle and hard to extend.

## 2. Goals and Non-Goals

### 2.1 Goals

- A single repo provisions infrastructure and runs E2E tests for all OSAC service models (VMaaS, CaaS, BMaaS).
- Infrastructure backends are pluggable — adding a new backend requires implementing a defined contract, not modifying test code.
- Test suites are infrastructure-agnostic — they run the same way regardless of which backend provisioned the cluster.
- Infrastructure and OSAC deployment are independently destroyable, allowing OSAC iteration without full reprovisioning.

### 2.3 Non-Goals

- Rewriting existing Ansible roles or test code — existing implementations move as-is.
- Unifying secret management across CI systems (Vault, Prow cluster profiles).
- Replacing cluster-tool or assisted-installer with Ansible.

## 3. Requirements

### 3.1 Functional Requirements

- **FR-1:** The repo supports multiple infrastructure backends, each in its own directory under `infra/<name>/`. Each backend uses whatever technology fits (Ansible, shell, Go, etc.). [User]
- **FR-2:** Every backend implements a standard Makefile contract with these targets: `deploy-infra` (provision the base cluster), `deploy-osac` (deploy OSAC on top), `setup-<suite>` (suite-specific infrastructure preparation, can be a no-op), `destroy-osac` (tear down OSAC only), `destroy-infra` (tear down everything), `gather` (collect diagnostics). [User]
- **FR-3:** After `deploy-osac`, the backend produces an environment file (`.env.cluster`) containing the configuration tests need to run. Required variables: `KUBECONFIG`, `OSAC_NAMESPACE`. Suite-specific required variables: `OSAC_VM_KUBECONFIG` (VMaaS), `OSAC_PULL_SECRET_PATH` (CaaS). Optional variables with defaults: `OSAC_VM_TEMPLATE`, `OSAC_CLUSTER_TEMPLATE`, `OSAC_CLI_PATH`, `OSAC_FULFILLMENT_ADDRESS`. [User]
- **FR-4:** Backends accept component image overrides, secret file paths, and backend-specific configuration via environment variables and `EXTRA_VARS`. [User]
- **FR-5:** Each backend declares which test suites it supports via a capabilities file (`SUPPORTED_SUITES`). The system prevents running an unsupported suite/backend combination before provisioning begins. [User]
- **FR-6:** Each test suite declares its requirements via a contract file: `REQUIRED_VARS`, `OPTIONAL_VARS`, `REQUIRED_TOOLS`. The system validates the backend's `.env.cluster` against the suite's contract before running tests. [User]
- **FR-7:** Suite-specific infrastructure setup is handled by `make setup-<suite>` in the backend. For example, CaaS requires InfraEnv creation, discovery VM boot, and agent registration on the Netris backend, while VMaaS requires no additional setup on any backend. [User]
- **FR-8:** A top-level Makefile orchestrates the full flow: `make e2e INFRA=<backend> SUITE=<suite>` runs deploy-infra, deploy-osac, setup-suite, and tests in sequence. Convenience targets allow running individual phases independently (e.g., `make test-vmaas` for just tests, `make redeploy-osac` for OSAC iteration). [User]
- **FR-9:** Three initial backends are supported: Netris (Ansible-based, supports VMaaS and CaaS), cluster-tool (shell-based, supports VMaaS, catalog, storage), and baremetal (shell-based, supports VMaaS). [User]
- **FR-10:** Test suites remain infrastructure-agnostic. Tests consume environment variables and do not contain backend-specific logic. [User]

### 3.2 Non-Functional Requirements

- **NFR-1:** Adding a new infrastructure backend requires only creating a new directory under `infra/`, implementing the Makefile contract, and declaring capabilities. No changes to test code or the top-level orchestration are needed. [User]
- **NFR-2:** Adding a new test suite requires only creating a new directory under `tests/`, adding a contract file, and updating backend capabilities where applicable. No changes to infrastructure code are needed. [User]

## 4. Acceptance Criteria

- [ ] A user can run `make e2e INFRA=netris SUITE=caas` and the system provisions a Netris lab, deploys OSAC, sets up CaaS infrastructure, and runs CaaS tests.
- [ ] A user can run `make e2e INFRA=cluster-tool SUITE=vmaas` and the system boots a snapshot cluster, deploys OSAC, and runs VMaaS tests.
- [ ] A user can run `make deploy-infra INFRA=netris` and `make deploy-osac INFRA=netris` independently to provision the lab and deploy OSAC as separate steps.
- [ ] A user can run `make destroy-osac INFRA=netris` followed by `make deploy-osac INFRA=netris` to redeploy OSAC without reprovisioning the lab.
- [ ] A user can run `make destroy-infra INFRA=netris` to tear down the entire lab independently.
- [ ] Running `make e2e INFRA=cluster-tool SUITE=caas` fails early with a clear message that cluster-tool does not support CaaS.
- [ ] Running a test suite against a backend that does not provide a required variable fails early with a clear message identifying the missing variable.
- [ ] A new backend can be added by creating `infra/<name>/` with a Makefile and capabilities file, without modifying any existing code.

## 5. Assumptions

- The existing Netris Ansible roles, cluster-tool binary, and assisted-installer tooling continue to work as-is and do not require modification beyond being wrapped in the new contract.
- The existing pytest test suites do not contain infrastructure-specific logic and can run against any backend that satisfies their contract.

## 6. Dependencies

- **netris-test-infra** — its Ansible roles, playbooks, inventory, and netris-lab submodule must be absorbed into the new repo structure.
- **openshift/release step registry** — Prow steps under `osac-project/netris/` must be updated to reference the unified repo.
- **osac-test-infra GitHub Actions** — existing workflows must be updated to use the new directory structure.

## 7. Risks

### 7.1 Netris submodule nesting

Absorbing netris-test-infra brings netris-lab as a nested git submodule, which can complicate cloning and CI.

- **Owner:** Dan Manor
- **Mitigation:** To be determined.
