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

### 2.2 Non-Goals

- Rewriting existing Ansible roles or test code — existing implementations move as-is.
- Unifying secret management across CI systems (Vault, Prow cluster profiles).
- Embedding cluster-tool as a backend — cluster-tool is an independent OSAC project repo consumed as an external dependency, not an embedded infrastructure workflow.

## 3. Requirements

### 3.1 Functional Requirements

- **FR-1:** The repo supports multiple infrastructure backends. Each backend uses whatever technology fits (Ansible, shell, Go, etc.). [User]
- **FR-2:** Every backend implements a standard contract with these lifecycle phases: provision the base cluster, deploy OSAC, suite-specific infrastructure preparation (can be a no-op), tear down OSAC only, tear down everything, and collect diagnostics. [User]
- **FR-3:** After OSAC deployment, the backend produces a configuration containing what tests need to run: cluster access credentials, OSAC namespace, and suite-specific settings (e.g., VM cluster access for VMaaS, pull secret for CaaS). [User]
- **FR-4:** Backends accept component image overrides, secret file paths, and backend-specific configuration. [User]
- **FR-5:** Each backend declares which test suites it supports. The system prevents running an unsupported suite/backend combination before provisioning begins. [User]
- **FR-6:** Each test suite declares its requirements (required and optional configuration, required tools). The system validates the backend's output against the suite's requirements before running tests. [User]
- **FR-7:** Suite-specific infrastructure setup is handled by the backend. For example, CaaS requires InfraEnv creation, discovery VM boot, and agent registration on the Netris backend, while VMaaS requires no additional setup on any backend. [User]
- **FR-8:** A top-level orchestration runs the full E2E flow: deploy lab, deploy OSAC, suite setup, and tests in sequence. Each phase can also be run independently. [User]
- **FR-9:** The initial backend is Netris (Ansible-based, supports VMaaS and CaaS). Additional backends can be added later following the same contract. [User]
- **FR-10:** Test suites remain infrastructure-agnostic. Tests consume configuration and do not contain backend-specific logic. [User]

### 3.2 Non-Functional Requirements

- **NFR-1:** Adding a new infrastructure backend requires only implementing the contract and declaring capabilities. No changes to test code or the top-level orchestration are needed. [User]
- **NFR-2:** Adding a new test suite requires only adding the tests and declaring requirements. No changes to infrastructure code are needed. [User]

## 4. Acceptance Criteria

- [ ] A full E2E run provisions the lab, deploys OSAC, sets up suite-specific infrastructure, and runs tests end-to-end.
- [ ] Lab provisioning, OSAC deployment, suite setup, and tests can each be run as standalone steps.
- [ ] OSAC can be torn down and redeployed without reprovisioning the lab.
- [ ] The lab can be torn down independently.
- [ ] Running an unsupported suite/backend combination fails early with a clear message.
- [ ] Running a test suite against a backend that does not provide a required configuration value fails early with a clear message.
- [ ] A new backend can be added without modifying any existing test or orchestration code.

## 5. Assumptions

- The existing Netris Ansible roles and test suites continue to work as-is and do not require modification beyond being wrapped in the new contract.
- The existing pytest test suites do not contain infrastructure-specific logic and can run against any backend that satisfies their contract.
- netris-test-infra remains intact during migration — content is copied, not moved, until the unified repo is proven.

## 6. Dependencies

- **netris-test-infra** — its Ansible roles, playbooks, inventory, and netris-lab submodule must be copied into the new repo structure.
- **cluster-tool** — consumed as an external dependency, not embedded.
- **openshift/release step registry** — Prow steps under `osac-project/netris/` must be updated to reference the unified repo.
- **osac-test-infra GitHub Actions** — existing workflows must be updated to use the new directory structure.

## 7. Risks

### 7.1 CI downtime during migration

Updating Prow step refs and GitHub Actions workflows to point at the unified repo requires coordinated changes across osac-test-infra and openshift/release. Mistimed or partial updates can break CI for all OSAC component repos.

- **Owner:** Dan Manor
- **Mitigation:** To be determined.
