# Test Plan — OSAC-1191 Carbide integration

## Overview

- **Public requirements:** [README.md](README.md)
- **Total test cases:** 3

Execution identifies matching assertions on OSAC main. Gaps describe remaining coverage for
the named work owner. No individual assignee or follow-up ticket is recorded here.

## Test cases

#### TC-CB-01: The existing ClusterTemplate selects the Carbide backend

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Contract
- **Owner:** [DEV]
- **References:** [README.md, lines 117-131](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-1191-carbide-integration/README.md#L117-L131)
- **Dependencies:** Real AAP role at an isolated recording Carbide endpoint; fixture credentials and site identifiers; no real provider or registration API.
- **Gap:** No Carbide role or test entry found in the canonical AAP and CaaS test trees. The proposal defines template selection and no new API.

**Preconditions.** Use a fixture ClusterTemplate with the Carbide backend, a site and a matching hostclass.

1. Evaluate cluster_infra with the fixture template.
2. Inspect the endpoint's requested site, network and instance-type selectors.

**Expected results.** The Carbide path receives the configured selectors and the ESI backend is not invoked.

#### TC-CB-02: A Carbide cluster allocates, scales and returns fixture workers

| Priority | Automation |
|---|---|
| critical | automated |

- **Tier:** E2E
- **Owner:** [QE]
- **References:** [README.md, lines 100-127](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-1191-carbide-integration/README.md#L100-L127)
- **Dependencies:** Real deployed fulfillment, operator, AAP and isolated Carbide test provider with a synthetic agent pool; no shared resources.
- **Gap:** No Carbide-backed lifecycle in the canonical AAP/CaaS suites. Provider pool handoff is an open design question and the fixture contract needs resolution.

**Preconditions.** Prepare a fixture site with two free agents of the named instance type.

1. Create a one-worker cluster, scale to two and back to one.
2. Delete the cluster and inspect its HostedCluster, network attachments and pool.

**Expected results.** The requested workers join, the removed agent returns to the pool, and deletion removes the HostedCluster and releases resources created for this cluster.

#### TC-CB-03: Provider unavailability leaves cluster reconciliation retryable

| Priority | Automation |
|---|---|
| high | automated |

- **Tier:** Contract
- **Owner:** [DEV]
- **References:** [README.md, lines 129-139](https://github.com/osac-project/enhancement-proposals/blob/c7ac7ef9842f0960caac31ea7fe2323211ac016e/enhancements/OSAC-1191-carbide-integration/README.md#L129-L139)
- **Dependencies:** Real AAP role and recording Carbide endpoint with a controlled availability fault; deployed provider omitted.
- **Gap:** No isolated Carbide failure test found in canonical AAP/CaaS sources. The proposal specifies retry or alert but defines no Carbide-specific condition value.

**Preconditions.** Use one fixture VPC request and a provider endpoint that temporarily returns unavailable.

1. Reconcile while the endpoint is unavailable.
2. Restore the endpoint and reconcile the same desired state.

**Expected results.** Failure is observable without reporting a completed allocation. The retry converges without duplicate allocations.
