# Test Plan — OSAC-22 Helm-based installation

## Overview

- **Public requirements:** [README.md](README.md)
- **Total test cases:** 7

Execution identifies matching assertions on OSAC main. Gaps describe remaining coverage for
the named work owner. No individual assignee or follow-up ticket is recorded here.

## Test cases

#### TC-HI-01: An isolated Kind full stack installs and reconciles API-created resources

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [README.md, lines 590-597](https://github.com/osac-project/enhancement-proposals/blob/1ce5c7c82eadc24bc920c3e57199a6686ac247bb/enhancements/OSAC-22-helm-based-installation/README.md#L590-L597)
- **Dependencies:** Real Kind API, Helm, fulfillment, operator, AAP, bundled PostgreSQL and Keycloak; fixture tenant and configuration; OpenShift-specific prerequisites belong to TC-HI-06.
- **Gap:** Preflight Kind deliberately omits workloads. No existing installer test was identified that jointly asserts the full installation and both API-to-hub paths.

**Preconditions.** Create a fresh Kind cluster and fixture tenant with an image and network template suitable for the development profile.

1. Install prerequisites then the umbrella chart with bundled PostgreSQL and Keycloak.
2. Create ComputeInstance vm-fixture and VirtualNetwork net-fixture through the tenant API and inspect the corresponding hub resources after reconciliation.

**Expected results.** Required workloads are healthy, both resources receive IDs, and their hub resources reflect the requested specs and report reconciliation.

#### TC-HI-02: Chart rendering rejects inconsistent values

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Unit
- **Owner:** [DEV]
- **References:** [README.md, lines 576-582](https://github.com/osac-project/enhancement-proposals/blob/1ce5c7c82eadc24bc920c3e57199a6686ac247bb/enhancements/OSAC-22-helm-based-installation/README.md#L576-L582)
- **Dependencies:** Helm rendering and local synthetic values; Kubernetes and providers omitted.
- **Gap:** The installer input-validation harness tests command ordering and argument validation. No test identified for the per-chart values schema condition in this case.

**Preconditions.** Start with valid standalone component fixture values and a copy with one schema-required value removed.

1. Render both copies using the same chart and Helm version.
2. Record diagnostics and verify whether each render emits manifests.

**Expected results.** Valid values emit manifests and the invalid copy identifies the missing schema field without emitting the affected resources.

#### TC-HI-03: An upgrade preserves existing resources and runs migration

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [README.md, lines 598-601](https://github.com/osac-project/enhancement-proposals/blob/1ce5c7c82eadc24bc920c3e57199a6686ac247bb/enhancements/OSAC-22-helm-based-installation/README.md#L598-L601)
- **Dependencies:** Real Kind, Helm, fulfillment, operator, AAP and bundled PostgreSQL/Keycloak; synthetic tenant data; no production services.
- **Gap:** The Kind preflight upgrade tests only the prerequisite gate and chart revision. No full-stack version-change suite found that checks migration, updated workloads and existing API objects together.

**Preconditions.** Install version N in disposable Kind, reconcile vm-fixture and net-fixture, and record their IDs and deployed image digests.

1. Upgrade to fixture version N+1 and inspect the migration and rollout.
2. Read the two objects and create a second fixture resource through the upgraded API.

**Expected results.** The migration completes, workloads report N+1, existing IDs and desired specs are preserved, and the new resource reconciles.

#### TC-HI-04: Component charts install and provide their own smoke endpoint in Kind

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [README.md, lines 585-588](https://github.com/osac-project/enhancement-proposals/blob/1ce5c7c82eadc24bc920c3e57199a6686ac247bb/enhancements/OSAC-22-helm-based-installation/README.md#L585-L588)
- **Dependencies:** Real isolated Kind and Helm per component chart; real dependencies required by that chart; other OSAC application workloads omitted.
- **Gap:** The canonical installer test inventory contains render and preflight suites. No single verified scenario installs and smokes each component chart in isolation.

**Preconditions.** Use a fresh namespace per chart and its supported test values and prerequisites.

1. Install fulfillment, operator and AAP separately.
2. Check each chart's expected workloads or jobs and probe fulfillment health, operator readiness and AAP bootstrap completion.

**Expected results.** Each chart creates its expected resources and passes its own smoke check without a full stack installation.

#### TC-HI-05: A healthy Kind install publishes a preflight report

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [README.md, lines 585-593](https://github.com/osac-project/enhancement-proposals/blob/1ce5c7c82eadc24bc920c3e57199a6686ac247bb/enhancements/OSAC-22-helm-based-installation/README.md#L585-L593)
- **Dependencies:** Real Helm and Kind API; fixture CRDs, endpoints and Secrets stand in for prerequisites; application workloads omitted.
- **Execution:** `osac-installer/scripts/test-preflight-kind.py`
- **Evidence:** `case_healthy_install_publishes_report` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/osac-installer/scripts/test-preflight-kind.py#L270)).
- **Selector:** `uv run --script scripts/test-preflight-kind.py --context kind-osac-fixture --only case_healthy_install_publishes_report` from `osac-installer`, with disposable Kind and Helm. Source reviewed, test not run.

**Preconditions.** Create the suite's isolated Kind namespace with its synthetic prerequisite resources.

1. Install the preflight-only chart and read the retained report.
2. Inspect the report summary, selected prerequisite results and Helm release status.

**Expected results.** The release is deployed at revision 1, the report has zero blocking checks and zero failures, and the issuer, database endpoints and Kafka fixture checks pass.

#### TC-HI-06: An OpenShift installation serves tenant VM and cluster workflows

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [README.md, lines 603-617](https://github.com/osac-project/enhancement-proposals/blob/1ce5c7c82eadc24bc920c3e57199a6686ac247bb/enhancements/OSAC-22-helm-based-installation/README.md#L603-L617)
- **Dependencies:** Real isolated OpenShift 4.18 or later, Helm, AAP, RHACM, OpenShift Virtualization and deployed OSAC; synthetic tenant, instance and cluster inputs.
- **Gap:** Deployed VMaaS and CaaS suites cover separate journeys. No test found in their canonical installers or suites for this single install, hub registration, tenant setup and dual lifecycle boundary.

**Preconditions.** Use a disposable OpenShift environment with the documented operators and fixture inputs.

1. Install via Helm, register the management hub and create the fixture tenant.
2. As its tenant user, create a VM and an OpenShift cluster and observe both through readiness.

**Expected results.** The hub and tenant are registered, the VM runs, and the cluster reaches its provisioned state with observable reconciliation.

#### TC-HI-07: The preflight-only chart reports a successful upgrade on Kind

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Component integration
- **Owner:** [DEV]
- **References:** [README.md, lines 598-601](https://github.com/osac-project/enhancement-proposals/blob/1ce5c7c82eadc24bc920c3e57199a6686ac247bb/enhancements/OSAC-22-helm-based-installation/README.md#L598-L601)
- **Dependencies:** Real Helm and disposable Kind. Synthetic prerequisite CRDs, endpoint and Secret objects replace production dependencies. This fixture omits application workloads and migrations.
- **Execution:** `osac-installer/scripts/test-preflight-kind.py`
- **Evidence:** `case_upgrade_with_unchanged_prerequisites` ([source](https://github.com/osac-project/osac/blob/b778b3abffc55bad57edcd5e82d37b82a1280c90/osac-installer/scripts/test-preflight-kind.py#L289)).
- **Selector:** `uv run --script scripts/test-preflight-kind.py --context kind-osac-fixture --only case_healthy_install_publishes_report --only case_upgrade_with_unchanged_prerequisites` from `osac-installer`, with disposable Kind and Helm. Source reviewed, test not run.

**Preconditions.** Use the suite preflight-only chart and successful revision 1 from the healthy install fixture.

1. Upgrade the same fixture release while keeping its prerequisite objects unchanged.
2. Read the preflight ConfigMap summary and release revision.

**Expected results.** Helm upgrade succeeds, the report records revision 2 and action upgrade, and blocking checks remain zero.
